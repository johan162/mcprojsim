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

