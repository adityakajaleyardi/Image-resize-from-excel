# AGENTS.md

Read this before exploring the codebase. It covers what the project is, where things live, and the
rules that are easy to break by accident.

## What this is

An internal tool that reads a CSV export of property image URLs, downloads each image, resizes it,
renames it to convention, and files it into folders. It runs as a web app that one person hosts on
their machine so colleagues can use it from a browser, because they cannot run an unsigned
executable on a managed laptop. A command line entry point also exists.

## Where things live

| Path | What it holds |
|---|---|
| `app/processing/` | All processing logic. No web dependencies. |
| `app/processing/engine.py` | The run itself: read rows, download, resize, name, save, log |
| `app/processing/naming.py` | Filename construction |
| `app/processing/constants.py` | Doc type mappings, source domains, iType sizing boxes |
| `app/processing/config.py` | `ProcessingConfig`, plus forgiving Config.csv parsing |
| `app/processing/validation.py` | Upload header checks |
| `app/main.py` | HTTP routes only. Thin. |
| `app/jobs.py` | Job workspaces, worker pool, ZIP packaging, expiry |
| `app/settings.py` | Paths, limits, saved default config |
| `cli.py` | Command line entry point |
| `tests/` | pytest suite |
| `samples/` | Templates with dummy data, also served from the app |
| `data/` | Runtime only. Gitignored. Never commit it. |

## Rules that must not be broken

**Output filenames and image dimensions are a contract.** Downstream systems match on them. The
naming rules in `naming.py` and the iType sizing boxes in `constants.py` must not change unless
that is explicitly what is being asked for. `tests/test_naming.py` and `tests/test_images.py` pin
them; if a change makes those fail, the change is wrong until proven otherwise.

**`Target Image Name` overrides all automatic naming.** When that column has a value, the only
processing applied to it is replacing characters Windows rejects and adding an extension if there
is none. Resizing and folder placement still apply.

**`app/processing/` must not import FastAPI** or any other web dependency. The command line entry
point depends on that package standing alone.

**Report progress with the `on_event` callback, never `print`.** The engine does not know whether
it is running under the web app or the terminal.

**Downloads are restricted to an allowlist and must stay that way.** URLs come from a file any
user can upload, so `is_download_url_allowed` in `constants.py` is what stops the server being
used to reach other machines on the internal network. Do not bypass it, and do not widen it to a
plain `endswith` check, which would match `notrentcafe.com`.

**Never commit real property data.** Live property codes, ids or URLs stay out of the repository.
`Config.csv`, `Img_Report.csv`, `PropertyHMY.csv` and `data/` are gitignored already.

## Conventions

- No bare `except:`. Catching broad `Exception` is fine where one bad row must not stop a run;
  it is not fine as a way to ignore errors.
- A new setting touches five places: `ProcessingConfig`, `FIELD_DESCRIPTIONS` and
  `WEB_EDITABLE_FIELDS` in `app/processing/config.py`, the form in `app/templates/index.html`, the
  field list in `app/static/app.js`, and `samples/Config.csv`.
- The front end is plain HTML, CSS and JavaScript with no build step. Keep it that way; the host
  machine has Python and nothing else.
- Ruff handles formatting and linting. Configuration is in `pyproject.toml`.

## Common tasks

```bash
python -m uvicorn app.main:app --reload   # develop against the app
.\scripts\start_server.ps1                # host it for colleagues
python cli.py --no-pause                  # run from the command line
pytest                                    # test
ruff check . && ruff format .             # lint and format
```

## Gotchas

- The source CSV is read with `header=None` and the first row is taken verbatim as the header,
  because column names contain characters pandas would otherwise mangle.
- `Propery Code` and `Propery Id` are misspelled in the real export. Both spellings are supported
  deliberately; do not "fix" them.
- Row numbers in logs are spreadsheet line numbers, so the first data row is 2.
- The max file size is a target, not a guarantee. JPEG quality stops stepping down at 10, and PNGs
  are never lossily compressed.
