---
title: Security Assurance Case
description: Threat model, trust boundaries, applied secure-design principles, and countered implementation weaknesses for httptap.
---

# Security Assurance Case

This document is httptap's security assurance case. It explains **why** the
project believes its security properties hold, not just **what** those
properties are. It is structured according to the OpenSSF Best Practices
silver-level `assurance_case` criterion.

**Last reviewed:** 2026-04-12 for httptap 0.4.7.

The assurance case is a living document; it is reviewed at every major
release and whenever the threat landscape or feature set changes
materially. Proposals for amendments are accepted as pull requests against
this file.

## What httptap Is

httptap is a command-line diagnostic tool. A developer supplies a single
URL (and optionally headers, a body, a proxy, a CA bundle, etc.) and
httptap performs one HTTP request (or a short redirect chain) and renders
per-phase timing and TLS information. It does **not**:

- accept network input from untrusted peers (it is not a server);
- manage user accounts, sessions, or long-lived credentials;
- execute remote code or evaluate server-supplied scripts;
- persist secrets or user data beyond the optional `--json` export.

## Security Requirements

The project commits to the following observable security properties. Each
is mapped to supporting arguments in the sections below.

| # | Requirement | Rationale |
|---|-------------|-----------|
| SR-1 | TLS certificate verification is enabled by default for every HTTPS target. | Prevents passive and active MITM by default. |
| SR-2 | Plaintext HTTP, weakened TLS, or custom CA bundles require an explicit user opt-in. | Ensures insecure configurations are always deliberate. |
| SR-3 | Credentials supplied by the user (e.g., `Authorization` headers) are forwarded only to the original URL and are not leaked to redirect targets on different hosts. | Prevents credential theft via open redirects. |
| SR-4 | The tool does not execute content served by the remote host. | No code-execution primitive from the server. |
| SR-5 | Release artifacts are signed and their build provenance is verifiable. | Protects users from tampered distributions. |
| SR-6 | All CI workflow tokens follow least privilege and are pinned by SHA. | Reduces the attack surface of the build pipeline. |
| SR-7 | Supply chain (dependencies, GitHub Actions, Docker images) is monitored for known vulnerabilities. | Timely patching of upstream weaknesses. |

## Trust Boundaries

```
   ┌─────────────────────┐
   │ CLI user            │   trusted
   │ (argv, stdin, env)  │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ httptap process     │   trusted
   │ (Python 3.10+)      │
   └──────────┬──────────┘
              │  TLS/HTTP  ◄─── untrusted: network, proxy, remote host
              ▼
   ┌─────────────────────┐
   │ Remote HTTP server  │   untrusted
   └─────────────────────┘
```

- **User → httptap** is trusted: the user is assumed to have legitimate
  reasons to issue any given request. Input validation still rejects
  malformed URLs, methods, timeouts, etc. to prevent operator mistakes.
- **httptap → network → remote server** is untrusted. All data crossing
  this boundary is treated as attacker-controlled: response headers,
  status codes, `Location` values, TLS certificates, content bodies.
- **Build pipeline → PyPI / GitHub Releases** is a separate trust boundary
  secured by GitHub OIDC (no long-lived keys), Sigstore signing, and SHA-
  pinned actions.

## Threat Model

Threats are listed using the STRIDE categories that apply to a
diagnostic HTTP client. Threats outside the scope of a client (e.g.,
server-side DoS) are explicitly excluded as non-goals.

| STRIDE | Threat | Mitigation |
|--------|--------|------------|
| **Spoofing** | Attacker impersonates the intended HTTPS server. | TLS certificate verification on by default (SR-1); `--ignore-ssl` is opt-in and documented as unsafe (SR-2). |
| **Spoofing** | Malicious PyPI mirror serves tampered wheel. | PyPI uses TLS; releases are Sigstore-signed with SLSA v1.0 provenance (SR-5); users can verify with `gh attestation verify`. |
| **Tampering** | Modified artifact on GitHub Releases. | Same as above — build provenance attestations allow independent verification. |
| **Tampering** | CI pipeline poisoned via compromised third-party action. | Every action is SHA-pinned (enforced by Scorecard Pinned-Dependencies 10/10 and zizmor pedantic); Dependabot raises PRs to update pins (SR-6, SR-7). |
| **Repudiation** | — | Out of scope; httptap is not a multi-user system. |
| **Information disclosure** | Credentials in `-H Authorization` leak to redirect target on a different host. | Redirect chain preserves host-scoped headers per httpx default; cross-origin redirects drop sensitive headers (SR-3). |
| **Information disclosure** | `--json` export includes auth headers on disk. | Users are advised in SECURITY.md and docs/troubleshooting.md to redact auth headers before sharing exports. |
| **Information disclosure** | MITM on insecure proxy. | Proxy URL scheme is validated; `socks5h://` / `https://` recommended for sensitive targets; proxy source is reported in output and JSON for audit. |
| **Denial of service** | Malicious server streams unbounded body. | Per-request timeout via `--timeout` (default 20s); transfer phase is bounded by the same deadline. |
| **Denial of service** | Malicious server streams zip bomb or gigantic body. | httptap does not decode or persist bodies beyond counting bytes for the timing metric, so memory cost is linear and bounded by the timeout. |
| **Elevation of privilege** | Malicious response body triggers parser RCE. | Bodies are never parsed for content — only length is read. No HTML, JS, or embedded-script interpretation (SR-4). |
| **Elevation of privilege** | Malicious CLI argument triggers shell injection in downstream invocation. | Arguments are parsed by `argparse` (no shell), forwarded as `list[str]` to `httpx` (no shell); there is no shell invocation in the request path. |

### Out-of-scope threats

- **Adversary with local code execution on the developer's machine.** Out
  of scope — that adversary already owns the process.
- **Adversary controlling the user's terminal / TTY.** Out of scope.
- **Cryptanalytic attacks on TLS itself.** Delegated to OpenSSL;
  mitigations are inherited from the system Python build.
- **Post-quantum threats.** Tracked upstream (OpenSSL / Python); out of
  scope for httptap itself.

## Applied Secure-Design Principles

Mapped to Saltzer & Schroeder (1975) plus modern additions.

| Principle | Application in httptap |
|-----------|-----------------------|
| Economy of mechanism | Small codebase (~2 kLoC), one purpose, no plugin loader, no runtime config files. |
| Fail-safe defaults | TLS verification on, sane default timeout, HTTP/2 preferred, no redirect following by default. |
| Complete mediation | Every outbound request is routed through `HTTPClientRequestExecutor`; there is no secondary or legacy code path. |
| Open design | Entire codebase is Apache-2.0 on GitHub; no security-through-obscurity. |
| Separation of privilege | Release pipeline is separate from development environment; PyPI publishing uses a GitHub Environment gated by OIDC. |
| Least privilege | Every CI job declares explicit minimum `permissions:`; no workflow has `write-all`. Token-Permissions Scorecard check scores 10/10. |
| Least common mechanism | No shared state across runs (single-request tool); no caches or background daemons. |
| Psychological acceptability | Curl-compatible flag aliases (`-X`, `-L`, `-k`, `-x`, `-H`) keep the mental model familiar. |
| Work factor | Attacker gains over a developer's local `curl` invocation are essentially zero — httptap exposes no more than curl does. |
| Compromise recording | JSON export captures the full request/response metadata and the proxy source, so post-hoc forensics is straightforward. |
| Defense in depth | Input validation + TLS verification + pinned build dependencies + SAST + secret scanning + Dependabot + signed releases. |

## Countered Common Implementation Weaknesses

Derived from the [CWE Top 25 (2023)](https://cwe.mitre.org/top25/) and
[OWASP ASVS 4.0](https://owasp.org/www-project-application-security-verification-standard/).
Items not listed are either not applicable to an HTTP client or handled
upstream.

| CWE | Weakness | Countermeasure |
|-----|----------|----------------|
| CWE-20 | Improper input validation | `argparse` enum/type coercion; URL/method/timeout/proxy explicitly checked. |
| CWE-22 | Path traversal (in `@file` data loader) | Path is taken verbatim from the user; no server-supplied path is ever used to open a file. |
| CWE-78 | OS command injection | No `subprocess`/`os.system` call on user-controlled data in the request path. |
| CWE-79 | XSS | No HTML rendering; output is plain text or Rich-rendered markup with escaping. |
| CWE-89 | SQL injection | No database. |
| CWE-94 | Code injection | `eval`/`exec` are not used; response bodies are never parsed. |
| CWE-116 | Improper output encoding | Rich handles terminal escape sequences safely; JSON export uses `json.dumps` with strict escaping. |
| CWE-200 | Sensitive information disclosure | Auth headers are not copied to log output; SECURITY.md and docs warn users to redact JSON exports before sharing. |
| CWE-295 | Improper certificate validation | TLS verification on by default; `--ignore-ssl` opt-in only, explicitly documented. |
| CWE-319 | Cleartext transmission | HTTPS preferred; plain HTTP requires explicit `http://` URL; proxy source reported. |
| CWE-327 | Broken crypto | Delegated to stdlib `ssl`; weak algorithms surface only when diagnosing remote servers. |
| CWE-330 | Insufficient randomness | No RNG use beyond OpenSSL-provided CSPRNG for TLS. |
| CWE-352 | CSRF | Not applicable — httptap is a client, not a server. |
| CWE-400 | Uncontrolled resource consumption | Per-request timeout; bounded redirect chain (max 10). |
| CWE-502 | Unsafe deserialization | `json.loads` only; no pickle, yaml.load, or marshal. |
| CWE-601 | Open redirect (credential leak) | Host-scoped header handling inherits httpx behavior — cross-origin redirects drop sensitive auth headers. |
| CWE-918 | SSRF | httptap is the client; it does not proxy requests on behalf of other systems. |

## Supply-Chain Assurance

Supporting the release-integrity property (SR-5):

- **Publishing**: PyPI via GitHub OIDC Trusted Publishing — no long-lived
  PyPI tokens anywhere.
- **Signing**: Sigstore keyless signing through
  `actions/attest-build-provenance`. Signing keys are short-lived,
  issued per-run by Fulcio, and verifiable via the Rekor transparency
  log.
- **Provenance**: SLSA v1.0 attestation accompanies every wheel and
  sdist.
- **Pinning**: every GitHub Action in every workflow is pinned by SHA;
  enforced by Scorecard Pinned-Dependencies and zizmor pedantic on every
  PR.
- **Dependency tracking**: SBOM in CycloneDX and SPDX formats is
  generated during release and attached as a GitHub Release asset.
- **Exploitability disclosure**: an OpenVEX document
  (`httptap-X.Y.Z.openvex.json`) ships alongside the SBOM, declaring
  for each dependency CVE whether `httptap` is actually affected. The
  source of truth is versioned in
  [`.vex/httptap.openvex.json`](https://github.com/ozeranskii/httptap/blob/main/.vex/httptap.openvex.json);
  scanners that consume VEX (Grype, Trivy, Snyk) use it to suppress
  false-positive alerts on unreachable vulnerable code paths.

Users can verify a downloaded artifact independently:

```shell
gh attestation verify dist/httptap-X.Y.Z-py3-none-any.whl \
  --repo ozeranskii/httptap
```

## Known Residual Risks

These are documented rather than mitigated. They represent trade-offs
that are explicit rather than oversights.

- **Git tags are unsigned.** Release *artifacts* are Sigstore-signed, which
  is strictly stronger than tag signatures, but the tag-signing criterion
  is formally unmet; see ROADMAP.md.
- **Solo maintainer.** Bus factor is 1 (tracked in GOVERNANCE.md). The
  continuity plan mitigates single-point-of-failure for operations but not
  for code review: a single reviewer can merge changes without a second
  set of eyes. Pre-commit, CI gates, and public audit trail partly
  compensate.
- **No runtime sandboxing.** httptap executes with the user's full
  privileges. This is appropriate for a developer diagnostic tool but
  means a bug in `httptap` itself runs with the user's privileges.
- **TLS trust anchors inherited from the OS.** If the OS trust store is
  compromised (e.g., a corporate MITM proxy installs a private CA),
  httptap cannot detect this. The `network.tls_custom_ca` and
  `proxy_source` fields in the JSON export document whether a custom CA
  bundle or proxy was in use.

## Change History

| Date | Notes |
|------|-------|
| 2026-04-12 | Initial assurance case for httptap 0.4.7 (silver submission). |

---

## References

- [SECURITY.md](https://github.com/ozeranskii/httptap/blob/main/SECURITY.md) — vulnerability reporting process and supported versions.
- [GOVERNANCE.md](https://github.com/ozeranskii/httptap/blob/main/GOVERNANCE.md) — project roles, decisions, and continuity plan.
- [ROADMAP.md](https://github.com/ozeranskii/httptap/blob/main/ROADMAP.md) — scope, non-goals, and deprecation policy.
- [Troubleshooting & FAQ](../troubleshooting.md) — operational guidance.
- [CWE Top 25](https://cwe.mitre.org/top25/) and
  [OWASP ASVS 4.0](https://owasp.org/www-project-application-security-verification-standard/)
  — reference catalogs of implementation weaknesses.
