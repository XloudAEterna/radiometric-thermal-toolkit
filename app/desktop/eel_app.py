"""Windows desktop integration for Radiometric Toolkit."""

from __future__ import annotations

import ctypes
import os
import socket
import sys
import threading
import time
from typing import Any

import eel
import webview

from app.core.processor import ThermalProcessor


processor = ThermalProcessor()


@eel.expose
def select_folder() -> dict[str, Any] | None:
    """Open a native folder dialog and return supported image information."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)

    try:
        folder_path = filedialog.askdirectory(
            title="Select Radiometric Thermal Images Folder"
        )
    finally:
        root.destroy()

    if not folder_path:
        return None

    normalized_path = os.path.normpath(folder_path)
    images = processor.find_images(normalized_path)
    counts = processor.count_image_types(normalized_path)

    return {
        "success": True,
        "folder": normalized_path,
        "count": len(images),
        "counts": counts,
    }


@eel.expose
def start_conversion(params: dict[str, Any]) -> dict[str, Any]:
    """Start the conversion pipeline without blocking the desktop interface."""

    def run_conversion() -> None:
        try:
            success, message = processor.execute_conversion(
                folder_path=params["folder_path"],
                distance=params["distance"],
                emissivity=params["emissivity"],
                reflected_temp=params["reflected_temp"],
                ambient_temp=params["ambient_temp"],
                humidity=params["humidity"],
                progress_callback=eel.updateDesktopProgress,
            )

            eel.conversionFinished(success, message)
        except Exception as error:
            eel.conversionFinished(
                False,
                f"Critical Thread Failure: {error}",
            )

    threading.Thread(
        target=run_conversion,
        daemon=True,
    ).start()

    return {
        "success": True,
        "message": "Conversion started.",
    }


@eel.expose
def open_output_folder(folder_path: str) -> dict[str, Any]:
    """Open the converted TIFF folder in Windows Explorer."""
    try:
        normalized_path = os.path.normpath(folder_path)

        if not os.path.isdir(normalized_path):
            return {"success": False, "message": "Output folder not found."}

        os.startfile(normalized_path)
        return {"success": True, "message": "Folder opened."}
    except Exception as error:
        return {"success": False, "message": f"Could not open folder: {error}"}


DESKTOP_SERVER_HOST = "127.0.0.1"
DESKTOP_SERVER_PORT = 8135
WINDOWS_APP_ID = "RadiometricToolkit.Desktop"


def _get_resource_path(*parts: str) -> str:
    """Return a resource path in source and packaged modes."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_directory = sys._MEIPASS
    else:
        base_directory = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
            )
        )

    return os.path.join(base_directory, *parts)

def _get_application_icon_path() -> str:
    """Return the Windows application icon path."""
    return _get_resource_path(
        "resources",
        "branding",
        "app_icon.ico",
    )

def _get_web_directory() -> str:
    """Return the frontend directory."""
    return _get_resource_path("web")


def _configure_webview2() -> None:
    """Force WebView2 to connect to the local Eel server directly."""
    variable_name = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"
    direct_connection_argument = "--no-proxy-server"

    current_arguments = os.environ.get(variable_name, "").strip()

    if direct_connection_argument not in current_arguments.split():
        os.environ[variable_name] = (
            f"{current_arguments} {direct_connection_argument}"
        ).strip()


def _ensure_desktop_port_is_available() -> None:
    """Stop clearly if the desktop port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        try:
            server_socket.bind((DESKTOP_SERVER_HOST, DESKTOP_SERVER_PORT))
        except OSError as error:
            raise RuntimeError(
                "Radiometric Toolkit is already running, "
                f"or local port {DESKTOP_SERVER_PORT} is in use."
            ) from error


def _wait_for_desktop_server(timeout_seconds: float = 10.0) -> None:
    """Wait until the local Eel server accepts connections."""
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        try:
            with socket.create_connection(
                (DESKTOP_SERVER_HOST, DESKTOP_SERVER_PORT),
                timeout=0.25,
            ):
                return
        except OSError:
            time.sleep(0.1)

    raise RuntimeError("The desktop application server did not start in time.")


def _run_eel_server() -> None:
    """Run the Eel server in a background thread."""
    eel.start(
        "desktop/index.html",
        mode=None,
        host=DESKTOP_SERVER_HOST,
        port=DESKTOP_SERVER_PORT,
        block=True,
    )


def run_desktop_application() -> None:
    """Run the Eel application inside a native Windows window."""
    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            WINDOWS_APP_ID
        )

    _configure_webview2()
    _ensure_desktop_port_is_available()

    eel.init(_get_web_directory())

    server_thread = threading.Thread(
        target=_run_eel_server,
        name="eel-desktop-server",
        daemon=True,
    )
    server_thread.start()

    _wait_for_desktop_server()

    application_url = (
        f"http://{DESKTOP_SERVER_HOST}:{DESKTOP_SERVER_PORT}/desktop/index.html"
    )

    webview.create_window(
        title="Radiometric Toolkit",
        url=application_url,
        width=900,
        height=1000,
        min_size=(820, 820),
        resizable=True,
        background_color="#0b1017",
        text_select=False,
    )

    try:
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            icon=_get_application_icon_path(),
        )
    except (SystemExit, KeyboardInterrupt):
        pass
