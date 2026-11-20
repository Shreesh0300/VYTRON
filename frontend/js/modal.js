/**
 * VYTRON — Incident Diagnostic Modal Handler
 */

const IncidentModal = {
  backdrop: null,
  closeBtn: null,
  ackBtn: null,

  init() {
    this.backdrop = document.getElementById("incidentModalBackdrop");
    this.closeBtn = document.getElementById("modalCloseBtn");
    this.ackBtn = document.getElementById("modalAcknowledgeBtn");

    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", () => this.close());
    }
    if (this.ackBtn) {
      this.ackBtn.addEventListener("click", () => this.close());
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

    // Populate modal fields
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
    modalPrio.textContent = prio;
    modalPrio.className = `priority-badge-modal prio-${prio.toLowerCase()}`;

    modalIncId.textContent = incident.incident_id || "INC-2026-XXXX";
    modalServerLabel.textContent = `${incident.server_id} — ${incident.server_name || "Server"} (${incident.server_type || "Node"})`;
    
    modalSeverity.textContent = incident.severity || "MEDIUM";
    modalStatus.textContent = incident.status || "OPEN";
    modalStatus.style.color = incident.status === "OPEN" ? "#f87171" : "#34d399";

    modalTimeDetected.textContent = incident.created_at_str || "--:--:--";
    modalTimeResolved.textContent = incident.resolved_at_str || "In Progress (Active)";

    modalObserved.textContent = `${incident.observed_value} ${incident.unit || ""}`;
    modalThreshold.textContent = `${incident.threshold_value} ${incident.unit || ""}`;
    modalParamName.textContent = incident.metric_name || incident.metric_key || "Metric";
    modalIssueDesc.textContent = incident.issue_description || "Threshold breach detected by real-time detector.";

    modalAction.textContent = incident.recommended_action || "Investigate telemetry and normalize server workload.";

    this.backdrop.classList.add("open");
  },

  close() {
    if (this.backdrop) {
      this.backdrop.classList.remove("open");
    }
  }
};

window.IncidentModal = IncidentModal;
