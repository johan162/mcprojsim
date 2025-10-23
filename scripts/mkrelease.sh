#!/bin/bash
# Release script for mcprojsim

set -e

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.0.0"
    exit 1
fi

echo "=== Creating release $VERSION ==="

# Update version in pyproject.toml
echo "Updating version to $VERSION..."
sed -i.bak "s/^version = .*/version = \"$VERSION\"/" pyproject.toml
rm pyproject.toml.bak

# Run tests
echo "Running tests..."
pytest

# Build the package
echo "Building package..."
./scripts/mkblbd.sh

# Create git tag
echo "Creating git tag v$VERSION..."
git add pyproject.toml
git commit -m "Release version $VERSION"
git tag -a "v$VERSION" -m "Version $VERSION"

echo "=== Release $VERSION ready ==="
echo "To publish to PyPI:"
echo "  python -m twine upload dist/*"
echo ""
echo "To push to GitHub:"
echo "  git push && git push --tags"
