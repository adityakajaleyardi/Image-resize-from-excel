# Internal Tools

A small web app holding the batch jobs our team runs by hand. One person hosts it and everyone
else opens a link, because a managed laptop will not run an unsigned executable. Each tool takes
some files, works through them in the background, and hands back a ZIP.

| Tool | What it does |
|---|---|
| **Images** | Downloads property images listed in a CSV export, resizes them, renames them to convention and files them into folders |
| **PDF Flatten** | Bakes form fields and annotations permanently into a batch of PDFs |

There is also a command line entry point for the image tool.

> The suite has not been named yet. It is called *Internal Tools* in one place, `APP_NAME` in
> [`app/settings.py`](app/settings.py). Change it there and the whole interface follows.

## Contents

- [Hosting the app](#hosting-the-app)
- [The Images tool](#the-images-tool)
- [The PDF Flatten tool](#the-pdf-flatten-tool)
- [Command line use](#command-line-use)
- [Project layout](#project-layout)
- [Development](#development)

## Hosting the app

One person hosts it; everyone else just opens the link.

```powershell
git clone https://github.com/adityakajaleyardi/Image-resize-from-excel.git
cd Image-resize-from-excel
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-flatten.txt   # only needed for the PDF Flatten tool

.\scripts\start_server.ps1
```

The script prints two addresses. Share the second one, which looks like `http://10.x.x.x:8000`.
If PowerShell refuses to run the script, double click `scripts\start_server.bat` instead, which
works around the execution policy.

Use `-Port` to serve somewhere else:

```powershell
.\scripts\start_server.ps1 -Port 8080
```

### The flatten dependency

Flattening lives in a separate repository,
[adityakajaleyardi/Flatten](https://github.com/adityakajaleyardi/Flatten), and is installed as an
ordinary pip package. It is kept out of `requirements.txt` on purpose: it is fetched from GitHub,
so a network that cannot reach github.com would otherwise break the install of everything else.

Without it the app still runs and every other tool works; the PDF Flatten tab simply says it is
unavailable and shows the install command.

```powershell
pip install -r requirements-flatten.txt          # from GitHub, for a server
pip install -e ..\Flatten                        # from a local checkout, for development
```

### If a colleague cannot open the link

Almost always the Windows firewall. Allow the port once, from an administrator PowerShell window:

```powershell
New-NetFirewallRule -DisplayName 'Internal Tools' -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

The host machine must stay on and the window must stay open for the app to be reachable.

### Notes on hosting

- There is no login. Anyone who can reach the address can use it, which is the intent for an
  internal tool on a trusted network. Do not expose the port to the internet.
- Image downloads are restricted to `rentcafe.com`, so the server cannot be pointed at other
  machines on your network. See [Downloads](#downloads).
- Two runs execute at a time, across all tools; further runs queue.
- Everything a run produces lives under `data/jobs/` and is deleted after 24 hours.

Environment variables, if you need them: `TOOLKIT_DATA_DIR`, `TOOLKIT_MAX_CONCURRENT_JOBS`,
`TOOLKIT_JOB_RETENTION_HOURS`, and `IMAGE_PROCESSOR_EXTRA_HOSTS` for the image allowlist. The
older `IMAGE_PROCESSOR_` spellings of the first three are still honoured.

---

# The Images tool

Downloads the images listed in a CSV export, resizes them, renames them to convention, and files
them into folders.

1. **Choose your files.** The source export is required. The property mapping file is optional.
2. **Check the settings.** They start from the saved defaults and apply to this run only, unless
   you press *Save as default*.
3. **Start the run.** Progress appears line by line and can be cancelled at any point.
4. **Download the ZIP.** It contains the images in their folders, plus the process log.

If a column name is wrong the app says so before the run starts, naming every column that is
missing.

## Input files

### Source export (required)

One row per image, with a header row. Column names must match exactly.

| Column | Required | Purpose |
|---|---|---|
| `Property/Company Code` or `Property Code` | Yes | Identifies the property the image came from |
| `File Name` | Yes | Original file name, used in the log |
| `iType` | Yes | Image type code, which decides the target size |
| `Doc. Type` | Yes | Document type, which decides the folder and the filename suffix |
| `Active/Inactive` | Yes | Rows marked `Inactive` are skipped |
| `Full Path` | Yes | URL to download |
| `Property Name` | No | Reference only |
| `Order` | No | Reference only |
| `Floorplan Code` | No | Reference only |
| `Target Property` | No | File the image under a different property |
| `Target Image Name` | No | Name the output file yourself, skipping all automatic naming |

### Property mapping (optional)

Maps property codes to property ids, so older `p-code` URLs can be retried against the current id.

| Column | Purpose |
|---|---|
| `Propery Code` or `Property Code` | Property code as it appears in the source export |
| `Propery Id` or `Property Id` | Numeric property id |

The misspelling is what the standard export produces, so both spellings are accepted.

Templates for both files are in [samples/](samples/) and downloadable from the app.

## Settings

| Setting | Default | Effect |
|---|---|---|
| Operation mode | Resize and rename | Rename only leaves the image untouched |
| Property type | MVC | Changes the target size for iTypes 1 and 120 |
| Manual sizing | Off | On resizes every image to the exact width and height below |
| Target width, height | 2560 x 1707 | Used only with manual sizing on |
| Max file size MB | 1.0 | JPEG quality steps down until the file fits |
| Optimized suffix | Off | On appends `Optimized` to generated filenames |

Saved defaults live in `data/default_config.json`. On first run they are seeded from a `Config.csv`
left over from the desktop version, so existing settings carry over.

## Naming and sizing rules

### Filenames

With `Target Image Name` filled in, that name is used exactly as given. Only characters Windows
rejects are replaced, and an extension is added if you left one off. The extension decides whether
the output is JPEG or PNG.

Otherwise the name is built as:

```
TargetProperty_ImageDescription_iType_DocTypeSuffix.jpg
```

The description comes from the URL. A property code the export prefixed onto it is stripped, and
the iType and doc type suffixes are skipped when the description already states them. So
`p0054389_photogallery_bedroom.jpg` for property `Ridgecrest Village` becomes
`Ridgecrest_Village_photogallery_bedroom_40.jpg`, not
`Ridgecrest_Village_p0054389_photogallery_bedroom_40_PG.jpg`.

Files are written into `TargetProperty__DocType/`.

### Sizes

Images are only ever scaled down, never enlarged. Portrait images have 15% trimmed from the top
and bottom before scaling, so they are not reduced to a sliver inside a landscape box.

| iType | MVC | Legacy |
|---|---|---|
| 1 | 2560 x 1707 | 1024 x 768 |
| 2 | Height 480 | Height 480 |
| 5 | 500 x 350 | 500 x 350 |
| 6 | Width 350 | Width 350 |
| 40 | Height 1000 | Height 1000 |
| 120 | 2560 x 1707 | 670 x 480 |
| 4, 10, 12, 13, 14, 15, 28 | 2560 x 1707 | No rule |

An iType with no rule is left at its original size.

### Downloads

Each URL is tried as given. If it is on `www.rentcafe.com` the CDN mirrors
`cdngeneral.rentcafe.com` and `cdngeneralcf.rentcafe.com` are tried too. When a property mapping
is supplied, `p-code` URLs are also retried with the path rewritten to the mapped property id.

A row that cannot be downloaded is recorded and the run continues.

**Only `rentcafe.com` and its subdomains can be downloaded from.** URLs come from a file that any
user can upload, so without this the server would fetch whatever it was told to, from its position
inside the network. Anything else is refused without being contacted. To permit another source,
set `IMAGE_PROCESSOR_EXTRA_HOSTS` to a comma separated list of domains before starting the server.

---

# The PDF Flatten tool

Turns fillable PDFs into fixed ones. The values stay visible exactly where they were, but they
stop being editable fields, so a form filler cannot change them and Acrobat's *Prepare Form* tool
will not re-detect or delete them.

1. **Pick a folder.** Everything inside is scanned, including subfolders. Only PDFs are uploaded;
   anything else is ignored. You can pick individual files instead.
2. **Check the settings.** Leave the engine on *auto* unless you are chasing a specific problem.
3. **Start the run.** Files are flattened one at a time and progress appears per file.
4. **Download the ZIP.** It mirrors the folder structure you picked and includes a report.

## The three outcomes

Every result is checked by rendering the pages before and after and comparing them, so a document
that lost content is flagged rather than quietly handed back.

| Outcome | What it means | In the ZIP? |
|---|---|---|
| **Flattened** | Verified against the original; nothing moved or disappeared | Yes |
| **Needs review** | No engine produced a result that passed the check, so the closest attempt was kept. The report says what looked wrong, for example *page 3 lost 1.2% of its content* | Yes |
| **Failed** | Every engine failed outright, usually a corrupt or password protected file | No |

`Flatten_Report.csv` travels inside the ZIP with a row per file: the outcome, the engine that
produced it, why it was flagged, how much content changed, and which engines were tried.

## Settings

| Setting | Default | Effect |
|---|---|---|
| Engine | auto | `auto` tries each engine and keeps the first result that verifies. `bake`, `stamp` and `raster` force one |
| Flatten annotations | On | Also flattens comments and stamps, not just form fields. Links stay clickable either way |
| Allow rasterising | Off | Lets `auto` fall back to rendering pages as images. Always looks right, but the text stops being searchable |
| Verify | On | Re-render and compare every result |
| Verification DPI | 72 | Higher is stricter and slower |
| Tolerance | 0.005 | How much of a page's content may change before it is flagged |
| Raster DPI | 150 | Resolution used when a page is rasterised |

Saved defaults live in `data/flatten_default_options.json`.

## Limits

Up to 100 files per batch, 50 MB per file and 300 MB in total. Folder picking needs Chrome or
Edge; in other browsers use *pick individual files*.

## How the flattener is integrated

The web app never implements flattening. It calls `flatten_bytes(data, options)` from the
[Flatten](https://github.com/adityakajaleyardi/Flatten) package and writes out what comes back.
The two repositories stay separate and are joined only by the pip dependency, so the flattener can
be improved and released without touching this app.

The library is imported lazily, inside the runner, so the app starts and every other tool keeps
working on a server where it is not installed.

---

## Command line use

`cli.py` reproduces the behaviour of the original desktop image script. With no arguments it reads
`Config.csv` or `Config.xlsx` from the current folder, processes the source file named there, and
writes into the output folder beside it.

```bash
python cli.py
python cli.py --source Export.csv --output ./out --no-pause
python cli.py --config Config.xlsx --property-map PropertyHMY.csv
```

It exits with status 1 if any row failed, so it can be used in a scheduled task.

The Flatten package ships its own command line, `flatten-pdf`, documented in its repository.

## Project layout

```
app/
  main.py                 app assembly and the shared job endpoints
  registry.py             the list of tools, and whether each one is installed
  jobs.py                 job workspaces, worker pool, ZIP packaging, expiry
  events.py               progress events and ToolError, shared by every tool
  uploads.py              storing uploads without trusting their filenames
  settings.py             shared paths and limits, APP_NAME
  templating.py           the shared Jinja environment
  tools/
    images/               routes and settings for the image tool
    flatten/              routes, settings, options and runner for the flatten tool
  processing/             the image pipeline, no web dependencies
    constants.py          doc type mappings, domains, iType sizing rules
    config.py             ProcessingConfig and Config.csv parsing
    validation.py         upload header checks
    naming.py             filename construction
    images.py             resize, crop, compress
    engine.py             the image run itself
  templates/, static/     front end
cli.py                    command line entry point for the image tool
scripts/                  start_server.ps1 and .bat
samples/                  templates for the input files
tests/                    pytest suite
data/                     runtime only, never committed
```

### How a tool fits in

`app/jobs.py` knows nothing about any particular tool. A tool hands `submit` a runner: a callable
that receives a `JobContext` (an upload folder, an output folder, an event sink and a cancel flag)
and returns a summary. Everything else, including progress polling, cancellation, ZIP packaging
and expiry, is shared. On the front end the same split exists between `static/job-runner.js` and
the small per-tool scripts beside it.

## Development

```bash
pip install -r requirements.txt
pip install -e ..\Flatten          # or -r requirements-flatten.txt
pip install pytest httpx ruff

pytest
ruff check .
ruff format .

python -m uvicorn app.main:app --reload
```

Tests for the flatten tool skip themselves when the library is not installed, so the suite passes
either way.

`app/processing/` must not import FastAPI or anything web related, so the command line keeps
working independently. The same applies to `app/events.py`.

Output filenames and image dimensions are a contract with downstream systems. They are pinned by
tests in `tests/test_naming.py` and `tests/test_images.py`; do not change them incidentally.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and [CHANGELOG.md](CHANGELOG.md) for
version history.

## License

MIT. See [LICENSE](LICENSE).
