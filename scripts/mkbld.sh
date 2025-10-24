#!/bin/bash
# Build script for mcprojsim

set -eu

echo "=== Building mcprojsim ==="

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info

# Run type checking with mypy
echo "Running type checking with mypy..."
mypy src/mcprojsim

if [ $? -ne 0 ]; then
    echo "❌ Type checking failed"
    exit 1
fi

echo "✅ Type checking passed"

# Run code style checking with black
echo "Running code style checking with black..."
black --check --diff src/mcprojsim tests/

if [ $? -ne 0 ]; then
    echo "❌ Code style check failed"
    echo "Run 'black src/mcprojsim tests/' to fix formatting issues"
    exit 1
fi

echo "✅ Code style check passed"

# Run unit tests with coverage
echo "Running unit tests with coverage..."
pytest tests/ -v --cov=mcprojsim --cov-report=term --cov-report=html --cov-fail-under=80

if [ $? -ne 0 ]; then
    echo "❌ Tests failed or coverage is below 80%"
    exit 1
fi

echo "✅ All tests passed with coverage >= 80%"

# Build the package
echo "Building package..."
python -m build

echo "=== Build complete ==="
echo "Artifacts created in dist/"
ls -lh dist/
