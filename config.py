"""Application-wide configuration values and bundled resource paths."""

import os
import sys

APP_TITLE = "DJI THERMAL CONVERTER"
APP_GEOMETRY = "450x600"

DEFAULT_PARAMS = {
    "Distance (m)": "50",
    "Emissivity": "0.98",
    "Reflected Temp (°C)": "32",
    "Ambient Temp (°C)": "32",
    "Humidity (%)": "40",
}


def get_resource_path(relative_path):
    """
    Resolve a path to a bundled resource (SDK, exiftool, etc).
    Works both when running from source AND when packaged into a
    single .exe with PyInstaller (which unpacks bundled files into
    a temporary folder referenced by sys._MEIPASS).
    """
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# Bundled DJI SDK executable — the user never needs to select this manually.
DJI_SDK_EXE = get_resource_path(
    os.path.join("resources", "dji_sdk", "utility", "bin", "windows", "release_x64", "dji_irp.exe")
)

# Bundled exiftool executable — used to copy GPS/EXIF metadata onto the output TIFF.
EXIFTOOL_EXE = get_resource_path(os.path.join("resources", "exiftool", "exiftool.exe"))
INDEX_HTML = get_resource_path(os.path.join("web", "index.html"))