/**
 * Collector Fleet Health View
 * Verifies local Tier 1 collector vitality, heartbeats, and offline detection.
 */
async function loadCollectors() {
  const collectors = await apiGet("/api/collectors");
  if (!collectors) return;

  const container = document.getElementById("collectors-container");
  if (!container) return;

  container.innerHTML = collectors.map(c => `
    <div class="stat-card" style="border-left: 4px solid ${c.status === 'online' ? 'var(--status-excellent)' : 'var(--status-poor)'};">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="stat-label">COLLECTOR ID: <strong>${c.collector_id}</strong></span>
        ${c.status === 'online' ? '<span class="badge badge-excellent">ONLINE</span>' : '<span class="badge badge-poor">OFFLINE (POOR)</span>'}
      </div>
      <div style="margin-top: 0.5rem;">
        <p style="font-size: 0.85rem; color: var(--text-secondary);">Tenant: <strong>${c.tenant_id}</strong> | Version: <strong>v${c.software_version}</strong></p>
        <p style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem;">Configuration State: <strong>${c.configuration_status}</strong></p>
        <div style="margin-top: 0.75rem; display: flex; gap: 1.5rem;">
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted);">HOST CPU</span>
            <p style="font-weight: 700; font-size: 1.1rem;">${c.cpu_usage.toFixed(1)}%</p>
          </div>
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted);">HOST RAM</span>
            <p style="font-weight: 700; font-size: 1.1rem;">${c.memory_usage.toFixed(1)}%</p>
          </div>
          <div>
            <span style="font-size: 0.75rem; color: var(--text-muted);">LAST HEARTBEAT</span>
            <p style="font-size: 0.85rem; margin-top: 0.2rem;">${c.seconds_since_last_seen}s ago</p>
          </div>
        </div>
      </div>
      <div style="margin-top: 0.75rem; font-size: 0.7rem; color: var(--text-muted);">
        Timestamp: ${formatTimestamp(c.last_seen)}
      </div>
    </div>
  `).join("");
}

window.loadCollectors = loadCollectors;
