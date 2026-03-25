#!/bin/bash
# Proposed minimal local release-preparation script.
#
# This file is a design proposal only.
# It is not used by the production release pipeline.

set -euo pipefail

show_help() {
    cat <<'EOF'
Prepare a release locally using the current branch-flow model while delegating validation, tagging, and publishing to CI.

Usage:
  ./scripts/mkrelease-small.sh <version> [major|minor|patch] [--dry-run]

What it does:
  1. Validates that the repo is on develop and clean
  2. Validates that the version is semver or rc variant
  3. Runs all tests and determines coverage
  4. Updates coverage badges
  5. Validates that CHANGELOG.md already contains the release entry
  6. Bumps the Poetry version
  7. Commits the release-preparation changes on develop
  8. Pushes develop
  9. Squash-merges develop into main and pushes main
  10. Back-merges main into develop and pushes develop

What it does NOT do:
  - build artifacts
  - tag releases
  - create GitHub Releases
  - publish to PyPI
EOF
}

VERSION="${1:-}"
RELEASE_TYPE="${2:-minor}"
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --help|-h)
            show_help
            exit 0
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
    esac
done

if [[ -z "$VERSION" ]]; then
    echo "Error: version is required" >&2
    exit 2
fi

run() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[DRY-RUN] $*"
    else
        "$@"
    fi
}

if [[ ! -f pyproject.toml ]]; then
    echo "Error: run from repo root" >&2
    exit 2
fi

if [[ "$(git branch --show-current)" != "develop" ]]; then
    echo "Error: must run from develop" >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Error: working tree must be clean" >&2
    exit 1
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(rc[1-9][0-9]?)?$ ]]; then
    echo "Error: version must be semver or rc variant" >&2
    exit 2
fi

if ! grep -Eq "^## \[v${VERSION}\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$" CHANGELOG.md; then
    echo "Error: CHANGELOG.md is missing entry for v${VERSION}" >&2
    echo "Run ./scripts/mkchlogentry.sh ${VERSION} ${RELEASE_TYPE} first or use /changelog-entry" >&2
    exit 1
fi

poetry run pytest \
            tests/ \
            -m "not heavy" \
            -n auto \
            --cov=src/mcprojsim \
            --cov-report=term-missing \
            --cov-report=html \
            --cov-report=xml \
            --junitxml=pytest-report.xml \
            --cov-fail-under=80

if [[ $? -ne 0 ]]; then
    echo "Error: tests failed" >&2
    exit 1
fi

if ! ./scripts/mkcovupd.sh; then
    echo "Error: failed to update coverage badges" >&2
    exit 1
fi

run poetry version "$VERSION"
run git add pyproject.toml poetry.lock CHANGELOG.md README.md
run git commit -m "chore(release): prepare v${VERSION}"
run git push origin develop

run git checkout main
run git pull origin main
run git merge --squash develop
run git commit -m "release: ${VERSION}"
run git push origin main

# Do a regular merge back to develop to keep the history clean and avoid merge conflicts on the next release
run git checkout develop
run git merge --no-ff -m "chore: sync develop with main after release v${VERSION}" main
run git push origin develop

cat <<EOF

Release branch flow complete for v${VERSION}.

Next steps:
    1. Wait for CI on main to finish successfully
    2. Let GitHub Actions create the tag, GitHub Release, and PyPI publish
    3. Let docs publish on the release tag
EOF