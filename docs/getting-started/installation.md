# Installation

## Requirements

Before installing httptap, ensure you have:

- **Python 3.10 or higher** (CPython recommended)
- **pip** or **uv** package manager
- **macOS, Linux, or Windows** operating system

No system dependencies beyond standard networking are required.

## Installing from PyPI

=== "Using uv (recommended)"

    ```bash
    uv pip install httptap
    ```

    Or install as a global tool:

    ```bash
    uv tool install httptap
    ```

=== "Using pip"

    ```bash
    pip install httptap
    ```

=== "Using pipx"

    For isolated CLI tool installation:

    ```bash
    pipx install httptap
    ```

## Installing from Source

### Clone the repository

```bash
git clone https://github.com/ozeranskii/httptap.git
cd httptap
```

### Install with uv

```bash
uv sync
uv pip install -e .
```

### Install with pip

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## Verifying Installation

After installation, verify that httptap is correctly installed:

```bash
httptap --version
```

You should see output similar to:

```
httptap X.Y.Z
```

## Upgrading

To upgrade httptap to the latest version:

=== "Using uv"

    ```bash
    uv pip install --upgrade httptap
    ```

=== "Using pip"

    ```bash
    pip install --upgrade httptap
    ```

## Uninstalling

To remove httptap from your system:

=== "Using uv"

    ```bash
    uv pip uninstall httptap
    ```

=== "Using pip"

    ```bash
    pip uninstall httptap
    ```

=== "Using pipx"

    ```bash
    pipx uninstall httptap
    ```

---

## What's Next?

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **[Quick Start Guide](quick-start.md)**

    ---

    Learn the basics with simple examples

-   :material-console:{ .lg .middle } **[Basic Usage](../usage/basic.md)**

    ---

    Complete command-line reference

-   :material-api:{ .lg .middle } **[API Reference](../api/overview.md)**

    ---

    Use httptap programmatically

</div>
