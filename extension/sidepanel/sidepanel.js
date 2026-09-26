/**
 * AI Virtual Try-On - Side Panel Studio Controller
 * Handles user interactions, profiles, and communication with backend.
 */

const BACKEND_BASE = 'http://localhost:8000';

const spStatusBadge = document.getElementById('sp-status-badge');
const spStatusText = document.getElementById('sp-status-text');
const spProfileSelect = document.getElementById('sp-profile-select');
const spManageProfilesBtn = document.getElementById('sp-manage-profiles-btn');
const userPhotoInput = document.getElementById('user-photo-input');
const userPhotoZone = document.getElementById('user-photo-zone');
const garmentPhotoInput = document.getElementById('garment-photo-input');
const garmentPhotoZone = document.getElementById('garment-photo-zone');
const tryonBtn = document.getElementById('tryon-btn');

let state = {
  profiles: [],
  activeProfileId: null,
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

    const response = await fetch(`${BACKEND_BASE}/health`, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (response.ok) {
      setBackendStatus('online', 'Online');
      state.backendConnected = true;
      loadProfiles();
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
 * Load user profiles for quick switching in side panel
 */
async function loadProfiles() {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/profiles`);
    if (!res.ok) return;
    state.profiles = await res.json();

    spProfileSelect.innerHTML = '';
    if (state.profiles.length === 0) {
      spProfileSelect.innerHTML = '<option value="">No profiles (Click + Setup)</option>';
      return;
    }

    state.profiles.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.photo_count}/5)`;
      spProfileSelect.appendChild(opt);
    });

    if (!state.activeProfileId && state.profiles.length > 0) {
      state.activeProfileId = state.profiles[0].id;
      spProfileSelect.value = state.activeProfileId;
      loadProfileReferencePhoto(state.activeProfileId);
    }
  } catch (e) {
    console.warn('[AI Try-On] Error fetching profiles:', e);
  }
}

/**
 * Load active profile reference photo into Section 1
 */
async function loadProfileReferencePhoto(profileId) {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/profiles/${profileId}`);
    if (!res.ok) return;
    const profile = await res.json();
    const photos = profile.photos || [];

    // Prioritize front_full_body, fallback to upper_body
    const refPhoto =
      photos.find((p) => p.photo_type === 'front_full_body') ||
      photos.find((p) => p.photo_type === 'upper_body') ||
      photos[0];

    if (refPhoto) {
      const photoUrl = `${BACKEND_BASE}${refPhoto.access_url}`;
      state.userImage = photoUrl;
      userPhotoZone.innerHTML = `
        <div style="position: relative; width: 100%; height: 160px; display: flex; align-items: center; justify-content: center; overflow: hidden; border-radius: 8px;">
          <img src="${photoUrl}" alt="${profile.name}" style="max-height: 100%; max-width: 100%; object-fit: contain; border-radius: 6px;">
          <span style="position: absolute; bottom: 6px; right: 6px; background: rgba(0,0,0,0.6); padding: 2px 6px; border-radius: 4px; font-size: 10px; color: #a5b4fc;">${refPhoto.photo_type}</span>
        </div>
      `;
      updateGenerateButton();
    }
  } catch (e) {
    console.warn('[AI Try-On] Error loading profile photo:', e);
  }
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

// Event Listeners
spProfileSelect.addEventListener('change', (e) => {
  const val = Number(e.target.value);
  if (val) {
    state.activeProfileId = val;
    loadProfileReferencePhoto(val);
  }
});

spManageProfilesBtn.addEventListener('click', () => {
  chrome.tabs.create({ url: chrome.runtime.getURL('profile/profile.html') });
});

// Initialize
setupFilePreview(userPhotoInput, userPhotoZone, 'userImage');
setupFilePreview(garmentPhotoInput, garmentPhotoZone, 'garmentImage');
checkBackendHealth();

// Re-check periodically
setInterval(checkBackendHealth, 15000);
