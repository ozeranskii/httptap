---
title: Caso de garantía de seguridad
description: Modelo de amenazas, límites de confianza, principios de diseño seguro aplicados y debilidades de implementación contrarrestadas para httptap.
---

# Caso de garantía de seguridad

Este documento es el caso de garantía de seguridad de httptap. Explica **por qué**
el proyecto cree que sus propiedades de seguridad se sostienen, no solo **cuáles**
son esas propiedades. Está estructurado conforme al criterio `assurance_case`
del nivel plata de las OpenSSF Best Practices.

**Última revisión:** 2026-10-05.

El caso de garantía es un documento vivo; se revisa en cada versión mayor
y siempre que el panorama de amenazas o el conjunto de funcionalidades cambie
de forma material. Las propuestas de enmiendas se aceptan como pull requests
contra este archivo.

## Qué es httptap

httptap es una herramienta de diagnóstico de línea de comandos. Un desarrollador
proporciona una única URL (y opcionalmente cabeceras, un cuerpo, un proxy, un
paquete de CA, etc.) y httptap realiza una solicitud HTTP (o una cadena corta de
redirecciones) y muestra información de tiempos por fase e información de TLS. **No**:

- acepta entrada de red de pares no confiables (no es un servidor);
- gestiona cuentas de usuario, sesiones ni credenciales de larga duración;
- ejecuta código remoto ni evalúa scripts proporcionados por el servidor;
- persiste secretos ni datos de usuario más allá del informe opcional `--json`, el
  archivo `--har` y el textfile de `--prometheus`;
- envía mediciones a ningún sitio que no sea el collector OTLP que el usuario indica
  con la opción `--otlp`.

## Requisitos de seguridad

El proyecto se compromete con las siguientes propiedades de seguridad observables.
Cada una se asigna a argumentos de apoyo en las secciones siguientes.

| # | Requisito | Justificación |
|---|-------------|-----------|
| SR-1 | La verificación del certificado TLS está habilitada de forma predeterminada para todo destino HTTPS. | Previene por defecto los ataques MITM pasivos y activos. |
| SR-2 | El HTTP en texto plano, el TLS debilitado o los paquetes de CA personalizados requieren una habilitación explícita por parte del usuario. | Garantiza que las configuraciones inseguras sean siempre deliberadas. |
| SR-3 | Las credenciales proporcionadas por el usuario (cabeceras `Authorization`, `Cookie`, `Proxy-Authorization`) no se envían a destinos de redirección de otro origen (esquema, host o puerto), y el cuerpo de la petición no se reenvía tras una redirección que cambia el método a `GET`. | Previene el robo de credenciales mediante redirecciones abiertas. |
| SR-4 | La herramienta no ejecuta contenido servido por el host remoto. | Ninguna primitiva de ejecución de código desde el servidor. |
| SR-5 | Los artefactos de publicación (wheels/sdist de PyPI, imágenes de contenedor, etiquetas de git y commits de publicación) están firmados y su procedencia de compilación es verificable. | Protege a los usuarios de distribuciones manipuladas. |
| SR-6 | Todos los tokens del flujo de trabajo de CI siguen el menor privilegio y están fijados por SHA. | Reduce la superficie de ataque de la canalización de compilación. |
| SR-7 | La cadena de suministro (dependencias, GitHub Actions, imágenes de Docker) se supervisa en busca de vulnerabilidades conocidas. | Aplicación oportuna de parches a las debilidades de origen. |

## Límites de confianza

```
   ┌─────────────────────┐
   │ CLI user            │   trusted
   │ (argv, stdin, env)  │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐  --json, --har, --prometheus  ┌─────────────────────┐
   │ httptap process     │ ────────────────────────────► │ Local files, stdout │  trusted
   │ (Python 3.11+)      │                               └─────────────────────┘
   │                     │  --otlp (OTLP/HTTP)           ┌─────────────────────┐
   │                     │ ────────────────────────────► │ OTLP collector      │  user-chosen
   └──────────┬──────────┘                               └─────────────────────┘
              │  TLS/HTTP  ◄─── untrusted: network, proxy, remote host
              ▼
   ┌─────────────────────┐
   │ Remote HTTP server  │   untrusted
   └─────────────────────┘
```

- **Usuario → httptap** es confiable: se asume que el usuario tiene razones
  legítimas para emitir cualquier solicitud dada. La validación de entrada aún
  rechaza URLs, métodos, tiempos de espera, etc. mal formados para prevenir
  errores del operador.
- **httptap → red → servidor remoto** no es confiable. Todos los datos que cruzan
  este límite se tratan como controlados por el atacante: cabeceras de respuesta,
  códigos de estado, valores `Location`, certificados TLS, cuerpos de contenido.
- **httptap → salidas locales** es confiable: `--json` escribe el informe en un
  archivo o en stdout, `--har` escribe un archivo HAR 1.2 en un archivo o en
  stdout, y `--har` y `--prometheus` escriben sus archivos de forma atómica
  (archivo temporal en el mismo directorio y después un renombrado).
  Las etiquetas de Prometheus solo llevan el nombre de host y el número de paso de
  redirección, nunca rutas ni cadenas de consulta. Los archivos se crean donde el
  usuario indica y los puede leer cualquiera que tenga acceso a esa ubicación.
- **httptap → collector OTLP** cruza la red hacia un endpoint que el usuario
  proporciona con `--otlp` (extra opcional `httptap[otel]`), sobre `http://` o
  `https://` según se indique. Cada paso de la solicitud se convierte en un span con
  spans hijos por fase, que llevan el método, el código de estado, el tamaño del
  cuerpo, el nombre de host, la IP del par, las versiones de HTTP y TLS y el mensaje
  de error de un paso fallido. Los spans nunca incluyen la URL completa (ruta, cadena
  de consulta, credenciales) ni ninguna cabecera. Los fallos de entrega se informan
  como advertencias y no cambian el código de salida.
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
| **Information disclosure** | Las credenciales en `-H Authorization` se filtran al destino de redirección en un host diferente. | httptap sigue las redirecciones por sí mismo (`follow_redirects=False` en httpx) y descarta `Authorization`, `Cookie` y `Proxy-Authorization` cuando una redirección cambia el esquema, el host o el puerto; `303`, y `301`/`302` tras `POST`, pasan a `GET` sin cuerpo (SR-3). |
| **Information disclosure** | La exportación `--json` o `--har` incluye cabeceras de autenticación o credenciales de proxy en disco. | Las cabeceras `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie` y de claves de API se enmascaran en la salida y en la exportación, y las credenciales de las URL se ocultan en las URL de destino y de proxy, en las cabeceras `Location`/`Content-Location` y el destino de la redirección, y en el endpoint de `--otlp` que muestran los avisos de exportación; aun así, SECURITY.md y docs/troubleshooting.md aconsejan revisar las exportaciones antes de compartirlas. |
| **Information disclosure** | Las exportaciones de telemetría revelan detalles de la solicitud a quien lea el textfile o gestione el collector. | Las etiquetas de Prometheus se limitan al nombre de host y al paso; los spans OTLP omiten la URL completa y las cabeceras. La exportación OTLP es de habilitación explícita y solo se envía al endpoint indicado con `--otlp`; se recomienda `https://` para collectors remotos. |
| **Information disclosure** | MITM en un proxy inseguro. | Las URL de proxy se validan (esquema, host, puerto); se recomienda `socks5h://` / `https://` para destinos sensibles; el origen del proxy se reporta en la salida y en el JSON para auditoría. |
| **Denial of service** | Un servidor malicioso transmite un cuerpo sin límite. | `-m/--timeout` (20s por defecto) es un plazo estricto para toda la cadena: un temporizador cierra la conexión cuando vence, de modo que un servidor que se detiene o envía bytes con cuentagotas no puede prolongar la ejecución. |
| **Denial of service** | Un servidor malicioso transmite una bomba zip o un cuerpo gigantesco. | httptap no decodifica ni persiste los cuerpos más allá de contar los bytes para la métrica de tiempos, así que el coste de memoria es lineal y está acotado por el tiempo de espera. |
| **Elevation of privilege** | Un cuerpo de respuesta malicioso desencadena una RCE en el analizador. | Los cuerpos nunca se analizan por su contenido: solo se lee la longitud. Ninguna interpretación de HTML, JS ni scripts embebidos (SR-4). |
| **Elevation of privilege** | Un argumento de CLI malicioso desencadena una inyección de shell en una invocación posterior. | Los argumentos se analizan con `argparse` (sin shell), se reenvían como `list[str]` a `httpx` (sin shell); no hay invocación de shell en la ruta de la solicitud. |

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
| Economía del mecanismo | Base de código pequeña (~6 kLoC), un solo propósito, sin cargador de plugins, sin archivos de configuración en tiempo de ejecución. |
| Valores predeterminados a prueba de fallos | Verificación TLS activada, tiempo de espera predeterminado sensato, HTTP/2 preferido, sin seguimiento de redirecciones por defecto. |
| Mediación completa | Toda solicitud HTTP saliente se enruta a través de `HTTPClientRequestExecutor`; no hay una ruta de código heredada. La única ruta secundaria es una sonda solo TLS al mismo host y puerto, sin solicitud HTTP: una sonda de respaldo cuando la conexión activa no expone datos TLS, y una sonda de diagnóstico sin verificación que informa del certificado tras un fallo de verificación (la solicitud sigue fallando). Ambas se omiten cuando se usa un proxy y están limitadas por el plazo de la solicitud. |
| Diseño abierto | Toda la base de código es Apache-2.0 en GitHub; sin seguridad por oscuridad. |
| Separación de privilegios | La canalización de publicación está separada del entorno de desarrollo; la publicación en PyPI usa un GitHub Environment protegido por OIDC. |
| Menor privilegio | Cada job de CI declara un `permissions:` mínimo explícito; ningún flujo de trabajo tiene `write-all`. La verificación Token-Permissions de Scorecard puntúa 10/10. |
| Mecanismo menos común | Sin estado compartido entre ejecuciones (herramienta de una sola solicitud); sin cachés ni demonios en segundo plano. |
| Aceptabilidad psicológica | Los alias de flags compatibles con curl (`-X`, `-L`, `-k`, `-x`, `-H`) mantienen familiar el modelo mental. |
| Factor de trabajo | Las ganancias de un atacante frente a una invocación local de `curl` de un desarrollador son esencialmente nulas: httptap no expone más de lo que expone curl. |
| Registro de compromisos | La exportación JSON captura todos los metadatos de solicitud/respuesta y el origen del proxy, así que el análisis forense a posteriori es sencillo. |
| Defensa en profundidad | Validación de entrada + verificación TLS + dependencias de compilación fijadas + SAST + escaneo de secretos + Dependabot + publicaciones firmadas. |

## Debilidades de implementación comunes contrarrestadas

Derivadas del [CWE Top 25 (2023)](https://cwe.mitre.org/top25/) y de
[OWASP ASVS 4.0](https://owasp.org/www-project-application-security-verification-standard/).
Los elementos no enumerados o bien no aplican a un cliente HTTP o se manejan
de forma ascendente.

| CWE | Debilidad | Contramedida |
|-----|----------|----------------|
| CWE-20 | Validación de entrada indebida | Coerción de enum/tipo de `argparse`; URL/método/tiempo de espera/proxy verificados explícitamente (esquema, host y puerto del proxy, con código de salida `64`); los nombres de `-H` deben ser tokens RFC 9110 y los valores ASCII imprimible; los destinos de redirección se validan antes de seguirlos. |
| CWE-22 | Traversal de rutas (en el cargador de datos `@file`) | La ruta se toma literalmente del usuario; nunca se usa una ruta proporcionada por el servidor para abrir un archivo. |
| CWE-78 | Inyección de comandos del SO | Ninguna llamada a `subprocess`/`os.system` sobre datos controlados por el usuario en la ruta de la solicitud. |
| CWE-79 | XSS | Sin renderizado de HTML; los valores controlados por el servidor (URL, `Server`, `Location`, campos del certificado, mensajes de error) se escapan con `rich.markup.escape` antes del renderizado de Rich, y los modos de una línea se imprimen sin marcado. |
| CWE-89 | Inyección SQL | Sin base de datos. |
| CWE-94 | Inyección de código | No se usan `eval`/`exec`; los cuerpos de respuesta nunca se analizan. |
| CWE-113 | División de solicitudes HTTP (CRLF en cabeceras) | Los valores de `-H` con CR, LF u otros caracteres de control se rechazan antes de realizar ninguna solicitud. |
| CWE-116 | Codificación de salida indebida | Las cadenas controladas por el servidor se escapan antes del renderizado de marcado de Rich; la exportación JSON usa `json.dumps` con escapado estricto. |
| CWE-200 | Divulgación de información sensible | Las cabeceras sensibles se enmascaran y las credenciales de las URL (destino, proxy, `Location`/`Content-Location`, endpoint de `--otlp`) se ocultan en la salida, en los avisos y en la exportación JSON; las exportaciones de Prometheus y OTLP no llevan rutas de URL, cadenas de consulta ni cabeceras; las cabeceras de credenciales no se reenvían a otros orígenes en las redirecciones (SR-3); SECURITY.md y la documentación aconsejan revisar las exportaciones antes de compartirlas. |
| CWE-295 | Validación de certificado indebida | Verificación TLS activada por defecto; `--ignore-ssl` solo de habilitación explícita, documentado explícitamente. |
| CWE-319 | Transmisión en texto claro | HTTPS preferido; el HTTP simple requiere una URL `http://` explícita; se reporta el origen del proxy. |
| CWE-327 | Criptografía rota | Delegada a la `ssl` de la biblioteca estándar; los algoritmos débiles solo afloran al diagnosticar servidores remotos. |
| CWE-330 | Aleatoriedad insuficiente | Ningún uso de RNG más allá del CSPRNG provisto por OpenSSL para TLS. |
| CWE-352 | CSRF | No aplica: httptap es un cliente, no un servidor. |
| CWE-400 | Consumo de recursos no controlado | Plazo total para toda la cadena, aplicado incluso a lecturas detenidas; cadena de redirecciones acotada (máximo 10). |
| CWE-502 | Deserialización insegura | Solo `json.loads`; sin pickle, yaml.load ni marshal. |
| CWE-601 | Redirección abierta (filtración de credenciales) | httptap sigue las redirecciones con una comprobación explícita de origen: `Authorization`, `Cookie` y `Proxy-Authorization` se descartan en saltos entre orígenes. |
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
- **Seguimiento de dependencias**: se genera un SBOM en formatos CycloneDX y SPDX
  durante la publicación y se adjunta como asset de GitHub Release.
- **Divulgación de explotabilidad**: un documento OpenVEX
  (`httptap-X.Y.Z.openvex.json`) se distribuye junto al SBOM, declarando
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
  comprometido (por ejemplo, un proxy MITM corporativo instala una CA privada),
  httptap no puede detectarlo. Los campos `network.tls_custom_ca` y
  `proxy_source` en la exportación JSON documentan si se usó un paquete de CA
  personalizado o un proxy.

## Historial de cambios

| Fecha | Notas |
|------|-------|
| 2026-04-12 | Caso de garantía inicial para httptap 0.4.7 (envío para nivel plata). |
| 2026-04-13 | Endurecimiento OSS para 0.5.0: commits/etiquetas de publicación firmados con gitsign, verificación previa en TestPyPI, imágenes de contenedor GHCR firmadas con procedencia SLSA, hadolint en CI, artefacto de página de manual. |
| 2026-09-17 | Correcciones de seguridad en 0.6.2 ([GHSA-pgxm-hj3g-p7wv](https://github.com/ozeranskii/httptap/security/advisories/GHSA-pgxm-hj3g-p7wv)): SR-3 se garantiza con una comprobación explícita de origen en las redirecciones, los valores controlados por el servidor se escapan antes del renderizado de Rich (CWE-79/116) y las credenciales de proxy se ocultan (CWE-200); OpenVEX registra ahora el estado del aviso. |
| 2026-10-05 | Se añadieron las salidas de textfile `--prometheus` y de trazas `--otlp` a los límites de confianza, al modelo de amenazas y a las contramedidas de CWE-200; se documentaron las sondas TLS de respaldo y de diagnóstico en la mediación completa; se documentaron la validación de entrada de `-x/--proxy` y `-H` (CWE-20, CWE-113), la ocultación de credenciales de URL en las cabeceras `Location` y en el endpoint de `--otlp` (CWE-200), y el plazo total estricto (CWE-400). |

---

## Referencias

- [SECURITY.md](https://github.com/ozeranskii/httptap/blob/main/SECURITY.md) — proceso de reporte de vulnerabilidades y versiones soportadas.
- [GOVERNANCE.md](https://github.com/ozeranskii/httptap/blob/main/GOVERNANCE.md) — roles del proyecto, decisiones y plan de continuidad.
- [ROADMAP.md](https://github.com/ozeranskii/httptap/blob/main/ROADMAP.md) — alcance, no objetivos y política de obsolescencia.
- [Resolución de problemas y preguntas frecuentes](../troubleshooting.md) — orientación operativa.
- [CWE Top 25](https://cwe.mitre.org/top25/) y
  [OWASP ASVS 4.0](https://owasp.org/www-project-application-security-verification-standard/)
  — catálogos de referencia de debilidades de implementación.
