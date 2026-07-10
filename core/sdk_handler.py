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
    STARTUPINFO.wShowWindow = 0  # SW_HIDE (Görünmez yap)

# How many images to process at the same time. Capped at 8 so we don't
# overwhelm slower machines, even if they have more CPU cores.
MAX_WORKERS = min(8, os.cpu_count() or 4)


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
        """Run the full SDK + TIFF pipeline for one image. Returns (base_name, success)."""
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        raw_path = os.path.join(raw_folder, base_name + ".raw")
        tiff_path = os.path.join(output_folder, base_name + ".tiff")

        result = self._run_sdk_on_single_image(image_path, raw_path, params)
        if result.returncode != 0 or not os.path.exists(raw_path):
            return base_name, False

        success = self._raw_to_tiff(raw_path, image_path, tiff_path, ambient_temp)
        return base_name, success

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
        images in parallel.
        """
        dependency_error = self.check_dependencies()
        if dependency_error:
            return False, dependency_error

        try:
            float(distance)
            float(emissivity)
            float(reflected_temp.replace("°C", "").replace(" ", ""))
            float(ambient_temp.replace("°C", "").replace(" ", ""))
            float(humidity.replace("%", "").replace(" ", ""))
        except ValueError:
            return False, "Please enter valid numbers for all parameters."

        folder_path = os.path.normpath(folder_path)
        raw_folder = os.path.normpath(os.path.join(folder_path, "_raw_temp"))
        output_folder = os.path.normpath(os.path.join(folder_path, "converted_tiff"))

        os.makedirs(raw_folder, exist_ok=True)
        os.makedirs(output_folder, exist_ok=True)

        if float(distance) > 25.0:
            distance = "25.0"

        params = {
            "distance": distance,
            "emissivity": emissivity.replace(" ", ""),
            "reflected_temp": reflected_temp.replace("°C", "").replace(" ", ""),
            "humidity": humidity.replace("%", "").replace(" ", ""),
        }
        ambient_temp_clean = ambient_temp.replace("°C", "").replace(" ", "")

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
                        self._process_single_image, path, raw_folder, output_folder, params, ambient_temp_clean
                    )
                    for path in image_files
                ]

                for future in as_completed(futures):
                    base_name, success = future.result()
                    done += 1
                    if success:
                        converted_count += 1
                    else:
                        failed_files.append(base_name)
                    if progress_callback:
                        progress_callback(done, total)
        finally:
            shutil.rmtree(raw_folder, ignore_errors=True)

        if converted_count == 0:
            return False, f"Conversion failed for all files: {failed_files}"

        metadata_ok = self._copy_metadata_batch(output_folder)

        msg = f"Success! {converted_count} TIFF file(s) saved to:\n{output_folder}"
        if failed_files:
            msg += f"\n\nFailed: {len(failed_files)} file(s): {', '.join(failed_files)}"
        if metadata_ok:
            msg += f"\nGPS/metadata copied for {converted_count} file(s)."
        else:
            msg += "\nWarning: metadata copy step failed."
        return True, msg