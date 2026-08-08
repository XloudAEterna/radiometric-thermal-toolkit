/* Shared UI helpers for desktop and server modes. */

const PARAM_RANGES = {
  distance: { min: 1, max: 25, label: "Distance" },
  emissivity: { min: 0.1, max: 1, label: "Emissivity" },
  reflected: { min: -40, max: 500, label: "Reflected Temp" },
  ambient: { min: -40, max: 80, label: "Ambient Temp" },
  humidity: { min: 20, max: 100, label: "Humidity" },
};


function logMessage(message) {
  const log = document.getElementById("log");

  if (!log) {
    return;
  }

  const timestamp = new Date().toLocaleTimeString([], { hour12: false });

  const lines = String(message)
    .split("\n")
    .filter((lineText) => lineText.trim().length > 0);

  let failedSection = false;

  lines.forEach((lineText, index) => {
    const line = document.createElement("div");

    line.textContent = index === 0 ? `[${timestamp}] ${lineText}` : `    ${lineText}`;
    const normalizedLine = lineText.trim().toUpperCase();

    if (normalizedLine.startsWith("FAILED:")) {
      failedSection = true;
    } else if (normalizedLine.startsWith("GPS/METADATA")) {
      failedSection = false;
    }

    if (normalizedLine.startsWith("ERROR:") || failedSection) {
      line.classList.add("log-line-error");
    } else if (normalizedLine.startsWith("SUCCESS!")) {
      line.classList.add("log-line-success");
    } else if (normalizedLine.startsWith("WARNING:")) {
      line.classList.add("log-line-warning");
    }

    log.appendChild(line);
  });

  log.scrollTop = log.scrollHeight;
}

function validateParams() {
  for (const [fieldId, range] of Object.entries(PARAM_RANGES)) {
    const input = document.getElementById(fieldId);
    const value = Number.parseFloat(input.value);

    if (
      Number.isNaN(value)
      || value < range.min
      || value > range.max
    ) {
      input.classList.add("is-invalid");

      logMessage(
        `ERROR: ${range.label} must be between `
        + `${range.min} and ${range.max}.`
      );

      return false;
    }

    input.classList.remove("is-invalid");
  }

  return true;
}


function getConversionParams() {
  return {
    distance: document.getElementById("distance").value,
    emissivity: document.getElementById("emissivity").value,
    reflected_temp: document.getElementById("reflected").value,
    ambient_temp: document.getElementById("ambient").value,
    humidity: document.getElementById("humidity").value,
  };
}


function setConversionRunning(isRunning) {
  const convertButton = document.getElementById("convertBtn");

  if (convertButton) {
    convertButton.disabled = isRunning;
  }
}


function updateProgress(done, total, percentage = null) {
  const progressWrap = document.getElementById("progressWrap");
  const progressFill = document.getElementById("progressFill");
  const progressText = document.getElementById("progressText");

  const resolvedPercentage = percentage
    ?? (total > 0 ? Math.round((done / total) * 100) : 0);

  if (progressWrap) {
    progressWrap.style.visibility = "visible";
  }

  if (progressFill) {
    progressFill.style.width = `${resolvedPercentage}%`;
  }

  if (progressText) {
    progressText.textContent = `${done} / ${total}`;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderInlineMarkdown(text) {
  // Only handles **bold** — the one inline style actually used in release notes.
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

/**
 * Minimal Markdown -> HTML renderer, scoped to exactly what release notes
 * use: #/##/### headings, "- " bullet lists, **bold** text, and plain
 * paragraphs. Not a general-purpose Markdown parser — kept intentionally
 * small since the content is authored in-house, not user-submitted.
 */
function renderReleaseNotesMarkdown(markdown) {
  const lines = markdown.split("\n");
  const htmlParts = [];
  let listOpen = false;

  const closeList = () => {
    if (listOpen) {
      htmlParts.push("</ul>");
      listOpen = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      closeList();
      continue;
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.*)$/);
    if (headingMatch) {
      closeList();
      const level = headingMatch[1].length + 3; // maps # ## ### to h4 h5 h6
      htmlParts.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    const listMatch = line.match(/^[-*]\s+(.*)$/);
    if (listMatch) {
      if (!listOpen) {
        htmlParts.push("<ul>");
        listOpen = true;
      }
      htmlParts.push(`<li>${renderInlineMarkdown(listMatch[1])}</li>`);
      continue;
    }

    closeList();
    htmlParts.push(`<p>${renderInlineMarkdown(line)}</p>`);
  }

  closeList();
  return htmlParts.join("");
}

async function loadReleaseNotes() {
  const content =
    document.getElementById("releaseNotesContent");

  const baseUrl =
    document.body.dataset.releaseNotesBaseUrl;

  try {
    const response = await fetch(
      `${baseUrl}/release-notes.md`,
      {
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    content.innerHTML = renderReleaseNotesMarkdown(await response.text());
  } catch (error) {
    content.textContent =
      "Release notes could not be loaded.";
  }
}


function initializeReleaseNotes() {
  const modalElement =
    document.getElementById("releaseNotesModal");

  const button =
    document.getElementById("releaseNotesButton");

  if (!modalElement || !button) {
    return;
  }

  const modal =
    bootstrap.Modal.getOrCreateInstance(modalElement);

  button.addEventListener("click", async () => {
    await loadReleaseNotes();
    modal.show();
  });
}

document.addEventListener(
  "DOMContentLoaded",
  initializeReleaseNotes
);

async function loadSupportedFiles() {
  const content =
    document.getElementById("supportedFilesContent");

  if (!content || content.dataset.loaded === "true") {
    return;
  }

  const url =
    document.body.dataset.supportedFilesUrl;

  if (!url) {
    content.textContent =
      "Supported file information is not configured.";

    return;
  }

  try {
    const response = await fetch(
      url,
      {
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    content.innerHTML = await response.text();
    content.dataset.loaded = "true";
  } catch (error) {
    console.error(
      "Supported file information could not be loaded:",
      error
    );

    content.textContent =
      "Supported file information could not be loaded.";
  }
}


function initializeSupportedFiles() {
  const modal =
    document.getElementById("supportedFilesModal");

  if (!modal) {
    return;
  }

  modal.addEventListener(
    "show.bs.modal",
    loadSupportedFiles
  );
}


document.addEventListener(
  "DOMContentLoaded",
  initializeSupportedFiles
);