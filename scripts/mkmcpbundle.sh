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

This self-contained bundle installs the **mcprojsim** MCP server so that
AI assistants (GitHub Copilot, Claude Desktop, and any other MCP-compatible
client) can generate, validate, and simulate software project schedules using
Monte Carlo analysis.

---

## Bundle Contents

\`\`\`
mcprojsim-mcp-bundle-${VERSION}/
├── README.md          ← this file
├── manifest.json      ← bundle metadata
├── bootstrap.sh       ← install + launch script
└── wheels/
    └── mcprojsim-${VERSION}-py3-none-any.whl
\`\`\`

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.14 |
| Internet access | Required on first run — pip downloads mcprojsim's runtime dependencies (numpy, scipy, matplotlib, pydantic, click, jinja2, etc.) and \`mcp[cli]\` from PyPI |
| bash | Any modern version |

---

## Installation

### Step 1 — Extract the bundle

\`\`\`bash
unzip mcprojsim-mcp-bundle-${VERSION}.zip
cd mcprojsim-mcp-bundle-${VERSION}
\`\`\`

### Step 2 — Run bootstrap (installs dependencies and the server)

\`\`\`bash
bash bootstrap.sh
\`\`\`

The bootstrap script:
1. Creates a Python virtual environment at \`.venv/\` inside the bundle directory
   (all packages are installed there — nothing is written to the system Python)
2. Installs the bundled \`mcprojsim\` wheel from \`wheels/\`
3. pip automatically resolves and downloads mcprojsim's runtime dependencies
   from PyPI: \`numpy\`, \`scipy\`, \`matplotlib\`, \`pydantic\`, \`click\`,
   \`jinja2\`, \`pyyaml\`, \`tabulate\`, \`tomli-w\`
4. Downloads and installs \`mcp[cli]>=1.0.0\` and its dependencies from PyPI
5. Starts the MCP server process via the \`mcprojsim-mcp\` entry point

Re-running \`bootstrap.sh\` is safe — it skips installation if the venv already exists.

### Custom venv location (optional)

\`\`\`bash
MCPROJSIM_MCP_VENV=/opt/mcprojsim-venv bash bootstrap.sh
\`\`\`

### Custom Python interpreter (optional)

\`\`\`bash
PYTHON_CMD=python3.14 bash bootstrap.sh
\`\`\`

---

## Configure Your MCP Client

Copy the absolute path to \`bootstrap.sh\` (e.g. \`/path/to/mcprojsim-mcp-bundle-${VERSION}/bootstrap.sh\`)
and add it to your client's MCP configuration.

### VS Code — \`.vscode/mcp.json\`

\`\`\`json
{
  "servers": {
    "mcprojsim": {
      "type": "stdio",
      "command": "/ABSOLUTE/PATH/TO/mcprojsim-mcp-bundle-${VERSION}/bootstrap.sh"
    }
  }
}
\`\`\`

### VS Code — \`settings.json\` (user or workspace)

\`\`\`json
{
  "mcp": {
    "servers": {
      "mcprojsim": {
        "type": "stdio",
        "command": "/ABSOLUTE/PATH/TO/mcprojsim-mcp-bundle-${VERSION}/bootstrap.sh"
      }
    }
  }
}
\`\`\`

### Claude Desktop — \`claude_desktop_config.json\`

\`\`\`json
{
  "mcpServers": {
    "mcprojsim": {
      "command": "/ABSOLUTE/PATH/TO/mcprojsim-mcp-bundle-${VERSION}/bootstrap.sh"
    }
  }
}
\`\`\`

---

## Automated Installation for AI Agents

An AI agent (e.g., a remote Copilot chat session) can install and configure
this server by following these instructions verbatim.

### Agent installation procedure

1. Locate the extracted bundle directory.  The \`manifest.json\` and
   \`bootstrap.sh\` files must be present at its root.

2. Determine the absolute path to \`bootstrap.sh\`:
   \`\`\`bash
   BUNDLE_DIR="\$(cd "\$(dirname bootstrap.sh)" && pwd)"
   BOOTSTRAP="\${BUNDLE_DIR}/bootstrap.sh"
   \`\`\`

3. Run the bootstrap to install the venv and start the server once to verify
   it launches:
   \`\`\`bash
   bash "\${BOOTSTRAP}" &
   MCP_PID=\$!
   sleep 2 && kill "\${MCP_PID}" 2>/dev/null || true
   \`\`\`

4. Read \`manifest.json\` to confirm metadata:
   \`\`\`bash
   cat "\${BUNDLE_DIR}/manifest.json"
   # Expected: name=mcprojsim, version=${VERSION}, entrypoint=mcprojsim-mcp
   \`\`\`

5. Determine the correct MCP config file for the active client:
   - **VS Code workspace**: \`.vscode/mcp.json\` (create if absent)
   - **VS Code user settings**: \`~/Library/Application Support/Code/User/settings.json\` (macOS)
   - **Claude Desktop**: \`~/Library/Application Support/Claude/claude_desktop_config.json\` (macOS)

6. Insert (or merge) the following server entry, replacing the path:
   \`\`\`json
   {
     "servers": {
       "mcprojsim": {
         "type": "stdio",
         "command": "\${BOOTSTRAP}"
       }
     }
   }
   \`\`\`

7. Reload the MCP client so it picks up the new server.

---

## Available MCP Tools

Once connected, the following tools are available to the AI assistant.

### \`generate_project_file\`

Converts a plain-text project description into a valid \`mcprojsim\` YAML
project specification.

**Input:** \`description\` (string) — semi-structured text with project name,
start date, numbered tasks, sizing estimates (T-shirt or story points), and
optional resource/calendar definitions.

**Returns:** YAML project file content ready to pass to \`mcprojsim simulate\`.

**Example call:**
\`\`\`
generate_project_file(description=\"\"\"
Project name: Portal Redesign
Start date: 2026-04-01

Task 1:
- Design mockups
- Size: M

Task 2:
- Backend API
- Depends on Task 1
- Size: XL

Task 3:
- Frontend integration
- Depends on Task 2
- Size: L
\"\"\")
\`\`\`

---

### \`validate_project_description\`

Checks a project description for parse errors and missing fields without
generating a file.

**Input:** \`description\` (string)

**Returns:** Validation report listing any warnings or errors.

---

### \`simulate_project\`

Parses a project description and immediately runs a Monte Carlo simulation,
returning statistics, confidence intervals, delivery dates, critical paths,
sensitivity analysis, schedule slack, and risk impact.

**Inputs:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| \`description\` | string | required | Plain-text project description |
| \`iterations\` | int | 10000 | Number of Monte Carlo iterations |
| \`seed\` | int or null | null | Random seed for reproducibility |
| \`config_yaml\` | string or null | null | Optional YAML config overrides |

**Returns:** Multi-section text report including generated YAML, statistics,
percentile delivery dates, sensitivity correlation, schedule slack,
risk impact, and most-frequent critical paths.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| \`MCPROJSIM_MCP_VENV\` | \`<bundle>/.venv\` | Override the venv location |
| \`PYTHON_CMD\` | \`python3\` | Override the Python interpreter used to create the venv |

---

## Updating the Server

To upgrade to a newer bundle version:

1. Download and extract the new bundle zip.
2. Update the \`command\` path in your MCP config to point to the new
   \`bootstrap.sh\`.
3. Restart your MCP client.

The old venv directory can be deleted once you are satisfied with the upgrade.

---

## Troubleshooting

**"No mcprojsim wheel found in bundle wheels/ directory."**
The \`wheels/\` directory is empty or the zip was extracted incorrectly.
Re-extract the zip and verify \`wheels/mcprojsim-${VERSION}-py3-none-any.whl\` is present.

**"python3: command not found"**
Python 3.14 is not on your PATH. Install it or set \`PYTHON_CMD\`:
\`\`\`bash
PYTHON_CMD=/usr/local/bin/python3.14 bash bootstrap.sh
\`\`\`

**pip install fails with network error**
The bootstrap script downloads \`mcp[cli]\` from PyPI on first run.
Ensure the machine has internet access, or pre-populate the venv manually:
\`\`\`bash
pip install --target . "mcp[cli]>=1.0.0"
\`\`\`

**MCP client shows "server not found"**
Verify the \`command\` path in your config is the absolute path to \`bootstrap.sh\`
and that the file is executable (\`chmod +x bootstrap.sh\`).

---

## License

MIT — see the project repository for full license text:
https://github.com/johan162/mcprojsim
EOF

cat > "${PAYLOAD_DIR}/bootstrap.sh" <<'EOF'
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${MCPROJSIM_MCP_VENV:-${SCRIPT_DIR}/.venv}"
PYTHON_CMD="${PYTHON_CMD:-python3}"
WHEEL_PATH="$(ls "${SCRIPT_DIR}"/wheels/mcprojsim-*.whl | head -n 1)"

if [[ -z "${WHEEL_PATH}" ]]; then
    echo "Error: no mcprojsim wheel found in bundle wheels/ directory." >&2
    exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    "${PYTHON_CMD}" -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install "${WHEEL_PATH}" "mcp[cli]>=1.0.0"
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
