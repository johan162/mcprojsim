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

