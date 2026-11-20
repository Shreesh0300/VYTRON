/**
 * Overview Dashboard View
 * Displays high-level health metrics, alert totals, and incident counts.
 */
let healthDoughnutChart = null;

async function loadOverview() {
  const [servers, collectors, alerts, incidents] = await Promise.all([
    apiGet("/api/servers"),
    apiGet("/api/collectors"),
    apiGet("/api/alerts?limit=10"),
    apiGet("/api/incidents"),
  ]);

  // Update stat cards
  const totalServers = servers ? servers.length : 10;
  const activeAlerts = alerts ? alerts.length : 0;
  const criticalIncidents = incidents ? incidents.filter(i => i.severity === "critical" && i.status === "open").length : 0;
  
  const onlineCollectors = collectors ? collectors.filter(c => c.status === "online").length : 0;
  const totalCollectors = collectors ? collectors.length : 1;

  document.getElementById("stat-server-count").innerText = totalServers;
  document.getElementById("stat-collector-status").innerText = `${onlineCollectors}/${totalCollectors} Online`;
  document.getElementById("stat-active-alerts").innerText = activeAlerts;
  document.getElementById("stat-open-incidents").innerText = criticalIncidents;

  // Render recent alerts table
  const tbody = document.getElementById("overview-alerts-table");
  if (tbody && alerts) {
    tbody.innerHTML = alerts.slice(0, 5).map(a => `
      <tr>
        <td>${renderSeverityBadge(a.severity)}</td>
        <td><strong>${a.server_id}</strong></td>
        <td>${a.description}</td>
        <td><span class="badge badge-info">${a.detection_method}</span></td>
        <td>${formatTimestamp(a.created_at)}</td>
      </tr>
    `).join("") || `<tr><td colspan="5" style="text-align:center;">No recent alerts</td></tr>`;
  }

  // Four-State health counter
  let states = { excellent: 0, good: 0, fair: 0, poor: 0 };
  if (servers) {
    servers.forEach(s => {
      let st = (s.status || "good").toLowerCase();
      if (st === "online") st = "excellent";
      else if (st === "warning") st = "fair";
      else if (st === "critical" || st === "offline") st = "poor";
      if (states[st] !== undefined) states[st]++;
      else states["good"]++;
    });
  }

  renderHealthChart(states);
}

function renderHealthChart(states) {
  const ctx = document.getElementById("healthDoughnut");
  if (!ctx) return;

  if (healthDoughnutChart) {
    healthDoughnutChart.data.datasets[0].data = [
      states.excellent,
      states.good,
      states.fair,
      states.poor,
    ];
    healthDoughnutChart.update();
    return;
  }

  healthDoughnutChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Excellent", "Good", "Fair", "Poor"],
      datasets: [{
        data: [states.excellent, states.good, states.fair, states.poor],
        backgroundColor: ["#10b981", "#3b82f6", "#f59e0b", "#ef4444"],
        borderColor: "#1f2937",
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#9ca3af" }
        }
      }
    }
  });
}

window.loadOverview = loadOverview;
