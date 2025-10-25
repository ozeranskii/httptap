# Contributing to httptap

Thank you for your interest in contributing to httptap! This document provides guidelines and information for
contributors.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected
to uphold this code.

## Ways to Contribute

- 🐛 **Report bugs** - Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml)
- ✨ **Suggest features** - Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.yml)
- 🐌 **Report performance issues** - Use the [Performance Issue template](.github/ISSUE_TEMPLATE/performance_issue.yml)
- 📚 **Improve documentation** - Use the [Documentation template](.github/ISSUE_TEMPLATE/documentation.yml)
- 💻 **Submit code** - Send a pull request
- 💬 **Join discussions** - Share ideas in [Discussions](https://github.com/ozeranskii/httptap/discussions)

## Getting Started

### Prerequisites

- Python 3.10+ (CPython)
- [uv](https://docs.astral.sh/uv/) package manager
- Git

### Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/httptap.git
cd httptap
```

2. **Install dependencies**

```bash
uv sync
```

This installs httptap in editable mode with all development dependencies.

3. **Set up pre-commit hooks (recommended)**

```bash
# Install pre-commit
pip install pre-commit

# Install the git hook scripts
pre-commit install
```

This will automatically run ruff (linting/formatting) and mypy (type checking) before each commit.

4. **Verify installation**

```bash
uv run httptap --version
uv run pytest
uv run ruff check .
uv run mypy httptap
```

## Development Workflow

### Pre-commit Hooks

If you've set up pre-commit hooks (recommended), they will automatically run before each commit:

- **Ruff**: Lints and formats your code
- **MyPy**: Performs type checking

**If hooks fail:**

- Fix the issues and commit again
- The hooks will re-run automatically
- You can skip hooks with `git commit --no-verify` (not recommended)

**Manual pre-commit run:**

```bash
# Run hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff
pre-commit run mypy

# Validate configuration
pre-commit validate-config
```

**CI Validation:**
The CI automatically validates that the pre-commit configuration stays in sync and all hooks work correctly. This ensures consistency across all contributors.

### Code Style

httptap follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

**Linting and formatting:**

```bash
# Check code style
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

**Type checking:**

```bash
uv run mypy httptap
```

All code must pass mypy strict mode checks.

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov --cov-report=term --cov-report=html

# Run specific test file
uv run pytest tests/test_http_client.py

# Run tests matching pattern
uv run pytest -k "test_timing"

# Verbose output
uv run pytest -v
```

### Writing Tests

- Place tests in `tests/` directory
- Follow naming convention: `test_*.py`
- Use descriptive test names: `test_get_metrics_calculates_dns_ms`
- Mock external dependencies when possible (see `tests/test_implementations_timing.py`)
- Aim for high coverage (current: ~90%)

**Example test:**

```python
from unittest.mock import patch
from httptap.implementations.timing import PerfCounterTimingCollector


def test_timing_collector():
    """Test that timing collector accurately measures phases."""
    with patch("time.perf_counter", side_effect=[1.0, 1.1, 1.2]):
        collector = PerfCounterTimingCollector()
        collector.mark_dns_start()
        collector.mark_dns_end()

        metrics = collector.get_metrics()
        assert metrics.dns_ms == 100.0  # 0.1 seconds = 100ms
```

### Making Changes

1. **Create a feature branch**

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-123
```

2. **Make your changes**

- Write clear, self-documenting code
- Add docstrings to new functions/classes (Google style)
- Update type hints
- Add tests for new functionality

3. **Test your changes**

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy httptap
```

4. **Commit your changes**

```bash
git add .
git commit -m "feat: add support for custom timeout per phase"
```

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Build/tooling changes

5. **Push and create PR**

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub using the [PR template](.github/pull_request_template.md).

## Pull Request Guidelines

### Before Submitting

- [ ] All tests pass: `uv run pytest`
- [ ] Code is formatted: `uv run ruff format .` (or let pre-commit handle it)
- [ ] Linting passes: `uv run ruff check .` (or let pre-commit handle it)
- [ ] Type checking passes: `uv run mypy httptap` (or let pre-commit handle it)
- [ ] Documentation updated (if applicable)
- [ ] Tests added for new features
- [ ] Changelog updated (if significant change)

**Note**: If you're using pre-commit hooks, the formatting, linting, and type checking will be handled automatically before each commit.

### PR Description

Use the PR template and include:

- **What**: Clear description of changes
- **Why**: Problem being solved or use case
- **How**: Approach taken
- **Testing**: How you verified it works
- **Screenshots/output**: For UI/output changes

### Review Process

1. Automated checks run (CI/CD)
2. Maintainers review code
3. Address feedback
4. Approval and merge

## Project Structure

```
httptap/
├── httptap/                 # Main package
│   ├── __init__.py         # Public API
│   ├── cli.py              # CLI entry point
│   ├── http_client.py      # HTTP client with tracing
│   ├── analyzer.py         # High-level analyzer
│   ├── models.py           # Data models (Step, Timing, NetworkInfo)
│   ├── interfaces.py       # Protocol definitions
│   ├── implementations/    # Concrete implementations
│   │   ├── dns.py         # DNS resolvers
│   │   ├── tls.py         # TLS inspectors
│   │   └── timing.py      # Timing collectors
│   ├── tls_inspector.py   # TLS certificate inspection
│   ├── formatters.py      # Output formatters
│   ├── visualizer.py      # Rich table visualizer
│   └── constants.py       # Configuration constants
├── tests/                  # Test suite
├── .github/               # GitHub configuration
│   ├── workflows/         # CI/CD workflows
│   └── ISSUE_TEMPLATE/    # Issue templates
├── pyproject.toml         # Project metadata and dependencies
├── uv.lock               # Dependency lock file
└── README.md             # Project documentation
```

## Architecture

httptap uses Protocol-based dependency injection for extensibility:

- **Protocols** (`interfaces.py`): Define contracts (DNSResolver, TLSInspector, TimingCollector, etc.)
- **Implementations** (`implementations/`): Concrete implementations
- **Analyzer** (`analyzer.py`): High-level orchestration
- **HTTP Client** (`http_client.py`): Low-level httpcore integration with tracing

This allows users to swap implementations:

```python
from httptap import HTTPTapAnalyzer, SystemDNSResolver


class CustomDNS(SystemDNSResolver):
    def resolve(self, host, port, timeout):
        return "93.184.216.34", "IPv4", 0.1


analyzer = HTTPTapAnalyzer(dns_resolver=CustomDNS())
```

## Adding Features

### New Output Format

1. Implement `Visualizer` Protocol in `interfaces.py`
2. Add implementation to `visualizer.py` or `formatters.py`
3. Register in CLI options (`cli.py`)
4. Add tests
5. Update documentation

### New Measurement Phase

1. Update `Timing` model in `models.py`
2. Add measurement logic in `http_client.py` or `implementations/timing.py`
3. Update trace hooks if needed
4. Add to output formatters
5. Add tests
6. Update documentation

### New Network Inspection

1. Implement `TLSInspector` Protocol
2. Add to `implementations/tls.py`
3. Integrate into `http_client.py`
4. Update `NetworkInfo` model if needed
5. Add tests
6. Update documentation

## Documentation

### Docstring Format

Use Google style docstrings:

```python
def resolve(self, host: str, port: int, timeout: float) -> tuple[str, str, float]:
    """Resolve hostname to IP address.

    Args:
        host: Hostname to resolve.
        port: Port number (may affect resolution).
        timeout: Maximum time to wait in seconds.

    Returns:
        Tuple of (ip_address, ip_family, duration_ms).

    Raises:
        DNSResolutionError: If resolution fails.

    Examples:
        >>> resolver = SystemDNSResolver()
        >>> ip, family, duration = resolver.resolve("example.com", 443, 5.0)
        >>> print(f"{ip} ({family})")
        93.184.216.34 (IPv4)
    """
```

### README Updates

Update `README.md` when:

- Adding new CLI flags
- Adding new output formats
- Changing installation instructions
- Adding new features to "Highlights" section

## Release Process

(For maintainers)

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release tag: `git tag -a v0.2.0 -m "Release v0.2.0"`
4. Push tag: `git push origin v0.2.0`
5. Build and publish to PyPI: `uv build && uv publish`
6. Create GitHub release with changelog

## Getting Help

- 💬 [GitHub Discussions](https://github.com/ozeranskii/httptap/discussions) - Ask questions, share ideas
- 🐛 [GitHub Issues](https://github.com/ozeranskii/httptap/issues) - Report bugs, request features
- 📧 Email maintainer (see `pyproject.toml`)

## License

By contributing to httptap, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

---

**Thank you for contributing to httptap!** 🚀
