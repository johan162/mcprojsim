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

cat > "${PAYLOAD_DIR}/README.md" <<EOF
# mcprojsim MCP Server Bundle — v${VERSION}

This bundle installs the **mcprojsim** MCP server for any MCP-compatible client.
Installation is user-scoped by default and does not depend on any editor.

## Bundle Contents

\`\`\`
mcprojsim-mcp-bundle-${VERSION}/
├── README.md
├── manifest.json
├── bootstrap.sh
├── launcher.sh
└── wheels/
    └── mcprojsim-${VERSION}-py3-none-any.whl
\`\`\`

  ## Prerequisites

  | Requirement | Version |
  |---|---|
  | Python | >= 3.13 |
  | Internet access | Required on first run to download runtime dependencies from PyPI |
  | bash | Any modern version |

## How \`launcher.sh\` works

\`launcher.sh\` serves two roles in one script:

1. **Installer** — on first run it creates a Python venv and installs \`mcprojsim\` into it.
2. **Server launcher** — on every run it \`exec\`s the installed \`mcprojsim-mcp\` binary.

Because of this dual role, **your MCP client's \`command\` must always point to \`launcher.sh\`**
— not directly to the binary. The client calls \`command\` every time it needs to start the
server. \`launcher.sh\` handles install-if-needed automatically.

### \`--install-only\` flag

Pass \`--install-only\` to install the server and exit cleanly, **without starting the server**:

\`\`\`bash
bash launcher.sh --install-only
\`\`\`

Use this flag when:
- Pre-installing before the first client start
- Verifying the installation from the command line
- Automating installation from a script or agent

Without this flag, \`launcher.sh\` starts the MCP server process (which speaks JSON-RPC on
stdin/stdout and runs until the client disconnects). This is correct when called by an MCP
client, but will appear to hang if run manually in a terminal.

## How \`bootstrap.sh\` works

\`bootstrap.sh\` is the recommended one-step installer. It:

1. **Detects your MCP client** using a two-stage strategy:
   - **Primary (location-based):** if the bundle lives inside \`~/.copilot/\` or \`~/.claude/\`,
     the target client is known with certainty — no guessing required.
   - **Fallback (directory presence):** if the bundle is in a neutral location, it checks
     whether \`~/.copilot\` or \`~/.claude\` exist. If **both** exist it stops and asks you to
     set \`MCP_CLIENT\` explicitly rather than silently picking the wrong one.
   - Override at any time with \`MCP_CLIENT=<profile>\`.
2. **Installs the server** — calls \`launcher.sh --install-only\` to create the venv and
   install \`mcprojsim\`.
3. **Writes the client config** — merges the \`mcprojsim\` server entry into the correct
   config file for the detected client:
   - Copilot CLI: \`~/.copilot/mcp-config.json\`
   - Claude Desktop: \`~/Library/Application Support/Claude/claude_desktop_config.json\` (macOS)
     or \`~/.config/claude/claude_desktop_config.json\` (Linux)
   - Generic: prints a config snippet to paste manually

The cleanest setup is to place the bundle **inside the target client's home directory**
so detection is always unambiguous:

\`\`\`bash
~/.copilot/mcp/bundle/mcprojsim-mcp-bundle-${VERSION}/   # Copilot CLI
~/.claude/mcp/bundle/mcprojsim-mcp-bundle-${VERSION}/    # Claude Desktop
\`\`\`

Run \`bootstrap.sh\` on first install and again when upgrading to a new bundle version.

## Installation

### Quick Install (Recommended)

Extract the bundle into your client's home directory and run \`bootstrap.sh\`:

\`\`\`bash
unzip mcprojsim-mcp-bundle-${VERSION}.zip

# Copilot CLI (recommended path — enables unambiguous auto-detection):
mkdir -p ~/.copilot/mcp/bundle
mv mcprojsim-mcp-bundle-${VERSION} ~/.copilot/mcp/bundle/
cd ~/.copilot/mcp/bundle/mcprojsim-mcp-bundle-${VERSION}

# Claude Desktop:
# mkdir -p ~/.claude/mcp/bundle
# mv mcprojsim-mcp-bundle-${VERSION} ~/.claude/mcp/bundle/
# cd ~/.claude/mcp/bundle/mcprojsim-mcp-bundle-${VERSION}

bash bootstrap.sh
\`\`\`

\`bootstrap.sh\` detects your client from its own location, installs the server, and writes
the config file. Restart your MCP client when done.

If you place the bundle in a neutral location (e.g. \`~/.local/share/\`) and only one client
is installed, detection still works automatically. If both \`~/.copilot\` and \`~/.claude\`
exist, set the profile explicitly:

\`\`\`bash
MCP_CLIENT=copilot bash bootstrap.sh   # Copilot CLI
MCP_CLIENT=claude  bash bootstrap.sh   # Claude Desktop
MCP_CLIENT=generic bash bootstrap.sh   # install only, print config snippet
\`\`\`

### Manual Installation

If you prefer full control over each step:

#### Step 1 — Extract and place the bundle

\`\`\`bash
unzip mcprojsim-mcp-bundle-${VERSION}.zip
mv mcprojsim-mcp-bundle-${VERSION} ~/.local/share/mcprojsim-mcp-bundle-${VERSION}
cd ~/.local/share/mcprojsim-mcp-bundle-${VERSION}
\`\`\`

#### Step 2 — Pre-install the server

\`\`\`bash
bash launcher.sh --install-only
\`\`\`

The script will install the server, print the binary path, and exit — without starting
the server. You can verify the result:

\`\`\`bash
~/.copilot/mcp/servers/mcprojsim/.venv/bin/mcprojsim-mcp --version  # Copilot CLI
~/.claude/mcp/servers/mcprojsim/.venv/bin/mcprojsim-mcp --version   # Claude
\`\`\`

#### Step 3 — Configure your MCP client manually

Point your MCP client's \`command\` at \`launcher.sh\` in the extracted folder (see
**Configuring Your MCP Client** below). Subsequent starts skip the install and launch
immediately.

### Explicit client selection (optional)

If auto-detection does not match your client, override it explicitly:

\`\`\`bash
MCP_CLIENT=claude  bash launcher.sh --install-only
MCP_CLIENT=copilot bash launcher.sh --install-only
MCP_CLIENT=generic bash launcher.sh --install-only
\`\`\`

### Explicit install root (optional)

\`\`\`bash
MCPROJSIM_MCP_HOME=/my/custom/path/mcprojsim bash bootstrap.sh
\`\`\`

## After Installation

The server installs into a user-scoped venv under the detected client profile:
- Claude:   \`~/.claude/mcp/servers/mcprojsim/.venv\`
- Copilot:  \`~/.copilot/mcp/servers/mcprojsim/.venv\`
- Generic:  \`~/.mcp/servers/mcprojsim/.venv\`

Configure your MCP client to use \`launcher.sh\` as the server command (see below).

## Configuring Your MCP Client

The MCP client starts the server by running \`command\` each session. Set \`command\` to
the absolute path of \`launcher.sh\` — it handles install-if-needed then launches the
server via \`exec\`, making it both the installer and the persistent launcher.

### Claude Desktop

1. Open the Claude Desktop configuration file:
   \`\`\`bash
   open ~/Library/Application\\ Support/Claude/claude_desktop_config.json
   \`\`\`

2. Add (or update) the mcprojsim server entry using the **absolute path** to \`launcher.sh\`:
   \`\`\`json
   {
     "mcpServers": {
       "mcprojsim": {
         "command": "/absolute/path/to/mcprojsim-mcp-bundle-${VERSION}/launcher.sh"
       }
     }
   }
   \`\`\`

3. Save the file and restart Claude Desktop. The server installs and starts automatically.

### Copilot / VS Code Agent

1. Open VS Code settings (\`Cmd+,\`).
2. Search for \`MCP\` or \`mcpServers\`.
3. Add the server entry using the **absolute path** to \`launcher.sh\`:
   \`\`\`json
   "mcpServers": {
     "mcprojsim": {
       "command": "/absolute/path/to/mcprojsim-mcp-bundle-${VERSION}/launcher.sh"
     }
   }
   \`\`\`
4. Reload VS Code.

### Generic MCP Clients

\`\`\`json
{
  "mcpServers": {
    "mcprojsim": {
      "command": "/absolute/path/to/mcprojsim-mcp-bundle-${VERSION}/launcher.sh"
    }
  }
}
\`\`\`

Refer to your client's MCP configuration documentation for the exact location
and format of this configuration file.

## Automated Installation for Agents

An automation agent can install and configure this server with a single command:

\`\`\`bash
unzip mcprojsim-mcp-bundle-${VERSION}.zip
mkdir -p ~/.copilot/mcp/bundle
mv mcprojsim-mcp-bundle-${VERSION} ~/.copilot/mcp/bundle/
bash ~/.copilot/mcp/bundle/mcprojsim-mcp-bundle-${VERSION}/bootstrap.sh
\`\`\`

Placing the bundle inside \`~/.copilot/\` guarantees unambiguous client detection — no
\`MCP_CLIENT\` override needed even when multiple clients are installed. For more
granular control:

\`\`\`bash
BUNDLE_DIR="\${HOME}/.copilot/mcp/bundle/mcprojsim-mcp-bundle-${VERSION}"

# Install + configure in one step
bash "\${BUNDLE_DIR}/bootstrap.sh"

# Or: install only, then write the client config manually
bash "\${BUNDLE_DIR}/launcher.sh" --install-only
# Add "command": "\${BUNDLE_DIR}/launcher.sh" to your MCP client config

# Read the manifest for version metadata
cat "\${BUNDLE_DIR}/manifest.json"
\`\`\`

## Available MCP Tools

Once connected, the MCP server exposes these tools:

### \`generate_project_file\`

Converts a plain-text project description into valid \`mcprojsim\` YAML.

Input:
- \`description\` (string): semi-structured project text

Output:
- YAML project file content

Example input:
\`\`\`
Project name: Portal Redesign
Start date: 2026-04-01

Task 1:
- Design mockups
- Size: M

Task 2:
- Backend API
- Depends on Task 1
- Size: XL
\`\`\`

Example output (truncated):
\`\`\`yaml
name: Portal Redesign
start_date: 2026-04-01
tasks:
  - id: task_1
    name: Design mockups
    t_shirt_size: M
  - id: task_2
    name: Backend API
    t_shirt_size: XL
    dependencies: [task_1]
\`\`\`

Example input:

Even some quite unstructured descriptions can be parsed:

\`\`\`
Simulate a project that starts at 2026-05-01 and have two tasks, task 1 and task 2. Both tasks has size
  "M". Task 2 depends on Task 1. What date are we 95% sure the work is done?
\`\`\`

Example output:

\`\`\`txt
For the dependency chain Task 1 -> Task 2, the P95 completion date is 2026-06-24.

So you’re about 95% confident the project is done by June 24, 2026.
\`\`\`


### \`validate_project_description\`

Checks a project description for parse issues without generating a file.

Input:
- \`description\` (string)

Output:
- Validation result text (errors/warnings or valid status)

Example output:
\`\`\`
Validation issues:
  - WARNING: No start date specified.
\`\`\`

### \`simulate_project\`

Generates a project model from text and runs Monte Carlo simulation directly.

Inputs:
- \`description\` (string, required)
- \`iterations\` (int, default: 10000)
- \`seed\` (int or null, default: null)
- \`config_yaml\` (string or null, default: null)

Output:
- Multi-section report with generated YAML, percentiles, dates, sensitivity,
  slack, risk impact, and critical paths

Example output excerpt:
\`\`\`
=== Simulation Results ===
Project: Portal Redesign
Iterations: 10000
Mean: 842.31 hours
Median (P50): 821.45 hours
Confidence Intervals:
  P50: 821.45 hours
  P80: 943.20 hours
  P90: 1012.76 hours
\`\`\`

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| \`MCP_CLIENT\` | auto-detected | Client profile: \`claude\`, \`copilot\`, or \`generic\` |
| \`MCPROJSIM_MCP_HOME\` | profile-specific | Override install root directly |
| \`MCPROJSIM_MCP_VENV\` | \`<MCPROJSIM_MCP_HOME>/.venv\` | Override venv location |
| \`CLAUDE_HOME\` | \`~/.claude\` | Base Claude home directory |
| \`COPILOT_HOME\` | \`~/.copilot\` | Base Copilot home directory |
| \`MCP_CLIENT_HOME\` | unset | Base home for generic MCP profile |
| \`XDG_CONFIG_HOME\` | platform default | Fallback base for profile directories |
| \`PYTHON_CMD\` | \`python3\` | Python executable used to create the venv |

## Updating the Server

To upgrade to a newer bundle version:
1. Download and extract the new bundle zip.
2. Move it to a permanent location and run \`bash bootstrap.sh\` in the new bundle directory.
3. Restart the MCP client.

The old install root can be removed after confirming the new version works.

## Troubleshooting

### Bootstrap Issues

**"No mcprojsim wheel found in bundle wheels/ directory."**
- Re-extract the bundle zip file completely.
- Verify that \`wheels/mcprojsim-${VERSION}-py3-none-any.whl\` exists in the extracted directory.
- If the wheel is still missing, the zip may be corrupted. Download and extract the bundle again.

**"python3: command not found"**
- Set \`PYTHON_CMD\` to an explicit Python 3.13 path and re-run the launcher:
  \`\`\`bash
  PYTHON_CMD=/usr/local/bin/python3.13 bash launcher.sh
  \`\`\`
- If you don't know where Python is installed, find it with:
  \`\`\`bash
  which python3
  # or
  which python3.13
  \`\`\`

**pip install fails with network error**
- The first launcher run downloads dependencies from PyPI. Ensure you have internet connectivity.
- If behind a corporate proxy, configure pip to use your proxy:
  \`\`\`bash
  pip install --proxy [user:passwd@]proxy.server:port ...
  \`\`\`
- Or set environment variables:
  \`\`\`bash
  HTTP_PROXY=http://proxy.server:port HTTPS_PROXY=http://proxy.server:port bash launcher.sh --install-only
  \`\`\`

**Installation hangs or takes a long time**
- Use \`--install-only\` so the script exits after installation instead of starting the server:
  \`\`\`bash
  bash launcher.sh --install-only
  \`\`\`
- The first run may take 1-2 minutes while downloading and installing dependencies.
- If it still hangs, interrupt (Ctrl+C) and re-run with verbose output:
  \`\`\`bash
  bash -x launcher.sh --install-only
  \`\`\`

### Client Configuration Issues

**MCP client cannot start server (Claude, Copilot, etc.)**
- Verify the \`command\` path in your client config points to the correct \`launcher.sh\`:
  \`\`\`bash
  ls -l /path/to/launcher.sh
  \`\`\`
- Confirm the path is absolute (starts with \`/\`), not relative.
- Restart your client after updating the configuration.

**Server appears in configuration but doesn't connect**
- Check that the launcher script is executable:
  \`\`\`bash
  chmod +x /path/to/launcher.sh
  \`\`\`
- Verify the server is installed correctly:
  \`\`\`bash
  bash /path/to/launcher.sh --install-only
  \`\`\`
- Check your client's logs for error messages (e.g., \`~/.claude/logs\` for Claude).

**Claude Desktop reports "Server crashed" or similar**
- The server may not be finding its venv. Verify the install root exists:
  \`\`\`bash
  ls -la ~/.claude/mcp/servers/mcprojsim/
  \`\`\`
- If missing, re-run the launcher to reinstall:
  \`\`\`bash
  cd /path/to/mcprojsim-mcp-bundle-${VERSION}
  bash launcher.sh --install-only
  \`\`\`

**"Permission denied" when running launcher**
- Make the script executable:
  \`\`\`bash
  chmod +x launcher.sh
  bash launcher.sh --install-only
  \`\`\`

### Server Not Appearing in Client

**Agent doesn't see mcprojsim tools**
1. Confirm it's installed:
   \`\`\`bash
   ls ~/.claude/mcp/servers/mcprojsim/   # for Claude
   ls ~/.copilot/mcp/servers/mcprojsim/  # for Copilot
   \`\`\`
2. Confirm it's in the client config with the correct absolute path to \`launcher.sh\`.
3. Restart the client (close and reopen).
4. Check the client's MCP server status (e.g., in Copilot's settings, look for MCP server list).

### Getting Help

If you encounter other issues:
1. Re-run \`bootstrap.sh\` (or \`launcher.sh --install-only\`) to check for errors:
   \`\`\`bash
   cd /path/to/mcprojsim-mcp-bundle-${VERSION}
   bash bootstrap.sh
   \`\`\`
2. Verify the Python venv was created and has the server installed:
   \`\`\`bash
   ~/.claude/mcp/servers/mcprojsim/.venv/bin/mcprojsim-mcp --version
   \`\`\`
3. Run with bash debug mode for detailed logging:
   \`\`\`bash
   bash -x launcher.sh --install-only 2>&1 | tail -50
   \`\`\`
EOF

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
