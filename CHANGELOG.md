# Changelog

All notable changes to this project will be documented in this file.

## [0.4.2] - 2026-01-13

### Miscellaneous Tasks

- Bump mypy from 1.19.0 to 1.19.1 in the dev-tools group ([#55](https://github.com/ozeranskii/httptap/issues/55))
- Bump pre-commit from 4.5.0 to 4.5.1 ([#58](https://github.com/ozeranskii/httptap/issues/58))
- Bump ruff from 0.14.9 to 0.14.10 in the dev-tools group ([#59](https://github.com/ozeranskii/httptap/issues/59))
- Bump ruff in the dev-tools group ([#63](https://github.com/ozeranskii/httptap/issues/63))

## [0.4.1] - 2025-12-09

### Miscellaneous Tasks

- Update CNAME to point docs subdomain

### Performance

- Dial resolved IPs while preserving Host/SNI ([#51](https://github.com/ozeranskii/httptap/issues/51))

## [0.4.0] - 2025-11-17

### Features

- Add support for custom CA bundle for TLS verification ([#45](https://github.com/ozeranskii/httptap/issues/45))

## [0.3.1] - 2025-11-13

### Features

- Surface normalized HTTP version in network info ([#41](https://github.com/ozeranskii/httptap/issues/41))
- Add curl-compatible flag aliases for request options ([#42](https://github.com/ozeranskii/httptap/issues/42))

## [0.3.0] - 2025-11-04

### Features

- Add support for request bodies and multiple HTTP methods ([#36](https://github.com/ozeranskii/httptap/issues/36))

## [0.2.1] - 2025-11-02

### Features

- Add shell completions support and update installation docs ([#33](https://github.com/ozeranskii/httptap/issues/33))

## [0.2.0] - 2025-10-29

### Documentation

- Add promo banner and clarify proxy env precedence ([#30](https://github.com/ozeranskii/httptap/issues/30))

### Features

- Add optional TLS verification and pluggable request executor ([#27](https://github.com/ozeranskii/httptap/issues/27))
- Add proxy support for outbound requests ([#29](https://github.com/ozeranskii/httptap/issues/29))

### Miscellaneous Tasks

- Add pre-commit policy and standardize GitHub workflows ([#23](https://github.com/ozeranskii/httptap/issues/23))
- Add support for free-threaded Python 3.14t ([#24](https://github.com/ozeranskii/httptap/issues/24))

## [0.1.1] - 2025-10-25

### Documentation

- Add full documentation site and GitHub Pages deploy ([#15](https://github.com/ozeranskii/httptap/issues/15))
- Add imaging support and social card configuration ([#16](https://github.com/ozeranskii/httptap/issues/16))

### Miscellaneous Tasks

- Widen Python support to 3.10–3.14 and modernize metadata ([#17](https://github.com/ozeranskii/httptap/issues/17))
- Refresh and commit uv.lock during release workflow ([#21](https://github.com/ozeranskii/httptap/issues/21))

## [0.1.0] - 2025-10-24

### Documentation

- Reorganize README badges into grouped table ([#12](https://github.com/ozeranskii/httptap/issues/12))

### Features

- Add initial httptap core, CLI, instrumentation and tests ([#1](https://github.com/ozeranskii/httptap/issues/1))
- Add automated release workflow and changelog ([#13](https://github.com/ozeranskii/httptap/issues/13))

### Miscellaneous Tasks

- Skip Codecov uploads for dependabot runs ([#6](https://github.com/ozeranskii/httptap/issues/6))
- Switch Dependabot to uv and add dependency workflows ([#7](https://github.com/ozeranskii/httptap/issues/7))
- Add CodeQL filter for legacy-TLS and document safe usage ([#9](https://github.com/ozeranskii/httptap/issues/9))
- Add GitHub templates, contributing guide, and CodeQL ([#10](https://github.com/ozeranskii/httptap/issues/10))
- Generate full changelog with --unreleased and fallback for notes ([#14](https://github.com/ozeranskii/httptap/issues/14))
- Provide deploy SSH key to checkout action
