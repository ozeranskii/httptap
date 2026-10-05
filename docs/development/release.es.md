---
description: El proceso de publicación automatizado con GitHub Actions para httptap.
---

# Proceso de publicación

Este documento describe el proceso de publicación automatizado para httptap.

## Visión general

Las publicaciones están totalmente automatizadas usando GitHub Actions. El flujo de trabajo gestiona el versionado, la generación del registro de cambios, las pruebas,
la compilación, la firma, la publicación en TestPyPI y PyPI, y el envío de una
imagen de contenedor firmada a GHCR.

## Requisitos previos

Antes de crear una publicación, asegúrate de:

1. **GitHub Environments** - Entornos `release`, `testpypi` y `pypi` configurados en la configuración del repositorio,
   cada uno admitiendo despliegues solo desde `main`; `pypi` requiere un revisor
2. **PyPI Trusted Publishing** - Configurado tanto para PyPI como para TestPyPI (OIDC, sin tokens)
3. **Deploy Key** - Clave de despliegue SSH con acceso de escritura, guardada solo como secreto `DEPLOY_KEY` del
   entorno `release` y autorizada a eludir la protección de la rama `main` y el conjunto de reglas que protege
   las etiquetas `refs/tags/v*`
4. **Acceso a GHCR** - Permiso `packages: write` en el job de publicación (otorgado por flujo de trabajo)
5. **Todas las pruebas pasando** - CI debe estar en verde en la rama main

## Flujo de trabajo de publicación

El proceso de publicación se activa manualmente mediante GitHub Actions.

### Activar una publicación

1. Ve al flujo de trabajo **Actions** → **Release**
2. Haz clic en **Run workflow**
3. Elige la estrategia de versión:
    - **Versión explícita**: Introduce la versión exacta (por ejemplo, `0.3.0`)
    - **Incremento semántico**: Selecciona `patch`, `minor` o `major`

### Versionado semántico

| Tipo de incremento | Ejemplo       | Caso de uso                           |
|-----------|---------------|------------------------------------|
| `patch`   | 0.1.0 → 0.1.1 | Correcciones de errores, mejoras pequeñas      |
| `minor`   | 0.1.0 → 0.2.0 | Nuevas funcionalidades, compatible hacia atrás |
| `major`   | 0.1.0 → 1.0.0 | Cambios incompatibles                   |

### Qué sucede automáticamente

1. **Actualización de versión**
   ```bash
   uv version 0.2.0  # or
   uv version --bump minor
   ```
   Actualiza `version` en `pyproject.toml`

2. **Actualización del lockfile**
   ```bash
   uv lock
   ```
   Regenera `uv.lock` para que se mantenga sincronizado con la nueva versión

3. **Generación del registro de cambios**
   ```bash
   git cliff --tag v0.2.0 --unreleased --prepend CHANGELOG.md
   ```
   Genera el registro de cambios a partir de los conventional commits

4. **Commit y etiqueta firmados (solo en local)**
   ```bash
   git commit -S -m "chore: release v0.2.0"
   git tag -s v0.2.0 -m "Release v0.2.0"
   git bundle create release.bundle "^$GITHUB_SHA" HEAD refs/tags/v0.2.0
   ```
   Firma sin claves de Sigstore mediante [gitsign](https://github.com/sigstore/gitsign):
   se emite un certificado Fulcio de corta duración a través de la identidad OIDC
   del flujo de trabajo, de modo que no se requieren claves GPG de larga duración.
   Todavía no se envía nada: el commit y la etiqueta pasan a los siguientes jobs
   como un artefacto de git bundle.

5. **Compilación**
   ```bash
   uv sync --locked --no-dev --group test
   uv run --no-sync pytest  # Full test suite
   uv build  # Create wheel and sdist
   uv venv "$RUNNER_TEMP/httptap-wheel"
   uv pip install --python "$RUNNER_TEMP/httptap-wheel" "$(echo dist/httptap-*.whl)[otel]"
   uv sync --locked --no-dev --no-install-project --group test --group e2e
   uv run --no-sync pytest tests/e2e --no-cov -n auto --httptap "$RUNNER_TEMP/httptap-wheel/bin/httptap"
   ```
   Se ejecuta sobre la etiqueta de publicación no enviada procedente del bundle. Después, la suite de
   extremo a extremo ejecuta la CLI del wheel compilado, instalado con el extra `otel`, de modo que un
   error de empaquetado hace fallar la publicación antes de atestar o subir nada.

6. **Envío del commit y la etiqueta**
   ```bash
   git push --atomic origin "v0.2.0^{commit}:refs/heads/main" refs/tags/v0.2.0:refs/tags/v0.2.0
   ```
   Solo después de que la compilación y la atestación tengan éxito. El envío es
   únicamente fast-forward y atómico, así que si `main` avanzó durante la
   publicación no se actualizan ni la rama ni la etiqueta, y el flujo de trabajo
   se detiene aquí, antes de publicar nada.

7. **Publicación en TestPyPI**
    - Sube primero a TestPyPI mediante OIDC Trusted Publishing, con atestaciones
      PEP 740, como prueba de humo antes del envío de producción.

8. **Publicación en PyPI**
    - Usa OIDC Trusted Publishing (no se requieren tokens)
    - Sube el wheel y la distribución de código fuente con atestaciones PEP 740

9. **Publicación de la imagen de contenedor en GHCR**
    - Se ejecuta solo después de la publicación en PyPI, por lo que espera la revisión de `pypi`
    - Compila una imagen multiarquitectura (linux/amd64, linux/arm64)
    - Envía a `ghcr.io/ozeranskii/httptap` con las etiquetas `{version}`, `{major}.{minor}`,
      `{major}` y `latest`
    - Firma la imagen con cosign (Sigstore sin claves)
    - Adjunta procedencia de compilación SLSA mediante `actions/attest-build-provenance`

10. **GitHub Release**
    - Crea la publicación con notas generadas
    - Adjunta los artefactos de compilación, los SBOM, el VEX y la página de manual

## Configuración del flujo de trabajo

El flujo de trabajo de publicación está definido en `.github/workflows/release.yml`:

### Jobs clave

#### 1. Preparar la publicación

- Extrae el código (solo lectura, sin clave de despliegue)
- Configura Python y uv
- Actualiza la versión en pyproject.toml
- Genera el registro de cambios
- Añade la publicación a las declaraciones `fixed` de `.vex/httptap.openvex.json` e incrementa la versión del documento
- Crea localmente el commit y la etiqueta de publicación firmados
- Los sube como artefacto `release-bundle`; no se envía nada

#### 2. Compilar el paquete

- Extrae la etiqueta de publicación no enviada desde el bundle
- Ejecuta el conjunto de pruebas completo
- Compila el wheel y el sdist
- Ejecuta la suite de extremo a extremo (`tests/e2e`) contra el wheel compilado con el extra `otel`
- Genera el SBOM en formatos JSON CycloneDX y SPDX mediante [Syft](https://github.com/anchore/syft)
- Falla si alguna declaración `fixed` de `.vex/httptap.openvex.json` no incluye la publicación y luego copia el documento al directorio `sbom/` como `httptap-X.Y.Z.openvex.json`
- Genera una página `man(1)` comprimida con gzip usando [argparse-manpage](https://github.com/praiskup/argparse-manpage)
- Sube los artefactos `dist/`, `sbom/` y `man/` por separado

#### 3. Enviar el commit y la etiqueta de publicación

- Se ejecuta solo después de que la compilación y la atestación de procedencia tengan éxito
- Es el único job que escribe en el repositorio git; envía por SSH con la clave de despliegue del entorno
  `release`, así que su token del flujo de trabajo es de solo lectura (`contents: read`)
- Avanza `main` mediante fast-forward hasta el commit de publicación y envía la etiqueta en un único envío
  atómico; falla sin publicar nada si `main` avanzó durante la publicación

#### 4. Publicar en TestPyPI

- Descarga los artefactos `dist/`
- Publica mediante TestPyPI OIDC Trusted Publishing con atestaciones PEP 740

#### 5. Publicar en PyPI

- Se ejecuta solo después de que TestPyPI tenga éxito
- Publica usando Trusted Publishing con atestaciones PEP 740

#### 6. Publicar la imagen de contenedor en GHCR

- Se ejecuta solo después de la publicación en PyPI, así que nada llega a GHCR antes de la revisión del entorno `pypi`
- Compila una imagen multiarquitectura con Buildx + QEMU
- Firma con cosign (Sigstore OIDC sin claves)
- Adjunta procedencia de compilación SLSA

#### 7. Crear la GitHub Release

- Es el único job con `contents: write`, que necesita para crear la publicación
- Descarga los artefactos `dist/`, `sbom/` y `man/`
- Crea la publicación de GitHub con las notas del registro de cambios
- Adjunta el wheel, el sdist, el SBOM (`*.cdx.json`, `*.spdx.json`), el VEX (`*.openvex.json`) y la página de manual

## Generación del registro de cambios

Los registros de cambios se generan automáticamente usando [git-cliff](https://git-cliff.org/) a partir de los conventional commits.

### Formato de commit

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Tipos soportados

| Tipo       | Sección del registro de cambios | Ejemplo                                  |
|------------|-------------------|------------------------------------------|
| `feat`     | Features          | `feat(cli): add --timeout flag`          |
| `fix`      | Bug Fixes         | `fix(tls): handle expired certificates`  |
| `perf`     | Performance       | `perf(dns): optimize resolver cache`     |
| `docs`     | Documentation     | `docs: update API reference`             |
| `refactor` | Refactor          | `refactor(core): extract analyzer logic` |
| `test`     | Testing           | `test: add integration tests`            |
| `chore`    | Miscellaneous     | `chore: update dependencies`             |

### Cambios incompatibles

Marca los cambios incompatibles en el footer del commit:

```
feat(api): redesign analyzer interface

BREAKING CHANGE: HTTPTapAnalyzer constructor signature changed
```

## Estrategia de versión

httptap sigue el [Versionado Semántico](https://semver.org/):

- **Versión mayor** (1.0.0) - Cambios incompatibles
- **Versión menor** (0.1.0) - Nuevas funcionalidades, compatible hacia atrás
- **Versión de parche** (0.0.1) - Correcciones de errores

### Desarrollo pre-1.0

Durante el desarrollo pre-1.0 (0.x.x):

- La versión menor puede incluir cambios incompatibles
- La versión de parche para correcciones de errores y funcionalidades menores
- Pasar a 1.0.0 cuando la API sea estable

## Resolución de problemas

### Errores de protección de ramas

Si el push falla debido a la protección de ramas:

1. Verifica que la clave de despliegue tenga acceso de escritura
2. Comprueba que la clave de despliegue esté en la lista de exención de las reglas de protección de ramas y del
   conjunto de reglas de etiquetas `refs/tags/v*`
3. Asegúrate de que `ssh-key` esté configurado en el checkout del flujo de trabajo
4. Comprueba que `DEPLOY_KEY` sea un secreto del entorno `release` y que el flujo de trabajo se haya ejecutado
   desde `main`, la única rama que admite el entorno

### Registro de cambios vacío

Si la generación del registro de cambios devuelve vacío:

1. Asegúrate de que los commits sigan el formato conventional
2. Comprueba la configuración de git-cliff en `.release/git-cliff.toml`
3. Verifica que la etiqueta no exista ya

### Falla la publicación en PyPI

Si la publicación en PyPI falla:

1. Verifica que exista el entorno `pypi`
2. Comprueba que Trusted Publishing esté configurado en PyPI
3. Asegúrate de que el flujo de trabajo tenga el permiso `id-token: write`

### Fallos de pruebas

Si las pruebas fallan durante la publicación:

1. El flujo de trabajo se detendrá antes de publicar
2. Corrige los problemas y vuelve a ejecutar el flujo de trabajo
3. No se producirán publicaciones parciales

## Post-publicación

Tras una publicación exitosa:

1. Verifica el paquete en PyPI: https://pypi.org/project/httptap/
2. Comprueba la publicación de GitHub: https://github.com/ozeranskii/httptap/releases
3. Prueba la instalación: `uv pip install httptap=={version}`
4. Anuncia la publicación (por ejemplo, GitHub Discussions, Telegram)

## Lista de verificación de publicación

Antes de activar la publicación:

- [ ] Todas las comprobaciones de CI pasando en main
- [ ] Sin errores críticos conocidos
- [ ] Documentación actualizada
- [ ] Cambios incompatibles documentados
- [ ] Guía de migración escrita (para versiones mayores)
- [ ] Dependencias actualizadas
- [ ] Vulnerabilidades de seguridad atendidas

## Véase también

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Versionado Semántico](https://semver.org/)
- [Documentación de git-cliff](https://git-cliff.org/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
