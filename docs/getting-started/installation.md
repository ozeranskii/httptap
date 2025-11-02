# Installation

## Requirements

Before installing httptap, ensure you have:

- **Python 3.10 or higher** (CPython recommended)
- **pip** or **uv** package manager
- **macOS, Linux, or Windows** operating system

No system dependencies beyond standard networking are required.

## Installing via Homebrew

=== "macOS"

    ```bash
    brew install httptap
    ```

=== "Linux"

    ```bash
    brew install httptap
    ```

!!! tip "Recommended for macOS/Linux users"
    Homebrew installation is the simplest method and includes automatic shell completion setup.

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

=== "Using Homebrew"

    ```bash
    brew upgrade httptap
    ```

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

=== "Using Homebrew"

    ```bash
    brew uninstall httptap
    ```

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

## Shell Completions

httptap supports shell completions for bash and zsh.

### Homebrew Installation

If you installed httptap via Homebrew, **completions are automatically configured**. Simply restart your shell:

```bash
# Restart your shell
exec $SHELL
```

Homebrew automatically places completion scripts in:

- **Bash**: `$(brew --prefix)/etc/bash_completion.d/`
- **Zsh**: `$(brew --prefix)/share/zsh/site-functions/`

!!! success "No additional setup required"
    Homebrew handles all completion setup automatically. Just restart your shell and start using Tab completion!

### Python Package Installation

If you installed httptap via `pip`, `uv`, or `pipx`, you need to install the optional `completion` extras:

=== "Using uv"

    ```bash
    uv pip install "httptap[completion]"
    ```

=== "Using pip"

    ```bash
    pip install "httptap[completion]"
    ```

=== "Using pipx"

    ```bash
    pipx install "httptap[completion]"
    ```

#### Activation

1. Activate your virtual environment (if using venv):

    ```bash
    source .venv/bin/activate
    ```

2. Run the global activation script:

    ```bash
    activate-global-python-argcomplete
    ```

3. Restart your shell.

### Usage

Once installed and activated, you can use `Tab` to autocomplete commands and options:

```bash
# Complete command options
httptap --<TAB>

# Complete after typing partial option
httptap --fol<TAB>
# Completes to: httptap --follow

# Complete multiple options
httptap --follow --time<TAB>
# Completes to: httptap --follow --timeout
```

!!! note
    The global activation script provides argument completions for bash and zsh only. Other shells are not covered by the script and must be configured separately.

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
