---
description: Elige entre los modos de salida rich, compact, metrics-only y JSON para adaptarte a la depuración o la automatización.
---

# Formatos de salida

httptap admite múltiples formatos de salida para adaptarse a distintos casos de uso, desde la resolución interactiva de problemas hasta el
scripting automatizado.

## Modo Rich (por defecto)

El formato de salida por defecto usa la biblioteca [Rich](https://github.com/Textualize/rich) para mostrar una preciosa tabla de cascada
en tu terminal.

```bash
httptap https://httpbin.io
```

### Características

- **Salida coloreada** con resaltado de sintaxis
- **Barras de progreso visuals** para las fases de temporización
- **Tablas estructuradas** para una lectura sencilla
- **Detalles de red** incluyendo IP, versión de TLS e información del certificado
- **Metadatos de la respuesta** que muestran estado, cabeceras y tamaño del cuerpo

### Cuándo usarlo

- Sesiones de depuración interactivas
- Inspección visual del rendimiento de las solicitudes
- Presentación de datos de temporización a las partes interesadas

## Modo Compact

Una línea legible por humanos por cada paso, diseñada para registros de terminal y
el rastreo de cadenas de redirecciones.

```bash
httptap --compact https://httpbin.io/get
```

### Ejemplo de salida

```
Step 1: 200 GET https://httpbin.io/get | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 389 B
```

### Características

- **Una sola línea por paso** — primero el estado HTTP, luego el método y la URL, luego
  los tiempos por fase, y por último el tamaño del cuerpo legible por humanos.
- **Los tiempos llevan el sufijo `ms`** para que se lean con naturalidad junto a las
  entradas de registro en prosa.
- **El tamaño de la respuesta** se formatea con la unidad apropiada (`B`, `KB`, `MB`).
- **La tabla resumen de redirecciones** se sigue imprimiendo tras las líneas por paso
  para que la forma general de la cadena permanezca visible.

### Cuándo usarlo

- Añadir a archivos de registro
- Comparaciones rápidas de rendimiento
- Salida de pipelines de CI/CD donde aún quieres ver la URL y el estado
- Resúmenes amigables para la terminal cuando la cascada completa resulta demasiado ruidosa

## Modo Metrics-Only

Métricas en bruto sin formato, optimizadas para su análisis por otras herramientas.

```bash
httptap --metrics-only https://httpbin.io
```

### Ejemplo de salida

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

### Características

- Formato **procesable por máquinas**
- **Métricas completas** incluyendo detalles de red
- **Estructura consistente** para una extracción sencilla
- **Sin colores ni characters de formato**

### Cuándo usarlo

- Scripting y automatización
- Recopilación de datos para análisis
- Integración con herramientas de monitorización
- Análisis con awk/grep/sed

### Ejemplos de análisis

```bash
# Extraer los valores de TTFB
httptap --metrics-only https://httpbin.io/delay/1 | grep -oP 'ttfb=\K[0-9.]+'

# Obtener todas las métricas de temporización
httptap --metrics-only https://httpbin.io/get | \
  awk '{for(i=1;i<=NF;i++){if($i ~ /=/) print $i}}'
```

## Exportación JSON

Todos los datos de la solicitud exportados como JSON estructurado para un análisis completo.

```bash
httptap --json output.json https://httpbin.io
```

### Estructura JSON

```json
{
  "initial_url": "https://httpbin.io",
  "total_steps": 1,
  "steps": [
    {
      "url": "https://httpbin.io",
      "step_number": 1,
      "request": {
        "method": "GET",
        "headers": {},
        "body_bytes": 0
      },
      "timing": {
        "dns_ms": 8.947,
        "connect_ms": 96.977,
        "tls_ms": 194.566,
        "ttfb_ms": 445.951,
        "total_ms": 447.344,
        "wait_ms": 145.461,
        "xfer_ms": 1.392,
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
        "status": 200,
        "bytes": 389,
        "content_type": "application/json",
        "server": null,
        "date": "2025-10-23T19:20:36+00:00",
        "location": null,
        "headers": {
          "date": "Thu, 23 Oct 2025 19:20:36 GMT",
          "content-type": "application/json",
          "server": "gunicorn/19.9.0"
        }
      },
      "error": null,
      "note": null,
      "proxy": null
    }
  ],
  "summary": {
    "total_time_ms": 447.344,
    "final_status": 200,
    "final_url": "https://httpbin.io",
    "final_bytes": 389,
    "errors": 0
  }
}
```

### Características

- **Exportación completa de datos** de todas las fases
- **Formato estructurado** para un análisis sencillo
- **Compatibilidad con cadenas de redirecciones** con múltiples pasos
- **Conservación de metadatos** (cabeceras, marcas de tiempo)
- **Información de errores** cuando las solicitudes fallan

### Cuándo usarlo

- Análisis de posprocesamiento
- Integración con pipelines de datos
- Seguimiento del rendimiento a largo plazo
- Sesiones de depuración detalladas
- Compartir resultados con los miembros del equipo

### Ejemplos de procesamiento

Usando `jq` para extraer campos específicos:

```bash
# Obtener el tiempo total
jq '.summary.total_time_ms' output.json

# Extraer todos los valores de TTFB
jq '.steps[].timing.ttfb_ms' output.json

# Obtener la caducidad del certificado
jq '.steps[0].network.cert_days_left' output.json

# Filtrar las solicitudes fallidas
jq 'select(.summary.errors > 0)' output.json
```

## Cadenas de redirecciones

Al usar `--follow`, todos los formatos de salida incluyen datos de cada paso de la cadena de redirecciones.

### Modo Rich

Muestra una tabla resumen con los totales de toda la cadena.

```bash
httptap --follow https://httpbin.io/redirect/3
```

### Modo Compact

Genera una línea por cada paso de redirección, seguida de la tabla resumen
de la cadena de redirecciones.

```bash
httptap --follow --compact https://httpbin.io/redirect/2
```

Salida:

```
Step 1: 302 GET https://httpbin.io/redirect/2 | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 0 B
Step 2: 302 GET https://httpbin.io/relative-redirect/1 | dns=2.7ms connect=97.5ms tls=194.0ms ttfb=400.2ms total=400.6ms | 0 B
Step 3: 200 GET https://httpbin.io/get | dns=2.6ms connect=97.4ms tls=197.3ms ttfb=403.2ms total=404.0ms | 389 B
```

### Exportación JSON

Incluye todos los pasos en el array `steps` con temporización y metadatos completos.

```bash
httptap --follow --json redirect-chain.json https://httpbin.io/redirect/3
```

## Combinar opciones

Las opciones de formato de salida pueden combinarse con otros flags:

```bash
# Seguir redirecciones con salida compact
httptap --follow --compact https://httpbin.io/redirect/2

# Exportar la cadena de redirecciones a JSON con visualización de métricas
httptap --follow --json chain.json --metrics-only https://bit.ly/example
```

!!! note
    Cuando se usan juntos `--json` y los modos de visualización (`--compact`, `--metrics-only`), el modo de visualización se muestra en stdout mientras que el JSON se escribe en el archivo.

---

## Superposición de umbrales SLO

`--slo KEY=MS[,KEY=MS...]` amplía cada modo de salida con un veredicto de
aprobado/fallido evaluado frente a la solicitud final correcta.

- **Modo Rich** — se imprime un panel enmarcado después de la cascada.
  El borde es verde para aprobado, rojo para fallido, y cada violación se
  enumera con el valor real, el umbral y el exceso en milisegundos.
- **Modo Compact** — se comporta como el modo Rich anterior; el panel SLO
  se sigue imprimiendo tras los resúmenes de paso de una línea.
- **Metrics-only** — la línea del paso final correcto obtiene los tokens
  `slo=pass` o `slo=fail slo_violations=<keys>`. Los pasos de redirección
  intermedios permanecen sin cambios.
- **JSON** — `summary.slo` contiene `pass`, `thresholds_ms` y
  `violations[]` (cada uno con `key`, `threshold_ms`, `actual_ms`,
  `delta_ms`). Ausente cuando no se proporciona `--slo`.

Una violación have que `httptap` salga con el código `4` sin dejar de renderizar
la salida completa, de modo que la evidencia se conserva para el análisis posterior.

Consulta la página dedicada [Comprobación de umbrales SLO](slo.md) para la
gramática de especificación, las reglas de evaluación, la precedencia de códigos de salida y
recetas de CI/cron.

---

## ¿Qué sigue?

<div class="grid cards" markdown>

-   :material-cog:{ .lg .middle } **[Funciones avanzadas](advanced.md)**

    ---

    Componentes personalizados, monitorización, análisis por lotes

-   :material-api:{ .lg .middle } **[Referencia de la API](../api/overview.md)**

    ---

    Uso programático y extensions

</div>
