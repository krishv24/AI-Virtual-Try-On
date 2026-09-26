/**
 * Digital Profile Studio - Interactive Profile & MediaPipe Validation Controller
 */

const API_BASE = 'http://localhost:8000';

const STEP_DEFINITIONS = [
  {
    type: 'front_full_body',
    title: 'Front / Full-Body Photo',
    stepNumber: 'Step 1 of 5',
    description: 'Full-length photo from head to shoes. MediaPipe checks shoulders, hips, knees, and ankles.',
    guidance: [
      'Stand 6-8 feet back so your entire body from head to feet is inside the frame.',
      'Keep arms slightly away from your sides and legs shoulder-width apart.',
      'Use bright, even lighting and a plain, uncluttered background.',
      'Wear fitted, neutral clothing for optimal virtual drape.'
    ]
  },
  {
    type: 'upper_body',
    title: 'Upper-Body Photo',
    stepNumber: 'Step 2 of 5',
    description: 'Torso from waist up to head. MediaPipe validates shoulders, torso, and arm keypoints.',
    guidance: [
      'Frame yourself from the belt/waistline up to the top of your head.',
      'Keep your torso centered and shoulders relaxed.',
      'Arms resting naturally at sides without blocking torso contours.',
      'Avoid high-glare backlighting behind your head.'
    ]
  },
  {
    type: 'legs',
    title: 'Legs / Lower-Body Photo',
    stepNumber: 'Step 3 of 5',
    description: 'Lower body from waist down to ankles. MediaPipe validates hip, knee, and ankle keypoints.',
    guidance: [
      'Frame from waistline down to ankles and feet.',
      'Stand straight with both legs clearly visible and uncrossed.',
      'Ensure background contrasts well with your pants or legs.',
      'Keep legs parallel with a slight gap between feet.'
    ]
  },
  {
    type: 'feet',
    title: 'Foot / Shoe Photo',
    stepNumber: 'Step 4 of 5',
    description: 'Clear photo of both feet or footwear. MediaPipe checks lower extremities and ankle positions.',
    guidance: [
      'Take photo looking down or from low angle capturing both feet clearly.',
      'Ensure shoes or bare feet are fully visible and not cut off.',
      'Provide good floor illumination without harsh cast shadows.',
      'Avoid oversized garments covering the ankles or shoe tops.'
    ]
  },
  {
    type: 'face',
    title: 'Face / Portrait Photo',
    stepNumber: 'Step 5 of 5',
    description: 'Centered portrait photo. MediaPipe validates facial contour and eye/nose landmarks.',
    guidance: [
      'Position your face centered in frame at eye level.',
      'Maintain a neutral expression with eyes open facing the camera.',
      'Ensure even lighting across both sides of the face.',
      'Keep hair back or away from covering eyes and cheekbones.'
    ]
  }
];

// App State
let state = {
  profiles: [],
  activeProfileId: null,
  activeProfileData: null,
  currentStepIndex: 0,
};

// DOM References
const profileDropdown = document.getElementById('profile-dropdown');
const newProfileBtn = document.getElementById('new-profile-btn');
const backendStatus = document.getElementById('backend-status');
const activeProfileName = document.getElementById('active-profile-name');
const activeProfileMeta = document.getElementById('active-profile-meta');
const completenessPercent = document.getElementById('completeness-percent');
const progressFill = document.getElementById('progress-fill');
const deleteProfileBtn = document.getElementById('delete-profile-btn');

// Dialog References
const createProfileDialog = document.getElementById('create-profile-dialog');
const profileNameInput = document.getElementById('profile-name-input');
const cancelCreateBtn = document.getElementById('cancel-create-btn');
const submitCreateBtn = document.getElementById('submit-create-btn');

// Workbench References
const currentStepTag = document.getElementById('current-step-tag');
const currentStepTitle = document.getElementById('current-step-title');
const currentStepDesc = document.getElementById('current-step-desc');
const currentGuidanceList = document.getElementById('current-guidance-list');
const mainDropZone = document.getElementById('main-drop-zone');
const dropZoneEmpty = document.getElementById('drop-zone-empty');
const dropZonePreview = document.getElementById('drop-zone-preview');
const previewImage = document.getElementById('preview-image');
const mpAnalyzingOverlay = document.getElementById('mp-analyzing-overlay');
const stepFileInput = document.getElementById('step-file-input');
const validationBanner = document.getElementById('validation-banner');
const bannerIcon = document.getElementById('banner-icon');
const bannerTitle = document.getElementById('banner-title');
const bannerMessage = document.getElementById('banner-message');
const prevStepBtn = document.getElementById('prev-step-btn');
const nextStepBtn = document.getElementById('next-step-btn');
const deletePhotoBtn = document.getElementById('delete-photo-btn');

/**
 * Check backend connection
 */
async function checkBackend() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      backendStatus.className = 'status-badge online';
      backendStatus.querySelector('.status-label').textContent = 'API Online';
      return true;
    }
  } catch (e) {
    // Offline
  }
  backendStatus.className = 'status-badge offline';
  backendStatus.querySelector('.status-label').textContent = 'API Offline';
  return false;
}

/**
 * Load list of profiles
 */
async function loadProfiles() {
  try {
    const res = await fetch(`${API_BASE}/api/profiles`);
    if (!res.ok) throw new Error('Failed to load profiles');
    state.profiles = await res.json();
    renderProfileDropdown();

    if (state.profiles.length > 0) {
      if (!state.activeProfileId || !state.profiles.find(p => p.id === state.activeProfileId)) {
        state.activeProfileId = state.profiles[0].id;
      }
      profileDropdown.value = state.activeProfileId;
      await loadActiveProfile(state.activeProfileId);
    } else {
      showCreateDialog();
    }
  } catch (err) {
    console.error('Error fetching profiles:', err);
  }
}

/**
 * Render profile select dropdown
 */
function renderProfileDropdown() {
  profileDropdown.innerHTML = '';
  if (state.profiles.length === 0) {
    profileDropdown.innerHTML = '<option value="" disabled selected>No profiles found</option>';
    deleteProfileBtn.disabled = true;
    return;
  }

  deleteProfileBtn.disabled = false;
  state.profiles.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = `${p.name} (${p.photo_count || 0}/5 photos)`;
    profileDropdown.appendChild(opt);
  });
}

/**
 * Load detailed data for active profile
 */
async function loadActiveProfile(profileId) {
  try {
    const res = await fetch(`${API_BASE}/api/profiles/${profileId}`);
    if (!res.ok) throw new Error('Failed to load profile details');
    state.activeProfileData = await res.json();
    state.activeProfileId = profileId;

    activeProfileName.textContent = state.activeProfileData.name;
    activeProfileMeta.textContent = `ID #${state.activeProfileData.id} • Created ${new Date(state.activeProfileData.created_at).toLocaleDateString()}`;

    updateBadgesAndProgress();
    renderStep(state.currentStepIndex);
  } catch (err) {
    console.error('Error loading profile:', err);
  }
}

/**
 * Update step navigation badges and progress bar
 */
function updateBadgesAndProgress() {
  const photos = state.activeProfileData?.photos || [];
  let completedCount = 0;

  STEP_DEFINITIONS.forEach(def => {
    const existing = photos.find(p => p.photo_type === def.type);
    const badge = document.getElementById(`badge-${def.type}`);
    if (existing) {
      badge.textContent = '✅';
      completedCount++;
    } else {
      badge.textContent = '⭕';
    }
  });

  const percent = Math.round((completedCount / 5) * 100);
  completenessPercent.textContent = `${percent}%`;
  progressFill.style.width = `${percent}%`;
}

/**
 * Render current step UI & guidance
 */
function renderStep(index) {
  state.currentStepIndex = index;
  const def = STEP_DEFINITIONS[index];

  // Update step headers
  currentStepTag.textContent = def.stepNumber;
  currentStepTitle.textContent = def.title;
  currentStepDesc.textContent = def.description;

  // Update guidance items
  currentGuidanceList.innerHTML = '';
  def.guidance.forEach(text => {
    const li = document.createElement('li');
    li.textContent = text;
    currentGuidanceList.appendChild(li);
  });

  // Update active sidebar nav
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.type === def.type);
  });

  // Update buttons
  prevStepBtn.disabled = index === 0;
  nextStepBtn.textContent = index === STEP_DEFINITIONS.length - 1 ? 'Finish Profile' : 'Next Step';

  // Check if current photo exists for this profile
  const existingPhoto = state.activeProfileData?.photos?.find(p => p.photo_type === def.type);
  hideValidationBanner();

  if (existingPhoto) {
    // Show existing photo preview
    dropZoneEmpty.classList.add('hidden');
    dropZonePreview.classList.remove('hidden');
    previewImage.src = `${API_BASE}${existingPhoto.access_url}`;
    deletePhotoBtn.classList.remove('hidden');
    showValidationBanner('success', 'MediaPipe Landmark Validated', 'Photo meets all body landmark criteria and is registered.');
  } else {
    // Empty state
    dropZoneEmpty.classList.remove('hidden');
    dropZonePreview.classList.add('hidden');
    previewImage.src = '';
    deletePhotoBtn.classList.add('hidden');
  }
}

/**
 * Handle Photo Upload with MediaPipe Validation
 */
async function handlePhotoUpload(file) {
  if (!state.activeProfileId) {
    showValidationBanner('error', 'No Profile Selected', 'Please select or create a profile first.');
    return;
  }

  const def = STEP_DEFINITIONS[state.currentStepIndex];

  // Show local preview immediately & analyzing overlay
  const reader = new FileReader();
  reader.onload = (e) => {
    previewImage.src = e.target.result;
    dropZoneEmpty.classList.add('hidden');
    dropZonePreview.classList.remove('hidden');
    mpAnalyzingOverlay.classList.remove('hidden');
  };
  reader.readAsDataURL(file);

  showValidationBanner('info', 'Analyzing with MediaPipe...', 'Validating human presence, posture, and required landmarks.');

  // Submit to backend
  const formData = new FormData();
  formData.append('photo_type', def.type);
  formData.append('file', file);

  try {
    const res = await fetch(`${API_BASE}/api/profiles/${state.activeProfileId}/photos`, {
      method: 'POST',
      body: formData,
    });

    mpAnalyzingOverlay.classList.add('hidden');

    if (res.status === 201) {
      const photo = await res.json();
      showValidationBanner(
        'success',
        'MediaPipe Validation Passed! ✓',
        'Required landmarks detected with high confidence. Photo securely saved.'
      );
      deletePhotoBtn.classList.remove('hidden');
      await loadActiveProfile(state.activeProfileId);
    } else {
      const err = await res.json();
      const message = err.detail || 'MediaPipe validation rejected this photo.';
      showValidationBanner(
        'error',
        'MediaPipe Landmark Rejection ⚠️',
        `${message} Please review the on-screen guidance and re-upload.`
      );
      deletePhotoBtn.classList.add('hidden');
      dropZoneEmpty.classList.remove('hidden');
      dropZonePreview.classList.add('hidden');
      previewImage.src = '';
    }
  } catch (err) {
    mpAnalyzingOverlay.classList.add('hidden');
    showValidationBanner('error', 'Upload Error', 'Could not reach backend API server.');
  }
}

/**
 * Delete photo for current step
 */
async function handleDeletePhoto() {
  const def = STEP_DEFINITIONS[state.currentStepIndex];
  const photo = state.activeProfileData?.photos?.find(p => p.photo_type === def.type);
  if (!photo) return;

  try {
    const res = await fetch(`${API_BASE}/api/photos/${photo.id}`, { method: 'DELETE' });
    if (res.status === 204) {
      showValidationBanner('info', 'Photo Removed', 'You can now upload a new replacement photo.');
      await loadActiveProfile(state.activeProfileId);
    }
  } catch (err) {
    console.error('Failed to delete photo:', err);
  }
}

/**
 * Create new profile
 */
async function handleCreateProfile() {
  const name = profileNameInput.value.trim();
  if (!name) return;

  try {
    const res = await fetch(`${API_BASE}/api/profiles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });

    if (res.ok) {
      const newProfile = await res.json();
      createProfileDialog.classList.add('hidden');
      profileNameInput.value = '';
      await loadProfiles();
      state.activeProfileId = newProfile.id;
      profileDropdown.value = newProfile.id;
      await loadActiveProfile(newProfile.id);
      renderStep(0);
    }
  } catch (err) {
    console.error('Error creating profile:', err);
  }
}

/**
 * Delete active profile
 */
async function handleDeleteProfile() {
  if (!state.activeProfileId) return;
  const confirmed = confirm(`Are you sure you want to delete profile "${state.activeProfileData?.name}"? All photos will be permanently removed.`);
  if (!confirmed) return;

  try {
    const res = await fetch(`${API_BASE}/api/profiles/${state.activeProfileId}`, {
      method: 'DELETE',
    });
    if (res.status === 204) {
      state.activeProfileId = null;
      await loadProfiles();
    }
  } catch (err) {
    console.error('Failed to delete profile:', err);
  }
}

/**
 * Banner feedback helper
 */
function showValidationBanner(type, title, message) {
  validationBanner.className = `validation-banner ${type}`;
  bannerTitle.textContent = title;
  bannerMessage.textContent = message;
  bannerIcon.textContent = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  validationBanner.classList.remove('hidden');
}

function hideValidationBanner() {
  validationBanner.classList.add('hidden');
}

function showCreateDialog() {
  createProfileDialog.classList.remove('hidden');
  profileNameInput.focus();
}

// Event Listeners
profileDropdown.addEventListener('change', (e) => {
  loadActiveProfile(Number(e.target.value));
});

newProfileBtn.addEventListener('click', showCreateDialog);
cancelCreateBtn.addEventListener('click', () => createProfileDialog.classList.add('hidden'));
submitCreateBtn.addEventListener('click', handleCreateProfile);
profileNameInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleCreateProfile();
});

deleteProfileBtn.addEventListener('click', handleDeleteProfile);
deletePhotoBtn.addEventListener('click', handleDeletePhoto);

// Navigation clicks
document.querySelectorAll('.nav-item').forEach((item, index) => {
  item.addEventListener('click', () => renderStep(index));
});

prevStepBtn.addEventListener('click', () => {
  if (state.currentStepIndex > 0) renderStep(state.currentStepIndex - 1);
});

nextStepBtn.addEventListener('click', () => {
  if (state.currentStepIndex < STEP_DEFINITIONS.length - 1) {
    renderStep(state.currentStepIndex + 1);
  } else {
    alert('🎉 Digital Profile Completed! All body landmarks verified with MediaPipe.');
  }
});

// File upload events
mainDropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  mainDropZone.style.borderColor = 'var(--accent-primary)';
});

mainDropZone.addEventListener('dragleave', () => {
  mainDropZone.style.borderColor = '';
});

mainDropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  mainDropZone.style.borderColor = '';
  if (e.dataTransfer.files.length > 0) {
    handlePhotoUpload(e.dataTransfer.files[0]);
  }
});

stepFileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    handlePhotoUpload(e.target.files[0]);
  }
});

// Initialize
checkBackend();
loadProfiles();
renderStep(0);
