# Image Processor

A professional Python-based image processing tool designed to download, resize, rename, and organize images from URLs with intelligent doc-type recognition and folder management.

## Features

- 🖼️ **Batch Image Processing** - Process multiple images from CSV sources
- 📥 **Smart Download** - Multi-domain fallback support for reliable image retrieval
- 🔄 **Intelligent Resizing** - Context-aware sizing based on image type (iType)
- 📝 **Custom Naming** - Generate professional file names with doc-type abbreviations or use custom names
- 📁 **Automatic Organization** - Organize images into structured folders by property and document type
- 🎯 **Flexible Configuration** - CSV-based configuration with property type support (MVC/LEGACY)
- ✅ **Comprehensive Logging** - Detailed process logs and error tracking
- 🔧 **Extensible** - Support for 30+ document types with mappings

## System Requirements

- Python 3.7+
- Windows/macOS/Linux
- Internet connection (for downloading images)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/image-processor.git
   cd image-processor
   ```

2. **Create virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### 1. Prepare Input Files

Create or use the following CSV files in the project directory:

#### **Source.csv** (Main input file)
| Column | Description | Required |
|--------|-------------|----------|
| Property/Company Code | Property identifier | ✓ |
| Property Name | Human-readable property name | ✓ |
| File Name | Original file name | ✓ |
| iType | Image type code (determines sizing) | ✓ |
| Order | Sort order | Optional |
| Doc. Type | Document type (for categorization) | ✓ |
| Floorplan Code | Floorplan identifier | Optional |
| Active/Inactive | Process flag | ✓ |
| Full Path | Image URL | ✓ |
| Target Property | Override property for output | Optional |
| Target Image Name | Custom output filename (skips auto-naming) | Optional |

#### **Config.csv** (Configuration)
```
sourcefile,Source.csv
outputfolder,Processed_Images
propertytype,MVC
operationmode,2
targetwidth,2560
targetheight,1707
maxfilesizemb,1.0
manualsizing,0
optimizedsuffix,0
```

#### **PropertyHMY.csv** (Property ID mapping)
```
Property Code,Property Id
p0054387,50651
p0054388,50652
```

#### **UnitMapping.csv** (Optional - for unit type mappings)

### 2. Configure (Optional)

Edit `Config.csv`:
- **operationmode**: 1=Rename only, 2=Resize (default: 2)
- **propertytype**: MVC or LEGACY (affects sizing rules)
- **manualsizing**: 0=Auto rules, 1=Manual config
- **optimizedsuffix**: 1=Add "Optimized" suffix, 0=Don't add (default: 0)
- **targetwidth/height**: Used when manualsizing=1

### 3. Run the Processor

```bash
python image_processor.py
```

The processor will:
1. Load configuration from `Config.csv`
2. Read image entries from `Source.csv`
3. Download images (with fallback domains)
4. Resize/crop based on iType and config
5. Generate professional filenames or use custom names
6. Save to organized folder structure
7. Generate process logs

### 4. Check Results

- **Processed images**: `Processed_Images/[Property]__[DocType]/`
- **Process log**: `Processed_Images/Process_Log.csv`
- **Error log**: `Processed_Images/Failed_Log.csv` or `.xlsx`

## Configuration Details

### Image Types (iType)

| iType | Description | Target Size |
|-------|-------------|------------|
| 1 | Primary image | 2560x1707 (MVC) or 1024x768 (LEGACY) |
| 2 | Wide format | 99999x480 |
| 4 | Standard | 2560x1707 (MVC) |
| 5 | Thumbnail | 500x350 |
| 6 | Vertical | 350x99999 |
| 40 | Photo gallery | 99999x1000 |
| ... | [See DOC_TYPE_MAPPING] | - |

### Document Type Abbreviations

- PG = Photo Gallery
- FP = Floorplan
- SP = Site Plan
- BG = Background Image
- Banner = Banner Image
- log = Property Logo
- AmenityImage = Amenity Images
- Template = Template Images
- ... [30+ types supported]

### Target Image Name Feature

Leave blank to use auto-generated names:
```
SizableCompanyName_ImageDescription_40_PG.jpg
```

Or provide a custom name to skip all renaming logic:
```
my_custom_image_name.jpg
```

**Note**: Sizing and folder organization still apply with custom names.

## Supported Image Types & Domains

### Primary Domain
- www.rentcafe.com

### Fallback Domains (if primary fails)
- cdngeneral.rentcafe.com
- cdngeneralcf.rentcafe.com

### Supported Formats
- **Input**: JPEG, PNG, GIF, WebP
- **Output**: JPEG (default) or PNG (based on iType)

## Output Structure

```
Processed_Images/
├── Process_Log.csv
├── Failed_Log.csv
├── PropertyName__DocType/
│   ├── propertyname_imagedesc_itype_docabbr.jpg
│   ├── propertyname_imagedesc_itype_docabbr.jpg
│   └── ...
└── AnotherProperty__OtherDocType/
    └── ...
```

## Advanced Usage

### Custom Sizing Rules

To use custom dimensions instead of intelligent sizing:

1. Set `manualsizing` to `1` in `Config.csv`
2. Set desired `targetwidth` and `targetheight`
3. All images will be resized to these dimensions

### Vertical Image Handling

Vertical images (height > width) are automatically:
1. Cropped to remove 15% from top and bottom
2. Resized to fit target box
3. Logged with "Vertical Crop & Resized" action

### Batch Processing with Errors

Failed records are saved with detailed error messages:
- Check `Failed_Log.csv/xlsx` for failed entries
- Errors include download issues, processing errors, file system issues

## Logging

### Process Log Columns
- Folder: Output directory
- status: 'success' or 'fail'
- Original: Source URL
- New: Output file path
- SizeMB: Final file size
- Error: Error message (if failed)

## Troubleshooting

### Issue: "File could not be downloaded (404/Timeout)"
- Check URL in Source.csv
- Verify internet connection
- Check if image still exists at source

### Issue: Images not resized
- Verify iType value is correct
- Check if `operationmode` is set to 2 (Resize)
- Check image dimensions vs target sizing rules

### Issue: Folder names look strange
- This is expected - special characters are converted to underscores
- Use `Target Property` column to override property name

### Issue: File size too large
- Reduce `maxfilesizemb` in Config.csv
- This applies compression to reduce file size

## Performance Tips

- Process in batches of 100-500 images
- Use robust internet connection for reliability
- Enable logging for troubleshooting
- Verify a few rows before processing entire dataset

## Dependencies

See [requirements.txt](requirements.txt) for full list:
- pandas
- Pillow
- requests
- openpyxl (for Excel export)

## Making Changes

1. Modify `image_processor.py` for core logic changes
2. Update `.spec` versioning files when PyInstaller builds
3. Update `README.md` when adding features

## Version History

- **v4.2** - Added Target Image Name column for custom naming
- **v4.1** - Enhanced doc-type mapping with 30+ types
- **v3.4** - Added vertical image crop logic
- **v1.0** - Initial release

## Building Executable (Optional)

To create a standalone executable using PyInstaller:

```bash
pip install pyinstaller
pyinstaller ImageProcessorV4.2.spec
```

Executable will be in `dist/ImageProcessor/`

## Contributing

1. Create feature branch
2. Make changes
3. Test thoroughly
4. Create pull request

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or suggestions:
- Check the Troubleshooting section
- Review process logs for details
- Create an issue in the repository

---

**Last Updated**: March 2026  
**Current Version**: 4.2
