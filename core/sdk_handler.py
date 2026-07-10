"""Wraps the DJI Thermal SDK tool to convert thermal JPGs into radiometric TIFF files."""

import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import tifffile
from PIL import Image

from config import DJI_SDK_EXE, EXIFTOOL_EXE

# Windows background process flags to prevent CMD window popups
STARTUPINFO = None
if os.name == 'nt':
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUPINFO.wShowWindow = 0  # SW_HIDE

# How many images to process at the same time. Capped at 8 so we don't
# overwhelm slower machines, even if they have more CPU cores.
MAX_WORKERS = min(8, os.cpu_count() or 4)

# Valid ranges for each thermal parameter, per the DJI Thermal SDK's own
# dirp_measurement_params_range_t limits, confirmed with the DJI SDK contact
# (Jacopo). These are the values the SDK itself will accept; anything outside
# them will be rejected by dji_irp.exe.
PARAM_RANGES = {
    "distance": (1.0, 25.0),
    "emissivity": (0.1, 1.0),
    "reflected_temp": (-40.0, 500.0),
    "ambient_temp": (-20.0, 50.0),
    "humidity": (20, 100),
}


class ThermalProcessor:
    """Finds DJI thermal images and converts them into TIFF files using the bundled DJI SDK."""

    def find_images(self, folder_path):
        """Return a list of all .jpg/.jpeg files found in the given folder."""
        image_list = []
        for file in os.listdir(folder_path):
            if file.lower().endswith((".jpg", ".jpeg")):
                image_list.append(os.path.join(folder_path, file))
        return image_list

    def check_dependencies(self):
        """Verify that the bundled SDK and exiftool are present. Returns an error message or None."""
        if not os.path.exists(DJI_SDK_EXE):
            return "Application files are missing (DJI SDK). Please reinstall the application."
        if not os.path.exists(EXIFTOOL_EXE):
            return "Application files are missing (exiftool). Please reinstall the application."
        return None

    def _run_sdk_on_single_image(self, image_path, raw_path, params):
        """Run the SDK tool on one image and save its raw temperature output."""
        working_dir = os.path.dirname(DJI_SDK_EXE)
        command = [
            DJI_SDK_EXE,
            "-s", image_path,
            "-a", "measure",
            "-o", raw_path,
            "--measurefmt", "float32",
            "--distance", str(params["distance"]),
            "--emissivity", str(params["emissivity"]),
            "--reflection", str(params["reflected_temp"]),
            "--humidity", str(params["humidity"]),
        ]
        return subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=False, cwd=working_dir,
            startupinfo=STARTUPINFO,
        )

    def _raw_to_tiff(self, raw_path, original_jpg_path, tiff_path, ambient_temp):
        """Convert a raw temperature file into a TIFF file. Returns True on success."""
        with Image.open(original_jpg_path) as im:
            width, height = im.size

        data = np.fromfile(raw_path, dtype=np.float32)
        if data.size != width * height:
            return False

        temperature_grid = data.reshape(height, width)
        description = f"Ambient Temp (reference only, not used in calculation): {ambient_temp} C"

        tifffile.imwrite(
            tiff_path,
            temperature_grid.astype(np.float32),
            description=description,
            compression="zlib",
        )
        return True

    def _process_single_image(self, image_path, raw_folder, output_folder, params, ambient_temp):
        """Run the full SDK + TIFF pipeline for one image. Returns (base_name, success, error_detail)."""
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        raw_path = os.path.join(raw_folder, base_name + ".raw")
        tiff_path = os.path.join(output_folder, base_name + ".tiff")

        result = self._run_sdk_on_single_image(image_path, raw_path, params)
        if result.returncode != 0 or not os.path.exists(raw_path):
            # Surface the SDK's own error instead of hiding it. This is where an
            # out-of-calibration-range distance for a given camera/image would
            # actually get caught, rather than a hardcoded app-side guess.
            detail = result.stderr.strip() if result.stderr else f"exit code {result.returncode}"
            return base_name, False, detail

        success = self._raw_to_tiff(raw_path, image_path, tiff_path, ambient_temp)
        detail = "" if success else "raw-to-tiff size mismatch"
        return base_name, success, detail

    def _copy_metadata_batch(self, output_folder):
        """
        Copy EXIF/GPS metadata from each original JPG to its matching TIFF
        with ONE exiftool call for the whole folder (instead of one call per
        file), since exiftool's own startup time is the main bottleneck.
        """
        try:
            result = subprocess.run(
                [
                    EXIFTOOL_EXE,
                    "-overwrite_original",
                    "-tagsFromFile", "%d../%f.JPG",
                    "-all:all",
                    "-ext", "tiff",
                    output_folder,
                ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
                startupinfo=STARTUPINFO,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def execute_conversion(self, folder_path, distance, emissivity,
                            reflected_temp, ambient_temp, humidity, progress_callback=None):
        """
        Convert every thermal image in folder_path to TIFF, running several
        images in parallel. Returns (success, message).
        """
        dependency_error = self.check_dependencies()
        if dependency_error:
            return False, dependency_error

        try:
            distance_value = float(distance)
            emissivity_value = float(emissivity)
            reflected_value = float(reflected_temp.replace("°C", "").replace(" ", ""))
            ambient_value = float(ambient_temp.replace("°C", "").replace(" ", ""))
            humidity_value = float(humidity.replace("%", "").replace(" ", ""))
        except ValueError:
            return False, "Please enter valid numbers for all parameters."

        if not (PARAM_RANGES["distance"][0] <= distance_value <= PARAM_RANGES["distance"][1]):
            return False, (
                f"Distance must be between {PARAM_RANGES['distance'][0]} and "
                f"{PARAM_RANGES['distance'][1]} meters (DJI Thermal SDK limit)."
            )
        if not (PARAM_RANGES["emissivity"][0] <= emissivity_value <= PARAM_RANGES["emissivity"][1]):
            return False, f"Emissivity must be between {PARAM_RANGES['emissivity'][0]} and {PARAM_RANGES['emissivity'][1]}."
        if not (PARAM_RANGES["reflected_temp"][0] <= reflected_value <= PARAM_RANGES["reflected_temp"][1]):
            return False, f"Reflected Temp must be between {PARAM_RANGES['reflected_temp'][0]} and {PARAM_RANGES['reflected_temp'][1]} °C."
        if not (PARAM_RANGES["ambient_temp"][0] <= ambient_value <= PARAM_RANGES["ambient_temp"][1]):
            return False, f"Ambient Temp must be between {PARAM_RANGES['ambient_temp'][0]} and {PARAM_RANGES['ambient_temp'][1]} °C."
        if not (PARAM_RANGES["humidity"][0] <= humidity_value <= PARAM_RANGES["humidity"][1]):
            return False, f"Humidity must be between {PARAM_RANGES['humidity'][0]} and {PARAM_RANGES['humidity'][1]}%."

        folder_path = os.path.normpath(folder_path)
        raw_folder = os.path.normpath(os.path.join(folder_path, "_raw_temp"))
        output_folder = os.path.normpath(os.path.join(folder_path, "converted_tiff"))

        os.makedirs(raw_folder, exist_ok=True)
        os.makedirs(output_folder, exist_ok=True)

        params = {
            "distance": distance_value,
            "emissivity": emissivity_value,
            "reflected_temp": reflected_value,
            "humidity": humidity_value,
        }

        image_files = self.find_images(folder_path)
        if not image_files:
            return False, "No JPG files found in the selected folder."

        total = len(image_files)
        done = 0
        converted_count = 0
        failed_files = []

        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [
                    executor.submit(
                        self._process_single_image, path, raw_folder, output_folder, params, ambient_value
                    )
                    for path in image_files
                ]

                for future in as_completed(futures):
                    base_name, success, error_detail = future.result()
                    done += 1
                    if success:
                        converted_count += 1
                    else:
                        failed_files.append(f"{base_name} ({error_detail})")
                    if progress_callback:
                        progress_callback(done, total)
        finally:
            shutil.rmtree(raw_folder, ignore_errors=True)

        if converted_count == 0:
            return False, "Conversion failed for all files:\n" + "\n".join(failed_files)

        metadata_ok = self._copy_metadata_batch(output_folder)

        msg = f"Success! {converted_count} TIFF file(s) saved to:\n{output_folder}"
        if failed_files:
            msg += f"\n\nFailed: {len(failed_files)} file(s):\n" + "\n".join(failed_files)
        if metadata_ok:
            msg += f"\nGPS/metadata copied for {converted_count} file(s)."
        else:
            msg += "\nWarning: metadata copy step failed."
        return True, msg