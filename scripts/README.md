# Build Scripts

This directory contains the maintenance scripts for `mcprojsim`.
They support local development, CI validation, release preparation,
documentation workflows, setup verification, and containerized docs serving.

# Table of Contents

- [Build Scripts](#build-scripts)
- [Table of Contents](#table-of-contents)
  - [Script Conventions](#script-conventions)
  - [Scripts Overview](#scripts-overview)
    - [`mkbld.sh` - Main Build Script](#mkbldsh---main-build-script)
    - [`mkcovupd.sh` - Coverage Badge Updater](#mkcovupdsh---coverage-badge-updater)
    - [`mkrelease.sh` - Release Automation Script](#mkreleasesh---release-automation-script)
    - [`mkghrelease.sh` - GitHub Release Creator](#mkghreleasesh---github-release-creator)
    - [`mkdocs.sh` - Documentation Automation Script](#mkdocssh---documentation-automation-script)
    - [`verify_setup.sh` - Local Setup Verification](#verify_setupsh---local-setup-verification)
    - [`docs-contctl.sh` - Containerized Docs Server Manager](#docs-contctlsh---containerized-docs-server-manager)
  - [Typical Workflows](#typical-workflows)
    - [Daily Development Check](#daily-development-check)
    - [Fresh Local Setup Verification](#fresh-local-setup-verification)
    - [Documentation Workflows](#documentation-workflows)
    - [Release Workflow](#release-workflow)
  - [Troubleshooting](#troubleshooting)
  - [Related Files](#related-files)


## Script Conventions

- Most scripts support `--help`.
- Several scripts support `--dry-run`, but not all do.
- The project is Poetry-based, so the scripts generally assume `poetry` is installed.
- Scripts that are meant for guarded automation typically exit on the first error.

## Scripts Overview

### `mkbld.sh` - Main Build Script

Runs the main quality and packaging pipeline and is the primary script used by CI.

```bash
./scripts/mkbld.sh [OPTIONS]
```

**What it does:**
1. Verifies the Poetry environment and required dev tools
2. Runs `flake8`, `mypy`, and `black --check`
3. Runs the test suite with coverage enforcement
4. Updates the README coverage badge locally when `coverage.xml` changes
5. Builds wheel and source distribution artifacts
6. Validates the built artifacts with `twine check`

**Options:**
- `--dry-run` - Show commands without executing them
- `--help` - Display help message

**Requirements:**
- Poetry installed and available on `PATH`
- Development dependencies installed: `poetry install --with dev`
- Run from the project root

**Outputs:**
- `coverage.xml`
- `htmlcov/`
- `dist/`

### `mkcovupd.sh` - Coverage Badge Updater

Updates the coverage badge in the top-level `README.md` from the current `coverage.xml` report.

```bash
./scripts/mkcovupd.sh [OPTIONS]
```

**What it does:**
1. Extracts line coverage from `coverage.xml`
2. Converts it to a rounded percentage
3. Chooses the Shields badge color from the current coverage result
4. Updates the coverage badge URL in `README.md`
5. Asserts that the exact expected badge URL is present afterward
6. Skips rewriting `README.md` when the badge is already up to date

**Options:**
- `--dry-run` - Show commands without executing them
- `--help` - Display help message

**Badge color mapping:**
- `>= 90%` → `darkgreen`
- `>= 80%` → `brightgreen`
- `>= 70%` → `yellowgreen`
- `>= 60%` → `yellow`
- `>= 50%` → `orange`
- `< 50%` → `red`

**Requirements:**
- `coverage.xml` must exist
- `README.md` must already contain a coverage badge

### `mkrelease.sh` - Release Automation Script

Automates the local release workflow, including version bumping, quality gates, changelog updates, and git operations.

```bash
./scripts/mkrelease.sh <version> [major|minor|patch] [OPTIONS]
```

**Examples:**
```bash
./scripts/mkrelease.sh 0.2.0rc5 minor --dry-run
./scripts/mkrelease.sh 0.2.0 patch
```

**What it does:**
1. Validates the requested version and release prerequisites
2. Runs the project quality gates
3. Updates the Poetry version in `pyproject.toml`
4. Updates release-related files such as `CHANGELOG.md` with a new template entry that has to be completed by the developer
5. Performs the configured branch / tag workflow. This means tagging `develop` and squash merge `develop` to `main` and also back-sync `main` to `develop` 

**Options:**
- `--dry-run` - Preview release actions
- `--help`, `-h` - Display help message

**Notes:**
- Versioning is Poetry-driven; package version data is not edited manually in `__init__.py`
- Pre-release versions should use the current Poetry / PEP 440 style, for example `0.2.0rc5`


### `mkghrelease.sh` - GitHub Release Creator

Creates a GitHub release with the `gh` CLI after the local release work and CI/artifact generation are complete.'
It will base the GitHub release on the latest tag on `main`

```bash
./scripts/mkghrelease.sh [OPTIONS]
```

**What it does:**
1. Validates that `gh` is installed and authenticated
2. Finds the release tag to publish
3. Collects artifacts from `dist/`
4. Prepares release notes
5. Creates the GitHub release and uploads the artifacts

**Options:**
- `--help` - Display help message
- `--pre-release` - Force pre-release mode (same as ticking the pre-release box in the GitHub UI)
- `--dry-run` - Preview without creating the release

**Requirements:**
- GitHub CLI installed and authenticated
- Release artifacts already built in `dist/`
- Typically run after `mkrelease.sh` and after CI completes successfully


### `mkdocs.sh` - Documentation Automation Script

Builds, serves, deploys, or cleans the MkDocs documentation site.

```bash
./scripts/mkdocs.sh {serve|build|deploy|clean}
```

**Commands:**
- `serve` - Start the local MkDocs development server
- `build` - Build the static site into `site/`
- `deploy` - Deploy docs with `mkdocs gh-deploy`
- `clean` - Remove built docs artifacts

**Behavior:**
- Works from the project root automatically
- Ensures docs dependencies are available before running
- Creates the `docs/CHANGELOG.md` symlink when needed

**Requirements:**
- Poetry docs dependencies preferred: `poetry install --with docs`

### `verify_setup.sh` - Local Setup Verification

Verifies that a local Poetry-based installation is working end to end.

```bash
./scripts/verify_setup.sh
```

**What it does:**
1. Verifies Poetry is installed
2. Installs dependencies with `poetry install --with dev`
3. Checks that the `mcprojsim` CLI is available
4. Validates the sample project file
5. Runs a short simulation
6. Confirms expected output files are created
7. Verifies the configuration command works

**Best used for:**
- Initial local setup verification
- Smoke testing a fresh development environment

### `docs-contctl.sh` - Containerized Docs Server Manager

Manages the containerized documentation server built from `Dockerfile.docs`.

```bash
./scripts/docs-contctl.sh [command] [options]
```

**Commands:**
- `start` - Start the docs server container (default)
- `stop` - Stop and remove the docs server container
- `restart` - Restart the docs server container
- `status` - Show current status and URL
- `logs` - Show container logs
- `build` - Build or rebuild the docs image

**Options:**
- `-p`, `--port PORT` - Published host port
- `-n`, `--name NAME` - Container name override
- `-d`, `--detach` - Run in the background
- `-f`, `--foreground` - Run in the foreground
- `-h`, `--help` - Display help message

**Environment variables:**
- `MCPROJSIM_DOCS_IMAGE` - Override image name
- `MCPROJSIM_DOCS_PORT` - Override default port
- `MCPROJSIM_USE_PROXY_CA=true` - Build with proxy CA support

**When to use it:**
- Use this script when you want the docs served from the same containerized environment used for docs image validation
- Prefer `make docs-serve` or `poetry run mkdocs serve` for the fastest local editing feedback

## Typical Workflows

### Daily Development Check

```bash
./scripts/mkbld.sh
open htmlcov/index.html
```

### Fresh Local Setup Verification

```bash
./scripts/verify_setup.sh
```

### Documentation Workflows

```bash
# Local fast feedback
poetry install --with docs
make docs-serve

# Containerized docs environment
make docs-container-start
./scripts/docs-contctl.sh status
./scripts/docs-contctl.sh logs --follow
```

### Release Workflow

```bash
# Preview the release steps first
./scripts/mkrelease.sh 0.2.0rc5 minor --dry-run

# Perform the release workflow
./scripts/mkrelease.sh 0.2.0rc5 minor

# After CI and artifacts are ready, create the GitHub release
./scripts/mkghrelease.sh
```

## Troubleshooting

**Problem: `coverage.xml` not found**

```bash
poetry run pytest --cov=src/mcprojsim --cov-report=xml
./scripts/mkcovupd.sh
```

**Problem: docs dependencies missing**

```bash
poetry install --with docs
```

**Problem: dev tools missing for build scripts**

```bash
poetry install --with dev
```

**Problem: Podman not available for containerized docs**

- Install Podman and ensure the engine is running before using `docs-contctl.sh`

## Related Files

- [Makefile](../Makefile) - Thin wrappers for common development and docs commands
- [README.md](../README.md) - Main project usage and installation guide
- [QUICKSTART.md](../QUICKSTART.md) - End-user quick start guide
- [GitHub workflows](../.github/workflows/) - CI/CD automation
