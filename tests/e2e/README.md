# End-to-end tests

Black-box tests for the `httptap` CLI. Each test runs the CLI as a subprocess and checks the
exit code, stdout, stderr, the files it writes and what the local servers received. The suite
never imports `httptap`, so it works the same against a source checkout, an installed wheel or a
container image.

Everything runs offline against servers started for the session: HTTP and TLS origins (with an
IPv6 twin on `::1`), a forward/CONNECT proxy that rejects unbracketed IPv6 authorities like
Squid, SOCKS5 proxies, and an OTLP/HTTP collector. Certificates come from a throwaway test CA.
The only name resolved through the system resolver is a reserved `.invalid` one.

A plain `uv run pytest` does not collect this directory (see `norecursedirs` in
`pyproject.toml`), because the suite needs an `httptap` executable and adds no coverage of the
package itself. Pass the directory explicitly.

## Running

```bash
# Against the source checkout; the otel extra is needed for the --otlp tests
uv run --extra otel pytest tests/e2e --no-cov -n auto

# Against a built wheel, as CI does
uv build
uv venv /tmp/httptap-wheel
uv pip install --python /tmp/httptap-wheel "$(ls dist/httptap-*.whl)[otel]"
uv run pytest tests/e2e --no-cov -n auto --httptap /tmp/httptap-wheel/bin/httptap
```

`-n auto` comes from `pytest-xdist` (in the `e2e` dependency group); drop it for a serial run.
`-m "not slow"` skips the tests that wait on deadlines.

Without `--httptap`, the suite uses `HTTPTAP_CMD`, then the `httptap` script next to the running
Python interpreter (the project virtual environment under `uv run`), then `httptap` on `PATH`.

### Docker

On Linux, host networking puts the container on the host's loopback (`127.0.0.1` and `::1`), so
the loopback-only tests run too. Files the suite shares with httptap (certificates,
`--json`/`--prometheus` outputs, `--slo-file` inputs) live in `--shared-dir`, which must be mounted
at the same path. The suite keeps its directories private, so the container runs as your user:

```bash
SHARED=/tmp/httptap-e2e; mkdir -p "$SHARED"
uv run pytest tests/e2e --no-cov -n auto --shared-dir "$SHARED" \
  --httptap "docker run --rm --network host --user $(id -u):$(id -g) -v $SHARED:$SHARED IMAGE"
```

On Docker Desktop for macOS, host networking does not reach the host's loopback. Use
`host.docker.internal`, which Docker Desktop forwards to the host's `127.0.0.1`, so the servers
can stay on loopback:

```bash
SHARED=/private/tmp/httptap-e2e; mkdir -p "$SHARED"
uv run pytest tests/e2e --no-cov -n auto --shared-dir "$SHARED" \
  --httptap "docker run --rm -v $SHARED:$SHARED IMAGE" \
  --target-host host.docker.internal \
  --target-ip "$(docker run --rm --entrypoint python IMAGE -c \
      'import socket; print(socket.gethostbyname("host.docker.internal"))')" \
  --bind-host 127.0.0.1
```

Environment variables a test sets (`HTTP_PROXY`, `NO_PROXY`, ...) are passed to `docker run` and
`podman run` with `-e`. Tests that need httptap on the same loopback as the servers (IPv6 `::1`,
`-4`/`-6` with `localhost`, an IP SAN on `127.0.0.1`) are skipped when `--target-host` is not a
loopback address. The two tests that pass raw non-UTF-8 argv bytes are skipped for any `docker`
or `podman` command, because the client sends argv to the daemon as JSON strings and replaces
those bytes with U+FFFD. Signals reach httptap through the signal proxy of `docker run`.

## CI

| Where                                                    | httptap under test                                                           |
| -------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `ci.yml`, job `test-e2e` (every push and pull request)   | The wheel built in the job, with the `otel` extra                            |
| `ci.yml`, job `container-build` (amd64 and arm64)        | The image built and loaded in the job                                        |
| `release.yml`, job `build`                               | The release wheel, before it is attested or uploaded                         |
| `e2e.yml` (daily, manual, and pull requests touching it) | The wheel on Linux, macOS and Windows with Python 3.11, 3.13, 3.14 and 3.14t |

The container job runs the suite on the runner with host networking, against the tag it has just
loaded (`--pull never` keeps Docker from fetching anything else):

```bash
SHARED="$RUNNER_TEMP/httptap-e2e"
mkdir -p "$SHARED"
uv run --no-sync pytest tests/e2e --no-cov -n auto \
  --shared-dir "$SHARED" --bind-host 127.0.0.1 \
  --httptap "docker run --rm --pull never --network host -v $SHARED:$SHARED --user $(id -u):$(id -g) httptap:ci-smoke"
```

Every job installs the test dependencies with
`uv sync --locked --no-dev --no-install-project --group test --group e2e`, so the project itself is
not installed next to the suite and only the `httptap` under test runs. On Windows, pass the path
to `Scripts\httptap.exe`: an `--httptap` value that names an existing file is used as one
argument, without shell-splitting.

## Options

| Option             | Default                                               | Meaning                                                                          |
| ------------------ | ----------------------------------------------------- | -------------------------------------------------------------------------------- |
| `--httptap CMD`    | see above                                             | Command prefix used to run httptap; shell-split unless it names a file.          |
| `--target-host H`  | `127.0.0.1`                                           | Host in the test URLs, as httptap reaches the servers.                           |
| `--target-ip IP`   | `--target-host` resolved locally                      | Address of `--target-host` as httptap sees it, for the `--resolve` tests.        |
| `--bind-host A`    | `127.0.0.1` (`0.0.0.0` if the target is not loopback) | Address the servers listen on.                                                   |
| `--shared-dir DIR` | system temp directory                                 | Parent of the per-session directory; each session and xdist worker gets its own. |
| `--wall-slack S`   | `0.75`                                                | Seconds a run may exceed `-m`, on top of the measured process start-up time.     |

Markers: `slow` (waits on deadlines) and `posix` (needs POSIX signals or argv bytes; skipped on
Windows). If httptap cannot reach the servers, a preflight check stops the session with a hint.

## Layout

| File                   | Contents                                                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| `conftest.py`          | Options and session fixtures: certificates, servers, runner, preflight.                     |
| `harness.py`           | Subprocess runner, `Result`, the `Servers` bundle, metrics parser and assertion helpers.    |
| `servers.py`           | Origin, forward/CONNECT proxy, SOCKS5 proxy and OTLP collector; each records its requests.  |
| `certs.py`             | Test CA and valid, self-signed, expired, wrong-host and IP-only certificates.               |
| `test_cli_args.py`     | `--help`/`--version`, usage errors (exit 64) and input validation.                          |
| `test_output_modes.py` | Rich, compact, metrics-only, JSON and Prometheus output; byte counts and timing invariants. |
| `test_requests.py`     | Methods, bodies, headers and masking of sensitive headers.                                  |
| `test_redirects.py`    | Redirect chains, method rewriting, credential handling and redirect failures.               |
| `test_tls.py`          | Verification, custom CAs, `-k`, certificate errors, IDN names, HTTP/1.1.                    |
| `test_network.py`      | Refused and unresolvable targets, address families, `--resolve`, deadlines, signals.        |
| `test_proxies.py`      | HTTP, CONNECT and SOCKS5 proxies, proxy auth, environment proxies and `NO_PROXY`.           |
| `test_exports_slo.py`  | OTLP export, SLO evaluation, exit-code precedence and credential redaction in every sink.   |
