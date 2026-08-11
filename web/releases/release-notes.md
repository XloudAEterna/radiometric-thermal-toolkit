# Radiometric Toolkit v1.0.0

## Release Overview

Radiometric Toolkit is a Windows desktop application for processing DJI radiometric JPEG images and exporting temperature data as single-band Float32 TIFF files.

## Features

- Batch processing of supported DJI radiometric JPEG images
- Single-band Float32 TIFF output
- Configurable distance
- Configurable emissivity
- Configurable reflected temperature
- Configurable ambient temperature
- Configurable humidity
- Automatic thermal image classification
- Conversion progress tracking
- Detailed execution log
- Local folder selection
- Direct access to generated output files
- Windows desktop interface

## Processing

Radiometric Toolkit uses the DJI Thermal SDK to extract radiometric temperature information from supported thermal images.

The conversion workflow is:

1. Select a folder containing supported thermal images.
2. Configure the radiometric parameters.
3. Start the conversion.
4. Monitor processing progress and execution logs.
5. Access the generated Float32 TIFF files.

## Version

**1.0.0**