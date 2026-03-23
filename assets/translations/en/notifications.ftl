# Errors
ntf-error = <i>❌ An error occurred. Please try again later.</i>
ntf-error-lost-context = <i>⚠️ An error occurred. Dialog restarted.</i>
ntf-error-log-not-found = <i>⚠️ Error: Log file not found.</i>

# Exchange notifications
ntf-exchange-points-no-points = ❌ You don't have enough points to exchange.
ntf-exchange-points-disabled = ❌ Points exchange is temporarily disabled.
ntf-exchange-points-min = ❌ Minimum points for exchange: { $min_points }
ntf-exchange-points-success = ✅ Success! You exchanged { $points } points for { $days } days of subscription.
ntf-exchange-gift-no-plan = ❌ Gift subscription plan is not configured. Please contact the administrator.
ntf-exchange-gift-success = ✅ Promocode created! Code: { $promocode }
ntf-exchange-discount-success = ✅ Success! You received a { $discount }% discount on your next purchase. Spent { $points } points.
ntf-exchange-traffic-success = ✅ Success! You added { $traffic } GB of traffic. Spent { $points } points.
ntf-points-exchange-invalid-value = ❌ Invalid value. Please enter a positive number.
ntf-points-exchange-invalid-percent = ❌ Invalid percentage. Please enter a value between 1 and 100.


# Events
ntf-event-error =
    #EventError

    <b>🔅 Event: An error occurred!</b>

    { $user -> 
    [1]
    { hdr-user }
    { frg-user-info }
    *[0] { space }
    }

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>

ntf-event-error-remnawave =
    #EventError

    <b>🔅 Event: Error connecting to Remnawave!</b>

    <blockquote>
    Proper bot operation is impossible without an active connection!
    </blockquote>

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>

ntf-event-error-webhook =
    #EventError

    <b>🔅 Event: Webhook error detected!</b>

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>

ntf-event-bot-startup =
    #EventBotStarted

    <b>🔅 Event: Bot started!</b>

    <blockquote>
    • <b>Access mode</b>: { access-mode }
    </blockquote>

ntf-event-bot-shutdown =
    #EventBotShutdown

    <b>🔅 Event: Bot stopped!</b>

ntf-event-bot-update =
    #EventBotUpdate

    <b>🔅 Event: New AltShop release detected!</b>

    <blockquote>
    • <b>Current version</b>: { $local_version }
    • <b>Available version</b>: { $remote_version }
    • <b>Release date</b>: { $release_published_at }
    { $has_release_title ->
        [true] • <b>Release title</b>: { $release_title }
       *[false] { "" }
    }
    </blockquote>

ntf-event-new-user =
    #EventNewUser

    <b>🔅 Event: New user!</b>

    { hdr-user }
    { frg-user-info }

    { $has_referrer ->
    [0] { empty }
    *[HAS]
    <b>🤝 Referrer:</b>
    <blockquote>
    • <b>ID</b>: <code>{ $referrer_user_id }</code>
    • <b>Name</b>: { $referrer_user_name } { $referrer_username -> 
        [0] { empty }
        *[HAS] (<a href="tg://user?id={ $referrer_user_id }">@{ $referrer_username }</a>)
    }
    </blockquote>
    }
    
ntf-event-subscription-trial =
    #EventTrialGetted

    <b>🔅 Event: Trial subscription received!</b>

    { hdr-user }
    { frg-user-info }
    
    { hdr-plan }
    { frg-plan-snapshot }

ntf-event-subscription-new =
    #EventSubscriptionNew

    <b>🔅 Event: Subscription purchase!</b>

    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

ntf-event-subscription-renew =
    #EventSubscriptionRenew

    <b>🔅 Event: Subscription renewal!</b>
    
    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

ntf-event-subscription-additional =
    #EventSubscriptionAdditional

    <b>🔅 Event: Additional subscription purchase!</b>

    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

ntf-event-node-connection-lost =
    #EventNode

    <b>🔅 Event: Node connection lost!</b>

    { hdr-node }
    { frg-node-info }

ntf-event-node-connection-restored =
    #EventNode

    <b>🔅 Event: Node connection restored!</b>

    { hdr-node }
    { frg-node-info }

ntf-event-node-traffic =
    #EventNode

    <b>🔅 Event: Node reached traffic limit threshold!</b>

    { hdr-node }
    { frg-node-info }

ntf-event-user-first-connected =
    #EventUser

    <b>🔅 Event: User first connection!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-subscription }
    { frg-subscription-details }

ntf-event-user-expiring =
    <b>⚠️ Attention! Your subscription expires in { unit-day }.</b>

ntf-event-user-expired =
    <b>⛔ Attention! Access suspended — VPN is not working.</b>

    Your subscription has expired, renew it to continue using VPN!

ntf-event-user-expired_ago =
    <b>⛔ Attention! Access suspended — VPN is not working.</b>

    Your subscription expired {unit-day} ago, renew it to continue using VPN!

ntf-event-user-limited =
    <b>⛔ Attention! Access suspended — VPN is not working.</b>

    You have exhausted your traffic limit, renew your subscription to continue using VPN!

ntf-event-user-hwid-added =
    #EventUserHwid

    <b>🔅 Event: New device added for user!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-hwid }
    { frg-user-hwid }

ntf-event-user-hwid-deleted =
    #EventUserHwid

    <b>🔅 Event: Device removed for user!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-hwid }
    { frg-user-hwid }

ntf-event-user-referral-attached =
    <b>🎉 You invited a friend!</b>
    
    <blockquote>
    User <b>{ $name }</b> joined using your invite link! To receive your reward, make sure they purchase a subscription.
    </blockquote>

ntf-event-user-referral-qualified =
    <b>✅ Referral qualified!</b>
    
    <blockquote>
    User <b>{ $name }</b> has met the qualification conditions and now counts in your referral program.
    </blockquote>

ntf-event-user-referral-reward =
    <b>💰 You received a reward!</b>
    
    <blockquote>
    User <b>{ $name }</b> made a payment. You received <b>{ $value } { $reward_type ->
    [POINTS] { $value -> 
        [one] point
        *[other] points 
        }
    [EXTRA_DAYS] extra { $value -> 
        [one] day
        *[other] days
        }
    *[OTHER] { $reward_type }
    }</b> to your subscription!
    </blockquote>

ntf-event-user-referral-reward-error =
    <b>❌ Failed to issue reward!</b>
    
    <blockquote>
    User <b>{ $name }</b> made a payment, but we couldn't credit your reward because <b>you don't have a purchased subscription</b> to which we could add {$value} { $value ->
            [one] extra day
            *[other] extra days
        }.
    
    <i>Purchase a subscription to receive bonuses for invited friends!</i>
    </blockquote>


# Notifications
ntf-command-paysupport = 💸 <b>To request a refund, please contact our support team.</b>
ntf-command-help = 🆘 <b>Click the button below to contact support. We'll help solve your problem.</b>
ntf-channel-join-required = ❇️ Subscribe to our channel and get <b>free days, promotions, and news</b>! After subscribing, click the "Confirm" button.
ntf-channel-join-required-left = ⚠️ You unsubscribed from our channel! Please subscribe to continue using the bot.
ntf-rules-accept-required = ⚠️ <b>Before using the service, please read and accept the <a href="{ $url }">Terms of Service</a>.</b>

ntf-double-click-confirm = <i>⚠️ Click again to confirm the action.</i>
ntf-channel-join-error = <i>⚠️ We don't see your channel subscription. Make sure you subscribed and try again.</i>
ntf-throttling-many-requests = <i>⚠️ You're sending too many requests, please wait a moment.</i>
ntf-squads-empty = <i>⚠️ No squads found. Please check their availability in the panel.</i>
ntf-invite-withdraw-points-error = ❌ You don't have enough points to complete the exchange.
ntf-exchange-points-no-points = <i>❌ You have no points to exchange.</i>
ntf-exchange-points-success = <i>✅ Success! You exchanged <b>{ $points }</b> points for <b>{ $days }</b> days of subscription.</i>
ntf-exchange-points-disabled = <i>❌ Points exchange is temporarily disabled.</i>
ntf-exchange-points-min-not-reached = <i>❌ Minimum points for exchange: <b>{ $min_points }</b>.</i>
ntf-exchange-points-max-exceeded = <i>❌ Maximum points per exchange: <b>{ $max_points }</b>.</i>
ntf-points-exchange-invalid-value = <i>❌ Invalid value. Please enter a positive number.</i>
ntf-points-exchange-updated = <i>✅ Points exchange settings successfully updated.</i>

ntf-connect-not-available =
    ⚠️ { $status -> 
    [LIMITED] You have used all available traffic. Your access is now limited until you purchase a new subscription.
    [EXPIRED] Your subscription has expired. To continue using the service, renew your subscription or purchase a new one.
    *[OTHER] An error occurred while checking status or your subscription was disabled. Try refreshing your data or contact support.
    }

ntf-connect-device-url =
    <b>🔗 Connection Link</b>

    <blockquote>
    <code>{ $url }</code>
    </blockquote>

    <i>Copy the link and paste it into the app to connect.</i>

ntf-subscription-not-found = <i>❌ Subscription not found.</i>

ntf-user-not-found = <i>❌ User not found.</i>
ntf-user-transactions-empty = <i>❌ Transaction list is empty.</i>
ntf-user-subscription-empty = <i>❌ No subscriptions found for this user.</i>
ntf-user-plans-empty = <i>❌ No available plans to issue.</i>
ntf-user-devices-empty = <i>❌ Device list is empty.</i>
ntf-user-invalid-number = <i>❌ Invalid number.</i>
ntf-user-allowed-plans-empty = <i>❌ No available plans to grant access.</i>
ntf-user-message-success = <i>✅ Message sent successfully.</i>
ntf-user-message-not-sent = <i>❌ Failed to send message.</i>
ntf-user-sync-failed = <i>❌ Failed to synchronize user.</i>
ntf-user-sync-success = <i>✅ User synchronization completed.</i>

ntf-user-invalid-expire-time = <i>❌ Unable to { $operation ->
    [ADD] extend subscription by the specified number of days
    *[SUB] reduce subscription by the specified number of days
    }.</i>

ntf-user-invalid-points = <i>❌ Unable to { $operation ->
    [ADD] add the specified number of points
    *[SUB] subtract the specified number of points
    }.</i>

ntf-referral-invalid-reward = <i>❌ Invalid value.</i>

ntf-access-denied = <i>🚧 Bot is in maintenance mode, please try again later.</i>
ntf-access-denied-registration = <i>❌ New user registration is disabled.</i>
ntf-access-denied-only-invited = <i>❌ New user registration is only available through invitation by another user.</i>
ntf-access-denied-purchasing = <i>🚧 Bot is in maintenance mode, you will be notified when the bot is available again.</i>
ntf-access-allowed = <i>❇️ All bot functionality is available again, thank you for waiting.</i>
ntf-access-id-saved = <i>✅ Channel/group ID successfully updated.</i>
ntf-access-link-saved = <i>✅ Channel/group link successfully updated.</i>
ntf-access-channel-invalid = <i>❌ Invalid channel/group link or ID.</i>

ntf-plan-invalid-name = <i>❌ Invalid name.</i>
ntf-plan-invalid-description = <i>❌ Invalid description.</i>
ntf-plan-invalid-tag = <i>❌ Invalid tag.</i>
ntf-plan-invalid-number = <i>❌ Invalid number.</i>
ntf-plan-trial-once-duration = <i>❌ Trial plan can only have one duration.</i>
ntf-plan-trial-already-exists = <i>❌ Trial plan already exists.</i>
ntf-plan-duration-already-exists = <i>❌ This duration already exists.</i>
ntf-plan-duration-last = <i>❌ Cannot delete the last duration.</i>
ntf-plan-save-error = <i>❌ Error saving plan.</i>
ntf-plan-name-already-exists = <i>❌ A plan with this name already exists.</i>
ntf-plan-invalid-user-id = <i>❌ Invalid user ID.</i>
ntf-plan-no-user-found = <i>❌ User not found.</i>
ntf-plan-user-already-allowed = <i>❌ User is already in the allowed list.</i>
ntf-plan-confirm-delete = <i>⚠️ Click again to delete.</i>
ntf-plan-updated-success = <i>✅ Plan successfully updated.</i>
ntf-plan-created-success = <i>✅ Plan successfully created.</i>
ntf-plan-deleted-success = <i>✅ Plan successfully deleted.</i>
ntf-plan-internal-squads-empty = <i>❌ Select at least one internal squad.</i>

ntf-gateway-not-configured = <i>❌ Payment gateway not configured.</i>
ntf-gateway-not-configurable = <i>❌ Payment gateway has no settings.</i>
ntf-gateway-field-wrong-value = <i>❌ Invalid value.</i>
ntf-gateway-test-payment-created = <i>✅ <a href="{ $url }">Test payment</a> successfully created.</i>
ntf-gateway-test-payment-error = <i>❌ An error occurred while creating the test payment.</i>
ntf-gateway-test-payment-confirmed = <i>✅ Test payment successfully processed.</i>

ntf-subscription-plans-not-available = <i>❌ No available plans.</i>
ntf-subscription-gateways-not-available = <i>❌ No available payment systems.</i>
ntf-subscription-renew-plan-unavailable = <i>❌ Your plan is outdated and not available for renewal.</i>
ntf-subscription-payment-creation-failed = <i>❌ An error occurred while creating the payment, please try again later.</i>
ntf-subscription-limit-exceeded = <i>❌ Subscription limit exceeded. You already have { $current } out of { $max } possible subscriptions.</i>
ntf-subscription-deleted = <i>✅ Subscription successfully deleted.</i>
ntf-subscription-select-at-least-one = <i>❌ Select at least one subscription to renew.</i>

ntf-broadcast-list-empty = <i>❌ Broadcast list is empty.</i>
ntf-broadcast-audience-not-available = <i>❌ No available users for the selected audience.</i>
ntf-broadcast-audience-not-active = <i>❌ No users with ACTIVE subscription for this plan.</i>
ntf-broadcast-plans-not-available = <i>❌ No available plans.</i>
ntf-broadcast-empty-content = <i>❌ Content is empty.</i>
ntf-broadcast-wrong-content = <i>❌ Invalid content.</i>
ntf-broadcast-content-saved = <i>✅ Message content successfully saved.</i>
ntf-broadcast-promocode-code-required = <i>❌ Enter a valid promocode first.</i>
ntf-broadcast-promocode-saved = <i>✅ Promocode <b>{ $code }</b> saved for this broadcast.</i>
ntf-broadcast-promocode-cleared = <i>✅ Promocode removed from this broadcast.</i>
ntf-broadcast-promocode-button-enabled = <i>✅ Promocode button enabled for this broadcast.</i>
ntf-broadcast-promocode-button-disabled = <i>✅ Promocode button disabled for this broadcast.</i>
ntf-broadcast-promocode-webapp-missing = <i>❌ WEB_APP_URL or BOT_MINI_APP URL is required to use promo buttons in broadcast.</i>
ntf-broadcast-preview = { $content }
ntf-broadcast-not-cancelable = <i>❌ Broadcast cannot be canceled.</i>
ntf-broadcast-canceled = <i>✅ Broadcast successfully canceled.</i>
ntf-broadcast-deleting = <i>⚠️ Deleting all sent messages.</i>
ntf-broadcast-already-deleted = <i>❌ Broadcast is being deleted or already deleted.</i>

ntf-broadcast-deleted-success =
    ✅ Broadcast <code>{ $task_id }</code> successfully deleted.

    <blockquote>
    • <b>Total messages</b>: { $total_count }
    • <b>Successfully deleted</b>: { $deleted_count }
    • <b>Failed to delete</b>: { $failed_count }
    </blockquote>

ntf-trial-unavailable = <i>❌ Trial subscription is temporarily unavailable.</i>

# Multi Subscription
ntf-multi-subscription-invalid-value = <i>❌ Invalid value. Enter a positive number or -1 for unlimited.</i>
ntf-multi-subscription-disabled = <i>❌ Multi-subscription is disabled. Enable it first in RemnaShop settings.</i>
ntf-multi-subscription-updated = <i>✅ Multi-subscription settings updated.</i>

# Promocodes
ntf-promocode-not-found = <i>❌ Promocode not found.</i>
ntf-promocode-inactive = <i>❌ Promocode is inactive.</i>
ntf-promocode-expired = <i>❌ Promocode has expired.</i>
ntf-promocode-depleted = <i>❌ Promocode activation limit reached.</i>
ntf-promocode-already-activated = <i>❌ You have already activated this promocode.</i>
ntf-promocode-not-available = <i>❌ Promocode is not available for you.</i>
ntf-promocode-reward-failed = <i>❌ Failed to apply promocode reward.</i>
ntf-promocode-activation-error = <i>❌ An error occurred while activating the promocode. Please try again later.</i>
ntf-promocode-error = <i>❌ An error occurred while activating the promocode.</i>
ntf-promocode-no-subscription = <i>❌ An active subscription is required to activate this promocode.</i>
ntf-promocode-no-subscription-for-duration = <i>❌ You have no active subscriptions to add days to. Please purchase a subscription first.</i>

ntf-promocode-activated = <i>✅ Promocode <b>{ $code }</b> successfully activated!</i>
ntf-promocode-activated-duration = <i>✅ Promocode <b>{ $code }</b> activated! { $reward } added to your subscription.</i>
ntf-promocode-activated-traffic = <i>✅ Promocode <b>{ $code }</b> activated! { $reward } traffic added.</i>
ntf-promocode-activated-devices = <i>✅ Promocode <b>{ $code }</b> activated! { $reward } devices added.</i>
ntf-promocode-activated-subscription = <i>✅ Promocode <b>{ $code }</b> activated! Subscription granted.</i>
ntf-promocode-activated-subscription-extended = <i>✅ Promocode <b>{ $code }</b> activated! { $days } { $days ->
    [1] day
    *[other] days
    } added to your subscription.</i>
ntf-promocode-activated-personal-discount = <i>✅ Promocode <b>{ $code }</b> activated! Personal discount of { $reward } set.</i>
ntf-promocode-activated-purchase-discount = <i>✅ Promocode <b>{ $code }</b> activated! { $reward } discount on next purchase set.</i>

ntf-promocode-code-required = <i>❌ Please enter the promocode code.</i>
ntf-promocode-plan-required = <i>❌ Please select a plan for the "Subscription" type promocode.</i>
ntf-promocode-reward-required = <i>❌ Please specify the promocode reward.</i>
ntf-promocode-allowed-users-required = <i>❌ Add at least one user for ALLOWED availability.</i>
ntf-promocode-code-exists = <i>❌ A promocode with this code already exists.</i>
ntf-promocode-created = <i>✅ Promocode successfully created.</i>
ntf-promocode-updated = <i>✅ Promocode successfully updated.</i>
ntf-promocode-deleted = <i>✅ Promocode successfully deleted.</i>
ntf-invalid-value = <i>❌ Invalid value.</i>

ntf-event-promocode-activated =
    #EventPromocodeActivated

    <b>🔅 Event: Promocode activated!</b>

    { hdr-user }
    { frg-user-info }

    <b>🎟 Promocode:</b>
    <blockquote>
    • <b>Code</b>: { $code }
    • <b>Reward type</b>: { $reward_type }
    • <b>Reward</b>: { $reward }
    </blockquote>

ntf-importer-not-file = <i>⚠️ Please send the database as a file.</i>
ntf-importer-db-invalid = <i>❌ This file cannot be imported.</i>
ntf-importer-db-failed = <i>❌ Error importing database.</i>
ntf-importer-exported-users-empty =  <i>❌ User list in database is empty.</i>
ntf-importer-internal-squads-empty = <i>❌ Select at least one internal squad.</i>
ntf-importer-import-started = <i>✅ User import started, please wait...</i>
ntf-importer-sync-started = <i>✅ User synchronization started, please wait...</i>
ntf-importer-users-not-found = <i>❌ Could not find users to synchronize.</i>
ntf-importer-not-support = <i>⚠️ Full data import from 3xui-shop is temporarily unavailable. You can use import from 3X-UI panel!</i>


# Partner Program
ntf-partner-created = <i>✅ Partner access successfully granted to user.</i>
ntf-partner-activated = <i>✅ Partner account activated.</i>
ntf-partner-deactivated = <i>✅ Partner account deactivated.</i>
ntf-partner-deleted = <i>✅ Partner account deleted.</i>
ntf-partner-already-exists = <i>❌ User already has a partner account.</i>
ntf-partner-not-found = <i>❌ Partner account not found.</i>
ntf-partner-disabled = <i>❌ Partner program is disabled.</i>

ntf-partner-balance-insufficient = <i>❌ Insufficient balance for withdrawal.</i>
ntf-partner-balance-updated = <i>✅ Partner balance successfully updated.</i>
ntf-partner-balance-invalid-amount = <i>❌ Invalid amount. Enter a number (positive to add, negative to subtract).</i>

ntf-partner-invalid-percent = <i>❌ Invalid percentage. Enter a number from 0 to 100.</i>
ntf-partner-invalid-amount = <i>❌ Invalid amount. Enter a positive number.</i>
ntf-partner-invalid-level = <i>❌ Invalid level. Allowed values: 1, 2, 3.</i>
ntf-partner-percent-updated = <i>✅ Level { $level } percentage updated to { $percent }%.</i>
ntf-partner-tax-updated = <i>✅ Tax rate updated to { $percent }%.</i>
ntf-partner-gateway-fee-updated = <i>✅ Payment system fee updated to { $percent }%.</i>
ntf-partner-min-withdrawal-updated = <i>✅ Minimum withdrawal amount updated to { $amount }.</i>
ntf-partner-settings-updated = <i>✅ Partner program settings updated.</i>
ntf-partner-individual-settings-updated = <i>✅ Individual partner settings updated.</i>
ntf-partner-invalid-percent-format = <i>❌ Invalid format. Enter in format: <code>level percent</code> (e.g., 1 15)</i>
ntf-partner-invalid-amount-format = <i>❌ Invalid amount. Enter a positive number.</i>

ntf-partner-withdraw-min-not-reached = <i>❌ Minimum withdrawal amount: { $min_withdrawal }.</i>
ntf-partner-withdraw-insufficient-balance = <i>❌ Insufficient balance.</i>
ntf-partner-withdraw-request-created = <i>✅ Withdrawal request created and sent for review.</i>
ntf-partner-balance-currency-updated = <i>✅ Partner balance currency updated: { $currency }.</i>
ntf-partner-withdraw-approved = <i>✅ Withdrawal request approved.</i>
ntf-partner-withdraw-rejected = <i>❌ Withdrawal request rejected.</i>
ntf-partner-withdraw-already-processed = <i>❌ Request has already been processed.</i>

ntf-partner-withdrawals-empty = <i>📭 No withdrawal requests.</i>

# Admin notifications for withdrawal processing
ntf-partner-withdrawal-approved = <i>✅ Withdrawal request successfully completed.</i>
ntf-partner-withdrawal-pending-set = <i>💭 Request marked as "Under review".</i>
ntf-partner-withdrawal-rejected = <i>🚫 Withdrawal request rejected.</i>
ntf-partner-withdrawal-error = <i>❌ Error processing withdrawal request.</i>

# User (partner) notifications about withdrawal status
ntf-partner-withdrawal-completed =
    <b>✅ Your withdrawal request completed!</b>
    
    <blockquote>
    Amount <b>{ $amount }</b> rubles has been successfully withdrawn.
    </blockquote>

ntf-partner-withdrawal-under-review =
    <b>💭 Your withdrawal request is under review</b>
    
    <blockquote>
    Withdrawal request for <b>{ $amount }</b> rubles has been placed under review.
    Please wait for the administrator's decision.
    </blockquote>

ntf-partner-withdrawal-rejected-user =
    <b>🚫 Your withdrawal request was rejected</b>
    
    <blockquote>
    Withdrawal request for <b>{ $amount }</b> rubles was rejected.
    Reason: { $reason }
    Funds have been returned to your partner balance.
    </blockquote>

ntf-event-partner-earning =
    <b>💰 Partner program earning!</b>
    
    <blockquote>
    Referral <b>{ $referral_name }</b> ({ $level ->
        [1] 1️⃣ level
        [2] 2️⃣ level
        [3] 3️⃣ level
        *[OTHER] level { $level }
    }) made a payment.
    You earned <b>+{ $amount }</b>!
    </blockquote>
    
    <b>Your balance:</b> { $new_balance }

ntf-event-partner-referral-registered =
    <b>🤝 New partner referral!</b>
    
    <blockquote>
    User <b>{ $name }</b> registered via your partner link.
    </blockquote>

ntf-event-partner-withdrawal-approved =
    <b>✅ Withdrawal request approved!</b>
    
    <blockquote>
    Your withdrawal request for <b>{ $amount }</b> was approved by the administrator.
    </blockquote>

ntf-event-partner-withdrawal-rejected =
    <b>❌ Withdrawal request rejected</b>
    
    <blockquote>
    Your withdrawal request for <b>{ $amount }</b> was rejected.
    Funds have been returned to your partner balance.
    </blockquote>

ntf-event-partner-withdrawal-request =
    #EventPartnerWithdrawal
    
    <b>🔅 Event: New withdrawal request!</b>
    
    { hdr-user }
    { frg-user-info }
    
    <b>💸 Request:</b>
    <blockquote>
    • <b>Amount</b>: { $amount }
    • <b>Partner balance</b>: { $partner_balance }
    </blockquote>

# Backup System
ntf-backup-creating = <i>🔄 Creating database backup...</i>
ntf-backup-created-success = <i>✅ Backup created successfully!</i>

    <blockquote>
    { $message }
    </blockquote>

ntf-backup-created-failed = <i>❌ Backup creation failed</i>

    <blockquote>
    { $message }
    </blockquote>

ntf-backup-restoring = <i>📥 Restoring from backup...</i>

    <blockquote>
    • <b>File</b>: <code>{ $filename }</code>
    • <b>Clear existing data</b>: { $clear_existing ->
        [true] Yes
        *[false] No
    }
    </blockquote>

ntf-backup-restored-success = <i>✅ Restore completed!</i>

    <blockquote>
    { $message }
    </blockquote>

ntf-backup-restored-failed = <i>❌ Restore failed</i>

    <blockquote>
    { $message }
    </blockquote>
# Importer plan assignment notifications
ntf-importer-sync-warning-no-active-plans = <i>⚠️ Before sync: create and activate a plan first, otherwise bulk assignment for this run will be unavailable. Press again to start sync.</i>
ntf-importer-sync-warning-has-active-plans = <i>ℹ️ After sync you can assign a selected plan to all users from this run. Individual adjustment is available in the user profile. Press again to start sync.</i>
ntf-importer-assign-plan-all-started = <i>⏳ Bulk plan assignment started, please wait...</i>
ntf-importer-assign-plan-all-done = <i>✅ Bulk plan assignment completed.</i>

    <blockquote>
    Updated subscriptions: { $updated }
    Skipped (no current subscription): { $skipped_no_subscription }
    Skipped (deleted subscription): { $skipped_deleted }
    Skipped (already assigned manually): { $skipped_already_assigned }
    Errors: { $errors }
    </blockquote>

ntf-importer-assign-plan-all-no-users = <i>❌ No users from the latest synchronization are available for bulk assignment.</i>
ntf-importer-assign-plan-all-no-plan = <i>❌ Select a plan before starting bulk assignment.</i>

# User plan assignment notifications
ntf-user-assign-plans-empty = <i>❌ No active plans available for assignment.</i>
ntf-user-plan-assigned = <i>✅ Plan <b>{ $plan_name }</b> has been assigned to the user's current subscription.</i>

ntf-event-web-user-registered =
    #EventWebUserRegistered

    <b>🆕 Event: User registered via Web!</b>

    { hdr-user }
    { frg-user-info }

    <b>🌐 Web:</b>
    <blockquote>
    • <b>Web login</b>: <code>{ $web_username }</code>
    • <b>Source</b>: { $auth_source }
    </blockquote>

ntf-event-web-account-linked =
    #EventWebAccountLinked

    <b>🔗 Event: Web account synced with Telegram!</b>

    { hdr-user }
    { frg-user-info }

    <b>🌐 Link details:</b>
    <blockquote>
    • <b>Web login</b>: <code>{ $web_username }</code>
    • <b>Previous profile ID</b>: <code>{ $old_user_id }</code>
    • <b>Linked Telegram ID</b>: <code>{ $linked_telegram_id }</code>
    </blockquote>

ntf-user-web-password-reset-issued =
    🔐 Temporary web password issued.

    <blockquote>
    • Login: <code>{ $username }</code>
    • Password: <code>{ $temp_password }</code>
    • Expires at: <b>{ $expires_at }</b>
    </blockquote>

    Share this password with the user manually. Password change will be required on first login.

ntf-user-web-password-reset-failed = ❌ Failed to reset web password: { $error }
ntf-plan-delete-blocked = <i>❌ This plan cannot be deleted while it is used by subscriptions or transitions. Archive it instead.</i>
ntf-plan-validation-error = <i>❌ Plan validation error: { $error }</i>
ntf-referral-invite-link-unavailable = <i>⚠️ Active invite link is unavailable right now. Check expiration time and free slots.</i>
ntf-referral-invite-regenerated = <i>✅ A new invite link has been generated.</i>
ntf-referral-invite-regenerate-blocked = <i>🚫 Cannot generate a new invite link because no free invite slots remain.</i>
ntf-access-denied-only-invited-soft = <i>🔒 This section is available only for invited users. Open the bot using a valid invite link.</i>
