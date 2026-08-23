# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.5-python3.14-trixie-slim@sha256:dc360d7e5f968c682e8b59e83027a315a0232dead15cb9dfe3e707a12ba390e1 AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps without the project so this layer stays cached across
# source-only changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project \
        --no-group docs --no-group lint --no-group test \
        --no-group typing --no-group precommit

COPY README.md LICENSE ./
COPY httptap/ ./httptap/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable \
        --no-group docs --no-group lint --no-group test \
        --no-group typing --no-group precommit


FROM python:3.14-slim-trixie@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4 AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    HOME=/tmp \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

RUN groupadd --system --gid 1000 httptap \
    && useradd --system --uid 1000 --gid httptap \
       --no-log-init --no-create-home --shell /usr/sbin/nologin httptap

COPY --link --from=builder --chown=1000:1000 /app/.venv /app/.venv
COPY --link --chown=1000:1000 LICENSE /usr/share/doc/httptap/LICENSE

USER 1000:1000
WORKDIR /work

ENTRYPOINT ["/app/.venv/bin/httptap"]

LABEL org.opencontainers.image.title="httptap" \
      org.opencontainers.image.description="Rich-powered CLI that dissects an HTTP request into DNS, TCP connect, TLS handshake, server wait, and body transfer phases and renders the results as a waterfall, compact summary, or machine-readable metrics. Includes per-phase latency SLO gate for CI jobs, cron probes, and Kubernetes readiness checks." \
      org.opencontainers.image.url="https://docs.httptap.dev" \
      org.opencontainers.image.documentation="https://docs.httptap.dev" \
      org.opencontainers.image.source="https://github.com/ozeranskii/httptap" \
      org.opencontainers.image.vendor="Sergei Ozeranskii" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.base.name="python:3.14-slim-trixie"
