/**
 * RESQAI - Authentication, Session & Role-Based Access Control
 * Handles JWT tokens, current user role, and 1-click demo persona switcher.
 */

const AuthState = {
  currentUser: {
    username: 'admin',
    role: 'admin',
    full_name: 'Col. Rajesh Malhotra (Retd.)',
    organization: 'State Disaster Management Control Room'
  },
  token: null
};

document.addEventListener('DOMContentLoaded', () => {
  initAuth();
});

function initAuth() {
  // Check stored session
  const storedUser = localStorage.getItem('resqai_user');
  const storedToken = localStorage.getItem('resqai_token');
  if (storedUser && storedToken) {
    try {
      AuthState.currentUser = JSON.parse(storedUser);
      AuthState.token = storedToken;
    } catch (e) {
      localStorage.removeItem('resqai_user');
    }
  }

  updateHeaderUserPill();
  initAuthModalEvents();
}

function updateHeaderUserPill() {
  const pill = document.getElementById('header-user-pill');
  if (!pill) return;

  const role = AuthState.currentUser?.role || 'citizen';
  const name = AuthState.currentUser?.full_name || 'Anonymous';
  
  pill.className = `role-pill role-${role}`;
  pill.innerHTML = `
    <span style="width: 8px; height: 8px; border-radius: 50%; background: currentColor;"></span>
    <span>${role.toUpperCase()}: ${name.split(' ')[0]}</span>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
  `;
}

function getAuthHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (AuthState.token) {
    headers['Authorization'] = `Bearer ${AuthState.token}`;
  }
  return headers;
}

function switchDemoRole(role) {
  if (role === 'admin') {
    loginWithCredentials('admin', 'admin123');
  } else if (role === 'responder') {
    loginWithCredentials('responder', 'responder123');
  } else {
    loginWithCredentials('citizen', 'citizen123');
  }
}

async function loginWithCredentials(username, password) {
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (res.ok && data.access_token) {
      AuthState.token = data.access_token;
      AuthState.currentUser = data.user;
      localStorage.setItem('resqai_token', data.access_token);
      localStorage.setItem('resqai_user', JSON.stringify(data.user));
      updateHeaderUserPill();
      closeAuthModal();
      showToast(`Switched active persona to ${data.user.role.toUpperCase()} (${data.user.full_name})`, 'success');
      
      // Refresh current view permissions
      if (typeof refreshOverviewKPIs === 'function') refreshOverviewKPIs();
    } else {
      showToast(data.detail || 'Login failed', 'error');
    }
  } catch (err) {
    showToast('Failed to authenticate with server', 'error');
  }
}

function initAuthModalEvents() {
  const pill = document.getElementById('header-user-pill');
  if (pill) {
    pill.addEventListener('click', () => openAuthModal());
  }

  const btnClose = document.getElementById('modal-auth-close');
  if (btnClose) {
    btnClose.addEventListener('click', () => closeAuthModal());
  }

  // Demo role switcher buttons
  const btnRoleAdmin = document.getElementById('demo-role-admin');
  if (btnRoleAdmin) btnRoleAdmin.addEventListener('click', () => switchDemoRole('admin'));

  const btnRoleResponder = document.getElementById('demo-role-responder');
  if (btnRoleResponder) btnRoleResponder.addEventListener('click', () => switchDemoRole('responder'));

  const btnRoleCitizen = document.getElementById('demo-role-citizen');
  if (btnRoleCitizen) btnRoleCitizen.addEventListener('click', () => switchDemoRole('citizen'));
}

function openAuthModal() {
  const modal = document.getElementById('modal-auth');
  if (modal) modal.classList.add('active');
}

function closeAuthModal() {
  const modal = document.getElementById('modal-auth');
  if (modal) modal.classList.remove('active');
}
