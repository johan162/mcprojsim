# Analysis of current workflow

Too many things are duplicated

```txt
Developer workstation                          GitHub
─────────────────────                          ──────

1. scripts/mkrelease.sh
   ├─ validate repo state (develop, clean)
   ├─ pytest + coverage ≥ 80%
   ├─ mypy, black
   ├─ smoke-test example projects
   ├─ poetry build + twine check
   ├─ bump version in pyproject.toml
   ├─ generate CHANGELOG template → user edits
   ├─ git commit on develop
   ├─ git checkout main
   ├─ git merge --squash develop
   ├─ git tag v$VERSION
   ├─ git push main + tag
   ├─ git checkout develop
   ├─ git merge --no-ff main
   ├─ git push develop
   ├─ gh run watch (wait for CI)           ──→  ci.yml triggers (push to main + develop)
   ├─ poetry build (again)                      docs.yml triggers (push to main, paths match)
   └─ twine check (again)

2. scripts/mkghrelease.sh
   ├─ validate tag exists
   ├─ poetry build (3rd time)
   ├─ twine check (3rd time)
   ├─ gh release create v$VERSION dist/*   ──→  publish-to-pypi.yml triggers (on release)
   └─ done

```

## Problems


- Redundant work<br>
poetry build + twine check runs 3 times: in mkrelease.sh, again at the end of mkrelease.sh, and again in mkghrelease.sh. CI also builds and checks.

- Redundant testing	
Full pytest + mypy + black run locally in the script, then again in CI. The script even waits for CI to finish.

- Two manual scripts	
Developer must remember to run mkrelease.sh then mkghrelease.sh in order.

- Local builds are not the published artifacts	
The artifacts uploaded to PyPI come from a local poetry build, not from the CI-built artifacts. This breaks reproducibility.

- CHANGELOG editing blocks automation	
The script pauses for interactive editing.

- Version bump is local	
poetry version runs locally; if anything fails mid-script the version is bumped but not released.

- Docs trigger is fragile	
Docs only rebuild when docs/** or mkdocs.yml change, so a version-only release skips docs.


# Proposed modern pipeline

Principles

- Local script does only what humans must do: validate, bump version, edit changelog, commit, push.
- CI does all quality gates: lint, type check, test, build, verify.
- CI creates the release: tag, GitHub Release, artifact upload, PyPI publish.
- Artifacts published to PyPI are built by CI, not locally.
- Docs always rebuild on release tags, not just on file-path changes

```txt
Developer workstation                        GitHub Actions
─────────────────────                        ──────────────

scripts/mkrelease.sh (simplified)
  ├─ validate: on develop, clean
  ├─ poetry version $VERSION
  ├─ prompt: edit CHANGELOG.md
  ├─ git commit "chore(release): prepare v$VERSION"
  ├─ git push develop
  └─ done                                 ──→ ci.yml (push develop)
                                               ├─ code-check (black, flake8, mypy)
                                               ├─ testing (pytest, smoke)
                                               └─ build (poetry build, twine check)

Developer: create PR develop → main          ──→ ci.yml (pull_request)
           or: git merge locally                  same jobs

Push / merge to main                         ──→ ci.yml (push main)
                                               ├─ code-check
                                               ├─ testing
                                               ├─ build
                                               └─ release (NEW)
                                                   ├─ detect version from pyproject.toml
                                                   ├─ create git tag v$VERSION
                                                   ├─ create GitHub Release with dist/*
                                                   └─ trigger publish-to-pypi.yml

Tag v* pushed (by release job)               ──→ publish-to-pypi.yml (existing)
                                                   └─ publish to PyPI

Tag v* pushed                                ──→ docs.yml
                                                   ├─ build docs
                                                   └─ deploy to gh-pages

```

## Updated CI pipelein

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: "3.14"
  POETRY_NO_INTERACTION: "1"
  POETRY_VIRTUALENVS_IN_PROJECT: "true"

jobs:
  # ─────────────────────────────────────────────
  # Job 1: Code quality
  # ─────────────────────────────────────────────
  code-check:
    name: Code check
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python and Poetry
        uses: ./.github/actions/setup-python-poetry
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          dependency-groups: dev,mcp
          install-root: "false"

      - name: Formatting check
        run: poetry run black --check src tests

      - name: Lint check
        run: poetry run flake8 src tests

      - name: Type check
        run: poetry run mypy src tests

  # ─────────────────────────────────────────────
  # Job 2: Testing
  # ─────────────────────────────────────────────
  testing:
    name: Testing
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y graphviz

      - name: Set up Python and Poetry
        uses: ./.github/actions/setup-python-poetry
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          dependency-groups: dev,mcp
          install-root: "true"

      - name: Run unit tests with coverage
        run: >
          poetry run pytest tests/
          -n auto
          --cov=src/mcprojsim
          --cov-report=term-missing
          --cov-report=html
          --cov-report=xml
          --junitxml=pytest-report.xml
          --cov-fail-under=80

      - name: Run smoke tests
        run: |
          poetry run mcprojsim --help
          poetry run mcprojsim validate examples/sample_project.yaml
          for project in examples/sample_project.yaml examples/tshirt_sizing_project.yaml examples/project_with_custom_thresholds.yaml; do
            if [[ -f "$project" ]]; then
              echo "Smoke testing: $project"
              poetry run mcprojsim simulate -n 50 "$project"
            fi
          done

      - name: Upload test artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-py${{ env.PYTHON_VERSION }}
          path: |
            htmlcov/
            .coverage
            pytest-report.xml
          retention-days: 7

  # ─────────────────────────────────────────────
  # Job 3: Build
  # ─────────────────────────────────────────────
  build:
    name: Build
    runs-on: ubuntu-latest
    needs: [code-check, testing]
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python and Poetry
        uses: ./.github/actions/setup-python-poetry
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          dependency-groups: dev
          install-root: "false"

      - name: Build package
        run: poetry build

      - name: Verify with Twine
        run: poetry run twine check dist/*

      - name: Get build metadata
        id: metadata
        run: |
          BRANCH="${GITHUB_REF#refs/heads/}"
          echo "short_sha=$(git rev-parse --short HEAD)" >> "$GITHUB_OUTPUT"
          echo "branch=${BRANCH//\//-}" >> "$GITHUB_OUTPUT"
          echo "timestamp=$(date +'%Y%m%d-%H%M%S')" >> "$GITHUB_OUTPUT"
          echo "version=$(grep -m1 'version' pyproject.toml | sed 's/.*"\(.*\)"/\1/')" >> "$GITHUB_OUTPUT"

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: mcprojsim-${{ steps.metadata.outputs.branch }}-${{ steps.metadata.outputs.short_sha }}-${{ steps.metadata.outputs.timestamp }}
          path: dist/
          retention-days: 3

      - name: Upload release artifacts
        if: github.ref == 'refs/heads/main'
        uses: actions/upload-artifact@v4
        with:
          name: release-dist
          path: dist/
          retention-days: 1

  # ─────────────────────────────────────────────
  # Job 4: Release (main branch only)
  # ─────────────────────────────────────────────
  release:
    name: Release
    runs-on: ubuntu-latest
    needs: [build]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Extract version from pyproject.toml
        id: version
        run: |
          VERSION=$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)"/\1/')
          echo "version=$VERSION" >> "$GITHUB_OUTPUT"
          echo "tag=v$VERSION" >> "$GITHUB_OUTPUT"
          echo "Detected version: $VERSION"

      - name: Check if tag already exists
        id: tag_check
        run: |
          TAG="v${{ steps.version.outputs.version }}"
          if git rev-parse "$TAG" >/dev/null 2>&1; then
            echo "exists=true" >> "$GITHUB_OUTPUT"
            echo "Tag $TAG already exists — skipping release"
          else
            echo "exists=false" >> "$GITHUB_OUTPUT"
            echo "Tag $TAG does not exist — proceeding with release"
          fi

      - name: Download release artifacts
        if: steps.tag_check.outputs.exists == 'false'
        uses: actions/download-artifact@v4
        with:
          name: release-dist
          path: dist/

      - name: Create git tag
        if: steps.tag_check.outputs.exists == 'false'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git tag -a "${{ steps.version.outputs.tag }}" -m "Release ${{ steps.version.outputs.tag }}"
          git push origin "${{ steps.version.outputs.tag }}"

      - name: Extract changelog for this version
        if: steps.tag_check.outputs.exists == 'false'
        id: changelog
        run: |
          VERSION="${{ steps.version.outputs.version }}"
          # Extract the section for this version from CHANGELOG.md
          NOTES=$(awk "/^## \\[v${VERSION}\\]/{found=1; next} /^## \\[v[0-9]/{if(found) exit} found{print}" CHANGELOG.md)
          if [[ -z "$NOTES" ]]; then
            NOTES="Release v${VERSION}"
          fi
          # Use a delimiter to handle multiline content
          {
            echo "notes<<CHANGELOG_EOF"
            echo "$NOTES"
            echo "CHANGELOG_EOF"
          } >> "$GITHUB_OUTPUT"

      - name: Create GitHub Release
        if: steps.tag_check.outputs.exists == 'false'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release create "${{ steps.version.outputs.tag }}" \
            dist/* \
            --title "MCProjSim ${{ steps.version.outputs.tag }}" \
            --notes "${{ steps.changelog.outputs.notes }}"
```


## Updated Docs workflow

```yaml
name: Documentation

on:
  push:
    branches: [main]
    tags: ['v*']
    paths:
      - 'docs/**'
      - 'mkdocs.yml'
      - 'pyproject.toml'
      - '.github/workflows/docs.yml'
  workflow_dispatch:

# ...existing code...
```


Note: When a tags: filter is present, the paths: filter is combined with OR for tags — GitHub Actions evaluates tag pushes against tags: regardless of paths:. If docs workflow does not behave that way, add a separate trigger block. The safest approach:

```yaml
name: Documentation

on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - 'mkdocs.yml'
      - 'pyproject.toml'
      - '.github/workflows/docs.yml'
  push:
    tags: ['v*']
  workflow_dispatch:

# ...existing code...
```

Since YAML does not allow duplicate keys, use this instead:

```yaml
name: Documentation

on:
  push:
    branches: [main]
    tags: ['v*']
  workflow_dispatch:

# ...existing code...
```

# New deverloper workflow

```txt
1.  ./scripts/mkrelease.sh 0.5.0 minor
    → bumps version, edits changelog, commits, pushes develop

2.  Merge develop → main (PR or local squash merge)
    → CI runs: lint → test → build → tag → GitHub Release → PyPI

3.  Done.
```

**Note:** Use the new `mkrelease2.sh`

