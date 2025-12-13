# Remnashop
ntf-remnashop-info =
    <b>💎 Altshop v{ $version }</b>

    This project is based on <a href="https://github.com/snoups/remnashop">Remnashop</a> by <b>snoups</b>. Since the bot is completely FREE and open source, it exists only thanks to your support.

    ⭐ <i>Star us on <a href="https://github.com/dizzzable/altshop">GitHub</a> and support the <a href="https://github.com/snoups/remnashop">original developer</a>.</i>


# Menu
msg-main-menu =
    { hdr-user-profile }
    { frg-user }

    { hdr-subscription }
    { $status ->
    [ACTIVE]
    { frg-subscription }
    [EXPIRED]
    <blockquote>
    • Subscription expired.

    <i>To renew, go to "💳 Subscription" menu</i>
    </blockquote>
    [LIMITED]
    <blockquote>
    • You have exceeded your traffic limit.

    <i>To reset traffic, go to "💳 Subscription" menu</i>
    </blockquote>
    [DISABLED]
    <blockquote>
    • Your subscription is disabled.

    <i>Contact support to find out the reason!</i>
    </blockquote>
    *[NONE]
    <blockquote>
    • You don't have an active subscription.

    <i>To subscribe, go to "💳 Subscription" menu</i>
    </blockquote>
    }

msg-menu-connect-device =
    <b>🚀 Select device to connect</b>

    Select the subscription for which you want to get a connection link.

msg-menu-connect-device-url =
    <b>🔗 Connection</b>

    Click the button below to connect.

msg-menu-devices =
    <b>📱 My Devices</b>

    { $subscriptions_count ->
    [1] Select a subscription to view devices.
    *[other] You have <b>{ $subscriptions_count }</b> { $subscriptions_count ->
        [one] subscription
        [few] subscriptions
        *[other] subscriptions
        } with device limits. Select a subscription to view.
    }

msg-menu-devices-subscription =
    <b>📱 Devices for subscription #{ $subscription_index }</b>

    <blockquote>
    • <b>Plan</b>: { $plan_name }
    • <b>Devices</b>: { $current_count } / { $max_count }
    </blockquote>

    { $devices_empty ->
    [1] <i>No connected devices.</i>
    *[0] Here you can remove connected devices or get a connection link.
    }

msg-menu-invite =
    <b>👥 Invite Friends</b>
    
    Share your unique link and receive rewards in the form of { $reward_type ->
        [POINTS] <b>points that can be exchanged for subscription or real money</b>
        [EXTRA_DAYS] <b>free days added to your subscription</b>
        *[OTHER] { $reward_type }
    }!

    <b>📊 Statistics:</b>
    <blockquote>
    👥 Total invited: { $referrals }
    💳 Payments from your link: { $payments }
    { $reward_type -> 
    [POINTS] 💎 Your points: { $points }
    *[EXTRA_DAYS] { empty }
    }
    </blockquote>

msg-menu-invite-about =
    <b>🎁 More about rewards</b>

    <b>✨ How to earn:</b>
    <blockquote>
    { $accrual_strategy ->
    [ON_FIRST_PAYMENT] Reward is credited for the first subscription purchase by an invited user.
    [ON_EACH_PAYMENT] Reward is credited for every purchase or renewal by an invited user.
    *[OTHER] { $accrual_strategy }
    }
    </blockquote>

    <b>💎 What you get:</b>
    <blockquote>
    { $max_level -> 
    [1] For invited friends: { $reward_level_1 }
    *[MORE]
    { $identical_reward ->
    [0]
    1️⃣ For your friends: { $reward_level_1 }
    2️⃣ For friends invited by your friends: { $reward_level_2 }
    *[1]
    For your friends and friends invited by them: { $reward_level_1 }
    }
    }
    
    { $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }
        [EXTRA_DAYS] <i>(All extra days are added to your current subscription)</i>
        *[OTHER] { $reward_type }
    }
    [PERCENT] { $reward_type ->
        [POINTS] <i>(Percentage of points from the cost of their purchased subscription)</i>
        [EXTRA_DAYS] <i>(Percentage of extra days from their purchased subscription)</i>
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }
    </blockquote>

msg-invite-reward = { $value }{ $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }{ $value ->
            [one] point
            *[other] points
            }
        [EXTRA_DAYS] { space }extra { $value ->
            [one] day
            *[other] days
            }
        *[OTHER] { $reward_type }
    }
    [PERCENT] % { $reward_type ->
        [POINTS] points
        [EXTRA_DAYS] extra days
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }

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
    *[0] <i>You don't have any points yet. Invite friends to earn rewards!</i>
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

    You can exchange points for a promocode with a gift subscription for a friend.

    <blockquote>
    • <b>Your points</b>: { $points }
    • <b>Cost</b>: { $cost } points
    • <b>Duration</b>: { $duration_days } days
    </blockquote>

    { $can_exchange ->
    [1] <i>Select a plan for the gift subscription.</i>
    *[0] <i>You don't have enough points for exchange.</i>
    }

msg-menu-exchange-gift-select-plan =
    <b>📦 Select a plan for gift subscription</b>

    Select the plan that your friend will receive when activating the promocode.

    <blockquote>
    • <b>Your points</b>: { $points }
    • <b>Cost</b>: { $cost } points
    </blockquote>

msg-menu-exchange-gift-confirm =
    <b>🎁 Confirm exchange</b>

    You are about to create a gift subscription promocode:

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


# Dashboard
msg-dashboard-main = <b>🛠 Control Panel</b>
msg-users-main = <b>👥 Users</b>
msg-broadcast-main = <b>📢 Broadcast</b>
msg-statistics-main = { $statistics }
    
msg-statistics-users =
    <b>👥 User Statistics</b>

    <blockquote>
    • <b>Total</b>: { $total_users }
    • <b>New today</b>: { $new_users_daily }
    • <b>New this week</b>: { $new_users_weekly }
    • <b>New this month</b>: { $new_users_monthly }

    • <b>With subscription</b>: { $users_with_subscription }
    • <b>Without subscription</b>: { $users_without_subscription }
    • <b>With trial</b>: { $users_with_trial }

    • <b>Blocked</b>: { $blocked_users }
    • <b>Blocked bot</b>: { $bot_blocked_users }

    • <b>User → purchase conversion</b>: { $user_conversion }%
    • <b>Trial → subscription conversion</b>: { $trial_conversion }%
    </blockquote>

msg-statistics-transactions =
    <b>🧾 Transaction Statistics</b>

    <blockquote>
    • <b>Total transactions</b>: { $total_transactions }
    • <b>Completed transactions</b>: { $completed_transactions }
    • <b>Free transactions</b>: { $free_transactions }
    { $popular_gateway ->
    [0] { empty }
    *[HAS] • <b>Popular payment system</b>: { $popular_gateway }
    }
    </blockquote>

    { $payment_gateways }

msg-statistics-subscriptions =
    <b>💳 Subscription Statistics</b>

    <blockquote>
    • <b>Active</b>: { $total_active_subscriptions }
    • <b>Expired</b>: { $total_expire_subscriptions }
    • <b>Trial</b>: { $active_trial_subscriptions }
    • <b>Expiring (7 days)</b>: { $expiring_subscriptions }
    </blockquote>

    <blockquote>
    • <b>Unlimited</b>: { $total_unlimited }
    • <b>With traffic limit</b>: { $total_traffic }
    • <b>With device limit</b>: { $total_devices }
    </blockquote>

msg-statistics-plans = 
    <b>📦 Plan Statistics</b>

    { $plans }

msg-statistics-promocodes =
    <b>🎁 Promocode Statistics</b>

    <blockquote>
    • <b>Total activations</b>: { $total_promo_activations }
    • <b>Most popular promocode</b>: { $most_popular_promo ->
    [0] { unknown }
    *[HAS] { $most_popular_promo }
    }
    • <b>Days issued</b>: { $total_promo_days }
    • <b>Traffic issued</b>: { $total_promo_days }
    • <b>Subscriptions issued</b>: { $total_promo_subscriptions }
    • <b>Personal discounts issued</b>: { $total_promo_personal_discounts }
    • <b>One-time discounts issued</b>: { $total_promo_purchase_discounts }
    </blockquote>

msg-statistics-referrals =
    <b>👪 Referral System Statistics</b>
    
    <blockquote>
    • <b></b>:
    </blockquote>

msg-statistics-transactions-gateway =
    <b>{ gateway-type }:</b>
    <blockquote>
    • <b>Total income</b>: { $total_income }{ $currency }
    • <b>Daily income</b>: { $daily_income }{ $currency }
    • <b>Weekly income</b>: { $weekly_income }{ $currency }
    • <b>Monthly income</b>: { $monthly_income }{ $currency }
    • <b>Average check</b>: { $average_check }{ $currency }
    • <b>Total discounts</b>: { $total_discounts }{ $currency }
    </blockquote>

msg-statistics-plan =
    <b>{ $plan_name }:</b> { $popular -> 
    [0] { space }
    *[HAS] (⭐)
    }
    <blockquote>
    • <b>Total subscriptions</b>: { $total_subscriptions }
    • <b>Active subscriptions</b>: { $active_subscriptions }
    • <b>Popular duration</b>: { $popular_duration }

    • <b>Total income</b>: 
    { $all_income }
    </blockquote>

msg-statistics-plan-income = { $income }{ $currency }
    


# Access
msg-access-main =
    <b>🔓 Access Mode</b>
    
    <b>Status</b>: { access-mode }.

msg-access-conditions =
    <b>⚙️ Access Conditions</b>

msg-access-rules =
    <b>✳️ Change rules link</b>

    Enter a link (in format https://telegram.org/tos).

msg-access-channel =
    <b>❇️ Change channel/group link</b>

    If your group doesn't have a @username, send the group ID and invite link as separate messages.
    
    If you have a public channel/group, enter only the @username.


# Broadcast
msg-broadcast-list = <b>📄 Broadcast List</b>
msg-broadcast-plan-select = <b>📦 Select plan for broadcast</b>
msg-broadcast-send = <b>📢 Send broadcast ({ audience-type })</b>

    Broadcast will be sent to { $audience_count } { $audience_count ->
    [one] user
    *[other] users
    }

msg-broadcast-content =
    <b>✉️ Broadcast Content</b>

    Send any message: text, image, or both (HTML supported).

msg-broadcast-buttons = <b>✳️ Broadcast Buttons</b>

msg-broadcast-view =
    <b>📢 Broadcast</b>

    <blockquote>
    • <b>ID</b>: <code>{ $broadcast_id }</code>
    • <b>Status</b>: { broadcast-status }
    • <b>Audience</b>: { audience-type }
    • <b>Created</b>: { $created_at }
    </blockquote>

    <blockquote>
    • <b>Total messages</b>: { $total_count }
    • <b>Successful</b>: { $success_count }
    • <b>Failed</b>: { $failed_count }
    </blockquote>


# Users
msg-users-recent-registered = <b>🆕 Recently Registered</b>
msg-users-recent-activity = <b>📝 Recent Activity</b>
msg-user-transactions = <b>🧾 User Transactions</b>
msg-user-devices = <b>📱 User Devices ({ $current_count } / { $max_count })</b>
msg-user-give-access = <b>🔑 Grant Plan Access</b>

msg-users-search =
    <b>🔍 Search User</b>

    Enter user ID, part of their name, or forward any of their messages.

msg-users-search-results =
    <b>🔍 Search User</b>

    Found <b>{ $count }</b> { $count ->
    [one] user
    *[other] users
    } matching the query

msg-user-main = 
    <b>📝 User Information</b>

    { hdr-user-profile }
    { frg-user-details }

    <b>💸 Discount:</b>
    <blockquote>
    • <b>Personal</b>: { $personal_discount }%
    • <b>Next purchase</b>: { $purchase_discount }%
    </blockquote>
    
    { hdr-subscription }
    { $status ->
    [ACTIVE]
    { frg-subscription }
    [EXPIRED]
    <blockquote>
    • Subscription expired.
    </blockquote>
    [LIMITED]
    <blockquote>
    • Traffic limit exceeded.
    </blockquote>
    [DISABLED]
    <blockquote>
    • Subscription disabled.
    </blockquote>
    *[NONE]
    <blockquote>
    • No active subscription.
    </blockquote>
    }

msg-user-give-subscription =
    <b>🎁 Give Subscription</b>

    Select the plan you want to give to the user.

msg-user-give-subscription-duration =
    <b>⏳ Select Duration</b>

    Select the duration of the subscription to give.

msg-user-discount =
    <b>💸 Change Personal Discount</b>

    Select from buttons or enter your own value.

msg-user-points =
    <b>💎 Change Referral Points</b>

    <b>Current points: { $current_points }</b>

    Select from buttons or enter your own value to add or subtract.

msg-user-subscription-traffic-limit =
    <b>🌐 Change Traffic Limit</b>

    Select from buttons or enter your own value (in GB) to change the traffic limit.

msg-user-subscription-device-limit =
    <b>📱 Change Device Limit</b>

    Select from buttons or enter your own value to change the device limit.

msg-user-subscription-expire-time =
    <b>⏳ Change Expiry Time</b>

    <b>Expires in: { $expire_time }</b>

    Select from buttons or enter your own value (in days) to add or subtract.

msg-user-subscription-squads =
    <b>🔗 Change Squad List</b>

    { $internal_squads ->
    [0] { empty }
    *[HAS] <b>⏺️ Internal:</b> { $internal_squads }
    }

    { $external_squad ->
    [0] { empty }
    *[HAS] <b>⏹️ External:</b> { $external_squad }
    }

msg-user-subscription-internal-squads =
    <b>⏺️ Change Internal Squads</b>

    Select which internal groups will be assigned to this user.

msg-user-subscription-external-squads =
    <b>⏹️ Change External Squad</b>

    Select which external group will be assigned to this user.

msg-user-subscription-info =
    <b>💳 Current Subscription Info</b>
    
    { hdr-subscription }
    { frg-subscription-details }

    <blockquote>
    • <b>Squads</b>: { $squads -> 
    [0] { unknown }
    *[HAS] { $squads }
    }
    • <b>First connected</b>: { $first_connected_at -> 
    [0] { unknown }
    *[HAS] { $first_connected_at }
    }
    • <b>Last connected</b>: { $last_connected_at ->
    [0] { unknown }
    *[HAS] { $last_connected_at } ({ $node_name })
    } 
    </blockquote>

    { hdr-plan }
    { frg-plan-snapshot }

msg-user-transaction-info =
    <b>🧾 Transaction Information</b>

    { hdr-payment }
    <blockquote>
    • <b>ID</b>: <code>{ $payment_id }</code>
    • <b>Type</b>: { purchase-type }
    • <b>Status</b>: { transaction-status }
    • <b>Payment method</b>: { gateway-type }
    • <b>Amount</b>: { frg-payment-amount }
    • <b>Created</b>: { $created_at }
    </blockquote>

    { $is_test -> 
    [1] ⚠️ Test transaction
    *[0]
    { hdr-plan }
    { frg-plan-snapshot }
    }
    
msg-user-role = 
    <b>👮‍♂️ Change Role</b>
    
    Select a new role for the user.

msg-users-blacklist =
    <b>🚫 Blacklist</b>

    Blocked: <b>{ $count_blocked }</b> / <b>{ $count_users }</b> ({ $percent }%).

msg-user-message =
    <b>📩 Send Message to User</b>

    Send any message: text, image, or both (HTML supported).
    

# RemnaWave
msg-remnawave-main =
    <b>🌊 RemnaWave</b>
    
    <b>🖥️ System:</b>
    <blockquote>
    • <b>CPU</b>: { $cpu_cores } { $cpu_cores ->
    [one] core
    *[other] cores
    } { $cpu_threads } { $cpu_threads ->
    [one] thread
    *[other] threads
    }
    • <b>RAM</b>: { $ram_used } / { $ram_total } ({ $ram_used_percent }%)
    • <b>Uptime</b>: { $uptime }
    </blockquote>

msg-remnawave-users =
    <b>👥 Users</b>

    <b>📊 Statistics:</b>
    <blockquote>
    • <b>Total</b>: { $users_total }
    • <b>Active</b>: { $users_active }
    • <b>Disabled</b>: { $users_disabled }
    • <b>Limited</b>: { $users_limited }
    • <b>Expired</b>: { $users_expired }
    </blockquote>

    <b>🟢 Online:</b>
    <blockquote>
    • <b>Last day</b>: { $online_last_day }
    • <b>Last week</b>: { $online_last_week }
    • <b>Never logged in</b>: { $online_never }
    • <b>Online now</b>: { $online_now }
    </blockquote>

msg-remnawave-host-details =
    <b>{ $remark } ({ $status ->
    [ON] enabled
    *[OFF] disabled
    }):</b>
    <blockquote>
    • <b>Address</b>: <code>{ $address }:{ $port }</code>
    { $inbound_uuid ->
    [0] { empty }
    *[HAS] • <b>Inbound</b>: <code>{ $inbound_uuid }</code>
    }
    </blockquote>

msg-remnawave-node-details =
    <b>{ $country } { $name } ({ $status ->
    [ON] connected
    *[OFF] disconnected
    }):</b>
    <blockquote>
    • <b>Address</b>: <code>{ $address }{ $port -> 
    [0] { empty }
    *[HAS]:{ $port }
    }</code>
    • <b>Uptime (xray)</b>: { $xray_uptime }
    • <b>Users online</b>: { $users_online }
    • <b>Traffic</b>: { $traffic_used } / { $traffic_limit }
    </blockquote>

msg-remnawave-inbound-details =
    <b>🔗 { $tag }</b>
    <blockquote>
    • <b>ID</b>: <code>{ $inbound_id }</code>
    • <b>Protocol</b>: { $type } ({ $network })
    { $port ->
    [0] { empty }
    *[HAS] • <b>Port</b>: { $port }
    }
    { $security ->
    [0] { empty }
    *[HAS] • <b>Security</b>: { $security } 
    }
    </blockquote>

msg-remnawave-hosts =
    <b>🌐 Hosts</b>
    
    { $host }

msg-remnawave-nodes = 
    <b>🖥️ Nodes</b>

    { $node }

msg-remnawave-inbounds =
    <b>🔌 Inbounds</b>

    { $inbound }


# RemnaShop
msg-remnashop-main = <b>🛍 RemnaShop</b>
msg-admins-main = <b>👮‍♂️ Administrators</b>


# Multi Subscription
msg-multi-subscription-main =
    <b>📦 Multi-subscription</b>

    <blockquote>
    • <b>Status</b>: { $is_enabled ->
        [1] 🟢 Enabled
        *[0] 🔴 Disabled
        }
    • <b>Default max subscriptions</b>: { $default_max ->
        [-1] ∞ Unlimited
        *[other] { $default_max }
        }
    </blockquote>

    <i>When multi-subscription is disabled, users can only have one subscription.
    Individual limits can be configured for each user separately.</i>

msg-multi-subscription-max =
    <b>🔢 Max subscriptions</b>

    <blockquote>
    Current value: { $default_max ->
        [-1] <b>∞ Unlimited</b>
        *[other] <b>{ $default_max }</b>
        }
    </blockquote>

    Enter the maximum number of subscriptions a user can purchase.
    Enter -1 to remove the limit.

msg-user-max-subscriptions =
    <b>📦 Individual subscription limit</b>

    <blockquote>
    • <b>Mode</b>: { $use_global ->
        [1] 🌐 Global settings
        *[0] ⚙️ Individual settings
        }
    • <b>Current limit</b>: { $current_max ->
        [-1] ∞ Unlimited
        *[other] { $current_max }
        }
    { $use_global ->
    [0] { empty }
    *[1] • <b>Global limit</b>: { $global_max ->
        [-1] ∞ Unlimited
        *[other] { $global_max }
        }
    }
    </blockquote>

    { $use_global ->
    [1] <i>User is using global settings. Click the button below to set an individual limit.</i>
    *[0] <i>Select a limit from the list or enter your own value.
    Enter -1 to remove the limit.</i>
    }


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


# Gateways
msg-gateways-main = <b>🌐 Payment Systems</b>
msg-gateways-settings = <b>🌐 { gateway-type } Configuration</b>
msg-gateways-default-currency = <b>💸 Default Currency</b>
msg-gateways-placement = <b>🔢 Change Positioning</b>

msg-gateways-field =
    <b>🌐 { gateway-type } Configuration</b>

    Enter a new value for { $field }.


# Referral
msg-referral-main =
    <b>👥 Referral System</b>

    <blockquote>
    • <b>Status</b>: { $is_enable ->
        [1] 🟢 Enabled
        *[0] 🔴 Disabled
        }
    • <b>Reward type</b>: { reward-type }
    • <b>Number of levels</b>: { $referral_level }
    • <b>Accrual condition</b>: { accrual-strategy }
    • <b>Reward calculation</b>: { reward-strategy }
    • <b>Plans for rewards</b>: { $has_plan_filter ->
        [1] { $eligible_plans_count } { $eligible_plans_count ->
            [one] plan
            *[other] plans
            }
        *[0] All plans
        }
    </blockquote>

    Select an item to change.

msg-referral-level =
    <b>🔢 Change Level</b>

    Select the maximum referral level.

msg-referral-reward-type =
    <b>🎀 Change Reward Type</b>

    Select a new reward type.
    
msg-referral-accrual-strategy =
    <b>📍 Change Accrual Condition</b>

    Select when the reward will be credited.


msg-referral-reward-strategy =
    <b>⚖️ Change Reward Calculation</b>

    Select the reward calculation method.


msg-referral-reward-level = Level { $level }: { $value }{ $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }{ $value -> 
            [one] point
            *[other] points
            }
        [EXTRA_DAYS] { space }extra { $value -> 
            [one] day
            *[other] days
            }
        *[OTHER] { $reward_type }
    }
    [PERCENT] % { $reward_type ->
        [POINTS] points
        [EXTRA_DAYS] extra days
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }
    
msg-referral-reward =
    <b>🎁 Change Reward</b>

    <blockquote>
    { $reward }
    </blockquote>

    { $reward_strategy_type ->
        [AMOUNT] Enter the number of { $reward_type ->
            [POINTS] points
            [EXTRA_DAYS] days
            *[OTHER] { $reward_type }
        }
        [PERCENT] Enter the percentage of { $reward_type ->
            [POINTS] <u>subscription cost</u>
            [EXTRA_DAYS] <u>subscription duration</u>
            *[OTHER] { $reward_type }
        }
        *[OTHER] { $reward_strategy_type }
    } (in format: level=value)

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

# Plans
msg-plans-main = <b>📦 Plans</b>

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
    • <b>Traffic limit</b>: { $is_unlimited_traffic ->
        [1] { unlimited }
        *[0] { $traffic_limit }
        }
    • <b>Device limit</b>: { $is_unlimited_devices ->
        [1] { unlimited }
        *[0] { $device_limit }
        }
    • <b>Subscription count</b>: { $subscription_count }
    </blockquote>

    Select an item to change.

msg-plan-name =
    <b>🏷️ Change Name</b>

    { $name ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $name }
    </blockquote>
    }

    Enter a new plan name.

msg-plan-description =
    <b>💬 Change Description</b>

    { $description ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $description }
    </blockquote>
    }

    Enter a new plan description.

msg-plan-tag =
    <b>📌 Change Tag</b>

    { $tag ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $tag }
    </blockquote>
    }

    Enter a new plan tag (uppercase Latin letters, numbers, and underscores only).

msg-plan-type =
    <b>🔖 Change Type</b>

    Select a new plan type.

msg-plan-availability =
    <b>✴️ Change Availability</b>

    Select plan availability.

msg-plan-traffic =
    <b>🌐 Change Traffic Limit and Reset Strategy</b>

    Enter a new traffic limit (in GB) and select the reset strategy.

msg-plan-devices =
    <b>📱 Change Device Limit</b>

    Enter a new device limit.

msg-plan-subscription-count =
    <b>🔢 Change Subscription Count</b>

    Enter the number of subscriptions the user will receive when purchasing this plan.
    
    <i>For example: 1 - one subscription, 3 - three subscriptions, etc.</i>

msg-plan-durations =
    <b>⏳ Plan Durations</b>

    Select a duration to change the price.

msg-plan-duration =
    <b>⏳ Add Plan Duration</b>

    Enter a new duration (in days).

msg-plan-prices =
    <b>💰 Change Prices for Duration ({ $value ->
            [-1] { unlimited }
            *[other] { unit-day }
        })</b>

    Select a currency price to change.

msg-plan-price =
    <b>💰 Change Price for Duration ({ $value ->
            [-1] { unlimited }
            *[other] { unit-day }
        })</b>

    Enter a new price for currency { $currency }.

msg-plan-allowed-users = 
    <b>👥 Change Allowed Users List</b>

    Enter a user ID to add to the list.

msg-plan-squads =
    <b>🔗 Squads</b>

    { $internal_squads ->
    [0] { empty }
    *[HAS] <b>⏺️ Internal:</b> { $internal_squads }
    }

    { $external_squad ->
    [0] { empty }
    *[HAS] <b>⏹️ External:</b> { $external_squad }
    }

msg-plan-internal-squads =
    <b>⏺️ Change Internal Squads</b>

    Select which internal groups will be assigned to this plan.

msg-plan-external-squads =
    <b>⏹️ Change External Squad</b>

    Select which external group will be assigned to this plan.


# Notifications
msg-notifications-main = <b>🔔 Notification Settings</b>
msg-notifications-user = <b>👥 User Notifications</b>
msg-notifications-system = <b>⚙️ System Notifications</b>


# Subscription
msg-subscription-main = <b>💳 Subscription</b>

    { $subscriptions_count ->
    [0] <blockquote>You have no active subscriptions.</blockquote>
    [1] <blockquote>You have <b>1</b> subscription.</blockquote>
    *[other] <blockquote>You have <b>{ $subscriptions_count }</b> { $subscriptions_count ->
        [one] subscription
        *[other] subscriptions
        }.</blockquote>
    }

msg-subscription-my-subscriptions =
    <b>📋 My Subscriptions</b>

    Select a subscription to view details and get a connection link.

msg-subscription-details-view =
    <b>💳 Subscription #{ $subscription_index }</b>

    <blockquote>
    • Status: { $status ->
        [ACTIVE] 🟢 Active
        [EXPIRED] 🔴 Expired
        [LIMITED] 🟡 Limit reached
        [DISABLED] ⚫ Disabled
        *[OTHER] { $status }
        }
    • Plan: { $plan_name }
    • Traffic limit: { $traffic_limit }
    • Device limit: { $device_limit }
    • Paid at: { $paid_at }
    • Valid until: { $expire_time }
    • Device: { $device_type ->
        [0] not specified
        [ANDROID] 📱 Android
        [IPHONE] 🍏 iPhone
        [WINDOWS] 🖥 Windows
        [MAC] 💻 Mac
        *[OTHER] { $device_type }
        }
    </blockquote>

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

msg-subscription-select-for-renew =
    <b>🔄 Select subscription to renew</b>

    You have multiple subscriptions. Select which one you want to renew.

msg-subscription-select-for-renew-single =
    <b>🔄 Select subscription to renew</b>

    You have multiple subscriptions. Select one subscription you want to renew.

msg-subscription-select-for-renew-multi =
    <b>🔄 Select subscriptions to renew</b>

    Select one or more subscriptions you want to renew.
    { $selected_count ->
    [0] <i>Nothing selected</i>
    [1] <i>1 subscription selected</i>
    [2] <i>2 subscriptions selected</i>
    *[other] <i>{ $selected_count } subscriptions selected</i>
    }

msg-subscription-confirm-renew-selection =
    <b>✅ Confirm Selection</b>

    You selected <b>{ $selected_count }</b> { $selected_count ->
    [1] subscription
    *[other] subscriptions
    } to renew.

    <blockquote>
    { $has_discount ->
    [1] • <b>Cost</b>: <s>{ $total_original_price }{ $currency }</s> <b>{ $final_amount }{ $currency }</b> (−{ $discount_percent }%)
    *[0] • <b>Cost</b>: <b>{ $final_amount }{ $currency }</b>
    }
    </blockquote>

    Click "Continue" to select duration.

msg-subscription-plans = <b>📦 Select Plan</b>
msg-subscription-new-success = To start using our service, click the <code>`{ btn-subscription-connect }`</code> button and follow the instructions!
msg-subscription-renew-success = Your subscription has been extended by { $added_duration }.

msg-subscription-details =
    <b>{ $plan }:</b>
    <blockquote>
    { $description ->
    [0] { empty }
    *[HAS]
    { $description }
    }

    • <b>Traffic limit</b>: { $traffic }
    • <b>Device limit</b>: { $devices }
    { $subscription_count ->
    [1] { empty }
    *[HAS] • <b>Subscription count</b>: { $subscription_count }
    }
    { $period ->
    [0] { empty }
    *[HAS] • <b>Duration</b>: { $period }
    }
    { $final_amount ->
    [0] { empty }
    *[HAS] • <b>Cost</b>: { frg-payment-amount }
    }
    </blockquote>

msg-subscription-duration = 
    <b>⏳ Select Duration</b>

    { msg-subscription-details }

msg-subscription-payment-method =
    <b>💳 Select Payment Method</b>

    { msg-subscription-details }

msg-subscription-confirm =
    { $purchase_type ->
    [RENEW] <b>🛒 Confirm Subscription Renewal</b>
    [ADDITIONAL] <b>🛒 Confirm Additional Subscription Purchase</b>
    *[OTHER] <b>🛒 Confirm Subscription Purchase</b>
    }

    { msg-subscription-details }

    { $purchase_type ->
    [RENEW] <i>⚠️ Your current subscription will be <u>extended</u> by the selected period.</i>
    [ADDITIONAL] <i>💠 An additional subscription will be created for a new device.</i>
    *[OTHER] { empty }
    }

msg-subscription-trial =
    <b>✅ Trial subscription successfully received!</b>

    { msg-subscription-new-success }

msg-subscription-success =
    <b>✅ Payment successful!</b>

    { $purchase_type ->
    [NEW] { msg-subscription-new-success }
    [RENEW] { msg-subscription-renew-success }
    [ADDITIONAL] { msg-subscription-additional-success }
    *[OTHER] { $purchase_type }
    }

msg-subscription-additional-success =
    Additional subscription created successfully!

    <b>{ $plan_name }</b>
    { frg-subscription }
    
    <i>You can now use this subscription on a new device.</i>

msg-subscription-failed = 
    <b>❌ An error occurred!</b>

    Don't worry, support has been notified and will contact you shortly. We apologize for the inconvenience.


# Importer
msg-importer-main =
    <b>📥 Import Users</b>

    Start synchronization: checking all users in RemnaWave. If a user doesn't exist in the bot's database, they will be created with a temporary subscription. If user data differs, it will be automatically updated.

msg-importer-from-xui =
    <b>📥 Import Users (3X-UI)</b>
    
    { $has_exported -> 
    [1]
    <b>🔍 Found:</b>
    <blockquote>
    Total users: { $total }
    With active subscription: { $active }
    With expired subscription: { $expired }
    </blockquote>
    *[0]
    All active users with numeric email will be imported.

    It's recommended to disable users whose email field doesn't contain a Telegram ID beforehand. The operation may take significant time depending on the number of users.

    Send the database file (.db format).
    }

msg-importer-squads =
    <b>🔗 Internal Squads List</b>

    Select which internal groups will be available to imported users.

msg-importer-import-completed =
    <b>📥 User Import Completed</b>
    
    <b>📃 Information:</b>
    <blockquote>
    • <b>Total users</b>: { $total_count }
    • <b>Successfully imported</b>: { $success_count }
    • <b>Failed to import</b>: { $failed_count }
    </blockquote>

msg-importer-sync-completed =
    <b>📥 User Synchronization Completed</b>

    <b>📃 Information:</b>
    <blockquote>
    Total users in panel: { $total_panel_users }
    Total users in bot: { $total_bot_users }

    New users: { $added_users }
    Added subscriptions: { $added_subscription }
    Updated subscriptions: { $updated}
    
    Users without Telegram ID: { $missing_telegram }
    Synchronization errors: { $errors }
    </blockquote>


# Promocodes
msg-promocodes-main = <b>🎟 Promocodes</b>
msg-promocodes-list = <b>📃 Promocode List</b>

msg-promocode-configurator =
    <b>🎟 Promocode Configurator</b>

    <blockquote>
    • <b>Code</b>: { $code }
    • <b>Type</b>: { promocode-type }
    • <b>Availability</b>: { availability-type }
    • <b>Status</b>: { $is_active ->
        [1] 🟢 Active
        *[0] 🔴 Inactive
        }
    </blockquote>

    <blockquote>
    { $promocode_type ->
    [DURATION] • <b>Duration</b>: { $reward }
    [TRAFFIC] • <b>Traffic</b>: { $reward }
    [DEVICES] • <b>Devices</b>: { $reward }
    [SUBSCRIPTION] • <b>Subscription</b>: { frg-plan-snapshot }
    [PERSONAL_DISCOUNT] • <b>Personal discount</b>: { $reward }%
    [PURCHASE_DISCOUNT] • <b>Purchase discount</b>: { $reward }%
    *[OTHER] { $promocode_type }
    }
    • <b>Lifetime</b>: { $lifetime }
    • <b>Activation limit</b>: { $max_activations }
    </blockquote>

    Select an item to change.

msg-promocode-code =
    <b>🏷️ Promocode Code</b>

    Enter a promocode code or click the button to generate a random code.

msg-promocode-type =
    <b>🔖 Reward Type</b>

    Select the promocode reward type.

msg-promocode-availability =
    <b>✴️ Promocode Availability</b>

    Select who can use this promocode.

msg-promocode-reward =
    <b>🎁 Promocode Reward</b>

    { $reward_type ->
    [DURATION] Enter the number of days.
    [TRAFFIC] Enter the amount of GB traffic.
    [DEVICES] Enter the number of devices.
    [PERSONAL_DISCOUNT] Enter personal discount percentage (1-100).
    [PURCHASE_DISCOUNT] Enter purchase discount percentage (1-100).
    *[OTHER] Enter the reward value.
    }

msg-promocode-lifetime =
    <b>⌛ Lifetime</b>

    Enter the number of days the promocode will be valid.
    Enter -1 for unlimited.

msg-promocode-allowed =
    <b>👥 Activation Limit</b>

    Enter the maximum number of activations.
    Enter -1 for unlimited.

msg-subscription-promocode =
    <b>🎟 Activate Promocode</b>

    Enter a promocode to activate.

msg-subscription-promocode-select =
    <b>🎟 Select Subscription for Promocode</b>

    You have active subscriptions. Select which one to add <b>{ $promocode_days }</b> { $promocode_days ->
    [1] day
    *[other] days
    } to.

    Or create a new subscription.

msg-subscription-promocode-select-duration =
    <b>🎟 Select subscription for days</b>

    You have multiple active subscriptions. Select which subscription to add <b>{ $promocode_days }</b> { $promocode_days ->
    [1] day
    *[other] days
    } from the promocode.

msg-subscription-promocode-confirm-new =
    <b>🎟 Create New Subscription</b>

    You are about to create a new subscription with a promocode:

    <blockquote>
    • <b>Plan</b>: { $plan_name }
    • <b>Duration</b>: { $days_formatted }
    </blockquote>

    Click "Create" to confirm.

msg-promocode-plan =
    <b>📦 Select a plan for the promocode</b>

    Select the plan that will be issued when the promocode is activated.

msg-promocode-duration =
    <b>⏳ Select duration</b>

    Select the subscription duration for the plan <b>{ $plan_name }</b>.


# Partner Program (Admin Settings)
msg-partner-admin-main =
    <b>👾 Partner Program</b>

    <blockquote>
    • <b>Status</b>: { $is_enabled ->
        [1] 🟢 Enabled
        *[0] 🔴 Disabled
        }
    • <b>Percentages by level</b>:
      1️⃣ { $level1_percent }%
      2️⃣ { $level2_percent }%
      3️⃣ { $level3_percent }%
    • <b>Tax</b>: { $tax_percent }%
    • <b>Min. withdrawal</b>: { $min_withdrawal }
    </blockquote>

    <b>💳 Payment system fees:</b>
    <blockquote>
    { $gateway_fees }
    </blockquote>

    Select an item to change.

msg-partner-level-percents =
    <b>📊 Percentages by level</b>

    <blockquote>
    1️⃣ Level 1: { $level1_percent }%
    2️⃣ Level 2: { $level2_percent }%
    3️⃣ Level 3: { $level3_percent }%
    </blockquote>

    Enter a new value in format: <code>level=percent</code>
    For example: <code>1=10</code> for 10% at level 1.

msg-partner-level-percent-edit =
    <b>📊 Edit level { $level } percentage</b>

    <blockquote>
    Current percentage: <b>{ $current_percent }%</b>
    </blockquote>

    Enter a new percentage (0-100).

msg-partner-tax-settings =
    <b>🏛 Tax Settings</b>

    <blockquote>
    Current tax: <b>{ $tax_percent }%</b>
    </blockquote>

    Enter the tax percentage (0-100).
    This percentage will be deducted from partner earnings.

msg-partner-gateway-fees =
    <b>💳 Payment System Fees</b>

    Select a payment system to change the fee.

msg-partner-gateway-fee-edit =
    <b>💳 { gateway-type } Fee</b>

    <blockquote>
    Current fee: <b>{ $current_fee }%</b>
    </blockquote>

    Enter the payment system fee percentage (0-100).

msg-partner-min-withdrawal =
    <b>⬇️ Minimum Withdrawal Amount</b>

    <blockquote>
    Current value: <b>{ $min_withdrawal }</b>
    </blockquote>

    Enter the minimum amount for withdrawal.

msg-partner-withdrawals =
    <b>💸 Withdrawal Requests</b>

    { $count ->
    [0] <i>No withdrawal requests.</i>
    [1] <b>1</b> request pending review.
    *[other] <b>{ $count }</b> requests pending review.
    }

msg-partner-withdrawals-list =
    <b>📝 Withdrawal Requests</b>

    List of withdrawal requests from partners. Select a request to view details and process.

msg-partner-withdrawal-details =
    <b>📝 Withdrawal Request Details</b>

    <blockquote>
    • <b>Partner ID</b>: <code>{ $partner_telegram_id }</code>
    • <b>Amount</b>: { $amount_rubles } rubles
    • <b>Status</b>: { $status ->
        [PENDING] 🕓 Pending
        [COMPLETED] ✅ Completed
        [REJECTED] 🚫 Rejected
        *[OTHER] { $status }
        }
    • <b>Created</b>: { $created_at }
    { $processed_at ->
        [0] { empty }
        *[HAS] • <b>Processed</b>: { $processed_at }
    }
    { $payment_details ->
        [Not specified] { empty }
        *[HAS] • <b>Payment details</b>: { $payment_details }
    }
    </blockquote>

    Select an action to process the request:

msg-partner-withdrawal-view =
    <b>💸 Withdrawal Request</b>

    <blockquote>
    • <b>ID</b>: <code>{ $withdrawal_id }</code>
    • <b>Partner</b>: { $partner_user_id }
    • <b>Amount</b>: { $amount }
    • <b>Status</b>: { $status ->
        [PENDING] 🕓 Pending
        [APPROVED] ✅ Approved
        [REJECTED] ❌ Rejected
        *[OTHER] { $status }
        }
    • <b>Created</b>: { $created_at }
    </blockquote>

    { $status ->
    [PENDING] Select an action:
    *[OTHER] { empty }
    }

# Partner Program (User Edit in Admin)
msg-user-partner =
    <b>👾 User Partner Program</b>

    { $is_partner ->
    [1]
    <blockquote>
    • <b>Status</b>: { $is_active ->
        [1] 🟢 Active
        *[0] 🔴 Inactive
        }
    • <b>Balance</b>: { $balance }
    • <b>Total earned</b>: { $total_earned }
    • <b>Referrals invited</b>: { $referrals_count }
    • <b>Created</b>: { $created_at }
    </blockquote>

    <b>📊 Earnings by level:</b>
    <blockquote>
    1️⃣ { $level1_earned } ({ $level1_count } referrals)
    2️⃣ { $level2_earned } ({ $level2_count } referrals)
    3️⃣ { $level3_earned } ({ $level3_count } referrals)
    </blockquote>
    *[0]
    <blockquote>
    User doesn't have a partner account.
    </blockquote>

    <i>Grant partner access so the user can invite referrals and earn % from their payments.</i>
    }

msg-user-partner-balance =
    <b>💰 Adjust Partner Balance</b>

    <b>Current balance: { $current_balance }</b>

    Select from buttons or enter your own value (in rubles) to add or subtract.

msg-user-partner-withdrawals =
    <b>💸 User Withdrawal Requests</b>

    { $count ->
    [0] <i>No withdrawal requests.</i>
    [1] <b>1</b> request.
    *[other] <b>{ $count }</b> requests.
    }

msg-user-partner-settings =
    <b>⚙️ Individual Partner Settings</b>

    <blockquote>
    • <b>Mode</b>: { $use_global ->
        [1] 🌐 Global settings
        *[0] ⚙️ Individual settings
        }
    { $use_global ->
    [1] { empty }
    *[0]
    • <b>Accrual condition</b>: { $accrual_strategy ->
        [ON_FIRST_PAYMENT] 💳 First payment only
        [ON_EACH_PAYMENT] 💸 Every payment
        *[OTHER] { $accrual_strategy }
        }
    • <b>Reward type</b>: { $reward_type ->
        [PERCENT] 📊 Percentage of payment
        [FIXED_AMOUNT] 💰 Fixed amount
        *[OTHER] { $reward_type }
        }
    { $reward_type ->
    [PERCENT]
    • <b>Percentages by level</b>:
      1️⃣ { $level1_percent }%
      2️⃣ { $level2_percent }%
      3️⃣ { $level3_percent }%
    [FIXED_AMOUNT]
    • <b>Fixed amounts</b>:
      1️⃣ { $level1_fixed } rubles
      2️⃣ { $level2_fixed } rubles
      3️⃣ { $level3_fixed } rubles
    *[OTHER] { empty }
    }
    }
    </blockquote>

    Select a parameter to change.

msg-user-partner-accrual-strategy =
    <b>📍 Partner Accrual Condition</b>

    Select when the partner will receive reward for referral:

    <blockquote>
    • <b>First payment only</b> — partner gets reward only for referral's first payment
    • <b>Every payment</b> — partner gets reward for every referral payment
    </blockquote>

msg-user-partner-reward-type =
    <b>🎀 Partner Reward Type</b>

    Select how partner reward is calculated:

    <blockquote>
    • <b>Percentage of payment</b> — percentage of referral's payment amount
    • <b>Fixed amount</b> — fixed reward for each payment
    </blockquote>

msg-user-partner-percent =
    <b>📊 Percentages by level</b>

    <blockquote>
    Current values:
    1️⃣ Level 1: { $current_level1 }%
    2️⃣ Level 2: { $current_level2 }%
    3️⃣ Level 3: { $current_level3 }%

    Global settings:
    1️⃣ { $global_level1 }% | 2️⃣ { $global_level2 }% | 3️⃣ { $global_level3 }%
    </blockquote>

    Select a percentage for each level below or enter manually in format: <code>level percent</code>
    Example: <code>1 15</code> — sets 15% for level 1.

msg-user-partner-percent-level1 =
    <b>1️⃣ Level 1</b> (current: { $current_level1 }%)

msg-user-partner-percent-level2 =
    <b>2️⃣ Level 2</b> (current: { $current_level2 }%)

msg-user-partner-percent-level3 =
    <b>3️⃣ Level 3</b> (current: { $current_level3 }%)

msg-user-partner-percent-edit =
    <b>📊 Edit level { $level } percentage</b>

    <blockquote>
    Current percentage: <b>{ $current_percent }%</b>
    </blockquote>

    Enter a new percentage (0-100).

msg-user-partner-fixed =
    <b>💰 Fixed amounts by level</b>

    <blockquote>
    Current values:
    1️⃣ Level 1: { $current_level1 } rubles
    2️⃣ Level 2: { $current_level2 } rubles
    3️⃣ Level 3: { $current_level3 } rubles
    </blockquote>

    Select an amount for each level below or enter manually in format: <code>level amount</code>
    Example: <code>1 150</code> — sets 150 rubles for level 1.

msg-user-partner-fixed-level1 =
    <b>1️⃣ Level 1</b> (current: { $current_level1 } rubles)

msg-user-partner-fixed-level2 =
    <b>2️⃣ Level 2</b> (current: { $current_level2 } rubles)

msg-user-partner-fixed-level3 =
    <b>3️⃣ Level 3</b> (current: { $current_level3 } rubles)

msg-user-partner-fixed-edit =
    <b>💰 Edit level { $level } amount</b>

    <blockquote>
    Current amount: <b>{ $current_amount } rubles</b>
    </blockquote>

    Enter a new amount (in rubles).

# Partner Program (Client Interface)
msg-partner-main =
    <b>👾 Partner Program</b>

    Invite friends and earn a percentage from every payment they make!

    <b>💰 Your balance:</b>
    <blockquote>
    • <b>Available for withdrawal</b>: { $balance }
    • <b>Total earned</b>: { $total_earned }
    • <b>Withdrawn</b>: { $total_withdrawn }
    </blockquote>

    <b>👥 Your referrals:</b>
    <blockquote>
    • 1️⃣ level: { $level1_count } (earned: { $level1_earned })
    • 2️⃣ level: { $level2_count } (earned: { $level2_earned })
    • 3️⃣ level: { $level3_count } (earned: { $level3_earned })
    </blockquote>

    <b>📊 Your percentages:</b>
    <blockquote>
    • 1️⃣ level: { $level1_percent }%
    • 2️⃣ level: { $level2_percent }%
    • 3️⃣ level: { $level3_percent }%
    </blockquote>

msg-partner-referrals =
    <b>👥 My Referrals</b>

    { $count ->
    [0] <i>You don't have any referrals yet. Share your link with friends!</i>
    [1] You have <b>1</b> referral.
    *[other] You have <b>{ $count }</b> referrals.
    }

msg-partner-earnings =
    <b>📊 Earnings History</b>

    { $count ->
    [0] <i>You don't have any earnings yet.</i>
    *[other] Recent earnings:
    }

msg-partner-earning-item =
    <blockquote>
    • <b>Amount</b>: +{ $amount }
    • <b>Level</b>: { $level ->
        [1] 1️⃣
        [2] 2️⃣
        [3] 3️⃣
        *[OTHER] { $level }
        }
    • <b>From referral</b>: { $referral_id }
    • <b>Date</b>: { $created_at }
    </blockquote>

msg-partner-withdraw =
    <b>💸 Withdrawal</b>

    <blockquote>
    • <b>Available for withdrawal</b>: { $balance }
    • <b>Minimum amount</b>: { $min_withdrawal }
    </blockquote>

    { $can_withdraw ->
    [1] Enter the amount to withdraw or click the button to withdraw all funds.
    *[0] <i>Insufficient funds for withdrawal. Minimum amount: { $min_withdrawal }</i>
    }

msg-partner-withdraw-confirm =
    <b>📝 Confirm Withdrawal Request</b>

    <blockquote>
    • <b>Amount</b>: { $amount }
    • <b>Fee</b>: { $fee } ({ $fee_percent }%)
    • <b>You will receive</b>: { $net_amount }
    </blockquote>

    <i>⚠️ After confirmation, your request will be sent for administrator review. Funds will be transferred after approval.</i>

msg-partner-withdraw-success =
    <b>✅ Withdrawal Request Created</b>

    Your withdrawal request for <b>{ $amount }</b> has been sent for review.
    Administrator will contact you for details.

msg-partner-history =
    <b>📜 Withdrawal History</b>

    { $count ->
    [0] <i>You don't have any withdrawals yet.</i>
    *[other] Your withdrawal requests:
    }

msg-partner-history-item =
    <blockquote>
    • <b>Amount</b>: { $amount }
    • <b>Status</b>: { $status ->
        [PENDING] 🕓 Pending
        [APPROVED] ✅ Approved
        [REJECTED] ❌ Rejected
        *[OTHER] { $status }
        }
    • <b>Date</b>: { $created_at }
    </blockquote>

msg-partner-invite =
    <b>🔗 Invite Friends</b>

    Share your link with friends and earn { $level1_percent }% from every payment they make!

    Your partner link:
    <code>{ $invite_link }</code>

msg-partner-net-earning-info =
    <b>💰 Earning Calculation</b>

    <blockquote>
    • <b>Payment amount</b>: { $payment_amount }
    • <b>Payment system fee</b>: -{ $gateway_fee } ({ $gateway_fee_percent }%)
    • <b>Tax</b>: -{ $tax } ({ $tax_percent }%)
    • <b>Net amount</b>: { $net_amount }
    • <b>Your percentage</b>: { $partner_percent }%
    • <b>Your earning</b>: <b>+{ $partner_earning }</b>
    </blockquote>