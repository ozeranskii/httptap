## Description

<!-- Provide a clear and concise description of your changes -->

Fixes # (issue number, if applicable)

## Type of Change

<!-- Mark the relevant option with an 'x' -->

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🎨 Code style/refactoring (no functional changes)
- [ ] ⚡ Performance improvement
- [ ] ✅ Test improvements
- [ ] 🔧 Build/CI/tooling changes

## Changes Made

<!-- Describe what you changed and why -->

-
-
-

## Testing

<!-- Describe how you tested your changes -->

**Test environment:**

- OS:
- Python version:
- httptap version:

**Tests performed:**

- [ ] Ran existing test suite: `uv run pytest`
- [ ] Added new tests for new functionality
- [ ] Manually tested with: `httptap <command>`
- [ ] Tested on multiple OS (if applicable): Linux / macOS / Windows

**Test commands:**

```bash
# Example commands used to verify the changes
httptap https://httpbin.io/get
```

**Expected behavior:**
<!-- What should happen after your changes? -->

**Actual behavior:**
<!-- What actually happens? Include output if relevant -->

## Screenshots/Output

<!-- If applicable, add screenshots or sample output to demonstrate the changes -->

```
# Paste sample output here
```

## Checklist

<!-- Ensure you've completed these steps before submitting -->

- [ ] My code follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [ ] I have run `uv run ruff check .` and `uv run ruff format .`
- [ ] I have run `uv run mypy httptap` and resolved type errors
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] All tests pass locally: `uv run pytest`
- [ ] I have updated the documentation (if applicable)
- [ ] I have added docstrings to new functions/classes
- [ ] My changes don't introduce new dependencies (or I've justified them)
- [ ] I have checked that my changes work on multiple platforms (if applicable)

## Breaking Changes

<!-- If this is a breaking change, describe the impact and migration path -->

**Impact:**
<!-- Who will be affected? -->

**Migration:**
<!-- How should users update their code/usage? -->

## Additional Context

<!-- Add any other context about the PR here -->

---

**For Maintainers:**
<!-- This section is for maintainers to fill out during review -->

- [ ] Code review completed
- [ ] Tests verified
- [ ] Documentation reviewed
- [ ] Ready to merge
