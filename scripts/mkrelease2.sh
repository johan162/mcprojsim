#!/bin/bash
# mcprojsim Release Script
# Description: Prepares a release, merges to main, and pushes. CI handles quality gates and publishing.
# Usage: ./scripts/mkrelease.sh <version> [major|minor|patch] [--dry-run] [--help]

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROGRAMNAME="mcprojsim"
PROGRAMNAME_PRETTY="MCProjSim"
SMOKE_TEST_FILE="tests/test_simulation.py"

print_step()    { echo -e "${BLUE}==>${NC} ${1}"; }
print_success() { echo -e "${GREEN}✓${NC} ${1}"; }
print_error()   { echo -e "${RED}✗${NC} ${1}" >&2; }
print_warning() { echo -e "${YELLOW}⚠${NC} ${1}"; }

# =====================================
# Help
# =====================================
show_help() {
    cat << 'EOF'
🚀 MCProjSim Release Script

DESCRIPTION:
    Prepares a release on develop, merges to main, and pushes both branches.
    CI then handles all quality gates, tagging, GitHub Release, and PyPI publish.

USAGE:
    ./scripts/mkrelease.sh <version> [release-type] [options]

ARGUMENTS:
    version         Semantic version (e.g. 2.1.0, 1.0.0rc1)
    release-type    major | minor | patch  (default: minor)

OPTIONS:
    --dry-run       Preview without making changes
    --help, -h      Show this help

WORKFLOW:
    This script:
      1. Validate repo state
      2. Bump version and edit changelog on develop
      3. Commit and push develop
      4. Squash merge develop → main and push
      5. Merge main → develop (back-merge) and push

    CI then automatically:
      • Runs lint, type check, tests
      • Builds and verifies artifacts
      • Creates git tag and GitHub Release
      • Publishes to PyPI
      • Rebuilds and deploys documentation

EXAMPLES:
    ./scripts/mkrelease.sh 2.1.0 minor --dry-run
    ./scripts/mkrelease.sh 2.1.0 minor
EOF
}

# =====================================
# Parse arguments
# =====================================
VERSION=""
RELEASE_TYPE="minor"
DRY_RUN=false

for arg in "$@"; do
    case $arg in
        --help|-h) show_help; exit 0 ;;
        --dry-run)  DRY_RUN=true ;;
        -*)         print_error "Unknown option: $arg"; exit 1 ;;
        *)
            if [[ -z "$VERSION" ]]; then
                VERSION="$arg"
            else
                RELEASE_TYPE="$arg"
            fi
            ;;
    esac
done

if [[ -z "$VERSION" ]]; then
    print_error "Version required. Run '$0 --help' for usage."
    exit 1
fi

VERSION="${VERSION/-rc/rc}"

run_cmd() {
    local cmd="$1" desc="${2:-}"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $desc"
        echo "  Would run: $cmd"
    else
        [[ -n "$desc" ]] && print_step "$desc"
        eval "$cmd" || { print_error "$desc failed"; exit 1; }
    fi
}

# =====================================
# PHASE 1: VALIDATE
# =====================================
echo ""
print_step "🔍 PHASE 1: VALIDATION"
echo ""

# Must be in project root
[[ -f pyproject.toml ]] || { print_error "Run from project root."; exit 1; }

# Must be on develop
BRANCH=$(git symbolic-ref --short HEAD)
[[ "$BRANCH" == "develop" ]] || { print_error "Must be on develop (currently on $BRANCH)."; exit 1; }

# Must be clean
if [[ -n $(git status --porcelain) ]]; then
    print_error "Working directory is not clean."
    git status --short
    exit 1
fi

# Version format
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(rc[1-9][0-9]?)?$ ]]; then
    print_error "Invalid version format: $VERSION (expected x.y.z or x.y.zrcN)"
    exit 1
fi

# Tag must not exist
if git tag | grep -q "^v${VERSION}$"; then
    print_error "Tag v$VERSION already exists."
    exit 1
fi

# Static analysis and code quality
echo "  ✓ Checking code formatting..."
run_cmd "poetry run black --check --diff src/ tests/" "Checking code formatting"
run_cmd "poetry run flake8 src/${PROGRAMNAME} tests/ --max-line-length=120 --extend-ignore=E203,W503,E501,E402" "Running flake8 static analysis"
run_cmd "poetry run mypy src/${PROGRAMNAME} --ignore-missing-imports" "Running mypy static analysis"

# Make sure we get the latest develop changes before we start
run_cmd "git pull origin develop" "Pull latest develop"
print_success "Validation passed"


# =====================================
# PHASE 2: PREPARE RELEASE
# =====================================
echo ""
print_step "📝 PHASE 2: PREPARE RELEASE"
echo ""

# 2.1: Bump version
run_cmd "poetry version $VERSION" "Bump version to $VERSION"

# 2.2: Quick local smoke test (fast feedback before pushing)
run_cmd "poetry run pytest $SMOKE_TEST_FILE -q --no-header" "Quick smoke test"

# 2.3: Changelog
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}[DRY-RUN]${NC} Would prepend changelog template and open editor"
else
    CHANGELOG_DATE=$(date +%Y-%m-%d)
    ENTRY=$(cat <<EOF
## [v$VERSION] - $CHANGELOG_DATE

Release Type: $RELEASE_TYPE

### 📋 Summary
- [Brief summary of the release]

### ⚠️ Breaking Changes
- [Breaking changes]

### ✨ Additions
- [New features]

### 🚀 Improvements
- [Improvements]

### 🐛 Bug Fixes
- [Bug fixes]

### 📚 Documentation
- [Documentation changes]

### 🛠 Internal
- [Internal changes]

EOF
)

    if [[ -f CHANGELOG.md ]]; then
        echo "$ENTRY" | cat - CHANGELOG.md > CHANGELOG.tmp && mv CHANGELOG.tmp CHANGELOG.md
    else
        echo "$ENTRY" > CHANGELOG.md
    fi

    print_step "Edit CHANGELOG.md now. Press Enter when done, or Ctrl+C to abort."
    read -r
fi

# =====================================
# PHASE 3: COMMIT AND PUSH DEVELOP
# =====================================
echo ""
print_step "🚀 PHASE 3: COMMIT AND PUSH DEVELOP"
echo ""

run_cmd "git add pyproject.toml poetry.lock CHANGELOG.md" "Stage release files"

run_cmd "git commit -m 'chore(release): prepare v$VERSION

- Bump version to $VERSION
- Update changelog
- Release type: $RELEASE_TYPE'" "Commit release preparation"

run_cmd "git push origin develop" "Push develop"

print_success "Develop branch updated and pushed"

# =====================================
# PHASE 4: MERGE TO MAIN
# =====================================
echo ""
print_step "🔀 PHASE 4: MERGE DEVELOP → MAIN"
echo ""

run_cmd "git checkout main" "Switch to main"
run_cmd "git pull origin main" "Pull latest main"
run_cmd "git merge --squash develop" "Squash merge develop into main"
run_cmd "git commit -m 'release: v$VERSION

- Squash merge from develop
- Release type: $RELEASE_TYPE'" "Commit squash merge"
run_cmd "git push origin main" "Push main"

print_success "Main branch updated and pushed"

# =====================================
# PHASE 5: BACK-MERGE MAIN → DEVELOP
# =====================================
echo ""
print_step "🔄 PHASE 5: BACK-MERGE MAIN → DEVELOP"
echo ""

run_cmd "git checkout develop" "Switch back to develop"
run_cmd "git merge --no-ff main -m 'chore: back-merge main after v$VERSION release'" "Back-merge main into develop"
run_cmd "git push origin develop" "Push develop"

print_success "Develop branch synchronized with main"

# =====================================
# SUMMARY
# =====================================
echo ""
if [[ "$DRY_RUN" == "true" ]]; then
    print_step "🔍 DRY RUN COMPLETE"
    echo ""
    echo "To execute:  $0 $VERSION $RELEASE_TYPE"
else
    print_success "🎉 Release v$VERSION complete"
    echo ""
    echo "📋 What happened:"
    echo "   ✓ Version bumped to $VERSION on develop"
    echo "   ✓ Changelog updated"
    echo "   ✓ Develop pushed"
    echo "   ✓ Squash merged develop → main"
    echo "   ✓ Main pushed"
    echo "   ✓ Back-merged main → develop"
    echo "   ✓ Develop pushed"
    echo ""
    echo "📋 What CI will now do automatically:"
    echo "   • Run lint, type check, and tests"
    echo "   • Build and verify artifacts"
    echo "   • Create git tag v$VERSION"
    echo "   • Create GitHub Release with artifacts"
    echo "   • Publish to PyPI"
    echo "   • Rebuild and deploy documentation"
    echo ""
    echo "📋 Monitor CI:"
    echo "   gh run watch"
fi

echo ""
exit 0

# EOF
