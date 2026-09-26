/**
 * AI Virtual Try-On - Popup Logic
 * Communicates with backend health API and handles side panel invocation.
 * Note: Never store API keys in the extension.
 */

const BACKEND_HEALTH_URL = 'http://localhost:8000/health';

const statusBadge = document.getElementById('backend-status-badge');
const statusText = document.getElementById('backend-status-text');
const serverAlert = document.getElementById('server-alert');
const openSidepanelBtn = document.getElementById('open-sidepanel-btn');
const recheckBtn = document.getElementById('recheck-btn');

/**
 * Check backend health status
 */
async function checkBackendHealth() {
  setStatus('checking', 'Checking API...');
  serverAlert.classList.add('hidden');

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    const response = await fetch(BACKEND_HEALTH_URL, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();
      setStatus('online', 'Backend Online');
      console.log('[AI Try-On] Backend status:', data);
    } else {
      throw new Error(`HTTP error ${response.status}`);
    }
  } catch (error) {
    console.warn('[AI Try-On] Backend unavailable:', error.message);
    setStatus('offline', 'Backend Offline');
    serverAlert.classList.remove('hidden');
  }
}

/**
 * Set visual status badge
 */
function setStatus(state, label) {
  statusBadge.className = `status-badge ${state}`;
  statusText.textContent = label;
}

/**
 * Open the Chrome Side Panel
 */
async function openSidePanel() {
  try {
    // Try opening via tabs query in active window
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && chrome.sidePanel && chrome.sidePanel.open) {
      await chrome.sidePanel.open({ tabId: tab.id });
      window.close(); // Close popup once side panel is opened
    } else {
      // Fallback via background message
      chrome.runtime.sendMessage({ type: 'OPEN_SIDE_PANEL' }, (res) => {
        if (res && res.success) {
          window.close();
        } else {
          console.error('[AI Try-On] Could not open side panel:', res?.error);
        }
      });
    }
  } catch (err) {
    console.error('[AI Try-On] Error opening side panel:', err);
  }
}

const popupProfileSelect = document.getElementById('popup-profile-select');

async function loadPopupProfiles() {
  try {
    const res = await fetch('http://localhost:8000/api/profiles');
    if (!res.ok) return;
    const profiles = await res.json();

    popupProfileSelect.innerHTML = '';
    if (profiles.length === 0) {
      popupProfileSelect.innerHTML = '<option value="" disabled selected>No profiles found</option>';
      return;
    }

    profiles.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.photo_count || 0}/5)`;
      popupProfileSelect.appendChild(opt);
    });

    // Check stored activeProfileId
    chrome.storage.local.get(['activeProfileId'], (result) => {
      if (result && result.activeProfileId) {
        popupProfileSelect.value = result.activeProfileId;
      } else if (profiles.length > 0) {
        popupProfileSelect.value = profiles[0].id;
        chrome.storage.local.set({ activeProfileId: profiles[0].id });
      }
    });
  } catch (e) {
    console.warn('[AI Try-On] Error fetching popup profiles:', e);
  }
}

if (popupProfileSelect) {
  popupProfileSelect.addEventListener('change', (e) => {
    const id = Number(e.target.value);
    if (id) {
      chrome.storage.local.set({ activeProfileId: id });
    }
  });
}

// Event Listeners
openSidepanelBtn.addEventListener('click', openSidePanel);
recheckBtn.addEventListener('click', () => {
  checkBackendHealth();
  loadPopupProfiles();
});

const openProfileBtn = document.getElementById('open-profile-btn');
if (openProfileBtn) {
  openProfileBtn.addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('profile/profile.html') });
  });
}

// Initialize on popup load
document.addEventListener('DOMContentLoaded', () => {
  checkBackendHealth();
  loadPopupProfiles();
});
