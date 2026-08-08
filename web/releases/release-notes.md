# Portfolio Edition

## Desktop Application

- Radiometric Toolkit is packaged as a Windows-only desktop application.
- The existing Eel + pywebview desktop workflow is preserved.
- The portfolio interface keeps the dark thermal-analysis visual system with teal-to-heat accents.
- Organization-specific branding, account login, Docker deployment, and server upload workflows are not included.

## Conversion Workflow

- Batch classification of R, T, V, and Z images is preserved.
- Supported radiometric images are converted to single-band Float32 TIFF output.
- Metadata transfer and conversion progress reporting are preserved.
- Converted files are written to the local `converted_tiff` folder next to the selected source images.
