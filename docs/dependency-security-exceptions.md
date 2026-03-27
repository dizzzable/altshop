# Dependency Security Exceptions

Last reviewed: `2026-03-26`

This file tracks the temporary dependency advisories that are accepted for
[ALT-34](/ALT/issues/ALT-34). CI and release audits ignore only the IDs listed
below. Any new advisory must fail the pipeline until it is fixed or added here
with a dated exception.

| Package | Advisory | Scope | Accepted until | Owner | Rationale | Exit criteria |
| --- | --- | --- | --- | --- | --- | --- |
| `ecdsa 0.19.1` | `CVE-2024-23342` | runtime transitive dependency via `python-jose[cryptography]` | `2026-04-30` | Python Engineer | `python-jose` still hard-depends on `ecdsa`, and no fixed `ecdsa` release is available in the current advisory feeds. AltShop uses the `cryptography` backend, but the package remains installed. | Replace `python-jose` or upgrade once upstream ships a fixed `ecdsa`/`python-jose` path. |
| `pygments 2.19.2` | `CVE-2026-4539` | dev-only transitive dependency via `pytest` | `2026-04-30` | Python Engineer | PyPI still publishes `2.19.2` as the latest release, so there is no clean upgrade path today. | Upgrade once PyPI publishes a fixed `pygments` release or the test stack moves off the affected version. |
