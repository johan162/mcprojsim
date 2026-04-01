#!/bin/bash
# MCP Bundle Builder
# Creates a versioned MCP server bundle zip with manifest + launcher script.
#
# Usage:
#   ./scripts/mkmcpbundle.sh
#   ./scripts/mkmcpbundle.sh --help
#
# Notes:
# - Assumes ./scripts/mkbld.sh has been run first.
# - If the project wheel is missing in dist/, this script builds it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
PACKAGE_NAME="mcprojsim"
README_TEMPLATE="${SCRIPT_DIR}/mcp_bundle_README.md.template"

show_help() {
    cat << 'EOF'
Build an MCP bundle zip for mcprojsim.

The script:
1. Reads version from pyproject.toml
2. Ensures a wheel exists in dist/
3. Creates a bundle payload with:
   - manifest.json
   - bootstrap.sh
   - launcher.sh
   - README.md
   - wheels/<mcprojsim wheel>
4. Writes dist/mcprojsim-mcp-bundle-<version>.zip

Usage:
  ./scripts/mkmcpbundle.sh
  ./scripts/mkmcpbundle.sh --help
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    show_help
    exit 0
fi

if [[ ! -f "${ROOT_DIR}/pyproject.toml" ]]; then
    echo "Error: run this script from the project repository." >&2
    exit 2
fi

if ! command -v poetry >/dev/null 2>&1; then
    echo "Error: poetry is required on PATH." >&2
    exit 2
fi

if ! command -v zip >/dev/null 2>&1; then
    echo "Error: zip is required on PATH." >&2
    exit 2
fi

if [[ ! -f "${README_TEMPLATE}" ]]; then
  echo "Error: README template not found at ${README_TEMPLATE}" >&2
  exit 2
fi

VERSION="$(awk -F '"' '/^version = / {print $2; exit}' "${ROOT_DIR}/pyproject.toml")"
if [[ -z "${VERSION}" ]]; then
    echo "Error: could not determine version from pyproject.toml." >&2
    exit 2
fi

mkdir -p "${DIST_DIR}"
WHEEL_PATH="${DIST_DIR}/${PACKAGE_NAME}-${VERSION}-py3-none-any.whl"

if [[ ! -f "${WHEEL_PATH}" ]]; then
    echo "Wheel not found for version ${VERSION}, building wheel..."
    (
        cd "${ROOT_DIR}"
        poetry build -f wheel
    )
fi

if [[ ! -f "${WHEEL_PATH}" ]]; then
    echo "Error: expected wheel not found at ${WHEEL_PATH}" >&2
    exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

BUNDLE_STEM="${PACKAGE_NAME}-mcp-bundle-${VERSION}"
PAYLOAD_DIR="${TMP_DIR}/${BUNDLE_STEM}"
WHEEL_BASENAME="$(basename "${WHEEL_PATH}")"

mkdir -p "${PAYLOAD_DIR}/wheels"
cp "${WHEEL_PATH}" "${PAYLOAD_DIR}/wheels/${WHEEL_BASENAME}"

cat > "${PAYLOAD_DIR}/manifest.json" <<EOF
{
  "name": "mcprojsim",
  "version": "${VERSION}",
  "description": "mcprojsim MCP server bundle",
  "bootstrap": "bootstrap.sh",
  "launcher": "launcher.sh",
  "entrypoint": "mcprojsim-mcp",
  "readme": "README.md"
}
EOF

sed "s/__VERSION__/${VERSION}/g" "${README_TEMPLATE}" > "${PAYLOAD_DIR}/README.md"

cat > "${PAYLOAD_DIR}/launcher.sh" <<'EOF'
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --install-only: install the server (if needed) and exit without starting it.
# Useful for pre-installation, agent automation, and manual verification.
INSTALL_ONLY=0
if [[ "${1:-}" == "--install-only" ]]; then
    INSTALL_ONLY=1
    shift
fi

CLIENT_PROFILE="${MCP_CLIENT:-}"

if [[ -z "${CLIENT_PROFILE}" ]]; then
  if [[ -n "${CLAUDE_HOME:-}" || -d "${HOME}/.claude" ]]; then
    CLIENT_PROFILE="claude"
  elif [[ -n "${COPILOT_HOME:-}" || -d "${HOME}/.copilot" ]]; then
    CLIENT_PROFILE="copilot"
  else
    CLIENT_PROFILE="generic"
  fi
fi

case "${CLIENT_PROFILE}" in
  claude|Claude|CLAUDE)
    CLAUDE_BASE="${CLAUDE_HOME:-${HOME}/.claude}"
    DEFAULT_INSTALL_ROOT="${CLAUDE_BASE}/mcp/servers/mcprojsim"
    ;;
  copilot|Copilot|COPILOT)
    if [[ -n "${COPILOT_HOME:-}" ]]; then
      COPILOT_BASE="${COPILOT_HOME}"
    elif [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
      COPILOT_BASE="${XDG_CONFIG_HOME}/copilot"
    else
      COPILOT_BASE="${HOME}/.copilot"
    fi
    DEFAULT_INSTALL_ROOT="${COPILOT_BASE}/mcp/servers/mcprojsim"
    ;;
  *)
    if [[ -n "${MCP_CLIENT_HOME:-}" ]]; then
      GENERIC_BASE="${MCP_CLIENT_HOME}"
    elif [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
      GENERIC_BASE="${XDG_CONFIG_HOME}/mcp"
    else
      GENERIC_BASE="${HOME}/.mcp"
    fi
    DEFAULT_INSTALL_ROOT="${GENERIC_BASE}/servers/mcprojsim"
    ;;
esac

INSTALL_ROOT="${MCPROJSIM_MCP_HOME:-${DEFAULT_INSTALL_ROOT}}"
VENV_DIR="${MCPROJSIM_MCP_VENV:-${INSTALL_ROOT}/.venv}"
PYTHON_CMD="${PYTHON_CMD:-python3}"
WHEEL_PATH="$(ls "${SCRIPT_DIR}"/wheels/mcprojsim-*.whl | head -n 1)"

if [[ -z "${WHEEL_PATH}" ]]; then
    echo "Error: no mcprojsim wheel found in bundle wheels/ directory." >&2
    exit 1
fi

mkdir -p "${INSTALL_ROOT}"

if [[ ! -x "${VENV_DIR}/bin/mcprojsim-mcp" ]]; then
    echo "[mcprojsim] Installing MCP server to ${INSTALL_ROOT}..."
    "${PYTHON_CMD}" -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip >/dev/null 2>&1
    "${VENV_DIR}/bin/pip" install "${WHEEL_PATH}" "mcp[cli]>=1.0.0" >/dev/null 2>&1
    echo "[mcprojsim] Installation complete." >&2
else
    echo "[mcprojsim] Already installed at ${INSTALL_ROOT}." >&2
fi

if [[ "${INSTALL_ONLY}" == "1" ]]; then
    echo "[mcprojsim] Server binary: ${VENV_DIR}/bin/mcprojsim-mcp" >&2
    exit 0
fi

exec "${VENV_DIR}/bin/mcprojsim-mcp" "$@"
EOF
chmod +x "${PAYLOAD_DIR}/launcher.sh"

cat > "${PAYLOAD_DIR}/bootstrap.sh" <<'EOF'
#!/bin/bash
# bootstrap.sh — One-step installer and MCP client configurator for mcprojsim.
#
# Detects your MCP client, installs the server via launcher.sh, and writes
# the appropriate client configuration file — all in one step.
#
# Usage:
#   bash bootstrap.sh                      # auto-detect client
#   MCP_CLIENT=copilot bash bootstrap.sh   # Copilot CLI
#   MCP_CLIENT=claude  bash bootstrap.sh   # Claude Desktop
#   MCP_CLIENT=generic bash bootstrap.sh   # install only, print config snippet

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Detect client profile ─────────────────────────────────────────────────────
CLIENT_PROFILE="${MCP_CLIENT:-}"
if [[ -z "${CLIENT_PROFILE}" ]]; then
  COPILOT_BASE="${COPILOT_HOME:-${HOME}/.copilot}"
  CLAUDE_BASE="${CLAUDE_HOME:-${HOME}/.claude}"

  # Primary signal: use the script's own location.
  # A bundle placed inside ~/.copilot/ or ~/.claude/ unambiguously identifies
  # the target client without relying on which directories happen to exist.
  if [[ "${SCRIPT_DIR}" == "${COPILOT_BASE}"/* ]]; then
    CLIENT_PROFILE="copilot"
  elif [[ "${SCRIPT_DIR}" == "${CLAUDE_BASE}"/* ]]; then
    CLIENT_PROFILE="claude"
  else
    # Fallback: directory presence — but refuse to guess when both exist.
    HAS_COPILOT=0; HAS_CLAUDE=0
    [[ -n "${COPILOT_HOME:-}" || -d "${HOME}/.copilot" ]] && HAS_COPILOT=1
    [[ -n "${CLAUDE_HOME:-}"  || -d "${HOME}/.claude"  ]] && HAS_CLAUDE=1

    if [[ "${HAS_COPILOT}" == "1" && "${HAS_CLAUDE}" == "1" ]]; then
      echo "[mcprojsim] Error: both ~/.copilot and ~/.claude detected." >&2
      echo "[mcprojsim] Cannot determine target client automatically." >&2
      echo "[mcprojsim] Re-run with an explicit profile:" >&2
      echo "[mcprojsim]   MCP_CLIENT=copilot bash bootstrap.sh" >&2
      echo "[mcprojsim]   MCP_CLIENT=claude  bash bootstrap.sh" >&2
      exit 1
    elif [[ "${HAS_COPILOT}" == "1" ]]; then
      CLIENT_PROFILE="copilot"
    elif [[ "${HAS_CLAUDE}" == "1" ]]; then
      CLIENT_PROFILE="claude"
    else
      CLIENT_PROFILE="generic"
    fi
  fi
fi

case "${CLIENT_PROFILE}" in
  claude|Claude|CLAUDE)    CLIENT_PROFILE="claude"   ;;
  copilot|Copilot|COPILOT) CLIENT_PROFILE="copilot"  ;;
  *)                       CLIENT_PROFILE="generic"  ;;
esac

echo "[mcprojsim] Client profile : ${CLIENT_PROFILE}"

# ── Resolve config file path ───────────────────────────────────────────────────
case "${CLIENT_PROFILE}" in
  copilot)
    if [[ -n "${COPILOT_HOME:-}" ]]; then
      COPILOT_BASE="${COPILOT_HOME}"
    elif [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
      COPILOT_BASE="${XDG_CONFIG_HOME}/copilot"
    else
      COPILOT_BASE="${HOME}/.copilot"
    fi
    CONFIG_FILE="${COPILOT_BASE}/mcp-config.json"
    ;;
  claude)
    case "$(uname -s)" in
      Darwin) CLAUDE_CONFIG_DIR="${HOME}/Library/Application Support/Claude" ;;
      *)      CLAUDE_CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/claude" ;;
    esac
    CONFIG_FILE="${CLAUDE_CONFIG_DIR}/claude_desktop_config.json"
    ;;
  *)
    CONFIG_FILE=""
    ;;
esac

# ── Install the server ─────────────────────────────────────────────────────────
bash "${SCRIPT_DIR}/launcher.sh" --install-only
LAUNCHER_ABS="${SCRIPT_DIR}/launcher.sh"

# ── Write client config ────────────────────────────────────────────────────────
if [[ -z "${CONFIG_FILE}" ]]; then
  echo ""
  echo "[mcprojsim] Generic profile — add the following to your MCP client config:"
  echo ""
  printf '  {\n    "mcpServers": {\n      "mcprojsim": {\n        "command": "%s"\n      }\n    }\n  }\n' "${LAUNCHER_ABS}"
  echo ""
  exit 0
fi

MCPROJSIM_CONFIG_FILE="${CONFIG_FILE}" \
MCPROJSIM_LAUNCHER_ABS="${LAUNCHER_ABS}" \
MCPROJSIM_CLIENT="${CLIENT_PROFILE}" \
python3 - <<'PYEOF'
import json, os, sys

config_file = os.environ["MCPROJSIM_CONFIG_FILE"]
launcher    = os.environ["MCPROJSIM_LAUNCHER_ABS"]
client      = os.environ["MCPROJSIM_CLIENT"]

entries = {
    "copilot": {"type": "stdio", "command": launcher, "args": [], "tools": ["*"]},
    "claude":  {"command": launcher},
}
entry = entries.get(client, {"command": launcher})

if os.path.exists(config_file):
    with open(config_file) as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            print("[mcprojsim] Warning: existing config unreadable — overwriting.", file=sys.stderr)
            config = {}
else:
    config = {}

config.setdefault("mcpServers", {})["mcprojsim"] = entry

config_dir = os.path.dirname(config_file)
if config_dir:
    os.makedirs(config_dir, exist_ok=True)

with open(config_file, "w") as f:
    json.dump(config, f, indent=2)
    f.write("\n")

print(f"[mcprojsim] Config written : {config_file}")
PYEOF

echo ""
echo "[mcprojsim] ✓ Done. Restart your MCP client to activate the server."
EOF
chmod +x "${PAYLOAD_DIR}/bootstrap.sh"

OUTPUT_ZIP="${DIST_DIR}/${BUNDLE_STEM}.zip"
rm -f "${OUTPUT_ZIP}"
(
    cd "${TMP_DIR}"
    zip -qr "${OUTPUT_ZIP}" "${BUNDLE_STEM}"
)

echo "Created MCP bundle: ${OUTPUT_ZIP}"
