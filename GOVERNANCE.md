# Governance

This document describes how the httptap project is organized, who makes
decisions, and how those decisions are made. It is intentionally minimal and
reflects the project's current scale: a small open-source utility maintained
primarily by a single person.

If the project grows, this document will be updated accordingly — proposals
to amend governance are themselves accepted as pull requests against this
file.

## Project Type

httptap is an independent open-source project distributed under the
[Apache License 2.0](LICENSE). It is not currently part of any foundation,
company, or consortium.

## Roles

### Maintainer

The maintainer is responsible for the long-term direction of the project,
has write access to the repository, and is accountable for releases.

- **Current maintainer:** Sergei Ozeranskii
  ([@ozeranskii](https://github.com/ozeranskii))

Responsibilities:

- Triage issues and pull requests.
- Review, approve, and merge contributions.
- Cut releases and publish to PyPI.
- Respond to vulnerability reports per [SECURITY.md](SECURITY.md).
- Keep [ROADMAP.md](ROADMAP.md) and project documentation current.
- Enforce the [Code of Conduct](CODE_OF_CONDUCT.md).

### Reviewer

Reviewers are trusted contributors who review pull requests on behalf of the
maintainer. Reviewers do **not** have write access; their reviews are
advisory and must still be accepted by the maintainer before merge.

The project currently has no formal reviewers beyond the maintainer.
Candidates are invited after a sustained track record of high-quality
contributions.

### Contributor

Anyone who submits an issue, pull request, or documentation improvement.
Contribution requirements are documented in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Decision Making

The project uses a **benevolent dictator for life (BDFL)** model: the
maintainer has final say on all changes. In practice, most decisions are
consensus-driven through pull request review, and disagreements are
resolved by public discussion on GitHub.

- **Day-to-day changes** (bug fixes, documentation, minor features): merged
  once the maintainer approves the pull request and CI passes.
- **Significant changes** (new public API, breaking changes, dependency
  additions): discussed in a GitHub issue before implementation.
- **Scope changes** (items moving in or out of [ROADMAP.md](ROADMAP.md)):
  decided by the maintainer after community feedback on the relevant issue.
- **Governance changes** (this file, CODE_OF_CONDUCT, SECURITY, LICENSE):
  require explicit maintainer approval of a pull request.

## Contribution Process

See [CONTRIBUTING.md](CONTRIBUTING.md). In short:

1. Open or comment on an issue to signal intent for non-trivial work.
2. Fork the repository and submit a pull request from a feature branch.
3. Ensure `uv run pre-commit run --all-files` and `uv run pytest` pass.
4. Address review feedback; the maintainer merges when ready.

Contributions are accepted under the inbound=outbound licensing model
(Apache-2.0 for code, CC-BY-4.0 for documentation); no separate Contributor
License Agreement (CLA) is required.

## Releases

Releases are cut by the maintainer using the automated release workflow in
[`.github/workflows/release.yml`](.github/workflows/release.yml).

- **Cadence:** as-needed, typically every 2–6 weeks.
- **Versioning:** [Semantic Versioning 2.0.0](https://semver.org).
- **Channel:** [PyPI](https://pypi.org/project/httptap/) via OIDC Trusted
  Publishing (no long-lived API tokens).
- **Supply chain:** releases are signed with Sigstore keyless signing and
  ship SLSA v1.0 build provenance attestations via
  `actions/attest-build-provenance`.
- **Supported versions:** see [SECURITY.md](SECURITY.md).

## Continuity

To ensure the project can continue with minimal interruption if the current
maintainer becomes unavailable:

- **Source code** is mirrored to every contributor's fork and to PyPI sdist;
  the repository can be forked and continued by anyone under Apache-2.0.
- **Release infrastructure** relies on GitHub-native OIDC Trusted Publishing
  rather than long-lived secrets; a new maintainer with PyPI project
  ownership can continue releases without any key handoff.
- **PyPI project ownership** can be recovered via PyPI's account recovery
  process (maintainer recovery email is on file with PyPI).
- **Domain** (`httptap.dev`) and GitHub account recovery are covered by the
  maintainer's personal credential inheritance plan.
- **Issue trackers and discussions** continue to work on GitHub without
  maintainer action.

In the event of prolonged maintainer absence (>30 days with no response),
the community is encouraged to fork the project under Apache-2.0 and
self-organize. Such a fork may request transfer of the `httptap` PyPI name
from the PyPI administrators if the original project is abandoned.

## Code of Conduct

All participants — maintainer, reviewers, contributors, and commenters —
are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security Reporting

Vulnerabilities are reported privately via GitHub Security Advisories, as
documented in [SECURITY.md](SECURITY.md). Public issue reports for
security-sensitive bugs are discouraged.

## Amending This Document

Open a pull request. Non-trivial changes to governance should be discussed
in an issue first so the community can weigh in.
