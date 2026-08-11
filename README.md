# Radiometric Toolkit

Radiometric Toolkit is a Windows desktop utility for converting supported DJI radiometric thermal JPEG images into single-band `Float32 TIFF` temperature maps.

The application runs locally. It uses a shared Python conversion engine, an HTML/CSS/JavaScript desktop interface, Eel for the Python/JavaScript bridge, and pywebview to present the interface in a native Windows window.


## Features

- Batch scanning of `.jpg` and `.jpeg` files
- Automatic R, T, V, and Z image classification
- Conversion of supported radiometric R-JPEG / thermal images
- Automatic skipping of visible `_V` and zoom `_Z` images
- Dynamic thermal matrix dimensions from the DJI Thermal SDK
- Single-band 32-bit floating-point TIFF output
- Adobe Deflate TIFF compression
- Parallel image conversion
- EXIF, GPS, XMP, camera, flight, RTK, gimbal, and DJI metadata transfer
- Native Windows folder selection
- Local conversion progress and structured logs
- One-click opening of the generated output folder

## Measurement Parameters

| Parameter | Accepted range |
|---|---:|
| Distance | 1.0–25.0 m |
| Emissivity | 0.10–1.00 |
| Reflected temperature | -40.0–500.0 °C |
| Ambient temperature | -40.0–80.0 °C |
| Humidity | 20–100% |

These values are forwarded to the DJI Thermal SDK. Actual accepted values can also depend on the SDK version, camera model, and calibration data embedded in the source R-JPEG.

## Requirements

- Windows 10/11 x64
- Python 3.11 x64 when running from source
- Microsoft Edge WebView2 Runtime

The bundled DJI Thermal SDK and ExifTool files in this repository are Windows x64 components.

## Run from Source

Open PowerShell in the project directory:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

If `py -3.11` is not available, install a 64-bit Python 3.11 release first and recreate the virtual environment with that interpreter.

The desktop application starts an Eel service bound only to:

```text
127.0.0.1:8135
```

pywebview then loads the local desktop interface in a native Windows window. The application does not require a remote web service.

## Output

Converted TIFF files are written to:

```text
selected_folder/converted_tiff/
```

Temporary RAW files are created during conversion and removed after the conversion workflow completes.

## Project Structure

```text
radiometric-toolkit/
├── app/
│   ├── core/
│   │   └── processor.py        # Thermal conversion and metadata pipeline
│   └── desktop/
│       └── eel_app.py          # Windows desktop integration
├── resources/
│   ├── dji_sdk/windows_x64/    # DJI Thermal SDK runtime files
│   └── exiftool/               # Windows ExifTool distribution
├── tests/
│   ├── test_processor_dimensions.py
│   └── test_processor_reporting.py
├── web/
│   ├── desktop/                # Desktop HTML and JavaScript
│   ├── help/                   # Supported-file information
│   ├── releases/               # In-app release notes
│   └── shared/                 # Shared CSS, JavaScript, and Bootstrap assets
├── config.py                   # Bundled resource paths
├── main.py                     # Desktop entry point
├── requirements.txt
└── THIRD_PARTY_NOTICES.md
```

## Architecture

```text
Desktop UI (HTML/CSS/JavaScript)
            │
            │ Eel bridge
            ▼
Python desktop layer
            │
            ▼
ThermalProcessor
      ├── DJI Thermal SDK
      ├── NumPy
      ├── tifffile
      ├── Pillow
      └── ExifTool
            │
            ▼
Float32 TIFF + transferred metadata
```

The conversion engine is kept separate from the desktop integration so thermal processing logic can be tested independently of the GUI.

## Development Checks

Run the unit tests:

```powershell
python -m unittest discover -s tests -v
```

Compile-check the Python source:

```powershell
python -m compileall -q app config.py main.py
```

Check the first-party JavaScript syntax when Node.js is available:

```powershell
node --check web/desktop/app.js
node --check web/shared/js/common.js
```

Before publishing a release, also perform a Windows smoke test with a non-confidential supported radiometric image and confirm that folder selection, conversion, TIFF creation, metadata transfer, progress reporting, and opening the output folder all work as expected.

## Privacy

Radiometric Toolkit is designed as a local desktop utility. Selected image folders and generated TIFF files remain on the local machine. The application does not include telemetry, cloud uploads, or remote data processing.

## Third-Party Components

The repository includes third-party runtime components required by the conversion workflow. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

The DJI Thermal SDK and ExifTool remain subject to their own licenses and distribution terms. Do not assume that a license applied to the first-party source code also applies to bundled third-party binaries.

## Public Repository Note

Before publishing this project, confirm that you have the right to publish the source code and bundled third-party components. Create the public repository with fresh Git history rather than copying the former private repository's `.git` directory.
