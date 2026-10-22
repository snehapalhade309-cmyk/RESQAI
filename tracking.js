/**
 * RESQAI - Citizen Incident Tracking Controller
 * Allows citizens to track lifecycle progression and response unit dispatch via Incident Code.
 */

document.addEventListener('DOMContentLoaded', () => {
  initTrackingView();
});

function initTrackingView() {
  const btnTrack = document.getElementById('btn-track-submit');
  const inputCode = document.getElementById('track-incident-code');
  const inputPin = document.getElementById('track-incident-pin');

  if (btnTrack && inputCode) {
    btnTrack.addEventListener('click', (e) => {
      e.preventDefault();
      const code = inputCode.value.trim();
      const pin = inputPin ? inputPin.value.trim() : '';
      if (!code) {
        showToast('Please enter a valid Incident Code (e.g. INC-2026-001)', 'warning');
        return;
      }
      trackIncident(code, pin);
    });

    inputCode.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        btnTrack.click();
      }
    });
  }

  // Pre-fill if code passed in URL hash (e.g. #tab-tracking?code=INC-2026-001)
  const hash = window.location.hash;
  if (hash.includes('code=')) {
    const code = hash.split('code=')[1].split('&')[0];
    if (inputCode) inputCode.value = code;
    trackIncident(code);
  }
}

async function trackIncident(code, pin = '') {
  const resultContainer = document.getElementById('tracking-result-card');
  if (!resultContainer) return;

  resultContainer.style.display = 'block';
  resultContainer.innerHTML = `
    <div style="text-align: center; padding: 2rem; color: var(--text-dim);">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
      <div style="margin-top: 0.5rem;">Querying Command Net for ${escapeHtml(code)}...</div>
    </div>
  `;

  try {
    let url = `/api/incidents/track/${encodeURIComponent(code)}`;
    if (pin) url += `?pin=${encodeURIComponent(pin)}`;

    const res = await fetch(url);
    const data = await res.json();

    if (!res.ok) {
      resultContainer.innerHTML = `
        <div style="padding: 2rem; text-align: center; color: var(--sev-critical);">
          <div style="font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem;">Incident Code Not Found</div>
          <div style="font-size: 0.85rem; color: var(--text-muted);">${escapeHtml(data.detail || 'Please verify the incident identifier.')}</div>
        </div>
      `;
      return;
    }

    renderTrackingTimeline(data, resultContainer);

  } catch (err) {
    resultContainer.innerHTML = `
      <div style="padding: 2rem; text-align: center; color: var(--sev-critical);">
        Network error while querying incident tracking. Please try again.
      </div>
    `;
  }
}

function renderTrackingTimeline(data, container) {
  const timeline = data.timeline || [];
  const assigned = data.assigned_unit;

  container.innerHTML = `
    <div class="card-header" style="background: rgba(11, 19, 41, 0.7);">
      <div>
        <span class="badge badge-${(data.risk_category || 'medium').toLowerCase()}" style="margin-right: 0.5rem;">
          ${(data.risk_category || 'MEDIUM').toUpperCase()} PRIORITY
        </span>
        <strong style="color: #fff; font-size: 1.1rem;">${escapeHtml(data.incident_code)}</strong>
      </div>
      <span style="font-size: 0.8rem; color: var(--text-muted);">
        Reported: ${new Date(data.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
      </span>
    </div>

    <div class="card-body">
      <h3 style="color: #fff; font-size: 1.15rem; margin-bottom: 0.3rem;">${escapeHtml(data.title)}</h3>
      <div style="color: var(--accent-cyan); font-size: 0.85rem; margin-bottom: 1.25rem;">
        📍 Location: ${escapeHtml(data.location_name)}
      </div>

      <!-- Lifecycle Stepper -->
      <div class="timeline-stepper">
        ${timeline.map((step, idx) => `
          <div class="step-node ${step.completed ? 'completed' : ''} ${step.current ? 'current' : ''}">
            <div class="step-circle">${idx + 1}</div>
            <div class="step-label">${escapeHtml(step.label)}</div>
          </div>
        `).join('')}
      </div>

      <!-- Assigned Response Unit Status -->
      ${assigned ? `
        <div style="background: rgba(2, 132, 199, 0.15); border: 1px solid var(--accent-blue); border-radius: var(--radius-md); padding: 1rem; margin-bottom: 1.25rem; display: flex; align-items: center; justify-content: space-between;">
          <div>
            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent-cyan); font-weight: 700;">
              Assigned Tactical Response Unit
            </div>
            <div style="font-weight: 700; color: #fff; font-size: 1rem; margin-top: 0.2rem;">
              ${escapeHtml(assigned.name)} (${escapeHtml(assigned.type.replace('_', ' ').toUpperCase())})
            </div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">
              Status: <span style="color: var(--sev-high); font-weight: 700;">${escapeHtml(assigned.status.toUpperCase())}</span> | Dispatched: ${new Date(assigned.dispatch_time).toLocaleTimeString()}
            </div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="switchTab('tab-map')">
            Track On Map
          </button>
        </div>
      ` : `
        <div style="background: rgba(255, 255, 255, 0.03); border: 1px dashed var(--border-subtle); border-radius: var(--radius-md); padding: 0.9rem; margin-bottom: 1.25rem; font-size: 0.85rem; color: var(--text-muted);">
          ℹ️ <strong>Dispatch Status:</strong> Incident is in command review queue. Tactical unit assignment pending field verification.
        </div>
      `}

      <!-- Responder Notes -->
      <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem;">
        <div style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.4rem;">
          Command Dispatcher Field Notes
        </div>
        <div style="font-size: 0.88rem; color: #fff; line-height: 1.5;">
          ${escapeHtml(data.responder_notes || 'Incident registered in command database. First responders mobilized to primary sector.')}
        </div>
      </div>

      <div style="margin-top: 1.25rem; font-size: 0.75rem; color: var(--text-dim); border-top: 1px solid var(--border-subtle); padding-top: 0.75rem;">
        🔒 Privacy notice: Personal reporter contact details are masked for public security. Authorized field personnel access contact info via authenticated portal.
      </div>
    </div>
  `;
}
