let map = null;
let activeBaseLayer = null;
let stationLayer = null;
let riskRingLayer = null;
let labelLayer = null;
let contextLayer = null;
let latestStations = [];
let currentSource = "hybrid";
let currentRiskFilter = "all";
let currentSearchTerm = "";
let selectedStationId = null;
let latestStationKey = "";
let hasAutoFitted = false;
let refreshInProgress = false;
let tileErrorSeen = false;
let latestAlerts = [];
let activeChannelFilter = "all";
let showAllStations = false;
let lastRefreshTimestamp = Date.now();
let previousWaterLevels = new Map();
let unreadAlertCount = 0;

const floodwatchContext = window.FLOODWATCH_CONTEXT || { canOperate: false, role: "guest" };
const DEFAULT_MAP_VIEW = [9.08, 8.68];
const DEFAULT_MAP_ZOOM = 6;

const rank = { Low: 1, Moderate: 2, High: 3, Severe: 4 };

const riskMeta = {
  Low: { cssClass: "risk-low", shortLabel: "L" },
  Moderate: { cssClass: "risk-moderate", shortLabel: "M" },
  High: { cssClass: "risk-high", shortLabel: "H" },
  Severe: { cssClass: "risk-severe", shortLabel: "S" },
};

const baseLayerLabels = {
  osm: "OpenStreetMap",
  satellite: "Satellite",
};

const channelLabels = {
  web: "Web dashboard",
  email: "Simulated email",
  sms: "Simulated SMS",
  Dashboard: "Web dashboard",
  Email: "Simulated email",
  SMS: "Simulated SMS",
};

const baseLayers = {
  osm: null,
  satellite: null,
};

const markersByStationId = new Map();

const riverCorridors = [
  {
    name: "Niger River corridor",
    path: [
      [12.45, 4.2],
      [11.1, 4.95],
      [9.6, 5.75],
      [7.8, 6.73],
      [6.15, 6.78],
    ],
    labelAt: [9.5, 5.7],
  },
  {
    name: "Benue River corridor",
    path: [
      [7.35, 13.6],
      [7.73, 8.53],
      [7.8, 6.73],
    ],
    labelAt: [7.55, 10.05],
  },
  {
    name: "Lake Chad basin context",
    path: [
      [13.2, 13.3],
      [12.5, 13.45],
      [11.83, 13.15],
    ],
    labelAt: [12.45, 13.35],
  },
  {
    name: "Lagos coastal drainage context",
    path: [
      [6.65, 2.75],
      [6.52, 3.38],
      [6.43, 4.05],
    ],
    labelAt: [6.58, 3.36],
  },
];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeColor(value) {
  const color = String(value || "");
  return /^#[0-9a-fA-F]{6}$/.test(color) ? color : "#009c88";
}

function asNumber(value, fallback = 0) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function formatNumber(value, fractionDigits = 2) {
  const number = asNumber(value, null);
  return number === null ? "unavailable" : number.toFixed(fractionDigits);
}

function formatProbability(value) {
  if (value === null || value === undefined) {
    return "unavailable";
  }

  const number = asNumber(value, null);
  if (number === null) {
    return "unavailable";
  }

  return `${Math.round(number * 100)}%`;
}

function parseTelemetryTimestamp(value) {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function dataAgeMinutes(value) {
  const parsed = parseTelemetryTimestamp(value);
  if (!parsed) {
    return null;
  }

  return (Date.now() - parsed.getTime()) / 60000;
}

function formatDataAge(value) {
  const minutes = dataAgeMinutes(value);
  if (minutes === null) {
    return "timestamp unavailable";
  }

  if (minutes < -5) {
    return "timestamp ahead of this device clock";
  }

  const safeMinutes = Math.max(minutes, 0);
  if (safeMinutes < 1) {
    return "less than 1 minute old";
  }

  if (safeMinutes < 60) {
    return `${Math.round(safeMinutes)} minute(s) old`;
  }

  if (safeMinutes < 1440) {
    return `${Math.round(safeMinutes / 60)} hour(s) old`;
  }

  return `${Math.round(safeMinutes / 1440)} day(s) old`;
}

function greetingForHour(hour) {
  /* The dashboard greeting follows the user's device clock, because the browser
     is what reflects the person's actual system time during a live demo. */
  if (hour >= 5 && hour < 12) {
    return "morning";
  }

  if (hour >= 12 && hour < 17) {
    return "afternoon";
  }

  if (hour >= 17 && hour < 21) {
    return "evening";
  }

  return "night";
}

function updateTimeAwareGreeting(now = new Date()) {
  const greeting = document.getElementById("time-aware-greeting");
  if (!greeting) {
    return;
  }

  greeting.textContent = greetingForHour(now.getHours());
}

function freshnessMeta(timestamp, signal = "online") {
  const normalizedSignal = String(signal || "").toLowerCase();
  const minutes = dataAgeMinutes(timestamp);

  if (normalizedSignal && normalizedSignal !== "online") {
    return {
      state: "stale",
      label: "signal check",
      message: "This station is not reporting an online signal. Verify the sensor link before relying on the latest reading.",
    };
  }

  if (minutes === null) {
    return {
      state: "stale",
      label: "time unknown",
      message: "The reading timestamp is unavailable, so responders should verify this station before using it for decisions.",
    };
  }

  if (minutes < -5) {
    return {
      state: "watch",
      label: "clock check",
      message: "The reading timestamp is ahead of this device clock. Verify the station clock during hardware testing.",
    };
  }

  if (minutes <= 20) {
    return {
      state: "live",
      label: "fresh",
      message: "This reading is recent enough for the live dashboard view.",
    };
  }

  if (minutes <= 120) {
    return {
      state: "watch",
      label: "watch age",
      message: "This reading is older than the live window. Keep monitoring and confirm with the next sensor update.",
    };
  }

  return {
    state: "stale",
    label: "stale",
    message: "This reading is old. Use it as historical context and verify current conditions before decision support.",
  };
}

function sourceLabel(source) {
  if (source === "hardware") {
    return "hardware";
  }

  if (source === "simulated") {
    return "simulated";
  }

  return "hybrid";
}

function sourceModeMeta(source) {
  if (source === "hardware") {
    return {
      title: "Hardware telemetry mode",
      description: "Shows readings posted by physical sensor hardware only. If this layer is empty or smaller than the simulated layer, it means no hardware node has sent recent data for those stations yet.",
    };
  }

  if (source === "simulated") {
    return {
      title: "Simulation telemetry mode",
      description: "Shows reproducible simulator-generated readings only. Use this mode when demonstrating the system without physical sensors connected.",
    };
  }

  return {
    title: "Hybrid telemetry mode",
    description: "Compares simulated and hardware readings for the same station and displays the more serious current risk. Use it when both simulator and hardware data exist.",
  };
}

function updateSourceModePanel(visibleCount = 0, elevatedCount = 0) {
  const meta = sourceModeMeta(currentSource);
  setText("source-mode-title", meta.title);
  setText("source-mode-description", meta.description);
  setText("source-mode-count", String(visibleCount));
  setText("source-mode-elevated", String(elevatedCount));
}

function riskClass(riskLevel) {
  return (riskMeta[riskLevel] || riskMeta.Low).cssClass;
}

function riskShortLabel(riskLevel) {
  return (riskMeta[riskLevel] || riskMeta.Low).shortLabel;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) {
    node.textContent = value;
  }
}

function setMapHealth(message, state = "ok") {
  const node = document.getElementById("map-health");
  if (!node) {
    return;
  }

  node.textContent = message;
  node.classList.toggle("is-warning", state === "warning");
  node.classList.toggle("is-ok", state !== "warning");
}

function sortStations(stations) {
  return [...stations].sort((left, right) => {
    const riskDifference = (rank[right.risk_level] || 0) - (rank[left.risk_level] || 0);
    if (riskDifference !== 0) {
      return riskDifference;
    }
    return String(left.station_name).localeCompare(String(right.station_name));
  });
}

function filterStations(stations) {
  const search = currentSearchTerm.trim().toLowerCase();

  return stations.filter((station) => {
    const matchesRisk = currentRiskFilter === "all" || (currentRiskFilter === "high-severe" && ["High", "Severe"].includes(station.risk_level)) || station.risk_level === currentRiskFilter;
    const searchableText = [
      station.station_id,
      station.station_name,
      station.data_source,
      station.risk_level,
      station.signal,
      freshnessMeta(station.timestamp, station.signal).label,
    ]
      .join(" ")
      .toLowerCase();
    const matchesSearch = !search || searchableText.includes(search);
    return matchesRisk && matchesSearch;
  });
}

function formatElapsedSince(timestamp) {
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

function updateElapsedRefreshLabel() {
  setText("updated-at", formatElapsedSince(lastRefreshTimestamp));
}

function filtersAreActive(totalCount, visibleCount) {
  return currentRiskFilter !== "all" || currentSearchTerm.trim() !== "" || totalCount !== visibleCount;
}

async function getJson(url) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (response.status === 401) {
    window.location.href = "/login?next=/dashboard";
    return null;
  }
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return response.json();
}

function renderForecast(forecast) {
  const summary = document.getElementById("forecast-summary");
  const hours = document.getElementById("forecast-hours");
  if (!summary || !hours) {
    return;
  }

  if (!forecast?.available) {
    summary.textContent = forecast?.message || "Weather forecast is temporarily unavailable. Flood-risk telemetry remains active.";
    hours.innerHTML = "";
    return;
  }

  const wettestHour = Math.max(...forecast.next_hours.map((hour) => hour.rainfall_mm));
  summary.textContent = `${forecast.current.condition}, ${forecast.current.temperature_c ?? "-"} C now. Peak rainfall in the next six hours: ${wettestHour.toFixed(1)} mm.`;
  hours.innerHTML = forecast.next_hours.map((hour) => {
    const time = new Date(hour.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return `<div class="forecast-hour"><strong>${escapeHtml(time)}</strong><span>${Number(hour.precipitation_probability)}% rain</span><b>${Number(hour.rainfall_mm).toFixed(1)} mm</b></div>`;
  }).join("");
}

async function refreshForecast() {
  try {
    renderForecast(await getJson("/api/weather-forecast"));
  } catch (error) {
    console.warn("Weather forecast unavailable", error);
    renderForecast({ available: false });
  }
}

function showToast(message) {
  const container = document.getElementById("command-toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = "command-toast";
  toast.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2dd4bf" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

function formatSignedMetres(value, decimals = 2) {
  const number = asNumber(value, 0);
  const sign = number > 0 ? "+" : "";
  return `${sign}${number.toFixed(decimals)} m`;
}

function modelAvailabilitySummary(allStations, visibleStations) {
  const source = visibleStations.length ? visibleStations : allStations;
  const available = source.filter((station) => station.model_available).length;
  const total = source.length;
  const percentage = total ? Math.round((available / total) * 100) : 0;
  return { available, total, percentage, ready: available > 0 };
}

function estimateLeadTimeLabel(station) {
  const currentLevel = asNumber(station.water_level_m, 0);
  const dangerLevel = asNumber(station.danger_level_m, 0);
  const rateOfRise = asNumber(station.rate_of_rise_m, 0);

  if (!dangerLevel) {
    return { value: "N/A", sub: "danger level unavailable" };
  }

  if (currentLevel >= dangerLevel) {
    return { value: "At threshold", sub: "current reading is at or above danger level" };
  }

  if (rateOfRise <= 0) {
    return { value: "Not rising", sub: "based on previous reading" };
  }

  const readingsToDanger = Math.ceil((dangerLevel - currentLevel) / rateOfRise);
  return { value: `${readingsToDanger} reading(s)`, sub: "if current rise continues" };
}

function summarize(allStations, visibleStations) {
  const highest = visibleStations.reduce((best, item) => (!best || rank[item.risk_level] > rank[best.risk_level] ? item : best), null);
  const activeWarnings = visibleStations.filter((station) => station.risk_level === "High" || station.risk_level === "Severe").length;
  const activeWatches = visibleStations.filter((station) => station.risk_level === "Moderate").length;
  const elevatedTotal = visibleStations.filter((station) => station.risk_level !== "Low").length;
  const totalCount = allStations.length;
  const visibleCount = visibleStations.length;
  const countLabel = totalCount && visibleCount !== totalCount ? `${visibleCount} / ${totalCount}` : String(visibleCount);
  const pctVisible = totalCount ? Math.round((visibleCount / totalCount) * 100) : 0;
  const modelSummary = modelAvailabilitySummary(allStations, visibleStations);

  setText("station-count", countLabel);
  setText("side-station-count", String(totalCount));
  setText("alert-count", activeWarnings);
  setText("side-alert-count", String(activeWarnings));
  setText("highest-risk", highest ? highest.risk_level : "-");
  setText("model-status", modelSummary.ready ? "Ready" : "Standby");
  setText("model-kpi-sub", modelSummary.ready ? `ML signal available on ${modelSummary.available}/${modelSummary.total} visible station(s)` : "Threshold-only fallback active");
  setText("model-confidence-percent", modelSummary.ready ? `${modelSummary.available}/${modelSummary.total}` : "Unavailable");
  setText("model-card-status-text", modelSummary.ready ? "Future-horizon model available" : "Waiting for trained model signal");

  const kpiBar = document.getElementById("kpi-stations-bar");
  if (kpiBar) kpiBar.style.width = `${pctVisible}%`;
  setText("kpi-stations-sub", totalCount ? `${visibleCount} of ${totalCount} current reading(s) visible` : "Waiting for telemetry");

  const modelKpiBar = document.getElementById("model-kpi-bar");
  if (modelKpiBar) modelKpiBar.style.width = `${modelSummary.percentage}%`;
  const modelProgress = document.getElementById("model-progress-bar");
  if (modelProgress) modelProgress.setAttribute("aria-valuenow", String(modelSummary.percentage));
  const modelProgressFill = document.getElementById("model-progress-fill");
  if (modelProgressFill) modelProgressFill.style.width = `${modelSummary.percentage}%`;

  const warningTag = document.getElementById("kpi-warning-tag");
  if (warningTag) warningTag.style.display = activeWarnings > 0 ? "inline-block" : "none";
  setText("kpi-watches-sub", activeWatches ? `${activeWatches} moderate reading(s)` : "No moderate readings yet");

  setText("kpi-people-count", String(elevatedTotal));
  setText("kpi-people-sub", elevatedTotal ? `${elevatedTotal} station(s) at Moderate, High, or Severe risk` : "No elevated readings yet");
  updateSourceModePanel(visibleCount, elevatedTotal);

  setText("quick-stations-count", visibleCount);
  const measuredRain = visibleStations
    .map((station) => asNumber(station.rainfall_mm_hr, null))
    .filter((value) => value !== null);
  const avgRain = measuredRain.length
    ? `${(measuredRain.reduce((acc, value) => acc + value, 0) / measuredRain.length).toFixed(1)} mm`
    : "unavailable";
  setText("quick-avg-rain", avgRain);
  const risingCount = visibleStations.filter((s) => asNumber(s.rate_of_rise_m, 0) > 0.05).length;
  setText("quick-rising-count", risingCount);

  setText("tab-warning-count", activeWarnings);
}

function channelSummary(station) {
  const channels = station.alert_channels || {};
  const channelEntries = Object.entries(channels);
  if (!channelEntries.length) {
    return "No simulated alert channel listed";
  }
  return channelEntries.map(([name, status]) => `${escapeHtml(name)}: ${escapeHtml(status)}`).join(" / ");
}

function updateMapSummary(allStations, visibleStations) {
  if (!allStations.length) {
    setText("map-summary", `No ${sourceLabel(currentSource)} station readings are available yet. The map is waiting for simulator or hardware telemetry.`);
    return;
  }

  if (!visibleStations.length) {
    setText("map-summary", `No station matches the current search/filter. ${allStations.length} station(s) are available in ${sourceLabel(currentSource)} mode.`);
    return;
  }

  const sortedStations = sortStations(visibleStations);
  const highest = sortedStations[0];
  const elevatedCount = visibleStations.filter((station) => station.risk_level !== "Low").length;
  const filterNote = filtersAreActive(allStations.length, visibleStations.length)
    ? `${visibleStations.length} of ${allStations.length} station(s) shown after filtering.`
    : `${visibleStations.length} station(s) displayed.`;

  setText(
    "map-summary",
    `${filterNote} Source mode: ${sourceLabel(currentSource)}. Highest visible risk: ${highest.risk_level} at ${highest.station_name}. ${elevatedCount} visible station(s) are Moderate, High, or Severe. Risk rings are planning cues only, not official flood extents.`
  );
}

function renderStationList(visibleStations, totalCount) {
  const list = document.getElementById("station-list");
  if (!list) {
    return;
  }

  if (!totalCount) {
    list.innerHTML = `
      <li>
        <h3>No station data yet</h3>
        <p>Start the simulator or connect a hardware node to populate the live dashboard.</p>
      </li>
    `;
    return;
  }

  if (!visibleStations.length) {
    list.innerHTML = `
      <li class="empty-filter">
        <h3>No station matches the current filter</h3>
        <p>Clear the search or risk filter to show the available station readings again.</p>
        <div class="station-actions">
          <button class="station-focus" type="button" data-clear-map-filters="true">Clear filters</button>
        </div>
      </li>
    `;
    return;
  }

  list.innerHTML = sortStations(visibleStations)
    .map((station) => {
      const color = safeColor(station.color);
      const riskCssClass = riskClass(station.risk_level);
      const stationId = escapeHtml(station.station_id);
      const stationName = escapeHtml(station.station_name);
      const riskLevel = escapeHtml(station.risk_level);
      const dataSource = escapeHtml(station.data_source);
      const freshness = freshnessMeta(station.timestamp, station.signal);

      return `
        <li data-station-id="${stationId}" style="border-left-color: ${color}">
          <h3>${stationName}</h3>
          <div class="station-meta" aria-label="Station risk and source">
            <span class="risk-pill ${riskCssClass}" style="background: ${color}">${riskLevel} risk</span>
            <span class="source-pill">${dataSource} source</span>
            <span class="freshness-pill freshness-${freshness.state}">${escapeHtml(freshness.label)}</span>
          </div>
          <p>Water ${escapeHtml(formatNumber(station.water_level_m, 2))} m / danger ${escapeHtml(formatNumber(station.danger_level_m, 2))} m</p>
          <p>Rainfall ${escapeHtml(formatNumber(station.rainfall_mm_hr, 2))} mm/hr - flow ${escapeHtml(formatNumber(station.flow_rate_m3s, 2))} m3/s</p>
          <p>Battery ${escapeHtml(formatNumber(station.battery_pct, 1))}% - signal ${escapeHtml(station.signal)}</p>
          <p>Reading age: ${escapeHtml(formatDataAge(station.timestamp))}. ${escapeHtml(freshness.message)}</p>
          <p>${escapeHtml(station.message)}</p>
          <p>Channels: ${channelSummary(station)}</p>
          <div class="station-actions">
            <button class="station-focus" type="button" data-focus-station="${stationId}" aria-label="Focus ${stationName} on the map">
              Focus on map
            </button>
          </div>
        </li>
      `;
    })
    .join("");
}

function renderStationTable(visibleStations) {
  const tbody = document.getElementById("station-table-body");
  if (!tbody) return;

  if (!visibleStations.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #648292; padding: 28px;">No stations match the selected filter.</td></tr>`;
    return;
  }

  const sortedStations = sortStations(visibleStations);
  const stationsToRender = showAllStations ? sortedStations : sortedStations.slice(0, 10);
  tbody.innerHTML = stationsToRender.map((station) => {
    const isSelected = String(station.station_id) === String(selectedStationId);
    const color = safeColor(station.color);
    const risk = station.risk_level || "Low";
    const dotClass = risk === "Severe" ? "dot-severe" : risk === "High" ? "dot-high" : risk === "Moderate" ? "dot-moderate" : "dot-low";
    const badgeClass = risk === "Severe" ? "badge-emergency" : risk === "High" ? "badge-warning" : risk === "Moderate" ? "badge-watch" : "badge-normal";
    const badgeLabel = risk;
    const ratioPct = Math.min(100, Math.round((asNumber(station.water_level_m) / asNumber(station.danger_level_m, 1)) * 100));

    const previousLevel = previousWaterLevels.get(station.station_id);
    const currentLevel = asNumber(station.water_level_m);
    const changeClass = previousLevel !== undefined && previousLevel !== currentLevel ? "value-changed" : "";
    const changeDirection = previousLevel === undefined || previousLevel === currentLevel ? "" : currentLevel > previousLevel ? " rising" : " falling";
    return `
      <tr class="${isSelected ? 'selected-row' : ''}" data-table-station-id="${escapeHtml(station.station_id)}">
        <td>
          <div class="table-station-cell">
            <span class="status-dot-cell ${dotClass}"></span>
            <div>
              <div class="station-name-bold">${escapeHtml(station.station_name)}</div>
              <div class="station-code-muted">${escapeHtml(station.station_id)}</div>
            </div>
          </div>
        </td>
        <td>
          <div class="water-level-bar-wrap">
            <span class="level-val-bold ${changeClass}">${escapeHtml(formatNumber(station.water_level_m, 2))} m${changeDirection}</span>
            <div class="mini-level-bar">
              <div class="mini-level-fill" style="width: ${ratioPct}%; background: ${color};"></div>
            </div>
          </div>
        </td>
        <td>
          <span>${escapeHtml(formatNumber(station.rainfall_mm_hr, 1))} mm</span>
        </td>
        <td>
          <span class="status-pill-badge ${badgeClass}">● ${badgeLabel}</span>
        </td>
        <td>
          <span class="last-reading-cell">${escapeHtml(formatDataAge(station.timestamp))}</span>
        </td>
        <td>
          <button class="btn-icon-circle" style="width: 26px; height: 26px; border: none;" type="button" aria-label="Station actions">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle>
            </svg>
          </button>
        </td>
      </tr>
    `;
  }).join("");

  tbody.querySelectorAll("tr[data-table-station-id]").forEach((row) => {
    row.addEventListener("click", () => {
      const stationId = row.getAttribute("data-table-station-id");
      selectStation(stationId);
      focusStationOnMap(stationId);
    });
  });

  const toggle = document.getElementById("station-table-toggle");
  if (toggle) {
    toggle.hidden = sortedStations.length <= 10;
    toggle.textContent = showAllStations ? "Show less" : `Show all ${sortedStations.length} stations`;
    toggle.setAttribute("aria-expanded", String(showAllStations));
  }
}

function alertChannels(alert) {
  const channels = Object.keys(alert.channels || { web: true, email: true, sms: true });
  return channels.length ? channels : ["web"];
}

function channelDisplayName(channel) {
  return channelLabels[channel] || channel;
}

function channelButtonMarkup(channels) {
  return channels.map((channel) => `<button class="channel-filter-tag${activeChannelFilter === channel ? " active" : ""}" type="button" data-channel-filter="${escapeHtml(channel)}">${escapeHtml(channelDisplayName(channel))}</button>`).join("");
}

function notificationRiskClass(riskLevel) {
  return String(riskLevel || "update").toLowerCase().replace(/[^a-z0-9-]/g, "-");
}

function updateNotificationPanel() {
  const list = document.getElementById("notification-list");
  const badge = document.getElementById("top-alert-badge");
  if (!list) return;

  list.innerHTML = latestAlerts.slice(0, 5).map((alert) => {
    const channels = alertChannels(alert).map(channelDisplayName).join(" · ");
    const riskClass = notificationRiskClass(alert.risk_level);
    const alertTime = alert.updated_at || alert.created_at || alert.timestamp;

    return `
      <li class="notification-item notification-risk-${escapeHtml(riskClass)}">
        <div class="notification-item-top">
          <strong>${escapeHtml(alert.station_name || "Station alert")}</strong>
          <span>${escapeHtml(alert.risk_level || "Warning")}</span>
        </div>
        <p>${escapeHtml(alert.message || "A station status update was logged for review.")}</p>
        <small>${escapeHtml(formatDataAge(alertTime))} · ${escapeHtml(channels || "Web dashboard")}</small>
      </li>
    `;
  }).join("") || '<li class="notification-empty">No recent alert logs yet.</li>';

  unreadAlertCount = Math.max(0, latestAlerts.length - Number(sessionStorage.getItem("floodwatch-read-alerts") || 0));
  if (badge) {
    badge.textContent = String(unreadAlertCount);
    badge.hidden = unreadAlertCount === 0;
  }
}

function alertWorkflowButtons(alert) {
  if (!floodwatchContext.canOperate || !alert.id) {
    return "";
  }
  const actions = [];
  if (alert.status === "new") actions.push(["acknowledge", "Acknowledge"]);
  if (["new", "acknowledged"].includes(alert.status)) actions.push(["escalate", "Escalate"]);
  if (alert.status !== "resolved") actions.push(["resolve", "Resolve"]);
  actions.push(["audit", "View history"]);
  return `
    <div class="alert-workflow-actions" aria-label="Operator alert workflow actions">
      ${actions.map(([action, label]) => `<button type="button" data-alert-action="${action}" data-alert-id="${escapeHtml(alert.id)}">${label}</button>`).join("")}
    </div>
  `;
}

async function changeAlertWorkflow(alertId, action) {
  if (action === "audit") {
    let panel = document.getElementById("alert-audit-panel");
    if (!panel) {
      panel = document.createElement("section");
      panel.id = "alert-audit-panel";
      panel.className = "alert-audit-panel";
      panel.tabIndex = -1;
      panel.setAttribute("aria-label", "Alert workflow history");
      document.getElementById("alert-queue")?.after(panel);
    }
    panel.textContent = "Loading alert history...";
    panel.focus();
    try {
      const response = await fetch(`/api/alerts/${encodeURIComponent(alertId)}/audit`, { credentials: "same-origin" });
      if (!response.ok) throw new Error("History unavailable");
      const entries = await response.json();
      panel.innerHTML = `<h3>Alert history</h3>${entries.length ? "<ol>" + entries.map((entry) => `<li>${escapeHtml(entry.action)}: ${escapeHtml(entry.from_status)} to ${escapeHtml(entry.to_status)}. ${escapeHtml(entry.notes || "No note")} <small>${escapeHtml(entry.operator_email)}</small></li>`).join("") + "</ol>" : "<p>No operator actions recorded yet.</p>"}`;
    } catch { panel.textContent = "Alert history is unavailable. An operator session is required."; }
    return;
  }
  const notes = window.prompt(`Operator note for ${action}:`, "");
  if (notes === null) return;
  try {
    const response = await fetch(`/api/alerts/${encodeURIComponent(alertId)}/${encodeURIComponent(action)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ notes }),
    });
    if (response.status === 401 || response.status === 403) {
      showToast("Operator role required for alert workflow changes.");
      return;
    }
    if (!response.ok) {
      showToast("Alert workflow update was rejected.");
      return;
    }
    showToast(`Alert ${action} recorded with audit log.`);
    await renderAlertQueue(latestStations);
  } catch (error) {
    console.error("Alert workflow error", error);
    showToast("Alert workflow update failed.");
  }
}

async function renderAlertQueue(visibleStations) {
  const queue = document.getElementById("alert-queue");
  if (!queue) {
    return;
  }
  const channelReset = document.getElementById("all-channel-filter");
  if (channelReset) channelReset.hidden = activeChannelFilter === "all";

  try {
    const alerts = await getJson("/api/alerts");
    if (alerts && alerts.length) {
      latestAlerts = alerts;
      updateNotificationPanel();
      latestAlerts = alerts;
      const filteredAlerts = activeChannelFilter === "all"
        ? alerts
        : alerts.filter((alert) => alertChannels(alert).includes(activeChannelFilter));
      queue.innerHTML = filteredAlerts.slice(0, 5).map((alert) => {
        const risk = alert.risk_level || "Warning";
        const iconBg = (risk === "Severe" || risk === "High") ? "#fee2e2" : "#fef3c7";
        const iconColor = (risk === "Severe" || risk === "High") ? "#dc2626" : "#d97706";
        const timeAgo = formatDataAge(alert.updated_at || alert.created_at || alert.timestamp);
        const channels = alertChannels(alert);
        const statusLabel = alert.status || "new";

        return `
          <li class="alert-feed-item">
            <div class="alert-icon-box" style="background: ${iconBg}; color: ${iconColor};">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
              </svg>
            </div>
            <div class="alert-item-body">
              <div class="alert-item-header">
                <strong class="alert-station-name">${escapeHtml(alert.station_name)}</strong>
                <span class="alert-timestamp">${escapeHtml(statusLabel)} · ${escapeHtml(timeAgo)}</span>
              </div>
              <p class="alert-message-text">${escapeHtml(alert.message)}</p>
              ${alert.operator_notes ? `<p class="alert-message-text"><strong>Operator note:</strong> ${escapeHtml(alert.operator_notes)}</p>` : ""}
              <div class="alert-channel-tags">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                ${channelButtonMarkup(channels)}
              </div>
              ${alertWorkflowButtons(alert)}
            </div>
          </li>
        `;
      }).join("");
      return;
    }
  } catch (e) {
    console.warn("Could not fetch remote alert queue", e);
  }

  const elevatedStations = sortStations(visibleStations.filter((station) => station.risk_level !== "Low")).slice(0, 4);
  if (!elevatedStations.length) {
    queue.innerHTML = `
      <li class="alert-feed-item">
        <div class="alert-icon-box" style="background: #e0f2fe; color: #0284c7;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
        </div>
        <div class="alert-item-body">
          <strong class="alert-station-name">No elevated station readings</strong>
          <p class="alert-message-text">No Moderate, High, or Severe flood-risk readings are currently reported on visible monitored corridors.</p>
          <div class="alert-channel-tags"><span>System standby</span></div>
        </div>
      </li>
    `;
    return;
  }

  queue.innerHTML = elevatedStations
    .map((station) => {
      const color = safeColor(station.color);
      const channels = ["web", "email", "sms"];
      if (activeChannelFilter !== "all" && !channels.includes(activeChannelFilter)) return "";
      return `
        <li class="alert-feed-item" style="border-left: 3px solid ${color};">
          <div class="alert-icon-box" style="background: #fee2e2; color: #dc2626;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            </svg>
          </div>
          <div class="alert-item-body">
            <div class="alert-item-header">
              <strong class="alert-station-name">${escapeHtml(station.station_name)}</strong>
              <span class="alert-timestamp">${escapeHtml(formatDataAge(station.timestamp))}</span>
            </div>
            <p class="alert-message-text">${escapeHtml(station.message)}</p>
            <div class="alert-channel-tags">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
              ${channelButtonMarkup(channels)}
            </div>
          </div>
        </li>
      `;
    })
    .join("");
}

function estimateRiskRingRadius(station) {
  const baseRadiusByRisk = {
    Low: 7000,
    Moderate: 14000,
    High: 28000,
    Severe: 44000,
  };

  const baseRadius = baseRadiusByRisk[station.risk_level] || baseRadiusByRisk.Low;
  const rainfallBonus = Math.min(Math.max(asNumber(station.rainfall_mm_hr), 0) * 250, 10000);
  const ratioBonus = Math.min(Math.max(asNumber(station.risk_ratio), 0) * 5000, 8000);
  return baseRadius + rainfallBonus + ratioBonus;
}

function popupContent(station) {
  const channels = channelSummary(station);
  const freshness = freshnessMeta(station.timestamp, station.signal);
  return `
    <strong>${escapeHtml(station.station_name)}</strong><br>
    <span>${escapeHtml(station.risk_level)} risk - ${escapeHtml(station.data_source)} source</span><br>
    Water: ${escapeHtml(formatNumber(station.water_level_m, 2))} m / configured threshold ${escapeHtml(formatNumber(station.danger_level_m, 2))} m<br>\n    Threshold type: ${escapeHtml(station.threshold_type || "unknown")}<br>
    Rainfall: ${escapeHtml(formatNumber(station.rainfall_mm_hr, 2))} mm/hr<br>
    Flow: ${escapeHtml(formatNumber(station.flow_rate_m3s, 2))} m3/s<br>
    Model probability: ${escapeHtml(formatProbability(station.ml_probability))}<br>
    Signal: ${escapeHtml(station.signal)} - battery ${escapeHtml(formatNumber(station.battery_pct, 1))}%<br>
    Reading age: ${escapeHtml(formatDataAge(station.timestamp))} - ${escapeHtml(freshness.label)}<br>
    Channels: ${channels}<br>
    <em>${escapeHtml(station.message)}</em>
  `;
}

function shortStationName(station) {
  const rawName = String(station.station_name || station.station_id || "Station");
  return rawName.replace(/\s*\([^)]*\)\s*/g, "").trim().slice(0, 28) || "Station";
}

function validLatLng(station) {
  const lat = asNumber(station.lat, null);
  const lon = asNumber(station.lon, null);
  return lat !== null && lon !== null && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}

function toggleMapEmpty(visibleStations) {
  const emptyPanel = document.getElementById("map-empty");
  if (emptyPanel) {
    emptyPanel.hidden = visibleStations.length > 0;
  }
}

function markFocusedStation(stationId) {
  document.querySelectorAll("#station-list [data-station-id]").forEach((item) => {
    item.classList.toggle("is-focused", item.getAttribute("data-station-id") === stationId);
  });
}

function findStationById(stations, stationId) {
  return stations.find((station) => String(station.station_id) === String(stationId));
}

function ensureSelectedStation(visibleStations) {
  if (!visibleStations.length) {
    selectedStationId = null;
    return;
  }

  if (!findStationById(visibleStations, selectedStationId)) {
    selectedStationId = sortStations(visibleStations)[0].station_id;
  }
}

function renderSelectedStationPanel(visibleStations, totalCount) {
  const detail = document.getElementById("selected-station-content");

  if (!totalCount) {
    if (detail) {
      detail.innerHTML = `
        <p>No telemetry has been received yet. Start the simulator or connect a hardware node to populate station details.</p>
      `;
    }
    return;
  }

  if (!visibleStations.length) {
    if (detail) {
      detail.innerHTML = `
        <p>No selected station is visible because the current filters hide all stations. Clear the filters to review station details.</p>
      `;
    }
    return;
  }

  const station = findStationById(visibleStations, selectedStationId) || sortStations(visibleStations)[0];
  selectedStationId = station.station_id;

  const color = safeColor(station.color);
  const freshness = freshnessMeta(station.timestamp, station.signal);

  // 1. Situation Room Selected Station Card UI
  setText("selected-station-title", station.station_name);
  const regionMap = {
    "NG-LOK-01": "Kogi · Niger-Benue · River",
    "NG-MKD-02": "Benue · Benue River",
    "NG-MDG-03": "Borno · Lake Chad Basin",
    "NG-YEN-04": "Bayelsa · Niger Delta",
    "NG-LOS-05": "Lagos · Coastal Drainage",
    "NG-JBB-06": "Kwara · Upper Niger River",
    "NG-KNJ-07": "Niger · Kainji Basin",
    "NG-BAR-08": "Niger · Middle Niger Reach",
    "NG-ONT-09": "Anambra · Lower Niger Corridor",
    "NG-YAU-10": "Kebbi · Yauri Reach",
  };
  setText("selected-station-location", regionMap[station.station_id] || "Nigeria Monitored Reach");
  setText("selected-station-code", station.station_id);

  const bannerLevelMap = {
    Severe: "SEVERE LEVEL",
    High: "HIGH LEVEL",
    Moderate: "MODERATE LEVEL",
    Low: "LOW LEVEL",
  };
  setText("banner-level-tag", bannerLevelMap[station.risk_level] || "MONITORED");
  setText("banner-instruction", station.message || "Conditions within expected seasonal thresholds.");
  const probVal = station.model_available && station.ml_probability != null ? `${Math.round(station.ml_probability * 100)}%` : "N/A";
  setText("banner-prob-val", probVal);
  setText("banner-prob-sub", station.model_available ? "model probability" : "model unavailable");

  const banner = document.getElementById("station-risk-banner");
  if (banner) {
    if (station.risk_level === "Severe" || station.risk_level === "High") {
      banner.style.background = "#fef2f2";
      banner.style.borderColor = "#fee2e2";
    } else if (station.risk_level === "Moderate") {
      banner.style.background = "#fffbeb";
      banner.style.borderColor = "#fef3c7";
    } else {
      banner.style.background = "#ecfdf5";
      banner.style.borderColor = "#d1fae5";
    }
  }

  // Horizon Forecast Curve
  setText("curve-danger-val", `${formatNumber(station.danger_level_m, 1)} m`);
  const danger = asNumber(station.danger_level_m, 10.0);
  const currentLevel = asNumber(station.water_level_m, 5.0);
  const yStart = Math.max(20, Math.min(115, 115 - (currentLevel / danger) * 80));
  let yEnd;
  if (station.risk_level === "Severe") {
    yEnd = 20;
  } else if (station.risk_level === "High") {
    yEnd = 32;
  } else if (station.risk_level === "Moderate") {
    yEnd = 58;
  } else {
    yEnd = 95;
  }

  const fillPath = document.getElementById("horizon-fill-path");
  const strokePath = document.getElementById("horizon-stroke-path");
  const startDot = document.getElementById("horizon-start-point");
  const endDot = document.getElementById("horizon-end-point");

  const curveColor = (station.risk_level === "Severe" || station.risk_level === "High") ? "#ef4444" : (station.risk_level === "Moderate" ? "#f59e0b" : "#10b981");

  if (fillPath && strokePath) {
    const cpY = (yStart + yEnd) / 2 - 12;
    fillPath.setAttribute("d", `M 0 ${yStart} Q 400 ${cpY} 800 ${yEnd} L 800 130 L 0 130 Z`);
    strokePath.setAttribute("d", `M 0 ${yStart} Q 400 ${cpY} 800 ${yEnd}`);
    strokePath.setAttribute("stroke", curveColor);

    const grad = document.getElementById("horizonCurveGrad");
    if (grad && grad.children.length >= 2) {
      grad.children[0].setAttribute("stop-color", curveColor);
      grad.children[1].setAttribute("stop-color", curveColor);
    }
  }
  if (startDot) {
    startDot.setAttribute("cy", yStart);
    startDot.setAttribute("fill", curveColor);
  }
  if (endDot) {
    endDot.setAttribute("cy", yEnd);
    endDot.setAttribute("fill", curveColor);
  }

  // Station Metrics
  setText("selected-water-level", `${formatNumber(station.water_level_m, 2)} m`);
  const trendEl = document.getElementById("selected-water-trend");
  if (trendEl) {
    const rateOfRise = asNumber(station.rate_of_rise_m, 0);
    trendEl.textContent = Math.abs(rateOfRise) < 0.01
      ? "No measurable change since previous reading"
      : `${formatSignedMetres(rateOfRise)} since previous reading`;
    trendEl.classList.toggle("trend-rising", rateOfRise > 0.01);
  }
  setText("selected-rainfall-rate", `${formatNumber(station.rainfall_mm_hr, 1)} mm`);
  const measuredRainfall = asNumber(station.rainfall_mm_hr, null);
  const intensity = measuredRainfall === null
    ? "Not measured"
    : measuredRainfall > 25
      ? "High intensity"
      : measuredRainfall > 10
        ? "Moderate intensity"
        : "Low intensity";
  setText("selected-rainfall-intensity", intensity);

  const leadEstimate = estimateLeadTimeLabel(station);
  setText("selected-lead-time", leadEstimate.value);
  setText("selected-lead-time-sub", leadEstimate.sub);

  // 2. Legacy / test_api.py required structure
  if (detail) {
    detail.innerHTML = `
      <div class="station-detail" style="border-left: 5px solid ${color}; padding-left: 12px;">
        <h3>${escapeHtml(station.station_name)}</h3>
        <div class="station-meta" aria-label="Selected station risk, source, and freshness">
          <span class="risk-pill ${riskClass(station.risk_level)}" style="background: ${color}">${escapeHtml(station.risk_level)} risk</span>
          <span class="source-pill">${escapeHtml(station.data_source)} source</span>
          <span class="freshness-pill freshness-${freshness.state}">${escapeHtml(freshness.label)}</span>
        </div>
        <div class="station-detail-grid">
          <div><span>Water level</span><strong>${escapeHtml(formatNumber(station.water_level_m, 2))} m</strong></div>
          <div><span>Configured threshold</span><strong>${escapeHtml(formatNumber(station.danger_level_m, 2))} m</strong></div>\n          <div><span>Threshold type</span><strong>${escapeHtml(station.threshold_type || "unknown")}</strong></div>
          <div><span>Rainfall</span><strong>${escapeHtml(formatNumber(station.rainfall_mm_hr, 2))} mm/hr</strong></div>
          <div><span>Flow rate</span><strong>${escapeHtml(formatNumber(station.flow_rate_m3s, 2))} m3/s</strong></div>
          <div><span>ML probability</span><strong>${escapeHtml(formatProbability(station.ml_probability))}</strong></div>
          <div><span>Battery</span><strong>${escapeHtml(formatNumber(station.battery_pct, 1))}%</strong></div>
        </div>
        <p><strong>Signal:</strong> ${escapeHtml(station.signal)}.</p>
        <p><strong>Reading age:</strong> ${escapeHtml(formatDataAge(station.timestamp))}. ${escapeHtml(freshness.message)}</p>
        <p>${escapeHtml(station.message)}</p>
        <p><strong>Alert paths:</strong> ${channelSummary(station)}</p>
      </div>
    `;
  }
  markFocusedStation(String(station.station_id));
}

function selectStation(stationId) {
  selectedStationId = stationId;
  const visibleStations = filterStations(latestStations);
  renderSelectedStationPanel(visibleStations, latestStations.length);
  markFocusedStation(String(stationId));
}

function fitToStations() {
  const markers = [...markersByStationId.values()];
  if (!markers.length) {
    map.setView(DEFAULT_MAP_VIEW, DEFAULT_MAP_ZOOM);
    return;
  }

  const group = L.featureGroup(markers);
  map.fitBounds(group.getBounds().pad(0.22), { maxZoom: 9 });
}

function focusStationOnMap(stationId) {
  const marker = markersByStationId.get(stationId);
  if (!marker) {
    return;
  }

  selectStation(stationId);
  map.setView(marker.getLatLng(), Math.max(map.getZoom(), 9), { animate: true });
  marker.openPopup();
}

function renderMap(visibleStations) {
  if (!map || !stationLayer || !riskRingLayer || !labelLayer) {
    return;
  }

  stationLayer.clearLayers();
  riskRingLayer.clearLayers();
  labelLayer.clearLayers();
  markersByStationId.clear();
  toggleMapEmpty(visibleStations);

  const showRiskRings = document.getElementById("risk-zone-toggle")?.checked ?? true;
  const showStationLabels = document.getElementById("station-label-toggle")?.checked ?? true;

  sortStations(visibleStations).forEach((station) => {
    if (!validLatLng(station)) {
      return;
    }

    const latLng = [asNumber(station.lat), asNumber(station.lon)];
    const color = safeColor(station.color);
    const cssClass = riskClass(station.risk_level);
    const stationId = String(station.station_id);
    const freshness = freshnessMeta(station.timestamp, station.signal);

    if (showRiskRings) {
      L.circle(latLng, {
        radius: estimateRiskRingRadius(station),
        color,
        fillColor: color,
        fillOpacity: 0.08,
        opacity: 0.5,
        weight: 2,
        dashArray: "6 8",
        interactive: false,
      }).addTo(riskRingLayer);
    }

    const marker = L.marker(latLng, {
      keyboard: true,
      title: `${station.station_name} - ${station.risk_level} risk - ${freshness.label}`,
      icon: L.divIcon({
        className: "station-marker-icon",
        html: `<span class="station-marker ${cssClass} freshness-${freshness.state}" aria-hidden="true">${escapeHtml(riskShortLabel(station.risk_level))}</span>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
        popupAnchor: [0, -18],
      }),
    })
      .bindPopup(popupContent(station), { maxWidth: 320 })
      .on("click", () => selectStation(stationId))
      .addTo(stationLayer);

    markersByStationId.set(stationId, marker);

    if (showStationLabels) {
      L.marker(latLng, {
        interactive: false,
        icon: L.divIcon({
          className: "station-label-icon",
          html: `<span class="station-label-badge">${escapeHtml(shortStationName(station))}</span>`,
          iconSize: [160, 28],
          iconAnchor: [-20, 40],
        }),
      }).addTo(labelLayer);
    }
  });

  const stationKey = sortStations(visibleStations)
    .filter(validLatLng)
    .map((station) => `${station.station_id}:${station.lat}:${station.lon}`)
    .join("|");

  if (stationKey && (!hasAutoFitted || stationKey !== latestStationKey)) {
    fitToStations();
    hasAutoFitted = true;
    latestStationKey = stationKey;
  }
}

function renderContextLayer() {
  if (!map || !contextLayer) {
    return;
  }

  contextLayer.clearLayers();
  const showContext = document.getElementById("corridor-toggle")?.checked ?? true;
  if (!showContext) {
    return;
  }

  riverCorridors.forEach((corridor) => {
    L.polyline(corridor.path, {
      color: "#1976a2",
      opacity: 0.72,
      weight: 3,
      dashArray: "10 8",
    })
      .bindPopup(
        `<strong>${escapeHtml(corridor.name)}</strong><br>
         Schematic river/basin context for dashboard interpretation only. This is not an official flood boundary.`
      )
      .addTo(contextLayer);

    L.marker(corridor.labelAt, {
      interactive: false,
      icon: L.divIcon({
        className: "context-label-icon",
        html: `<span class="context-label-badge">${escapeHtml(corridor.name)}</span>`,
        iconSize: [190, 24],
        iconAnchor: [95, 12],
      }),
    }).addTo(contextLayer);
  });
}

function renderDashboardState() {
  const visibleStations = filterStations(latestStations);
  ensureSelectedStation(visibleStations);
  summarize(latestStations, visibleStations);
  updateMapSummary(latestStations, visibleStations);
  renderStationList(visibleStations, latestStations.length);
  renderStationTable(visibleStations);
  renderSelectedStationPanel(visibleStations, latestStations.length);
  renderAlertQueue(visibleStations);
  renderMap(visibleStations);
  visibleStations.forEach((station) => previousWaterLevels.set(station.station_id, asNumber(station.water_level_m)));
}

function setRefreshButtonLoading(loading) {
  const button = document.getElementById("refresh-data");
  const icon = button?.querySelector("svg");
  button?.classList.toggle("is-loading", loading);
  icon?.classList.toggle("spinning", loading);
  if (button) button.disabled = loading;
}

function clearMapFilters() {
  currentSearchTerm = "";
  currentRiskFilter = "all";

  const searchInput = document.getElementById("station-search");
  const tableSearch = document.getElementById("table-search-input");
  const riskFilter = document.getElementById("risk-filter");
  if (searchInput) searchInput.value = "";
  if (tableSearch) tableSearch.value = "";
  if (riskFilter) riskFilter.value = "all";

  document.querySelectorAll(".risk-pill-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-risk") === "all");
  });
  document.querySelectorAll(".table-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.getAttribute("data-tab") === "all");
  });

  hasAutoFitted = false;
  latestStationKey = "";
  renderDashboardState();
}

function setBaseLayer(layerName) {
  const requestedLayer = baseLayers[layerName] || baseLayers.osm;
  if (activeBaseLayer && map.hasLayer(activeBaseLayer)) {
    map.removeLayer(activeBaseLayer);
  }

  tileErrorSeen = false;
  activeBaseLayer = requestedLayer;
  activeBaseLayer.addTo(map);
  setMapHealth(`${baseLayerLabels[layerName] || "Map"} base layer selected. Station list remains available if tiles are slow to load.`);
}

function watchTileHealth(layer, label) {
  layer.on("tileerror", () => {
    tileErrorSeen = true;
    setMapHealth(`${label} tiles are slow or unavailable. Station markers and the text station list remain usable.`, "warning");
  });

  layer.on("load", () => {
    if (!tileErrorSeen) {
      setMapHealth(`${label} base layer ready. Station list remains available if tiles are slow to load.`);
    }
  });
}

async function refreshDashboard() {
  if (refreshInProgress) {
    return;
  }

  refreshInProgress = true;
  setRefreshButtonLoading(true);
  try {
    const stations = await getJson(`/api/risk-status?data_source=${encodeURIComponent(currentSource)}`);
    if (!stations) {
      return;
    }

    latestStations = stations;
    lastRefreshTimestamp = Date.now();
    renderDashboardState();
    showToast(`Data refreshed — ${stations.length} stations updated`);
  } catch (error) {
    console.error(error);
    setText("map-summary", "The dashboard could not load station data. Check that the FastAPI server is still running.");
    showToast("Could not refresh telemetry data.");
  } finally {
    refreshInProgress = false;
    setRefreshButtonLoading(false);
  }
}

document.addEventListener("DOMContentLoaded", function () {
  updateTimeAwareGreeting();
  setInterval(updateTimeAwareGreeting, 60 * 1000);

  map = L.map("map", {
    scrollWheelZoom: false,
    zoomControl: true,
  }).setView(DEFAULT_MAP_VIEW, DEFAULT_MAP_ZOOM);

  baseLayers.osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 18,
  });
  baseLayers.satellite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    attribution: "&copy; Esri",
    maxZoom: 18,
  });

  watchTileHealth(baseLayers.osm, "OpenStreetMap");
  watchTileHealth(baseLayers.satellite, "Satellite");

  setBaseLayer("osm");
  contextLayer = L.layerGroup().addTo(map);
  riskRingLayer = L.layerGroup().addTo(map);
  stationLayer = L.layerGroup().addTo(map);
  labelLayer = L.layerGroup().addTo(map);
  renderContextLayer();

  document.getElementById("source-select")?.addEventListener("change", (event) => {
    currentSource = event.target.value;
    hasAutoFitted = false;
    latestStationKey = "";
    updateSourceModePanel(0, 0);
    showToast(`${sourceModeMeta(currentSource).title} selected.`);
    refreshDashboard();
  });

  document.getElementById("layer-select")?.addEventListener("change", (event) => {
    setBaseLayer(event.target.value);
  });

  document.getElementById("station-search")?.addEventListener("input", (event) => {
    currentSearchTerm = event.target.value;
    const tableSearch = document.getElementById("table-search-input");
    if (tableSearch) tableSearch.value = event.target.value;
    hasAutoFitted = false;
    latestStationKey = "";
    renderDashboardState();
  });

  document.getElementById("table-search-input")?.addEventListener("input", (event) => {
    currentSearchTerm = event.target.value;
    const mapSearch = document.getElementById("station-search");
    if (mapSearch) mapSearch.value = event.target.value;
    hasAutoFitted = false;
    latestStationKey = "";
    renderDashboardState();
  });

  document.getElementById("risk-filter")?.addEventListener("change", (event) => {
    currentRiskFilter = event.target.value;
    hasAutoFitted = false;
    latestStationKey = "";
    renderDashboardState();
  });

  document.querySelectorAll(".risk-pill-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".risk-pill-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentRiskFilter = btn.getAttribute("data-risk") || "all";
      const rf = document.getElementById("risk-filter");
      if (rf) rf.value = currentRiskFilter;
      hasAutoFitted = false;
      latestStationKey = "";
      renderDashboardState();
    });
  });

  document.querySelectorAll(".table-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".table-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const filterVal = tab.getAttribute("data-tab");
      if (filterVal === "all" || filterVal === "Online") {
        currentRiskFilter = "all";
      } else if (filterVal === "High") {
        currentRiskFilter = "high-severe";
      } else {
        currentRiskFilter = filterVal;
      }
      const rf = document.getElementById("risk-filter");
      if (rf) rf.value = ["all", "Low", "Moderate", "High", "Severe"].includes(currentRiskFilter) ? currentRiskFilter : "all";
      hasAutoFitted = false;
      latestStationKey = "";
      renderDashboardState();
    });
  });

  document.getElementById("clear-map-filters")?.addEventListener("click", clearMapFilters);
  document.getElementById("fit-stations")?.addEventListener("click", fitToStations);
  document.getElementById("reset-map")?.addEventListener("click", () => {
    map.setView(DEFAULT_MAP_VIEW, DEFAULT_MAP_ZOOM);
  });

  document.getElementById("risk-zone-toggle")?.addEventListener("change", renderDashboardState);
  document.getElementById("station-label-toggle")?.addEventListener("change", renderDashboardState);
  document.getElementById("corridor-toggle")?.addEventListener("change", renderContextLayer);
  document.getElementById("refresh-data")?.addEventListener("click", refreshDashboard);

  document.getElementById("station-table-toggle")?.addEventListener("click", () => {
    showAllStations = !showAllStations;
    renderStationTable(filterStations(latestStations));
  });

  document.getElementById("alert-queue")?.addEventListener("click", (event) => {
    const workflowButton = event.target.closest("[data-alert-action]");
    if (workflowButton) {
      changeAlertWorkflow(workflowButton.getAttribute("data-alert-id"), workflowButton.getAttribute("data-alert-action"));
      return;
    }
    const button = event.target.closest("[data-channel-filter]");
    if (!button) return;
    activeChannelFilter = button.getAttribute("data-channel-filter") || "all";
    renderAlertQueue(filterStations(latestStations));
    showToast(`${activeChannelFilter} channel filter applied.`);
  });

  document.getElementById("all-channel-filter")?.addEventListener("click", () => {
    activeChannelFilter = "all";
    renderAlertQueue(filterStations(latestStations));
  });

  document.getElementById("btn-map-layers")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const menu = document.getElementById("layers-dropdown-menu");
    if (menu) menu.hidden = !menu.hidden;
  });

  document.getElementById("layers-dropdown-menu")?.addEventListener("click", (event) => event.stopPropagation());

  function toggleOptions(toggleId, menuId) {
    document.getElementById(toggleId)?.addEventListener("click", (event) => {
      event.stopPropagation();
      const menu = document.getElementById(menuId);
      if (!menu) return;
      menu.hidden = !menu.hidden;
      event.currentTarget.setAttribute("aria-expanded", String(!menu.hidden));
    });
  }
  toggleOptions("station-options-toggle", "station-options-menu");
  toggleOptions("queue-options-toggle", "queue-options-menu");

  document.getElementById("station-options-menu")?.addEventListener("click", async (event) => {
    const action = event.target.getAttribute("data-station-action");
    const station = latestStations.find((item) => String(item.station_id) === String(selectedStationId));
    if (!action || !station) return;
    if (action === "copy") {
      await navigator.clipboard?.writeText(station.station_id);
      showToast("Station ID copied.");
    } else if (action === "export") {
      const blob = new Blob([JSON.stringify(station, null, 2)], { type: "application/json" });
      const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `${station.station_id}.json` });
      link.click();
      URL.revokeObjectURL(link.href);
      showToast("Station data exported.");
    } else if (action === "history") {
      window.location.href = `/data?station_id=${encodeURIComponent(station.station_id)}`;
    } else if (action === "focus") {
      focusStationOnMap(station.station_id);
    }
    document.getElementById("station-options-menu").hidden = true;
  });

  document.getElementById("queue-options-menu")?.addEventListener("click", (event) => {
    const action = event.target.getAttribute("data-queue-action");
    if (!action) return;
    if (action === "read") {
      const badge = document.getElementById("top-alert-badge");
      if (badge) badge.hidden = true;
      sessionStorage.setItem("floodwatch-read-alerts", String(latestAlerts.length));
      showToast("All queue alerts marked as read.");
    } else if (action === "clear") {
      latestAlerts = latestAlerts.filter((alert) => alert.status !== "resolved");
      renderAlertQueue(filterStations(latestStations));
      showToast("Resolved alerts cleared.");
    } else if (action === "export") {
      const blob = new Blob([JSON.stringify(latestAlerts, null, 2)], { type: "application/json" });
      const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "floodwatch-alerts.json" });
      link.click();
      URL.revokeObjectURL(link.href);
      showToast("Alert log exported.");
    }
    document.getElementById("queue-options-menu").hidden = true;
  });

  // Shared navigation and notification events are owned by site.js.
  document.addEventListener("click", () => {
    const layersMenu = document.getElementById("layers-dropdown-menu");
    if (layersMenu) layersMenu.hidden = true;
    ["station-options-menu", "queue-options-menu"].forEach((id) => {
      const menu = document.getElementById(id);
      if (menu) menu.hidden = true;
    });
  });

  document.getElementById("btn-run-scenario")?.addEventListener("click", async () => {
    if (!selectedStationId) return;
    showToast(`Injecting scenario: Rising limb telemetry on ${selectedStationId}...`);
    try {
      const res = await fetch("/api/scenario/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ station_id: selectedStationId, scenario: "flood" }),
      });
      if (res.status === 401 || res.status === 403) {
        showToast("Operator role required to run scenarios.");
        return;
      }
      if (res.ok) {
        showToast("Scenario applied: Water level elevated & risk recomputed.");
        await refreshDashboard();
      } else {
        showToast("Scenario could not be applied.");
      }
    } catch (err) {
      console.error("Scenario error", err);
      showToast("Could not apply scenario.");
    }
  });

  document.getElementById("btn-dispatch-alert")?.addEventListener("click", async () => {
    if (!selectedStationId) return;
    showToast("Logging simulated alert bulletin across web, SMS, and email channels...");
    try {
      const res = await fetch("/api/alerts/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ station_id: selectedStationId }),
      });
      if (res.status === 401 || res.status === 403) {
        showToast("Operator role required to log alert workflow actions.");
        return;
      }
      if (res.ok) {
        showToast("Simulated alert bulletin logged for decision-support review.");
        await renderAlertQueue(latestStations);
      } else {
        showToast("Alert simulation log was rejected.");
      }
    } catch (err) {
      console.error("Alert simulation log error", err);
      showToast("Alert simulation log failed.");
    }
  });

  document.getElementById("btn-open-alert-centre")?.addEventListener("click", () => {
    const target = document.getElementById("alert-centre");
    if (target) {
      target.scrollIntoView({ behavior: "smooth" });
      showToast("Navigated to Response Queue.");
    }
  });

  document.getElementById("station-list")?.addEventListener("click", (event) => {
    const clearButton = event.target.closest("[data-clear-map-filters]");
    if (clearButton) {
      clearMapFilters();
      return;
    }

    const focusButton = event.target.closest("[data-focus-station]");
    if (focusButton) {
      focusStationOnMap(focusButton.getAttribute("data-focus-station"));
    }
  });

  refreshDashboard();
  refreshForecast();
  updateNotificationPanel();
  updateElapsedRefreshLabel();
  setInterval(updateElapsedRefreshLabel, 1000);
  setInterval(refreshDashboard, 15000);
  setInterval(refreshForecast, 15 * 60 * 1000);
});
