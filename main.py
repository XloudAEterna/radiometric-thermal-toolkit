"""Main entrypoint for the DJI Thermal Converter desktop application using Eel."""

import os
import sys
import threading

import eel

from core.sdk_handler import ThermalProcessor
from config import DEFAULT_PARAMS


processor = ThermalProcessor()

@eel.expose
def get_default_params():
    """Return default thermal parameter values so the frontend can populate the input fields."""
    return DEFAULT_PARAMS

@eel.expose
def select_folder():
    """Opens a native Windows folder dialog using tkinter tightly scoped to this function.

    This ensures no residual GUI memory overhead and 100% reliability.
    """
    import tkinter as tk
    from tkinter import filedialog

    # Standard context manager or tight scope to completely eliminate tkinter overhead
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)  # Bring the folder dialog to the front

    folder_path = filedialog.askdirectory(title="Select DJI Thermal Images Folder")
    root.destroy()  # Instantly wipe tkinter out of memory

    if folder_path:
        folder_path = os.path.normpath(folder_path)
        images = processor.find_images(folder_path)
        return {"folder": folder_path, "count": len(images)}
    return None


@eel.expose
def start_conversion(params):
    """Launch the multi-threaded radiometric conversion pipeline in a background thread."""

    def run():
        try:
            success, message = processor.execute_conversion(
                folder_path=params["folder_path"],
                distance=params["distance"],
                emissivity=params["emissivity"],
                reflected_temp=params["reflected_temp"],
                ambient_temp=params["ambient_temp"],
                humidity=params["humidity"],
                progress_callback=eel.updateProgress,
            )
            eel.conversionFinished(success, message)
        except Exception as e:
            eel.conversionFinished(False, f"Critical Thread Failure: {str(e)}")

    # Execute in a daemon thread so the UI never freezes
    threading.Thread(target=run, daemon=True).start()


def main():
    """Configure Eel asset pathways and deploy the local web application container."""
    # Ensure relative asset pathways map correctly when bundled inside PyInstaller
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        web_dir = os.path.join(sys._MEIPASS, "web")
    else:
        web_dir = "web"

    eel.init(web_dir)

    try:
        # Start the application using Chrome/Edge user interface
        eel.start(
            "index.html",
            mode="edge",
            size=(850, 750),
            cmdline_args=["--disable-extensions", "--disable-plugins"],
        )
    except (SystemExit, MemoryError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()