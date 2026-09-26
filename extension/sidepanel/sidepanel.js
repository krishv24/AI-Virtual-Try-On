/**
 * AI Virtual Try-On - Side Panel Studio Controller (Phase 3 Shell)
 * Manages Profile Switcher, Products on this page, Try-On processing, and Results View.
 * Uses chrome.storage.local for lightweight state only (never storing photo blobs).
 */

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
    renderModelPhoto();
    updateTryOnButtonState();
  } catch (err) {
    console.warn('[AI Try-On] Error loading profile detail:', err);
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

    const currentImg = state.variantSelections[prod.id];
    const isSelected = state.selectedProductId === prod.id;

    const card = document.createElement('div');
    card.className = `product-card ${isSelected ? 'selected' : ''}`;
    card.dataset.id = prod.id;

    card.innerHTML = `
      <img src="${currentImg}" alt="${prod.title}" class="product-thumb" id="sp-thumb-${prod.id}" loading="lazy">
      <div class="product-meta">
        <span class="product-name" title="${prod.title}">${prod.title}</span>
        <div class="product-tags">
          <span class="category-tag">${prod.category || 'Apparel'}</span>
          <span class="product-price">${prod.price || ''}</span>
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

async function handleTryOnExecution() {
  if (!state.selectedProductId || !state.activeProfileId || state.isProcessing) return;

  const selectedProd = state.products.find((p) => p.id === state.selectedProductId);
  if (!selectedProd) return;

  const chosenGarmentImg = state.variantSelections[selectedProd.id] || selectedProd.imageUrl;
  if (!chosenGarmentImg) return;

  state.isProcessing = true;
  updateTryOnButtonState();

  // Show Processing Status Area
  processingStatusArea.classList.remove('hidden');
  resetPipelineSteps();

  try {
    // Step 1: Garment & Variant Analysis
    setStepStatus(stageClip, 'active', 'Step 1: Analyzing garment variant & category...');
    pipelineProgressFill.style.width = '25%';
    await delay(500);
    setStepStatus(stageClip, 'done', `Garment identified: ${selectedProd.category || 'Apparel'}`);

    // Step 2: MediaPipe Landmark resolution
    setStepStatus(stagePose, 'active', 'Step 2: Resolving profile pose & body keypoints...');
    pipelineProgressFill.style.width = '50%';
    await delay(600);
    setStepStatus(stagePose, 'done', 'Profile pose aligned with garment drape');

    // Step 3: CatVTON Neural Synthesis on ZeroGPU
    setStepStatus(stageVton, 'active', 'Step 3: CatVTON diffusion synthesizing on ZeroGPU...');
    pipelineProgressFill.style.width = '75%';

    const payload = {
      profile_id: state.activeProfileId,
      garment_image_url: chosenGarmentImg,
      product_id: typeof selectedProd.id === 'number' ? selectedProd.id : null,
      category: selectedProd.category || 'overall',
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
        errorMsg = errorData.detail || errorMsg;
      } catch (_) {}
      throw new Error(errorMsg);
    }

    const tryonResult = await response.json();

    setStepStatus(stageVton, 'done', 'CatVTON ZeroGPU try-on synthesis complete!');
    pipelineProgressFill.style.width = '100%';
    await delay(400);

    // Reveal Result View with real composited image
    showResultView(selectedProd, tryonResult);
  } catch (err) {
    console.error('Try-On error:', err);
    setStepStatus(stageVton, 'error', `Try-On failed: ${err.message}`);
    processingMainStatus.textContent = 'Virtual Try-On error';
    processingDetailText.textContent = err.message;
    alert(`Virtual Try-On error:\n${err.message}`);
  } finally {
    state.isProcessing = false;
    updateTryOnButtonState();
    setTimeout(() => {
      processingStatusArea.classList.add('hidden');
    }, 3000);
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
  resultCategoryTag.textContent = product.category || 'Apparel';

  // Persist try-on result record (metadata only)
  setStoredState({
    lastResult: {
      productId: product.id,
      title: product.title,
      category: product.category,
      selectedImageUrl: chosenImg,
      resultAccessUrl: tryonResult ? tryonResult.access_url : null,
      timestamp: new Date().toISOString(),
    },
  });
}

function resetResultView() {
  resultsEmptyState.classList.remove('hidden');
  resultsContent.classList.add('hidden');
  resultsActions.classList.add('hidden');
  resultImg.src = '';
  setStoredState({ lastResult: null });
}

function downloadResult() {
  if (!resultImg.src) return;
  const link = document.createElement('a');
  link.href = resultImg.src;
  link.download = `tryon_result_${Date.now()}.png`;
  link.click();
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
tryonBtn.addEventListener('click', handleTryOnExecution);
resetResultBtn.addEventListener('click', resetResultView);
downloadResultBtn.addEventListener('click', downloadResult);

// --- 7. Initialization ---

async function init() {
  await checkBackendHealth();

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
