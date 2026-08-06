# Image Processor

A web app that downloads property images listed in a CSV export, resizes them, renames them to
convention, and files them into folders. Users open it in a browser and download the results as a
ZIP, so nothing has to be installed on their machine.

There is also a command line entry point for scripted or offline use.

## Contents

- [Hosting the app](#hosting-the-app)
- [Using the app](#using-the-app)
- [Input files](#input-files)
- [Settings](#settings)
- [Naming and sizing rules](#naming-and-sizing-rules)
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

.\scripts\start_server.ps1
```

The script prints two addresses. Share the second one, which looks like `http://10.x.x.x:8000`.
If PowerShell refuses to run the script, double click `scripts\start_server.bat` instead, which
works around the execution policy.

Use `-Port` to serve somewhere else:

```powershell
.\scripts\start_server.ps1 -Port 8080
```

### If a colleague cannot open the link

Almost always the Windows firewall. Allow the port once, from an administrator PowerShell window:

```powershell
New-NetFirewallRule -DisplayName 'Image Processor' -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

The host machine must stay on and the window must stay open for the app to be reachable.

### Notes on hosting

- There is no login. Anyone who can reach the address can use it, which is the intent for an
  internal tool on a trusted network. Do not expose the port to the internet.
- Downloads are restricted to `rentcafe.com`, so the server cannot be pointed at other machines
  on your network. See [Downloads](#downloads).
- Two runs execute at a time; further runs queue.
- Everything a run produces lives under `data/jobs/` and is deleted after 24 hours.

Environment variables, if you need them: `IMAGE_PROCESSOR_DATA_DIR`,
`IMAGE_PROCESSOR_MAX_CONCURRENT_JOBS`, `IMAGE_PROCESSOR_JOB_RETENTION_HOURS`,
`IMAGE_PROCESSOR_EXTRA_HOSTS`.

## Using the app

1. **Choose your files.** The source export is required. The property mapping file is optional.
2. **Check the settings.** They start from the saved defaults and apply to this run only, unless
   you press *Save as default*.
3. **Start the run.** Progress appears line by line and can be cancelled at any point.
4. **Download the ZIP.** It contains the images in their folders, plus the process log.

If a column name is wrong the app says so before the run starts, naming every column that is
missing. The Help page in the app documents the file formats and offers template downloads.

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

## Command line use

`cli.py` reproduces the behaviour of the original desktop script. With no arguments it reads
`Config.csv` or `Config.xlsx` from the current folder, processes the source file named there, and
writes into the output folder beside it.

```bash
python cli.py
python cli.py --source Export.csv --output ./out --no-pause
python cli.py --config Config.xlsx --property-map PropertyHMY.csv
```

It exits with status 1 if any row failed, so it can be used in a scheduled task.

## Project layout

```
app/
  main.py                 HTTP routes
  jobs.py                 job workspaces, worker pool, ZIP packaging, expiry
  settings.py             paths, limits, saved defaults
  processing/             pure processing logic, no web dependencies
    constants.py          doc type mappings, domains, iType sizing rules
    config.py             ProcessingConfig and Config.csv parsing
    validation.py         upload header checks
    naming.py             filename construction
    images.py             resize, crop, compress
    engine.py             the run itself
  templates/, static/     front end
cli.py                    command line entry point
scripts/                  start_server.ps1 and .bat
samples/                  templates for the input files
tests/                    pytest suite
data/                     runtime only, never committed
```

## Development

```bash
pip install -r requirements.txt
pip install pytest httpx ruff

pytest
ruff check .
ruff format .

python -m uvicorn app.main:app --reload
```

`app/processing/` must not import FastAPI or anything web related, so the command line keeps
working independently.

Output filenames and image dimensions are a contract with downstream systems. They are pinned by
tests in `tests/test_naming.py` and `tests/test_images.py`; do not change them incidentally.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and [CHANGELOG.md](CHANGELOG.md) for
version history.

## License

MIT. See [LICENSE](LICENSE).
