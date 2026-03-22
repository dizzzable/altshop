# Back
btn-back = ⬅️ Back
btn-main-menu = ↩️ Main Menu
btn-back-main-menu = ↩️ Back to Main Menu
btn-back-dashboard = ↩️ Back to Control Panel


# Remnashop
btn-remnashop-release-latest = 👀 View
btn-remnashop-how-upgrade = ❓ How to Update
btn-remnashop-github = ⭐ GitHub
btn-remnashop-telegram = 👪 Telegram
btn-remnashop-donate = 💰 Support Developer
btn-remnashop-guide = ❓ Guide


# Other
btn-rules-accept = ✅ Accept Rules
btn-channel-join = ❤️ Go to Channel
btn-channel-confirm = ✅ Confirm
btn-notification-close = ❌ Close
btn-contact-support = 📩 Contact Support

btn-squad-choice = { $selected -> 
    [1] 🔘
    *[0] ⚪
    } { $name }


# Menu
btn-menu-connect = 🚀 Connect

btn-menu-connect-not-available =
    ⚠️ { $status -> 
    [LIMITED] TRAFFIC LIMIT EXCEEDED
    [EXPIRED] SUBSCRIPTION EXPIRED
    *[OTHER] YOUR SUBSCRIPTION IS NOT WORKING
    } ⚠️

btn-menu-trial = 🎁 TRY FOR FREE
btn-menu-devices = 📱 My Devices ({ $count })
btn-menu-devices-empty = ⚠️ No Connected Devices
btn-menu-devices-subscription = { $status ->
    [ACTIVE] 🟢
    [EXPIRED] 🔴
    [LIMITED] 🟡
    [DISABLED] ⚫
    *[OTHER] ⚪
    } { $plan_name } ({ $device_count } dev.)
btn-menu-devices-get-url = 🔗 Get Link
btn-menu-subscription = 💳 Subscription ({ $count })
btn-menu-invite = 👥 Invite
btn-menu-invite-about = ❓ More About Reward
btn-menu-invite-referrals = 👥 My Referrals
btn-menu-invite-referrals-empty = ⚠️ No referrals yet
btn-menu-invite-copy = 🔗 Copy Link
btn-menu-invite-send = 📩 Invite
btn-menu-invite-qr = 🧾 QR Code
btn-menu-invite-withdraw-points = 💎 Exchange Points
btn-menu-exchange = 🎁 Rewards
btn-menu-exchange-select-type = 🔄 Select Exchange Type
btn-menu-exchange-points = ⏳ Exchange for Subscription Days
btn-menu-exchange-days = ⏳ Add Days to Subscription
btn-menu-exchange-gift = 🎁 Get Gift Promocode
btn-menu-exchange-gift-select-plan = 📦 Select Plan
btn-menu-exchange-discount = 💸 Get Discount
btn-menu-exchange-traffic = 🌐 Add Traffic
btn-menu-exchange-points-confirm = ✅ Confirm Exchange
btn-menu-exchange-gift-confirm = 🎁 Get Promocode
btn-menu-exchange-discount-confirm = 💸 Get { $discount_percent }% Discount ({ $points_to_spend } points)
btn-menu-exchange-traffic-confirm = 🌐 Add { $traffic_gb } GB ({ $points_to_spend } points)
btn-menu-copy-promocode = 📋 Copy Promocode

btn-menu-exchange-type-choice = { $available ->
    [1] { $type ->
        [SUBSCRIPTION_DAYS] ⏳ Subscription Days
        [GIFT_SUBSCRIPTION] 🎁 Gift Subscription
        [DISCOUNT] 💸 Purchase Discount
        [TRAFFIC] 🌐 Extra Traffic
        *[OTHER] { $type }
        }
    *[0] ❌ { $type ->
        [SUBSCRIPTION_DAYS] Subscription Days (unavailable)
        [GIFT_SUBSCRIPTION] Gift Subscription (unavailable)
        [DISCOUNT] Discount (unavailable)
        [TRAFFIC] Traffic (unavailable)
        *[OTHER] { $type }
        }
    }
btn-menu-support = 🆘 Support
btn-menu-dashboard = 🛠 Control Panel


# Dashboard
btn-dashboard-statistics = 📊 Statistics
btn-dashboard-users = 👥 Users
btn-dashboard-broadcast = 📢 Broadcast
btn-dashboard-promocodes = 🎟 Promocodes
btn-dashboard-access = 🔓 Access Mode
btn-dashboard-remnawave = 🌊 RemnaWave
btn-dashboard-remnashop = 🛍 AltShop
btn-dashboard-importer = 📥 Import Users


# Statistics
btn-statistics-page =
    { $target_page1 ->
    [1] 👥
    [2] 🧾
    [3] 💳
    [4] 📦
    [5] 🎁
    [6] 👪
    *[OTHER] page
    }

btn-statistics-current-page =
    { $current_page1 ->
    [1] [👥]
    [2] [🧾]
    [3] [💳]
    [4] [📦]
    [5] [🎁]
    [6] [👪]
    *[OTHER] [page]
    }


# Users
btn-users-search = 🔍 Search User
btn-users-recent-registered = 🆕 Recently Registered
btn-users-recent-activity = 📝 Recent Activity
btn-users-blacklist = 🚫 Blacklist
btn-users-referrals = 👥 All Invited
btn-users-unblock-all = 🔓 Unblock All


# User
btn-user-discount = 💸 Personal Discount
btn-user-purchase-discount = 🛒 Next Purchase Discount
btn-user-points = 💎 Change Points
btn-user-statistics = 📊 Statistics
btn-user-message = 📩 Message
btn-user-role = 👮‍♂️ Change Role
btn-user-transactions = 🧾 Transactions
btn-user-referrals = 👥 Invited Users
btn-user-give-access = 🔑 Plan Access
btn-user-current-subscription = 💳 Current Subscription
btn-user-subscriptions = 💳 { $count ->
    [1] Subscription ({ $count })
    *[other] Subscriptions ({ $count })
    }
btn-user-subscription-choice = { $is_current ->
    [1] ⭐
    *[0] ▫️
    } { $status ->
    [ACTIVE] 🟢
    [EXPIRED] 🔴
    [LIMITED] 🟠
    [DISABLED] 🚫
    *[other] ⚪
    } { $device_name } - { $expire_time }
btn-user-subscription-traffic-limit = 🌐 Traffic Limit
btn-user-subscription-device-limit = 📱 Device Limit
btn-user-subscription-expire-time = ⏳ Expiry Time
btn-user-subscription-squads = 🔗 Squads
btn-user-subscription-traffic-reset = 🔄 Reset Traffic
btn-user-subscription-devices = 🧾 Device List
btn-user-subscription-url = 📋 Copy Link
btn-user-subscription-set = ✅ Set Subscription
btn-user-subscription-delete = ❌ Delete
btn-user-message-preview = 👀 Preview
btn-user-message-confirm = ✅ Send
btn-user-sync = 🌀 Synchronize
btn-user-give-subscription = 🎁 Give Subscription
btn-user-subscription-internal-squads = ⏺️ Internal Squads
btn-user-subscription-external-squads = ⏹️ External Squad

btn-user-allowed-plan-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $plan_name }

btn-user-subscription-active-toggle = { $is_active ->
    [1] 🔴 Disable
    *[0] 🟢 Enable
    }

btn-user-transaction = { $status ->
    [PENDING] 🕓
    [COMPLETED] ✅
    [CANCELED] ❌
    [REFUNDED] 💸
    [FAILED] ⚠️
    *[OTHER] { $status }
} { $created_at }

btn-user-block = { $is_blocked ->
    [1] 🔓 Unblock
    *[0] 🔒 Block
    }

btn-user-partner = 👾 Partner
btn-user-partner-balance = 💰 Adjust Balance
btn-user-partner-create = ✅ Grant Partner Access
btn-user-partner-toggle = { $is_active ->
    [1] 🔴 Deactivate
    *[0] 🟢 Activate
    }
btn-user-partner-delete = ❌ Delete Partner Access
btn-user-partner-withdrawals = 💸 Withdrawal Requests
btn-user-partner-withdrawal = { $status ->
    [PENDING] 🕓
    [APPROVED] ✅
    [REJECTED] ❌
    *[OTHER] { $status }
    } { $amount } - { $created_at }
btn-user-partner-withdrawal-approve = ✅ Approve
btn-user-partner-withdrawal-reject = ❌ Reject
btn-user-partner-settings = ⚙️ Individual Settings
btn-user-partner-use-global = { $use_global ->
    [1] 🔘 Global Settings
    *[0] ⚪ Individual Settings
    }
btn-user-partner-accrual-strategy = 📍 Accrual Condition
btn-user-partner-reward-type = 🎀 Reward Type
btn-user-partner-percents = 📊 Level Percentages
btn-user-partner-fixed-amounts = 💰 Fixed Amounts
btn-user-partner-accrual-strategy-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $strategy ->
    [ON_FIRST_PAYMENT] 💳 First Payment Only
    [ON_EACH_PAYMENT] 💸 Every Payment
    *[OTHER] { $strategy }
    }
btn-user-partner-reward-type-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $reward_type ->
    [PERCENT] 📊 Percentage of Payment
    [FIXED_AMOUNT] 💰 Fixed Amount
    *[OTHER] { $reward_type }
    }
btn-user-partner-level-percent = { $level ->
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $level }
    } level: { $percent }%
btn-user-partner-level-fixed = { $level ->
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $level }
    } level: { $amount } rubles


# Broadcast
btn-broadcast-list = 📄 All Broadcasts
btn-broadcast-all = 👥 Everyone
btn-broadcast-plan = 📦 By Plan
btn-broadcast-subscribed = ✅ With Subscription
btn-broadcast-unsubscribed = ❌ Without Subscription
btn-broadcast-expired = ⌛ Expired
btn-broadcast-trial = ✳️ With Trial
btn-broadcast-content = ✉️ Edit Content
btn-broadcast-buttons = ✳️ Edit Buttons
btn-broadcast-promocode-toggle = { $enabled ->
    [1] 🎟 Promo button: ON
    *[0] 🎟 Promo button: OFF
    }
btn-broadcast-promocode-code = 🎟 Promo code: { $code }
btn-broadcast-promocode-clear = 🧹 Clear promo code
btn-broadcast-preview = 👀 Preview
btn-broadcast-confirm = ✅ Start Broadcast
btn-broadcast-refresh = 🔄 Refresh Data
btn-broadcast-viewing = 👀 View
btn-broadcast-cancel = ⛔ Stop Broadcast
btn-broadcast-delete = ❌ Delete Sent Messages

btn-broadcast-button-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    }

btn-broadcast =  { $status ->
    [PROCESSING] ⏳
    [COMPLETED] ✅
    [CANCELED] ⛔
    [DELETED] ❌
    [ERROR] ⚠️
    *[OTHER] { $status }
} { $created_at }


# Go to
btn-goto-subscription = 💳 Buy Subscription
btn-goto-promocode = 🎟 Activate Promocode
btn-goto-subscription-renew = 🔄 Renew Subscription
btn-goto-user-profile = 👤 Go to User


# Promocodes
btn-promocodes-list = 📃 Promocode List
btn-promocodes-search = 🔍 Search Promocode
btn-promocodes-create = 🆕 Create
btn-promocodes-delete = 🗑️ Delete
btn-promocodes-edit = ✏️ Edit


# Access
btn-access-mode = { access-mode }
btn-access-conditions = ⚙️ Access Conditions
btn-access-rules = ✳️ Accept Rules
btn-access-channel = ❇️ Channel Subscription

btn-access-condition-toggle = { $enabled ->
    [1] 🔘 Enabled
    *[0] ⚪ Disabled
    }


# RemnaShop
btn-remnashop-admins = 👮‍♂️ Administrators
btn-remnashop-gateways = 🌐 Payment Systems
btn-remnashop-referral = 👥 Referral System
btn-remnashop-partner = 👾 Partner Program
btn-remnashop-withdrawal-requests = 📝 Withdrawal Requests ({ $count })
btn-remnashop-advertising = 🎯 Advertising
btn-remnashop-plans = 📦 Plans
btn-remnashop-notifications = 🔔 Notifications
btn-remnashop-banners = 🖼️ Banners
btn-remnashop-logs = 📄 Logs
btn-remnashop-audit = 🔍 Audit
btn-remnashop-multi-subscription = 📦 Multi-Subscription
btn-remnashop-branding = 🎨 Branding

# Multi Subscription
btn-multi-subscription-toggle = { $is_enabled ->
    [1] 🟢 Enabled
    *[0] 🔴 Disabled
    }
btn-multi-subscription-max = 🔢 Max Subscriptions ({ $default_max ->
    [-1] ∞
    *[other] { $default_max }
    })

btn-user-max-subscriptions = 📦 Subscription Limit
btn-user-max-subscriptions-use-global = { $use_global ->
    [1] 🔘 Global Settings
    *[0] ⚪ Individual Settings
    }

# Banners
btn-banner-item = 🖼️ { $name }
btn-banner-locale-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $locale }
btn-banner-upload = 📤 Upload
btn-banner-delete = 🗑️ Delete
btn-banner-confirm-delete = ❌ Confirm Deletion


# Gateways
btn-gateway-title = { gateway-type }
btn-gateways-setting = { $field }
btn-gateways-webhook-copy = 📋 Copy Webhook

btn-gateway-active = { $is_active ->
    [1] 🟢 Enabled
    *[0] 🔴 Disabled
    }

btn-gateway-test = 🐞 Test
btn-gateways-default-currency = 💸 Default Currency
btn-gateways-placement = 🔢 Change Positioning

btn-gateways-default-currency-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $symbol } { $currency }


# Referral
btn-referral-level = 🔢 Level
btn-referral-reward-type = 🎀 Reward Type
btn-referral-accrual-strategy = 📍 Accrual Condition
btn-referral-reward-strategy = ⚖️ Reward Calculation
btn-referral-reward = 🎁 Reward
btn-referral-eligible-plans = 📦 Plans for Rewards
btn-referral-clear-filter = 🗑️ Clear Filter
btn-referral-points-exchange = 💎 Points Exchange Settings
btn-referral-exchange-enable = { $exchange_enabled ->
    [1] 🟢 Exchange Enabled
    *[0] 🔴 Exchange Disabled
    }
btn-referral-exchange-types = 🔄 Exchange Types ({ $enabled_types_count })
btn-referral-points-per-day = 📊 Exchange Rate ({ $points_per_day } point = 1 day)
btn-referral-min-exchange = ⬇️ Min. Points ({ $min_exchange_points })
btn-referral-max-exchange = ⬆️ Max. Points ({ $max_exchange_points ->
    [-1] ∞
    *[other] { $max_exchange_points }
    })

btn-referral-exchange-type-choice = { $enabled ->
    [1] 🟢
    *[0] 🔴
    } { $type ->
    [SUBSCRIPTION_DAYS] ⏳ Subscription Days
    [GIFT_SUBSCRIPTION] 🎁 Gift Subscription
    [DISCOUNT] 💸 Purchase Discount
    [TRAFFIC] 🌐 Extra Traffic
    *[OTHER] { $type }
    }

btn-referral-exchange-type-enable = { $enabled ->
    [1] 🟢 Enabled
    *[0] 🔴 Disabled
    }

btn-referral-exchange-type-cost = 💰 Cost ({ $points_cost } points)
btn-referral-exchange-type-min = ⬇️ Min. Points ({ $min_points })
btn-referral-exchange-type-max = ⬆️ Max. Points ({ $max_points ->
    [-1] ∞
    *[other] { $max_points }
    })

btn-referral-gift-plan = 📦 Plan ({ $gift_plan_name })
btn-referral-gift-duration = ⏳ Duration ({ $gift_duration_days } days)
btn-referral-discount-max = 💸 Max. Discount ({ $max_discount_percent }%)
btn-referral-traffic-max = 🌐 Max. Traffic ({ $max_traffic_gb } GB)

btn-referral-gift-plan-choice = { $selected ->
    [1] ✅
    *[0] ⬜
    } { $is_active ->
    [1] 🟢
    *[0] 🔴
    } { $plan_name }

btn-referral-eligible-plan-choice = { $selected ->
    [1] ✅
    *[0] ⬜
    } { $is_active ->
    [1] 🟢
    *[0] 🔴
    } { $plan_name }

btn-referral-enable = { $is_enable -> 
    [1] 🟢 Enabled
    *[0] 🔴 Disabled
    }

btn-referral-level-choice = { $type -> 
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $type }
    }

btn-referral-reward-choice = { $type -> 
    [POINTS] 💎 Points
    [EXTRA_DAYS] ⏳ Days
    *[OTHER] { $type }
    }

btn-referral-accrual-strategy-choice = { $type -> 
    [ON_FIRST_PAYMENT] 💳 First Payment
    [ON_EACH_PAYMENT] 💸 Every Payment
    *[OTHER] { $type }
    }

btn-referral-reward-strategy-choice = { $type -> 
    [AMOUNT] 🔸 Fixed
    [PERCENT] 🔹 Percentage
    *[OTHER] { $type }
    }


# Notifications
btn-notifications-user = 👥 User

btn-notifications-user-choice = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } { $type ->
    [EXPIRES_IN_3_DAYS] Subscription Expiring (3 days)
    [EXPIRES_IN_2_DAYS] Subscription Expiring (2 days)
    [EXPIRES_IN_1_DAYS] Subscription Expiring (1 day)
    [EXPIRED] Subscription Expired
    [LIMITED] Traffic Exhausted
    [EXPIRED_1_DAY_AGO] Subscription Expired (1 day ago)
    [REFERRAL_ATTACHED] Referral Attached
    [REFERRAL_REWARD] Reward Received
    [REFERRAL_QUALIFIED] Referral Qualified
    [PARTNER_REFERRAL_REGISTERED] Partner Referral Registered
    [PARTNER_EARNING] Partner Earning
    [PARTNER_WITHDRAWAL_REQUEST_CREATED] Partner: Withdrawal Request Created
    [PARTNER_WITHDRAWAL_UNDER_REVIEW] Partner: Withdrawal Under Review
    [PARTNER_WITHDRAWAL_COMPLETED] Partner: Withdrawal Completed
    [PARTNER_WITHDRAWAL_REJECTED] Partner: Withdrawal Rejected
    *[OTHER] { $type }
    }

btn-notifications-system = ⚙️ System

btn-notifications-system-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $type ->
    [BOT_LIFETIME] Bot Lifecycle
    [BOT_UPDATE] Bot Updates
    [USER_REGISTERED] User Registration
    [WEB_USER_REGISTERED] Web User Registration
    [WEB_ACCOUNT_LINKED] Web-Telegram Sync
    [SUBSCRIPTION] Subscription Purchase
    [PROMOCODE_ACTIVATED] Promocode Activation
    [TRIAL_GETTED] Trial Received
    [NODE_STATUS] Node Status
    [USER_FIRST_CONNECTED] First Connection
    [USER_HWID] User Devices
    *[OTHER] { $type }
    }


# Plans
btn-plans-statistics = 📊 Statistics
btn-plans-create = 🆕 Create
btn-plan-save = ✅ Save
btn-plan-create = ✅ Create Plan
btn-plan-delete = ❌ Delete
btn-plan-name = 🏷️ Name
btn-plan-description = 💬 Description
btn-plan-description-remove = ❌ Remove Current Description
btn-plan-tag = 📌 Tag
btn-plan-tag-remove = ❌ Remove Current Tag
btn-plan-type = 🔖 Type
btn-plan-availability = ✴️ Availability
btn-plan-durations-prices = ⏳ Durations and 💰 Prices
btn-plan-traffic = 🌐 Traffic
btn-plan-devices = 📱 Devices
btn-plan-subscription-count = 🔢 Subscription Count
btn-plan-allowed = 👥 Allowed Users
btn-plan-squads = 🔗 Squads
btn-plan-internal-squads = ⏺️ Internal Squads
btn-plan-external-squads = ⏹️ External Squad
btn-allowed-user = { $id }
btn-plan-duration-add = 🆕 Add Duration
btn-plan-price-choice = 💸 { $price } { $currency }

btn-plan = { $is_active ->
    [1] 🟢
    *[0] 🔴 
    } { $name }

btn-plan-active = { $is_active -> 
    [1] 🟢 Active
    *[0] 🔴 Inactive
    }

btn-plan-type-choice = { $type -> 
    [TRAFFIC] 🌐 Traffic
    [DEVICES] 📱 Devices
    [BOTH] 🔗 Traffic + Devices
    [UNLIMITED] ♾️ Unlimited
    *[OTHER] { $type }
    }

btn-plan-availability-choice = { $type -> 
    [ALL] 🌍 For Everyone
    [NEW] 🌱 For New Users
    [EXISTING] 👥 For Existing Users
    [INVITED] ✉️ For Invited
    [ALLOWED] 🔐 For Allowed
    [TRIAL] 🎁 For Trial
    *[OTHER] { $type }
    }

btn-plan-traffic-strategy-choice = { $selected ->
    [1] 🔘 { traffic-strategy }
    *[0] ⚪ { traffic-strategy }
    }

btn-plan-duration = ⌛ { $value ->
    [-1] { unlimited }
    *[other] { unit-day }
    }


# RemnaWave
btn-remnawave-users = 👥 Users
btn-remnawave-hosts = 🌐 Hosts
btn-remnawave-nodes = 🖥️ Nodes
btn-remnawave-inbounds = 🔌 Inbounds


# Importer
btn-importer-from-xui = 💩 Import from 3X-UI Panel
btn-importer-from-xui-shop = 🛒 3xui-shop Bot
btn-importer-sync = 🌀 Start Synchronization
btn-importer-squads = 🔗 Internal Squads
btn-importer-import-all = ✅ Import All
btn-importer-import-active = ❇️ Import Active


# Subscription
btn-subscription-device-type = { $type ->
    [ANDROID] 📱 Android
    [IPHONE] 🍏 iPhone
    [WINDOWS] 🖥 Windows
    [MAC] 💻 Mac
    *[OTHER] 🛩️ Other
    }
btn-subscription-new = 💸 Buy Subscription
btn-subscription-renew = 🔄 Renew
btn-subscription-additional = 💠 Purchase Additional Subscription
btn-subscription-delete = ❌ Delete
btn-subscription-confirm-delete = ❌ Confirm Delete
btn-subscription-cancel-delete = ✅ Keep
btn-subscription-my-subscriptions = 📋 My Subscriptions ({ $count })
btn-subscription-item = { $status ->
    [ACTIVE] 🟢
    [EXPIRED] 🔴
    [LIMITED] 🟡
    [DISABLED] ⚫
    *[OTHER] ⚪
    } { $device_name } - { $expire_time }

btn-subscription-item-selectable = { $is_selected ->
    [1] ✅
    *[0] ⬜
    } { $status ->
    [ACTIVE] 🟢
    [EXPIRED] 🔴
    [LIMITED] 🟡
    [DISABLED] ⚫
    *[OTHER] ⚪
    } { $plan_name } - { $expire_time }

btn-subscription-confirm-selection = ✅ Continue ({ $count })
btn-subscription-continue-to-duration = ➡️ Select Duration
btn-subscription-connect-url = 🔗 Get Link
btn-subscription-copy-url = 📋 Copy Link
btn-subscription-promocode = 🎟 Activate Promocode
btn-subscription-payment-method = { gateway-type } | { $price } { $currency }
btn-subscription-pay = 💳 Pay
btn-subscription-get = 🎁 Get for Free
btn-subscription-back-plans = ⬅️ Back to Plan Selection
btn-subscription-back-duration = ⬅️ Change Duration
btn-subscription-back-device-type = ⬅️ Change Device
btn-subscription-back-payment-method = ⬅️ Change Payment Method
btn-subscription-connect = 🚀 Connect
btn-subscription-duration = { $period } | { $final_amount ->
    [0] 🎁
    *[HAS] { $final_amount }{ $currency }
    }
btn-subscription-promocode-create-new = ➕ Create New Subscription
btn-subscription-promocode-confirm-create = ✅ Create
btn-subscription-privacy-policy = 📄 Privacy Policy
btn-subscription-terms-of-service = 📋 Terms of Service


# Promocodes
btn-promocode-code = 🏷️ Code
btn-promocode-type = 🔖 Reward Type
btn-promocode-availability = ✴️ Availability
btn-promocode-generate = 🎲 Generate Code

btn-promocode-active = { $is_active ->
    [1] 🟢
    *[0] 🔴
    } Status

btn-promocode-reward = 🎁 Reward
btn-promocode-lifetime = ⌛ Lifetime
btn-promocode-allowed = 👥 Activation Limit
btn-promocode-activation-limit = 👥 Activation Limit
btn-promocode-plan-filter = 📋 Plan Filter
btn-promocode-allowed-users = 🔐 Allowed Users
btn-promocode-clear-plan-filter = 🗑️ Clear Filter
btn-promocode-confirm = ✅ Confirm

btn-promocode-type-choice = { $type ->
    [DURATION] ⏳ Subscription Days
    [TRAFFIC] 🌐 Traffic
    [DEVICES] 📱 Devices
    [SUBSCRIPTION] 💳 Subscription
    [PERSONAL_DISCOUNT] 💸 Personal Discount
    [PURCHASE_DISCOUNT] 🏷️ Purchase Discount
    *[OTHER] { $type }
    }

btn-promocode-availability-choice = { $type ->
    [ALL] 🌍 For Everyone
    [NEW] 🌱 For New Users
    [EXISTING] 👥 For Existing Users
    [INVITED] ✉️ For Invited
    [ALLOWED] 🔐 For Allowed
    *[OTHER] { $type }
    }

btn-promocode-plan-filter-choice = { $selected ->
    [true] ✅
    *[false] ⬜
    } { $is_active ->
    [true] 🟢
    *[false] 🔴
    } { $plan_name }


# Partner Program (Admin)
btn-partner-enable = { $is_enabled ->
    [1] 🟢 Enabled
    *[0] 🔴 Disabled
    }
btn-partner-level-percents = 📊 Level Percentages
btn-partner-level-percent = { $level ->
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $level }
    } level: { $percent }%
btn-partner-tax-settings = 🏛 Taxes
btn-partner-tax-percent = 🏛 Tax ({ $percent }%)
btn-partner-gateway-fees = 💳 Payment System Fees
btn-partner-gateway-fee = { gateway-type }: { $fee }%
btn-partner-min-withdrawal = ⬇️ Min. Withdrawal ({ $min_withdrawal })
btn-partner-level-choice = { $level ->
    [1] 1️⃣ Level 1
    [2] 2️⃣ Level 2
    [3] 3️⃣ Level 3
    *[OTHER] Level { $level }
    }
btn-partner-withdrawals = 📝 Requests ({ $count })
btn-partner-withdrawal-status = { $status ->
    [PENDING] 🕓 Pending
    [APPROVED] ✅ Approved
    [REJECTED] ❌ Rejected
    *[OTHER] { $status }
    }
btn-partner-withdrawal-item = { $status ->
    [PENDING] 🕓
    [COMPLETED] ✅
    [REJECTED] ❌
    *[OTHER] { $status }
    } { $user_id } - { $amount } - { $created_at }
btn-partner-withdrawal-approve = ✅ Completed
btn-partner-withdrawal-pending = 💭 Under Review
btn-partner-withdrawal-reject = 🚫 Rejected

# Partner Program (Client)
btn-menu-partner = 👾 Partner
btn-partner-referrals = 👥 My Referrals ({ $count })
btn-partner-earnings = 📊 My Earnings
btn-partner-withdraw = 💰 Withdrawal
btn-partner-withdraw-confirm = ✅ Confirm Request
btn-partner-invite-copy = 🔗 Copy Link
btn-partner-invite-send = 📩 Invite
btn-partner-history = 📜 Withdrawal History
btn-partner-balance-currency = 💱 Balance Currency
btn-partner-balance-currency-choice = { $selected ->
    [1] ⚪️
    *[0] ⚫️
    } { $label }
btn-partner-balance-currency-auto = 🤖 Auto ({ $currency })
btn-partner-referral-item = { $level ->
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $level }
    } { $username } - { $total_earned }

# Importer plan assignment
btn-importer-assign-plan-all = Assign plan to all
btn-importer-assign-plan-confirm = Confirm assignment
btn-importer-assign-plan-choice = { $selected ->
    [1] ✅
    *[0] ⬜
    } { $name }

# User plan assignment
btn-user-assign-plan = Assign plan
btn-user-assign-plan-choice = { $selected ->
    [1] ✅
    *[0] ⬜
    } { $plan_name }

btn-user-reset-web-password = 💥Reset web password
btn-subscription-back-payment-asset = Change Coin
btn-plan-archived = { $is_archived ->
    [1] 🗄 Archived
    *[0] 🛒 Public
    }
btn-plan-renew-mode = 🔁 Renewal: { $renew_mode ->
    [SELF_RENEW] Same plan only
    [REPLACE_ON_RENEW] Replace on renew
    *[other] { $renew_mode }
    }
btn-plan-renew-mode-choice = { $mode ->
    [SELF_RENEW] Renew the same plan
    [REPLACE_ON_RENEW] Replace with available plan
    *[other] { $mode }
    }
btn-plan-replacements = 🔄 Renew replacements ({ $count })
btn-plan-upgrades = ⬆️ Upgrade targets ({ $count })
btn-plan-transition-choice = { $selected ->
    [1] ✅
    *[0] ◻️
    } { $name }
