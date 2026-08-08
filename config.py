"""Define platform-specific paths for bundled application resources."""

import os
import platform
import sys
from pathlib import Path


BASE_DIR = Path(
    getattr(
        sys,
        "_MEIPASS",
        Path(__file__).resolve().parent,
    )
)

IS_WINDOWS = platform.system() == "Windows"


def get_resource_path(*parts: str) -> str:
    """Return an absolute path inside the application resources directory."""
    return str(BASE_DIR.joinpath(*parts))


if IS_WINDOWS:
    DJI_SDK_EXE = get_resource_path(
        "resources",
        "dji_sdk",
        "windows_x64",
        "dji_irp.exe",
    )

    EXIFTOOL_EXE = get_resource_path(
        "resources",
        "exiftool",
        "exiftool.exe",
    )
else:
    DJI_SDK_EXE = get_resource_path(
        "resources",
        "dji_sdk",
        "ubuntu_x64",
        "dji_irp",
    )

    EXIFTOOL_EXE = os.environ.get(
        "EXIFTOOL_EXE",
        "/usr/bin/exiftool",
    )
