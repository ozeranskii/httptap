# Contributing

We welcome contributions to httptap! This guide will help you get started.

## Code of Conduct

Please note that this project follows
the [Contributor Covenant Code of Conduct](https://github.com/ozeranskii/httptap/blob/main/CODE_OF_CONDUCT.md). By
participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git

### Setting Up Development Environment

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/httptap.git
   cd httptap
   ```

2. **Install dependencies:**

   ```bash
   uv sync
   ```

3. **Verify installation:**

   ```bash
   uv run httptap --version
   ```

## Development Workflow

### Running Tests

Run the full test suite:

```bash
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov --cov-report=html
```

View coverage report:

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Code Quality

#### Linting

Run Ruff linter:

```bash
uv run ruff check
```

Auto-fix issues:

```bash
uv run ruff check --fix
```

#### Formatting

Check formatting:

```bash
uv run ruff format --check
```

Auto-format code:

```bash
uv run ruff format .
```

#### Type Checking

Run mypy:

```bash
uv run mypy httptap
```

### Running Locally

Test your changes:

```bash
uv run httptap https://httpbin.io
```

Or install in editable mode:

```bash
uv pip install -e .
httptap https://httpbin.io
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-http2-support` - New features
- `fix/tls-timeout-issue` - Bug fixes
- `docs/update-api-reference` - Documentation
- `refactor/extract-parser` - Code refactoring

### Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `refactor` - Code refactoring
- `test` - Adding/updating tests
- `chore` - Maintenance tasks
- `perf` - Performance improvements

**Examples:**

```
feat(cli): add --timeout flag for request timeout

Add command-line option to specify custom timeout for HTTP requests.
Defaults to 30 seconds if not specified.

Closes #123
```

```
fix(tls): handle certificate expiry edge case

Fix crash when certificate expiry date is in the past.
Now properly reports negative days and warns user.

Fixes #456
```

### Code Style

Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html):

- Use type hints for all function signatures
- Write docstrings for all public APIs
- Keep lines under 120 characters
- Use double quotes for strings
- Follow PEP 8 naming conventions

**Example:**

```python
def resolve_hostname(host: str, timeout: float = 5.0) -> tuple[str, str]:
    """Resolve hostname to IP address.

    Args:
        host: Hostname to resolve.
        timeout: Maximum time to wait in seconds.

    Returns:
        Tuple of (ip_address, family).

    Raises:
        DNSError: If resolution fails.
    """
    pass
```

### Testing Guidelines

- Write tests for all new features
- Maintain or improve code coverage
- Use descriptive test names
- Mock external dependencies (DNS, TLS, HTTP)
- Test both success and failure cases

**Example:**

```python
def test_analyzer_follows_redirects(mock_http_client):
    """Test that analyzer follows redirect chains correctly."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url(
        "https://httpbin.io/redirect/3",
        follow_redirects=True
    )

    assert len(steps) == 4  # Initial + 3 redirects
    assert steps[-1].response.status == 200
```

## Pull Request Process

1. **Create a feature branch:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes and commit:**

   ```bash
   git add .
   git commit -m "feat: add awesome feature"
   ```

3. **Push to your fork:**

   ```bash
   git push origin feature/your-feature-name
   ```

4. **Create a Pull Request:**

    - Go to the [httptap repository](https://github.com/ozeranskii/httptap)
    - Click "New Pull Request"
    - Select your branch
    - Fill out the PR template

### PR Checklist

Before submitting, ensure:

- [ ] Tests pass (`uv run pytest`)
- [ ] Code is formatted (`uv run ruff format .`)
- [ ] Linter passes (`uv run ruff check`)
- [ ] Type checks pass (`uv run mypy httptap`)
- [ ] Documentation is updated (if needed)
- [ ] CHANGELOG.md is updated (for significant changes)
- [ ] Commit messages follow conventional format

## Documentation

### Updating Docs

Documentation is in the `docs/` directory:

```
docs/
├── getting-started/
├── usage/
├── api/
├── development/
└── about/
```

Build docs locally:

```bash
uv run mkdocs serve
```

View at: http://127.0.0.1:8000

### Documentation Standards

- Use clear, concise language
- Include code examples
- Keep examples realistic and practical
- Use proper Markdown formatting
- Test all code examples

## Areas for Contribution

### Good First Issues

Look for issues labeled [`good first issue`](https://github.com/ozeranskii/httptap/labels/good%20first%20issue) - these
are beginner-friendly.

### Help Wanted

Issues labeled [`help wanted`](https://github.com/ozeranskii/httptap/labels/help%20wanted) are priorities we'd love
assistance with.

### Ideas for Contributions

- **HTTP/2 and HTTP/3 support** - Extend to newer protocols
- **More export formats** - CSV, XML, Prometheus metrics
- **Additional visualizations** - Flamegraphs, charts
- **Performance optimizations** - Faster DNS, connection pooling
- **More TLS details** - OCSP, certificate chain analysis
- **Custom reporters** - Slack, webhook notifications
- **Additional protocols** - WebSocket, gRPC timing

## Getting Help

- **GitHub Issues** - Bug reports and feature requests
- **Discussions** - Questions and general discussion
- **Discord** - Real-time chat (coming soon)

## Recognition

Contributors are recognized in:

- [CHANGELOG.md](https://github.com/ozeranskii/httptap/blob/main/CHANGELOG.md)
- GitHub Contributors page
- Release notes

Thank you for contributing to httptap! 🎉
