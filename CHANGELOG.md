# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [PEP 440](https://www.python.org/dev/peps/pep-0440/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.0.2]

### Added
* setuptools_scm management of version info
* pytest configuration to pyproject.toml

### Changed
* tests so that unstable tests (test with small chance of failure) are not run automatically

## [0.0.1]

### Added
* CI/CD tooling for project

### Fixed
* Fixed incorrect configuration issue with the build-and-deploy actions. Limited build to Linux x86_64 and MacOS x86_64/ARM64 architectures

## [0.0.0]

### Added
* Initial version of project
