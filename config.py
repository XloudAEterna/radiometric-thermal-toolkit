"""Application-wide configuration values and bundled resource paths."""

import os
import sys

APP_TITLE = "DJI THERMAL CONVERTER"

# Default values shown in the input fields when the app opens.
# Kept at 0 on purpose so the field is obviously "not yet set" — the user
# must enter their own value before converting. Keys match the parameter
# names used throughout sdk_handler.py and app.js.
DEFAULT_PARAMS = {
    "distance": "0",
    "emissivity": "0",
    "reflected_temp": "0",
    "ambient_temp": "0",
    "humidity": "0",
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