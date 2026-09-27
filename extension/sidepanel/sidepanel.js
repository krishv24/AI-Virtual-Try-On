/**
 * AI Virtual Try-On - Side Panel Studio Controller (Phase 3 Shell)
 * Manages Profile Switcher, Products on this page, Try-On processing, and Results View.
 * Uses chrome.storage.local for lightweight state only (never storing photo blobs).
 */

/* ── Theme Toggle (dark default) ─────────────────────────────── */
(function initTheme() {
  chrome.storage.local.get('aivton_theme', (res) => {
    if (res.aivton_theme === 'light') document.body.classList.add('light');
  });
})();
document.addEventListener('DOMContentLoaded', () => {
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      document.body.classList.toggle('light');
      const mode = document.body.classList.contains('light') ? 'light' : 'dark';
      chrome.storage.local.set({ aivton_theme: mode });
    });
  }
});

const BACKEND_BASE = 'http://localhost:8000';

// Default mock products for initial testing / demo empty state
const DEMO_GARMENTS = [
  {
    id: 'prod_hoodie_01',
    title: 'Oversized Streetwear Hoodie',
    category: 'Upper Body',
    price: '$58.00',
    imageUrl: 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=400&auto=format&fit=crop&q=80',
    sourceUrl: 'https://example.com/demo-hoodie',
  },
  {
    id: 'prod_jacket_02',
    title: 'Classic Denim Trucker Jacket',
    category: 'Upper Body',
    price: '$79.99',
    imageUrl: 'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=400&auto=format&fit=crop&q=80',
    sourceUrl: 'https://example.com/demo-denim',
  },
  {
    id: 'prod_pants_03',
    title: 'Pleated Wide-Leg Trousers',
    category: 'Lower Body',
    price: '$64.50',
    imageUrl: 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=400&auto=format&fit=crop&q=80',
    sourceUrl: 'https://example.com/demo-pants',
  }
];

// App State
let state = {
  profiles: [],
  activeProfileId: null,
  activeProfileData: null,
  activeAngle: 'front_full_body',
  activeModelPhotoUrl: null,
  products: [],
  selectedProductId: null,
  isProcessing: false,
  closetItems: [],
  activeClosetCategory: 'all',
  compareSlots: {
    lookA: null,
    lookB: null,
  },
  compareMode: 'dual',
};

// DOM References
const spStatusBadge = document.getElementById('sp-status-badge');
const spStatusText = document.getElementById('sp-status-text');
const spProfileSelect = document.getElementById('sp-profile-select');
const spManageProfilesBtn = document.getElementById('sp-manage-profiles-btn');
const spGoUploadBtn = document.getElementById('sp-go-upload-btn');
const activeModelImg = document.getElementById('active-model-img');
const modelEmptyState = document.getElementById('model-empty-state');
const angleChips = document.getElementById('angle-chips');

// Bonus Feature 2: Quick Profile Controls
const activeProfileNameBadge = document.getElementById('active-profile-name-badge');
const spQuickAddProfileBtn = document.getElementById('sp-quick-add-profile-btn');
const quickProfileCreator = document.getElementById('quick-profile-creator');
const quickProfileNameInput = document.getElementById('quick-profile-name-input');
const quickProfileSaveBtn = document.getElementById('quick-profile-save-btn');
const quickProfileCancelBtn = document.getElementById('quick-profile-cancel-btn');

const productCountBadge = document.getElementById('product-count-badge');
const scanPageBtn = document.getElementById('scan-page-btn');
const addDemoProductBtn = document.getElementById('add-demo-product-btn');
const productsEmptyState = document.getElementById('products-empty-state');
const productsGrid = document.getElementById('products-grid');

const tryonBtn = document.getElementById('tryon-btn');
const tryonBtnText = document.getElementById('tryon-btn-text');
const processingStatusArea = document.getElementById('processing-status-area');
const processingMainStatus = document.getElementById('processing-main-status');
const processingDetailText = document.getElementById('processing-detail-text');
const pipelineProgressFill = document.getElementById('pipeline-progress-fill');
const stageClip = document.getElementById('stage-clip');
const stagePose = document.getElementById('stage-pose');
const stageVton = document.getElementById('stage-vton');

const resultsEmptyState = document.getElementById('results-empty-state');
const resultsContent = document.getElementById('results-content');
const resultsActions = document.getElementById('results-actions');
const resultImg = document.getElementById('result-img');
const resultGarmentTitle = document.getElementById('result-garment-title');
const resultCategoryTag = document.getElementById('result-category-tag');
const resetResultBtn = document.getElementById('reset-result-btn');
const downloadResultBtn = document.getElementById('download-result-btn');
const comparisonBadge = document.getElementById('comparison-badge');
const lowConfidenceBanner = document.getElementById('low-confidence-banner');
const lowConfidenceReason = document.getElementById('low-confidence-reason');
const resultCachedBadge = document.getElementById('result-cached-badge');
const forceRefreshBtn = document.getElementById('force-refresh-btn');

// Bonus Feature 1: Virtual Wardrobe References
const closetCountBadge = document.getElementById('closet-count-badge');
const refreshClosetBtn = document.getElementById('refresh-closet-btn');
const closetEmptyState = document.getElementById('closet-empty-state');
const closetEmptyTitle = document.getElementById('closet-empty-title');
const closetEmptySubtext = document.getElementById('closet-empty-subtext');
const closetGrid = document.getElementById('closet-grid');
const closetFiltersBar = document.getElementById('closet-filters-bar');

// Phase 12 Progress & Error Notice References
const processingTimer = document.getElementById('processing-timer');
const processingPercent = document.getElementById('processing-percent');
const errorNoticeCard = document.getElementById('error-notice-card');
const errorCardIcon = document.getElementById('error-card-icon');
const errorCardTitle = document.getElementById('error-card-title');
const errorCardBadge = document.getElementById('error-card-badge');
const errorCardMessage = document.getElementById('error-card-message');
const errorActionBtn = document.getElementById('error-action-btn');
const errorDismissBtn = document.getElementById('error-dismiss-btn');

// Bonus Feature 4: Side-by-Side Comparison Dock & Modal References
const compareDock = document.getElementById('compare-dock');
const compareDockCount = document.getElementById('compare-dock-count');
const compareClearBtn = document.getElementById('compare-clear-btn');
const slotACard = document.getElementById('slot-a-card');
const slotAName = document.getElementById('slot-a-name');
const slotARemove = document.getElementById('slot-a-remove');
const slotBCard = document.getElementById('slot-b-card');
const slotBName = document.getElementById('slot-b-name');
const slotBRemove = document.getElementById('slot-b-remove');
const launchCompareBtn = document.getElementById('launch-compare-btn');

const compareModal = document.getElementById('compare-modal');
const closeCompareModalBtn = document.getElementById('close-compare-modal-btn');
const toggleDualMode = document.getElementById('toggle-dual-mode');
const toggleSliderMode = document.getElementById('toggle-slider-mode');
const compareDualView = document.getElementById('compare-dual-view');
const compareSliderView = document.getElementById('compare-slider-view');

const compTitleA = document.getElementById('comp-title-a');
const compImgA = document.getElementById('comp-img-a');
const compScoreA = document.getElementById('comp-score-a');
const compCatA = document.getElementById('comp-cat-a');
const compLoadingA = document.getElementById('comp-loading-a');
const compRunA = document.getElementById('comp-run-a');

const compTitleB = document.getElementById('comp-title-b');
const compImgB = document.getElementById('comp-img-b');
const compScoreB = document.getElementById('comp-score-b');
const compCatB = document.getElementById('comp-cat-b');
const compLoadingB = document.getElementById('comp-loading-b');
const compRunB = document.getElementById('comp-run-b');

const splitSliderContainer = document.getElementById('split-slider-container');
const sliderImgBg = document.getElementById('slider-img-bg');
const sliderImgFg = document.getElementById('slider-img-fg');
const sliderFgContainer = document.getElementById('slider-fg-container');
const sliderDividerLine = document.getElementById('slider-divider-line');

// --- 1. Lightweight Storage Sync Helpers ---

async function getStoredState() {
  return new Promise((resolve) => {
    chrome.storage.local.get(
      ['activeProfileId', 'selectedProductId', 'storedProducts', 'activeAngle'],
      (result) => resolve(result || {})
    );
  });
}

function setStoredState(data) {
  chrome.storage.local.set(data);
}

// --- 2. Backend Health & Profile Switcher ---

async function checkBackendHealth() {
  try {
    const res = await fetch(`${BACKEND_BASE}/health`, { signal: AbortSignal.timeout(2500) });
    if (res.ok) {
      spStatusBadge.className = 'status-chip online';
      spStatusText.textContent = 'API Online';
      return true;
    }
  } catch (e) {}
  spStatusBadge.className = 'status-chip offline';
  spStatusText.textContent = 'API Offline';
  return false;
}

async function loadProfiles() {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/profiles`);
    if (!res.ok) return;
    state.profiles = await res.json();

    spProfileSelect.innerHTML = '';
    if (state.profiles.length === 0) {
      spProfileSelect.innerHTML = '<option value="" disabled selected>No profiles (Click + Manage)</option>';
      renderModelPhoto();
      updateTryOnButtonState();
      return;
    }

    state.profiles.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.photo_count || 0}/5 photos)`;
      spProfileSelect.appendChild(opt);
    });

    // Check stored activeProfileId or select first
    const stored = await getStoredState();
    let targetId = stored.activeProfileId;
    if (!targetId || !state.profiles.find((p) => p.id === targetId)) {
      targetId = state.profiles[0].id;
    }

    state.activeProfileId = targetId;
    spProfileSelect.value = targetId;
    setStoredState({ activeProfileId: targetId });

    await loadActiveProfileData(targetId);
  } catch (err) {
    console.warn('[AI Try-On] Error loading profiles:', err);
  }
}

async function loadActiveProfileData(profileId) {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/profiles/${profileId}`);
    if (!res.ok) return;
    state.activeProfileData = await res.json();
    if (activeProfileNameBadge) {
      activeProfileNameBadge.textContent = state.activeProfileData?.name || 'Active';
    }
    renderModelPhoto();
    updateTryOnButtonState();
    await loadClosetHistory(profileId);
  } catch (err) {
    console.warn('[AI Try-On] Error loading profile detail:', err);
  }
}

function toggleQuickProfileCreator(show) {
  if (!quickProfileCreator) return;
  if (show === undefined) {
    quickProfileCreator.classList.toggle('hidden');
  } else if (show) {
    quickProfileCreator.classList.remove('hidden');
    if (quickProfileNameInput) quickProfileNameInput.focus();
  } else {
    quickProfileCreator.classList.add('hidden');
    if (quickProfileNameInput) quickProfileNameInput.value = '';
  }
}

async function handleQuickCreateProfile() {
  const name = quickProfileNameInput ? quickProfileNameInput.value.trim() : '';
  if (!name) {
    if (quickProfileNameInput) quickProfileNameInput.focus();
    return;
  }

  try {
    const res = await fetch(`${BACKEND_BASE}/api/profiles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, consent_no_training: true }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not create profile');
    }

    const newProfile = await res.json();
    toggleQuickProfileCreator(false);
    await loadProfiles();
    state.activeProfileId = newProfile.id;
    if (spProfileSelect) spProfileSelect.value = newProfile.id;
    setStoredState({ activeProfileId: newProfile.id });
    await loadActiveProfileData(newProfile.id);
  } catch (err) {
    alert(`Could not create profile: ${err.message}`);
  }
}

function renderModelPhoto() {
  const photos = state.activeProfileData?.photos || [];
  const targetPhoto = photos.find((p) => p.photo_type === state.activeAngle) || photos[0];

  if (targetPhoto) {
    state.activeModelPhotoUrl = `${BACKEND_BASE}${targetPhoto.access_url}`;
    activeModelImg.src = state.activeModelPhotoUrl;
    activeModelImg.classList.remove('hidden');
    modelEmptyState.classList.add('hidden');
  } else {
    state.activeModelPhotoUrl = null;
    activeModelImg.src = '';
    activeModelImg.classList.add('hidden');
    modelEmptyState.classList.remove('hidden');
  }
}

// --- 2.5 Front Shot Heuristics for Variant Handling ---

function scoreProductImage(url) {
  if (!url) return -100;
  const lower = url.toLowerCase();
  let score = 0;
  if (lower.includes('front')) score += 50;
  if (lower.includes('main') || lower.includes('primary') || lower.includes('hero')) score += 40;
  if (lower.includes('flat') || lower.includes('ghost') || lower.includes('packshot')) score += 45;
  if (lower.includes('white') || lower.includes('clean')) score += 25;
  if (lower.includes('back') || lower.includes('rear')) score -= 45;
  if (lower.includes('side')) score -= 25;
  if (lower.includes('detail') || lower.includes('zoom')) score -= 35;
  if (lower.includes('swatch') || lower.includes('thumb')) score -= 40;
  if (lower.includes('lifestyle') || lower.includes('lookbook') || lower.includes('editorial') || lower.includes('street')) score -= 50;
  if (lower.includes('2000') || lower.includes('1500') || lower.includes('hires')) score += 15;
  return score;
}

function selectBestFrontShot(imageUrls) {
  if (!imageUrls || imageUrls.length === 0) return null;
  if (imageUrls.length === 1) return imageUrls[0];
  let best = imageUrls[0];
  let maxScore = scoreProductImage(best);
  for (let i = 1; i < imageUrls.length; i++) {
    const s = scoreProductImage(imageUrls[i]);
    if (s > maxScore) {
      maxScore = s;
      best = imageUrls[i];
    }
  }
  return best;
}

// Map tracking chosen variant per product
state.variantSelections = {};

// --- 3. Products on this Page ---

function renderProducts() {
  productCountBadge.textContent = state.products.length;

  if (state.products.length === 0) {
    productsEmptyState.classList.remove('hidden');
    productsGrid.classList.add('hidden');
    productsGrid.innerHTML = '';
    state.selectedProductId = null;
    setStoredState({ selectedProductId: null });
    updateTryOnButtonState();
    return;
  }

  productsEmptyState.classList.add('hidden');
  productsGrid.classList.remove('hidden');
  productsGrid.innerHTML = '';

  state.products.forEach((prod) => {
    const images = Array.isArray(prod.imageUrls) && prod.imageUrls.length > 0
      ? prod.imageUrls
      : [prod.imageUrl].filter(Boolean);

    const autoFrontShot = selectBestFrontShot(images);
    if (!state.variantSelections[prod.id]) {
      state.variantSelections[prod.id] = autoFrontShot || images[0];
    }

    const currentImg = state.variantSelections[prod.id] || images[0] || '';
    const isSelected = state.selectedProductId === prod.id;
    const isStaged = isStagedForCompare(prod.id);

    const card = document.createElement('div');
    card.className = `product-card ${isSelected ? 'selected' : ''}`;
    card.dataset.id = prod.id;

    card.innerHTML = `
      ${images.length > 1 ? '<span class="auto-front-badge" title="Auto-selected front-facing angle">✨ Front Shot</span>' : ''}
      <img src="${currentImg}" alt="${prod.title}" class="product-thumb" id="sp-thumb-${prod.id}" loading="lazy">
      <div class="product-meta">
        <span class="product-name" title="${prod.title}">${prod.title}</span>
        <div class="product-tags">
          <span class="category-tag">${prod.category || 'Apparel'}</span>
          <span class="product-price">${prod.price || ''}</span>
          <button class="card-compare-btn ${isStaged ? 'staged' : ''}" data-compare-id="${prod.id}" title="Stage for side-by-side comparison">
            ${isStaged ? '✓ In Compare' : '⚖️ Compare'}
          </button>
        </div>
      </div>
    `;

    // Multiple Images Variant Selector
    if (images.length > 1) {
      const variantStrip = document.createElement('div');
      variantStrip.style.cssText = 'display:flex; gap:4px; overflow-x:auto; padding-top:4px; border-top:1px solid rgba(255,255,255,0.06); margin-top:2px;';

      images.forEach((imgUrl, idx) => {
        const t = document.createElement('img');
        t.src = imgUrl;
        t.style.cssText = `width:26px; height:30px; object-fit:cover; border-radius:3px; cursor:pointer; border:1.5px solid ${imgUrl === currentImg ? '#818cf8' : 'transparent'}; flex-shrink:0;`;
        t.title = imgUrl === autoFrontShot ? '⭐ Clearest Front Shot (Auto-selected)' : `Angle #${idx + 1}`;

        t.addEventListener('click', (e) => {
          e.stopPropagation();
          state.variantSelections[prod.id] = imgUrl;
          const mainThumb = document.getElementById(`sp-thumb-${prod.id}`);
          if (mainThumb) mainThumb.src = imgUrl;

          variantStrip.querySelectorAll('img').forEach((thumb) => {
            thumb.style.borderColor = 'transparent';
          });
          t.style.borderColor = '#818cf8';

          selectProduct(prod.id, imgUrl);
        });

        variantStrip.appendChild(t);
      });

      card.appendChild(variantStrip);
    }

    // Compare button click handler
    const compBtn = card.querySelector('.card-compare-btn');
    if (compBtn) {
      compBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        stageItemForComparison({
          id: prod.id,
          title: prod.title,
          category: prod.category || 'Apparel',
          price: prod.price || '',
          imageUrl: currentImg,
        });
      });
    }

    card.addEventListener('click', () => selectProduct(prod.id, currentImg));
    productsGrid.appendChild(card);
  });

  updateTryOnButtonState();
}

function selectProduct(productId, chosenImageUrl) {
  if (state.selectedProductId === productId && !chosenImageUrl) {
    state.selectedProductId = null;
    setStoredState({ selectedProductId: null, activeTryOnTarget: null });
  } else {
    state.selectedProductId = productId;
    const prod = state.products.find((p) => p.id === productId);
    const img = chosenImageUrl || state.variantSelections[productId] || prod?.imageUrl;

    const target = {
      productId,
      title: prod ? prod.title : '',
      price: prod ? prod.price : '',
      category: prod ? prod.category : 'Apparel',
      selectedImageUrl: img,
      sourceUrl: prod ? prod.sourceUrl : window.location.href,
      updatedAt: new Date().toISOString(),
    };

    setStoredState({ selectedProductId: productId, activeTryOnTarget: target });
  }

  // Update card styles
  document.querySelectorAll('.product-card').forEach((card) => {
    card.classList.toggle('selected', card.dataset.id === state.selectedProductId);
  });

  updateTryOnButtonState();
}

function addDemoGarments() {
  // Toggle demo items into products list
  const existingIds = new Set(state.products.map((p) => p.id));
  const newItems = DEMO_GARMENTS.filter((g) => !existingIds.has(g.id));

  if (newItems.length > 0) {
    state.products = [...newItems, ...state.products];
  } else {
    // Toggle/reset
    state.products = [...DEMO_GARMENTS];
  }

  setStoredState({ storedProducts: state.products });
  renderProducts();
}

// --- 4. Try On Button & Processing Feedback ---

function updateTryOnButtonState() {
  if (state.isProcessing) {
    tryonBtn.disabled = true;
    tryonBtnText.textContent = 'Processing Virtual Try-On...';
    return;
  }

  const hasPhoto = Boolean(state.activeModelPhotoUrl);
  const hasProduct = Boolean(state.selectedProductId);

  if (!hasPhoto) {
    tryonBtn.disabled = true;
    tryonBtnText.textContent = 'Upload reference photo to Try On';
  } else if (!hasProduct) {
    tryonBtn.disabled = true;
    tryonBtnText.textContent = 'Select a product above to Try On';
  } else {
    tryonBtn.disabled = false;
    const selectedProd = state.products.find((p) => p.id === state.selectedProductId);
    tryonBtnText.textContent = `Try On: ${selectedProd ? selectedProd.title : 'Selected Garment'}`;
  }
}

// --- 4.5 Real-Time Progress Tracker & Error Surfacing ---

let progressInterval = null;
let progressStartTime = 0;

function startProgressTracker(forceRefresh = false) {
  stopProgressTracker(false);
  progressStartTime = Date.now();
  if (processingTimer) processingTimer.textContent = '0.0s';
  if (processingPercent) processingPercent.textContent = '10%';
  if (pipelineProgressFill) pipelineProgressFill.style.width = '10%';

  progressInterval = setInterval(() => {
    const elapsedSec = (Date.now() - progressStartTime) / 1000;
    if (processingTimer) {
      processingTimer.textContent = `${elapsedSec.toFixed(1)}s`;
    }

    // Dynamic curve simulating 5-25s diffusion inference with live milestone feedback
    let currentPct = 10;
    if (elapsedSec < 1.0) {
      currentPct = 10 + elapsedSec * 15; // 10 -> 25%
      setStepStatus(stageClip, 'active', 'Step 1: Identifying product attributes & front view...');
    } else if (elapsedSec < 2.5) {
      setStepStatus(stageClip, 'done', 'Target identified & front-angle normalized');
      setStepStatus(stagePose, 'active', 'Step 2: Resolving profile pose & body keypoints...');
      currentPct = 25 + (elapsedSec - 1.0) * 13; // 25 -> 45%
    } else {
      setStepStatus(stageClip, 'done', 'Target identified');
      setStepStatus(stagePose, 'done', 'Profile pose aligned');
      setStepStatus(stageVton, 'active', forceRefresh ? 'Step 3: Neural diffusion re-generating (cache bypassed)...' : 'Step 3: Neural diffusion drape synthesis...');

      if (elapsedSec < 7.0) {
        currentPct = 45 + (elapsedSec - 2.5) * 5.5; // 45 -> 70%
        processingDetailText.textContent = 'Denoising garment warp & fabric textures...';
      } else if (elapsedSec < 16.0) {
        currentPct = 70 + (elapsedSec - 7.0) * 1.6; // 70 -> 84%
        processingDetailText.textContent = 'Synthesizing realistic body contours & lighting...';
      } else if (elapsedSec < 28.0) {
        currentPct = 84 + (elapsedSec - 16.0) * 0.6; // 84 -> 91%
        processingDetailText.textContent = 'ZeroGPU worker finalizing composite drape...';
      } else {
        currentPct = 93;
        processingDetailText.textContent = 'ZeroGPU worker allocating compute (almost ready)...';
      }
    }

    currentPct = Math.min(94, Math.round(currentPct));
    if (pipelineProgressFill) pipelineProgressFill.style.width = `${currentPct}%`;
    if (processingPercent) processingPercent.textContent = `${currentPct}%`;
  }, 100);
}

function stopProgressTracker(success = true) {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
  if (success) {
    const elapsedSec = ((Date.now() - progressStartTime) / 1000).toFixed(1);
    if (processingTimer) processingTimer.textContent = `${elapsedSec}s`;
    if (pipelineProgressFill) pipelineProgressFill.style.width = '100%';
    if (processingPercent) processingPercent.textContent = '100%';
  }
}

function formatErrorMessage(errorData, fallbackStatus) {
  if (!errorData) return `Server error ${fallbackStatus || 500}`;
  if (typeof errorData === 'string') return errorData;

  // FastAPI validation error list: {"detail": [{"loc": [...], "msg": "..."}]}
  if (Array.isArray(errorData.detail)) {
    return errorData.detail
      .map((item) => {
        if (typeof item === 'string') return item;
        const field = Array.isArray(item.loc) ? item.loc.filter((k) => k !== 'body').join('.') : '';
        const msg = item.msg || item.message || JSON.stringify(item);
        return field ? `${field}: ${msg}` : msg;
      })
      .join(' | ');
  }

  if (typeof errorData.detail === 'object' && errorData.detail !== null) {
    return errorData.detail.message || errorData.detail.msg || errorData.detail.detail || errorData.detail.error || JSON.stringify(errorData.detail);
  }

  if (typeof errorData.detail === 'string') {
    return errorData.detail;
  }

  if (errorData.message) return String(errorData.message);
  if (errorData.error) return String(errorData.error);

  try {
    return JSON.stringify(errorData);
  } catch (_) {
    return String(errorData);
  }
}

function showErrorNotice(type, title, message, actionLabel = null, actionFn = null) {
  if (!errorNoticeCard) return;
  hideErrorNotice();

  errorNoticeCard.className = `error-notice-card ${type}`;

  const icons = {
    timeout: '⏱️',
    'no-product': '🛍️',
    unsupported: '🚫',
    'missing-photo': '👤',
    offline: '🔌',
    generic: '⚠️',
  };

  const badges = {
    timeout: 'Timeout',
    'no-product': 'No Apparel',
    unsupported: 'Unsupported',
    'missing-photo': 'Photo Needed',
    offline: 'Offline',
    generic: 'Issue',
  };

  let cleanMsg = message;
  if (typeof message === 'object' && message !== null) {
    try {
      cleanMsg = message.message || message.msg || message.detail || JSON.stringify(message);
    } catch (_) {
      cleanMsg = String(message);
    }
  }

  if (errorCardIcon) errorCardIcon.textContent = icons[type] || '⚠️';
  if (errorCardTitle) errorCardTitle.textContent = title;
  if (errorCardBadge) errorCardBadge.textContent = badges[type] || 'Notice';
  if (errorCardMessage) errorCardMessage.textContent = cleanMsg || 'An unexpected error occurred during processing.';

  if (actionLabel && actionFn && errorActionBtn) {
    errorActionBtn.textContent = actionLabel;
    errorActionBtn.classList.remove('hidden');
    errorActionBtn.onclick = () => {
      hideErrorNotice();
      actionFn();
    };
  } else if (errorActionBtn) {
    errorActionBtn.classList.add('hidden');
  }

  errorNoticeCard.classList.remove('hidden');
}

function hideErrorNotice() {
  if (errorNoticeCard) {
    errorNoticeCard.classList.add('hidden');
  }
}

async function handleTryOnExecution(forceRefresh = false) {
  hideErrorNotice();

  // Guard against PointerEvent/MouseEvent passed when used directly as event listener
  const shouldForceRefresh = typeof forceRefresh === 'boolean' ? forceRefresh : false;

  // Distinct check 1: No products detected on page
  if (!state.products || state.products.length === 0) {
    showErrorNotice(
      'no-product',
      'No Apparel Detected',
      'No clothing products have been detected on this page yet. Please browse an apparel store or tap the "+" button above to add our sample demo garment.',
      '➕ Add Demo Garment',
      addDemoGarments
    );
    return;
  }

  // Distinct check 2: No product selected
  const selectedProd = state.products.find((p) => p.id === state.selectedProductId);
  if (!selectedProd) {
    showErrorNotice(
      'no-product',
      'Select a Product',
      'Please select one of the detected clothing items above to begin your virtual try-on.',
      'Select First Item',
      () => {
        if (state.products.length > 0) selectProduct(state.products[0].id);
      }
    );
    return;
  }

  // Distinct check 3: No profile loaded
  if (!state.activeProfileId) {
    showErrorNotice(
      'missing-photo',
      'No Profile Loaded',
      'Please select or create a digital profile first before running virtual try-on.',
      '👤 Open Studio',
      openStudio
    );
    return;
  }

  const chosenGarmentImg = state.variantSelections[selectedProd.id] || selectedProd.imageUrl;
  if (!chosenGarmentImg) {
    showErrorNotice(
      'no-product',
      'Missing Garment Image',
      'Could not find a valid product image URL for this item.',
      'Rescan Page',
      scanActivePageProducts
    );
    return;
  }

  state.isProcessing = true;
  updateTryOnButtonState();

  // Show Processing Status Area & Start Live Timer Tracker
  processingStatusArea.classList.remove('hidden');
  resetPipelineSteps();
  startProgressTracker(shouldForceRefresh);

  try {
    const payload = {
      profile_id: state.activeProfileId,
      garment_image_url: chosenGarmentImg,
      product_id: typeof selectedProd.id === 'number' ? selectedProd.id : null,
      category: selectedProd.category || 'auto',
      force_refresh: shouldForceRefresh,
    };

    const response = await fetch(`${BACKEND_BASE}/api/tryon`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let errorMsg = `Server error ${response.status}`;
      try {
        const errorData = await response.json();
        errorMsg = formatErrorMessage(errorData, response.status);
      } catch (_) {
        try {
          const text = await response.text();
          if (text) errorMsg = text;
        } catch (__) {}
      }
      throw new Error(errorMsg);
    }

    const tryonResult = await response.json();

    stopProgressTracker(true);
    const handlerLabel = tryonResult.cached
      ? '⚡ Instant Cache Hit'
      : (tryonResult.handler_name || 'Try-on synthesis');
    setStepStatus(stageVton, 'done', `${handlerLabel} complete!`);
    await delay(350);

    // Reveal Result View with real composited image
    showResultView(selectedProd, tryonResult);
    await loadClosetHistory(state.activeProfileId);
  } catch (err) {
    console.error('Try-On error:', err);
    stopProgressTracker(false);
    setStepStatus(stageVton, 'error', `Try-On failed: ${err.message}`);
    processingMainStatus.textContent = 'Virtual Try-On error';
    processingDetailText.textContent = err.message;

    const errMsg = err.message || '';
    const errLower = errMsg.toLowerCase();

    if (errLower.includes('timeout') || errLower.includes('timed out') || errLower.includes('504')) {
      showErrorNotice(
        'timeout',
        'Model Inference Timeout',
        'The CatVTON neural diffusion model took longer than 30s to respond. Hugging Face ZeroGPU workers occasionally experience cold starts (30–60s). Please wait a moment and try again.',
        '🔄 Retry Try-On',
        () => handleTryOnExecution(true)
      );
    } else if (errLower.includes('unsupported category') || errLower.includes('422')) {
      showErrorNotice(
        'unsupported',
        'Unsupported Garment Category',
        errMsg,
        'Browse Apparel',
        () => {}
      );
    } else if (errLower.includes('no uploaded photos') || errLower.includes('missing reference photo')) {
      showErrorNotice(
        'missing-photo',
        'Reference Photo Needed',
        errMsg,
        '👤 Open Profile Studio',
        openStudio
      );
    } else if (errLower.includes('failed to fetch') || errLower.includes('network') || errLower.includes('500') || errLower.includes('offline')) {
      showErrorNotice(
        'offline',
        'Backend Server Offline',
        'Could not communicate with the virtual try-on backend. Please verify that the FastAPI server is running on http://127.0.0.1:8000.',
        'Check Health',
        checkBackendHealth
      );
    } else {
      showErrorNotice(
        'generic',
        'Virtual Try-On Issue',
        errMsg,
        '🔄 Retry',
        () => handleTryOnExecution(false)
      );
    }
  } finally {
    state.isProcessing = false;
    updateTryOnButtonState();
    setTimeout(() => {
      if (!errorNoticeCard || errorNoticeCard.classList.contains('hidden')) {
        processingStatusArea.classList.add('hidden');
      }
    }, 3500);
  }
}



function resetPipelineSteps() {
  [stageClip, stagePose, stageVton].forEach((st) => {
    st.className = 'stage-step';
  });
  pipelineProgressFill.style.width = '10%';
  processingMainStatus.textContent = 'Initializing Try-On Pipeline...';
  processingDetailText.textContent = 'Preparing model image & garment source';
}

function setStepStatus(stepEl, status, detailMsg) {
  stepEl.className = `stage-step ${status}`;
  processingDetailText.textContent = detailMsg;
  if (status === 'active' || status === 'error') {
    processingMainStatus.textContent = detailMsg;
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// --- 5. Results View ---

function showResultView(product, tryonResult = null) {
  resultsEmptyState.classList.add('hidden');
  resultsContent.classList.remove('hidden');
  resultsActions.classList.remove('hidden');

  const chosenImg = state.variantSelections[product.id] || product.imageUrl;

  // Use synthesized tryon result image if available, else chosenImg
  if (tryonResult && tryonResult.access_url) {
    resultImg.src = `${BACKEND_BASE}${tryonResult.access_url}`;
  } else {
    resultImg.src = chosenImg;
  }

  resultGarmentTitle.textContent = product.title;
  const displayCat = (tryonResult && tryonResult.category) ? tryonResult.category : (product.category || 'Apparel');
  resultCategoryTag.textContent = displayCat;

  // Cached indicator & force-refresh button
  if (tryonResult && tryonResult.cached) {
    if (resultCachedBadge) resultCachedBadge.classList.remove('hidden');
    if (forceRefreshBtn) forceRefreshBtn.classList.remove('hidden');
  } else {
    if (resultCachedBadge) resultCachedBadge.classList.add('hidden');
    if (forceRefreshBtn) forceRefreshBtn.classList.add('hidden');
  }

  // Phase 9 Product Accuracy Safeguards: flag low confidence
  if (tryonResult && tryonResult.is_low_confidence) {
    if (lowConfidenceBanner) {
      lowConfidenceBanner.classList.remove('hidden');
      if (lowConfidenceReason) {
        lowConfidenceReason.textContent =
          tryonResult.accuracy_metrics?.flag_reason ||
          'Color or pattern deviation detected from original product.';
      }
    }
    if (comparisonBadge) {
      const scorePct = Math.round((tryonResult.accuracy_score || 0.4) * 100);
      comparisonBadge.textContent = `Fidelity: ${scorePct}% (Low Confidence)`;
      comparisonBadge.classList.add('low-conf');
    }
  } else {
    if (lowConfidenceBanner) {
      lowConfidenceBanner.classList.add('hidden');
    }
    if (comparisonBadge) {
      const scorePct = Math.round((tryonResult?.accuracy_score || 0.95) * 100);
      comparisonBadge.textContent = `Fidelity: ${scorePct}%`;
      comparisonBadge.classList.remove('low-conf');
    }
  }

  // Persist try-on result record (metadata only)
  setStoredState({
    lastResult: {
      productId: product.id,
      title: product.title,
      category: displayCat,
      selectedImageUrl: chosenImg,
      resultAccessUrl: tryonResult ? tryonResult.access_url : null,
      handlerName: tryonResult ? tryonResult.handler_name : null,
      accuracyScore: tryonResult ? tryonResult.accuracy_score : null,
      isLowConfidence: tryonResult ? tryonResult.is_low_confidence : false,
      timestamp: new Date().toISOString(),
    },
  });
}

function resetResultView() {
  resultsEmptyState.classList.remove('hidden');
  resultsContent.classList.add('hidden');
  resultsActions.classList.add('hidden');
  resultImg.src = '';
  if (lowConfidenceBanner) lowConfidenceBanner.classList.add('hidden');
  if (comparisonBadge) comparisonBadge.classList.remove('low-conf');
  if (resultCachedBadge) resultCachedBadge.classList.add('hidden');
  if (forceRefreshBtn) forceRefreshBtn.classList.add('hidden');
  setStoredState({ lastResult: null });
}

function downloadResult() {
  if (!resultImg.src) return;
  const link = document.createElement('a');
  link.href = resultImg.src;
  link.download = `tryon_result_${Date.now()}.png`;
  link.click();
}

// --- 5.5 Virtual Wardrobe (Category Browsable Gallery) & Comparison Staging ---

function normalizeCategoryGroup(cat) {
  if (!cat) return 'tops';
  const c = cat.toLowerCase();
  if (c.includes('pant') || c.includes('trouser') || c.includes('jean') || c.includes('short') || c.includes('skirt') || c.includes('lower') || c.includes('bottom')) return 'bottoms';
  if (c.includes('dress') || c.includes('gown') || c.includes('robe') || c.includes('frock')) return 'dresses';
  if (c.includes('shoe') || c.includes('sneaker') || c.includes('boot') || c.includes('footwear') || c.includes('heel') || c.includes('sandal')) return 'shoes';
  if (c.includes('neck') || c.includes('jewel') || c.includes('ring') || c.includes('earring') || c.includes('watch') || c.includes('bag') || c.includes('access')) return 'accessories';
  return 'tops';
}

async function loadClosetHistory(profileId) {
  if (!profileId) return;
  try {
    const res = await fetch(`${BACKEND_BASE}/api/tryon/profile/${profileId}`);
    if (!res.ok) return;
    const history = await res.json();
    state.closetItems = history || [];
    renderCloset();
  } catch (err) {
    console.warn('[AI Try-On] Error loading closet history:', err);
  }
}

async function deleteWardrobeItem(resultId) {
  if (!confirm('Remove this try-on fitting from your virtual wardrobe?')) return;
  try {
    const res = await fetch(`${BACKEND_BASE}/api/tryon/results/${resultId}`, { method: 'DELETE' });
    if (res.ok || res.status === 204) {
      state.closetItems = state.closetItems.filter((i) => i.id !== resultId);
      if (state.compareSlots.lookA && state.compareSlots.lookA.resultId === resultId) state.compareSlots.lookA = null;
      if (state.compareSlots.lookB && state.compareSlots.lookB.resultId === resultId) state.compareSlots.lookB = null;
      renderCompareDock();
      renderCloset();
    }
  } catch (err) {
    console.error('Error deleting wardrobe item:', err);
  }
}

function renderCloset() {
  if (!closetCountBadge || !closetEmptyState || !closetGrid) return;
  const items = state.closetItems || [];
  closetCountBadge.textContent = items.length;

  // Update Category Chip Counts
  const counts = {
    all: items.length,
    tops: items.filter((i) => normalizeCategoryGroup(i.category) === 'tops').length,
    bottoms: items.filter((i) => normalizeCategoryGroup(i.category) === 'bottoms').length,
    dresses: items.filter((i) => normalizeCategoryGroup(i.category) === 'dresses').length,
    shoes: items.filter((i) => normalizeCategoryGroup(i.category) === 'shoes').length,
    accessories: items.filter((i) => normalizeCategoryGroup(i.category) === 'accessories').length,
  };

  Object.entries(counts).forEach(([cat, num]) => {
    const el = document.getElementById(`chip-count-${cat}`);
    if (el) el.textContent = num;
  });

  const filteredItems = state.activeClosetCategory === 'all'
    ? items
    : items.filter((i) => normalizeCategoryGroup(i.category) === state.activeClosetCategory);

  if (items.length === 0) {
    if (closetEmptyTitle) closetEmptyTitle.textContent = 'Wardrobe is Empty';
    if (closetEmptySubtext) closetEmptySubtext.textContent = 'Past fittings for this profile are saved here and cached for instant preview.';
    closetEmptyState.classList.remove('hidden');
    closetGrid.classList.add('hidden');
    closetGrid.innerHTML = '';
    return;
  }

  if (filteredItems.length === 0) {
    const catLabel = state.activeClosetCategory.charAt(0).toUpperCase() + state.activeClosetCategory.slice(1);
    if (closetEmptyTitle) closetEmptyTitle.textContent = `No Saved ${catLabel}`;
    if (closetEmptySubtext) closetEmptySubtext.textContent = `You don't have any saved try-ons in the ${catLabel} collection yet.`;
    closetEmptyState.classList.remove('hidden');
    closetGrid.classList.add('hidden');
    closetGrid.innerHTML = '';
    return;
  }

  closetEmptyState.classList.add('hidden');
  closetGrid.classList.remove('hidden');
  closetGrid.innerHTML = '';

  filteredItems.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'closet-item';
    card.title = `Click to view fitting for ${item.product_title || item.category}`;

    const scorePct = Math.round((item.accuracy_score || 0.9) * 100);
    const isLow = item.is_low_confidence;
    const isStaged = isStagedForCompare(item.product_id || item.id);

    card.innerHTML = `
      <div class="closet-thumb-wrap">
        <img class="closet-thumb" src="${BACKEND_BASE}${item.access_url}" alt="${item.category}" loading="lazy">
        <span class="closet-item-badge ${isLow ? 'low' : ''}">${isLow ? '⚠️ Low' : `${scorePct}%`}</span>
        <div class="closet-item-actions">
          <button class="closet-action-icon-btn view-btn" title="View Result">👁️</button>
          <button class="closet-action-icon-btn compare-btn ${isStaged ? 'staged' : ''}" title="Stage for Compare">⚖️</button>
          <button class="closet-action-icon-btn delete-btn" title="Remove from Wardrobe">🗑️</button>
        </div>
      </div>
      <div class="closet-item-info">
        <span class="closet-item-title">${item.product_title || `${item.category.toUpperCase()} Fitting`}</span>
        <div class="closet-item-meta">
          <span>${item.category}</span>
          <span>${new Date(item.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
        </div>
      </div>
    `;

    const mockProd = {
      id: item.product_id || 9999,
      title: item.product_title || `${item.category.toUpperCase()} Fitting`,
      category: item.category,
      imageUrl: item.garment_image_url || `${BACKEND_BASE}${item.access_url}`,
    };

    const viewBtn = card.querySelector('.view-btn');
    if (viewBtn) {
      viewBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        showResultView(mockProd, item);
      });
    }

    const compBtn = card.querySelector('.compare-btn');
    if (compBtn) {
      compBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        stageItemForComparison({
          id: item.product_id || item.id,
          resultId: item.id,
          title: item.product_title || `${item.category} Fitting`,
          category: item.category,
          imageUrl: item.garment_image_url || `${BACKEND_BASE}${item.access_url}`,
          tryonUrl: `${BACKEND_BASE}${item.access_url}`,
          accuracy_score: item.accuracy_score,
        });
      });
    }

    const delBtn = card.querySelector('.delete-btn');
    if (delBtn) {
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteWardrobeItem(item.id);
      });
    }

    card.addEventListener('click', () => {
      showResultView(mockProd, item);
    });

    closetGrid.appendChild(card);
  });
}

// --- 5.6 Side-by-Side Comparison Methods ---

function isStagedForCompare(id) {
  if (!id) return false;
  return (state.compareSlots.lookA && state.compareSlots.lookA.id === id) ||
         (state.compareSlots.lookB && state.compareSlots.lookB.id === id);
}

function stageItemForComparison(item) {
  if (!item) return;

  if (state.compareSlots.lookA && state.compareSlots.lookA.id === item.id) {
    state.compareSlots.lookA = null;
  } else if (state.compareSlots.lookB && state.compareSlots.lookB.id === item.id) {
    state.compareSlots.lookB = null;
  } else if (!state.compareSlots.lookA) {
    state.compareSlots.lookA = item;
  } else if (!state.compareSlots.lookB) {
    state.compareSlots.lookB = item;
  } else {
    state.compareSlots.lookB = item;
  }

  renderCompareDock();
  renderProducts();
  renderCloset();
}

function clearCompareSlots() {
  state.compareSlots.lookA = null;
  state.compareSlots.lookB = null;
  renderCompareDock();
  renderProducts();
  renderCloset();
}

function renderCompareDock() {
  if (!compareDock) return;
  const count = (state.compareSlots.lookA ? 1 : 0) + (state.compareSlots.lookB ? 1 : 0);
  if (compareDockCount) compareDockCount.textContent = `${count}/2`;

  if (count === 0) {
    compareDock.classList.add('hidden');
    return;
  }

  compareDock.classList.remove('hidden');

  if (state.compareSlots.lookA) {
    slotACard.classList.add('filled');
    slotAName.textContent = state.compareSlots.lookA.title || 'Look A';
    slotARemove.classList.remove('hidden');
    slotARemove.onclick = (e) => {
      e.stopPropagation();
      state.compareSlots.lookA = null;
      renderCompareDock();
      renderProducts();
      renderCloset();
    };
  } else {
    slotACard.classList.remove('filled');
    slotAName.textContent = 'Select 1st garment';
    slotARemove.classList.add('hidden');
  }

  if (state.compareSlots.lookB) {
    slotBCard.classList.add('filled');
    slotBName.textContent = state.compareSlots.lookB.title || 'Look B';
    slotBRemove.classList.remove('hidden');
    slotBRemove.onclick = (e) => {
      e.stopPropagation();
      state.compareSlots.lookB = null;
      renderCompareDock();
      renderProducts();
      renderCloset();
    };
  } else {
    slotBCard.classList.remove('filled');
    slotBName.textContent = 'Select 2nd garment';
    slotBRemove.classList.add('hidden');
  }

  if (launchCompareBtn) {
    launchCompareBtn.disabled = count < 2;
    launchCompareBtn.textContent = count < 2
      ? `Select 1 more item to compare (${count}/2)`
      : `Compare Looks Side-by-Side (2)`;
  }
}

function openCompareModal() {
  if (!compareModal || !state.compareSlots.lookA || !state.compareSlots.lookB) return;
  compareModal.classList.remove('hidden');

  const itemA = state.compareSlots.lookA;
  const itemB = state.compareSlots.lookB;

  compTitleA.textContent = itemA.title || 'Garment A';
  compCatA.textContent = itemA.category || 'Apparel';
  const imgUrlA = itemA.tryonUrl || (itemA.access_url ? `${BACKEND_BASE}${itemA.access_url}` : null);
  if (imgUrlA) {
    compImgA.src = imgUrlA;
    compScoreA.textContent = itemA.accuracy_score ? `${Math.round(itemA.accuracy_score * 100)}% Match` : '97% Match';
    compScoreA.classList.remove('hidden');
    compRunA.classList.add('hidden');
  } else {
    compImgA.src = itemA.imageUrl || state.activeModelPhotoUrl || '';
    compScoreA.classList.add('hidden');
    compRunA.classList.remove('hidden');
    compRunA.onclick = () => runComparisonSlotTryOn('A');
  }

  compTitleB.textContent = itemB.title || 'Garment B';
  compCatB.textContent = itemB.category || 'Apparel';
  const imgUrlB = itemB.tryonUrl || (itemB.access_url ? `${BACKEND_BASE}${itemB.access_url}` : null);
  if (imgUrlB) {
    compImgB.src = imgUrlB;
    compScoreB.textContent = itemB.accuracy_score ? `${Math.round(itemB.accuracy_score * 100)}% Match` : '95% Match';
    compScoreB.classList.remove('hidden');
    compRunB.classList.add('hidden');
  } else {
    compImgB.src = itemB.imageUrl || state.activeModelPhotoUrl || '';
    compScoreB.classList.add('hidden');
    compRunB.classList.remove('hidden');
    compRunB.onclick = () => runComparisonSlotTryOn('B');
  }

  sliderImgBg.src = compImgB.src;
  sliderImgFg.src = compImgA.src;

  setCompareMode('dual');
}

function closeCompareModal() {
  if (compareModal) compareModal.classList.add('hidden');
}

function setCompareMode(mode) {
  state.compareMode = mode;
  if (mode === 'slider') {
    if (toggleSliderMode) toggleSliderMode.classList.add('active');
    if (toggleDualMode) toggleDualMode.classList.remove('active');
    if (compareDualView) compareDualView.classList.add('hidden');
    if (compareSliderView) compareSliderView.classList.remove('hidden');
    if (splitSliderContainer) splitSliderContainer.style.setProperty('--split-pos', '50%');
    if (sliderDividerLine) sliderDividerLine.style.left = '50%';
  } else {
    if (toggleDualMode) toggleDualMode.classList.add('active');
    if (toggleSliderMode) toggleSliderMode.classList.remove('active');
    if (compareDualView) compareDualView.classList.remove('hidden');
    if (compareSliderView) compareSliderView.classList.add('hidden');
  }
}

async function runComparisonSlotTryOn(slotKey) {
  const item = slotKey === 'A' ? state.compareSlots.lookA : state.compareSlots.lookB;
  const loadingEl = slotKey === 'A' ? compLoadingA : compLoadingB;
  const imgEl = slotKey === 'A' ? compImgA : compImgB;
  const scoreEl = slotKey === 'A' ? compScoreA : compScoreB;
  const btnEl = slotKey === 'A' ? compRunA : compRunB;

  if (!item || !state.activeProfileId) return;

  loadingEl.classList.remove('hidden');
  btnEl.classList.add('hidden');

  try {
    const payload = {
      profile_id: state.activeProfileId,
      garment_image_url: item.imageUrl,
      product_id: typeof item.id === 'number' ? item.id : null,
      category: item.category || 'auto',
      force_refresh: false,
    };

    const res = await fetch(`${BACKEND_BASE}/api/tryon`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    item.tryonUrl = `${BACKEND_BASE}${data.access_url}`;
    item.accuracy_score = data.accuracy_score;
    imgEl.src = item.tryonUrl;
    scoreEl.textContent = `${Math.round((data.accuracy_score || 0.95) * 100)}% Match`;
    scoreEl.classList.remove('hidden');

    if (slotKey === 'A') sliderImgFg.src = item.tryonUrl;
    else sliderImgBg.src = item.tryonUrl;

    await loadClosetHistory(state.activeProfileId);
  } catch (err) {
    alert(`Try-on failed: ${err.message}`);
    btnEl.classList.remove('hidden');
  } finally {
    loadingEl.classList.add('hidden');
  }
}

function initSplitSlider() {
  if (!splitSliderContainer || !sliderFgContainer || !sliderDividerLine) return;

  let isDragging = false;

  const updateSliderPos = (clientX) => {
    const rect = splitSliderContainer.getBoundingClientRect();
    if (!rect.width) return;
    let x = clientX - rect.left;
    if (x < 0) x = 0;
    if (x > rect.width) x = rect.width;
    const pct = Math.max(0, Math.min(100, (x / rect.width) * 100));

    splitSliderContainer.style.setProperty('--split-pos', `${pct}%`);
    sliderDividerLine.style.left = `${pct}%`;
  };

  splitSliderContainer.addEventListener('mousedown', (e) => {
    isDragging = true;
    updateSliderPos(e.clientX);
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    updateSliderPos(e.clientX);
  });

  window.addEventListener('mouseup', () => {
    isDragging = false;
  });

  splitSliderContainer.addEventListener('touchstart', (e) => {
    if (e.touches && e.touches[0]) {
      isDragging = true;
      updateSliderPos(e.touches[0].clientX);
    }
  }, { passive: true });

  window.addEventListener('touchmove', (e) => {
    if (!isDragging || !e.touches || !e.touches[0]) return;
    updateSliderPos(e.touches[0].clientX);
  }, { passive: true });

  window.addEventListener('touchend', () => {
    isDragging = false;
  });
}

// --- 6. Event Listeners ---

spProfileSelect.addEventListener('change', async (e) => {
  const profileId = Number(e.target.value);
  if (profileId) {
    state.activeProfileId = profileId;
    setStoredState({ activeProfileId: profileId });
    await loadActiveProfileData(profileId);
  }
});

const openStudio = () => chrome.tabs.create({ url: chrome.runtime.getURL('profile/profile.html') });
spManageProfilesBtn.addEventListener('click', openStudio);
spGoUploadBtn.addEventListener('click', openStudio);

// Angle selection chips
angleChips.querySelectorAll('.angle-chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    angleChips.querySelectorAll('.angle-chip').forEach((c) => c.classList.remove('active'));
    chip.classList.add('active');
    state.activeAngle = chip.dataset.angle;
    setStoredState({ activeAngle: state.activeAngle });
    renderModelPhoto();
    updateTryOnButtonState();
  });
});

async function scanActivePageProducts() {
  productCountBadge.textContent = '...';
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      renderProducts();
      return;
    }

    // Don't scan internal chrome:// pages
    if (tab.url && (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://'))) {
      renderProducts();
      return;
    }

    chrome.tabs.sendMessage(tab.id, { type: 'DETECT_PRODUCTS' }, (response) => {
      if (chrome.runtime.lastError) {
        // Content script might not be injected yet or tab restricted
        console.log('[AI Try-On] Content script message error:', chrome.runtime.lastError.message);
        renderProducts();
        return;
      }

      if (response && response.success && Array.isArray(response.products) && response.products.length > 0) {
        state.products = response.products;
        setStoredState({ storedProducts: state.products });
        renderProducts();
      } else {
        renderProducts();
      }
    });
  } catch (err) {
    console.warn('[AI Try-On] Error querying active tab:', err);
    renderProducts();
  }
}

scanPageBtn.addEventListener('click', scanActivePageProducts);
addDemoProductBtn.addEventListener('click', addDemoGarments);
tryonBtn.addEventListener('click', () => handleTryOnExecution(false));
resetResultBtn.addEventListener('click', resetResultView);
downloadResultBtn.addEventListener('click', downloadResult);
if (forceRefreshBtn) {
  forceRefreshBtn.addEventListener('click', () => handleTryOnExecution(true));
}
if (refreshClosetBtn) {
  refreshClosetBtn.addEventListener('click', () => {
    if (state.activeProfileId) loadClosetHistory(state.activeProfileId);
  });
}
if (errorDismissBtn) {
  errorDismissBtn.addEventListener('click', hideErrorNotice);
}

// Bonus Feature 1: Wardrobe Category Filter Chips
if (closetFiltersBar) {
  closetFiltersBar.querySelectorAll('.closet-filter-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      closetFiltersBar.querySelectorAll('.closet-filter-chip').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      state.activeClosetCategory = chip.dataset.cat;
      renderCloset();
    });
  });
}

// Bonus Feature 2: Quick Profile Creator Listeners
if (spQuickAddProfileBtn) {
  spQuickAddProfileBtn.addEventListener('click', () => toggleQuickProfileCreator());
}
if (quickProfileCancelBtn) {
  quickProfileCancelBtn.addEventListener('click', () => toggleQuickProfileCreator(false));
}
if (quickProfileSaveBtn) {
  quickProfileSaveBtn.addEventListener('click', handleQuickCreateProfile);
}
if (quickProfileNameInput) {
  quickProfileNameInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleQuickCreateProfile();
    if (e.key === 'Escape') toggleQuickProfileCreator(false);
  });
}

// Bonus Feature 4: Side-by-Side Compare Listeners
if (compareClearBtn) {
  compareClearBtn.addEventListener('click', clearCompareSlots);
}
if (launchCompareBtn) {
  launchCompareBtn.addEventListener('click', openCompareModal);
}
if (closeCompareModalBtn) {
  closeCompareModalBtn.addEventListener('click', closeCompareModal);
}
if (toggleDualMode) {
  toggleDualMode.addEventListener('click', () => setCompareMode('dual'));
}
if (toggleSliderMode) {
  toggleSliderMode.addEventListener('click', () => setCompareMode('slider'));
}

// Close compare modal when clicking outside card
if (compareModal) {
  compareModal.addEventListener('click', (e) => {
    if (e.target === compareModal) closeCompareModal();
  });
}

// --- 7. Initialization ---

async function init() {
  await checkBackendHealth();
  initSplitSlider();

  // Load stored state
  const stored = await getStoredState();
  if (stored.activeAngle) {
    state.activeAngle = stored.activeAngle;
    angleChips.querySelectorAll('.angle-chip').forEach((chip) => {
      chip.classList.toggle('active', chip.dataset.angle === state.activeAngle);
    });
  }

  if (stored.storedProducts && Array.isArray(stored.storedProducts)) {
    state.products = stored.storedProducts;
  }

  if (stored.selectedProductId) {
    state.selectedProductId = stored.selectedProductId;
  }

  await loadProfiles();
  renderProducts();

  // Try auto-scanning the active page
  setTimeout(scanActivePageProducts, 300);

  // Listen to cross-extension selection changes from popup
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local') {
      if (changes.activeTryOnTarget?.newValue) {
        const target = changes.activeTryOnTarget.newValue;
        if (target.productId) {
          state.selectedProductId = target.productId;
          if (target.selectedImageUrl) {
            state.variantSelections[target.productId] = target.selectedImageUrl;
          }
          renderProducts();
        }
      }
    }
  });

  setInterval(checkBackendHealth, 15000);
}

document.addEventListener('DOMContentLoaded', init);
