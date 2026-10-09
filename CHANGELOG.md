# Changelog

All notable changes to this project will be documented in this file.

## [0.8.1] - 2026-10-09


## [0.8.0] - 2026-10-06

### Bug Fixes

- **docker:** Rebuild the project instead of reusing a cached wheel ([372b5c1](https://github.com/ozeranskii/httptap/commit/372b5c18f270d759d143844fc95a6773bfdaab1d))

### Documentation

- **installation:** Fix the cosign link and stop pinning example tags to 0.6 ([e08bac1](https://github.com/ozeranskii/httptap/commit/e08bac156b414697cb9e1dd93a6e7f1b23591596))

### Features

- **har:** Export the request chain as a HAR 1.2 archive with --har ([4945c34](https://github.com/ozeranskii/httptap/commit/4945c34ebc37db77194384780a714eef9a760859))

### Testing

- **http_client:** Give the total-deadline test more room on slow runners ([3798d8f](https://github.com/ozeranskii/httptap/commit/3798d8f1f3a62e548d2567ddeea984258d9014bf))


## [0.7.0] - 2026-10-05

### Bug Fixes

- **utils:** Drop deprecated ssl APIs and fail tests on warnings ([d5e648f](https://github.com/ozeranskii/httptap/commit/d5e648f612c4a744ee34f3b5d4589c8574ab4f20))
- **http_client:** Honor resolved proxy settings ([2daa146](https://github.com/ozeranskii/httptap/commit/2daa146980431fe38e6205a1a1b9dd2a2f5d3851))
- **http_client:** Exclude client setup from timings ([e7f7c46](https://github.com/ozeranskii/httptap/commit/e7f7c46af332fefefafd175e8cb498d6b4709e0f))
- **http_client:** Measure TLS through CONNECT proxy ([1307db2](https://github.com/ozeranskii/httptap/commit/1307db2db52f88f63215420ea20e10836c95fdab))
- **cli:** Return tempfail for network errors ([f605ab4](https://github.com/ozeranskii/httptap/commit/f605ab4d7a5eaeb13f0c29cd3a0dbbea6430fffb))
- **cli:** Handle non-utf8 output streams ([3036210](https://github.com/ozeranskii/httptap/commit/303621003facdb90f95aa89d28a0d480505ca7f4))
- **http_client:** Report wire response bytes ([6f184d4](https://github.com/ozeranskii/httptap/commit/6f184d48470e7d058cf518f97d692a6f3953a759))
- **analyzer:** Report redirect limit reached ([bd460f1](https://github.com/ozeranskii/httptap/commit/bd460f12fc352d7144bec60d840c90c806bf64a3))
- **http_client:** Preserve user Host header ([c2d5458](https://github.com/ozeranskii/httptap/commit/c2d54589c6fc12f1b7c32c61528e79c5a06db1be))
- **cli:** Validate CLI connection arguments ([e5b2487](https://github.com/ozeranskii/httptap/commit/e5b2487ec197569e7417ac67f54578ca27f8535f))
- **cli:** Handle JSON export streams ([2951923](https://github.com/ozeranskii/httptap/commit/2951923b0ab4463ef5755f2c6cc01ca70a41f550))
- **http_client:** Preserve URL params and userinfo ([5a46291](https://github.com/ozeranskii/httptap/commit/5a46291f5eb3ac94584ed677ef6c0fed2dcc45f4))
- **tls_inspector:** Extract certificates when verification is disabled ([bde1a0a](https://github.com/ozeranskii/httptap/commit/bde1a0a1f311c9c382b1f356fc779e5d454f1539))
- **http_client:** Retry next resolved address ([9ec4944](https://github.com/ozeranskii/httptap/commit/9ec49441ae2686bd97eea7642884ee584e787ea0))
- **http_client:** Enforce total max-time deadline ([9eff747](https://github.com/ozeranskii/httptap/commit/9eff747edd0d2657f6c56b37ebbf6320e600a4ba))
- **http_client:** Count CONNECT tunnel setup as connect time ([df199ae](https://github.com/ozeranskii/httptap/commit/df199aee1e6c6e20a7b90caf6e14098b571f1f3e))
- **analyzer:** Redact URL credentials in step data and output ([d24d0a7](https://github.com/ozeranskii/httptap/commit/d24d0a76b91a3b1bc8174b1b7b5579828466c681))
- **http_client:** Honour resolve() overrides and reject empty resolutions ([9cb084f](https://github.com/ozeranskii/httptap/commit/9cb084f0788c65ebbcd00cd4bac948edb648fdd7))
- **http_client:** Send IDNA host in Host header and SNI ([f84352f](https://github.com/ozeranskii/httptap/commit/f84352f0fef0f68caf0691301445c05200a36817))
- **http_client:** Keep partial network info on failed requests ([e3e51d7](https://github.com/ozeranskii/httptap/commit/e3e51d71cc20a91e0912581bfc4e8f6e427f4e25))
- **cli:** Reject URLs with an invalid port instead of failing internally ([08a3d5b](https://github.com/ozeranskii/httptap/commit/08a3d5bc9dc5740138fedb3060521a514bc63872))
- **cli:** Rank the --json export failure inside determine_exit_code ([93c8154](https://github.com/ozeranskii/httptap/commit/93c8154f87e09e56ff3264ebc962177502067487))
- **formatters:** Keep --metrics-only lines key=value parseable ([ad26513](https://github.com/ozeranskii/httptap/commit/ad26513500bf794cd2a4d38d63643ed8e9c63248))
- **http_client:** Probe TLS at the address the request used ([cd0d652](https://github.com/ozeranskii/httptap/commit/cd0d652cd0376ec5cda4a8096e19531b42c4d8fe))
- **pkgmeta:** Read License-Expression and Project-URL metadata ([5435885](https://github.com/ozeranskii/httptap/commit/543588579b9e6adb04bc5f7401cd7651a0ebdc3a))
- **cli:** Merge user headers case-insensitively and reject an empty --json path ([307f81c](https://github.com/ozeranskii/httptap/commit/307f81c6437aaf7b07f18727134a8f3f962d12c7))
- **http_client:** Measure connect and TLS timing through SOCKS proxies ([5d6622d](https://github.com/ozeranskii/httptap/commit/5d6622dbf5de3505fd5b2d1da8bf2f915acfbe6d))
- **otlp:** Export through the SDK span pipeline as one sequential trace ([a2cba39](https://github.com/ozeranskii/httptap/commit/a2cba39f543d0695ec31ff5ea29787c572a3c1ee))
- **packaging:** Ship py.typed, drop dnspython and stabilize timing tests ([f3f053f](https://github.com/ozeranskii/httptap/commit/f3f053f829e0115b6f678495361eaf4f4c811976))
- **cli:** Validate proxy/header input and redact credentials in redirects and OTLP errors ([0c92982](https://github.com/ozeranskii/httptap/commit/0c9298232235edbd0f8c671e082bfa440ffe7324))
- **http_client:** Harden proxies, deadlines, address fallback and IDNA handling ([ceef230](https://github.com/ozeranskii/httptap/commit/ceef230b4bc49c2c99fe5d6bda5cb80f954d1b80))
- **cli:** Encode undecodable URL bytes, keep IP SANs and hold back OTLP SDK warnings ([466de06](https://github.com/ozeranskii/httptap/commit/466de068cb10267abc184c8f1a41ce07fef61b99))
- **http_client:** Bracket IPv6 literal targets in HTTP proxy request lines ([dbdb2c0](https://github.com/ozeranskii/httptap/commit/dbdb2c057cc7e7e4eaf5ef8f6b8adf3f4fd3aca5))
- **http_client:** Keep the response received before a mid-body failure ([d3285f7](https://github.com/ozeranskii/httptap/commit/d3285f785c84f8369be80ebd6e7e2ddecc260988))
- **dns:** Treat IPv4-mapped IPv6 addresses as IPv4 ([d44046f](https://github.com/ozeranskii/httptap/commit/d44046fb676158844e2a18088831a9eef1ce3b59))

### Documentation

- **release:** Update release and contributing documentation ([2228e91](https://github.com/ozeranskii/httptap/commit/2228e91074c1e0ff0bf45e6caae5b26ee400d2a6))
- **i18n:** Sync es, ja and zh pages with recent CLI changes ([0448fa8](https://github.com/ozeranskii/httptap/commit/0448fa84f75abdc9ad4930dd8094d4d0bb26c49a))
- **security:** Correct security, governance and contributor metadata ([b27a277](https://github.com/ozeranskii/httptap/commit/b27a2775600e29aba7a642540468badfa94ee36f))
- **usage:** Bring user and API docs in line with the 0.7 features ([1438504](https://github.com/ozeranskii/httptap/commit/14385043b62459f54ed9b7bc0dec54bd7f313a3c))
- **i18n:** Sync es, ja and zh pages and README translations with the 0.7 docs ([a0614aa](https://github.com/ozeranskii/httptap/commit/a0614aa628328d919542417bee52a8bb115690e9))
- **usage:** Correct inaccurate statements and document the 0.7 hardening ([16a7e1b](https://github.com/ozeranskii/httptap/commit/16a7e1ba3bc15ed9483b591dc874e067915e3ceb))

### Features

- **exporter:** Add JSON export metadata ([b3aa64b](https://github.com/ozeranskii/httptap/commit/b3aa64b0a6e1b505a336c5b210e331463612577a))
- **cli:** Fail on HTTP error responses ([de82077](https://github.com/ozeranskii/httptap/commit/de82077804ececcd805aec2f5734e7599abe64da))
- **cli:** Polish help defaults, method case and waterfall width ([ea61e87](https://github.com/ozeranskii/httptap/commit/ea61e87cb5909198efb2a356ea83a219caab1a7b))
- **slo:** Add file-based SLO thresholds ([f29fb77](https://github.com/ozeranskii/httptap/commit/f29fb77d5661826fdbecf186fc51f4723f4b3cb6))
- **cli:** Add ip family and resolve flags ([2d1a0b8](https://github.com/ozeranskii/httptap/commit/2d1a0b8aa0c8e963fbad117fd66c9dad05aec056))
- **cli:** Add prometheus and otlp exports ([2e10f83](https://github.com/ozeranskii/httptap/commit/2e10f837f73ca140f581acb8d28702f837051a6f))
- **http_client:** Show cert details on TLS failures ([9e70294](https://github.com/ozeranskii/httptap/commit/9e70294dc43ec531665e0e3faae4806058f53708))

### Miscellaneous Tasks

- **infra:** Disable coverage and reports in CodSpeed runs ([cd301b3](https://github.com/ozeranskii/httptap/commit/cd301b32c597f7b4967883fe4683cdd4b6960f5c))
- **infra:** Apply yamlfmt to codspeed workflow ([57b9fe6](https://github.com/ozeranskii/httptap/commit/57b9fe688085d500f59d39a0097c092cafcf5cd2))
- **docs:** Trigger docs workflow on source and dependency changes ([32a1b10](https://github.com/ozeranskii/httptap/commit/32a1b101302bfaf877c5bc17b80ed7c79e0e654d))
- **infra:** Run pre-commit hooks in CI ([71de726](https://github.com/ozeranskii/httptap/commit/71de726a6884fa864828d94a4c3a0080505cfd01))
- **release:** Harden release artifact checks ([2d78b90](https://github.com/ozeranskii/httptap/commit/2d78b90d4fbc1f921cf7e46f4e81c54422084f6e))
- **infra:** Speed up PR workflows ([647bfa7](https://github.com/ozeranskii/httptap/commit/647bfa77f5d4b750fa6a1c277a7e3f04089310b2))
- **release:** Push the release commit and tag only after tests pass ([b978e4b](https://github.com/ozeranskii/httptap/commit/b978e4bf0d7fca0a72366cc9ecb248e8331160bf))
- **infra:** Harden release, docs and CI workflows ([081cfc3](https://github.com/ozeranskii/httptap/commit/081cfc30e198c69032d2961d6566e2e7ade5e5eb))
- **python:** Drop Python 3.10 and ship the otel extra in the image ([709762e](https://github.com/ozeranskii/httptap/commit/709762e42177cc850f07b0b0004e0a7a9463dcba))
- **release:** Harden the release workflow, docs deploy and CI concurrency ([797df63](https://github.com/ozeranskii/httptap/commit/797df634c5e2983826c019af7f1d46899d5d6f05))

### Refactor

- **core:** Remove dead options and duplicated helpers ([2fe4164](https://github.com/ozeranskii/httptap/commit/2fe41641faa607b46e43462a280ba6dc9f9e8cb1))

### Testing

- **otlp:** Drop the redundant del in the collector's log_message ([f2cf756](https://github.com/ozeranskii/httptap/commit/f2cf7564aadcf8b0b3bac7febf3320ce71a6934b))
- Resolve CodeQL code-quality alerts in the test suite ([0c23ecf](https://github.com/ozeranskii/httptap/commit/0c23ecf30f9be6e02f500ba5b1638df13faed805))
- **e2e:** Add an end-to-end suite for the CLI and run it in CI, releases and a daily matrix ([b141b8d](https://github.com/ozeranskii/httptap/commit/b141b8d5582d61aab8bd64d5f46398d3e3c89019))


### New Contributors

- @0then0 made their first contribution in [#321](https://github.com/ozeranskii/httptap/pull/321)
- @fclss made their first contribution in [#343](https://github.com/ozeranskii/httptap/pull/343)
- @tanishpx made their first contribution in [#315](https://github.com/ozeranskii/httptap/pull/315)
- @Aarav-cyber made their first contribution in [#314](https://github.com/ozeranskii/httptap/pull/314)

## [0.6.3] - 2026-09-17

### Bug Fixes

- **cli:** Warn when --compact is ignored by --metrics-only ([88bef58](https://github.com/ozeranskii/httptap/commit/88bef5838856c79672560daa6632b5f2cc74f9df))
- **render:** Prevent metrics-only and compact lines from wrapping in pipes ([17078dd](https://github.com/ozeranskii/httptap/commit/17078dd1bd1fca885f9a0e299168f6da42c96287))

### Documentation

- **changelog:** Add security notes for 0.6.2 ([9a7ff07](https://github.com/ozeranskii/httptap/commit/9a7ff0761a09e951910fc80bfe21e0f07f71e6ae))
- **vex:** Record GHSA-pgxm-hj3g-p7wv status ([e5d3f07](https://github.com/ozeranskii/httptap/commit/e5d3f07c760ab7137c45cfd62cb6b6ba7828b29f))
- **security:** Update policy and usage docs for 0.6.2 security fixes ([20c33d7](https://github.com/ozeranskii/httptap/commit/20c33d7e00fa8f357fdb1cf63382f21f466045d9))


### New Contributors

- @adnandispatch9-jpg made their first contribution in [#310](https://github.com/ozeranskii/httptap/pull/310)
- @HarshRajSinghania made their first contribution in [#307](https://github.com/ozeranskii/httptap/pull/307)

## [0.6.2] - 2026-09-17

### Security

- Credentials (`Authorization`, `Cookie`, `Proxy-Authorization`) and request bodies are no longer forwarded to a different origin when following redirects ([GHSA-pgxm-hj3g-p7wv](https://github.com/ozeranskii/httptap/security/advisories/GHSA-pgxm-hj3g-p7wv)). Reported by @iam-niranjan.
- Server-controlled values (URL, `Server`, `Location`, certificate fields, error messages) are escaped before Rich rendering, so a server can no longer inject markup or crash the output ([GHSA-pgxm-hj3g-p7wv](https://github.com/ozeranskii/httptap/security/advisories/GHSA-pgxm-hj3g-p7wv)).
- Proxy credentials are redacted in terminal output and JSON export ([#302](https://github.com/ozeranskii/httptap/issues/302)).

### Bug Fixes

- **analyzer:** Apply RFC 9110 rules when following redirects ([f8bb8e1](https://github.com/ozeranskii/httptap/commit/f8bb8e10afa7c6e5bc4a5185cbbc1fc8588083ff))
- **utils:** Redact proxy credentials in output and export ([6c0df77](https://github.com/ozeranskii/httptap/commit/6c0df77c593b651d5dbb2a934240b36f15b3863e))

### Miscellaneous Tasks

- **infra:** Read ruff version from uv.lock in ruff-action ([b2d1837](https://github.com/ozeranskii/httptap/commit/b2d1837c2a52a08cc759147e8afc5ad9fec19438))


### New Contributors

- @Voyagerroc-Lab made their first contribution in [#304](https://github.com/ozeranskii/httptap/pull/304)


## [0.6.1] - 2026-09-06

### Documentation

- **i18n:** Add Simplified Chinese translation and mkdocstrings API reference ([84b6702](https://github.com/ozeranskii/httptap/commit/84b670273396788da3d3dad56c73a7b07e502226))
- **i18n:** Fix banner image path on the Chinese home page ([e12e6a1](https://github.com/ozeranskii/httptap/commit/e12e6a10efcb8508813db580376b9da6928f944d))
- **i18n:** Add Japanese and Spanish translations ([63158e5](https://github.com/ozeranskii/httptap/commit/63158e52513a909d529390d5f8c90d0a02ee6a4a))
- **readme:** Add Trendshift badge ([cd3cbe4](https://github.com/ozeranskii/httptap/commit/cd3cbe4dae0a1a9e922b771ad297842ba39de929))


## [0.6.0] - 2026-08-23

### Bug Fixes

- **http_client:** Read TLS from the live connection instead of a separate probe ([ec386dd](https://github.com/ozeranskii/httptap/commit/ec386ddc00ea1c3fc5ac10bf43f70953bb764339))

### Documentation

- **mkdocs:** Sync footer copyright year with LICENSE (2025-2026) ([507acb7](https://github.com/ozeranskii/httptap/commit/507acb708a863500e954d5481393f7f07762a2b5))
- **readme:** Add Simplified Chinese translation ([88f4187](https://github.com/ozeranskii/httptap/commit/88f41874e7684bbe073b4b21d20a34ae37616caa))
- **readme:** Complete the installation and top-level TOC ([d6f8b4a](https://github.com/ozeranskii/httptap/commit/d6f8b4abbe8e3244930ebd4ef27ef87d53f60b1d))


## [0.5.4] - 2026-08-23

### Documentation

- Add uvx as recommended install method ([d7d4116](https://github.com/ozeranskii/httptap/commit/d7d411689b3ddfb7f2f32c564d472355328d9759))
- **mkdocs:** Point site_url to docs.httptap.dev ([71920c7](https://github.com/ozeranskii/httptap/commit/71920c7d309876633f8c317fa7a998f03eeb0478))


### New Contributors

- @cr2007 made their first contribution in [#234](https://github.com/ozeranskii/httptap/pull/234)

## [0.5.3] - 2026-07-19

### Bug Fixes

- **utils:** Require a non-empty host in validate_url ([63594f2](https://github.com/ozeranskii/httptap/commit/63594f2444b3e4a29a59157bf82086c61cf6d16b))


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
