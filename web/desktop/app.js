/* Bridge the desktop converter interface to Python through Eel. */

let selectedFolderPath = "";
let lastOutputFolder = "";

const selectFolderButton = document.getElementById("selectFolderBtn");
const convertButton = document.getElementById("convertBtn");

selectFolderButton.addEventListener("click", async () => {
  try {
    const result = await eel.select_folder()();

    if (result && result.success === false) {
      logMessage(`ERROR: ${result.message}`);
      return;
    }

    if (!result || !result.folder) {
      return;
    }

    selectedFolderPath = result.folder;
    lastOutputFolder = "";
    document.getElementById("openFolderBtn").style.display = "none";
    document.getElementById("folderLabel").textContent = result.folder;
    document.getElementById("imageCount").textContent = `Convertible: ${result.count}`;

    logMessage(`${result.count} image(s) available for conversion.`);

    for (const key of ["r", "t", "v", "z", "other"]) {
      document.getElementById(`${key}Count`).textContent = result.counts[key];
      document.getElementById(`${key}CountRow`).style.display =
        result.counts[key] > 0 ? "inline" : "none";
    }

    document.getElementById("imageTypeSummary").style.visibility = "visible";

    const skippedCount = result.counts.v + result.counts.z;
    if (result.count === 0 && skippedCount > 0) {
      logMessage(
        "ERROR: No supported conversion candidates were found. " +
        "Visible images (_V) and zoom images (_Z) are not converted."
      );
    }
  } catch (error) {
    logMessage(`ERROR: Failed to select folder: ${error}`);
  }
});

convertButton.addEventListener("click", async () => {
  if (!selectedFolderPath) {
    logMessage("ERROR: Please select an image folder first.");
    return;
  }

  if (!validateParams()) {
    return;
  }

  lastOutputFolder = `${selectedFolderPath}\\converted_tiff`;
  document.getElementById("openFolderBtn").style.display = "none";

  const params = {
    folder_path: selectedFolderPath,
    ...getConversionParams(),
  };

  setConversionRunning(true);
  updateProgress(0, 0, 0);
  logMessage("Starting conversion process...");

  try {
    const result = await eel.start_conversion(params)();
    if (result && result.success === false) {
      setConversionRunning(false);
      logMessage(`ERROR: ${result.message}`);
    }
  } catch (error) {
    logMessage(`ERROR: Thread execution failed: ${error}`);
    setConversionRunning(false);
  }
});

eel.expose(updateDesktopProgress);
function updateDesktopProgress(done, total) {
  updateProgress(done, total);
}

eel.expose(conversionFinished);
function conversionFinished(success, message) {
  logMessage(message);
  setConversionRunning(false);

  if (success) {
    document.getElementById("openFolderBtn").style.display = "inline-block";
  }
}

document.getElementById("clearLogBtn").addEventListener("click", () => {
  document.getElementById("log").innerHTML = "";
});

document.getElementById("openFolderBtn").addEventListener("click", async (event) => {
  event.preventDefault();
  const result = await eel.open_output_folder(lastOutputFolder)();

  if (result && result.success === false) {
    logMessage(`ERROR: ${result.message}`);
  }
});

logMessage("Ready. Select a folder to begin.");
