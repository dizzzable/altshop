# Changelog

All notable changes to this repository will be documented in this file.

The format is based on Keep a Changelog, adapted for the public AltShop GitHub mirror.

## [Unreleased]

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
