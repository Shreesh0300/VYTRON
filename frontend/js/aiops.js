/**
 * AIOps Insights View
 * Displays Rule-based evidence, Statistical anomaly evidence (z-score/baselines),
 * and Explainable LLM-driven incident analysis.
 */
async function loadAIOps() {
  const insights = await apiGet("/api/aiops/insights");
  if (!insights) return;

  // 1. Rule Evidence
  const ruleContainer = document.getElementById("aiops-rules-evidence");
  if (ruleContainer) {
    ruleContainer.innerHTML = insights.rule_based_evidence.slice(0, 5).map(e => `
      <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-color); font-size: 0.8rem;">
        <span class="badge badge-warning">RULE</span>
        <strong>${e.server_id}</strong>: ${e.description}
      </div>
    `).join("") || `<p style="font-size:0.8rem; color: var(--text-muted);">No threshold violations.</p>`;
  }

  // 2. Statistical Baseline Evidence
  const statContainer = document.getElementById("aiops-stats-evidence");
  if (statContainer) {
    statContainer.innerHTML = insights.statistical_evidence.slice(0, 5).map(e => `
      <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-color); font-size: 0.8rem;">
        <span class="badge badge-critical">Z-SCORE ANOMALY</span>
        <strong>${e.server_id}</strong>: ${e.description}
      </div>
    `).join("") || `<p style="font-size:0.8rem; color: var(--text-muted);">Baseline normal. No statistical deviations.</p>`;
  }

  // 3. LLM Explainable Recommendations
  const llmContainer = document.getElementById("aiops-recommendations");
  if (llmContainer) {
    llmContainer.innerHTML = insights.recommendations.map(r => `
      <div class="panel" style="margin-bottom: 1rem; border-left: 4px solid var(--accent-color);">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h5>${r.recommended_action}</h5>
          ${r.llm_generated ? '<span class="badge badge-info">LLM-POWERED INSIGHT</span>' : '<span class="badge badge-warning">STATIC RULE</span>'}
        </div>
        <p style="margin: 0.5rem 0; font-size: 0.85rem; color: var(--text-secondary);">${r.explanation}</p>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top: 0.5rem;">
          <span style="font-size: 0.75rem; color: var(--text-muted);">Linked to: <strong>${r.incident_id}</strong> | Status: <strong>${r.approval_status.toUpperCase()}</strong></span>
          <button class="btn btn-sm" onclick="navigateToRemediation('${r.recommendation_id}')">View Remediation Action</button>
        </div>
      </div>
    `).join("") || `<p style="color: var(--text-muted);">No recommendations currently pending.</p>`;
  }
}

function navigateToRemediation(recId) {
  const remNav = document.querySelector('.nav-item[data-page="remediation"]');
  if (remNav) remNav.click();
}

window.loadAIOps = loadAIOps;
window.navigateToRemediation = navigateToRemediation;
