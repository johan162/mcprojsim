#!/bin/bash
# GitHub release script for mcprojsim

set -e

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.0.0"
    exit 1
fi

echo "=== Creating GitHub release for v$VERSION ==="

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

# Build the package
echo "Building package..."
./scripts/mkblbd.sh

# Create GitHub release
echo "Creating GitHub release..."
gh release create "v$VERSION" \
    --title "Version $VERSION" \
    --notes "Release version $VERSION" \
    dist/*

echo "=== GitHub release v$VERSION created ==="
