# Development guide

This document is the developer reference for working on `mcprojsim` from a source checkout.
It brings together the operational detail that does not belong in the end-user quick start: local development, Poetry usage, Makefile workflows, container builds, documentation builds, release automation, proxy certificate handling, and the GitHub Actions setup.

The intended reader is a contributor or maintainer working on the repository itself.

## Scope of this guide

This guide covers:

- the local Python and Poetry workflow
- when to use `make` and when to call `poetry` directly
- the project structure and where the major responsibilities live
- build and validation scripts in [scripts/README.md](https://github.com/johan162/mcprojsim/blob/main/scripts/README.md)
- building and running the main application container
- building and serving the documentation container
- release preparation with `mkrelease.sh`
- GitHub release publication with `mkghrelease.sh`
- corporate proxy / custom CA handling in both Dockerfiles
- the GitHub Actions CI/CD workflows in [.github/workflows](https://github.com/johan162/mcprojsim/tree/main/.github/workflows)

## Development model at a glance

There are four primary ways to work with this repository:

1. **Direct Poetry workflow**  
   Best when developing Python code locally and running tools directly.
2. **Makefile workflow**  
   Best when you want memorisable shortcuts for common commands.
3. **Script-driven workflow**  
   Best for repeatable higher-level tasks such as release preparation or docs container control.
4. **Container workflow**  
   Best when validating reproducible images or working in an environment where container execution is preferred.

All four are used in this project. They are complementary rather than competing.

## Core toolchain

### Python and Poetry

The project uses Poetry as the source of truth for:

- dependency resolution
- virtual environment management
- packaging metadata
- package build output
- version management
- CLI entry point registration

Relevant configuration is in [pyproject.toml](https://github.com/johan162/mcprojsim/blob/main/pyproject.toml).

Key points from the current setup:

- Python requirement: `>=3.14`
- runtime dependencies live under `[tool.poetry.dependencies]`
- developer tools live under `[tool.poetry.group.dev.dependencies]`
- docs tooling lives under `[tool.poetry.group.docs.dependencies]`
- the CLI entry point is `mcprojsim = "mcprojsim.cli:cli"`

### Recommended local setup

From the project root:

```bash
poetry config virtualenvs.in-project true
poetry install
```

For a contributor, the most useful installs are usually:

```bash
poetry install --with dev,docs
```

That gives you:

- the application itself
- test tooling such as `pytest`, `pytest-cov`, and `pytest-xdist`
- formatting and linting tools such as `black`, `flake8`, and `mypy`
- docs tooling such as `mkdocs`, `mkdocs-material`, and `mkdocstrings`

### Typical direct Poetry commands

```bash
poetry run pytest
poetry run black src/ tests/
poetry run flake8 src/ tests/
poetry run mypy src/
poetry run mkdocs serve
poetry run mcprojsim --help
```

## Makefile vs Poetry

The Makefile does **not** replace Poetry.
Poetry remains the source of truth for the Python environment and packaging metadata.
The Makefile mainly provides short, repeatable entry points for common workflows.

### Use Poetry when:

- you are experimenting with one-off commands
- you want direct control over tool flags
- you are debugging dependency or packaging issues
- you are inspecting the active virtual environment

### Use `make` when:

- you want a standard project workflow with a short command
- you want to avoid remembering long command lines
- you want a wrapper around docs, container, or registry tasks
- you want the repo-maintained defaults

### Practical interpretation

In practice, the relationship is:

- **Poetry** = canonical Python environment and packaging system
- **Makefile** = task launcher and workflow wrapper
- **scripts/** = higher-level automation where shell logic is too large for a Make target

### Examples of overlap

These pairs intentionally overlap:

| Goal | Direct command | Makefile / script wrapper |
|---|---|---|
| install dev environment | `poetry install --with dev,docs` | `make install` |
| run tests | `poetry run pytest` | `make test` |
| run formatting | `poetry run black src/ tests/` | `make format` |
| run docs locally | `poetry run mkdocs serve` | `make docs-serve` |
| build docs | `poetry run mkdocs build` | `make docs` or `./scripts/mkdocs.sh build` |
| build package | `poetry build` | `make build` or `./scripts/mkbld.sh` |

### Why the duplication is useful

The overlap is deliberate.
Poetry is well suited to running tools inside the managed environment.
The Makefile and scripts are better suited to packaging multi-step workflows into a single command.
This is especially useful for:

- release preparation
- container builds
- docs container lifecycle
- GHCR publishing
- CI parity

## Project structure

At a high level, the repository is organised like this:

```text
mcprojsim/
├── src/mcprojsim/          Python package source
│   ├── analysis/           Post-simulation analysis such as statistics and critical path logic
│   ├── exporters/          JSON, CSV, and HTML output generation
│   ├── models/             Pydantic data models for projects and simulation data
│   ├── parsers/            YAML / TOML parsing and error reporting
│   ├── simulation/         Sampling, scheduling, risks, and engine logic
│   ├── utils/              Logging and validation helpers
│   ├── cli.py              Click CLI entry point
│   └── config.py           Runtime configuration handling
├── tests/                  Unit and integration-style tests
├── docs/                   MkDocs documentation source
├── examples/               Example input files and sample output artifacts
├── scripts/                Build, release, verification, and docs-control scripts
├── bin/                    User-facing wrapper scripts such as container CLI launchers
├── Dockerfile              Main runtime container image
├── Dockerfile.docs         Documentation image
├── Makefile                Developer task shortcuts and container wrappers
├── pyproject.toml          Poetry metadata and dependency definitions
└── .github/workflows/      CI/CD workflows
```

### Directory purpose summary

#### `src/mcprojsim/`
This is the implementation.
If you are changing application behavior, most of your work will happen here.

#### `tests/`
This contains test coverage for the main subsystems.
Tests are run in CI and also during release preparation.

#### `docs/`
This contains the source for the published documentation site.
The docs are built with MkDocs and Material for MkDocs.

#### `examples/`
These are useful both for users and maintainers.
They are also used by the release automation as smoke-test inputs.

#### `scripts/`
These scripts hold more complex workflows that would be awkward in the Makefile.
Examples include:

- `mkrelease.sh`
- `mkghrelease.sh`
- `mkbld.sh`
- `docs-contctl.sh`
- `verify_setup.sh`

#### `bin/`
This holds user-facing helper wrappers.
In particular, [bin/mcprojsim.sh](https://github.com/johan162/mcprojsim/blob/main/bin/mcprojsim.sh) allows running the CLI through a container while mounting the host working directory into `/work`.

## Local development workflow

A typical local development session looks like this:

```bash
poetry install --with dev,docs
poetry run pytest
poetry run black src/ tests/
poetry run flake8 src/ tests/
poetry run mypy src/
poetry run mcprojsim validate examples/sample_project.yaml
poetry run mcprojsim simulate examples/sample_project.yaml --seed 42
```

If you prefer wrappers:

```bash
make install
make check
make test
make docs-serve
```

## The Makefile in detail

The Makefile provides a single entry point for common project tasks.
Some targets are thin wrappers while others contain real workflow logic.

### Important general behavior

The Makefile currently:

- requires Poetry to be installed
- requires either Podman or Docker to be installed
- checks whether Podman or Docker is running
- auto-detects whether proxy support should be used for container builds
- uses timestamp files to avoid rerunning some tasks unnecessarily

### Useful everyday targets

#### Setup and quality

```bash
make install
make check
make test
make test-short
make test-html
make pre-commit
```

Meaning:

- `make install` installs dependencies and prepares the local environment
- `make check` runs formatting, linting, and type checking targets
- `make test` runs the full test target with coverage enforcement
- `make test-short` is a faster no-coverage run
- `make test-html` produces coverage artifacts in `coverage.xml` and `htmlcov/`
- `make pre-commit` runs checks plus a shorter test pass

#### Documentation

```bash
make docs
make docs-serve
make docs-container-build
make docs-container-start
make docs-container-stop
make docs-container-status
make docs-container-logs
make docs-deploy
```

#### Packaging and release support

```bash
make build
```

This runs a larger pipeline that includes:

- install
- quality checks
- tests
- docs build
- package build
- artifact verification

#### Container management

```bash
make container-build
make container-build-proxy
make container-build-standard
make container-rebuild
make ghcr-login
make ghcr-push
make ghcr-logout
```

### Notes for maintainers

The Makefile includes some historical naming and a few targets that appear to have been adapted from an earlier project.
When updating it, preserve working behavior first and simplify inconsistencies in a dedicated maintenance pass.
For new contributors, the safest approach is to rely on the documented targets above rather than infer intent from every variable name.

## Build scripts

The `scripts/` directory contains the more detailed automation.
For a script-by-script overview, see [scripts/README.md](https://github.com/johan162/mcprojsim/blob/main/scripts/README.md).

Below is the developer interpretation of the most important scripts.

### `mkbld.sh`

Purpose:

- local and CI build validation pipeline
- static analysis
- tests with coverage
- package build
- `twine check`

Typical usage:

```bash
./scripts/mkbld.sh
./scripts/mkbld.sh --dry-run
```

Use this when you want a CI-like validation run locally.
It is also the main quality gate invoked by the CI workflow.

### `verify_setup.sh`

Purpose:

- check that a fresh environment is actually able to run the project
- confirm that the CLI works
- validate sample input
- run a smoke simulation

Use this after setting up a new development machine.

### `mkdocs.sh`

Purpose:

- serve docs locally
- build docs
- deploy docs
- clean docs artifacts

Typical usage:

```bash
./scripts/mkdocs.sh serve
./scripts/mkdocs.sh build
./scripts/mkdocs.sh deploy
```

### `docs-contctl.sh`

Purpose:

- lifecycle manager for the docs container image built from [Dockerfile.docs](https://github.com/johan162/mcprojsim/blob/main/Dockerfile.docs)

Typical usage:

```bash
./scripts/docs-contctl.sh start
./scripts/docs-contctl.sh status
./scripts/docs-contctl.sh logs --follow
./scripts/docs-contctl.sh stop
```

### `mkrelease.sh`

Purpose:

- local release orchestration for maintainers
- version bumping through Poetry
- changelog template insertion
- test and package validation
- branch merge workflow
- annotated tag creation
- push to remote and wait for CI

This is the main maintainer script for preparing a release tag.

### `mkghrelease.sh`

Purpose:

- create the GitHub Release object from the tag already pushed by `mkrelease.sh`
- confirm that workflows on `main` have completed successfully
- extract release notes from `CHANGELOG.md`
- upload the artifacts from `dist/`

This is the script that bridges local release preparation with the GitHub Release UI/API step.

## Main application container

The main runtime image is defined in [Dockerfile](https://github.com/johan162/mcprojsim/blob/main/Dockerfile).
It is a multi-stage build.

### Build structure

#### Builder stage
The `builder` stage:

- starts from `python:3.14-slim`
- installs Poetry
- copies the package source and packaging metadata
- optionally appends a proxy CA certificate to the system bundle
- runs `poetry install --only main`
- removes build-time tooling from the in-project virtual environment
- strips caches and non-essential artifacts

#### Runtime stage
The `runtime` stage:

- starts from `python:3.14-slim`
- creates a non-root `mcprojsim` user
- copies the built `.venv`
- sets `PATH` so the CLI entry point is available
- uses `mcprojsim` as the container entrypoint
- sets the working directory to `/work`

### Why the image is structured this way

The image is designed as a runtime CLI container rather than a general development container.
It therefore tries to:

- keep Poetry out of the final image
- avoid shipping unnecessary build tooling
- run as a non-root user
- make the CLI feel like a normal host command when combined with a bind mount

### Build the main container with raw commands

#### Standard build with Podman

```bash
podman build -t mcprojsim:latest -t mcprojsim:$(poetry version --short) .
```

#### Standard build with Docker

```bash
docker build -t mcprojsim:latest -t mcprojsim:$(poetry version --short) .
```

#### Proxy-aware build with Podman

```bash
podman build \
  --build-arg USE_PROXY_CA=true \
  --secret id=proxy_ca,src=CA_proxy_fw_all.pem \
  -t mcprojsim:latest \
  -t mcprojsim:$(poetry version --short) \
  .
```

#### Proxy-aware build with Docker

```bash
docker build \
  --build-arg USE_PROXY_CA=true \
  --secret id=proxy_ca,src=CA_proxy_fw_all.pem \
  -t mcprojsim:latest \
  -t mcprojsim:$(poetry version --short) \
  .
```

### Build the main container with Make

```bash
make container-build
```

This is the preferred wrapper target.
It auto-detects whether a proxy-aware build should be used.

Explicit variants:

```bash
make container-build-standard
make container-build-proxy
```

### Run the main container directly

#### Podman

```bash
podman run --rm -v "$PWD:/work:Z" mcprojsim validate examples/sample_project.yaml
podman run --rm -v "$PWD:/work:Z" mcprojsim simulate examples/sample_project.yaml --seed 42
```

#### Docker

```bash
docker run --rm -v "$PWD:/work" mcprojsim validate examples/sample_project.yaml
docker run --rm -v "$PWD:/work" mcprojsim simulate examples/sample_project.yaml --seed 42
```

### Run through the wrapper script

The wrapper in [bin/mcprojsim.sh](https://github.com/johan162/mcprojsim/blob/main/bin/mcprojsim.sh) provides a more convenient interface for both users and developers.
It:

- auto-detects Podman or Docker
- builds the image if missing
- mounts the chosen working directory into `/work`
- rewrites file paths when possible

Typical usage:

```bash
./bin/mcprojsim.sh --help
./bin/mcprojsim.sh validate examples/sample_project.yaml
./bin/mcprojsim.sh simulate examples/sample_project.yaml --seed 42
```

## Documentation build workflow

There are two supported docs workflows.

### Fast local docs workflow

This is the best option when editing docs frequently.

```bash
poetry install --with docs
poetry run mkdocs serve
```

Equivalent wrappers:

```bash
make docs
make docs-serve
./scripts/mkdocs.sh serve
```

### Containerized docs workflow

This is useful when you want to validate the containerized docs image itself or mimic a deployment-like environment.

```bash
make docs-container-build
make docs-container-start
make docs-container-status
make docs-container-logs
make docs-container-stop
```

Or directly:

```bash
./scripts/docs-contctl.sh build
./scripts/docs-contctl.sh start -p 8100
./scripts/docs-contctl.sh status
./scripts/docs-contctl.sh logs --follow
./scripts/docs-contctl.sh stop
```

## Documentation container in detail

The docs image is defined in [Dockerfile.docs](https://github.com/johan162/mcprojsim/blob/main/Dockerfile.docs).
It is separate from the main CLI image.

### Build structure

#### Builder stage
The docs builder stage:

- starts from `python:3.13-slim`
- copies `pyproject.toml`, `mkdocs.yml`, `docs/`, `src/`, and `README.md`
- optionally appends a proxy CA certificate to the system trust bundle
- installs MkDocs, Material, mkdocstrings, and the package itself
- runs `mkdocs build --strict`

#### Server stage
The final stage:

- starts from `nginx:alpine`
- copies the built static site into `/usr/share/nginx/html`
- installs a custom nginx config
- serves docs on port `80`
- exposes a `/health` endpoint

### Build the docs image with raw commands

#### Standard build with Podman

```bash
podman build -f Dockerfile.docs -t mcprojsim-docs .
```

#### Standard build with Docker

```bash
docker build -f Dockerfile.docs -t mcprojsim-docs .
```

#### Proxy-aware build

```bash
podman build -f Dockerfile.docs \
  --build-arg USE_PROXY_CA=true \
  -t mcprojsim-docs \
  .
```

or:

```bash
docker build -f Dockerfile.docs \
  --build-arg USE_PROXY_CA=true \
  -t mcprojsim-docs \
  .
```

For the docs image, the CA file is expected in the build context when proxy support is enabled.
See the certificate section below for the details.

### Run the docs image with raw commands

#### Podman

```bash
podman run -d --rm -p 9090:80 --name mcprojsim-docs mcprojsim-docs
```

#### Docker

```bash
docker run -d --rm -p 9090:80 --name mcprojsim-docs mcprojsim-docs
```

Then open <http://localhost:9090>.

## Container certificate handling behind a company firewall

This project explicitly supports environments where HTTPS traffic is intercepted and re-signed by an internal CA.
That matters because Poetry, `pip`, and related tools may otherwise fail TLS validation during image builds.

The certificate handling is different in the two Dockerfiles.
That difference is worth understanding.

### Common problem being solved

In a corporate environment you may see failures such as:

- TLS certificate verify failed
- unable to get local issuer certificate
- Poetry cannot fetch dependencies
- `pip` cannot connect to PyPI or GitHub

The fix is usually to trust the company CA during the image build.

## Main container certificate handling

The main image in [Dockerfile](https://github.com/johan162/mcprojsim/blob/main/Dockerfile) uses a **build secret**.

### How it works

The Dockerfile defines:

- `ARG USE_PROXY_CA=false`
- `ARG CA_CERT_FILE=CA_proxy_fw_all.pem`
- a secret mount at `/run/secrets/proxy_ca`

During the build:

1. if `USE_PROXY_CA=false`, nothing special is done
2. if `USE_PROXY_CA=true`, the build expects the secret `proxy_ca`
3. the secret contents are appended to `/etc/ssl/certs/ca-certificates.crt`
4. `REQUESTS_CA_BUNDLE` and `SSL_CERT_FILE` are set to that bundle

### Why this is good

Using a secret means:

- the certificate does not need to be committed to the repository
- the certificate does not need to remain in the final image layers as a copied file
- the build is safer for internal PKI material

### Raw command example

```bash
podman build \
  --build-arg USE_PROXY_CA=true \
  --secret id=proxy_ca,src=CA_proxy_fw_all.pem \
  -t mcprojsim .
```

### Makefile support

The Makefile makes this easier through:

- `PROXY_CA_FILE := CA_proxy_fw_all.pem`
- proxy auto-detection through proxy environment variables or presence of the file
- `make container-build` which dispatches to either:
  - `make container-build-standard`
  - `make container-build-proxy`

The proxy-specific target validates that the CA file exists and then passes the secret correctly.

## Documentation container certificate handling

The docs image in [Dockerfile.docs](https://github.com/johan162/mcprojsim/blob/main/Dockerfile.docs) currently uses a different mechanism.
It expects a CA file in the build context when proxy support is enabled.

### How it works

The docs Dockerfile defines:

- `ARG USE_PROXY_CA=false`
- `ARG CA_CERT_FILE=CA_proxy_fw_all.pem`
- `COPY ${CA_CERT_FILE}* /tmp/certs/`

During the build:

1. the file matching `CA_proxy_fw_all.pem` is copied into the build context path `/tmp/certs/`
2. when `USE_PROXY_CA=true`, the file is appended to the system CA bundle
3. `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, and `PIP_CERT` are set to the updated bundle

### Operational consequence

For the docs image, enabling proxy support means the CA file must be available in the project root at build time.
This differs from the main container, which uses a build secret.

### `docs-contctl.sh` and proxy support

The docs control script supports:

```bash
MCPROJSIM_USE_PROXY_CA=true ./scripts/docs-contctl.sh build
```

However, that script currently passes the build arg and relies on the CA file being present in the build context.
So if you are behind a corporate firewall, make sure `CA_proxy_fw_all.pem` exists in the project root before invoking the docs image build.

## Recommended certificate handling workflow

For maintainers working behind a company firewall:

1. place the CA certificate in the project root as `CA_proxy_fw_all.pem`
2. use `make container-build` for the main image
3. use `MCPROJSIM_USE_PROXY_CA=true ./scripts/docs-contctl.sh build` for the docs image
4. remove or secure the CA file when not needed

### Important security note

Do not commit internal CA material to the repository.
Treat it as an environment-specific file.
Use the filename convention expected by the tooling, but keep the actual certificate local.

## Raw container commands vs Makefile wrappers

For developers, both styles are useful.

### Use raw Podman/Docker commands when:

- debugging image build behavior
- testing exact flags
- validating a Dockerfile change
- reproducing CI/container issues manually

### Use Makefile wrappers when:

- you want project defaults
- you want proxy auto-detection
- you want fewer memorised commands
- you are switching often between tasks

A good rule is:

- **debug with raw commands**
- **work daily with `make`**

## Release management

Release management is split into two stages:

1. local release preparation with `mkrelease.sh`
2. GitHub release creation with `mkghrelease.sh`

This is intentionally more explicit than a single black-box release command.
It lets the maintainer confirm local state, branch state, and workflow success before publishing the GitHub release entry.

## `mkrelease.sh` in detail

Script: [scripts/mkrelease.sh](https://github.com/johan162/mcprojsim/blob/main/scripts/mkrelease.sh)

### Purpose

This is the local maintainer release script.
It:

- validates repository state
- requires a clean `develop` branch
- runs quality checks and smoke simulations
- updates the Poetry version
- prepares a changelog entry template
- stages and commits release prep changes
- squash-merges `develop` into `main`
- creates an annotated tag `v<version>`
- pushes `main` and the tag
- merges `main` back into `develop`
- waits for GitHub Actions to complete
- rebuilds distribution artifacts

### Typical usage

Dry-run first:

```bash
./scripts/mkrelease.sh 0.2.1 patch --dry-run
```

Actual release example:

```bash
./scripts/mkrelease.sh 0.2.1 patch
```

Pre-release example:

```bash
./scripts/mkrelease.sh 0.3.0rc1 minor
```

### Preconditions

The script expects:

- to be run from the project root
- Poetry to be installed and working
- dev tools available in the Poetry environment
- current branch = `develop`
- a clean working tree
- `gh` available for workflow watching

### Release phases performed by the script

#### Phase 1: validation
- project root check
- Poetry environment and tool availability
- branch and working tree check
- pull latest `develop`
- validate requested version format
- ensure tag does not already exist

#### Phase 2: QA and smoke testing
- full pytest run with coverage threshold
- `mypy`
- `black --check`
- smoke simulations on example projects
- `poetry build`
- `twine check dist/*`

#### Phase 3: release preparation
- `poetry version <version>`
- changelog template insertion into `CHANGELOG.md`
- maintainer pauses to edit changelog text
- final smoke test

#### Phase 4: release execution
- commit release preparation on `develop`
- checkout `main`
- squash merge `develop`
- create the release commit on `main`
- create annotated tag `v<version>`
- push `main` and tag

#### Phase 5: branch reconciliation
- checkout `develop`
- merge `main` back into `develop` with `--no-ff`
- push updated `develop`

#### Phase 6: wait for workflows
- watches GitHub Actions status
- fails if CI fails

#### Phase 7: rebuild distribution artifacts
- rebuilds `dist/`
- reruns `twine check`

### Maintainer recommendation

Always run the dry-run first.
That is the safest way to confirm:

- version format
- branch state assumptions
- intended git operations
- the release type

## `mkghrelease.sh` in detail

Script: [scripts/mkghrelease.sh](https://github.com/johan162/mcprojsim/blob/main/scripts/mkghrelease.sh)

### Purpose

This script creates the GitHub Release object after the tag already exists and CI has completed.
It is a separate step from `mkrelease.sh`.

### Typical usage

```bash
./scripts/mkghrelease.sh --dry-run
./scripts/mkghrelease.sh
```

If needed:

```bash
./scripts/mkghrelease.sh --pre-release
```

### Preconditions

The script expects:

- current branch = `main`
- clean working tree
- local `main` synced with `origin/main`
- `gh` installed and authenticated
- recent workflows on `main` completed successfully
- a tag already present on `main`
- built artifacts present in `dist/`

### What the script checks

It validates:

- GitHub CLI availability and version
- GitHub authentication
- no running workflows on `main`
- latest workflow conclusion is `success`
- latest tag format is valid
- GitHub release does not already exist for that tag
- `dist/` contains the expected wheel and sdist for that version

### Release notes behavior

The script extracts the section matching the current tag from `CHANGELOG.md`.
It writes those notes to a temporary file and opens the editor defined by `EDITOR` or `VISUAL`.
That gives the maintainer a final editing chance before creating the GitHub release.

### Pre-release detection

The script automatically treats tags ending with `rcN` as pre-releases.
You can override that behavior with `--pre-release`.

### Relationship to PyPI publishing

`mkghrelease.sh` creates the GitHub Release entry.
The actual package publishing is then handled by the GitHub Actions release workflow described later in this document.

## Suggested release sequence for maintainers

A practical end-to-end release flow is:

```bash
# 1. Validate the repository is ready
./scripts/mkbld.sh

# 2. Preview the release steps
./scripts/mkrelease.sh 0.2.1 patch --dry-run

# 3. Execute the local release process
./scripts/mkrelease.sh 0.2.1 patch

# 4. Confirm workflows on main succeeded
gh run list --branch main --limit 5

# 5. Create the GitHub Release entry
./scripts/mkghrelease.sh
```

## Compact release checklist

Use this checklist before creating a release.

### Before running `mkrelease.sh`

- confirm the working tree is clean
- confirm the current branch is `develop`
- confirm `poetry install --with dev,docs` has completed successfully
- run `./scripts/mkbld.sh`
- review the changes included in the release
- confirm the target version number and whether it is a production release or pre-release

### During `mkrelease.sh`

- start with `--dry-run`
- verify the reported git operations are expected
- update the generated `CHANGELOG.md` entry with final release notes
- confirm the script completes the version, branch, tag, and push steps successfully
- confirm the CI run triggered by the release completes successfully

### Before running `mkghrelease.sh`

- confirm local `main` is in sync with `origin/main`
- confirm no workflows are still running on `main`
- confirm the latest workflow on `main` succeeded
- confirm `dist/` contains the wheel and source distribution for the target version
- confirm `gh auth status` succeeds

### During `mkghrelease.sh`

- review the extracted release notes carefully
- confirm whether the release should be marked as a pre-release
- confirm the GitHub Release is created with the expected artifacts

### After the GitHub Release is published

- verify that the publish workflow started
- verify whether the tag should route to PyPI or TestPyPI
- verify the package appears in the target registry
- verify the release notes and attached artifacts on GitHub

## GitHub Actions and CI/CD workflows

The repository currently contains three workflows:

- [.github/workflows/ci.yml](https://github.com/johan162/mcprojsim/blob/main/.github/workflows/ci.yml)
- [.github/workflows/docs.yml](https://github.com/johan162/mcprojsim/blob/main/.github/workflows/docs.yml)
- [.github/workflows/publish-to-pypi.yml](https://github.com/johan162/mcprojsim/blob/main/.github/workflows/publish-to-pypi.yml)

### 1. Continuous integration workflow

File: [ci.yml](https://github.com/johan162/mcprojsim/blob/main/.github/workflows/ci.yml)

#### Triggers

- pushes to `develop`
- pushes to `main`
- pushes to `feature/**`, `bugfix/**`, `hotfix/**`
- pull requests targeting `develop` or `main`

#### What it does

The `build-and-test` job:

- runs on `ubuntu-latest`
- uses Python `3.14`
- installs `graphviz`
- installs Poetry with `pipx`
- enables in-project virtual environments
- caches `.venv`
- runs `poetry install --with dev`
- executes `./scripts/mkbld.sh`

#### Artifacts

On failure it uploads:

- `htmlcov/`
- `.coverage`
- `pytest-report.xml`

On success it uploads:

- `dist/` artifacts with a metadata-rich artifact name containing branch, short SHA, timestamp, and Python version

#### Developer interpretation

This workflow is the main quality gate.
If you want to reproduce CI locally, `./scripts/mkbld.sh` is the closest equivalent.

### 2. Documentation workflow

File: [docs.yml](https://github.com/johan162/mcprojsim/blob/main/.github/workflows/docs.yml)

#### Triggers

- pushes to `main` or `develop` affecting `docs/**`, `mkdocs.yml`, or the workflow file itself
- pull requests to `main` or `develop` affecting docs paths
- manual dispatch via `workflow_dispatch`

#### Build job

The `build` job:

- checks out with full history
- sets up Python `3.14`
- installs Poetry
- runs `poetry install --with docs`
- creates the `docs/CHANGELOG.md` symlink
- runs `poetry run mkdocs build`
- uploads the built `site/` artifact

#### Deploy job

The `deploy` job runs only when:

- the event is a push
- the branch is `main`

It then:

- configures git identity for the GitHub Actions bot
- runs `poetry run mkdocs gh-deploy --force`

#### Developer interpretation

In practice, this means:

- docs changes are validated on both `develop` and `main`
- published documentation is deployed only from `main`
- `main` is the source of truth for GitHub Pages deployment

### 3. Publish-to-PyPI workflow

File: [publish-to-pypi.yml](https://github.com/johan162/mcprojsim/blob/main/.github/workflows/publish-to-pypi.yml)

#### Trigger

- GitHub Release published

This means the workflow depends on the GitHub Release object, not only on the existence of a tag.
That is why `mkghrelease.sh` matters in the release flow.

#### What it does

The workflow:

- checks out the repo
- sets up Python `3.14`
- validates the tag format type
- installs Poetry and caches `.venv`
- installs dev-only tooling without the project root package
- runs `poetry check`
- runs `poetry build`
- runs `poetry run twine check dist/*`

#### Production vs pre-release routing

The workflow decides where to publish based on the tag name:

- exact `vMAJOR.MINOR.PATCH` → publish to real PyPI
- anything else → publish to TestPyPI

Examples:

- `v0.2.0` → PyPI
- `v0.2.0rc1` → TestPyPI

#### Secrets expected by the workflow

- `PYPI_API_TOKEN`
- `TEST_PYPI_API_TOKEN`

### CI/CD relationship summary

The overall flow is:

1. developer or maintainer pushes code
2. `ci.yml` validates code quality and package buildability
3. `docs.yml` validates docs changes and deploys docs from `main`
4. maintainer runs `mkrelease.sh`
5. maintainer runs `mkghrelease.sh`
6. GitHub Release publication triggers `publish-to-pypi.yml`
7. package is published to PyPI or TestPyPI depending on tag format

## Common developer workflows

### Fast local iteration

```bash
poetry install --with dev,docs
poetry run pytest tests/test_simulation.py
poetry run black src/ tests/
poetry run mcprojsim simulate examples/sample_project.yaml --seed 42
```

### Pre-PR validation

```bash
./scripts/mkbld.sh
```

or roughly equivalently:

```bash
poetry run black --check src/ tests/
poetry run flake8 src/ tests/
poetry run mypy src/
poetry run pytest
poetry build
poetry run twine check dist/*
```

### Docs editing workflow

```bash
poetry install --with docs
make docs-serve
```

### Docs container validation

```bash
make docs-container-build
make docs-container-start
make docs-container-status
```

### Main container validation

```bash
make container-build
./bin/mcprojsim.sh validate examples/sample_project.yaml
./bin/mcprojsim.sh simulate examples/sample_project.yaml --seed 42
```

## Troubleshooting

### Poetry is installed but commands fail

Check:

```bash
poetry env info
poetry install --with dev,docs
```

### `mcprojsim` CLI is not found inside Poetry

Run:

```bash
poetry install
poetry run mcprojsim --help
```

### Docs build fails due to missing MkDocs tooling

Run:

```bash
poetry install --with docs
```

### Container build fails with certificate errors

Check whether you are behind a corporate proxy.
If so:

- place the CA file at `CA_proxy_fw_all.pem`
- use `make container-build` or `make container-build-proxy`
- for docs builds, ensure the file is present before calling the docs image build

### `mkghrelease.sh` fails because workflows are still running

Wait for GitHub Actions to finish:

```bash
gh run list --branch main --limit 5
```

Then rerun the script.

### Release script stops on branch or cleanliness checks

That behavior is expected.
The release automation is intentionally conservative and stops rather than guessing.

## Recommended developer habits

- keep Poetry environments in-project for predictability
- use `./scripts/mkbld.sh` before opening a PR
- use `make docs-serve` for fast documentation work
- use raw container commands when debugging Dockerfile behavior
- use `make container-build` for everyday image builds
- never commit internal CA certificates
- always dry-run `mkrelease.sh` before a real release
- treat `CHANGELOG.md` as release input, not as an afterthought

## Appendix: common commands cheat sheet

This appendix collects the commands used most often during daily development and release work.

### Environment setup

```bash
poetry config virtualenvs.in-project true
poetry install --with dev,docs
poetry env info
```

### Local quality checks

```bash
poetry run pytest
poetry run black src/ tests/
poetry run flake8 src/ tests/
poetry run mypy src/
./scripts/mkbld.sh
make check
make test
```

### CLI smoke tests

```bash
poetry run mcprojsim --help
poetry run mcprojsim validate examples/sample_project.yaml
poetry run mcprojsim simulate examples/sample_project.yaml --seed 42
./scripts/verify_setup.sh
```

### Documentation

```bash
poetry run mkdocs serve
poetry run mkdocs build
make docs-serve
make docs
./scripts/mkdocs.sh serve
./scripts/mkdocs.sh build
```

### Documentation container

```bash
make docs-container-build
make docs-container-start
make docs-container-status
make docs-container-logs
make docs-container-stop
./scripts/docs-contctl.sh build
./scripts/docs-contctl.sh start -p 8100
```

### Main container

```bash
make container-build
make container-build-standard
make container-build-proxy
./bin/mcprojsim.sh validate examples/sample_project.yaml
./bin/mcprojsim.sh simulate examples/sample_project.yaml --seed 42
podman run --rm -v "$PWD:/work:Z" mcprojsim --help
docker run --rm -v "$PWD:/work" mcprojsim --help
```

### Release workflow

```bash
./scripts/mkrelease.sh 0.2.1 patch --dry-run
./scripts/mkrelease.sh 0.2.1 patch
gh run list --branch main --limit 5
./scripts/mkghrelease.sh --dry-run
./scripts/mkghrelease.sh
```

### Registry and packaging

```bash
poetry build
poetry run twine check dist/*
make ghcr-login
make ghcr-push GITHUB_USER=<github-user>
make ghcr-logout
```

## Related references

- [README.md](https://github.com/johan162/mcprojsim/blob/main/README.md)
- [QUICKSTART.md](https://github.com/johan162/mcprojsim/blob/main/QUICKSTART.md)
- [scripts/README.md](https://github.com/johan162/mcprojsim/blob/main/scripts/README.md)
- [pyproject.toml](https://github.com/johan162/mcprojsim/blob/main/pyproject.toml)
- [Makefile](https://github.com/johan162/mcprojsim/blob/main/Makefile)
- [Dockerfile](https://github.com/johan162/mcprojsim/blob/main/Dockerfile)
- [Dockerfile.docs](https://github.com/johan162/mcprojsim/blob/main/Dockerfile.docs)
- [ci.yml](https://github.com/johan162/mcprojsim/blob/main/.github/workflows/ci.yml)
- [docs.yml](https://github.com/johan162/mcprojsim/blob/main/.github/workflows/docs.yml)
- [publish-to-pypi.yml](https://github.com/johan162/mcprojsim/blob/main/.github/workflows/publish-to-pypi.yml)
