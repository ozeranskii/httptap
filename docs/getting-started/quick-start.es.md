---
description: Comienza con httptap mediante solicitudes básicas y ejemplos habituales de la línea de commandos.
---

# Inicio rápido

Esta guía te acompañará a través del uso básico de httptap.

## Solicitud básica

Ejecuta una solicitud HTTP sencilla y muestra una vista de cascada de Rich:

```bash
httptap https://httpbin.io
```

Esto generará un desglose detallado de la temporización que muestra:

- Tiempo de resolución DNS
- Establecimiento de la conexión TCP
- Negociación TLS (para HTTPS)
- Tiempo hasta el primer byte (TTFB)
- Tiempo de transferencia del cuerpo de la respuesta

## Realización de solicitudes POST

Envía datos JSON a una API:

```bash
httptap --data '{"name": "John Doe", "email": "john@example.com"}' https://httpbin.io/post
```

!!! tip "Comportamiento de POST automático"
    Cuando se proporciona `--data` sin `--method`, httptap cambia automáticamente a POST (similar a curl).

!!! tip "Opciones compatibles con curl"
    Las opciones más comunes de curl funcionan sin cambios. Usa `-X/--request` para el método HTTP, `-L/--location` para seguir redirecciones, `-m/--max-time` para los tiempos de espera, `-k/--insecure` para desactivar la verificación de certificados, `-x` para los proxies y `--http1.1` para forzar HTTP/1.1 (equivalente a `--no-http2`). No todas las opciones de curl son compatibles, así que cíñete a estas opciones compartidas al intercambiar commandos.

Carga datos desde un archivo:

```bash
echo '{"title": "New Post", "content": "Hello World"}' > post-data.json
httptap --data @post-data.json https://httpbin.io/post
```

## Uso de otros métodos HTTP

httptap admite todos los métodos HTTP estándar:

**Solicitud PUT:**
```bash
httptap --method PUT --data '{"status": "updated"}' https://httpbin.io/put
```

**Solicitud PATCH:**
```bash
httptap --method PATCH --data '{"field": "value"}' https://httpbin.io/patch
```

**Solicitud DELETE:**
```bash
httptap --method DELETE https://httpbin.io/delete
```

**Solicitud HEAD (solo cabeceras):**
```bash
httptap --method HEAD https://httpbin.io/get
```

## Adición de cabeceras personalizadas

Añade cabeceras HTTP personalizadas usando la opción `-H`:

```bash
httptap -H "Accept: application/json" https://httpbin.io/json
```

Se pueden añadir varias cabeceras repitiendo la opción:

```bash
httptap \
  -H "Accept: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  https://httpbin.io/bearer
```

## Seguimiento de redirecciones

De forma predeterminada, httptap no sigue las redirecciones. Para seguir las cadenas de redirecciones:

```bash
httptap --follow https://httpbin.io/redirect/3
```

Esto mostrará la información de temporización de cada paso de la cadena de redirecciones.

## Salida compacta

Para una única línea legible por humanos por paso — adecuada para logs
de terminal y seguimiento mediante `grep` / `tee`:

```bash
httptap --compact https://httpbin.io/get
```

Ejemplo de salida:

```
Step 1: 200 GET https://httpbin.io/get | dns=8.9ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=447.3ms | 389 B
```

La línea encabeza con el estado HTTP para que los fallos resalten; los tiempos
llevan el sufijo `ms` y el tamaño de la respuesta se representa con una
unidad apropiada (`B`, `KB`, `MB`). Las cadenas de redirecciones aún terminan con
la tabla completa `Redirect Chain Summary`, de modo que la forma general de la
solicitud permanece visible.

Para una salida `key=value` analizable por máquina (sin unidades, con campos de
IP/familia/TLS incluidos), usa `--metrics-only` a continuación.

## Modo de solo métricas

Obtén métricas en bruto sin formato, perfecto para scripts:

```bash
httptap --metrics-only https://httpbin.io
```

Ejemplo de salida:

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=476.0 status=200 bytes=389 ip=44.211.11.205 family=IPv4 tls_version=TLSv1.2 proxy=direct
```

## Exportación JSON

Exporta los datos completos de la solicitud a JSON para su análisis posterior:

```bash
httptap --json output.json https://httpbin.io
```

El archivo JSON contendrá:

- Temporización detallada de todas las fases
- Información de red (IP, versión de TLS, detalles del certificado)
- Metadatos de la respuesta (estado, cabeceras, tamaño del cuerpo)
- Cadena de redirecciones completa (si se usa `--follow`)
- Evaluación del SLO (si se proporciona `--slo`)

## Comprobación de umbrales de SLO

Condiciona los trabajos de CI, las sondas de cron o las comprobaciones de disponibilidad de Kubernetes a
presupuestos de latencia por fase con `--slo`:

```bash
httptap --slo total=500,ttfb=200 https://httpbin.io/get
```

El código de salida es `0` cuando todos los presupuestos se cumplen y `4` cuando se viola cualquier umbral.
La cascada completa se sigue representando para que puedas ver *por qué*
falló la comprobación.

!!! tip "Claves de SLO admitidas"
    `dns`, `connect`, `tls`, `ttfb`, `wait`, `xfer`, `total` — cada una
    se corresponde con una fase de temporización. Consulta la página dedicada
    [Comprobación de umbrales de SLO](../usage/slo.md) para la especificación
    completa y las recetas.

## Casos de uso comunes

### Pruebas de API

Prueba un flujo de trabajo completo de una API REST:

```bash
# Create a resource
httptap --data '{"title": "Test Post"}' https://httpbin.io/post

# Update the resource
httptap --method PUT --data '{"title": "Updated Post"}' https://httpbin.io/put

# Partial update
httptap --method PATCH --data '{"published": true}' https://httpbin.io/patch

# Delete the resource
httptap --method DELETE https://httpbin.io/delete
```

### Comprobación de la latencia de una API

```bash
httptap --compact https://httpbin.io/status/200
```

### Depuración de respuestas lentas

```bash
httptap https://httpbin.io/delay/3
```

La vista de cascada ayudará a identificar qué fase está causando el retraso (DNS, conexión, TLS o procesamiento del servidor).

### Verificación de la configuración de TLS

```bash
httptap https://httpbin.io
```

Comprueba la versión de TLS, el conjunto de cifrado y la caducidad del certificado en la salida.

### Evaluación comparativa del rendimiento

Establece líneas base de rendimiento y realiza un seguimiento de los cambios a lo largo del tiempo:

```bash
# Collect 10 samples and calculate statistics
for i in {1..10}; do
  httptap --metrics-only https://httpbin.io/delay/1
done | awk '/total=/ {
  # Extract total value
  for (i = 1; i <= NF; i++) {
    if ($i ~ /^total=/) {
      sub(/^total=/, "", $i)
      sum += $i
      values[++count] = $i
      break
    }
  }
}
END {
  if (count > 0) {
    avg = sum / count
    printf "Average: %.1f ms\n", avg
    printf "Samples: %d\n", count

    # Calculate min/max
    min = values[1]; max = values[1]
    for (i = 1; i <= count; i++) {
      if (values[i] < min) min = values[i]
      if (values[i] > max) max = values[i]
    }
    printf "Min: %.1f ms\n", min
    printf "Max: %.1f ms\n", max
    printf "Range: %.1f ms\n", (max - min)
  }
}'
```

Ejemplo de salida:
```
Average: 1490.0 ms
Samples: 10
Min: 1445.4 ms
Max: 1532.4 ms
Range: 87.0 ms
```

Esto ayuda a identificar la variabilidad del rendimiento y a establecer líneas base fiables para las pruebas de regresión.

---

## ¿Qué sigue?

<div class="grid cards" markdown>

-   :material-console:{ .lg .middle } **[Guía de uso básico](../usage/basic.md)**

    ---

    Referencia completa de la línea de commandos

-   :material-palette:{ .lg .middle } **[Formatos de salida](../usage/output-formats.md)**

    ---

    Modos Rich, compacto, JSON y métricas

-   :material-api:{ .lg .middle } **[Referencia de la API](../api/overview.md)**

    ---

    Amplía httptap con componentes personalizados

</div>
