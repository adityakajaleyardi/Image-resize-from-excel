# AGENTS.md

Read this before exploring the codebase. It covers what the project is, where things live, and the
rules that are easy to break by accident.

## What this is

A small internal web app holding the batch jobs the team runs by hand. One person hosts it on
their machine so colleagues can use it from a browser, because they cannot run an unsigned
executable on a managed laptop. Four tools live in it today:

- **Images from CSV** — reads a CSV export of property image URLs, downloads each image, resizes
 it, renames it to convention and files it into folders. Also has a command line entry point.
- **PDF Flatten** — bakes form fields and annotations into a batch of PDFs.
- **Images from Folder** — the same naming convention, applied to a folder of images already on
 disk rather than a list of URLs.
- **Emails to HTML and Images** — decodes the compressed email bodies in a database export into
 readable HTML, and screenshots each one.

The last three each belong to a separate package installed with pip; see the rules below.

The suite has not been named yet. `APP_NAME` in `app/settings.py` is the only place that decides.

**There is no authentication.** No login, no sessions, nothing behind a password. This is a
deliberate choice: the app is only reachable on the internal network. Do not write anything that
implies otherwise, and if you are adding a tool whose output is sensitive, say so in its help page
and give it a short retention rather than pretending it is protected.

## Where things live

| Path | What it holds |
|---|---|
| `app/main.py` | App assembly plus the job endpoints every tool shares. Thin. |
| `app/registry.py` | The list of tools, their nav entries, and whether each one's dependency is installed |
| `app/jobs.py` | Job workspaces, worker pool, event log, ZIP packaging, expiry. Tool agnostic. |
| `app/events.py` | `Event` and `ToolError`. No dependencies beyond the standard library. |
| `app/uploads.py` | Storing uploads without trusting their filenames |
| `app/settings.py` | Shared paths and limits, `APP_NAME` |
| `app/templating.py` | The shared Jinja environment and its globals |
| `app/tools/images/` | Routes and settings for the image tool |
| `app/tools/flatten/` | Routes, settings, options and runner for the flatten tool |
| `app/tools/folder/` | Routes, settings, options and runner for the folder image tool |
| `app/tools/emails/` | Routes, settings, options and runner for the email converter |
| `app/processing/` | The image pipeline. No web dependencies. |
| `app/processing/engine.py` | The image run: read rows, download, resize, name, save, log |
| `app/processing/naming.py` | Filename construction |
| `app/processing/constants.py` | Doc type mappings, source domains, iType sizing boxes |
| `app/processing/config.py` | `ProcessingConfig`, plus forgiving Config.csv parsing |
| `app/processing/validation.py` | Upload header checks |
| `app/templates/`, `app/static/` | Front end. One folder per tool under `templates/`. |
| `cli.py` | Command line entry point for the image tool |
| `tests/` | pytest suite |
| `samples/` | Templates with dummy data, also served from the app |
| `data/` | Runtime only. Gitignored. Never commit it. |

## How a tool fits in

`app/jobs.py` knows nothing about any particular tool. A tool hands `JobManager.submit` a runner:
a callable taking a `JobContext` (upload folder, output folder, event sink, cancel flag) and
returning a summary dict. Progress polling, cancellation, ZIP packaging and expiry are shared.

Two things a tool may ask for, neither of which names it inside `jobs.py`:

- `submit(job, runner, lane="<name>")` runs it on a worker of its own instead of the shared pool
 of two. For a tool whose runs last hours, so it queues against itself rather than starving the
 quick ones. Emails to HTML and Images is the only one that does this.
- `create(tool, retention_hours=N)` deletes the workspace sooner than the server-wide window. The
 value is also written into the workspace, so a restart does not lose it.

The same split exists on the front end: `static/job-runner.js` owns submitting, polling, the log
and the results card; each tool's script supplies only its payload, its summary wording and any
extra rendering.

Adding a tool means: a package under `app/tools/`, an entry in `app/registry.py`, templates under
`app/templates/<tool>/`, and a script beside `job-runner.js`. Nothing in `app/jobs.py` should need
to change.

## Rules that must not be broken

**Do not reimplement what the tool packages do.** Three of the four tools are thin wrappers over
libraries that live in their own repositories and are installed with pip:
[Flatten](https://github.com/adityakajaleyardi/Flatten), `image-from-folder` and
[greystar-email-converter](https://github.com/adityakajaleyardi/greystar-email-converter). Do not
copy those modules in, do not merge the repositories, and do not work around them by shelling out
to their command line entry points. Call the Python API.

**Do not touch the email converter's render settings.** Zoom, the default width and the maximum
width in its `RenderOptions` are calibrated against screenshots produced before this app existed.
`app/tools/emails/options.py` deliberately does not expose them, and nothing should pass a
`RenderOptions` to `EmailConverter`.

**Import a tool's library lazily, never at module import time.** Each runner imports inside the
runner and each `options.py` inside its conversion method. A server without the library must still
start and serve every other tool; `app/registry.py` is what makes the tab report itself
unavailable. `tests/test_flatten_api.py::TestWhenTheLibraryIsMissing` and
`tests/test_emails_api.py::TestWhenTheLibraryIsMissing` pin this.

**Options modules mirror their library's defaults.** `FlattenSettings` duplicates `FlattenOptions`,
and `LAYOUT_COLUMNS` in the email options duplicates `ColumnMapping`. They are copied so the form
can be rendered and validated without the library installed. The `TestLibraryAgreement` class in
`tests/test_flatten_options.py` and `tests/test_emails_options.py` fails if they drift; fix the
duplicate rather than deleting the test.

**wkhtmltoimage is a program, not a pip package.** Email screenshots shell out to it. It cannot go
in a requirements file, so it is checked at startup in `app/main.py`, checked again when the run
page is drawn, and checked by `scripts/start_server.ps1`. A server without it must still run the
tool and produce HTML; only the screenshot option is disabled. There is no Dockerfile here and the
host is Windows, so `apt-get` instructions belong in comments for a future Linux deploy, not in the
deploy path.

**A batch must never be one long request.** Every tool runs on the job thread pool and reports
progress through events. One bad item is recorded and the run continues.

**Output filenames and image dimensions are a contract.** Downstream systems match on them. The
naming rules in `naming.py` and the iType sizing boxes in `constants.py` must not change unless
that is explicitly what is being asked for. `tests/test_naming.py` and `tests/test_images.py` pin
them; if a change makes those fail, the change is wrong until proven otherwise.

**`Target Image Name` overrides all automatic naming.** When that column has a value, the only
processing applied to it is replacing characters Windows rejects and adding an extension if there
is none. Resizing and folder placement still apply.

**`app/processing/` must not import FastAPI** or any other web dependency. The command line entry
point depends on that package standing alone. `app/events.py` is under the same restriction,
because `app/processing/` imports it.

**Report progress with the event callback, never `print`.** A runner does not know whether it is
running under the web app or the terminal.

**Image downloads are restricted to an allowlist and must stay that way.** URLs come from a file
any user can upload, so `is_download_url_allowed` in `constants.py` is what stops the server being
used to reach other machines on the internal network. Do not bypass it, and do not widen it to a
plain `endswith` check, which would match `notrentcafe.com`.

**Uploaded filenames are hostile.** Everything written to disk goes through
`safe_relative_path` in `app/uploads.py`, which strips `..`, drive letters and characters Windows
rejects. The folder structure from `webkitdirectory` is reproduced in the output, so this is the
only thing standing between a crafted path and the rest of the disk. `tests/test_uploads.py` pins
it.

**No server paths in the interface.** `JobContext` deliberately exposes only two directories, and
no route returns a filesystem path.

**Never commit real property data.** Live property codes, ids or URLs stay out of the repository.
`Config.csv`, `Img_Report.csv`, `PropertyHMY.csv` and `data/` are gitignored already.

**Decoded emails are personal data.** They hold resident names, addresses and lease details, so:
they are written under `data/` like every other output and never below `static/`; they are
downloaded through the shared job endpoints rather than served as files; the workspace is deleted
after `RETENTION_HOURS` in `app/tools/emails/settings.py`, well before the server-wide window; the
body column is stripped from the failure log, which a user downloads; and nothing logs an email
body, only record ids. Keep all five true.

## Conventions

- No bare `except:`. Catching broad `Exception` is fine where one bad item must not stop a run;
  it is not fine as a way to ignore errors.
- A new image setting touches five places: `ProcessingConfig`, `FIELD_DESCRIPTIONS` and
  `WEB_EDITABLE_FIELDS` in `app/processing/config.py`, the form in
  `app/templates/images/run.html`, the field list in `app/static/images.js`, and
  `samples/Config.csv`.
- A new setting on any other tool touches four: the settings dataclass and `FIELD_DESCRIPTIONS` in
  that tool's `options.py`, the form in `app/templates/<tool>/run.html`, and `OPTION_FIELDS` in
  `app/static/<tool>.js`.
- A new tool touches six: a package under `app/tools/`, templates under `app/templates/<tool>/`, a
  script beside `job-runner.js`, an entry in `app/registry.py`, a router line in `app/main.py`, and
  the `packages` list in `pyproject.toml`. The home page grid is sized for the number of tools, so
  check it still fits without scrolling.
- The front end is plain HTML, CSS and JavaScript with no build step. Keep it that way; the host
  machine has Python and nothing else.
- Ruff handles formatting and linting. Configuration is in `pyproject.toml`.

## Common tasks

```bash
python -m uvicorn app.main:app --reload   # develop against the app
.\scripts\start_server.ps1                # host it for colleagues
python cli.py --no-pause                  # run the image tool from the command line
pytest                                    # test
ruff check . && ruff format .             # lint and format

pip install -e ..\Flatten                 # develop against a local Flatten checkout
pip install -r requirements-flatten.txt   # install Flatten from GitHub, for a server
pip install -r requirements-folder.txt    # the folder image tool
pip install -r requirements-emails.txt    # the email converter
```

Email screenshots also need the `wkhtmltoimage` program, which pip cannot install. On Windows it
comes from the installer at <https://wkhtmltopdf.org/downloads.html>; on Debian it is
`apt-get install -y wkhtmltopdf`. It is found on `PATH`, at the default install location, or
wherever `WKHTMLTOIMAGE_PATH` points.

## Gotchas

- The source CSV is read with `header=None` and the first row is taken verbatim as the header,
  because column names contain characters pandas would otherwise mangle.
- `Propery Code` and `Propery Id` are misspelled in the real export. Both spellings are supported
  deliberately; do not "fix" them.
- Row numbers in image logs are spreadsheet line numbers, so the first data row is 2.
- The max image file size is a target, not a guarantee. JPEG quality stops stepping down at 10,
  and PNGs are never lossily compressed.
- `flatten_bytes` returns a tuple of `(bytes, FlattenResult)`, not just bytes. `result.degraded`
  is what "needs review" means, and it still returns usable output in that case.
- Every tool but Emails to HTML and Images shares one worker pool of two. Flattening is CPU
  bound and image processing is network bound, so they behave differently under load.
- The email converter's own `convert_file` reports progress only every hundredth row through the
  logger and cannot be interrupted. `app/tools/emails/runner.py` therefore drives `read_table` and
  `convert_row` itself, which are both public, to get per-record progress and a working cancel.
  That is orchestration, not a reimplementation: no decoding, width detection or rendering is
  duplicated.
- Two email column layouts exist in the wild and picking the wrong one is the usual cause of a
  failed run, which is why the form detects from the headings by default.
