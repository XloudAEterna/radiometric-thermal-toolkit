"""Tests for DJI thermal matrix dimension handling."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

from app.core.processor import ThermalProcessor


class ProcessorDimensionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.processor = ThermalProcessor()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_source_jpeg(self, width: int, height: int) -> Path:
        source_path = self.root / "source.jpg"
        Image.new("RGB", (width, height)).save(source_path)
        return source_path

    def _write_raw(self, width: int, height: int) -> Path:
        raw_path = self.root / "temperature.raw"
        data = np.arange(width * height, dtype="<f4")
        data.tofile(raw_path)
        return raw_path

    def test_parses_dimensions_from_sdk_output(self) -> None:
        dimensions = self.processor._parse_sdk_dimensions(
            "image width : 640\nimage height = 512"
        )

        self.assertEqual(dimensions, (640, 512))

    def test_normalizes_windows_unsigned_exit_code(self) -> None:
        self.assertEqual(
            self.processor._normalize_exit_code(4294967289),
            -7,
        )

    def test_raw_to_tiff_uses_sdk_dimensions_not_preview_dimensions(self) -> None:
        source_path = self._write_source_jpeg(1280, 1024)
        raw_path = self._write_raw(640, 512)
        tiff_path = self.root / "result.tiff"

        success, minimum, maximum, detail = self.processor._raw_to_tiff(
            raw_path=str(raw_path),
            original_jpg_path=str(source_path),
            tiff_path=str(tiff_path),
            ambient_temp=25.0,
            sdk_output="width : 640\nheight : 512",
        )

        self.assertTrue(success)
        self.assertEqual(detail, "")
        self.assertEqual(minimum, 0.0)
        self.assertEqual(maximum, float((640 * 512) - 1))
        self.assertEqual(tifffile.imread(tiff_path).shape, (512, 640))

    def test_raw_to_tiff_falls_back_to_known_matrix_size(self) -> None:
        source_path = self._write_source_jpeg(1920, 1080)
        raw_path = self._write_raw(640, 512)
        tiff_path = self.root / "result.tiff"

        success, _, _, detail = self.processor._raw_to_tiff(
            raw_path=str(raw_path),
            original_jpg_path=str(source_path),
            tiff_path=str(tiff_path),
            ambient_temp=25.0,
            sdk_output="",
        )

        self.assertTrue(success)
        self.assertEqual(detail, "")
        self.assertEqual(tifffile.imread(tiff_path).shape, (512, 640))

    def test_reports_sdk_and_raw_dimension_mismatch(self) -> None:
        source_path = self._write_source_jpeg(1280, 1024)
        raw_path = self._write_raw(640, 512)
        tiff_path = self.root / "result.tiff"

        success, _, _, detail = self.processor._raw_to_tiff(
            raw_path=str(raw_path),
            original_jpg_path=str(source_path),
            tiff_path=str(tiff_path),
            ambient_temp=25.0,
            sdk_output="width : 1280\nheight : 1024",
        )

        self.assertFalse(success)
        self.assertIn("DJI SDK reported 1280 x 1024", detail)
        self.assertIn("327680 Float32 pixels", detail)
        self.assertFalse(tiff_path.exists())


if __name__ == "__main__":
    unittest.main()
