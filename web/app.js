/* Bridges UI events to the Python API via Eel and handles progress/result updates. */

function logMessage(message) {
  const log = document.getElementById("log");
  if (log) {
    const line = document.createElement("div");
    line.textContent = message;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
  }
}

// Load default parameter values from config.py when the page opens
window.addEventListener("DOMContentLoaded", async () => {
  try {
    const defaults = await eel.get_default_params()();
    document.getElementById("distance").value = defaults.distance;
    document.getElementById("emissivity").value = defaults.emissivity;
    document.getElementById("reflected").value = defaults.reflected_temp;
    document.getElementById("ambient").value = defaults.ambient_temp;
    document.getElementById("humidity").value = defaults.humidity;
  } catch (error) {
    logMessage("Warning: could not load default parameters, using fallback values.");
  }
});

// Global variable to keep track of the selected folder path
let selectedFolderPath = "";

document.getElementById("selectFolderBtn").addEventListener("click", async () => {
  try {
    // Call the exposed Python function to trigger native directory selection
    const result = await eel.select_folder()();
    if (result && result.folder) {
      selectedFolderPath = result.folder;
      document.getElementById("folderLabel").textContent = result.folder;
      document.getElementById("imageCount").textContent = `Images Found: ${result.count}`;
    }
  } catch (error) {
    logMessage("ERROR: Failed to select folder: " + error);
  }
});

document.getElementById("convertBtn").addEventListener("click", async () => {
  if (!selectedFolderPath) {
    logMessage("ERROR: Please select an image folder first!");
    return;
  }

  // Fetch metrics dynamically from index.html input fields
  const params = {
    folder_path: selectedFolderPath,
    distance: document.getElementById("distance").value,
    emissivity: document.getElementById("emissivity").value,
    reflected_temp: document.getElementById("reflected").value,
    ambient_temp: document.getElementById("ambient").value,
    humidity: document.getElementById("humidity").value,
  };

  // Reset and show progress UI elements safely
  document.getElementById("convertBtn").disabled = true;
  
  const progressWrap = document.getElementById("progressWrap");
  if (progressWrap) {
    progressWrap.style.display = "block";
  }
  
  document.getElementById("progressFill").style.width = "0%";
  document.getElementById("progressText").textContent = "0 / 0";
  logMessage("Starting conversion process...");

  try {
    // Trigger the background multi-threaded conversion in Python
    await eel.start_conversion(params)();
  } catch (error) {
    logMessage("ERROR: Thread execution failed: " + error);
    document.getElementById("convertBtn").disabled = false;
  }
});

// Exposed JavaScript functions that Python can call directly using eel.js
eel.expose(updateProgress);
function updateProgress(done, total) {
  const percent = Math.round((done / total) * 100);
  const progressFill = document.getElementById("progressFill");
  const progressText = document.getElementById("progressText");
  
  if (progressFill) progressFill.style.width = percent + "%";
  if (progressText) progressText.textContent = `${done} / ${total}`;
}

eel.expose(conversionFinished);
function conversionFinished(success, message) {
  logMessage(message);
  document.getElementById("convertBtn").disabled = false;
}