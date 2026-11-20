/**
 * VYTRON — AI IT Manager Support Chatbot Controller
 * Handles live RAG interaction, contextual incident threading, and session state.
 */

const ChatApp = {
  sessionId: null,
  incidentContext: null,
  isGenerating: false,

  // DOM Elements
  elements: {
    messagesContainer: null,
    inputText: null,
    sendBtn: null,
    clearBtn: null,
    thinkingEl: null,
    suggestionsContainer: null,
    incidentBanner: null,
    clearConfirmModal: null,
    aiHealthStatus: null,
    aiStatusText: null,
  },

  init() {
    this.elements.messagesContainer = document.getElementById("chatMessages");
    this.elements.inputText = document.getElementById("chatInputText");
    this.elements.sendBtn = document.getElementById("btnSendChat");
    this.elements.clearBtn = document.getElementById("btnClearChat");
    this.elements.thinkingEl = document.getElementById("chatThinking");
    this.elements.suggestionsContainer = document.getElementById("suggestionsContainer");
    this.elements.incidentBanner = document.getElementById("chatIncidentBanner");
    this.elements.clearConfirmModal = document.getElementById("clearConfirmModal");
    this.elements.aiHealthStatus = document.getElementById("aiHealthIndicator");
    this.elements.aiStatusText = document.getElementById("aiStatusText");

    // Retrieve or initialize session ID
    this.sessionId = localStorage.getItem("vytron_chat_session_id");
    if (!this.sessionId) {
      this.sessionId = "session-" + Math.random().toString(36).substring(2, 12);
      localStorage.setItem("vytron_chat_session_id", this.sessionId);
    }

    // Set welcome time
    const welcomeTime = document.getElementById("welcomeTime");
    if (welcomeTime) {
      welcomeTime.textContent = new Date().toLocaleTimeString();
    }

    // Inspect incident context from sessionStorage or URL query params
    this.loadIncidentContext();

    // Setup Event Listeners
    this.setupListeners();

    // Check backend AI service health
    this.checkHealth();

    // Load contextual suggestions
    this.loadSuggestions();
  },

  loadIncidentContext() {
    // 1. Try sessionStorage first
    try {
      const stored = sessionStorage.getItem("vytron_chat_incident_context");
      if (stored) {
        this.incidentContext = JSON.parse(stored);
      }
    } catch (e) {
      console.warn("Error reading incident context from sessionStorage:", e);
    }

    // 2. Fallback to URL query params
    const params = new URLSearchParams(window.location.search);
    const incId = params.get("incident_id");
    const srvId = params.get("server_id");
    if (incId && (!this.incidentContext || this.incidentContext.incident_id !== incId)) {
      this.incidentContext = {
        incident_id: incId,
        server_id: srvId || "APP-01",
        metric_name: "Investigated Metric",
        observed_value: "Recorded",
        threshold_value: "Standard",
        severity: "WARNING",
        priority: "P2"
      };
    }

    // Render incident banner if context present
    if (this.incidentContext && this.incidentContext.incident_id) {
      this.renderIncidentBanner(this.incidentContext);
    } else if (this.elements.incidentBanner) {
      this.elements.incidentBanner.style.display = "none";
    }
  },

  renderIncidentBanner(ctx) {
    if (!this.elements.incidentBanner) return;
    const prioEl = document.getElementById("bannerPriority");
    const incIdEl = document.getElementById("bannerIncidentId");
    const srvEl = document.getElementById("bannerServer");
    const metricEl = document.getElementById("bannerMetric");
    const obsEl = document.getElementById("bannerObserved");
    const threshEl = document.getElementById("bannerThreshold");
    const sevEl = document.getElementById("bannerSeverity");

    const prio = ctx.priority || "P3";
    if (prioEl) {
      prioEl.textContent = prio;
      prioEl.className = `prio-tag p-${prio.toLowerCase()}`;
    }
    if (incIdEl) incIdEl.textContent = ctx.incident_id || "INC-2026-XXXX";
    if (srvEl) srvEl.textContent = `${ctx.server_id || "NODE"} (${ctx.server_name || ctx.server_type || "Server"})`;
    if (metricEl) metricEl.textContent = ctx.metric_name || ctx.metric_key || "Metric";
    if (obsEl) obsEl.textContent = `${ctx.observed_value} ${ctx.unit || ""}`;
    if (threshEl) threshEl.textContent = `${ctx.threshold_value} ${ctx.unit || ""}`;
    if (sevEl) {
      const sev = ctx.severity || "MEDIUM";
      sevEl.textContent = sev;
      sevEl.className = sev === "CRITICAL" ? "text-red" : "text-amber";
    }

    this.elements.incidentBanner.style.display = "flex";
  },

  clearIncidentContext() {
    this.incidentContext = null;
    try {
      sessionStorage.removeItem("vytron_chat_incident_context");
    } catch (e) {}

    // Remove query params from URL without reload
    const url = new URL(window.location);
    url.search = "";
    window.history.pushState({}, "", url);

    if (this.elements.incidentBanner) {
      this.elements.incidentBanner.style.display = "none";
    }

    // Reload suggestions for general IT chat
    this.loadSuggestions();
  },

  setupListeners() {
    // Send button
    if (this.elements.sendBtn) {
      this.elements.sendBtn.addEventListener("click", () => this.handleUserSend());
    }

    // Textarea Enter to send (Shift+Enter for newline)
    if (this.elements.inputText) {
      this.elements.inputText.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.handleUserSend();
        }
      });

      // Auto-resize textarea
      this.elements.inputText.addEventListener("input", () => {
        this.elements.inputText.style.height = "auto";
        this.elements.inputText.style.height = Math.min(this.elements.inputText.scrollHeight, 120) + "px";
      });
    }

    // Clear session modal triggers
    if (this.elements.clearBtn) {
      this.elements.clearBtn.addEventListener("click", () => {
        if (this.elements.clearConfirmModal) {
          this.elements.clearConfirmModal.style.display = "flex";
        }
      });
    }

    const cancelClearBtn = document.getElementById("btnCancelClear");
    if (cancelClearBtn) {
      cancelClearBtn.addEventListener("click", () => {
        if (this.elements.clearConfirmModal) {
          this.elements.clearConfirmModal.style.display = "none";
        }
      });
    }

    const confirmClearBtn = document.getElementById("btnConfirmClear");
    if (confirmClearBtn) {
      confirmClearBtn.addEventListener("click", () => this.executeClearSession());
    }
  },

  async checkHealth() {
    try {
      const res = await fetch("/api/chat/health");
      if (res.ok) {
        const data = await res.json();
        if (this.elements.aiStatusText) {
          const totalChunks = data.total_knowledge_chunks || 35249;
          this.elements.aiStatusText.textContent = `AI Online (ChromaDB: ${totalChunks.toLocaleString()} chunks)`;
        }
      }
    } catch (e) {
      if (this.elements.aiStatusText) {
        this.elements.aiStatusText.textContent = "AI Offline (Connecting...)";
      }
    }
  },

  async loadSuggestions() {
    if (!this.elements.suggestionsContainer) return;
    let url = "/api/chat/suggestions";
    if (this.incidentContext) {
      const incId = encodeURIComponent(this.incidentContext.incident_id || "");
      const srvId = encodeURIComponent(this.incidentContext.server_id || "");
      const metric = encodeURIComponent(this.incidentContext.metric_name || this.incidentContext.metric_key || "");
      url += `?incident_id=${incId}&server_id=${srvId}&metric=${metric}`;
    }

    try {
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        const list = data.suggestions || [];
        this.elements.suggestionsContainer.innerHTML = list.map(q => `
          <button class="suggestion-chip" onclick="ChatApp.sendPrompt('${q.replace(/'/g, "\\'")}')">
            <span>${q}</span>
          </button>
        `).join("");
      }
    } catch (e) {
      console.warn("Could not load suggested questions:", e);
    }
  },

  sendPrompt(promptText) {
    if (this.isGenerating || !promptText) return;
    if (this.elements.inputText) {
      this.elements.inputText.value = promptText;
    }
    this.handleUserSend();
  },

  async handleUserSend() {
    if (this.isGenerating || !this.elements.inputText) return;
    const message = this.elements.inputText.value.trim();
    if (!message) return;

    // Clear input
    this.elements.inputText.value = "";
    this.elements.inputText.style.height = "auto";

    // Append User Message to UI
    this.appendUserMessage(message);

    // Show Thinking / Loading Indicator
    this.setGenerating(true);

    try {
      const payload = {
        message: message,
        session_id: this.sessionId,
        incident_context: this.incidentContext || null
      };

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      this.appendAssistantMessage(data);

    } catch (err) {
      console.error("Chat communication error:", err);
      this.appendErrorMessage(`Failed to connect to VYTRON AI Assistant: ${err.message}. Please verify the backend server.`);
    } finally {
      this.setGenerating(false);
    }
  },

  setGenerating(isGen) {
    this.isGenerating = isGen;
    if (this.elements.sendBtn) {
      this.elements.sendBtn.disabled = isGen;
    }
    if (this.elements.thinkingEl) {
      this.elements.thinkingEl.style.display = isGen ? "flex" : "none";
    }
    this.scrollToBottom();
  },

  appendUserMessage(text) {
    if (!this.elements.messagesContainer) return;
    const timeStr = new Date().toLocaleTimeString();
    const row = document.createElement("div");
    row.className = "chat-bubble-row user-row";
    row.innerHTML = `
      <div class="chat-bubble-card user-bubble">
        <div class="bubble-header">
          <span class="bubble-sender">IT Manager</span>
          <span class="bubble-time">${timeStr}</span>
        </div>
        <div class="bubble-body">
          <p>${this.escapeHtml(text)}</p>
        </div>
      </div>
      <div class="avatar-badge user-avatar">IT</div>
    `;
    this.elements.messagesContainer.appendChild(row);
    this.scrollToBottom();
  },

  appendAssistantMessage(data) {
    if (!this.elements.messagesContainer) return;
    const timeStr = new Date().toLocaleTimeString();
    const formattedHtml = this.formatMarkdown(data.answer || "No response generated.");

    // Sources Pills HTML
    let sourcesHtml = "";
    if (data.sources && data.sources.length > 0) {
      const pills = data.sources.map(s => `
        <a href="${s.url || '#'}" target="_blank" rel="noopener noreferrer" class="source-chip" title="Click to view runbook: ${s.title}">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
            <polyline points="15 3 21 3 21 9"></polyline>
            <line x1="10" y1="14" x2="21" y2="3"></line>
          </svg>
          <span><strong>${s.source || 'Doc'}:</strong> ${s.title}</span>
        </a>
      `).join("");

      sourcesHtml = `
        <div class="assistant-sources-wrap">
          <span class="sources-label">Retrieved Runbook Grounding:</span>
          <div class="sources-pills-list">${pills}</div>
        </div>
      `;
    }

    // Context used tag
    let contextTag = "";
    if (data.incident_context_used && this.incidentContext) {
      contextTag = `<span class="context-pill">Grounded in ${this.incidentContext.server_id} Telemetry</span>`;
    }

    const row = document.createElement("div");
    row.className = "chat-bubble-row assistant-row";
    row.innerHTML = `
      <div class="avatar-badge assistant-avatar">AI</div>
      <div class="chat-bubble-card assistant-bubble">
        <div class="bubble-header">
          <span class="bubble-sender">VYTRON AI IT Support Assistant</span>
          <div style="display:flex; align-items:center; gap:8px;">
            ${contextTag}
            <span class="bubble-time">${timeStr}</span>
          </div>
        </div>
        <div class="bubble-body markdown-body">
          ${formattedHtml}
        </div>
        ${sourcesHtml}
      </div>
    `;
    this.elements.messagesContainer.appendChild(row);
    this.scrollToBottom();
  },

  appendErrorMessage(errorText) {
    if (!this.elements.messagesContainer) return;
    const timeStr = new Date().toLocaleTimeString();
    const row = document.createElement("div");
    row.className = "chat-bubble-row assistant-row";
    row.innerHTML = `
      <div class="avatar-badge assistant-avatar" style="background:#ef4444;">!</div>
      <div class="chat-bubble-card assistant-bubble" style="border-color: rgba(239, 68, 68, 0.4);">
        <div class="bubble-header">
          <span class="bubble-sender" style="color:#f87171;">System Notification</span>
          <span class="bubble-time">${timeStr}</span>
        </div>
        <div class="bubble-body">
          <p style="color:#fca5a5;">${this.escapeHtml(errorText)}</p>
        </div>
      </div>
    `;
    this.elements.messagesContainer.appendChild(row);
    this.scrollToBottom();
  },

  async executeClearSession() {
    try {
      await fetch("/api/chat/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: this.sessionId })
      });
    } catch (e) {
      console.warn("Could not notify backend of session clear:", e);
    }

    if (this.elements.clearConfirmModal) {
      this.elements.clearConfirmModal.style.display = "none";
    }

    // Keep only welcome message
    if (this.elements.messagesContainer) {
      const timeStr = new Date().toLocaleTimeString();
      this.elements.messagesContainer.innerHTML = `
        <div class="chat-bubble-row assistant-row">
          <div class="avatar-badge assistant-avatar">AI</div>
          <div class="chat-bubble-card assistant-bubble">
            <div class="bubble-header">
              <span class="bubble-sender">VYTRON AI IT Support Assistant</span>
              <span class="bubble-time">${timeStr}</span>
            </div>
            <div class="bubble-body">
              <p>Conversation history cleared. I am ready to assist with your next infrastructure operations inquiry.</p>
            </div>
          </div>
        </div>
      `;
    }
  },

  scrollToBottom() {
    if (this.elements.messagesContainer) {
      setTimeout(() => {
        this.elements.messagesContainer.scrollTop = this.elements.messagesContainer.scrollHeight;
      }, 50);
    }
  },

  escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  },

  formatMarkdown(text) {
    if (!text) return "";
    let html = text;

    // Headers (### Heading)
    html = html.replace(/^### (.*$)/gim, '<h3 class="chat-h3">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="chat-h2">$1</h2>');

    // Bold (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Inline code (`code`)
    html = html.replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>');

    // Unordered lists (- item)
    html = html.replace(/^\- (.*$)/gim, '<li class="chat-li">$1</li>');
    html = html.replace(/<\/li>\n<li/g, '</li><li');
    html = html.replace(/(<li class="chat-li">.*<\/li>)/gms, '<ul class="chat-ul">$1</ul>');

    // Paragraph line breaks
    html = html.replace(/\n\n/g, '</p><p>');
    html = `<p>${html}</p>`;
    html = html.replace(/<p><h/g, '<h').replace(/<\/h3><\/p>/g, '</h3>').replace(/<\/h2><\/p>/g, '</h2>');
    html = html.replace(/<p><ul/g, '<ul').replace(/<\/ul><\/p>/g, '</ul>');

    return html;
  }
};

document.addEventListener("DOMContentLoaded", () => {
  ChatApp.init();
});
