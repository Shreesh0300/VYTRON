/**
 * VYTRON — Egress Proof & Privacy Audit Controller
 * Connects directly to collector.db audit APIs:
 * - Fetches real egress statistics (payloads sent, sensitive fields blocked, pending, failed)
 * - Renders detailed payload audit table
 * - Loads exact Before vs After comparison with field-level syntax highlighting
 */

const EgressApp = {
  currentPayloadId: null,
  cachedRecords: [],
  activeFilter: "all",
  activeServer: "ALL",
  searchQuery: "",

  async init() {
    this.setupListeners();
    await this.fetchStats();
    await this.fetchRecords();
  },

  setupListeners() {
    const searchInput = document.getElementById("egressSearchInput");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        this.searchQuery = e.target.value.trim().toLowerCase();
        this.applyFilters();
      });
    }

    const policyFilter = document.getElementById("egressPolicyFilter");
    if (policyFilter) {
      policyFilter.addEventListener("change", (e) => {
        this.activeFilter = e.target.value;
        this.applyFilters();
      });
    }

    const serverFilter = document.getElementById("egressServerFilter");
    if (serverFilter) {
      serverFilter.addEventListener("change", (e) => {
        this.activeServer = e.target.value;
        this.applyFilters();
      });
    }

    const copyBtn = document.getElementById("btnCopyOutgoingJson");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        const viewer = document.getElementById("egressViewerAfter");
        if (viewer) {
          navigator.clipboard.writeText(viewer.getAttribute("data-raw-json") || viewer.innerText);
          const origText = copyBtn.innerText;
          copyBtn.innerText = "✓ Copied!";
          setTimeout(() => { copyBtn.innerText = origText; }, 2000);
        }
      });
    }
  },

  async fetchStats() {
    try {
      const res = await fetch("/api/egress/stats");
      if (res.ok) {
        const stats = await res.json();
        this.renderStats(stats);
      }
    } catch (e) {
      console.warn("Failed to fetch egress stats:", e);
    }
  },

  renderStats(stats) {
    const elSent = document.getElementById("statEgressSent");
    const elBlocked = document.getElementById("statEgressBlocked");
    const elPending = document.getElementById("statEgressPending");
    const elFailed = document.getElementById("statEgressFailed");

    if (elSent) elSent.textContent = (stats.payloads_sent || 0).toLocaleString();
    if (elBlocked) elBlocked.textContent = (stats.sensitive_fields_blocked || 0).toLocaleString();
    if (elPending) elPending.textContent = (stats.pending_transfers || 0).toLocaleString();
    if (elFailed) elFailed.textContent = (stats.failed_transfers || 0).toLocaleString();
  },

  async fetchRecords() {
    try {
      const res = await fetch("/api/egress?limit=100");
      if (res.ok) {
        this.cachedRecords = await res.json();
        this.populateServerFilterOptions(this.cachedRecords);
        this.applyFilters();

        // Select first record (which is prioritized as redacted for maximum demonstration impact)
        if (this.cachedRecords.length > 0 && !this.currentPayloadId) {
          this.loadPayloadDetail(this.cachedRecords[0].payload_id);
        }
      }
    } catch (e) {
      console.warn("Failed to fetch egress records:", e);
    }
  },

  populateServerFilterOptions(records) {
    const serverFilter = document.getElementById("egressServerFilter");
    if (!serverFilter) return;

    const servers = new Set();
    records.forEach(r => { if (r.server_id) servers.add(r.server_id); });
    
    // Preserve ALL
    let optionsHtml = '<option value="ALL">All Monitored Servers</option>';
    Array.from(servers).sort().forEach(s => {
      optionsHtml += `<option value="${s}">${s}</option>`;
    });
    serverFilter.innerHTML = optionsHtml;
  },

  applyFilters() {
    let filtered = this.cachedRecords;

    if (this.activeFilter === "redacted") {
      filtered = filtered.filter(r => r.policy_result === "redacted");
    } else if (this.activeFilter === "approved") {
      filtered = filtered.filter(r => r.policy_result === "approved");
    }

    if (this.activeServer !== "ALL") {
      filtered = filtered.filter(r => r.server_id === this.activeServer);
    }

    if (this.searchQuery) {
      filtered = filtered.filter(r => 
        (r.payload_id && r.payload_id.toLowerCase().includes(this.searchQuery)) ||
        (r.server_id && r.server_id.toLowerCase().includes(this.searchQuery)) ||
        (r.audit_id && r.audit_id.toLowerCase().includes(this.searchQuery))
      );
    }

    this.renderTable(filtered);
  },

  renderTable(records) {
    const tbody = document.getElementById("egressAuditTbody");
    const countBadge = document.getElementById("egressRecordsCountBadge");
    if (!tbody) return;

    if (countBadge) {
      countBadge.textContent = `${records.length} Payloads Audited`;
    }

    if (!records || records.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-state">No egress audit records match the selected filters.</td>
        </tr>
      `;
      return;
    }

    let rowsHtml = "";
    records.forEach((r) => {
      const isSelected = r.payload_id === this.currentPayloadId;
      const isRedacted = r.policy_result === "redacted";
      const policyClass = isRedacted ? "redacted" : "approved";
      
      let statusClass = "text-muted";
      if (r.transmission_status === "delivered") statusClass = "text-green";
      else if (r.transmission_status === "failed") statusClass = "text-red";
      else if (r.transmission_status === "queued" || r.transmission_status === "pending") statusClass = "text-cyan";

      const timeFormatted = r.timestamp ? r.timestamp.replace("T", " ").split(".")[0] : "--";

      rowsHtml += `
        <tr class="clickable-row ${isSelected ? 'selected-row' : ''}" 
            onclick="EgressApp.loadPayloadDetail('${r.payload_id}')">
          <td style="font-family: var(--font-mono); font-weight: 700; color: #fff;">${r.payload_id}</td>
          <td><span class="server-id-badge" style="background:rgba(255,255,255,0.08); padding:2px 7px; border-radius:4px;">${r.server_id}</span></td>
          <td><span class="policy-badge ${policyClass}">${r.policy_result.toUpperCase()}</span></td>
          <td><span style="color:#34d399; font-weight:600;">${r.approved_count} allowed</span></td>
          <td>
            ${r.blocked_count > 0 
              ? `<span style="background:rgba(239,68,68,0.2); color:#f87171; padding:2px 6px; border-radius:4px; font-weight:700;">${r.blocked_count} blocked</span>`
              : `<span style="color:var(--text-dim);">0 (Clean)</span>`}
          </td>
          <td><span class="${statusClass}" style="font-weight:700; text-transform:uppercase; font-size:11px;">${r.transmission_status}</span></td>
          <td style="font-family: var(--font-mono); color: var(--text-dim); font-size:11px;">${timeFormatted}</td>
        </tr>
      `;
    });

    tbody.innerHTML = rowsHtml;
  },

  async loadPayloadDetail(payloadId) {
    if (!payloadId) return;
    this.currentPayloadId = payloadId;

    // Update selected row in table
    const tbody = document.getElementById("egressAuditTbody");
    if (tbody) {
      Array.from(tbody.querySelectorAll("tr")).forEach(tr => {
        tr.classList.remove("selected-row");
      });
      // Re-render table highlight
      this.applyFilters();
    }

    try {
      const res = await fetch(`/api/egress/${payloadId}`);
      if (!res.ok) return;
      const detail = await res.json();
      this.renderComparison(detail);
    } catch (e) {
      console.warn("Failed to load payload detail:", e);
    }
  },

  renderComparison(detail) {
    const elPayloadId = document.getElementById("compPayloadId");
    const elServerId = document.getElementById("compServerId");
    const elPolicyBadge = document.getElementById("compPolicyBadge");
    const elStatus = document.getElementById("compDeliveryStatus");
    const elTimestamp = document.getElementById("compTimestamp");
    const chipsContainer = document.getElementById("compFieldChipsBar");

    if (elPayloadId) elPayloadId.textContent = detail.payload_id;
    if (elServerId) elServerId.textContent = detail.server_id;
    if (elStatus) elStatus.textContent = detail.transmission_status.toUpperCase();
    if (elTimestamp) elTimestamp.textContent = detail.timestamp;

    if (elPolicyBadge) {
      const isRedacted = detail.policy_result === "redacted";
      elPolicyBadge.textContent = isRedacted ? `REDACTED (${detail.blocked_fields.length} SENSITIVE FIELDS STRIPPED)` : "APPROVED (100% CLEAN ALLOW-LIST)";
      elPolicyBadge.className = `policy-badge ${isRedacted ? 'redacted' : 'approved'}`;
    }

    // Render Field Chips (Allowed in Green, Blocked in Red)
    if (chipsContainer) {
      let allowedChips = detail.approved_fields.map(f => `
        <span class="field-chip allowed">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          ${f}
        </span>
      `).join("");

      let blockedChips = detail.blocked_fields.map(f => `
        <span class="field-chip blocked">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
          ${f}
        </span>
      `).join("");

      if (!blockedChips) {
        blockedChips = '<span style="color:var(--text-dim); font-size:11px; font-style:italic;">None (Zero sensitive fields detected in payload)</span>';
      }

      chipsContainer.innerHTML = `
        <div class="chips-group">
          <span class="chips-group-label" style="color:#34d399;">ALLOWED FIELDS (${detail.approved_fields.length}):</span>
          ${allowedChips}
        </div>
        <div class="chips-group" style="margin-top:6px;">
          <span class="chips-group-label" style="color:#f87171;">BLOCKED / STRIPPED (${detail.blocked_fields.length}):</span>
          ${blockedChips}
        </div>
      `;
    }

    // Render Left Pane (BEFORE - Raw Ingest with highlighted blocked keys)
    const viewerBefore = document.getElementById("egressViewerBefore");
    if (viewerBefore) {
      const formattedRaw = JSON.stringify(detail.raw_original_telemetry, null, 2);
      viewerBefore.innerHTML = this.highlightJson(formattedRaw, detail.blocked_fields, "before");
    }

    // Render Right Pane (AFTER - Exact Serialized Outgoing JSON)
    const viewerAfter = document.getElementById("egressViewerAfter");
    if (viewerAfter) {
      let formattedOutgoing = "";
      try {
        formattedOutgoing = JSON.stringify(detail.outgoing_parsed, null, 2);
      } catch (e) {
        formattedOutgoing = detail.outgoing_serialized_json;
      }
      viewerAfter.setAttribute("data-raw-json", detail.outgoing_serialized_json);
      viewerAfter.innerHTML = this.highlightJson(formattedOutgoing, detail.approved_fields, "after");
    }
  },

  highlightJson(jsonStr, targetFields, mode) {
    if (!jsonStr) return "";

    // Escape basic HTML
    let safe = jsonStr
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Syntax highlight JSON keys and values
    // Matches "key": value
    safe = safe.replace(/("(\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*")(\s*:)?/g, (match, p1, p2, p3) => {
      if (p3) {
        // It's a key!
        const cleanKey = p1.replace(/"/g, "");
        const isBlockedKey = mode === "before" && (
          cleanKey === "password" || cleanKey === "api_key" || cleanKey === "raw_payload" || 
          cleanKey.includes("secret") || cleanKey.includes("token")
        );

        if (isBlockedKey) {
          return `<span class="hl-key-blocked">${p1}</span>${p3}`;
        }
        return `<span class="hl-key-allowed">${p1}</span>${p3}`;
      } else {
        // It's a string value
        if (p1.includes("[BLOCKED_SECRET]") || p1.includes("[REDACTED_SECRET]")) {
          return `<span class="hl-val-masked">${p1}</span>`;
        }
        return `<span class="hl-val-string">${p1}</span>`;
      }
    });

    // Numbers & Booleans
    safe = safe.replace(/:\s*(-?\d+(\.\d+)?([eE][+-]?\d+)?)\b/g, ': <span class="hl-val-num">$1</span>');
    safe = safe.replace(/:\s*(true|false|null)\b/g, ': <span class="hl-val-bool">$1</span>');

    return safe;
  }
};

window.EgressApp = EgressApp;
