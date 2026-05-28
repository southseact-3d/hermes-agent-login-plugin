(function () {
  "use strict";

  const pluginName = "jlcpcb-auth";
  const API = "/api/plugins/jlcpcb-auth";

  const registry = window.__HERMES_PLUGINS__;
  const SDK = window.__HERMES_PLUGIN_SDK__;
  const React = (SDK && SDK.React) || window.React;
  const hooks = (SDK && SDK.hooks) || React;

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

  const TEMPLATE = `
    <style>${STYLES}</style>
    <div class="jlc-panel">
      <h2>🔐 JLCPCB Authentication</h2>
      <p class="jlc-subtitle">
        Manage credentials for automated JLCPCB logins.
        Credentials are stored in <code>~/.hermes/.env</code>
        and are <strong>never</strong> visible to the AI model.
      </p>

      <div class="jlc-status-card" data-el="status-card">
        <div class="jlc-stat">
          <span class="jlc-stat-label">Username</span>
          <span class="jlc-stat-value" data-el="username-status">—</span>
        </div>
        <div class="jlc-stat">
          <span class="jlc-stat-label">Password</span>
          <span class="jlc-stat-value" data-el="password-status">—</span>
        </div>
        <div class="jlc-stat">
          <span class="jlc-stat-label">Session</span>
          <span class="jlc-stat-value" data-el="session-status">—</span>
        </div>
        <div class="jlc-stat">
          <span class="jlc-stat-label">Env file</span>
          <span class="jlc-stat-value" data-el="envfile-status">—</span>
        </div>
      </div>

      <div class="jlc-form">
        <div class="jlc-field">
          <label for="jlc-username">Email / Username</label>
          <input
            type="email"
            id="jlc-username"
            data-el="username-input"
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
            data-el="password-input"
            placeholder="••••••••••••"
            autocomplete="current-password"
          />
          <span class="jlc-hint">
            Write-only. Once saved, the password is never displayed here.
            To update, enter a new value and save again.
          </span>
        </div>

        <div class="jlc-actions">
          <button class="jlc-btn jlc-btn-primary" data-el="save-btn">
            Save Credentials
          </button>
          <button class="jlc-btn jlc-btn-ghost" data-el="test-btn">
            Check Status
          </button>
          <button class="jlc-btn jlc-btn-danger" data-el="clear-btn">
            Clear Credentials
          </button>
        </div>

        <div class="jlc-msg" data-el="msg"></div>
      </div>

      <hr class="jlc-divider" />

      <div class="jlc-security-note">
        <strong>Security model:</strong>
        Credentials are stored in <code>~/.hermes/.env</code> (chmod 600) and
        loaded by plugin tools at runtime. The AI model only sees
        <code>jlcpcb_login()</code> with no parameters and never receives the
        raw credential values.
      </div>
    </div>
  `;

  function escapeHtml(str) {
    return (str || "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  async function fetchStatus() {
    try {
      const res = await fetch(`${API}/status`);
      return await res.json();
    } catch {
      return null;
    }
  }

  function updateStatusCard(root, data) {
    if (!data || !root) {
      return;
    }

    const { credentials, session, env_file_exists } = data;

    const usernameEl = root.querySelector('[data-el="username-status"]');
    const passwordEl = root.querySelector('[data-el="password-status"]');
    const sessionEl = root.querySelector('[data-el="session-status"]');
    const envEl = root.querySelector('[data-el="envfile-status"]');

    if (usernameEl) {
      usernameEl.innerHTML = credentials.username_set
        ? `<span class="badge-ok">✓ ${escapeHtml(credentials.username_hint)}</span>`
        : '<span class="badge-missing">✗ Not set</span>';
    }
    if (passwordEl) {
      passwordEl.innerHTML = credentials.password_set
        ? '<span class="badge-ok">✓ Set</span>'
        : '<span class="badge-missing">✗ Not set</span>';
    }
    if (sessionEl) {
      if (session.logged_in) {
        const mins = session.session_age_seconds ? Math.floor(session.session_age_seconds / 60) : 0;
        sessionEl.innerHTML = `<span class="badge-ok">✓ Active (${mins}m ago)</span>`;
      } else {
        sessionEl.innerHTML = '<span class="badge-warn">Not logged in</span>';
      }
    }
    if (envEl) {
      envEl.innerHTML = env_file_exists
        ? '<span class="badge-ok">✓ ~/.hermes/.env</span>'
        : '<span class="badge-warn">Not yet created</span>';
    }
  }

  function showMsg(root, text, type) {
    const el = root && root.querySelector('[data-el="msg"]');
    if (!el) {
      return;
    }

    el.textContent = text;
    el.className = `jlc-msg show ${type || "info"}`;
    setTimeout(() => {
      el.classList.remove("show");
    }, 6000);
  }

  function mount(container) {
    if (!container) {
      return;
    }

    container.innerHTML = TEMPLATE;
    const scoped = container.querySelector(".jlc-panel") || container;

    fetchStatus().then((data) => updateStatusCard(scoped, data));

    const usernameInput = scoped.querySelector('[data-el="username-input"]');
    const passwordInput = scoped.querySelector('[data-el="password-input"]');
    const saveBtn = scoped.querySelector('[data-el="save-btn"]');
    const testBtn = scoped.querySelector('[data-el="test-btn"]');
    const clearBtn = scoped.querySelector('[data-el="clear-btn"]');

    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        const username = (usernameInput && usernameInput.value ? usernameInput.value : "").trim();
        const password = passwordInput && passwordInput.value ? passwordInput.value : "";

        if (!username || !password) {
          showMsg(scoped, "Please enter both username and password.", "error");
          return;
        }

        saveBtn.disabled = true;
        saveBtn.textContent = "Saving…";

        try {
          const res = await fetch(`${API}/credentials`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
          });
          const data = await res.json();

          if (data.success) {
            showMsg(scoped, `✓ Credentials saved for ${data.username_hint}`, "success");
            if (usernameInput) usernameInput.value = "";
            if (passwordInput) passwordInput.value = "";
            const status = await fetchStatus();
            updateStatusCard(scoped, status);
          } else {
            showMsg(scoped, data.detail || "Failed to save credentials.", "error");
          }
        } catch {
          showMsg(scoped, "Network error saving credentials.", "error");
        } finally {
          saveBtn.disabled = false;
          saveBtn.textContent = "Save Credentials";
        }
      });
    }

    if (testBtn) {
      testBtn.addEventListener("click", async () => {
        testBtn.disabled = true;
        testBtn.textContent = "Checking…";
        try {
          const res = await fetch(`${API}/test`, { method: "POST" });
          const data = await res.json();
          showMsg(scoped, data.message, data.success ? "info" : "error");
          const status = await fetchStatus();
          updateStatusCard(scoped, status);
        } catch {
          showMsg(scoped, "Could not reach backend.", "error");
        } finally {
          testBtn.disabled = false;
          testBtn.textContent = "Check Status";
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", async () => {
        if (!window.confirm("Clear stored JLCPCB credentials? The agent will not be able to log in until new credentials are set.")) {
          return;
        }

        try {
          const res = await fetch(`${API}/clear`, { method: "POST" });
          const data = await res.json();
          showMsg(scoped, data.message, "info");
          const status = await fetchStatus();
          updateStatusCard(scoped, status);
        } catch {
          showMsg(scoped, "Could not clear credentials.", "error");
        }
      });
    }
  }

  if (registry && React && hooks) {
    const useEffect = hooks.useEffect;
    const useRef = hooks.useRef;

    function JlcpcbAuthPanel() {
      const rootRef = useRef(null);
      useEffect(() => {
        mount(rootRef.current);
      }, []);
      return React.createElement("div", { ref: rootRef });
    }

    registry.register(pluginName, JlcpcbAuthPanel);
    return;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("jlcpcb-auth-root") || document.body;
    mount(root);
  });
})();
