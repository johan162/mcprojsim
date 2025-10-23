#!/bin/bash
# Setup verification script for mcprojsim

set -e

echo "=== mcprojsim Setup Verification ==="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found"
    echo "Run: python3 -m venv venv"
    exit 1
fi
echo "✅ Virtual environment exists"

# Activate virtual environment
source venv/bin/activate

# Check if package is installed
if ! command -v mc-estimate &> /dev/null; then
    echo "❌ mc-estimate command not found"
    echo "Run: pip install -e ."
    exit 1
fi
echo "✅ mc-estimate command available"

# Check version
VERSION=$(mc-estimate --version)
echo "✅ Version: $VERSION"

# Validate example project
echo ""
echo "Testing project validation..."
if mc-estimate validate examples/sample_project.yaml 2>&1 | grep -q "valid"; then
    echo "✅ Project validation works"
else
    echo "❌ Project validation failed"
    exit 1
fi

# Run quick simulation
echo ""
echo "Running quick simulation test (100 iterations)..."
if mc-estimate simulate examples/sample_project.yaml --iterations 100 --seed 42 --quiet > /dev/null 2>&1; then
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
if mc-estimate config show 2>&1 | grep -q "Uncertainty Factors"; then
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
echo "  mc-estimate --help"
echo "  mc-estimate validate examples/sample_project.yaml"
echo "  mc-estimate simulate examples/sample_project.yaml"
echo "  mc-estimate config show"
echo ""
echo "See QUICKSTART.md for more information."
