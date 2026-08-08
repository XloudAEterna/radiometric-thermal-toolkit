"""Convert DJI radiometric thermal images into Float32 TIFF files."""

import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import tifffile
from PIL import Image

from config import DJI_SDK_EXE, EXIFTOOL_EXE

# Prevent DJI SDK and ExifTool console windows from appearing on Windows.
STARTUPINFO = None

if os.name == "nt":
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUPINFO.wShowWindow = 0

# How many images to process at the same time. Capped at 8 so we don't
# overwhelm slower machines, even if they have more CPU cores.
MAX_WORKERS = min(8, os.cpu_count() or 4)

KNOWN_THERMAL_DIMENSIONS = (
    (640, 512),
    (1280, 1024),
)

DIRP_ERROR_MESSAGES = {
    -1: "The DJI SDK ran out of memory while processing this image.",
    -2: "The DJI SDK encountered an internal error (null pointer).",
    -3: "The DJI SDK rejected the conversion parameters as invalid.",
    -4: "This file's embedded thermal data is invalid or corrupted.",
    -5: "This file's thermal header is invalid or missing.",
    -6: "This file's calibration curve data is invalid.",
    -7: (
        "This file is not a valid radiometric thermal image. Only true "
        "R-JPEG files contain the data needed for temperature conversion."
    ),
    -8: "The DJI SDK reported an unexpected data size for this image.",
    -9: "The DJI SDK reported an invalid internal handle.",
    -10: "This file's format is not supported by the DJI SDK.",
    -11: "The DJI SDK could not produce output in the requested format.",
    -12: "This operation is not supported by the installed DJI SDK version.",
    -13: "The DJI SDK was not ready to process this image.",
    -14: "The DJI SDK reported a licensing/activation error.",
    -15: "The DJI SDK configuration file is invalid.",
    -16: "The DJI SDK could not load a required internal library.",
}

PARAM_RANGES = {
    "distance": (1.0, 25.0),
    "emissivity": (0.1, 1.0),
    "reflected_temp": (-40.0, 500.0),
    "ambient_temp": (-40.0, 80.0),
    "humidity": (20, 100),
}


class ThermalProcessor:
    """Convert DJI thermal images using the platform-specific DJI SDK."""

    def find_images(self, folder_path):
        """Return JPG files that may contain radiometric thermal data."""
        images = []

        for file_name in os.listdir(folder_path):
            if not file_name.lower().endswith((".jpg", ".jpeg")):
                continue

            base_name = os.path.splitext(file_name)[0].upper()

            if base_name.endswith(("_V", "_Z")):
                continue

            images.append(os.path.join(folder_path, file_name))

        return images
    
    def count_image_types(self, folder_path):
        counts = {
            "r": 0,
            "t": 0,
            "v": 0,
            "z": 0,
            "other": 0,
        }

        for file_name in os.listdir(folder_path):
            if not file_name.lower().endswith((".jpg", ".jpeg")):
                continue

            base_name = os.path.splitext(file_name)[0].upper()

            if base_name.endswith("_R"):
                counts["r"] += 1
            elif base_name.endswith("_T"):
                counts["t"] += 1
            elif base_name.endswith("_V"):
                counts["v"] += 1
            elif base_name.endswith("_Z"):
                counts["z"] += 1
            else:
                counts["other"] += 1

        return counts

    def check_dependencies(self):
        """Return an error message when a required executable is missing."""
        if not os.path.exists(DJI_SDK_EXE):
            return "Application files are missing (DJI SDK). Please reinstall the application."
        if not os.path.exists(EXIFTOOL_EXE):
            return "Application files are missing (exiftool). Please reinstall the application."
        return None

    @staticmethod
    def _parse_numeric_value(value, suffix=""):
        """Normalize a user-provided numeric value and convert it to float."""
        normalized_value = str(value).replace(suffix, "").replace(" ", "")

        return float(normalized_value)

    @staticmethod
    def _parse_sdk_dimensions(output_text):
        """Extract the thermal matrix width and height from DJI SDK output."""
        width_match = re.search(
            r"\bwidth\s*[:=]\s*(\d+)\b",
            output_text or "",
            flags=re.IGNORECASE,
        )
        height_match = re.search(
            r"\bheight\s*[:=]\s*(\d+)\b",
            output_text or "",
            flags=re.IGNORECASE,
        )

        if not width_match or not height_match:
            return None

        width = int(width_match.group(1))
        height = int(height_match.group(1))

        if width <= 0 or height <= 0:
            return None

        return width, height

    @staticmethod
    def _normalize_exit_code(return_code):
        """Return the signed DJI error code used by the SDK."""
        if return_code > 0x7FFFFFFF:
            return return_code - 0x100000000

        # On Linux, a program returning a negative code is exposed as an
        # unsigned 8-bit process status: for example 250 means -6.
        if 128 <= return_code <= 255:
            return return_code - 256

        return return_code

    @staticmethod
    def _extract_sdk_error_code(result):
        """Read the real DJI code from CLI output, then fall back to process status."""
        sdk_output = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if part and part.strip()
        )

        matches = re.findall(
            r"return\s+code\s*[:=]?\s*(-?\d+)",
            sdk_output,
            flags=re.IGNORECASE,
        )

        if matches:
            return int(matches[-1])

        return ThermalProcessor._normalize_exit_code(result.returncode)

    @staticmethod
    def _format_measurement_params(params):
        """Format the active measurement parameters for a user-facing error."""
        return (
            f"Distance {params['distance']:g} m, "
            f"Emissivity {params['emissivity']:g}, "
            f"Reflected Temp {params['reflected_temp']:g} °C, "
            f"Ambient Temp {params['ambient_temp']:g} °C, "
            f"Humidity {params['humidity']:g}%"
        )

    @staticmethod
    def _format_sdk_failure(result, params):
        """Convert a DJI SDK failure into a short user-facing message."""
        code = ThermalProcessor._extract_sdk_error_code(result)

        if code == -3:
            return (
                "DJI SDK rejected these parameters for this image. "
                "Supported ranges may vary by camera model and embedded "
                "R-JPEG calibration. "
                "SDK code -3."
            )

        if code == -6:
            return (
                "DJI SDK could not use this image's thermal calibration. "
                "Compatibility may vary by camera model and embedded "
                "R-JPEG calibration. "
                "SDK code -6."
            )

        known_message = DIRP_ERROR_MESSAGES.get(code)

        if known_message:
            return f"{known_message} SDK code {code}."

        if code <= -32:
            return (
                "DJI SDK returned a camera/model-specific error. "
                f"SDK code {code}."
            )

        if code == 0:
            return (
                "DJI SDK finished without creating the required RAW "
                "temperature file."
            )

        return (
            "DJI SDK failed to convert this image. "
            f"SDK code {code}."
        )

    def _resolve_temperature_dimensions(
        self,
        data_size,
        original_jpg_path,
        sdk_output,
    ):
        """Resolve the RAW thermal matrix dimensions without trusting preview size."""
        sdk_dimensions = self._parse_sdk_dimensions(sdk_output)

        if sdk_dimensions is not None:
            width, height = sdk_dimensions

            if width * height == data_size:
                return width, height, None

            return (
                None,
                None,
                (
                    "Thermal matrix size mismatch: the DJI SDK reported "
                    f"{width} x {height} ({width * height} pixels), but the "
                    f"RAW file contains {data_size} Float32 pixels."
                ),
            )

        # Some SDK builds do not print dimensions. The visible JPEG size is a
        # valid fallback only when its pixel count exactly matches the RAW data.
        try:
            with Image.open(original_jpg_path) as image:
                source_width, source_height = image.size
        except (OSError, ValueError):
            source_width = source_height = 0

        if source_width * source_height == data_size:
            return source_width, source_height, None

        # DJI enterprise thermal imagery commonly uses these matrix sizes. This
        # fallback is based on RAW pixel count, not on the visible preview size.
        for width, height in KNOWN_THERMAL_DIMENSIONS:
            if width * height == data_size:
                return width, height, None

        return (
            None,
            None,
            (
                "Thermal matrix dimensions could not be determined. "
                f"The RAW file contains {data_size} Float32 pixels and the DJI "
                "SDK did not report a matching width and height."
            ),
        )

    def _run_sdk_on_single_image(
        self,
        image_path,
        raw_path,
        params,
    ):
        """Run the DJI SDK for one source image."""
        working_directory = os.path.dirname(DJI_SDK_EXE)

        command = [
            DJI_SDK_EXE,
            "-s",
            image_path,
            "-a",
            "measure",
            "-o",
            raw_path,
            "--measurefmt",
            "float32",
            "--distance",
            str(params["distance"]),
            "--emissivity",
            str(params["emissivity"]),
            "--ambient",
            str(params["ambient_temp"]),
            "--reflection",
            str(params["reflected_temp"]),
            "--humidity",
            str(params["humidity"]),
        ]

        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            cwd=working_directory,
            startupinfo=STARTUPINFO,
        )

    def _raw_to_tiff(
        self,
        raw_path,
        original_jpg_path,
        tiff_path,
        ambient_temp,
        sdk_output,
    ):
        """
        Convert a raw Float32 temperature file into a TIFF image.

        Returns:
            A tuple containing the success state, minimum temperature,
            maximum temperature, and a readable error detail.
        """
        data = np.fromfile(
            raw_path,
            dtype="<f4",
        )

        width, height, dimension_error = self._resolve_temperature_dimensions(
            data_size=data.size,
            original_jpg_path=original_jpg_path,
            sdk_output=sdk_output,
        )

        if dimension_error:
            return False, None, None, dimension_error

        temperature_grid = data.reshape(
            height,
            width,
        )

        minimum_temperature = float(np.min(temperature_grid))

        maximum_temperature = float(np.max(temperature_grid))

        description = (
            f"Ambient Temp used in DJI measurement: {ambient_temp} C"
        )

        tifffile.imwrite(
            tiff_path,
            temperature_grid.astype(np.float32),
            description=description,
            compression="zlib",
        )

        return (
            True,
            minimum_temperature,
            maximum_temperature,
            "",
        )

    def _process_single_image(
        self,
        image_path,
        raw_folder,
        output_folder,
        params,
        ambient_temp,
    ):
        """
        Convert one thermal image and return its conversion result.

        Returns:
            A tuple containing the source name, success state, error detail,
            temperature range, source path, and output TIFF path.
        """
        base_name = os.path.splitext(os.path.basename(image_path))[0]

        raw_path = os.path.join(
            raw_folder,
            base_name + ".raw",
        )

        tiff_path = os.path.join(
            output_folder,
            base_name + ".tiff",
        )

        result = self._run_sdk_on_single_image(
            image_path,
            raw_path,
            params,
        )

        sdk_output = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if part and part.strip()
        )

        if result.returncode != 0 or not os.path.exists(raw_path):
            detail = self._format_sdk_failure(
                result=result,
                params=params,
            )

            return (
                base_name,
                False,
                detail,
                None,
                None,
                image_path,
                tiff_path,
            )

        (
            success,
            minimum_temperature,
            maximum_temperature,
            detail,
        ) = self._raw_to_tiff(
            raw_path,
            image_path,
            tiff_path,
            ambient_temp,
            sdk_output,
        )

        return (
            base_name,
            success,
            detail,
            minimum_temperature,
            maximum_temperature,
            image_path,
            tiff_path,
        )

    def _copy_metadata_batch(
        self,
        conversion_records,
        measurement_params,
    ):
        """
        Copy source metadata and conversion parameters using one ExifTool process.

        Keeping ExifTool open for the complete batch avoids creating a new
        process for every converted TIFF file.
        """
        if not conversion_records:
            return False

        command_lines = []

        for index, record in enumerate(conversion_records, start=1):
            source_path = record["source_path"]
            tiff_path = record["tiff_path"]

            user_comment = {
                "elements": None,
                "pseudo_color": 0,
                "measurement_params": {
                    "distance": measurement_params["distance"],
                    "humidity": measurement_params["humidity"],
                    "emissivity": measurement_params["emissivity"],
                    "reflection": measurement_params["reflection"],
                    "ambient_temp": measurement_params["ambient_temp"],
                },
                "temperature_range": {
                    "high": record["maximum_temperature"],
                    "low": record["minimum_temperature"],
                },
            }

            user_comment_text = json.dumps(
                user_comment,
                separators=(",", ":"),
                ensure_ascii=True,
            )

            command_lines.extend(
                [
                    "-q",
                    "-q",
                    "-overwrite_original",
                    "-tagsFromFile",
                    source_path,
                    "-all:all",
                    f"-UserComment={user_comment_text}",
                    tiff_path,
                    f"-execute{index}",
                ]
            )

        command_lines.extend(
            [
                "-stay_open",
                "False",
            ]
        )

        command_input = "\n".join(command_lines) + "\n"

        try:
            process = subprocess.Popen(
                [
                    EXIFTOOL_EXE,
                    "-stay_open",
                    "True",
                    "-@",
                    "-",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=STARTUPINFO,
            )

            _, stderr = process.communicate(input=command_input)

            if process.returncode not in (0, None):
                return False

            if stderr and "error" in stderr.lower():
                return False

            return True

        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            return False

    @staticmethod
    def _format_failure_summary(failed_files):
        """Group identical errors so batch logs stay readable."""
        grouped_failures = {}

        for item in failed_files:
            if isinstance(item, tuple) and len(item) == 2:
                file_name, detail = item
            else:
                legacy_text = str(item)

                if ": " in legacy_text:
                    file_name, detail = legacy_text.split(": ", 1)
                else:
                    file_name = legacy_text
                    detail = "Conversion failed."

            grouped_failures.setdefault(str(detail), []).append(
                str(file_name)
            )

        lines = []

        for detail, file_names in grouped_failures.items():
            reason_label = (
                "Reason:"
                if len(file_names) == 1
                else f"Reason ({len(file_names)} files):"
            )

            lines.extend(
                [
                    reason_label,
                    detail,
                    f"Affected files ({len(file_names)}):",
                ]
            )
            lines.extend(
                f"- {file_name}"
                for file_name in sorted(file_names, key=str.lower)
            )
            lines.append("")

        if lines:
            lines.pop()

        return "\n".join(lines)

    @staticmethod
    def _build_conversion_report(
        converted_count,
        failed_files,
        metadata_ok=None,
        output_folder=None,
    ):
        """Build a consistent user-facing conversion result message."""
        failed_count = len(failed_files)

        if converted_count == 0:
            title = "ERROR: Conversion failed for all files."
        elif failed_count > 0 or metadata_ok is False:
            title = "Warning: Conversion completed with warnings."
        else:
            title = "Success! Conversion completed."

        lines = [
            title,
            f"Converted: {converted_count}",
            f"Failed: {failed_count}",
        ]

        if metadata_ok is True:
            lines.append(
                f"Metadata copied: {converted_count}"
            )
        elif metadata_ok is False:
            lines.append(
                "Metadata copied: not confirmed"
            )

        if output_folder:
            lines.extend(
                [
                    "",
                    f"Output folder: {output_folder}",
                ]
            )

        if failed_files:
            lines.extend(
                [
                    "",
                    ThermalProcessor._format_failure_summary(failed_files),
                ]
            )

        if metadata_ok is False:
            lines.extend(
                [
                    "",
                    (
                        "Warning: Some TIFF files may not contain "
                        "the original GPS or EXIF metadata."
                    ),
                ]
            )

        return "\n".join(lines)

    def execute_conversion(
        self,
        folder_path,
        distance,
        emissivity,
        reflected_temp,
        ambient_temp,
        humidity,
        progress_callback=None,
        output_folder=None,
        raw_folder=None,
        include_output_path=True,
    ):
        """
        Convert all supported thermal images from the selected folder.

        Images are processed concurrently. The method returns a tuple
        containing the overall success state and a user-facing message.
        """
        dependency_error = self.check_dependencies()

        if dependency_error:
            return False, dependency_error

        try:
            distance_value = self._parse_numeric_value(distance)
            emissivity_value = self._parse_numeric_value(emissivity)
            reflected_value = self._parse_numeric_value(
                reflected_temp,
                "°C",
            )
            ambient_value = self._parse_numeric_value(
                ambient_temp,
                "°C",
            )
            humidity_value = self._parse_numeric_value(
                humidity,
                "%",
            )
        except (TypeError, ValueError):
            return False, "Please enter valid numbers for all parameters."

        if not (
            PARAM_RANGES["distance"][0] <= distance_value <= PARAM_RANGES["distance"][1]
        ):
            return False, (
                f"Distance must be between {PARAM_RANGES['distance'][0]} and "
                f"{PARAM_RANGES['distance'][1]} meters (DJI Thermal SDK limit)."
            )
        if not (
            PARAM_RANGES["emissivity"][0]
            <= emissivity_value
            <= PARAM_RANGES["emissivity"][1]
        ):
            return (
                False,
                f"Emissivity must be between {PARAM_RANGES['emissivity'][0]} and {PARAM_RANGES['emissivity'][1]}.",
            )
        if not (
            PARAM_RANGES["reflected_temp"][0]
            <= reflected_value
            <= PARAM_RANGES["reflected_temp"][1]
        ):
            return (
                False,
                f"Reflected Temp must be between {PARAM_RANGES['reflected_temp'][0]} and {PARAM_RANGES['reflected_temp'][1]} °C.",
            )
        if not (
            PARAM_RANGES["ambient_temp"][0]
            <= ambient_value
            <= PARAM_RANGES["ambient_temp"][1]
        ):
            return (
                False,
                f"Ambient Temp must be between {PARAM_RANGES['ambient_temp'][0]} and {PARAM_RANGES['ambient_temp'][1]} °C.",
            )
        if not (
            PARAM_RANGES["humidity"][0] <= humidity_value <= PARAM_RANGES["humidity"][1]
        ):
            return (
                False,
                f"Humidity must be between {PARAM_RANGES['humidity'][0]} and {PARAM_RANGES['humidity'][1]}%.",
            )

        folder_path = os.path.abspath(os.path.normpath(folder_path))

        if output_folder is None:
            output_folder = os.path.join(folder_path, "converted_tiff")

        if raw_folder is None:
            raw_folder = os.path.join(folder_path, "_raw_temp")

        output_folder = os.path.abspath(os.path.normpath(output_folder))
        raw_folder = os.path.abspath(os.path.normpath(raw_folder))

        if not os.path.isdir(folder_path):
            return False, f"Input folder does not exist: {folder_path}"

        os.makedirs(output_folder, exist_ok=True)
        os.makedirs(raw_folder, exist_ok=True)

        params = {
            "distance": distance_value,
            "emissivity": emissivity_value,
            "reflected_temp": reflected_value,
            "ambient_temp": ambient_value,
            "humidity": humidity_value,
        }

        image_files = self.find_images(folder_path)
        if not image_files:
            return False, "No JPG files found in the selected folder."

        total = len(image_files)
        done = 0
        converted_count = 0
        failed_files = []
        conversion_records = []

        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [
                    executor.submit(
                        self._process_single_image,
                        path,
                        raw_folder,
                        output_folder,
                        params,
                        ambient_value,
                    )
                    for path in image_files
                ]

                for future in as_completed(futures):
                    (
                        base_name,
                        success,
                        error_detail,
                        minimum_temperature,
                        maximum_temperature,
                        source_path,
                        tiff_path,
                    ) = future.result()

                    done += 1

                    if success:
                        converted_count += 1

                        conversion_records.append(
                            {
                                "source_path": source_path,
                                "tiff_path": tiff_path,
                                "minimum_temperature": minimum_temperature,
                                "maximum_temperature": maximum_temperature,
                            }
                        )
                    else:
                        failed_files.append(
                            (
                                os.path.basename(source_path),
                                error_detail,
                            )
                        )

                    if progress_callback:
                        progress_callback(done, total)
        finally:
            shutil.rmtree(raw_folder, ignore_errors=True)

        if converted_count == 0:
            message = self._build_conversion_report(
                converted_count=0,
                failed_files=failed_files,
            )

            return False, message

        measurement_params = {
            "distance": distance_value,
            "humidity": humidity_value,
            "emissivity": emissivity_value,
            "reflection": reflected_value,
            "ambient_temp": ambient_value,
        }

        metadata_ok = self._copy_metadata_batch(
            conversion_records=conversion_records,
            measurement_params=measurement_params,
        )

        message = self._build_conversion_report(
            converted_count=converted_count,
            failed_files=failed_files,
            metadata_ok=metadata_ok,
            output_folder=(
                output_folder
                if include_output_path
                else None
            ),
        )

        return True, message