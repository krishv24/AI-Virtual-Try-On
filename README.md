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
│   ├── manifest.json        # MV3 manifest with popup and side panel support
│   ├── background.js        # Service worker for panel & lifecycle events
│   ├── icons/               # 16px, 48px, 128px extension icons
│   ├── popup/               # Extension popup UI
│   │   ├── popup.html       # Glassmorphism popup with backend status check
│   │   ├── popup.css        # Modern dark-mode styling
│   │   └── popup.js         # API health check & side panel launcher
│   └── sidepanel/           # Chrome side panel workstation
│       ├── sidepanel.html   # Model & garment upload + preview studio
│       ├── sidepanel.css    # Responsive side panel layout & controls
│       └── sidepanel.js     # Side panel state & backend connector
└── backend/                 # Python FastAPI Backend
    ├── .env.example         # Environment template (keys, model endpoints)
    ├── requirements.txt     # Python backend dependencies
    └── app/
        ├── __init__.py      # Package indicator
        ├── config.py        # Settings loader with pydantic-settings
        └── main.py          # FastAPI app with CORS & /health endpoint
```

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
