/**
 * VYTRON AIOps — Google Authentication & Role-Based Access Control Client
 * Handles:
 * 1. Google OAuth 2.0 / OpenID Connect ID Token flows via Google Identity Services (GSI).
 * 2. Role selection (IT Team vs Admin) with backend-enforced authorization.
 * 3. User profile display, avatar rendering, and dropdown management.
 * 4. Session management and logout.
 * 5. Admin user management modal for authorized administrators.
 */

const AuthManager = {
  currentUser: null,
  oauthConfig: {
    configured: false,
    google_client_id: null,
    message: ""
  },
  selectedRole: "it_team",

  elements: {},

  init() {
    this.cacheElements();
    this.bindEvents();
    this.fetchAuthConfig().then(() => {
      this.checkSession();
    });
  },

  cacheElements() {
    this.elements = {
      headerContainer: document.getElementById("authHeaderContainer"),
      modal: document.getElementById("authModal"),
      btnClose: document.getElementById("btnAuthModalClose"),
      btnCancel: document.getElementById("btnAuthCancel"),
      btnContinueGoogle: document.getElementById("btnContinueWithGoogle"),
      roleCardItTeam: document.getElementById("roleCardItTeam"),
      roleCardAdmin: document.getElementById("roleCardAdmin"),
      roleRadioItTeam: document.getElementById("roleRadioItTeam"),
      roleRadioAdmin: document.getElementById("roleRadioAdmin"),
      alertBanner: document.getElementById("authAlertBanner"),
      oauthNotice: document.getElementById("oauthNotConfiguredNotice"),
      googleGsiDiv: document.getElementById("googleGsiButtonDiv"),
      adminModal: document.getElementById("adminUsersModal"),
      btnAdminModalClose: document.getElementById("btnAdminModalClose"),
      btnAdminClose: document.getElementById("btnAdminClose"),
      adminTableBody: document.getElementById("adminUsersTableBody")
    };
  },

  bindEvents() {
    // Global click listener for authentication and modal triggers
    document.addEventListener("click", (e) => {
      const loginBtn = e.target.closest("#btnOpenLoginModal");
      if (loginBtn) {
        e.preventDefault();
        this.openModal();
        return;
      }

      const profileBtn = e.target.closest("#userProfileBtn");
      if (profileBtn) {
        e.preventDefault();
        this.toggleUserDropdown();
        return;
      }

      const logoutBtn = e.target.closest("#btnLogout");
      if (logoutBtn) {
        e.preventDefault();
        this.logout();
        return;
      }

      const adminMgmtBtn = e.target.closest("#btnOpenAdminMgmt");
      if (adminMgmtBtn) {
        e.preventDefault();
        this.closeUserDropdown();
        this.openAdminModal();
        return;
      }

      // Close modal when clicking directly on the backdrop outside the modal box
      if (e.target.id === "authModal") {
        this.closeModal();
      }
      if (e.target.id === "adminUsersModal") {
        this.closeAdminModal();
      }
    });

    // Modal Close buttons
    const btnClose = document.getElementById("btnAuthModalClose");
    if (btnClose) {
      btnClose.addEventListener("click", () => this.closeModal());
    }
    const btnCancel = document.getElementById("btnAuthCancel");
    if (btnCancel) {
      btnCancel.addEventListener("click", () => this.closeModal());
    }

    // Role Selection
    const roleIt = document.getElementById("roleCardItTeam");
    const roleAd = document.getElementById("roleCardAdmin");
    if (roleIt && roleAd) {
      roleIt.addEventListener("click", () => this.selectRole("it_team"));
      roleAd.addEventListener("click", () => this.selectRole("admin"));
    }

    // Google Continue Button
    const btnGoogle = document.getElementById("btnContinueWithGoogle");
    if (btnGoogle) {
      btnGoogle.addEventListener("click", () => this.handleGoogleButtonClick());
    }

    // Admin Modal Close
    const btnAdmClose = document.getElementById("btnAdminModalClose");
    if (btnAdmClose) {
      btnAdmClose.addEventListener("click", () => this.closeAdminModal());
    }
    const btnAdmFootClose = document.getElementById("btnAdminClose");
    if (btnAdmFootClose) {
      btnAdmFootClose.addEventListener("click", () => this.closeAdminModal());
    }

    // Close dropdown on outside click
    document.addEventListener("click", (e) => {
      const dropdown = document.getElementById("userProfileDropdown");
      const profileBtn = document.getElementById("userProfileBtn");
      if (dropdown && !dropdown.contains(e.target) && profileBtn && !profileBtn.contains(e.target)) {
        this.closeUserDropdown();
      }
    });

    // Close modals on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        this.closeModal();
        this.closeAdminModal();
        this.closeUserDropdown();
      }
    });
  },

  async fetchAuthConfig() {
    try {
      const res = await fetch("/api/auth/config");
      if (res.ok) {
        this.oauthConfig = await res.json();
        this.setupGoogleGsiClient();
      }
    } catch (err) {
      console.warn("[Auth] Failed to load auth config:", err);
    }
  },

  setupGoogleGsiClient() {
    const gsiDiv = document.getElementById("googleGsiButtonDiv");
    const customBtn = document.getElementById("btnContinueWithGoogle");

    if (!this.oauthConfig.configured || !this.oauthConfig.google_client_id) {
      if (gsiDiv) gsiDiv.style.display = "none";
      if (customBtn) customBtn.style.display = "flex";
      return;
    }

    // Check if Google GSI library is loaded
    if (typeof google !== "undefined" && google.accounts && google.accounts.id) {
      try {
        google.accounts.id.initialize({
          client_id: this.oauthConfig.google_client_id,
          callback: (response) => this.handleGoogleCredentialResponse(response),
          auto_select: false,
          cancel_on_tap_outside: true
        });

        if (gsiDiv) {
          gsiDiv.style.display = "flex";
          gsiDiv.style.justifyContent = "center";
          gsiDiv.style.width = "100%";
          google.accounts.id.renderButton(gsiDiv, {
            theme: "outline",
            size: "large",
            type: "standard",
            text: "continue_with",
            shape: "rectangular",
            logo_alignment: "left",
            width: 380
          });
        }
        if (customBtn) {
          customBtn.style.display = "none";
        }
      } catch (err) {
        console.warn("[Auth] GSI initialization warning:", err);
      }
    } else {
      // Retry after 400ms in case the external script is still loading
      setTimeout(() => this.setupGoogleGsiClient(), 400);
    }
  },

  async checkSession() {
    try {
      const res = await fetch("/api/auth/me");
      if (res.ok) {
        const data = await res.json();
        if (data.authenticated) {
          this.currentUser = data;
          this.renderHeaderAuthenticated();
          if (window.updateEgressProofRoleView) window.updateEgressProofRoleView();
          return;
        }
      }
    } catch (err) {
      // Unauthenticated, standard state
    }
    this.currentUser = null;
    this.renderHeaderUnauthenticated();
    if (window.updateEgressProofRoleView) window.updateEgressProofRoleView();
  },

  renderHeaderUnauthenticated() {
    if (!this.elements.headerContainer) return;
    this.elements.headerContainer.innerHTML = `
      <button id="btnOpenLoginModal" class="btn-auth-login" title="Sign in to VYTRON">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
        <span>Login / Sign Up</span>
      </button>
    `;
    if (window.updateEgressProofRoleView) window.updateEgressProofRoleView();
  },

  renderHeaderAuthenticated() {
    if (!this.elements.headerContainer || !this.currentUser) return;

    if (window.updateEgressProofRoleView) window.updateEgressProofRoleView();

    const u = this.currentUser;
    const isAd = u.authorized_role === "admin";
    const roleBadgeClass = isAd ? "role-pill-admin" : "role-pill-it";
    const roleLabel = isAd ? "ADMIN" : "IT TEAM";

    // Avatar image or initials
    let avatarHtml = "";
    if (u.picture && u.picture.startsWith("http")) {
      avatarHtml = `<img src="${u.picture}" alt="${u.name}" class="user-avatar-img" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                    <span class="user-avatar-initials" style="display:none;">${u.name.charAt(0).toUpperCase()}</span>`;
    } else {
      avatarHtml = `<span class="user-avatar-initials">${u.name ? u.name.charAt(0).toUpperCase() : "U"}</span>`;
    }

    this.elements.headerContainer.innerHTML = `
      <div class="user-profile-menu-wrap">
        <button id="userProfileBtn" class="user-profile-btn" aria-haspopup="true" aria-expanded="false" title="Click to view profile and role">
          <div class="user-avatar-slot">
            ${avatarHtml}
          </div>
          <span class="user-display-name">${u.name || "IT Operator"}</span>
          <span class="user-role-pill ${roleBadgeClass}">${roleLabel}</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="user-dropdown-caret">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>

        <!-- Dropdown Menu -->
        <div id="userProfileDropdown" class="user-profile-dropdown hidden">
          <div class="dropdown-header">
            <div class="dropdown-user-name">${u.name}</div>
            <div class="dropdown-user-email">${u.email}</div>
            <div class="dropdown-meta">ID: <code>${u.user_id}</code></div>
          </div>

          <div class="dropdown-role-section">
            <div class="dropdown-role-label">Platform Role</div>
            <div class="dropdown-role-val">
              <span class="user-role-pill ${roleBadgeClass}">${roleLabel}</span>
              <span class="dropdown-role-status">${u.account_status === "active" ? "✓ Authorized" : "⏳ Pending Admin Approval"}</span>
            </div>
            <div class="dropdown-role-desc">
              ${isAd
                ? "Full administrative access: user management, role assignments, platform policies."
                : "Operational access: 5-server telemetry, incident investigation, AI troubleshooting assistant."}
            </div>
          </div>

          <div class="dropdown-actions">
            ${isAd ? `
              <button id="btnOpenAdminMgmt" class="dropdown-item-btn admin-action">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                  <circle cx="9" cy="7" r="4"></circle>
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                  <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                </svg>
                <span>Manage Users & Roles</span>
              </button>
            ` : ""}

            <button id="btnLogout" class="dropdown-item-btn logout-action">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>
    `;
  },

  toggleUserDropdown() {
    const dropdown = document.getElementById("userProfileDropdown");
    if (!dropdown) return;
    const isHidden = dropdown.classList.contains("hidden");
    if (isHidden) {
      dropdown.classList.remove("hidden");
    } else {
      dropdown.classList.add("hidden");
    }
  },

  closeUserDropdown() {
    const dropdown = document.getElementById("userProfileDropdown");
    if (dropdown) dropdown.classList.add("hidden");
  },

  selectRole(role) {
    this.selectedRole = role;
    if (role === "it_team") {
      this.elements.roleCardItTeam.classList.add("selected");
      this.elements.roleCardAdmin.classList.remove("selected");
      this.elements.roleRadioItTeam.checked = true;
    } else {
      this.elements.roleCardAdmin.classList.add("selected");
      this.elements.roleCardItTeam.classList.remove("selected");
      this.elements.roleRadioAdmin.checked = true;
    }
  },

  openModal() {
    this.hideAlert();
    this.selectRole("it_team");

    // Check if OAuth is configured
    const notice = document.getElementById("oauthNotConfiguredNotice");
    if (!this.oauthConfig.configured) {
      if (notice) {
        notice.classList.remove("hidden");
        notice.style.display = "flex";
      }
    } else {
      if (notice) {
        notice.classList.add("hidden");
        notice.style.display = "none";
      }
    }

    const modal = document.getElementById("authModal");
    if (modal) {
      modal.classList.add("open");
      modal.classList.remove("hidden");
      modal.style.display = "flex";
    }
  },

  closeModal() {
    const modal = document.getElementById("authModal");
    if (modal) {
      modal.classList.remove("open");
      modal.classList.add("hidden");
      modal.style.display = "none";
    }
    this.hideAlert();
  },

  handleGoogleButtonClick() {
    this.hideAlert();

    // 1. Validate that role is selected
    if (!this.selectedRole) {
      this.showAlert("Please select a role (IT Team or Admin) before continuing.", "warning");
      return;
    }

    // 2. Check if OAuth credentials are configured
    if (!this.oauthConfig.configured || !this.oauthConfig.google_client_id) {
      this.showAlert(
        "Google OAuth 2.0 is not configured on this server. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env to connect your Google Cloud project.",
        "warning"
      );
      if (this.elements.oauthNotice) {
        this.elements.oauthNotice.classList.remove("hidden");
      }
      return;
    }

    // 3. Trigger Google Identity Services Flow
    if (typeof google !== "undefined" && google.accounts && google.accounts.id) {
      try {
        // Trigger GSI prompt
        google.accounts.id.prompt((notification) => {
          if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
            // Fallback: click rendered GSI button
            const gsiBtn = this.elements.googleGsiDiv.querySelector("div[role=button]");
            if (gsiBtn) {
              gsiBtn.click();
            }
          }
        });
      } catch (err) {
        this.showAlert(`Google sign-in error: ${err.message}`, "error");
      }
    } else {
      this.showAlert("Google authentication service is loading. Please try again in a few seconds.", "warning");
    }
  },

  async handleGoogleCredentialResponse(response) {
    if (!response || !response.credential) {
      this.showAlert("Google did not return a valid identity token.", "error");
      return;
    }

    this.showAlert("Verifying Google identity and validating authorization with backend...", "info");

    try {
      const res = await fetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          credential: response.credential,
          requested_role: this.selectedRole
        })
      });

      const data = await res.json();

      if (!res.ok) {
        this.showAlert(data.detail || "Authentication failed. Invalid Google token.", "error");
        return;
      }

      // Success
      this.currentUser = {
        authenticated: true,
        user_id: data.user_id,
        name: data.name,
        email: data.email,
        picture: data.picture,
        authorized_role: data.authorized_role,
        requested_role: data.requested_role,
        account_status: data.account_status
      };

      this.renderHeaderAuthenticated();
      this.closeModal();

      // Show notice if admin request was downgraded for security
      if (data.requested_role === "admin" && data.authorized_role !== "admin") {
        alert(`Notice: ${data.message}`);
      }
    } catch (err) {
      this.showAlert(`Authentication request failed: ${err.message}`, "error");
    }
  },

  async logout() {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch (err) {
      console.warn("[Auth] Logout request failed:", err);
    }
    this.currentUser = null;
    window._lastTier1RawRecord = null;
    this.renderHeaderUnauthenticated();
    this.closeUserDropdown();
    if (window.updateEgressProofRoleView) window.updateEgressProofRoleView();
  },

  // ── Admin Modal Operations ────────────────────────────────────────────────

  async openAdminModal() {
    if (!this.currentUser || this.currentUser.authorized_role !== "admin") {
      alert("Access Denied: Administrator privileges required.");
      return;
    }

    const adminModal = document.getElementById("adminUsersModal");
    if (adminModal) {
      adminModal.classList.add("open");
      adminModal.classList.remove("hidden");
      adminModal.style.display = "flex";
    }
    this.loadAdminUsers();
  },

  closeAdminModal() {
    const adminModal = document.getElementById("adminUsersModal");
    if (adminModal) {
      adminModal.classList.remove("open");
      adminModal.classList.add("hidden");
      adminModal.style.display = "none";
    }
  },

  async loadAdminUsers() {
    if (!this.elements.adminTableBody) return;
    this.elements.adminTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:15px; color:#94a3b8;">Loading platform users from SQLite...</td></tr>`;

    try {
      const res = await fetch("/api/admin/users");
      if (!res.ok) {
        const err = await res.json();
        this.elements.adminTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#f87171; padding:15px;">Error: ${err.detail || "Unauthorized"}</td></tr>`;
        return;
      }

      const data = await res.json();
      const users = data.users || [];

      if (users.length === 0) {
        this.elements.adminTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:15px; color:#94a3b8;">No registered users found.</td></tr>`;
        return;
      }

      this.elements.adminTableBody.innerHTML = users.map(u => {
        const isCurrent = u.email === this.currentUser.email;
        const rolePill = u.authorized_role === "admin"
          ? `<span class="user-role-pill role-pill-admin">ADMIN</span>`
          : `<span class="user-role-pill role-pill-it">IT TEAM</span>`;

        const statusPill = u.account_status === "active"
          ? `<span class="status-pill status-active">Active</span>`
          : `<span class="status-pill status-pending">Pending Approval</span>`;

        return `
          <tr>
            <td>
              <div style="font-weight:600; color:#f8fafc;">${u.name}</div>
              <div style="font-size:11px; color:#64748b;">${u.user_id}</div>
            </td>
            <td style="color:#cbd5e1; font-family:monospace; font-size:12px;">${u.email}</td>
            <td>${rolePill}</td>
            <td>${statusPill}</td>
            <td>
              ${isCurrent ? `<span style="font-size:11px; color:#64748b;">(Current User)</span>` : `
                <select class="admin-role-select" onchange="AuthManager.changeUserRole('${u.user_id}', this.value)">
                  <option value="it_team" ${u.authorized_role === "it_team" ? "selected" : ""}>IT Team</option>
                  <option value="admin" ${u.authorized_role === "admin" ? "selected" : ""}>Admin</option>
                </select>
              `}
            </td>
          </tr>
        `;
      }).join("");
    } catch (err) {
      this.elements.adminTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#f87171; padding:15px;">Failed to load users: ${err.message}</td></tr>`;
    }
  },

  async changeUserRole(userId, newRole) {
    try {
      const res = await fetch("/api/admin/assign-role", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, new_role: newRole })
      });
      if (!res.ok) {
        const err = await res.json();
        alert(`Failed to assign role: ${err.detail || "Server error"}`);
      } else {
        if (this.currentUser && this.currentUser.user_id === userId) {
          this.currentUser.authorized_role = newRole;
          this.renderHeaderAuthenticated();
        }
        this.loadAdminUsers();
      }
    } catch (err) {
      alert(`Role assignment error: ${err.message}`);
    }
  },

  showAlert(message, type = "error") {
    if (!this.elements.alertBanner) return;
    this.elements.alertBanner.className = `auth-alert-banner alert-${type}`;
    this.elements.alertBanner.textContent = message;
    this.elements.alertBanner.classList.remove("hidden");
  },

  hideAlert() {
    if (!this.elements.alertBanner) return;
    this.elements.alertBanner.classList.add("hidden");
    this.elements.alertBanner.textContent = "";
  }
};

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => AuthManager.init());
} else {
  AuthManager.init();
}
