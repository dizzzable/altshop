# Changelog

All notable changes to this repository will be documented in this file.

The format is based on Keep a Changelog, adapted for the public AltShop GitHub mirror.

## [Unreleased]

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
