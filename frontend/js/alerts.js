/**
 * Alerts & Correlated Incidents View
 * Demonstrates how multiple raw alerts correlate into unified high-level incidents.
 */
async function loadAlerts() {
  const [alerts, incidents] = await Promise.all([
    apiGet("/api/alerts?limit=50"),
    apiGet("/api/incidents"),
  ]);

  // Render Incidents Panel
  const incContainer = document.getElementById("incidents-list");
  if (incContainer && incidents) {
    incContainer.innerHTML = incidents.map(inc => `
      <div class="panel" style="border-left: 4px solid ${inc.severity === 'critical' ? 'var(--status-poor)' : 'var(--status-fair)'};">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h4>${inc.title}</h4>
          ${renderSeverityBadge(inc.severity)}
        </div>
        <p style="margin: 0.5rem 0; font-size: 0.85rem; color: var(--text-secondary);">${inc.summary}</p>
        <div style="display:flex; gap: 1rem; font-size: 0.75rem; color: var(--text-muted);">
          <span>Incident ID: <strong>${inc.incident_id}</strong></span>
          <span>Correlated Alerts: <strong>${inc.alert_count}</strong></span>
          <span>Status: <strong>${inc.status.toUpperCase()}</strong></span>
          <span>Created: ${formatTimestamp(inc.created_at)}</span>
        </div>
      </div>
    `).join("") || `<p style="color: var(--text-muted);">No correlated incidents detected.</p>`;
  }

  // Render Raw Alert Log
  const tbody = document.getElementById("alerts-table-body");
  if (tbody && alerts) {
    tbody.innerHTML = alerts.map(a => `
      <tr>
        <td>${renderSeverityBadge(a.severity)}</td>
        <td><strong>${a.server_id}</strong></td>
        <td>${a.description}</td>
        <td><span class="badge badge-info">${a.detection_method.toUpperCase()}</span></td>
        <td>${formatTimestamp(a.created_at)}</td>
        <td><span class="badge ${a.status === 'active' ? 'badge-warning' : 'badge-excellent'}">${a.status.toUpperCase()}</span></td>
      </tr>
    `).join("") || `<tr><td colspan="6" style="text-align:center;">No active alerts.</td></tr>`;
  }
}

window.loadAlerts = loadAlerts;
