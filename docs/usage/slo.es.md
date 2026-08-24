---
title: Comprobación de umbrales SLO
description: Usa --slo para condicionar solicitudes a presupuestos de latencia por fase en CI, cron y comprobaciones de disponibilidad.
---

# Comprobación de umbrales SLO

`httptap --slo` comprueba los tiempos medidos frente a presupuestos de latencia
por fase y sale con un código distinto de cero cuando se supera cualquier presupuesto.
Esto convierte una única solicitud en una sonda de aprobado/fallido adecuada para
gates de CI, monitorización sintética basada en cron, comprobaciones de disponibilidad y
pruebas de humo tras el despliegue, sin escribir un analizador de shell personalizado.

## Ejemplo rápido

```shell
httptap --slo total=500,ttfb=200 https://api.example.com/health
```

- Sale con `0` cuando `total_ms ≤ 500` **y** `ttfb_ms ≤ 200`.
- Sale con `4` cuando se supera cualquier presupuesto.
- Sigue imprimiendo la cascada completa y la exportación JSON independientemente
  del resultado, de modo que las investigaciones nunca quedan bloqueadas por el gate.

## Sintaxis de especificación

Pasa a `--slo` una lista de pares `KEY=MS` separados por comas:

```
--slo KEY=MS[,KEY=MS]*
```

- `KEY` es una de las fases de temporización admitidas (sin distinción de mayúsculas/minúsculas).
- `MS` es un número finito positivo de milisegundos (entero o decimal).
- Se tolera el espacio en blanco alrededor de las claves y los valores.

### Claves admitidas

| Clave     | Significado                                                    |
|-----------|----------------------------------------------------------------|
| `dns`     | Tiempo de resolución DNS                                       |
| `connect` | Establecimiento de la conexión TCP                             |
| `tls`     | Negociación TLS (`0` para HTTP sin cifrar)                     |
| `ttfb`    | Tiempo hasta el primer byte (DNS + connect + TLS + espera del servidor) |
| `wait`    | Tiempo de procesamiento del servidor (`ttfb - (dns + connect + tls)`) |
| `xfer`    | Tiempo de transferencia del cuerpo de la respuesta (`total - ttfb`) |
| `total`   | Duración de la solicitud de extremo a extremo                 |

### Especificaciones mal formadas

`--slo` rechaza lo siguiente y sale con `64` (error de uso):

- Especificación vacía (`--slo ""`).
- Clave desconocida (`--slo foo=500` → `Unknown SLO key 'foo'`).
- Clave duplicada (`--slo total=500,total=600`).
- Valor no numérico (`--slo total=fast`).
- Valor cero, negativo o no finito (`--slo total=0`, `total=nan`,
  `total=inf`).
- Falta el `=` (`--slo total500`).

El error específico se imprime en un panel con formato Rich para el uso
interaction, y en texto plano con `--metrics-only`.

## Reglas de evaluación

Los umbrales SLO se evalúan frente al **paso final correcto** de
una cadena de solicitudes:

- Solicitud única → se comprueba frente a esa solicitud.
- Cadena de redirecciones (`--follow`) → se comprueba frente a la respuesta terminal,
  no frente a las redirecciones intermedias. Se assume que a los usuarios les importa
  lo que realmente sirvió su solicitud.
- Todos los pasos con error → el SLO se omite por completo; el código de salida refleja
  el fallo de red (véase más abajo).

Un umbral se aprueba cuando `actual ≤ threshold`. La igualdad **no**
cuenta como violación. Las violaciones se reportan en orden alfabético de
su clave para una salida determinista.

## Códigos de salida

`--slo` se integra con la precedencia general de códigos de salida de `httptap`:

| Prioridad | Condición                                | Código de salida |
|:--------:|-----------------------------------------|:---------:|
| 1        | Arguments inválidos (especificación `--slo` incorrecta) | `64`      |
| 2        | Fallo de red / TLS en cualquier paso     | `75`      |
| 3        | Error interno                            | `70`      |
| 4        | Violación de SLO en el paso final correcto | `4`      |
| 5        | Éxito                                     | `0`       |

Los errores de red siempre tienen prioridad sobre las violaciones de SLO, de modo que un
host que falla no se have pasar por una regresión de latencia en un registro de CI.

## Formatos de salida

### Rich (por defecto)

Tras la cascada y cualquier resumen de redirecciones, `httptap` imprime un panel
que resume la evaluación del SLO:

```
╭───────────────── ✗ SLO: fail ─────────────────╮
│ Thresholds: total≤500ms, ttfb≤200ms            │
│ Violations:                                    │
│   • total: 723.4ms > 500ms (+223.4ms)          │
│   • ttfb: 315.2ms > 200ms (+115.2ms)          │
╰────────────────────────────────────────────────╯
```

El borde y el icono del panel coinciden con el estado: verde `✓` para aprobado, rojo
`✗` para fallido.

### Compact

`--compact` imprime una línea legible por humanos por cada paso, seguida del
mismo panel SLO de Rich mostrado en el modo por defecto:

```
Step 1: 200 GET https://api.example.com | dns=3.3ms connect=97.0ms tls=194.6ms ttfb=446.0ms total=900.0ms | 1.2 KB

╭───────────────── ✗ SLO: fail ─────────────────╮
│ Thresholds: total≤500ms                        │
│ Violations:                                    │
│   • total: 900.0ms > 500ms (+400.0ms)          │
╰────────────────────────────────────────────────╯
```

### Metrics-only

`--metrics-only` añade tokens de SLO a la línea estándar `key=value`
del paso final correcto:

```
Step 1: dns=30.1 connect=97.3 tls=199.0 ttfb=472.2 total=900.0 ... slo=fail slo_violations=total,ttfb
```

Caso de aprobado:

```
Step 1: ... proxy=direct slo=pass
```

Los pasos de redirección intermedios **no** llevan tokens de SLO, manteniendo el
recuento de líneas sin cambios.

### Exportación JSON

`--json PATH` amplía el bloque `summary` con un objeto `slo`:

```json
{
  "summary": {
    "total_time_ms": 900.0,
    "final_status": 200,
    "final_url": "https://api.example.com/health",
    "final_bytes": 128,
    "errors": 0,
    "slo": {
      "pass": false,
      "thresholds_ms": { "total": 500.0, "ttfb": 200.0 },
      "violations": [
        {
          "key": "total",
          "threshold_ms": 500.0,
          "actual_ms": 900.0,
          "delta_ms": 400.0
        }
      ]
    }
  }
}
```

Cada violación lleva la clave, el umbral proporcionado por el usuario, el
valor medido y el exceso. `delta_ms` es estrictamente positivo y
puede usarse para clasificar las violaciones por gravedad.

Cuando no se pasa ningún flag `--slo`, la clave `slo` está ausente — la forma del
resumen es retrocompatible con los consumidores existentes.

## Recetas

### Monitorización sintética basada en cron

```cron
* * * * * httptap --slo total=1000,ttfb=500 https://api.example.com/health \
  || curl -X POST https://alerts.example.com/page/oncall
```

### Gate de CI tras el despliegue

```yaml
- name: Smoke-test staging latency
  run: |
    httptap --slo total=2000,tls=300,ttfb=800 \
      https://staging.example.com/
```

El paso falla solo con salida `4` o `64`. Los errores de red (salida `75`)
pueden gestionarse por separado:

```yaml
- name: Smoke-test staging latency
  id: smoke
  continue-on-error: true
  run: httptap --slo total=2000 https://staging.example.com/
- name: Fail CI only on SLO violation
  if: steps.smoke.outcome == 'failure' && steps.smoke.conclusion != 'success'
  run: |
    if [ "${{ steps.smoke.outputs.exit_code }}" = "4" ]; then
      echo "SLO violation — failing build."
      exit 1
    fi
```

### Sonda de disponibilidad (readiness) de Kubernetes

```yaml
readinessProbe:
  exec:
    command:
      - httptap
      - --slo
      - total=5000
      - http://localhost:8080/healthz
```

### Barra de regresión

```shell
httptap --slo total=500,ttfb=200 --json regression.json https://prod.example.com/
jq '.summary.slo.violations' regression.json
```

### Canary multi-host

```shell
for host in prod-eu prod-us prod-ap; do
  httptap --slo total=1500 "https://${host}.example.com/health" || echo "${host}: SLO miss"
done
```

## Consejos

- Empieza con `--slo total=<latencia P95>` y añade presupuestos por fase
  una vez que tengas datos de referencia de las exportaciones `--json`.
- `xfer` y `wait` son métricas derivadas; su suma está acotada por
  `total`. Si estableces un presupuesto de `total`, las fases individuals quedan
  implícitamente limitadas.
- Combínalo con `--timeout`: `--slo` comprueba la latencia *después* de que
  la solicitud se completa; `--timeout` mata de forma abrupta una solicitud que se cuelga.
  Normalmente querrás ambos.
- La salida de SLO refleja el formato del
  [`--slo` de `httpstat`](https://github.com/reorx/httpstat#slo-thresholds)
  (tokens `slo=pass` / `slo=fail`, código de salida `4`), de modo que los scripts
  pueden usarse indistintamente.
