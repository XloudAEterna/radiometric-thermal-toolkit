# DJI Thermal Image Converter

A modern, high-performance Windows desktop application for batch converting thermal images (R-JPEG/JPG) captured by DJI Enterprise drones (such as M3T) into true radiometric, scientific-grade TIFF format (32-bit float temperature matrices) with **100% loss-free metadata retention**.

Unlike basic image editors, this tool wraps the official **DJI Thermal SDK** directly to extract pure temperature matrices and integrates **ExifTool** to clone every critical EXIF, GPS, and XMP flight data profile. The generated TIFFs are immediately ready for seamless photogrammetry and geospatial positioning inside GIS software like **QGIS**, **ArcGIS**, or **WebODM**.

---

## 🚀 Key Features

- **Radiometric Temperature Extraction**
  - Extracts raw pixel-by-pixel thermal measurement arrays directly from DJI R-JPEG metadata.
  - Reconstructs and exports data structures into scientific-grade `Float32` single-band TIFF matrices.

- **Lossless Metadata Replication**
  - Automatically parses and transfers all critical spatial and telemetry blocks via embedded ExifTool routines.
  - Retains native `GPS Position`, `GPS Altitude`, `Camera Model (M3T)`, original timestamps, and telemetry XMP tags with zero data loss.

- **Asynchronous Concurrent Multithreading**
  - Implements a parallel execution pipeline leveraging Python's `ThreadPoolExecutor` to process large flight datasets simultaneously.
  - Drastically optimizes batch execution speed by eliminating sequential subprocess runtime overhead.

- **Adobe Deflate Data Compression**
  - Applies lossless bit-level mathematical compression during TIFF compilation.
  - Significantly reduces storage space footprint relative to the input imagery size without impacting numeric precision.

---

## 📂 New Project Structure

```text
dji_thermal_converter/
├── core/
│   └── sdk_handler.py       # Threaded conversion loop and ExifTool tag injection
├── web/                     # Unified Modern Frontend Layer
│   ├── css/
│   │   └── bootstrap.min.css
│   ├── js/
│   │   └── bootstrap.bundle.min.js
│   ├── app.js               # Event bridges mapping directly to native exposed Python
│   └── index.html           # Dark Theme UI layouts
├── resources/               # Bundled binary components
│   ├── dji_sdk/             # Official DJI Thermal SDK libraries
│   └── exiftool/            # Embedded ExifTool binary
├── config.py                # Global default constants and systemic paths
├── main.py                  # Single-file application entry point
├── requirements.txt         # Virtual Environment isolation package manifest
└── README.md
```

## 📝 Prerequisites

### Operating System
- Windows 10 / 11 (64-bit)

### Python
- Python 3.10 or newer (Ensure `Add Python to PATH` option is enabled during installation)

---

## 📖 Usage Guide

### 1. Environment Setup & Dependency Installation
Initialize a localized virtual environment, activate the shell configuration context, and deploy the application package dependencies:

```bash
# Navigate to the project root directory
cd dji_thermal_converter

# Create an isolated virtual environment
python -m venv venv

# Activate the virtual environment
venv\Scripts\activate

# Install compiled dependencies
pip install -r requirements.txt
```
### 2. Launching the Desktop Application
Ensure the virtual environment remains active, then start the asynchronous engine loop:

```bash
python main.py
```
### 3. Execution Steps
1- Select Input Workspace: Click Select Folder and navigate to the target workspace containing raw DJI R-JPEG/JPG images. The console automatically outputs the verified dataset density.

2- Configure Thermal Calibration Profiles: Fine-tune environmental correction metrics (Distance, Emissivity, Reflected Temperature, Ambient Temperature, and Relative Humidity) to adjust atmospheric attenuation factors based on flight telemetry data.

3- Execute Conversion: Click Start Conversion. The multi-threaded pipeline extracts the metadata layer, runs structural binary calculations via numpy, injects cloned flight metadata tags, and writes the output files into a new converted_tiff subdirectory created inside your source image directory.

## 🔬 Verifying the Results (Optional)
Want to prove that the conversion was successful and the temperature data is intact? Run the included inspection script:

```bash
python verify.py
```
1. Paste the path to your `converted_tiff` folder.
2. Select one of the generated files.
3. The script will output the exact Shape, Min, Max, and Mean temperatures and display a beautiful thermal heatmap using `matplotlib`.

## 📝 Technical Notes
- **The 25-Meter Constraint:** The DJI core processing engine implements a physical threshold restriction limiting distance calculations to 25.0 meters. Entering parameters exceeding this ceiling automatically triggers an internal safety clipping routine at 25.0m to prevent execution exceptions or thread faults.
- **Atmospheric Model Parity:** The user interface exposes an "Ambient Temperature" data field to sustain compatibility metrics relative to standard FLIR processing flows. However, the DJI thermodynamic algorithm ignores ambient air values at short drone operation margins, depending strictly on the "Reflected Temperature" constant to calculate true path compensation variables.