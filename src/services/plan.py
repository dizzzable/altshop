from typing import Optional, Sequence

from loguru import logger

from src.core.enums import ArchivedPlanRenewMode, PlanAvailability
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import PlanDto, UserDto
from src.infrastructure.database.models.sql import Plan, PlanDuration, PlanPrice


class PlanValidationError(ValueError):
    pass


class PlanDeletionBlockedError(ValueError):
    def __init__(self, *, plan_id: int) -> None:
        super().__init__(
            "Plan is referenced by subscriptions or transition rules. Archive it instead."
        )
        self.plan_id = plan_id


# TODO: Implement logic for plan availability for specific gateways
# TODO: Implement general discount for plan
class PlanService:
    uow: UnitOfWork

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def create(self, plan: PlanDto) -> PlanDto:
        await self._validate_for_persist(plan)

        existing_plan = await self.get_by_name(plan.name)
        if existing_plan:
            raise PlanValidationError(f"Plan with name '{plan.name}' already exists")

        order_index = await self.uow.repository.plans.get_max_index()
        order_index = (order_index or 0) + 1
        plan.order_index = order_index

        db_plan = self._dto_to_model(plan)
        db_created_plan = await self.uow.repository.plans.create(db_plan)
        await self.uow.commit()
        logger.info(f"Created plan '{plan.name}' with ID '{db_created_plan.id}'")
        return PlanDto.from_model(db_created_plan)  # type: ignore[return-value]

    async def get(self, plan_id: int) -> Optional[PlanDto]:
        db_plan = await self.uow.repository.plans.get(plan_id)

        if db_plan:
            logger.debug(f"Retrieved plan '{plan_id}'")
        else:
            logger.warning(f"Plan '{plan_id}' not found")

        return PlanDto.from_model(db_plan)

    async def get_by_name(self, plan_name: str) -> Optional[PlanDto]:
        db_plan = await self.uow.repository.plans.get_by_name(plan_name)

        if db_plan:
            logger.debug(f"Retrieved plan by name '{plan_name}'")
        else:
            logger.warning(f"Plan with name '{plan_name}' not found")

        return PlanDto.from_model(db_plan)

    async def get_by_tag(self, tag: str) -> Optional[PlanDto]:
        db_plan = await self.uow.repository.plans.get_by_tag(tag)

        if db_plan:
            logger.debug(f"Retrieved plan by tag '{tag}'")
        else:
            logger.debug(f"Plan with tag '{tag}' not found")

        return PlanDto.from_model(db_plan)

    async def get_all(self) -> list[PlanDto]:
        db_plans = await self.uow.repository.plans.get_all()
        logger.debug(f"Retrieved '{len(db_plans)}' plans")
        return PlanDto.from_model_list(db_plans)

    async def update(self, plan: PlanDto) -> Optional[PlanDto]:
        await self._validate_for_persist(plan)

        existing_plan = await self.get_by_name(plan.name)
        if existing_plan and existing_plan.id != plan.id:
            raise PlanValidationError(f"Plan with name '{plan.name}' already exists")

        db_plan = self._dto_to_model(plan)
        db_updated_plan = await self.uow.repository.plans.update(db_plan)

        if db_updated_plan:
            logger.info(f"Updated plan '{plan.name}' (ID: '{plan.id}') successfully")
        else:
            logger.warning(
                f"Attempted to update plan '{plan.name}' (ID: '{plan.id}'), "
                "but plan was not found or update failed"
            )

        return PlanDto.from_model(db_updated_plan)

    async def delete(self, plan_id: int) -> bool:
        db_plan = await self.uow.repository.plans.get(plan_id)
        if not db_plan:
            logger.warning(f"Failed to delete plan '{plan_id}'. Plan not found or deletion failed")
            return False

        subscriptions = await self.uow.repository.subscriptions.filter_by_plan_id(plan_id)
        transition_refs = await self.uow.repository.plans.get_transition_references(plan_id)
        if subscriptions or transition_refs:
            raise PlanDeletionBlockedError(plan_id=plan_id)

        result = await self.uow.repository.plans.delete(plan_id)

        if result:
            logger.info(f"Plan '{plan_id}' deleted successfully")
        else:
            logger.warning(f"Failed to delete plan '{plan_id}'. Plan not found or deletion failed")

        return result

    async def count(self) -> int:
        count = await self.uow.repository.plans.count()
        logger.debug(f"Total plans count: '{count}'")
        return count

    async def get_trial_plan(self) -> Optional[PlanDto]:
        db_plans: list[Plan] = await self.uow.repository.plans.filter_by_availability(
            availability=PlanAvailability.TRIAL
        )

        if db_plans:
            if len(db_plans) > 1:
                logger.warning(
                    f"Multiple trial plans found ({len(db_plans)}). "
                    f"Using the first one: '{db_plans[0].name}'"
                )

            db_plan = db_plans[0]

            if db_plan.is_publicly_purchasable:
                logger.debug(f"Available trial plan '{db_plans[0].name}'")
                return PlanDto.from_model(db_plans[0])

            logger.warning(f"Trial plan '{db_plans[0].name}' found but is not publicly available")

        logger.debug("No active trial plan found")
        return None

    async def get_available_plans(self, user: UserDto) -> list[PlanDto]:
        logger.debug(f"Fetching available plans for user '{user.telegram_id}'")

        db_plans: list[Plan] = await self.uow.repository.plans.filter_publicly_purchasable()
        logger.debug(f"Total active plans retrieved: '{len(db_plans)}'")
        db_filtered_plans = self._filter_plans_for_user(db_plans=db_plans, user=user)
        logger.info(
            f"Available plans filtered: '{len(db_filtered_plans)}' for user '{user.telegram_id}'"
        )
        return PlanDto.from_model_list(db_filtered_plans)

    async def get_purchase_available_plans_by_ids(
        self,
        *,
        user: UserDto,
        plan_ids: Sequence[int],
    ) -> list[PlanDto]:
        if not plan_ids:
            return []

        db_plans = await self.uow.repository.plans.get_by_ids(plan_ids)
        db_filtered_plans = self._filter_plans_for_user(
            db_plans=[plan for plan in db_plans if plan.is_publicly_purchasable],
            user=user,
        )
        return PlanDto.from_model_list(db_filtered_plans)

    async def get_assignable_active_plans(self) -> list[PlanDto]:
        db_plans = await self.uow.repository.plans.filter_assignable_active()
        return PlanDto.from_model_list(db_plans)

    async def get_allowed_plans(self) -> list[PlanDto]:
        db_plans: list[Plan] = await self.uow.repository.plans.filter_by_availability(
            availability=PlanAvailability.ALLOWED,
        )

        if db_plans:
            logger.debug(
                f"Retrieved '{len(db_plans)}' plans with availability '{PlanAvailability.ALLOWED}'"
            )
        else:
            logger.debug(f"No plans found with availability '{PlanAvailability.ALLOWED}'")

        return PlanDto.from_model_list(db_plans)

    async def move_plan_up(self, plan_id: int) -> bool:
        db_plans = await self.uow.repository.plans.get_all()
        db_plans.sort(key=lambda p: p.order_index)

        index = next((i for i, p in enumerate(db_plans) if p.id == plan_id), None)
        if index is None:
            logger.warning(f"Plan with ID '{plan_id}' not found for move operation")
            return False

        if index == 0:
            plan = db_plans.pop(0)
            db_plans.append(plan)
            logger.debug(f"Plan '{plan_id}' moved from top to bottom")
        else:
            db_plans[index - 1], db_plans[index] = db_plans[index], db_plans[index - 1]
            logger.debug(f"Plan '{plan_id}' moved up one position")

        for i, plan in enumerate(db_plans, start=1):
            plan.order_index = i

        logger.info(f"Plan '{plan_id}' reorder successfully")
        return True

    def _filter_plans_for_user(self, *, db_plans: list[Plan], user: UserDto) -> list[Plan]:
        db_filtered_plans: list[Plan] = []

        for db_plan in db_plans:
            match db_plan.availability:
                case PlanAvailability.ALL:
                    db_filtered_plans.append(db_plan)
                case PlanAvailability.NEW if not user.has_any_subscription:
                    logger.debug(
                        f"User {user.telegram_id} has no subscription, "
                        f"eligible for new user plan '{db_plan.name}'"
                    )
                    db_filtered_plans.append(db_plan)
                case PlanAvailability.EXISTING if user.has_any_subscription:
                    logger.debug(
                        f"User {user.telegram_id} has an existing subscription, "
                        f"eligible for existing user plan '{db_plan.name}'"
                    )
                    db_filtered_plans.append(db_plan)
                case PlanAvailability.INVITED if user.is_invited_user:
                    logger.debug(
                        f"User {user.telegram_id} was invited, "
                        f"eligible for invited user plan '{db_plan.name}'"
                    )
                    db_filtered_plans.append(db_plan)
                case PlanAvailability.ALLOWED if user.telegram_id in (
                    db_plan.allowed_user_ids or []
                ):
                    logger.debug(
                        f"User {user.telegram_id} is explicitly allowed for plan '{db_plan.name}'"
                    )
                    db_filtered_plans.append(db_plan)

        return db_filtered_plans

    async def _validate_for_persist(self, plan: PlanDto) -> None:
        self._normalize_plan_transitions(plan)
        await self._validate_trial_plan_constraints(plan)
        await self._validate_transition_targets(plan)

    def _normalize_plan_transitions(self, plan: PlanDto) -> None:
        plan.replacement_plan_ids = list(dict.fromkeys(plan.replacement_plan_ids))
        plan.upgrade_to_plan_ids = list(dict.fromkeys(plan.upgrade_to_plan_ids))

        if not plan.is_archived:
            plan.archived_renew_mode = ArchivedPlanRenewMode.SELF_RENEW
            plan.replacement_plan_ids = []

    async def _validate_trial_plan_constraints(self, plan: PlanDto) -> None:
        if plan.availability != PlanAvailability.TRIAL:
            return

        existing_trial = await self.get_trial_plan()
        if existing_trial and existing_trial.id != plan.id:
            raise PlanValidationError("Only one active trial plan is allowed")

    async def _validate_transition_targets(self, plan: PlanDto) -> None:
        transition_ids = set(plan.replacement_plan_ids) | set(plan.upgrade_to_plan_ids)

        if plan.id is not None and plan.id in transition_ids:
            raise PlanValidationError("Plan transitions cannot reference the same plan")

        if (
            plan.is_archived
            and plan.archived_renew_mode == ArchivedPlanRenewMode.REPLACE_ON_RENEW
            and not plan.replacement_plan_ids
        ):
            raise PlanValidationError(
                "Archived plans with replacement renew mode must define replacement plans"
            )

        if not transition_ids:
            return

        referenced_plans = {
            candidate.id: candidate
            for candidate in await self.uow.repository.plans.get_by_ids(list(transition_ids))
            if candidate.id is not None
        }

        missing_ids = sorted(transition_ids - set(referenced_plans))
        if missing_ids:
            raise PlanValidationError(f"Referenced plans not found: {missing_ids}")

        invalid_ids = sorted(
            plan_id
            for plan_id, referenced_plan in referenced_plans.items()
            if not referenced_plan.is_publicly_purchasable
        )
        if invalid_ids:
            raise PlanValidationError(
                f"Replacement and upgrade plans must be active public plans: {invalid_ids}"
            )

    def _dto_to_model(self, plan_dto: PlanDto) -> Plan:
        db_plan = Plan(**plan_dto.model_dump(exclude={"durations"}))

        for duration_dto in plan_dto.durations:
            db_duration = PlanDuration(**duration_dto.model_dump(exclude={"prices"}))
            db_plan.durations.append(db_duration)
            db_duration.plan = db_plan

            for price_dto in duration_dto.prices:
                db_price = PlanPrice(**price_dto.model_dump())
                db_duration.prices.append(db_price)
                db_price.plan_duration = db_duration

        return db_plan
