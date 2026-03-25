# Changelog

All notable changes to this repository will be documented in this file.

The format is based on Keep a Changelog, adapted for the public AltShop GitHub mirror.

## [Unreleased]

## [1.2.8] - 2026-03-25

### Changed

- `clear_existing` database restore now clears restore-owned tables in one atomic PostgreSQL `TRUNCATE ... RESTART IDENTITY CASCADE` pass, which avoids half-cleared transactions and removes dependent invite/account records safely before inserts begin
- merge restore for `users` now reconciles existing rows through direct scalar SQL updates keyed by `telegram_id`, so restore no longer mutates ORM relationship graphs while user and subscription links are being rebuilt
- new backups now include durable `referral_invites` and `web_accounts` data, while older archives that do not contain those tables still restore as empty sets

### Fixed

- `clear_existing=true` restore no longer aborts on foreign keys like `referral_invites_inviter_telegram_id_fkey` and no longer continues inside an already failed transaction
- merge and full restore no longer fail on SQLAlchemy `Circular dependency detected` while syncing existing users and post-restore subscription links
- restore failure notifications remain short and Telegram-safe, while full technical details stay only in server logs

## [1.2.7] - 2026-03-25

### Changed

- deferred `users.current_subscription_id` relinking now runs as a direct scalar database update after subscriptions are restored, which avoids SQLAlchemy relationship graph cycles during merge/full restore
- restore failure text is now summarized before it is returned to the bot flow, while full exception details remain in server logs

### Fixed

- restoring `DB` and `Full` backups no longer fails on SQLAlchemy `Circular dependency detected` when users and subscriptions are re-linked after a merge restore
- overly long restore-failure notifications are now truncated safely before sending to Telegram, so backup error alerts no longer fail with `message is too long`

## [1.2.6] - 2026-03-25

### Changed

- deferred restore updates now carry an explicit phase, and user `current_subscription_id` links are applied only in the post-subscription phase of database recovery

### Fixed

- restoring `DB` and `Full` backups no longer fails on `fk_users_current_subscription_id` when a backup references current subscriptions that are missing or restored later in the pipeline
- missing subscription targets during deferred user relinking are now skipped with a warning instead of aborting the whole restore

## [1.2.5] - 2026-03-25

### Changed

- merge-restore for `users` now reconciles existing rows by `telegram_id`, so imported backups can update live users instead of trying to insert duplicates with a different internal `id`
- restore now defers `users.current_subscription_id` until after `subscriptions` are restored, which keeps the cyclic user/subscription linkage consistent during database recovery

### Fixed

- restoring `DB` and `Full` backups into a non-empty instance no longer fails on `users_telegram_id_key` when the target database already contains users created after the backup was taken
- user restore no longer risks tripping a follow-up foreign-key problem on `current_subscription_id` before subscription rows are back in place

## [1.2.4] - 2026-03-25

### Changed

- restore now detects legacy backups that contain `plan_durations` and related plan snapshots but an empty `plans` table, and reconstructs minimal plan records before restoring child tables
- backup restore notifications now escape service error text before sending HTML-formatted Telegram messages, so failed restore alerts do not break on raw exception text

### Fixed

- restoring legacy broken archives from `1.2.1` and earlier no longer immediately dies on `plan_durations_plan_id_fkey` when the backup lost the parent `plans` rows during export
- backup failure notifications no longer crash with Telegram `can't parse entities` errors when the restore exception text contains fragments like `<class ...>`

## [1.2.3] - 2026-03-25

### Changed

- database restore now flushes each restored table before moving to dependent child tables, which makes the restore order deterministic for plans, durations, prices, and other foreign-key chains
- per-record existence checks during restore now run without accidental autoflush, so pending child rows no longer get pushed into PostgreSQL before their parent tables are fully restored

### Fixed

- restoring `DB` and `Full` backups no longer trips foreign-key errors like `plan_durations_plan_id_fkey` when plans and their durations are recovered into a non-empty database
- plan restore now reliably repopulates the admin `Plans` screen after restore instead of leaving durations/prices orphaned behind failed child inserts

## [1.2.2] - 2026-03-25

### Changed

- database and full backups now preserve `ARRAY`- and `JSON`-backed fields in a restore-safe structure instead of stringifying lists and collapsing empty containers to `null`
- restore now understands both the new native backup container format and legacy pre-`1.2.2` payloads with stringified arrays, so older imported and Telegram-backed archives stay recoverable

### Fixed

- restoring `DB` and `Full` backups now correctly brings back created plans, durations, prices, transition arrays, and other array-backed data that previously disappeared after restore
- legacy backups with missing or `null` non-nullable array fields now recover into usable empty arrays, which prevents plan and related records from silently breaking on restore

## [1.2.1] - 2026-03-25

### Added

- a backup registry that tracks local and Telegram-delivered archives, plus a new dashboard import flow for manually uploading legacy backup files back into the restore list
- restore support for Telegram-backed backups that no longer exist locally, allowing the bot to download the archived document and run the normal restore pipeline from that temporary copy

### Changed

- runtime `assets/` are now fully resynced from the image defaults whenever the app version changes, with the previous runtime assets archived into `.bak` before replacement
- the backup dashboard now shows the archive source (`Local`, `Telegram`, or both), exposes restore for any valid source, and limits delete actions to the local copy when a Telegram copy also exists

### Fixed

- updated translation assets from the release image now actually reach deployed bots without requiring a manual `RESET_ASSETS`, so buttons like `🎫 Назначить план` stop getting stuck on stale runtime translations
- active partners no longer see the regular `Invite` entrypoint in the bot, and direct web visits to the referrals page now redirect into the partner flow instead of leaving a dead-end referral screen

## [1.2.0] - 2026-03-25

### Added

- a new bot `Mini App-first` main-menu mode with settings-backed Mini App URL resolution, custom link buttons, and a dedicated admin `Bot Menu` section for configuring the user-facing menu without touching other bot flows
- a new internal `bot_menu` settings contract and migration, including `miniapp_only_enabled`, `mini_app_url`, and ordered custom buttons with `URL` and `WEB_APP` kinds
- regression coverage for Mini App-first menu rendering, button resolution order, legacy `BOT_MINI_APP` fallback, and localization guardrails for the new bot-menu surfaces

### Changed

- privileged bot users now keep access to the dashboard button even when Mini App-first mode is enabled, while ordinary users see only the primary Mini App entry, enabled custom buttons, and support in `MainMenu.MAIN`
- the purchase screen internals were cleaned up to replace inline render helpers with dedicated components, and the dashboard navigation module was trimmed to remove an unused public export
- the `v1.2.0` release bundles the full pending worktree, including the prepared bot-menu feature package and the already-staged web cleanup changes

## [1.1.18] - 2026-03-24

### Changed

- GitHub release notifications can now be pushed directly into the app through a protected internal endpoint, while the old GitHub polling task remains only as a fallback safety net
- the final purchase stage in mobile web and Telegram Mini App now uses a steadier checkout surface with less aggressive overlay/select rendering, which reduces the visible shake and glitch artifacts without changing the current bottom-sheet flow

### Fixed

- DEV update alerts no longer fire after the instance is already updated to the same version; notifications now only trigger for strictly newer upstream releases
- update alerts now use a dedicated AltShop-specific translation key so stale runtime translation overrides cannot keep showing visible `Remnashop` wording
- Telegram notification sends now treat `chat not found` like an unreachable bot chat, mark the user as blocked, and stop repeating noisy delivery errors for that chat

## [1.1.17] - 2026-03-24

### Changed

- the payment purchase screen now resolves its default plan, duration, gateway, and payment asset through a stable derived selection model, which removes the visible jump/shake on mobile web and Telegram Mini App while keeping the current dropdown UX
- purchase selectors on mobile now use a steadier dropdown and checkout sheet configuration, reducing WebView rendering artifacts without changing the rest of the app's dialogs or selects
- external checkout requests now carry explicit success and failure redirect URLs so web and Mini App return can be resumed through a dedicated payment return bridge

### Fixed

- returning from external payment pages now reliably lands back in the web dashboard or Telegram Mini App instead of getting stuck outside the app context after checkout
- the project/update info notification no longer shows visible `Remnashop` wording and now uses the configured project name, such as `AltShop`

## [1.1.16] - 2026-03-24

### Fixed

- DEV release notifications now fire once for every newly published GitHub release tag even when the running instance already has the same semantic version, which restores alerts for freshly published releases like `1.1.15`
- update-check audit tests now cover the “current version was just officially released” path, so this notification regression does not silently come back on future patch releases

## [1.1.15] - 2026-03-24

### Added

- unified trial eligibility now serves both bot and web flows from a shared backend resolver, including a web exception that allows invited users and partner-attributed users to activate trial without mandatory Telegram linking
- bot admin user cards now explicitly show internal shadow ID, linked Telegram ID, web login, profile username, and identity kind for web-only versus Telegram-linked accounts
- regression coverage now guards archived-plan purchase rejection and shared trial eligibility rules

### Changed

- Telegram Mini App checkout now opens all external gateway payment pages outside the embedded WebView instead of navigating the in-app page directly
- web login validation is now explicitly restricted to lowercase Latin letters, digits, dots, and underscores, with matching localized helper copy on the web auth screens
- visible runtime bot/web strings were moved into localization, and bot notices now use localized emoji-rich copy while web remains plain localized text
- bot renew flows now rely on the shared subscription purchase policy, so archived renew and replacement rules match web and Mini App behavior

### Fixed

- Platega and other external payment gateways no longer break inside Telegram Mini App with `ERR_UNKNOWN_URL_SCHEME` during checkout handoff
- archived plans can no longer be purchased as brand new subscriptions via web or Mini App; existing owners can still renew or upgrade according to archived-plan rules
- bot admin search now finds web-only users by negative shadow ID, exact web login, and broader identity search paths instead of effectively hiding them from the normal users flow

## [1.1.14] - 2026-03-24

### Added

- selective backup scopes in the dashboard: admins can now create `Database only`, `Assets only`, or `Full backup` archives instead of being limited to a single full-database flow
- backup manifests and backup list metadata now record scope, included database/assets content, asset root, and asset file counts, making it clear what each archive actually contains
- regression coverage for selective backup creation/restoration and lazy access-mode application without recent-user menu refresh

### Changed

- any database-containing backup now explicitly preserves plans, durations, prices, users, subscriptions, referrals, partner data, transactions, withdrawals, broadcasts, and instance settings as part of the supported backup contract
- access-mode switches now apply lazily on the next bot click, message, web request, or Mini App request instead of proactively resending users' profiles and main menus
- when access reopens, only targeted waitlist notifications are sent; regular users no longer receive spontaneous “menu/profile updated” messages from access-mode changes

### Fixed

- assets-only restore now merges and overwrites included runtime assets without deleting unrelated custom files in the instance `assets/` directory
- selective restore now correctly restores only the archive contents that were actually backed up, so DB-only restore leaves assets untouched and assets-only restore leaves the database untouched

## [1.1.13] - 2026-03-23

### Added

- unified access-mode policy now applies across the Telegram bot, web dashboard, and Telegram Mini App, including capability-based web access flags and a new `invite_mode_started_at` timestamp for invite-only grandfathering
- regression coverage now checks safe direct `MainMenu` starts and middleware handling for users who blocked the bot

### Changed

- `INVITED` mode now keeps users who existed before invite-only was enabled fully operational, while newly created non-invited users are blocked consistently in bot, web, and mini app
- `PURCHASE_BLOCKED` now behaves as a true cross-surface read-only purchase mode: subscriptions and devices stay visible, but buy, renew, upgrade, and trial actions are disabled everywhere
- bot access denials no longer re-send the profile/main menu on every forbidden click; callback denials use alerts and message denials are rate-limited notices

### Fixed

- switching access modes no longer produces `TelegramForbiddenError: bot was blocked by the user` error files when recent-user menu refresh touches users who blocked the bot
- direct `MainMenu` dialog starts now mark blocked users safely instead of crashing the dispatcher when the menu banner/photo cannot be delivered
- web and Telegram Mini App now respect global access modes instead of letting users buy through the web when purchases are blocked globally

## [1.1.12] - 2026-03-23

### Added

- every GitHub release update check now stores an internal Redis audit snapshot with the final outcome, compared versions, dedupe value, recipient resolution, and delivery counts for later diagnosis
- startup coverage now verifies that application boot still queues the update checker, in addition to the existing worker and scheduler task registration regression tests

### Changed

- the AltShop update checker now emits explicit structured outcomes such as `up_to_date`, `already_notified`, `toggle_disabled`, `delivery_failed`, and `notified` instead of only ad-hoc logs
- DEV recipient resolution for update notifications is now audited explicitly, including whether a real DEV recipient was found or the fallback temp-DEV path was used

### Fixed

- missed DEV update notifications are now easier to diagnose because failed fetch, parse, toggle, dedupe, and delivery branches each leave a persistent audit trail instead of disappearing into generic logs
- future update alerts no longer require guessing whether the checker ran, found recipients, or skipped dedupe: the final reason is now recorded on every run

## [1.1.11] - 2026-03-23

### Added

- mobile settings now include an explicit logout section, so mobile users can sign out without relying on the desktop-only header menu
- regression coverage for client-facing branding targets, shared subscription action state, and branded bot/email fallbacks

### Changed

- landing and Telegram Mini App entry pages now render the visible product name from branding settings instead of hardcoded `AltShop`
- DEV dashboard shop labels and the RemnaShop main header in the bot now use runtime branding values from `project_name` and `bot_menu_button_text`
- email verification and password-reset subjects plus Telegram password-reset fallback text now use the configured branded project name

### Fixed

- desktop and mobile subscription cards now derive `Upgrade` visibility from the same shared action model, so desktop no longer hides upgrade where mobile shows it
- customer-facing `AltShop` labels were removed from the remaining branded web, bot, and email surfaces that should follow reseller branding

## [1.1.10] - 2026-03-23

### Fixed

- Telegram linking no longer creates the impression that a user's web login changed: the auth login is now exposed separately as `web_login`, while `username` remains the public profile username
- Telegram-based password recovery in the web settings now uses the real web login instead of the public profile username, so linked accounts keep working even when their visible username differs from their login
- DEV web-account registration and linking notifications now label the auth field explicitly as `Web login`, which removes the ambiguity between login credentials and the profile username

### Changed

- `/api/v1/auth/me` and `/api/v1/user/me` now return both `username` and `web_login`, letting clients distinguish profile identity from the actual web sign-in credential
- the settings screen now shows `Web login` separately from `Profile username`, and the Telegram Mini App web-credential bootstrap flow prefers the real web login when pre-filling auth fields

## [1.1.9] - 2026-03-23

### Fixed

- Platega webhooks now resolve the local internal payment UUID from `GET /transaction/{id}` `payload` instead of incorrectly treating the callback `id` as the local `payment_id`
- payment processing no longer silently swallows missing local transactions or users after a webhook arrives; these cases now fail fast so the webhook inbox stays failed instead of being marked processed
- legacy stuck Platega webhook events are now automatically reconciled in the background by restoring the internal payment UUID from Platega and replaying the correct local success or cancel flow

### Changed

- Platega callback handling now verifies headers, restores the real local payment UUID from the provider transaction details, and logs both the external transaction id and the resolved internal payment id for diagnostics
- payment webhook processing now keeps `PENDING` events out of the terminal `PROCESSED` state, so a later final callback can still finish the purchase normally
- application startup and the payment worker now schedule periodic recovery for orphaned Platega webhook inbox events that were stored with the external provider UUID under the old implementation

## [1.1.8] - 2026-03-23

### Fixed

- Taskiq worker and scheduler now explicitly register AltShop task modules at startup, which fixes the missing `check_bot_update` task and restores hourly plus startup release checks
- DEV GitHub release notifications now mark a version as notified only after the update message is actually delivered, so transient queue or delivery failures no longer permanently swallow update alerts

## [1.1.7] - 2026-03-23

### Fixed

- mobile auth inputs now keep a `16px` text size on narrow screens, which prevents iPhone and Telegram WebView from zooming into login and recovery forms on focus
- new users without a subscription now see normal readable main-menu subscription copy again instead of mojibake, even on deployments that still have older bind-mounted translation assets

## [1.1.6] - 2026-03-22

### Fixed

- the main Telegram menu now renders both its text and product buttons from one resolved access-state source, which removes the hybrid state where unlocked buttons could appear together with the invite-only warning
- deployments with mounted translation assets now use an isolated default main-menu key, so stale bind-mounted translations can no longer force the old invite-lock copy onto the normal public menu
- the `/miniapp` Telegram landing now uses a scrollable content area with a sticky bottom CTA, so the `Open dashboard` button stays reachable on narrow mobile Telegram viewports instead of slipping below the fold

## [1.1.5] - 2026-03-22

### Added

- DEV update notifications now track official GitHub Releases of `dizzzable/altshop` and include the current version, available version, release date, and direct upgrade links
- regression coverage for GitHub release parsing/deduplication and access-mode refresh after invite-only soft-lock

### Changed

- update checks now use the AltShop GitHub Releases API instead of the old upstream raw version file, so self-hosted instances are notified only about real AltShop releases
- repository, latest release, and upgrade-guide links are now centralized and reused by both the checker and Telegram notification keyboard

### Fixed

- users who were previously shown the invite-only soft-lock screen now get their main menu refreshed when access mode is switched back to `PUBLIC`, so the stale "Доступ ограничен приглашением" screen no longer lingers
- main menu invite-lock state is now resolved through the central access service instead of duplicating the condition in the menu getter

## [1.1.4] - 2026-03-22

### Added

- token-based invite links for the regular referral system with configurable TTL, invite slot limits, automatic slot refill from qualified referrals, and a dedicated `referral_invites` persistence layer
- global DEV controls for referral invite limits plus per-user override settings for TTL and slot policy directly in the user card
- referral portal and web API fields for invite status, expiration, remaining slots, total capacity, refill progress, and blocked-link reasons
- regression coverage for invite capacity/refill rules and invite-only bot soft-lock behavior

### Changed

- regular referral onboarding now validates active invite tokens instead of permanent `users.referral_code` links, while the partner program continues using the classic partner referral code flow unchanged
- invite-only mode in the Telegram bot is now soft-locked: users can open `/start` and safe informational screens, but product actions stay blocked until they open the bot via a valid invite link
- referral screens in both bot and web now explain whether the link is active, expired, exhausted by slots, or needs regeneration, and show the current slot/refill state instead of silently exposing an unusable link
- Telegram `/start ref_...` and web registration now cleanly separate regular referral attachment from partner attribution, so ordinary invite tokens no longer bleed into the partner flow

### How It Works

- every regular referrer now has at most one active invite link at a time; generating a new one revokes the previous link immediately
- when TTL is enabled, the invite link stops working exactly at `expires_at` and the user must regenerate a fresh link before inviting again
- when slot limits are enabled, capacity is spent only when a new user is actually attached to the referrer for the first time; repeated opens by the same referred user do not consume extra slots
- slot capacity grows automatically according to the configured threshold and refill amount based on the existing `qualified_at` referral qualification logic
- the web cabinet now displays the invite link status and capacity summary, while invite regeneration stays an explicit action in the Telegram bot

### Upgrade Notes

- regular non-partner referral links based on the old permanent `referral_code` are no longer accepted after this release; users must generate a fresh invite link
- partner referral links and partner attribution rules are intentionally unchanged

## [1.1.3] - 2026-03-22

### Added

- DEV `Assign plan` flow in the user card now asks which non-deleted subscription to update when a user has multiple subscriptions, instead of always targeting `current_subscription`

### Changed

- plan reassignment in the DEV user card now uses the already selected subscription context and returns to a dedicated subscription picker when the assign flow starts from a multi-subscription user
- RU/EN bot copy for plan reassignment now explicitly refers to the selected subscription and explains the new subscription-picking step

## [1.1.2] - 2026-03-22

### Added

- DEV user management now supports selecting and inspecting any non-deleted subscription when a user has multiple subscriptions, instead of being limited to `current_subscription`
- archived plan configurator screens now show clearer localized guidance for renew mode, replacement plans, and upgrade targets directly in the dialog flow

### Changed

- Telegram bot i18n now overlays mounted `assets/translations` with bundled default translations at runtime, so partial VPS bind mounts inherit missing keys from built-in defaults automatically
- DEV subscription actions such as details, traffic reset, device management, squad management, limits, expiration changes, and deletion now operate on the explicitly selected subscription

### Fixed

- missing translation keys once again preserve emoji-friendly labels through prefix-aware fallback text instead of degrading to flat plain-text identifiers
- deployments with older mounted translation assets no longer lose new bot labels for archived plan settings after updating containers

## [1.1.1] - 2026-03-22

### Fixed

- bot dialogs and notifications no longer crash when a deployment runs newer code against older mounted translation assets; missing i18n keys now degrade to safe fallback labels instead of raising `KeyNotFoundError`
- archived plan configurator release is now compatible with VPS setups that update containers via `docker compose pull && up -d` while preserving an older `./assets` bind mount

## [1.1.0] - 2026-03-21

### Added

- archived plan lifecycle controls with self-renew, replacement-on-renew, upgrade targets, and migration support for existing trial plans
- explicit single-subscription purchase options API and upgrade purchase flow across backend, bot configurator, and web cabinet
- regression pytest coverage for archived renew policy, upgrade eligibility, historical trial usage, guarded plan deletion, and Remnawave-aware subscription deletion

### Changed

- subscription renewals now follow explicit backend policy instead of allowing free-form plan switching from the web UI
- plan assignment and DEV plan issuance now allow active archived plans while regular storefront visibility remains limited to public plans
- web subscription cards and purchase screens now expose upgrade actions, locked renew selection, and archived/upgrade warning banners with localized copy

### Fixed

- trial subscriptions can no longer be re-abused after expiration or deletion because trial usage is now tracked historically
- deleting a subscription from the web cabinet now deletes the Remnawave profile first, soft-deletes the local record, and switches or clears the current subscription correctly
- deleted subscriptions are no longer returned in the default web subscription list, so removed cards disappear from the cabinet as expected

## [1.0.3] - 2026-03-21

### Added

- GHCR-backed release publishing for `altshop-backend` and `altshop-nginx` images on semantic-version tags
- a pull-based `docker-compose.prod.yml` contract for VPS updates without local backend or frontend builds

### Changed

- production deployment docs now point to the GHCR update flow and host-side certificates in `/opt/altshop/nginx`
- the production nginx image now renders `APP_DOMAIN` into `server_name` at container startup

### Fixed

- synchronized `uv.lock` with the project version so locked backend image builds pass during release publishing

## [1.0.2] - 2026-03-21

### Fixed

- restored branding settings compatibility by bringing back `bot_menu_button_text` in the settings DTO and dashboard editor
- fixed the referrals menu screen so `msg-menu-invite-referrals` always receives the required `count` value
- repaired subscription duration rendering for multi-renew flows by removing the broken `gateways` reference and recalculating prices from resolved durations
- normalized dialog-stored enum values in the subscription payment flow to prevent cache-key and crypto gateway regressions after FSM state restoration

## [1.0.1] - 2026-03-08

### Added

- automated GitHub Release workflow for semantic-version tags `v*.*.*`
- reusable release notes template and changelog-driven release note generation
- `CHANGELOG.md` as the canonical release history for future tags

### Changed

- documented the release process in contribution and development docs

### Fixed

- frontend CI on GitHub now receives the real `web-app/src/lib` modules instead of missing alias targets
- the root `.gitignore` no longer hides public frontend runtime modules under the generic `lib/` rule

## [1.0.0] - 2026-03-08

### Added

- the first public AltShop GitHub release with English and Russian repository landing pages
- clearer project positioning for service owners, operators, and buyers
- release metadata aligned to `altshop` `1.0.0`

### Changed

- refreshed the public repository presentation and deployment guidance
- aligned package metadata and lockfile with the public `altshop` identity
- clarified that deployment and day-to-day configuration stay intentionally close to `snoups/remnashop`

### Removed

- internal backend `tests/` from the public GitHub mirror while keeping them local-only

### Fixed

- public CI, docs, and `Makefile` now match the public/private repository split
