<p align="center">
  <img src="docs/assets/httptap-banner.svg" alt="httptap" width="100%" />
</p>

<p align="center">
  <a href="https://trendshift.io/repositories/23438?utm_source=trendshift-badge&amp;utm_medium=badge&amp;utm_campaign=badge-trendshift-23438" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/trendshift/repositories/23438/daily?language=Python" alt="ozeranskii%2Fhttptap | Trendshift" width="250" height="55" /></a>
</p>

# httptap

<table>
  <tr>
    <th>Releases</th>
    <th>CI &amp; Quality</th>
    <th>Security</th>
    <th>Project Info</th>
  </tr>
  <tr>
    <td>
      <a href="https://pypi.org/project/httptap/">
        <img src="https://img.shields.io/pypi/v/httptap?color=3775A9&label=PyPI&logo=pypi" alt="PyPI" />
      </a><br />
      <a href="https://pypi.org/project/httptap/">
        <img src="https://img.shields.io/pypi/pyversions/httptap?logo=python" alt="Python Versions" />
      </a>
    </td>
    <td>
      <a href="https://github.com/ozeranskii/httptap/actions/workflows/ci.yml">
        <img src="https://github.com/ozeranskii/httptap/actions/workflows/ci.yml/badge.svg" alt="CI" />
      </a><br />
      <a href="https://codecov.io/github/ozeranskii/httptap">
        <img src="https://codecov.io/github/ozeranskii/httptap/graph/badge.svg?token=OFOHOI1X5J" alt="Coverage" />
      </a><br />
      <a href="https://codspeed.io/ozeranskii/httptap?utm_source=badge">
        <img src="https://img.shields.io/endpoint?url=https://codspeed.io/badge.json" alt="CodSpeed Badge" />
      </a>
    </td>
    <td>
      <a href="https://github.com/ozeranskii/httptap/actions/workflows/codeql.yml">
        <img src="https://github.com/ozeranskii/httptap/actions/workflows/codeql.yml/badge.svg" alt="CodeQL" />
      </a><br />
      <a href="https://scorecard.dev/viewer/?uri=github.com/ozeranskii/httptap">
        <img src="https://api.scorecard.dev/projects/github.com/ozeranskii/httptap/badge" alt="OpenSSF Scorecard" />
      </a><br />
      <a href="https://www.bestpractices.dev/projects/12474">
        <img src="https://www.bestpractices.dev/projects/12474/badge" alt="OpenSSF Best Practices" />
      </a><br />
      <a href="https://www.bestpractices.dev/projects/12474">
        <img src="https://www.bestpractices.dev/projects/12474/baseline" alt="OpenSSF Baseline" />
      </a>
    </td>
    <td>
      <a href="https://github.com/astral-sh/uv">
        <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="Build Tool" />
      </a><br />
      <a href="https://github.com/astral-sh/ruff">
        <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Lint" />
      </a><br />
      <a href="https://github.com/ozeranskii/httptap/blob/main/LICENSE">
        <img src="https://img.shields.io/github/license/ozeranskii/httptap?color=2E7D32" alt="License" />
      </a>
    </td>
  </tr>
</table>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-CN.md">简体中文</a> | <a href="README.ja.md">日本語</a> | <b>Español</b>
</p>

> **Nota:** Esta es una traducción de la comunidad y puede estar desactualizada respecto a la versión en inglés. Si hay discrepancias, prevalece el [README en inglés](README.md).

`httptap` es una CLI impulsada por Rich que descompone una solicitud HTTP en cada fase significativa —resolución DNS, conexión
TCP, negociación TLS, espera del servidor y transferencia del cuerpo— y presenta los resultados como una tabla de línea de
tiempo, un resumen compacto o métricas legibles por máquina. Está diseñada para la resolución de problemas interactiva, el
análisis de regresiones y el registro de líneas base de rendimiento.

---

## Índice

- [Puntos destacados](#puntos-destacados)
- [Comparativa](#comparativa)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
  - [Uso de Homebrew (macOS/Linux)](#uso-de-homebrew-macoslinux)
  - [Uso de `uvx` (recomendado)](#uso-de-uvx-recomendado)
  - [Uso de `uv`](#uso-de-uv)
  - [Uso de `pip`](#uso-de-pip)
  - [Imagen de contenedor](#imagen-de-contenedor)
  - [Desde el código fuente](#desde-el-código-fuente)
  - [Autocompletado del shell](#autocompletado-del-shell)
- [Inicio rápido](#inicio-rápido)
  - [Solicitud GET básica](#solicitud-get-básica)
  - [Solicitud POST con datos](#solicitud-post-con-datos)
  - [Otros métodos HTTP](#otros-métodos-http)
  - [Cabeceras personalizadas](#cabeceras-personalizadas)
  - [Redirecciones y exportación a JSON](#redirecciones-y-exportación-a-json)
  - [Modos de salida](#modos-de-salida)
  - [Uso avanzado](#uso-avanzado)
- [Comprobación de umbrales SLO](#comprobación-de-umbrales-slo)
- [Variables de entorno](#variables-de-entorno)
- [Códigos de salida](#códigos-de-salida)
- [Publicación de versiones](#publicación-de-versiones)
- [Salida de ejemplo](#salida-de-ejemplo)
- [Estructura de la exportación a JSON](#estructura-de-la-exportación-a-json)
- [Scripting solo con métricas](#scripting-solo-con-métricas)
- [Uso avanzado](#uso-avanzado-1)
- [Desarrollo](#desarrollo)
- [Contribuir](#contribuir)
- [Licencia](#licencia)
- [Agradecimientos](#agradecimientos)
- [Historial de estrellas](#historial-de-estrellas)

---

## Puntos destacados

- **Medición fase por fase** – mediciones precisas construidas a partir de los hooks de rastreo de httpcore (con
  alternativas razonables cuando los datos de bajo nivel no están disponibles).
- **Todos los métodos HTTP** – GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS con soporte para cuerpo de solicitud.
- **Soporte de cuerpo de solicitud** – envía JSON, XML o cualquier dato en línea o desde un archivo con detección
  automática de Content-Type.
- **Compatible con IPv4/IPv6** – el solucionador y el inspector TLS informan tanto la dirección como su familia.
- **Información TLS** – el CN del certificado, los SAN, el emisor, el número de serie, la ventana de validez y la cuenta
  regresiva de caducidad, además del conjunto de cifrado y la versión del protocolo, se capturan automáticamente desde la
  conexión en vivo (sin negociación TLS adicional).
- **Múltiples modos de salida** – vista de cascada enriquecida, resúmenes compactos de una sola línea o `--metrics-only`
  para scripting.
- **Exportación a JSON** – conserva los datos completos de cada paso (incluidas las cadenas de redirección) para su
  procesamiento posterior.
- **Comprobación de umbrales SLO** – `--slo total=500,ttfb=200` condiciona los trabajos de CI, las sondas cron y las
  comprobaciones de disponibilidad según presupuestos de latencia por fase; código de salida distinto de cero ante una
  violación, sin dejar de mostrar el informe completo.
- **Extensible** – interfaces Protocol limpias para DNS, TLS, medición, visualización y exportación que permiten
  incorporar comportamientos personalizados.

> 📣 <strong>Exclusivo para usuarios de httptap:</strong> Ahorra un 50 % en <a href="https://gitkraken.cello.so/vY8yybnplsZ"><strong>GitKraken Pro</strong></a>. Combina GitKraken Client, GitLens para VS Code y potentes herramientas de CLI para acelerar cada flujo de trabajo del repositorio.

---

## Comparativa

| Característica                            | `httptap` | `curl -w`              | [`httpstat`](https://github.com/reorx/httpstat) | `httpie`          |
|------------------------------------------|:---------:|:----------------------:|:-----------------------------------------------:|:-----------------:|
| Medición fase por fase (DNS/TCP/TLS/TTFB) | ✅        | ✅ (cadena de formato) | ✅                                              | ❌                |
| Visualización de cascada enriquecida     | ✅        | ❌                     | ⚠️ barras de texto                              | ❌                |
| Cadena de redirección con medición por paso | ✅     | ❌                     | ❌                                              | ❌                |
| Exportación a JSON (legible por máquina) | ✅        | ✅ (`-w '%{json}'`)    | ✅ (`--format json/jsonl`, esquema v1)          | ❌ (sin métricas) |
| Modo solo con métricas para scripting    | ✅        | ✅                     | ✅ (`--format json`)                            | ❌                |
| Comprobación de umbrales SLO             | ✅ (`--slo`) | ❌                  | ✅ (`--slo total=500,...`)                      | ❌                |
| Inspección de certificado TLS (CN, caducidad) | ✅   | ⚠️ mediante `-v`       | ❌                                              | ❌                |
| Informe de IPv4/IPv6                     | ✅ familia | ⚠️ IP mediante `remote_ip` | ⚠️ solo IP (`remote_ip`/`remote_port`)     | ❌                |
| Soporte de HTTP/2                        | ✅        | ✅                     | ⚠️ mediante paso a curl                         | ⚠️ solo con complemento |
| Proxy con atribución de origen           | ✅        | ⚠️ sin atribución      | ⚠️ mediante paso a curl                         | ⚠️ sin atribución |
| Paquete de CA personalizado              | ✅        | ✅                     | ⚠️ mediante paso a curl                         | ✅                |
| API de Python extensible                 | ✅        | ❌ (pycurl ≠ misma API) | ❌                                             | ⚠️ mediante requests |
| Flags compatibles con curl               | ✅        | —                      | ✅ (paso directo)                               | ❌                |
| Cero dependencias del sistema            | ✅        | ✅                      | necesita curl                                   | ✅                |

**Cuándo elegir cada uno:**
- **`httptap`** — resolución de problemas interactiva, análisis de regresiones y líneas base con scripts usando JSON estructurado.
- **`curl -w`** — comprobaciones puntuales en el shell donde curl ya es la dependencia.
- **`httpstat`** — desglose visual rápido sobre una instalación de curl existente.
- **`httpie`** — exploración de solicitud/respuesta de propósito general, no perfilado de latencia.

---

## Requisitos

- Python 3.10-3.15 (CPython)
- macOS, Linux o Windows (probado en CPython)
- Sin dependencias del sistema más allá de la red estándar
- El código debe seguir la Google Python Style Guide (docstrings, formato). Consulta
  [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

---

## Instalación

### Uso de Homebrew (macOS/Linux)

```shell
brew install httptap
```

### Uso de `uvx` (recomendado)

```shell
uvx --from "httptap[completion]" httptap https://example.com
```

### Uso de `uv`

```shell
uv pip install httptap
```

### Uso de `pip`

```shell
pip install httptap
```

### Imagen de contenedor

```shell
docker run --rm ghcr.io/ozeranskii/httptap:latest https://example.com
```

Multiarquitectura (linux/amd64, linux/arm64), firmado con cosign (Sigstore sin claves) y distribuido con procedencia de compilación SLSA.

### Desde el código fuente

```shell
git clone https://github.com/ozeranskii/httptap.git
cd httptap
uv venv
uv pip install .
```

---

### Autocompletado del shell

#### Instalación con Homebrew

Si instalaste httptap mediante Homebrew, el autocompletado del shell está disponible automáticamente tras la instalación. Solo reinicia tu shell:

```shell
# Restart your shell or reload configuration
exec $SHELL
```

Homebrew instala automáticamente el autocompletado en:
- Bash: `$(brew --prefix)/etc/bash_completion.d/`
- Zsh: `$(brew --prefix)/share/zsh/site-functions/`

#### Instalación mediante paquete de Python

Si instalaste httptap mediante `pip` o `uv`, necesitas instalar los extras opcionales de autocompletado:

1. Instala los extras de autocompletado:

   ```shell
   uv pip install "httptap[completion]"
   # or
   pip install "httptap[completion]"
   ```

2. Activa tu entorno virtual:

   ```shell
   source .venv/bin/activate
   ```

3. Ejecuta el script de activación global para el autocompletado de argumentos:

   ```shell
   activate-global-python-argcomplete
   ```

4. Reinicia tu shell. El autocompletado debería funcionar ahora tanto en bash como en zsh.

**Nota:** El script de activación global solo proporciona autocompletado de argumentos para bash y zsh. Otros shells no están cubiertos por el script y deben configurarse por separado.

#### Ejemplos de uso

Una vez instalado el autocompletado, puedes usar `Tab` para autocompletar comandos y opciones:

```shell
# Complete command options
httptap --<TAB>
# Shows: --method, --data, --follow, --timeout, --no-http2, --ignore-ssl, --cacert, --proxy, --header, --compact, --metrics-only, --json, --version, --help

# Complete after typing partial option
httptap --fol<TAB>
# Completes to: httptap --follow

# Complete multiple options
httptap --follow --time<TAB>
# Completes to: httptap --follow --timeout
```

---

## Inicio rápido

### Solicitud GET básica

Ejecuta una única solicitud y muestra una cascada enriquecida:

```shell
httptap https://httpbin.io/get
```

### Solicitud POST con datos

Envía datos JSON (detecta automáticamente el Content-Type):

```shell
httptap https://httpbin.io/post --data '{"name": "John", "email": "john@example.com"}'
```

**Nota:** Cuando se proporciona `--data` sin `--method`, httptap cambia automáticamente a POST (similar a curl).

**Flags compatibles con curl:** httptap acepta la sintaxis más común de curl, por lo que a menudo puedes reemplazar `curl` directamente por `httptap`. Los alias incluyen `-X/--request` para `--method`, `-L/--location` para `--follow`, `-m/--max-time` para `--timeout`, `-k/--insecure` para `--ignore-ssl`, `-x` para `--proxy` y `--http1.1` para `--no-http2`. (No todas las opciones de curl son compatibles: limítate a estos flags compartidos al intercambiar comandos.)

Carga datos desde un archivo:

```shell
httptap https://httpbin.io/post --data @payload.json
```

Especifica el método explícitamente (omite el auto-POST):

```shell
httptap https://httpbin.io/post --method POST --data '{"status": "active"}'
```

### Otros métodos HTTP

Solicitud PUT:

```shell
httptap https://httpbin.io/put --method PUT --data '{"key": "value"}'
```

Solicitud PATCH:

```shell
httptap https://httpbin.io/patch --method PATCH --data '{"field": "updated"}'
```

Solicitud DELETE:

```shell
httptap https://httpbin.io/delete --method DELETE
```

### Cabeceras personalizadas

Añade cabeceras personalizadas (repite `-H` para varios valores):

```shell
httptap \
  -H "Accept: application/json" \
  -H "Authorization: Bearer super-secret" \
  https://httpbin.io/bearer
```

### Redirecciones y exportación a JSON

Sigue las cadenas de redirección y vuelca las métricas a JSON:

```shell
httptap --follow --json out/report.json https://httpbin.io/redirect/2
```

### Modos de salida

Recopila mediciones compactas (de una sola línea) adecuadas para registros:

```shell
httptap --compact https://httpbin.io/get
```

Expón métricas en bruto para scripts:

```shell
httptap --metrics-only https://httpbin.io/get | tee timings.log
```

### Uso avanzado

Los usuarios que trabajan de forma programática pueden inyectar un ejecutor personalizado para escenarios avanzados. Proporciona tu propia implementación de `RequestExecutor` si necesitas cambiar la forma en que se ejecutan las solicitudes (por ejemplo, para incorporar una pila HTTP diferente o añadir rastreo).

#### Opciones de certificado TLS

Omite la verificación TLS al diagnosticar endpoints autofirmados:

```shell
httptap --ignore-ssl https://self-signed.badssl.com
```

El flag desactiva la validación del certificado y relaja muchas
restricciones de negociación para que los endpoints heredados
(caducados/autofirmados/con nombres de host no coincidentes, hashes
débiles, versiones de TLS antiguas) sigan completándose. Algunos
algoritmos eliminados de las compilaciones modernas de OpenSSL (por
ejemplo RC4 o 3DES) pueden seguir sin estar disponibles. Usa este modo
solo en redes de confianza.

Usa un paquete de certificados CA personalizado para APIs internas:

```shell
httptap --cacert /path/to/company-ca.pem https://internal-api.company.com
```

Esto resulta útil al probar servicios internos que usan certificados firmados por una Autoridad de Certificación (CA) personalizada que no está en el almacén de confianza predeterminado del sistema. La opción `--cacert` (también disponible como `--ca-bundle`) acepta una ruta a un paquete de certificados CA en formato PEM.

**Nota:** `--ignore-ssl` y `--cacert` son mutuamente excluyentes. Usa `--ignore-ssl` para desactivar toda la verificación, o `--cacert` para verificar con un paquete de CA personalizado.

Cuando se usa `--cacert`, la salida de la CLI marca la conexión con `TLS CA: custom bundle`, y las exportaciones a JSON incluyen `network.tls_custom_ca: true` para que la automatización pueda detectar una configuración de confianza personalizada.

Enruta el tráfico a través de un proxy HTTP/SOCKS (la anulación explícita tiene prioridad sobre las variables de entorno `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`):

```shell
httptap --proxy socks5h://proxy.local:1080 https://httpbin.io/get
```

Ignora todas las variables de entorno de proxy y conecta directamente:

```shell
httptap --proxy "" https://httpbin.io/get
```

La salida y la exportación a JSON incluyen el URI del proxy y su origen para que
puedas confirmar qué ruta se usó (p. ej., `(from arg --proxy)`,
`(from env HTTPS_PROXY)`, `(bypassed by env no_proxy)`).

---

## Comprobación de umbrales SLO

Condiciona los trabajos de CI, las sondas cron y las comprobaciones de
disponibilidad de Kubernetes según presupuestos de latencia por fase con
`--slo KEY=MS[,KEY=MS...]`:

```shell
httptap --slo total=500,ttfb=200 https://api.example.com/health
```

- Sale con `0` cuando todos los umbrales se cumplen.
- Sale con `4` cuando al menos un umbral se supera en el **último paso
  exitoso** (las redirecciones intermedias no se evalúan).
- Sale con `64` ante una especificación mal formada (clave desconocida,
  clave duplicada, valor no positivo, sintaxis incorrecta).
- La salida completa de cascada / compacta / JSON siempre se muestra para
  conservar la evidencia de una regresión.

Claves admitidas: `dns`, `connect`, `tls`, `ttfb`, `wait`, `xfer`, `total`.

Extensiones de la salida:

- **Rich / compacto** — un panel con bordes tras la cascada enumera los
  umbrales y cualquier violación (real, umbral, exceso).
- **`--metrics-only`** — el último paso exitoso lleva los tokens `slo=pass`
  o `slo=fail slo_violations=<keys>`.
- **`--json`** — el bloque `summary.slo` contiene `pass`,
  `thresholds_ms` y, por cada violación, `{key, threshold_ms, actual_ms, delta_ms}`.

```shell
# CI gate — fail only on SLO violation, tolerate transient network errors
httptap --slo total=2000,tls=300,ttfb=800 https://staging.example.com/
case $? in
  0) echo "healthy" ;;
  4) echo "SLO violation"; exit 1 ;;
  75) echo "network flake, retrying later" ;;
esac
```

Especificación completa, reglas de evaluación y recetas:
[docs.httptap.dev/usage/slo](https://docs.httptap.dev/usage/slo/).

---

## Variables de entorno

httptap lee las siguientes variables de entorno en tiempo de ejecución. Todas
ellas se pueden anular mediante flags de la CLI, y el origen real usado para
cada solicitud se registra en la salida y en la exportación a JSON.

| Variable                              | Propósito                                                                                                     | Anulada por           |
|---------------------------------------|--------------------------------------------------------------------------------------------------------------|-----------------------|
| `HTTP_PROXY` / `http_proxy`           | URL de proxy usada para destinos `http://`.                                                                  | `-x/--proxy`          |
| `HTTPS_PROXY` / `https_proxy`         | URL de proxy usada para destinos `https://`.                                                                 | `-x/--proxy`          |
| `ALL_PROXY` / `all_proxy`             | URL de proxy de reserva cuando las variables específicas de esquema no están definidas.                      | `-x/--proxy`          |
| `NO_PROXY` / `no_proxy`               | Lista de exclusión separada por comas (admite `*`, `.` inicial, coincidencias exactas). Las entradas omitidas conectan directamente. | `--proxy ""` |
| `NO_COLOR`                            | Desactiva los colores ANSI en toda la salida de Rich (respeta la convención [NO_COLOR](https://no-color.org)). | —                     |
| `FORCE_COLOR`                         | Fuerza la salida con color incluso cuando stdout no es un TTY (convención de Rich).                          | —                     |
| `TERM=dumb`                           | Rich reduce la representación a texto plano.                                                                  | —                     |

> Precedencia para la configuración del proxy: `-x/--proxy` explícito → `--proxy ""`
> (desactiva el entorno) → `HTTPS_PROXY`/`HTTP_PROXY`/`ALL_PROXY` (coincidencia de esquema) →
> exclusión `NO_PROXY` → conexión directa.

---

## Códigos de salida

httptap sigue la convención BSD `sysexits.h`, por lo que se integra limpiamente
con pipelines de shell, trabajos de CI y servicios de systemd.

| Código | Símbolo               | Significado                                                |
|:-----:|-------------------------|------------------------------------------------------------|
| `0`   | `EX_OK`                 | Éxito.                                                     |
| `4`   | —                       | Violación de umbral SLO (la solicitud tuvo éxito pero fue demasiado lenta). |
| `64`  | `EX_USAGE`              | Argumentos de línea de comandos no válidos.                |
| `70`  | `EX_SOFTWARE`           | Error interno (excepción inesperada, error de programa).   |
| `75`  | `EX_TEMPFAIL`           | Error de red / TLS (aún puede mostrarse salida parcial).   |
| `128 + N` | Desplazamiento de señal | Terminado por la señal `N` (p. ej., `130` para `SIGINT` / Ctrl-C). |

Ejemplo: hacer fallar un trabajo de CI solo ante errores de uso, tolerando
problemas de red transitorios:

```shell
httptap --metrics-only https://api.example.com/health
rc=$?
if [ "$rc" = 64 ] || [ "$rc" = 70 ]; then
  exit "$rc"
fi
```

---


## Publicación de versiones

### Requisitos previos

- El entorno de GitHub `pypi` debe estar configurado en los ajustes del repositorio
- Trusted Publishing de PyPI configurado para `ozeranskii/httptap`

### Pasos

1. Activa el flujo de trabajo **Release** desde GitHub Actions:
   - Proporciona la versión exacta (p. ej., `0.3.0`), O BIEN
   - Selecciona el tipo de incremento: `patch`, `minor` o `major`
2. El flujo de trabajo hará lo siguiente:
   - Actualizar la versión en `pyproject.toml` usando `uv version`
   - Generar el registro de cambios con `git-cliff` y actualizar `CHANGELOG.md`
   - Confirmar los cambios y crear una etiqueta de git
   - Ejecutar la suite de pruebas completa sobre la versión etiquetada
   - Compilar el wheel y la distribución de código fuente
   - Generar el SBOM en formatos CycloneDX y SPDX mediante Syft
   - Adjuntar el documento OpenVEX actual (`.vex/httptap.openvex.json`)
   - Publicar en PyPI mediante Trusted Publishing (OIDC)
   - Crear la GitHub Release con los activos de wheel, sdist, SBOM y VEX

---

## Salida de ejemplo

![sample-output.png](docs/assets/sample-output.png)

El resumen de redirección incluye una fila de total:
![sample-follow-redirects-output.png](docs/assets/sample-follow-redirects-output.png)

---

## Estructura de la exportación a JSON

```json
{
  "initial_url": "https://httpbin.io/redirect/2",
  "total_steps": 3,
  "steps": [
    {
      "url": "https://httpbin.io/redirect/2",
      "step_number": 1,
      "request": {
        "method": "GET",
        "headers": {},
        "body_bytes": 0
      },
      "timing": {
        "dns_ms": 8.947208058089018,
        "connect_ms": 96.97712492197752,
        "tls_ms": 194.56583401188254,
        "ttfb_ms": 445.9513339679688,
        "total_ms": 447.3437919514254,
        "wait_ms": 145.46116697601974,
        "xfer_ms": 1.392457983456552,
        "is_estimated": false
      },
      "network": {
        "ip": "44.211.11.205",
        "ip_family": "IPv4",
        "http_version": "HTTP/2.0",
        "tls_version": "TLSv1.2",
        "tls_cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "cert_cn": "httpbin.io",
        "cert_days_left": 143,
        "cert_sans": ["httpbin.io", "*.httpbin.io"],
        "cert_issuer": "WE1",
        "cert_serial": "05BB0F0AA84C8FECE0E72D805BA7A5D2B",
        "cert_not_before": "2025-04-01T00:00:00+00:00",
        "cert_not_after": "2025-09-01T00:00:00+00:00",
        "tls_verified": true,
        "tls_custom_ca": null,
        "proxy_url": null,
        "proxy_source": null
      },
      "response": {
        "status": 302,
        "bytes": 0,
        "content_type": null,
        "server": null,
        "date": "2025-10-23T19:20:36+00:00",
        "location": "/relative-redirect/1",
        "headers": {
          "access-control-allow-credentials": "true",
          "access-control-allow-origin": "*",
          "location": "/relative-redirect/1",
          "date": "Thu, 23 Oct 2025 19:20:36 GMT",
          "content-length": "0"
        }
      },
      "error": null,
      "note": null,
      "proxy": null
    },
    {
      "url": "https://httpbin.io/relative-redirect/1",
      "step_number": 2,
      "request": {
        "method": "GET",
        "headers": {},
        "body_bytes": 0
      },
      "timing": {
        "dns_ms": 2.6895420160144567,
        "connect_ms": 97.51500003039837,
        "tls_ms": 193.99016606621444,
        "ttfb_ms": 400.2034160075709,
        "total_ms": 400.60841606464237,
        "wait_ms": 106.00870789494365,
        "xfer_ms": 0.4050000570714474,
        "is_estimated": false
      },
      "network": {
        "ip": "44.211.11.205",
        "ip_family": "IPv4",
        "http_version": "HTTP/2.0",
        "tls_version": "TLSv1.2",
        "tls_cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "cert_cn": "httpbin.io",
        "cert_days_left": 143,
        "cert_sans": ["httpbin.io", "*.httpbin.io"],
        "cert_issuer": "WE1",
        "cert_serial": "05BB0F0AA84C8FECE0E72D805BA7A5D2B",
        "cert_not_before": "2025-04-01T00:00:00+00:00",
        "cert_not_after": "2025-09-01T00:00:00+00:00",
        "tls_verified": true,
        "tls_custom_ca": null,
        "proxy_url": null,
        "proxy_source": null
      },
      "response": {
        "status": 302,
        "bytes": 0,
        "content_type": null,
        "server": null,
        "date": "2025-10-23T19:20:36+00:00",
        "location": "/get",
        "headers": {
          "access-control-allow-credentials": "true",
          "access-control-allow-origin": "*",
          "location": "/get",
          "date": "Thu, 23 Oct 2025 19:20:36 GMT",
          "content-length": "0"
        }
      },
      "error": null,
      "note": null,
      "proxy": null
    },
    {
      "url": "https://httpbin.io/get",
      "step_number": 3,
      "request": {
        "method": "GET",
        "headers": {},
        "body_bytes": 0
      },
      "timing": {
        "dns_ms": 2.643457963131368,
        "connect_ms": 97.36416593659669,
        "tls_ms": 197.3062080796808,
        "ttfb_ms": 403.2038329169154,
        "total_ms": 403.9644579170272,
        "wait_ms": 105.89000093750656,
        "xfer_ms": 0.7606250001117587,
        "is_estimated": false
      },
      "network": {
        "ip": "52.70.33.41",
        "ip_family": "IPv4",
        "http_version": "HTTP/2.0",
        "tls_version": "TLSv1.2",
        "tls_cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "cert_cn": "httpbin.io",
        "cert_days_left": 143,
        "cert_sans": ["httpbin.io", "*.httpbin.io"],
        "cert_issuer": "WE1",
        "cert_serial": "05BB0F0AA84C8FECE0E72D805BA7A5D2B",
        "cert_not_before": "2025-04-01T00:00:00+00:00",
        "cert_not_after": "2025-09-01T00:00:00+00:00",
        "tls_verified": true,
        "tls_custom_ca": null,
        "proxy_url": null,
        "proxy_source": null
      },
      "response": {
        "status": 200,
        "bytes": 389,
        "content_type": "application/json; charset=utf-8",
        "server": null,
        "date": "2025-10-23T19:20:37+00:00",
        "location": null,
        "headers": {
          "access-control-allow-credentials": "true",
          "access-control-allow-origin": "*",
          "content-type": "application/json; charset=utf-8",
          "date": "Thu, 23 Oct 2025 19:20:37 GMT",
          "content-length": "389"
        }
      },
      "error": null,
      "note": null,
      "proxy": null
    }
  ],
  "summary": {
    "total_time_ms": 1251.916665933095,
    "final_status": 200,
    "final_url": "https://httpbin.io/get",
    "final_bytes": 389,
    "errors": 0
  }
}
```

## Scripting solo con métricas

```shell
httptap --metrics-only https://httpbin.io/get
```

```terminaloutput
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

---

## Uso avanzado

### Implementaciones personalizadas

Sustituye por tu propio solucionador o inspector TLS (cualquier cosa que satisfaga el Protocol de `httptap.interfaces`):

```python
from httptap import HTTPTapAnalyzer, SystemDNSResolver


class HardcodedDNS(SystemDNSResolver):
    def resolve(self, host, port, timeout):
        return "93.184.216.34", "IPv4", 0.1


analyzer = HTTPTapAnalyzer(dns_resolver=HardcodedDNS())
steps = analyzer.analyze_url("https://httpbin.io")
```

---

## Desarrollo

```shell
git clone https://github.com/ozeranskii/httptap.git
cd httptap
uv sync
uv run pytest
uv run ruff check
uv run ruff format .
```

Las pruebas esperan acceso de red saliente; puedes simular `SystemDNSResolver` / `SocketTLSInspector` al ejecutar sin conexión.

---

## Contribuir

1. Haz un fork y clona el repositorio.
2. Crea una rama de funcionalidad.
3. Ejecuta `pytest` y `ruff` antes de confirmar.
4. Envía un pull request con una descripción clara y cualquier captura de pantalla o benchmark relevante.

Damos la bienvenida a informes de errores, propuestas de funcionalidades, mejoras en la documentación y nuevas visualizaciones o exportadores creativos.

---

## Licencia

Apache License 2.0 © Sergei Ozeranskii. Consulta [LICENSE](https://github.com/ozeranskii/httptap/blob/main/LICENSE) para más
detalles.

---

## Agradecimientos

- Construido sobre los hombros de bibliotecas fantásticas: [httpx](https://www.python-httpx.org/), [httpcore](https://github.com/encode/httpcore),
  [dnspython](https://www.dnspython.org/) y [Rich](https://github.com/Textualize/rich).
- Inspirado en el ecosistema de herramientas en torno al rendimiento web (p. ej., las cascadas de DevTools, `curl --trace`).
- Un agradecimiento especial a todos los que abren issues, comparten ideas o contribuyen con parches.

---

## Historial de estrellas

<a href="https://www.star-history.com/?repos=ozeranskii%2Fhttptap&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=ozeranskii/httptap&type=date&theme=dark&legend=top-left&sealed_token=l9nG3PE0bX5aj34TLoeySlfh-_SB3q51PgWOaU2CmnMGqBBvE8afuR1znzOdI0Vffj7Eh07VC1QPIOro5aeWb1B8BVdWOtnFhVcsJ22WFSfZkZWNx0v74LF--vP-rnm_WSMwooWGpUCQK24Anw5-qoqR2ItPauLxdsBhDZwLKJMEX0J46yaHWtJ-D1jc" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=ozeranskii/httptap&type=date&legend=top-left&sealed_token=l9nG3PE0bX5aj34TLoeySlfh-_SB3q51PgWOaU2CmnMGqBBvE8afuR1znzOdI0Vffj7Eh07VC1QPIOro5aeWb1B8BVdWOtnFhVcsJ22WFSfZkZWNx0v74LF--vP-rnm_WSMwooWGpUCQK24Anw5-qoqR2ItPauLxdsBhDZwLKJMEX0J46yaHWtJ-D1jc" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=ozeranskii/httptap&type=date&legend=top-left&sealed_token=l9nG3PE0bX5aj34TLoeySlfh-_SB3q51PgWOaU2CmnMGqBBvE8afuR1znzOdI0Vffj7Eh07VC1QPIOro5aeWb1B8BVdWOtnFhVcsJ22WFSfZkZWNx0v74LF--vP-rnm_WSMwooWGpUCQK24Anw5-qoqR2ItPauLxdsBhDZwLKJMEX0J46yaHWtJ-D1jc" />
 </picture>
</a>
