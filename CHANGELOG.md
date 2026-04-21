# Changelog

All notable changes to this project will be documented in this file.

## [0.5.2] - 2026-04-21


## [0.5.1] - 2026-04-13

### Miscellaneous Tasks

- **release:** Harden supply chain with signed commits, container images, and TestPyPI ([ad654ec](https://github.com/ozeranskii/httptap/commit/ad654ec854b152a087dc573e4dbbe460141b0eb5))
- **infra:** Avoid template expansion in container smoke test ([471ae15](https://github.com/ozeranskii/httptap/commit/471ae150f587c3b50509d0254eaf4c1ea169bffd))
- **infra:** Use correct uv invocation to run argparse-manpage in release workflow ([17342f6](https://github.com/ozeranskii/httptap/commit/17342f688de244cc7f5bb8cc2fcd53dcf71aabbd))
- **infra:** Use --module when running argparse-manpage in release workflow ([bb0fdbf](https://github.com/ozeranskii/httptap/commit/bb0fdbfc5ef3d95f8ee8258abace97325c71980c))


## [0.5.0] - 2026-04-12

### Features

- **cli:** Add --slo threshold checking ([5fae63e](https://github.com/ozeranskii/httptap/commit/5fae63eea9772dda85ea3c6ee53d27bbdd79db01))


## [0.4.9] - 2026-04-12

### Bug Fixes

- **cli:** Emit one line per step for --compact ([adc29ae](https://github.com/ozeranskii/httptap/commit/adc29ae6d0ca5e4111ba9f1fbc6043dee92d08da))

### Documentation

- Fix mkdocs build on Python 3.14 ([1b9281f](https://github.com/ozeranskii/httptap/commit/1b9281f77347cb03f81371febc8301c62dbb8f89))


## [0.4.8] - 2026-04-12

### Documentation

- **readme:** Add project banner to README and docs index ([c74dda6](https://github.com/ozeranskii/httptap/commit/c74dda60bc237b7ab9f5b32c314d8a96e7fdaf1d))
- **readme:** Add OpenSSF Best Practices passing badge ([a110d21](https://github.com/ozeranskii/httptap/commit/a110d21dc99cf070a78131f7b78db5b2778b7e6d))

### Miscellaneous Tasks

- **ci:** Add zizmor and harden GitHub Actions workflows ([15e4451](https://github.com/ozeranskii/httptap/commit/15e445177a30cd1a0f53e7ba9d83ee45059caa4f))
- **release:** Attest build provenance for release artifacts ([678df32](https://github.com/ozeranskii/httptap/commit/678df32b63da1811976d6494f573f360a5e1242a))
- **release:** Auto-bump CITATION.cff and refresh SECURITY.md ([c80cf60](https://github.com/ozeranskii/httptap/commit/c80cf60a5699fa42d0ea32ef2db7882d38eb5760))
- **release:** Fix git-cliff install and stale release notes ([94aa412](https://github.com/ozeranskii/httptap/commit/94aa4128e642413001743ebc429dbd74236a5ff3))


## [0.4.7] - 2026-03-30

### Miscellaneous Tasks

- Add CodSpeed continuous performance benchmarks and workflow ([3c20d52](https://github.com/ozeranskii/httptap/commit/3c20d52c921a5ac873cee5456b2d8060b2001404))
- **ci:** Harden GitHub Actions security and enhance changelog ([73653b6](https://github.com/ozeranskii/httptap/commit/73653b6f7512e2c7b02f32e082458095197de4df))


### New Contributors

- @codspeed-hq[bot] made their first contribution in [#89](https://github.com/ozeranskii/httptap/pull/89)

## [0.4.6] - 2026-03-20

### Miscellaneous Tasks

- Bump ruff from 0.15.6 to 0.15.7 in the dev-tools group ([#87](https://github.com/ozeranskii/httptap/issues/87))

## [0.4.5] - 2026-03-14

### Features

- Display proxy source and explicit no-proxy status ([#78](https://github.com/ozeranskii/httptap/issues/78))

### Miscellaneous Tasks

- Update Codecov action to v5 and upload test results ([#74](https://github.com/ozeranskii/httptap/issues/74))
- Bump ruff from 0.15.1 to 0.15.2 in the dev-tools group ([#76](https://github.com/ozeranskii/httptap/issues/76))
- Bump faker in the test-dependencies group ([#77](https://github.com/ozeranskii/httptap/issues/77))
- Bump ruff from 0.15.2 to 0.15.4 in the dev-tools group ([#81](https://github.com/ozeranskii/httptap/issues/81))
- Bump ruff from 0.15.4 to 0.15.5 in the dev-tools group ([#82](https://github.com/ozeranskii/httptap/issues/82))
- Bump faker in the test-dependencies group ([#83](https://github.com/ozeranskii/httptap/issues/83))
- Bump faker in the test-dependencies group ([#86](https://github.com/ozeranskii/httptap/issues/86))
- Bump ruff from 0.15.5 to 0.15.6 in the dev-tools group ([#85](https://github.com/ozeranskii/httptap/issues/85))

## [0.4.4] - 2026-02-14

### Bug Fixes

- Respect SOCKS5h proxy DNS resolution and harden CI pipeline ([#61](https://github.com/ozeranskii/httptap/issues/61))

### Miscellaneous Tasks

- Bump ruff in the dev-tools group ([#68](https://github.com/ozeranskii/httptap/issues/68))
- Add typos and improve pre-commit params ([#69](https://github.com/ozeranskii/httptap/issues/69))

## [0.4.3] - 2026-01-19

### Miscellaneous Tasks

- Bump ruff in the dev-tools group ([#66](https://github.com/ozeranskii/httptap/issues/66))

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
