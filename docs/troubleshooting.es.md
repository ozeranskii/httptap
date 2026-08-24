---
title: Resolución de problemas y preguntas frecuentes
description: Problemas comunes, mensajes de error y diagnósticos al ejecutar httptap.
---

# Resolución de problemas y preguntas frecuentes

Esta página recopila las preguntas y errores más comunes que encuentran los usuarios al ejecutar
`httptap`. Si tu problema no aparece en la lista,
[abre una incidencia](https://github.com/ozeranskii/httptap/issues) con el commando exacto,
la exportación JSON (si la hay) y la salida de terminal relevant.

## TLS y certificados

### `TLS handshake failed: CERTIFICATE_VERIFY_FAILED`

El servidor presentó un certificado que tu almacén de confianza no reconoce.

- **Certificado autofirmado o caducado en un host que no es de producción** — añade `--ignore-ssl`
  (desactiva la validación, úsalo solo en redes de confianza).
- **CA interna** — apunta `--cacert` (alias `--ca-bundle`) a tu paquete PEM.
- **Almacén de confianza del sistema desactualizado** — actualiza `ca-certificates` en Linux, o
  refresca `certifi` en tu entorno de Python (`uv pip install --upgrade certifi`).

La exportación JSON muestra `network.tls_verified: false` y, cuando se usa `--cacert`,
`network.tls_custom_ca: true`.

### El certificado muestra `cert_days_left: null` o un valor negativo

`cert_days_left` se analiza a partir del campo `notAfter` del certificado de hoja. Un
valor `null` significa que el certificado no se pudo obtener/analizar — normalmente TLS
se abortó antes de recibir un certificado, o se usó `--ignore-ssl` (con la
verificación desactivada, el certificado del par no se expone como un diccionario
analizado, por lo que `cert_cn`/`cert_days_left` y los demás campos `cert_*` permanecen
en `null` mientras que `tls_version`/`tls_cipher` se siguen informando). Un valor **negativo**
significa que el certificado ya ha caducado.

### `--ignore-ssl` sigue fallando con `DH_KEY_TOO_SMALL` / `WRONG_VERSION_NUMBER`

Las compilaciones modernas de OpenSSL descartan algunos cifrados y parámetros DH por seguridad.
`--ignore-ssl` relaja la verificación y las restricciones de protocolo, pero no puede recuperar
los conjuntos de cifrado (RC4, 3DES, DH débil) que se eliminaron del binario.
Soluciones alternativas: usa un curl más antiguo, un proxy que determine TLS o recompila OpenSSL.

## Proxies

### `--proxy` se ignore

La opción explícita `-x/--proxy` siempre prevalece sobre las variables de entorno. Comprueba:

1. Que no pasaste una cadena vacía por error — `--proxy ""` **desactiva explícitamente**
   los proxies basados en el entorno y fuerza la conexión directa.
2. Que el esquema coincide con el destino — `HTTPS_PROXY` se usa para URLs `https://`,
   `HTTP_PROXY` para `http://`.
3. Que el host de destino no coincide con `NO_PROXY`. Comprueba el campo `proxy_source`
   en la exportación JSON; si indica `NO_PROXY`, tu host está excluido.

### Referencia de patrons de `NO_PROXY`

- Host exacto: `api.internal.example`
- Sufijo de dominio: `.internal.example` (coincide con `foo.internal.example`)
- Comodín: `*` (excluye todo)
- Múltiples entradas: separadas por comas, con espacios en blanco recortados

La coincidencia de IP/CIDR **no** es compatible — esto sigue el comportamiento ampliamente
adoptado de curl.

## HTTP/2

### El servidor responde con HTTP/1.1 aunque no se pasó `--no-http2`

HTTP/2 require la negociación ALPN durante la negociación TLS. Si:

- el servidor no anuncia `h2` en ALPN, **o**
- el destino usa `http://` plano (h2c no es compatible),

httptap recurre a HTTP/1.1. Comprueba `network.http_version` en la exportación
JSON.

### ¿Cómo fuerzo HTTP/1.1?

Usa `--no-http2` (alias compatible con curl `--http1.1`). Esto desactiva por completo
la negociación ALPN de h2.

## Temporización

### `timing.is_estimated: true` — ¿qué significa?

httptap normalmente obtiene los tiempos de las fases a partir de los ganchos de traza de `httpcore`. Cuando esos
ganchos no están disponibles (p. ej., un `RequestExecutor` personalizado que los omite,
o ciertas rutas de reutilización de conexiones HTTP/2), httptap recurre a dividir el
tiempo total transcurrido mediante heurísticas. El desglose sigue siendo direccionalmente
correcto, pero menos preciso que la ruta predeterminada.

### ¿Por qué dos ejecuciones consecutivas muestran valores de `dns_ms` tan dispares?

El resolutor del sistema almacena entradas en caché. La primera solicitud paga el RTT completo hasta
tu servidor DNS; las solicitudes posteriores dan en la caché (a menudo por debajo del milisegundo).
Para omitir las cachés, proporciona un resolutor personalizado a través de la API de Python o vacía la
caché local (p. ej., `sudo dscacheutil -flushcache` en macOS, `resolvectl flush-caches`
en systemd).

### `ttfb_ms` es cero o inferior a `connect_ms`

En la reutilización de conexiones (keep-alive para pasos de redirección posteriores, multiplexación de
flujos HTTP/2) no hay una nueva conexión TCP para ese paso — `connect_ms` será
`0` o muy pequeño. `ttfb_ms` mide el tiempo hasta el primer byte de respuesta en
esa solicitud específica; es de esperar que compararlo con `connect_ms` entre pasos
parezca extraño.

## Salida

### No hay colores en mi terminal

httptap respeta la convención [`NO_COLOR`](https://no-color.org) y la detección de
TTY de Rich:

- Anula `NO_COLOR` si está configurada.
- Redirigir stdout a un archivo u otro proceso desactiva los colores; configura
  `FORCE_COLOR=1` para anularlo.
- `TERM=dumb` también desactiva la representación.

### `--metrics-only` dejó de mostrar un campo `proxy=`

No lo hizo — el campo siempre está presente. Las capturas/ejemplos antiguos pueden set anteriores
al cambio. Formato esperado:

```
Step 1: dns=30.1 ... tls_version=TLSv1.2 proxy=direct
```

Fuentes para `proxy`: `direct`, `none` (coincidencia con NO_PROXY), `disabled` (`--proxy ""`),
`<url>` con una pista `proxy_from=...`.

## Scripting y CI

### ¿Qué códigos de salida debo comprobar?

Consulta la sección [Exit Codes](https://github.com/ozeranskii/httptap#exit-codes)
del README. Patrón típico de CI: trata `75` (red / TLS, transitorio) como
reintentable, falla de forma rotunda con `64` (uso), `70` (error) y `4` (violación de SLO si
proporcionaste `--slo`).

### Mi presupuesto de `--slo` nunca se activa aunque la solicitud sea lenta.

Comprueba tres cosas:

1. Que la clave que configuraste se corresponde con una fase de temporización real. Las claves válidas son
   `dns`, `connect`, `tls`, `ttfb`, `wait`, `xfer`, `total` — cualquier otra
   rechaza el commando con código de salida `64` (panel de error de SLO).
2. El SLO se evalúa sobre el **paso exitoso final**, no sobre las redirecciones
   intermedias. Si `--follow` rebotó a través de various saltos y el último
   paso fue rápido, el total general de la cadena no se compara. Usa `total`
   contra el presupuesto de la solicitud terminal, o agrega manualmente desde
   `--json` si necesitas garantías por paso.
3. Si todos los pasos dieron error, el SLO se omite por completo — el código de salida
   refleja el fallo de red (normalmente `75`). En ese caso no aparece ningún token
   `slo=` en la salida de `--metrics-only`.

### ¿Puede httptap emitir métricas de Prometheus?

No de forma nativa. Usa `--metrics-only` y postprocesa con `awk`/`jq`, o
analiza la exportación `--json`. Un exportador dedicado está en la hoja de ruta — sigue el
[gestor de incidencias](https://github.com/ozeranskii/httptap/issues) para novedades.

## API de Python

### `ImportError: cannot import name 'HTTPMethod' from 'httptap'`

`HTTPMethod` reside en `httptap.constants`, no en el espacio de nombres de nivel superior:

```python
from httptap import HTTPTapAnalyzer
from httptap.constants import HTTPMethod
```

### No se llama a mi resolutor personalizado

`HTTPTapAnalyzer` usa el resolutor inyectado solo para la temporización de la búsqueda DNS de diagnóstico.
La resolución real de la conexión la sigue realizando `httpx`/`httpcore`.
Para enrutar la conexión real a través de tu resolutor, implementa también un
`RequestExecutor` personalizado.

---

## ¿Sigues atascado?

- Ejecuta con `--metrics-only` e incluye la salida completa en tu inform.
- Ejecuta con `--json report.json` y adjunta el inform (censura las cabeceras de autenticación).
- Confirma la versión — `httptap --version` — solo damos soporte a la última
  versión menor.
