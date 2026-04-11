# Layout
space = {" "}
empty = { "!empty!" }
btn-test = Button
msg-test = Message
development = Temporarily unavailable!
test-payment = Test payment
unlimited = ∞
unknown = —

unit-unlimited = { $value ->
    [-1] { unlimited }
    [0] { unlimited }
    *[other] { $value }
}

# Other
payment-invoice-description = { purchase-type } subscription { $name } for { $duration }
payment-invoice-description-multi = { purchase-type } { $count } { $count ->
    [one] subscription
    *[other] subscriptions
} for { $duration }
contact-support-help = Hello! I need help.
contact-support-paysupport = Hello! I would like to request a refund.
contact-support-withdraw-points = Hello! I would like to request a points exchange.
cmd-start = Restart bot
cmd-paysupport = Refund
cmd-help = Help

referral-invite-message =
    { space }
    🚀 Hey! Want a stable and fast VPN?  
    
    ↘️ CLICK HERE AND TRY FOR FREE!
    { $url }


# Headers
hdr-user = <b>👤 User:</b>
hdr-user-profile = <b>👤 Profile:</b>

hdr-subscription = { $is_trial ->
    [1] <b>🎁 Trial Subscription:</b>
    *[0] <b>💳 Subscription:</b>
    }

hdr-plan = <b>📦 Plan:</b>
hdr-payment = <b>💰 Payment:</b>
hdr-error = <b>⚠️ Error:</b>
hdr-node = <b>🖥 Node:</b>
hdr-hwid = <b>📱 Device:</b>

# Fragments
frg-user =
    <blockquote>
    • <b>ID</b>: <code>{ $user_id }</code>
    • <b>Name</b>: { $user_name }
    { $personal_discount ->
    [0] { empty }
    *[HAS] • <b>Your discount</b>: { $personal_discount }%
    }
    </blockquote>

frg-user-info =
    <blockquote>
    • <b>ID</b>: <code>{ $user_id }</code>
    • <b>Name</b>: { $user_name } { $username -> 
        [0] { empty }
        *[HAS] (<a href="tg://user?id={ $user_id }">@{ $username }</a>)
    }
    </blockquote>

frg-user-details =
    <blockquote>
    • <b>Internal ID</b>: <code>{ $user_id }</code>
    • <b>Identity</b>: { identity-kind }
    { $has_linked_telegram_id ->
    [1] • <b>Linked Telegram ID</b>: <code>{ $linked_telegram_id }</code>
    *[0] { empty }
    }
    { $has_web_login ->
    [1] • <b>Web login</b>: <code>{ $web_login }</code>
    *[0] { empty }
    }
    { $has_public_username ->
    [1] • <b>Profile username</b>: @{ $public_username }
    *[0] { empty }
    }
    • <b>Name</b>: { $user_name }
    • <b>Role</b>: { role }
    • <b>Language</b>: { language }
    { $show_points ->
    [1] • <b>Points</b>: { $points }
    *[0] { empty }
    }
    </blockquote>

frg-user-discounts-details =
    <blockquote>
    • <b>Personal</b>: { $personal_discount }%
    • <b>Next purchase</b>: { $purchase_discount }%
    </blockquote>

frg-subscription =
    <blockquote>
    • <b>Traffic limit</b>: { $traffic_limit }
    • <b>Device limit</b>: { $device_limit }
    • <b>Remaining</b>: { $expire_time }
    { $subscriptions_count ->
    [0] { empty }
    [1] { empty }
    *[other] • <b>Total subscriptions</b>: { $subscriptions_count }
    }
    </blockquote>

frg-subscription-details =
    <blockquote>
    • <b>ID</b>: <code>{ $subscription_id }</code>
    • <b>Status</b>: { subscription-status }
    • <b>Traffic</b>: { $traffic_used } / { $traffic_limit }
    • <b>Device limit</b>: { $device_limit }
    • <b>Remaining</b>: { $expire_time }
    </blockquote>

frg-payment-info =
    <blockquote>
    • <b>ID</b>: <code>{ $payment_id }</code>
    • <b>Payment method</b>: { gateway-type }
    • <b>Amount</b>: { frg-payment-amount }
    </blockquote>

frg-payment-amount = { $final_amount }{ $currency } { $discount_percent -> 
    [0] { space }
    *[more] { space } <strike>{ $original_amount }{ $currency }</strike> (-{ $discount_percent }%)
    }

frg-plan-snapshot =
    <blockquote>
    • <b>Plan</b>: <code>{ $plan_name }</code>
    • <b>Type</b>: { plan-type }
    • <b>Traffic limit</b>: { $plan_traffic_limit }
    • <b>Device limit</b>: { $plan_device_limit }
    • <b>Duration</b>: { $plan_duration }
    </blockquote>

frg-plan-snapshot-comparison =
    <blockquote>
    • <b>Plan</b>: <code>{ $previous_plan_name }</code> -> <code>{ $plan_name }</code>
    • <b>Type</b>: { $previous_plan_type } -> { plan-type }
    • <b>Traffic limit</b>: { $previous_plan_traffic_limit } -> { $plan_traffic_limit }
    • <b>Device limit</b>: { $previous_plan_device_limit } -> { $plan_device_limit }
    • <b>Duration</b>: { $previous_plan_duration } -> { $plan_duration }
    </blockquote>

frg-node-info =
    <blockquote>
    • <b>Name</b>: { $country } { $name }
    • <b>Address</b>: <code>{ $address }:{ $port }</code>
    • <b>Traffic</b>: { $traffic_used } / { $traffic_limit }
    • <b>Last status</b>: { $last_status_message }
    • <b>Status changed</b>: { $last_status_change }
    </blockquote>

frg-user-hwid =
    <blockquote>
    • <b>HWID</b>: <code>{ $hwid }</code>

    • <b>Platform</b>: { $platform }
    • <b>Model</b>: { $device_model }
    • <b>OS Version</b>: { $os_version }
    • <b>Agent</b>: { $user_agent }
    </blockquote>

# Roles
role-dev = Developer
role-admin = Administrator
role-user = User
role = 
    { $role ->
    [DEV] { role-dev }
    [ADMIN] { role-admin }
    *[USER] { role-user }
}

identity-kind = 
    { $identity_kind ->
    [WEB_ONLY] Web-only
    [TELEGRAM_PROVISIONAL] Telegram provisional
    [TELEGRAM_LINKED] Telegram linked
    *[TELEGRAM_ONLY] Telegram only
}


# Units
unit-device = { $value -> 
    [-1] { unlimited }
    *[other] { $value } 
} { $value ->
    [-1] { space }
    [one] device
    *[other] devices
}

unit-byte = { $value } B
unit-kilobyte = { $value } KB
unit-megabyte = { $value } MB
unit-gigabyte = { $value } GB
unit-terabyte = { $value } TB

unit-second = { $value } { $value ->
    [one] second
    *[other] seconds
}

unit-minute = { $value } { $value ->
    [one] minute
    *[other] minutes
}

unit-hour = { $value } { $value ->
    [one] hour
    *[other] hours
}

unit-day = { $value } { $value ->
    [one] day
    *[other] days
}

unit-month = { $value } { $value ->
    [one] month
    *[other] months
}

unit-year = { $value } { $value ->
    [one] year
    *[other] years
}


# Types
plan-type = { $plan_type -> 
    [TRAFFIC] Traffic
    [DEVICES] Devices
    [BOTH] Traffic + Devices
    [UNLIMITED] Unlimited
    *[OTHER] { $plan_type }
}

promocode-type = { $promocode_type -> 
    [DURATION] Duration
    [TRAFFIC] Traffic
    [DEVICES] Devices
    [SUBSCRIPTION] Subscription
    [PERSONAL_DISCOUNT] Personal Discount
    [PURCHASE_DISCOUNT] Purchase Discount
    *[OTHER] { $promocode_type }
}

availability-type = { $availability_type -> 
    [ALL] For Everyone
    [NEW] For New Users
    [EXISTING] For Existing Users
    [INVITED] For Invited
    [ALLOWED] For Allowed
    [TRIAL] For Trial
    *[OTHER] { $availability_type }
}

gateway-type = { $gateway_type ->
    [TELEGRAM_STARS] Telegram Stars
    [YOOKASSA] YooKassa
    [YOOMONEY] YooMoney
    [CRYPTOMUS] Cryptomus
    [HELEKET] Heleket
    [CRYPTOPAY] CryptoBot
    [TBANK] T-Bank
    [PAL24] PayPalych
    [WATA] WATA
    [PLATEGA] Platega
    [ROBOKASSA] Robokassa
    [URLPAY] UrlPay
    *[OTHER] { $gateway_type }
}

# Partner gateway keys (lowercase for use in partner settings)
yookassa = YooKassa
telegram_stars = Telegram Stars
cryptopay = CryptoBot
heleket = Heleket
pal24 = PayPalych
wata = WATA
platega = Platega

access-mode = { $access_mode ->
    [PUBLIC] 🟢 Open for Everyone
    [INVITED] ⚪ Open for Invited
    [PURCHASE_BLOCKED] 🟡 Purchases Blocked
    [REG_BLOCKED] 🟠 Registration Blocked
    [RESTRICTED] 🔴 Closed for Everyone
    *[OTHER] { $access_mode }
}

audience-type = { $audience_type ->
    [ALL] Everyone
    [PLAN] By Plan
    [SUBSCRIBED] With Subscription
    [UNSUBSCRIBED] Without Subscription
    [EXPIRED] Expired
    [TRIAL] With Trial
    *[OTHER] { $audience_type }
}

broadcast-status = { $broadcast_status ->
    [PROCESSING] Processing
    [COMPLETED] Completed
    [CANCELED] Canceled
    [DELETED] Deleted
    [ERROR] Error
    *[OTHER] { $broadcast_status }
}

transaction-status = { $transaction_status ->
    [PENDING] Pending
    [COMPLETED] Completed
    [CANCELED] Canceled
    [REFUNDED] Refunded
    [FAILED] Failed
    *[OTHER] { $transaction_status }
}

subscription-status = { $subscription_status ->
    [ACTIVE] Active
    [DISABLED] Disabled
    [LIMITED] Traffic Exhausted
    [EXPIRED] Expired
    [DELETED] Deleted
    *[OTHER] { $subscription_status }
}

purchase-type = { $purchase_type ->
    [NEW] Purchase
    [RENEW] Renewal
    [CHANGE] Change
    *[OTHER] { $purchase_type }
}

traffic-strategy = { $strategy_type -> 
    [NO_RESET] On Payment
    [DAY] Every Day
    [WEEK] Every Week
    [MONTH] Every Month
    *[OTHER] { $strategy_type }
    }

reward-type = { $reward_type -> 
    [POINTS] Points
    [EXTRA_DAYS] Days
    *[OTHER] { $reward_type }
    }

accrual-strategy = { $accrual_strategy_type -> 
    [ON_FIRST_PAYMENT] First Payment
    [ON_EACH_PAYMENT] Every Payment
    *[OTHER] { $accrual_strategy_type }
    }

reward-strategy = { $reward_strategy_type -> 
    [AMOUNT] Fixed
    [PERCENT] Percentage
    *[OTHER] { $reward_strategy_type }
    }

language = { $language ->
    [ar] Arabic
    [az] Azerbaijani
    [be] Belarusian
    [cs] Czech
    [de] German
    [en] English
    [es] Spanish
    [fa] Persian
    [fr] French
    [he] Hebrew
    [hi] Hindi
    [id] Indonesian
    [it] Italian
    [ja] Japanese
    [kk] Kazakh
    [ko] Korean
    [ms] Malay
    [nl] Dutch
    [pl] Polish
    [pt] Portuguese
    [ro] Romanian
    [ru] Russian
    [sr] Serbian
    [tr] Turkish
    [uk] Ukrainian
    [uz] Uzbek
    [vi] Vietnamese
    *[OTHER] { $language }
}
