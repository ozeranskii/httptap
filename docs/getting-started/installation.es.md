---
description: Instala httptap con uvx, Homebrew, PyPI, un contenedor o desde el código fuente, y habilita la autocompletado de shell.
---

# Instalación

## Requisitos

Antes de instalar httptap, asegúrate de tener:

- **Python 3.10-3.15** (se recomienda CPython)
- Gestor de paquetes **pip** o **uv**
- Sistema operativo **macOS, Linux o Windows**

No se requieren dependencies del sistema más allá de la red estándar.

## Ejecución con uvx

La forma más rápida de ejecutar httptap sin una instalación permanente. [`uvx`](https://docs.astral.sh/uv/guides/tools/) (incluido con [uv](https://docs.astral.sh/uv/)) obtiene httptap y lo ejecuta en un entorno efímero y aislado:

```bash
uvx --from "httptap[completion]" httptap https://example.com
```

!!! tip "Recomendado para una prueba rápida"
    `uvx` no necesita un paso de instalación previo y no deja nada atrás — ideal para comprobaciones puntuales o para probar httptap. Para un uso repetido, instálalo con uno de los métodos siguientes.

## Instalación mediante Homebrew

=== "macOS"

    ```bash
    brew install httptap
    ```

=== "Linux"

    ```bash
    brew install httptap
    ```

!!! tip "Cómodo para usuarios de macOS/Linux"
    La instalación con Homebrew es el método más sencillo e incluye la configuración automática del autocompletado de shell.

## Instalación desde PyPI

=== "Con uv"

    ```bash
    uv pip install httptap
    ```

    O instálalo como una herramienta global:

    ```bash
    uv tool install httptap
    ```

=== "Con pip"

    ```bash
    pip install httptap
    ```

=== "Con pipx"

    Para una instalación aislada de la herramienta de CLI:

    ```bash
    pipx install httptap
    ```

## Ejecución mediante contenedor

En cada versión se publican imágenes multiarquitectura firmadas (linux/amd64, linux/arm64) en GitHub Container Registry:

```bash
docker run --rm ghcr.io/ozeranskii/httptap:latest https://example.com
```

Verifica la firma de la imagen con [cosign](https://docs.sigstore.dev/cosign/overview/) (Sigstore sin claves):

```bash
cosign verify ghcr.io/ozeranskii/httptap:latest \
  --certificate-identity-regexp 'https://github\.com/ozeranskii/httptap/\.github/workflows/release\.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

También se publican etiquetas mayores/menores fijadas (p. ej. `:0`, `:0.6`, `:0.6.0`).

## Instalación desde el código fuente

### Clona el repositorio

```bash
git clone https://github.com/ozeranskii/httptap.git
cd httptap
```

### Instala con uv

```bash
uv sync
```

### Instala con pip

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## Verificación de la instalación

Después de la instalación, verifica que httptap se instaló correctamente:

```bash
httptap --version
```

Deberías ver una salida similar a:

```
httptap X.Y.Z
```

## Actualización

Para actualizar httptap a la última versión:

=== "Con Homebrew"

    ```bash
    brew upgrade httptap
    ```

=== "Con uv"

    ```bash
    uv pip install --upgrade httptap
    ```

=== "Con pip"

    ```bash
    pip install --upgrade httptap
    ```

## Desinstalación

Para eliminar httptap de tu sistema:

=== "Con Homebrew"

    ```bash
    brew uninstall httptap
    ```

=== "Con uv"

    ```bash
    uv pip uninstall httptap
    ```

=== "Con pip"

    ```bash
    pip uninstall httptap
    ```

=== "Con pipx"

    ```bash
    pipx uninstall httptap
    ```

---

## Autocompletado de shell

httptap admite el autocompletado de shell para bash y zsh.

### Instalación con Homebrew

Si instalaste httptap mediante Homebrew, **el autocompletado se configura automáticamente**. Simplemente reinicia tu shell:

```bash
# Restart your shell
exec $SHELL
```

Homebrew coloca automáticamente los scripts de autocompletado en:

- **Bash**: `$(brew --prefix)/etc/bash_completion.d/`
- **Zsh**: `$(brew --prefix)/share/zsh/site-functions/`

!!! success "No se require configuración adicional"
    Homebrew gestiona toda la configuración del autocompletado automáticamente. ¡Solo reinicia tu shell y empieza a usar el autocompletado con Tab!

### Instalación del paquete de Python

Si instalaste httptap mediante `pip`, `uv` o `pipx`, necesitas instalar los extras opcionales de `completion`:

=== "Con uv"

    ```bash
    uv pip install "httptap[completion]"
    ```

=== "Con pip"

    ```bash
    pip install "httptap[completion]"
    ```

=== "Con pipx"

    ```bash
    pipx install "httptap[completion]"
    ```

#### Activación

1. Activa tu entorno virtual (si usas venv):

    ```bash
    source .venv/bin/activate
    ```

2. Habilita el autocompletado para bash/zsh. O bien regístralo globalmente una vez:

    ```bash
    activate-global-python-argcomplete
    ```

    O, para habilitarlo solo para `httptap`, añade esto a tu archivo de inicio del shell (p. ej. `~/.bashrc` o `~/.zshrc`):

    ```bash
    eval "$(register-python-argcomplete httptap)"
    ```

3. Reinicia tu shell.

### Uso

Una vez instalado y activado, puedes usar `Tab` para autocompletar commandos y opciones:

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
    El script de activación global proporciona autocompletado de arguments solo para bash y zsh. Otros shells no están cubiertos por el script y deben configurarse por separado.

---

## ¿Qué sigue?

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **[Guía de inicio rápido](quick-start.md)**

    ---

    Aprende lo básico con ejemplos sencillos

-   :material-console:{ .lg .middle } **[Uso básico](../usage/basic.md)**

    ---

    Referencia completa de la línea de commandos

-   :material-api:{ .lg .middle } **[Referencia de la API](../api/overview.md)**

    ---

    Usa httptap de forma programática

</div>
