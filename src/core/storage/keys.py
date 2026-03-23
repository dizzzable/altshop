from src.core.storage.key_builder import StorageKey


class WebhookLockKey(StorageKey, prefix="webhook_lock"):
    bot_id: int
    webhook_hash: str


class LastNotifiedVersionKey(StorageKey, prefix="last_notified_version"): ...


class LastUpdateCheckAuditKey(StorageKey, prefix="last_update_check_audit"): ...


class AccessWaitListKey(StorageKey, prefix="access_wait_list"): ...


class RecentRegisteredUsersKey(StorageKey, prefix="recent_registered_users"): ...


class RecentActivityUsersKey(StorageKey, prefix="recent_activity_users"): ...


class SubscriptionRuntimeSnapshotKey(StorageKey, prefix="subscription_runtime_snapshot"):
    user_remna_id: str


class SubscriptionDeviceListSnapshotKey(StorageKey, prefix="subscription_device_list_snapshot"):
    user_remna_id: str


class SubscriptionRuntimeRefreshLockKey(StorageKey, prefix="subscription_runtime_refresh_lock"):
    user_telegram_id: int


class MarketAssetUsdQuoteKey(StorageKey, prefix="market_asset_usd_quote"):
    asset: str


class MarketUsdRubQuoteKey(StorageKey, prefix="market_usd_rub_quote"): ...
