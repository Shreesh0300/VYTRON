/**
 * VYTRON — Real-Time Telemetry & Incident Prioritization Dashboard Application
 */

const AppState = {
  selectedServerId: "APP-01",
  latestSnapshot: null,
  ws: null,
  pollingInterval: null,
  wsConnected: false,
};

// ── Initialization ────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Incident Modal
  if (window.IncidentModal) {
    window.IncidentModal.init();
  }

  // Setup Clock
  updateClock();
  setInterval(updateClock, 1000);

  // Setup Simulation Controls
  setupControlListeners();

  // Connect Real-Time WebSocket
  connectWebSocket();
});

function updateClock() {
  const clockEl = document.getElementById("clockDisplay");
  if (clockEl) {
    clockEl.textContent = new Date().toLocaleTimeString();
  }
}

// ── WebSocket & Fallback Polling ───────────────────────────────────────────

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  const wsStatusEl = document.getElementById("wsStatus");

  try {
    const ws = new WebSocket(wsUrl);
    AppState.ws = ws;

    ws.onopen = () => {
      AppState.wsConnected = true;
      if (wsStatusEl) {
        wsStatusEl.innerHTML = `
          <span class="status-dot green"></span>
          <span class="status-label">LIVE STREAM</span>
        `;
      }
      // Stop fallback polling if active
      if (AppState.pollingInterval) {
        clearInterval(AppState.pollingInterval);
        AppState.pollingInterval = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const snapshot = JSON.parse(event.data);
        handleSnapshot(snapshot);
      } catch (err) {
        console.error("Failed to parse telemetry snapshot:", err);
      }
    };

    ws.onclose = () => {
      AppState.wsConnected = false;
      if (wsStatusEl) {
        wsStatusEl.innerHTML = `
          <span class="status-dot red" style="background:#f59e0b; box-shadow:0 0 8px #f59e0b;"></span>
          <span class="status-label" style="color:#fbbf24;">POLLING FALLBACK</span>
        `;
      }
      startPollingFallback();
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  } catch (err) {
    console.warn("WebSocket connection error:", err);
    startPollingFallback();
  }
}

function startPollingFallback() {
  if (AppState.pollingInterval) return;
  AppState.pollingInterval = setInterval(async () => {
    try {
      const res = await fetch("/api/state");
      if (res.ok) {
        const snapshot = await res.json();
        handleSnapshot(snapshot);
      }
    } catch (e) {
      console.warn("REST state poll failed:", e);
    }
  }, 1500);
}

// ── Central Telemetry Dispatcher ──────────────────────────────────────────

function handleSnapshot(snapshot) {
  if (!snapshot || !snapshot.servers) return;
  AppState.latestSnapshot = snapshot;

  renderOverview(snapshot.overview, snapshot.active_scenario);
  renderServersGrid(snapshot.servers);
  renderSelectedServerDetail(snapshot.servers);
  renderNotifications(snapshot.notifications);
  renderPriorityQueue(snapshot.priority_queue);
}

// ── Section A: Overview Rendering ─────────────────────────────────────────

function renderOverview(overview, activeScenario) {
  if (!overview) return;

  const totalEl = document.getElementById("statTotalServers");
  const normalEl = document.getElementById("statNormalServers");
  const warnEl = document.getElementById("statWarningServers");
  const critEl = document.getElementById("statCriticalServers");
  const activeIncEl = document.getElementById("statActiveIncidents");
  const prioBadge = document.getElementById("statHighestPriorityBadge");
  const prioDesc = document.getElementById("statHighestPriorityDesc");
  const scenarioPill = document.getElementById("scenarioActivePill");

  if (totalEl) totalEl.textContent = overview.total_servers || 5;
  if (normalEl) normalEl.textContent = overview.normal_count || 0;
  if (warnEl) warnEl.textContent = overview.warning_count || 0;
  if (critEl) critEl.textContent = overview.critical_count || 0;
  if (activeIncEl) activeIncEl.textContent = overview.active_incidents || 0;

  if (prioBadge) {
    const hp = overview.highest_priority || "NONE";
    prioBadge.textContent = hp;
    prioBadge.className = `priority-badge-lg p-${hp.toLowerCase()}`;
  }

  if (prioDesc) {
    if (overview.highest_priority_incident) {
      const inc = overview.highest_priority_incident;
      prioDesc.textContent = `${inc.server_id}: ${inc.metric_name}`;
    } else {
      prioDesc.textContent = "Cluster Stable";
    }
  }

  if (scenarioPill) {
    if (activeScenario) {
      scenarioPill.textContent = `Active: ${activeScenario.title} [${activeScenario.affected_servers.join(", ")}]`;
      scenarioPill.classList.add("active");
    } else {
      scenarioPill.textContent = "Normal Baseline (All 5 Stable)";
      scenarioPill.classList.remove("active");
    }
  }
}

// ── Section B: Server Cards Grid Rendering ─────────────────────────────────

function renderServersGrid(servers) {
  const container = document.getElementById("serversCardsGrid");
  if (!container) return;

  const serverIds = Object.keys(servers);
  let html = "";

  serverIds.forEach((sid) => {
    const s = servers[sid];
    const isSelected = sid === AppState.selectedServerId;
    const status = s.status || "NORMAL";
    const statusClass = status.toLowerCase();

    let alertClass = "";
    if (status === "CRITICAL") alertClass = "alert-critical";
    else if (status === "WARNING") alertClass = "alert-warning";

    // 4 metrics mini list
    let metricsHtml = "";
    const meta = s.parameters_meta || {};
    Object.keys(meta).slice(0, 4).forEach((pKey) => {
      const pMeta = meta[pKey];
      const val = s.metrics[pKey];
      const thresholds = pMeta.thresholds;
      let valClass = "";

      if (thresholds) {
        const dir = thresholds.direction || "above";
        if (dir === "above") {
          if (val >= thresholds.critical) valClass = "crit";
          else if (val >= thresholds.warning) valClass = "warn";
        } else {
          if (val <= thresholds.critical) valClass = "crit";
          else if (val <= thresholds.warning) valClass = "warn";
        }
      }

      metricsHtml += `
        <div class="mini-metric-row">
          <span class="mini-metric-name">${pMeta.name}</span>
          <span class="mini-metric-val ${valClass}">${val} ${pMeta.unit}</span>
        </div>
      `;
    });

    html += `
      <div class="server-summary-card ${isSelected ? 'selected' : ''} ${alertClass}" 
           data-server-id="${sid}" onclick="selectServer('${sid}')">
        <div>
          <div class="card-top">
            <span class="server-id-badge">${s.id}</span>
            <span class="status-badge status-${statusClass}">${status}</span>
          </div>
          <div class="server-summary-name">${s.name}</div>
          <div class="card-metrics-mini">
            ${metricsHtml}
          </div>
        </div>
        <div class="inspect-hint">${isSelected ? '● ACTIVE INSPECTION' : 'Click to inspect'}</div>
      </div>
    `;
  });

  container.innerHTML = html;
}

window.selectServer = function(serverId) {
  AppState.selectedServerId = serverId;
  if (AppState.latestSnapshot && AppState.latestSnapshot.servers) {
    renderServersGrid(AppState.latestSnapshot.servers);
    renderSelectedServerDetail(AppState.latestSnapshot.servers);
  }
};

// ── Selected Server Detailed Diagnostics & Charts ─────────────────────────

function renderSelectedServerDetail(servers) {
  const sid = AppState.selectedServerId || "APP-01";
  const s = servers[sid] || Object.values(servers)[0];
  if (!s) return;

  const idEl = document.getElementById("detailServerId");
  const nameEl = document.getElementById("detailServerName");
  const typeEl = document.getElementById("detailServerType");
  const statusEl = document.getElementById("detailServerStatus");
  const roleEl = document.getElementById("detailServerRole");
  const uptimeEl = document.getElementById("detailServerUptime");

  if (idEl) idEl.textContent = s.id;
  if (nameEl) nameEl.textContent = s.name;
  if (typeEl) typeEl.textContent = s.type;
  if (statusEl) {
    statusEl.textContent = s.status;
    statusEl.className = `status-pill status-${s.status.toLowerCase()}`;
  }
  if (roleEl) roleEl.textContent = s.description;
  if (uptimeEl) uptimeEl.textContent = s.uptime_str;

  // Render 4 parameter highlight cards
  const paramsGrid = document.getElementById("detailParametersGrid");
  if (paramsGrid && s.parameters_meta) {
    let cardsHtml = "";
    Object.keys(s.parameters_meta).slice(0, 4).forEach((pKey) => {
      const pMeta = s.parameters_meta[pKey];
      const val = s.metrics[pKey];
      const thresholds = pMeta.thresholds;

      let breachClass = "";
      let threshMetaText = "Normal range";

      if (thresholds) {
        const dir = thresholds.direction || "above";
        threshMetaText = `Warn: ${thresholds.warning} | Crit: ${thresholds.critical}`;
        if (dir === "above") {
          if (val >= thresholds.critical) breachClass = "breach-crit";
          else if (val >= thresholds.warning) breachClass = "breach-warn";
        } else {
          if (val <= thresholds.critical) breachClass = "breach-crit";
          else if (val <= thresholds.warning) breachClass = "breach-warn";
        }
      }

      cardsHtml += `
        <div class="param-card ${breachClass}">
          <div class="param-card-header">
            <span class="param-name">${pMeta.name}</span>
            <span class="param-unit">${pMeta.unit}</span>
          </div>
          <div class="param-value">${val}</div>
          <div class="param-threshold-meta">${threshMetaText}</div>
        </div>
      `;
    });
    paramsGrid.innerHTML = cardsHtml;
  }

  // Update Charts
  if (window.ServerCharts) {
    window.ServerCharts.updateCharts(s);
  }
}

// ── Section C: Notifications Table Rendering ──────────────────────────────

function renderNotifications(notifications) {
  const tbody = document.getElementById("notificationsTbody");
  const badge = document.getElementById("notificationsCountBadge");
  if (!tbody) return;

  if (badge) {
    badge.textContent = `${(notifications && notifications.length) || 0} alerts`;
  }

  if (!notifications || notifications.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="empty-state">No incidents detected. All 5 servers operating within normal thresholds.</td>
      </tr>
    `;
    return;
  }

  let rowsHtml = "";
  notifications.forEach((inc) => {
    const prio = inc.priority || "P3";
    const status = inc.status || "OPEN";
    const statusClass = status === "OPEN" ? "open" : "resolved";
    const prioClass = `prio-${prio.toLowerCase()}`;

    // Serialize safely for modal onclick
    const incJson = JSON.stringify(inc).replace(/"/g, '&quot;');

    rowsHtml += `
      <tr class="clickable-row" onclick="openIncidentFromData('${inc.incident_id}')">
        <td style="font-family: var(--font-mono); font-weight: 700; color: #fff;">${inc.incident_id}</td>
        <td style="font-family: var(--font-mono); color: var(--text-dim);">${inc.created_at_str}</td>
        <td><strong>${inc.server_id}</strong> <span style="color:var(--text-dim); font-size:11px;">(${inc.server_type})</span></td>
        <td>${inc.issue_description}</td>
        <td><span class="prio-pill ${prioClass}">${prio}</span></td>
        <td><span class="status-tag ${statusClass}">${status}</span></td>
      </tr>
    `;
  });

  tbody.innerHTML = rowsHtml;
}

window.openIncidentFromData = function(incidentId) {
  if (!AppState.latestSnapshot) return;
  const list = [
    ...(AppState.latestSnapshot.priority_queue || []),
    ...(AppState.latestSnapshot.notifications || []),
  ];
  const found = list.find(x => x.incident_id === incidentId);
  if (found && window.IncidentModal) {
    window.IncidentModal.open(found);
  }
};

// ── Section D: Priority Queue Rendering ───────────────────────────────────

function renderPriorityQueue(priorityQueue) {
  const container = document.getElementById("priorityQueueList");
  const badge = document.getElementById("queueCountBadge");
  if (!container) return;

  if (badge) {
    badge.textContent = `${(priorityQueue && priorityQueue.length) || 0} active`;
  }

  if (!priorityQueue || priorityQueue.length === 0) {
    container.innerHTML = `
      <div class="empty-state-queue">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="M8 12l2 2 4-4"></path>
        </svg>
        <p>Queue is empty — No active unresolved incidents.</p>
      </div>
    `;
    return;
  }

  let cardsHtml = "";
  priorityQueue.forEach((inc) => {
    const isHighest = inc.is_highest_priority;
    const prio = inc.priority || "P3";
    const prioClass = `prio-${prio.toLowerCase()}`;

    cardsHtml += `
      <div class="queue-card ${isHighest ? 'highest-prio' : ''}">
        <div class="queue-rank-wrap">
          <span class="queue-rank">#${inc.rank}</span>
          <span class="prio-pill ${prioClass}">${prio}</span>
        </div>

        <div class="queue-main-info">
          <div class="queue-top-line">
            <span class="queue-inc-id">${inc.incident_id}</span>
            <span class="queue-server-tag">${inc.server_id} · ${inc.server_name}</span>
            ${isHighest ? '<span style="font-size:10px; font-weight:800; color:var(--p1-color); background:rgba(239,68,68,0.2); padding:1px 6px; border-radius:3px;">HIGHEST PRIORITY</span>' : ''}
          </div>
          <div class="queue-issue">${inc.issue_description}</div>
        </div>

        <button class="queue-action-btn" onclick="openIncidentFromData('${inc.incident_id}')">
          Investigate ➔
        </button>
      </div>
    `;
  });

  container.innerHTML = cardsHtml;
}

// ── Simulation Control Actions ─────────────────────────────────────────────

function setupControlListeners() {
  const btnStart = document.getElementById("btnStart");
  const btnStop = document.getElementById("btnStop");
  const btnReset = document.getElementById("btnReset");
  const scenarioSelect = document.getElementById("scenarioSelect");

  if (btnStart) {
    btnStart.addEventListener("click", async () => {
      const scenarioId = scenarioSelect ? scenarioSelect.value : "scenario_01";
      try {
        const res = await fetch("/api/simulation/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scenario: scenarioId }),
        });
        const data = await res.json();
        if (data.state) handleSnapshot(data.state);
      } catch (e) {
        console.error("Failed to start scenario:", e);
      }
    });
  }

  if (btnStop) {
    btnStop.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/simulation/stop", { method: "POST" });
        const data = await res.json();
        if (data.state) handleSnapshot(data.state);
      } catch (e) {
        console.error("Failed to stop simulation:", e);
      }
    });
  }

  if (btnReset) {
    btnReset.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/simulation/reset", { method: "POST" });
        const data = await res.json();
        if (data.state) handleSnapshot(data.state);
      } catch (e) {
        console.error("Failed to reset simulation:", e);
      }
    });
  }
}
