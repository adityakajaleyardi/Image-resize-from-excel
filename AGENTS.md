# AGENTS.md

Read this before exploring the codebase. It covers what the project is, where things live, and the
rules that are easy to break by accident.

## What this is

A small internal web app holding the batch jobs the team runs by hand. One person hosts it on
their machine so colleagues can use it from a browser, because they cannot run an unsigned
executable on a managed laptop. Two tools live in it today:

- **Images** — reads a CSV export of property image URLs, downloads each image, resizes it,
  renames it to convention and files it into folders. Also has a command line entry point.
- **PDF Flatten** — bakes form fields and annotations into a batch of PDFs. The flattening itself
  belongs to a separate package; see the rules below.

The suite has not been named yet. `APP_NAME` in `app/settings.py` is the only place that decides.

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

The same split exists on the front end: `static/job-runner.js` owns submitting, polling, the log
and the results card; each tool's script supplies only its payload, its summary wording and any
extra rendering.

Adding a tool means: a package under `app/tools/`, an entry in `app/registry.py`, templates under
`app/templates/<tool>/`, and a script beside `job-runner.js`. Nothing in `app/jobs.py` should need
to change.

## Rules that must not be broken

**Do not reimplement PDF flattening.** It lives in the separate
[Flatten](https://github.com/adityakajaleyardi/Flatten) repository and is installed with pip. The
web app calls `flatten_bytes(data, options)` and writes out the bytes it returns. Do not copy that
module in, do not merge the repositories, and do not work around it by shelling out to its CLI.

**Import `flatten_pdf` lazily, never at module import time.** `app/tools/flatten/runner.py` imports
it inside the runner and `options.py` inside `to_flatten_options`. A server without the library
must still start and serve every other tool; `app/registry.py` is what makes the tab report itself
unavailable. `tests/test_flatten_api.py::TestWhenTheLibraryIsMissing` pins this.

**`FlattenSettings` mirrors the library's `FlattenOptions` defaults.** They are duplicated so the
form can be rendered and validated without the library installed.
`tests/test_flatten_options.py::TestLibraryAgreement` fails if they drift; fix the duplicate rather
than deleting the test.

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

## Conventions

- No bare `except:`. Catching broad `Exception` is fine where one bad item must not stop a run;
  it is not fine as a way to ignore errors.
- A new image setting touches five places: `ProcessingConfig`, `FIELD_DESCRIPTIONS` and
  `WEB_EDITABLE_FIELDS` in `app/processing/config.py`, the form in
  `app/templates/images/run.html`, the field list in `app/static/images.js`, and
  `samples/Config.csv`.
- A new flatten setting touches four: `FlattenSettings` and `FIELD_DESCRIPTIONS` in
  `app/tools/flatten/options.py`, the form in `app/templates/flatten/run.html`, and
  `OPTION_FIELDS` in `app/static/flatten.js`.
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
```

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
- Both tools share one worker pool of two. Flattening is CPU bound and image processing is network
  bound, so they behave differently under load.
