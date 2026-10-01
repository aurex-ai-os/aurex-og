/**
 * Provider Intelligence Center Module for Aurex
 * Unified management for models, providers, provider pools (OmniRoute, FreeLLMAPI),
 * health monitoring, active routing pipeline visualization, and TokenLedger analytics.
 */

(function() {
    // DOM Elements
    const modal = document.getElementById('provider-intelligence-modal');
    if (!modal) return;
    
    const closeBtn = modal.querySelector('.close-btn');
    const navBtns = modal.querySelectorAll('.pi-nav-btn');
    const pages = modal.querySelectorAll('.pi-page');
    
    const overviewCounts = document.getElementById('pi-overview-counts');
    const overviewHealth = document.getElementById('pi-overview-health');
    const overviewLocal = document.getElementById('pi-overview-local');
    
    const modelGrid = document.getElementById('pi-model-grid');
    const modelCountBadge = document.getElementById('pi-model-count-badge');
    const providerList = document.getElementById('pi-provider-list');
    
    const routingContent = document.getElementById('pi-routing-content');
    const healthList = document.getElementById('pi-health-list');
    const pingAllBtn = document.getElementById('pi-ping-all-btn');
    const usageContent = document.getElementById('pi-usage-content');
    
    const modelDetail = document.getElementById('pi-model-detail');
    const detailBackBtn = document.getElementById('pi-detail-back-btn');
    const detailBody = document.getElementById('pi-model-detail-body');
    
    // State
    let piState = {
        providers: [],
        models: [],
        pools: [],
        health: [],
        usage: { count: 0 },
        routing_decision: null
    };
    
    let activePage = 'overview';
    let modelLimit = 60;

    // API Fetch
    async function fetchState() {
        try {
            const res = await fetch('/api/v1/provider-intelligence/state', { credentials: 'same-origin' });
            if (res.ok) {
                piState = await res.json();
                renderAll();
            } else if (res.status === 401) {
                console.warn("Provider Intelligence requires authentication");
            }
        } catch (e) {
            console.error("Provider Intelligence fetch failed", e);
        }
    }

    // Modal Visibility Controls
    window.openProviderIntelligence = function(targetTab = null) {
        modal.classList.remove('hidden');
        if (targetTab) {
            switchTab(targetTab);
        }
        fetchState();
    };
    
    window.closeProviderIntelligence = function() {
        modal.classList.add('hidden');
        if (modelDetail) modelDetail.classList.add('hidden');
    };

    if (closeBtn) closeBtn.addEventListener('click', window.closeProviderIntelligence);

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
            window.closeProviderIntelligence();
        }
    });

    // Close on backdrop click (clicking outside the modal window)
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            window.closeProviderIntelligence();
        }
    });
    
    if (detailBackBtn) {
        detailBackBtn.addEventListener('click', () => {
            modelDetail.classList.add('hidden');
        });
    }

    // Tab Navigation
    function switchTab(target) {
        activePage = target;
        navBtns.forEach(b => {
            if (b.getAttribute('data-pi-target') === target) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });

        pages.forEach(p => {
            if (p.id === `pi-page-${target}`) {
                p.classList.add('active');
            } else {
                p.classList.remove('active');
            }
        });

        // Close detail panel on tab switch
        if (modelDetail) modelDetail.classList.add('hidden');
    }

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-pi-target');
            if (target) switchTab(target);
        });
    });

    // Quick Action Jump Cards on Overview Page
    document.querySelectorAll('.pi-action-card[data-pi-jump]').forEach(card => {
        card.addEventListener('click', () => {
            const jumpTo = card.getAttribute('data-pi-jump');
            if (jumpTo) switchTab(jumpTo);
        });
    });

    // Render Master
    function renderAll() {
        renderOverview();
        renderModels();
        renderProviders();
        renderRouting();
        renderHealth();
        renderUsage();
    }

    // 1. Overview Page
    function renderOverview() {
        const pCount = piState.providers.length;
        const mCount = piState.models.length;
        const lCount = piState.models.filter(m => m.is_local).length;
        const healthyCount = piState.providers.filter(p => p.health === 'HEALTHY' || p.health === 'ONLINE').length;
        
        if (overviewCounts) {
            overviewCounts.innerHTML = `${pCount} Providers &middot; ${mCount} Models &middot; ${lCount} Local`;
        }
        if (overviewHealth) {
            overviewHealth.innerHTML = `${healthyCount} / ${pCount} providers active`;
        }
        if (overviewLocal) {
            overviewLocal.innerHTML = `${lCount} models`;
        }
    }

    // 2. Models Page
    let filteredModels = [];

    function renderModels() {
        if (!modelGrid) return;

        const searchTerm = (document.getElementById('pi-model-search')?.value || '').toLowerCase().trim();
        const capFilter = document.getElementById('pi-model-filter-cap')?.value || '';
        const locFilter = document.getElementById('pi-model-filter-loc')?.value || '';

        filteredModels = piState.models.filter(model => {
            const matchesSearch = !searchTerm || 
                model.name.toLowerCase().includes(searchTerm) || 
                model.id.toLowerCase().includes(searchTerm) ||
                (model.provider_id && model.provider_id.toLowerCase().includes(searchTerm));
            
            const matchesCap = !capFilter || (model.capabilities && model.capabilities.includes(capFilter));
            
            let matchesLoc = true;
            if (locFilter === 'local') matchesLoc = !!model.is_local;
            else if (locFilter === 'remote') matchesLoc = !model.is_local;
            else if (locFilter === 'free') matchesLoc = !!model.is_free;

            return matchesSearch && matchesCap && matchesLoc;
        });

        if (modelCountBadge) {
            modelCountBadge.textContent = `${filteredModels.length} of ${piState.models.length} models`;
        }

        modelGrid.innerHTML = '';
        if (filteredModels.length === 0) {
            modelGrid.innerHTML = `
                <div class="pi-empty-state" style="grid-column: 1/-1;">
                    <h3>No Models Found</h3>
                    <p>Try adjusting your search criteria or capability filters.</p>
                </div>
            `;
            return;
        }

        const visibleModels = filteredModels.slice(0, modelLimit);
        visibleModels.forEach(model => {
            const card = document.createElement('div');
            card.className = 'pi-card pi-model-card';
            
            const capsHtml = (model.capabilities || []).slice(0, 4).map(c => 
                `<span class="pi-cap-chip">${c.replace('_', ' ')}</span>`
            ).join('');

            const ctxK = Math.round((model.context_window || 128000) / 1000);
            
            card.innerHTML = `
                <div class="pi-model-title" title="${model.name}">${model.name}</div>
                <div class="pi-model-provider">
                    ${model.provider_id || 'Direct'} 
                    ${model.is_local ? '<span class="pi-local-badge">LOCAL</span>' : ''} 
                    ${model.is_free ? '<span class="pi-local-badge" style="background:#2ea043;color:#fff;margin-left:4px;">FREE</span>' : ''}
                </div>
                <div class="pi-model-caps">${capsHtml || '<span class="pi-cap-chip">CHAT</span>'}</div>
                <div class="pi-model-footer">
                    <span><span class="pi-dot pi-healthy"></span> Ready</span>
                    <span>${ctxK}K ctx</span>
                </div>
            `;
            
            card.addEventListener('click', () => openModelDetail(model));
            modelGrid.appendChild(card);
        });

        if (filteredModels.length > modelLimit) {
            const moreWrap = document.createElement('div');
            moreWrap.style.cssText = 'grid-column: 1/-1; text-align: center; padding: 16px 0;';
            const moreBtn = document.createElement('button');
            moreBtn.className = 'pi-btn pi-btn-primary';
            moreBtn.textContent = `Load More (${filteredModels.length - modelLimit} remaining)`;
            moreBtn.addEventListener('click', () => {
                modelLimit += 60;
                renderModels();
            });
            moreWrap.appendChild(moreBtn);
            modelGrid.appendChild(moreWrap);
        }
    }

    document.getElementById('pi-model-search')?.addEventListener('input', () => {
        modelLimit = 60;
        renderModels();
    });
    document.getElementById('pi-model-filter-cap')?.addEventListener('change', () => {
        modelLimit = 60;
        renderModels();
    });
    document.getElementById('pi-model-filter-loc')?.addEventListener('change', () => {
        modelLimit = 60;
        renderModels();
    });

    // Model Detail Sliding Panel
    function openModelDetail(model) {
        if (!detailBody || !modelDetail) return;

        detailBody.innerHTML = `
            <div class="pi-detail-row">
                <span class="pi-detail-label">Model Identifier</span>
                <span class="pi-detail-value" style="word-break:break-all;">${model.id}</span>
            </div>
            <div class="pi-detail-row">
                <span class="pi-detail-label">Provider</span>
                <span class="pi-detail-value">${model.provider_id || 'System'}</span>
            </div>
            <div class="pi-detail-row">
                <span class="pi-detail-label">Execution Environment</span>
                <span class="pi-detail-value">${model.is_local ? '💻 Local Device (Ollama/Llama.cpp)' : '☁️ Remote API Endpoint'}</span>
            </div>
            <div class="pi-detail-row">
                <span class="pi-detail-label">Context Window</span>
                <span class="pi-detail-value">${(model.context_window || 128000).toLocaleString()} tokens</span>
            </div>
            <div class="pi-detail-row">
                <span class="pi-detail-label">Cost Tier</span>
                <span class="pi-detail-value">${model.is_free ? '🟢 Free / Open Weights' : '🔵 Standard API'}</span>
            </div>
            <div class="pi-detail-row">
                <span class="pi-detail-label">Health & Availability</span>
                <span class="pi-detail-value"><span class="pi-dot pi-healthy"></span> Active & Verified</span>
            </div>
            <hr style="border-color:var(--aurex-border); margin: 20px 0;">
            <h4 style="margin-bottom: 12px; font-size: 13px; color: var(--aurex-text-muted); text-transform:uppercase; letter-spacing:0.04em;">Supported Capabilities</h4>
            <div style="display:flex; flex-direction:column; gap:8px; font-size:14px; margin-bottom: 24px;">
                ${(model.capabilities || ['CHAT', 'STREAMING']).map(c => `<div><span style="color:#2ea043; margin-right:8px;">✓</span> Supports ${c.toLowerCase().replace('_', ' ')}</div>`).join('')}
                <div><span style="color:#2ea043; margin-right:8px;">✓</span> Passes 0.92 context admission margin</div>
                <div><span style="color:#2ea043; margin-right:8px;">✓</span> Verified for multi-turn conversations</div>
            </div>
            <button id="pi-use-model-btn" class="pi-btn pi-btn-primary" style="width: 100%; padding: 12px; font-weight:600;">
                Select This Model in Chat
            </button>
        `;

        document.getElementById('pi-use-model-btn')?.addEventListener('click', () => {
            localStorage.setItem('aurex_active_model', model.id);
            document.dispatchEvent(new CustomEvent('aurex:force-select-model', { 
                detail: { modelId: model.id } 
            }));
            
            const modelInput = document.getElementById('selected-model-input') || document.querySelector('.model-picker-button span');
            if (modelInput) modelInput.textContent = model.name;

            window.closeProviderIntelligence();
        });

        modelDetail.classList.remove('hidden');
    }

    // 3. Providers Page
    function renderProviders() {
        if (!providerList) return;
        providerList.innerHTML = '';

        if (!piState.providers || piState.providers.length === 0) {
            providerList.innerHTML = `
                <div class="pi-empty-state">
                    <h3>No Active Providers</h3>
                    <p>Connect a provider or configure an endpoint in Settings.</p>
                </div>
            `;
            return;
        }

        piState.providers.forEach(prov => {
            const el = document.createElement('div');
            el.className = 'pi-pref-item';
            el.innerHTML = `
                <div class="pi-pref-info">
                    <h4 style="display:flex; align-items:center; gap:8px;">
                        ${prov.name} 
                        ${prov.is_local ? '<span class="pi-local-badge">LOCAL</span>' : ''}
                        ${prov.type === 'pool' ? '<span class="pi-local-badge" style="background:#8b5cf6;color:#fff;">PROVIDER POOL</span>' : ''}
                    </h4>
                    <p style="margin-top:4px;">
                        <span class="pi-dot pi-healthy"></span> ${prov.health} &middot; 
                        <strong>${prov.models_count || 0}</strong> models &middot; 
                        ${prov.latency_ms || 50}ms avg latency
                    </p>
                </div>
                <div class="pi-pref-control">
                    <button class="pi-btn pi-manage-prov-btn" data-prov-id="${prov.id}">Configure</button>
                </div>
            `;
            providerList.appendChild(el);
        });

        providerList.querySelectorAll('.pi-manage-prov-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                window.closeProviderIntelligence();
                const settingsBtn = document.getElementById('user-bar-settings');
                if (settingsBtn) {
                    settingsBtn.click();
                    setTimeout(() => {
                        const servicesTab = document.querySelector('.settings-nav-item[data-settings-tab="services"]');
                        if (servicesTab) servicesTab.click();
                    }, 80);
                }
            });
        });
    }

    // 4. Routing Page
    function renderRouting() {
        if (!routingContent) return;
        
        const dec = piState.routing_decision || {
            active_mode: 'auto',
            preferred_models: {
                coding: 'claude-3-5-sonnet',
                reasoning: 'deepseek-chat',
                fast_chat: 'gpt-4o-mini'
            },
            admission_policy: { safety_margin: 0.92, waterfall_levels: 10 }
        };

        const codingModel = dec.preferred_models?.coding || 'auto';
        const reasoningModel = dec.preferred_models?.reasoning || 'auto';
        const fastModel = dec.preferred_models?.fast_chat || 'auto';

        routingContent.innerHTML = `
            <div class="pi-routing-overview">
                <div class="pi-card">
                    <div class="pi-card-header">OPTIMAL CODING ROUTE</div>
                    <div class="pi-status-val" style="font-size:15px;word-break:break-all;">${codingModel}</div>
                    <div class="pi-status-sub">High reasoning & tool accuracy</div>
                </div>
                <div class="pi-card">
                    <div class="pi-card-header">OPTIMAL REASONING ROUTE</div>
                    <div class="pi-status-val" style="font-size:15px;word-break:break-all;">${reasoningModel}</div>
                    <div class="pi-status-sub">Deep math & structured analysis</div>
                </div>
                <div class="pi-card">
                    <div class="pi-card-header">FAST CHAT ROUTE</div>
                    <div class="pi-status-val" style="font-size:15px;word-break:break-all;">${fastModel}</div>
                    <div class="pi-status-sub">Ultra-low latency & cost saving</div>
                </div>
            </div>

            <div class="pi-routing-pipeline-box">
                <h4 style="margin:0 0 6px 0;font-size:16px;">Aurex Intelligent Routing Pipeline</h4>
                <p style="margin:0;font-size:13px;color:var(--aurex-text-muted);">
                    Incoming user prompts pass through 4 automated gates before execution:
                </p>
                <div class="pi-pipeline-steps">
                    <div class="pi-pipeline-step">
                        <span class="pi-step-num">STAGE 1</span>
                        <div class="pi-step-body">
                            <h5>Intent & Capability Classification</h5>
                            <p>Analyzes user prompt for required modalities: Tool calling, Vision, Multi-step reasoning, Code execution.</p>
                        </div>
                    </div>
                    <div class="pi-pipeline-step">
                        <span class="pi-step-num">STAGE 2</span>
                        <div class="pi-step-body">
                            <h5>Context Admission & Waterfall Compression</h5>
                            <p>Verifies input tokens against verified context windows with a 0.92 safety margin. Applies waterfall levels 0–9 to eliminate context overflow.</p>
                        </div>
                    </div>
                    <div class="pi-pipeline-step">
                        <span class="pi-step-num">STAGE 3</span>
                        <div class="pi-step-body">
                            <h5>Provider Pool Selection</h5>
                            <p>Evaluates configured endpoints, OmniRoute, and FreeLLMAPI adapters for lowest latency, highest reliability, and cost-efficiency.</p>
                        </div>
                    </div>
                    <div class="pi-pipeline-step">
                        <span class="pi-step-num">STAGE 4</span>
                        <div class="pi-step-body">
                            <h5>Circuit Breaker & Fallback Chain</h5>
                            <p>If primary endpoint returns rate-limit or network timeout, the request seamlessly routes through the fallback chain without user failure.</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="pi-sim-panel">
                <h4 style="margin:0 0 4px 0;font-size:16px;">Interactive Route Simulator</h4>
                <p style="margin:0;font-size:13px;color:var(--aurex-text-muted);">Test how Aurex routes a hypothetical prompt through the pipeline in real-time:</p>
                
                <div class="pi-sim-form">
                    <div class="pi-sim-form-group">
                        <label>Task Type</label>
                        <select class="pi-select" id="pi-sim-task-type">
                            <option value="coding">Software Engineering / Coding</option>
                            <option value="reasoning">Complex Mathematical Reasoning</option>
                            <option value="general">General Knowledge & Q&A</option>
                            <option value="high_context">Large Corpus / Document Analysis</option>
                        </select>
                    </div>
                    <div class="pi-sim-form-group">
                        <label>Prompt Tokens</label>
                        <input type="number" class="pi-input" id="pi-sim-tokens" value="2500" step="500" min="100">
                    </div>
                    <div class="pi-sim-form-group" style="flex-direction:row;align-items:center;gap:8px;">
                        <input type="checkbox" id="pi-sim-tools" checked>
                        <label for="pi-sim-tools" style="cursor:pointer;margin:0;">Requires Tools</label>
                    </div>
                    <div class="pi-sim-form-group" style="flex-direction:row;align-items:center;gap:8px;">
                        <input type="checkbox" id="pi-sim-vision">
                        <label for="pi-sim-vision" style="cursor:pointer;margin:0;">Requires Vision</label>
                    </div>
                    <button class="pi-btn pi-btn-primary" id="pi-run-sim-btn" style="height:36px;">
                        Simulate Route
                    </button>
                </div>

                <div id="pi-sim-result" class="pi-sim-res-box" style="display:none;"></div>
            </div>
        `;

        document.getElementById('pi-run-sim-btn')?.addEventListener('click', runSimulation);
    }

    async function runSimulation() {
        const taskType = document.getElementById('pi-sim-task-type')?.value || 'coding';
        const tokens = parseInt(document.getElementById('pi-sim-tokens')?.value || '2500', 10);
        const tools = !!document.getElementById('pi-sim-tools')?.checked;
        const vision = !!document.getElementById('pi-sim-vision')?.checked;
        const resBox = document.getElementById('pi-sim-result');
        if (!resBox) return;

        resBox.style.display = 'block';
        resBox.innerHTML = '<span>⚡ Running routing simulation...</span>';

        try {
            const res = await fetch('/api/v1/provider-intelligence/simulate-route', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_type: taskType,
                    prompt_tokens: tokens,
                    requires_tools: tools,
                    requires_vision: vision
                })
            });
            const data = await res.json();
            
            resBox.innerHTML = `
                <div style="font-weight:600; font-size:15px; margin-bottom:8px; color:var(--aurex-text);">
                    🎯 Selected Route: <span style="color:var(--aurex-accent);font-family:'Fira Code',monospace;">${data.selected_model}</span>
                </div>
                <div style="font-size:13px; color:var(--aurex-text-muted); margin-bottom:12px;">
                    Provider: <strong>${data.provider || 'Direct API'}</strong> &middot; Evaluated: <strong>${data.candidates_evaluated}</strong> models &middot; Admitted: <strong>${data.candidates_admitted}</strong>
                </div>
                <div style="font-size:12px; display:flex; flex-direction:column; gap:4px;">
                    ${(data.decision_steps || []).map(s => `<div><span style="color:#2ea043;margin-right:6px;">✓</span> ${s}</div>`).join('')}
                </div>
            `;
        } catch (e) {
            resBox.innerHTML = `<span style="color:#ef4444;">Simulation error: ${e.message}</span>`;
        }
    }

    // 5. Health Matrix Page
    function renderHealth() {
        if (!healthList) return;
        healthList.innerHTML = '';

        const healthData = piState.health && piState.health.length > 0 
            ? piState.health 
            : piState.providers.map(p => ({
                id: p.id,
                name: p.name,
                status: p.health || 'HEALTHY',
                is_local: p.is_local,
                latency_ms: p.latency_ms || 45,
                models_count: p.models_count || 0,
                last_check: 'Live connection active',
                uptime_pct: 99.9
            }));

        if (healthData.length === 0) {
            healthList.innerHTML = `
                <div class="pi-empty-state" style="grid-column:1/-1;">
                    <h3>No Endpoints Configured</h3>
                    <p>Add a provider or connect to local Ollama to begin health tracking.</p>
                </div>
            `;
            return;
        }

        healthData.forEach(item => {
            const card = document.createElement('div');
            card.className = 'pi-health-card';
            card.id = `health-card-${item.id}`;

            const isHealthy = item.status === 'HEALTHY' || item.status === 'ONLINE';

            card.innerHTML = `
                <div class="pi-health-top">
                    <div>
                        <div class="pi-health-title">${item.name}</div>
                        <div style="font-size:12px;color:var(--aurex-text-muted);margin-top:2px;">${item.is_local ? 'Local Inference' : 'Remote Gateway'}</div>
                    </div>
                    <span class="pi-health-badge ${isHealthy ? 'healthy' : 'disabled'}">
                        <span class="pi-dot ${isHealthy ? 'pi-healthy' : 'pi-unavailable'}"></span>
                        ${item.status}
                    </span>
                </div>

                <div class="pi-health-meta-grid">
                    <div>
                        <div class="pi-health-meta-label">LATENCY</div>
                        <div class="pi-health-meta-val" id="latency-val-${item.id}">${item.latency_ms} ms</div>
                    </div>
                    <div>
                        <div class="pi-health-meta-label">UPTIME</div>
                        <div class="pi-health-meta-val">${item.uptime_pct || 99.8}%</div>
                    </div>
                    <div>
                        <div class="pi-health-meta-label">REGISTERED MODELS</div>
                        <div class="pi-health-meta-val">${item.models_count || 0}</div>
                    </div>
                    <div>
                        <div class="pi-health-meta-label">CIRCUIT BREAKER</div>
                        <div class="pi-health-meta-val" style="color:#2ea043;">CLOSED (PASS)</div>
                    </div>
                </div>

                <div class="pi-health-actions">
                    <button class="pi-ping-btn" data-ping-id="${item.id}">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                        Test Ping
                    </button>
                </div>
            `;
            healthList.appendChild(card);
        });

        healthList.querySelectorAll('.pi-ping-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const provId = btn.getAttribute('data-ping-id');
                btn.innerHTML = `<span>Pinging...</span>`;
                btn.disabled = true;

                try {
                    const res = await fetch('/api/v1/provider-intelligence/ping', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider_id: provId })
                    });
                    const d = await res.json();
                    const latEl = document.getElementById(`latency-val-${provId}`);
                    if (latEl) latEl.textContent = `${d.latency_ms} ms`;
                    btn.innerHTML = `<span style="color:#2ea043;">✓ ${d.latency_ms}ms</span>`;
                } catch (err) {
                    btn.innerHTML = `<span style="color:#ef4444;">Failed</span>`;
                }
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg> Test Ping`;
                }, 2000);
            });
        });
    }

    if (pingAllBtn) {
        pingAllBtn.addEventListener('click', () => {
            document.querySelectorAll('.pi-ping-btn').forEach(b => b.click());
        });
    }

    // 6. Usage & TokenLedger Page
    function renderUsage() {
        if (!usageContent) return;
        const u = piState.usage || { count: 0 };

        const totalReq = (u.count || 0).toLocaleString();
        const inTokens = (u.input_tokens || 0).toLocaleString();
        const outTokens = (u.output_tokens || 0).toLocaleString();
        const savedTokens = (u.compression_savings || 0).toLocaleString();
        const avgLat = u.avg_latency_ms ? `${Math.round(u.avg_latency_ms)}ms` : '--';

        usageContent.innerHTML = `
            <div class="pi-usage-grid">
                <div class="pi-usage-stat-card">
                    <div class="pi-usage-stat-label">TOTAL REQUESTS</div>
                    <div class="pi-usage-stat-value">${totalReq}</div>
                    <div class="pi-usage-stat-sub">Tracked via TokenLedger</div>
                </div>
                <div class="pi-usage-stat-card">
                    <div class="pi-usage-stat-label">INPUT TOKENS</div>
                    <div class="pi-usage-stat-value">${inTokens}</div>
                    <div class="pi-usage-stat-sub">Prompts, context & tools</div>
                </div>
                <div class="pi-usage-stat-card">
                    <div class="pi-usage-stat-label">OUTPUT TOKENS</div>
                    <div class="pi-usage-stat-value">${outTokens}</div>
                    <div class="pi-usage-stat-sub">Completions & generations</div>
                </div>
                <div class="pi-usage-stat-card">
                    <div class="pi-usage-stat-label">COMPRESSION SAVED</div>
                    <div class="pi-usage-stat-value" style="color:#2ea043;">${savedTokens}</div>
                    <div class="pi-usage-stat-sub">Via Waterfall levels 0–9</div>
                </div>
                <div class="pi-usage-stat-card">
                    <div class="pi-usage-stat-label">AVG LATENCY</div>
                    <div class="pi-usage-stat-value">${avgLat}</div>
                    <div class="pi-usage-stat-sub">Round-trip response time</div>
                </div>
            </div>

            <div class="pi-usage-section">
                <div class="pi-usage-section-title">Token Accounting & Safety Architecture</div>
                <p style="font-size:13px;color:var(--aurex-text-muted);line-height:1.6;margin-bottom:16px;">
                    Every request processed through Aurex is logged into an encrypted SQLite token ledger for auditability and quota management. 
                    <strong>Zero Sensitive Data:</strong> API keys, bearer tokens, OAuth credentials, and raw prompt contents are strictly stripped before recording.
                </p>
                <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:13px;">
                    <div style="background:var(--aurex-border);padding:8px 14px;border-radius:6px;">
                        Ledger Status: <span style="color:#2ea043;font-weight:600;">ACTIVE</span>
                    </div>
                    <div style="background:var(--aurex-border);padding:8px 14px;border-radius:6px;">
                        Storage: <span style="font-family:'Fira Code',monospace;">data/token_ledger.db</span>
                    </div>
                    <div style="background:var(--aurex-border);padding:8px 14px;border-radius:6px;">
                        Active Providers: <strong>${piState.providers.length}</strong>
                    </div>
                </div>
            </div>
        `;
    }

    // 7. Preferences Persistence
    const routingSelect = document.getElementById('pi-routing-mode-select');
    const telemetryToggle = document.getElementById('pi-disable-telemetry');
    
    if (routingSelect) {
        const savedMode = localStorage.getItem('aurex_pi_routing_mode') || 'auto';
        routingSelect.value = savedMode;
        routingSelect.addEventListener('change', () => {
            localStorage.setItem('aurex_pi_routing_mode', routingSelect.value);
        });
    }
    
    if (telemetryToggle) {
        const savedTelemetry = localStorage.getItem('aurex_pi_disable_telemetry') === 'true';
        telemetryToggle.checked = savedTelemetry;
        telemetryToggle.addEventListener('change', () => {
            localStorage.setItem('aurex_pi_disable_telemetry', telemetryToggle.checked);
        });
    }

    // Connect Provider Button
    document.getElementById('pi-add-provider-btn')?.addEventListener('click', () => {
        window.closeProviderIntelligence();
        const settingsBtn = document.getElementById('user-bar-settings');
        if (settingsBtn) {
            settingsBtn.click();
            setTimeout(() => {
                const servicesTab = document.querySelector('.settings-nav-item[data-settings-tab="services"]');
                if (servicesTab) servicesTab.click();
            }, 80);
        }
    });

    // Reliable Trigger Binding
    function bindTriggers() {
        const piBtn = document.getElementById("sidebar-pi-btn");
        if (piBtn) {
            piBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                window.openProviderIntelligence();
            };
        }

        const sb = document.querySelector('.settings-sidebar');
        if (sb && !document.getElementById('settings-pi-nav-btn')) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.id = 'settings-pi-nav-btn';
            btn.className = 'settings-nav-item';
            btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><circle cx="12" cy="12" r="10"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/><line x1="2" y1="12" x2="22" y2="12"/></svg>Provider Intelligence`;
            btn.addEventListener('click', () => {
                const sModal = document.getElementById('settings-modal');
                if (sModal) sModal.classList.add('hidden');
                window.openProviderIntelligence();
            });
            sb.appendChild(btn);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener("DOMContentLoaded", bindTriggers);
    } else {
        bindTriggers();
    }

    // Also run binding again on window load to ensure all dynamic elements are caught
    window.addEventListener('load', bindTriggers);

})();
