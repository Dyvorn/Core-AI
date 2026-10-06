/**
 * C.O.R.E. AI :: Sovereign Mesh Master Dashboard Controller
 * Real-time WebSocket connection to Edge Nodes & Gateway
 */

const STATE = {
  activeFilter: 'all',
  devices: [],
  models: {},
  events: [],
  wsConnected: false
};

const DEVICE_ICONS = {
  laptop: '💻',
  desktop: '🖥️',
  phone: '📱',
  vehicle_car: '🚗',
  vehicle: '🚗',
  vehicle_bike: '🚲',
  smart_glasses: '👓',
  mirror: '🪞',
  smart_mirror: '🪞',
  raspberry_pi: '🍓',
  arduino: '⚡',
  generic: '📡'
};

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
  setupEventListeners();
  connectWebSocket();
  // Poll server metrics every 6 seconds
  setInterval(fetchServerMetrics, 6000);
});

async function initDashboard() {
  await Promise.all([
    fetchServerStatus(),
    fetchServerMetrics(),
    fetchDevices(),
    fetchModels()
  ]);
}

function setupEventListeners() {
  // Filter chips
  document.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', (e) => {
      document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      STATE.activeFilter = chip.dataset.filter;
      renderEvents();
    });
  });

  // Goal Command Input
  const cmdForm = document.getElementById('command-form');
  if (cmdForm) {
    cmdForm.addEventListener('submit', handleCommandSubmit);
  }

  // Model Modal
  const openModelBtn = document.getElementById('btn-open-models');
  const closeModelBtn = document.getElementById('modal-close-btn');
  const cancelModelBtn = document.getElementById('modal-cancel-btn');
  const saveModelBtn = document.getElementById('modal-save-btn');
  const modalBackdrop = document.getElementById('model-modal');

  if (openModelBtn) {
    openModelBtn.addEventListener('click', openModelModal);
  }
  if (closeModelBtn) closeModelBtn.addEventListener('click', closeModelModal);
  if (cancelModelBtn) cancelModelBtn.addEventListener('click', closeModelModal);
  if (saveModelBtn) saveModelBtn.addEventListener('click', saveModelPreferences);
}

// WebSocket Connection
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/events`;
  
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    STATE.wsConnected = true;
    updatePulseStatus(true);
    addEvent({
      category: 'system',
      title: 'LIVE MESH LINK ESTABLISHED',
      desc: `Connected to Universal Gateway WebSocket on ${window.location.host}`,
      time: new Date().toLocaleTimeString(),
      data: { status: 'connected' }
    });
  };

  ws.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data);
      handleIncomingEvent(parsed);
    } catch (e) {
      console.error('Error parsing incoming WS message', e);
    }
  };

  ws.onclose = () => {
    STATE.wsConnected = false;
    updatePulseStatus(false);
    setTimeout(connectWebSocket, 4000);
  };

  ws.onerror = () => {
    STATE.wsConnected = false;
    updatePulseStatus(false);
  };
}

function updatePulseStatus(online) {
  const pulsePill = document.getElementById('pulse-indicator');
  const pulseText = document.getElementById('pulse-text');
  if (!pulsePill) return;

  if (online) {
    pulsePill.style.color = 'var(--emerald-live)';
    pulsePill.style.borderColor = 'rgba(0, 230, 153, 0.25)';
    pulsePill.style.background = 'rgba(0, 230, 153, 0.08)';
    pulseText.textContent = 'LIVE MESH LINK';
  } else {
    pulsePill.style.color = 'var(--amber-warn)';
    pulsePill.style.borderColor = 'rgba(255, 183, 3, 0.25)';
    pulsePill.style.background = 'rgba(255, 183, 3, 0.08)';
    pulseText.textContent = 'RECONNECTING MESH...';
  }
}

function handleIncomingEvent(msg) {
  const eventType = msg.event || 'EVENT';
  const data = msg.data || {};
  let category = 'edge';
  let title = eventType;
  let desc = JSON.stringify(data);

  if (eventType === 'EDGE_EVENT') {
    category = 'edge';
    title = `[NODE: ${data.node_id || 'UNKNOWN'}] EVENT`;
    desc = JSON.stringify(data.payload || data);
    fetchDevices(); // Refresh devices state
  } else if (eventType === 'PIPELINE_COMPLETED') {
    category = 'tool';
    title = `PIPELINE SOLVED (${data.status})`;
    desc = data.output ? (typeof data.output === 'string' ? data.output : JSON.stringify(data.output)) : data.error || 'Execution finished';
  } else if (eventType === 'BUS_EVENT') {
    category = 'voice';
    title = `TTS / AMBIENT DISPATCH`;
    desc = data.text || JSON.stringify(data);
  } else if (eventType === 'HUD_CARD') {
    category = 'voice';
    title = `HUD AMBIENT CARD`;
    desc = data.title ? `${data.title} - ${data.body || ''}` : JSON.stringify(data);
  }

  addEvent({
    category,
    title,
    desc,
    time: new Date().toLocaleTimeString(),
    data
  });
}

function addEvent(ev) {
  STATE.events.unshift(ev);
  if (STATE.events.length > 150) STATE.events.pop();
  renderEvents();
}

function renderEvents() {
  const container = document.getElementById('events-stream');
  if (!container) return;

  const filtered = STATE.activeFilter === 'all' 
    ? STATE.events 
    : STATE.events.filter(e => e.category === STATE.activeFilter);

  if (filtered.length === 0) {
    container.innerHTML = `<div style="color: var(--text-dim); text-align: center; padding: 24px; font-family: var(--font-mono);">No events in stream</div>`;
    return;
  }

  container.innerHTML = filtered.map(e => `
    <div class="event-entry">
      <div class="event-top-line">
        <span class="event-badge badge-${e.category}">${e.category}</span>
        <span class="event-time">${e.time}</span>
      </div>
      <div class="event-desc"><strong>${e.title}:</strong> ${escapeHtml(e.desc)}</div>
    </div>
  `).join('');
}

// REST Data Fetching
async function fetchServerStatus() {
  try {
    const res = await fetch('/api/v1/server/status');
    if (!res.ok) return;
    const data = await res.json();
    
    document.getElementById('nav-lan-ip').textContent = data.lan_ip || '127.0.0.1';
    document.getElementById('nav-operator').textContent = data.active_user || 'Operator';
    document.getElementById('kpi-active-model').textContent = data.active_model || 'heuristic';
    document.getElementById('kpi-nodes-count').textContent = data.connected_nodes_count || 0;
  } catch (err) {
    console.debug('Failed to fetch server status', err);
  }
}

async function fetchServerMetrics() {
  try {
    const res = await fetch('/api/v1/server/metrics');
    if (!res.ok) return;
    const data = await res.json();

    if (data.host) {
      document.getElementById('kpi-ram-usage').textContent = `${data.host.ram_used_percent}%`;
      document.getElementById('kpi-ram-sub').textContent = `${data.host.avail_ram_gb} GB Available / ${data.host.total_ram_gb} GB Total`;
      document.getElementById('nav-platform').textContent = `${data.host.platform} (${data.host.cpu_cores}C)`;
    }
    if (data.storage) {
      document.getElementById('kpi-zones-count').textContent = `${data.storage.zones_count} Zones`;
      document.getElementById('nav-db-size').textContent = `${data.storage.db_size_kb} KB`;
    }
    if (data.process && data.process.memory_rss_mb !== null) {
      document.getElementById('kpi-proc-rss').textContent = `${data.process.memory_rss_mb} MB RSS`;
    }
  } catch (err) {
    console.debug('Failed to fetch metrics', err);
  }
}

async function fetchDevices() {
  try {
    const [devRes, statusRes] = await Promise.all([
      fetch('/api/v1/devices'),
      fetch('/api/v1/server/status')
    ]);
    if (!devRes.ok) return;
    const devices = await devRes.json();
    const status = statusRes.ok ? await statusRes.json() : {};
    const liveConnectedIds = status.connected_edge_nodes || [];

    // Ensure host is always represented
    let allDevices = [...devices];
    const hasHost = allDevices.some(d => d.device_id === 'core_host' || d.name === 'Main Server');
    if (!hasHost) {
      allDevices.unshift({
        device_id: 'central_server',
        name: 'Sovereign Core Host',
        device_type: 'desktop',
        current_zone: 'server/hub',
        trust_tier: 'owner',
        capabilities: ['ai_kernel', 'gateway', 'mesh_router', 'database'],
        is_fixed_anchor: true,
        is_online: true
      });
    }

    STATE.devices = allDevices.map(d => ({
      ...d,
      is_online: d.device_id === 'central_server' || liveConnectedIds.includes(d.device_id)
    }));

    renderDevices();
  } catch (err) {
    console.debug('Failed to fetch devices', err);
  }
}

function renderDevices() {
  const container = document.getElementById('devices-grid');
  if (!container) return;

  if (STATE.devices.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); font-family: var(--font-mono); padding: 24px;">No devices enrolled in mesh yet.</div>`;
    return;
  }

  container.innerHTML = STATE.devices.map(d => {
    const icon = DEVICE_ICONS[d.device_type] || DEVICE_ICONS.generic;
    const statusClass = d.is_online ? 'status-online' : 'status-offline';
    const statusText = d.is_online ? 'ONLINE' : 'OFFLINE';
    const tier = (d.trust_tier || 'owner').toLowerCase();

    const capabilitiesHtml = (d.capabilities || []).map(c => 
      `<span class="tag-zone">${c}</span>`
    ).join('');

    return `
      <div class="device-card">
        <div class="device-card-header">
          <div class="device-identity">
            <div class="device-icon-box">${icon}</div>
            <div>
              <div class="device-name">${escapeHtml(d.name || d.device_id)}</div>
              <div class="device-id">${escapeHtml(d.device_id)}</div>
            </div>
          </div>
          <span class="device-status-badge ${statusClass}">${statusText}</span>
        </div>

        <div class="device-meta-row">
          <span class="tag-zone">📍 ${escapeHtml(d.current_zone || 'default')}</span>
          <span class="tag-tier tier-${tier}">${tier.toUpperCase()}</span>
          ${d.is_fixed_anchor ? '<span class="tag-zone">⚓ Fixed Anchor</span>' : '<span class="tag-zone">Roaming</span>'}
        </div>

        ${capabilitiesHtml ? `
        <div class="device-tools-box">
          <div class="tools-title">Capabilities</div>
          <div class="tools-list">${capabilitiesHtml}</div>
        </div>` : ''}
      </div>
    `;
  }).join('');
}

async function fetchModels() {
  try {
    const res = await fetch('/api/v1/models');
    if (!res.ok) return;
    STATE.models = await res.json();
  } catch (err) {
    console.debug('Failed to fetch models', err);
  }
}

// Command Submission
async function handleCommandSubmit(e) {
  e.preventDefault();
  const input = document.getElementById('command-input');
  const btn = document.getElementById('command-submit-btn');
  const drawer = document.getElementById('output-drawer');
  const spokenEl = document.getElementById('output-spoken');
  const stepsEl = document.getElementById('output-steps');

  const goal = input.value.trim();
  if (!goal) return;

  btn.disabled = true;
  btn.textContent = 'DISPATCHING...';
  drawer.classList.add('active');
  spokenEl.textContent = 'Reasoning across mesh...';
  stepsEl.innerHTML = '';

  try {
    const res = await fetch('/api/v1/pipeline/solve_sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, context: { client: 'dashboard' } })
    });

    const data = await res.json();
    spokenEl.textContent = data.spoken_response || data.final_output || 'Task completed.';

    if (data.steps && data.steps.length > 0) {
      stepsEl.innerHTML = data.steps.map(s => `
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
          ✓ Step [${s.name || s.id}]: Tool <code>${s.tool_name}</code> (${s.status})
        </div>
      `).join('');
    }

    addEvent({
      category: 'tool',
      title: `COMMAND: "${goal}"`,
      desc: data.spoken_response || data.final_output || 'Solved',
      time: new Date().toLocaleTimeString(),
      data
    });

    input.value = '';
  } catch (err) {
    spokenEl.textContent = `Execution error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'DISPATCH';
  }
}

// Model Preferences Modal
function openModelModal() {
  const modal = document.getElementById('model-modal');
  if (!modal) return;

  const currentRoles = (STATE.models && STATE.models.roles) ? STATE.models.roles : {};

  // Set current values in dropdowns if available
  const pSelect = document.getElementById('select-planner');
  const dSelect = document.getElementById('select-deep');
  const fSelect = document.getElementById('select-fallback');
  const lSelect = document.getElementById('select-fast');

  if (pSelect && currentRoles.planner) pSelect.value = currentRoles.planner.model;
  if (dSelect && currentRoles.deep_reasoning) dSelect.value = currentRoles.deep_reasoning.model;
  if (fSelect && currentRoles.fallback) fSelect.value = currentRoles.fallback.model;
  if (lSelect && currentRoles.fast_local) lSelect.value = currentRoles.fast_local.model;

  modal.classList.add('open');
}

function closeModelModal() {
  const modal = document.getElementById('model-modal');
  if (modal) modal.classList.remove('open');
}

async function saveModelPreferences() {
  const pVal = document.getElementById('select-planner').value;
  const dVal = document.getElementById('select-deep').value;
  const fVal = document.getElementById('select-fallback').value;
  const lVal = document.getElementById('select-fast').value;

  try {
    await Promise.all([
      fetch('/api/v1/models/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Trust-Tier': 'owner' },
        body: JSON.stringify({ role: 'planner', model_name: pVal })
      }),
      fetch('/api/v1/models/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Trust-Tier': 'owner' },
        body: JSON.stringify({ role: 'deep_reasoning', model_name: dVal })
      }),
      fetch('/api/v1/models/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Trust-Tier': 'owner' },
        body: JSON.stringify({ role: 'fallback', model_name: fVal })
      }),
      fetch('/api/v1/models/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Trust-Tier': 'owner' },
        body: JSON.stringify({ role: 'fast_local', model_name: lVal })
      })
    ]);

    closeModelModal();
    fetchServerStatus();
    fetchModels();

    addEvent({
      category: 'system',
      title: 'AI MODEL PREFERENCES UPDATED',
      desc: `Planner set to ${pVal}, Deep Reasoning set to ${dVal}`,
      time: new Date().toLocaleTimeString(),
      data: { planner: pVal, deep_reasoning: dVal }
    });
  } catch (err) {
    alert(`Failed to save preferences: ${err.message}`);
  }
}

function escapeHtml(str) {
  if (typeof str !== 'string') str = String(str || '');
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}
