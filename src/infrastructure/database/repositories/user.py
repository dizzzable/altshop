import secrets
import string
from typing import Any, Optional

from sqlalchemy import func, or_, select, text, update

from src.core.enums import UserRole
from src.infrastructure.database.models.sql import User

from .base import BaseRepository


class UserRepository(BaseRepository):
    async def create(self, user: User) -> User:
        return await self.create_instance(user)

    async def get(self, telegram_id: int) -> Optional[User]:
        return await self._get_one(User, User.telegram_id == telegram_id)

    async def get_for_update(self, telegram_id: int) -> Optional[User]:
        query = select(User).where(User.telegram_id == telegram_id).with_for_update()
        result = await self.session.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_by_ids(self, telegram_ids: list[int]) -> list[User]:
        return await self._get_many(User, User.telegram_id.in_(telegram_ids))

    async def get_by_partial_name(self, query: str) -> list[User]:
        search_pattern = f"%{query.lower()}%"
        conditions = [
            func.lower(User.name).like(search_pattern),
            func.lower(User.username).like(search_pattern),
        ]
        return await self._get_many(User, or_(*conditions))

    async def get_by_referral_code(self, referral_code: str) -> Optional[User]:
        return await self._get_one(User, User.referral_code == referral_code)

    async def get_all(self) -> list[User]:
        return await self._get_many(User)

    async def update(self, telegram_id: int, **data: Any) -> Optional[User]:
        return await self._update(User, User.telegram_id == telegram_id, **data)

    async def set_rules_accepted_for_non_privileged(self, accepted: bool) -> int:
        query = (
            update(User)
            .where(User.role.notin_([UserRole.DEV, UserRole.ADMIN]))
            .values(is_rules_accepted=accepted)
        )
        result = await self.session.execute(query)
        return self._rowcount(result)

    async def delete(self, telegram_id: int) -> bool:
        return bool(await self._delete(User, User.telegram_id == telegram_id))

    async def count(self) -> int:
        return await self._count(User)

    async def get_min_telegram_id(self) -> Optional[int]:
        query = text("SELECT MIN(telegram_id) FROM users")
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def filter_by_role(self, role: UserRole) -> list[User]:
        return await self._get_many(User, User.role == role)

    async def filter_by_blocked(self, blocked: bool) -> list[User]:
        return await self._get_many(User, User.is_blocked == blocked)

    async def has_material_data(self, telegram_id: int, *, include_referrals: bool = True) -> bool:
        referrals_clause = (
            "OR EXISTS(SELECT 1 FROM referrals r "
            "WHERE r.referrer_telegram_id = :telegram_id OR r.referred_telegram_id = :telegram_id)"
            "OR EXISTS(SELECT 1 FROM referral_invites ri "
            "WHERE ri.inviter_telegram_id = :telegram_id)"
            if include_referrals
            else ""
        )
        query = text(
            f"""
            SELECT (
                EXISTS(
                    SELECT 1 FROM subscriptions s
                    WHERE s.user_telegram_id = :telegram_id AND s.status <> 'DELETED'
                )
                OR EXISTS(
                    SELECT 1 FROM transactions t WHERE t.user_telegram_id = :telegram_id
                )
                OR EXISTS(
                    SELECT 1 FROM promocode_activations pa
                    WHERE pa.user_telegram_id = :telegram_id
                )
                {referrals_clause}
                OR EXISTS(
                    SELECT 1 FROM referral_rewards rr WHERE rr.user_telegram_id = :telegram_id
                )
                OR EXISTS(SELECT 1 FROM partners p WHERE p.user_telegram_id = :telegram_id)
                OR EXISTS(
                    SELECT 1 FROM partner_transactions pt
                    WHERE pt.referral_telegram_id = :telegram_id
                )
                OR EXISTS(
                    SELECT 1 FROM partner_referrals pr
                    WHERE pr.referral_telegram_id = :telegram_id
                )
                OR EXISTS(
                    SELECT 1 FROM user_notification_events une
                    WHERE une.user_telegram_id = :telegram_id
                )
                OR EXISTS(
                    SELECT 1 FROM users u
                    WHERE u.telegram_id = :telegram_id
                      AND (
                          u.points <> 0
                          OR u.personal_discount <> 0
                          OR u.purchase_discount <> 0
                      )
                )
            ) AS has_data
            """
        )
        result = await self.session.execute(query, {"telegram_id": telegram_id})
        return bool(result.scalar_one_or_none())

    async def reassign_telegram_id_references(
        self, source_telegram_id: int, target_telegram_id: int
    ) -> None:
        params = {
            "source": source_telegram_id,
            "target": target_telegram_id,
        }
        statements = [
            (
                "UPDATE subscriptions "
                "SET user_telegram_id = :target WHERE user_telegram_id = :source"
            ),
            (
                "UPDATE transactions "
                "SET user_telegram_id = :target WHERE user_telegram_id = :source"
            ),
            (
                "UPDATE promocode_activations "
                "SET user_telegram_id = :target WHERE user_telegram_id = :source"
            ),
            (
                "UPDATE referral_rewards "
                "SET user_telegram_id = :target WHERE user_telegram_id = :source"
            ),
            (
                "UPDATE partners "
                "SET user_telegram_id = :target WHERE user_telegram_id = :source"
            ),
            (
                "UPDATE partner_transactions "
                "SET referral_telegram_id = :target WHERE referral_telegram_id = :source"
            ),
            (
                "UPDATE partner_referrals "
                "SET referral_telegram_id = :target WHERE referral_telegram_id = :source"
            ),
            (
                "UPDATE user_notification_events "
                "SET user_telegram_id = :target WHERE user_telegram_id = :source"
            ),
            (
                "UPDATE referral_invites "
                "SET inviter_telegram_id = :target WHERE inviter_telegram_id = :source"
            ),
        ]
        for statement in statements:
            await self.session.execute(text(statement), params)

        # Update referrer links first, avoid creating self-referral rows.
        await self.session.execute(
            text(
                """
                UPDATE referrals
                SET referrer_telegram_id = :target
                WHERE referrer_telegram_id = :source
                  AND referred_telegram_id <> :target
                """
            ),
            params,
        )
        await self.session.execute(
            text(
                """
                DELETE FROM referrals
                WHERE referrer_telegram_id = :target
                  AND referred_telegram_id = :target
                """
            ),
            params,
        )

        # Merge source/target attribution rows before moving the "referred" side so the
        # unique referred_telegram_id constraint is preserved and the earliest referral wins.
        await self.session.execute(
            text(
                """
                WITH source_ref AS (
                    SELECT id, created_at
                    FROM referrals
                    WHERE referred_telegram_id = :source
                    ORDER BY created_at ASC, id ASC
                    LIMIT 1
                ),
                target_ref AS (
                    SELECT id, created_at
                    FROM referrals
                    WHERE referred_telegram_id = :target
                    ORDER BY created_at ASC, id ASC
                    LIMIT 1
                ),
                decision AS (
                    SELECT
                        CASE
                            WHEN s.id IS NULL THEN t.id
                            WHEN t.id IS NULL THEN s.id
                            WHEN s.created_at < t.created_at
                                OR (s.created_at = t.created_at AND s.id < t.id)
                                THEN s.id
                            ELSE t.id
                        END AS keep_id,
                        CASE
                            WHEN s.id IS NULL OR t.id IS NULL THEN NULL
                            WHEN s.created_at < t.created_at
                                OR (s.created_at = t.created_at AND s.id < t.id)
                                THEN t.id
                            ELSE s.id
                        END AS drop_id
                    FROM source_ref s
                    FULL OUTER JOIN target_ref t ON TRUE
                )
                UPDATE referral_rewards rr
                SET referral_id = d.keep_id
                FROM decision d
                WHERE d.drop_id IS NOT NULL
                  AND rr.referral_id = d.drop_id
                """
            ),
            params,
        )
        await self.session.execute(
            text(
                """
                WITH source_ref AS (
                    SELECT id, created_at
                    FROM referrals
                    WHERE referred_telegram_id = :source
                    ORDER BY created_at ASC, id ASC
                    LIMIT 1
                ),
                target_ref AS (
                    SELECT id, created_at
                    FROM referrals
                    WHERE referred_telegram_id = :target
                    ORDER BY created_at ASC, id ASC
                    LIMIT 1
                ),
                decision AS (
                    SELECT
                        CASE
                            WHEN s.id IS NULL THEN t.id
                            WHEN t.id IS NULL THEN s.id
                            WHEN s.created_at < t.created_at
                                OR (s.created_at = t.created_at AND s.id < t.id)
                                THEN s.id
                            ELSE t.id
                        END AS keep_id,
                        CASE
                            WHEN s.id IS NULL OR t.id IS NULL THEN NULL
                            WHEN s.created_at < t.created_at
                                OR (s.created_at = t.created_at AND s.id < t.id)
                                THEN t.id
                            ELSE s.id
                        END AS drop_id
                    FROM source_ref s
                    FULL OUTER JOIN target_ref t ON TRUE
                )
                DELETE FROM referrals r
                USING decision d
                WHERE d.drop_id IS NOT NULL
                  AND r.id = d.drop_id
                """
            ),
            params,
        )

        # Move "referred" side and keep first-touch attribution by earliest created_at.
        await self.session.execute(
            text(
                """
                UPDATE referrals
                SET referred_telegram_id = :target
                WHERE referred_telegram_id = :source
                  AND referrer_telegram_id <> :target
                """
            ),
            params,
        )
        await self.session.execute(
            text(
                """
                WITH ranked AS (
                    SELECT
                        r.id,
                        ROW_NUMBER() OVER (
                            PARTITION BY r.referred_telegram_id
                            ORDER BY r.created_at ASC, r.id ASC
                        ) AS row_num,
                        FIRST_VALUE(r.id) OVER (
                            PARTITION BY r.referred_telegram_id
                            ORDER BY r.created_at ASC, r.id ASC
                        ) AS keep_id
                    FROM referrals r
                    WHERE r.referred_telegram_id = :target
                ),
                duplicates AS (
                    SELECT id, keep_id
                    FROM ranked
                    WHERE row_num > 1
                )
                UPDATE referral_rewards rr
                SET referral_id = d.keep_id
                FROM duplicates d
                WHERE rr.referral_id = d.id
                """
            ),
            params,
        )
        await self.session.execute(
            text(
                """
                WITH ranked AS (
                    SELECT
                        r.id,
                        ROW_NUMBER() OVER (
                            PARTITION BY r.referred_telegram_id
                            ORDER BY r.created_at ASC, r.id ASC
                        ) AS row_num
                    FROM referrals r
                    WHERE r.referred_telegram_id = :target
                )
                DELETE FROM referrals r
                USING ranked d
                WHERE r.id = d.id
                  AND d.row_num > 1
                """
            ),
            params,
        )

    async def generate_unique_referral_code(self, length: int = 8) -> str:
        """Generate a unique referral code."""
        alphabet = string.ascii_uppercase + string.digits

        for _ in range(10):  # Try up to 10 times
            code = "".join(secrets.choice(alphabet) for _ in range(length))
            existing = await self.get_by_referral_code(code)
            if not existing:
                return code

        # Fallback: use longer code
        return "".join(secrets.choice(alphabet) for _ in range(length + 4))
