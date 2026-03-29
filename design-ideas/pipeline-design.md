# CI/CD Pipeline Design Proposal

## Purpose

This document proposes a modernized release pipeline for mcprojsim with these goals:

- minimize local release scripting
- move quality gates, artifact creation, tagging, and publishing to GitHub Actions
- prevent bad git states and partial local releases
- eliminate duplicated build and verification work
- preserve all required publish outputs

Required publish outputs for each release:

1. README coverage badge update
2. Python package publish to PyPI
3. Runtime container publish to GHCR
4. MCP server bundle publish as GitHub release artifact
5. Docs publish to gh-pages

## Current State Review

Current automation is split between local scripts and workflows:

- [scripts/mkrelease.sh](scripts/mkrelease.sh) performs local checks, tests, local build, branch merges, local tagging, and push.
- [scripts/mkghrelease.sh](scripts/mkghrelease.sh) then creates the GitHub Release from local artifacts.
- [scripts/mkbld.sh](scripts/mkbld.sh) overlaps with CI quality and build checks.
- [.github/workflows/ci.yml](.github/workflows/ci.yml) already runs code checks, tests, smoke tests, and builds artifacts.
- [.github/workflows/publish-to-pypi.yml](.github/workflows/publish-to-pypi.yml) rebuilds and publishes after release publication.
- [.github/workflows/docs.yml](.github/workflows/docs.yml) only deploys docs on docs-related path changes on main.

### Problems in current flow

- Build and twine validation are duplicated across local scripts and workflows.
- Tests and static checks run locally and in CI for release flow.
- Release is split into two scripts with manual sequencing.
- Git tag and release artifacts originate from local machine state.
- Docs deployment can be skipped on version-only releases.
- No GHCR publish in Actions today.

## Design Principles

- Local script does only human-required prep.
- CI validates and produces release artifacts.
- Release publishing uses CI-built artifacts only.
- Tag and GitHub Release are created by Actions, not local machine.
- Pipeline is idempotent and guarded against duplicate or partial releases.

## Proposed Target Pipeline

### High-level flow

1. Developer runs a minimal local release prep script on develop.
2. Script bumps version, verifies changelog entry, commits, and pushes develop.
3. Developer opens and merges develop -> main via PR (required checks enabled).
4. CI on main runs checks, tests, build, coverage badge update, release artifact packaging.
5. Release workflow runs after successful CI on main:
   - confirms release intent and version
   - creates or reuses tag
   - creates GitHub Release
   - uploads CI-built artifacts
   - publishes package to PyPI
   - publishes runtime container to GHCR
6. Docs workflow deploys on tag push and on docs changes to main.

This removes local tagging, local release creation, and local publishing.

## Proposed Workflows

### 1) ci.yml (read-only validation and build)

Triggers:

- push: develop, main
- pull_request: main (and optionally develop)

Jobs:

1. code-check
   - black --check
   - flake8
   - mypy
2. test
   - pytest with coverage threshold >= 80
   - smoke CLI simulations on selected examples
3. build-release-artifacts (needs code-check + test)
   - poetry build
   - twine check dist/*
   - build user guide pdf
   - build MCP bundle via [scripts/mkmcpbundle.sh](scripts/mkmcpbundle.sh)
   - upload artifact named release-dist (wheel, sdist, pdf, mcp zip)
4. coverage-badge-update (main only)
   - run [scripts/mkcovupd.sh](scripts/mkcovupd.sh)
   - commit and push README change only when badge value changed

Notes:

- Keep permissions at contents: read except badge update job, which needs contents: write.
- Make badge update job skip when actor is github-actions[bot] to avoid loops.

### 2) release.yml (privileged release orchestration)

Trigger:

- workflow_run on successful ci.yml completion for main

Permissions:

- contents: write
- packages: write
- id-token: write (if Trusted Publishing for PyPI is enabled)

Guards before any publish:

1. Assert source workflow conclusion is success.
2. Assert head branch is main.
3. Parse version from pyproject.toml.
4. Assert matching changelog section exists in CHANGELOG.md.
5. Assert release tag does not already exist, or exit successfully as no-op.
6. Assert release artifact bundle is present and complete.

Release actions:

1. Download release-dist artifact produced by ci.yml run.
2. Create annotated tag vX.Y.Z at tested main commit.
3. Create GitHub Release with changelog notes.
4. Upload wheel, sdist, pdf, MCP bundle to the release.
5. Publish wheel/sdist to PyPI.
6. Build and publish runtime container image to GHCR.

GHCR publish details:

- Build from [Dockerfile](Dockerfile).
- Use docker/login-action with GITHUB_TOKEN.
- Push tags:
  - ghcr.io/<owner>/mcprojsim:vX.Y.Z
  - ghcr.io/<owner>/mcprojsim:latest (stable releases only)
- Add OCI labels for source, revision, and version.

### 3) publish-to-pypi.yml (simplify or retire)

Two acceptable patterns:

1. Preferred: move publish step into release.yml and retire [.github/workflows/publish-to-pypi.yml](.github/workflows/publish-to-pypi.yml).
2. Transitional: keep publish-to-pypi.yml, but consume release assets instead of rebuilding.

Recommendation: use a single release.yml to avoid re-build drift.

### 4) docs.yml (release-safe docs deploy)

Triggers:

- push to main for docs-related paths
- push tags matching v*
- workflow_dispatch

Deploy condition:

- deploy on main pushes and tag pushes

This guarantees docs deployment for each release tag.

## Minimal Local Script Proposal

Introduce a new minimal script, for example scripts/mkrelease-min.sh (new file), with only these responsibilities:

1. verify branch is develop
2. verify working tree is clean
3. verify changelog entry exists for target version
4. set version using poetry version
5. stage and commit pyproject.toml, poetry.lock, CHANGELOG.md
6. push develop
7. print next step to open PR develop -> main

It should not:

- run full tests/lint/type checks
- build artifacts
- tag
- merge branches
- create GitHub release
- publish anything

Safety checks in script:

- fail fast on detached HEAD
- fail if local develop is behind origin/develop
- fail if release tag already exists remotely
- optional dry-run mode

## Controls To Avoid Bad Git States

1. Protect main branch:
   - require PRs
   - require ci.yml success
   - disallow force push
2. Remove local tag creation from scripts.
3. Keep release workflow idempotent (tag exists => no-op).
4. Ensure release job is tied to tested commit from successful CI run.
5. Keep all publish actions after validation and artifact checks.

## Coverage Badge Update Strategy

Current behavior exists locally via [scripts/mkcovupd.sh](scripts/mkcovupd.sh).

Proposed behavior:

- run badge update only on main in CI
- if README changes, commit as bot with message chore(ci): update coverage badge
- use [skip ci] in commit message, or guard workflow on actor/message, to prevent recursive runs

This preserves your existing badge behavior while moving it into automation.

## Artifact Contract Per Release

release-dist must include:

- dist/mcprojsim-<version>-py3-none-any.whl
- dist/mcprojsim-<version>.tar.gz
- dist/mcprojsim-mcp-bundle-<version>.zip
- dist/mcprojsim_user_guide-v<version>.pdf

Release workflow should verify all files exist before tagging.

## Migration Plan

### Phase 1: Introduce in parallel

- add new release.yml
- extend ci.yml with artifact completeness checks and MCP/PDF packaging
- update docs.yml trigger rules for tags
- keep old scripts/workflows intact

### Phase 2: Switch release operation

- use minimal local script + PR merge flow for one supervised release
- stop using mkghrelease.sh for normal releases

### Phase 3: Clean up

- retire duplicated local release logic in mkrelease.sh
- retire or simplify publish-to-pypi.yml
- update [scripts/README.md](scripts/README.md) to remove stale references (for example mkrelease2.sh if still absent)

## Validation Checklist For The New Pipeline

1. Develop push runs ci.yml fully.
2. PR develop -> main is blocked on failed checks.
3. Main merge produces release-dist artifact.
4. release.yml creates tag and GitHub Release once.
5. PyPI gets the package from CI-built artifacts.
6. GHCR gets versioned container image.
7. GitHub Release contains MCP bundle and user guide pdf.
8. docs.yml deploys on release tag.
9. README coverage badge updates automatically on main.

## Open Questions To Confirm

1. Should stable release merges into main be squash-only, or any merge strategy allowed?
2. Do you want Trusted Publishing for PyPI now, or keep token-based publish initially?
3. For GHCR tagging, should latest be pushed only for stable tags and never for rc tags?
4. Should release creation be automatic on every version bump merged to main, or manually approved through an environment gate?

## Recommendation

Adopt CI-driven release orchestration with a minimal local prep script and PR-based promotion from develop to main. This eliminates duplicated local work, reduces risk of bad local git state, and ensures PyPI, GHCR, MCP artifact, docs, and coverage badge updates all come from one consistent pipeline.

---

## Draft Scripts and Workflows

The following are concrete drafts ready for iteration and implementation.
Each section is self-contained and meant to replace the corresponding
existing file when the migration is complete.

---

### Draft: `scripts/mkrelease-min.sh`

Replaces the combined `mkrelease.sh` + `mkghrelease.sh` workflow.
Does nothing beyond preparing a release commit on `develop` and pushing it.
All quality gates, tagging, artifact packaging, and publishing happen in CI.

```bash
#!/usr/bin/env bash
# mkrelease-min.sh — Minimal release preparation script
#
# Prepares a release commit on develop and pushes it to origin.
# All quality gates, artifact creation, tagging, and publishing are
# handled automatically by GitHub Actions after you merge to main.
#
# Usage:
#   ./scripts/mkrelease-min.sh <version> [major|minor|patch] [--dry-run] [--help]
#
# Examples:
#   ./scripts/mkrelease-min.sh 0.8.0 minor
#   ./scripts/mkrelease-min.sh 0.8.0 minor --dry-run

set -euo pipefail

# ─────────────────────────────
# Configuration
# ─────────────────────────────
PROGRAMNAME_PRETTY="MCProjSim"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()      { echo -e "${GREEN}✓${NC} ${1}"; }
err()     { echo -e "${RED}✗${NC} ${1}" >&2; exit 1; }
warn()    { echo -e "${YELLOW}⚠${NC} ${1}"; }
step()    { echo -e "${BLUE}==> ${1}${NC}"; }
dryrun()  { echo -e "${YELLOW}[DRY-RUN]${NC} Would: ${1}"; }

# ─────────────────────────────
# Argument parsing
# ─────────────────────────────
VERSION=""
RELEASE_TYPE="minor"
DRY_RUN=false

show_help() {
      cat <<EOF
${PROGRAMNAME_PRETTY} minimal release preparation script

USAGE:
      $0 <version> [release-type] [--dry-run] [--help]

ARGUMENTS:
      version        PEP 440 semver, e.g. 1.2.3 or 1.2.3rc1
      release-type   major | minor | patch  (default: minor)

OPTIONS:
      --dry-run  Preview actions without making changes
      --help     Show this message

WORKFLOW (all CI steps are automatic after you push):
      1. Run this script on develop
      2. Open PR: develop -> main  (or use: gh pr create --base main --head develop)
      3. CI validates, builds, and packages artifacts
      4. Merge the PR when all checks pass
      5. CI creates tag, GitHub Release, publishes to PyPI, GHCR, and gh-pages docs
EOF
}

for arg in "$@"; do
      case $arg in
            --help|-h) show_help; exit 0 ;;
            --dry-run) DRY_RUN=true ;;
            -*) err "Unknown option: $arg" ;;
            *)
                  if [[ -z "$VERSION" ]]; then VERSION="$arg"
                  else RELEASE_TYPE="$arg"; fi
                  ;;
      esac
done

[[ -z "$VERSION" ]] && { show_help; err "Version is required"; }

# Normalise -rc to rc (poetry / PEP 440 format)
VERSION="${VERSION/-rc/rc}"

[[ "$DRY_RUN" == "true" ]] && warn "DRY-RUN MODE — no changes will be made"

echo ""
echo "================================================"
echo "  ${PROGRAMNAME_PRETTY} Release Preparation"
echo "  Version:      v${VERSION}"
echo "  Release type: ${RELEASE_TYPE}"
echo "================================================"
echo ""

# ─────────────────────────────
# Phase 1: Guards
# ─────────────────────────────
step "Phase 1: Pre-flight checks"

[[ -f pyproject.toml ]] || err "Must run from project root (pyproject.toml not found)"
ok "Project root confirmed"

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(rc[1-9][0-9]?)?$ ]] \
      || err "Version must be x.y.z or x.y.zrcN — got: ${VERSION}"
ok "Version format valid"

[[ "$RELEASE_TYPE" =~ ^(major|minor|patch)$ ]] \
      || err "Release type must be major, minor, or patch — got: ${RELEASE_TYPE}"

# Must be on develop (not a detached HEAD)
CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")
[[ "$CURRENT_BRANCH" == "develop" ]] \
      || err "Must be on 'develop' branch (currently on '${CURRENT_BRANCH:-detached HEAD}')"
ok "On develop branch"

# Working tree must be clean
[[ -z "$(git status --porcelain)" ]] || {
      git status --short
      err "Working tree is not clean — commit or stash all changes first"
}
ok "Working tree clean"

# Sync check — refuse if local develop is behind origin/develop
git fetch origin develop --quiet 2>/dev/null
LOCAL_SHA=$(git rev-parse develop)
REMOTE_SHA=$(git rev-parse origin/develop)
[[ "$LOCAL_SHA" == "$REMOTE_SHA" ]] \
      || err "Local develop is out of sync with origin/develop — run: git pull origin develop"
ok "develop is in sync with origin"

# Tag must not already exist on remote
if git ls-remote --exit-code --tags origin "refs/tags/v${VERSION}" >/dev/null 2>&1; then
      err "Tag v${VERSION} already exists on origin"
fi
ok "Tag v${VERSION} does not yet exist on origin"

# CHANGELOG entry must already exist (created manually or via mkchlogentry.sh)
grep -Eq "^## \[v${VERSION}\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$" CHANGELOG.md 2>/dev/null \
      || err "No CHANGELOG.md entry found for v${VERSION}
   Run first: ./scripts/mkchlogentry.sh ${VERSION} ${RELEASE_TYPE}"
ok "CHANGELOG entry found for v${VERSION}"

echo ""

# ─────────────────────────────
# Phase 2: Bump version
# ─────────────────────────────
step "Phase 2: Bump version in pyproject.toml"

if [[ "$DRY_RUN" == "true" ]]; then
      dryrun "poetry version ${VERSION}"
else
      poetry version "${VERSION}"
      BUMPED="$(poetry version --short)"
      ok "pyproject.toml version set to ${BUMPED}"
fi

echo ""

# ─────────────────────────────
# Phase 3: Commit and push
# ─────────────────────────────
step "Phase 3: Commit and push develop"

COMMIT_MSG="chore(release): prepare v${VERSION}

- Bump version to ${VERSION}
- CHANGELOG.md entry already present
- CI will validate, build artifacts, and publish after merge to main"

if [[ "$DRY_RUN" == "true" ]]; then
      dryrun "git add pyproject.toml poetry.lock CHANGELOG.md"
      dryrun "git commit -m 'chore(release): prepare v${VERSION}'"
      dryrun "git push origin develop"
else
      git add pyproject.toml poetry.lock CHANGELOG.md
      git commit -m "$COMMIT_MSG"
      git push origin develop
      ok "develop pushed to origin"
fi

echo ""

# ─────────────────────────────
# Phase 4: Next steps
# ─────────────────────────────
step "Phase 4: Next steps"
echo ""
echo "  Open a PR:  develop -> main"
echo "    $ gh pr create --base main --head develop --fill"
echo ""
echo "  Wait for all CI checks to pass, then merge."
echo ""
echo "  After the merge, CI will automatically:"
echo "    ✓ Build wheel, sdist, MCP bundle, and user-guide PDF"
echo "    ✓ Update README coverage badge"
echo "    ✓ Create tag v${VERSION} and a GitHub Release"
echo "    ✓ Publish package to PyPI"
echo "    ✓ Push container image to GHCR"
echo "    ✓ Deploy documentation to gh-pages"
echo ""
```

---

### Draft: `.github/workflows/ci.yml`

Extends the current workflow with a `package` job (MCP bundle + user-guide PDF,
main only) and a `coverage-badge` job. Splits release artifact upload cleanly
so the `release.yml` can download it by run ID.

```yaml
name: Continuous Integration

on:
   push:
      branches: [main, develop, 'feature/**', 'bugfix/**', 'hotfix/**']
   pull_request:
      branches: [main, develop]
   workflow_dispatch:

permissions:
   contents: read

concurrency:
   group: ci-${{ github.workflow }}-${{ github.ref }}
   cancel-in-progress: true

env:
   PYTHON_VERSION: '3.13'
   POETRY_NO_INTERACTION: '1'
   POETRY_VIRTUALENVS_IN_PROJECT: 'true'

jobs:
   # ──────────────────────────────────────────
   # 1. Code quality (format / lint / types)
   # ──────────────────────────────────────────
   code-check:
      name: Code check
      runs-on: ubuntu-latest
      steps:
         - uses: actions/checkout@v4

         - name: Set up Python and Poetry
            uses: ./.github/actions/setup-python-poetry
            with:
               python-version: ${{ env.PYTHON_VERSION }}
               dependency-groups: dev,mcp
               install-root: 'false'

         - name: Formatting check
            run: poetry run black --check src tests

         - name: Lint check
            run: poetry run flake8 src tests

         - name: Type check
            run: poetry run mypy src tests

   # ──────────────────────────────────────────
   # 2. Tests + smoke
   # ──────────────────────────────────────────
   testing:
      name: Testing
      runs-on: ubuntu-latest
      steps:
         - uses: actions/checkout@v4

         - name: Install system dependencies
            run: sudo apt-get update && sudo apt-get install -y graphviz

         - name: Set up Python and Poetry
            uses: ./.github/actions/setup-python-poetry
            with:
               python-version: ${{ env.PYTHON_VERSION }}
               dependency-groups: dev,mcp
               install-root: 'true'

         - name: Run unit tests with coverage
            run: |
               poetry run pytest tests/ \
                  -m "not heavy" \
                  -n auto \
                  --cov=src/mcprojsim \
                  --cov-report=term-missing \
                  --cov-report=html \
                  --cov-report=xml \
                  --junitxml=pytest-report.xml \
                  --cov-fail-under=80

         - name: Run smoke tests
            run: |
               poetry run mcprojsim validate examples/sample_project.yaml
               poetry run mcprojsim simulate examples/sample_project.yaml --iterations 50 --quiet
               poetry run mcprojsim simulate examples/tshirt_sizing_project.yaml --iterations 50 --quiet
               poetry run mcprojsim simulate examples/project_with_custom_thresholds.yaml --iterations 50 --quiet

         - name: Upload coverage XML for badge job
            if: github.ref == 'refs/heads/main'
            uses: actions/upload-artifact@v4
            with:
               name: coverage-xml
               path: coverage.xml
               retention-days: 1

         - name: Upload test results on failure
            if: failure()
            uses: actions/upload-artifact@v4
            with:
               name: test-results
               path: |
                  htmlcov/
                  .coverage
                  pytest-report.xml
               retention-days: 7

   # ──────────────────────────────────────────
   # 3. Build — always verify wheel/sdist;
   #    on main also build MCP bundle + PDF
   #    and upload the complete release-dist.
   # ──────────────────────────────────────────
   build:
      name: Build
      runs-on: ubuntu-latest
      needs: [code-check, testing]
      steps:
         - uses: actions/checkout@v4
            with:
               fetch-depth: 0  # needed for make update-version

         - name: Set up Python and Poetry
            uses: ./.github/actions/setup-python-poetry
            with:
               python-version: ${{ env.PYTHON_VERSION }}
               dependency-groups: dev
               install-root: 'false'

         - name: Build wheel and sdist
            run: poetry build

         - name: Verify with Twine
            run: poetry run twine check dist/*

         # ── Main-only: full release artifact set ──────────────────────────────

         - name: Build MCP bundle
            if: github.ref == 'refs/heads/main'
            run: ./scripts/mkmcpbundle.sh

         - name: Install PDF build dependencies
            if: github.ref == 'refs/heads/main'
            run: |
               sudo apt-get update
               sudo apt-get install -y \
                  pandoc \
                  texlive-xetex \
                  texlive-latex-extra \
                  texlive-fonts-recommended \
                  fonts-dejavu \
                  lmodern

         - name: Build user guide PDF
            if: github.ref == 'refs/heads/main'
            # continue-on-error so a TeX regression does not block the release;
            # the artifact check below will warn and exclude the PDF if missing.
            continue-on-error: true
            run: make pdf

         - name: Verify release artifact completeness
            if: github.ref == 'refs/heads/main'
            run: |
               VERSION=$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)"/\1/')
               # PEP 440: poetry strips hyphens, e.g. 1.2.3rc1 (no dash)
               PYPI_VER="${VERSION//-/}"
               WHEEL="dist/mcprojsim-${PYPI_VER}-py3-none-any.whl"
               SDIST="dist/mcprojsim-${PYPI_VER}.tar.gz"
               BUNDLE="dist/mcprojsim-mcp-bundle-${PYPI_VER}.zip"
               GUIDE="dist/mcprojsim_user_guide-v${VERSION}.pdf"

               FAILED=0
               for f in "$WHEEL" "$SDIST" "$BUNDLE"; do
                  if [[ -f "$f" ]]; then
                     echo "OK  $(basename "$f")  ($(du -sh "$f" | cut -f1))"
                  else
                     echo "MISSING  $f"
                     FAILED=1
                  fi
               done
               [[ -f "$GUIDE" ]] \
                  && echo "OK  $(basename "$GUIDE")  ($(du -sh "$GUIDE" | cut -f1))" \
                  || echo "WARN  user-guide PDF not found ($(basename "$GUIDE")) — will be excluded from release"

               [[ $FAILED -eq 0 ]] || { echo "Required release artifacts are missing — aborting."; exit 1; }

         - name: Upload release-dist artifact
            if: github.ref == 'refs/heads/main'
            uses: actions/upload-artifact@v4
            with:
               name: release-dist
               path: dist/
               retention-days: 1   # consumed by release.yml which runs shortly after

         # ── Non-main: ephemeral build artifact for inspection ─────────────────

         - name: Get build metadata
            if: github.ref != 'refs/heads/main'
            id: meta
            run: |
               BRANCH="${GITHUB_REF#refs/heads/}"
               echo "branch=${BRANCH//\//-}" >> "$GITHUB_OUTPUT"
               echo "short_sha=$(git rev-parse --short HEAD)" >> "$GITHUB_OUTPUT"
               echo "ts=$(date +'%Y%m%d-%H%M%S')" >> "$GITHUB_OUTPUT"

         - name: Upload ephemeral build artifact
            if: github.ref != 'refs/heads/main'
            uses: actions/upload-artifact@v4
            with:
               name: >-
                  mcprojsim-${{ steps.meta.outputs.branch }}-${{ steps.meta.outputs.short_sha }}-${{ steps.meta.outputs.ts }}
               path: dist/
               retention-days: 3

   # ──────────────────────────────────────────
   # 4. Coverage badge — main pushes only.
   #    Commits README.md update when the
   #    badge percentage actually changes.
   # ──────────────────────────────────────────
   coverage-badge:
      name: Update coverage badge
      runs-on: ubuntu-latest
      needs: [testing, build]
      # Only direct pushes to main; skip PRs and bot commits to avoid infinite loops.
      if: >
         github.event_name == 'push' &&
         github.ref == 'refs/heads/main' &&
         github.actor != 'github-actions[bot]'
      permissions:
         contents: write
      steps:
         - uses: actions/checkout@v4
            with:
               token: ${{ secrets.GITHUB_TOKEN }}

         - name: Download coverage XML
            uses: actions/download-artifact@v4
            with:
               name: coverage-xml

         - name: Update badge
            run: ./scripts/mkcovupd.sh

         - name: Commit if badge changed
            run: |
               git diff --quiet README.md && { echo "Badge unchanged — nothing to commit."; exit 0; }
               git config user.name  "github-actions[bot]"
               git config user.email "github-actions[bot]@users.noreply.github.com"
               git add README.md
               git commit -m "chore(ci): update coverage badge [skip ci]"
               git push
```

---

### Draft: `.github/workflows/release.yml`

Triggered by a successful `ci.yml` run on `main`. All release actions happen
here — tag creation, GitHub Release, PyPI publish, and GHCR container push.
The workflow is idempotent: if the tag already exists it exits cleanly.

```yaml
name: Release

on:
   workflow_run:
      workflows: ['Continuous Integration']
      types: [completed]
      branches: [main]

permissions:
   contents: write   # create tags, GitHub Releases
   packages: write   # push to ghcr.io
   # id-token: write # uncomment when PyPI Trusted Publishing is configured

jobs:
   # ──────────────────────────────────────────
   # Gate: decide whether this CI run
   # represents an actual release commit.
   # Outputs version, tag, and boolean flags.
   # ──────────────────────────────────────────
   gate:
      name: Release gate
      runs-on: ubuntu-latest
      # Only act on successful CI runs for main
      if: >
         github.event.workflow_run.conclusion == 'success' &&
         github.event.workflow_run.head_branch == 'main'
      outputs:
         version:      ${{ steps.detect.outputs.version }}
         tag:          ${{ steps.detect.outputs.tag }}
         is_release:   ${{ steps.detect.outputs.is_release }}
         is_prerelease: ${{ steps.detect.outputs.is_prerelease }}
      steps:
         - uses: actions/checkout@v4
            with:
               ref: ${{ github.event.workflow_run.head_sha }}
               fetch-depth: 0

         - name: Detect release intent
            id: detect
            run: |
               VERSION=$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)"/\1/')
               TAG="v${VERSION}"

               echo "version=${VERSION}" >> "$GITHUB_OUTPUT"
               echo "tag=${TAG}"         >> "$GITHUB_OUTPUT"

               # ── Idempotency guard ───────────────────────────────────────────────
               if git rev-parse "$TAG" >/dev/null 2>&1; then
                  echo "Tag $TAG already exists — this is not a new release."
                  echo "is_release=false" >> "$GITHUB_OUTPUT"
                  exit 0
               fi

               # ── CHANGELOG must have an entry for this version ───────────────────
               if ! grep -Eq "^## \[${TAG}\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$" CHANGELOG.md; then
                  echo "No CHANGELOG entry for $TAG — treating as a non-release commit."
                  echo "is_release=false" >> "$GITHUB_OUTPUT"
                  exit 0
               fi

               # ── Version must be strictly newer than the latest existing tag ─────
               LATEST_TAG=$(git tag -l 'v*' | sort -V | tail -1)
               LATEST_VER="${LATEST_TAG#v}"
               if [[ -z "$LATEST_VER" ]]; then LATEST_VER="0.0.0"; fi

               # Use sort -V: if VERSION is strictly greater, it appears last
               HIGHEST=$(printf '%s\n%s\n' "$LATEST_VER" "$VERSION" | sort -V | tail -1)
               if [[ "$HIGHEST" != "$VERSION" || "$VERSION" == "$LATEST_VER" ]]; then
                  echo "Version ${VERSION} is not newer than latest tag ${LATEST_TAG:-none} — skipping."
                  echo "is_release=false" >> "$GITHUB_OUTPUT"
                  exit 0
               fi

               # ── All guards passed: this is a release commit ─────────────────────
               echo "is_release=true" >> "$GITHUB_OUTPUT"

               # rc suffix (PEP 440 style, e.g. 1.2.3rc1) → pre-release
               if [[ "$VERSION" =~ rc[0-9]+$ ]]; then
                  echo "is_prerelease=true" >> "$GITHUB_OUTPUT"
               else
                  echo "is_prerelease=false" >> "$GITHUB_OUTPUT"
               fi

               echo "Proceeding with release of $TAG (pre-release: $([[ "$VERSION" =~ rc[0-9]+$ ]] && echo true || echo false))"

   # ──────────────────────────────────────────
   # Release: tag → GitHub Release → PyPI → GHCR
   # Skipped entirely when gate.is_release == 'false'
   # ──────────────────────────────────────────
   release:
      name: Publish release
      runs-on: ubuntu-latest
      needs: gate
      if: needs.gate.outputs.is_release == 'true'
      env:
         VERSION: ${{ needs.gate.outputs.version }}
         TAG:     ${{ needs.gate.outputs.tag }}
      steps:
         - uses: actions/checkout@v4
            with:
               ref: ${{ github.event.workflow_run.head_sha }}
               fetch-depth: 0

         # ── Download CI-built artifacts ─────────────────────────────────────────
         - name: Download release-dist artifact
            uses: actions/download-artifact@v4
            with:
               name: release-dist
               run-id: ${{ github.event.workflow_run.id }}
               github-token: ${{ secrets.GITHUB_TOKEN }}
               path: dist/

         - name: Verify release-dist completeness
            run: |
               PYPI_VER="${VERSION//-/}"
               REQUIRED=(
                  "dist/mcprojsim-${PYPI_VER}-py3-none-any.whl"
                  "dist/mcprojsim-${PYPI_VER}.tar.gz"
                  "dist/mcprojsim-mcp-bundle-${PYPI_VER}.zip"
               )
               FAILED=0
               for f in "${REQUIRED[@]}"; do
                  [[ -f "$f" ]] && echo "OK  $(basename "$f")" || { echo "MISSING  $f"; FAILED=1; }
               done
               [[ $FAILED -eq 0 ]] || { echo "Required artifacts missing — aborting release."; exit 1; }
               # PDF is optional; warn but continue
               GUIDE="dist/mcprojsim_user_guide-v${VERSION}.pdf"
               [[ -f "$GUIDE" ]] && echo "OK  $(basename "$GUIDE")" || echo "WARN  user-guide PDF absent"

         # ── Create annotated git tag ────────────────────────────────────────────
         - name: Configure git
            run: |
               git config user.name  "github-actions[bot]"
               git config user.email "github-actions[bot]@users.noreply.github.com"

         - name: Create and push tag
            run: |
               git tag -a "$TAG" -m "Release $TAG"
               git push origin "$TAG"

         # ── Extract CHANGELOG section for this version ──────────────────────────
         - name: Extract changelog notes
            id: changelog
            run: |
               NOTES=$(awk "/^## \[${TAG}\]/{found=1; next} /^## \[v[0-9]/{if(found) exit} found{print}" CHANGELOG.md)
               if [[ -z "$NOTES" ]]; then NOTES="Release ${TAG}"; fi
               {
                  echo "notes<<CHANGELOG_EOF"
                  echo "$NOTES"
                  echo "CHANGELOG_EOF"
               } >> "$GITHUB_OUTPUT"

         # ── Create GitHub Release and upload artifacts ───────────────────────────
         - name: Create GitHub Release
            env:
               GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
            run: |
               PYPI_VER="${VERSION//-/}"
               WHEEL="dist/mcprojsim-${PYPI_VER}-py3-none-any.whl"
               SDIST="dist/mcprojsim-${PYPI_VER}.tar.gz"
               BUNDLE="dist/mcprojsim-mcp-bundle-${PYPI_VER}.zip"
               GUIDE="dist/mcprojsim_user_guide-v${VERSION}.pdf"

               ASSETS=("$WHEEL" "$SDIST" "$BUNDLE")
               [[ -f "$GUIDE" ]] && ASSETS+=("$GUIDE")

               PRERELEASE_FLAG=""
               [[ "${{ needs.gate.outputs.is_prerelease }}" == "true" ]] && PRERELEASE_FLAG="--prerelease"

               gh release create "$TAG" \
                  --title "MCProjSim ${TAG}" \
                  --notes "${{ steps.changelog.outputs.notes }}" \
                  $PRERELEASE_FLAG \
                  "${ASSETS[@]}"

         # ── Publish to PyPI ──────────────────────────────────────────────────────
         - name: Install Poetry
            run: python -m pip install poetry

         - name: Publish to PyPI (stable)
            if: needs.gate.outputs.is_prerelease == 'false'
            env:
               POETRY_HTTP_BASIC_PYPI_USERNAME: __token__
               POETRY_HTTP_BASIC_PYPI_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
            run: poetry publish --no-build --no-interaction
            # NOTE: switch to Trusted Publishing (id-token: write) when configured:
            # run: poetry publish --no-build --no-interaction --repository pypi

         - name: Publish to TestPyPI (pre-release)
            if: needs.gate.outputs.is_prerelease == 'true'
            env:
               POETRY_REPOSITORIES_TESTPYPI_URL: https://test.pypi.org/legacy/
               POETRY_HTTP_BASIC_TESTPYPI_USERNAME: __token__
               POETRY_HTTP_BASIC_TESTPYPI_PASSWORD: ${{ secrets.TEST_PYPI_API_TOKEN }}
            run: poetry publish --no-build --no-interaction --repository testpypi

         # ── Build and push container image to GHCR ───────────────────────────────
         - name: Log in to GHCR
            uses: docker/login-action@v3
            with:
               registry: ghcr.io
               username: ${{ github.actor }}
               password: ${{ secrets.GITHUB_TOKEN }}

         - name: Generate container image metadata
            id: imgmeta
            uses: docker/metadata-action@v5
            with:
               images: ghcr.io/${{ github.repository }}
               tags: |
                  type=raw,value=${{ needs.gate.outputs.tag }}
                  type=raw,value=latest,enable=${{ needs.gate.outputs.is_prerelease == 'false' }}
               labels: |
                  org.opencontainers.image.title=MCProjSim
                  org.opencontainers.image.description=Monte Carlo project simulation tool
                  org.opencontainers.image.version=${{ needs.gate.outputs.version }}
                  org.opencontainers.image.source=${{ github.server_url }}/${{ github.repository }}
                  org.opencontainers.image.revision=${{ github.event.workflow_run.head_sha }}

         - name: Build and push container image
            uses: docker/build-push-action@v6
            with:
               context: .
               push: true
               tags: ${{ steps.imgmeta.outputs.tags }}
               labels: ${{ steps.imgmeta.outputs.labels }}
```

---

### Trigger update for `.github/workflows/docs.yml`

Replace only the `on:` block in the existing docs workflow.
Adding `tags: ['v*']` to the `push:` key makes docs deploy on every release tag,
regardless of which files changed. The `paths:` filter continues to apply to
branch pushes only (GitHub Actions applies path filters and tag filters
independently within the same `push:` entry).

```yaml
# Replace the existing on: block with this:
on:
   push:
      branches:
         - main
      paths:
         - 'docs/**'
         - 'mkdocs.yml'
         - '.github/workflows/docs.yml'
      tags:
         - 'v*'        # <── always deploy on release tags
   pull_request:
      branches:
         - main
      paths:
         - 'docs/**'
         - 'mkdocs.yml'
   workflow_dispatch:
```

Also update the `publish-docs` job condition so it fires on tag pushes as well
as branch pushes:

```yaml
# replace the existing if: condition on publish-docs
if: >
   github.event_name == 'push' &&
   (github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v'))
```
