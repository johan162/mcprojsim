#!/bin/bash
# Setup & Verification script for mcprojsim
# Purpose: Do all necessary steps toi setup a local development environment and verify installation
# CI/CD Support: Yes. Can be run in CI environments.
# Usage: ./scripts/verify_setup.sh

set -e

echo "=== mcprojsim Setup Verification ==="
echo ""

# Ensure Poetry is available
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Install with: pip install poetry"
    exit 1
fi
echo "✅ Poetry is available"

# Install project dependencies via Poetry
echo "Installing dependencies with Poetry..."
poetry install --with dev
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
if poetry run mcprojsim config show 2>&1 | grep -q "Uncertainty Factors"; then
    echo "✅ Config command works"
else
    echo "❌ Config command failed"
    exit 1
fi

echo ""
echo "==================================="
echo "✅ All checks passed!"
echo "==================================="
echo ""
echo "mcprojsim is ready to use!"
echo ""
echo "Quick commands:"
echo "  poetry run mcprojsim --help"
echo "  poetry run mcprojsim validate examples/sample_project.yaml"
echo "  poetry run mcprojsim simulate examples/sample_project.yaml"
echo "  poetry run mcprojsim config show"
echo ""
echo "See QUICKSTART.md for more information."
