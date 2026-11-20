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
      this.latestGuidance = guidance;
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
      .map(c => {
        if (typeof c === "object" && c !== null) {
          return `
            <li class="ai-hypo-item">
              <div class="ai-hypo-title"><span class="ai-hypo-tag">HYPOTHESIS</span> <strong>${c.hypothesis || "Unidentified anomaly"}</strong></div>
              <div class="ai-hypo-row"><span class="ai-hypo-lbl">Why Possible:</span> <span>${c.why || "Not specified"}</span></div>
              <div class="ai-hypo-row"><span class="ai-hypo-lbl">Supporting Evidence:</span> <span class="ai-hypo-val">${c.evidence || "Not available"}</span></div>
              <div class="ai-hypo-row"><span class="ai-hypo-lbl">Missing Evidence Needed:</span> <span>${c.missing_evidence || "Not available"}</span></div>
              <div class="ai-hypo-row"><span class="ai-hypo-lbl">Operator Verification:</span> <span class="ai-hypo-val">${c.verification || "Inspect system telemetry"}</span></div>
            </li>
          `;
        }
        return `<li>${c}</li>`;
      })
      .join("");
    const causesHtml = `
      <div class="ai-card-section">
        <div class="ai-card-header">
          <span class="ai-card-title">2. Possible Root Causes</span>
          <span class="ai-badge-hypo">Hypotheses — Not Confirmed Facts</span>
        </div>
        <ul class="ai-hypo-list">${causesList || "<li>Requires manual triage.</li>"}</ul>
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

    // Format 5. Recommended Solutions
    const solutionsList = (guidance.recommended_solutions || [])
      .map(s => `<li>${s}</li>`)
      .join("");
    const solutionsHtml = `
      <div class="ai-card-section">
        <div class="ai-card-title">5. Recommended Corrective Actions</div>
        <ul class="ai-list">${solutionsList || "<li>Restart degraded worker containers.</li>"}</ul>
      </div>
    `;

    // Format 6. Expected Outcome
    const outcomeHtml = `
      <div class="ai-card-section">
        <div class="ai-card-title">6. Expected Outcome After Remediation</div>
        <p class="ai-text-block">${guidance.expected_outcome || "Normalized baseline telemetry."}</p>
      </div>
    `;

    // Format 7. Continue Conversation in IT Support Chatbot CTA
    const chatbotCtaHtml = `
      <div class="ai-card-section ai-chatbot-cta-box" style="border: 1px solid rgba(6, 182, 212, 0.4); background: rgba(6, 182, 212, 0.05); border-radius: 8px; padding: 16px; margin-top: 14px;">
        <div style="display:flex; align-items:center; justify-content:space-between; gap:14px; flex-wrap:wrap;">
          <div>
            <div style="font-weight:700; color:#38bdf8; font-size:13px; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              <span>Interactive Incident Troubleshooting</span>
            </div>
            <div style="font-size:11px; color:var(--text-dim);">Continue deep-dive root cause analysis and ask follow-up questions in the dedicated IT Manager Support Chatbot.</div>
          </div>
          <button class="btn btn-primary btn-chat-redirect" style="background:#06b6d4; color:#0f172a; font-weight:700; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-size:12px; display:flex; align-items:center; gap:6px;" onclick="IncidentModal.openChatbot()">
            Continue Conversation in IT Support Chatbot ➔
          </button>
        </div>
      </div>
    `;

    this.aiContent.innerHTML = `
      ${explanationHtml}
      ${causesHtml}
      ${evidenceHtml}
      ${stepsHtml}
      ${solutionsHtml}
      ${outcomeHtml}
      ${chatbotCtaHtml}
    `;

    this.aiContent.style.display = "flex";
  },

  openChatbot() {
    if (!this.currentIncident) return;
    const chatContext = {
      incident_id: this.currentIncident.incident_id,
      server_id: this.currentIncident.server_id,
      server_name: this.currentIncident.server_name,
      server_type: this.currentIncident.server_type,
      metric_name: this.currentIncident.metric_name || this.currentIncident.metric_key,
      metric_key: this.currentIncident.metric_key,
      observed_value: this.currentIncident.observed_value,
      threshold_value: this.currentIncident.threshold_value,
      severity: this.currentIncident.severity,
      priority: this.currentIncident.priority,
      created_at: this.currentIncident.created_at_str,
      issue_description: this.currentIncident.issue_description,
      recommended_action: this.currentIncident.recommended_action,
      guidance: this.latestGuidance || null
    };

    try {
      sessionStorage.setItem("vytron_chat_incident_context", JSON.stringify(chatContext));
    } catch (e) {
      console.warn("Could not save to sessionStorage:", e);
    }

    const incParam = encodeURIComponent(this.currentIncident.incident_id || "");
    const srvParam = encodeURIComponent(this.currentIncident.server_id || "");
    window.location.href = `chat.html?incident_id=${incParam}&server_id=${srvParam}`;
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
