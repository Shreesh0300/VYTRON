/**
 * VYTRON — Incident Diagnostic & RAG-Powered AI Troubleshooting Modal Handler
 */

const IncidentModal = {
  backdrop: null,
  closeBtn: null,
  ackBtn: null,
  aiBtn: null,
  aiSection: null,
  aiLoading: null,
  aiContent: null,
  currentIncident: null,

  init() {
    this.backdrop = document.getElementById("incidentModalBackdrop");
    this.closeBtn = document.getElementById("modalCloseBtn");
    this.ackBtn = document.getElementById("modalAcknowledgeBtn");
    this.aiBtn = document.getElementById("btnInvestigateAi");
    this.aiSection = document.getElementById("modalAiSection");
    this.aiLoading = document.getElementById("modalAiLoading");
    this.aiContent = document.getElementById("modalAiContent");

    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", () => this.close());
    }
    if (this.ackBtn) {
      this.ackBtn.addEventListener("click", () => this.close());
    }
    if (this.aiBtn) {
      this.aiBtn.addEventListener("click", () => this.runAiInvestigation());
    }
    if (this.backdrop) {
      this.backdrop.addEventListener("click", (e) => {
        if (e.target === this.backdrop) {
          this.close();
        }
      });
    }

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen()) {
        this.close();
      }
    });
  },

  isOpen() {
    return this.backdrop && this.backdrop.classList.contains("open");
  },

  open(incident) {
    if (!this.backdrop || !incident) return;
    this.currentIncident = incident;

    // Reset AI troubleshooting state
    if (this.aiLoading) this.aiLoading.style.display = "none";
    if (this.aiContent) {
      this.aiContent.style.display = "none";
      this.aiContent.innerHTML = "";
    }
    if (this.aiBtn) {
      this.aiBtn.disabled = false;
      this.aiBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
        Investigate with AI
      `;
    }

    // Populate standard incident fields
    const modalPrio = document.getElementById("modalPriorityBadge");
    const modalIncId = document.getElementById("modalIncidentId");
    const modalServerLabel = document.getElementById("modalServerLabel");
    const modalSeverity = document.getElementById("modalSeverity");
    const modalStatus = document.getElementById("modalStatus");
    const modalTimeDetected = document.getElementById("modalTimeDetected");
    const modalTimeResolved = document.getElementById("modalTimeResolved");
    const modalObserved = document.getElementById("modalObserved");
    const modalThreshold = document.getElementById("modalThreshold");
    const modalParamName = document.getElementById("modalParamName");
    const modalIssueDesc = document.getElementById("modalIssueDesc");
    const modalAction = document.getElementById("modalRecommendedAction");

    const prio = incident.priority || "P3";
    if (modalPrio) {
      modalPrio.textContent = prio;
      modalPrio.className = `priority-badge-modal prio-${prio.toLowerCase()}`;
    }

    if (modalIncId) modalIncId.textContent = incident.incident_id || "INC-2026-XXXX";
    if (modalServerLabel) {
      modalServerLabel.textContent = `${incident.server_id} — ${incident.server_name || "Server"} (${incident.server_type || "Node"})`;
    }

    if (modalSeverity) modalSeverity.textContent = incident.severity || "MEDIUM";
    if (modalStatus) {
      modalStatus.textContent = incident.status || "OPEN";
      modalStatus.style.color = incident.status === "OPEN" ? "#f87171" : "#34d399";
    }

    if (modalTimeDetected) modalTimeDetected.textContent = incident.created_at_str || "--:--:--";
    if (modalTimeResolved) modalTimeResolved.textContent = incident.resolved_at_str || "In Progress (Active)";

    if (modalObserved) modalObserved.textContent = `${incident.observed_value} ${incident.unit || ""}`;
    if (modalThreshold) modalThreshold.textContent = `${incident.threshold_value} ${incident.unit || ""}`;
    if (modalParamName) modalParamName.textContent = incident.metric_name || incident.metric_key || "Metric";
    if (modalIssueDesc) modalIssueDesc.textContent = incident.issue_description || "Threshold breach detected by real-time detector.";

    if (modalAction) modalAction.textContent = incident.recommended_action || "Investigate telemetry and normalize server workload.";

    this.backdrop.classList.add("open");
  },

  close() {
    if (this.backdrop) {
      this.backdrop.classList.remove("open");
    }
  },

  async runAiInvestigation() {
    if (!this.currentIncident || !this.aiBtn) return;

    // Show loading state
    this.aiBtn.disabled = true;
    this.aiBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
        <circle cx="12" cy="12" r="10"></circle>
      </svg>
      Analyzing with RAG...
    `;

    if (this.aiLoading) this.aiLoading.style.display = "flex";
    if (this.aiContent) this.aiContent.style.display = "none";

    try {
      const res = await fetch("/api/aiops/troubleshoot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident: this.currentIncident }),
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const guidance = await res.json();
      this.renderAiGuidance(guidance);
    } catch (err) {
      console.error("Failed to run AI investigation:", err);
      if (this.aiContent) {
        this.aiContent.innerHTML = `
          <div class="ai-card-section" style="border-color: rgba(239, 68, 68, 0.4);">
            <div class="ai-card-title" style="color: #f87171;">Investigation Error</div>
            <p class="ai-text-block">Failed to connect to AI troubleshooting pipeline: ${err.message}. Please verify the backend service.</p>
          </div>
        `;
        this.aiContent.style.display = "flex";
      }
    } finally {
      if (this.aiLoading) this.aiLoading.style.display = "none";
      if (this.aiBtn) {
        this.aiBtn.disabled = false;
        this.aiBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          Re-Analyze
        `;
      }
    }
  },

  renderAiGuidance(guidance) {
    if (!this.aiContent || !guidance) return;

    // Format 1. Incident Explanation
    const explanationHtml = `
      <div class="ai-card-section">
        <div class="ai-card-title">1. Incident Explanation</div>
        <p class="ai-text-block">${guidance.explanation || "No explanation provided."}</p>
      </div>
    `;

    // Format 2. Possible Root Causes
    const causesList = (guidance.possible_root_causes || [])
      .map(c => `<li>${c}</li>`)
      .join("");
    const causesHtml = `
      <div class="ai-card-section">
        <div class="ai-card-header">
          <span class="ai-card-title">2. Possible Root Causes</span>
          <span class="ai-badge-hypo">Hypotheses — Not Confirmed Facts</span>
        </div>
        <ul class="ai-list">${causesList || "<li>Requires manual triage.</li>"}</ul>
      </div>
    `;

    // Format 3. Telemetry Evidence
    const evidenceList = (guidance.telemetry_evidence || [])
      .map(e => `<li>${e}</li>`)
      .join("");
    const evidenceHtml = `
      <div class="ai-card-section">
        <div class="ai-card-title">3. Supporting Telemetry Evidence</div>
        <ul class="ai-list">${evidenceList || "<li>Telemetry within standard parameters.</li>"}</ul>
      </div>
    `;

    // Format 4. Investigation Steps
    const stepsList = (guidance.investigation_steps || [])
      .map(s => `<li>${s}</li>`)
      .join("");
    const stepsHtml = `
      <div class="ai-card-section">
        <div class="ai-card-title">4. SRE Investigation Procedures</div>
        <ul class="ai-list">${stepsList || "<li>Monitor server status.</li>"}</ul>
      </div>
    `;

    // Format 5. Diagnostic Commands (with Copy button)
    const commandsList = (guidance.diagnostic_commands || []).map((cmdObj, idx) => {
      const cmdText = typeof cmdObj === "string" ? cmdObj : cmdObj.command;
      const cmdDesc = typeof cmdObj === "object" ? cmdObj.description : "Diagnostic check";
      const escapedCmd = cmdText.replace(/"/g, '&quot;');
      return `
        <div class="ai-command-box">
          <div class="ai-command-info">
            <span class="ai-command-desc">${cmdDesc}</span>
            <code class="ai-command-code">${cmdText}</code>
          </div>
          <button class="btn-copy-cmd" onclick="IncidentModal.copyCommand('${escapedCmd}', this)">Copy</button>
        </div>
      `;
    }).join("");

    const commandsHtml = `
      <div class="ai-card-section">
        <div class="ai-card-header">
          <span class="ai-card-title">5. Diagnostic Commands</span>
          <span style="font-size:10px; color:var(--text-dim);">Manual IT Operator Execution</span>
        </div>
        <div>${commandsList || "<p class='ai-text-block'>No specific shell commands suggested.</p>"}</div>
      </div>
    `;

    // Format 6. Recommended Solutions
    const solutionsList = (guidance.recommended_solutions || [])
      .map(s => `<li>${s}</li>`)
      .join("");
    const solutionsHtml = `
      <div class="ai-card-section">
        <div class="ai-card-title">6. Recommended Corrective Actions</div>
        <ul class="ai-list">${solutionsList || "<li>Restart degraded worker containers.</li>"}</ul>
      </div>
    `;

    // Format 7. Expected Outcome
    const outcomeHtml = `
      <div class="ai-card-section">
        <div class="ai-card-title">7. Expected Outcome After Remediation</div>
        <p class="ai-text-block">${guidance.expected_outcome || "Normalized baseline telemetry."}</p>
      </div>
    `;

    // Format 8. Knowledge Sources (clickable links)
    const sourcesList = (guidance.knowledge_sources || []).map(src => {
      const title = src.title || "Technical Documentation";
      const url = src.url || "#";
      const sourceOrg = src.source || "Official Source";
      const section = src.section || "Diagnostics";
      return `
        <a href="${url}" target="_blank" rel="noopener noreferrer" class="ai-source-pill" title="Click to view official documentation: ${title} (${section})">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
            <polyline points="15 3 21 3 21 9"></polyline>
            <line x1="10" y1="14" x2="21" y2="3"></line>
          </svg>
          <span><strong>${sourceOrg}</strong>: ${title} (${section})</span>
        </a>
      `;
    }).join("");

    const sourcesHtml = `
      <div class="ai-card-section">
        <div class="ai-card-title">8. Retrieved Documentation Sources (ChromaDB)</div>
        <div class="ai-sources-wrap">${sourcesList || "<p class='ai-text-block'>Local knowledge base grounding.</p>"}</div>
        <div class="ai-provider-tag">${guidance.synthesized_by || "VYTRON Intelligence Engine"}</div>
      </div>
    `;

    this.aiContent.innerHTML = `
      ${explanationHtml}
      ${causesHtml}
      ${evidenceHtml}
      ${stepsHtml}
      ${commandsHtml}
      ${solutionsHtml}
      ${outcomeHtml}
      ${sourcesHtml}
    `;

    this.aiContent.style.display = "flex";
  },

  copyCommand(commandText, btnEl) {
    if (!navigator.clipboard) {
      // Fallback for non-https or older browser environments
      const tempArea = document.createElement("textarea");
      tempArea.value = commandText;
      document.body.appendChild(tempArea);
      tempArea.select();
      document.execCommand("copy");
      document.body.removeChild(tempArea);
    } else {
      navigator.clipboard.writeText(commandText);
    }

    if (btnEl) {
      const originalText = btnEl.textContent;
      btnEl.textContent = "✓ Copied";
      btnEl.style.background = "#10b981";
      btnEl.style.color = "#ffffff";
      setTimeout(() => {
        btnEl.textContent = originalText;
        btnEl.style.background = "";
        btnEl.style.color = "";
      }, 1500);
    }
  }
};

window.IncidentModal = IncidentModal;
