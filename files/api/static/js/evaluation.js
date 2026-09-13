function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function pct(value) {
  const number = Number(value);
  if (value == null || !Number.isFinite(number)) return "Not recorded";
  return `${(number * 100).toFixed(1)}%`;
}

function metricCard(title, value, help) {
  return `
    <article class="metric-card">
      <span>${escapeHtml(title)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(help)}</small>
    </article>
  `;
}

function bar(label, value, maxValue, className = "") {
  if (value == null || !Number.isFinite(Number(value))) {
    return `<p>${escapeHtml(label)}: not recorded</p>`;
  }
  const numericValue = Number(value) || 0;
  const denominator = Math.max(Number(maxValue) || 1, 1);
  const width = Math.max(0, Math.min(100, (numericValue / denominator) * 100));
  const display = maxValue === 100 && !className ? `${numericValue.toFixed(1)}%` : String(numericValue);
  return `
    <div class="chart-row ${className}">
      <div class="chart-row-label">${escapeHtml(label)}</div>
      <div class="chart-track" aria-hidden="true">
        <span style="width: ${width}%"></span>
      </div>
      <div class="chart-row-value">${escapeHtml(display)}</div>
    </div>
  `;
}

function renderModelEvaluation(payload) {
  const status = document.getElementById("model-evaluation-status");
  const cards = document.getElementById("model-metric-cards");
  const charts = document.getElementById("model-chart-list");
  if (!status || !cards || !charts) return;

  const results = payload.results || {};
  const forest = results.random_forest || {};
  status.textContent = `${payload.data_source}. Target: ${payload.prediction_target}; horizon: ${payload.prediction_horizon_ticks} ticks.`;
  cards.innerHTML = [
    metricCard("Random Forest F1", pct(forest.f1), "Current saved model"),
    metricCard("False positives", forest.false_positive ?? "—", "Predicted crossing that did not occur"),
    metricCard("False negatives", forest.false_negative ?? "—", "Missed future threshold crossing"),
    metricCard("Samples used", payload.label_policy?.total_samples_used ?? "—", "Simulator-generated evidence"),
  ].join("");

  const maxError = Math.max(
    ...Object.values(results).flatMap((values) => [Number(values.false_positive) || 0, Number(values.false_negative) || 0]),
    1,
  );
  charts.innerHTML = Object.entries(results).map(([modelName, values]) => `
    <article class="chart-card">
      <h3>${escapeHtml(modelName.replaceAll("_", " "))}</h3>
      ${bar("Accuracy", values.accuracy == null ? null : values.accuracy * 100, 100)}
      ${bar("Precision", values.precision == null ? null : values.precision * 100, 100)}
      ${bar("Recall", values.recall == null ? null : values.recall * 100, 100)}
      ${bar("F1", values.f1 == null ? null : values.f1 * 100, 100)}
      ${bar("False positives", values.false_positive, maxError, "chart-row-warning")}
      ${bar("False negatives", values.false_negative, maxError, "chart-row-danger")}
    </article>
  `).join("");
}

async function loadModelEvaluation() {
  const status = document.getElementById("model-evaluation-status");
  try {
    const response = await fetch("/api/model-evaluation", { credentials: "same-origin" });
    if (!response.ok) throw new Error(`Model metrics request failed with ${response.status}`);
    renderModelEvaluation(await response.json());
  } catch (error) {
    if (status) status.textContent = "Model metrics are temporarily unavailable. Run train_model.py and reload this page.";
  }
}

async function loadScenarioRuns() {
  const list = document.getElementById("scenario-run-list");
  if (!list) return;
  try {
    const response = await fetch("/api/scenario-runs", { credentials: "same-origin" });
    if (response.status === 401 || response.status === 403) {
      list.innerHTML = '<div class="notice-box">Operator role required to view scenario-run reports.</div>';
      return;
    }
    if (!response.ok) throw new Error(`Scenario request failed with ${response.status}`);
    const runs = await response.json();
    if (!runs.length) {
      list.innerHTML = '<div class="notice-box">No scenario runs have been logged yet. Run a dashboard scenario as an operator first.</div>';
      return;
    }
    list.innerHTML = runs.map((run) => `
      <article class="station-card">
        <div class="station-card-top">
          <h3>${escapeHtml(run.station_name)}</h3>
          <span class="risk-pill risk-${escapeHtml(String(run.after_risk).toLowerCase())}">${escapeHtml(run.after_risk)}</span>
        </div>
        <p>${escapeHtml(run.scenario)} scenario changed water level from ${escapeHtml(run.before_water_level_m)} m to ${escapeHtml(run.after_water_level_m)} m.</p>
        <small>Operator: ${escapeHtml(run.operator_email)} · ${escapeHtml(new Date(run.created_at).toLocaleString())}</small>
        <p><a class="btn btn-secondary" href="/api/scenario-runs/${encodeURIComponent(run.id)}/report.pdf">Download scenario PDF</a></p>
      </article>
    `).join("");
  } catch (error) {
    list.innerHTML = '<div class="error-box">Scenario runs could not be loaded.</div>';
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadModelEvaluation();
  loadScenarioRuns();
});
