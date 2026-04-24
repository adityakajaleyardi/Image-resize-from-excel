# Repository Structure

This document explains the organization and purpose of files in this repository.

## Root Level Files (Repository Core)

```
image_processor.py          - Main application script
requirements.txt            - Python dependencies
README.md                   - Comprehensive project documentation
CHANGELOG.md                - Version history and changes
CONTRIBUTING.md             - Contribution guidelines
LICENSE                     - MIT License
.gitignore                  - Files/folders excluded from git
```

## Configuration Files (Use in Production)

These files are used by the application and should be customized:

```
Config.csv                  - Application configuration
Source.csv                  - Input data (images to process)
PropertyHMY.csv             - Property ID mappings
UnitMapping.csv             - Unit type mappings (optional)
```

**Note**: Keep these in root directory. They're actual working files, not examples.

## Samples Directory

Contains example/template files for reference:

```
samples/
├── Source.csv.example      - Example input file structure
├── Config.csv.example      - Example configuration
├── PropertyHMY.csv.example - Example property mappings
└── README.md               - Sample data documentation
```

Copy these to root and rename if starting fresh.

## GitHub-Specific Files

```
.github/
└── workflows/
    └── quality.yml         - CI/CD pipeline configuration
```

## Folders to Exclude from Git (.gitignore)

These are **NOT** included in the repository:

### Build/Distribution
```
build/                      - PyInstaller build artifacts
dist/                       - PyInstaller distribution files
*.spec                      - PyInstaller specification files
```

### Output
```
Processed_Images/           - Output directory (generated at runtime)
```

### Backup Files
```
image_processor - Copy.py   - Backup script (excluded)
*.bak, *.backup             - Backup files
```

### Python Cache
```
__pycache__/                - Python bytecode cache
*.pyc, *.pyo                - Compiled Python files
```

### IDE/Editor Files
```
.vscode/                    - VS Code settings (local)
.idea/                      - JetBrains IDE settings
*.swp, *.swo                - Editor temporary files
```

### Hidden OS Files
```
.DS_Store                   - macOS system files
Thumbs.db                   - Windows thumbnail cache
```

## File Purposes

### Application Code
- **image_processor.py**: Core application with all processing logic

### Configuration
- **Config.csv**: Configures operation mode, sizing, output settings
- **Source.csv**: List of images to process with metadata
- **PropertyHMY.csv**: Maps property codes to HMY IDs
- **UnitMapping.csv**: Optional - unit type mappings

### Documentation
- **README.md**: Full documentation, features, quick start, troubleshooting
- **CHANGELOG.md**: Version history tracking
- **CONTRIBUTING.md**: Guidelines for contributors
- **LICENSE**: MIT license terms

### Dependencies
- **requirements.txt**: Python packages needed to run the application

### Screenshots & Examples (when added)
- A `docs/` folder could be created for additional documentation
- A `tests/` folder for automated tests (future enhancement)

## Workflow for Users

1. Clone repository
2. Copy sample files from `samples/` to root (or rename existing ones)
3. Edit Config.csv, Source.csv, PropertyHMY.csv as needed
4. Run: `python image_processor.py`
5. Check `Processed_Images/` for results

## What Gets Pushed to GitHub

- ✅ image_processor.py
- ✅ requirements.txt
- ✅ README.md, CHANGELOG.md, CONTRIBUTING.md
- ✅ LICENSE
- ✅ .gitignore
- ✅ .github/ (workflows)
- ✅ samples/ (examples)
- ❌ Config.csv, Source.csv (these are working files - users create their own)
- ❌ PropertyHMY.csv, UnitMapping.csv (keep as templates in samples/)
- ❌ build/, dist/ (generated files)
- ❌ image_processor - Copy.py (backups)
- ❌ *.spec files (PyInstaller - regenerated during build)
- ❌ __pycache__, .DS_Store, etc. (ignored)

## Version Control Notes

### Branches Recommended
- **main** - Stable, production-ready code
- **develop** - Development branch for new features
- **feature/*** - Feature branches for specific work

### Tags
- Tag releases: v4.2, v4.1, v4.0, etc.

### CI/CD
- GitHub Actions runs on push/PR to main and develop
- Checks code quality and formatting

## Future Enhancements

Consider adding:
- `tests/` directory with unit tests
- `docs/` directory with additional documentation and screenshots
- `scripts/` directory with utility scripts
- GitHub Action for automated testing
- Pre-commit hooks for code quality

---

**Last Updated**: March 2026
