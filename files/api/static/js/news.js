function newsEscapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNewsDate(value) {
  if (!value) return "Date not supplied";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date not supplied";
  return date.toLocaleString();
}

function newsSafeUrl(value) {
  try {
    const parsed = new URL(value);
    return ["https:", "http:"].includes(parsed.protocol) ? parsed.href : "";
  } catch { return ""; }
}

function renderNewsFeed(payload) {
  const status = document.getElementById("news-feed-status");
  const list = document.getElementById("news-feed-list");
  if (!status || !list) return;

  status.textContent = `${payload.message} Query: ${payload.query || "flood"}. Provider: ${payload.provider}.`;
  if (!payload.configured || !payload.articles?.length) {
    list.innerHTML = `
      <div class="notice-box">
        <strong>${payload.configured ? "No articles are available right now." : "News feed is not connected yet."}</strong>
        <p>${newsEscapeHtml(payload.message || "Please check again later.")}</p>
      </div>
    `;
    return;
  }

  list.innerHTML = payload.articles.filter((article) => newsSafeUrl(article.url)).map((article) => `
    <article class="news-feed-card">
      <div>
        <span class="eyebrow">${newsEscapeHtml(article.provider)} · ${newsEscapeHtml(article.source)}</span>
        <h3><a href="${newsEscapeHtml(newsSafeUrl(article.url))}" target="_blank" rel="noopener noreferrer">${newsEscapeHtml(article.title)}</a></h3>
        <p>${newsEscapeHtml(article.description || "No summary supplied by the provider.")}</p>
        <small>${newsEscapeHtml(formatNewsDate(article.published_at))}</small>
      </div>
    </article>
  `).join("");
}

async function loadNewsFeed(forceRefresh = false) {
  const status = document.getElementById("news-feed-status");
  const refresh = document.getElementById("news-refresh");
  try {
    if (refresh) refresh.disabled = true;
    if (status) status.textContent = forceRefresh ? "Refreshing external feed..." : "Checking configured news provider...";
    const response = await fetch(`/api/news-feed?limit=8&refresh=${forceRefresh ? "true" : "false"}`, {
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error(`News request failed with ${response.status}`);
    renderNewsFeed(await response.json());
  } catch (error) {
    if (status) status.textContent = "External feed could not be loaded. The local project notes remain available below.";
  } finally {
    if (refresh) refresh.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadNewsFeed(false);
  document.getElementById("news-refresh")?.addEventListener("click", () => loadNewsFeed(true));
});
