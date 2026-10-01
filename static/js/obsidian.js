/**
 * ✨ Obsidian Vault & Knowledge Galaxy Module for Aurex
 * Provides full interactive Obsidian Vault exploration, 60fps Force Galaxy,
 * Note Reader/Editor with wikilink navigation, and desktop URI integration.
 */

const API_BASE = window.location.origin;

class ObsidianGalaxy {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.nodes = [];
    this.links = [];
    this.nodeMap = new Map();
    this.transform = { x: 0, y: 0, k: 0.5 };
    this.isDragging = false;
    this.dragNode = null;
    this.lastMouse = { x: 0, y: 0 };
    this.hoverNode = null;
    this.activeFilter = null;
    this.animId = null;
    this.initEvents();
  }

  setData(data) {
    // 1. Identify primary central core orb (MOC hub or highest degree)
    let centerNode = data.nodes.find(n => n.category === 'moc' || (n.title && n.title.includes('MOC')) || (n.id && n.id.includes('MOC')));
    if (!centerNode) {
      centerNode = data.nodes.reduce((max, n) => ((n.degree || 0) > (max?.degree || 0) ? n : max), data.nodes[0]);
    }

    const nonCenter = data.nodes.filter(n => n.id !== centerNode.id);

    // Group into orbital shells
    const shell1 = []; // Modules & Canvas (inner planetary orbit)
    const shell2 = []; // Major Concepts & Bridges (mid orbit)
    const shell3 = []; // Theorems & Mathematicians (deep orbit)
    const shell4 = []; // Definitions, Examples, Flashcards (outer sphere)

    nonCenter.forEach(n => {
      if (n.category === 'module' || n.category === 'canvas') {
        shell1.push(n);
      } else if (n.category === 'concept' || n.category === 'bridge') {
        shell2.push(n);
      } else if (n.category === 'theorem' || n.category === 'mathematician') {
        shell3.push(n);
      } else {
        shell4.push(n);
      }
    });

    const initNode = (n, rMin, rMax, index, total) => {
      const angle = (index / Math.max(1, total)) * Math.PI * 2 + (Math.random() - 0.5) * 0.35;
      const r = rMin + ((rMax - rMin) * (index % 4)) / 4 + (Math.random() - 0.5) * 10;
      const orbitSpeed = Math.min(1.4, Math.max(0.4, 9.5 / Math.sqrt(r + 35)));
      return {
        ...n,
        x: Math.cos(angle) * r,
        y: Math.sin(angle) * r,
        vx: -Math.sin(angle) * orbitSpeed * 0.6,
        vy: Math.cos(angle) * orbitSpeed * 0.6,
        radius: Math.max(5, Math.min(20, 5 + Math.sqrt(n.degree || 1) * 2.2)),
        isCenter: false
      };
    };

    this.nodes = [
      {
        ...centerNode,
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        radius: 25,
        isCenter: true
      },
      ...shell1.map((n, i) => initNode(n, 115, 145, i, shell1.length)),
      ...shell2.map((n, i) => initNode(n, 190, 245, i, shell2.length)),
      ...shell3.map((n, i) => initNode(n, 285, 345, i, shell3.length)),
      ...shell4.map((n, i) => initNode(n, 380, 460, i, shell4.length))
    ];

    this.centerNode = this.nodes[0];
    this.time = 0;

    this.nodeMap.clear();
    this.nodes.forEach(n => this.nodeMap.set(n.id, n));

    this.links = data.links.map(l => ({
      source: this.nodeMap.get(l.source),
      target: this.nodeMap.get(l.target)
    })).filter(l => l.source && l.target);

    // Initial camera centered at origin
    this.transform.x = this.canvas.width / 2;
    this.transform.y = this.canvas.height / 2;
    this.transform.k = 0.52;

    this.startSimulation();
  }

  resize() {
    if (!this.canvas || !this.canvas.parentElement) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const w = Math.max(300, rect.width || window.innerWidth * 0.88 || 800);
    const h = Math.max(300, rect.height || window.innerHeight * 0.72 || 600);
    this.canvas.width = w;
    this.canvas.height = h;
    if (this.transform.x === 0 && this.transform.y === 0) {
      this.transform.x = w / 2;
      this.transform.y = h / 2;
    }
  }

  initEvents() {
    const c = this.canvas;

    c.addEventListener('mousedown', e => {
      const pos = this.screenToWorld(e.offsetX, e.offsetY);
      const clicked = this.findNodeAt(pos.x, pos.y);
      if (clicked) {
        this.dragNode = clicked;
      } else {
        this.isDragging = true;
      }
      this.lastMouse = { x: e.offsetX, y: e.offsetY };
    });

    window.addEventListener('mousemove', e => {
      if (!this.canvas.offsetParent) return;
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (this.dragNode) {
        const pos = this.screenToWorld(mouseX, mouseY);
        this.dragNode.x = pos.x;
        this.dragNode.y = pos.y;
        this.dragNode.vx = 0;
        this.dragNode.vy = 0;
      } else if (this.isDragging) {
        this.transform.x += mouseX - this.lastMouse.x;
        this.transform.y += mouseY - this.lastMouse.y;
        this.lastMouse = { x: mouseX, y: mouseY };
      } else {
        const pos = this.screenToWorld(mouseX, mouseY);
        const hovered = this.findNodeAt(pos.x, pos.y);
        if (hovered !== this.hoverNode) {
          this.hoverNode = hovered;
          this.onHover(hovered, e.clientX, e.clientY);
        }
      }
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
      this.dragNode = null;
    });

    // Zoom via mouse wheel — scatter ONLY happens while zooming in
    c.addEventListener('wheel', e => {
      e.preventDefault();
      const isZoomIn = e.deltaY < 0;
      const zoomFactor = isZoomIn ? 1.12 : 0.88;
      const newK = Math.max(0.18, Math.min(4.2, this.transform.k * zoomFactor));

      const mouseX = e.offsetX;
      const mouseY = e.offsetY;
      const focus = this.screenToWorld(mouseX, mouseY);

      this.transform.x = mouseX - (mouseX - this.transform.x) * (newK / this.transform.k);
      this.transform.y = mouseY - (mouseY - this.transform.y) * (newK / this.transform.k);
      this.transform.k = newK;

      // Scatter cluster ONLY while zooming in
      if (isZoomIn) {
        this.scatterClusterAt(focus.x, focus.y, 1.0);
      }
    }, { passive: false });

    c.addEventListener('click', e => {
      const pos = this.screenToWorld(e.offsetX, e.offsetY);
      const clicked = this.findNodeAt(pos.x, pos.y);
      if (clicked && this.onSelect) {
        this.onSelect(clicked);
      }
    });

    c.addEventListener('dblclick', e => {
      const pos = this.screenToWorld(e.offsetX, e.offsetY);
      const clicked = this.findNodeAt(pos.x, pos.y);
      const targetX = clicked ? clicked.x : pos.x;
      const targetY = clicked ? clicked.y : pos.y;

      const newK = Math.min(4.2, this.transform.k * 1.35);
      const cx = this.canvas.width / 2;
      const cy = this.canvas.height / 2;

      this.transform.k = newK;
      this.transform.x = cx - targetX * newK;
      this.transform.y = cy - targetY * newK;

      this.scatterClusterAt(targetX, targetY, 1.5);
    });
  }

  // Gently scatters only the cluster of nodes immediately under the zoom cursor
  scatterClusterAt(fx, fy, intensity = 1.0) {
    const radiusOfEffect = 175;
    for (const n of this.nodes) {
      if (n === this.dragNode) continue;
      const dx = n.x - fx;
      const dy = n.y - fy;
      const d = Math.sqrt(dx * dx + dy * dy);

      if (d < radiusOfEffect) {
        const factor = ((radiusOfEffect - d) / radiusOfEffect) * 3.5 * intensity;
        let angle = d > 1 ? Math.atan2(dy, dx) : Math.random() * Math.PI * 2;
        angle += (Math.random() - 0.5) * 0.25;

        n.vx += Math.cos(angle) * factor;
        n.vy += Math.sin(angle) * factor;
      }
    }
  }

  scatterAll(intensity = 1.0) {
    for (const n of this.nodes) {
      if (n === this.dragNode) continue;
      const angle = Math.atan2(n.y, n.x) + (Math.random() - 0.5) * 0.4;
      const force = (1.5 + Math.random() * 2.0) * intensity;
      n.vx += Math.cos(angle) * force;
      n.vy += Math.sin(angle) * force;
    }
  }

  screenToWorld(sx, sy) {
    return {
      x: (sx - this.transform.x) / this.transform.k,
      y: (sy - this.transform.y) / this.transform.k
    };
  }

  findNodeAt(x, y) {
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i];
      if (this.activeFilter && n.category !== this.activeFilter) continue;
      const dx = n.x - x;
      const dy = n.y - y;
      if (dx * dx + dy * dy <= (n.radius + 5) * (n.radius + 5)) {
        return n;
      }
    }
    return null;
  }

  startSimulation() {
    if (this.animId) cancelAnimationFrame(this.animId);

    const step = () => {
      this.updatePhysics();
      this.render();
      this.animId = requestAnimationFrame(step);
    };
    this.animId = requestAnimationFrame(step);
  }

  updatePhysics() {
    const alpha = 0.04;
    const repel = 340;
    const linkDist = 68;
    this.time = (this.time || 0) + 0.016;

    const cx = this.centerNode ? this.centerNode.x : 0;
    const cy = this.centerNode ? this.centerNode.y : 0;

    // Anchor the center core orb (unless actively being dragged by mouse)
    if (this.centerNode && this.centerNode !== this.dragNode) {
      this.centerNode.vx = 0;
      this.centerNode.vy = 0;
      this.centerNode.x += (0 - this.centerNode.x) * 0.06;
      this.centerNode.y += (0 - this.centerNode.y) * 0.06;
    }

    // 1. Orbital Mechanics: Tangential Velocity & Centripetal Gravity
    for (const n of this.nodes) {
      if (n.isCenter || n === this.dragNode) continue;

      const dx = n.x - cx;
      const dy = n.y - cy;
      const r = Math.hypot(dx, dy) || 1;

      // Tangential unit vector (counter-clockwise celestial orbit)
      const tx = -dy / r;
      const ty = dx / r;

      // Keplerian speed: inner orbits rotate smoothly, outer orbits stately
      const orbitSpeed = Math.min(1.3, Math.max(0.32, 9.2 / Math.sqrt(r + 35)));
      n.vx += tx * (orbitSpeed * 0.062);
      n.vy += ty * (orbitSpeed * 0.062);

      // Centripetal inward pull holding the node in stable circular orbit
      const centripetal = (0.0013 + 0.0000018 * r) * alpha;
      n.vx -= dx * centripetal;
      n.vy -= dy * centripetal;
    }

    // 2. Softened Pairwise Repulsion (+450 prevents overlap on the same orbit)
    for (let i = 0; i < this.nodes.length; i++) {
      const n1 = this.nodes[i];
      for (let j = i + 1; j < this.nodes.length; j++) {
        const n2 = this.nodes[j];
        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const d2 = dx * dx + dy * dy + 450;

        if (d2 < 55000) {
          const d = Math.sqrt(d2);
          const force = (repel / d2) * alpha;
          const fx = (dx / d) * force;
          const fy = (dy / d) * force;

          if (n1 !== this.dragNode && !n1.isCenter) { n1.vx -= fx; n1.vy -= fy; }
          if (n2 !== this.dragNode && !n2.isCenter) { n2.vx += fx; n2.vy += fy; }
        }
      }
    }

    // 3. Link Spring Forces — holds connected concepts as modular constellations
    for (const link of this.links) {
      const s = link.source;
      const t = link.target;
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (d - linkDist) * 0.006 * alpha;
      const fx = (dx / d) * force;
      const fy = (dy / d) * force;
      if (s !== this.dragNode && !s.isCenter) { s.vx += fx; s.vy += fy; }
      if (t !== this.dragNode && !t.isCenter) { t.vx += fx; t.vy += fy; }
    }

    // 4. Soft Cosmic Boundary, Velocity Limiter & Orbital Damping
    const maxSpeed = 4.8;
    for (const n of this.nodes) {
      if (n === this.dragNode || n.isCenter) continue;

      // Soft outer boundary keeping nodes within cosmic horizon
      const dist = Math.hypot(n.x - cx, n.y - cy);
      if (dist > 520) {
        const pull = (dist - 520) * 0.015;
        n.vx -= ((n.x - cx) / dist) * pull;
        n.vy -= ((n.y - cy) / dist) * pull;
      }

      // Clamp max velocity
      const spd = Math.hypot(n.vx, n.vy);
      if (spd > maxSpeed) {
        n.vx = (n.vx / spd) * maxSpeed;
        n.vy = (n.vy / spd) * maxSpeed;
      }

      n.x += n.vx;
      n.y += n.vy;

      // Smooth orbital damping (balances continuous tangential impulse)
      n.vx *= 0.965;
      n.vy *= 0.965;
    }
  }

  render() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    ctx.save();
    ctx.translate(this.transform.x, this.transform.y);
    ctx.scale(this.transform.k, this.transform.k);

    const cx = this.centerNode ? this.centerNode.x : 0;
    const cy = this.centerNode ? this.centerNode.y : 0;

    // 0. Celestial Orbit Rings (faint planetarium track lines)
    const orbitRadii = [130, 220, 315, 420];
    ctx.save();
    ctx.setLineDash([4 / this.transform.k, 10 / this.transform.k]);
    ctx.lineWidth = 1 / this.transform.k;
    for (const r of orbitRadii) {
      ctx.strokeStyle = 'rgba(192, 132, 252, 0.08)';
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.restore();

    // 1. Draw Links
    ctx.lineWidth = 1 / this.transform.k;
    for (const link of this.links) {
      const s = link.source;
      const t = link.target;
      const isHighlighted = (this.hoverNode && (s === this.hoverNode || t === this.hoverNode));

      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);

      if (isHighlighted) {
        ctx.strokeStyle = 'rgba(216, 180, 254, 0.85)';
        ctx.lineWidth = 2.2 / this.transform.k;
      } else {
        ctx.strokeStyle = 'rgba(147, 197, 253, 0.11)';
        ctx.lineWidth = 0.9 / this.transform.k;
      }
      ctx.stroke();
    }

    // 2. Draw Nodes
    for (const n of this.nodes) {
      const isFiltered = this.activeFilter && n.category !== this.activeFilter;
      const isHovered = this.hoverNode === n;

      ctx.globalAlpha = isFiltered ? 0.15 : (isHovered ? 1 : 0.85);

      if (n.isCenter) {
        // --- Radiant Central Core Orb (Supermassive Star) ---
        const pulse = 1 + 0.14 * Math.sin((this.time || 0) * 2.5);

        // Grand Coronal Glow
        const grad = ctx.createRadialGradient(n.x, n.y, n.radius * 0.4, n.x, n.y, n.radius * 2.8 * pulse);
        grad.addColorStop(0, 'rgba(233, 213, 255, 0.45)');
        grad.addColorStop(0.5, 'rgba(192, 132, 252, 0.2)');
        grad.addColorStop(1, 'rgba(192, 132, 252, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius * 2.8 * pulse, 0, Math.PI * 2);
        ctx.fill();

        // Solar Corona Flare
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius * 1.5, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(233, 213, 255, 0.35)';
        ctx.fill();

        // Star Body
        ctx.beginPath();
        ctx.arc(n.x, n.y, isHovered ? n.radius + 4 : n.radius, 0, Math.PI * 2);
        ctx.fillStyle = '#e9d5ff';
        ctx.fill();

        // White Starlight Core
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius * 0.45, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();

        // Stellar Border
        ctx.lineWidth = 2.2 / this.transform.k;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();

        // Crown Core Label
        ctx.font = `bold ${Math.max(12, 13 / Math.sqrt(this.transform.k))}px sans-serif`;
        ctx.fillStyle = '#f8fafc';
        ctx.textAlign = 'center';
        ctx.fillText(`👑 ${n.title}`, n.x, n.y + n.radius + 15);
      } else {
        // --- Orbiting Stars ---
        if (n.radius > 10 || isHovered) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.radius * (isHovered ? 2.2 : 1.7), 0, Math.PI * 2);
          ctx.fillStyle = n.color.replace(')', ', 0.18)').replace('rgb', 'rgba');
          ctx.fill();
        }

        // Star Body
        ctx.beginPath();
        ctx.arc(n.x, n.y, isHovered ? n.radius + 3 : n.radius, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.fill();

        // Border
        ctx.lineWidth = 1.2 / this.transform.k;
        ctx.strokeStyle = isHovered ? '#ffffff' : 'rgba(255, 255, 255, 0.4)';
        ctx.stroke();

        // Label
        if (isHovered || n.radius >= 14 || this.transform.k > 0.85) {
          ctx.font = `${Math.max(10, 11 / Math.sqrt(this.transform.k))}px sans-serif`;
          ctx.fillStyle = isHovered ? '#ffffff' : '#cbd5e1';
          ctx.textAlign = 'center';
          ctx.fillText(n.title, n.x, n.y + n.radius + 12);
        }
      }
    }

    ctx.restore();
  }

  zoomIn() {
    const oldK = this.transform.k;
    const newK = Math.min(4.2, oldK * 1.25);
    const cx = this.canvas.width / 2;
    const cy = this.canvas.height / 2;
    const focus = this.screenToWorld(cx, cy);

    this.transform.x = cx - (cx - this.transform.x) * (newK / oldK);
    this.transform.y = cy - (cy - this.transform.y) * (newK / oldK);
    this.transform.k = newK;

    this.scatterClusterAt(focus.x, focus.y, 1.1);
  }

  zoomOut() {
    const oldK = this.transform.k;
    const newK = Math.max(0.18, oldK * 0.8);
    const cx = this.canvas.width / 2;
    const cy = this.canvas.height / 2;

    this.transform.x = cx - (cx - this.transform.x) * (newK / oldK);
    this.transform.y = cy - (cy - this.transform.y) * (newK / oldK);
    this.transform.k = newK;
  }

  resetView() {
    this.transform.x = this.canvas.width / 2;
    this.transform.y = this.canvas.height / 2;
    this.transform.k = 0.52;
  }
}

class ObsidianUI {
  constructor() {
    this.isOpen = false;
    this.galaxy = null;
    this.allNotes = [];
    this.activeNote = null;
    this.activeTab = 'galaxy';
    this.activeFilter = null;
    window.obsidianUI = this;

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.init());
    } else {
      this.init();
    }
  }

  init() {
    this.injectStyles();
    this.injectModal();
    this.bindSidebarButtons();
    this.bindShortcuts();
  }

  injectStyles() {
    if (!document.getElementById('obsidian-css-link')) {
      const link = document.createElement('link');
      link.id = 'obsidian-css-link';
      link.rel = 'stylesheet';
      link.href = '/static/css/obsidian.css';
      document.head.appendChild(link);
    }
  }

  injectModal() {
    if (document.getElementById('obsidian-modal')) return;
    if (!document.body) return;

    const modal = document.createElement('div');
    modal.id = 'obsidian-modal';
    modal.className = 'obsidian-modal-backdrop';
    modal.innerHTML = `
      <div class="obsidian-modal-window">
        <header class="obsidian-header">
          <div class="obsidian-brand">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
            <span>Obsidian Knowledge Galaxy</span>
          </div>

          <div class="obsidian-stats-badge" id="obsidian-stats-pill">
            <span>🌌 Loading vault...</span>
          </div>

          <div class="obsidian-tabs">
            <button class="obsidian-tab-btn active" data-tab="galaxy">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
              <span>Knowledge Galaxy</span>
            </button>
            <button class="obsidian-tab-btn" data-tab="notes">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
              <span>Vault Notes</span>
            </button>
            <button class="obsidian-tab-btn" data-tab="reader">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
              <span>Note Reader</span>
            </button>
          </div>

          <div class="obsidian-actions">
            <button class="obsidian-action-btn" id="obsidian-open-desktop-btn" title="Open vault in Obsidian Desktop">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              <span>Obsidian App</span>
            </button>
            <button class="obsidian-action-btn" id="obsidian-sync-rag-btn" title="Sync Vault to Aurex RAG Vector Engine">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
              <span>Sync RAG</span>
            </button>
            <button class="obsidian-close-btn" id="obsidian-close-modal-btn" title="Close (Esc)">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </header>

        <div class="obsidian-body">
          <!-- TAB 1: GALAXY -->
          <div class="obsidian-view-pane active" id="pane-galaxy">
            <div class="galaxy-canvas-container">
              <canvas id="obsidian-galaxy-canvas"></canvas>

              <div class="galaxy-floating-controls">
                <div class="galaxy-search-wrap">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                  <input type="text" id="galaxy-search-input" placeholder="Search constellations..." />
                </div>
              </div>

              <div class="galaxy-category-legend" id="galaxy-legend">
                <!-- Dynamically populated -->
              </div>

              <div class="galaxy-zoom-controls">
                <button class="galaxy-tool-btn" id="galaxy-zoom-in" title="Zoom In & Expand Cluster">+</button>
                <button class="galaxy-tool-btn" id="galaxy-zoom-out" title="Zoom Out">-</button>
                <button class="galaxy-tool-btn" id="galaxy-scatter-btn" title="Scatter & Disperse Constellations">✦</button>
                <button class="galaxy-tool-btn" id="galaxy-reset-view" title="Reset View">⌖</button>
              </div>

              <div class="galaxy-hover-card" id="galaxy-tooltip"></div>
            </div>
          </div>

          <!-- TAB 2: NOTES EXPLORER -->
          <div class="obsidian-view-pane" id="pane-notes">
            <div class="obsidian-notes-pane">
              <div class="notes-filter-bar" id="notes-folder-filters"></div>
              <div class="notes-grid" id="notes-card-grid"></div>
            </div>
          </div>

          <!-- TAB 3: NOTE READER & EDITOR -->
          <div class="obsidian-view-pane" id="pane-reader">
            <div class="obsidian-reader-pane">
              <div class="obsidian-reader-main">
                <div class="reader-header">
                  <div>
                    <h2 class="reader-title" id="reader-note-title">Select a Note</h2>
                    <div id="reader-note-meta" style="font-size:0.75rem; color:#94a3b8; margin-top:4px;"></div>
                  </div>
                  <div class="reader-actions">
                    <button class="obsidian-action-btn" id="reader-open-native-btn" title="Open this note in Desktop Obsidian">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                      <span>In App</span>
                    </button>
                    <button class="obsidian-action-btn" id="reader-edit-toggle-btn">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                      <span>Edit</span>
                    </button>
                    <button class="obsidian-action-btn" id="reader-save-btn" style="display:none; background:rgba(52,211,153,0.2); border-color:#34d399; color:#a7f3d0;">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                      <span>Save</span>
                    </button>
                  </div>
                </div>

                <div class="reader-content" id="reader-content-rendered">
                  <p style="color:#64748b; font-style:italic;">Click any star in the galaxy or note in the explorer to read its contents...</p>
                </div>
                <textarea class="reader-editor-textarea" id="reader-content-editor" style="display:none;"></textarea>
              </div>

              <!-- Sidebar: Backlinks & Forward Links -->
              <div class="obsidian-reader-sidebar">
                <div>
                  <div class="reader-section-title">Forward Links (References)</div>
                  <div id="reader-outgoing-links"></div>
                </div>
                <div>
                  <div class="reader-section-title">Backlinks (Mentioned In)</div>
                  <div id="reader-backlinks"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    this.bindModalEvents();
  }

  bindSidebarButtons() {
    const bindBtn = (id) => {
      const el = document.getElementById(id);
      if (el) {
        el.style.cursor = 'pointer';
        el.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.open();
        };
      }
    };

    bindBtn('tool-obsidian-btn');
    bindBtn('rail-obsidian');

    // Document-level delegated click listener (bulletproof fail-safe)
    document.addEventListener('click', (e) => {
      const trigger = e.target.closest('#tool-obsidian-btn, #rail-obsidian');
      if (trigger) {
        e.preventDefault();
        e.stopPropagation();
        this.open();
      }
    });
  }

  bindShortcuts() {
    window.addEventListener('keydown', e => {
      if (e.altKey && (e.key === 'o' || e.key === 'O')) {
        e.preventDefault();
        this.toggle();
      }
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
    });
  }

  bindModalEvents() {
    const modal = document.getElementById('obsidian-modal');
    if (!modal) return;

    // Close buttons
    const closeBtn = document.getElementById('obsidian-close-modal-btn');
    if (closeBtn) closeBtn.onclick = () => this.close();
    modal.onclick = (e) => {
      if (e.target === modal) this.close();
    };

    // Tab buttons
    modal.querySelectorAll('.obsidian-tab-btn').forEach(btn => {
      btn.onclick = () => this.switchTab(btn.dataset.tab);
    });

    // Open Desktop button
    const openDeskBtn = document.getElementById('obsidian-open-desktop-btn');
    if (openDeskBtn) {
      openDeskBtn.onclick = () => this.openInDesktopApp(this.activeNote ? this.activeNote.path : null);
    }

    const readerOpenBtn = document.getElementById('reader-open-native-btn');
    if (readerOpenBtn) {
      readerOpenBtn.onclick = () => {
        if (this.activeNote) this.openInDesktopApp(this.activeNote.path);
      };
    }

    // Sync RAG
    const syncBtn = document.getElementById('obsidian-sync-rag-btn');
    if (syncBtn) {
      syncBtn.onclick = async () => {
        syncBtn.style.opacity = '0.5';
        try {
          const res = await fetch('/api/obsidian/sync', { method: 'POST', credentials: 'same-origin' });
          const data = await res.json();
          if (data.success) {
            this.showToast(`✨ Synced ${data.stats.total_documents} notes into Aurex Knowledge Base!`);
          }
        } catch (err) {
          this.showToast('Failed to sync: ' + err.message);
        } finally {
          syncBtn.style.opacity = '1';
        }
      };
    }

    // Galaxy zoom controls
    const zoomIn = document.getElementById('galaxy-zoom-in');
    if (zoomIn) zoomIn.onclick = () => this.galaxy?.zoomIn();
    const zoomOut = document.getElementById('galaxy-zoom-out');
    if (zoomOut) zoomOut.onclick = () => this.galaxy?.zoomOut();
    const scatterBtn = document.getElementById('galaxy-scatter-btn');
    if (scatterBtn) scatterBtn.onclick = () => this.galaxy?.scatterAll(2.0);
    const resetV = document.getElementById('galaxy-reset-view');
    if (resetV) resetV.onclick = () => this.galaxy?.resetView();

    // Galaxy Search
    const searchInp = document.getElementById('galaxy-search-input');
    if (searchInp) {
      searchInp.oninput = (e) => {
        const q = e.target.value.toLowerCase().trim();
        if (!this.galaxy) return;
        if (!q) {
          this.galaxy.hoverNode = null;
        } else {
          const found = this.galaxy.nodes.find(n => n.title.toLowerCase().includes(q) || (n.stem && n.stem.toLowerCase().includes(q)));
          if (found) {
            this.galaxy.hoverNode = found;
            this.galaxy.transform.x = this.galaxy.canvas.width / 2 - found.x * this.galaxy.transform.k;
            this.galaxy.transform.y = this.galaxy.canvas.height / 2 - found.y * this.galaxy.transform.k;
          }
        }
      };
    }

    // Edit Toggle & Save in Reader
    const editToggle = document.getElementById('reader-edit-toggle-btn');
    const saveBtn = document.getElementById('reader-save-btn');
    const rendered = document.getElementById('reader-content-rendered');
    const editor = document.getElementById('reader-content-editor');

    if (editToggle && saveBtn && rendered && editor) {
      editToggle.onclick = () => {
        const isEditing = editor.style.display !== 'none';
        if (isEditing) {
          editor.style.display = 'none';
          rendered.style.display = 'block';
          saveBtn.style.display = 'none';
          editToggle.querySelector('span').textContent = 'Edit';
        } else {
          editor.style.display = 'block';
          rendered.style.display = 'none';
          saveBtn.style.display = 'inline-flex';
          editToggle.querySelector('span').textContent = 'Preview';
          editor.value = this.activeNote ? this.activeNote.content : '';
        }
      };

      saveBtn.onclick = async () => {
        if (!this.activeNote) return;
        saveBtn.style.opacity = '0.5';
        try {
          const res = await fetch('/api/obsidian/notes', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              path: this.activeNote.path,
              content: editor.value
            })
          });
          const data = await res.json();
          if (data.success) {
            this.showToast(`Saved note "${this.activeNote.title}" to Vault!`);
            await this.loadNote(this.activeNote.path);
            editor.style.display = 'none';
            rendered.style.display = 'block';
            saveBtn.style.display = 'none';
            editToggle.querySelector('span').textContent = 'Edit';
          }
        } catch (err) {
          this.showToast('Save failed: ' + err.message);
        } finally {
          saveBtn.style.opacity = '1';
        }
      };
    }
  }

  async open() {
    let modal = document.getElementById('obsidian-modal');
    if (!modal) {
      this.injectModal();
      modal = document.getElementById('obsidian-modal');
    }
    if (!modal) return;

    modal.classList.add('active');
    document.getElementById('tool-obsidian-btn')?.classList.add('active');
    document.getElementById('rail-obsidian')?.classList.add('active');
    this.isOpen = true;

    // Load status
    this.loadStatus().catch(e => console.warn('Status load error:', e));

    // Initialize Galaxy canvas
    if (!this.galaxy) {
      const canvas = document.getElementById('obsidian-galaxy-canvas');
      if (canvas) {
        this.galaxy = new ObsidianGalaxy(canvas);
        this.galaxy.onSelect = node => {
          this.loadNote(node.path);
          this.switchTab('reader');
        };
        this.galaxy.onHover = (node, cx, cy) => {
          const tip = document.getElementById('galaxy-tooltip');
          if (!tip) return;
          if (!node) {
            tip.style.display = 'none';
            return;
          }
          tip.style.display = 'block';
          tip.style.left = `${cx + 14}px`;
          tip.style.top = `${cy + 14}px`;
          tip.innerHTML = `
            <div class="galaxy-hover-title" style="color:${node.color}">${node.title}</div>
            <div class="galaxy-hover-meta">
              <span>${node.category_label || node.category || ''}</span> • <span>${node.degree || 0} links</span>
            </div>
          `;
        };
      }
    }

    if (this.galaxy) {
      setTimeout(() => this.galaxy.resize(), 60);
    }
    await this.loadGraph();
    await this.loadNotes();
  }

  close() {
    const modal = document.getElementById('obsidian-modal');
    if (modal) modal.classList.remove('active');
    document.getElementById('tool-obsidian-btn')?.classList.remove('active');
    document.getElementById('rail-obsidian')?.classList.remove('active');
    this.isOpen = false;
  }

  toggle() {
    if (this.isOpen) this.close();
    else this.open();
  }

  switchTab(tabName) {
    this.activeTab = tabName;
    const modal = document.getElementById('obsidian-modal');

    // Tab buttons
    modal.querySelectorAll('.obsidian-tab-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.tab === tabName);
    });

    // Tab panes
    modal.querySelectorAll('.obsidian-view-pane').forEach(p => {
      p.classList.remove('active');
    });

    const activePane = document.getElementById(`pane-${tabName}`);
    if (activePane) activePane.classList.add('active');

    if (tabName === 'galaxy' && this.galaxy) {
      setTimeout(() => this.galaxy.resize(), 50);
    }
  }

  async loadStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/obsidian/status`);
      const data = await res.json();
      const countBadge = document.getElementById('sidebar-obsidian-count');
      const pill = document.getElementById('obsidian-stats-pill');
      if (data.exists) {
        pill.innerHTML = `<span>🌌 ${data.total_notes} Notes • ${data.total_links} Links</span>`;
        if (countBadge) countBadge.textContent = data.total_notes;
      } else {
        pill.innerHTML = `<span>🌌 0 Notes</span>`;
        if (countBadge) countBadge.textContent = "0";
      }
    } catch (err) {
      console.error('Failed to load obsidian status', err);
    }
  }

  async loadGraph() {
    try {
      const res = await fetch(`${API_BASE}/api/obsidian/graph`);
      const data = await res.json();
      this.galaxy.setData(data);

      // Populate Legend
      const legend = document.getElementById('galaxy-legend');
      legend.innerHTML = '';

      Object.entries(data.categories).forEach(([key, info]) => {
        if (key === 'default') return;
        const pill = document.createElement('div');
        pill.className = 'galaxy-legend-pill';
        pill.style.color = info.hex;
        pill.innerHTML = `
          <span class="galaxy-legend-dot" style="background:${info.hex}"></span>
          <span>${info.label}</span>
        `;
        pill.addEventListener('click', () => {
          if (this.activeFilter === key) {
            this.activeFilter = null;
            pill.classList.remove('active');
          } else {
            legend.querySelectorAll('.galaxy-legend-pill').forEach(p => p.classList.remove('active'));
            this.activeFilter = key;
            pill.classList.add('active');
          }
          this.galaxy.activeFilter = this.activeFilter;
        });
        legend.appendChild(pill);
      });
    } catch (err) {
      console.error('Failed to load graph data', err);
    }
  }

  async loadNotes() {
    try {
      const res = await fetch(`${API_BASE}/api/obsidian/notes`);
      const data = await res.json();
      this.allNotes = data.notes;
      this.renderFolderFilters();
      this.renderNotesGrid(this.allNotes);
    } catch (err) {
      console.error('Failed to load notes', err);
    }
  }

  renderFolderFilters() {
    const bar = document.getElementById('notes-folder-filters');
    const folders = ['All', ...new Set(this.allNotes.map(n => n.folder).filter(Boolean))];

    bar.innerHTML = '';
    folders.forEach(f => {
      const chip = document.createElement('div');
      chip.className = `notes-folder-chip ${f === 'All' ? 'active' : ''}`;
      chip.textContent = f;
      chip.addEventListener('click', () => {
        bar.querySelectorAll('.notes-folder-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        const filtered = (f === 'All') ? this.allNotes : this.allNotes.filter(n => n.folder === f);
        this.renderNotesGrid(filtered);
      });
      bar.appendChild(chip);
    });
  }

  renderNotesGrid(notes) {
    const grid = document.getElementById('notes-card-grid');
    grid.innerHTML = '';

    notes.forEach(note => {
      const card = document.createElement('div');
      card.className = 'note-card';
      card.style.setProperty('--card-color', note.color);
      card.innerHTML = `
        <div class="note-card-title">${note.title}</div>
        <div class="note-card-folder">${note.folder} • ${note.category}</div>
        <div class="note-card-tags">
          ${(note.tags || []).slice(0, 3).map(t => `<span class="note-card-tag">#${t}</span>`).join('')}
        </div>
        <div class="note-card-footer">
          <span>${note.link_count} links</span>
          <button class="obsidian-action-btn" style="padding:2px 8px; font-size:0.7rem;" title="Open in Obsidian Desktop">↗ Open</button>
        </div>
      `;

      card.addEventListener('click', e => {
        if (e.target.closest('button')) {
          e.stopPropagation();
          this.openInDesktopApp(note.path);
        } else {
          this.loadNote(note.path);
          this.switchTab('reader');
        }
      });

      grid.appendChild(card);
    });
  }

  async loadNote(path) {
    try {
      let res = await fetch(`${API_BASE}/api/obsidian/notes/${encodeURIComponent(path)}`);
      if (!res.ok) {
        // If note doesn't exist, auto-create a blank one just like Obsidian does!
        if (confirm(`The note "${path}" does not exist yet. Create it now?`)) {
            const createRes = await fetch(`${API_BASE}/api/obsidian`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'create',
                    path: path.endsWith('.md') ? path : path + '.md',
                    content: `---
tags: [ghost-resolved]
---
# ${path.split('/').pop().replace('.md', '')}

`
                })
            });
            if (createRes.ok) {
                res = await fetch(`${API_BASE}/api/obsidian/notes/${encodeURIComponent(path)}`);
            } else {
                throw new Error('Failed to create note');
            }
        } else {
            return;
        }
      }
      const note = await res.json();
      this.activeNote = note;

      document.getElementById('reader-note-title').textContent = note.title;
      document.getElementById('reader-note-meta').textContent = `${note.path} • ${note.category}`;

      // Render markdown content
      const rendered = document.getElementById('reader-content-rendered');
      rendered.innerHTML = this.renderMarkdown(note.content);

      // Bind clickable internal wikilinks
      rendered.querySelectorAll('a.internal-link').forEach(a => {
        a.addEventListener('click', e => {
          e.preventDefault();
          const target = a.dataset.target;
          this.loadNote(target);
        });
      });

      // Render Forward Links
      const outWrap = document.getElementById('reader-outgoing-links');
      outWrap.innerHTML = '';
      if (!note.outgoing_links || note.outgoing_links.length === 0) {
        outWrap.innerHTML = '<div style="font-size:0.75rem; color:#64748b;">No outgoing links</div>';
      } else {
        note.outgoing_links.forEach(l => {
          const item = document.createElement('div');
          item.className = 'reader-link-item';
          item.innerHTML = `<span>➔</span> <span>${l.alias || l.target}</span>`;
          item.addEventListener('click', () => this.loadNote(l.target));
          outWrap.appendChild(item);
        });
      }

      // Render Backlinks
      const backWrap = document.getElementById('reader-backlinks');
      backWrap.innerHTML = '';
      if (!note.backlinks || note.backlinks.length === 0) {
        backWrap.innerHTML = '<div style="font-size:0.75rem; color:#64748b;">No backlinks</div>';
      } else {
        note.backlinks.forEach(b => {
          const item = document.createElement('div');
          item.className = 'reader-link-item';
          item.innerHTML = `<span>⬅</span> <span>${b.title}</span>`;
          item.addEventListener('click', () => this.loadNote(b.path));
          backWrap.appendChild(item);
        });
      }

    } catch (err) {
      console.error('Failed to load note', err);
      this.showToast('Failed to load note: ' + err.message);
    }
  }

  renderMarkdown(text) {
    if (!text) return '';

    // Strip frontmatter
    let body = text.replace(/^---[\s\S]*?---\n*/, '');

    // Convert [[wikilinks]] (but ignore matrices like [[1,2],[3,4]])
    body = body.replace(/\[\[(.*?)(?:\|(.*?))?\]\]/g, (match, target, alias) => {
      // If the target looks like an array/matrix (contains '],[' or is just numbers/commas)
      if (target.includes('],[') || /^[0-9\s,\.\-]+$/.test(target)) {
        return match;
      }
      const cleanTarget = target.split('#')[0];
      const displayText = alias || cleanTarget.split('/').pop();
      return `<a class="internal-link" data-target="${cleanTarget}">${displayText}</a>`;
    });

    // Escape HTML (basic)
    // Convert headers
    body = body
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/gim, '<em>$1</em>')
      .replace(/^\> (.*$)/gim, '<blockquote style="border-left:3px solid #c084fc; padding-left:12px; margin:10px 0; color:#94a3b8;">$1</blockquote>')
      .replace(/\n\n/g, '<p></p>');

    return body;
  }

  async openInDesktopApp(path) {
    try {
      const res = await fetch(`${API_BASE}/api/obsidian/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path || '' })
      });
      const data = await res.json();
      if (data.opened || data.success) {
        this.showToast(`🚀 Opened in Obsidian desktop app!`);
      }
    } catch (err) {
      this.showToast('Failed to open app: ' + err.message);
    }
  }

  showToast(msg) {
    const toast = document.getElementById('toast');
    if (toast) {
      toast.textContent = msg;
      toast.classList.add('visible');
      setTimeout(() => toast.classList.remove('visible'), 3200);
    } else {
      console.log(msg);
    }
  }
}

// Instantiate on startup
const obsidianUI = new ObsidianUI();
window.obsidianUI = obsidianUI;

export default obsidianUI;
