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
- **Metadatos de la respuesta** que muestran estado, tamaño del cuerpo, la cabecera `Server` y el destino de la redirección

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
- **Valores escapados** con codificación porcentual cuando es necesario, de modo que cada métrica
  siga siendo un único token `key=value`.

### Cuándo usarlo

- Scripting y automatización
- Recopilación de datos para análisis
- Integración con herramientas de monitorización
- Análisis con awk/grep/sed

### Combinado con `--compact`

`--metrics-only` tiene prioridad sobre `--compact`. Si se pasan ambas opciones,
se sigue emitiendo la línea legible por máquina `key=value` (los scripts existentes
siguen funcionando) y se muestra en stderr un aviso de que `--compact` se ha ignorado.

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

Pasa `-` como ruta para escribir el JSON en stdout (se suprime el informe
habitual); los mensajes de estado van a stderr:

```bash
httptap --json - https://httpbin.io | jq '.steps[0].timing'
```

### Estructura JSON

```json
{
  "schema_version": 1,
  "httptap_version": "0.6.3",
  "timestamp": "2026-09-18T08:00:00Z",
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
        "cert_days_left": 41,
        "cert_sans": ["httpbin.io", "*.httpbin.io"],
        "cert_issuer": "WE1",
        "cert_serial": "05BB0F0AA84C8FECE0E72D805BA7A5D2B",
        "cert_not_before": "2026-08-01T00:00:00+00:00",
        "cert_not_after": "2026-10-30T00:00:00+00:00",
        "tls_verified": true,
        "tls_custom_ca": false,
        "proxy_url": null,
        "proxy_source": null
      },
      "response": {
        "status": 200,
        "bytes": 389,
        "content_type": "application/json",
        "server": "gunicorn/19.9.0",
        "date": "2026-09-18T07:59:59+00:00",
        "location": null,
        "headers": {
          "date": "Fri, 18 Sep 2026 07:59:59 GMT",
          "content-type": "application/json",
          "server": "gunicorn/19.9.0"
        }
      },
      "error": null,
      "note": null,
      "redirect_limit_reached": false,
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

### Referencia de campos

Los metadatos de nivel superior identifican el formato del informe y cuándo se generó.
Los consumidores deben usar `schema_version` para seleccionar una lógica de análisis compatible.

| Campo             | Tipo    | Descripción                                                                                    |
| ----------------- | ------- | ---------------------------------------------------------------------------------------------- |
| `schema_version`  | integer | Versión del formato del informe JSON. La versión actual es `1`.                                |
| `httptap_version` | string  | Versión de httptap que generó el informe.                                                      |
| `timestamp`       | string  | Hora de creación de la exportación en formato RFC 3339 UTC, por ejemplo `2026-09-18T08:00:00Z`. |
| `initial_url`     | string  | URL pasada a httptap antes de las redirecciones.                                               |
| `total_steps`     | integer | Número de entradas en `steps`.                                                                 |
| `steps`           | array   | Mediciones por solicitud, incluida cada redirección seguida.                                   |
| `summary`         | object  | Valores agregados de la exportación.                                                           |

Los valores de temporización que terminan en `_ms` están en milisegundos. Los tamaños de los cuerpos
de solicitud y respuesta están en bytes. Los tamaños de respuesta (`bytes`, `final_bytes`) cuentan el
cuerpo tal como se recibe por la red, antes de decodificar `Content-Encoding`, como `size_download` de
curl. Las fechas del certificado y de la respuesta son marcas de tiempo ISO 8601/RFC 3339 cuando
están disponibles. Consulta el ejemplo anterior para ver la estructura anidada de `steps` y `summary`.

Las credenciales se enmascaran: la contraseña (o un token suelto) de la parte userinfo de las `url` de los pasos,
`response.location`, las cabeceras `Location` y `Content-Location`, y `network.proxy_url` se sustituye por `****`, y
las cabeceras sensibles como `Authorization` y `Set-Cookie` también se enmascaran.

`network.tls_custom_ca` es `true` cuando se usó `--cacert` y `false` en caso contrario. El campo
`redirect_limit_reached` de un paso es `true` cuando `--follow` se detuvo en el límite de 10
redirecciones en ese paso; ese paso también cuenta en `summary.errors`.

Un paso con `error` conserva la respuesta que ya había recibido: si la línea de
estado y las cabeceras llegaron antes del fallo (por ejemplo, el cuerpo se
detuvo más allá de `-m/--max-time`), se rellenan `response.status`,
`response.headers` y `response.bytes` (los bytes del cuerpo recibidos hasta
ese momento). Un paso que falló antes de la línea de estado tiene
`response.status: null`. El código de salida sigue siendo el de error de red (`75`).

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

## Exportación HAR { #har-export }

`--har PATH` escribe la cadena de solicitudes analizada como un documento
[HTTP Archive (HAR) 1.2](http://www.softwareishard.com/blog/har-12-spec/), el
formato que leen las DevTools de los navegadores y los visores de HAR. Pasa `-`
para escribirlo en stdout (se suprime el informe habitual); los mensajes de
estado van a stderr:

```bash
httptap --follow --har run.har https://httpbin.io/redirect/2
httptap --har - https://httpbin.io/get | jq '.log.entries[].timings'
```

`--har` y `--json` se pueden combinar, pero solo uno de ellos puede escribir en
stdout. Si no se puede escribir el archivo, httptap sale con el código `73`,
igual que con `--json`.

Para abrir el archivo en Chrome DevTools, abre el panel **Network** y usa
**Import HAR file** (la flecha de subida de la barra de herramientas), o
arrastra el archivo al panel. Firefox DevTools ofrece **Import HAR** en el menú
de ajustes del panel Network.

### Estructura HAR

Un ejemplo recortado para una única solicitud HTTPS:

```json
{
  "log": {
    "version": "1.2",
    "creator": { "name": "httptap", "version": "0.7.0" },
    "pages": [
      {
        "startedDateTime": "2026-10-06T08:00:00.000+00:00",
        "id": "page_1",
        "title": "https://httpbin.io/get",
        "pageTimings": { "onContentLoad": -1, "onLoad": -1 }
      }
    ],
    "entries": [
      {
        "pageref": "page_1",
        "startedDateTime": "2026-10-06T08:00:00.000+00:00",
        "time": 448.2,
        "request": {
          "method": "GET",
          "url": "https://httpbin.io/get",
          "httpVersion": "HTTP/2.0",
          "cookies": [],
          "headers": [],
          "queryString": [],
          "headersSize": -1,
          "bodySize": 0
        },
        "response": {
          "status": 200,
          "statusText": "OK",
          "httpVersion": "HTTP/2.0",
          "cookies": [],
          "headers": [{ "name": "content-type", "value": "application/json; charset=utf-8" }],
          "content": { "size": 389, "mimeType": "application/json; charset=utf-8" },
          "redirectURL": "",
          "headersSize": -1,
          "bodySize": 389,
          "_transferSize": 389
        },
        "cache": {},
        "timings": {
          "blocked": -1,
          "dns": 8.9,
          "connect": 291.6,
          "send": 0,
          "wait": 146.4,
          "receive": 1.3,
          "ssl": 194.6
        },
        "serverIPAddress": "44.211.11.205",
        "_tls": {
          "version": "TLSv1.2",
          "cipher": "ECDHE-RSA-AES128-GCM-SHA256",
          "certCN": "httpbin.io",
          "certIssuer": "Amazon RSA 2048 M03",
          "certDaysLeft": 200,
          "verified": true
        }
      }
    ]
  }
}
```

El documento contiene:

- **Una página** para la ejecución. Su `title` es la URL pasada a httptap; los
  tiempos de carga de página no aplican y valen `-1`.
- **Una entrada por solicitud**, en el orden de la cadena de redirecciones, cada
  una enlazada a la página mediante `pageref`. httptap mide duraciones, no
  horas de inicio reales, así que las entradas se colocan una tras otra y la
  última termina cuando se escribe el archivo.
- **Solicitud**: método, URL, versión HTTP negociada, las cabeceras que recibió
  httptap (`-H` y el `Content-Type` derivado de `--data`), la query string
  analizada y `bodySize`. El cuerpo de la solicitud nunca se escribe.
- **Respuesta**: estado, versión HTTP, cabeceras, `redirectURL` (la cabecera
  `Location`), `content.mimeType` (el `Content-Type`, o `x-unknown` si falta) y
  el tamaño del cuerpo. httptap no decodifica el cuerpo, así que
  `content.size` y `bodySize` son el tamaño recibido por la red, antes de
  decodificar `Content-Encoding`. El texto del cuerpo nunca se incluye.
- **`serverIPAddress`**: la dirección a la que se conectó httptap.

`statusText` es la frase estándar del código de estado (vacía para códigos
desconocidos) y `headersSize` vale `-1`: httptap no registra la frase ni el
tamaño de las cabeceras enviadas por la red. Los arrays `cookies` están vacíos; `Cookie` y `Set-Cookie` aparecen,
enmascaradas, en las cabeceras.

### Tiempos

| Campo HAR  | Valor de httptap       | Notas                                                                    |
| ---------- | ---------------------- | ------------------------------------------------------------------------ |
| `blocked`  | `-1`                   | No se mide.                                                              |
| `dns`      | `dns_ms`               |                                                                          |
| `connect`  | `connect_ms + tls_ms`  | Incluye el handshake TLS, como exige la especificación HAR.              |
| `ssl`      | `tls_ms`               | Solo HTTPS, `-1` para HTTP sin cifrar. Ya forma parte de `connect`.      |
| `send`     | `0`                    | No se mide por separado; el envío de la solicitud forma parte de `wait`. |
| `wait`     | `wait_ms`              | Procesamiento del servidor, hasta el primer byte de la respuesta.        |
| `receive`  | `xfer_ms`              | Transferencia del cuerpo.                                                |

`time` es la suma de `blocked`, `dns`, `connect`, `send`, `wait` y `receive`,
omitiendo los valores `-1`. `ssl` no se vuelve a sumar porque `connect` ya lo
contiene. Los valores son milisegundos redondeados a tres decimales. Cuando las
fases de conexión y TLS se estimaron en lugar de medirse (`is_estimated` en la
exportación JSON), `timings` incluye `"_estimated": true`.

### Solicitudes fallidas

Un paso que falló también se exporta. Su `response.status` es `0`, o el estado
que ya había llegado (por ejemplo, cuando el cuerpo se detuvo más allá de
`-m/--max-time`), y el mensaje de error está en `response._error`, donde Chrome
DevTools lo lee al importar un HAR. Como un paso fallido no tiene fases
medidas, sus `dns`, `connect` y `ssl` valen `-1`, `send`, `wait` y `receive`
valen `0`, y `time` es `0`.

### Campos personalizados

La especificación HAR reserva los campos que empiezan por `_` para extensiones.
httptap añade:

| Campo                    | Ubicación  | Contenido                                                                              |
| ------------------------ | ---------- | -------------------------------------------------------------------------------------- |
| `_tls`                   | entrada    | `version`, `cipher`, `certCN`, `certIssuer`, `certDaysLeft`, `verified`; solo HTTPS.   |
| `_proxy`                 | entrada    | `url` (credenciales enmascaradas) y `source` del proxy por el que pasó la solicitud.  |
| `_redirectLimitReached`  | entrada    | `true` cuando `--follow` se detuvo en el límite de 10 redirecciones en este paso.      |
| `_estimated`             | `timings`  | `true` cuando los tiempos de conexión y TLS se estimaron.                              |
| `_transferSize`          | `response` | Bytes del cuerpo recibidos por la red, `-1` si no llegó respuesta.                     |
| `_error`, `_errorKind`   | `response` | Mensaje de error y su tipo (`network` o `internal`) de un paso fallido.                |

### Redacción de credenciales

La exportación HAR aplica el mismo enmascaramiento que la exportación JSON: la
contraseña (o un token suelto) en el userinfo de una URL se sustituye por
`****` en las URL de las solicitudes, el título de la página, `redirectURL`,
las cabeceras `Location` y `Content-Location` y la URL del proxy, y las
cabeceras sensibles como `Authorization`, `Cookie` y `Set-Cookie` se
enmascaran.

!!! warning
    Las rutas y las query strings se conservan, y los archivos HAR suelen
    adjuntarse a informes de errores. Revisa un archivo HAR en busca de datos
    sensibles antes de compartirlo.

## Exportación textfile de Prometheus { #prometheus-textfile-export }

Escribe un informe para el textfile collector de node_exporter con `--prometheus PATH`:

```bash
httptap --prometheus /var/lib/node_exporter/httptap.prom https://api.example.com/health
```

El archivo se escribe de forma atómica. Cada muestra lleva una etiqueta `host` (solo el nombre
de host) y el `step` de la cadena de redirecciones, de modo que varias sondas pueden compartir un
mismo directorio de textfiles. Gauges exportados:

| Métrica                                 | Etiquetas extra | Significado                                                |
| --------------------------------------- | --------------- | ---------------------------------------------------------- |
| `httptap_request_success`               |                 | `1` si el paso se completó, `0` ante un error de red/TLS   |
| `httptap_request_duration_seconds`      | `phase`         | `dns`, `connect`, `tls`, `ttfb`, `wait`, `xfer`, `total`   |
| `httptap_response_status_code`          |                 | Estado HTTP del paso                                       |
| `httptap_response_body_size_bytes`      |                 | Tamaño del cuerpo de la respuesta en la red                |
| `httptap_last_run_timestamp_seconds`    |                 | Hora Unix en que se escribió el archivo (solo `host`)      |

Los pasos fallidos exportan solo `httptap_request_success 0`, de modo que una caída nunca parece
una respuesta rápida. Las rutas y las query strings nunca se usan como etiquetas.

## Exportación de OpenTelemetry { #opentelemetry-export }

`--otlp ENDPOINT` envía trazas OTLP/HTTP. Instala primero el extra opcional:

```bash
pip install 'httptap[otel]'
httptap --otlp http://localhost:4318/v1/traces https://api.example.com/health
```

Una ejecución se exporta como una única traza: un span raíz `httptap.analysis` con un span
`http.request` por cada paso de redirección, dispuestos uno tras otro, y spans hijos para las
fases de DNS, conexión, TLS, espera del servidor y transferencia. La entrega está acotada por
`-m`/`--max-time`; un error del collector se informa como advertencia y no cambia el código de
salida. La exportación omite la URL completa de la solicitud, de modo que los parámetros de
consulta no se envían al collector.

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

Una violación hace que `httptap` salga con el código `4` sin dejar de renderizar
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
