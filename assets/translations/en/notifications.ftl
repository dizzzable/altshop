# Errors
ntf-error = <i>❌ An error occurred. Please try again later.</i>
ntf-error-lost-context = <i>⚠️ An error occurred. Dialog restarted.</i>
ntf-error-log-not-found = <i>⚠️ Error: Log file not found.</i>

# Exchange Points
ntf-exchange-points-no-points = <i>❌ You have no points to exchange.</i>
ntf-exchange-points-success = <i>✅ Success! You exchanged <b>{ $points }</b> points for <b>{ $days }</b> days of subscription.</i>
ntf-exchange-points-disabled = <i>❌ Points exchange is temporarily disabled.</i>
ntf-exchange-points-min-not-reached = <i>❌ Minimum points for exchange: <b>{ $min_points }</b>.</i>
ntf-exchange-points-max-exceeded = <i>❌ Maximum points per exchange: <b>{ $max_points }</b>.</i>
ntf-points-exchange-invalid-value = <i>❌ Invalid value. Please enter a positive number.</i>
ntf-points-exchange-invalid-percent = <i>❌ Invalid percentage. Please enter a value between 1 and 100.</i>
ntf-points-exchange-updated = <i>✅ Points exchange settings successfully updated.</i>
ntf-exchange-gift-no-plan = <i>❌ Gift subscription plan is not configured. Please contact the administrator.</i>
ntf-exchange-gift-success = <i>✅ Promocode created! Code: { $promocode }</i>
ntf-exchange-discount-success = <i>✅ Success! You received a { $discount }% discount on your next purchase. Spent { $points } points.</i>
ntf-exchange-traffic-success = <i>✅ Success! You added { $traffic } GB of traffic. Spent { $points } points.</i>

# Subscriptions
ntf-subscription-limit-exceeded = <i>❌ Subscription limit exceeded. You already have { $current } out of { $max } possible subscriptions.</i>
ntf-subscription-deleted = <i>✅ Subscription successfully deleted.</i>
ntf-user-subscription-empty = <i>❌ Current subscription not found.</i>
ntf-subscription-renew-plan-unavailable = <i>❌ Your plan is outdated and not available for renewal.</i>

ntf-event-subscription-additional =
    #EventSubscriptionAdditional

    <b>🔅 Event: Additional subscription purchase!</b>

    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

# Promocodes
ntf-promocode-no-subscription-for-duration = <i>❌ You have no active subscriptions to add days to. Please purchase a subscription first.</i>
ntf-promocode-plan-required = <i>❌ Please select a plan for the "Subscription" type promocode.</i>
ntf-promocode-code-required = <i>❌ Please enter the promocode code.</i>
ntf-promocode-reward-required = <i>❌ Please specify the promocode reward.</i>
ntf-promocode-code-exists = <i>❌ A promocode with this code already exists.</i>
ntf-promocode-created = <i>✅ Promocode successfully created.</i>
ntf-promocode-updated = <i>✅ Promocode successfully updated.</i>
ntf-promocode-deleted = <i>✅ Promocode successfully deleted.</i>
ntf-invalid-value = <i>❌ Invalid value.</i>