"""Tests for conversion result reporting."""

import unittest

from app.core.processor import ThermalProcessor


class ProcessorReportingTests(unittest.TestCase):

    def test_successful_conversion_report(self) -> None:
        message = ThermalProcessor._build_conversion_report(
            converted_count=5,
            failed_files=[],
            metadata_ok=True,
            output_folder=r"C:\images\converted_tiff",
        )

        self.assertIn(
            "Success! Conversion completed.",
            message,
        )
        self.assertIn("Converted: 5", message)
        self.assertIn("Failed: 0", message)
        self.assertIn("Metadata copied: 5", message)
        self.assertIn(
            r"Output folder: C:\images\converted_tiff",
            message,
        )

    def test_partial_conversion_report(self) -> None:
        message = ThermalProcessor._build_conversion_report(
            converted_count=4,
            failed_files=[
                "DJI_0005.JPG: Invalid radiometric data.",
            ],
            metadata_ok=True,
        )

        self.assertIn(
            "Warning: Conversion completed with warnings.",
            message,
        )
        self.assertIn("Converted: 4", message)
        self.assertIn("Failed: 1", message)
        self.assertIn("Reason:", message)
        self.assertIn("Invalid radiometric data.", message)
        self.assertIn("Affected files (1):", message)
        self.assertIn("- DJI_0005.JPG", message)
        self.assertNotIn("Output folder:", message)

    def test_failed_conversion_report(self) -> None:
        message = ThermalProcessor._build_conversion_report(
            converted_count=0,
            failed_files=[
                "DJI_0001.JPG: Unsupported image.",
                "DJI_0002.JPG: Invalid thermal data.",
            ],
        )

        self.assertIn(
            "ERROR: Conversion failed for all files.",
            message,
        )
        self.assertIn("Converted: 0", message)
        self.assertIn("Failed: 2", message)
        self.assertNotIn("Metadata copied:", message)


if __name__ == "__main__":
    unittest.main()