/**
 * RESQAI - Main Application Controller & State Orchestrator
 * Coordinates real-time feeds, tab switching, telemetry, and toasts.
 */

const AppState = {
  activeTab: 'tab-overview',
  incidents: [],
  resources: [],
  shelters: [],
  alerts: [],
  weather: null,
  activeRoutePolyline: null,
  selectedCoords: { lat: 18.5204, lon: 73.8567 }
};

document.addEventListener('DOMContentLoaded', () => {
  initClock();
  initNavigation();
  initHeaderWeather();
  initQuickActions();

  // Load core application datasets
  loadInitialData();

  // Register PWA service worker if supported
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }

  // Periodic polling every 30 seconds for live command center telemetry
  setInterval(() => {
    refreshOverviewKPIs();
    if (typeof loadAlerts === 'function') loadAlerts(false);
  }, 30000);
});

/**
 * Live UTC and Local Clocks
 */
function initClock() {
  const clockTime = document.getElementById('clock-time');
  const clockDate = document.getElementById('clock-date');

  function update() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    
    if (clockTime) clockTime.textContent = `${hours}:${minutes}:${seconds} IST`;
    if (clockDate) clockDate.textContent = now.toISOString().split('T')[0];
  }

  update();
  setInterval(update, 1000);
}

/**
 * Tab Navigation Controller
 */
function initNavigation() {
  const navLinks = document.querySelectorAll('.nav-link[data-tab]');
  
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const tabId = link.getAttribute('data-tab');
      switchTab(tabId);
    });
  });

  const btnGotoReport = document.getElementById('btn-goto-report');
  if (btnGotoReport) {
    btnGotoReport.addEventListener('click', () => switchTab('tab-report'));
  }
}

function switchTab(tabId) {
  AppState.activeTab = tabId;

  // Update nav links
  document.querySelectorAll('.nav-link').forEach(l => {
    l.classList.toggle('active', l.getAttribute('data-tab') === tabId);
  });

  // Update tab panes
  document.querySelectorAll('.tab-pane').forEach(p => {
    p.classList.toggle('active', p.id === tabId);
  });

  // If switched to map, invalidate Leaflet map size
  if (tabId === 'tab-map' && window.resqaiMap) {
    setTimeout(() => {
      window.resqaiMap.invalidateSize();
    }, 150);
  }

  // Tab-specific lifecycle activations
  if (tabId === 'tab-disasters' && typeof loadDisasterFeed === 'function') {
    loadDisasterFeed();
  }
  if (tabId === 'tab-resources' && typeof loadEmergencyResources === 'function') {
    loadEmergencyResources();
  }
  if (tabId === 'tab-weather' && typeof loadWeatherCenterData === 'function') {
    loadWeatherCenterData();
  }
  if (tabId === 'tab-analytics' && typeof renderAnalyticsCharts === 'function') {
    renderAnalyticsCharts();
  }
  if (tabId === 'tab-health' && typeof runHealthProbe === 'function') {
    runHealthProbe();
  }
}

/**
 * Header Quick Weather Pill
 */
async function initHeaderWeather() {
  const tempElem = document.getElementById('weather-temp');
  const condElem = document.getElementById('weather-cond');
  const threatElem = document.getElementById('kpi-weather-threat');

  try {
    const res = await fetch('/api/weather?lat=18.5204&lon=73.8567&forecast=false');
    if (res.ok) {
      const data = await res.json();
      AppState.weather = data;
      if (tempElem) tempElem.textContent = `${data.temperature}°C`;
      if (condElem) condElem.textContent = data.condition;

      if (threatElem) {
        if (data.flood_threat_flag || data.storm_threat_flag) {
          threatElem.textContent = 'HIGH THREAT';
          threatElem.style.color = 'var(--sev-critical)';
        } else {
          threatElem.textContent = 'NORMAL';
          threatElem.style.color = 'var(--sev-low)';
        }
      }
    }
  } catch (err) {
    if (tempElem) tempElem.textContent = '26°C';
    if (condElem) condElem.textContent = 'Operational';
  }
}

/**
 * Header Quick Actions & Modals
 */
function initQuickActions() {
  const btnReport = document.getElementById('btn-quick-report');
  if (btnReport) {
    btnReport.addEventListener('click', () => switchTab('tab-report'));
  }

  const btnAlerts = document.getElementById('btn-header-alerts');
  if (btnAlerts) {
    btnAlerts.addEventListener('click', () => switchTab('tab-alerts'));
  }

  const btnModalClose = document.getElementById('modal-inc-close');
  const btnModalClose2 = document.getElementById('modal-inc-btn-close');
  if (btnModalClose) btnModalClose.addEventListener('click', closeIncidentModal);
  if (btnModalClose2) btnModalClose2.addEventListener('click', closeIncidentModal);

  const btnRefreshOverview = document.getElementById('btn-refresh-overview');
  if (btnRefreshOverview) {
    btnRefreshOverview.addEventListener('click', () => {
      loadInitialData();
      showToast('Command Center telemetry refreshed.', 'success');
    });
  }
}

/**
 * Load Initial Application Data
 */
async function loadInitialData() {
  await Promise.all([
    refreshOverviewKPIs(),
    loadIncidents(),
    loadResources(),
    loadShelters(),
    loadAlerts(false),
    loadRecentAuditFeed()
  ]);
}

/**
 * Refresh Command Center KPI Metrics
 */
async function refreshOverviewKPIs() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const stats = await res.json();

    const activeElem = document.getElementById('kpi-active-incidents');
    const critElem = document.getElementById('kpi-critical-sub');
    if (activeElem) activeElem.textContent = stats.incidents.active;
    if (critElem) critElem.textContent = `${stats.incidents.critical_active} Critical Tier`;

    const availElem = document.getElementById('kpi-avail-resources');
    const fleetElem = document.getElementById('kpi-fleet-sub');
    if (availElem) availElem.textContent = stats.resources.available;
    if (fleetElem) fleetElem.textContent = `${stats.resources.total} Total Units`;

    const shelterPctElem = document.getElementById('kpi-shelter-pct');
    const shelterSubElem = document.getElementById('kpi-shelter-sub');
    if (shelterPctElem) shelterPctElem.textContent = `${stats.shelters.utilization_pct}%`;
    if (shelterSubElem) shelterSubElem.textContent = `${stats.shelters.current_occupancy.toLocaleString()} / ${stats.shelters.total_capacity.toLocaleString()} Occupied`;

    const alertCount = document.getElementById('header-alert-count');
    if (alertCount) alertCount.textContent = stats.alerts.unacknowledged;

  } catch (err) {
    console.warn('Failed to refresh KPIs:', err);
  }
}

/**
 * Load Resources
 */
async function loadResources() {
  try {
    const res = await fetch('/api/resources?category=ambulance');
    const fleet = await fetch('/api/dispatch/fleet-units').catch(() => null);
    const data = await res.json();
    AppState.resources = data;

    const quickList = document.getElementById('quick-fleet-list');
    if (quickList) {
      quickList.innerHTML = data.slice(0, 5).map(r => `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:0.4rem 0; border-bottom:1px solid var(--border-subtle); font-size:0.78rem;">
          <div>
            <strong style="color:#fff;">${escapeHtml(r.name)}</strong>
            <div style="color:var(--text-dim); font-size:0.72rem;">${escapeHtml(r.base_station || r.address || '')}</div>
          </div>
          <span class="badge ${r.status === 'available' ? 'badge-low' : 'badge-high'}">${(r.status || 'READY').toUpperCase()}</span>
        </div>
      `).join('');
    }
  } catch (e) {}
}

/**
 * Load Shelters
 */
async function loadShelters() {
  try {
    const res = await fetch('/api/shelters');
    const data = await res.json();
    AppState.shelters = data;
  } catch (e) {}
}

/**
 * Load Recent Audit Logs
 */
async function loadRecentAuditFeed() {
  const container = document.getElementById('audit-feed-list');
  if (!container) return;

  try {
    const res = await fetch('/api/audit-logs?limit=8');
    const logs = await res.json();

    if (logs.length === 0) {
      container.innerHTML = '<div style="color: var(--text-dim); font-size: 0.78rem;">No recent audit activity.</div>';
      return;
    }

    container.innerHTML = logs.map(l => {
      const timeStr = new Date(l.timestamp).toLocaleTimeString('en-IN', { hour12: false });
      return `
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.76rem; border-bottom:1px solid rgba(255,255,255,0.04); padding:0.35rem 0;">
          <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:70%;">
            <strong style="color:var(--accent-cyan); font-family:var(--font-mono);">${l.action}</strong>
            <span style="color:var(--text-muted); margin-left:0.4rem;">${escapeHtml(l.actor || 'system')}</span>
          </div>
          <span style="color:var(--text-dim); font-family:var(--font-mono); font-size:0.7rem;">${timeStr}</span>
        </div>
      `;
    }).join('');
  } catch (e) {}
}

/**
 * Toast Notification System
 */
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : (type === 'error' ? '✕' : 'ℹ')}</span>
    <div>${message}</div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(50px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
