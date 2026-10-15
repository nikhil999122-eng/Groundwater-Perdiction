/**
 * AquaSense AI - Frontend Controller & API Integration
 * BTech Mini Project: AI-Powered Web-Based Groundwater Monitoring & Prediction System
 *
 * Connects the HTML/CSS frontend to the Flask REST API:
 * - GET  /api/locations/states
 * - GET  /api/locations/districts?state=...
 * - GET  /api/locations/stations?state=...&district=...
 * - GET  /api/groundwater/station/:id
 * - GET  /api/groundwater/history?station_id=...
 * - GET  /api/groundwater/observations?station_id=...
 * - GET  /api/dashboard?station_id=...
 * - GET  /api/data/status
 * - POST /api/data/ingest
 * - GET  /api/export/csv?station_id=...
 * - POST /api/predict
 * - GET  /api/risk
 * - POST /api/chat
 */

// ============================================================================
// CONFIGURATION & GLOBAL STATE
// ============================================================================

// Automatically detects whether to use relative /api (if served via Flask)
// or direct http://127.0.0.1:5000 (if opened directly in browser or Live Server)
const API_BASE = (window.location.protocol.startsWith("http") && window.location.port === "5000")
    ? ""
    : "http://127.0.0.1:5000";

let currentStationId = null;
let currentStationData = null;
let currentLocation = "All India";
let currentWaterLevel = null;
let currentRiskLevel = "Normal";
let groundwaterChart = null;


// ============================================================================
// INITIALIZATION ON PAGE LOAD
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    console.log("AquaSense AI Frontend Initialized. API Base:", API_BASE || "Relative /api");
    initChart();
    checkBackendHealth();
    initDWLRSystem();
    initPredictionPopupEvents();
});


// ============================================================================
// 1. SYSTEM HEALTH & CONNECTIVITY
// ============================================================================

async function checkBackendHealth() {
    const dot = document.getElementById("systemStatusDot");
    const text = document.getElementById("systemStatusText");

    try {
        const response = await fetch(`${API_BASE}/api/health`);
        if (response.ok) {
            const data = await response.json();
            if (dot) dot.style.background = "var(--success)";
            if (text) text.textContent = "System Online • Connected";
        } else {
            throw new Error("Backend returned status " + response.status);
        }
    } catch (err) {
        console.warn("Backend currently unreachable:", err);
        if (dot) dot.style.background = "var(--warning)";
        if (text) text.textContent = "System Demo Mode (Flask Offline)";
    }
}


// ============================================================================
// 2. CHART VISUALIZATION (Chart.js)
// ============================================================================

function initChart() {
    const canvas = document.getElementById("groundwaterChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    groundwaterChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: ["No station selected"],
            datasets: [{
                label: "Depth to Water Level (m bgl)",
                data: [0],
                borderColor: "#42d6a3",
                backgroundColor: "rgba(66,214,163,.08)",
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: "#42d6a3"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: "#0d241f",
                    titleColor: "#f2faf7",
                    bodyColor: "#42d6a3",
                    borderColor: "rgba(66,214,163,.3)",
                    borderWidth: 1,
                    callbacks: {
                        label: (ctx) => `Depth: ${ctx.parsed.y} m bgl (below ground level)`
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: "#718d84",
                        maxTicksLimit: 12
                    }
                },
                y: {
                    grid: {
                        color: "rgba(255,255,255,.05)"
                    },
                    ticks: {
                        color: "#718d84",
                        callback: (val) => `${val} m`
                    }
                }
            }
        }
    });
}


async function updateChartWithObservations(observations, stationName) {
    if (!groundwaterChart || !observations || observations.length === 0) return;

    // Filter valid positive depths and sort chronologically (oldest to newest for trend)
    const validObs = observations
        .filter(o => o.water_level !== null && o.water_level !== undefined && o.water_level >= 0)
        .slice()
        .reverse(); // observations API returns newest first; chart shows oldest to newest

    if (validObs.length === 0) return;

    const labels = validObs.map(o => {
        const dt = o.data_acquisition_time || o.date || "";
        // Extract DD-MM or date part
        if (dt.includes(" ")) return dt.split(" ")[0];
        return dt;
    });

    const values = validObs.map(o => o.water_level);

    groundwaterChart.data.labels = labels;
    groundwaterChart.data.datasets[0].data = values;
    groundwaterChart.update();

    const chartSubtitle = document.getElementById("chartHeadingSubtitle");
    if (chartSubtitle) {
        chartSubtitle.textContent = `DWLR Telemetry Trend • ${stationName} (m bgl)`;
    }

    const chartYear = document.getElementById("chartYearBadge");
    if (chartYear) {
        const lastDt = validObs[validObs.length - 1].data_acquisition_time || "";
        if (lastDt.includes("-")) {
            const yr = lastDt.split("-")[2] ? lastDt.split("-")[2].split(" ")[0] : "2024";
            chartYear.textContent = yr;
        } else {
            chartYear.textContent = "DWLR";
        }
    }
}


// ============================================================================
// 3. DWLR SYSTEM INIT & STATUS CHECK
// ============================================================================

async function initDWLRSystem() {
    try {
        const response = await fetch(`${API_BASE}/api/data/status`);
        if (response.ok) {
            const result = await response.json();
            const status = result.data;
            updateStatusBanner(status);
        }
    } catch (err) {
        console.warn("Could not check DWLR data status:", err);
    }

    // Populate the States dropdown
    await loadStatesList();
}


function updateStatusBanner(status) {
    const headline = document.getElementById("ingestionHeadline");
    const subline = document.getElementById("ingestionSubline");
    const dwlrStatusText = document.getElementById("dwlrStatusText");
    const dot = document.getElementById("dwlrStatusDot");

    if (status && status.dwlr_available) {
        if (headline) headline.textContent = `Official CGWB DWLR Database Active (${status.total_stations} Stations Loaded)`;
        if (subline) subline.textContent = `Indexed ${status.total_observations.toLocaleString()} groundwater observations from National Water Data Portal (NWDP).`;
        if (dwlrStatusText) dwlrStatusText.textContent = `NWDP Active (${status.total_stations} Stn)`;
        if (dot) dot.style.background = "var(--success)";

        const activeStat = document.getElementById("activeLocationsStat");
        if (activeStat) activeStat.textContent = status.total_stations;
        const activeChange = document.getElementById("activeLocationsChange");
        if (activeChange) activeChange.textContent = `${status.states_with_data} States indexed`;
    } else {
        if (headline) headline.textContent = `No Local DWLR Datasets Cached Yet`;
        if (subline) subline.textContent = `Click "Sync / Ingest NWDP Data" to download authentic Central Ground Water Board telemetry CSVs.`;
        if (dwlrStatusText) dwlrStatusText.textContent = `NWDP Cache Empty`;
        if (dot) dot.style.background = "var(--warning)";
    }
}


function toggleIngestModal() {
    const modal = document.getElementById("ingestModal");
    if (!modal) return;
    modal.style.display = modal.style.display === "none" ? "block" : "none";
}


async function triggerIngestion() {
    const keyInput = document.getElementById("ingestKeyInput");
    const btn = document.getElementById("startIngestBtn");
    const logEl = document.getElementById("ingestLog");
    const key = keyInput ? keyInput.value.trim() : "";

    if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Downloading NWDP CSVs...";
    }
    if (logEl) {
        logEl.style.display = "block";
        logEl.textContent = "Connecting to National Water Data Portal CKAN API...";
    }

    try {
        const response = await fetch(`${API_BASE}/api/data/ingest`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ key: key || "aquasense2024" })
        });

        const result = await response.json();
        if (response.ok && result.success) {
            if (logEl) {
                logEl.style.color = "var(--success)";
                logEl.textContent = `✓ Ingestion finished! Downloaded: ${result.summary.downloaded}, Cached: ${result.summary.cached}, Stations: ${result.summary.stations_indexed}, Observations: ${result.summary.observations_inserted}`;
            }
            // Refresh system status & state list
            await initDWLRSystem();
        } else {
            throw new Error(result.error || "Ingestion returned error");
        }
    } catch (err) {
        console.error("Ingestion error:", err);
        if (logEl) {
            logEl.style.color = "var(--danger)";
            logEl.textContent = `❌ Ingestion failed: ${err.message}`;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Start Ingestion";
        }
    }
}


// ============================================================================
// 4. LOCATION SEARCH WORKFLOW (State -> District -> Station)
// ============================================================================

async function loadStatesList() {
    const select = document.getElementById("stateSelect");
    if (!select) return;

    try {
        const response = await fetch(`${API_BASE}/api/locations/states`);
        if (!response.ok) throw new Error("Failed to fetch states");

        const result = await response.json();
        const states = result.data || [];

        select.innerHTML = '<option value="">-- Choose State / UT --</option>';

        // Separate states that have active DWLR data from others
        const activeStates = states.filter(s => s.has_data);
        const otherStates = states.filter(s => !s.has_data);

        if (activeStates.length > 0) {
            const grpActive = document.createElement("optgroup");
            grpActive.label = "States with Cached DWLR Telemetry";
            activeStates.forEach(s => {
                const opt = document.createElement("option");
                opt.value = s.state;
                opt.textContent = `📍 ${s.state} (${s.station_count} DWLR Stations)`;
                grpActive.appendChild(opt);
            });
            select.appendChild(grpActive);
        }

        if (otherStates.length > 0) {
            const grpOther = document.createElement("optgroup");
            grpOther.label = "All Indian States & UTs";
            otherStates.forEach(s => {
                const opt = document.createElement("option");
                opt.value = s.state;
                opt.textContent = s.state;
                grpOther.appendChild(opt);
            });
            select.appendChild(grpOther);
        }

    } catch (err) {
        console.warn("Could not load states list:", err);
    }
}


async function onStateChanged() {
    const stateSelect = document.getElementById("stateSelect");
    const districtSelect = document.getElementById("districtSelect");
    const stationSelect = document.getElementById("stationSelect");
    const viewBtn = document.getElementById("viewStationBtn");
    const countInfo = document.getElementById("stationCountInfo");

    const state = stateSelect ? stateSelect.value : "";

    // Reset dependent dropdowns
    districtSelect.innerHTML = '<option value="">-- Choose District --</option>';
    districtSelect.disabled = true;
    stationSelect.innerHTML = '<option value="">-- First Select District --</option>';
    stationSelect.disabled = true;
    if (viewBtn) viewBtn.disabled = true;
    if (countInfo) countInfo.textContent = "";

    if (!state) return;

    try {
        const response = await fetch(`${API_BASE}/api/locations/districts?state=${encodeURIComponent(state)}`);
        if (!response.ok) throw new Error("Failed to fetch districts");

        const result = await response.json();
        const districts = result.data || [];

        if (districts.length === 0) {
            districtSelect.innerHTML = '<option value="">-- No districts with DWLR data --</option>';
            if (countInfo) countInfo.textContent = `No cached DWLR stations for ${state}. You can click "Sync / Ingest NWDP Data" to load records.`;
            return;
        }

        districtSelect.innerHTML = '<option value="">-- Choose District --</option>';
        districts.forEach(d => {
            const opt = document.createElement("option");
            opt.value = d.district;
            opt.textContent = `${d.district} (${d.station_count} stations)`;
            districtSelect.appendChild(opt);
        });
        districtSelect.disabled = false;

        if (countInfo) {
            countInfo.textContent = `Found ${districts.length} districts in ${state}.`;
        }

    } catch (err) {
        console.error("Error fetching districts:", err);
    }
}


async function onDistrictChanged() {
    const stateSelect = document.getElementById("stateSelect");
    const districtSelect = document.getElementById("districtSelect");
    const stationSelect = document.getElementById("stationSelect");
    const viewBtn = document.getElementById("viewStationBtn");
    const countInfo = document.getElementById("stationCountInfo");

    const state = stateSelect ? stateSelect.value : "";
    const district = districtSelect ? districtSelect.value : "";

    stationSelect.innerHTML = '<option value="">-- Choose Station --</option>';
    stationSelect.disabled = true;
    if (viewBtn) viewBtn.disabled = true;

    if (!district) return;

    try {
        const response = await fetch(`${API_BASE}/api/locations/stations?state=${encodeURIComponent(state)}&district=${encodeURIComponent(district)}`);
        if (!response.ok) throw new Error("Failed to fetch stations");

        const result = await response.json();
        const stations = result.data || [];

        if (stations.length === 0) {
            stationSelect.innerHTML = '<option value="">-- No stations in district --</option>';
            return;
        }

        stationSelect.innerHTML = '<option value="">-- Choose DWLR Station --</option>';
        stations.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.station_id || s.id;
            const levelInfo = s.latest_water_level !== null ? ` [${s.latest_water_level} m bgl]` : "";
            opt.textContent = `${s.station_name}${levelInfo}`;
            stationSelect.appendChild(opt);
        });
        stationSelect.disabled = false;

        if (countInfo) {
            countInfo.textContent = `${stations.length} DWLR telemetry stations found in ${district}.`;
        }

    } catch (err) {
        console.error("Error fetching stations:", err);
    }
}


function onStationChanged() {
    const stationSelect = document.getElementById("stationSelect");
    const viewBtn = document.getElementById("viewStationBtn");
    const stationId = stationSelect ? stationSelect.value : "";

    if (viewBtn) {
        viewBtn.disabled = !stationId;
    }
}


function resetLocationSearch() {
    const stateSelect = document.getElementById("stateSelect");
    const districtSelect = document.getElementById("districtSelect");
    const stationSelect = document.getElementById("stationSelect");
    const viewBtn = document.getElementById("viewStationBtn");
    const countInfo = document.getElementById("stationCountInfo");
    const welcomeCard = document.getElementById("locationWelcomeCard");
    const detailSection = document.getElementById("stationDetailSection");

    if (stateSelect) stateSelect.value = "";
    if (districtSelect) {
        districtSelect.innerHTML = '<option value="">-- First Select State --</option>';
        districtSelect.disabled = true;
    }
    if (stationSelect) {
        stationSelect.innerHTML = '<option value="">-- First Select District --</option>';
        stationSelect.disabled = true;
    }
    if (viewBtn) viewBtn.disabled = true;
    if (countInfo) countInfo.textContent = "";

    if (welcomeCard) welcomeCard.style.display = "block";
    if (detailSection) detailSection.style.display = "none";

    currentStationId = null;
    currentStationData = null;
}


async function viewSelectedStation() {
    const stationSelect = document.getElementById("stationSelect");
    const stationId = stationSelect ? stationSelect.value : "";
    if (!stationId) return;

    await loadDWLRStationData(stationId);
}


// ============================================================================
// 5. LOAD & DISPLAY DWLR STATION DATA
// ============================================================================

async function loadDWLRStationData(stationId) {
    currentStationId = stationId;

    const welcomeCard = document.getElementById("locationWelcomeCard");
    const detailSection = document.getElementById("stationDetailSection");

    try {
        // 1. Fetch Station Details
        const stnRes = await fetch(`${API_BASE}/api/groundwater/station/${encodeURIComponent(stationId)}`);
        if (!stnRes.ok) throw new Error("Station detail fetch failed");
        const stnJson = await stnRes.json();
        const station = stnJson.data;
        currentStationData = station;
        currentLocation = station.station_name;

        // 2. Fetch Observations Table
        const obsRes = await fetch(`${API_BASE}/api/groundwater/observations?station_id=${encodeURIComponent(stationId)}&limit=100`);
        let observations = [];
        if (obsRes.ok) {
            const obsJson = await obsRes.json();
            observations = obsJson.data || [];
        }

        // 3. Render Station Metadata Card
        setText("stationDetailName", station.station_name);
        setText("stationAgencyBadge", `${station.agency || 'CGWB'} DWLR`);
        setText("stationStateBadge", station.state);

        const path = [station.district, station.tehsil, station.block, station.village]
            .filter(Boolean)
            .filter(v => v !== "-")
            .join(" • ");
        setText("stationDetailLocationPath", path || `${station.district}, ${station.state}`);

        const levelStr = station.latest_water_level !== null ? `${station.latest_water_level} m bgl` : "-- m bgl";
        setText("stationDetailLevel", levelStr);
        setText("stationDetailDate", station.latest_date ? `Latest Observation: ${station.latest_date}` : "Date: --");

        const coords = (station.latitude && station.longitude)
            ? `${station.latitude.toFixed(4)}° N, ${station.longitude.toFixed(4)}° E`
            : "Coordinates not recorded";
        setText("stationCoordinates", coords);

        const tehsil = [station.tehsil, station.block].filter(Boolean).filter(v => v !== "-").join(" / ") || "Not specified";
        setText("stationTehsilBlock", tehsil);

        const basin = [station.basin, station.river].filter(Boolean).filter(v => v !== "-").join(" / ") || "Not specified";
        setText("stationBasin", basin);

        setText("stationElevation", station.rl_msl ? `${station.rl_msl} m above MSL` : "N/A");

        // 4. Render Observations Table
        renderObservationsTable(observations);

        // 5. Update Overview Dashboard (Stat cards, Chart, AI Risk, Prediction)
        updateOverviewDashboardForStation(station, observations);

        // Toggle UI sections
        if (welcomeCard) welcomeCard.style.display = "none";
        if (detailSection) detailSection.style.display = "block";

    } catch (err) {
        console.error("Error loading DWLR station data:", err);
        alert("Failed to load station telemetry: " + err.message);
    }
}


function renderObservationsTable(observations) {
    const tbody = document.getElementById("observationsTableBody");
    const badge = document.getElementById("recordsCountBadge");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (badge) {
        badge.textContent = `${observations.length} records`;
    }

    if (observations.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--muted)">No recorded observations available for this station.</td></tr>`;
        return;
    }

    observations.forEach((obs, idx) => {
        const tr = document.createElement("tr");
        const level = obs.water_level !== null ? `${obs.water_level} m bgl` : "--";
        const dateStr = obs.data_acquisition_time || obs.date || "N/A";
        const agency = obs.agency || "CGWB";

        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td style="font-weight:600; color:var(--text);">${escapeHtml(dateStr)}</td>
            <td style="color:var(--primary); font-weight:700;">${level}</td>
            <td>${escapeHtml(agency)}</td>
            <td><span class="badge" style="margin:0; font-size:10px; padding:3px 8px;">Recorded DWLR</span></td>
        `;
        tbody.appendChild(tr);
    });
}


function updateOverviewDashboardForStation(station, observations) {
    // 1. Water level stat card
    currentWaterLevel = station.latest_water_level;
    const levelStr = station.latest_water_level !== null ? `${station.latest_water_level} m bgl` : "-- m bgl";
    setText("waterLevel", levelStr);
    setText("waterLevelChange", station.latest_date ? `Latest telemetry: ${station.latest_date}` : "CGWB observation");

    // 2. Subtitle
    setText("overviewLocationSubtitle", `CGWB Telemetry • ${station.station_name} (${station.district}, ${station.state})`);
    const now = new Date();
    setText("dashboardUpdatedText", `Loaded ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);

    // 3. Update Chart
    updateChartWithObservations(observations, station.station_name);

    // 4. Update AI Prediction & Risk
    if (station.latest_water_level !== null) {
        fetchPrediction(station.station_name, station.latest_water_level, 0, 0);
        fetchRiskAnalysis(station.station_name, station.latest_water_level, 0, 0);
    }
}


function scrollUpToDashboard() {
    const dash = document.getElementById("dashboard");
    if (dash) dash.scrollIntoView({ behavior: "smooth" });
}


function exportCurrentStationCSV() {
    if (!currentStationId) {
        alert("Please select a DWLR station first.");
        return;
    }
    const url = `${API_BASE}/api/export/csv?station_id=${encodeURIComponent(currentStationId)}`;
    window.open(url, "_blank");
}


// ============================================================================
// 6. PREDICTION ENGINE (POST /api/predict)
// ============================================================================

async function fetchPrediction(location, waterLevel, rainfall, temperature) {
    try {
        const payload = {
            station_id: currentStationId,
            location: location,
            water_level: waterLevel,
            rainfall: rainfall,
            temperature: temperature
        };

        const response = await fetch(`${API_BASE}/api/predict`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Prediction API error");

        const result = await response.json();
        const pred = result.data;
        updatePredictionUI(pred);

    } catch (err) {
        console.warn("Prediction API failed, using fallback:", err);
    }
}


function updatePredictionUI(pred) {
    setText("predictionValue", `${pred.predicted_groundwater_level} m bgl`);
    setText("predictionConfidenceBadge", pred.confidence_badge || `${pred.confidence_percentage}% confidence`);
    setText("predCurrentValue", `${pred.current_water_level} m bgl`);
    setText("predExpectedChange", pred.expected_change_formatted || `${pred.expected_change} m`);
    setText("predModelName", pred.model ? pred.model.split(" ")[0] + " Forest" : "Random Forest");
    setText("predForecastHorizon", pred.prediction_period || "30 Days");

    const badge = document.getElementById("predictionConfidenceBadge");
    if (badge) {
        badge.className = `risk-badge ${pred.predicted_groundwater_level > 14 ? 'risk-high' : 'risk-medium'}`;
    }
}


// ============================================================================
// 6. PREDICTION ENGINE & LIVE PREDICTION MODAL POPUP
// ============================================================================

let isPredictionRunning = false;
let predAnimFrameId = null;
let currentPredictionAbort = null;
let predLastActiveElement = null;
const CIRCLE_CIRCUMFERENCE = 534.07; // 2 * Math.PI * 85

/**
 * Updates the SVG circular progress ring and percentage label.
 * @param {number} percent - Number between 0 and 100.
 */
function setPredProgress(percent) {
    const clamped = Math.max(0, Math.min(100, percent));
    const offset = CIRCLE_CIRCUMFERENCE - (clamped / 100) * CIRCLE_CIRCUMFERENCE;

    const ring = document.getElementById("predRingProgress");
    if (ring) {
        ring.style.strokeDashoffset = offset.toFixed(2);
        if (clamped >= 100) {
            ring.classList.add("complete");
        } else {
            ring.classList.remove("complete");
        }
    }

    // Update glowing tip dot position around the circular perimeter
    const dot = document.getElementById("predRingDot");
    if (dot) {
        if (clamped <= 0.5) {
            dot.style.opacity = "0";
        } else {
            dot.style.opacity = "1";
            // With SVG transform rotate(-90deg), angle 0 is at 12 o'clock
            const angleRad = (clamped / 100) * 2 * Math.PI;
            const cx = 100 + 85 * Math.cos(angleRad);
            const cy = 100 + 85 * Math.sin(angleRad);
            dot.setAttribute("cx", cx.toFixed(2));
            dot.setAttribute("cy", cy.toFixed(2));
        }
    }

    const percentEl = document.getElementById("predPercent");
    if (percentEl) {
        percentEl.textContent = `${Math.round(clamped)}%`;
    }
}

/**
 * Updates the status message beneath the circular indicator.
 */
function setPredStatus(text) {
    const el = document.getElementById("predStatus");
    if (el) {
        el.textContent = text;
    }
}

/**
 * Opens the AI Prediction Modal Popup.
 */
function openPredPopup() {
    predLastActiveElement = document.activeElement;

    const overlay = document.getElementById("predPopupOverlay");
    const progressContainer = document.getElementById("predProgressContainer");
    const resultsContainer = document.getElementById("predResults");
    const errorContainer = document.getElementById("predError");
    const aiPulse = document.getElementById("predAiPulse");
    const statusEl = document.getElementById("predStatus");

    if (progressContainer) progressContainer.style.display = "block";
    if (aiPulse) aiPulse.style.display = "flex";
    if (statusEl) statusEl.style.display = "block";
    if (resultsContainer) resultsContainer.style.display = "none";
    if (errorContainer) errorContainer.style.display = "none";

    setPredProgress(0);
    setPredStatus("Connecting to DWLR telemetry database...");

    if (overlay) {
        overlay.classList.add("active");
        overlay.focus();
    }
    document.body.style.overflow = "hidden";
}

/**
 * Closes the AI Prediction Modal Popup.
 * @param {boolean} viewInDashboard - Whether to scroll to and highlight the dashboard prediction card.
 */
function closePredPopup(viewInDashboard = false) {
    if (isPredictionRunning) {
        if (currentPredictionAbort) {
            try { currentPredictionAbort.abort(); } catch (_) {}
        }
        if (predAnimFrameId) {
            cancelAnimationFrame(predAnimFrameId);
            predAnimFrameId = null;
        }
        isPredictionRunning = false;
    }

    const overlay = document.getElementById("predPopupOverlay");
    if (overlay) {
        overlay.classList.remove("active");
    }
    document.body.style.overflow = "";

    const btn = document.getElementById("runLivePredictionBtn");
    if (btn) {
        btn.disabled = false;
        btn.style.opacity = "1";
    }

    if (predLastActiveElement && typeof predLastActiveElement.focus === "function") {
        predLastActiveElement.focus();
    }

    if (viewInDashboard) {
        const predCard = document.getElementById("prediction");
        if (predCard) {
            predCard.scrollIntoView({ behavior: "smooth", block: "center" });
            predCard.classList.remove("highlight-pulse");
            // Trigger reflow to restart animation
            void predCard.offsetWidth;
            predCard.classList.add("highlight-pulse");
            setTimeout(() => {
                predCard.classList.remove("highlight-pulse");
            }, 2500);
        }
    }
}

/**
 * Retries the prediction after an error.
 */
function retryPrediction() {
    triggerLivePrediction();
}

/**
 * Smoothly animates progress from startPercent up to 100%.
 */
function animateProgressTo100(startPercent) {
    return new Promise(resolve => {
        const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (prefersReducedMotion) {
            setPredProgress(100);
            return resolve();
        }

        const startVal = Math.max(0, startPercent);
        const duration = 320; // ms
        const startTime = performance.now();

        function step(now) {
            const elapsed = now - startTime;
            const progress = Math.min(1, elapsed / duration);
            // Ease out cubic
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const val = startVal + (100 - startVal) * easeOut;
            setPredProgress(val);

            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                setPredProgress(100);
                resolve();
            }
        }
        requestAnimationFrame(step);
    });
}

/**
 * Renders authentic prediction results inside the modal popup.
 */
function showPredictionResults(data) {
    const progressContainer = document.getElementById("predProgressContainer");
    const aiPulse = document.getElementById("predAiPulse");
    const resultsContainer = document.getElementById("predResults");
    const resultsGrid = document.getElementById("predResultsGrid");
    const resultsNote = document.getElementById("predResultsNote");
    const statusEl = document.getElementById("predStatus");

    if (progressContainer) progressContainer.style.display = "none";
    if (aiPulse) aiPulse.style.display = "none";
    if (statusEl) statusEl.style.display = "none";

    if (!resultsGrid || !resultsContainer) return;

    if (data.available === false) {
        // Honest notification when telemetry data is insufficient for ML prediction
        resultsGrid.innerHTML = `
            <div class="pred-result-item highlight" style="border-color: rgba(245, 199, 107, 0.4);">
                <div class="pred-result-label" style="color: var(--warning);">Telemetry Notice</div>
                <div class="pred-result-value" style="font-size: 15px; font-weight: 600; line-height: 1.5; color: var(--text);">
                    ${escapeHtml(data.reason || "Insufficient historical data for this station.")}
                </div>
            </div>
            <div class="pred-result-item">
                <div class="pred-result-label">Station ID</div>
                <div class="pred-result-value">${escapeHtml(data.station_id || "Selected")}</div>
            </div>
            <div class="pred-result-item">
                <div class="pred-result-label">Observations Available</div>
                <div class="pred-result-value">${escapeHtml(data.observations_available || "0")} (min 6 needed)</div>
            </div>
        `;

        if (resultsNote) {
            resultsNote.innerHTML = `
                ℹ️ <strong>DWLR Observation Notice:</strong> Select another monitoring station with more telemetry history, or sync NWDP records to view full ML forecasts.
            `;
        }
    } else {
        // Authentic prediction results from backend & ML model
        const risk = data.risk_assessment || {};
        const riskLevel = risk.risk_level || "Normal";
        const riskColor = getRiskColor(riskLevel);
        const riskBadge = risk.badge || risk.badge_label || riskLevel.toUpperCase();
        
        const changeNum = typeof data.expected_change === "number" ? data.expected_change : 0;
        let trendLabel = "Stable depth";
        let trendColor = "var(--muted)";
        if (changeNum > 0.1) {
            trendLabel = "Extraction stress (water deepening)";
            trendColor = "var(--warning)";
        } else if (changeNum < -0.1) {
            trendLabel = "Favorable recharge (water rising)";
            trendColor = "var(--success)";
        }

        const predictedLevel = data.predicted_groundwater_level !== undefined ? `${data.predicted_groundwater_level} ${data.unit || 'm'}` : "Unavailable";
        const currentLevel = data.current_water_level !== undefined ? `${data.current_water_level} m bgl` : "Unavailable";
        const expectedChange = data.expected_change_formatted || (changeNum >= 0 ? `+${changeNum} m` : `${changeNum} m`);
        const modelName = data.model || "Random Forest Regressor";
        const confidence = data.confidence_percentage ? `${data.confidence_percentage}% confidence` : (data.confidence_badge || "78% confidence");

        resultsGrid.innerHTML = `
            <div class="pred-result-item highlight">
                <div class="pred-result-label">Predicted Groundwater Level</div>
                <div class="pred-result-value">${escapeHtml(predictedLevel)}</div>
            </div>
            <div class="pred-result-item">
                <div class="pred-result-label">Current Water Level</div>
                <div class="pred-result-value">${escapeHtml(currentLevel)}</div>
            </div>
            <div class="pred-result-item">
                <div class="pred-result-label">Expected Change</div>
                <div class="pred-result-value" style="color:${trendColor}">${escapeHtml(expectedChange)}</div>
            </div>
            <div class="pred-result-item">
                <div class="pred-result-label">Forecast Horizon</div>
                <div class="pred-result-value">${escapeHtml(data.prediction_period || "Next 30 days")}</div>
            </div>
            <div class="pred-result-item">
                <div class="pred-result-label">Risk Classification</div>
                <div class="pred-result-value">
                    <span class="risk-badge" style="color:${riskColor}; background:${getRiskBadgeBg(riskLevel)}; padding:3px 9px; font-size:12px;">
                        ${escapeHtml(riskBadge)}
                    </span>
                </div>
            </div>
            <div class="pred-result-item" style="grid-column: 1 / -1;">
                <div class="pred-result-label">AI Model & Trend Analysis</div>
                <div class="pred-result-value" style="font-size:13px; font-weight:600; color:var(--text);">
                    ${escapeHtml(modelName)} • ${escapeHtml(confidence)}<br>
                    <span style="font-size:11.5px; color:${trendColor}; font-weight:500;">Trend: ${escapeHtml(trendLabel)}</span>
                </div>
            </div>
        `;

        if (resultsNote) {
            const recommendation = risk.ai_recommendation || risk.recommendation || risk.description || data.note || "";
            const stationInfo = currentLocation ? ` • Station: ${escapeHtml(currentLocation)}` : "";
            resultsNote.innerHTML = `
                <div><strong>💡 AI Recommendation:</strong> ${escapeHtml(recommendation)}</div>
                <div style="margin-top:6px; font-size:11px; opacity:0.8; color:var(--muted);">
                    Data Source: ${escapeHtml(data.data_source || "CGWB DWLR Telemetry")}${stationInfo}
                </div>
            `;
        }
    }

    resultsContainer.style.display = "block";
}

/**
 * Displays error state inside the modal popup.
 */
function showPredictionError(errorMessage) {
    const progressContainer = document.getElementById("predProgressContainer");
    const aiPulse = document.getElementById("predAiPulse");
    const statusEl = document.getElementById("predStatus");
    const resultsContainer = document.getElementById("predResults");
    const errorContainer = document.getElementById("predError");
    const errorMsgEl = document.getElementById("predErrorMessage");

    if (progressContainer) progressContainer.style.display = "none";
    if (aiPulse) aiPulse.style.display = "none";
    if (statusEl) statusEl.style.display = "none";
    if (resultsContainer) resultsContainer.style.display = "none";

    if (errorMsgEl) {
        errorMsgEl.textContent = errorMessage || "Unable to complete prediction. Please verify that the Flask backend is running on port 5000.";
    }

    if (errorContainer) {
        errorContainer.style.display = "block";
    }
}

/**
 * Updates the risk section of the dashboard if the prediction includes risk classification.
 */
function updateRiskUIFromPrediction(risk) {
    if (!risk) return;
    if (risk.risk_level) {
        currentRiskLevel = risk.risk_level;
        setText("riskStat", risk.risk_level);
        setText("riskStatChange", risk.badge || risk.risk_level);
        const riskStatChangeEl = document.getElementById("riskStatChange");
        if (riskStatChangeEl) {
            riskStatChangeEl.style.color = getRiskColor(risk.risk_level);
        }
        setText("riskLevelName", risk.risk_level);
        setText("riskLevelBadge", risk.badge || risk.risk_level.toUpperCase());
    }
    if (risk.description) setText("riskDescription", risk.description);
    if (risk.ai_recommendation || risk.recommendation) {
        setText("riskRecommendation", risk.ai_recommendation || risk.recommendation);
    }
    const bar = document.getElementById("riskProgressBar");
    if (bar && (risk.score !== undefined || risk.score_percentage)) {
        bar.style.width = risk.score_percentage || `${risk.score}%`;
        bar.style.background = (risk.risk_level === "High" || risk.risk_level === "Critical")
            ? "linear-gradient(90deg, var(--warning), var(--danger))"
            : "linear-gradient(90deg, var(--success), var(--warning))";
    }
    const badge = document.getElementById("riskLevelBadge");
    if (badge && risk.risk_level) {
        badge.style.color = risk.color_token || getRiskColor(risk.risk_level);
        badge.style.background = getRiskBadgeBg(risk.risk_level);
    }
}

/**
 * Main handler triggered when user clicks "Run Live AI Prediction (API)".
 */
async function triggerLivePrediction() {
    // Prevent duplicate prediction requests while one is already running
    if (isPredictionRunning) return;

    isPredictionRunning = true;
    currentPredictionAbort = new AbortController();

    const btn = document.getElementById("runLivePredictionBtn");
    if (btn) {
        btn.disabled = true;
        btn.style.opacity = "0.7";
    }

    // 1. Open popup immediately
    openPredPopup();

    // Prepare authentic payload
    const payload = {};
    if (currentStationId) {
        payload.station_id = currentStationId;
    }
    if (currentWaterLevel !== null && currentWaterLevel !== undefined) {
        payload.water_level = currentWaterLevel;
    } else {
        payload.water_level = 12.4; // Default baseline depth
    }
    if (currentLocation) {
        payload.location = currentLocation;
    }

    // Animation state
    let displayedProgress = 0;
    let isRequestComplete = false;
    const startTime = performance.now();

    // Relevant status messages mapping accurately to backend operations
    const statusSteps = [
        { threshold: 0, text: "Connecting to DWLR telemetry database..." },
        { threshold: 18, text: "Collecting station groundwater observations..." },
        { threshold: 38, text: "Analyzing historical groundwater trends..." },
        { threshold: 58, text: "Evaluating environmental and recharge conditions..." },
        { threshold: 74, text: "Running Random Forest regression model..." },
        { threshold: 86, text: "Calculating groundwater risk and recharge dynamics..." }
    ];

    const updateEstimatedProgress = (currentTime) => {
        if (!isPredictionRunning) return;

        if (!isRequestComplete) {
            const elapsed = currentTime - startTime;
            // Realistic asymptotic easing towards 89%:
            // Moves smoothly towards 89%, never reaching 100% while waiting
            const targetAsymptotic = 89 * (1 - Math.exp(-elapsed / 1100));
            displayedProgress += (targetAsymptotic - displayedProgress) * 0.12;
            if (displayedProgress > 89.4) displayedProgress = 89.4;

            setPredProgress(displayedProgress);

            // Update status text based on progress
            for (let i = statusSteps.length - 1; i >= 0; i--) {
                if (displayedProgress >= statusSteps[i].threshold) {
                    setPredStatus(statusSteps[i].text);
                    break;
                }
            }

            predAnimFrameId = requestAnimationFrame(updateEstimatedProgress);
        }
    };

    predAnimFrameId = requestAnimationFrame(updateEstimatedProgress);

    try {
        // Send prediction request to existing Flask backend
        const timeoutId = setTimeout(() => {
            currentPredictionAbort.abort();
        }, 15000);

        const response = await fetch(`${API_BASE}/api/predict`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            signal: currentPredictionAbort.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            let errorMsg = `Server error (HTTP ${response.status})`;
            try {
                const errData = await response.json();
                if (errData && errData.error) errorMsg = errData.error;
            } catch (_) {}
            throw new Error(errorMsg);
        }

        const json = await response.json();
        if (!json.success || !json.data) {
            throw new Error(json.error || "Prediction API returned unsuccessful response.");
        }

        const data = json.data;
        isRequestComplete = true;
        if (predAnimFrameId) {
            cancelAnimationFrame(predAnimFrameId);
            predAnimFrameId = null;
        }

        // Advance to 100% smoothly
        setPredStatus("Finalizing your prediction...");
        await animateProgressTo100(displayedProgress);

        // Display brief success state
        setPredProgress(100);
        setPredStatus("✓ Prediction complete!");

        // Update dashboard UI in background
        if (data.available !== false) {
            updatePredictionUI(data);
            if (data.risk_assessment) {
                updateRiskUIFromPrediction(data.risk_assessment);
            }
        }

        // Brief delay for user satisfaction at 100%
        await new Promise(r => setTimeout(r, 650));

        if (!isPredictionRunning) return;

        // Display prediction results
        showPredictionResults(data);

    } catch (err) {
        if (err.name === "AbortError") {
            console.log("Prediction request aborted.");
            return;
        }

        console.error("Live prediction error:", err);
        isRequestComplete = true;
        if (predAnimFrameId) {
            cancelAnimationFrame(predAnimFrameId);
            predAnimFrameId = null;
        }

        showPredictionError(err.message || "Failed to communicate with prediction server.");
    } finally {
        isPredictionRunning = false;
        if (btn) {
            btn.disabled = false;
            btn.style.opacity = "1";
        }
    }
}

/**
 * Initializes accessibility and keyboard events for the prediction popup.
 */
function initPredictionPopupEvents() {
    const overlay = document.getElementById("predPopupOverlay");
    const closeBtn = document.getElementById("predPopupClose");

    if (closeBtn) {
        closeBtn.addEventListener("click", () => closePredPopup(false));
    }

    if (overlay) {
        overlay.addEventListener("click", (e) => {
            // Prevent accidental interaction while prediction is running
            if (e.target === overlay && !isPredictionRunning) {
                closePredPopup(false);
            }
        });
    }

    document.addEventListener("keydown", (e) => {
        const modal = document.getElementById("predPopupOverlay");
        if (!modal || !modal.classList.contains("active")) return;

        if (e.key === "Escape") {
            e.preventDefault();
            closePredPopup(false);
        } else if (e.key === "Tab") {
            trapPopupFocus(e, modal);
        }
    });
}

/**
 * Focus trap helper for accessible keyboard navigation.
 */
function trapPopupFocus(e, modal) {
    const focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey && document.activeElement === first) {
        last.focus();
        e.preventDefault();
    } else if (!e.shiftKey && document.activeElement === last) {
        first.focus();
        e.preventDefault();
    }
}


// ============================================================================
// 7. RISK ASSESSMENT (GET /api/risk)
// ============================================================================

async function fetchRiskAnalysis(location, waterLevel, rainfall, temperature) {
    try {
        const url = `${API_BASE}/api/risk?location=${encodeURIComponent(location)}&water_level=${waterLevel}&station_id=${encodeURIComponent(currentStationId || '')}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error("Risk API error");

        const result = await response.json();
        const risk = result.data;

        currentRiskLevel = risk.risk_level;
        setText("riskStat", risk.risk_level);
        setText("riskStatChange", risk.status || risk.risk_level);
        const riskStatChangeEl = document.getElementById("riskStatChange");
        if (riskStatChangeEl) {
            riskStatChangeEl.style.color = getRiskColor(risk.risk_level);
        }

        setText("riskLevelName", risk.risk_level);
        setText("riskLevelBadge", risk.badge || risk.risk_level.toUpperCase());
        setText("riskDescription", risk.description);
        setText("riskRecommendation", risk.ai_recommendation);

        const bar = document.getElementById("riskProgressBar");
        if (bar) {
            bar.style.width = risk.score_percentage || `${risk.score}%`;
            bar.style.background = risk.risk_level === "High" || risk.risk_level === "Critical"
                ? "linear-gradient(90deg, var(--warning), var(--danger))"
                : "linear-gradient(90deg, var(--success), var(--warning))";
        }

        const badge = document.getElementById("riskLevelBadge");
        if (badge) {
            badge.style.color = risk.color_token || getRiskColor(risk.risk_level);
            badge.style.background = getRiskBadgeBg(risk.risk_level);
        }

    } catch (err) {
        console.warn("Risk API request failed:", err);
    }
}


let chatHistory = [];

function askAiAboutCurrentRisk() {
    openChat();
    let q = "";

    if (currentStationData) {
        const stn = currentStationData;
        const levelStr = stn.latest_water_level !== null ? `${stn.latest_water_level} m bgl` : "unrecorded";
        const dateStr = stn.latest_date || "date unavailable";
        const locPath = [stn.station_name, stn.district, stn.state].filter(Boolean).join(", ");

        q = `Why is groundwater risk in ${locPath} classified as ${currentRiskLevel}? ` +
            `The latest DWLR observation is ${levelStr} recorded on ${dateStr}. ` +
            `Please explain the underlying factors driving this assessment and recommended recharge interventions.`;
    } else if (currentLocation && currentLocation !== "All India") {
        const levelStr = currentWaterLevel !== null ? `${currentWaterLevel} m bgl` : "unrecorded";
        q = `Why is groundwater risk in ${currentLocation} classified as ${currentRiskLevel}? ` +
            `The current water level is ${levelStr}. What are the primary concerns and recommended recharge measures?`;
    } else {
        q = `How does AquaSense AI evaluate groundwater risk levels (Safe, Moderate, High, Critical), ` +
            `and what data factors determine if a station's risk is undefined or requires monitoring?`;
    }

    const input = document.getElementById("chatInput");
    if (input) {
        input.value = q;
        sendMessage();
    }
}


// ============================================================================
// 8. AI CHAT ASSISTANT (Powered by Google Gemini API)
// ============================================================================

function toggleChat() {
    const chat = document.getElementById("chatWindow");
    if (!chat) return;

    if (chat.style.display === "flex") {
        chat.style.display = "none";
    } else {
        chat.style.display = "flex";
        const input = document.getElementById("chatInput");
        if (input) input.focus();
    }
}


function openChat() {
    const chat = document.getElementById("chatWindow");
    if (!chat) return;

    chat.style.display = "flex";
    const input = document.getElementById("chatInput");
    if (input) input.focus();
}


function clearChatHistory() {
    chatHistory = [];
    const container = document.getElementById("chatMessages");
    if (container) {
        container.innerHTML = `
            <div class="message bot-message">
                👋 Conversation reset. I'm <strong>Aqua AI</strong>, your groundwater hydrologist assistant powered by <strong>Gemini Generative AI</strong>.<br><br>
                Ask me any question about groundwater conservation, DWLR telemetry, aquifers, risk analysis, or ML predictions! 🌊
            </div>
        `;
    }
}


function handleEnter(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}


function askQuick(question) {
    openChat();
    const input = document.getElementById("chatInput");
    if (input) {
        input.value = question;
        sendMessage();
    }
}


async function sendMessage() {
    const input = document.getElementById("chatInput");
    const sendBtn = document.querySelector(".send-btn");
    if (!input) return;

    const message = input.value.trim();
    if (!message) return;

    // Render user bubble
    addMessage(escapeHtml(message), "user-message");
    input.value = "";

    // Record turn in client history
    chatHistory.push({ role: "user", content: message });

    // Show temporary thinking indicator
    const thinkingId = "thinking-" + Date.now();
    addThinkingBubble(thinkingId);

    // Disable input while generating
    input.disabled = true;
    if (sendBtn) sendBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                history: chatHistory.slice(-10),
                station_id: currentStationId,
                location: currentLocation
            })
        });

        removeThinkingBubble(thinkingId);

        const data = await response.json();

        if (data.success && data.response) {
            // Append assistant reply to conversation history
            chatHistory.push({ role: "model", content: data.response });
            addMessage(formatBotResponse(data.response), "bot-message");
        } else {
            // Display clear error notification if service fails or key missing
            const errorMsg = data.error || `Server responded with status ${response.status}`;
            const isKeyIssue = data.error_type === "api_client_error" || errorMsg.includes("API key");

            if (isKeyIssue) {
                addMessage(
                    `<div style="color:var(--warning); line-height:1.5;">` +
                    `<strong>⚠️ Aqua AI Service Notice:</strong><br>${escapeHtml(errorMsg)}` +
                    `<div style="margin-top:12px; padding:12px; background:rgba(0,0,0,0.3); border-radius:12px; border:1px solid rgba(245,199,107,0.3); text-align:left;">` +
                    `<div style="font-size:11px; color:var(--text); margin-bottom:8px; font-weight:600;">` +
                    `🔑 Quick Activation: Paste your Gemini API key below or enter it into <code>.env</code>:` +
                    `</div>` +
                    `<div style="display:flex; gap:6px;">` +
                    `<input type="password" id="quickApiKeyInput" placeholder="Paste AI Studio Key (AIzaSy...)" style="flex:1; padding:7px 10px; font-size:11px; border-radius:8px; border:1px solid var(--border); background:rgba(255,255,255,0.06); color:var(--text); outline:none;">` +
                    `<button onclick="saveQuickApiKey()" style="padding:7px 14px; font-size:11px; font-weight:700; border-radius:8px; background:var(--primary); color:#071611; border:none; cursor:pointer;">Activate</button>` +
                    `</div>` +
                    `<div style="font-size:10px; color:var(--muted); margin-top:8px;">` +
                    `Get a free key in 30 seconds at <a href="https://aistudio.google.com/" target="_blank" style="color:var(--secondary); text-decoration:underline;">aistudio.google.com</a>` +
                    `</div>` +
                    `</div>` +
                    `</div>`,
                    "bot-message"
                );
            } else {
                addMessage(
                    `<div style="color:var(--danger); line-height:1.5;">` +
                    `<strong>⚠️ Aqua AI Service Notice:</strong><br>${escapeHtml(errorMsg)}` +
                    `</div>`,
                    "bot-message"
                );
            }
        }

    } catch (err) {
        console.error("Chat communication failure:", err);
        removeThinkingBubble(thinkingId);

        addMessage(
            `<div style="color:var(--danger); line-height:1.5;">` +
            `<strong>⚠️ Connection Error:</strong><br>Unable to communicate with the AquaSense AI backend (${escapeHtml(err.message)}). Please verify that the Flask server is running on http://127.0.0.1:5000.` +
            `</div>`,
            "bot-message"
        );
    } finally {
        input.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        input.focus();
    }
}


function addMessage(formattedHtml, className) {
    const container = document.getElementById("chatMessages");
    if (!container) return;

    const msg = document.createElement("div");
    msg.className = "message " + className;
    msg.innerHTML = formattedHtml;

    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}


function addThinkingBubble(id) {
    const container = document.getElementById("chatMessages");
    if (!container) return;

    const msg = document.createElement("div");
    msg.id = id;
    msg.className = "message bot-message thinking-bubble";
    msg.style.opacity = "0.75";
    msg.innerHTML = `<span>Thinking with Gemini AI... 💭</span>`;

    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}


function removeThinkingBubble(id) {
    const el = document.getElementById(id);
    if (el && el.parentNode) {
        el.parentNode.removeChild(el);
    }
}


function formatBotResponse(text) {
    if (!text) return "";

    return text
        // Headers
        .replace(/^### (.*$)/gim, '<div style="font-weight:700; color:var(--primary); font-size:13px; margin:8px 0 4px 0;">$1</div>')
        .replace(/^## (.*$)/gim, '<div style="font-weight:700; color:var(--text); font-size:14px; margin:10px 0 6px 0;">$1</div>')
        // Bold
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // Bullet points
        .replace(/^[•\-\*]\s+(.*$)/gim, '&bull; $1')
        // Line breaks
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
}



async function saveQuickApiKey() {
    const input = document.getElementById("quickApiKeyInput");
    const key = input ? input.value.trim() : "";
    if (!key) {
        alert("Please paste your Gemini API key (starting with AIzaSy...).");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/config/api-key`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ gemini_api_key: key })
        });

        const data = await response.json();
        if (data.success) {
            addMessage(
                `<div style="color:var(--success); line-height:1.5;">` +
                `✓ <strong>Gemini API Key Successfully Activated!</strong><br>` +
                `Aqua AI is now connected to the Gemini Generative AI model. Try asking any question or click a suggested topic below.` +
                `</div>`,
                "bot-message"
            );
        } else {
            alert(data.error || "Failed to save key");
        }
    } catch (err) {
        alert("Connection error while saving key: " + err.message);
    }
}


// ============================================================================
// 9. HELPER UTILITIES
// ============================================================================

function setText(elementId, text) {
    const el = document.getElementById(elementId);
    if (el) el.textContent = text;
}

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = String(text);
    return div.innerHTML;
}

function getRiskColor(level) {
    const l = (level || "").toLowerCase();
    if (l === "low" || l === "safe") return "var(--success)";
    if (l === "medium" || l === "moderate") return "var(--warning)";
    return "var(--danger)";
}

function getRiskBadgeBg(level) {
    const l = (level || "").toLowerCase();
    if (l === "low" || l === "safe") return "rgba(72,213,151,.1)";
    if (l === "medium" || l === "moderate") return "rgba(245,199,107,.1)";
    return "rgba(255,107,107,.1)";
}
