/**
 * Server Monitoring View
 * Shows the 10 server profiles with real-time performance line charts (CPU/RAM/Disk).
 */
let serverMetricChart = null;
let currentSelectedServer = "APP-01";

async function loadServers() {
  const servers = await apiGet("/api/servers");
  if (!servers) return;

  const tbody = document.getElementById("servers-list-table");
  if (tbody) {
    tbody.innerHTML = servers.map(s => `
      <tr style="cursor: pointer;" onclick="selectServer('${s.server_id}')" class="${s.server_id === currentSelectedServer ? 'selected-row' : ''}">
        <td><strong>${s.server_id}</strong></td>
        <td>${s.server_name}</td>
        <td><span class="badge badge-info">${s.server_type}</span></td>
        <td>${renderHealthBadge(s.status)}</td>
        <td>${s.is_stale ? '<span class="text-warning">Stale (>60s)</span>' : '<span class="text-success">Live</span>'}</td>
        <td>${formatTimestamp(s.last_metric_time)}</td>
      </tr>
    `).join("");
  }

  loadServerMetrics(currentSelectedServer);
}

function selectServer(serverId) {
  currentSelectedServer = serverId;
  document.getElementById("selected-server-header").innerText = `Telemetry Trend: ${serverId}`;
  loadServerMetrics(serverId);
}

async function loadServerMetrics(serverId) {
  const metrics = await apiGet(`/api/metrics?server_id=${serverId}&limit=30`);
  if (!metrics) return;

  // Group metrics by name
  const cpuData = metrics.filter(m => m.metric_name === "cpu_usage").reverse();
  const memData = metrics.filter(m => m.metric_name === "memory_usage").reverse();

  const labels = cpuData.map(m => new Date(m.event_timestamp).toLocaleTimeString());
  const cpuVals = cpuData.map(m => m.metric_value);
  const memVals = memData.map(m => m.metric_value);

  const ctx = document.getElementById("serverMetricsChart");
  if (!ctx) return;

  if (serverMetricChart) {
    serverMetricChart.data.labels = labels;
    serverMetricChart.data.datasets[0].data = cpuVals;
    serverMetricChart.data.datasets[1].data = memVals;
    serverMetricChart.update();
    return;
  }

  serverMetricChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "CPU Usage (%)",
          data: cpuVals,
          borderColor: "#ef4444",
          backgroundColor: "rgba(239, 68, 68, 0.1)",
          tension: 0.3,
          fill: true,
        },
        {
          label: "Memory Usage (%)",
          data: memVals,
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59, 130, 246, 0.1)",
          tension: 0.3,
          fill: true,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          max: 100,
          grid: { color: "#374151" },
          ticks: { color: "#9ca3af" }
        },
        x: {
          grid: { color: "#374151" },
          ticks: { color: "#9ca3af" }
        }
      },
      plugins: {
        legend: { labels: { color: "#f9fafb" } }
      }
    }
  });
}

window.loadServers = loadServers;
window.selectServer = selectServer;
