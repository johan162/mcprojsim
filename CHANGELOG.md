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

