/**
 * RESQAI - Real-Time Disaster Feed Controller
 * Aggregates USGS earthquakes, NDMA SACHET India alerts, Open-Meteo severe weather,
 * NASA FIRMS satellite thermal anomalies, and Citizen SOS reports.
 */

let currentDisasterFilter = 'all';
let currentSeverityFilter = 'all';

document.addEventListener('DOMContentLoaded', () => {
  initDisasterView();
});

function initDisasterView() {
  const btnRefresh = document.getElementById('btn-refresh-disasters');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => loadDisasterFeed());
  }

  // Filter chips
  const chips = document.querySelectorAll('.disaster-filter-chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentDisasterFilter = chip.getAttribute('data-filter') || 'all';
      loadDisasterFeed();
    });
  });

  // Severity selector
  const sevSelect = document.getElementById('disaster-sev-select');
  if (sevSelect) {
    sevSelect.addEventListener('change', (e) => {
      currentSeverityFilter = e.target.value;
      loadDisasterFeed();
    });
  }
}

async function loadDisasterFeed() {
  const container = document.getElementById('disaster-cards-container');
  const countBadge = document.getElementById('disaster-total-count');
  const statusBadge = document.getElementById('disaster-feed-status');
  if (!container) return;

  container.innerHTML = `
    <div style="grid-column: 1 / -1; text-align: center; padding: 2.5rem; color: var(--text-dim);">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite; margin-bottom: 0.5rem;"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
      <div>Querying USGS, NDMA SACHET, Open-Meteo, and Citizen command streams...</div>
    </div>
  `;

  try {
    let url = `/api/disasters?limit=80`;
    if (currentDisasterFilter !== 'all') {
      url += `&hazard_type=${encodeURIComponent(currentDisasterFilter)}`;
    }
    if (currentSeverityFilter !== 'all') {
      url += `&severity=${encodeURIComponent(currentSeverityFilter)}`;
    }

    const res = await fetch(url);
    const data = await res.json();

    if (countBadge) countBadge.textContent = `${data.total_events || 0} Events Active`;
    if (statusBadge) {
      statusBadge.textContent = data.status || 'LIVE DATA AVAILABLE';
      statusBadge.className = 'badge badge-success';
    }

    const events = data.events || [];
    if (events.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; background: var(--bg-card); border-radius: var(--radius-md); border: 1px dashed var(--border-subtle);">
          <div style="color: var(--text-muted); font-size: 1rem; font-weight: 600;">No active disaster records match current filter.</div>
          <div style="color: var(--text-dim); font-size: 0.8rem; margin-top: 0.4rem;">Select "All Hazards" or adjust severity threshold.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = events.map(evt => renderDisasterCard(evt)).join('');

    // Attach map locate listeners
    container.querySelectorAll('.btn-locate-disaster').forEach(btn => {
      btn.addEventListener('click', () => {
        const lat = parseFloat(btn.getAttribute('data-lat'));
        const lon = parseFloat(btn.getAttribute('data-lon'));
        const title = btn.getAttribute('data-title');
        if (!isNaN(lat) && !isNaN(lon)) {
          locateOnLiveMap(lat, lon, title);
        } else {
          showToast('Coordinates not available for this alert', 'info');
        }
      });
    });

  } catch (err) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--sev-critical);">
        Failed to retrieve real-time disaster streams. Reconnecting...
      </div>
    `;
    if (statusBadge) {
      statusBadge.textContent = 'SOURCE UNAVAILABLE';
      statusBadge.className = 'badge badge-critical';
    }
  }
}

function renderDisasterCard(evt) {
  const sev = (evt.severity || 'moderate').toLowerCase();
  let badgeClass = 'badge-medium';
  if (sev === 'critical') badgeClass = 'badge-critical';
  else if (sev === 'high') badgeClass = 'badge-high';
  else if (sev === 'minor' || sev === 'low') badgeClass = 'badge-low';

  // Classification styling
  const classification = evt.data_classification || 'official alert';
  let classColor = '#38bdf8';
  if (classification.includes('earthquake')) classColor = '#f59e0b';
  else if (classification.includes('official')) classColor = '#10b981';
  else if (classification.includes('citizen')) classColor = '#ef4444';
  else if (classification.includes('satellite')) classColor = '#ec4899';

  const timeFormatted = evt.event_time ? new Date(evt.event_time).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: true }) : 'Recent';

  const hasCoords = evt.latitude !== null && evt.longitude !== null && evt.latitude !== undefined;

  return `
    <div class="disaster-card" style="border-left: 4px solid var(--sev-${sev === 'critical' ? 'critical' : (sev === 'high' ? 'high' : 'medium')});">
      <div class="disaster-card-header">
        <span class="badge ${badgeClass}">${sev.toUpperCase()}</span>
        <span style="font-size: 0.72rem; font-weight: 700; color: ${classColor}; text-transform: uppercase;">
          ${classification}
        </span>
      </div>

      <div class="disaster-card-title">${escapeHtml(evt.title)}</div>

      <div style="font-size: 0.8rem; color: var(--text-muted); line-height: 1.4;">
        ${escapeHtml(evt.details || evt.location_name || '')}
      </div>

      <div class="disaster-card-meta">
        <span>📍 ${escapeHtml(evt.location_name || 'India Region')}</span>
        <span>🕒 ${timeFormatted}</span>
      </div>

      <div style="display: flex; align-items: center; justify-content: space-between; margin-top: auto; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.06);">
        <span style="font-size: 0.7rem; color: var(--text-dim); max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          Source: ${escapeHtml(evt.source || 'Official')}
        </span>
        <div style="display: flex; gap: 0.4rem;">
          ${hasCoords ? `
            <button class="btn btn-secondary btn-sm btn-locate-disaster" data-lat="${evt.latitude}" data-lon="${evt.longitude}" data-title="${escapeHtml(evt.title)}">
              View Map
            </button>
          ` : ''}
          ${evt.source_url ? `
            <a href="${escapeHtml(evt.source_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="text-decoration:none;">
              Source Link ↗
            </a>
          ` : ''}
        </div>
      </div>
    </div>
  `;
}

function locateOnLiveMap(lat, lon, title) {
  switchTab('tab-map');
  if (window.resqaiMap) {
    window.resqaiMap.setView([lat, lon], 12);
    L.popup()
      .setLatLng([lat, lon])
      .setContent(`<b>${escapeHtml(title)}</b><br><small>Coordinates: ${lat.toFixed(4)}, ${lon.toFixed(4)}</small>`)
      .openOn(window.resqaiMap);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
