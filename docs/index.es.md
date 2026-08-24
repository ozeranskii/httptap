---
title: httptap
description: CLI basada en Rich que descompone una solicitud HTTP en cada fase significativa
---

<p align="center">
  <img src="../assets/httptap-banner.svg" alt="httptap" style="width: 100%; max-width: 1280px; height: auto;" />
</p>

# httptap

<div style="text-align: center; margin-bottom: 2em;">
  <p>
    <a href="https://pypi.org/project/httptap/"><img src="https://img.shields.io/pypi/v/httptap?color=3775A9&label=PyPI&logo=pypi" alt="PyPI" /></a>
    <a href="https://pypi.org/project/httptap/"><img src="https://img.shields.io/pypi/pyversions/httptap?logo=python" alt="Python Versions" /></a>
    <a href="https://github.com/ozeranskii/httptap/actions/workflows/ci.yml"><img src="https://github.com/ozeranskii/httptap/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
    <a href="https://codecov.io/github/ozeranskii/httptap"><img src="https://codecov.io/github/ozeranskii/httptap/graph/badge.svg?token=OFOHOI1X5J" alt="Coverage" /></a>
  </p>
</div>

`httptap` es una CLI basada en Rich que descompone una solicitud HTTP en cada fase significativa —DNS, conexión TCP,
negociación TLS, espera del servidor y transferencia del cuerpo— y presenta los resultados como una tabla de línea de
tiempo, un resumen compacto o métricas legibles por máquina. Está diseñada para la resolución de problemas interactiva,
el análisis de regresiones y el registro de líneas base de rendimiento.

!!! tip "Oferta especial"
    <div style="text-align: center; margin-bottom: 0.6em;">
      :gift:{ style="font-size: 1.5em; margin-right: 0.35em; vertical-align: middle;" } <span style="font-weight: 700; font-size: 1.05em;">Ahorra un 50 % en GitKraken Pro</span>
    </div>

    <div style="text-align: center; font-size: 0.95em; margin-bottom: 1em; line-height: 1.5;">
      Combina GitKraken Client, GitLens para VS Code y potentes herramientas de CLI para acelerar cada flujo de trabajo de tus repositorios.
    </div>

    <div style="display: block; text-align: center; margin-top: 1em; margin-bottom: 0.8em;">
      [:fontawesome-solid-bolt: Obtén un 50 % de descuento](https://gitkraken.cello.so/vY8yybnplsZ){ .md-button .md-button--primary style="font-size: 0.95em; padding: 0.6em 1.8em; font-weight: 600; letter-spacing: 0.01em; background: linear-gradient(135deg, #3949ab 0%, #5e35b1 100%); border: none; box-shadow: 0 2px 8px rgba(57, 73, 171, 0.3);" }
    </div>

    <small style="display: block; margin-top: 0.6em; opacity: 0.75; font-size: 0.85em; text-align: center;">*Exclusivo para la comunidad de httptap*</small>

## Aspects destacados

- **Temporización fase por fase** – mediciones precisas construidas a partir de los ganchos de traza de httpcore (con
  alternativas sensatas cuando los datos de bajo nivel no están disponibles)
- **Todos los métodos HTTP** – GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS con soporte de cuerpo de solicitud
- **Soporte de cuerpo de solicitud** – envía JSON, XML o cualquier dato en línea o desde un archivo con detección automática de Content-Type
- **Consciente de IPv4/IPv6** – el resolutor y el inspector de TLS informan tanto la dirección como su familia
- **Información de TLS** – el CN del certificado, los SAN, el emisor, el número de series, la ventana de validez y la cuenta atrás de caducidad, además del conjunto de cifrado y la versión del protocolo, se capturan automáticamente desde la conexión activa (sin negociación TLS adicional)
- **Múltiples modos de salida** – vista de cascada de Rich, resúmenes compactos de una sola línea o `--metrics-only` para scripting
- **Exportación JSON** – conserva los datos completos de los pasos (incluidas las cadenas de redirecciones) para su procesamiento posterior
- **Extensible** – interfaces Protocol limpias para DNS, TLS, temporización, visualización y exportación para que puedas
  incorporar comportamiento personalizado

## Ejemplos rápidos

**Solicitud GET:**
```bash
httptap https://httpbin.io/get
```

**POST con datos JSON:**
```bash
httptap --data '{"name": "John"}' https://httpbin.io/post
```

![Salida de ejemplo](assets/sample-output.png)

## Características clave

### Visualización de cascada con Rich

Consulta el desglose detallado de la temporización de cada fase de la solicitud HTTP con una hermosa interfaz de terminal basada en Rich.

### Múltiples formatos de salida

- **Modo Rich** (predeterminado): hermosa tabla de cascada con colores y formato
- **Modo compacto** (`--compact`): resúmenes de una sola línea adecuados para logs
- **Modo de métricas** (`--metrics-only`): métricas en bruto para scripting y automatización
- **Exportación JSON** (`--json`): datos completos de la solicitud, incluidas las cadenas de redirecciones

### Información avanzada de red

- Temporización de la resolución DNS con detección de familia de IP (IPv4/IPv6)
- Temporización del establecimiento de la conexión TCP
- Análisis de la negociación TLS con información del certificado
- Medición del tiempo hasta el primer byte (TTFB)
- Temporización de la transferencia del cuerpo de la respuesta

### Soporte de cadenas de redirecciones

Sigue las redirecciones HTTP y consulta el desglose de la temporización de cada paso de la cadena con la opción `--follow`.

## ¿Qué sigue?

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **[Instalación](getting-started/installation.md)**

    ---

    Empieza con httptap en segundos

-   :material-lightning-bolt:{ .lg .middle } **[Inicio rápido](getting-started/quick-start.md)**

    ---

    Aprende lo básico con ejemplos sencillos

-   :material-console:{ .lg .middle } **[Guía de uso](usage/basic.md)**

    ---

    Explora todas las características y opciones

-   :material-api:{ .lg .middle } **[Referencia de la API](api/overview.md)**

    ---

    Amplía httptap con componentes personalizados

</div>

## Requisitos

- Python 3.10-3.15
- macOS, Linux o Windows
- Sin dependencies del sistema más allá de la red estándar

## Licencia

Apache License 2.0 © Sergei Ozeranskii

## Conecta

Sigue al author para conocer ideas basadas en experiencia del mundo real:

- :fontawesome-brands-telegram:{ .telegram } **[Canal de Telegram](https://t.me/sergeiozeranskii)** - Desarrollo, DevOps, arquitectura y seguridad. Experiencia real e ideas prácticas sin relleno.
- :fontawesome-brands-github: **[GitHub](https://github.com/ozeranskii)** - Proyectos de código abierto y contribuciones

## Agradecimientos

Construido sobre los hombros de bibliotecas fantásticas:

- [httpx](https://www.python-httpx.org/) - Cliente HTTP moderno
- [httpcore](https://github.com/encode/httpcore) - Implementación de bajo nivel del protocolo HTTP
- [dnspython](https://www.dnspython.org/) - Kit de herramientas DNS para Python
- [Rich](https://github.com/Textualize/rich) - Hermoso formato de terminal
