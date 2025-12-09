# Menu
msg-menu-connect-device-url =
    <b>🔗 Connection</b>

    Click the button below to connect.

msg-menu-exchange =
    <b>🎁 Referral Rewards</b>

    Here you can exchange your accumulated points for various bonuses.

    <b>📊 Your balance:</b>
    <blockquote>
    💎 Points: <b>{ $points }</b>
    </blockquote>

    <b>📈 Statistics:</b>
    <blockquote>
    👥 Friends invited: { $referrals }
    💳 Payments from your link: { $payments }
    </blockquote>

    <b>🔄 Available exchange types:</b>
    <blockquote>
    { $subscription_days_available ->
    [1] ⏳ Subscription days: { $days_available } days ({ $subscription_days_cost } point = 1 day)
    *[0] { empty }
    }
    { $gift_subscription_available ->
    [1] 🎁 Gift subscription: { $gift_plan_name } for { $gift_duration_days } days
    *[0] { empty }
    }
    { $discount_available ->
    [1] 💸 Discount: up to { $discount_percent }% ({ $discount_cost } points = 1%)
    *[0] { empty }
    }
    { $traffic_available ->
    [1] 🌐 Traffic: up to { $traffic_gb } GB ({ $traffic_cost } points = 1 GB)
    *[0] { empty }
    }
    </blockquote>

    { $has_points ->
    [1] <i>Select an exchange type below.</i>
    *[0] <i>You don't have any points yet. Invite friends to earn them!</i>
    }

msg-menu-exchange-select-type =
    <b>🔄 Select exchange type</b>

    You have <b>{ $points }</b> { $points ->
        [one] point
        *[other] points
    }.

    Select what you want to exchange points for:

msg-menu-exchange-gift =
    <b>🎁 Exchange for gift subscription</b>

    You can exchange points for a promocode with a gift subscription.

    <blockquote>
    • <b>Plan</b>: { $plan_name }
    • <b>Duration</b>: { $duration_days } days
    • <b>Cost</b>: { $cost } points
    </blockquote>

    { $can_exchange ->
    [1] <i>Click the button below to get the promocode.</i>
    *[0] <i>You don't have enough points for exchange.</i>
    }

msg-menu-exchange-gift-success =
    <b>🎉 Promocode created!</b>

    Your gift subscription promocode:

    <blockquote>
    <code>{ $promocode }</code>
    </blockquote>

    <b>Details:</b>
    <blockquote>
    • <b>Plan</b>: { $plan_name }
    • <b>Duration</b>: { $duration_days } days
    </blockquote>

    <i>Copy the promocode and send it to a friend. The promocode is one-time use only!</i>

msg-menu-exchange-discount =
    <b>💸 Exchange for discount</b>

    You can exchange points for a discount on your next purchase.

    <blockquote>
    • <b>Your points</b>: { $points }
    • <b>Rate</b>: { $cost_per_percent } points = 1% discount
    • <b>Available discount</b>: { $discount_percent }%
    • <b>Will be spent</b>: { $points_to_spend } points
    • <b>Maximum discount</b>: { $max_discount }%
    </blockquote>

    { $can_exchange ->
    [1] <i>Click the button below to get the discount.</i>
    *[0] <i>You don't have enough points for exchange.</i>
    }

msg-menu-exchange-traffic =
    <b>🌐 Exchange for traffic</b>

    You can exchange points for additional traffic.

    <blockquote>
    • <b>Your points</b>: { $points }
    • <b>Rate</b>: { $cost_per_gb } points = 1 GB
    • <b>Available traffic</b>: { $traffic_gb } GB
    • <b>Maximum</b>: { $max_traffic } GB
    </blockquote>

    Select a subscription to add traffic to:

msg-menu-exchange-traffic-confirm =
    <b>🌐 Confirm traffic exchange</b>

    You are about to exchange <b>{ $points_to_spend }</b> points for <b>{ $traffic_gb }</b> GB of traffic.

    <blockquote>
    • <b>Subscription</b>: { $subscription_name }
    • <b>Current limit</b>: { $current_traffic_limit }
    </blockquote>

    Click "Confirm" to complete the exchange.

exchange-type-days-value = { $days } { $days ->
    [one] day
    *[other] days
    }
exchange-type-gift-value = { $plan_name } for { $days } days
exchange-type-discount-value = { $percent }% discount
exchange-type-traffic-value = { $gb } GB of traffic

msg-menu-exchange-points =
    <b>💎 Select subscription</b>

    You have <b>{ $points }</b> { $points ->
        [one] point
        *[other] points
    }, which equals <b>{ $days_available }</b> { $days_available ->
        [one] day
        *[other] days
    } of subscription.

    Select a subscription to add days to:

msg-menu-exchange-points-confirm =
    <b>💎 Confirm exchange</b>

    You are about to exchange <b>{ $points }</b> { $points ->
        [one] point
        *[other] points
    } for <b>{ $days_to_add }</b> { $days_to_add ->
        [one] day
        *[other] days
    } of subscription.

    <blockquote>
    • <b>Subscription</b>: { $subscription_name }
    • <b>Current expiry</b>: { $expire_time }
    </blockquote>

    Click "Confirm exchange" to complete the operation.

# Subscription
msg-subscription-confirm-delete =
    <b>⚠️ Delete Confirmation</b>

    Are you sure you want to delete subscription <b>#{ $subscription_index }</b>?

    <blockquote>
    • <b>Plan</b>: { $plan_name }
    • <b>Expires</b>: { $expire_time }
    </blockquote>

    <i>This action cannot be undone. The subscription will be deleted from the panel and database.</i>

msg-subscription-device-type =
    <b>📱 Select device{ $is_multiple ->
    [1] { space }({ $current_index } of { $total_count })
    *[0] { empty }
    }</b>

    Which device will you use { $is_multiple ->
    [1] this subscription on?
    *[0] the subscription on?
    }


msg-subscription-select-for-renew-single =
    <b>🔄 Select subscription to renew</b>

    You have multiple subscriptions. Select one subscription you want to renew.

msg-subscription-promocode-select-duration =
    <b>🎟 Select subscription for days</b>

    You have multiple active subscriptions. Select which subscription to add <b>{ $promocode_days }</b> { $promocode_days ->
    [1] day
    *[other] days
    } from the promocode.

# Referral
msg-referral-eligible-plans =
    <b>📦 Plans for reward accrual</b>

    { $has_filter ->
    [1] Selected <b>{ $eligible_count }</b> { $eligible_count ->
        [one] plan
        *[other] plans
        }. Rewards are only accrued for purchases of selected plans.
    *[0] No filter set. Rewards are accrued for purchases of <b>any</b> plan.
    }

    Select plans for which referral rewards will be accrued.

msg-referral-points-exchange =
    <b>💎 Points Exchange Settings</b>

    <blockquote>
    • <b>Status</b>: { $exchange_enabled ->
        [1] 🟢 Enabled
        *[0] 🔴 Disabled
        }
    • <b>Exchange types enabled</b>: { $enabled_types_count }
    • <b>Exchange rate (days)</b>: { $points_per_day } { $points_per_day ->
        [one] point
        *[other] points
        } = 1 day
    • <b>Min. points for exchange</b>: { $min_exchange_points }
    • <b>Max. points per exchange</b>: { $max_exchange_points ->
        [-1] Unlimited
        *[other] { $max_exchange_points }
        }
    </blockquote>

    Select a parameter to change.

msg-referral-exchange-types =
    <b>🔄 Points Exchange Types</b>

    Select an exchange type to configure. Enabled types will be available to users.

msg-referral-exchange-type-settings =
    <b>⚙️ Exchange Type Settings</b>

    <blockquote>
    • <b>Type</b>: { $exchange_type ->
        [SUBSCRIPTION_DAYS] ⏳ Subscription days
        [GIFT_SUBSCRIPTION] 🎁 Gift subscription
        [DISCOUNT] 💸 Purchase discount
        [TRAFFIC] 🌐 Additional traffic
        *[OTHER] { $exchange_type }
        }
    • <b>Status</b>: { $enabled ->
        [1] 🟢 Enabled
        *[0] 🔴 Disabled
        }
    • <b>Cost</b>: { $points_cost } { $points_cost ->
        [one] point
        *[other] points
        } { $exchange_type ->
        [SUBSCRIPTION_DAYS] = 1 day
        [GIFT_SUBSCRIPTION] = 1 promocode
        [DISCOUNT] = 1% discount
        [TRAFFIC] = 1 GB
        *[OTHER] { empty }
        }
    • <b>Min. points</b>: { $min_points }
    • <b>Max. points</b>: { $max_points ->
        [-1] Unlimited
        *[other] { $max_points }
        }
    { $exchange_type ->
    [GIFT_SUBSCRIPTION]
    • <b>Plan</b>: { $gift_plan_name }
    • <b>Duration</b>: { $gift_duration_days } days
    [DISCOUNT]
    • <b>Max. discount</b>: { $max_discount_percent }%
    [TRAFFIC]
    • <b>Max. traffic</b>: { $max_traffic_gb } GB
    *[OTHER] { empty }
    }
    </blockquote>

    Select a parameter to change.

msg-referral-exchange-type-cost =
    <b>💰 Cost in points</b>

    <blockquote>
    Current cost: <b>{ $points_cost }</b> { $points_cost ->
        [one] point
        *[other] points
        }
    </blockquote>

    Enter the number of points per unit { $exchange_type ->
        [SUBSCRIPTION_DAYS] (1 subscription day)
        [GIFT_SUBSCRIPTION] (1 promocode)
        [DISCOUNT] (1% discount)
        [TRAFFIC] (1 GB of traffic)
        *[OTHER] { empty }
        }.

msg-referral-exchange-type-min =
    <b>⬇️ Minimum points</b>

    <blockquote>
    Current value: <b>{ $min_points }</b>
    </blockquote>

    Enter the minimum number of points for this exchange type.

msg-referral-exchange-type-max =
    <b>⬆️ Maximum points</b>

    <blockquote>
    Current value: { $max_points ->
        [-1] <b>Unlimited</b>
        *[other] <b>{ $max_points }</b>
        }
    </blockquote>

    Enter the maximum number of points per exchange.
    Enter -1 to remove the limit.

msg-referral-gift-plan =
    <b>📦 Plan for gift subscription</b>

    Select the plan that will be issued when exchanging points for a gift subscription.

msg-referral-gift-duration =
    <b>⏳ Gift subscription duration</b>

    <blockquote>
    Current duration: <b>{ $gift_duration_days }</b> days
    </blockquote>

    Enter the number of days for the gift subscription.

msg-referral-discount-max =
    <b>💸 Maximum discount percentage</b>

    <blockquote>
    Current value: <b>{ $max_discount_percent }%</b>
    </blockquote>

    Enter the maximum discount percentage (1-100).

msg-referral-traffic-max =
    <b>🌐 Maximum traffic amount</b>

    <blockquote>
    Current value: <b>{ $max_traffic_gb } GB</b>
    </blockquote>

    Enter the maximum amount of GB traffic.

exchange-type-subscription-days-desc = Exchange points for additional subscription days
exchange-type-gift-subscription-desc = Subscription promocode ({ $plan_name }, { $days } days)
exchange-type-discount-desc = Discount on next purchase (up to { $max_percent }%)
exchange-type-traffic-desc = Additional traffic (up to { $max_gb } GB)

msg-referral-points-per-day =
    <b>📊 Change exchange rate</b>

    <blockquote>
    Current rate: <b>{ $points_per_day }</b> { $points_per_day ->
        [one] point
        *[other] points
        } = 1 subscription day
    </blockquote>

    Enter the number of points required to get 1 day of subscription.

msg-referral-min-exchange-points =
    <b>⬇️ Minimum points for exchange</b>

    <blockquote>
    Current value: <b>{ $min_exchange_points }</b>
    </blockquote>

    Enter the minimum number of points a user must accumulate for exchange.

msg-referral-max-exchange-points =
    <b>⬆️ Maximum points per exchange</b>

    <blockquote>
    Current value: { $max_exchange_points ->
        [-1] <b>Unlimited</b>
        *[other] <b>{ $max_exchange_points }</b>
        }
    </blockquote>

    Enter the maximum number of points that can be exchanged at once.
    Enter -1 to remove the limit.

# RemnaShop
msg-user-partner-balance =
    <b>💰 Adjust partner balance</b>

    <b>Current balance: { $current_balance }</b>

    Select a button or enter a custom amount (in rubles) to add or subtract.

msg-partner-withdrawals-list =
    <b>📝 Withdrawal Requests</b>

    List of withdrawal requests from partners. Select a request to view details and process.

msg-partner-withdraw-confirm =
    <b>📝 Confirm Withdrawal Request</b>

    <blockquote>
    • <b>Amount</b>: { $amount }
    • <b>Fee</b>: { $fee } ({ $fee_percent }%)
    • <b>You will receive</b>: { $net_amount }
    </blockquote>

    <i>⚠️ After confirmation, your request will be sent for administrator review. Funds will be transferred after approval.</i>

msg-partner-withdrawal-details =
    <b>📝 Withdrawal Request</b>

    <blockquote>
    • <b>Partner ID</b>: { $partner_id }
    • <b>Amount</b>: { $amount } ₽
    • <b>Status</b>: { $status ->
        [pending] ⏳ Pending
        [completed] ✅ Completed
        [rejected] 🚫 Rejected
        [canceled] ❌ Canceled
        *[other] { $status }
    }
    • <b>Created</b>: { $created_at }
    • <b>Payment details</b>: { $payment_details }
    </blockquote>

    Select an action:

# Banners
msg-banners-main =
    <b>🖼️ Banner Management</b>

    Here you can upload and delete banners for various sections of the bot.

    <blockquote>
    Supported formats: JPG, JPEG, PNG, GIF, WEBP
    </blockquote>

    Select a banner to edit:

msg-banner-select =
    <b>🖼️ Banner: { $banner_display_name }</b>

    { $has_banner ->
    [1] <blockquote>
    ✅ Banner uploaded for locale <b>{ $locale }</b>
    </blockquote>
    *[0] <blockquote>
    ❌ Banner not uploaded for locale <b>{ $locale }</b>
    </blockquote>
    }

    Select locale and action:

msg-banner-upload =
    <b>📤 Upload Banner</b>

    <blockquote>
    • <b>Banner</b>: { $banner_display_name }
    • <b>Locale</b>: { $locale }
    </blockquote>

    Send an image to upload.

    <i>Supported formats: { $supported_formats }</i>

msg-banner-confirm-delete =
    <b>⚠️ Delete Confirmation</b>

    Are you sure you want to delete this banner?

    <blockquote>
    • <b>Banner</b>: { $banner_display_name }
    • <b>Locale</b>: { $locale }
    </blockquote>

    <i>This action cannot be undone.</i>

msg-promocode-plan =
    <b>📦 Select a plan for the promocode</b>

    Select the plan that will be issued when the promocode is activated.

msg-promocode-duration =
    <b>⏳ Select duration</b>

    Select the subscription duration for the plan <b>{ $plan_name }</b>.

msg-plan-configurator =
    <b>📦 Plan Configurator</b>

    <blockquote>
    • <b>Name</b>: { $name }
    • <b>Type</b>: { plan-type }
    • <b>Availability</b>: { availability-type }
    • <b>Status</b>: { $is_active ->
        [1] 🟢 Active
        *[0] 🔴 Inactive
        }
    </blockquote>
    
    <blockquote>
    • <b>Traffic Limit</b>: { $is_unlimited_traffic ->
        [1] { unlimited }
        *[0] { $traffic_limit }
        }
    • <b>Device Limit</b>: { $is_unlimited_devices ->
        [1] { unlimited }
        *[0] { $device_limit }
        }
    • <b>Subscription Count</b>: { $subscription_count }
    </blockquote>