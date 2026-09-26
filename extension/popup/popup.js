/**
 * AI Virtual Try-On - Popup Controller (Phase 5: Product Selection & Variant Handling)
 * Manages selectable product list, variant angle picking, auto-selecting clearest front shot,
 * and saving the chosen product + image URL to chrome.storage.local.
 */

/* ── Theme Toggle (dark default) ── */
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

const BACKEND_HEALTH_URL = 'http://localhost:8000/health';

// Sample demo garments for immediate interactive testing
const DEMO_GARMENTS = [
  {
    id: 'prod_hoodie_01',
    title: 'Oversized Streetwear Fleece Hoodie',
    category: 'Upper Body',
    price: '$58.00',
    imageUrl: 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=500&auto=format&fit=crop&q=80',
    imageUrls: [
      'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=500&auto=format&fit=crop&q=80', // Front
      'https://images.unsplash.com/photo-1509967419530-da38b4704bc6?w=500&auto=format&fit=crop&q=80', // Flat layout
      'https://images.unsplash.com/photo-1578587018452-892bacefd3f2?w=500&auto=format&fit=crop&q=80'  // Lifestyle
    ],
    sourceUrl: 'https://example.com/demo-hoodie',
  },
  {
    id: 'prod_jacket_02',
    title: 'Vintage Denim Trucker Jacket',
    category: 'Upper Body',
    price: '$79.99',
    imageUrl: 'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=500&auto=format&fit=crop&q=80',
    imageUrls: [
      'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=500&auto=format&fit=crop&q=80',
      'https://images.unsplash.com/photo-1516257984-b1b4d707412e?w=500&auto=format&fit=crop&q=80'
    ],
    sourceUrl: 'https://example.com/demo-jacket',
  },
  {
    id: 'prod_pants_03',
    title: 'Tailored Wide-Leg Chino Trousers',
    category: 'Lower Body',
    price: '$64.50',
    imageUrl: 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=500&auto=format&fit=crop&q=80',
    imageUrls: [
      'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=500&auto=format&fit=crop&q=80',
      'https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=500&auto=format&fit=crop&q=80'
    ],
    sourceUrl: 'https://example.com/demo-pants',
  }
];

// App State
let state = {
  profiles: [],
  activeProfileId: null,
  products: [],
  selectedProductId: null,
  activeTarget: null, // { productId, title, price, category, selectedImageUrl, sourceUrl }
  variantSelections: {}, // productId -> chosenImageUrl
};

// DOM References
const statusBadge = document.getElementById('backend-status-badge');
const statusText = document.getElementById('backend-status-text');
const serverAlert = document.getElementById('server-alert');
const popupProfileSelect = document.getElementById('popup-profile-select');
const openProfileBtn = document.getElementById('open-profile-btn');
const openSidepanelBtn = document.getElementById('open-sidepanel-btn');
const recheckBtn = document.getElementById('recheck-btn');

const popupProductCount = document.getElementById('popup-product-count');
const popupRescanBtn = document.getElementById('popup-rescan-btn');
const popupAddDemoBtn = document.getElementById('popup-add-demo-btn');
const popupEmptyProducts = document.getElementById('popup-empty-products');
const popupLoadDemoBtn = document.getElementById('popup-load-demo-btn');
const popupProductList = document.getElementById('popup-product-list');

const activeTargetCard = document.getElementById('active-target-card');
const targetTitle = document.getElementById('target-title');
const targetVariantBadge = document.getElementById('target-variant-badge');
const targetCategoryText = document.getElementById('target-category-text');

// =========================================================================
// 1. Clearest Front-Facing Shot Heuristics
// =========================================================================

/**
 * Score an image URL based on keywords and naming patterns to prioritize
 * front-facing, clean-background product shots over lifestyle/clutter.
 */
function scoreProductImage(url) {
  if (!url) return -100;
  const lower = url.toLowerCase();
  let score = 0;

  // Positive signals: front / main / hero / clean flat
  if (lower.includes('front')) score += 50;
  if (lower.includes('main') || lower.includes('primary') || lower.includes('hero')) score += 40;
  if (lower.includes('flat') || lower.includes('ghost') || lower.includes('packshot')) score += 45;
  if (lower.includes('white') || lower.includes('clean') || lower.includes('isolated')) score += 25;

  // Negative signals: back / side / detail / lifestyle / clutter
  if (lower.includes('back') || lower.includes('rear') || lower.includes('behind')) score -= 45;
  if (lower.includes('side') || lower.includes('profile')) score -= 25;
  if (lower.includes('detail') || lower.includes('zoom') || lower.includes('close_up')) score -= 35;
  if (lower.includes('swatch') || lower.includes('thumb')) score -= 40;
  if (lower.includes('lifestyle') || lower.includes('lookbook') || lower.includes('editorial') || lower.includes('street')) score -= 50;
  if (lower.includes('context') || lower.includes('scene') || lower.includes('env')) score -= 40;

  // High resolution / full size bonus
  if (lower.includes('2000') || lower.includes('1500') || lower.includes('1000') || lower.includes('hires') || lower.includes('large')) {
    score += 15;
  }

  return score;
}

/**
 * Auto-select the clearest front-facing product shot
 */
function selectBestFrontShot(imageUrls) {
  if (!imageUrls || imageUrls.length === 0) return null;
  if (imageUrls.length === 1) return imageUrls[0];

  let bestUrl = imageUrls[0];
  let highestScore = scoreProductImage(bestUrl);

  for (let i = 1; i < imageUrls.length; i++) {
    const s = scoreProductImage(imageUrls[i]);
    if (s > highestScore) {
      highestScore = s;
      bestUrl = imageUrls[i];
    }
  }

  return bestUrl;
}

// =========================================================================
// 2. Backend Health & Profile Loading
// =========================================================================

async function checkBackendHealth() {
  setStatus('checking', 'Checking API...');
  serverAlert.classList.add('hidden');

  try {
    const res = await fetch(BACKEND_HEALTH_URL, { signal: AbortSignal.timeout(2500) });
    if (res.ok) {
      setStatus('online', 'Backend Online');
      return true;
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (error) {
    setStatus('offline', 'Backend Offline');
    serverAlert.classList.remove('hidden');
    return false;
  }
}

function setStatus(state, label) {
  statusBadge.className = `status-badge ${state}`;
  statusText.textContent = label;
}

async function loadProfiles() {
  try {
    const res = await fetch('http://localhost:8000/api/profiles');
    if (!res.ok) return;
    state.profiles = await res.json();

    popupProfileSelect.innerHTML = '';
    if (state.profiles.length === 0) {
      popupProfileSelect.innerHTML = '<option value="" disabled selected>No profiles (Click ⚙️)</option>';
      return;
    }

    state.profiles.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.photo_count || 0}/5)`;
      popupProfileSelect.appendChild(opt);
    });

    chrome.storage.local.get(['activeProfileId'], (result) => {
      let targetId = result?.activeProfileId;
      if (!targetId || !state.profiles.find((p) => p.id === targetId)) {
        targetId = state.profiles[0].id;
      }
      state.activeProfileId = targetId;
      popupProfileSelect.value = targetId;
      chrome.storage.local.set({ activeProfileId: targetId });
    });
  } catch (e) {
    console.warn('[AI Try-On] Error loading popup profiles:', e);
  }
}

// =========================================================================
// 3. Product Selection & Variant Handling (Phase 5)
// =========================================================================

function renderProductList() {
  popupProductCount.textContent = state.products.length;

  if (state.products.length === 0) {
    popupEmptyProducts.classList.remove('hidden');
    popupProductList.classList.add('hidden');
    popupProductList.innerHTML = '';
    activeTargetCard.classList.add('hidden');
    return;
  }

  popupEmptyProducts.classList.add('hidden');
  popupProductList.classList.remove('hidden');
  popupProductList.innerHTML = '';

  state.products.forEach((prod) => {
    // Get all image candidates for this product
    const images = Array.isArray(prod.imageUrls) && prod.imageUrls.length > 0
      ? prod.imageUrls
      : [prod.imageUrl].filter(Boolean);

    const autoFrontShot = selectBestFrontShot(images);

    // If user previously selected a variant for this product, use it; otherwise auto-select clearest front shot
    if (!state.variantSelections[prod.id]) {
      state.variantSelections[prod.id] = autoFrontShot || images[0];
    }

    const currentChosenImg = state.variantSelections[prod.id];
    const isSelected = state.selectedProductId === prod.id;

    // Card Container
    const card = document.createElement('div');
    card.className = `product-item-card ${isSelected ? 'selected' : ''}`;
    card.dataset.id = prod.id;

    // Card Header Row (Thumbnail, Title, Price, Selection Radio)
    const cardRow = document.createElement('div');
    cardRow.className = 'card-main-row';

    cardRow.innerHTML = `
      <img src="${currentChosenImg}" alt="${prod.title}" class="product-item-thumb" id="thumb-${prod.id}">
      <div class="product-item-info">
        <span class="product-item-title" title="${prod.title}">${prod.title}</span>
        <div class="product-item-sub">
          <span class="sub-category">${prod.category || 'Apparel'}</span>
          <span class="sub-price">${prod.price || ''}</span>
        </div>
      </div>
      <div class="select-indicator">✓</div>
    `;

    cardRow.addEventListener('click', () => {
      selectTargetProduct(prod, currentChosenImg, autoFrontShot);
    });

    card.appendChild(cardRow);

    // Multiple Images Variant Selector Row
    if (images.length > 1) {
      const variantRow = document.createElement('div');
      variantRow.className = 'variant-picker-row';

      const label = document.createElement('span');
      label.className = 'variant-picker-label';
      label.textContent = `Choose Angle / Variant (${images.length} views):`;
      variantRow.appendChild(label);

      const strip = document.createElement('div');
      strip.className = 'variant-thumbs-strip';

      images.forEach((imgUrl, idx) => {
        const thumb = document.createElement('img');
        thumb.src = imgUrl;
        thumb.className = `variant-strip-thumb ${imgUrl === currentChosenImg ? 'active' : ''}`;
        thumb.title = imgUrl === autoFrontShot ? '⭐ Clearest Front Shot (Auto-detected)' : `Angle #${idx + 1}`;

        thumb.addEventListener('click', (e) => {
          e.stopPropagation(); // Avoid parent toggle

          state.variantSelections[prod.id] = imgUrl;

          // Update main card thumb
          const mainThumb = document.getElementById(`thumb-${prod.id}`);
          if (mainThumb) mainThumb.src = imgUrl;

          // Update strip active border
          strip.querySelectorAll('.variant-strip-thumb').forEach((t) => t.classList.remove('active'));
          thumb.classList.add('active');

          // Select this product & chosen image as target
          selectTargetProduct(prod, imgUrl, autoFrontShot);
        });

        strip.appendChild(thumb);
      });

      variantRow.appendChild(strip);
      card.appendChild(variantRow);
    }

    popupProductList.appendChild(card);
  });

  updateActiveTargetBanner();
}

/**
 * Select product + specific image variant and store as active try-on target
 */
function selectTargetProduct(product, chosenImageUrl, autoFrontShot) {
  state.selectedProductId = product.id;
  const isAutoFront = chosenImageUrl === (autoFrontShot || selectBestFrontShot(product.imageUrls));

  state.activeTarget = {
    productId: product.id,
    title: product.title,
    price: product.price || '',
    category: product.category || 'Apparel',
    selectedImageUrl: chosenImageUrl,
    sourceUrl: product.sourceUrl || window.location.href,
    isAutoFront,
    updatedAt: new Date().toISOString(),
  };

  // Persist to chrome.storage.local (lightweight metadata, zero blobs)
  chrome.storage.local.set({
    selectedProductId: product.id,
    activeTryOnTarget: state.activeTarget,
  });

  // Re-render UI highlights
  document.querySelectorAll('.product-item-card').forEach((card) => {
    card.classList.toggle('selected', card.dataset.id === product.id);
  });

  updateActiveTargetBanner();
}

function updateActiveTargetBanner() {
  if (state.activeTarget && state.selectedProductId) {
    activeTargetCard.classList.remove('hidden');
    targetTitle.textContent = state.activeTarget.title;
    targetCategoryText.textContent = state.activeTarget.category;

    if (state.activeTarget.isAutoFront) {
      targetVariantBadge.textContent = '✨ Clearest Front Shot (Auto-Selected)';
      targetVariantBadge.className = 'badge-front';
    } else {
      targetVariantBadge.textContent = '📷 Custom Selected View';
      targetVariantBadge.className = 'badge-front custom';
    }
  } else {
    activeTargetCard.classList.add('hidden');
  }
}

// =========================================================================
// 4. Content Script Scanning & Actions
// =========================================================================

async function scanActivePageProducts() {
  popupProductCount.textContent = '...';
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id || tab.url?.startsWith('chrome://')) {
      renderProductList();
      return;
    }

    chrome.tabs.sendMessage(tab.id, { type: 'DETECT_PRODUCTS' }, (response) => {
      if (chrome.runtime.lastError) {
        console.log('[AI Try-On] Content script unavailable on tab:', chrome.runtime.lastError.message);
        renderProductList();
        return;
      }

      if (response && response.success && Array.isArray(response.products)) {
        state.products = response.products;
        chrome.storage.local.set({ storedProducts: state.products });

        // Auto-select first product if none selected yet
        if (!state.selectedProductId && state.products.length > 0) {
          const first = state.products[0];
          const bestImg = selectBestFrontShot(first.imageUrls || [first.imageUrl]);
          selectTargetProduct(first, bestImg, bestImg);
        }

        renderProductList();
      }
    });
  } catch (err) {
    console.warn('[AI Try-On] Error scanning tab:', err);
    renderProductList();
  }
}

function addDemoGarments() {
  const existingIds = new Set(state.products.map((p) => p.id));
  const newItems = DEMO_GARMENTS.filter((g) => !existingIds.has(g.id));

  state.products = newItems.length > 0 ? [...newItems, ...state.products] : [...DEMO_GARMENTS];
  chrome.storage.local.set({ storedProducts: state.products });

  if (state.products.length > 0 && !state.selectedProductId) {
    const first = state.products[0];
    const bestImg = selectBestFrontShot(first.imageUrls);
    selectTargetProduct(first, bestImg, bestImg);
  }

  renderProductList();
}

async function openSidePanel() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && chrome.sidePanel && chrome.sidePanel.open) {
      await chrome.sidePanel.open({ tabId: tab.id });
      window.close();
    } else {
      chrome.runtime.sendMessage({ type: 'OPEN_SIDE_PANEL' }, () => window.close());
    }
  } catch (err) {
    console.error('[AI Try-On] Error opening side panel:', err);
  }
}

// =========================================================================
// 5. Event Listeners & Init
// =========================================================================

popupProfileSelect.addEventListener('change', (e) => {
  const id = Number(e.target.value);
  if (id) {
    state.activeProfileId = id;
    chrome.storage.local.set({ activeProfileId: id });
  }
});

openProfileBtn.addEventListener('click', () => {
  chrome.tabs.create({ url: chrome.runtime.getURL('profile/profile.html') });
});

openSidepanelBtn.addEventListener('click', openSidePanel);

popupRescanBtn.addEventListener('click', scanActivePageProducts);
popupAddDemoBtn.addEventListener('click', addDemoGarments);
popupLoadDemoBtn.addEventListener('click', addDemoGarments);

recheckBtn.addEventListener('click', () => {
  checkBackendHealth();
  loadProfiles();
  scanActivePageProducts();
});

async function init() {
  await checkBackendHealth();
  await loadProfiles();

  // Restore stored state
  chrome.storage.local.get(['storedProducts', 'selectedProductId', 'activeTryOnTarget'], (res) => {
    if (res?.storedProducts && Array.isArray(res.storedProducts)) {
      state.products = res.storedProducts;
    }
    if (res?.selectedProductId) {
      state.selectedProductId = res.selectedProductId;
    }
    if (res?.activeTryOnTarget) {
      state.activeTarget = res.activeTryOnTarget;
      if (res.activeTryOnTarget.productId && res.activeTryOnTarget.selectedImageUrl) {
        state.variantSelections[res.activeTryOnTarget.productId] = res.activeTryOnTarget.selectedImageUrl;
      }
    }

    renderProductList();
    scanActivePageProducts();
  });
}

document.addEventListener('DOMContentLoaded', init);
