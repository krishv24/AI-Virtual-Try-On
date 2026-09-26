/**
 * Universal E-Commerce Product Detector (Content Script - Phase 4)
 * Extracts candidate products in priority order:
 *  1. Site-Specific Heuristics Plugin Registry (extensible)
 *  2. Schema.org Product JSON-LD structured data
 *  3. Open Graph & Twitter meta tags
 *  4. Visual Fallback Heuristic (Largest image near "Add to Cart"/"Buy" CTA)
 *
 * Captures: title, price, category guess, primary imageUrl, and all associated imageUrls.
 */

(function () {
  'use strict';

  // --- Category Classification Heuristic ---
  const CATEGORY_KEYWORDS = {
    'Upper Body': [
      'hoodie', 'sweatshirt', 'shirt', 't-shirt', 'tee', 'blouse', 'sweater',
      'jumper', 'jacket', 'coat', 'cardigan', 'tank', 'top', 'blazer', 'polo',
      'vest', 'pullover', 'turtleneck', 'windbreaker', 'anorak'
    ],
    'Lower Body': [
      'pants', 'jeans', 'trousers', 'shorts', 'skirt', 'joggers', 'leggings',
      'sweatpants', 'chinos', 'cargo', 'bottoms', 'slacks', 'denim'
    ],
    'Full Body / Dress': [
      'dress', 'gown', 'jumpsuit', 'romper', 'overall', 'suit', 'robe', 'kimono',
      'maxi dress', 'midi dress', 'mini dress', 'bodysuit'
    ],
    'Footwear': [
      'shoes', 'sneakers', 'sneaker', 'boots', 'boot', 'loafers', 'sandals',
      'heels', 'trainers', 'slippers', 'slides', 'clogs', 'flats'
    ]
  };

  function guessCategory(text) {
    if (!text) return 'Apparel';
    const lower = text.toLowerCase();
    for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
      for (const kw of keywords) {
        // Regex word boundary matching
        const regex = new RegExp(`\\b${kw}\\b`, 'i');
        if (regex.test(lower)) {
          return category;
        }
      }
    }
    return 'Apparel';
  }

  // Price Regex Pattern
  const PRICE_REGEX = /(?:[\$\€\£\¥\₹]|USD|EUR|GBP|INR)\s*\d+(?:[.,]\d{2})?|\b\d+(?:[.,]\d{2})?\s*(?:USD|EUR|GBP|INR)\b/i;

  function cleanPrice(priceStr, currency) {
    if (!priceStr) return null;
    const str = String(priceStr).trim();
    if (PRICE_REGEX.test(str)) {
      return str.match(PRICE_REGEX)[0];
    }
    if (currency) {
      return `${currency} ${str}`;
    }
    return `$${str}`;
  }

  function resolveUrl(url) {
    if (!url) return null;
    try {
      return new URL(url, window.location.href).href;
    } catch (e) {
      return url;
    }
  }

  // =========================================================================
  // 1. Site-Specific Heuristics Registry (Extensible Plugin Architecture)
  // =========================================================================
  const siteHeuristicsRegistry = [];

  /**
   * Register a new site-specific heuristic without touching core logic.
   * @param {RegExp|Function} matcher - Regex to test against window.location.hostname/href, or matcher function
   * @param {Function} extractor - Function receiving (document, url) and returning array of products
   */
  function registerSiteHeuristic(matcher, extractor) {
    siteHeuristicsRegistry.push({ matcher, extractor });
  }

  // Example built-in site heuristic: Amazon
  registerSiteHeuristic(/amazon\.[a-z.]+/i, (doc) => {
    const titleEl = doc.getElementById('productTitle');
    const imgEl = doc.getElementById('landingImage') || doc.querySelector('#imgTagWrapperId img');
    const priceEl = doc.querySelector('.a-price .a-offscreen') || doc.getElementById('priceblock_ourprice');

    if (titleEl && imgEl) {
      const title = titleEl.textContent.trim();
      const imageUrl = imgEl.getAttribute('data-old-hires') || imgEl.src;
      const price = priceEl ? priceEl.textContent.trim() : null;

      // Collect variant thumbnails if available
      const altImages = Array.from(doc.querySelectorAll('#altImages img'))
        .map(i => i.src.replace(/\._[A-Z0-9_,]+_\./, '.'))
        .filter(u => u && !u.includes('play-button'));

      return [{
        id: 'amazon_' + Date.now(),
        title,
        price,
        category: guessCategory(title),
        imageUrl: resolveUrl(imageUrl),
        imageUrls: altImages.length > 0 ? altImages : [resolveUrl(imageUrl)],
        sourceUrl: window.location.href,
        method: 'site_heuristic (Amazon)'
      }];
    }
    return null;
  });

  // Example built-in site heuristic: Shopify generic stores
  registerSiteHeuristic((url) => document.querySelector('meta[content*="Shopify"]') !== null, (doc) => {
    const jsonScript = doc.querySelector('script[data-product-json]');
    if (jsonScript) {
      try {
        const data = JSON.parse(jsonScript.textContent);
        if (data && data.title) {
          const images = (data.images || []).map(resolveUrl);
          const price = data.price ? `$${(data.price / 100).toFixed(2)}` : null;
          return [{
            id: 'shopify_' + (data.id || Date.now()),
            title: data.title,
            price,
            category: guessCategory(data.title + ' ' + (data.type || '')),
            imageUrl: images[0] || null,
            imageUrls: images,
            sourceUrl: window.location.href,
            method: 'site_heuristic (Shopify)'
          }];
        }
      } catch (e) {}
    }
    return null;
  });

  // =========================================================================
  // 2. Schema.org Product JSON-LD Extractor
  // =========================================================================
  function extractJsonLdProducts() {
    const products = [];
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');

    scripts.forEach((script) => {
      try {
        const raw = JSON.parse(script.textContent);
        const items = Array.isArray(raw) ? raw : (raw['@graph'] || [raw]);

        items.forEach((item) => {
          if (!item) return;
          const type = item['@type'];
          const isProduct = type === 'Product' || (Array.isArray(type) && type.includes('Product'));

          if (isProduct && item.name) {
            // Collect images
            let imageList = [];
            if (Array.isArray(item.image)) {
              imageList = item.image.map(img => typeof img === 'string' ? img : (img.url || img.contentUrl));
            } else if (typeof item.image === 'string') {
              imageList = [item.image];
            } else if (item.image && (item.image.url || item.image.contentUrl)) {
              imageList = [item.image.url || item.image.contentUrl];
            }

            imageList = imageList.map(resolveUrl).filter(Boolean);

            // Extract price from offers
            let price = null;
            if (item.offers) {
              const offer = Array.isArray(item.offers) ? item.offers[0] : item.offers;
              if (offer) {
                const rawPrice = offer.price || offer.lowPrice;
                const currency = offer.priceCurrency;
                price = cleanPrice(rawPrice, currency);
              }
            }

            const category = item.category ? guessCategory(String(item.category)) : guessCategory(item.name);

            if (imageList.length > 0) {
              products.push({
                id: 'jsonld_' + (item.sku || item.productID || Math.random().toString(36).substr(2, 9)),
                title: String(item.name).trim(),
                price,
                category,
                imageUrl: imageList[0],
                imageUrls: imageList,
                sourceUrl: window.location.href,
                method: 'Schema.org JSON-LD'
              });
            }
          }
        });
      } catch (e) {
        // Skip malformed JSON-LD scripts
      }
    });

    return products;
  }

  // =========================================================================
  // 3. Open Graph & Meta Tags Extractor
  // =========================================================================
  function extractOpenGraphProduct() {
    const getMeta = (prop) => {
      const el = document.querySelector(`meta[property="${prop}"], meta[name="${prop}"]`);
      return el ? el.getAttribute('content') : null;
    };

    const title = getMeta('og:title') || getMeta('twitter:title') || document.title;
    const ogImage = getMeta('og:image') || getMeta('og:image:secure_url') || getMeta('twitter:image');

    if (!ogImage || !title) return null;

    // Filter out common non-product images (icons, logos, blank placeholders)
    const lowerImg = ogImage.toLowerCase();
    if (lowerImg.includes('logo') || lowerImg.includes('favicon') || lowerImg.endsWith('.svg')) {
      return null;
    }

    // Collect all og:image tags on the page
    const allImages = Array.from(document.querySelectorAll('meta[property="og:image"], meta[property="og:image:secure_url"]'))
      .map(el => resolveUrl(el.getAttribute('content')))
      .filter((u, i, arr) => u && arr.indexOf(u) === i);

    // Extract price
    const rawPrice = getMeta('product:price:amount') || getMeta('og:price:amount') || getMeta('twitter:data1');
    const currency = getMeta('product:price:currency') || getMeta('og:price:currency');
    const price = cleanPrice(rawPrice, currency);

    return [{
      id: 'og_' + Math.random().toString(36).substr(2, 9),
      title: title.split(/[-–—|]/)[0].trim(), // Clean brand suffixes
      price,
      category: guessCategory(title),
      imageUrl: resolveUrl(ogImage),
      imageUrls: allImages.length > 0 ? allImages : [resolveUrl(ogImage)],
      sourceUrl: window.location.href,
      method: 'Open Graph'
    }];
  }

  // =========================================================================
  // 4. Visual Fallback Heuristic (Largest Product-Like Image near CTA)
  // =========================================================================
  const CTA_PATTERNS = [
    'add to cart', 'add to bag', 'add to basket', 'buy now', 'purchase',
    'buy it now', 'in den warenkorb', 'ajouter au panier', 'añadir a la cesta',
    'comprar ahora', 'order now'
  ];

  function extractVisualFallbackProduct() {
    // 1. Locate CTA buttons
    const candidates = Array.from(document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"]'));
    const ctaElements = candidates.filter((el) => {
      const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().toLowerCase();
      return CTA_PATTERNS.some(p => text.includes(p));
    });

    if (ctaElements.length === 0) return null;

    const primaryCta = ctaElements[0];

    // 2. Walk up container tree to find the surrounding product card/container
    let container = primaryCta.parentElement;
    for (let i = 0; i < 5; i++) {
      if (!container || container === document.body) break;
      const imgs = container.querySelectorAll('img');
      if (imgs.length >= 1) break;
      container = container.parentElement;
    }

    if (!container) container = document.body;

    // 3. Find largest valid product-like image in the container (or viewport)
    const images = Array.from(container.querySelectorAll('img, picture img')).filter((img) => {
      const src = img.currentSrc || img.src;
      if (!src || src.startsWith('data:image/svg') || src.includes('icon') || src.includes('logo') || src.includes('badge')) {
        return false;
      }
      const rect = img.getBoundingClientRect();
      const width = img.naturalWidth || rect.width;
      const height = img.naturalHeight || rect.height;
      const aspect = width / (height || 1);
      // Discard banners, tracking pixels, or tiny icons
      return width >= 160 && height >= 160 && aspect >= 0.35 && aspect <= 2.8;
    });

    if (images.length === 0) return null;

    // Sort by surface area
    images.sort((a, b) => {
      const areaA = (a.naturalWidth || a.width) * (a.naturalHeight || a.height);
      const areaB = (b.naturalWidth || b.width) * (b.naturalHeight || b.height);
      return areaB - areaA;
    });

    const primaryImg = images[0];
    const primaryUrl = resolveUrl(primaryImg.currentSrc || primaryImg.src);

    // Collect gallery images
    const allGalleryUrls = images
      .map(i => resolveUrl(i.currentSrc || i.src))
      .filter((u, idx, arr) => u && arr.indexOf(u) === idx)
      .slice(0, 6);

    // 4. Extract Title from nearest heading
    let title = null;
    const headings = container.querySelectorAll('h1, h2, h3, [class*="product-title"], [class*="productName"]');
    if (headings.length > 0) {
      title = headings[0].innerText.trim();
    } else {
      title = document.querySelector('h1')?.innerText?.trim() || document.title.split(/[-–—|]/)[0].trim();
    }

    // 5. Extract Price from text near CTA
    let price = null;
    const priceEl = container.querySelector('[class*="price"], [id*="price"]');
    if (priceEl) {
      const match = priceEl.innerText.match(PRICE_REGEX);
      if (match) price = match[0];
    }

    if (!title || !primaryUrl) return null;

    return [{
      id: 'visual_' + Math.random().toString(36).substr(2, 9),
      title,
      price,
      category: guessCategory(title),
      imageUrl: primaryUrl,
      imageUrls: allGalleryUrls.length > 0 ? allGalleryUrls : [primaryUrl],
      sourceUrl: window.location.href,
      method: 'Visual CTA Fallback'
    }];
  }

  // =========================================================================
  // Master Extraction Pipeline
  // =========================================================================
  function detectProductsOnPage() {
    const results = [];
    const seenUrls = new Set();

    function addUnique(list) {
      if (!list || !Array.isArray(list)) return;
      list.forEach((prod) => {
        if (prod && prod.imageUrl && !seenUrls.has(prod.imageUrl)) {
          seenUrls.add(prod.imageUrl);
          results.push(prod);
        }
      });
    }

    // Priority 0: Site-Specific Registered Heuristics
    for (const { matcher, extractor } of siteHeuristicsRegistry) {
      let matched = false;
      if (typeof matcher === 'function') {
        matched = Boolean(matcher(window.location.href, document));
      } else if (matcher instanceof RegExp) {
        matched = matcher.test(window.location.hostname) || matcher.test(window.location.href);
      }

      if (matched) {
        try {
          const siteProducts = extractor(document, window.location.href);
          if (siteProducts && siteProducts.length > 0) {
            addUnique(siteProducts);
            console.log('[AI Try-On] Matched site-specific heuristic:', siteProducts);
            return results; // Site-specific heuristics take top precedence
          }
        } catch (e) {
          console.warn('[AI Try-On] Error in site heuristic:', e);
        }
      }
    }

    // Priority 1: Schema.org JSON-LD
    const jsonLdProducts = extractJsonLdProducts();
    if (jsonLdProducts && jsonLdProducts.length > 0) {
      addUnique(jsonLdProducts);
      console.log('[AI Try-On] Detected products via Schema.org JSON-LD:', jsonLdProducts);
      return results;
    }

    // Priority 2: Open Graph Meta Tags
    const ogProducts = extractOpenGraphProduct();
    if (ogProducts && ogProducts.length > 0) {
      addUnique(ogProducts);
      console.log('[AI Try-On] Detected product via Open Graph:', ogProducts);
      return results;
    }

    // Priority 3: Visual CTA Fallback
    const fallbackProducts = extractVisualFallbackProduct();
    if (fallbackProducts && fallbackProducts.length > 0) {
      addUnique(fallbackProducts);
      console.log('[AI Try-On] Detected product via Visual Fallback:', fallbackProducts);
      return results;
    }

    return results;
  }

  // =========================================================================
  // Message Listener & Lightweight State Sync
  // =========================================================================
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'DETECT_PRODUCTS') {
      const products = detectProductsOnPage();

      // Store detected products in chrome.storage.local (lightweight metadata only)
      chrome.storage.local.set({ storedProducts: products }, () => {
        sendResponse({ success: true, count: products.length, products });
      });
      return true; // Keep channel open for async response
    }

    if (request.type === 'GET_PAGE_PRODUCTS') {
      const products = detectProductsOnPage();
      sendResponse({ success: true, count: products.length, products });
      return true;
    }
  });

  // Automatically scan on load & cache in storage
  window.addEventListener('load', () => {
    setTimeout(() => {
      const products = detectProductsOnPage();
      if (products && products.length > 0) {
        chrome.storage.local.set({ storedProducts: products });
      }
    }, 800);
  });

  // Expose registry for developer console extension if needed
  window.__AITryOnRegisterHeuristic = registerSiteHeuristic;
})();
