# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.2] - 2026-03-31

### Added
- New "Target Image Name" column in Source.csv for custom output filenames
- Logic to skip renaming when target image name is provided
- Professional GitHub repository structure with documentation
- .gitignore with proper exclusions for PyInstaller artifacts
- requirements.txt with all dependencies
- GitHub Actions workflow for code quality checks
- CONTRIBUTING.md with contributor guidelines
- LICENSE (MIT)

### Changed
- Improved naming logic to check for target image name first
- Enhanced documentation with more detailed examples

## [4.1] - 2026-02-15

### Added
- Extended doc-type mapping with 30+ document types
- Optimized suffix configuration option
- Better error logging and handling
- Support for PropertyHMY.csv lookup

### Fixed
- Issue with vertical image detection
- Improved URL encoding for special characters

## [4.0] - 2026-01-20

### Added
- Vertical image crop logic (removes 15% from top/bottom)
- Multi-domain fallback for image downloads
- Flexible sizing rules based on property type (MVC/LEGACY)
- Support for manual sizing override
- Detailed process and error logging

### Changed
- Complete refactor of naming logic
- Improved folder organization
- Better error messages

## [3.4] - 2026-01-05

### Added
- Vertical image handling
- Better image format detection

### Fixed
- Encoding issues with special characters in filenames

## [3.3] - 2025-12-20

### Added
- Initial doc-type abbreviation system
- Process logging

### Fixed
- Image resizing accuracy

## [3.2] - 2025-12-10

### Added
- Image compression with quality adjustment
- File size limitation

## [3.1] - 2025-12-01

### Added
- Initial resizing logic
- Configuration file support

## [2.2] - 2025-11-15

### Added
- Target Property column support
- Batch processing

## [2.1] - 2025-11-08

### Added
- Basic URL download functionality

## [1.2] - 2025-11-01

### Added
- CSV parsing with multiple encodings

## [1.1] - 2025-10-25

### Added
- Initial configuration system

## [1.0] - 2025-10-20

### Added
- Initial release
- Basic image download and processing

---

## How to Version

- **MAJOR** version when making incompatible API changes
- **MINOR** version when adding functionality in backward-compatible manner
- **PATCH** version when making backward-compatible bug fixes

## Unreleased Changes

(None at this time)
