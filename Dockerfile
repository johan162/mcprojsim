# syntax=docker/dockerfile:1

# =============================================================================
# Multi-stage Dockerfile for mcprojsim
# Monte Carlo Project Simulator
#
# Build: podman build -t mcprojsim .
# Proxy: podman build --build-arg USE_PROXY_CA=true \
#                     --secret id=proxy_ca,src=CA_proxy_fw_all.pem -t mcprojsim .
# Run:   podman run --rm -v "$(pwd):/work:Z" mcprojsim <args>
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - resolve deps, pre-download wheels, build project wheel
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS builder

ARG USE_PROXY_CA=false
ARG CA_CERT_FILE=CA_proxy_fw_all.pem

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Optionally configure a proxy CA certificate for corporate/proxied environments.
# The certificate is provided as a build secret named "proxy_ca", so standard
# builds do not require any placeholder file in the build context.
RUN --mount=type=secret,id=proxy_ca,target=/run/secrets/proxy_ca,required=false \
    if [ "$USE_PROXY_CA" = "true" ]; then \
        if [ -s /run/secrets/proxy_ca ]; then \
            echo "✓ Configuring proxy CA certificate..."; \
            cat /run/secrets/proxy_ca >> /etc/ssl/certs/ca-certificates.crt; \
            echo "✓ CA certificate appended to system bundle"; \
        else \
            echo "⚠ Warning: USE_PROXY_CA=true but no proxy_ca build secret was provided!"; \
            echo "   Rebuild with: --secret id=proxy_ca,src=${CA_CERT_FILE}"; \
            exit 1; \
        fi; \
    else \
        echo "→ Using standard SSL certificates (no proxy)"; \
    fi

# All runtime deps ship binary wheels for Python 3.13 
# Poetry is only needed in the builder stage.
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.in-project true \
    && poetry config certificates.pypi.cert /etc/ssl/certs/ca-certificates.crt

WORKDIR /build

ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# ── deps layer: cached until pyproject.toml / poetry.lock changes ─────────────
# Install deps only (--no-root skips the project package itself), then
# pre-download every installed package as a wheel for the offline stage-2 install.
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --only main --no-interaction --no-ansi --no-root \
    && poetry run pip list --format=freeze | grep -v '^-e' > /tmp/deps.txt \
    && pip download --no-cache-dir -r /tmp/deps.txt -d /tmp/wheels

# ── source layer: cached until src/ changes ───────────────────────────────────
# Build the project wheel; the .whl carries full metadata so stage 2 only needs
# pip install, no Poetry, no venv, no build tooling.
COPY src/ ./src/
RUN poetry build -f wheel

# -----------------------------------------------------------------------------
# Stage 2: Runtime - install wheel + pre-downloaded deps, nothing else
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 mcprojsim && \
    useradd --uid 1000 --gid 1000 --create-home mcprojsim

# Install into the system Python directly (no venv needed in a single-purpose
# container). --no-index guarantees a fully reproducible, offline install.
COPY --from=builder /tmp/wheels /tmp/wheels
COPY --from=builder /build/dist  /tmp/dist
RUN pip install --no-cache-dir --no-index --find-links /tmp/wheels /tmp/dist/*.whl \
    && rm -rf /tmp/wheels /tmp/dist

WORKDIR /work
USER mcprojsim
ENTRYPOINT ["mcprojsim"]
CMD ["--help"]
