# 💧 AquaSense AI — AI-Powered Web-Based Groundwater Monitoring & Prediction System

A complete BTech mini-project web platform that integrates real-time environmental data monitoring, SQLite database persistence, Machine Learning (Random Forest) water-level forecasting, automated risk assessment, an interactive AI groundwater assistant, and authentic **Central Ground Water Board (CGWB) Digital Water Level Recorder (DWLR)** telemetry from the **National Water Data Portal (NWDP)**.

---

## 🌟 Key Features

1. **Authentic CGWB DWLR Telemetry**:
   - Replaced static city cards with a dynamic, user-driven search: **State → District → Station → View Groundwater Data**.
   - Directly integrates official datasets from the National Water Data Portal (NWDP CKAN API: https://nwdp.nwic.gov.in).
   - Accurately reports measurements as **depth below ground level (`m bgl`)** — where a lower number indicates water closer to the surface and a higher number represents deeper depletion.
   - Comprehensive station metadata: Agency (`CGWB`), State, District, Tehsil/Block, Latitude/Longitude, River/Basin, and Elevation (`RL_MSL`).
   - Detailed historical telemetry observations table with timestamps and direct **CSV Export**.

2. **Machine Learning Predictive Engine**:
   - Random Forest Regressor predicting future 30-day water level depths with confidence estimation.
   - Automatically incorporates recent station observation trends.

3. **Dynamic Risk Assessment**:
   - Rule-based & trend-weighted risk classifier: **Safe / Low**, **Moderate / Medium**, **Critical / High**.
   - Transparently indicates operational recommendations (e.g. rainwater percolation pits, borewell extraction regulations).

4. **Aqua AI Assistant (Powered by Google Gemini Generative AI)**:
   - Replaced keyword-matching with official **Google Gemini API (`google-genai` SDK)**.
   - Natural language comprehension: handles spelling errors, colloquial phrasing, follow-up questions, and arbitrary groundwater inquiries.
   - Grounded in real project data: automatically extracts verified CGWB DWLR telemetry, observation timestamps, units (`m bgl`), and risk parameters from SQLite.
   - Context-aware "Ask AI for Details" button in Risk Assessment section.
   - Full conversation history tracking, free-text prompt input, and transparent error handling (no fake simulated fallback).

---

## 📁 1. Project Directory Structure

```text
my project/
│
├── frontend/                     # Frontend UI (Premium dark forest-green & teal theme)
│   ├── index.html                # Upgraded dashboard with DWLR Telemetry Explorer
│   ├── style.css                 # Responsive stylesheet & telemetry data table styles
│   └── script.js                 # Cascading State->District->Station controller & Chart.js
│
├── backend/                      # Python Flask Backend (REST APIs)
│   ├── app.py                    # Flask server entrypoint (serves static UI & REST APIs)
│   ├── cgwb_data.py              # Official NWDP/CGWB ingestion, caching, & query engine
│   ├── database.py               # SQLite database layer & schema initialization
│   ├── routes.py                 # REST API endpoints (DWLR, predictions, risk, chat, CSV)
│   ├── prediction.py             # Machine learning inference engine
│   ├── risk_analysis.py          # Groundwater risk classification algorithm
│   ├── chatbot.py                # AI Groundwater Assistant (offline hydrology engine)
│   ├── requirements.txt          # Python dependencies
│   └── groundwater.db            # SQLite database file (persisting DWLR stations & readings)
│
├── data/                         # Datasets & Ingestion Cache
│   ├── cgwb_cache/               # Local cache of downloaded official NWDP CSV files
│   └── groundwater_data.csv      # Baseline reference dataset
│
├── ml/                           # Machine Learning Pipeline
│   ├── train_model.py            # Model training & evaluation script (Random Forest)
│   ├── groundwater_model.pkl     # Trained Random Forest Regressor model
│   └── model_metadata.json       # Model metrics, feature names, and R² score
│
├── .env.example                  # Environment configuration template
├── index.html                    # Root companion frontend page
├── miniproject.html              # Standalone mirror of frontend page
└── README.md                     # Complete project documentation & viva guide
```

---

## 🚀 2. How to Run the Project (Step-by-Step)

### Step 1: Open Terminal in the Project Folder
Open PowerShell or Command Prompt:
```powershell
cd "c:\Users\91880\Downloads\my project"
```

### Step 2: (Optional but Recommended) Activate Virtual Environment
```powershell
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Required Python Packages
```powershell
pip install -r backend/requirements.txt
```

### Step 4: Start the Flask Backend Server
```powershell
python backend/app.py
```
You will see:
```text
==================================================
   Starting AquaSense AI Groundwater Backend...   
==================================================
DWLR database tables initialized.
Database and DWLR tables ready.
Server running at: http://127.0.0.1:5000
Press Ctrl+C to stop.
```

### Step 5: Open in Your Web Browser
Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

*Note: You can also double-click `miniproject.html` or `index.html` directly. The frontend JavaScript automatically communicates with the Flask server at `http://127.0.0.1:5000`.*

---

## 🔍 3. How to Use the DWLR Telemetry Explorer

1. **Explore Monitoring Stations**:
   - Scroll down to the **DWLR Telemetry Explorer** section.
   - The status banner shows how many real government stations and telemetry observations are indexed.
   - Choose a state (e.g. **Bihar**, **Punjab**, **Haryana**, **Delhi**).
   - Select a district (e.g. **Patna**).
   - Select a specific DWLR station (e.g. **A.N. College**).
   - Click **📊 View Groundwater Telemetry**.

2. **Inspect Station Telemetry**:
   - View exact station metadata: Agency (`CGWB DWLR`), District, Tehsil, Block, Latitude, Longitude, and Basin.
   - Read the latest depth in **`m bgl` (meters below ground level)**.
   - Scroll through the **Recorded Telemetry Observations Table** to see timestamps and recorded values.
   - Click **📥 Download Station CSV** to export the station's raw historical records.

3. **Synchronize Dashboard & Predictions**:
   - Selecting a station automatically updates the top **Groundwater Overview** dashboard.
   - The line chart plots recent telemetry depths.
   - Click **⚡ Run Live AI Prediction (API)** to calculate the 30-day forecast.
   - Open the **Aqua AI Chat Assistant** (bottom-right bubble) and ask questions like *"What is a DWLR station?"* or *"Why is risk moderate in this station?"*.

---

## 📡 4. REST API Documentation

| Endpoint | Method | Description | Request Example / Query Params |
| :--- | :--- | :--- | :--- |
| `/api/health` | `GET` | Health check and system status | None |
| `/api/data/status` | `GET` | DWLR cache status and station counts | None |
| `/api/data/ingest` | `POST` | Trigger NWDP CSV download and indexing | `{"key": "aquasense2024"}` |
| `/api/locations/states` | `GET` | List all 36 Indian states & UTs with station counts | None |
| `/api/locations/districts` | `GET` | List districts in a state with DWLR data | `?state=Bihar` |
| `/api/locations/stations` | `GET` | List DWLR stations in state & district | `?state=Bihar&district=Patna` |
| `/api/groundwater/station/<id>` | `GET` | Station metadata and latest telemetry reading | URL path parameter |
| `/api/groundwater/observations` | `GET` | Chronological telemetry observations table | `?station_id=9&limit=100` |
| `/api/groundwater/history` | `GET` | Formatted series for Chart.js trend visualization | `?station_id=9&limit=50` |
| `/api/dashboard` | `GET` | Summary statistics for cards & overview | `?station_id=9` |
| `/api/export/csv` | `GET` | Export station telemetry records as CSV | `?station_id=9` |
| `/api/predict` | `POST` | Machine learning water level prediction | `{"station_id": 9, "water_level": 12.09}` |
| `/api/risk` | `GET`/`POST` | Rule & trend-based risk assessment | `?station_id=9&water_level=12.09` |
| `/api/chat` | `POST` | Hydrology AI Chatbot | `{"message": "What does m bgl mean?", "station_id": 9}` |

---

## 🎓 5. Academic Viva / Presentation Guide

When presenting AquaSense AI for your BTech evaluation:
1. **What is a DWLR?**
   - *Digital Water Level Recorder*: An automated hydrostatic pressure sensor installed in piezometers or observation wells by the Central Ground Water Board (CGWB). It eliminates manual tape measurements and logs water depths at hourly or quadridaily intervals.
2. **What does `m bgl` mean?**
   - *Meters Below Ground Level*: The standard hydrological unit representing the depth from the ground surface down to the water table. A value of `5.0 m bgl` means water is 5 meters down (healthy); `25.0 m bgl` indicates severe depletion.
3. **Data Authenticity**:
   - Telemetry data is sourced directly from the government's **National Water Data Portal (NWDP)** via open CKAN APIs, ensuring real, verifiable government observations rather than synthetic placeholders.
4. **Machine Learning Approach**:
   - Random Forest Regressor chosen for its ability to model non-linear seasonal recharge dynamics and resist sensor noise.

---

## 🤖 6. Aqua AI Gemini Assistant: Setup, Costs & Testing

### Step 1: Obtain a Free Google Gemini API Key
1. Visit **Google AI Studio**: [https://aistudio.google.com/](https://aistudio.google.com/).
2. Sign in with your Google account.
3. Click **"Get API key"** and create a free key.

### Step 2: Configure Environment (`.env`)
1. Create a file named `.env` in the root folder (`my project/.env`).
2. Add your Gemini API key:
   ```env
   FLASK_ENV=development
   FLASK_PORT=5000
   GEMINI_API_KEY=AIzaSyYourRealKeyHere
   GEMINI_MODEL=gemini-2.5-flash
   ```
*(Note: `.env` is listed in `.gitignore` and will never be committed to Git).*

### Step 3: API Usage Limits & Costs
* **Free Tier Available**: Google AI Studio provides a free tier for `gemini-2.5-flash` and `gemini-1.5-flash`.
* **Rate Limits (Free Tier)**:
  * 15 Requests Per Minute (RPM)
  * 1,000,000 Tokens Per Minute (TPM)
  * 1,500 Requests Per Day (RPD)
* **Cost**: ₹0 / $0 for student projects and local development testing.

### Step 4: Run Chatbot Test Suite
Run the automated test verifying all 9 required scenarios:
```powershell
python -m unittest scratch/test_ai_chatbot.py # or:
python "C:\Users\91880\.gemini\antigravity-ide\brain\9647edc0-79b0-4622-9e80-215ece6f6683\scratch\test_ai_chatbot.py"
```

