# syntax=docker/dockerfile:1

# =============================================================================
# Multi-stage Dockerfile for mcprojsim
# Monte Carlo Project Simulator
# 
# Build: podman build -t mcprojsim .
# Proxy build: podman build --build-arg USE_PROXY_CA=true --secret id=proxy_ca,src=CA_proxy_fw_all.pem -t mcprojsim .
# Run:   podman run --rm -v "$(pwd):/work:Z" mcprojsim <args>
# Keep container: podman run --name mcprojsim-job -v "$(pwd):/work:Z" mcprojsim validate examples/sample_project.yaml
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies and build the package
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS builder

# Build argument to enable proxy/CA certificate handling
# Usage: docker build --build-arg USE_PROXY_CA=true ...
ARG USE_PROXY_CA=false
ARG CA_CERT_FILE=CA_proxy_fw_all.pem

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install build dependencies and Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.in-project true

# Copy project files
WORKDIR /build
COPY pyproject.toml poetry.lock README.md ./
COPY src/ ./src/

# Optionally configure a proxy CA certificate for corporate/proxied environments.
# The certificate is provided as a build secret named "proxy_ca", so standard builds
# do not require any placeholder file in the build context.
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

# Set environment variables for SSL/TLS (ensures pip and requests use system CA bundle)
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Install the package and its dependencies via Poetry
RUN poetry install --only main --no-interaction --no-ansi

# Remove build/install tooling and other non-runtime artifacts from the virtualenv
RUN /build/.venv/bin/python - <<'PY'
from pathlib import Path
import shutil

venv = Path('/build/.venv')
site_packages = next((venv / 'lib').glob('python*/site-packages'))

paths_to_remove = [
    site_packages / 'pip',
    site_packages / 'setuptools',
    site_packages / 'wheel',
    site_packages / 'pandas' / 'tests',
    site_packages / 'numpy' / 'tests',
    site_packages / 'scipy' / 'tests',
    site_packages / 'matplotlib' / 'tests',
]

for dist_info in site_packages.glob('pip-*.dist-info'):
    paths_to_remove.append(dist_info)
for dist_info in site_packages.glob('setuptools-*.dist-info'):
    paths_to_remove.append(dist_info)
for dist_info in site_packages.glob('wheel-*.dist-info'):
    paths_to_remove.append(dist_info)

for path in paths_to_remove:
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

for pattern in ('pip*', 'wheel*'):
    for path in (venv / 'bin').glob(pattern):
        if path.exists() and path.is_file():
            path.unlink()
PY

RUN find /build/.venv -type d -name '__pycache__' -prune -exec rm -rf '{}' + \
    && find /build/.venv -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete \
    && find /build/.venv -type f \( -name '*.pxd' -o -name '*.pyi' -o -name '*.a' -o -name '*.la' \) -delete \
    && find /build/.venv -type f \( -name '*.so' -o -name '*.so.*' \) -exec strip --strip-unneeded '{}' + 2>/dev/null || true

# -----------------------------------------------------------------------------
# Stage 2: Runtime - Minimal container for execution
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/build/.venv/bin:$PATH"

# Create non-root user for security
RUN groupadd --gid 1000 mcprojsim && \
    useradd --uid 1000 --gid 1000 --create-home mcprojsim

# Copy virtual environment from builder (Poetry creates .venv in-project)
COPY --from=builder /build/.venv /build/.venv
COPY --from=builder /build/src /build/src

# Set working directory (will be used for volume mount)
WORKDIR /work

# Change to non-root user
USER mcprojsim

# Set entrypoint to the mcprojsim CLI
ENTRYPOINT ["mcprojsim"]

# Default command shows help
CMD ["--help"]
