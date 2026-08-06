# Contributing

## Setup

```bash
git clone https://github.com/adityakajaleyardi/Image-resize-from-excel.git
cd Image-resize-from-excel
python -m venv .venv
.venv\Scripts\activate          # macOS and Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install pytest httpx ruff
```

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

**Report progress with `on_event`, not `print`.** The engine has no idea whether it is running
under the web app or the command line.

**Adding a setting** means touching `ProcessingConfig`, `FIELD_DESCRIPTIONS` and
`WEB_EDITABLE_FIELDS` in `app/processing/config.py`, the form in `app/templates/index.html`, the
field list in `app/static/app.js`, the route in `app/main.py`, and `samples/Config.csv`.

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
