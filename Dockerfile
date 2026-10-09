# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.24-python3.14-trixie-slim@sha256:a93df64b1084b616b0b7af75b7dd6309a146defdd93520f5c1b509451b69fb94 AS builder

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
    uv sync --frozen --no-dev --extra otel --no-install-project

COPY README.md LICENSE ./
COPY httptap/ ./httptap/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra otel --no-editable --reinstall-package httptap


FROM python:3.14-slim-trixie@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS runtime

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
