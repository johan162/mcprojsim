#!/usr/bin/env bash
# =============================================================================
# mcprojsim.sh - Run mcprojsim in a container like a local command
#
# This script wraps the mcprojsim tool to run inside a container while
# transparently handling file I/O with the host filesystem.
#
# Usage:
#   ./bin/mcprojsim.sh [mcprojsim options]
#
# Examples:
#   ./bin/mcprojsim.sh --help
#   ./bin/mcprojsim.sh simulate project.yaml -n 10000
#   ./bin/mcprojsim.sh simulate project.yaml -n 10000 -o results -f json,csv,html
#   ./bin/mcprojsim.sh validate project.yaml
#   ./bin/mcprojsim.sh config show
#
# Environment Variables:
#   MCPROJSIM_IMAGE          - Container image name (default: mcprojsim:latest)
#   MCPROJSIM_WORKDIR        - Working directory to mount (default: current directory)
#   MCPROJSIM_USE_PROXY_CA   - Set to "true" to build with proxy CA cert (default: false)
#   MCPROJSIM_CONTAINER_CMD  - Override container engine command
#   CONTAINER_OPTS           - Additional container engine options
#   PODMAN_OPTS              - Additional Podman options (legacy alias)
# =============================================================================

set -euo pipefail

# Paths
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(
    if [[ -f "${SCRIPT_DIR}/Dockerfile" ]]; then
        cd "${SCRIPT_DIR}" && pwd
    elif [[ -f "${SCRIPT_DIR}/../Dockerfile" ]]; then
        cd "${SCRIPT_DIR}/.." && pwd
    else
        cd "${SCRIPT_DIR}" && pwd
    fi
)"
readonly DOCKERFILE_PATH="${PROJECT_ROOT}/Dockerfile"

# Configuration
readonly IMAGE_NAME="${MCPROJSIM_IMAGE:-mcprojsim:latest}"
readonly USE_PROXY_CA="${MCPROJSIM_USE_PROXY_CA:-false}"
readonly CONTAINER_WORK="/work"
readonly REQUESTED_WORK_DIR="${MCPROJSIM_WORKDIR:-$PWD}"

CONTAINER_CMD=""
WORK_DIR=""

# Colors for output (disabled if not a terminal)
if [[ -t 1 ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[0;33m'
    readonly NC='\033[0m' # No Color
else
    readonly RED=''
    readonly GREEN=''
    readonly YELLOW=''
    readonly NC=''
fi

# Print error message and exit
error() {
    echo -e "${RED}Error: $*${NC}" >&2
    exit 1
}

# Print warning message
warn() {
    echo -e "${YELLOW}Warning: $*${NC}" >&2
}

# Print info message
info() {
    echo -e "${GREEN}$*${NC}" >&2
}

# Resolve working directory to an absolute canonical path
resolve_workdir() {
    if [[ ! -d "${REQUESTED_WORK_DIR}" ]]; then
        error "Working directory '${REQUESTED_WORK_DIR}' does not exist"
    fi

    WORK_DIR="$(cd "${REQUESTED_WORK_DIR}" && pwd)"
}

# Detect which container engine to use
detect_container_cmd() {
    if [[ -n "${MCPROJSIM_CONTAINER_CMD:-}" ]]; then
        CONTAINER_CMD="${MCPROJSIM_CONTAINER_CMD}"
        return
    fi

    if command -v podman &>/dev/null; then
        CONTAINER_CMD="podman"
        return
    fi

    if command -v docker &>/dev/null; then
        CONTAINER_CMD="docker"
        return
    fi

    error "Neither Podman nor Docker is installed. Please install one of them first."
}

# Check if the image exists, build if not
ensure_image() {
    if ! "${CONTAINER_CMD}" image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
        warn "Image '${IMAGE_NAME}' not found."

        if [[ -f "${DOCKERFILE_PATH}" ]]; then
            info "Building image from ${DOCKERFILE_PATH} with ${CONTAINER_CMD}..."

            local build_cmd=("${CONTAINER_CMD}" build -f "${DOCKERFILE_PATH}" -t "${IMAGE_NAME}")

            if [[ "${USE_PROXY_CA}" == "true" ]]; then
                info "Building with proxy CA certificate support..."
                build_cmd+=(--build-arg USE_PROXY_CA=true)
            fi

            build_cmd+=("${PROJECT_ROOT}")

            "${build_cmd[@]}" || error "Failed to build image"
            info "Image built successfully."
        else
            error "Image not found and no Dockerfile available at ${DOCKERFILE_PATH}"
        fi
    fi
}

# Convert host path to container path if it's within the work directory
convert_path() {
    local path="$1"
    local abs_path
    
    # If it's a relative path, make it relative to work dir
    if [[ ! "${path}" = /* ]]; then
        # Keep relative paths as-is since we mount current dir to /work
        echo "${path}"
        return
    fi
    
    # Absolute path - check if it's within work directory
    abs_path="${WORK_DIR}"
    if [[ "${path}" == "${abs_path}"* ]]; then
        # Convert to container path
        echo "${CONTAINER_WORK}${path#${abs_path}}"
    else
        # Path outside work directory - this won't be accessible
        warn "Path '${path}' is outside the mounted directory and won't be accessible in the container"
        echo "${path}"
    fi
}

# Process arguments, converting file paths where necessary
process_args() {
    local args=()
    local expect_file=false
    
    for arg in "$@"; do
        # Check if previous argument was a file-expecting option
        if [[ "${expect_file}" == true ]]; then
            # Convert path if it looks like a file path
            if [[ -f "${arg}" ]] || [[ "${arg}" == */* ]] || [[ "${arg}" == *.yaml ]] || \
               [[ "${arg}" == *.yml ]] || [[ "${arg}" == *.toml ]] || [[ "${arg}" == *.json ]]; then
                args+=("$(convert_path "${arg}")")
            else
                args+=("${arg}")
            fi
            expect_file=false
            continue
        fi
        
        # Check for options that expect file arguments
        case "${arg}" in
            -c|--config|-o|--output)
                expect_file=true
                args+=("${arg}")
                ;;
            *)
                # For positional arguments that might be files
                if [[ -f "${arg}" ]] || [[ "${arg}" == *.yaml ]] || \
                   [[ "${arg}" == *.yml ]] || [[ "${arg}" == *.toml ]]; then
                    args+=("$(convert_path "${arg}")")
                else
                    args+=("${arg}")
                fi
                ;;
        esac
    done
    
    printf '%s\n' "${args[@]}"
}

# Main function
main() {
    resolve_workdir
    detect_container_cmd
    ensure_image
    
    # Process arguments
    local processed_args=()
    if [[ $# -gt 0 ]]; then
        while IFS= read -r arg; do
            processed_args+=("${arg}")
        done < <(process_args "$@")
    fi
    
    local volume_spec="${WORK_DIR}:${CONTAINER_WORK}"
    if [[ "${CONTAINER_CMD}" == "podman" ]]; then
        volume_spec="${volume_spec}:Z"
    fi

    # Build container command
    local container_cmd=(
        "${CONTAINER_CMD}" run
        --rm
        --interactive
        --volume "${volume_spec}"
        --workdir "${CONTAINER_WORK}"
    )

    if [[ -t 0 ]]; then
        container_cmd+=(--tty)
    fi
    
    # Add any additional container options from environment
    if [[ -n "${CONTAINER_OPTS:-}" ]]; then
        # shellcheck disable=SC2206
        container_cmd+=(${CONTAINER_OPTS})
    elif [[ -n "${PODMAN_OPTS:-}" ]]; then
        # shellcheck disable=SC2206
        container_cmd+=(${PODMAN_OPTS})
    fi
    
    # Add image name
    container_cmd+=("${IMAGE_NAME}")
    
    # Add processed arguments
    if [[ ${#processed_args[@]} -gt 0 ]]; then
        container_cmd+=("${processed_args[@]}")
    fi

    # Debug: print the final command
    info "Running command: ${container_cmd[*]}"
    
    # Execute the command
    exec "${container_cmd[@]}"
}

# Run main function with all arguments
main "$@"
