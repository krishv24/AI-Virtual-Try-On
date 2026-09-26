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

// Event Listeners
openSidepanelBtn.addEventListener('click', openSidePanel);
recheckBtn.addEventListener('click', checkBackendHealth);

// Initialize on popup load
document.addEventListener('DOMContentLoaded', checkBackendHealth);
