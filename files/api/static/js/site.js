function showNotice(title, message) {
  const modal = document.createElement("div");
  modal.className = "modal";
  modal.innerHTML = `
    <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="notice-title">
      <h2 id="notice-title">${escapeText(title)}</h2>
      <p>${escapeText(message)}</p>
      <button class="btn btn-primary" type="button">OK</button>
    </div>
  `;
  document.body.appendChild(modal);
  modal.querySelector("button").addEventListener("click", () => modal.remove());
}

function escapeText(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function notificationRiskClass(riskLevel) {
  return String(riskLevel || "update").toLowerCase().replace(/[^a-z0-9-]/g, "-");
}

function formatNotificationTime(timestamp) {
  const parsed = Date.parse(timestamp || "");
  if (Number.isNaN(parsed)) {
    return "Time not recorded";
  }
  return new Date(parsed).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatNotificationChannels(channels) {
  const labels = {
    web: "Web dashboard",
    Dashboard: "Web dashboard",
    email: "Simulated email",
    Email: "Simulated email",
    sms: "Simulated SMS",
    SMS: "Simulated SMS",
  };
  const names = Object.keys(channels || {});
  return (names.length ? names : ["web"]).map((name) => labels[name] || name).join(" · ");
}

function renderNotificationList(notificationList, alerts) {
  if (!alerts.length) {
    notificationList.innerHTML = '<li class="notification-empty">No recent alert logs yet.</li>';
    return;
  }

  notificationList.innerHTML = alerts.map((alert) => {
    const stationName = escapeText(alert.station_name || "Station update");
    const riskLevel = escapeText(alert.risk_level || "Update");
    const message = escapeText(alert.message || "A station status update was logged for review.");
    const time = escapeText(formatNotificationTime(alert.updated_at || alert.created_at || alert.timestamp));
    const channels = escapeText(formatNotificationChannels(alert.channels));
    const riskClass = notificationRiskClass(alert.risk_level);

    return `
      <li class="notification-item notification-risk-${riskClass}">
        <div class="notification-item-top">
          <strong>${stationName}</strong>
          <span>${riskLevel}</span>
        </div>
        <p>${message}</p>
        <small>${time} · ${channels}</small>
      </li>
    `;
  }).join("");
}

document.addEventListener("DOMContentLoaded", function () {
  // Shared menu handlers belong here so every page has exactly one handler.
  const userButton = document.getElementById("user-menu-btn");
  const userMenu = document.getElementById("user-dropdown-pane");
  const closeUserMenu = () => {
    if (userMenu) userMenu.hidden = true;
    userButton?.setAttribute("aria-expanded", "false");
  };
  userButton?.addEventListener("click", (event) => {
    event.stopPropagation();
    if (userMenu) {
      userMenu.hidden = !userMenu.hidden;
      userButton.setAttribute("aria-expanded", String(!userMenu.hidden));
    }
  });
  userMenu?.addEventListener("click", (event) => event.stopPropagation());
  document.addEventListener("click", closeUserMenu);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeUserMenu();
  });
  document.getElementById("mobile-nav-close")?.addEventListener("click", () => {
    document.querySelector(".nav-links")?.classList.remove("nav-links-open");
  });
  const menuToggle = document.getElementById("menu-toggle-btn");
  menuToggle?.addEventListener("click", () => {
    document.querySelector(".command-sidebar")?.classList.toggle("sidebar-collapsed");
    document.querySelector(".nav-links")?.classList.toggle("nav-links-open");
  });

  const notificationButton = document.getElementById("top-notification-bell");
  const notificationDropdown = document.getElementById("notification-dropdown");
  const notificationList = document.getElementById("notification-list");
  const closeNotifications = () => {
    if (notificationDropdown) notificationDropdown.hidden = true;
    notificationButton?.setAttribute("aria-expanded", "false");
  };

  notificationDropdown?.addEventListener("click", (event) => event.stopPropagation());

  notificationButton?.addEventListener("click", async (event) => {
    event.stopPropagation();
    if (!notificationDropdown || !notificationList) {
      return;
    }

    if (!notificationDropdown.hidden) {
      closeNotifications();
      return;
    }

    notificationDropdown.hidden = false;
    notificationButton.setAttribute("aria-expanded", "true");
    notificationList.innerHTML = '<li class="notification-empty">Loading recent alerts...</li>';

    try {
      const response = await fetch("/api/alerts?limit=5", { credentials: "same-origin" });
      const alerts = response.ok ? await response.json() : [];
      renderNotificationList(notificationList, alerts);
      const badge = document.getElementById("top-alert-badge");
      if (badge) {
        badge.textContent = "0";
        badge.hidden = true;
      }
    } catch {
      notificationList.innerHTML = '<li class="notification-empty">Notifications are temporarily unavailable.</li>';
    }
  });

  document.addEventListener("click", closeNotifications);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeNotifications();
  });
  const topButton = document.createElement("button");
  topButton.className = "return-top";
  topButton.type = "button";
  topButton.setAttribute("aria-label", "Return to top");
  topButton.title = "Return to top";
  topButton.textContent = "↑";
  topButton.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  document.body.appendChild(topButton);

  const updateTopButton = () => topButton.classList.toggle("visible", window.scrollY > 420);
  window.addEventListener("scroll", updateTopButton, { passive: true });
  updateTopButton();
});
