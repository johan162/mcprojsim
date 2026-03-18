#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# gen-examples.sh — Generate docs/examples.md from docs/examples_template.md
#
# Expands two placeholder types (each must be on its own line):
#
#   {{file:path}}    → Inserts file contents in a fenced code block.
#                      Language tag is auto-detected from the extension.
#
#   {{run:command}}   → Emits a ```bash block showing the user-facing
#                      command (with "poetry run" and internal paths
#                      stripped), then executes the command and inserts
#                      the captured output in a ```text block.
#
# Multiple {{run:...}} placeholders can reference the same input file
# with different CLI flags to showcase different options.
#
# Usage:
#   scripts/gen-examples.sh [template] [output]
#   make gen-examples
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

TEMPLATE="${1:-docs/examples_template.md}"
OUTPUT="${2:-docs/examples.md}"
WORK_DIR=".build/gen-examples"

mkdir -p "$WORK_DIR"

file_count=0
run_count=0
errors=0

# Detect code-fence language from file extension
fence_lang() {
    case "${1##*.}" in
        yaml|yml) echo "yaml" ;;
        txt)      echo "text" ;;
        py)       echo "python" ;;
        json)     echo "json" ;;
        sh|bash)  echo "bash" ;;
        toml)     echo "toml" ;;
        *)        echo "" ;;
    esac
}

# Build user-facing display command from an internal {{run:...}} command.
# Strips "poetry run ", redirects, and splits && chains into separate lines.
display_cmd() {
    local raw="$1"
    # Split on ' && ', clean each part
    local IFS_BAK="$IFS"
    local result=""
    while IFS= read -r part; do
        # Strip leading/trailing whitespace
        part="${part#"${part%%[![:space:]]*}"}"
        part="${part%"${part##*[![:space:]]}"}"
        # Strip redirects  (>/dev/null 2>&1  or  2>/dev/null  etc.)
        part=$(echo "$part" | sed -E 's| *[12]?>[^ ]*||g')
        # Strip "poetry run " prefix
        part="${part#poetry run }"
        [[ -n "$part" ]] && result+="$part"$'\n'
    done <<< "${raw// && /$'\n'}"
    IFS="$IFS_BAK"
    # Remove trailing newline
    printf '%s' "${result%$'\n'}"
}

echo "Generating $OUTPUT from $TEMPLATE ..." >&2

{
    # Auto-generated header
    echo "<!-- AUTO-GENERATED FILE — DO NOT EDIT -->"
    echo "<!-- Source: $TEMPLATE -->"
    echo "<!-- Regenerate with: make gen-examples -->"
    echo ""

    while IFS= read -r line || [[ -n "$line" ]]; do

        # ── {{file:relative/path}} ──────────────────────────────────────
        if [[ "$line" =~ ^[[:space:]]*\{\{file:([^}]+)\}\}[[:space:]]*$ ]]; then
            fpath="${BASH_REMATCH[1]}"
            lang=$(fence_lang "$fpath")
            if [[ -f "$fpath" ]]; then
                echo '```'"$lang"
                cat "$fpath"
                echo '```'
                file_count=$((file_count + 1))
                echo "  ✓ file: $fpath" >&2
            else
                echo "<!-- ERROR: file not found: $fpath -->" 
                echo "  ✗ file not found: $fpath" >&2
                errors=$((errors + 1))
            fi

        # ── {{run:shell command}} ───────────────────────────────────────
        elif [[ "$line" =~ ^[[:space:]]*\{\{run:(.+)\}\}[[:space:]]*$ ]]; then
            cmd="${BASH_REMATCH[1]}"
            # Emit user-facing command display
            echo '```bash'
            display_cmd "$cmd"
            echo ""
            echo '```'
            echo ""
            # Execute and emit output
            echo '```text'
            if output=$(eval "$cmd" 2>/dev/null); then
                # Strip version banner, progress lines, and leading blank lines
                cleaned=$(printf '%s\n' "$output" \
                    | grep -v '^mcprojsim, version ' \
                    | grep -v '^Progress: ' \
                    | sed '/./,$!d')
                printf '%s\n' "$cleaned"
            else
                printf '%s\n' "$output"
                echo "  ⚠  non-zero exit: $cmd" >&2
            fi
            echo '```'
            run_count=$((run_count + 1))
            echo "  ✓ run:  ${cmd:0:72}…" >&2

        # ── Plain line (pass-through) ───────────────────────────────────
        else
            printf '%s\n' "$line"
        fi

    done < "$TEMPLATE"
} > "$OUTPUT"

echo "" >&2
echo "✓ Generated $OUTPUT  (files: $file_count, runs: $run_count, errors: $errors)" >&2
if (( errors > 0 )); then
    echo "⚠  There were $errors error(s) — review the output for <!-- ERROR --> comments." >&2
    exit 1
fi
