from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from remnawave import RemnawaveSDK
from remnawave.exceptions import BadRequestError
from remnawave.models import CreateUserRequestDto, GetAllUsersResponseDto, UserResponseDto

from src.core.constants import IMPORTED_TAG
from src.core.enums import SubscriptionStatus
from src.infrastructure.database.models.dto import PlanDto, SubscriptionDto
from src.infrastructure.database.models.dto.plan import PlanSnapshotDto
from src.infrastructure.taskiq.broker import broker
from src.services.plan import PlanService
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.user import UserService


def _is_imported_or_unassigned_snapshot(snapshot: PlanSnapshotDto) -> bool:
    if snapshot.id <= 0:
        return True

    plan_tag = (snapshot.tag or "").upper()
    plan_name = (snapshot.name or "").upper()
    return plan_tag == IMPORTED_TAG or plan_name == IMPORTED_TAG


def _resolve_duration_days(plan: PlanDto, current_duration: int) -> int:
    available_duration_days = [duration.days for duration in plan.durations]
    if not available_duration_days:
        return current_duration
    if current_duration in available_duration_days:
        return current_duration
    return available_duration_days[0]


async def _assign_plan_to_subscription(
    *,
    subscription: SubscriptionDto,
    plan_id: int,
    plan: PlanDto,
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
    telegram_id: int,
) -> tuple[bool, bool, bool]:
    if subscription.status == SubscriptionStatus.DELETED:
        return False, True, False

    if not _is_imported_or_unassigned_snapshot(subscription.plan):
        return False, False, True

    if not subscription.url:
        refreshed_subscription_url = await remnawave_service.get_subscription_url(
            subscription.user_remna_id
        )
        if refreshed_subscription_url:
            subscription.url = refreshed_subscription_url

    current_duration = subscription.plan.duration if subscription.plan else 30
    resolved_duration = _resolve_duration_days(plan, current_duration)
    subscription.plan = PlanSnapshotDto.from_plan(plan, resolved_duration)
    updated_subscription = await subscription_service.update(subscription, auto_commit=False)
    if not updated_subscription:
        raise ValueError(
            f"Failed to persist subscription '{subscription.id}' update for user '{telegram_id}'"
        )

    return True, False, False


async def _assign_plan_for_user(
    *,
    plan_id: int,
    telegram_id: int,
    plan: PlanDto,
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
) -> tuple[int, int, int, int, int]:
    subscriptions = await subscription_service.get_all_by_user(telegram_id=telegram_id)
    if not subscriptions:
        return 0, 1, 0, 0, 0

    user_updated = 0
    user_skipped_deleted = 0
    user_skipped_already_assigned = 0
    user_errors = 0
    for subscription in subscriptions:
        try:
            updated, skipped_deleted, skipped_assigned = await _assign_plan_to_subscription(
                subscription=subscription,
                plan_id=plan_id,
                plan=plan,
                subscription_service=subscription_service,
                remnawave_service=remnawave_service,
                telegram_id=telegram_id,
            )
            if updated:
                user_updated += 1
            if skipped_deleted:
                user_skipped_deleted += 1
            if skipped_assigned:
                user_skipped_already_assigned += 1
        except Exception as exception:
            logger.exception(
                f"Failed to assign plan '{plan_id}' for subscription '{subscription.id}' "
                f"(user '{telegram_id}'): {exception}"
            )
            user_errors += 1

    logger.info(
        f"Bulk assignment user '{telegram_id}': total={len(subscriptions)}, "
        f"updated={user_updated}, skipped_deleted={user_skipped_deleted}, "
        f"skipped_already_assigned={user_skipped_already_assigned}, errors={user_errors}"
    )
    return user_updated, 0, user_skipped_deleted, user_skipped_already_assigned, user_errors


@broker.task
@inject(patch_module=True)
async def import_exported_users_task(
    imported_users: list[dict],
    active_internal_squads: list[UUID],
    remnawave: FromDishka[RemnawaveSDK],
) -> tuple[int, int]:
    logger.info(f"Starting import of '{len(imported_users)}' users")

    success_count = 0
    failed_count = 0

    for user in imported_users:
        try:
            username = user["username"]
            created_user = CreateUserRequestDto.model_validate(user)
            created_user.active_internal_squads = active_internal_squads
            await remnawave.users.create_user(created_user)
            success_count += 1
        except BadRequestError as error:
            logger.warning(f"User '{username}' already exists, skipping. Error: {error}")
            failed_count += 1

        except Exception as exception:
            logger.exception(f"Failed to create user '{username}' exception: {exception}")
            failed_count += 1

    logger.info(f"Import completed: '{success_count}' successful, '{failed_count}' failed")
    return success_count, failed_count


@broker.task
@inject(patch_module=True)
async def sync_all_users_from_panel_task(
    remnawave: FromDishka[RemnawaveSDK],
    remnawave_service: FromDishka[RemnawaveService],
    user_service: FromDishka[UserService],
) -> dict[str, int | list[int]]:
    all_remna_users = await _fetch_all_panel_users(remnawave)
    bot_users = await user_service.get_all()

    logger.info(f"Total users in panel: '{len(all_remna_users)}'")
    logger.info(f"Total users in bot: '{len(bot_users)}'")

    grouped_remna_users, missing_telegram = _group_profiles_by_telegram_id(all_remna_users)

    logger.info(
        f"Prepared '{len(grouped_remna_users)}' telegram_id group(s) for synchronization "
        f"from '{len(all_remna_users)}' panel profile(s)"
    )

    added_users, added_subscription, updated, errors = await _sync_grouped_profiles(
        grouped_remna_users=grouped_remna_users,
        remnawave_service=remnawave_service,
    )

    result: dict[str, int | list[int]] = {
        "total_panel_users": len(all_remna_users),
        "total_bot_users": len(bot_users),
        "added_users": added_users,
        "added_subscription": added_subscription,
        "updated": updated,
        "errors": errors,
        "missing_telegram": missing_telegram,
        "synced_telegram_ids": sorted(grouped_remna_users.keys()),
    }

    logger.info(f"Sync users summary: '{result}'")
    return result


async def _fetch_all_panel_users(
    remnawave: RemnawaveSDK,
    page_size: int = 50,
) -> list[UserResponseDto]:
    all_remna_users: list[UserResponseDto] = []
    start = 0

    while True:
        response = await remnawave.users.get_all_users(start=start, size=page_size)
        if not isinstance(response, GetAllUsersResponseDto) or not response.users:
            return all_remna_users

        all_remna_users.extend(response.users)
        start += len(response.users)
        if len(response.users) < page_size:
            return all_remna_users


def _group_profiles_by_telegram_id(
    remna_users: list[UserResponseDto],
) -> tuple[dict[int, list[UserResponseDto]], int]:
    missing_telegram = 0
    grouped_remna_users: dict[int, list[UserResponseDto]] = {}

    for remna_user in remna_users:
        telegram_id = _parse_telegram_id(remna_user)
        if telegram_id is None:
            missing_telegram += 1
            continue

        grouped_remna_users.setdefault(telegram_id, []).append(remna_user)

    return grouped_remna_users, missing_telegram


def _parse_telegram_id(remna_user: UserResponseDto) -> int | None:
    if not remna_user.telegram_id:
        return None

    try:
        telegram_id = int(remna_user.telegram_id)
    except (TypeError, ValueError):
        logger.warning(
            f"Skipping panel profile '{remna_user.uuid}': invalid telegram_id "
            f"'{remna_user.telegram_id}'"
        )
        return None

    if telegram_id <= 0:
        logger.warning(
            f"Skipping panel profile '{remna_user.uuid}': invalid telegram_id "
            f"'{remna_user.telegram_id}'"
        )
        return None

    return telegram_id


async def _sync_grouped_profiles(
    *,
    grouped_remna_users: dict[int, list[UserResponseDto]],
    remnawave_service: RemnawaveService,
) -> tuple[int, int, int, int]:
    added_users = 0
    added_subscription = 0
    updated = 0
    errors = 0

    for telegram_id, remna_profiles in grouped_remna_users.items():
        try:
            stats = await remnawave_service.sync_profiles_by_telegram_id(
                telegram_id=telegram_id,
                remna_users=remna_profiles,
                preserve_current=True,
            )
        except Exception as exception:
            logger.exception(
                f"Error syncing user group '{telegram_id}' with "
                f"'{len(remna_profiles)}' profile(s): {exception}"
            )
            errors += 1
            continue

        if stats.user_created:
            added_users += 1
        added_subscription += stats.subscriptions_created
        updated += stats.subscriptions_updated
        errors += stats.errors

    return added_users, added_subscription, updated, errors


@broker.task
@inject(patch_module=True)
async def assign_plan_to_synced_users_task(
    plan_id: int,
    synced_telegram_ids: list[int],
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> dict[str, int]:
    logger.info(
        f"Starting bulk plan assignment for '{len(synced_telegram_ids)}' user(s), "
        f"plan_id='{plan_id}'"
    )

    plan = await plan_service.get(plan_id)
    if not plan:
        raise ValueError(f"Plan '{plan_id}' not found")

    updated = 0
    skipped_no_subscription = 0
    skipped_deleted = 0
    skipped_already_assigned = 0
    errors = 0

    for telegram_id in synced_telegram_ids:
        try:
            (
                user_updated,
                user_skipped_no_subscription,
                user_skipped_deleted,
                user_skipped_already_assigned,
                user_errors,
            ) = await _assign_plan_for_user(
                plan_id=plan_id,
                telegram_id=telegram_id,
                plan=plan,
                subscription_service=subscription_service,
                remnawave_service=remnawave_service,
            )
            updated += user_updated
            skipped_no_subscription += user_skipped_no_subscription
            skipped_deleted += user_skipped_deleted
            skipped_already_assigned += user_skipped_already_assigned
            errors += user_errors
        except Exception as exception:
            logger.exception(
                f"Failed to assign plan '{plan_id}' for user '{telegram_id}': {exception}"
            )
            errors += 1

    if updated:
        await subscription_service.uow.commit()

    result = {
        "updated": updated,
        "skipped_no_subscription": skipped_no_subscription,
        "skipped_deleted": skipped_deleted,
        "skipped_already_assigned": skipped_already_assigned,
        "errors": errors,
    }
    logger.info(f"Bulk plan assignment completed: '{result}'")
    return result
