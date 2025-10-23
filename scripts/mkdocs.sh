#!/bin/bash
# Documentation build script for mcprojsim

set -e

echo "=== Building documentation ==="

# Install documentation dependencies
echo "Installing documentation dependencies..."
pip install -e ".[docs]"

# Build documentation
echo "Building MkDocs site..."
mkdocs build

echo "=== Documentation built ==="
echo "Documentation available in site/"
echo ""
echo "To serve locally:"
echo "  mkdocs serve"
echo ""
echo "To deploy to GitHub Pages:"
echo "  mkdocs gh-deploy"
