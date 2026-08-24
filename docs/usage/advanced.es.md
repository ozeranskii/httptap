---
description: Proxies, paquetes de CA personalizados, la API de Python y patrons de extensión para el uso avanzado de httptap.
---

# Funciones avanzadas

Esta guía cubre patrons de uso avanzado y opciones de personalización para httptap.

## Resolución DNS personalizada

Puedes proporcionar implementations personalizadas de resolutor DNS usando la API de Python. httptap siempre marca la dirección IP resuelta (IPv4/IPv6) conservando el nombre de host original para la cabecera `Host` y el SNI de TLS. Los literales IPv6 se ponen entre corchetes automáticamente, de modo que los resolutores personalizados solo necesitan devolver la tupla IP/familia correcta.

```python
from httptap import HTTPTapAnalyzer, SystemDNSResolver


class CustomDNSResolver(SystemDNSResolver):
    """Custom DNS resolver with hardcoded responses."""

    def resolve(self, host: str, port: int, timeout: float):
        # Override with custom logic
        if host == "httpbin.io":
            return "44.211.11.205", "IPv4", 0.1
        return super().resolve(host, port, timeout)


# Use custom resolver
analyzer = HTTPTapAnalyzer(dns_resolver=CustomDNSResolver())
steps = analyzer.analyze_url("https://httpbin.io")
```

## Inspección TLS personalizada

Implementa lógica de inspección TLS personalizada para extraer información adicional del certificado.

```python
from httptap import HTTPTapAnalyzer
from httptap.interfaces import TLSInspector
from httptap.models import NetworkInfo


class CustomTLSInspector:
    """Custom TLS inspector with extended certificate checks."""

    def inspect(self, host: str, port: int, timeout: float) -> NetworkInfo:
        # Custom TLS inspection logic
        # Return: NetworkInfo with TLS version, cipher, and certificate data
        ...


analyzer = HTTPTapAnalyzer(tls_inspector=CustomTLSInspector())
```

## Uso programático

Usa httptap como biblioteca de Python para integral en tus aplicaciones.

### Análisis básico

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

for step in steps:
    print(f"URL: {step.url}")
    print(f"Status: {step.response.status}")
    print(f"Total time: {step.timing.total_ms:.2f}ms")
```

### Con cabeceras personalizadas

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
headers = {"Authorization": "Bearer token123", "Accept": "application/json"}

steps = analyzer.analyze_url("https://httpbin.io/bearer", headers=headers)
```

### Seguir redirecciones

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer(follow_redirects=True)
steps = analyzer.analyze_url("https://httpbin.io/redirect/3")

print(f"Total steps in redirect chain: {len(steps)}")
```

### Enviar el cuerpo de la solicitud

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url(
    "https://httpbin.io/post",
    method=HTTPMethod.POST,
    content=b'{"key": "value"}',
    headers={"Content-Type": "application/json"},
)
```

## Ignorar la verificación TLS

Al resolver problemas en entornos de staging o en hosts con certificados autofirmados, puedes omitir la validación TLS:

```shell
httptap --ignore-ssl https://self-signed.badssl.com
```

La solicitud sigue registrando los metadatos de TLS, pero los errores de certificado se suprimen para que puedas centrarte en el flujo del protocolo. Usa este flag solo en entornos de confianza, porque desactiva la protección frente a ataques de intermediario (man-in-the-middle).
El cliente relaja muchos requisitos de cifrado y protocolo (hashes débiles,
versions de TLS más antiguas, grupos DH pequeños) para que sea más probable que los
endpoints heredados complement la negociación TLS. Los algorithms extremadamente
obsoletos que OpenSSL elimina por completo (por ejemplo, RC4, 3DES en algunas
plataformas) pueden fallar aun en este modo.

## Uso de proxies { #using-proxies }

Dirige las solicitudes a través de un proxy de salida (HTTP, HTTPS, SOCKS5/SOCKS5H):

```shell
httptap --proxy https://proxy.internal:8443 https://httpbin.io/get
```

```shell
httptap --proxy socks5h://proxy.internal:1080 https://httpbin.io/get
```

Ignore todas las variables de entorno de proxy y conecta directamente:

```shell
httptap --proxy "" https://httpbin.io/get
```

La salida Rich y la exportación JSON incluyen la URI del proxy y su origen
(por ejemplo, `(from arg --proxy)`, `(from env HTTPS_PROXY)`,
`(bypassed by env no_proxy)`) para que puedas confirmar qué ruta se usó.

### Protocols de proxy y resolución DNS

httptap admite cuatro protocols de proxy, cada uno con un comportamiento de resolución DNS distinto:

| Protocolo   | DNS resuelto por | Caso de uso |
|------------|----------------|----------|
| `socks5h://` | Servidor proxy | Privacidad, redes corporativas, acceso a DNS interno |
| `http://`    | Servidor proxy | Proxies HTTP estándar (método CONNECT) |
| `https://`   | Servidor proxy | Conexión cifrada al proxy |
| `socks5://`  | Cliente (local) | Cuando necesitas controlar la resolución DNS |

El sufijo `h` en `socks5h` significa "hostname" (una convención de curl). Con `socks5h://`, el nombre de host se envía al proxy, que lo resuelve. Con `socks5://`, el cliente resuelve el DNS localmente y envía la IP al proxy.

### Proxies por variables de entorno

Cuando no se proporciona el flag `--proxy`, httptap comprueba las variables de entorno:

1. `no_proxy` / `NO_PROXY` - Lista separada por comas de hosts a omitir (la minúscula tiene prioridad)
2. `https_proxy` / `HTTPS_PROXY` - Proxy para solicitudes HTTPS (la minúscula tiene prioridad)
3. `http_proxy` / `HTTP_PROXY` - Proxy para solicitudes HTTP (la minúscula tiene prioridad)
4. `all_proxy` / `ALL_PROXY` - Proxy alternativo para todos los protocols

El flag `--proxy` siempre tiene prioridad sobre las variables de entorno.

**Patrons de NO_PROXY:**

- `*` - Omite el proxy para todos los hosts
- `example.com` - Coincidencia exacta del nombre de host
- `.example.com` - Todos los subdominios de example.com
- `sub.example.com` - Coincidencia exacta de subdominio

## Paquetes de CA personalizados

Para endpoints internos firmados por una CA privada, proporciona un paquete PEM con `--cacert`:

```bash
httptap --cacert ~/certs/company-ca.pem https://internal-api.example.com/health
```

La salida de la CLI mostrará `TLS CA: custom bundle` para indicar que se usó el almacén de confianza ajeno al sistema. Las exportaciones JSON incluyen `network.tls_custom_ca: true` para que las herramientas posteriores puedan detectar la confianza personalizada. El flag es mutuamente excluyente con `--ignore-ssl`.

## Ejecutores de solicitud personalizados

Para un comportamiento totalmente personalizado puedes proporcionar tu propio ejecutor de solicitudes.
Los ejecutores reciben todos los parámetros empaquetados dentro de `RequestOptions`, de modo que los nuevos
flags añadidos por httptap siguen siendo retrocompatibles.

```python
from httptap import HTTPTapAnalyzer, RequestExecutor, RequestOptions, RequestOutcome


class RecordingExecutor(RequestExecutor):
    def __init__(self) -> None:
        self.last_options: RequestOptions | None = None

    def execute(self, options: RequestOptions) -> RequestOutcome:
        self.last_options = options
        # Call the built-in client (or your preferred HTTP library)
        from httptap.http_client import make_request

        timing, network, response = make_request(
            options.url,
            options.timeout,
            http2=options.http2,
            verify_ssl=options.verify_ssl,
            dns_resolver=options.dns_resolver,
            tls_inspector=options.tls_inspector,
            timing_collector=options.timing_collector,
            force_new_connection=options.force_new_connection,
            headers=options.headers,
        )
        return RequestOutcome(timing=timing, network=network, response=response)


executor = RecordingExecutor()
analyzer = HTTPTapAnalyzer(request_executor=executor)
analyzer.analyze_url("https://httpbin.io/get", headers={"X-Debug": "1"})
print(executor.last_options.headers)  # {'X-Debug': '1'}
```

## Visualización personalizada

Crea tu propia visualización implementando el protocolo `Visualizer`.

```python
from httptap.models import StepMetrics


class CustomVisualizer:
    """Custom visualizer for request steps."""

    def render(self, step: StepMetrics) -> None:
        print(f"Step {step.step_number}: {step.timing.total_ms}ms")


# Use custom visualizer
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

visualizer = CustomVisualizer()
for step in steps:
    visualizer.render(step)
```

## Formatos de exportación personalizados

Implementa formatos de exportación personalizados más allá de JSON.

```python
from collections.abc import Sequence
from httptap.models import StepMetrics
import csv


class CSVExporter:
    """Export request data to CSV format."""

    def export(self, steps: Sequence[StepMetrics], initial_url: str, output_path: str) -> None:
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url", "status", "dns_ms", "connect_ms", "tls_ms", "ttfb_ms", "total_ms"])

            for step in steps:
                writer.writerow(
                    [
                        step.url,
                        step.response.status,
                        step.timing.dns_ms,
                        step.timing.connect_ms,
                        step.timing.tls_ms,
                        step.timing.ttfb_ms,
                        step.timing.total_ms,
                    ]
                )


# Usage
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

exporter = CSVExporter()
exporter.export(steps, "https://httpbin.io", "output.csv")
```

## Monitorización del rendimiento

Usa httptap para la monitorización continua del rendimiento.

```python
import time
from httptap import HTTPTapAnalyzer


def monitor_endpoint(url: str, interval: int = 60):
    """Monitor endpoint every interval seconds."""
    analyzer = HTTPTapAnalyzer()

    while True:
        steps = analyzer.analyze_url(url)
        step = steps[0]

        # Log metrics
        print(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} - "
            f"TTFB: {step.timing.ttfb_ms:.2f}ms, "
            f"Total: {step.timing.total_ms:.2f}ms, "
            f"Status: {step.response.status}"
        )

        time.sleep(interval)


# Monitor API endpoint every minute
monitor_endpoint("https://httpbin.io/status/200", interval=60)
```

## Análisis por lotes

Analiza varias URL de forma concurrente.

```python
from concurrent.futures import ThreadPoolExecutor
from httptap import HTTPTapAnalyzer


def analyze_url(url: str):
    """Analyze a single URL."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url(url)
    return url, steps[0].timing.total_ms


# List of URLs to analyze
urls = ["https://httpbin.io", "https://httpbin.io/delay/1", "https://httpbin.io/gzip"]

# Analyze concurrently
with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(analyze_url, urls))

# Print results
for url, total_ms in results:
    print(f"{url}: {total_ms:.2f}ms")
```

## Manejo de errores

Maneja los errores con elegancia al analizar URL.

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io/status/500")

step = steps[0]
if step.has_error:
    print(f"Error: {step.error}")
else:
    print(f"Status: {step.response.status}")
```

## Integración con frameworks de pruebas

Usa httptap en tus suites de pruebas para verificar los requisitos de rendimiento.

```python
import pytest
from httptap import HTTPTapAnalyzer


def test_api_response_time():
    """Test that API responds within acceptable time."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url("https://httpbin.io/delay/0")

    # Assert TTFB is under 500ms
    assert steps[0].timing.ttfb_ms < 500, f"TTFB too high: {steps[0].timing.ttfb_ms}ms"

    # Assert total time is under 1 second
    assert steps[0].timing.total_ms < 1000, f"Total time too high: {steps[0].timing.total_ms}ms"


def test_tls_configuration():
    """Verify TLS configuration meets security standards."""
    analyzer = HTTPTapAnalyzer()
    steps = analyzer.analyze_url("https://httpbin.io")

    # Assert TLS 1.2 or higher
    assert steps[0].network.tls_version in ["TLSv1.2", "TLSv1.3"], (
        f"Insecure TLS version: {steps[0].network.tls_version}"
    )

    # Assert certificate is valid for at least 30 days
    assert steps[0].network.cert_days_left > 30, f"Certificate expiring soon: {steps[0].network.cert_days_left} days"
```

## Configuración específica por entorno

Configura httptap de forma diferente para distintos entornos.

```python
import os
from httptap import HTTPTapAnalyzer

# Environment-specific settings
config = {
    "production": {
        "timeout": 30,
        "follow_redirects": True,
    },
    "staging": {
        "timeout": 60,
        "follow_redirects": True,
    },
    "development": {
        "timeout": 120,
        "follow_redirects": False,
    },
}

env = os.getenv("ENVIRONMENT", "development")
settings = config[env]

analyzer = HTTPTapAnalyzer(
    timeout=settings["timeout"],
    follow_redirects=settings["follow_redirects"],
)
steps = analyzer.analyze_url("https://httpbin.io/status/200")
```

## Consejos de depuración

### Habilitar el registro detallado

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")
```

### Inspeccionar el tráfico HTTP en bruto

```python
from httptap import HTTPTapAnalyzer

analyzer = HTTPTapAnalyzer()
steps = analyzer.analyze_url("https://httpbin.io")

# Inspect response headers
step = steps[0]
print("Response headers:")
for key, value in step.response.headers.items():
    print(f"  {key}: {value}")
```

---

## ¿Qué sigue?

<div class="grid cards" markdown>

-   :material-api:{ .lg .middle } **[Referencia de la API](../api/overview.md)**

    ---

    Documentación detallada de la interfaz

-   :material-account-group:{ .lg .middle } **[Guía de contribución](../development/contributing.md)**

    ---

    Amplía httptap y contribute

-   :material-rocket-launch:{ .lg .middle } **[Proceso de publicación](../development/release.md)**

    ---

    Cómo funcionan las publicaciones

</div>
