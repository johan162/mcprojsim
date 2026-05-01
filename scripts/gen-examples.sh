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
#                      stripped), then inserts captured output from
#                      PASS 1 in a ```text block.
#
# The script uses two passes:
#   PASS 1: Scan template for {{run:...}} commands, run each unique command
#           in parallel, and cache outputs under .build/gen-examples/runs.
#   PASS 2: Render final markdown by expanding {{file:...}} and {{run:...}}
#           placeholders using cached PASS 1 outputs.
#
# Usage:
#   scripts/gen-examples.sh [--jobs N] [template] [output]
#   make gen-examples
# ---------------------------------------------------------------------------
set -euo pipefail

BLACK='\033[0;30m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'

DARKGRAY='\033[1;30m'
BRIGHTRED='\033[1;31m'
BRIGHTGREEN='\033[1;32m'
DARKYELLOW='\033[0;33m'
BRIGHTBLUE='\033[1;34m'
BRIGHTMAGENTA='\033[1;35m'
BRIGHTCYAN='\033[1;36m'
LIGHTGRAY='\033[0;37m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

JOBS=0

usage() {
    cat >&2 <<'EOF'
Usage: scripts/gen-examples.sh [--jobs N] [template] [output]

Options:
  --jobs N   Max number of parallel PASS 1 run commands.
             N <= 0 means no limit (run all at once; default).
EOF
}

args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --jobs)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: --jobs requires a numeric value" >&2
                usage
                exit 2
            fi
            if [[ ! "$2" =~ ^-?[0-9]+$ ]]; then
                echo "ERROR: --jobs must be an integer, got '$2'" >&2
                usage
                exit 2
            fi
            JOBS="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            args+=("$1")
            shift
            ;;
    esac
done

TEMPLATE="${args[0]:-docs/examples_template.md}"
OUTPUT="${args[1]:-docs/examples.md}"
WORK_DIR=".build/gen-examples"

mkdir -p "$WORK_DIR"

file_count=0
run_count=0
errors=0
run_failures=0

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

# Return index of command in run_cmds array, if present.
find_run_cmd_index() {
    local needle="$1"
    local i
    for i in "${!run_cmds[@]}"; do
        if [[ "${run_cmds[$i]}" == "$needle" ]]; then
            printf '%s' "$i"
            return 0
        fi
    done
    return 1
}

wait_for_free_slot() {
    local limit="$1"
    if (( limit <= 0 )); then
        return 0
    fi
    while (( ${#pids[@]} >= limit )); do
        local pid done_index=-1 idx
        for idx in "${!pids[@]}"; do
            pid="${pids[$idx]}"
            if ! kill -0 "$pid" 2>/dev/null; then
                wait "$pid" || true
                done_index="$idx"
                break
            fi
        done
        if (( done_index >= 0 )); then
            unset 'pids[done_index]'
            pids=("${pids[@]}")
        else
            sleep 0.05
        fi
    done
}

# echo "Generating $OUTPUT from $TEMPLATE ..." >&2

RUN_DIR="$WORK_DIR/runs"
mkdir -p "$RUN_DIR"
rm -f "$RUN_DIR"/*.out "$RUN_DIR"/*.status "$RUN_DIR"/*.cmd

# PASS 1: collect all unique run commands from template
run_cmds=()
while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^[[:space:]]*\{\{run:(.+)\}\}[[:space:]]*$ ]]; then
        cmd="${BASH_REMATCH[1]}"
        if ! find_run_cmd_index "$cmd" >/dev/null; then
            run_cmds+=("$cmd")
        fi
    fi
done < "$TEMPLATE"

if (( JOBS > 0 )); then
    echo -e "${DARKYELLOW}  PASS 1: executing ${#run_cmds[@]} unique run command(s) in parallel (jobs=$JOBS) ...${NC}" >&2
else
    echo -e "${DARKYELLOW}  PASS 1: executing ${#run_cmds[@]} unique run command(s) in parallel ...${NC}" >&2
fi

# Execute all unique run commands in parallel and cache outputs under .build
pids=()
for i in "${!run_cmds[@]}"; do
    wait_for_free_slot "$JOBS"
    cmd="${run_cmds[$i]}"
    printf '%s\n' "$cmd" > "$RUN_DIR/$i.cmd"
    (
        if output=$(eval "$cmd" 2>/dev/null); then
            cleaned=$(printf '%s\n' "$output" \
                | grep -v '^mcprojsim, version ' \
                | grep -v '^Progress: ' \
                | sed '/./,$!d')
            printf '%s\n' "$cleaned" > "$RUN_DIR/$i.out"
            printf '0\n' > "$RUN_DIR/$i.status"
        else
            printf '%s\n' "${output:-}" > "$RUN_DIR/$i.out"
            printf '1\n' > "$RUN_DIR/$i.status"
        fi
    ) &
    pids+=("$!")
done

for pid in "${pids[@]}"; do
    wait "$pid"
done

for i in "${!run_cmds[@]}"; do
    if [[ -f "$RUN_DIR/$i.status" ]] && [[ "$(cat "$RUN_DIR/$i.status")" != "0" ]]; then
        echo -e "${BRIGHTRED}  ⚠  non-zero exit: ${run_cmds[$i]}${NC}" >&2
        run_failures=$((run_failures + 1))
    else
        echo -e "${DARKYELLOW}  ✓ run:  ${run_cmds[$i]:0:72}…${NC}" >&2
    fi
done

echo -e "${DARKYELLOW}PASS 2: rendering $OUTPUT ...${NC}" >&2

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
            file_lang=$(fence_lang "$fpath")
            if [[ -f "$fpath" ]]; then
                echo '```'"$file_lang"
                cat "$fpath"
                echo '```'
                file_count=$((file_count + 1))
                echo -e "${DARKYELLOW}  ✓ file: $fpath${NC}" >&2
            else
                echo -e "${DARKRED}<!-- ERROR: file not found: $fpath -->${NC}" 
                echo -e "${DARKRED}  ✗ file not found: $fpath${NC}" >&2
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
            # Insert cached PASS 1 output
            echo '```text'
            if cmd_idx=$(find_run_cmd_index "$cmd"); then
                if [[ -f "$RUN_DIR/$cmd_idx.out" ]]; then
                    cat "$RUN_DIR/$cmd_idx.out"
                else
                    echo -e "${DARKRED}<!-- ERROR: missing cached output for run command -->${NC}"
                    errors=$((errors + 1))
                fi
            else
                echo -e "${DARKRED}<!-- ERROR: run command not found in pass 1 cache -->${NC}"
                errors=$((errors + 1))
            fi
            echo '```'
            run_count=$((run_count + 1))

        # ── Plain line (pass-through) ───────────────────────────────────
        else
            printf '%s\n' "$line"
        fi

    done < "$TEMPLATE"
} > "$OUTPUT"

echo "" >&2
echo -e "${BRIGHTGREEN}✓ Generated $OUTPUT  (files: $file_count, runs: $run_count, errors: $errors, run_failures: $run_failures)${NC}" >&2
if (( errors > 0 )); then
    echo -e "${BRIGHTRED}⚠  There were $errors error(s) — review the output for <!-- ERROR --> comments.${NC}" >&2
    exit 1
fi
