---
title: Caso de garantía de seguridad
description: Modelo de amenazas, límites de confianza, principios de diseño seguro aplicados y debilidades de implementación contrarrestadas para httptap.
---

# Caso de garantía de seguridad

Este documento es el caso de garantía de seguridad de httptap. Explica **por qué**
el proyecto cree que sus propiedades de seguridad se sostienen, no solo **cuáles**
son esas propiedades. Está estructurado conforme al criterio `assurance_case`
del nivel plata de las OpenSSF Best Practices.

**Última revisión:** 2026-04-13 para httptap 0.5.0.

El caso de garantía es un documento vivo; se revisa en cada versión mayor
y siempre que el panorama de amenazas o el conjunto de funcionalidades cambie
de forma material. Las propuestas de enmiendas se aceptan como pull requests
contra este archivo.

## Qué es httptap

httptap es una herramienta de diagnóstico de línea de commandos. Un desarrollador
proporciona una única URL (y opcionalmente cabeceras, un cuerpo, un proxy, un
paquete de CA, etc.) y httptap realiza una solicitud HTTP (o una cadena corta de
redirecciones) y muestra información de tiempos por fase e información de TLS. **No**:

- acepta entrada de red de pares no confiables (no es un servidor);
- gestiona cuentas de usuario, sesiones ni credenciales de larga duración;
- ejecuta código remoto ni evalúa scripts proporcionados por el servidor;
- persiste secrets ni datos de usuario más allá de la exportación opcional `--json`.

## Requisitos de seguridad

El proyecto se compromete con las siguientes propiedades de seguridad observables.
Cada una se asigna a arguments de apoyo en las secciones siguientes.

| # | Requisito | Justificación |
|---|-------------|-----------|
| SR-1 | La verificación del certificado TLS está habilitada de forma predeterminada para todo destino HTTPS. | Previene por defecto los ataques MITM pasivos y activos. |
| SR-2 | El HTTP en texto plano, el TLS debilitado o los paquetes de CA personalizados requieren una habilitación explícita por parte del usuario. | Garantiza que las configuraciones inseguras sean siempre deliberadas. |
| SR-3 | Las credenciales proporcionadas por el usuario (por ejemplo, las cabeceras `Authorization`) se reenvían solo a la URL original y no se filtran a destinos de redirección en hosts diferentes. | Previene el robo de credenciales mediante redirecciones abiertas. |
| SR-4 | La herramienta no ejecuta contenido servido por el host remoto. | Ninguna primitiva de ejecución de código desde el servidor. |
| SR-5 | Los artefactos de publicación (wheels/sdist de PyPI, imágenes de contenedor, etiquetas de git y commits de publicación) están firmados y su procedencia de compilación es verificable. | Protege a los usuarios de distribuciones manipuladas. |
| SR-6 | Todos los tokens del flujo de trabajo de CI siguen el menor privilegio y están fijados por SHA. | Reduce la superficie de ataque de la canalización de compilación. |
| SR-7 | La cadena de suministro (dependencies, GitHub Actions, imágenes de Docker) se supervisa en busca de vulnerabilidades conocidas. | Aplicación oportuna de parches a las debilidades de origen. |

## Límites de confianza

```
   ┌─────────────────────┐
   │ CLI user            │   trusted
   │ (argv, stdin, env)  │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ httptap process     │   trusted
   │ (Python 3.10+)      │
   └──────────┬──────────┘
              │  TLS/HTTP  ◄─── untrusted: network, proxy, remote host
              ▼
   ┌─────────────────────┐
   │ Remote HTTP server  │   untrusted
   └─────────────────────┘
```

- **Usuario → httptap** es confiable: se assume que el usuario tiene razones
  legítimas para emitir cualquier solicitud dada. La validación de entrada aún
  rechaza URLs, métodos, tiempos de espera, etc. mal formados para prevenir
  errores del operador.
- **httptap → red → servidor remoto** no es confiable. Todos los datos que cruzan
  este límite se tratan como controlados por el atacante: cabeceras de respuesta,
  códigos de estado, valores `Location`, certificados TLS, cuerpos de contenido.
- **Canalización de compilación → PyPI / GitHub Releases** es un límite de confianza
  independiente, asegurado mediante GitHub OIDC (sin claves de larga duración),
  firma con Sigstore y actions fijadas por SHA.

## Modelo de amenazas

Las amenazas se enumeran usando las categorías STRIDE que aplican a un
cliente HTTP de diagnóstico. Las amenazas fuera del alcance de un cliente (por
ejemplo, la denegación de servicio del lado del servidor) se excluyen
explícitamente como no objetivos.

| STRIDE | Amenaza | Mitigación |
|--------|--------|------------|
| **Spoofing** | El atacante suplanta al servidor HTTPS previsto. | Verificación del certificado TLS activada de forma predeterminada (SR-1); `--ignore-ssl` es de habilitación explícita y está documentado como inseguro (SR-2). |
| **Spoofing** | Un mirror malicioso de PyPI sirve un wheel manipulado. | PyPI usa TLS; las publicaciones están firmadas con Sigstore y con procedencia SLSA v1.0 (SR-5); los usuarios pueden verificar con `gh attestation verify`. |
| **Tampering** | Artefacto modificado en GitHub Releases. | Igual que arriba: las atestaciones de procedencia de compilación permiten una verificación independiente. |
| **Tampering** | Canalización de CI envenenada mediante una action de terceros comprometida. | Toda action está fijada por SHA (impuesto por Scorecard Pinned-Dependencies 10/10 y zizmor pedantic); Dependabot abre PRs para actualizar los pines (SR-6, SR-7). |
| **Repudiation** | — | Fuera de alcance; httptap no es un sistema multiusuario. |
| **Information disclosure** | Las credenciales en `-H Authorization` se filtran al destino de redirección en un host diferente. | La cadena de redirecciones preserva las cabeceras con alcance de host según el valor predeterminado de httpx; las redirecciones entre orígenes descartan las cabeceras sensibles (SR-3). |
| **Information disclosure** | La exportación `--json` incluye cabeceras de autenticación en disco. | Se aconseja a los usuarios en SECURITY.md y docs/troubleshooting.md que redacten las cabeceras de autenticación antes de compartir las exportaciones. |
| **Information disclosure** | MITM en un proxy inseguro. | El esquema de la URL del proxy se valida; se recomienda `socks5h://` / `https://` para destinos sensibles; el origen del proxy se reporta en la salida y en el JSON para auditoría. |
| **Denial of service** | Un servidor malicioso transmite un cuerpo sin límite. | Tiempo de espera por solicitud mediante `--timeout` (20s por defecto); la fase de transferencia está acotada por el mismo plazo. |
| **Denial of service** | Un servidor malicioso transmite una bomba zip o un cuerpo gigantesco. | httptap no decodifica ni persiste los cuerpos más allá de contar los bytes para la métrica de tiempos, así que el coste de memoria es lineal y está acotado por el tiempo de espera. |
| **Elevation of privilege** | Un cuerpo de respuesta malicioso desencadena una RCE en el analizador. | Los cuerpos nunca se analizan por su contenido: solo se lee la longitud. Ninguna interpretación de HTML, JS ni scripts embebidos (SR-4). |
| **Elevation of privilege** | Un argumento de CLI malicioso desencadena una inyección de shell en una invocación posterior. | Los arguments se analizan con `argparse` (sin shell), se reenvían como `list[str]` a `httpx` (sin shell); no hay invocación de shell en la ruta de la solicitud. |

### Amenazas fuera de alcance

- **Adversario con ejecución de código local en la máquina del desarrollador.** Fuera
  de alcance: ese adversario ya es dueño del proceso.
- **Adversario que controla el terminal / TTY del usuario.** Fuera de alcance.
- **Ataques criptoanalíticos contra el propio TLS.** Delegados a OpenSSL;
  las mitigaciones se heredan de la compilación de Python del sistema.
- **Amenazas poscuánticas.** Rastreadas de forma ascendente (OpenSSL / Python); fuera
  de alcance para el propio httptap.

## Principios de diseño seguro aplicados

Asignados a Saltzer & Schroeder (1975) más añadidos modernos.

| Principio | Aplicación en httptap |
|-----------|-----------------------|
| Economía del mecanismo | Base de código pequeña (~2 kLoC), un solo propósito, sin cargador de plugins, sin archivos de configuración en tiempo de ejecución. |
| Valores predeterminados a prueba de fallos | Verificación TLS activada, tiempo de espera predeterminado sensato, HTTP/2 preferido, sin seguimiento de redirecciones por defecto. |
| Mediación completa | Toda solicitud saliente se enruta a través de `HTTPClientRequestExecutor`; no hay una ruta de código secundaria ni heredada. |
| Diseño abierto | Toda la base de código es Apache-2.0 en GitHub; sin seguridad por oscuridad. |
| Separación de privilegios | La canalización de publicación está separada del entorno de desarrollo; la publicación en PyPI usa un GitHub Environment protegido por OIDC. |
| Menor privilegio | Cada job de CI declara un `permissions:` mínimo explícito; ningún flujo de trabajo tiene `write-all`. La verificación Token-Permissions de Scorecard puntúa 10/10. |
| Mecanismo menos común | Sin estado compartido entre ejecuciones (herramienta de una sola solicitud); sin cachés ni demonios en segundo plano. |
| Aceptabilidad psicológica | Los alias de flags compatibles con curl (`-X`, `-L`, `-k`, `-x`, `-H`) mantienen familiar el modelo mental. |
| Factor de trabajo | Las ganancias de un atacante frente a una invocación local de `curl` de un desarrollador son esencialmente nulas: httptap no expone más de lo que expone curl. |
| Registro de compromisos | La exportación JSON captura todos los metadatos de solicitud/respuesta y el origen del proxy, así que el análisis forense a posteriori es sencillo. |
| Defensa en profundidad | Validación de entrada + verificación TLS + dependencies de compilación fijadas + SAST + escaneo de secrets + Dependabot + publicaciones firmadas. |

## Debilidades de implementación comunes contrarrestadas

Derivadas del [CWE Top 25 (2023)](https://cwe.mitre.org/top25/) y de
[OWASP ASVS 4.0](https://owasp.org/www-project-application-security-verification-standard/).
Los elementos no enumerados o bien no aplican a un cliente HTTP o se manejan
de forma ascendente.

| CWE | Debilidad | Contramedida |
|-----|----------|----------------|
| CWE-20 | Validación de entrada indebida | Coerción de enum/tipo de `argparse`; URL/método/tiempo de espera/proxy verificados explícitamente. |
| CWE-22 | Traversal de rutas (en el cargador de datos `@file`) | La ruta se toma literalmente del usuario; nunca se usa una ruta proporcionada por el servidor para abrir un archivo. |
| CWE-78 | Inyección de commandos del SO | Ninguna llamada a `subprocess`/`os.system` sobre datos controlados por el usuario en la ruta de la solicitud. |
| CWE-79 | XSS | Sin renderizado de HTML; la salida es texto plano o marcado renderizado por Rich con escapado. |
| CWE-89 | Inyección SQL | Sin base de datos. |
| CWE-94 | Inyección de código | No se usan `eval`/`exec`; los cuerpos de respuesta nunca se analizan. |
| CWE-116 | Codificación de salida indebida | Rich maneja las secuencias de escape del terminal de forma segura; la exportación JSON usa `json.dumps` con escapado estricto. |
| CWE-200 | Divulgación de información sensible | Las cabeceras de autenticación no se copian a la salida de registro; SECURITY.md y la documentación advierten a los usuarios que redacten las exportaciones JSON antes de compartirlas. |
| CWE-295 | Validación de certificado indebida | Verificación TLS activada por defecto; `--ignore-ssl` solo de habilitación explícita, documentado explícitamente. |
| CWE-319 | Transmisión en texto claro | HTTPS preferido; el HTTP simple require una URL `http://` explícita; se reporta el origen del proxy. |
| CWE-327 | Criptografía rota | Delegada a la `ssl` de la biblioteca estándar; los algorithms débiles solo afloran al diagnosticar servidores remotos. |
| CWE-330 | Aleatoriedad insuficiente | Ningún uso de RNG más allá del CSPRNG provisto por OpenSSL para TLS. |
| CWE-352 | CSRF | No aplica: httptap es un cliente, no un servidor. |
| CWE-400 | Consumo de recursos no controlado | Tiempo de espera por solicitud; cadena de redirecciones acotada (máximo 10). |
| CWE-502 | Deserialización insegura | Solo `json.loads`; sin pickle, yaml.load ni marshal. |
| CWE-601 | Redirección abierta (filtración de credenciales) | El manejo de cabeceras con alcance de host hereda el comportamiento de httpx: las redirecciones entre orígenes descartan las cabeceras de autenticación sensibles. |
| CWE-918 | SSRF | httptap es el cliente; no actúa como proxy de solicitudes en nombre de otros sistemas. |

## Garantía de la cadena de suministro

En apoyo de la propiedad de integridad de la publicación (SR-5):

- **Publicación**: PyPI (y TestPyPI como prueba de humo de preproducción) mediante
  GitHub OIDC Trusted Publishing: ningún token de PyPI de larga duración en
  ningún sitio. Las atestaciones PEP 740 se muestran en PyPI como "Verified publisher".
- **Imágenes de contenedor**: las imágenes multiarquitectura (linux/amd64, linux/arm64) se
  compilan con Buildx y se publican en GHCR, se firman sin claves con cosign, y
  van acompañadas de procedencia de compilación SLSA adjunta al registro.
- **Firma de Git**: los commits de publicación y las etiquetas anotadas se firman sin claves
  con [gitsign](https://github.com/sigstore/gitsign) (x.509 mediante Fulcio
  + registro de transparencia Rekor), usando la identidad OIDC del flujo de trabajo de publicación.
- **Firma**: firma sin claves de Sigstore mediante
  `actions/attest-build-provenance` y cosign. Las claves de firma son
  de corta duración, emitidas por ejecución por Fulcio, y verificables mediante el
  registro de transparencia Rekor.
- **Procedencia**: una atestación SLSA v1.0 acompaña a cada wheel, sdist,
  y digest de imagen de contenedor.
- **Linting de Dockerfile**: `hadolint` se ejecuta en cada PR con un umbral de
  fallo a nivel de advertencia.
- **Fijación**: toda GitHub Action en todo flujo de trabajo está fijada por SHA;
  impuesto por Scorecard Pinned-Dependencies y zizmor pedantic en cada
  PR.
- **Seguimiento de dependencies**: se genera un SBOM en formatos CycloneDX y SPDX
  durante la publicación y se adjunta como asset de GitHub Release.
- **Divulgación de explotabilidad**: un documento OpenVEX
  (`httptap-X.Y.Z.openvex.json`) se distribute junto al SBOM, declarando
  para cada CVE de dependencia si `httptap` está realmente afectado. La
  fuente de verdad está versionada en
  [`.vex/httptap.openvex.json`](https://github.com/ozeranskii/httptap/blob/main/.vex/httptap.openvex.json);
  los escáneres que consumen VEX (Grype, Trivy, Snyk) lo usan para suprimir
  las alertas de falsos positivos en rutas de código vulnerable inalcanzables.

Los usuarios pueden verificar un artefacto descargado de forma independiente:

```shell
gh attestation verify dist/httptap-X.Y.Z-py3-none-any.whl \
  --repo ozeranskii/httptap
```

## Riesgos residuales conocidos

Estos están documentados en lugar de mitigados. Representan compensaciones
que son explícitas en lugar de descuidos.

- **Mantenedor único.** El factor bus es 1 (rastreado en GOVERNANCE.md). El
  plan de continuidad mitiga el punto único de fallo para las operaciones, pero no
  para la revisión de código: un único revisor puede fusionar cambios sin un segundo
  par de ojos. El pre-commit, las barreras de CI y el registro de auditoría público
  compensan en parte.
- **Sin sandboxing en tiempo de ejecución.** httptap se ejecuta con los privilegios
  completos del usuario. Esto es apropiado para una herramienta de diagnóstico de
  desarrollador, pero significa que un fallo en el propio `httptap` se ejecuta con
  los privilegios del usuario.
- **Anclas de confianza TLS heredadas del SO.** Si el almacén de confianza del SO está
  comprometido (por ejemplo, un proxy MITM corporation instala una CA privada),
  httptap no puede detector. Los campos `network.tls_custom_ca` y
  `proxy_source` en la exportación JSON documentan si se usó un paquete de CA
  personalizado o un proxy.

## Historical de cambios

| Fecha | Notas |
|------|-------|
| 2026-04-12 | Caso de garantía inicial para httptap 0.4.7 (envío para nivel plata). |
| 2026-04-13 | Endurecimiento OSS para 0.5.0: commits/etiquetas de publicación firmados con gitsign, verificación previa en TestPyPI, imágenes de contenedor GHCR firmadas con procedencia SLSA, hadolint en CI, artefacto de página de manual. |

---

## Referencias

- [SECURITY.md](https://github.com/ozeranskii/httptap/blob/main/SECURITY.md) — proceso de reporte de vulnerabilidades y versions soportadas.
- [GOVERNANCE.md](https://github.com/ozeranskii/httptap/blob/main/GOVERNANCE.md) — roles del proyecto, decisions y plan de continuidad.
- [ROADMAP.md](https://github.com/ozeranskii/httptap/blob/main/ROADMAP.md) — alcance, no objetivos y política de obsolescencia.
- [Resolución de problemas y preguntas frecuentes](../troubleshooting.md) — orientación operativa.
- [CWE Top 25](https://cwe.mitre.org/top25/) y
  [OWASP ASVS 4.0](https://owasp.org/www-project-application-security-verification-standard/)
  — catálogos de referencia de debilidades de implementación.
