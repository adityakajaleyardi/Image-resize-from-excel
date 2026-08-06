# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-08-06

The tool is now a web app. Colleagues cannot run an unsigned executable on a company laptop, so
one person hosts the app and everyone else opens it in a browser over the internal network.

### Added
- Web interface: upload the source export, edit the settings on screen, watch progress line by
  line, cancel mid-run, and download the results as a ZIP
- Settings are pre-filled from a saved default and can be changed for a single run, or saved as
  the new default
- Uploaded CSVs are checked before the run starts, so a misnamed column produces one clear message
  naming every column that is missing, rather than a run that fails on every row
- Help page documenting the required columns, doc types and sizing rules, with template downloads
- Downloads are restricted to `rentcafe.com` and its subdomains. The URLs come from an uploaded
  file, so without this anyone able to reach the server could make it request arbitrary addresses
  from inside the network. Extend with `IMAGE_PROCESSOR_EXTRA_HOSTS` if another source is needed.
- Isolated workspace per run, a two job queue, and automatic deletion after 24 hours
- `scripts/start_server.ps1` and `.bat`, which start the server and print the link to share
- Test suite pinning the filename and dimension rules, and a CI workflow running ruff and pytest

### Changed
- `image_processor.py` split into `app/processing`, where the engine takes explicit paths and
  reports progress through a callback instead of resolving paths against the working directory and
  printing. Filenames and image dimensions are unchanged.
- `cli.py` replaces `image_processor.py` for command line use, with the same default behaviour plus
  `--source`, `--config`, `--output`, `--property-map` and `--no-pause`
- Process log records paths relative to the output folder, so they make sense inside the ZIP
- CDN mirrors are no longer tried for URLs that are not on the primary domain, which stops three
  identical requests being made for every failing non-RentCafe URL
- Minimum Python version is now 3.10

### Fixed
- A missing source file was silently ignored when no property mapping file was present, because
  the check sat inside the mapping file branch
- Logged row numbers were one higher than the spreadsheet line they referred to
- Bare `except:` clauses that swallowed real errors, including `KeyboardInterrupt`
- Leftover debug output printing every rewritten p-code URL
- `openpyxl>=3.6.0` in requirements.txt, a version that does not exist

### Removed
- `Config.csv`, `Img_Report.csv` and `PropertyHMY.csv` are no longer tracked. They hold real
  property data and belong on the operator's machine. Templates with dummy data are in `samples/`.
- `GITHUB_SETUP_GUIDE.md` and `REPOSITORY_STRUCTURE.md`, one-off checklists the README now covers

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

## Versioning

- **MAJOR** for incompatible changes
- **MINOR** for functionality added in a backward compatible way
- **PATCH** for backward compatible fixes
