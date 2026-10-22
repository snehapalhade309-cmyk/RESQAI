/**
 * RESQAI - Incidents Management & Reporting Controller
 * Handles live priority queue, on-scene GPS reporting, instant risk preview,
 * secure incident creation with tracking PIN, and authorized status updates.
 */

document.addEventListener('DOMContentLoaded', () => {
  initReportForm();
  initVulnerabilityTagButtons();
  initGPSLocator();
});

function initGPSLocator() {
  const btnGPS = document.getElementById('btn-get-gps');
  if (!btnGPS) return;

  btnGPS.addEventListener('click', (e) => {
    e.preventDefault();
    if (!navigator.geolocation) {
      showToast('Geolocation is not supported by your browser.', 'warning');
      return;
    }

    btnGPS.textContent = 'Acquiring GPS...';
    btnGPS.disabled = true;

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude.toFixed(5);
        const lon = pos.coords.longitude.toFixed(5);

        const latInput = document.getElementById('rep-lat');
        const lonInput = document.getElementById('rep-lon');
        if (latInput) latInput.value = lat;
        if (lonInput) lonInput.value = lon;

        btnGPS.textContent = '✓ GPS Acquired';
        btnGPS.disabled = false;
        showToast(`GPS Position Set: ${lat}, ${lon}`, 'success');

        if (typeof triggerRiskPreview === 'function') triggerRiskPreview();
      },
      (err) => {
        btnGPS.textContent = 'Use My Browser GPS';
        btnGPS.disabled = false;
        showToast('GPS permission denied or timed out. Enter coordinates manually.', 'warning');
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  });
}

/**
 * Fetch and Render Incidents
 */
async function loadIncidents() {
  try {
    const res = await fetch('/api/incidents');
    if (!res.ok) throw new Error('Failed to load incidents');
    const incidents = await res.json();
    AppState.incidents = incidents;

    renderOverviewIncidentTable(incidents);
    if (typeof renderMapMarkers === 'function') {
      renderMapMarkers();
    }

    const badge = document.getElementById('nav-badge-map');
    if (badge) badge.textContent = incidents.length;
  } catch (err) {
    console.error('Error loading incidents:', err);
    const tbody = document.getElementById('overview-incidents-body');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--sev-critical); padding:2rem;">Failed to load incident stream. Ensure server is running.</td></tr>';
    }
  }
}

/**
 * Render Command Center Priority Table
 */
function renderOverviewIncidentTable(incidents) {
  const tbody = document.getElementById('overview-incidents-body');
  if (!tbody) return;

  if (incidents.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-dim); padding:2rem;">No active incidents reported. All clear.</td></tr>';
    return;
  }

  tbody.innerHTML = incidents.map(inc => {
    const riskCat = (inc.risk_category || 'Low').toLowerCase();
    const score = Number(inc.calculated_risk_score || 0).toFixed(1);

    const vulns = Array.isArray(inc.vulnerability_tags) ? inc.vulnerability_tags : [];
    const vulnsHtml = vulns.length > 0
      ? vulns.map(v => `<span class="badge" style="background:rgba(249,115,22,0.15); color:var(--sev-high); border:1px solid rgba(249,115,22,0.3); font-size:0.65rem; margin-right:3px;">${v.replace('_', ' ')}</span>`).join('')
      : '<span style="color:var(--text-dim); font-size:0.75rem;">None</span>';

    return `
      <tr>
        <td><strong style="color:var(--accent-cyan); font-family:var(--font-mono);">${inc.incident_code}</strong></td>
        <td><span class="badge badge-info">${inc.type.toUpperCase()}</span></td>
        <td>
          <div style="font-weight:600; color:#fff;">${escapeHtml(inc.title)}</div>
          <div style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(inc.location_name)}</div>
        </td>
        <td>
          <div style="display:flex; align-items:center; gap:0.4rem;">
            <span class="badge badge-${riskCat}">${score}</span>
            <span style="font-size:0.72rem; text-transform:uppercase; font-weight:700; color:var(--sev-${riskCat});">${inc.risk_category}</span>
          </div>
        </td>
        <td><strong>${inc.affected_people || 0}</strong> <span style="color:var(--text-dim); font-size:0.72rem;">civilians</span></td>
        <td>${vulnsHtml}</td>
        <td><span class="badge badge-${inc.status}">${inc.status.replace('_', ' ').toUpperCase()}</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="showIncidentDetail(${inc.id})">
            Inspect & Dispatch
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

/**
 * Vulnerability Need Tag Button Toggles
 */
function initVulnerabilityTagButtons() {
  const tagBtns = document.querySelectorAll('.vuln-tag-btn');
  tagBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      btn.classList.toggle('active');
      const checkbox = btn.querySelector('input[type="checkbox"]');
      if (checkbox) checkbox.checked = btn.classList.contains('active');
      if (typeof triggerRiskPreview === 'function') triggerRiskPreview();
    });
  });
}

/**
 * Handle Incident Report Form Submission
 */
function initReportForm() {
  const form = document.getElementById('form-report-incident');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const submitBtn = document.getElementById('btn-submit-report');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Verifying & Persisting...';

    // Collect vulnerability tags
    const activeTags = [];
    document.querySelectorAll('.vuln-tag-btn.active').forEach(b => {
      activeTags.push(b.getAttribute('data-tag'));
    });

    const payload = {
      type: document.getElementById('rep-type').value,
      reported_severity: document.getElementById('rep-severity').value,
      title: document.getElementById('rep-title').value.trim(),
      location_name: document.getElementById('rep-location').value.trim(),
      latitude: document.getElementById('rep-lat').value ? parseFloat(document.getElementById('rep-lat').value) : null,
      longitude: document.getElementById('rep-lon').value ? parseFloat(document.getElementById('rep-lon').value) : null,
      affected_people: parseInt(document.getElementById('rep-people').value, 10) || 0,
      vulnerability_tags: activeTags,
      description: document.getElementById('rep-description').value.trim(),
      reporter_name: document.getElementById('rep-reporter-name').value.trim() || 'Citizen Reporter',
      reporter_contact: document.getElementById('rep-reporter-contact').value.trim()
    };

    try {
      const headers = typeof getAuthHeaders === 'function' ? getAuthHeaders() : { 'Content-Type': 'application/json' };
      const res = await fetch('/api/incidents', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const data = await res.json();
        
        // Show success notification with tracking PIN
        showToast(`Incident SOS Logged: ${data.incident_code}! PIN: ${data.tracking_pin}`, 'success');

        // Reset form
        form.reset();
        document.querySelectorAll('.vuln-tag-btn.active').forEach(b => b.classList.remove('active'));

        // Refresh all tables and KPIs
        await loadIncidents();
        await refreshOverviewKPIs();
        if (typeof loadAlerts === 'function') loadAlerts(false);

        // Open Incident Confirmation Modal with Track Button
        openReportSuccessModal(data);

      } else {
        const err = await res.json();
        showToast(err.detail || err.error || 'Failed to submit incident report.', 'error');
      }
    } catch (err) {
      showToast('Network error while saving incident report.', 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit Incident to Command Net';
    }
  });
}

function openReportSuccessModal(data) {
  const modalHtml = `
    <div style="text-align: center; padding: 1rem 0;">
      <div style="font-size: 3rem; margin-bottom: 0.5rem;">🚨</div>
      <h3 style="color: #fff; font-size: 1.3rem; margin-bottom: 0.5rem;">Emergency SOS Submitted</h3>
      <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.5rem;">
        Your report has been validated and persisted to the Command Center database.
      </p>

      <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1.25rem; margin-bottom: 1.5rem; text-align: left;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
          <span style="color: var(--text-muted); font-size: 0.85rem;">Incident Tracking Code:</span>
          <strong style="color: var(--accent-cyan); font-family: var(--font-mono); font-size: 1.1rem;">${data.incident_code}</strong>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
          <span style="color: var(--text-muted); font-size: 0.85rem;">Private Tracking PIN:</span>
          <strong style="color: #fff; font-family: var(--font-mono); font-size: 1.1rem;">${data.tracking_pin}</strong>
        </div>
        <div style="display: flex; justify-content: space-between;">
          <span style="color: var(--text-muted); font-size: 0.85rem;">Calculated Risk Priority:</span>
          <span class="badge badge-${(data.risk_evaluation?.category || 'medium').toLowerCase()}">${data.risk_evaluation?.score}/100 (${data.risk_evaluation?.category})</span>
        </div>
      </div>

      <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid var(--sev-critical); border-radius: var(--radius-md); padding: 0.85rem; font-size: 0.78rem; color: #fca5a5; margin-bottom: 1.5rem; line-height: 1.4;">
        ⚠️ <strong>Notice:</strong> ResQAI is not automatically connected to emergency services. Submitting a request does not call 112 or guarantee rescue. If you are in immediate danger in India, contact <strong>112</strong> directly.
      </div>

      <div style="display: flex; gap: 0.75rem; justify-content: center;">
        <button class="btn btn-secondary" onclick="closeIncidentModal()">Close</button>
        <button class="btn btn-primary" onclick="closeIncidentModal(); trackIncidentFromReport('${data.incident_code}', '${data.tracking_pin}')">
          Track Status Now ↗
        </button>
      </div>
    </div>
  `;
  openIncidentModal(modalHtml);
}

function trackIncidentFromReport(code, pin) {
  switchTab('tab-tracking');
  const codeInput = document.getElementById('track-incident-code');
  const pinInput = document.getElementById('track-incident-pin');
  if (codeInput) codeInput.value = code;
  if (pinInput) pinInput.value = pin;
  if (typeof trackIncident === 'function') trackIncident(code, pin);
}

/**
 * Show Incident Detail & Dispatch Modal
 */
async function showIncidentDetail(incidentId) {
  try {
    const headers = typeof getAuthHeaders === 'function' ? getAuthHeaders() : {};
    const res = await fetch(`/api/incidents/${incidentId}`, { headers });
    if (!res.ok) throw new Error('Incident fetch failed');
    const data = await res.json();

    const inc = data.incident;
    const risk = data.risk_evaluation;
    const weather = data.weather;
    const brief = data.decision_brief;
    const recs = data.recommendations || [];
    const assigned = data.assigned_units || [];

    const riskCat = (inc.risk_category || 'Low').toLowerCase();

    // Render Factor Breakdown List
    const factorItems = (risk.factor_breakdown || []).map(f => `
      <div style="display:flex; justify-content:space-between; padding:0.35rem 0; border-bottom:1px solid var(--border-subtle); font-size:0.78rem;">
        <div>
          <strong style="color:#fff;">${escapeHtml(f.factor)}</strong>
          <div style="font-size:0.72rem; color:var(--text-muted);">${escapeHtml(f.description)}</div>
        </div>
        <span style="color:var(--accent-cyan); font-weight:700; font-family:var(--font-mono);">+${f.points} pts</span>
      </div>
    `).join('');

    // Tactical recommendations
    const actions = brief.actions || [];
    const briefContent = `
      <div style="background:var(--bg-surface); padding:0.85rem; border-radius:var(--radius-md); margin-top:0.75rem; border:1px solid var(--border-subtle);">
        <div style="font-weight:700; color:var(--accent-cyan); font-size:0.8rem; margin-bottom:0.4rem;">
          ${escapeHtml(brief.provider || 'ResQAI Situation Briefing Engine')}
        </div>
        <ul style="padding-left:1.2rem; font-size:0.78rem; color:var(--text-muted); display:flex; flex-direction:column; gap:0.25rem;">
          ${actions.map(r => `<li>${escapeHtml(r)}</li>`).join('')}
        </ul>
      </div>
    `;

    // Active units on-scene
    let assignedHtml = '';
    if (assigned.length > 0) {
      assignedHtml = `
        <div style="margin-top:1rem; padding:0.75rem; background:rgba(249,115,22,0.1); border:1px solid var(--sev-high); border-radius:var(--radius-md);">
          <strong style="color:var(--sev-high); font-size:0.8rem;">Active Response Units Deployed:</strong>
          ${assigned.map(u => `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.4rem; font-size:0.78rem;">
              <span><strong>${escapeHtml(u.name)}</strong> (${escapeHtml(u.type.toUpperCase())})</span>
              <button class="btn btn-secondary btn-sm" onclick="releaseUnit(${u.id}, ${inc.id})">Release Unit</button>
            </div>
          `).join('')}
        </div>
      `;
    }

    // Recommended fleet units
    let recsHtml = '';
    if (recs.length === 0) {
      recsHtml = '<div style="color:var(--text-dim); font-size:0.78rem;">No suitable units currently available in standby queue.</div>';
    } else {
      recsHtml = recs.map(r => `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:0.6rem; background:var(--bg-surface); border-radius:var(--radius-md); border:1px solid var(--border-subtle); margin-top:0.4rem;">
          <div>
            <div style="font-weight:700; color:#fff; font-size:0.82rem;">${escapeHtml(r.name)} (${escapeHtml(r.type.toUpperCase())})</div>
            <div style="font-size:0.72rem; color:var(--text-muted);">
              Distance: <strong style="color:var(--accent-cyan);">${r.distance_km !== null ? r.distance_km + ' km' : 'N/A'}</strong> |
              ETA: <strong style="color:var(--accent-cyan);">${r.eta_minutes !== null ? r.eta_minutes + ' min' : 'Pending GPS'}</strong> |
              Match: <strong style="color:var(--sev-low);">${r.suitability_score}%</strong>
            </div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="dispatchUnitToIncident(${inc.id}, ${r.resource_id}, '${escapeHtml(r.name)}')">
            Dispatch Unit
          </button>
        </div>
      `).join('');
    }

    const modalHtml = `
      <div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; border-bottom:1px solid var(--border-subtle); padding-bottom:0.75rem;">
          <div>
            <h3 style="color:#fff; font-size:1.15rem; margin-bottom:0.2rem;">${escapeHtml(inc.incident_code)}: ${escapeHtml(inc.title)}</h3>
            <div style="font-size:0.78rem; color:var(--text-muted);">
              📍 ${escapeHtml(inc.location_name)} | Reporter: <strong>${escapeHtml(inc.reporter_name || 'Anonymous')}</strong> | Contact: <code>${escapeHtml(inc.reporter_contact || 'N/A')}</code>
            </div>
          </div>
          <div style="display:flex; gap:0.5rem; align-items:center;">
            <span class="badge badge-${riskCat}">${inc.calculated_risk_score} ${inc.risk_category}</span>
            <select class="form-control" style="width:145px; padding:0.35rem 0.6rem; font-size:0.75rem;" onchange="updateStatus(${inc.id}, this.value)">
              <option value="submitted" ${inc.status === 'submitted' ? 'selected' : ''}>Submitted</option>
              <option value="under_review" ${inc.status === 'under_review' ? 'selected' : ''}>Under Review</option>
              <option value="verified" ${inc.status === 'verified' || inc.status === 'reported' ? 'selected' : ''}>Verified</option>
              <option value="assigned" ${inc.status === 'assigned' || inc.status === 'dispatched' ? 'selected' : ''}>Assigned</option>
              <option value="in_progress" ${inc.status === 'in_progress' || inc.status === 'on_scene' ? 'selected' : ''}>In Progress</option>
              <option value="resolved" ${inc.status === 'resolved' ? 'selected' : ''}>Resolved</option>
              <option value="rejected" ${inc.status === 'rejected' ? 'selected' : ''}>Rejected</option>
            </select>
          </div>
        </div>

        <p style="font-size:0.85rem; color:var(--text-main); line-height:1.5; margin-bottom:1rem;">
          ${escapeHtml(inc.description || 'No situational narrative provided.')}
        </p>

        <!-- Weather snapshot if available -->
        ${weather ? `
          <div style="display:flex; gap:1.5rem; padding:0.6rem 0.85rem; background:rgba(0,229,255,0.08); border-radius:var(--radius-md); font-size:0.75rem; margin-bottom:1rem;">
            <div><strong>Condition:</strong> ${weather.condition}</div>
            <div><strong>Temp:</strong> ${weather.temperature}°C</div>
            <div><strong>Rain:</strong> ${weather.precipitation} mm/hr</div>
            <div><strong>Wind:</strong> ${weather.wind_speed} km/h</div>
          </div>
        ` : ''}

        <!-- Decision Brief -->
        ${briefContent}

        ${assignedHtml}

        <!-- Smart Dispatch Section -->
        <div style="margin-top:1.25rem;">
          <h4 style="font-size:0.85rem; font-weight:700; color:#fff; margin-bottom:0.4rem;">
            Recommended Fleet Units (Capability & Proximity Ranked)
          </h4>
          <div style="display:flex; flex-direction:column; gap:0.35rem;">
            ${recsHtml}
          </div>
        </div>

        <!-- Risk Factor Breakdown -->
        <div style="margin-top:1.25rem;">
          <h4 style="font-size:0.85rem; font-weight:700; color:#fff; margin-bottom:0.4rem;">
            Explainable Risk Intelligence Breakdown (Deterministic Model v2.1)
          </h4>
          <div style="background:var(--bg-surface); padding:0.75rem; border-radius:var(--radius-md);">
            ${factorItems}
          </div>
        </div>
      </div>
    `;

    openIncidentModal(modalHtml);
  } catch (err) {
    showToast('Failed to retrieve incident details.', 'error');
  }
}

async function updateStatus(incidentId, newStatus) {
  try {
    const headers = typeof getAuthHeaders === 'function' ? getAuthHeaders() : { 'Content-Type': 'application/json' };
    const res = await fetch(`/api/incidents/${incidentId}/status`, {
      method: 'PATCH',
      headers: headers,
      body: JSON.stringify({ status: newStatus, actor: AuthState?.currentUser?.full_name || 'Command Dispatcher' })
    });
    if (res.ok) {
      showToast(`Incident status updated to ${newStatus.replace('_', ' ').toUpperCase()}`, 'info');
      loadIncidents();
      refreshOverviewKPIs();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Status update failed.', 'error');
    }
  } catch (err) {
    showToast('Status update failed.', 'error');
  }
}

function openIncidentModal(html) {
  const modal = document.getElementById('modal-incident-detail');
  const body = document.getElementById('modal-inc-body');
  if (modal && body) {
    body.innerHTML = html;
    modal.classList.add('active');
  }
}

function closeIncidentModal() {
  const modal = document.getElementById('modal-incident-detail');
  if (modal) modal.classList.remove('active');
}
