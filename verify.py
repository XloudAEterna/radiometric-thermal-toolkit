"""Inspect a converted radiometric TIFF file: prints min/max temperature and shows it as an image."""

import os
import sys

import tifffile
import matplotlib.pyplot as plt


def ask_for_folder():
    """Ask the user to enter the path to their converted_tiff folder."""
    folder = input("Enter the path to your converted_tiff folder: ").strip().strip('"')
    return folder


def list_tiff_files(folder):
    """Return a sorted list of .tiff files found in the given folder."""
    files = [f for f in os.listdir(folder) if f.lower().endswith((".tiff", ".tif"))]
    return sorted(files)


def choose_file(files):
    """Print a numbered list of files and ask the user to pick one."""
    print("\nAvailable TIFF files:\n")
    for i, name in enumerate(files, start=1):
        print(f"  [{i}] {name}")

    choice = input(f"\nSelect a file (1-{len(files)}): ")

    index = int(choice) - 1
    return files[index]


def inspect_tiff(path):
    """Load a TIFF file and print basic statistics about its pixel values."""
    arr = tifffile.imread(path)

    print("\nFile:", path)
    print("Shape (height, width):", arr.shape)
    print("Data type:", arr.dtype)
    print("Min temperature:", round(arr.min(), 2), "°C")
    print("Max temperature:", round(arr.max(), 2), "°C")
    print("Mean temperature:", round(arr.mean(), 2), "°C")

    return arr


def show_tiff(arr, title=""):
    """Display the temperature array as a color image."""
    plt.imshow(arr, cmap="inferno")
    plt.colorbar(label="Temperature (°C)")
    plt.title(title)
    plt.show()


if __name__ == "__main__":
    tiff_folder = ask_for_folder()

    if not os.path.exists(tiff_folder):
        print(f"Folder not found: {tiff_folder}")
        sys.exit(1)

    tiff_files = list_tiff_files(tiff_folder)

    if not tiff_files:
        print("No TIFF files found in this folder.")
        sys.exit(1)

    selected_file = choose_file(tiff_files)
    full_path = os.path.join(tiff_folder, selected_file)

    data = inspect_tiff(full_path)
    show_tiff(data, title=selected_file)