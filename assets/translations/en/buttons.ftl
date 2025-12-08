# Menu
btn-menu-exchange = 🎁 Rewards
btn-menu-exchange-select-type = 🔄 Select exchange type
btn-menu-exchange-points = ⏳ Exchange for subscription days
btn-menu-exchange-days = ⏳ Add days to subscription
btn-menu-exchange-gift = 🎁 Get gift promocode
btn-menu-exchange-discount = 💸 Get discount
btn-menu-exchange-traffic = 🌐 Add traffic
btn-menu-exchange-points-confirm = ✅ Confirm exchange
btn-menu-exchange-gift-confirm = 🎁 Get promocode ({ $cost } points)
btn-menu-exchange-discount-confirm = 💸 Get { $discount_percent }% discount ({ $points_to_spend } points)
btn-menu-exchange-traffic-confirm = 🌐 Add { $traffic_gb } GB ({ $points_to_spend } points)
btn-menu-copy-promocode = 📋 Copy promocode

btn-menu-exchange-type-choice = { $available ->
    [1] { $type ->
        [SUBSCRIPTION_DAYS] ⏳ Subscription days
        [GIFT_SUBSCRIPTION] 🎁 Gift subscription
        [DISCOUNT] 💸 Purchase discount
        [TRAFFIC] 🌐 Extra traffic
        *[OTHER] { $type }
        }
    *[0] ❌ { $type ->
        [SUBSCRIPTION_DAYS] Subscription days (unavailable)
        [GIFT_SUBSCRIPTION] Gift subscription (unavailable)
        [DISCOUNT] Discount (unavailable)
        [TRAFFIC] Traffic (unavailable)
        *[OTHER] { $type }
        }
    }

# Subscription
btn-subscription-confirm-delete = ❌ Confirm Delete
btn-subscription-cancel-delete = ✅ Keep
btn-subscription-back-device-type = ⬅️ Change device
btn-subscription-additional = 💠 Purchase additional subscription
btn-subscription-privacy-policy = 📄 Privacy Policy
btn-subscription-terms-of-service = 📋 Terms of Service

# Referral
btn-referral-eligible-plans = 📦 Plans for rewards
btn-referral-clear-filter = 🗑️ Clear filter
btn-referral-points-exchange = 💎 Points exchange settings
btn-referral-exchange-enable = { $exchange_enabled ->
    [1] 🟢 Exchange enabled
    *[0] 🔴 Exchange disabled
    }
btn-referral-exchange-types = 🔄 Exchange types ({ $enabled_types_count })
btn-referral-points-per-day = 📊 Exchange rate ({ $points_per_day } point = 1 day)
btn-referral-min-exchange = ⬇️ Min. points ({ $min_exchange_points })
btn-referral-max-exchange = ⬆️ Max. points ({ $max_exchange_points ->
    [-1] ∞
    *[other] { $max_exchange_points }
    })

btn-referral-exchange-type-choice = { $enabled ->
    [1] 🟢
    *[0] 🔴
    } { $type ->
    [SUBSCRIPTION_DAYS] ⏳ Subscription days
    [GIFT_SUBSCRIPTION] 🎁 Gift subscription
    [DISCOUNT] 💸 Purchase discount
    [TRAFFIC] 🌐 Extra traffic
    *[OTHER] { $type }
    }

btn-referral-exchange-type-enable = { $enabled ->
    [1] 🟢 Enabled
    *[0] 🔴 Disabled
    }

btn-referral-exchange-type-cost = 💰 Cost ({ $points_cost } points)
btn-referral-exchange-type-min = ⬇️ Min. points ({ $min_points })
btn-referral-exchange-type-max = ⬆️ Max. points ({ $max_points ->
    [-1] ∞
    *[other] { $max_points }
    })

btn-referral-gift-plan = 📦 Plan ({ $gift_plan_name })
btn-referral-gift-duration = ⏳ Duration ({ $gift_duration_days } days)
btn-referral-discount-max = 💸 Max. discount ({ $max_discount_percent }%)
btn-referral-traffic-max = 🌐 Max. traffic ({ $max_traffic_gb } GB)

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

# RemnaShop
btn-remnashop-banners = 🖼️ Banners

# Banners
btn-banner-item = 🖼️ { $name }
btn-banner-locale-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $locale }
btn-banner-upload = 📤 Upload
btn-banner-delete = 🗑️ Delete
btn-banner-confirm-delete = ❌ Confirm deletion