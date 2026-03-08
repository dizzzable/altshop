# Changelog

All notable changes to this repository will be documented in this file.

The format is based on Keep a Changelog, adapted for the public AltShop GitHub mirror.

## [Unreleased]

### Added

- `CHANGELOG.md` as the canonical release history for future tags
- automated GitHub Release workflow for semantic-version tags `v*.*.*`
- reusable release notes template and changelog-driven release note generation

### Changed

- documented the release process in contribution and development docs

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
