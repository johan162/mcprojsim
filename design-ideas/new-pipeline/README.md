# Proposed Release Pipeline

This directory contains a proposal for replacing the current largely local release flow with a smaller local release-preparation script and CI-driven release automation.

The proposal is intentionally isolated under `design-ideas/`.
It does not modify the active production workflows.

## Why This Proposal Exists

The current release flow works, but it has avoidable duplication and a few fragile edges:

- Local scripts run quality gates that CI runs again
- Release creation is split across `mkchlogentry.sh`, `mkrelease.sh`, and `mkghrelease.sh`
- The release process mutates branches locally and tags locally
- Docs deployment is path-gated, so version-only releases can skip docs publishing
- PyPI publishing rebuilds packages in a later workflow instead of consuming the prepared release artifacts directly
- Current CI does not produce all release artifacts, even though GitHub Releases require more than wheel + sdist

## Current Repo Findings

These observations are based on the current checked-in workflows and scripts:

- `.github/workflows/ci.yml` runs formatting, linting, type checking, tests, smoke tests, and `poetry build`, but does not create the MCP bundle or the User Guide PDF
- `.github/workflows/docs.yml` only runs on `main` when docs-related paths change, so a version-only release can skip docs deployment
- `.github/workflows/publish-to-pypi.yml` rebuilds the package after a GitHub Release is published
- `scripts/mkrelease.sh` still performs local testing, local artifact creation, local branch merges, local tagging, and waits for CI
- `scripts/mkghrelease.sh` separately validates artifacts and creates the GitHub Release via `gh`
- `scripts/README.md` documents `mkrelease2.sh`, but that file does not currently exist in `scripts/`

## Proposal Summary

The proposed final pipeline is:

1. Developer prepares the release on `develop`
2. The local script performs the same squash-merge-to-`main` and back-merge-to-`develop` branch flow used today
3. CI validates every change and prepares build artifacts
4. After a successful CI run on `main`, a dedicated release workflow creates the tag, GitHub Release, and PyPI publish from CI
5. Docs publish on release tags, not only on docs path changes

The local script becomes smaller and more deterministic than today, while still preserving the current branch workflow:

- Validate branch and working tree state
- Verify the CHANGELOG entry already exists
- Bump the version
- Commit the release-preparation changes on `develop`
- Push `develop`
- Squash-merge `develop` into `main`
- Push `main`
- Back-merge `main` into `develop`
- Push `develop` again

It does not:

- Run the full quality suite
- Build artifacts
- Create tags
- Create GitHub Releases
- Publish to PyPI

## Proposed Files In This Directory

- `mkrelease-small.sh`: proposed minimal local release-preparation script
- `ci.yml`: proposed read-only CI workflow for validation and build artifacts
- `release.yml`: proposed privileged release workflow triggered only after successful CI on `main`
- `docs.yml`: proposed docs workflow that always publishes on release tags

## Proposed Target Architecture

```txt
Developer workstation                         GitHub Actions
─────────────────────                         ──────────────

1. Create CHANGELOG entry
   - ./scripts/mkchlogentry.sh 0.7.3 patch
   - or /changelog-entry

2. Prepare release on develop
   - ./scripts/mkrelease-small.sh 0.7.3 patch
   - validates clean repo state
   - validates CHANGELOG entry exists
   - poetry version 0.7.3
      - git commit + push develop                  ──→ ci.yml on develop
                                                   - format/lint/type check
                                                   - tests + smoke
                                                   - build verification

3. Script squash-merges develop -> main
      and back-merges main -> develop             ──→ ci.yml on main
                                                   - same validation
                                                   - build release artifacts
                                                   - upload release-dist artifact

                                             ──→ release.yml on successful CI for main
                                                   - verify release commit intent
                                                   - verify version > latest tag
                                                   - verify CHANGELOG entry
                                                   - download release-dist artifact
                                                   - create tag vX.Y.Z
                                                   - create GitHub Release
                                                   - publish exact dist/* to PyPI/TestPyPI

                                             ──→ docs.yml on tag vX.Y.Z
                                                   - build docs
                                                   - deploy docs to gh-pages
```

## Why A Separate `release.yml` Is Better Than Putting Release Logic Inside `ci.yml`

The earlier draft suggested a `release` job inside `ci.yml`.
That works, but a separate workflow is safer:

- `ci.yml` can remain read-only with `contents: read`
- release permissions are isolated to the one workflow that actually needs them
- release only runs after CI has conclusively succeeded on `main`
- rerunning CI does not automatically imply re-running privileged tag/release logic unless the release workflow gates allow it
- failure analysis is cleaner because validation and release concerns are separated

## Key Safety Properties

The proposed design is optimized to minimize unknown or hard-to-revert states.

### 1. No Local Tagging

Tags are created only by CI after validation on `main` succeeds.

Effect:
- no local tag pushed before CI passes
- no local/main divergence caused by partial release scripts

### 2. Keep Local Merge Automation, Remove Local Tagging

This revised proposal preserves the current local branch choreography:

- commit release preparation on `develop`
- squash-merge `develop` into `main`
- push `main`
- back-merge `main` into `develop`

What changes is that tagging and publishing move out of the local script and into CI.

Effect:
- branch history stays aligned with the workflow you already use today
- local operator experience changes less
- the most irreversible steps still move to CI

### 3. Release Workflow Is Idempotent

The release workflow must exit cleanly if:

- the tag already exists
- the version in `pyproject.toml` is not newer than the latest tag
- the commit is not an approved release commit
- the expected CHANGELOG entry is missing

Effect:
- safe reruns
- reduced chance of duplicate releases

### 4. Release Artifacts Are Built In CI

The release workflow publishes artifacts built in GitHub Actions, not on a developer machine.

Effect:
- reproducibility
- cleaner provenance
- easier post-failure recovery because artifacts are attached to the CI run

### 5. Docs Build On Tags

Documentation deploys when a release tag is created.

Effect:
- docs stay in sync with released versions
- no path-filter surprises on version-only releases

## Proposed Improvements Beyond The Initial Draft

This proposal tightens the earlier idea in a few important ways.

### Improvement 1: Dedicated Release Workflow

Use `workflow_run` on successful CI for `main` rather than embedding release logic inside CI.

Reason:
- better separation of privileges and responsibilities

### Improvement 2: Explicit Release Intent Check

Only release if the `main` commit represents an actual release commit produced by the release script.

Suggested gates:
- commit message contains `release: X.Y.Z` or another explicitly approved release-commit format
- `pyproject.toml` version is newer than the latest tag
- `CHANGELOG.md` contains `## [vX.Y.Z] - YYYY-MM-DD`

Reason:
- prevents every merge to `main` from attempting a release

### Improvement 3: Build All Release Artifacts In CI

The release artifact set should include:

- `dist/mcprojsim-<version>-py3-none-any.whl`
- `dist/mcprojsim-<version>.tar.gz`
- `dist/mcprojsim-mcp-bundle-<version>.zip`
- `mcprojsim_user_guide-v<version>.pdf`

Reason:
- aligns CI build output with the GitHub Release contract

### Improvement 4: Prefer Trusted Publishing For PyPI

The release workflow should publish via GitHub OIDC trusted publishing if possible.
If that is not yet configured, token-based publishing can remain temporarily.

Reason:
- lower secret-management risk

### Improvement 5: Stop Mutating Tracked Template Files During PDF Builds

The current PDF build path updates `docs/user_guide/report_template.tex` in place during the build.
That is workable locally, but it is not a great release-pipeline primitive.

Recommended follow-up:
- generate a versioned derived template in `.build/` instead of editing a tracked source file in place

Reason:
- cleaner CI builds
- less risk of confusing dirty-worktree side effects

### Improvement 6: Clean Up Stale Docs About `mkrelease2.sh`

The repo currently documents `scripts/mkrelease2.sh`, but the file does not exist.

Recommended follow-up:
- either add the real script or remove the docs reference when production changes are made

Reason:
- avoids operator confusion during rollout

## Proposed Operator Workflow

### Normal Release

1. Create the CHANGELOG entry:

```bash
./scripts/mkchlogentry.sh 0.7.3 patch
```

2. Edit `CHANGELOG.md` to replace placeholders with final notes

3. Run the release script:

```bash
./scripts/mkrelease-small.sh 0.7.3 patch
```

4. The script will:
- commit the release prep on `develop`
- push `develop`
- squash-merge `develop` into `main`
- push `main`
- back-merge `main` into `develop`
- push `develop`

5. Wait for:
- `ci.yml` on `main`
- `release.yml`
- `docs.yml` on the new tag

### Example: Patch Release `0.7.3`

```bash
./scripts/mkchlogentry.sh 0.7.3 patch
$EDITOR CHANGELOG.md
./scripts/mkrelease-small.sh 0.7.3 patch
git log --oneline -3
```

Expected recent commit subjects:

```txt
chore(release): prepare v0.7.3
release: 0.7.3
chore: sync develop with main after release v0.7.3
```

After that:

1. CI validates and builds on `main`
2. release workflow creates `v0.7.3`
3. GitHub Release is created with all release artifacts
4. PyPI publish runs from CI
5. docs deploy on the new tag

## Failure And Recovery Model

### If The Local Script Fails

State is usually still simple:
- a local branch switch or merge may have happened
- no tag has been created
- no GitHub Release has been created
- no PyPI publish has happened

Recovery:
- inspect the current branch
- abort or repair the local merge state if needed
- rerun the script

### If CI Fails On `develop`

State is simple:
- nothing released
- no tag
- no GitHub Release

Recovery:
- fix on `develop`
- push again

### If CI Fails On `main`

State is still recoverable:
- no release should be created because `release.yml` only runs after successful CI

Recovery:
- fix forward with a follow-up commit or revert the merge on `main`

### If Release Workflow Fails After Artifact Download But Before Tag Creation

State remains safe:
- no official release exists yet

Recovery:
- fix the workflow issue
- rerun the release workflow for the same successful CI run

### If Release Workflow Fails After Tag Creation But Before PyPI Publish

State is partially published:
- git tag may already exist
- GitHub Release may or may not exist

Recovery plan:
- make the workflow detect and reuse an existing tag
- make GitHub Release creation idempotent where possible
- allow a manual rerun path that resumes publish instead of rebuilding logic from scratch

This is exactly why release gating and idempotency checks are important.

## Rollout Recommendation

When turning this proposal into production, do it in stages.

### Stage 1

- add `mkrelease-small.sh`
- add new `ci.yml`, `release.yml`, and `docs.yml`
- keep existing scripts temporarily
- do one release with extra maintainer supervision

### Stage 2

- stop using `mkghrelease.sh` for normal releases
- retire local tag creation from `mkrelease.sh`
- switch docs to tag-driven publishing fully

### Stage 3

- remove obsolete release-script paths and stale docs
- optionally add merge-queue protections or protected environments for release/publish jobs

## Recommendation

The best final design for this repo, given your current branch discipline, is:

- a smaller local release script that still performs the existing squash-merge and back-merge flow
- a read-only CI workflow
- a separate privileged release workflow triggered only after successful CI on `main`
- tag-triggered docs publishing
- PyPI publish from CI-built release artifacts

That preserves the workflow operators already know while still moving the highest-risk irreversible steps out of the workstation and into CI.