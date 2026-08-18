# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [7.0.0] - 2026-08-13

Two more tools, and a home page to choose between them. The job layer took the two changes
Emails to HTML and Images needed, both written so no future tool has to touch it either.

### Added
- **Emails to HTML and Images tool.** Upload a CSV or Excel export of stored email bodies and get
  back a ZIP of readable HTML and JPG screenshots, one per email. Conversion comes from the separate
  [greystar-email-converter](https://github.com/adityakajaleyardi/greystar-email-converter)
  package, installed as a pip dependency; nothing is copied in.
- The column layout is detected from the file's headings. Two shapes of export are in circulation
  and picking the wrong one by hand was the usual reason a run failed, so the dropdown is now an
  override rather than a decision. A file in neither layout fails naming both, and listing the
  columns it did find.
- Screenshots can be turned off, which is much faster and needs no `wkhtmltoimage`. When the binary
  is missing the option is disabled rather than the tool, since decoding to HTML works without it.
  Its presence is reported at startup, on the run page, and by `start_server.ps1`.
- **Images from Folder tool.** The Yardi naming convention applied to a folder of images already on
  disk. Unit images fan out to one output per apartment, cross referenced against three uploaded
  lookup files. From the separate `image-from-folder` package.
- A home page of tiles for choosing a tool, and a suite level help page.

### Changed
- `JobManager.submit` takes an optional `lane`, putting a tool's runs on a worker of their own.
  Email conversion uses it: an export can take hours, and would otherwise hold one of the two
  shared workers against everyone else's few-minute job.
- `JobManager.create` takes an optional `retention_hours`. Email conversions are deleted after two
  hours rather than the usual 24, because decoded emails hold resident names, addresses and lease
  details. The window is written into the workspace, so it survives a restart.
- The theme is flat teal tiles on a warm background, applied across every page.

### Security
- The email failure log, which a user downloads, keeps the other columns from the export but not
  the body column, so it never carries a copy of an email.
- Failure reasons are stripped of the raw bytes the decoder quotes from a value it could not read.
- Only record ids are logged, never email content.

### Notes
- There is still no authentication anywhere in the app, which now matters more than it did: the
  the output of Emails to HTML and Images is personal data. Job ids are unguessable and output is never
  served as a static file, but that is obscurity rather than access control. Treat the host
  accordingly.

## [6.0.0] - 2026-08-07

The app now holds more than one tool. Bulk PDF flattening is the second, and the shell around it
is general enough that a third should not require touching the job layer at all.

### Added
- **PDF Flatten tool.** Pick a folder, and every PDF in it has its form fields and annotations
  baked permanently into the page. Results download as a ZIP mirroring the folder structure you
  picked, with a `Flatten_Report.csv` beside them.
- Files that came back imperfect are flagged rather than quietly handed over. Every result is
  verified by rendering the pages before and after, giving three outcomes: flattened, needs
  review, or failed. The report and the results panel say which and why.
- Folder picking with `webkitdirectory`, filtered to PDFs, showing the count and total size before
  anything is uploaded. Individual file selection is offered for browsers that cannot pick folders.
- Flattening comes from the separate [Flatten](https://github.com/adityakajaleyardi/Flatten)
  repository, installed as a pip dependency. The two repositories stay independent; nothing is
  copied in. Install it with `requirements-flatten.txt` or from a local checkout with `pip install -e`.
- The tool degrades gracefully: if the library is not installed the app still starts, every other
  tool works, and the tab explains how to install it.
- Tool tabs in the header, with a Run and Help page for each tool.
- `app/uploads.py`, which strips `..`, drive letters and characters Windows rejects from every
  uploaded filename before it touches disk.

### Changed
- `app/jobs.py` is now tool agnostic. `submit` takes a runner callable and a `JobContext` instead
  of an image configuration, so the worker pool, event log, cancellation, ZIP packaging and expiry
  are shared by every tool.
- `Event` and the new `ToolError` moved to `app/events.py`, which the job layer imports instead of
  the image pipeline.
- `app/main.py` is now assembly plus the shared job endpoints. Tool specific routes live in
  `app/tools/<tool>/routes.py`.
- The polling, progress and results front end moved to `static/job-runner.js`, shared by both
  tools. `static/app.js` became `static/images.js` and holds only what is image specific.
- Routes are namespaced per tool. `/` now redirects to `/images`, `/help` became `/images/help`,
  and `/api/jobs`, `/api/config/default` and `/api/templates/{name}` became `/api/images/...`.
  Job status, cancel and download endpoints stay shared at `/api/jobs/{id}`.
- Templates moved into a folder per tool, with the progress card extracted into a shared partial.
- Environment variables are read as `TOOLKIT_*`, with the old `IMAGE_PROCESSOR_*` names still
  honoured so an existing deployment keeps working.
- The suite name lives in `APP_NAME` in `app/settings.py`, ready to be renamed in one place.
- The saved image default stays at `data/default_config.json`, so existing settings carry over.

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
