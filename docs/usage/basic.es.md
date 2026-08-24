---
description: Ejecuta httptap desde la línea de commandos y lee el desglose de tiempos por fase de cualquier solicitud HTTP.
---

# Uso básico

## Interfaz de línea de commandos

La interfaz de línea de commandos de `httptap` ofrece varias opciones para personalizar tus solicitudes HTTP y la salida.

## Sintaxis

```bash
httptap [OPTIONS] URL
```

## Opciones

> **Compatibilidad con curl:** Los flags habituales de curl se aceptan como alias. Cambia `curl` por `httptap` y sigue usando opciones familiares como `-X/--request`, `-L/--location`, `-m/--max-time`, `-k/--insecure`, `-x` y `--http1.1`. Esto no es un clon completo de curl: limítate a los flags coincidentes que se enumeran aquí.

### Opciones de solicitud

#### `-X, --request, --method METHOD`

Especifica el método HTTP que se usará. Métodos admitidos: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS.

*Alias compatibles con curl:* `-X`, `--request`.

```bash
httptap --method POST https://httpbin.io/post
```

**Comportamiento por defecto:**
- Sin `--data`: usa GET por defecto
- Con `--data` pero sin `--method`: cambia automáticamente a POST (similar a curl)
- Con `--method` explícito: respeta el método especificado

#### `-d, --data DATA`

Envía datos en el cuerpo de la solicitud. Puede set una cadena en línea o una referencia a un archivo usando la sintaxis `@filename`.

**Datos JSON en línea:**
```bash
httptap --data '{"name": "John", "email": "john@example.com"}' https://httpbin.io/post
```

**Cargar desde un archivo:**
```bash
httptap --data @payload.json https://httpbin.io/post
```

**Detección automática:**
- El Content-Type se detecta automáticamente (JSON, XML, texto plano)
- Primero se comprueba la extensión del archivo (.json, .xml, .txt)
- Recurre a la validación JSON

**Ejemplos con distintos métodos:**
```bash
# POST (detectado automáticamente cuando --data está presente)
httptap --data '{"key": "value"}' https://httpbin.io/post

# PUT
httptap --method PUT --data '{"status": "updated"}' https://httpbin.io/put

# PATCH
httptap --method PATCH --data '{"field": "modified"}' https://httpbin.io/patch

# GET explícito con cuerpo (poco común, genera una advertencia)
httptap --method GET --data 'query-data' https://httpbin.io/get
```

#### `-H, --header`

Añade cabeceras HTTP personalizadas a la solicitud. Puede usarse varias veces.

```bash
httptap -H "Accept: application/json" https://httpbin.io
```

```bash
httptap \
  -H "User-Agent: MyApp/1.0" \
  -H "Authorization: Bearer token123" \
  https://httpbin.io/bearer
```

#### `-L, --location, --follow`

Sigue las redirecciones HTTP y muestra la temporización de cada paso de la cadena (máximo 10 redirecciones).

*Alias compatibles con curl:* `-L`, `--location`.

```bash
httptap --follow https://httpbin.io/redirect/3
```

Por defecto, httptap no sigue las redirecciones y se detiene en la primera respuesta de redirección (código de estado 3xx).

#### `-m, --max-time, --timeout SECONDS`

Aborta la cadena de solicitudes si el tiempo total transcurrido supera el número de segundos especificado.

*Alias compatibles con curl:* `-m`, `--max-time`.

```bash
httptap --timeout 10 https://httpbin.io/delay/2
```

El tiempo de espera por defecto es de 20 segundos.

#### `--no-http2` / `--http1.1`

Desactiva la negociación de HTTP/2 y fuerza conexiones HTTP/1.1.

```bash
httptap --no-http2 https://httpbin.io
```

Por defecto, HTTP/2 está activado si el servidor lo admite.

*Alias compatible con curl:* `--http1.1`.

#### `-k, --insecure, --ignore-ssl`

Desactiva la verificación del certificado TLS. Útil para depurar hosts autofirmados o certificados caducados.

```bash
httptap --ignore-ssl https://self-signed.badssl.com
```

!!! warning
    Usa esta opción solo en redes de confianza. Desactiva la validación de certificados y relaja las restricciones de la negociación TLS.

*Alias compatibles con curl:* `-k`, `--insecure`.

#### `-x, --proxy URL`

Enruta las solicitudes a través del proxy especificado. Admite los protocols HTTP, HTTPS, SOCKS5 y SOCKS5H.

*Alias compatible con curl:* `-x`.

```bash
# proxy HTTP
httptap --proxy http://proxy.local:8080 https://httpbin.io/get

# proxy SOCKS5 (DNS resuelto por el proxy)
httptap --proxy socks5h://proxy.local:1080 https://httpbin.io/get

# proxy SOCKS5 (DNS resuelto localmente)
httptap --proxy socks5://proxy.local:1080 https://httpbin.io/get

# Ignore las variables de entorno de proxy y conecta directamente
httptap --proxy "" https://httpbin.io/get
```

El flag `--proxy` tiene prioridad sobre las variables de entorno (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`). Usa `--proxy ""` para ignorar todas las variables de entorno de proxy y conectar directamente. Consulta [Funciones avanzadas](advanced.md#using-proxies) para más detalles sobre los protocols de proxy, la resolución DNS y la configuración mediante variables de entorno.

#### `--cacert, --ca-bundle PATH`

Usa un paquete de certificados CA personalizado (formato PEM) para la verificación TLS. Útil para endpoints internos firmados por una CA privada.

```bash
httptap --cacert ~/certs/company-ca.pem https://internal-api.example.com/health
```

Mutuamente excluyente con `--ignore-ssl`.

### Opciones de salida

#### `--compact`

Muestra los resultados en un formato compacto de una sola línea, adecuado para el registro (logging).

```bash
httptap --compact https://httpbin.io/get
```

Salida:

```
Step 1: 200 GET https://httpbin.io/get | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 389 B
```

`--compact` imprime una línea legible por humanos por cada paso (adecuada para
registros y para el rastreo de cadenas de redirecciones) sin dejar de renderizar la cabecera
de análisis y la tabla `Redirect Chain Summary`. El tamaño de la respuesta se muestra
con la unidad apropiada (`B`, `KB`, `MB`). Para una salida procesable por máquinas,
consulta `--metrics-only`.

#### `--metrics-only`

Genera métricas en bruto sin formato, ideal para scripting y automatización.

```bash
httptap --metrics-only https://httpbin.io
```

Salida:

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

#### `--json PATH`

Exporta todos los datos de la solicitud a un archivo JSON.

```bash
httptap --json report.json https://httpbin.io
```

El archivo JSON contiene:

- Desglose de tiempos de todas las fases
- Información de red (dirección IP, detalles de TLS, información del certificado)
- Metadatos de la respuesta (estado, cabeceras, tamaño del cuerpo)
- Cadena completa de redirecciones (al usar `--follow`)
- Evaluación de SLO (cuando se proporciona `--slo`)

#### `--slo KEY=MS[,KEY=MS...]`

Comprueba el paso final correcto frente a presupuestos de latencia por fase. Ante una
violación, `httptap` sigue renderizando el inform completo pero sale con el código
`4` para que el resultado pueda condicionar trabajos de CI, sondas de cron o comprobaciones
de disponibilidad (readiness) de Kubernetes.

```bash
httptap --slo total=500,ttfb=200 https://httpbin.io/get
```

Claves admitidas: `dns`, `connect`, `tls`, `ttfb`, `wait`, `xfer`,
`total`. Consulta la página dedicada [Comprobación de umbrales SLO](slo.md) para
la especificación completa, la precedencia de códigos de salida y recetas de CI/cron.

#### `--version`

Muestra la versión de httptap y sale.

```bash
httptap --version
```

## Métodos HTTP

httptap admite todos los métodos HTTP estándar:

- **GET** - Recupera un recurso (por defecto cuando no se proporciona `--data`)
- **POST** - Crea/envía un recurso (seleccionado automáticamente cuando se proporciona `--data`)
- **PUT** - Reemplaza un recurso
- **PATCH** - Actualiza parcialmente un recurso
- **DELETE** - Elimina un recurso
- **HEAD** - Obtiene solo las cabeceras
- **OPTIONS** - Consulta los métodos permitidos

### Lógica de selección de método

1. **Método explícito:** `--method` siempre tiene prioridad
2. **Auto-POST:** Cuando `--data` está presente sin `--method`, usa POST por defecto
3. **GET por defecto:** Sin `--data` ni `--method`, usa GET

### Ejemplos por caso de uso

**Pruebas de API:**
```bash
# Crear recurso
httptap --data '{"title": "New Post"}' https://httpbin.io/post

# Actualizar recurso
httptap --method PUT --data '{"title": "Updated"}' https://httpbin.io/put

# Actualización parcial
httptap --method PATCH --data '{"status": "published"}' https://httpbin.io/patch

# Eliminar recurso
httptap --method DELETE https://httpbin.io/delete
```

**Comprobaciones de estado:**
```bash
# Comprobación rápida (solo cabeceras)
httptap --method HEAD https://httpbin.io/status/200

# Respuesta completa
httptap https://httpbin.io/status/200
```

## Flujo de la solicitud

Cada solicitud de httptap sigue estas fases:

1. **Resolución DNS** - Búsqueda del nombre de dominio
2. **Conexión TCP** - Establecer la conexión TCP
3. **Negociación TLS** - Negociar la conexión segura (solo HTTPS)
4. **Espera del servidor** - Tiempo entre el envío de la solicitud y el primer byte de la respuesta
5. **Transferencia del cuerpo** - Descargar el cuerpo de la respuesta

## Entender la salida

### Modo Rich (por defecto)

La salida rich por defecto muestra una tabla de cascada con:

- Nombre de la fase y duración
- Barra de progreso visual
- Detalles de red (IP, versión de TLS, información del certificado)
- Metadatos de la respuesta (estado, tamaño, content-type)

### Desglose de tiempos

- **DNS (ms)** - Tiempo para resolver el dominio a una dirección IP
- **Connect (ms)** - Tiempo para establecer la conexión TCP
- **TLS (ms)** - Tiempo de la negociación TLS (solo HTTPS)
- **TTFB (ms)** - Tiempo hasta el primer byte (incluye el procesamiento del servidor)
- **Transfer (ms)** - Tiempo para descargar el cuerpo de la respuesta
- **Total (ms)** - Duración de la solicitud de extremo a extremo

### Información de red

- **Dirección IP** - Dirección IP resuelta y familia (IPv4/IPv6)
- **Versión de TLS** - Versión del protocolo (TLS 1.2, TLS 1.3)
- **Conjunto de cifrado** - Conjunto de cifrado negociado
- **CN del certificado** - Common Name del certificado del servidor
- **Caducidad del certificado** - Días hasta que caduca el certificado

## Ejemplos

### Comprobación de estado básica

```bash
httptap https://httpbin.io/status/200
```

### Solicitud de API con autenticación

```bash
httptap \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Accept: application/json" \
  https://httpbin.io/bearer
```

### Seguir la cadena de redirecciones

```bash
httptap --follow https://httpbin.io/redirect/3
```

### Exportar para análisis

```bash
httptap --json analysis.json --follow https://httpbin.io/redirect/2
```

### Registrar en un archivo

```bash
httptap --metrics-only https://httpbin.io/delay/1 >> api-latency.log
```

---

## ¿Qué sigue?

<div class="grid cards" markdown>

-   :material-palette:{ .lg .middle } **[Formatos de salida](output-formats.md)**

    ---

    Modos rich, compact, JSON y metrics

-   :material-cog:{ .lg .middle } **[Funciones avanzadas](advanced.md)**

    ---

    Componentes personalizados y uso programático

-   :material-api:{ .lg .middle } **[Referencia de la API](../api/overview.md)**

    ---

    Amplía httptap con protocols

</div>
