# Contributing

## Setup

```bash
git clone https://github.com/adityakajaleyardi/Image-resize-from-excel.git
cd Image-resize-from-excel
python -m venv .venv
.venv\Scripts\activate          # macOS and Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install pytest httpx ruff

# The PDF Flatten tool, from a local checkout of the Flatten repo next door.
# Use -r requirements-flatten.txt to take it from GitHub instead.
pip install -e ..\Flatten
```

Tests for the flatten tool skip themselves when that library is absent, so the suite passes
without it. CI runs without it too.

Run the app with reload while working on it:

```bash
python -m uvicorn app.main:app --reload
```

## Before you open a pull request

```bash
ruff check .
ruff format .
pytest
```

CI runs the same three commands on Python 3.10 and 3.13.

## Things to know before changing code

**Output filenames and image dimensions are a contract.** Downstream systems match on them.
The rules live in `app/processing/naming.py` and `app/processing/constants.py` and are pinned by
`tests/test_naming.py` and `tests/test_images.py`. Do not change them unless that is the point of
the change, and say so explicitly in the pull request.

**`app/processing/` must not import FastAPI** or anything else web related. The command line entry
point depends on that package standing alone.

**Report progress with the event callback, not `print`.** A runner has no idea whether it is
running under the web app or the command line.

**Do not reimplement PDF flattening.** It comes from the separate
[Flatten](https://github.com/adityakajaleyardi/Flatten) repository as a pip dependency. Import it
lazily so the app still starts without it, and keep the two repositories separate.

**Adding a tool** means a package under `app/tools/`, an entry in `app/registry.py`, templates
under `app/templates/<tool>/`, and a script beside `static/job-runner.js`. Nothing in
`app/jobs.py` should need to change; if it does, the abstraction is wrong.

**Adding an image setting** means touching `ProcessingConfig`, `FIELD_DESCRIPTIONS` and
`WEB_EDITABLE_FIELDS` in `app/processing/config.py`, the form in
`app/templates/images/run.html`, the field list in `app/static/images.js`, the route in
`app/tools/images/routes.py`, and `samples/Config.csv`.

**Never commit real property data.** Anything with live property codes, ids or URLs stays out of
the repository. `Config.csv`, `Img_Report.csv`, `PropertyHMY.csv` and `data/` are already ignored.

## Style

- Ruff handles formatting and linting; the configuration is in `pyproject.toml`.
- Type hints on anything non-obvious.
- Comment intent and constraints, not what the next line does.

## Commit messages

`type: short description in the imperative`, where type is one of `feat`, `fix`, `docs`,
`refactor`, `test`, `perf` or `chore`. Explain in the body why the change was needed, not what the
diff already shows.

## Reporting a problem

Include the Python version, what you did, what you expected, what happened, and the relevant part
of the process log with any property data removed.
