function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

let telemetryRefreshTimer = null;
let currentTelemetrySource = "all";

function telemetryUrl() {
  const params = new URLSearchParams({ limit: "50" });
  if (currentTelemetrySource !== "all") {
    params.set("data_source", currentTelemetrySource);
  }
  return `/api/telemetry?${params.toString()}`;
}

function rowMatchesStationFilter(row) {
  const stationId = new URLSearchParams(window.location.search).get("station_id");
  if (!stationId) {
    return true;
  }
  return String(row.station_id) === stationId;
}

function setTelemetryStatus(message) {
  const status = document.getElementById("telemetry-status");
  if (status) {
    status.textContent = message;
  }
}

function renderTelemetryRows(rows) {
  const body = document.getElementById("telemetry-rows");
  if (!body) {
    return;
  }

  const stationFilteredRows = rows.filter(rowMatchesStationFilter);
  if (!stationFilteredRows.length) {
    body.innerHTML = '<tr><td colspan="6">No telemetry matches the current source or station filter.</td></tr>';
    return;
  }

  body.innerHTML = stationFilteredRows
    .map((row) => `
      <tr>
        <td>${escapeHtml(row.station_name)}</td>
        <td>${escapeHtml(row.data_source)}</td>
        <td>${escapeHtml(row.water_level_m)} m</td>
        <td>${escapeHtml(row.danger_level_m)} m</td>
        <td>${escapeHtml(row.signal)}</td>
        <td>${escapeHtml(new Date(row.timestamp).toLocaleString())}</td>
      </tr>
    `)
    .join("");
}

async function loadTelemetry() {
  const body = document.getElementById("telemetry-rows");
  try {
    setTelemetryStatus("Refreshing telemetry evidence...");
    const response = await fetch(telemetryUrl(), { credentials: "same-origin" });
    if (response.status === 401) {
      window.location.href = "/login?next=/data";
      return;
    }
    if (!response.ok) {
      throw new Error(`Telemetry request failed with ${response.status}`);
    }
    const rows = await response.json();
    renderTelemetryRows(rows);
    setTelemetryStatus(`Updated ${new Date().toLocaleTimeString()} - ${rows.length} row(s) from ${currentTelemetrySource === "all" ? "all sources" : currentTelemetrySource}`);
  } catch (error) {
    console.error(error);
    if (body) {
      body.innerHTML = '<tr><td colspan="6">Unable to load telemetry right now.</td></tr>';
    }
    setTelemetryStatus("Telemetry refresh failed. Check the FastAPI server.");
  }
}

function startTelemetryAutoRefresh() {
  if (telemetryRefreshTimer) {
    clearInterval(telemetryRefreshTimer);
  }
  telemetryRefreshTimer = setInterval(loadTelemetry, 15000);
}

function setCsvStatus(message, isError = false) {
  const node = document.getElementById("csv-upload-status");
  if (!node) return;
  node.textContent = message;
  node.className = isError ? "error-box" : "notice-box";
}

async function uploadTelemetryCsv(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const fileInput = document.getElementById("telemetry-csv-file");
  if (!fileInput?.files?.length) {
    setCsvStatus("Choose a CSV file before uploading.", true);
    return;
  }
  const formData = new FormData(form);
  try {
    setCsvStatus("Uploading and validating CSV rows...");
    const response = await fetch("/api/telemetry/upload-csv", {
      method: "POST",
      credentials: "same-origin",
      body: formData,
    });
    if (response.status === 401 || response.status === 403) {
      setCsvStatus("Operator role required to upload telemetry CSV files.", true);
      return;
    }
    const result = await response.json();
    if (!response.ok) {
      setCsvStatus(result.detail || "CSV upload was rejected.", true);
      return;
    }
    const errorPreview = result.errors?.length ? ` Rejected rows: ${result.errors.join("; ")}` : "";
    setCsvStatus(`CSV upload complete. Accepted ${result.accepted}; rejected ${result.rejected}.${errorPreview}`);
    form.reset();
    await loadTelemetry();
  } catch (error) {
    console.error(error);
    setCsvStatus("CSV upload failed. Check the FastAPI server and file format.", true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const sourceFilter = document.getElementById("telemetry-source-filter");
  sourceFilter?.addEventListener("change", (event) => {
    currentTelemetrySource = event.target.value;
    loadTelemetry();
  });

  document.getElementById("telemetry-refresh")?.addEventListener("click", loadTelemetry);
  document.getElementById("telemetry-csv-form")?.addEventListener("submit", uploadTelemetryCsv);
  loadTelemetry();
  startTelemetryAutoRefresh();
});
