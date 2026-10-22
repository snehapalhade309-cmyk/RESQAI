/**
 * RESQAI - Weather & Official Alert Centre Controller
 * Open-Meteo Live Forecasts, Hourly Telemetry, Geocoding & NDMA SACHET Feeds
 */

let weatherCenterLat = 18.5204;
let weatherCenterLon = 73.8567;
let weatherCenterCity = "Pune, Maharashtra, India";

document.addEventListener('DOMContentLoaded', () => {
  initWeatherCenter();
});

function initWeatherCenter() {
  const btnLocate = document.getElementById('btn-weather-locate');
  const btnSearch = document.getElementById('btn-weather-search');
  const searchInput = document.getElementById('weather-city-input');

  if (btnLocate) {
    btnLocate.addEventListener('click', () => {
      if (navigator.geolocation) {
        showToast('Acquiring browser GPS coordinates...', 'info');
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            weatherCenterLat = pos.coords.latitude;
            weatherCenterLon = pos.coords.longitude;
            weatherCenterCity = `GPS Position (${weatherCenterLat.toFixed(3)}, ${weatherCenterLon.toFixed(3)})`;
            loadWeatherCenterData();
            showToast('Weather updated for current GPS location.', 'success');
          },
          (err) => {
            showToast('Geolocation permission denied. Using manual selection.', 'warning');
          }
        );
      } else {
        showToast('Geolocation not supported by your browser.', 'warning');
      }
    });
  }

  if (btnSearch && searchInput) {
    btnSearch.addEventListener('click', () => searchAndSetCity());
    searchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') searchAndSetCity();
    });
  }

  // Initial load
  loadWeatherCenterData();
  loadWeatherAlertsList();
}

async function searchAndSetCity() {
  const searchInput = document.getElementById('weather-city-input');
  const query = searchInput.value.trim();
  if (!query) return;

  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
    const results = await res.json();
    if (results.length > 0) {
      const top = results[0];
      weatherCenterLat = top.latitude;
      weatherCenterLon = top.longitude;
      weatherCenterCity = top.display_name || top.name;
      loadWeatherCenterData();
      showToast(`Selected: ${weatherCenterCity}`, 'success');
    } else {
      showToast('No matching locations found. Try another city.', 'warning');
    }
  } catch (err) {
    showToast('Geocoding search failed.', 'error');
  }
}

async function loadWeatherCenterData() {
  const cityLabel = document.getElementById('weather-center-location');
  const tempVal = document.getElementById('weather-center-temp');
  const condVal = document.getElementById('weather-center-cond');
  const appTempVal = document.getElementById('weather-center-app-temp');
  const precipVal = document.getElementById('weather-center-precip');
  const windVal = document.getElementById('weather-center-wind');
  const humVal = document.getElementById('weather-center-hum');
  const dailyCardsContainer = document.getElementById('weather-daily-cards');
  const hourlyContainer = document.getElementById('weather-hourly-timeline');

  if (cityLabel) cityLabel.textContent = weatherCenterCity;

  try {
    const res = await fetch(`/api/weather?lat=${weatherCenterLat}&lon=${weatherCenterLon}&forecast=true`);
    const w = await res.json();

    if (tempVal) tempVal.textContent = `${w.temperature}°C`;
    if (condVal) condVal.textContent = w.condition;
    if (appTempVal) appTempVal.textContent = `${w.apparent_temperature || w.temperature}°C`;
    if (precipVal) precipVal.textContent = `${w.precipitation} ${w.precipitation_unit || 'mm/hr'}`;
    if (windVal) windVal.textContent = `${w.wind_speed} ${w.wind_speed_unit || 'km/h'}`;
    if (humVal) humVal.textContent = `${w.humidity} ${w.humidity_unit || '%'}`;

    // Render 3-Day Forecast Cards
    if (dailyCardsContainer && w.daily_forecast) {
      dailyCardsContainer.innerHTML = w.daily_forecast.map(day => `
        <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 1rem; text-align: center;">
          <div style="font-weight: 700; color: #fff; font-size: 0.9rem; margin-bottom: 0.25rem;">${escapeHtml(day.date)}</div>
          <div style="color: var(--accent-cyan); font-size: 0.8rem; margin-bottom: 0.5rem;">${escapeHtml(day.condition)}</div>
          <div style="font-size: 1.3rem; font-weight: 800; color: #fff;">${day.max_temp}°C <span style="font-size: 0.85rem; color: var(--text-muted); font-weight: 400;">/ ${day.min_temp}°C</span></div>
          <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 0.4rem;">
            Rain Sum: <strong>${day.precipitation_sum} mm</strong> | Prob: <strong>${day.precip_prob_max}%</strong>
          </div>
        </div>
      `).join('');
    }

    // Render Hourly Forecast Preview
    if (hourlyContainer && w.hourly_forecast) {
      hourlyContainer.innerHTML = w.hourly_forecast.map(h => {
        const timePart = h.time ? h.time.split('T')[1].slice(0, 5) : '--:--';
        return `
          <div style="display: flex; flex-direction: column; align-items: center; min-width: 65px; padding: 0.5rem; background: var(--bg-dark); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
            <span style="font-size: 0.72rem; color: var(--text-muted);">${timePart}</span>
            <span style="font-size: 0.95rem; font-weight: 700; color: #fff; margin: 0.2rem 0;">${h.temperature}°</span>
            <span style="font-size: 0.68rem; color: var(--accent-cyan);">${h.precip_prob}% rain</span>
            <span style="font-size: 0.65rem; color: var(--text-dim);">${h.wind_speed} km/h</span>
          </div>
        `;
      }).join('');
    }

  } catch (err) {
    showToast('Failed to fetch meteorological forecast.', 'error');
  }
}

async function loadWeatherAlertsList() {
  const container = document.getElementById('ndma-alerts-list');
  if (!container) return;

  try {
    const res = await fetch('/api/ndma-alerts?limit=15');
    const data = await res.json();
    const alerts = data.alerts || [];

    if (alerts.length === 0) {
      container.innerHTML = `
        <div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
          No critical meteorological alerts reported by NDMA at this time.
        </div>
      `;
      return;
    }

    container.innerHTML = alerts.map(al => `
      <div style="padding: 0.85rem; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); margin-bottom: 0.6rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
          <strong style="color: #fff; font-size: 0.88rem;">${escapeHtml(al.title)}</strong>
          <span class="badge badge-${al.severity === 'critical' ? 'critical' : 'high'}">${al.severity.toUpperCase()}</span>
        </div>
        <div style="font-size: 0.8rem; color: var(--text-muted); line-height: 1.4; margin-bottom: 0.4rem;">
          ${escapeHtml(al.description || '')}
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; color: var(--text-dim);">
          <span>Authority: ${escapeHtml(al.source)}</span>
          <a href="${escapeHtml(al.source_url)}" target="_blank" rel="noopener noreferrer" style="color: var(--accent-cyan); text-decoration: none;">
            Official Portal ↗
          </a>
        </div>
      </div>
    `).join('');

  } catch (err) {
    container.innerHTML = `<div style="padding: 1rem; color: var(--sev-critical); font-size: 0.8rem;">Unable to load NDMA alerts.</div>`;
  }
}
