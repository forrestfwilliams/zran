# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [PEP 440](https://www.python.org/dev/peps/pep-0440/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]
### Fixed
* Bug that would not allow you to create a valid modified index if the first point had a non-zero bits property

### Changed
* `create_modified_index` so that it no longer add a point before desired starting position
* `Point` is now a dataclass instead of a named tuple

### Added
* Docstrings and typing throughout

## [0.0.5]

### Added
* Set the window info to all zeros for first point in first point.bits != 0 case. This decreased compressed index size
* New default for `create_modified_index` is to remove the last stop point, since the final point represents the end of the data
* Update testing to increase coverage of `create_modified_index` corner cases

## [0.0.4]

### Added
* New information to the README.md concerning contributions and similar projects
* Contribution note to setup.py

## [0.0.3]
### Fixed
* Deploy actions checkout step now grabs full commit history so that setuptools_scm finds the correct version number

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
