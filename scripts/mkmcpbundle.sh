#!/bin/bash
# MCP Bundle Builder
# Creates a versioned MCP server bundle zip with manifest + bootstrap script.
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
└── wheels/
    └── mcprojsim-${VERSION}-py3-none-any.whl
\`\`\`

  ## Prerequisites

  | Requirement | Version |
  |---|---|
  | Python | >= 3.14 |
  | Internet access | Required on first run to download runtime dependencies from PyPI |
  | bash | Any modern version |

## Installation — ONE-TIME SETUP

**This installation is permanent.** Once you complete the steps below, the mcprojsim MCP server will be available to your MCP client(s) automatically. You will only need to run the bootstrap script once.

### Step 1 — Extract the bundle

\`\`\`bash
unzip mcprojsim-mcp-bundle-${VERSION}.zip
cd mcprojsim-mcp-bundle-${VERSION}
\`\`\`

### Step 2 — Run bootstrap (one time)

\`\`\`bash
bash bootstrap.sh
\`\`\`

The bootstrap script will:
1. Detect the active client profile and install into a user-scoped root:
  - Claude: \`~/.claude/mcp/servers/mcprojsim\`
  - Copilot: \`~/.copilot/mcp/servers/mcprojsim\`
  - Generic MCP clients: \`~/.mcp/servers/mcprojsim\`
2. Create a Python venv at \`<install-root>/.venv\`
3. Install the bundled \`mcprojsim\` wheel and \`mcp[cli]>=1.0.0\`
4. Verify the server is running

**After Step 2 completes successfully, the MCP server is permanently installed.**
You do not need to run this bootstrap script again unless you are updating to a new bundle version.

If you re-run the script, it will detect the existing installation and skip reinstall.

### Explicit client selection (optional, one-time)

If auto-detection does not match your client, override it explicitly:

\`\`\`bash
# Force Claude profile (one time only)
MCP_CLIENT=claude bash bootstrap.sh

# Force Copilot profile (one time only)
MCP_CLIENT=copilot bash bootstrap.sh

# Force generic profile (one time only)
MCP_CLIENT=generic bash bootstrap.sh
\`\`\`

After running once with your chosen profile, the server is permanently installed.

### Explicit install root (optional)

\`\`\`bash
MCPROJSIM_MCP_HOME=/my/custom/path/mcprojsim-mcp bash bootstrap.sh
\`\`\`

## After Installation

Once the bootstrap completes successfully, your MCP server is permanently installed and running.
You may now need to configure your MCP client to use the server (see below).

## Configuring Your MCP Client

After running \`bootstrap.sh\`, configure your client to connect to the server.

### Claude Desktop

1. Open the Claude Desktop configuration file:
   \`\`\`bash
   open ~/Library/Application\\ Support/Claude/claude_desktop_config.json
   \`\`\`

2. Add (or update) the mcprojsim server entry:
   \`\`\`json
   {
     "mcpServers": {
       "mcprojsim": {
         "command": "/absolute/path/to/mcprojsim-mcp-bundle-${VERSION}/bootstrap.sh"
       }
     }
   }
   \`\`\`
   Replace \`/absolute/path/to/mcprojsim-mcp-bundle-${VERSION}\` with the full path to your extracted bundle.

3. Save the file. Claude Desktop will automatically restart and load the server.

### Copilot / VS Code Agent

Copilot in VS Code typically auto-discovers MCP servers via the MCP client protocol.
If you need explicit configuration:

1. Open VS Code settings (\`Cmd+,\`).
2. Search for \`MCP\` or \`mcpServers\`.
3. Add your server:
   \`\`\`json
   "mcpServers": {
     "mcprojsim": {
       "command": "/absolute/path/to/mcprojsim-mcp-bundle-${VERSION}/bootstrap.sh"
     }
   }
   \`\`\`

4. Reload VS Code. The server will be available immediately.

### Generic MCP Clients

For any other MCP-compatible client, update your client's MCP server configuration
to include:

\`\`\`json
{
  "mcpServers": {
    "mcprojsim": {
      "command": "/absolute/path/to/mcprojsim-mcp-bundle-${VERSION}/bootstrap.sh"
    }
  }
}
\`\`\`

Refer to your client's MCP configuration documentation for the exact location
and format of this configuration file.

## Automated Installation for Agents

An automation agent can install and configure this server with:

\`\`\`bash
BUNDLE_DIR="\$(cd "\$(dirname bootstrap.sh)" && pwd)"
BOOTSTRAP="\${BUNDLE_DIR}/bootstrap.sh"

# Step 1: Run bootstrap in background to install
bash "\${BOOTSTRAP}" &
MCP_PID=\$!
sleep 2 && kill "\${MCP_PID}" 2>/dev/null || true

# Step 2: Read the manifest
cat "\${BUNDLE_DIR}/manifest.json"

# Step 3: Configure the client with BOOTSTRAP path
# (update client config with "command": "\${BOOTSTRAP}")
\`\`\`

Then update your MCP client config with the absolute \`\${BOOTSTRAP}\` path as the command.

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
2. Update the MCP client \`command\` path to the new \`bootstrap.sh\`.
3. Restart the MCP client.

The old install root can be removed after confirming the new version works.

## Troubleshooting

### Bootstrap Issues

**"No mcprojsim wheel found in bundle wheels/ directory."**
- Re-extract the bundle zip file completely.
- Verify that \`wheels/mcprojsim-${VERSION}-py3-none-any.whl\` exists in the extracted directory.
- If the wheel is still missing, the zip may be corrupted. Download and extract the bundle again.

**"python3: command not found"**
- Set \`PYTHON_CMD\` to an explicit Python 3.14 path and re-run bootstrap:
  \`\`\`bash
  PYTHON_CMD=/usr/local/bin/python3.14 bash bootstrap.sh
  \`\`\`
- If you don't know where Python is installed, find it with:
  \`\`\`bash
  which python3
  # or
  which python3.14
  \`\`\`

**pip install fails with network error**
- The first bootstrap run downloads dependencies from PyPI. Ensure you have internet connectivity.
- If behind a corporate proxy, configure pip to use your proxy:
  \`\`\`bash
  pip install --proxy [user:passwd@]proxy.server:port ...
  \`\`\`
- Or set environment variables:
  \`\`\`bash
  HTTP_PROXY=http://proxy.server:port HTTPS_PROXY=http://proxy.server:port bash bootstrap.sh
  \`\`\`

**Installation hangs or takes a long time**
- The first run may take 1-2 minutes while downloading and installing dependencies.
- If it hangs, interrupt (Ctrl+C) and re-run with verbose output:
  \`\`\`bash
  bash -x bootstrap.sh
  \`\`\`

### Client Configuration Issues

**MCP client cannot start server (Claude, Copilot, etc.)**
- Verify the \`command\` path in your client config points to the correct \`bootstrap.sh\`:
  \`\`\`bash
  ls -l /path/to/bootstrap.sh
  \`\`\`
- Confirm the path is absolute (starts with \`/\`), not relative.
- Restart your client after updating the configuration.

**Server appears in configuration but doesn't connect**
- Check that the bootstrap script is executable:
  \`\`\`bash
  chmod +x /path/to/bootstrap.sh
  \`\`\`
- Verify the installed server can start manually:
  \`\`\`bash
  /path/to/bootstrap.sh --help
  \`\`\`
- Check your client's logs for error messages (e.g., \`~/.claude/logs\` for Claude).

**Claude Desktop reports "Server crashed" or similar**
- The server may not be finding its venv. Verify the install root exists:
  \`\`\`bash
  ls -la ~/.claude/mcp/servers/mcprojsim/
  \`\`\`
- If missing, re-run bootstrap:
  \`\`\`bash
  cd /path/to/mcprojsim-mcp-bundle-${VERSION}
  bash bootstrap.sh
  \`\`\`

**"Permission denied" when running bootstrap**
- Make the script executable:
  \`\`\`bash
  chmod +x bootstrap.sh
  bash bootstrap.sh
  \`\`\`

### Server Not Appearing in Client

**Agent doesn't see mcprojsim tools**
1. Confirm it's installed:
   \`\`\`bash
   ls ~/.claude/mcp/servers/mcprojsim/   # for Claude
   ls ~/.copilot/mcp/servers/mcprojsim/  # for Copilot
   \`\`\`
2. Confirm it's in the client config with the correct command path.
3. Restart the client (close and reopen).
4. Check the client's MCP server status (e.g., in Copilot's settings, look for MCP server list).

### Getting Help

If you encounter other issues:
1. Check that \`bootstrap.sh\` runs without errors:
   \`\`\`bash
   cd /path/to/mcprojsim-mcp-bundle-${VERSION}
   bash bootstrap.sh
   \`\`\`
2. Verify the Python venv was created and has the server installed:
   \`\`\`bash
   ~/.claude/mcp/servers/mcprojsim/.venv/bin/mcprojsim-mcp --help
   \`\`\`
3. Run with bash debug mode for detailed logging:
   \`\`\`bash
   bash -x bootstrap.sh 2>&1 | tail -50
   \`\`\`
EOF

cat > "${PAYLOAD_DIR}/bootstrap.sh" <<'EOF'
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
    echo "[mcprojsim] Installation complete. Server is now permanently available." >&2
else
    echo "[mcprojsim] Already installed at ${INSTALL_ROOT}. Starting server..." >&2
fi

exec "${VENV_DIR}/bin/mcprojsim-mcp" "$@"
EOF
chmod +x "${PAYLOAD_DIR}/bootstrap.sh"

OUTPUT_ZIP="${DIST_DIR}/${BUNDLE_STEM}.zip"
rm -f "${OUTPUT_ZIP}"
(
    cd "${TMP_DIR}"
    zip -qr "${OUTPUT_ZIP}" "${BUNDLE_STEM}"
)

echo "Created MCP bundle: ${OUTPUT_ZIP}"
