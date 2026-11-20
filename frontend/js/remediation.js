/**
 * Assisted & Autonomous Ops Remediation Simulator
 * Implements Stage 4 & Stage 5 of the Autonomous Ops Roadmap:
 * - Operator Approval Step
 * - Policy-bounded Simulated Action Execution
 * - Action Rollback
 * - Complete Audit Trail Recording
 */
async function loadRemediation() {
  const recommendations = await apiGet("/api/recommendations");
  if (!recommendations) return;

  const container = document.getElementById("remediation-actions-container");
  if (!container) return;

  container.innerHTML = recommendations.map(rec => {
    let actionButtons = '';
    const status = rec.approval_status;

    if (status === 'pending') {
      actionButtons = `
        <button class="btn btn-success btn-sm" onclick="approveRemediation('${rec.recommendation_id}')">Approve Action</button>
      `;
    } else if (status === 'approved') {
      actionButtons = `
        <button class="btn btn-sm" onclick="executeRemediation('${rec.recommendation_id}')">Simulate Execution</button>
      `;
    } else if (status === 'executed') {
      actionButtons = `
        <span class="badge badge-excellent" style="margin-right: 0.5rem;">SIMULATED EXECUTED</span>
        <button class="btn btn-danger btn-sm" onclick="rollbackRemediation('${rec.recommendation_id}')">Rollback Simulation</button>
      `;
    } else if (status === 'rolled_back') {
      actionButtons = `
        <span class="badge badge-warning">ROLLED BACK</span>
      `;
    }

    return `
      <div class="panel" style="margin-bottom: 1rem; border-left: 4px solid ${getStatusBorder(status)};">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h4>${rec.recommended_action}</h4>
          <span class="badge badge-info">${status.toUpperCase()}</span>
        </div>
        <p style="margin: 0.5rem 0; font-size: 0.85rem; color: var(--text-secondary);">${rec.explanation}</p>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top: 0.75rem;">
          <span style="font-size: 0.75rem; color: var(--text-muted);">
            ID: <strong>${rec.recommendation_id}</strong> | Incident: <strong>${rec.incident_id}</strong> | Created: ${formatTimestamp(rec.created_at)}
          </span>
          <div style="display:flex; gap: 0.5rem;">
            ${actionButtons}
          </div>
        </div>
      </div>
    `;
  }).join("") || `<p style="color: var(--text-muted);">No remediation actions currently queued.</p>`;
}

function getStatusBorder(status) {
  switch (status) {
    case 'approved': return 'var(--accent-color)';
    case 'executed': return 'var(--status-excellent)';
    case 'rolled_back': return 'var(--status-fair)';
    default: return 'var(--border-color)';
  }
}

async function approveRemediation(recId) {
  const res = await apiPost("/api/remediation/approve", {
    recommendation_id: recId,
    approved_by: "lead_operator",
  });
  if (res && res.status === "approved") {
    showToast("Remediation action approved successfully!", "success");
    loadRemediation();
  }
}

async function executeRemediation(recId) {
  const res = await apiPost("/api/remediation/execute", {
    recommendation_id: recId,
    executed_by: "lead_operator",
  });
  if (res && res.status === "executed") {
    showToast("Simulated remediation action executed!", "success");
    loadRemediation();
  }
}

async function rollbackRemediation(recId) {
  const res = await apiPost("/api/remediation/rollback", {
    recommendation_id: recId,
    rolled_back_by: "lead_operator",
    reason: "Operator initiated rollback in test simulation environment",
  });
  if (res && res.status === "rolled_back") {
    showToast("Remediation safely rolled back in simulation.", "warning");
    loadRemediation();
  }
}

window.loadRemediation = loadRemediation;
window.approveRemediation = approveRemediation;
window.executeRemediation = executeRemediation;
window.rollbackRemediation = rollbackRemediation;
