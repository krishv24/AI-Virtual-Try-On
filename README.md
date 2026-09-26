# AI Virtual Try-On 👗✨

An AI-powered Virtual Try-On shopping assistant Chrome extension paired with a Python FastAPI backend.

---

## 🎯 Tech Stack Overview
*(Referenced from `techstack.txt`)*

- **Extension:** Chrome Manifest V3, Vanilla JavaScript (no framework, zero build step needed).
- **Backend:** Python 3.12+ with FastAPI & Uvicorn.
- **Database:** SQLite to start.
- **Try-On AI Pipeline:** CatVTON (initial stage) → IDM-VTON, self-hosted on Hugging Face Spaces (ZeroGPU free tier).
- **Category Classification:** CLIP (open-weight, free).
- **Pose / Body Landmarks:** MediaPipe (free, local execution).
- **Styling Suggestions / Descriptions:** Groq or Google Gemini free tier (**strictly zero OpenAI / Anthropic paid usage**).
- **Security Constraint:** Never hardcode API keys or secrets in the extension; all secrets reside exclusively in `backend/.env`.

---

## 📁 Repository Structure

```
AI-Virtual-Try-On/
├── .gitignore               # Ignores venvs, cache, .env, *.db
├── README.md                # Project documentation & quickstart
├── techstack.txt            # Architecture & tech stack specifications
├── extension/               # Chrome Manifest V3 Extension
│   ├── manifest.json        # MV3 manifest with popup, side panel & content scripts
│   ├── background.js        # Service worker for panel & lifecycle events
│   ├── icons/               # 16px, 48px, 128px extension icons
│   ├── content/             # Phase 4 Universal Product Detection
│   │   └── content.js       # Priority extractors (JSON-LD, OG, Visual CTA) & Plugin Registry
│   ├── popup/               # Extension popup UI
│   │   ├── popup.html       # Glassmorphism popup with backend status check & Studio link
│   │   ├── popup.css        # Modern dark-mode styling
│   │   └── popup.js         # API health check, side panel & profile launcher
│   ├── profile/             # Phase 2 Digital Profile Creation Studio
│   │   ├── profile.html     # Multi-step profile wizard & on-screen guidance
│   │   ├── profile.css      # Studio workspace styles & validation badges
│   │   └── profile.js       # MediaPipe upload feedback & multi-profile manager
│   └── sidepanel/           # Chrome side panel workstation (Phase 3 UI Shell)
│       ├── sidepanel.html   # Shell with profile switcher, products on page, feedback & results
│       ├── sidepanel.css    # Responsive workstation styles & animations
│       └── sidepanel.js     # chrome.storage.local sync, product selection, pipeline feedback
└── backend/                 # Python FastAPI Backend
    ├── .env.example         # Environment template (keys, model endpoints)
    ├── requirements.txt     # Python backend dependencies
    ├── tryon.db             # SQLite database (auto-generated on startup)
    ├── tests/               # Backend tests
    │   ├── test_phase1.py   # Test suite for CRUD & storage
    │   ├── test_phase2.py   # Test suite for MediaPipe validation & multi-profile
    │   └── test_phase4.py   # Test suite for product registration & catalog
    └── app/
        ├── __init__.py      # Package indicator
        ├── config.py        # Settings loader with private STORAGE_DIR
        ├── database.py      # SQLite connection & Phase 1 schema DDL
        ├── main.py          # FastAPI app with CORS & lifespan DB init
        ├── models/          # Pydantic schemas (profiles, photos, products)
        │   ├── __init__.py
        │   └── schemas.py
        ├── routers/         # API Routers
        │   ├── __init__.py
        │   ├── profiles.py  # Profiles CRUD + MediaPipe validated uploads
        │   ├── photos.py    # Private photo file streaming & deletion
        │   └── products.py  # Product registration & lookup
        └── services/        # AI & Computer Vision Services
            ├── __init__.py
            └── mediapipe_validator.py  # MediaPipe Pose & Face landmark verifier
```

---

## 🗄️ Database Schema (SQLite)

- **`profiles`**: `id`, `name`, `created_at`
- **`profile_photos`**: `id`, `profile_id` (FK CASCADE), `photo_type` (`front_full_body`, `upper_body`, `legs`, `feet`, `face`), `file_path`, `created_at`
- **`products`**: `id`, `source_url`, `title`, `image_urls`, `category`, `price`, `detected_at`
- **`tryon_results`**: `id`, `profile_id` (FK CASCADE), `product_id` (FK SET NULL), `category`, `image_path`, `created_at`

### 🔒 Storage Security Model
User photos are stored on local disk under `backend/storage/private_uploads/`. This directory is **never mounted or exposed publicly as a static web path**. Files can only be retrieved through the controlled `/api/photos/{photo_id}/file` endpoint or consumed internally by AI inference pipelines.

---

## 🚀 Quickstart Guide

### 1. Start the Backend
1. Open a terminal and navigate to the backend folder:
   ```bash
   cd backend
   ```
2. (Optional) Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
5. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
6. Verify the server is running by opening:
   - Health check: [http://localhost:8000/health](http://localhost:8000/health)
   - Interactive Swagger API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 2. Load the Chrome Extension
1. Open Google Chrome and go to `chrome://extensions/`.
2. Enable **Developer mode** toggle in the top-right corner.
3. Click **Load unpacked**.
4. Select the `extension/` folder inside this repository:
   `c:\Users\Krish Vinod\Desktop\Vs\AI try on\extension`
5. Pin the **AI Virtual Try-On** extension to your toolbar.
6. Click the extension icon to view the popup status monitor and launch the **Try-On Studio Side Panel**!
