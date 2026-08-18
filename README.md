# Internal Tools

A small web app holding the batch jobs our team runs by hand. One person hosts it and everyone
else opens a link, because a managed laptop will not run an unsigned executable. Each tool takes
some files, works through them in the background, and hands back a ZIP.

| Tool | What it does |
|---|---|
| **Images from CSV** | Downloads property images listed in a CSV export, resizes them, renames them to convention and files them into folders |
| **PDF Flatten** | Bakes form fields and annotations permanently into a batch of PDFs |
| **Images from Folder** | The same naming convention, applied to a folder of images you already have |
| **Emails to HTML and Images** | Decodes the compressed email bodies in a database export into readable HTML, and screenshots each one |

There is also a command line entry point for the image tool.

> The suite has not been named yet. It is called *Internal Tools* in one place, `APP_NAME` in
> [`app/settings.py`](app/settings.py). Change it there and the whole interface follows.

## Contents

- [Hosting the app](#hosting-the-app)
- [The Images from CSV tool](#the-images-from-csv-tool)
- [The PDF Flatten tool](#the-pdf-flatten-tool)
- [The Images from Folder tool](#the-images-from-folder-tool)
- [The Emails to HTML and Images tool](#the-emails-to-html-and-images-tool)
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

# Each of these adds one tool. Skip any you do not need; the tab says so.
pip install -r requirements-flatten.txt   # PDF Flatten
pip install -r requirements-folder.txt    # Images from Folder
pip install -r requirements-emails.txt    # Emails to HTML and Images

.\scripts\start_server.ps1
```

The script prints two addresses. Share the second one, which looks like `http://10.x.x.x:8000`.
If PowerShell refuses to run the script, double click `scripts\start_server.bat` instead, which
works around the execution policy.

Use `-Port` to serve somewhere else:

```powershell
.\scripts\start_server.ps1 -Port 8080
```

### The tool dependencies

Three of the four tools are thin wrappers over libraries that live in their own repositories and
are installed as ordinary pip packages. They are kept out of `requirements.txt` on purpose: they
are fetched from GitHub, so a network that cannot reach github.com would otherwise break the
install of everything else.

Without one of them the app still runs and every other tool works; that tab simply says it is
unavailable and shows the install command.

```powershell
pip install -r requirements-flatten.txt          # from GitHub, for a server
pip install -e ..\Flatten                        # from a local checkout, for development
```

### wkhtmltoimage, for email screenshots

Emails to HTML and Images takes its screenshots by shelling out to `wkhtmltoimage`, which is
an ordinary program rather than a Python package, so no requirements file can install it.

- **Windows:** the installer at <https://wkhtmltopdf.org/downloads.html>
- **Debian or Ubuntu:** `sudo apt-get install -y wkhtmltopdf`

It is found on `PATH`, at the default install location, or wherever `WKHTMLTOIMAGE_PATH` points.
The server checks for it at startup and prints where it found it, or a warning if it did not.
Decoding to HTML does not need it, so a server without it still converts emails; only the
screenshot option is switched off.

### If a colleague cannot open the link

Almost always the Windows firewall. Allow the port once, from an administrator PowerShell window:

```powershell
New-NetFirewallRule -DisplayName 'Internal Tools' -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

The host machine must stay on and the window must stay open for the app to be reachable.

### Notes on hosting

- There is no login. Anyone who can reach the address can use it, which is the intent for an
  internal tool on a trusted network. Do not expose the port to the internet. Bear this in mind
  for Emails to HTML and Images in particular, whose output contains resident details.
- Image downloads are restricted to `rentcafe.com`, so the server cannot be pointed at other
  machines on your network. See [Downloads](#downloads).
- Two runs execute at a time; further runs queue. Email conversions are the exception: they get a
  worker of their own, because a large export takes hours and would otherwise hold up everyone
  else's few-minute job.
- Everything a run produces lives under `data/jobs/` and is deleted after 24 hours. Email
  conversions are deleted after two.

Environment variables, if you need them: `TOOLKIT_DATA_DIR`, `TOOLKIT_MAX_CONCURRENT_JOBS`,
`TOOLKIT_JOB_RETENTION_HOURS`, and `IMAGE_PROCESSOR_EXTRA_HOSTS` for the image allowlist. The
older `IMAGE_PROCESSOR_` spellings of the first three are still honoured.

---

# The Images from CSV tool

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

# The Images from Folder tool

The same naming convention as the CSV tool, applied to images you already have on disk rather than
a list of URLs.

Pick the folder holding your property folders. Inside it every image must sit exactly two levels
down, as `property code / document type / image`. The document type folder decides both the target
size and the output name, and is matched ignoring case and spacing, so `UnitImage`, `unit image`
and `Unit Image` are the same thing. Anything at the wrong depth is listed back to you and left
out.

Unit images are the case worth knowing about: one floor plan is usually shared by many apartments,
so each is cross referenced against `UnitMapping.csv`, `CompanyUnitSummery.csv` and
`PropertyList-Property.csv`, and **one output is produced per apartment**. Expect far more files
out than in; a batch of 48 images can produce well over a thousand. Those three files hold live
property and rent data, so they are uploaded with each run rather than kept on the server. Leave
them empty if you are not processing unit images.

Everything comes out as `.jpg`, except favicons, which become 64x64 `.ico`. Transparent PNGs are
flattened onto an opaque background. The ZIP always contains `Process_Log.csv`.

Up to 2000 files per batch, 50 MB per file and 500 MB in total. Saved defaults live in
`data/folder_default_options.json`.

---

# The Emails to HTML and Images tool

The source system stores each email body compressed and Base64 encoded, so it is unreadable in any
export pulled from the database. This turns each one back into the HTML page it was, and takes a
screenshot of it.

1. **Upload the export.** One CSV or Excel file, one row per email.
2. **Check the settings.** Leave the column layout on *Detect from the file*.
3. **Start the run.** Progress appears per email and can be cancelled at any point.
4. **Download the ZIP.** It holds `html/`, `images/`, and a failure log if anything failed.

## The two column layouts

Two shapes of export are in circulation, and picking the wrong one is the most common reason a run
fails before it starts. That is why the default reads the headings and decides for itself; the
dropdown is there to override it.

| Layout | Body column | Name column |
|---|---|---|
| CSV export | `sBody` | `hResEmailLog` |
| Legacy Excel | `sEmailMessage` | `hHistoryId` |

The name column becomes the output filename, so `6111692732` produces `6111692732.html` and
`6111692732.jpg`. A file in neither layout fails with a message naming both, and listing the
columns it actually found.

## What comes out

| Path | Contents |
|---|---|
| `html/` | One `.html` file per email |
| `images/` | One `.jpg` screenshot per email, when screenshots are on |
| `Failed_Records.csv` | Only written when something failed |

Each screenshot is rendered at the width declared in the email itself, so a narrow newsletter and
a full width template come out at the sizes they were designed for.

A bad record never stops the batch. It is counted as failed, listed on the results card and
written to the log, and the run carries on. The usual causes are an empty body, a value that is
not a compressed email, and a blank record id.

## Settings

| Setting | Default | Effect |
|---|---|---|
| Column layout | Detect from the file | Reads the headings and picks the matching layout |
| Screenshots | On | Off writes the HTML only, which is much faster and needs no `wkhtmltoimage` |

The rendering settings themselves, zoom and the width rules, are not exposed. They are calibrated
to match screenshots produced before this app existed, and changing them would make new output
disagree with old.

Saved defaults live in `data/emails_default_options.json`.

## Speed, and why it has its own queue

Rendering takes roughly a second per email, so a 4,000 row export is over an hour. That is long
enough to matter to everyone else, so email conversions run on a worker of their own: two of them
queue behind each other rather than filling the two slots the other three tools share.

## Handling of personal data

Decoded emails contain resident names, addresses and lease details. So:

- Uploads and output live under `data/jobs/`, which is gitignored and is not served as static
  files. Downloads go through the same job endpoints as every other tool.
- A finished run is deleted after **two hours**, rather than the 24 that applies elsewhere. The
  window is written into the workspace, so it survives a restart of the server.
- The failure log you download keeps the other columns from your export but not the body column.
- Nothing is logged but record ids.

The one thing this does not do is authenticate anybody, because nothing in this app does. Anyone
who can reach the server can start a run and, if they know the job id, download it. Job ids are
random 32 character values and are not listed anywhere, but that is obscurity, not access control.
Treat the host as you would treat a shared folder containing the same data.

## Limits

One file per run, up to 250 MB. Accepted formats are `.csv`, `.tsv`, `.txt`, `.xlsx`, `.xlsm` and
`.xls`.

## How the converter is integrated

The web app never decodes, measures or renders anything itself. It calls `read_table` and
`convert_row` from the
[greystar-email-converter](https://github.com/adityakajaleyardi/greystar-email-converter) package.
Those are used rather than the package's own `convert_file` because driving the loop here is what
allows per-email progress and a cancel that takes effect within a second; `convert_file` reports
every hundredth row and cannot be interrupted. No decoding, width detection or rendering is
duplicated.

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
    folder/               the same, for the folder image tool
    emails/               the same, for the email converter
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

Two things a tool can ask for without `jobs.py` knowing which tool it is: a worker of its own, by
passing `lane=` to `submit`, and a retention window shorter than the server-wide one, by passing
`retention_hours=` to `create`.

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

Tests for a tool skip themselves when its library is not installed, so the suite passes either
way. Nothing in the suite needs `wkhtmltoimage`: the email tests put a stub renderer in its place,
so the screenshot path is covered without the binary.

`app/processing/` must not import FastAPI or anything web related, so the command line keeps
working independently. The same applies to `app/events.py`.

Output filenames and image dimensions are a contract with downstream systems. They are pinned by
tests in `tests/test_naming.py` and `tests/test_images.py`; do not change them incidentally.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and [CHANGELOG.md](CHANGELOG.md) for
version history.

## License

MIT. See [LICENSE](LICENSE).
