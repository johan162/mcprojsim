## [v0.11.0] - 2026-04-01

Release Type: minor

### 📋 Summary
This release adds a configurable histogram bin count for distribution charts, extends MCP server capabilities to cover two-pass scheduling and sprint override inputs, and refreshes documentation across sprint planning, examples, and the getting-started guide.

### ✨ Additions
- Added `histogram_bins` config field and `--number-bins` CLI flag to control the number of bins in simulation output distribution charts (default 50)

### 🚀 Improvements
- Updated MCP server bundle to reflect latest NL processing capabilities and new MCP command coverage
- Updated MCP server and NL processor to correctly handle two-phase simulation and `future_sprint_overrides` project inputs

### 📚 Documentation
- Updated examples to include the P10 confidence percentile added in the previous release
- Synced the getting-started guide with current simulate flags and output behavior

### 🛠 Internal
- Aded rendered PDF artifacts for all design documents for user with a full LaTeX setup
- Added addendum for a suggestion how to make use of team size into sprint-based-planning design document
- Improved design-doc build tooling to report an explicit error when xelatex is failing


## [v0.10.1] - 2026-03-31

Release Type: patch

### 📋 Summary
This release tightens input validation and keeps documentation aligned with current implementation. 
It focuses on safer config parsing, clearer reporting, and a broad refresh of the user-facing docs and formal grammar.

### 🚀 Improvements
- Improved input validation so malformed project/config data and invalid CLI option combinations fail earlier with clearer feedback
- Improved sprint-planning reporting by making future sprint override assumptions more explicit in console and report output
- Improved formal grammar coverage so project, config, and sprint-planning structures are documented in a cleaner implementation-aligned layout

### 🐛 Bug Fixes
- Fixed nested config validation so unknown keys in nested config models now fail fast instead of being silently accepted
- Fixed requirements and user-guide mismatches around sprint planning, output flags, risks, uncertainty factors, project-file fields, and estimation behavior

### 📚 Documentation
- Rewrote the formal grammar specification for clarity, correctness, and full coverage of current project and config file structures
- Updated sprint planning, configuration, project-file, risks, task-estimation, uncertainty-factor, interpreting-results, and getting-started documentation to match current behavior and defaults
- Expanded CLI documentation to cover recently added simulate flags and how they affect console and export output

### 🛠 Internal
- Applied formatting and cleanup updates to keep modified files consistent after the documentation and validation changes
- Some additional negative test cases to verify robustness of file parser


## [v0.10.0] - 2026-03-30

Release Type: minor

### 📋 Summary
This release introduces two-pass criticality-aware constrained scheduling to improve outcomes in resource-contention scenarios. It also adds end-to-end examples, traceability outputs, and supporting test and documentation updates.

### ✨ Additions
- Added two-pass criticality-aware constrained scheduling mode with pass-1 criticality indexing and pass-2 priority-ordered dispatch
- Added example files used for two-pass and contention-oriented documentation walkthroughs

### 🐛 Bug Fixes
- Fixed a race condition in parallel test execution

### 📚 Documentation
- Added a dedicated User Guide section for multi-phase two-pass simulation with usage examples and interpretation guidance
- Updated development and design documentation related to release workflow and build setup

### 🛠 Internal
- Added two-pass simulation fixtures, integration tests, and dedicated documentation for multi-phase simulation workflows
- Refactored and normalized modified files with style and import cleanup from code review follow-ups
- Expanded automated coverage for two-pass behavior across CLI and exporter paths
- Made it explicit that we expect `GNU make` v4.3+
- New design ideas for CI/CD release workflow proposals


## [v0.9.1] - 2026-03-29

Release Type: patch

### 📋 Summary
This release focuses on design-documentation workflow quality. maintainability and minor user guide updates
It improves how design PDFs are built from Makefiles, standardizes templated PDF generation.

### 📚 Documentation
- Added a short README in design-ideas to explain scope and PDF build flow
- Updated design proposals for multi-phase simulation and sensitivity analysis
- Improved User Guide with section on how to interpret Tornado-Graphs

### 🛠 Internal
- Refactored design-document build logic into reusable Makefile macros for easier maintenance
- Updated design-doc tooling structure to centralize shared LaTeX templating via design_template.tex
- Improved top-level build workflow so design-document PDFs can be built directly from the main Makefile
- Improved design-document PDF generation to use a dedicated design-ideas Makefile with cleaner orchestration
- Improved generated design PDF artifact naming with versioned filenames in design-ideas/dist

## [v0.9.0] - 2026-03-28

Release Type: minor

### 📋 Summary
This release extends constrained scheduling and export capabilities with clearer sickness-default behavior and richer historic sprint context in reports. 
It also strengthens verification through additional targeted tests and supporting documentation updates.

### ✨ Additions
- Added `constrained_scheduling.sickness_prob` in config as a default per-resource sickness probability fallback for constrained scheduling
- Added `--include-historic-base` support for simulation exports so historic baseline rows can be included in JSON and shown in HTML reports
- Added additional constrained-scheduling test coverage and direct CLI integration tests for simulation behavior

### 🚀 Improvements
- Improved simulation and reporting behavior by clarifying shared sickness duration defaults across constrained scheduling and sprint planning
- Improved algorithm efficiency in core simulation paths

### 🐛 Bug Fixes
- Fixed outdated export test behavior to align with current exporter call signatures
- Fixed assert usage in tests to use explicit value checks
- Fixed minor typos in build/documentation files

### 📚 Documentation
- Updated formal grammar and user-guide sections to clarify that sickness duration parameters are shared while sickness probabilities are mode-specific
- Updated constrained and sprint-planning documentation with clearer configuration guidance and examples
- Improved requirement documentation coverage for T-shirt category behavior

### 🛠 Internal
- Updated roadmap content and maintenance notes for the next development cycle


## [v0.8.3] - 2026-03-27

Release Type: patch

### 📋 Summary
This release improves documentation packaging and structure for end users. 

### 🐛 Bug Fixes
- Fixed broken links in the documentation so referenced pages resolve correctly

### 📚 Documentation
- Include Quickstart Guide in Doc site

### 🛠 Internal
- Updated release-maintenance commits for changelog bump and develop/main synchronization as part of the patch cycle
- Added generation of the User Guide PDF and MCP bundle artifacts as part of the automated release workflow


## [v0.8.2] - 2026-03-27

Release Type: patch

### 📋 Summary
This release refines documentation structure and keeps onboarding content aligned between repository files and the published docs. It also adjusts examples generation behavior to reduce unnecessary churn during docs updates.

### 📚 Documentation
- Restructured documentation layout and moved Quickstart content into the docs tree for rendered user-guide visibility
- Updated supporting documentation text and navigation details for consistency

### 🛠 Internal
- Updated release-maintenance commits for changelog bump and develop/main synchronization as part of the patch cycle
- Improved examples generation workflow to be less aggressive and produce fewer unnecessary updates


## [v0.8.1] - 2026-03-27

Release Type: patch

### 📋 Summary
This release is a documentation improvement. It streamlines onboarding flow between README, QUICKSTART, and the User Guide to reduce duplication and improve navigation.

### 📚 Documentation
- Updated README wording for clearer onboarding guidance and MCP usage pointers
- Updated QUICKSTART text to align with current CLI behavior and reduce overlap with the User Guide
- Made QUICKSTART part of the user guide to offer a rendered version
- Refined documentation wording and formatting across onboarding sections for consistency
- Improved top-level README structure by shortening repeated sections and clarifying install and navigation paths
- Improved documentation flow so users are routed more clearly between QUICKSTART, User Guide, and development references

### 🛠 Internal
- Updated generated User Guide PDF artifact content as part of the docs update cycle and use dist directory


## [v0.8.0] - 2026-03-26

Release Type: minor

### 📋 Summary
The main new feature is introduction of category-based T-shirt sizing, making Epics the default estimation category. This allows teams to express differently-scoped work with the right calibration. For example, `t_shirt_size: "M"` continues to work as before, but a new qualified form `t_shirt_size: "bug.M"` resolves to a different category with its own size definitions. This release also adds support for reading configuration from `~/.mcprojsim`, enabling persistent user-level config without modifying project files. By default the following categories are available: `story`, `bug`, `epic`, `business`, and `initiative` with `epic` as the default category. 

### ✨ Additions
- Added category-based T-shirt size system, allowing tasks to reference sizes in the context of Epic, Story, or other configurable categories
- Added support for reading configuration from `~/.mcprojsim`, enabling persistent user-level config without modifying project files
- Added new CLI flag `--tshirt-category` to override the default T-shirt size category for a simulation run
- Added new CLI flag to the `config` command `--generate` to generate a configuration file in `~/.mcprojsim` with the default configuration values as a starting point for user-level configuration.

### 🚀 Improvements
- Migrated tooling and docs build to only require Python 3.13+ (and not 3.14+ as before) to support a wider user base while still using modern language features
- Updated all documentation examples to use the new T-shirt size categories and reflect the new Epic-as default behavior

### 📚 Documentation
- Updated documentation and generated examples to reflect T-shirt size categories and Epic-as-default behaviour
- Synchronized API reference documentation with the current code base
- Fixed a few minor typos and formatting issues in the documentation, specially some typos in LaTeX formulas.

### 🛠 Internal
- Made the Makefile an implicit dependency for all targets (requires GNU Make ≥ 4.3). Some general improvements to fail-fast and give clearer feedback on failure for all targets, especially type-checking and linting targets. Updated the documentation to reflect the new Makefile usage and target structure.
- Only runb non-heavy tests by default; heavy tests are opt-in, added new target in Makefile for running all tests including heavy ones (`make test-all`)
- Reworked the creation of PDF version of design documents to use a single LaTeX template and a more robust generation process, improving consistency, formatting, and maintainability.


## [v0.7.4] - 2026-03-25

Release Type: patch

### 📋 Summary
This release improves the MCP onboarding flow for assistant-driven installs. It clarifies how users should ask their assistant to install the MCP bundle, adds a concrete first-run simulation example, and makes the follow-up workflow easier to discover.

### 🚀 Improvements
- Improved README MCP installation guidance with a more explicit assistant prompt for downloading and installing the latest server from GitHub Releases

### 📚 Documentation
- Updated the README MCP section to explain that the assistant should be restarted after installation so the new server is loaded as well as how to specify a simple project in naturl language


## [v0.7.3] - 2026-03-25

Release Type: patch

### 📋 Summary
This release improves release tooling workflows and MCP bundle installation guidance. It separates CHANGELOG entry creation into a reusable script, strengthens release validation, and significantly enhances the MCP bundle with explicit client configuration instructions, comprehensive troubleshooting, and clear messaging about permanent, one-time installation.

### 🚀 Improvements
- Improved release workflow by separating CHANGELOG entry generation into `scripts/mkchlogentry.sh`, a standalone reusable script with color-coded output and validation.
- Improved `scripts/mkrelease.sh` to validate pre-existing CHANGELOG entries before proceeding with release (fail-fast guarantee).
- Improved MCP bundle troubleshooting section with expanded coverage of bootstrap issues, client configuration issues, and per-client diagnostic guidance.Improved the README and user guide to clarify the installation.

### 📚 Documentation
- Added `scripts/mkchlogentry.sh` documentation to scripts README with usage examples and validation rules.
- Updated Release Workflow example in scripts README to include the new `mkchlogentry.sh` step before release.
- Expanded MCP bundle README with Prerequisites section, Configuring Your MCP Client section with per-client walkthroughs, and Getting Help troubleshooting guidance.

### 🛠 Internal
- Created `scripts/mkchlogentry.sh` script (240 lines) with version validation, duplicate detection, template generation, and environment awareness.
- Updated release script validation to check for CHANGELOG entry format: `^## \[v<version>\] - <YYYY-MM-DD>$`.
- Added `.github/skills/changelog-entry/SKILL.md` Copilot skill for AI-assisted CHANGELOG entry creation.
- Added proposal for new pipeline setup.


## [v0.7.1] - 2026-03-25

Release Type: patch

### 📋 Summary
This release improves release packaging and installation guidance. It hardens GitHub release artifact validation, adds the User Guide PDF as an uploaded release artifact, and updates docs text to emphasize MCP bundle-based setup workflows.

### 🚀 Improvements
- Improved `scripts/mkghrelease.sh` to fail fast when required release artifacts are missing before attempting release creation.
- Improved release artifact validation by requiring both `dist/mcprojsim-mcp-bundle-<version>.zip` and `mcprojsim_user_guide-v<version>.pdf`.
- Improved GitHub release uploads to include the User Guide PDF as a first-class release artifact.

### 📚 Documentation
- Updated README installation guidance to prioritize the MCP bundle artifact workflow for MCP-capable assistants.
- Expanded README MCP section with explicit MCP bundle install guidance and an assistant prompt example.

### 🛠 Internal
- Updated the User Guide PDF front-page template version label for release alignment.


## [v0.7.0] - 2026-03-24

Release Type: minor

### 📋 Summary
This release adds sprint planning as a first-class forecasting mode on top of the existing Monte Carlo duration simulation. It introduces sprint-history driven forecasting, velocity-model choices, sickness and spillover modelling, new examples and user-guide coverage, and supporting release/build tooling for MCP distribution and documentation generation.

### ✨ Additions
- Added sprint-planning simulation with dedicated sprint results, sprint burn-up outputs, and support for empirical and Negative Binomial velocity models.
- Added external sprint history loading from CSV and JSON files, including example project files and reference data sets.
- Added sprint-capacity modelling for per-person sickness, sprint volatility overlays, and backlog spillover behaviour.
- Added a full sprint planning user guide chapter and several sprint-planning example files, including a large 60-task sprint example with historical data.
- Added MCP bundle packaging support via `scripts/mkmcpbundle.sh`.

### 🚀 Improvements
- Improved CLI support for sprint planning with `simulate`-time overrides such as `--velocity-model` and `--no-sickness`.
- Improved JSON, CSV, and HTML exporters to include sprint-planning outputs and diagnostics.
- Improved validation and error reporting for sprint-planning project files and external history sources.
- Improved generated documentation examples through template-driven example generation and faster parallel example rendering.
- Improved top-level and script-level documentation so new sprint-planning workflows and build utilities are easier to discover.

### 🐛 Bug Fixes
- Fixed deterministic seeding for sickness modelling so repeated runs with the same `--seed` produce identical sprint-planning results.
- Fixed several documentation and formatting issues in sprint-planning design and user-guide outputs.

### 📚 Documentation
- Added user documentation for sprint planning, including workflow, configuration, history-file formats, sickness modelling, and output interpretation.
- Updated the README and command documentation to surface sprint-planning capabilities and newer simulation flags.
- Expanded the scripts README so all maintained helper scripts and support files are described.

### 🛠 Internal
- Added broad test coverage for sprint planning, including parser, model, exporter, CLI, and statistical integration tests.
- Added heavy-test marking and CI exclusion for longer-running statistical sprint tests.
- Added helper scripts for regenerating sprint examples and for documenting/generated example maintenance.


## [v0.6.1] - 2026-03-21

Release Type: patch

### 📋 Summary
- Make sure runs with the same `--seed` flag are identical

### 🐛 Bug Fixes
- Closes (#1). The specified `--seed` was not used in all `rand()` setup. Specifically it was not used when simulating sickness.

### 🛠 Internal
- Speedup when generating `examples.md` by running all included project files in parallel to generate the output.


## [v0.6.0] - 2026-03-21

Release Type: minor

### 📋 Summary
This release focuses on better planning realism and stronger authoring workflows. It adds constrained-scheduling support through natural-language and MCP flows, improves the user guide PDF pipeline, refines distribution modeling, and fixes natural-language parsing edge cases that affected generated project YAML files.

### ⚠️ Breaking Changes
- Log-normal duration modeling has been changed to a shifted log-normal approach derived from low/expected/high inputs, which can change simulation outcomes compared to previous versions.
- The `standard_deviation` field has been removed from task specifications in favor of the new shifted log-normal modeling approach, which may require updates to existing project files.
- Estimation ranges are now specified with `low`/`expected`/`high` fields instead of previous `min`/`most_likely`/`max` to better align with natural language inputs and the new distribution modeling approach. It is an an error to use the old field names in project files, and they must be updated to the new format.

### ✨ Additions
- Added resource constrained scheduling support in simulation. This included both MCP simulation flows and natural-language project generation.
- Added template-driven, live-generated examples for documentation via generator scripts and Makefile integration.
- Added a dedicated PDF build target workflow improvements for documentation builds.

### 🚀 Improvements
- Improved User Guide PDF generation using an explicit LaTeX template pipeline.
- Improved documentation structure and readability by removing manual section numbering.
- Added automatic version display on the User Guide front page.
- Refreshed project examples to align with updated simulation behavior.
- General Makefile cleanup and workflow polish for developer ergonomics.

### 🐛 Bug Fixes
- Fixed natural-language parser bug where task bullet lines using name: were incorrectly captured as literal task names.
- Fixed calendar parsing to correctly interpret date ranges for holidays in natural-language input.

### 📚 Documentation
- Expanded and modernized documentation build flow for high-quality PDF output (based on LaTeX templates) and added a Makefile target for easy generation.
- Updated documentation to cover new features and changes in simulation behavior.
- Added/updated example-generation sections to keep documentation examples consistent with code behavior.
- Updated wording and front-page content in the User Guide.

### 🛠 Internal
- Added baseline Copilot instruction scaffolding for repository workflows.
- Regenerated examples after distribution-model changes to keep fixtures aligned with current behavior.
- Minor maintenance and cleanup across build scripts and project housekeeping.


## [v0.5.0] - 2026-03-15

Release Type: minor

### 📋 Summary
Major improvements to the reports with additional information and automatically calculated suggested staffing based on Brook's law. The effort to be used in the staffing suggestion is controlled in the config file (default is P50). The staffing suggestion will also take into account the added overhead and complexity and use that when determining the efficiency of a team size.

### ⚠️ Breaking Changes
- The default ranges for T-Shirt sizes have been updated

### ✨ Additions
- New calculation of suggested staffing requirements
- Addition of Project Effort percentiles in addition to the existing calendar time
- Added thermometer for effort percentiles in HTML report
- Added `-qq` for really silent simulations

### 🚀 Improvements
- The HTML report formatting is easier to read and hours are presented as cealings
- All reports overhauled to use sam terminilogy and same headers
- All reports present statistical summary for both Calendar time and effort man-hours
- Add timing and memory information in the console output

### 📚 Documentation
- Added detailed description of config file syntax'
- Added information about how to interpret the staff suggestions

### 🛠 Internal
- Tighten several tests
- Added a large example with 100 task


## [v0.4.10] - 2026-03-14

Release Type: patch

### 📋 Summary
- Internal cleanup and dependencies bump

### 🛠 Internal
- Bump versions of numpy, black, etc.
- Improve verify_setup.sh script to give options to install
- Generate updated poetry.lock
- Ignore all generated reports in gitignore
- Don't require a running podman/docker to use Makefile targets
- Add poetry.toml


## [v0.4.9] - 2026-03-12

Release Type: patch

### 📋 Summary 
- Build scripts improvement

### 🛠 Internal
- Reduce duplicate work in release scripts


## [v0.4.8] - 2026-03-12

Release Type: patch

### 📋 Summary 
- Minor overhaul of documentation landing page and use stricter type checking for all source and tests.

### 🚀 Improvements
- Add `--strict` for `mypy` type checking and run on both `src/` and `tests/` 
- Update Quickstart Guide with latest changes in console output

### 🐛 Bug Fixes
- Fix all type related warnings and errors

### 🛠 Internal
- Add `pull-all` Makefile target


## [v0.4.7] - 2026-03-12

Release Type: patch

### 📋 Summary 
- More improvement in the documentation site

### 🚀 Improvements
- Rewrote the landing page of the documentation site to be more focused and concise

### 🛠 Internal
- Run stricter type checks in `mkbld.sh` 


## [v0.4.6] - 2026-03-12

Release Type: patch

### 📋 Summary 
- Pipeline work

### 🛠 Internal
- Only run Docs pipeline on main branch


## [v0.4.5] - 2026-03-12

Release Type: patch

### 📋 Summary 
- Update landing page for documentation


## [v0.4.4] - 2026-03-12

Release Type: patch

### 📋 Summary 
- Review test cases for type completeness and update the main CI/CD pipeline

### 🛠 Internal
- Fix errors for missing type annotations for tests
- Don't use the mkbld.sh script in pipeline.
- Setup pipeline to use multiple jobs instead of a single job. Makes it possible for some parallellization


## [v0.4.3] - 2026-03-11

Release Type: patch

### 📋 Summary 
- CI/CD Updates

### 🛠 Internal
- Don't use mkbld.sh in the CI/CD pipeline. Only pure Poetry commands
  

## [v0.4.2] - 2026-03-11

Release Type: minor

### 📋 Summary 
Major improvements to the documentation and added a new natural language project description tool with an MCP server interface.
In addition more analysis metrics have been added (skewness and kurtosis) and the handling of edge cases in the analysis has been improved. A new "Sensitivity Analysis" section has also been added to the documentation.

### ✨ Additions
- Added natural language project description tool 
- Added MCP server interface to allow both creation of project files and running simulations from natural language descriptions in any MCP-compatible client (e.g. GitHub Copilot, Claude Desktop, etc.)
- Added support for units in task estimates (hours/days/weeks)
- Improved documentation and added a new "Development" section
- Added more analysis metrics (skewness and kurtosis) and improved handling of edge cases in analysis
- Added a new "Sensitivity Analysis" section to the documentation

### 🚀 Improvements
- Added Table output option for CLI results

### 🛠 Internal
- Sanitize artifact names in CI/CD pipeline to avoid issues with special characters


## [v0.3.0] - 2026-03-09

Release Type: minor

### 📋 Summary 
- Much improved documentation.
- Handle units in task range estimates

### 🚀 Improvements
- The unit field can now be used to specify "hours", "days", or "weeks"
- The User Guide is now complete
- Added a new "Development" section in the docs
- Days have a configurable number of working hours
- Improved progress indicator in terminal

### 🛠 Internal
- Added randomized end-to-end tests by automating generation of valid project files which are used for estimation validation. This adds around 300 new full tests.


## [v0.2.1] - 2026-03-09

Release Type: patch

### 📋 Summary 
- Focus on making the README and QUICKSTART guide more focused and smaller

### 🚀 Improvements
- Shorter README and QUICKSTART docs
- Added a developer section in docs

### 🛠 Internal
- Clean all timestampe with `make clean`


## [v0.2.0] - 2026-03-08

Release Type: minor

### 📋 Summary 
- First public pre-release. There are still functionality missing to reach 1.0.0 but there is enough to be useful.

### ✨ Additions
- Added full critical path analysis to show the entire critical network

### 🚀 Improvements
- Much improved error reporting for errors in project specifications (with line numbers and suggestions)

### 🐛 Bug Fixes
- Fixed wrong field names in one example

### 🛠 Internal
- Added a todo.md for what remains to reach 1.0.0


## [v0.2.0rc6] - 2026-03-08

Release Type: minor

### 📋 Summary 
- Story point suppport and documentaton updates

### ✨ Additions
- Added Story Point task estimation support

### 🚀 Improvements
- The first two draft chapters of "User Guide" done
- Updated API reference in docs

### 🛠 Internal
- All default values now have a single source (config.py)


## [v0.2.0rc5] - 2026-03-07

Release Type: patch

### 📋 Summary 
- Internal project structure and documentation updates

### ✨ Additions
- `mcprojsim.sh` script in `bin/` directory to easily call the containeraized version of hte project

### 🚀 Improvements
- The containerized document server has a new control script in `scripts/` called `docs-contctl.sh`
- All README and QUICKSTART.have been revised and reworked

### 🛠 Internal
- The PyPi classification now better reflect tha purpose of the project


## [v0.2.0rc4] - 2026-03-07

Release Type: patch

### 📋 Summary 
- Fix Internal CI/CD pipeline

### 🛠 Internal
- Fix PyPi workflow script


## [v0.2.0rc3] - 2026-03-07

Release Type: minor

### 📋 Summary 
- Fix Internal CI/CD pipeline

### 🛠 Internal
- Correctly install Poetry on the runner before trying to upload to PyPi
  

## [v0.2.0rc2] - 2026-03-07

Release Type: patch

### 📋 Summary 
- Fix internal GitHub release script

### 🛠 Internal
- Accept 1.x.xrcYY as valid version number (PEP compliant)


## [v0.2.0rc1] - 2026-03-07

Release Type: minor

### 📋 Summary 
- Convert the build system to fully use Poetry
- Added Containerized build of program and docs

### 🛠 Internal
- Make program version single source (from pyproject)
- Tighten the Coverage badge update
- Bumped libraries and also removed dependency on Panda-libraries


## [v0.0.1-rc3] - 2025-11-20

Release Type: patch

### 📋 Summary 
- Setup doc structure for user guide.


## [v0.0.1-rc2] - 2025-11-20

Release Type: patch

### 📋 Summary 
- Fix release scripts

### 🛠 Internal
- Synchronize use of "v" in front of version used in different places.


## [v0.0.1-rc01] - 2025-11-20

Release Type: major

### 📋 Summary 
A first release to both debug the build and release scripts as well as getting the first pre-release out in the wild.
See documentation for more information

