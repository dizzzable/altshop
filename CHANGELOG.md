# Changelog

All notable changes to this repository will be documented in this file.

The format is based on Keep a Changelog, adapted for the public AltShop GitHub mirror.

## [Unreleased]

## [1.1.6] - 2026-03-22

### Fixed

- the main Telegram menu no longer reuses a stale `msg-main-menu` translation key on deployments with mounted translation assets, which fixes the case where the invite-only warning could still be shown even after access mode was switched back to `PUBLIC`
- self-hosted instances that update via fresh release images now receive an isolated default main-menu copy key, so the unlocked menu text and unlocked buttons stay in sync after upgrading

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
