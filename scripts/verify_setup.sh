#!/bin/bash
# Setup & Verification script for mcprojsim
# Purpose: Do all necessary steps toi setup a local development environment and verify installation
# CI/CD Support: Yes. Can be run in CI environments.
# Usage: ./scripts/verify_setup.sh

set -e

echo "=== mcprojsim Environment Setup & Verification ==="
echo ""

# Detect OS and distro for install hints
OS_NAME=""
DISTRO_ID=""
DISTRO_LIKE=""
if [[ "$(uname -s)" == "Darwin" ]]; then
    OS_NAME="macos"
else
    OS_NAME="linux"
    if [[ -f /etc/os-release ]]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO_ID="${ID:-}"
        DISTRO_LIKE="${ID_LIKE:-}"
    fi
fi

install_hint() {
    local pkg="$1"
    if [[ "$OS_NAME" == "macos" ]]; then
        echo "Install with: brew install ${pkg}"
        return
    fi

    case "$DISTRO_ID" in
        ubuntu|debian|linuxmint|pop)
            echo "Install with: sudo apt install ${pkg}"
            ;;
        fedora)
            echo "Install with: sudo dnf install ${pkg}"
            ;;
        rhel|centos|rocky|almalinux)
            echo "Install with: sudo dnf install ${pkg}"
            ;;
        arch|manjaro)
            echo "Install with: sudo pacman -S ${pkg}"
            ;;
        opensuse*|sles)
            echo "Install with: sudo zypper install ${pkg}"
            ;;
        *)
            if [[ "$DISTRO_LIKE" == *"debian"* ]]; then
                echo "Install with: sudo apt install ${pkg}"
            elif [[ "$DISTRO_LIKE" == *"rhel"* ]] || [[ "$DISTRO_LIKE" == *"fedora"* ]]; then
                echo "Install with: sudo dnf install ${pkg}"
            elif [[ "$DISTRO_LIKE" == *"arch"* ]]; then
                echo "Install with: sudo pacman -S ${pkg}"
            elif [[ "$DISTRO_LIKE" == *"suse"* ]]; then
                echo "Install with: sudo zypper install ${pkg}"
            else
                echo "Install with your package manager (package: ${pkg})"
            fi
            ;;
    esac
}

install_pyenv_hint() {
    if [[ "$OS_NAME" == "macos" ]]; then
        echo "Install pyenv with: brew install pyenv"
        return
    fi

    echo "Install pyenv with: curl https://pyenv.run | bash"
}

# Ensure Poetry is available
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found."
    install_hint "poetry"
    echo "You can also install with: pip install poetry"
    # Asks user if he wants to isatll poetry if not found
    read -p "Would you like to install Poetry now? (y/n) " -n -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pip install poetry
    else
        exit 1
    fi
fi
echo "✅ Poetry is available"

# Ensure pandoc is available
if ! command -v pandoc &> /dev/null; then
    echo "❌ pandoc not found."
    install_hint "pandoc"
    exit 1
fi
echo "✅ pandoc is available"

# Ensure ImageMagick is available (magick or convert)
if command -v magick &> /dev/null; then
    IMAGEMAGICK_CMD="magick"
elif command -v convert &> /dev/null; then
    IMAGEMAGICK_CMD="convert"
else
    echo "❌ ImageMagick not found (need 'magick' or 'convert')."
    install_hint "imagemagick"
    exit 1
fi
echo "✅ ImageMagick is available: ${IMAGEMAGICK_CMD}"


# Ensure required fonts are available for PDF rendering.
MONO_FONT_NAME="DejaVu Sans Mono"
SANS_FONT_NAME="DejaVu Sans"
BODY_FONT_NAME="Arial Unicode MS"
BODY_FONT_CASK_NAME="font-arial-unicode-ms"
BODY_FONT_FALLBACK_NAME="Noto Sans"

install_font_hint() {
    local font_key="$1"
    if [[ "$OS_NAME" == "macos" ]]; then
        case "$font_key" in
            dejavu)
                echo "Install with: brew install --cask font-dejavu"
                ;;
            noto)
                echo "Install with: brew install --cask font-noto-sans"
                ;;
        esac
        return
    fi

    case "$DISTRO_ID" in
        ubuntu|debian|linuxmint|pop)
            case "$font_key" in
                dejavu) echo "Install with: sudo apt install fonts-dejavu" ;;
                noto) echo "Install with: sudo apt install fonts-noto-core" ;;
            esac
            ;;
        fedora|rhel|centos|rocky|almalinux)
            case "$font_key" in
                dejavu) echo "Install with: sudo dnf install dejavu-sans-fonts dejavu-serif-fonts dejavu-sans-mono-fonts" ;;
                noto) echo "Install with: sudo dnf install google-noto-sans-fonts" ;;
            esac
            ;;
        arch|manjaro)
            case "$font_key" in
                dejavu) echo "Install with: sudo pacman -S ttf-dejavu" ;;
                noto) echo "Install with: sudo pacman -S noto-fonts" ;;
            esac
            ;;
        opensuse*|sles)
            case "$font_key" in
                dejavu) echo "Install with: sudo zypper install dejavu-fonts" ;;
                noto) echo "Install with: sudo zypper install noto-sans-fonts" ;;
            esac
            ;;
        *)
            case "$font_key" in
                dejavu) echo "Install DejaVu fonts with your package manager" ;;
                noto) echo "Install Noto Sans with your package manager" ;;
            esac
            ;;
    esac
}

has_font() {
    local font_name="$1"
    if command -v fc-list &> /dev/null; then
        fc-list | grep -qi "${font_name}"
    else
        system_profiler SPFontsDataType 2>/dev/null | grep -qi "${font_name}"
    fi
}

has_body_font() {
    has_font "${BODY_FONT_NAME}" || has_font "${BODY_FONT_FALLBACK_NAME}"
}

missing_fonts=()
if ! has_font "${MONO_FONT_NAME}"; then
    missing_fonts+=("${MONO_FONT_NAME}")
fi
if ! has_font "${SANS_FONT_NAME}"; then
    missing_fonts+=("${SANS_FONT_NAME}")
fi
if ! has_body_font; then
    missing_fonts+=("${BODY_FONT_NAME}")
fi

if [ ${#missing_fonts[@]} -gt 0 ]; then
    echo "❌ Missing required fonts: ${missing_fonts[*]}"

    if [[ " ${missing_fonts[*]} " == *" ${MONO_FONT_NAME} "* ]] || [[ " ${missing_fonts[*]} " == *" ${SANS_FONT_NAME} "* ]]; then
        if [[ "$OS_NAME" == "macos" ]]; then
            read -p "Would you like to install DejaVu fonts now via Homebrew? (y/n) " -n 1 -r
            echo ""

            if [[ $REPLY =~ ^[Yy]$ ]]; then
                if ! command -v brew &> /dev/null; then
                    echo "❌ Homebrew not found. Install Homebrew first, then run:"
                    install_font_hint "dejavu"
                    exit 1
                fi

                brew install --cask font-dejavu
            else
                echo "❌ DejaVu fonts are required for expected PDF output"
                exit 1
            fi
        else
            echo "❌ DejaVu fonts are required for expected PDF output"
            install_font_hint "dejavu"
            exit 1
        fi
    fi

    if [[ " ${missing_fonts[*]} " == *" ${BODY_FONT_NAME} "* ]]; then
        if [[ "$OS_NAME" == "macos" ]]; then
            read -p "Would you like to install ${BODY_FONT_NAME} now via Homebrew? (y/n) " -n 1 -r
            echo ""

            if [[ $REPLY =~ ^[Yy]$ ]]; then
                if ! command -v brew &> /dev/null; then
                    echo "❌ Homebrew not found. Install Homebrew first, then run:"
                    echo "   brew install --cask ${BODY_FONT_CASK_NAME}"
                    exit 1
                fi

                if brew info --cask "${BODY_FONT_CASK_NAME}" &> /dev/null; then
                    brew install --cask "${BODY_FONT_CASK_NAME}"
                else
                    echo "⚠️  ${BODY_FONT_CASK_NAME} is not available in Homebrew casks."
                    read -p "Install fallback ${BODY_FONT_FALLBACK_NAME} instead? (y/n) " -n 1 -r
                    echo ""
                    if [[ $REPLY =~ ^[Yy]$ ]]; then
                        brew install --cask font-noto-sans
                    else
                        echo "❌ ${BODY_FONT_NAME} is still missing and fallback was declined"
                        exit 1
                    fi
                fi
            else
                echo "❌ ${BODY_FONT_NAME} (or fallback ${BODY_FONT_FALLBACK_NAME}) is required for expected PDF body font output"
                exit 1
            fi
        else
            echo "❌ ${BODY_FONT_NAME} (or fallback ${BODY_FONT_FALLBACK_NAME}) is required for expected PDF body font output"
            install_font_hint "noto"
            exit 1
        fi
    fi

    # Re-check both fonts after any attempted installation.
    missing_fonts=()
    if ! has_font "${MONO_FONT_NAME}"; then
        missing_fonts+=("${MONO_FONT_NAME}")
    fi
    if ! has_font "${SANS_FONT_NAME}"; then
        missing_fonts+=("${SANS_FONT_NAME}")
    fi
    if ! has_body_font; then
        missing_fonts+=("${BODY_FONT_NAME}")
    fi

    if [ ${#missing_fonts[@]} -gt 0 ]; then
        echo "❌ Missing required fonts after installation attempt: ${missing_fonts[*]}"
        echo "   Please install them before continuing."
        exit 1
    fi
fi

if has_font "${BODY_FONT_NAME}"; then
    resolved_body_font="${BODY_FONT_NAME}"
else
    resolved_body_font="${BODY_FONT_FALLBACK_NAME}"
fi

echo "✅ Required fonts are available: ${MONO_FONT_NAME}, ${SANS_FONT_NAME}, ${resolved_body_font}"



# Make sure a local virtual environment is used
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f ".venv/bin/activate" ]; then
        echo "⚠️  Poetry virtual environment found at .venv, but it is not activated."
        read -p "Would you like to activate the Poetry virtual environment now? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # shellcheck disable=SC1091
            source .venv/bin/activate
            echo "✅ Poetry virtual environment activated"
        else
            exit 1
        fi
    else
        echo "❌ No virtual environment detected. Please create one with Poetry (poetry install)."
        # Automatically create and activate a virtual environment if not present
        # If user answers "y", we will create and activate a virtual environment
        read -p "Would you like to create and activate a Poetry virtual environment now? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            poetry config virtualenvs.in-project true --local
            poetry env remove --all
            rm -rf .venv
            poetry install
            source .venv/bin/activate
            echo "✅ Poetry virtual environment created and activated"
        else
            exit 1
        fi
    fi
fi
echo "✅ Poetry virtual environment detected"

# Install project dependencies via Poetry
echo "Installing dependencies with Poetry..."
poetry lock 
poetry install --with dev,docs,mcp
echo "✅ Dependencies installed"

# Check if package is installed
if ! poetry run mcprojsim --version &> /dev/null; then
    echo "❌ mcprojsim command not found after poetry install"
    exit 1
fi
echo "✅ mcprojsim command available"

# Check version
VERSION=$(poetry run mcprojsim --version)
echo "✅ Version: $VERSION"

# Validate example project
echo ""
echo "Testing project validation..."
if poetry run mcprojsim validate examples/sample_project.yaml 2>&1 | grep -q "valid"; then
    echo "✅ Project validation works"
else
    echo "❌ Project validation failed"
    exit 1
fi

# Run quick simulation
echo ""
echo "Running quick simulation test (100 iterations)..."
if poetry run mcprojsim simulate examples/sample_project.yaml --iterations 100 --seed 42 --quiet -f "html,csv,json" > /dev/null 2>&1; then
    echo "✅ Simulation runs successfully"
else
    echo "❌ Simulation failed"
    exit 1
fi

# Check output files exist
if [ -f "Customer Portal Redesign_results.json" ] && \
   [ -f "Customer Portal Redesign_results.csv" ] && \
   [ -f "Customer Portal Redesign_results.html" ]; then
    echo "✅ Output files generated"
else
    echo "❌ Output files missing"
    exit 1
fi

# Test config command
echo ""
echo "Testing config command..."
if poetry run mcprojsim config --list 2>&1 | grep -q "Uncertainty Factors"; then
    echo "✅ Config command works"
else
    echo "❌ Config command failed"
    exit 1
fi



# Check for Python 3.13 — required by this project
echo ""
if ! command -v python3.13 &> /dev/null; then
    echo "⚠️  Python 3.13 is not installed (required by mcprojsim)."
    echo "   The current Poetry environment may be using a different version:"
    poetry env info --path 2>/dev/null || true
    echo ""
    install_hint "python3.13"
    read -p "Would you like to install Python 3.13 now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [[ "$OS_NAME" == "macos" ]]; then
            if command -v brew &> /dev/null; then
                brew install python@3.13
            else
                echo "❌ Homebrew not found. Install from https://brew.sh, then: brew install python@3.13"
                exit 1
            fi
        else
            case "$DISTRO_ID" in
                ubuntu|debian|linuxmint|pop)
                    sudo apt install -y python3.13 ;;
                fedora)
                    sudo dnf install -y python3.13 ;;
                rhel|centos|rocky|almalinux)
                    sudo dnf install -y python3.13 ;;
                arch|manjaro)
                    sudo pacman -S --noconfirm python ;;
                opensuse*|sles)
                    sudo zypper install -y python313 ;;
                *)
                    echo "❌ Cannot auto-install Python 3.13 on this distro. Please install manually."
                    exit 1 ;;
            esac
        fi
    fi
fi

if command -v python3.13 &> /dev/null; then
    PY313_VERSION=$(python3.13 --version)
    CURRENT_POETRY_PYTHON=$(poetry run python --version 2>/dev/null || echo "unknown")
    echo "✅ Python 3.13 is installed: ${PY313_VERSION}"

    if [[ "$CURRENT_POETRY_PYTHON" != *"3.13"* ]]; then
        echo "⚠️  Poetry is currently using: ${CURRENT_POETRY_PYTHON}"
        read -p "Would you like to switch the Poetry environment to Python 3.13? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            poetry env use python3.13
            echo "✅ Poetry environment switched to Python 3.13"
            echo "   Run: poetry install --with dev,docs,mcp  to reinstall deps in the new environment"
        fi
    else
        echo "✅ Poetry is already using Python 3.13"
    fi
fi

echo ""
echo "==================================="
echo "✅ All checks passed!"
echo "==================================="
echo ""
echo "Full development environment for mcprojsim is ready to use!"
echo ""
echo "See development.md for more information on how to contribute and run tests."

# End of script

