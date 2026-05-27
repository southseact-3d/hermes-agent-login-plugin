/**
 * panel.js — JLCPCB Auth dashboard panel
 *
 * Renders a credentials management UI in the Hermes dashboard.
 * Uses the Hermes Plugin SDK (window.HermesPlugin) for tab registration
 * and API calls to the backend routes at /api/plugins/jlcpcb-auth/
 *
 * Design principles:
 *  - Password field is write-only — never displayed back to the user
 *  - Username shows only a redacted hint after saving
 *  - All API calls are to the local dashboard server (localhost)
 *  - No credentials are ever sent to or stored by the model
 */

(function () {
  "use strict";

  const API = "/api/plugins/jlcpcb-auth";

  // --------------------------------------------------------------------------
  // Styles
  // --------------------------------------------------------------------------
  const STYLES = `
    .jlc-panel {
      max-width: 560px;
      margin: 0 auto;
      padding: 2rem 1.5rem;
      font-family: var(--font-sans, system-ui, sans-serif);
      color: var(--foreground, #e2e8f0);
    }
    .jlc-panel h2 {
      font-size: 1.25rem;
      font-weight: 600;
      margin-bottom: 0.25rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .jlc-panel .jlc-subtitle {
      font-size: 0.85rem;
      color: var(--muted-foreground, #94a3b8);
      margin-bottom: 1.75rem;
    }
    .jlc-status-card {
      border: 1px solid var(--border, #334155);
      border-radius: var(--radius, 0.5rem);
      padding: 1rem 1.25rem;
      margin-bottom: 1.5rem;
      background: var(--card, rgba(15,23,42,0.6));
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }
    .jlc-stat { display: flex; flex-direction: column; gap: 0.2rem; }
    .jlc-stat-label {
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted-foreground, #64748b);
    }
    .jlc-stat-value { font-size: 0.9rem; font-weight: 500; }
    .badge-ok  { color: #4ade80; }
    .badge-missing { color: #f87171; }
    .badge-warn { color: #fb923c; }
    .jlc-form { display: flex; flex-direction: column; gap: 1rem; }
    .jlc-field { display: flex; flex-direction: column; gap: 0.35rem; }
    .jlc-field label {
      font-size: 0.82rem;
      font-weight: 500;
      color: var(--muted-foreground, #94a3b8);
    }
    .jlc-field input {
      padding: 0.55rem 0.75rem;
      border-radius: var(--radius, 0.375rem);
      border: 1px solid var(--border, #334155);
      background: var(--input, rgba(15,23,42,0.8));
      color: var(--foreground, #e2e8f0);
      font-size: 0.9rem;
      outline: none;
      transition: border-color 0.15s;
    }
    .jlc-field input:focus { border-color: var(--primary, #6366f1); }
    .jlc-field .jlc-hint {
      font-size: 0.76rem;
      color: var(--muted-foreground, #64748b);
    }
    .jlc-actions { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 0.5rem; }
    .jlc-btn {
      padding: 0.5rem 1.1rem;
      border-radius: var(--radius, 0.375rem);
      border: none;
      font-size: 0.87rem;
      font-weight: 500;
      cursor: pointer;
      transition: opacity 0.15s, background 0.15s;
    }
    .jlc-btn:disabled { opacity: 0.45; cursor: default; }
    .jlc-btn-primary {
      background: var(--primary, #6366f1);
      color: #fff;
    }
    .jlc-btn-primary:hover:not(:disabled) { opacity: 0.88; }
    .jlc-btn-ghost {
      background: transparent;
      border: 1px solid var(--border, #334155);
      color: var(--foreground, #e2e8f0);
    }
    .jlc-btn-ghost:hover:not(:disabled) { background: var(--muted, rgba(51,65,85,0.4)); }
    .jlc-btn-danger {
      background: transparent;
      border: 1px solid #ef4444;
      color: #f87171;
    }
    .jlc-btn-danger:hover:not(:disabled) { background: rgba(239,68,68,0.1); }
    .jlc-msg {
      margin-top: 0.75rem;
      padding: 0.6rem 0.9rem;
      border-radius: var(--radius, 0.375rem);
      font-size: 0.85rem;
      display: none;
    }
    .jlc-msg.show { display: block; }
    .jlc-msg.success { background: rgba(74,222,128,0.1); color: #4ade80; border: 1px solid rgba(74,222,128,0.3); }
    .jlc-msg.error   { background: rgba(248,113,113,0.1); color: #f87171; border: 1px solid rgba(248,113,113,0.3); }
    .jlc-msg.info    { background: rgba(99,102,241,0.1);  color: #a5b4fc; border: 1px solid rgba(99,102,241,0.3); }
    .jlc-divider { border: none; border-top: 1px solid var(--border, #1e293b); margin: 1.5rem 0; }
    .jlc-security-note {
      font-size: 0.78rem;
      color: var(--muted-foreground, #64748b);
      line-height: 1.55;
      padding: 0.75rem 1rem;
      border: 1px solid var(--border, #1e293b);
      border-radius: var(--radius, 0.375rem);
      background: var(--muted, rgba(15,23,42,0.4));
    }
    .jlc-security-note strong { color: var(--foreground, #e2e8f0); }
  `;

  // --------------------------------------------------------------------------
  // HTML template
  // --------------------------------------------------------------------------
  const TEMPLATE = `
    <style>${STYLES}</style>
    <div class="jlc-panel">
      <h2>🔐 JLCPCB Authentication</h2>
      <p class="jlc-subtitle">
        Manage credentials for automated JLCPCB logins.
        Credentials are stored in <code>~/.hermes/.env</code>
        and are <strong>never</strong> visible to the AI model.
      </p>

      <div class="jlc-status-card" id="jlc-status-card">
        <div class="jlc-stat">
          <span class="jlc-stat-label">Username</span>
          <span class="jlc-stat-value" id="jlc-username-status">—</span>
        </div>
        <div class="jlc-stat">
          <span class="jlc-stat-label">Password</span>
          <span class="jlc-stat-value" id="jlc-password-status">—</span>
        </div>
        <div class="jlc-stat">
          <span class="jlc-stat-label">Session</span>
          <span class="jlc-stat-value" id="jlc-session-status">—</span>
        </div>
        <div class="jlc-stat">
          <span class="jlc-stat-label">Env file</span>
          <span class="jlc-stat-value" id="jlc-envfile-status">—</span>
        </div>
      </div>

      <div class="jlc-form">
        <div class="jlc-field">
          <label for="jlc-username">Email / Username</label>
          <input
            type="email"
            id="jlc-username"
            placeholder="you@example.com"
            autocomplete="username"
          />
          <span class="jlc-hint">Your JLCPCB account email address.</span>
        </div>

        <div class="jlc-field">
          <label for="jlc-password">Password</label>
          <input
            type="password"
            id="jlc-password"
            placeholder="••••••••••••"
            autocomplete="current-password"
          />
          <span class="jlc-hint">
            Write-only. Once saved, the password is never displayed here.
            To update, enter a new value and save again.
          </span>
        </div>

        <div class="jlc-actions">
          <button class="jlc-btn jlc-btn-primary" id="jlc-save-btn">
            Save Credentials
          </button>
          <button class="jlc-btn jlc-btn-ghost" id="jlc-test-btn">
            Check Status
          </button>
          <button class="jlc-btn jlc-btn-danger" id="jlc-clear-btn">
            Clear Credentials
          </button>
        </div>

        <div class="jlc-msg" id="jlc-msg"></div>
      </div>

      <hr class="jlc-divider" />

      <div class="jlc-security-note">
        <strong>Security model:</strong>
        Credentials are stored in <code>~/.hermes/.env</code> (chmod 600) and
        injected into the Hermes process at startup via environment variables.
        The AI model only sees a tool called <code>jlcpcb_login()</code> with
        no parameters — it can trigger a login but <strong>never sees your
        username or password</strong>. A post-tool-call hook redacts any
        accidental leaks before results reach the model context.
      </div>
    </div>
  `;

  // --------------------------------------------------------------------------
  // Panel logic
  // --------------------------------------------------------------------------

  async function fetchStatus() {
    try {
      const res = await fetch(`${API}/status`);
      return await res.json();
    } catch {
      return null;
    }
  }

  function updateStatusCard(data) {
    if (!data) return;

    const { credentials, session, env_file_exists } = data;

    const usernameEl = document.getElementById("jlc-username-status");
    const passwordEl = document.getElementById("jlc-password-status");
    const sessionEl  = document.getElementById("jlc-session-status");
    const envEl      = document.getElementById("jlc-envfile-status");

    if (usernameEl) {
      usernameEl.innerHTML = credentials.username_set
        ? `<span class="badge-ok">✓ ${escapeHtml(credentials.username_hint)}</span>`
        : `<span class="badge-missing">✗ Not set</span>`;
    }
    if (passwordEl) {
      passwordEl.innerHTML = credentials.password_set
        ? `<span class="badge-ok">✓ Set</span>`
        : `<span class="badge-missing">✗ Not set</span>`;
    }
    if (sessionEl) {
      if (session.logged_in) {
        const mins = session.session_age_seconds
          ? Math.floor(session.session_age_seconds / 60)
          : 0;
        sessionEl.innerHTML = `<span class="badge-ok">✓ Active (${mins}m ago)</span>`;
      } else {
        sessionEl.innerHTML = `<span class="badge-warn">Not logged in</span>`;
      }
    }
    if (envEl) {
      envEl.innerHTML = env_file_exists
        ? `<span class="badge-ok">✓ ~/.hermes/.env</span>`
        : `<span class="badge-warn">Not yet created</span>`;
    }
  }

  function showMsg(text, type = "info") {
    const el = document.getElementById("jlc-msg");
    if (!el) return;
    el.textContent = text;
    el.className = `jlc-msg show ${type}`;
    setTimeout(() => el.classList.remove("show"), 6000);
  }

  function escapeHtml(str) {
    return str.replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  // --------------------------------------------------------------------------
  // Mount the panel
  // --------------------------------------------------------------------------

  function mount(container) {
    container.innerHTML = TEMPLATE;

    // Load initial status
    fetchStatus().then(updateStatusCard);

    // Save button
    document.getElementById("jlc-save-btn").addEventListener("click", async () => {
      const username = document.getElementById("jlc-username").value.trim();
      const password = document.getElementById("jlc-password").value;

      if (!username || !password) {
        showMsg("Please enter both username and password.", "error");
        return;
      }

      const btn = document.getElementById("jlc-save-btn");
      btn.disabled = true;
      btn.textContent = "Saving…";

      try {
        const res = await fetch(`${API}/credentials`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        const data = await res.json();

        if (data.success) {
          showMsg(`✓ Credentials saved for ${data.username_hint}`, "success");
          document.getElementById("jlc-username").value = "";
          document.getElementById("jlc-password").value = "";
          const status = await fetchStatus();
          updateStatusCard(status);
        } else {
          showMsg(data.detail || "Failed to save credentials.", "error");
        }
      } catch (e) {
        showMsg("Network error saving credentials.", "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "Save Credentials";
      }
    });

    // Test / refresh status button
    document.getElementById("jlc-test-btn").addEventListener("click", async () => {
      const btn = document.getElementById("jlc-test-btn");
      btn.disabled = true;
      btn.textContent = "Checking…";
      try {
        const res = await fetch(`${API}/test`, { method: "POST" });
        const data = await res.json();
        showMsg(data.message, data.success ? "info" : "error");
        const status = await fetchStatus();
        updateStatusCard(status);
      } catch {
        showMsg("Could not reach backend.", "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "Check Status";
      }
    });

    // Clear button
    document.getElementById("jlc-clear-btn").addEventListener("click", async () => {
      if (!confirm("Clear stored JLCPCB credentials? The agent will not be able to log in until new credentials are set.")) return;
      try {
        const res = await fetch(`${API}/clear`, { method: "POST" });
        const data = await res.json();
        showMsg(data.message, "info");
        const status = await fetchStatus();
        updateStatusCard(status);
      } catch {
        showMsg("Could not clear credentials.", "error");
      }
    });
  }

  // --------------------------------------------------------------------------
  // Register with Hermes Plugin SDK
  // --------------------------------------------------------------------------
  if (window.HermesPlugin) {
    window.HermesPlugin.registerTab({
      id: "jlcpcb-auth",
      label: "JLCPCB Auth",
      icon: "🔐",
      mount,
    });
  } else {
    // Fallback: auto-mount if SDK not present (standalone testing)
    document.addEventListener("DOMContentLoaded", () => {
      const root = document.getElementById("jlcpcb-auth-root") || document.body;
      mount(root);
    });
  }
})();
