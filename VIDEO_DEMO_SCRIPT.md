# 🎬 AI Virtual Try-On — Comprehensive Video Demo Script & Walkthrough

> **Target Audience:** Project Evaluator / Hiring Manager / Senior Engineering Reviewer  
> **Target Duration:** ~3:15 – 3:30 Minutes  
> **Tone:** Clear, engaging, technically rigorous, confident, and professional.

---

## 📋 Pre-Demo Recording Checklist

Before hitting record, ensure the environment is primed so the demo runs seamlessly without awkward loading pauses:

1. **Start the FastAPI Backend:**
   ```bash
   cd backend
   venv\Scripts\activate
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   *Verify health check at `http://127.0.0.1:8000/health` (Status: `"healthy"`, SQLite WAL active).*

2. **Load Chrome Extension (Manifest V3):**
   - Open Chrome `chrome://extensions/`.
   - Enable **Developer mode** (top right).
   - Click **Load unpacked** and select the `extension/` folder.
   - Pin the **AI Try-On** icon to your browser toolbar.

3. **Prepare Browser Tabs:**
   - **Tab 1:** An apparel product page with multiple photos (e.g., a jacket or dress on ASOS, Zara, Uniqlo, or H&M).
   - **Tab 2:** The Digital Profile Studio page (`chrome-extension://<id>/profile/profile.html`).

4. **Have at Least One Profile Pre-Loaded:**
   - Ensure a profile (e.g. "Alex" or "Jordan") is already created with at least 1 or 2 reference photos so you don't spend 40 seconds uploading files from scratch during the video.

---

## ⚡ Master Features & USPs Checklist (All Covered in Script)

| Phase / Module | Feature / USP | Highlighted In Demo? |
| :--- | :--- | :---: |
| **Architecture** | Chrome Manifest V3, SidePanel API, Python FastAPI, SQLite (WAL mode) | ✅ Scene 1 |
| **Zero Cost Stack** | 100% free & open-weight stack: Hugging Face ZeroGPU, MediaPipe, open-weight CLIP | ✅ Scene 1 |
| **Phase 2 & Bonus 2** | Multi-angle Profile Studio (5 perspectives) + MediaPipe posture gating + Multi-profile isolation | ✅ Scene 2 |
| **Phase 11** | Privacy & Right-to-be-Forgotten: Non-public local disk, `consent_no_training`, cascading purge | ✅ Scene 2 |
| **Phase 4 & 5** | Universal DOM extraction (JSON-LD, OG, CTA fallback) + Front-shot clarity scoring algorithm | ✅ Scene 3 |
| **Phase 7** | Pluggable Category Registry (Apparel, Footwear/Shoes, Accessories/Jewelry) | ✅ Scene 3 |
| **Phase 6** | CatVTON diffusion try-on model executing on Hugging Face ZeroGPU | ✅ Scene 4 |
| **Phase 9** | Quality Guardrail: CIELAB color delta + pattern gradient check + Low-Confidence alert | ✅ Scene 4 |
| **Phase 10** | Smart caching engine (`⚡ Cached` instant hit vs `🔄 Re-try` force refresh) | ✅ Scene 4 |
| **Bonus / Phase 8** | Side-by-Side Comparison Dock (Look A vs Look B) + Interactive Split Slider (`clip-path`) | ✅ Scene 5 |
| **Phase 10 / Bonus** | Virtual Wardrobe / Digital Closet with category filters (Tops, Bottoms, Shoes, etc.) | ✅ Scene 6 |

---

## 📜 Complete Step-by-Step Demo Script

```
TIMESTAMPS OVERVIEW:
0:00 - 0:35  | Scene 1: Introduction, Live Extension & Open-Weight Stack
0:35 - 1:05  | Scene 2: 5-Angle Profile Studio, MediaPipe Gating & Privacy
1:05 - 1:40  | Scene 3: Universal DOM Extraction, Clarity Heuristic & Pluggable Handlers
1:40 - 2:20  | Scene 4: ZeroGPU Drape Synthesis, Color Quality Guardrail & Caching
2:20 - 2:55  | Scene 5: Dual Look Comparison & Hardware-Accelerated Interactive Split Slider
2:55 - 3:20  | Scene 6: Virtual Wardrobe, Offline SQLite WAL & Conclusion
```

---

### Scene 1: Introduction, Live Extension & Open-Weight Stack
**Time:** `0:00 - 0:35`

#### 🖥️ Visuals & Actions:
- **Starting Screen:** Full screen on an active online clothing store (e.g. Zara or ASOS).
- **Action 1 (0:05):** Click the extension icon in the toolbar. Show the native Chrome Side Panel smoothly slide open alongside the webpage.
- **Action 2 (0:15):** Toggle the **Dark / Light theme** switch in the top-right header, then point to the green **"Backend: Healthy"** status chip.
- **Action 3 (0:25):** Show the active profile switcher dropdown at the top of the side panel.

#### 🎙️ Voiceover:
> *"Hello! Today, I’m presenting an AI Virtual Try-On system built as a native Chrome Extension backed by a Python FastAPI engine. It enables online shoppers to see realistic clothing, footwear, and accessories draped onto their own body in real time while browsing any e-commerce site.*
>
> *The frontend leverages **Chrome Manifest V3 and the native SidePanel API** for an unobtrusive side-by-side browsing experience. Crucially, the entire AI pipeline is built on a **100% open-weight, zero-cost architecture**—using CatVTON on Hugging Face ZeroGPU, local MediaPipe landmark detection, open-weight CLIP classification, and SQLite in WAL mode, avoiding expensive proprietary API lock-in."*

---

### Scene 2: 5-Angle Profile Studio, MediaPipe Gating & Privacy
**Time:** `0:35 - 1:05`

#### 🖥️ Visuals & Actions:
- **Action 1 (0:35):** In the Digital Profile section of the side panel, click **"Manage"** to open the full **Digital Profile Studio** tab.
- **Action 2 (0:45):** Highlight the 5 distinct perspective steps: **Front Full-Body, Upper Body, Legs, Feet, and Face**. Show the photo completeness meter (e.g. 80%).
- **Action 3 (0:52):** Hover over an uploaded photo showing the MediaPipe green landmark mesh confirmation ("Keypoints Validated").
- **Action 4 (0:58):** Briefly highlight the **"No AI Training / Local Storage Only"** privacy guarantee in the footer, then switch back to the shopping tab.

#### 🎙️ Voiceover:
> *"A good fitting begins with an accurate digital representation. The system supports multiple user profiles with complete data isolation.*
>
> *Instead of relying on a single generic selfie, the Digital Profile Studio guides users through **five targeted perspectives**: full body, upper torso, lower legs, footwear, and portrait. Each upload is gated by **local MediaPipe computer vision**, verifying joint visibility and posture before accepting.*
>
> *For privacy, all reference photos are stored exclusively on non-public local disk—never exposed via public static URLs. The system includes an explicit `consent_no_training` policy and cascading physical file deletion to ensure full compliance with Right-to-be-Forgotten standards."*

---

### Scene 3: Universal DOM Extraction, Clarity Heuristic & Pluggable Handlers
**Time:** `1:05 - 1:40`

#### 🖥️ Visuals & Actions:
- **Action 1 (1:05):** In the side panel, point to the **"Products on this page"** section showing the automatically detected garment (e.g. a stylish jacket or dress).
- **Action 2 (1:15):** Show the product card: title, category pill ("Upper Body"), and price detected from the page DOM.
- **Action 3 (1:22):** Point to the product thumbnail strip: show how the **Front-Shot Clarity Heuristic** automatically selected the clean studio packshot over the cluttered editorial/runway shot. Click another angle thumbnail to show variant flexibility.
- **Action 4 (1:32):** Hover over the category pill to emphasize that the backend handler knows whether to route this to apparel, footwear, or jewelry.

#### 🎙️ Voiceover:
> *"As a shopper browses, our content script scans the webpage using a multi-tiered fallback strategy: first inspecting Schema.org JSON-LD structured data, then Open Graph tags, and finally a visual proximity heuristic near the 'Add to Cart' button.*
>
> *When an item has multiple photo angles, the extension runs a **front-shot clarity scoring algorithm** that filters out noisy lifestyle and runway photos, auto-selecting the cleanest flat-lay packshot while still letting the user click alternative angles.*
>
> *Under the hood, requests pass through a **pluggable category registry**, automatically routing garments to CatVTON, footwear to foot-mesh warpers, and accessories to keypoint compositors."*

---

### Scene 4: ZeroGPU Drape Synthesis, Color Quality Guardrail & Caching
**Time:** `1:40 - 2:20`

#### 🖥️ Visuals & Actions:
- **Action 1 (1:40):** Click the primary **"✨ Try On: [Garment Name]"** button.
- **Action 2 (1:45):** Watch the 3-stage progress bar animate:
  - *Stage 1: CLIP Garment Analysis*
  - *Stage 2: MediaPipe Landmark Alignment*
  - *Stage 3: CatVTON ZeroGPU Diffusion*
- **Action 3 (1:58):** The composited result appears instantly in the Results View! Show the generated try-on image fitted onto the user's reference model.
- **Action 4 (2:05):** Point to the **"96% Match"** fidelity badge and explain the quality guardrail.
- **Action 5 (2:12):** Click **"Try On"** a second time to demonstrate the **instant cache hit**: the badge flips to **"⚡ Cached" (0.05s response)** with a **"🔄 Re-try"** option.

#### 🎙️ Voiceover:
> *"Clicking 'Try On' dispatches the reference photo and garment to our **CatVTON diffusion model hosted on Hugging Face ZeroGPU**. The pipeline segments the clothing, generates an inpainting mask, and warps fabric textures naturally around the user's pose.*
>
> *Once synthesized, the output is evaluated by our **Accuracy Validator**. It compares CIELAB color deltas and high-frequency texture gradient energy between the original product and the rendered drape. If color hallucination is detected, a **Low-Confidence Warning Banner** alerts the shopper immediately.*
>
> *Notice also the performance optimization: re-trying an item yields an **instant sub-second cache hit marked with a '⚡ Cached' pill**, preserving serverless GPU compute while allowing forced re-runs when desired."*

---

### Scene 5: Dual Look Comparison & Hardware-Accelerated Interactive Split Slider
**Time:** `2:20 - 2:55`

#### 🖥️ Visuals & Actions:
- **Action 1 (2:20):** Click **"Add to Look A"** on the first try-on result. The sticky **Side-by-Side Compare Dock** pops up at the bottom showing Look A staged.
- **Action 2 (2:25):** Select a second garment from the page (or click demo sample "➕"), generate or select it, and click **"Add to Look B"**.
- **Action 3 (2:32):** Click **"Compare Looks Side-by-Side"**. A modal opens showing **Dual View** with Look A on the left and Look B on the right with a central "VS" badge and match scores.
- **Action 4 (2:40):** Click the **"Interactive Split"** toggle button.
- **Action 5 (2:44):** Grab the vertical slider handle and drag it left and right across the modal, revealing Look A and Look B seamlessly over the model.

#### 🎙️ Voiceover:
> *"Shopping is all about choices. Our **Side-by-Side Comparison Dock** lets users stage two distinct outfits—Look A and Look B.*
>
> *The comparison modal offers two modes: a classic Dual View with independent match metrics, and our flagship **Interactive Split View**.*
>
> *As I drag the divider across the screen, Look A transitions into Look B. This is engineered using **hardware-accelerated CSS `clip-path` masks**, ensuring pixel-perfect spatial alignment across identical body coordinates so shoppers can judge neckline, hemline, and drape differences with zero visual jitter."*

---

### Scene 6: Virtual Wardrobe, Offline SQLite WAL & Conclusion
**Time:** `2:55 - 3:20`

#### 🖥️ Visuals & Actions:
- **Action 1 (2:55):** Close the comparison modal and scroll down to the **"Virtual Wardrobe" / Closet** section.
- **Action 2 (3:02):** Click the category filter chips: **"Tops"**, **"Bottoms"**, and **"All"**, showing instant filtering and historical fittings.
- **Action 3 (3:10):** Hover over a closet item to show the **Download** button and timestamp.
- **Action 4 (3:15):** Return to the main overview card, show the smooth interface, and wrap up.

#### 🎙️ Voiceover:
> *"Every generated look is automatically saved to the user's **Virtual Wardrobe**, filterable by category such as Tops, Bottoms, and Dresses. Powered by **SQLite in WAL mode**, wardrobe data loads instantly and supports high-concurrency local reading.*
>
> *Users can download high-resolution outputs for sharing or second opinions.*
>
> *In summary, this project bridges modern browser capabilities with advanced generative diffusion models, automated quality assurance, and strict privacy protection—delivering a seamless, production-grade virtual fitting room. Thank you!"*

---

## 💡 Evaluator Q&A Cheat Sheet (If Asked Questions Post-Demo)

| Anticipated Question | Bulletproof Answer |
| :--- | :--- |
| **"Why CatVTON over other try-on models?"** | *"CatVTON uses spatial concatenation rather than cross-attention text conditioning. This preserves intricate garment patterns, logos, and textures without distortion while running within the 16GB VRAM limit of free Hugging Face ZeroGPU."* |
| **"How is user privacy guaranteed?"** | *"Photos are never uploaded to public buckets like S3. They are stored locally on private disk accessed through authenticated FastAPI streaming routes. We enforce `consent_no_training` and CASCADE delete physical files on profile removal."* |
| **"How does the extension work on sites without JSON-LD?"** | *"Our detection pipeline has 3 tiers: (1) JSON-LD structured data, (2) Open Graph/Twitter meta tags, and (3) a visual DOM heuristic that scores images based on aspect ratio, pixel area, and proximity to checkout buttons."* |
| **"Why use CSS `clip-path` for the split slider?"** | *"Instead of re-rendering two overlapping canvases or slicing images, CSS `clip-path: polygon()` runs on the GPU compositor thread. It achieves 60 FPS slider movement with zero DOM re-layout."* |
