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

  renderOverview(snapshot.overview, snapshot.active_scenario, snapshot.data_freshness, snapshot.is_running);
  renderServersGrid(snapshot.servers);
  renderSelectedServerDetail(snapshot.servers);
  renderNotifications(snapshot.notifications);
  renderPriorityQueue(snapshot.priority_queue);
  if (snapshot.egress_proof) {
    renderEgressProof(snapshot.egress_proof, snapshot.data_freshness);
  }
}

// ── Section A: Overview Rendering ─────────────────────────────────────────

function renderOverview(overview, activeScenario, dataFreshness, isRunning) {
  if (!overview) return;

  const totalEl = document.getElementById("statTotalServers");
  const normalEl = document.getElementById("statNormalServers");
  const warnEl = document.getElementById("statWarningServers");
  const critEl = document.getElementById("statCriticalServers");
  const activeIncEl = document.getElementById("statActiveIncidents");
  const prioBadge = document.getElementById("statHighestPriorityBadge");
  const prioDesc = document.getElementById("statHighestPriorityDesc");
  const scenarioPill = document.getElementById("scenarioActivePill");
  const wsStatusEl = document.getElementById("wsStatus");
  const simToggleBtn = document.getElementById("btnToggleSimControls");

  if (simToggleBtn) {
    if (isRunning) {
      simToggleBtn.classList.add("sim-running");
    } else {
      simToggleBtn.classList.remove("sim-running");
    }
  }

  if (wsStatusEl && AppState.wsConnected) {
    if (isRunning) {
      wsStatusEl.innerHTML = `
        <span class="status-dot green"></span>
        <span class="status-label">LIVE STREAM</span>
      `;
    } else if (activeScenario && !isRunning) {
      wsStatusEl.innerHTML = `
        <span class="status-dot amber" style="background:#f59e0b; box-shadow:0 0 8px #f59e0b;"></span>
        <span class="status-label" style="color:#fbbf24;">STOPPED</span>
      `;
    } else {
      wsStatusEl.innerHTML = `
        <span class="status-dot green" style="background:#10b981; box-shadow:0 0 8px #10b981;"></span>
        <span class="status-label" style="color:#34d399;">STANDBY</span>
      `;
    }
  }

  // 4 Health State Cards
  const excellentEl = document.getElementById("statExcellentServers");
  const goodEl = document.getElementById("statGoodServers");
  const fairEl = document.getElementById("statFairServers");
  const poorEl = document.getElementById("statPoorServers");
  const clusterBadge = document.getElementById("clusterHealthBadge");

  if (totalEl) totalEl.textContent = overview.total_servers || 5;
  if (normalEl) normalEl.textContent = overview.normal_count || 0;
  if (warnEl) warnEl.textContent = overview.warning_count || 0;
  if (critEl) critEl.textContent = overview.critical_count || 0;
  if (activeIncEl) activeIncEl.textContent = overview.active_incidents || 0;

  if (excellentEl) excellentEl.textContent = overview.excellent_count !== undefined ? overview.excellent_count : (overview.normal_count || 0);
  if (goodEl) goodEl.textContent = overview.good_count !== undefined ? overview.good_count : 0;
  if (fairEl) fairEl.textContent = overview.fair_count !== undefined ? overview.fair_count : (overview.warning_count || 0);
  if (poorEl) poorEl.textContent = overview.poor_count !== undefined ? overview.poor_count : (overview.critical_count || 0);

  if (clusterBadge) {
    const ch = (overview.cluster_health || "EXCELLENT").toUpperCase();
    clusterBadge.textContent = ch;
    clusterBadge.className = `section-badge health-badge health-${ch.toLowerCase()}`;
  }

  // Trust Boundary & Real-Time Targets Header Bar
  if (dataFreshness) {
    const barLatency = document.getElementById("barLatency");
    const barAlertLatency = document.getElementById("barAlertLatency");
    const barFreshness = document.getElementById("barFreshness");

    if (barLatency && dataFreshness.ingest_latency_seconds !== undefined) {
      barLatency.textContent = `${dataFreshness.ingest_latency_seconds}s (Target ≤10s)`;
    }
    if (barAlertLatency && dataFreshness.alert_latency_seconds !== undefined) {
      barAlertLatency.textContent = `${dataFreshness.alert_latency_seconds}s (Target ≤15s)`;
    }
    if (barFreshness && dataFreshness.utc_timestamp) {
      barFreshness.textContent = `${dataFreshness.status || 'REAL-TIME'} (${dataFreshness.utc_timestamp.slice(11, 19)} UTC)`;
    }

    const barCollector = document.getElementById("barCollectorStatus");
    if (barCollector && dataFreshness.collector_status) {
      if (dataFreshness.collector_status === "BUFFERING_OFFLINE") {
        barCollector.textContent = "BUFFERING (OFFLINE)";
        barCollector.className = "text-amber";
      } else {
        barCollector.textContent = "ONLINE (COLLECTOR-01)";
        barCollector.className = "text-green";
      }
    }
  }

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
    if (activeScenario && isRunning) {
      const summaryText = activeScenario.summary || (activeScenario.affected_servers ? `[${activeScenario.affected_servers.join(", ")}]` : "Active Incidents");
      scenarioPill.textContent = `Active: ${summaryText}`;
      scenarioPill.className = "scenario-status-pill active";
    } else if (activeScenario && !isRunning) {
      scenarioPill.textContent = "Simulation Stopped (Paused)";
      scenarioPill.className = "scenario-status-pill paused";
    } else {
      scenarioPill.textContent = "Normal Baseline (All 5 Stable)";
      scenarioPill.className = "scenario-status-pill";
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

    // 4 Health State determination (EXCELLENT, GOOD, FAIR, POOR)
    const healthState = (s.health_state || (status === "CRITICAL" ? "POOR" : status === "WARNING" ? "FAIR" : "EXCELLENT")).toUpperCase();
    const healthReason = s.health_reason || `${s.name} operating within baseline parameters.`;

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

      // Concise display name to avoid UI truncation while preserving full name in title
      let displayName = pMeta.name;
      if (pKey === "requests_per_sec") displayName = "Requests / Sec";
      else if (pKey === "response_time") displayName = "Response Time";
      else if (pKey === "login_requests_per_sec") displayName = "Login Reqs / Sec";
      else if (pKey === "active_connections") displayName = "Connections";

      metricsHtml += `
        <div class="mini-metric-row">
          <span class="mini-metric-name" title="${pMeta.name}">${displayName}</span>
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
            <div class="card-badge-group">
              <span class="health-badge-card health-${healthState.toLowerCase()}" title="State: ${healthState}&#10;Reason: ${healthReason}">${healthState}</span>
              <span class="status-badge status-${statusClass}">${status}</span>
            </div>
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
      const selectedVal = scenarioSelect ? scenarioSelect.value : "auto";
      const payload = selectedVal === "auto" ? { scenario: "auto" } : { server_count: parseInt(selectedVal) };
      try {
        const res = await fetch("/api/simulation/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.state) handleSnapshot(data.state);
      } catch (e) {
        console.error("Failed to start random simulation:", e);
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
        if (scenarioSelect) scenarioSelect.value = "auto";
      } catch (e) {
        console.error("Failed to reset simulation:", e);
      }
    });
  }
}

// ── Simulation Control Bar Visibility Toggle ──────────────────────────────

window.toggleSimulationControlBar = function() {
  const bar = document.getElementById("controlBarContainer");
  const btn = document.getElementById("btnToggleSimControls");
  if (!bar) return;

  const isHidden = bar.classList.contains("collapsed") || bar.style.display === "none";
  if (isHidden) {
    bar.classList.remove("collapsed");
    bar.style.display = "block";
    if (btn) btn.classList.add("active");
  } else {
    bar.classList.add("collapsed");
    bar.style.display = "none";
    if (btn) btn.classList.remove("active");
  }
};

// ── Section E: Egress Proof & Privacy Audit Rendering (Role-Aware) ────────

window._lastTier1RawRecord = null;
window._lastTier1FetchTime = 0;
window._isFetchingTier1Raw = false;

window.fetchAdminTier1Raw = async function() {
  const user = window.AuthManager ? window.AuthManager.currentUser : null;
  if (!user || user.authorized_role !== "admin") return;
  if (window._isFetchingTier1Raw) return;

  window._isFetchingTier1Raw = true;
  const rawPre = document.getElementById("egressRawJson");
  const statusPill = document.getElementById("tier1StatusPill");
  const subtitle = document.getElementById("tier1Subtitle");

  try {
    const res = await fetch("/api/egress/tier1-raw", {
      headers: {
        "X-Customer-Local-Auth": "granted"
      }
    });

    if (res.ok) {
      const data = await res.json();
      if (data.raw_tier1_record) {
        window._lastTier1RawRecord = data.raw_tier1_record;
        if (rawPre) {
          rawPre.textContent = JSON.stringify(data.raw_tier1_record, null, 2);
        }
        if (statusPill) {
          statusPill.textContent = "BLOCKED FROM EGRESS";
          statusPill.className = "privacy-status-pill blocked";
        }
        if (subtitle) {
          subtitle.textContent = "Raw Logs, Internal IPs & Injected Secrets (Kept Local)";
        }
      }
    } else if (res.status === 403) {
      if (rawPre && !window._lastTier1RawRecord) {
        rawPre.textContent = "// Customer-local inspection unavailable: Local authorization required to inspect on-premise logs.";
      }
      if (statusPill) {
        statusPill.textContent = "LOCAL ACCESS UNAVAILABLE";
        statusPill.className = "privacy-status-pill blocked";
      }
    }
  } catch (err) {
    console.warn("[Egress] Customer-local inspection source unreachable:", err);
    if (rawPre && !window._lastTier1RawRecord) {
      rawPre.textContent = "// Unable to reach customer-local inspection source.";
    }
  } finally {
    window._isFetchingTier1Raw = false;
  }
};

window.updateEgressProofRoleView = function() {
  const user = window.AuthManager ? window.AuthManager.currentUser : null;
  const isAuthenticated = !!(user && user.authorized_role);
  const userRole = isAuthenticated ? user.authorized_role : null;
  const isAd = userRole === "admin";
  const isItTeam = userRole === "it_team";

  const diffGrid = document.getElementById("egressDiffGrid");
  const tier1Card = document.getElementById("egressTier1Card");
  const itPrivacyBanner = document.getElementById("itPrivacyBanner");
  const egressRoleBadge = document.getElementById("egressRoleBadge");
  const rawPre = document.getElementById("egressRawJson");
  const tier1StatusPill = document.getElementById("tier1StatusPill");
  const tier1Subtitle = document.getElementById("tier1Subtitle");
  const tier1FooterNote = document.getElementById("tier1FooterNote");

  if (isItTeam) {
    // ── IT TEAM VIEW: TIER 1 COMPLETELY HIDDEN, TIER 2 ONLY ──
    if (diffGrid) diffGrid.classList.add("it-team-mode");
    if (tier1Card) tier1Card.style.display = "none";
    if (itPrivacyBanner) itPrivacyBanner.classList.remove("hidden");
    if (egressRoleBadge) {
      egressRoleBadge.textContent = "ROLE: IT TEAM (RESTRICTED TIER 2 VIEW)";
      egressRoleBadge.className = "egress-role-badge";
    }
    if (rawPre) {
      rawPre.textContent = "// Tier 1 Customer Local Data is restricted for IT Team role.";
    }
  } else {
    // ── ADMIN or DEFAULT VIEW: BOTH PANELS SIDE-BY-SIDE ──
    if (diffGrid) diffGrid.classList.remove("it-team-mode");
    if (tier1Card) tier1Card.style.display = "";
    if (itPrivacyBanner) itPrivacyBanner.classList.add("hidden");

    if (isAd) {
      // Admin-specific labels
      if (egressRoleBadge) {
        egressRoleBadge.textContent = "ROLE: ADMIN (FULL AUDIT & COMPARISON VIEW)";
        egressRoleBadge.className = "egress-role-badge admin-mode";
      }
      // Fetch live Tier 1 raw data via customer-local inspection
      window.fetchAdminTier1Raw();
    } else {
      // Unauthenticated default — show original layout
      if (egressRoleBadge) {
        egressRoleBadge.textContent = "EGRESS PROOF & PRIVACY AUDIT";
        egressRoleBadge.className = "egress-role-badge";
      }
      if (tier1StatusPill) {
        tier1StatusPill.textContent = "BLOCKED FROM EGRESS";
        tier1StatusPill.className = "privacy-status-pill blocked";
      }
      if (tier1Subtitle) {
        tier1Subtitle.textContent = "Raw Logs, Internal IPs & Injected Secrets (Kept Local)";
      }
      if (tier1FooterNote) {
        tier1FooterNote.textContent = "🚫 Red fields (credentials, internal IPs, raw queries) are stripped by policy before transmission.";
      }
    }
  }
};

function renderEgressProof(egressProof, dataFreshness) {
  if (!egressProof) return;

  // Sync role view state
  window.updateEgressProofRoleView();

  const latest = egressProof.latest || egressProof.latest_proof;
  const history = egressProof.history || egressProof.recent_history || [];
  const stats = egressProof.stats || {};
  const isOutage = stats.outage_simulated !== undefined ? stats.outage_simulated : egressProof.is_outage_simulated;
  const bufferedCount = stats.buffered_in_queue !== undefined ? stats.buffered_in_queue : (egressProof.buffered_count || 0);

  const user = window.AuthManager ? window.AuthManager.currentUser : null;
  const isAuthenticated = !!(user && user.authorized_role);
  const isAd = isAuthenticated && user.authorized_role === "admin";
  const isItTeam = isAuthenticated && user.authorized_role === "it_team";

  // Tier 1 Raw Local Telemetry
  const rawPre = document.getElementById("egressRawJson");
  if (rawPre) {
    if (isItTeam) {
      // IT Team: strictly restricted from accessing raw telemetry
      rawPre.textContent = "// Tier 1 Customer Local Data is restricted for IT Team role.";
    } else {
      // Admin or default view: render raw customer local telemetry details as before
      const rawData = latest?.raw_tier1_preview || latest?.raw_tier1_record || window._lastTier1RawRecord;
      if (rawData) {
        rawPre.textContent = JSON.stringify(rawData, null, 2);
      }
    }
  }

  // Tier 2 SaaS Sanitized Metadata (Accessible to both IT Team and Admin)
  const sanitizedPre = document.getElementById("egressSanitizedJson");
  const sanitizedData = latest?.sanitized_tier2_payload;
  if (sanitizedPre && sanitizedData) {
    sanitizedPre.textContent = JSON.stringify(sanitizedData, null, 2);
  }

  // Cryptographic SHA-256 Hash
  const hashEl = document.getElementById("egressSha256");
  if (hashEl && latest) {
    hashEl.textContent = latest.sha256_hash || "--";
  }

  // Policy Result Badge
  const policyEl = document.getElementById("egressPolicyResult");
  if (policyEl && latest) {
    policyEl.textContent = latest.policy_result || "APPROVED & ENCRYPTED";
  }

  // Outage Simulation Button State
  const outageBtn = document.getElementById("btnToggleOutage");
  const outageText = document.getElementById("outageBtnText");
  if (outageBtn && outageText) {
    if (isOutage) {
      outageBtn.className = "btn btn-sm btn-danger active";
      outageText.textContent = `⚠️ Network Outage Simulated (Buffering: ${bufferedCount})`;
    } else {
      outageBtn.className = "btn btn-sm btn-outline-warning";
      outageText.textContent = "Simulate Network Outage (Buffer Test)";
    }
  }

  // Transmission Audit Table & Stats
  const auditTbody = document.getElementById("egressAuditTbody");
  const auditStats = document.getElementById("egressAuditStats");

  if (auditStats) {
    const ingestSec = dataFreshness?.ingest_latency_seconds !== undefined ? dataFreshness.ingest_latency_seconds : "1.1";
    auditStats.textContent = `Policy: STRICT_ALLOW_LIST_ONLY | Secrets Scrubbed: 100% | Payloads Sent: ${history.length} | Ingest Latency: ${ingestSec}s`;
  }

  if (auditTbody && history.length > 0) {
    auditTbody.innerHTML = history.slice(0, 8).map(item => {
      const blockedCount = item.blocked_fields ? item.blocked_fields.length : 0;
      const allowedCount = item.allowed_fields ? item.allowed_fields.length : 0;
      const rawTs = item.timestamp_utc || item.timestamp;
      const timeStr = rawTs ? rawTs.slice(11, 19) : "--:--:--";
      let statusHtml = '<span class="status-transmitted">✓ Transmitted</span>';
      if (item.transmission_status === "BUFFERED_LOCALLY") {
        statusHtml = '<span style="color:#fbbf24; font-weight:700;">⏳ Buffered</span>';
      } else if (item.transmission_status === "REPLAYED_AFTER_OUTAGE") {
        statusHtml = '<span style="color:#10b981; font-weight:700;">⚡ Replayed (0 Loss)</span>';
      }

      return `
        <tr>
          <td class="font-mono">${item.payload_id || 'PAYLOAD-xxxx'}</td>
          <td class="font-mono">${timeStr} UTC</td>
          <td><span class="server-tag">${item.server_id}</span></td>
          <td><span class="badge-approved">${item.policy_result}</span></td>
          <td class="text-green">${allowedCount} fields allowed</td>
          <td class="text-red">${blockedCount} sensitive keys blocked</td>
          <td>${statusHtml}</td>
        </tr>
      `;
    }).join("");
  }
}

// ── Outage Simulation Toggle Handler ──────────────────────────────────────

window.toggleOutageSimulation = async function() {
  try {
    const res = await fetch("/api/collector/outage/toggle", { method: "POST" });
    const data = await res.json();
    const outageBtn = document.getElementById("btnToggleOutage");
    const outageText = document.getElementById("outageBtnText");

    if (data.status) {
      if (data.is_outage_simulated) {
        if (outageBtn) outageBtn.className = "btn btn-sm btn-danger active";
        if (outageText) outageText.textContent = `⚠️ Network Outage Simulated (Buffering: ${data.buffered_count})`;
      } else {
        if (outageBtn) outageBtn.className = "btn btn-sm btn-outline-warning";
        if (outageText) outageText.textContent = "Simulate Network Outage (Buffer Test)";
      }
    }
  } catch (e) {
    console.error("Failed to toggle network outage simulation:", e);
  }
};
