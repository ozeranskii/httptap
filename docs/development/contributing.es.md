---
description: Cómo configurar un entorno de desarrollo y contribuir con código, pruebas y documentación a httptap.
---

# Contribuir

¡Damos la bienvenida a las contribuciones a httptap! Esta guía te ayudará a empezar.

## Código de conducta

Ten en cuenta que este proyecto sigue
el [Código de conducta del Contributor Covenant](https://github.com/ozeranskii/httptap/blob/main/CODE_OF_CONDUCT.md). Al
participar, se espera que respetes este código.

## Primeros pasos

### Requisitos previous

- Python 3.10 o superior (CPython)
- El gestor de paquetes [uv](https://github.com/astral-sh/uv)
- Git

### Configurar el entorno de desarrollo

1. **Haz un fork y clona el repositorio:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/httptap.git
   cd httptap
   ```

2. **Instala las dependencies:**

   ```bash
   uv sync
   ```

3. **Verifica la instalación:**

   ```bash
   uv run httptap --version
   ```

## Flujo de trabajo de desarrollo

### Ejecutar pruebas

Ejecuta el conjunto de pruebas completo:

```bash
uv run pytest
```

Ejecuta con cobertura:

```bash
uv run pytest --cov --cov-report=html
```

Visualiza el inform de cobertura:

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Calidad del código

#### Linting

Ejecuta el linter Ruff:

```bash
uv run ruff check
```

Corrige problemas automáticamente:

```bash
uv run ruff check --fix
```

#### Formateo

Comprueba el formateo:

```bash
uv run ruff format --check
```

Formatea el código automáticamente:

```bash
uv run ruff format .
```

#### Comprobación de tipos

Ejecuta mypy:

```bash
uv run mypy httptap
```

### Ejecutar benchmarks

Los benchmarks de rendimiento usan [pytest-codspeed](https://codspeed.io) y se ejecutan automáticamente en CI:

```bash
# Ejecuta los benchmarks localmente (valida la corrección, sin datos de rendimiento)
uv run pytest tests/test_benchmarks.py --codspeed

# Mide el tiempo real localmente, con una tabla de resultados
uv run pytest tests/test_benchmarks.py --codspeed --codspeed-mode=walltime

# Ejecuta los benchmarks sin CodSpeed (como pruebas normals)
uv run pytest tests/test_benchmarks.py
```

Los benchmarks cubren funciones de cómputo puro a través de los módulos de modelos, formateadores, utilidades y exportadores. CI mide instrucciones de CPU (`simulation`) y asignaciones de memoria (`memory`).

Usa `--codspeed-mode=walltime` para comprobar una optimización localmente sin esperar a CI; toma aproximadamente dos segundos por benchmark. Los números de tiempo real son inherentemente ruidosos en hardware compartido, así que CI se basa en `simulation` en su lugar: trata los resultados locales de walltime como una señal directional, no como el valor que reportará CI.

### Ejecutar localmente

Prueba tus cambios:

```bash
uv run httptap https://httpbin.io
```

O instala en modo editable:

```bash
uv pip install -e .
httptap https://httpbin.io
```

## Realizar cambios

### Nomenclatura de ramas

Usa nombres de rama descriptions:

- `feature/add-http2-support` - Nuevas funcionalidades
- `fix/tls-timeout-issue` - Correcciones de errores
- `docs/update-api-reference` - Documentación
- `refactor/extract-parser` - Refactorización de código

### Mensajes de commit

Sigue el formato de conventional commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Tipos:**

- `feat` - Nueva funcionalidad
- `fix` - Corrección de error
- `docs` - Cambios en la documentación
- `refactor` - Refactorización de código
- `test` - Añadir/actualizar pruebas
- `chore` - Tareas de mantenimiento
- `perf` - Mejoras de rendimiento

**Ejemplos:**

```
feat(cli): add --timeout flag for request timeout

Add command-line option to specify custom timeout for HTTP requests.
Defaults to 20 seconds if not specified.

Closes #123
```

```
fix(tls): handle certificate expiry edge case

Fix crash when certificate expiry date is in the past.
Now properly reports negative days and warns user.

Fixes #456
```

### Estilo de código

Sigue la [Guía de estilo de Python de Google](https://google.github.io/styleguide/pyguide.html):

- Usa anotaciones de tipos para todas las firmas de funciones
- Escribe docstrings para todas las API públicas
- Mantén las líneas por debajo de 120 characters
- Usa comillas doubles para las cadenas
- Sigue las convenciones de nomenclatura de PEP 8

**Ejemplo:**

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

### Directrices de pruebas

- Escribe pruebas para todas las funcionalidades nuevas
- Mantén o mejora la cobertura de código
- Usa nombres de prueba descriptions
- Simula las dependencies externas (DNS, TLS, HTTP)
- Prueba tanto los casos de éxito como los de fallo

**Ejemplo:**

```python
def test_analyzer_follows_redirects(mock_http_client):
    """Test that analyzer follows redirect chains correctly."""
    analyzer = HTTPTapAnalyzer(follow_redirects=True)
    steps = analyzer.analyze_url("https://httpbin.io/redirect/3")

    assert len(steps) == 4  # Initial + 3 redirects
    assert steps[-1].response.status == 200
```

## Proceso de pull request

1. **Crea una rama de funcionalidad:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Realiza tus cambios y haz commit:**

   ```bash
   git add .
   git commit -m "feat: add awesome feature"
   ```

3. **Haz push a tu fork:**

   ```bash
   git push origin feature/your-feature-name
   ```

4. **Crea un Pull Request:**

    - Ve al [repositorio de httptap](https://github.com/ozeranskii/httptap)
    - Haz clic en "New Pull Request"
    - Selecciona tu rama
    - Rellena la plantilla de PR

### Lista de verificación de PR

Antes de enviar, asegúrate de que:

- [ ] Las pruebas pasan (`uv run pytest`)
- [ ] El código está formateado (`uv run ruff format .`)
- [ ] El linter pasa (`uv run ruff check`)
- [ ] Las comprobaciones de tipos pasan (`uv run mypy httptap`)
- [ ] La documentación está actualizada (si es necesario)
- [ ] CHANGELOG.md está actualizado (para cambios significativos)
- [ ] Los mensajes de commit siguen el formato conventional

## Documentación

### Actualizar la documentación

La documentación está en el directorio `docs/`:

```
docs/
├── getting-started/
├── usage/
├── api/
├── development/
└── about/
```

Construye la documentación localmente:

```bash
uv sync --group docs
uv run mkdocs serve
```

Visualízala en: http://127.0.0.1:8000

### Estándares de documentación

- Usa un lenguaje claro y conciso
- Incluye ejemplos de código
- Mantén los ejemplos realistas y prácticos
- Usa un formateo Markdown apropiado
- Prueba todos los ejemplos de código

## Áreas para contribuir

### Buenas primeras incidencias

Busca incidencias etiquetadas como [`good first issue`](https://github.com/ozeranskii/httptap/labels/good%20first%20issue): estas
son aptas para principiantes.

### Se busca ayuda

Las incidencias etiquetadas como [`help wanted`](https://github.com/ozeranskii/httptap/labels/help%20wanted) son prioridades en las que nos encantaría
recibir ayuda.

### Ideas para contribuciones

- **Soporte de HTTP/3** - Extender a la versión más reciente del protocolo
- **Más formatos de exportación** - CSV, XML, métricas de Prometheus
- **Visualizaciones adicionales** - Flamegraphs, gráficos
- **Optimizaciones de rendimiento** - DNS más rápido, agrupación de conexiones
- **Más detalles de TLS** - OCSP, análisis de la cadena de certificados
- **Reporters personalizados** - Notificaciones de Slack, webhook
- **Protocols adicionales** - Tiempos de WebSocket, gRPC

## Obtener ayuda

- **GitHub Issues** - Reporters de errores y solicitudes de funcionalidades
- **Discussions** - Preguntas y discusión general
- **Discord** - Chat en tiempo real (próximamente)

## Reconocimiento

Los colaboradores son reconocidos en:

- [CHANGELOG.md](https://github.com/ozeranskii/httptap/blob/main/CHANGELOG.md)
- La página de colaboradores de GitHub
- Las notas de publicación

¡Gracias por contribuir a httptap! 🎉
