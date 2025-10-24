# GitHub Configuration

This directory contains GitHub-specific configuration for the httptap project.

## Files

### `dependabot.yml`

Automated dependency updates configuration using Dependabot.

**Ecosystems monitored:**

1. **GitHub Actions** (`package-ecosystem: "github-actions"`)
   - Weekly updates every Monday at 08:00 UTC
   - Target branch: `main`
   - Labels: `dependencies`, `github-actions`
   - Limits: 5 open PRs max
   - Automatic rebase strategy

2. **Python via uv** (`package-ecosystem: "uv"`)
   - Weekly updates every Monday at 08:00 UTC
   - Target branch: `main`
   - Labels: `dependencies`, `python`
   - Limits: 10 open PRs max
   - Works with `pyproject.toml` and `uv.lock`

**Dependency grouping:**

Groups related packages to reduce PR noise:
- `pytest`: All pytest-related packages (`pytest*`)
- `dev-tools`: Development tools (`ruff`, `mypy`)
- `test-dependencies`: Test utilities (`pytest-*`, `faker`)
- `http-client`: HTTP client libraries (`httpx*`)

**Version update policy:**

- ✅ Automatic: Minor and patch version updates
- ❌ Ignored: Major version updates (requires manual review)
- Commit messages: `chore: update dependencies` format

**Why `uv` ecosystem?**

This project uses:
- `pyproject.toml` for dependency declaration (PEP 621)
- `uv.lock` for dependency locking
- `uv` package manager (modern, fast alternative to pip)

Dependabot's `"uv"` ecosystem is specifically designed for this stack and will properly parse `pyproject.toml` and update `uv.lock`.

### `workflows/`

GitHub Actions workflows for CI/CD automation.

#### `ci.yml` - Continuous Integration

Main CI pipeline that runs on every push and pull request to `main` branch.

**Jobs:**
- **lint**: Ruff linter and formatter checks (via `ruff-action@v3`)
- **type-check**: mypy type checking with full strict mode
- **test**: pytest suite on multiple OS (Ubuntu, macOS, Windows)
- **build**: Package build verification with uv
- **all-checks-pass**: Meta-job ensuring all checks succeeded

**Features:**
- Explicit permissions (contents: read) for security
- Concurrency control (cancels outdated runs)
- Multi-OS matrix testing (ubuntu-latest, macos-latest, windows-latest)
- Code coverage upload to Codecov
- Uses `setup-uv@v7` with built-in caching
- GitHub annotations for Ruff violations
- Artifact retention policy (7 days auto-cleanup)
- Environment variable isolation in job result checks

#### `dependencies.yml` - Dependency Management

Weekly dependency health checks and security audits.

**Jobs:**
- **check-lockfile**: Verifies `uv.lock` is up-to-date with `pyproject.toml`
- **security-audit**: Runs pip-audit on exported dependencies with detailed descriptions
- **test-dependency-updates**: Tests compatibility with latest versions (manual trigger only)

**Security Features:**
- Explicit permissions (contents: read) for least privilege
- Weekly automated security audits with pip-audit
- Requirements file uploaded as artifact for review
- Detailed vulnerability descriptions

**Triggers:**
- Scheduled: Every Monday at 08:00 UTC
- Manual: Via workflow_dispatch (includes update testing)

**Commands used:**
```bash
uv lock --check              # Verify lockfile validity
uv tree                      # Show dependency tree
uv export --no-hashes        # Export for security audit
uv lock --upgrade            # Update to latest versions (manual only)
```

## Action Versions

All workflows use consistent, up-to-date action versions:

| Action                    | Version | Used In                  |
|---------------------------|---------|--------------------------|
| `actions/checkout`        | **v5**  | ci.yml, dependencies.yml |
| `astral-sh/setup-uv`      | **v7**  | ci.yml, dependencies.yml |
| `astral-sh/ruff-action`   | **v3**  | ci.yml                   |
| `codecov/codecov-action`  | **v5**  | ci.yml                   |
| `actions/upload-artifact` | **v4**  | ci.yml                   |

**Note:** Dependabot will automatically create PRs to update these actions when new versions are released.

## Required Secrets

The following GitHub repository secrets should be configured:

| Secret          | Required  | Used By | Purpose                            |
|-----------------|-----------|---------|------------------------------------|
| `CODECOV_TOKEN` | Optional* | ci.yml  | Upload coverage reports to Codecov |

**To configure secrets:**
1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add `CODECOV_TOKEN` with your Codecov upload token

## Useful Commands

### Local Development

```bash
# Check if lockfile is up-to-date
uv lock --check

# Show dependency tree
uv tree

# Update lockfile to latest compatible versions
uv lock --upgrade

# Run tests locally
uv run pytest

# Run linting
uv run ruff check .
uv run ruff format --check .

# Run type checking
uv run mypy httptap
```

### Workflow Testing

```bash
# Validate workflow syntax (requires GitHub CLI)
gh workflow list

# Run workflow manually (requires GitHub CLI)
gh workflow run "Dependency Check"

# View workflow runs
gh run list --workflow="CI"
```

## Best Practices Applied

1. **Ecosystem-specific configuration**: Uses `uv` for Python instead of generic `pip`
2. **Grouped updates**: Related packages updated together
3. **Rate limiting**: Prevents PR spam with reasonable limits
4. **Conventional commits**: Consistent commit message format
5. **Major version protection**: Requires manual review for breaking changes
6. **Target branch control**: All PRs go to `main` branch
7. **Scheduled updates**: Predictable Monday morning updates
8. **Action version consistency**: Same versions across all workflows
9. **Security auditing**: Weekly pip-audit runs for vulnerability detection
10. **Lockfile verification**: Ensures dependency lock is always valid
11. **Explicit permissions**: Workflows use least-privilege permissions (contents: read)
12. **Artifact retention**: Auto-cleanup after 7 days to prevent storage bloat
13. **Environment variable isolation**: Prevents code injection in workflow scripts

## Troubleshooting

### Dependabot not creating PRs

**Issue:** Dependabot configured but no PRs appear

**Solutions:**
1. Check that `uv.lock` exists in repository root
2. Verify `package-ecosystem: "uv"` (not `"pip"`)
3. Check repository settings: Settings → Code security → Dependabot
4. Review Dependabot logs: Insights → Dependency graph → Dependabot

### Lockfile out of sync

**Issue:** `uv lock --check` fails in CI

**Solution:**
```bash
# Locally update lockfile
uv lock

# Commit changes
git add uv.lock
git commit -m "chore: update lockfile"
```

### Codecov upload failing

**Issue:** Coverage uploads times out or fails

**Solutions:**
1. Check `CODECOV_TOKEN` is set in repository secrets
2. For Dependabot PRs, add token to Dependabot secrets
3. For public repos, enable "Global Upload Token" in Codecov settings
4. Verify `fail_ci_if_error: true` - set to `false` for non-critical failures

### pip-audit finding vulnerabilities

**Issue:** Security audit job reports vulnerabilities

**Action:**
1. Review the vulnerability details in the workflow logs
2. Download the `requirements-audit` artifact from the workflow run
3. Check if updates are available: `uv lock --upgrade`
4. If no fix is available, add to ignore list or update manually
5. `continue-on-error: true` prevents blocking CI

### GitHub Security Alerts

**Issue:** CodeQL or Dependabot security alerts

**Actions:**
1. Review alerts in the Security tab
2. For workflow permissions: Ensure `permissions:` block is present
3. For dependency vulnerabilities: Check if Dependabot has created a PR
4. Review SECURITY.md for vulnerability reporting process

## Further Reading

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Dependabot Configuration Reference](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)
- [uv Documentation](https://docs.astral.sh/uv/)
- [Codecov Documentation](https://docs.codecov.com/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
