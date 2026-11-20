/**
 * Main Application Orchestrator
 * Handles navigation switching, polling loops, and UI badge formatters.
 */
document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initLucide();
  loadCurrentPage();
  
  // Auto-refresh polling every 5 seconds
  setInterval(() => {
    loadCurrentPage();
  }, 5000);
});

function initNavigation() {
  const navItems = document.querySelectorAll(".nav-item");
  navItems.forEach((item) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const pageId = item.getAttribute("data-page");
      if (!pageId) return;

      navItems.forEach((n) => n.classList.remove("active"));
      item.classList.add("active");

      document.querySelectorAll(".page-container").forEach((p) => {
        p.classList.remove("active");
      });

      const activePage = document.getElementById(`page-${pageId}`);
      if (activePage) {
        activePage.classList.add("active");
        const pageTitle = item.querySelector("span").innerText;
        document.getElementById("current-page-title").innerText = pageTitle;
        loadCurrentPage();
      }
    });
  });
}

function initLucide() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function loadCurrentPage() {
  const activeNav = document.querySelector(".nav-item.active");
  if (!activeNav) return;
  const pageId = activeNav.getAttribute("data-page");

  switch (pageId) {
    case "overview":
      if (window.loadOverview) window.loadOverview();
      break;
    case "servers":
      if (window.loadServers) window.loadServers();
      break;
    case "collectors":
      if (window.loadCollectors) window.loadCollectors();
      break;
    case "alerts":
      if (window.loadAlerts) window.loadAlerts();
      break;
    case "aiops":
      if (window.loadAIOps) window.loadAIOps();
      break;
    case "egress":
      if (window.loadEgress) window.loadEgress();
      break;
    case "audit":
      if (window.loadAudit) window.loadAudit();
      break;
    case "remediation":
      if (window.loadRemediation) window.loadRemediation();
      break;
  }
}

function formatTimestamp(isoStr) {
  if (!isoStr) return "--";
  try {
    const dt = new Date(isoStr);
    return dt.toLocaleTimeString() + " " + dt.toLocaleDateString();
  } catch (e) {
    return isoStr;
  }
}

function renderHealthBadge(state) {
  const s = (state || "good").toLowerCase();
  return `<span class="badge badge-${s}">${s.toUpperCase()}</span>`;
}

function renderSeverityBadge(sev) {
  const s = (sev || "info").toLowerCase();
  return `<span class="badge badge-${s}">${s.toUpperCase()}</span>`;
}
