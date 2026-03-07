#!/usr/bin/env bash
# =============================================================================
# mcprojsim.sh - Run mcprojsim in a Podman container
#
# This script wraps the mcprojsim tool to run inside a container while
# transparently handling file I/O with the host filesystem.
#
# Usage:
#   ./mcprojsim.sh [mcprojsim options]
#
# Examples:
#   ./mcprojsim.sh --help
#   ./mcprojsim.sh simulate project.yaml -n 10000
#   ./mcprojsim.sh simulate project.yaml -n 10000 -o results -f json,csv,html
#   ./mcprojsim.sh validate project.yaml
#   ./mcprojsim.sh config show
#
# Environment Variables:
#   MCPROJSIM_IMAGE        - Container image name (default: mcprojsim:latest)
#   MCPROJSIM_WORKDIR      - Working directory to mount (default: current directory)
#   MCPROJSIM_USE_PROXY_CA - Set to "true" to build with proxy CA cert (default: false)
#   PODMAN_OPTS            - Additional Podman options
# =============================================================================

set -euo pipefail

# Configuration
readonly IMAGE_NAME="${MCPROJSIM_IMAGE:-mcprojsim:latest}"
readonly WORK_DIR="${MCPROJSIM_WORKDIR:-$(pwd)}"
readonly USE_PROXY_CA="${MCPROJSIM_USE_PROXY_CA:-false}"
readonly CONTAINER_WORK="/work"

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

# Check if podman is available
check_podman() {
    if ! command -v podman &>/dev/null; then
        error "Podman is not installed. Please install Podman first."
    fi
}

# Check if the image exists, build if not
ensure_image() {
    if ! podman image exists "${IMAGE_NAME}" 2>/dev/null; then
        warn "Image '${IMAGE_NAME}' not found."
        
        # Check if Dockerfile exists in the script's directory
        local script_dir
        script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local dockerfile="${script_dir}/Dockerfile"
        
        if [[ -f "${dockerfile}" ]]; then
            info "Building image from ${dockerfile}..."
            
            # Build command with optional proxy CA support
            local build_cmd=(podman build -t "${IMAGE_NAME}")
            
            if [[ "${USE_PROXY_CA}" == "true" ]]; then
                info "Building with proxy CA certificate support..."
                build_cmd+=(--build-arg USE_PROXY_CA=true)
            fi
            
            build_cmd+=("${script_dir}")
            
            "${build_cmd[@]}" || error "Failed to build image"
            info "Image built successfully."
        else
            error "Image not found and no Dockerfile available at ${dockerfile}"
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
    abs_path="$(cd "${WORK_DIR}" && pwd)"
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
    local prev_arg=""
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
            prev_arg="${arg}"
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
        prev_arg="${arg}"
    done
    
    printf '%s\n' "${args[@]}"
}

# Main function
main() {
    check_podman
    ensure_image
    
    # Process arguments
    local processed_args=()
    if [[ $# -gt 0 ]]; then
        while IFS= read -r arg; do
            processed_args+=("${arg}")
        done < <(process_args "$@")
    fi
    
    # Build podman command
    local podman_cmd=(
        podman run
        --rm
        --interactive
        --tty
        --volume "${WORK_DIR}:${CONTAINER_WORK}:Z"
        --workdir "${CONTAINER_WORK}"
        --security-opt label=disable
    )
    
    # Add any additional podman options from environment
    if [[ -n "${PODMAN_OPTS:-}" ]]; then
        # shellcheck disable=SC2206
        podman_cmd+=(${PODMAN_OPTS})
    fi
    
    # Add image name
    podman_cmd+=("${IMAGE_NAME}")
    
    # Add processed arguments
    if [[ ${#processed_args[@]} -gt 0 ]]; then
        podman_cmd+=("${processed_args[@]}")
    fi

    # Debug: print the final command
    info "Running command: ${podman_cmd[*]}"
    
    # Execute the command
    exec "${podman_cmd[@]}"
}

# Run main function with all arguments
main "$@"
