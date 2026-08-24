---
description: El proceso de publicación automatizado con GitHub Actions para httptap, además de los pasos de publicación manuals.
---

# Proceso de publicación

Este documento describe el proceso de publicación automatizado para httptap.

## Visión general

Las publicaciones están totalmente automatizadas usando GitHub Actions. El flujo de trabajo gestiona el versionado, la generación del registro de cambios, las pruebas,
la compilación, la firma, la publicación en TestPyPI y PyPI, y el envío de una
imagen de contenedor firmada a GHCR.

## Requisitos previous

Antes de crear una publicación, asegúrate de:

1. **GitHub Environments** - Entornos `release`, `testpypi` y `pypi` configurados en la configuración del repositorio
2. **PyPI Trusted Publishing** - Configurado tanto para PyPI como para TestPyPI (OIDC, sin tokens)
3. **Deploy Key** - Clave de despliegue SSH con acceso de escritura (para eludir la protección de ramas)
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

4. **Commit y etiqueta firmados**
   ```bash
   git commit -S -m "chore: release v0.2.0"
   git tag -s v0.2.0 -m "Release v0.2.0"
   git push origin HEAD
   git push origin v0.2.0
   ```
   Firma sin claves de Sigstore mediante [gitsign](https://github.com/sigstore/gitsign):
   se emite un certificado Fulcio de corta duración a través de la identidad OIDC
   del flujo de trabajo, de modo que no se requieren claves GPG de larga duración.

5. **Compilación**
   ```bash
   uv sync --locked --group test
   uv run pytest  # Full test suite
   uv build  # Create wheel and sdist
   ```

6. **Publicación en TestPyPI**
    - Sube primero a TestPyPI mediante OIDC Trusted Publishing, con atestaciones
      PEP 740, como prueba de humo antes del envío de producción.

7. **Publicación en PyPI**
    - Usa OIDC Trusted Publishing (no se requieren tokens)
    - Sube el wheel y la distribución de código fuente con atestaciones PEP 740

8. **Publicación de la imagen de contenedor en GHCR**
    - Compila una imagen multiarquitectura (linux/amd64, linux/arm64)
    - Envía a `ghcr.io/ozeranskii/httptap` con las etiquetas `{version}`, `{major}.{minor}`,
      `{major}` y `latest`
    - Firma la imagen con cosign (Sigstore sin claves)
    - Adjunta procedencia de compilación SLSA mediante `actions/attest-build-provenance`

9. **GitHub Release**
    - Crea la publicación con notas generadas
    - Adjunta los artefactos de compilación, los SBOM, el VEX y la página de manual

## Configuración del flujo de trabajo

El flujo de trabajo de publicación está definido en `.github/workflows/release.yml`:

### Jobs clave

#### 1. Preparar la publicación

- Extrae el código con la clave de despliegue
- Configura Python y uv
- Actualiza la versión en pyproject.toml
- Genera el registro de cambios
- Have commit y push de los cambios
- Crea y envía la etiqueta de git

#### 2. Compilar el paquete

- Extrae la versión etiquetada
- Ejecuta el conjunto de pruebas completo
- Compila el wheel y el sdist
- Genera el SBOM en formatos JSON CycloneDX y SPDX mediante [Syft](https://github.com/anchore/syft)
- Copia el documento OpenVEX versionado desde `.vex/httptap.openvex.json` al directorio `sbom/` como `httptap-X.Y.Z.openvex.json`
- Genera una página `man(1)` comprimida con gzip usando [argparse-manpage](https://github.com/praiskup/argparse-manpage)
- Sube los artefactos `dist/`, `sbom/` y `man/` por separado

#### 3. Publicar en TestPyPI

- Descarga los artefactos `dist/`
- Publica mediante TestPyPI OIDC Trusted Publishing con atestaciones PEP 740

#### 4. Publicar en PyPI

- Se ejecuta solo después de que TestPyPI tenga éxito
- Publica usando Trusted Publishing con atestaciones PEP 740

#### 5. Publicar la imagen de contenedor en GHCR

- Compila una imagen multiarquitectura con Buildx + QEMU
- Firma con cosign (Sigstore OIDC sin claves)
- Adjunta procedencia de compilación SLSA

#### 6. Crear la GitHub Release

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

## Pasos de publicación manuals

Si necesitas publicar manualmente (no recomendado):

### 1. Actualizar la versión

```bash
uv version 0.2.0
```

### 2. Regenerar el lockfile

```bash
uv lock
```

### 3. Generar el registro de cambios

```bash
git cliff --tag v0.2.0 --unreleased --prepend CHANGELOG.md
```

### 4. Hacer commit de los cambios

```bash
git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "chore: release v0.2.0"
```

### 5. Crear la etiqueta

```bash
git tag -a v0.2.0 -m "Release v0.2.0"
```

### 6. Hacer push

```bash
git push origin main
git push origin v0.2.0
```

### 7. Compilar y publicar

```bash
uv build
uv publish  # Requires PyPI credentials
```

### 8. Crear la GitHub Release

Usa la CLI de `gh` o la interfaz web para crear la publicación con las notas del registro de cambios.

## Resolución de problemas

### Errores de protección de ramas

Si el push falla debido a la protección de ramas:

1. Verifica que la clave de despliegue tenga acceso de escritura
2. Comprueba que la clave de despliegue esté en la lista de exención de las reglas de protección de ramas
3. Asegúrate de que `ssh-key` esté configurado en el checkout del flujo de trabajo

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
- [ ] Guía de migración escrita (para versions mayores)
- [ ] Dependencies actualizadas
- [ ] Vulnerabilidades de seguridad atendidas

## Véase también

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Versionado Semántico](https://semver.org/)
- [Documentación de git-cliff](https://git-cliff.org/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
