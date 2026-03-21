# Changelog

All notable changes to this repository will be documented in this file.

The format is based on Keep a Changelog, adapted for the public AltShop GitHub mirror.

## [Unreleased]

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
