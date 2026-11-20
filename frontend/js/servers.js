/**
 * Upgraded Server Monitoring View
 * Features:
 * - 10 Independent simulated live server profiles
 * - Interactive Judge Demo Mode scenario triggers
 * - Quick Server Navigation Tabs Bar (click any server tab to switch)
 * - Live infrastructure fleet inventory with status & feed vitality
 * - Detailed server view with 10 real-time metrics, 4 Chart.js performance graphs
 * - Dynamic live operational log stream
 * - Fine-grained server fault injection controls
 */

let currentSelectedServer = "APP-01";

// 4 Chart.js Instances
let chartCpuMem = null;
let chartNetworkThroughput = null;
let chartWorkload = null;
let chartLatencyErrors = null;

/**
 * Format uptime seconds into human-readable e.g. "5d 14h 22m"
 */
function formatUptime(seconds) {
  if (!seconds || seconds <= 0) return "Offline";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${days}d ${hours}h ${minutes}m`;
}

/**
 * Render health state badge: ONLINE, WARNING, CRITICAL, OFFLINE
 */
function renderServerStatusBadge(status) {
  const s = (status || "ONLINE").toUpperCase();
  if (s === "ONLINE") {
    return `<span class="badge badge-online">ONLINE</span>`;
  } else if (s === "WARNING") {
    return `<span class="badge badge-warning">WARNING</span>`;
  } else if (s === "CRITICAL") {
    return `<span class="badge badge-critical">CRITICAL</span>`;
  } else {
    return `<span class="badge badge-offline">OFFLINE</span>`;
  }
}

/**
 * Render feed vitality badge: ACTIVE, DELAYED, LOST
 */
function renderFeedBadge(feed) {
  const f = (feed || "LOST").toUpperCase();
  if (f === "ACTIVE") {
    return `<span class="badge badge-active">ACTIVE</span>`;
  } else if (f === "DELAYED") {
    return `<span class="badge badge-delayed">DELAYED</span>`;
  } else {
    return `<span class="badge badge-lost">LOST</span>`;
  }
}

/**
 * Scroll smoothly back to top fleet table
 */
function scrollToFleetTable() {
  const table = document.getElementById("page-servers");
  if (table) {
    table.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

/**
 * Main servers inventory loader
 */
async function loadServers() {
  const [servers, demoState] = await Promise.all([
    apiGet("/api/servers"),
    apiGet("/api/demo/state"),
  ]);

  if (!servers) return;

  // 1. Update Demo Mode Active Scenario Banner
  const demoBanner = document.getElementById("demo-active-scenario-indicator");
  if (demoBanner && demoState) {
    const act = demoState.active_scenario || "Normal Operations";
    demoBanner.innerHTML = `Active: <strong>${act}</strong>`;
    if (act.toLowerCase().includes("normal") || act.toLowerCase().includes("recovery")) {
      demoBanner.className = "badge badge-excellent";
    } else if (act.toLowerCase().includes("cascade") || act.toLowerCase().includes("failure") || act.toLowerCase().includes("crash")) {
      demoBanner.className = "badge badge-critical";
    } else {
      demoBanner.className = "badge badge-warning";
    }
  }

  // 2. Count Fleet States
  let onlineCount = 0;
  let warnCount = 0;
  let critCount = 0;
  let offlineCount = 0;

  servers.forEach(s => {
    const st = (s.status || "ONLINE").toUpperCase();
    if (st === "ONLINE") onlineCount++;
    else if (st === "WARNING") warnCount++;
    else if (st === "CRITICAL") critCount++;
    else offlineCount++;
  });

  const fleetBadges = document.getElementById("fleet-summary-badges");
  if (fleetBadges) {
    fleetBadges.innerHTML = `
      <span class="badge badge-online">${onlineCount} Online</span>
      ${warnCount > 0 ? `<span class="badge badge-warning">${warnCount} Warning</span>` : ''}
      ${critCount > 0 ? `<span class="badge badge-critical">${critCount} Critical</span>` : ''}
      ${offlineCount > 0 ? `<span class="badge badge-offline">${offlineCount} Offline</span>` : ''}
    `;
  }

  // 3. Render Quick Server Navigation Tabs Bar
  const tabsContainer = document.getElementById("server-selector-tabs");
  if (tabsContainer) {
    tabsContainer.innerHTML = servers.map(s => {
      const isSelected = s.server_id === currentSelectedServer;
      const st = (s.status || "ONLINE").toUpperCase();
      let dotColor = "#10b981";
      if (st === "WARNING") dotColor = "#f59e0b";
      else if (st === "CRITICAL" || st === "OFFLINE") dotColor = "#ef4444";

      return `
        <button class="server-tab-btn ${isSelected ? 'active-tab' : ''}" onclick="selectServer('${s.server_id}')">
          <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: ${dotColor};"></span>
          <span>${s.server_id}</span>
        </button>
      `;
    }).join("");
  }

  // 4. Render Fleet Inventory Table
  const tbody = document.getElementById("servers-list-table");
  if (tbody) {
    tbody.innerHTML = servers.map(s => {
      const snap = s.snapshot || {};
      const cpu = snap.cpu_usage !== undefined ? snap.cpu_usage.toFixed(1) + "%" : "--";
      const mem = snap.memory_usage !== undefined ? snap.memory_usage.toFixed(1) + "%" : "--";
      const lat = snap.network_latency !== undefined ? snap.network_latency.toFixed(1) + "ms" : "--";
      const err = snap.error_rate !== undefined ? snap.error_rate.toFixed(1) + "%" : "--";

      const isSelected = s.server_id === currentSelectedServer;

      return `
        <tr data-server-id="${s.server_id}" style="cursor: pointer;" onclick="selectServer('${s.server_id}')" class="${isSelected ? 'selected-row' : ''}">
          <td><strong style="color: #60a5fa;">${s.server_id}</strong></td>
          <td>
            <div style="font-weight: 600;">${s.server_name}</div>
            <div style="font-size: 0.72rem; color: var(--text-secondary);">${s.role}</div>
          </td>
          <td><span class="badge badge-info">${s.server_type}</span></td>
          <td>${renderServerStatusBadge(s.status)}</td>
          <td>${renderFeedBadge(s.feed_status)}</td>
          <td>
            <div style="font-size: 0.75rem;">
              <span>CPU: <strong>${cpu}</strong></span> | 
              <span>RAM: <strong>${mem}</strong></span> | 
              <span>Lat: <strong>${lat}</strong></span> | 
              <span style="${parseFloat(err) > 5 ? 'color: #f87171;' : ''}">Err: <strong>${err}</strong></span>
            </div>
          </td>
          <td>${formatTimestamp(s.last_metric_time)}</td>
          <td>
            <button class="btn btn-sm" onclick="selectServer('${s.server_id}'); event.stopPropagation();">
              Inspect ${s.server_id}
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  // 5. Load Detailed View for Current Selection
  await loadServerDetail(currentSelectedServer);
}

/**
 * Handle user server selection: updates tabs, table highlight, loads data, and scrolls into view
 */
function selectServer(serverId) {
  currentSelectedServer = serverId;

  // 1. Update Table Row Selection Highlight
  const tbody = document.getElementById("servers-list-table");
  if (tbody) {
    const rows = tbody.querySelectorAll("tr");
    rows.forEach(r => {
      if (r.getAttribute("data-server-id") === serverId) {
        r.classList.add("selected-row");
      } else {
        r.classList.remove("selected-row");
      }
    });
  }

  // 2. Update Tabs Bar Highlight
  const tabsContainer = document.getElementById("server-selector-tabs");
  if (tabsContainer) {
    const tabBtns = tabsContainer.querySelectorAll(".server-tab-btn");
    tabBtns.forEach(btn => {
      if (btn.innerText.includes(serverId)) {
        btn.classList.add("active-tab");
      } else {
        btn.classList.remove("active-tab");
      }
    });
  }

  // 3. Immediately Load Server Detail
  loadServerDetail(serverId);

  // 4. Smoothly bring the detail section into view with a visual pulse
  const detailSec = document.getElementById("server-detail-section");
  if (detailSec) {
    detailSec.scrollIntoView({ behavior: "smooth", block: "start" });
    detailSec.classList.remove("highlight-pulse");
    void detailSec.offsetWidth; // trigger reflow
    detailSec.classList.add("highlight-pulse");
  }
}

/**
 * Load single server detailed view, metrics, charts, and logs
 */
async function loadServerDetail(serverId) {
  const detail = await apiGet(`/api/servers/${serverId}/detail`);
  if (!detail) return;

  // 1. Header & Identity
  const elId = document.getElementById("detail-server-id");
  if (elId) elId.innerText = detail.server_id;

  const elName = document.getElementById("detail-server-name");
  if (elName) elName.innerText = detail.server_name;

  const elRole = document.getElementById("detail-server-role");
  if (elRole) elRole.innerText = `${detail.role} — ${detail.server_type.toUpperCase()}`;

  const elStatus = document.getElementById("detail-server-status-badge");
  if (elStatus) {
    const st = (detail.status || "ONLINE").toLowerCase();
    elStatus.className = `badge badge-${st}`;
    elStatus.innerText = st.toUpperCase();
  }

  const elFeed = document.getElementById("detail-server-feed-badge");
  if (elFeed) {
    const feed = (detail.feed_status || "ACTIVE").toLowerCase();
    elFeed.className = `badge badge-${feed}`;
    elFeed.innerText = `FEED ${feed.toUpperCase()}`;
  }

  const elActivity = document.getElementById("detail-server-activity");
  if (elActivity) elActivity.innerText = detail.activity || "Serving operational workload";

  const elUptime = document.getElementById("detail-server-uptime");
  if (elUptime) elUptime.innerText = `Uptime: ${formatUptime(detail.uptime)}`;

  const elTermTitle = document.getElementById("terminal-server-title");
  if (elTermTitle) elTermTitle.innerText = `${detail.server_id} (${detail.server_name})`;

  // 2. 10 Core Metric Cards
  const m = detail.metrics || {};
  const setCard = (id, val, suffix = "") => {
    const el = document.getElementById(id);
    if (el) el.innerText = val !== undefined && val !== null ? `${val}${suffix}` : "--";
  };

  setCard("card-cpu-val", m.cpu_usage ? m.cpu_usage.toFixed(1) : "--", "%");
  setCard("card-mem-val", m.memory_usage ? m.memory_usage.toFixed(1) : "--", "%");
  setCard("card-disk-val", m.disk_usage ? m.disk_usage.toFixed(1) : "--", "%");
  setCard("card-netup-val", m.network_upload ? m.network_upload.toFixed(1) : "--", " KB/s");
  setCard("card-netdown-val", m.network_download ? m.network_download.toFixed(1) : "--", " KB/s");
  setCard("card-lat-val", m.network_latency ? m.network_latency.toFixed(1) : "--", " ms");
  setCard("card-req-val", m.request_rate ? m.request_rate.toFixed(1) : "--", " /s");
  setCard("card-err-val", m.error_rate !== undefined ? m.error_rate.toFixed(2) : "--", "%");
  setCard("card-resp-val", m.response_time ? m.response_time.toFixed(1) : "--", " ms");
  setCard("card-avail-val", m.service_availability !== undefined ? (m.service_availability > 0 ? "100%" : "0% (OFFLINE)") : "100%");

  // 3. Operational Terminal Logs
  const termBody = document.getElementById("server-terminal-logs");
  if (termBody && detail.recent_logs && detail.recent_logs.length > 0) {
    termBody.innerHTML = detail.recent_logs.map(log => {
      const lvl = (log.level || "INFO").toLowerCase();
      return `
        <div class="log-line">
          <span class="log-ts">${log.timestamp || '00:00:00'}</span>
          <span class="log-lvl-${lvl}">[${(log.level || 'INFO').toUpperCase()}]</span>
          <span class="log-msg">${log.message}</span>
        </div>
      `;
    }).join("");
    termBody.scrollTop = termBody.scrollHeight;
  }

  // 4. Alerts and Incidents for this server
  const alertsList = document.getElementById("server-detail-alerts-list");
  if (alertsList) {
    if (detail.alerts && detail.alerts.length > 0) {
      alertsList.innerHTML = detail.alerts.map(a => `
        <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
          <div>
            <span class="badge badge-${a.severity}">${a.severity.toUpperCase()}</span>
            <span style="font-size: 0.82rem; margin-left: 0.4rem;">${a.description}</span>
          </div>
          <span style="font-size: 0.72rem; color: var(--text-muted);">${formatTimestamp(a.created_at)}</span>
        </div>
      `).join("");
    } else {
      alertsList.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem 0;">All thresholds nominal. No active alerts on ${serverId}.</p>`;
    }
  }

  const incList = document.getElementById("server-detail-incidents-list");
  if (incList) {
    if (detail.incidents && detail.incidents.length > 0) {
      incList.innerHTML = detail.incidents.map(inc => `
        <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
          <div>
            <span class="badge badge-${inc.severity}">${inc.severity.toUpperCase()}</span>
            <span style="font-size: 0.82rem; font-weight: 600; margin-left: 0.4rem;">${inc.title}</span>
          </div>
          <span class="badge badge-warning">${inc.status.toUpperCase()}</span>
        </div>
      `).join("");
    } else {
      incList.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem 0;">No active correlated incident clusters for ${serverId}.</p>`;
    }
  }

  // 5. Render 4 Chart.js Charts
  await renderServerCharts(serverId);
}

/**
 * Render the 4 Chart.js charts with real historical time-series telemetry
 */
async function renderServerCharts(serverId) {
  const metrics = await apiGet(`/api/metrics?server_id=${serverId}&limit=120`);
  if (!metrics || metrics.length === 0) return;

  // Group metrics by name and reverse for chronological order
  const groupBy = (name) => metrics.filter(m => m.metric_name === name).reverse();

  const cpuData = groupBy("cpu_usage");
  const memData = groupBy("memory_usage");
  const upData = groupBy("network_upload");
  const downData = groupBy("network_download");
  const respData = groupBy("response_time");
  const reqData = groupBy("request_rate");
  const latData = groupBy("network_latency");
  const errData = groupBy("error_rate");

  // Derive common labels from timestamps
  const baseSeries = cpuData.length > 0 ? cpuData : (memData.length > 0 ? memData : metrics.slice(0, 20).reverse());
  const labels = baseSeries.map(m => new Date(m.event_timestamp).toLocaleTimeString());

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
    scales: {
      y: {
        grid: { color: "#1f2937" },
        ticks: { color: "#9ca3af", font: { size: 10 } }
      },
      x: {
        grid: { color: "#1f2937" },
        ticks: { color: "#9ca3af", font: { size: 10 }, maxTicksLimit: 8 }
      }
    },
    plugins: {
      legend: { labels: { color: "#f9fafb", boxWidth: 12, font: { size: 11 } } }
    }
  };

  // ── Chart 1: CPU & Memory Utilization ─────────────────────────────────
  const ctxCpu = document.getElementById("chartCpuMem");
  if (ctxCpu) {
    const cpuVals = cpuData.map(m => m.metric_value);
    const memVals = memData.map(m => m.metric_value);

    if (chartCpuMem) {
      chartCpuMem.data.labels = labels;
      chartCpuMem.data.datasets[0].label = `${serverId} CPU Usage (%)`;
      chartCpuMem.data.datasets[0].data = cpuVals;
      chartCpuMem.data.datasets[1].label = `${serverId} Memory Usage (%)`;
      chartCpuMem.data.datasets[1].data = memVals;
      chartCpuMem.update();
    } else {
      chartCpuMem = new Chart(ctxCpu, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: `${serverId} CPU Usage (%)`,
              data: cpuVals,
              borderColor: "#ef4444",
              backgroundColor: "rgba(239, 68, 68, 0.12)",
              tension: 0.3,
              fill: true,
              pointRadius: 2,
            },
            {
              label: `${serverId} Memory Usage (%)`,
              data: memVals,
              borderColor: "#3b82f6",
              backgroundColor: "rgba(59, 130, 246, 0.12)",
              tension: 0.3,
              fill: true,
              pointRadius: 2,
            }
          ]
        },
        options: {
          ...chartOptions,
          scales: {
            ...chartOptions.scales,
            y: { ...chartOptions.scales.y, min: 0, max: 100 }
          }
        }
      });
    }
  }

  // ── Chart 2: Network Upload & Download ────────────────────────────────
  const ctxNet = document.getElementById("chartNetworkThroughput");
  if (ctxNet) {
    const upVals = upData.map(m => m.metric_value);
    const downVals = downData.map(m => m.metric_value);

    if (chartNetworkThroughput) {
      chartNetworkThroughput.data.labels = labels;
      chartNetworkThroughput.data.datasets[0].label = `${serverId} Upload (KB/s)`;
      chartNetworkThroughput.data.datasets[0].data = upVals;
      chartNetworkThroughput.data.datasets[1].label = `${serverId} Download (KB/s)`;
      chartNetworkThroughput.data.datasets[1].data = downVals;
      chartNetworkThroughput.update();
    } else {
      chartNetworkThroughput = new Chart(ctxNet, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: `${serverId} Upload (KB/s)`,
              data: upVals,
              borderColor: "#06b6d4",
              backgroundColor: "rgba(6, 182, 212, 0.1)",
              tension: 0.3,
              fill: true,
              pointRadius: 2,
            },
            {
              label: `${serverId} Download (KB/s)`,
              data: downVals,
              borderColor: "#8b5cf6",
              backgroundColor: "rgba(139, 92, 246, 0.1)",
              tension: 0.3,
              fill: true,
              pointRadius: 2,
            }
          ]
        },
        options: chartOptions
      });
    }
  }

  // ── Chart 3: Workload & Response Time ─────────────────────────────────
  const ctxWorkload = document.getElementById("chartWorkload");
  if (ctxWorkload) {
    const respVals = respData.map(m => m.metric_value);
    const reqVals = reqData.map(m => m.metric_value);

    if (chartWorkload) {
      chartWorkload.data.labels = labels;
      chartWorkload.data.datasets[0].label = `${serverId} Response Time (ms)`;
      chartWorkload.data.datasets[0].data = respVals;
      chartWorkload.data.datasets[1].label = `${serverId} Request Rate (req/s)`;
      chartWorkload.data.datasets[1].data = reqVals;
      chartWorkload.update();
    } else {
      chartWorkload = new Chart(ctxWorkload, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: `${serverId} Response Time (ms)`,
              data: respVals,
              borderColor: "#f59e0b",
              backgroundColor: "rgba(245, 158, 11, 0.1)",
              tension: 0.3,
              fill: true,
              pointRadius: 2,
              yAxisID: "y",
            },
            {
              label: `${serverId} Request Rate (req/s)`,
              data: reqVals,
              borderColor: "#10b981",
              backgroundColor: "transparent",
              tension: 0.3,
              borderDash: [4, 4],
              pointRadius: 2,
              yAxisID: "y1",
            }
          ]
        },
        options: {
          ...chartOptions,
          scales: {
            y: {
              ...chartOptions.scales.y,
              title: { display: true, text: "ms", color: "#f59e0b" }
            },
            y1: {
              position: "right",
              grid: { drawOnChartArea: false },
              ticks: { color: "#10b981", font: { size: 10 } },
              title: { display: true, text: "req/s", color: "#10b981" }
            },
            x: chartOptions.scales.x
          }
        }
      });
    }
  }

  // ── Chart 4: Latency & Error Rate ─────────────────────────────────────
  const ctxLatErr = document.getElementById("chartLatencyErrors");
  if (ctxLatErr) {
    const latVals = latData.map(m => m.metric_value);
    const errVals = errData.map(m => m.metric_value);

    if (chartLatencyErrors) {
      chartLatencyErrors.data.labels = labels;
      chartLatencyErrors.data.datasets[0].label = `${serverId} Network Latency (ms)`;
      chartLatencyErrors.data.datasets[0].data = latVals;
      chartLatencyErrors.data.datasets[1].label = `${serverId} Error Rate (%)`;
      chartLatencyErrors.data.datasets[1].data = errVals;
      chartLatencyErrors.update();
    } else {
      chartLatencyErrors = new Chart(ctxLatErr, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: `${serverId} Network Latency (ms)`,
              data: latVals,
              borderColor: "#f97316",
              backgroundColor: "rgba(249, 115, 22, 0.1)",
              tension: 0.3,
              fill: true,
              pointRadius: 2,
              yAxisID: "y",
            },
            {
              label: `${serverId} Error Rate (%)`,
              data: errVals,
              borderColor: "#f43f5e",
              backgroundColor: "rgba(244, 63, 94, 0.2)",
              tension: 0.3,
              fill: true,
              pointRadius: 2,
              yAxisID: "y1",
            }
          ]
        },
        options: {
          ...chartOptions,
          scales: {
            y: {
              ...chartOptions.scales.y,
              title: { display: true, text: "Latency ms", color: "#f97316" }
            },
            y1: {
              position: "right",
              grid: { drawOnChartArea: false },
              ticks: { color: "#f43f5e", font: { size: 10 } },
              title: { display: true, text: "Errors %", color: "#f43f5e" }
            },
            x: chartOptions.scales.x
          }
        }
      });
    }
  }
}

/**
 * Trigger Judge Demo Scenario
 */
async function triggerDemoScenario(scenarioName) {
  showToast(`Injecting scenario: ${scenarioName}...`, "info");
  const res = await apiPost("/api/demo/scenario", { scenario: scenarioName });
  if (res) {
    showToast(`Scenario active: ${res.active_scenario || scenarioName}`, "success");
    setTimeout(() => { loadServers(); }, 500);
  }
}

/**
 * Fine-grained server fault injection controls
 */
async function sendServerControl(action, metric = null, value = null) {
  showToast(`Applying ${action} to ${currentSelectedServer}...`, "info");
  const res = await apiPost(`/api/servers/${currentSelectedServer}/control`, {
    action: action,
    metric: metric,
    value: value,
  });
  if (res) {
    showToast(`Control executed on ${currentSelectedServer}`, "success");
    setTimeout(() => { loadServers(); }, 500);
  }
}

// Window exports
window.loadServers = loadServers;
window.selectServer = selectServer;
window.scrollToFleetTable = scrollToFleetTable;
window.triggerDemoScenario = triggerDemoScenario;
window.sendServerControl = sendServerControl;
