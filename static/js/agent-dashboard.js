/**
 * AUREX AGENT DASHBOARD — Right-Rail HUD
 * ============================================================
 * TEMPORARY FEATURE — to remove: delete this file and the
 * <script src="/static/js/agent-dashboard.js"> tag in index.html
 * ============================================================
 *
 * Injects a collapsible right-hand panel showing:
 *  - Context budget (token usage ring + bar)
 *  - Active memories in context
 *  - Active workspace files
 *  - Quick AI state indicator
 */

(function aurexAgentDashboard() {
  'use strict';

  // ── CONFIG ──────────────────────────────────────────────────
  const PANEL_WIDTH    = 260;       // px when open
  const POLL_INTERVAL  = 6000;      // ms between data refreshes
  const STORAGE_KEY    = 'aurex-dashboard-open';

  // ── STATE ───────────────────────────────────────────────────
  let isOpen        = localStorage.getItem(STORAGE_KEY) !== 'false'; // default: open
  let pollTimer     = null;
  let currentSid    = null;
  let lastCtx       = null;
  let lastMemories  = [];

  // ── DOM CREATION ────────────────────────────────────────────
  function buildPanel() {
    const panel = document.createElement('aside');
    panel.id = 'aurex-dashboard';
    panel.innerHTML = `
      <div class="adb-header">
        <span class="adb-title">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
          Agent HUD
        </span>
        <button id="adb-toggle-btn" title="Collapse dashboard" aria-label="Toggle dashboard">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
      </div>

      <!-- AI State -->
      <div class="adb-section">
        <div class="adb-section-label">AI STATE</div>
        <div class="adb-state-row" id="adb-ai-state">
          <span class="adb-state-dot idle"></span>
          <span class="adb-state-text">Idle</span>
        </div>
      </div>

      <!-- Context Budget -->
      <div class="adb-section" id="adb-ctx-section">
        <div class="adb-section-label">CONTEXT BUDGET</div>
        <div class="adb-ctx-ring-row">
          <svg class="adb-ring" viewBox="0 0 36 36">
            <circle class="adb-ring-bg" cx="18" cy="18" r="15.9"/>
            <circle class="adb-ring-fill" id="adb-ring-fill" cx="18" cy="18" r="15.9"
              stroke-dasharray="0 100" stroke-dashoffset="25"/>
          </svg>
          <div class="adb-ctx-stats">
            <div class="adb-ctx-pct" id="adb-ctx-pct">—</div>
            <div class="adb-ctx-tokens" id="adb-ctx-tokens">— / — tokens</div>
            <div class="adb-ctx-model" id="adb-ctx-model"></div>
          </div>
        </div>
        <div class="adb-bar-wrap">
          <div class="adb-bar-fill" id="adb-bar-fill" style="width:0%"></div>
        </div>
      </div>

      <!-- Active Memories -->
      <div class="adb-section">
        <div class="adb-section-label">ACTIVE MEMORIES <span class="adb-count" id="adb-mem-count">0</span></div>
        <div class="adb-list" id="adb-mem-list">
          <div class="adb-empty">No active memories</div>
        </div>
      </div>

      <!-- Workspace Files -->
      <div class="adb-section">
        <div class="adb-section-label">WORKSPACE FILES <span class="adb-count" id="adb-files-count">0</span></div>
        <div class="adb-list" id="adb-files-list">
          <div class="adb-empty">No files in context</div>
        </div>
      </div>
    `;

    document.body.appendChild(panel);

    // Toggle button
    document.getElementById('adb-toggle-btn').addEventListener('click', togglePanel);

    // Also create the tab trigger on the far right edge
    const tab = document.createElement('button');
    tab.id = 'adb-tab';
    tab.title = 'Toggle Agent Dashboard';
    tab.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>`;
    tab.addEventListener('click', togglePanel);
    document.body.appendChild(tab);

    return panel;
  }

  // ── TOGGLE ───────────────────────────────────────────────────
  function togglePanel() {
    isOpen = !isOpen;
    localStorage.setItem(STORAGE_KEY, isOpen);
    applyPanelState();
  }

  function applyPanelState() {
    const panel = document.getElementById('aurex-dashboard');
    const chatContainer = document.getElementById('chat-container');
    const tab = document.getElementById('adb-tab');
    const toggleBtn = document.getElementById('adb-toggle-btn');

    if (!panel) return;

    if (isOpen) {
      panel.classList.remove('collapsed');
      if (chatContainer) chatContainer.style.marginRight = PANEL_WIDTH + 'px';
      if (tab) tab.classList.remove('tab-visible');
      if (toggleBtn) toggleBtn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>`;
    } else {
      panel.classList.add('collapsed');
      if (chatContainer) chatContainer.style.marginRight = '';
      if (tab) tab.classList.add('tab-visible');
      if (toggleBtn) toggleBtn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>`;
    }
  }

  // ── DATA FETCHING ────────────────────────────────────────────
  function getCurrentSessionId() {
    if (window.sessionModule && window.sessionModule.getCurrentSessionId) {
      return window.sessionModule.getCurrentSessionId();
    }
    return null;
  }

  async function fetchContextData(sid) {
    if (!sid) return;
    try {
      const res = await fetch(`/api/session/${encodeURIComponent(sid)}/context`, { credentials: 'same-origin' });
      if (!res.ok) return;
      const data = await res.json();
      lastCtx = data;
      renderContext(data);
    } catch (_) {}
  }

  async function fetchMemories() {
    try {
      const res = await fetch(`${window.location.origin}/api/memory`, { credentials: 'same-origin' });
      if (!res.ok) return;
      const data = await res.json();
      lastMemories = data.memory || data.memories || [];
      renderMemories(lastMemories);
    } catch (_) {}
  }

  async function refreshAll() {
    const sid = getCurrentSessionId();
    currentSid = sid;
    if (sid) await fetchContextData(sid);
    await fetchMemories();
    updateAiState();
  }

  // ── RENDER ───────────────────────────────────────────────────
  function renderContext(data) {
    const pct      = Math.round(Number(data.context_percent || 0));
    const used     = data.used_tokens || 0;
    const total    = data.context_length || 0;
    const model    = String(data.model || '').split('/').pop();

    const ringFill = document.getElementById('adb-ring-fill');
    const pctEl    = document.getElementById('adb-ctx-pct');
    const toksEl   = document.getElementById('adb-ctx-tokens');
    const modelEl  = document.getElementById('adb-ctx-model');
    const barFill  = document.getElementById('adb-bar-fill');

    if (ringFill) {
      const circumference = 100;
      const filled = (pct / 100) * circumference;
      ringFill.setAttribute('stroke-dasharray', `${filled} ${circumference - filled}`);
      // colour based on usage
      const colour = pct > 85 ? '#ef4444' : pct > 60 ? '#f59e0b' : 'var(--aurex-accent)';
      ringFill.style.stroke = colour;
      if (barFill) { barFill.style.width = pct + '%'; barFill.style.background = colour; }
    }
    if (pctEl) pctEl.textContent = pct + '%';
    if (toksEl) toksEl.textContent = `${_fmt(used)} / ${_fmt(total)}`;
    if (modelEl) modelEl.textContent = model;
  }

  function renderMemories(memories) {
    const list    = document.getElementById('adb-mem-list');
    const counter = document.getElementById('adb-mem-count');
    if (!list) return;

    if (counter) counter.textContent = memories.length;

    if (!memories.length) {
      list.innerHTML = '<div class="adb-empty">No memories saved yet</div>';
      return;
    }

    // Show at most 5 most-recent memories
    const recent = memories.slice(-5).reverse();
    list.innerHTML = recent.map(m => {
      const txt = String(m.text || '').slice(0, 60) + (m.text && m.text.length > 60 ? '…' : '');
      const cat = m.category || 'fact';
      return `<div class="adb-item"><span class="adb-item-badge ${cat}">${cat}</span><span class="adb-item-text">${_esc(txt)}</span></div>`;
    }).join('');
  }

  function updateAiState() {
    const dot  = document.querySelector('#adb-ai-state .adb-state-dot');
    const text = document.querySelector('#adb-ai-state .adb-state-text');
    if (!dot || !text) return;

    const isStreaming = !!document.querySelector('.send-btn[data-mode="streaming"], .send-btn.send-pending');
    const isThinking  = !!document.querySelector('.agent-thread.streaming, .msg-ai.streaming');

    if (isStreaming || isThinking) {
      dot.className  = 'adb-state-dot active';
      text.textContent = isThinking ? 'Using tools…' : 'Generating…';
    } else {
      dot.className  = 'adb-state-dot idle';
      text.textContent = 'Idle';
    }

    // Workspace files — read from the DOM (any tool output referencing files)
    const fileMatches = Array.from(document.querySelectorAll('.agent-thread-cmd, .agent-thread-content'))
      .map(el => el.textContent)
      .join(' ')
      .match(/(?:\/[\w.\-/]+\.\w{1,6})/g) || [];
    const uniqueFiles = [...new Set(fileMatches)].slice(0, 6);

    const filesList  = document.getElementById('adb-files-list');
    const filesCount = document.getElementById('adb-files-count');
    if (filesCount) filesCount.textContent = uniqueFiles.length;
    if (filesList) {
      if (!uniqueFiles.length) {
        filesList.innerHTML = '<div class="adb-empty">No files detected</div>';
      } else {
        filesList.innerHTML = uniqueFiles.map(f => {
          const name = f.split('/').pop();
          return `<div class="adb-item"><span class="adb-item-file">${_esc(name)}</span><span class="adb-item-path">${_esc(f)}</span></div>`;
        }).join('');
      }
    }
  }

  // ── HELPERS ──────────────────────────────────────────────────
  function _fmt(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }
  function _esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // ── STYLES ───────────────────────────────────────────────────
  function injectStyles() {
    const style = document.createElement('style');
    style.id = 'aurex-dashboard-styles';
    style.textContent = `
      /* === AUREX AGENT DASHBOARD — THEME-AWARE STYLES (TEMPORARY) === */

      /* Panel uses the app's real --panel / --bg / --border / --fg / --accent vars
         so it perfectly matches whatever theme or accent color is active. */

      #aurex-dashboard {
        position: fixed;
        top: 0;
        right: 0;
        bottom: 0;
        width: ${PANEL_WIDTH}px;
        z-index: 90;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
        overflow-x: hidden;
        /* Use the app's panel/bg colour with a light frosted glass tint */
        background: color-mix(in srgb, var(--panel, #111) 92%, transparent);
        backdrop-filter: blur(24px) saturate(1.4);
        -webkit-backdrop-filter: blur(24px) saturate(1.4);
        border-left: 1px solid var(--border, rgba(255,255,255,0.08));
        color: var(--fg);
        transition: transform 0.35s cubic-bezier(0.22, 0.61, 0.36, 1),
                    opacity 0.35s ease;
        transform: translateX(0);
        opacity: 1;
        scrollbar-width: thin;
        scrollbar-color: color-mix(in srgb, var(--fg) 15%, transparent) transparent;
      }

      #aurex-dashboard.collapsed {
        transform: translateX(${PANEL_WIDTH}px);
        opacity: 0;
        pointer-events: none;
      }

      /* Floating re-open tab */
      #adb-tab {
        position: fixed;
        right: 0;
        top: 50%;
        transform: translateY(-50%) translateX(100%);
        z-index: 91;
        width: 28px;
        height: 56px;
        background: color-mix(in srgb, var(--panel, #111) 92%, transparent);
        border: 1px solid var(--border);
        border-right: none;
        border-radius: 8px 0 0 8px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        color: color-mix(in srgb, var(--fg) 50%, transparent);
        transition: transform 0.35s cubic-bezier(0.22, 0.61, 0.36, 1), color 0.2s;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
      }
      #adb-tab.tab-visible { transform: translateY(-50%) translateX(0); }
      #adb-tab:hover { color: var(--fg); }

      /* Header */
      .adb-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 14px 10px;
        border-bottom: 1px solid var(--border);
        flex-shrink: 0;
        /* Subtle accent tint on header */
        background: color-mix(in srgb, var(--accent, var(--red)) 6%, transparent);
      }
      .adb-title {
        display: flex;
        align-items: center;
        gap: 7px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--accent, var(--red));
      }
      #adb-toggle-btn {
        background: none;
        border: none;
        cursor: pointer;
        color: color-mix(in srgb, var(--fg) 45%, transparent);
        padding: 4px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        transition: color 0.2s, background 0.2s;
      }
      #adb-toggle-btn:hover {
        color: var(--fg);
        background: color-mix(in srgb, var(--fg) 8%, transparent);
      }

      /* Sections */
      .adb-section {
        padding: 12px 14px;
        border-bottom: 1px solid var(--border);
        flex-shrink: 0;
      }
      .adb-section-label {
        font-size: 9.5px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: color-mix(in srgb, var(--fg) 35%, transparent);
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .adb-count {
        background: color-mix(in srgb, var(--accent, var(--red)) 15%, transparent);
        border-radius: 20px;
        padding: 1px 6px;
        font-size: 9px;
        color: var(--accent, var(--red));
        font-weight: 700;
      }

      /* AI State */
      .adb-state-row { display: flex; align-items: center; gap: 9px; }
      .adb-state-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
        transition: background 0.4s;
      }
      .adb-state-dot.idle {
        background: color-mix(in srgb, var(--fg) 20%, transparent);
      }
      .adb-state-dot.active {
        background: var(--accent, var(--red));
        box-shadow: 0 0 8px var(--accent, var(--red));
        animation: adb-pulse 1.8s ease-in-out infinite;
      }
      @keyframes adb-pulse {
        0%,100% { opacity: 1; } 50% { opacity: 0.35; }
      }
      .adb-state-text {
        font-size: 12px;
        color: color-mix(in srgb, var(--fg) 65%, transparent);
        font-weight: 500;
      }

      /* Context ring */
      .adb-ctx-ring-row {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 10px;
      }
      .adb-ring { width: 52px; height: 52px; flex-shrink: 0; }
      .adb-ring-bg {
        fill: none;
        stroke: color-mix(in srgb, var(--fg) 8%, transparent);
        stroke-width: 4;
      }
      .adb-ring-fill {
        fill: none;
        stroke: var(--accent, var(--red));
        stroke-width: 4;
        stroke-linecap: round;
        transition: stroke-dasharray 0.6s ease, stroke 0.4s;
      }
      .adb-ctx-stats { flex: 1; min-width: 0; }
      .adb-ctx-pct   { font-size: 20px; font-weight: 700; color: var(--fg); line-height: 1.1; }
      .adb-ctx-tokens { font-size: 10px; color: color-mix(in srgb, var(--fg) 40%, transparent); margin-top: 2px; }
      .adb-ctx-model  { font-size: 10px; color: color-mix(in srgb, var(--fg) 28%, transparent); margin-top: 1px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

      /* Bar */
      .adb-bar-wrap {
        height: 4px;
        border-radius: 99px;
        background: color-mix(in srgb, var(--fg) 10%, transparent);
        overflow: hidden;
      }
      .adb-bar-fill {
        height: 100%;
        border-radius: 99px;
        background: var(--accent, var(--red));
        transition: width 0.6s ease, background 0.4s;
      }

      /* Lists */
      .adb-list {
        display: flex;
        flex-direction: column;
        gap: 5px;
        max-height: 140px;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: color-mix(in srgb, var(--fg) 10%, transparent) transparent;
      }
      .adb-empty {
        font-size: 11px;
        color: color-mix(in srgb, var(--fg) 25%, transparent);
        font-style: italic;
        text-align: center;
        padding: 8px 0;
      }
      .adb-item {
        display: flex;
        align-items: flex-start;
        gap: 7px;
        padding: 5px 7px;
        border-radius: 7px;
        background: color-mix(in srgb, var(--fg) 4%, transparent);
        border: 1px solid color-mix(in srgb, var(--fg) 7%, transparent);
        min-width: 0;
      }
      .adb-item-badge {
        font-size: 8.5px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 3px 6px;
        border-radius: 4px;
        background: var(--accent, #e06c75);
        color: #ffffff !important;
        border: none;
        flex-shrink: 0;
      }
      .adb-item-badge.preference { background: #2ea043; }
      .adb-item-badge.contact    { background: #d97706; }
      .adb-item-badge.event      { background: #d32f2f; }
      
      /* Light mode readability overrides for badges */
      :root.light .adb-item-badge { background: var(--accent, #d32f2f); }
      :root.light .adb-item-badge.preference { background: #1f883d; }
      :root.light .adb-item-badge.contact    { background: #b05c04; }
      :root.light .adb-item-badge.event      { background: #cf222e; }
      
      .adb-item-text {
        font-size: 10.5px;
        color: color-mix(in srgb, var(--fg) 60%, transparent);
        line-height: 1.4;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
        min-width: 0;
      }
      .adb-item-file {
        font-size: 10.5px;
        color: var(--fg);
        font-family: monospace;
        font-weight: 600;
        flex-shrink: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .adb-item-path {
        color: color-mix(in srgb, var(--fg) 30%, transparent);
        font-family: monospace;
        font-size: 9px;
        align-self: center;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
        min-width: 0;
      }

      /* Chat container transition */
      #chat-container {
        transition: margin-right 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) !important;
      }

      /* Hide on small screens */
      @media (max-width: 900px) {
        #aurex-dashboard, #adb-tab { display: none !important; }
        #chat-container { margin-right: 0 !important; }
      }
    `;
    document.head.appendChild(style);
  }

  // ── INIT ─────────────────────────────────────────────────────

  function init() {
    injectStyles();
    buildPanel();
    applyPanelState();

    // First data load
    refreshAll();

    // Poll for updates
    pollTimer = setInterval(refreshAll, POLL_INTERVAL);

    // Also refresh immediately after each AI message finishes streaming
    document.addEventListener('aurex:stream-done', refreshAll);
    document.addEventListener('aurex:session-changed', refreshAll);

    // Watch send-btn state changes for AI state dot
    const observer = new MutationObserver(updateAiState);
    const sendBtn = document.querySelector('.send-btn');
    if (sendBtn) observer.observe(sendBtn, { attributes: true, attributeFilter: ['data-mode', 'class'] });

    // ── Settings toggle wiring ────────────────────────────────
    // The toggle in Settings > Appearance shows/hides the entire dashboard.
    // We use a separate localStorage key so "hidden by settings" is distinct
    // from "collapsed by the user clicking the arrow".
    const ENABLED_KEY = 'aurex-dashboard-enabled';

    function applyEnabledState(enabled) {
      const panel = document.getElementById('aurex-dashboard');
      const tab   = document.getElementById('adb-tab');
      if (!enabled) {
        if (panel) { panel.style.display = 'none'; }
        if (tab)   { tab.style.display   = 'none'; }
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer) chatContainer.style.marginRight = '';
      } else {
        if (panel) { panel.style.display = ''; }
        if (tab)   { tab.style.display   = ''; }
        applyPanelState(); // restore open/collapsed state
      }
    }

    function syncToggleUI() {
      const toggle = document.getElementById('agent-dashboard-toggle');
      if (!toggle) return;
      const enabled = localStorage.getItem(ENABLED_KEY) !== 'false';
      toggle.checked = enabled;
      applyEnabledState(enabled);
    }

    function bindToggle() {
      const toggle = document.getElementById('agent-dashboard-toggle');
      if (!toggle || toggle.dataset.adbBound) return;
      toggle.dataset.adbBound = '1';
      toggle.addEventListener('change', () => {
        const enabled = toggle.checked;
        localStorage.setItem(ENABLED_KEY, enabled);
        applyEnabledState(enabled);
      });
    }

    // Bind immediately and also after settings panel opens (it may not be in DOM yet)
    syncToggleUI();
    bindToggle();
    document.addEventListener('click', () => setTimeout(bindToggle, 200));
  }

  // Wait for DOM + modules to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    // Small delay so sessionModule is definitely available
    setTimeout(init, 800);
  }
})();
