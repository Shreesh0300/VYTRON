/**
 * System Audit Trail View
 * Lists auditable security, transfer, remediation, and offline-detection actions.
 */
async function loadAudit() {
  const logs = await apiGet("/api/audit-logs?limit=50");
  if (!logs) return;

  const tbody = document.getElementById("audit-logs-table");
  if (tbody) {
    tbody.innerHTML = logs.map(l => `
      <tr>
        <td><strong>${l.audit_id}</strong></td>
        <td><span class="badge badge-info">${l.actor}</span></td>
        <td><strong>${l.action}</strong></td>
        <td>${l.resource_type}:${l.resource_id}</td>
        <td>${l.details || '--'}</td>
        <td>${formatTimestamp(l.timestamp)}</td>
      </tr>
    `).join("") || `<tr><td colspan="6" style="text-align:center;">No audit logs found.</td></tr>`;
  }
}

window.loadAudit = loadAudit;
