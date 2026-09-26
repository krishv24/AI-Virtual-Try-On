/**
 * AI Virtual Try-On - Side Panel Studio Controller
 * Handles user interactions, local image previews, and communication with backend.
 */

const BACKEND_HEALTH_URL = 'http://localhost:8000/health';

const spStatusBadge = document.getElementById('sp-status-badge');
const spStatusText = document.getElementById('sp-status-text');
const userPhotoInput = document.getElementById('user-photo-input');
const userPhotoZone = document.getElementById('user-photo-zone');
const garmentPhotoInput = document.getElementById('garment-photo-input');
const garmentPhotoZone = document.getElementById('garment-photo-zone');
const tryonBtn = document.getElementById('tryon-btn');

let state = {
  userImage: null,
  garmentImage: null,
  backendConnected: false,
};

/**
 * Health check monitor
 */
async function checkBackendHealth() {
  setBackendStatus('checking', 'Connecting...');
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    const response = await fetch(BACKEND_HEALTH_URL, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (response.ok) {
      setBackendStatus('online', 'Online');
      state.backendConnected = true;
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (err) {
    setBackendStatus('offline', 'Offline');
    state.backendConnected = false;
  }
}

function setBackendStatus(status, text) {
  spStatusBadge.className = `status-chip ${status}`;
  spStatusText.textContent = text;
}

/**
 * Handle file input and render preview in the dropzone
 */
function setupFilePreview(inputElement, zoneElement, stateKey) {
  inputElement.addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      state[stateKey] = e.target.result;
      zoneElement.innerHTML = `
        <div style="position: relative; width: 100%; height: 140px; display: flex; align-items: center; justify-content: center; overflow: hidden; border-radius: 8px;">
          <img src="${e.target.result}" alt="Preview" style="max-height: 100%; max-width: 100%; object-fit: contain; border-radius: 6px;">
        </div>
      `;
      updateGenerateButton();
    };
    reader.readAsDataURL(file);
  });
}

function updateGenerateButton() {
  if (state.userImage && state.garmentImage) {
    tryonBtn.disabled = false;
  } else {
    tryonBtn.disabled = true;
  }
}

// Initialize
setupFilePreview(userPhotoInput, userPhotoZone, 'userImage');
setupFilePreview(garmentPhotoInput, garmentPhotoZone, 'garmentImage');
checkBackendHealth();

// Re-check periodically
setInterval(checkBackendHealth, 15000);
