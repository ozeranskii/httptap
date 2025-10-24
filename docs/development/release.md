# Release Process

This document describes the automated release process for httptap.

## Overview

Releases are fully automated using GitHub Actions. The workflow handles versioning, changelog generation, testing,
building, and publishing to PyPI.

## Prerequisites

Before creating a release, ensure:

1. **GitHub Environment** - `pypi` environment configured in repository settings
2. **PyPI Trusted Publishing** - Configured for `ozeranskii/httptap` repository
3. **Deploy Key** - SSH deploy key with write access (for bypassing branch protection)
4. **All tests passing** - CI must be green on main branch

## Release Workflow

The release process is triggered manually via GitHub Actions.

### Triggering a Release

1. Go to **Actions** → **Release** workflow
2. Click **Run workflow**
3. Choose version strategy:
    - **Explicit version**: Enter exact version (e.g., `0.3.0`)
    - **Semantic bump**: Select `patch`, `minor`, or `major`

### Semantic Versioning

| Bump Type | Example       | Use Case                           |
|-----------|---------------|------------------------------------|
| `patch`   | 0.1.0 → 0.1.1 | Bug fixes, small improvements      |
| `minor`   | 0.1.0 → 0.2.0 | New features, backwards compatible |
| `major`   | 0.1.0 → 1.0.0 | Breaking changes                   |

### What Happens Automatically

1. **Version Update**
   ```bash
   uv version 0.2.0  # or
   uv version --bump minor
   ```
   Updates `version` in `pyproject.toml`

2. **Changelog Generation**
   ```bash
   git cliff --tag v0.2.0 --unreleased --prepend CHANGELOG.md
   ```
   Generates changelog from conventional commits

3. **Commit and Tag**
   ```bash
   git commit -m "chore: release v0.2.0"
   git tag -a v0.2.0 -m "Release v0.2.0"
   git push origin HEAD
   git push origin v0.2.0
   ```

4. **Build**
   ```bash
   uv sync --locked --group test
   uv run pytest  # Full test suite
   uv build  # Create wheel and sdist
   ```

5. **Publish to PyPI**
    - Uses OIDC Trusted Publishing (no tokens required)
    - Uploads wheel and source distribution

6. **GitHub Release**
    - Creates release with generated notes
    - Attaches build artifacts

## Workflow Configuration

The release workflow is defined in `.github/workflows/release.yml`:

### Key Jobs

#### 1. Prepare Release

- Checks out code with deploy key
- Configures Python and uv
- Updates version in pyproject.toml
- Generates changelog
- Commits and pushes changes
- Creates and pushes git tag

#### 2. Build Package

- Checks out the tagged version
- Runs full test suite
- Builds wheel and sdist
- Uploads artifacts

#### 3. Publish to PyPI

- Downloads build artifacts
- Publishes using Trusted Publishing

#### 4. Create GitHub Release

- Downloads artifacts
- Creates GitHub release with changelog notes
- Attaches wheel and sdist

## Changelog Generation

Changelogs are automatically generated using [git-cliff](https://git-cliff.org/) based on conventional commits.

### Commit Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Supported Types

| Type       | Changelog Section | Example                                  |
|------------|-------------------|------------------------------------------|
| `feat`     | Features          | `feat(cli): add --timeout flag`          |
| `fix`      | Bug Fixes         | `fix(tls): handle expired certificates`  |
| `perf`     | Performance       | `perf(dns): optimize resolver cache`     |
| `docs`     | Documentation     | `docs: update API reference`             |
| `refactor` | Refactor          | `refactor(core): extract analyzer logic` |
| `test`     | Testing           | `test: add integration tests`            |
| `chore`    | Miscellaneous     | `chore: update dependencies`             |

### Breaking Changes

Mark breaking changes in commit footer:

```
feat(api): redesign analyzer interface

BREAKING CHANGE: HTTPTapAnalyzer constructor signature changed
```

## Version Strategy

httptap follows [Semantic Versioning](https://semver.org/):

- **Major version** (1.0.0) - Breaking changes
- **Minor version** (0.1.0) - New features, backwards compatible
- **Patch version** (0.0.1) - Bug fixes

### Pre-1.0 Development

During pre-1.0 development (0.x.x):

- Minor version may include breaking changes
- Patch version for bug fixes and minor features
- Move to 1.0.0 when API is stable

## Manual Release Steps

If you need to release manually (not recommended):

### 1. Update Version

```bash
uv version 0.2.0
```

### 2. Generate Changelog

```bash
git cliff --tag v0.2.0 --unreleased --prepend CHANGELOG.md
```

### 3. Commit Changes

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v0.2.0"
```

### 4. Create Tag

```bash
git tag -a v0.2.0 -m "Release v0.2.0"
```

### 5. Push

```bash
git push origin main
git push origin v0.2.0
```

### 6. Build and Publish

```bash
uv build
uv publish  # Requires PyPI credentials
```

### 7. Create GitHub Release

Use `gh` CLI or web interface to create release with changelog notes.

## Troubleshooting

### Branch Protection Errors

If push fails due to branch protection:

1. Verify deploy key has write access
2. Check deploy key is in bypass list for branch protection rules
3. Ensure `ssh-key` is configured in workflow checkout

### Changelog Empty

If changelog generation returns empty:

1. Ensure commits follow conventional format
2. Check git-cliff configuration in `.release/git-cliff.toml`
3. Verify tag doesn't already exist

### PyPI Publishing Fails

If PyPI publishing fails:

1. Verify `pypi` environment exists
2. Check Trusted Publishing is configured on PyPI
3. Ensure workflow has `id-token: write` permission

### Test Failures

If tests fail during release:

1. Workflow will stop before publishing
2. Fix issues and re-run workflow
3. No partial releases will occur

## Post-Release

After successful release:

1. Verify package on PyPI: https://pypi.org/project/httptap/
2. Check GitHub release: https://github.com/ozeranskii/httptap/releases
3. Test installation: `uv pip install httptap=={version}`
4. Announce release (Twitter, Discord, etc.)

## Release Checklist

Before triggering release:

- [ ] All CI checks passing on main
- [ ] No known critical bugs
- [ ] Documentation updated
- [ ] Breaking changes documented
- [ ] Migration guide written (for major versions)
- [ ] Dependencies updated
- [ ] Security vulnerabilities addressed

## See Also

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [git-cliff documentation](https://git-cliff.org/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
