/**
 * RESQAI - Emergency Resource Directory & Routing Controller
 * Verified Hospitals, Fire Stations, Evacuation Shelters, and NDRF Relief Hubs.
 */

let currentResourceCategory = 'all';

document.addEventListener('DOMContentLoaded', () => {
  initResourcesView();
});

function initResourcesView() {
  const searchInput = document.getElementById('resource-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => filterAndRenderResources());
  }

  const categoryChips = document.querySelectorAll('.resource-cat-chip');
  categoryChips.forEach(chip => {
    chip.addEventListener('click', () => {
      categoryChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentResourceCategory = chip.getAttribute('data-cat') || 'all';
      filterAndRenderResources();
    });
  });

  loadEmergencyResources();
}

let cachedResources = [];

async function loadEmergencyResources() {
  const container = document.getElementById('resource-directory-container');
  if (!container) return;

  container.innerHTML = `
    <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--text-dim);">
      Loading verified emergency services directory...
    </div>
  `;

  try {
    const res = await fetch('/api/resources');
    cachedResources = await res.json();
    filterAndRenderResources();
  } catch (err) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--sev-critical);">
        Failed to load resource directory from server.
      </div>
    `;
  }
}

function filterAndRenderResources() {
  const container = document.getElementById('resource-directory-container');
  const searchInput = document.getElementById('resource-search-input');
  const term = searchInput ? searchInput.value.toLowerCase().trim() : '';

  if (!container) return;

  const filtered = cachedResources.filter(item => {
    // Category filter
    if (currentResourceCategory !== 'all') {
      if (item.category !== currentResourceCategory) return false;
    }
    // Search term
    if (term) {
      const matchName = (item.name || '').toLowerCase().includes(term);
      const matchAddr = (item.address || '').toLowerCase().includes(term);
      const matchPhone = (item.phone || '').toLowerCase().includes(term);
      return matchName || matchAddr || matchPhone;
    }
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; background: var(--bg-card); border-radius: var(--radius-md); border: 1px dashed var(--border-subtle);">
        <div style="color: var(--text-muted); font-size: 1rem; font-weight: 600;">No resources match your query.</div>
        <div style="color: var(--text-dim); font-size: 0.8rem; margin-top: 0.3rem;">Try selecting "All Categories" or clearing the search bar.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(r => renderResourceCard(r)).join('');

  // Attach route calculation listeners
  container.querySelectorAll('.btn-route-to-resource').forEach(btn => {
    btn.addEventListener('click', () => {
      const lat = parseFloat(btn.getAttribute('data-lat'));
      const lon = parseFloat(btn.getAttribute('data-lon'));
      const name = btn.getAttribute('data-name');
      calculateEvacuationRouteToResource(lat, lon, name);
    });
  });
}

function renderResourceCard(r) {
  const cat = r.category || 'facility';
  let catBadge = 'badge-cyan';
  let catLabel = 'EMERGENCY FACILITY';
  let catIcon = '🏥';

  if (cat === 'hospital') {
    catBadge = 'badge-critical';
    catLabel = 'HOSPITAL / TRAUMA';
    catIcon = '🏥';
  } else if (cat === 'fire_station') {
    catBadge = 'badge-high';
    catLabel = 'FIRE & RESCUE';
    catIcon = '🚒';
  } else if (cat === 'shelter') {
    catBadge = 'badge-low';
    catLabel = 'EVACUATION SHELTER';
    catIcon = '🏕️';
  } else if (cat === 'ndrf_base') {
    catBadge = 'badge-medium';
    catLabel = 'NDRF SEARCH & RESCUE';
    catIcon = '🛡️';
  }

  const services = Array.isArray(r.services) ? r.services : [];

  return `
    <div class="card" style="padding: 1.1rem; display: flex; flex-direction: column; gap: 0.75rem;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div>
          <span class="badge ${catBadge}" style="margin-bottom: 0.3rem;">${catIcon} ${catLabel}</span>
          <h4 style="color: #fff; font-size: 1.05rem; font-weight: 700; line-height: 1.3;">${escapeHtml(r.name)}</h4>
        </div>
        <span class="badge badge-success" style="font-size: 0.68rem;">✓ VERIFIED</span>
      </div>

      <div style="font-size: 0.82rem; color: var(--text-muted); line-height: 1.4;">
        📍 ${escapeHtml(r.address)}
      </div>

      <div style="display: flex; flex-wrap: wrap; gap: 0.35rem;">
        ${services.map(s => `<span class="tag-pill" style="font-size: 0.7rem; padding: 0.2rem 0.5rem; background: var(--bg-surface); border: 1px solid var(--border-subtle); color: var(--accent-cyan); border-radius: var(--radius-sm);">${escapeHtml(s)}</span>`).join('')}
      </div>

      <div style="margin-top: auto; padding-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.06); display: flex; align-items: center; justify-content: space-between;">
        <a href="tel:${escapeHtml(r.phone)}" class="btn btn-secondary btn-sm" style="text-decoration:none; display: inline-flex; align-items: center; gap: 0.3rem;">
          📞 ${escapeHtml(r.phone)}
        </a>
        <button class="btn btn-primary btn-sm btn-route-to-resource" data-lat="${r.latitude}" data-lon="${r.longitude}" data-name="${escapeHtml(r.name)}">
          Route Directions ↗
        </button>
      </div>
    </div>
  `;
}

async function calculateEvacuationRouteToResource(destLat, destLon, name) {
  // Use currently selected coordinates or default to Pune center
  const originLat = (AppState && AppState.selectedCoords) ? AppState.selectedCoords.lat : 18.5312;
  const originLon = (AppState && AppState.selectedCoords) ? AppState.selectedCoords.lon : 73.8682;

  showToast(`Calculating route to ${name}...`, 'info');

  try {
    const res = await fetch(`/api/routes/evacuation?origin_lat=${originLat}&origin_lon=${originLon}&dest_lat=${destLat}&dest_lon=${destLon}`);
    const route = await res.json();

    // Switch to Map tab and render the route polyline
    switchTab('tab-map');

    if (window.resqaiMap && window.routeLayer) {
      window.routeLayer.clearLayers();

      if (route.geometry && route.geometry.coordinates) {
        // Leaflet GeoJSON coordinates are [lon, lat], leaflet takes [lat, lon]
        const latLngs = route.geometry.coordinates.map(pt => [pt[1], pt[0]]);
        const poly = L.polyline(latLngs, {
          color: '#00e5ff',
          weight: 5,
          opacity: 0.9,
          dashArray: route.fallback ? '6, 8' : null
        }).addTo(window.routeLayer);

        window.resqaiMap.fitBounds(poly.getBounds(), { padding: [50, 50] });

        poly.bindPopup(`
          <b>Evacuation Route to ${escapeHtml(name)}</b><br>
          Distance: <strong>${route.distance_km} km</strong> | Est. Time: <strong>${route.duration_minutes || '--'} mins</strong><br>
          <small style="color: #f59e0b;">${escapeHtml(route.safety_disclaimer)}</small>
        `).openPopup();

        showToast(`Route plotted: ${route.distance_km} km (${route.duration_minutes || '--'} mins)`, 'success');
      }
    }
  } catch (err) {
    showToast('Failed to calculate evacuation routing.', 'error');
  }
}
