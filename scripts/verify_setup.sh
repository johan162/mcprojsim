#!/bin/bash
# Setup & Verification script for mcprojsim
# Purpose: Do all necessary steps toi setup a local development environment and verify installation
# CI/CD Support: Yes. Can be run in CI environments.
# Usage: ./scripts/verify_setup.sh

set -e

echo "=== mcprojsim Setup Verification ==="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found"
    echo "Running: python3 -m venv .venv"
    python3 -m venv .venv
fi
echo "✅ Virtual environment exists"

# Activate virtual environment
source .venv/bin/activate

# Check if package is installed
if ! command -v mcprojsim &> /dev/null; then
    echo "❌ mcprojsim command not found"
    echo "Running: pip install -e \".[dev]\""
    pip install -e ".[dev]"
fi
if ! command -v mcprojsim &> /dev/null; then
    echo "❌ mcprojsim command still not found after installation"
    exit 1
fi
echo "✅ mcprojsim command available"

# Check version
VERSION=$(mcprojsim --version)
echo "✅ Version: $VERSION"

# Validate example project
echo ""
echo "Testing project validation..."
if mcprojsim validate examples/sample_project.yaml 2>&1 | grep -q "valid"; then
    echo "✅ Project validation works"
else
    echo "❌ Project validation failed"
    exit 1
fi

# Run quick simulation
echo ""
echo "Running quick simulation test (100 iterations)..."
if mcprojsim simulate examples/sample_project.yaml --iterations 100 --seed 42 --quiet -f "html,csv,json" > /dev/null 2>&1; then
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
if mcprojsim config show 2>&1 | grep -q "Uncertainty Factors"; then
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
echo "  mcprojsim --help"
echo "  mcprojsim validate examples/sample_project.yaml"
echo "  mcprojsim simulate examples/sample_project.yaml"
echo "  mcprojsim config show"
echo ""
echo "See QUICKSTART.md for more information."
