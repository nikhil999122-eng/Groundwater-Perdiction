"""
AI Groundwater Assistant Engine (Powered by Google Gemini API)
AquaSense AI - BTech Mini Project

Integrates the official google-genai SDK to provide intelligent, natural-language
answers grounded in real CGWB DWLR telemetry, SQLite monitoring observations,
and Machine Learning risk and prediction models.
"""

import os
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

# Official Google GenAI SDK
try:
    from google import genai
    from google.genai import types, errors
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from backend.cgwb_data import (
    get_station_detail,
    get_station_observations,
    get_stations_in_district,
    get_districts_in_state,
    get_db,
)
from backend.database import get_latest_record, get_locations
from backend.prediction import predict_water_level
from backend.risk_analysis import classify_groundwater_risk

logger = logging.getLogger(__name__)

# Supported model defaults
DEFAULT_MODEL = "gemini-2.5-flash"

AQUA_AI_SYSTEM_INSTRUCTION = """You are Aqua AI, the official Senior Groundwater Hydrologist and Environmental AI Specialist for AquaSense AI — an AI-Powered Web-Based Groundwater Monitoring and Prediction System.

Your audience includes students, citizens, farmers, researchers, and municipal planners. Explain concepts in clear, educational, and accessible language with structured bullet points and bold headers.

### CORE GROUNDWATER KNOWLEDGE & HYDROLOGICAL STANDARDS:
1. **Measurement Units (m bgl)**:
   - Groundwater level depth is recorded in **m bgl (meters below ground level)**.
   - **Crucial Rule**: A LOWER value (e.g., 3.5 m bgl) means water is CLOSER to the surface (healthier water table).
   - A HIGHER value (e.g., 19.8 m bgl) means the water table is DEEP underground (depleted aquifer).
   - Always clarify this distinction so users never confuse deeper depletion with higher water volume.

2. **Official Government Telemetry (CGWB via NWDP)**:
   - Telemetry data is collected by automated Digital Water Level Recorders (DWLRs) deployed in piezometers by the Central Ground Water Board (CGWB), Ministry of Jal Shakti, Government of India, published through the National Water Data Portal (NWDP).
   - Always state observation dates and station names when answering queries about specific locations.
   - Clearly distinguish between:
     (a) **Verified historical observations** (recorded by CGWB DWLR sensors),
     (b) **AI Model Predictions** (forecasted 30-day depths via Random Forest Regressor), and
     (c) **General hydrological science**.
   - NEVER fabricate or assume live current readings if data is unavailable. State limitations honestly.

3. **Explaining Risk Classifications & Undefined States**:
   - AquaSense AI categorizes risk into tiers: Safe/Low (<8m), Moderate/Medium (8-14m), High (14-20m), and Critical (>20m), weighted by seasonal rate of decline.
   - Explain limitations: this is an indicative academic screening model, not a statutory CGWB notification. Local aquifer geometry, rock type (alluvial vs hard rock), and specific yield vary locally.
   - If risk or prediction is **Undefined** or **Unavailable** for a station, explain the exact verified reason:
     - e.g. Single calibration reading without a multi-month time series to compute rate of decline.
     - e.g. Missing extraction/rainfall parameters.
     - e.g. Station records not yet cached for that district in the local database.

4. **Causes of Groundwater Depletion**:
   - Heavy tubewell extraction for water-intensive monocultures (paddy, sugarcane, wheat) in semi-arid zones.
   - Concrete urbanization and paved surfaces preventing monsoon infiltration into shallow aquifers.
   - Over-pumping enabled by subsidized/unmetered agricultural electricity.
   - Erratic monsoon precipitation and prolonged dry spells.

5. **Conservation & Recharge Interventions**:
   - **Rainwater Harvesting (RWH)**: Rooftop catchment, silt filters, and percolation recharge shafts.
   - **Agricultural Interventions**: Micro-irrigation (drip & sprinkler saving 40-60% water), soil moisture sensors, mulching, and crop diversification (millets, pulses, oilseeds).
   - **Community Structures**: Check dams, recharge trenches, contour bunds, and revitalizing traditional water bodies (stepwells, ponds).
   - **Household Conservation**: Aerators, fixing leaks, recycling greywater from RO units and showers for non-potable uses.

6. **Contamination & Water Quality**:
   - Agricultural runoff (nitrate enrichment, pesticide leaching).
   - Industrial effluent discharge (heavy metals like chromium, lead).
   - Domestic sewage leaks (bacterial/coliform pathogens).
   - Geogenic contamination: Naturally occurring fluoride and salinity in arid belts, arsenic in the Gangetic plain.

Always be polite, direct, concise, and scientifically accurate. Use the provided [VERIFIED SYSTEM CONTEXT] whenever answering questions about specific locations or stations.
"""


def get_gemini_client() -> Tuple[Optional[Any], Optional[str]]:
    """
    Initializes and returns the google-genai Client if GEMINI_API_KEY is configured.
    Returns (client, error_message).
    """
    if not GENAI_AVAILABLE:
        return None, (
            "The 'google-genai' SDK is not installed. "
            "Please run 'pip install google-genai' in your environment."
        )

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key.strip() in ("", "your_gemini_api_key_here", "your_api_key_here"):
        return None, (
            "Gemini API key is not configured. Please add your GEMINI_API_KEY "
            "to the .env file in the project directory. "
            "You can obtain a free API key at https://aistudio.google.com/."
        )

    try:
        client = genai.Client(api_key=api_key.strip())
        return client, None
    except Exception as e:
        return None, f"Failed to initialize Gemini client: {str(e)}"


def build_groundwater_context(
    user_message: str,
    station_id: Optional[Any] = None,
    location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves verified groundwater data from SQLite database to ground the AI model:
    - Specific station detail and recent observations
    - State/district level DWLR station summaries
    - Legacy city observations (Ahmedabad, Delhi, Jaipur, etc.)
    - Risk assessment parameters and ML prediction
    """
    context_lines = []
    metadata = {}
    msg_lower = (user_message or "").lower()

    # 1. Target Station Context
    target_station = None
    if station_id:
        try:
            target_station = get_station_detail(int(station_id))
        except (ValueError, TypeError):
            pass

    # If no station_id passed, attempt to detect station from message
    if not target_station:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, station_name, state, district FROM dwlr_stations")
        stations = cursor.fetchall()
        for s in stations:
            s_name = s["station_name"].lower()
            if s_name in msg_lower or (len(s_name) > 6 and s_name[:10] in msg_lower):
                target_station = get_station_detail(s["id"])
                break

    if target_station:
        metadata["station_id"] = target_station["id"]
        metadata["station_name"] = target_station["station_name"]
        metadata["state"] = target_station["state"]
        metadata["district"] = target_station["district"]

        obs_records = get_station_observations(target_station["id"], limit=15)
        metadata["observations_count"] = target_station.get("total_observations", len(obs_records))

        latest_level = target_station.get("latest_water_level")
        latest_date = target_station.get("latest_date")
        earliest_date = target_station.get("earliest_observation")

        context_lines.append("=== VERIFIED STATION TELEMETRY (CGWB DWLR) ===")
        context_lines.append(f"• Station: {target_station['station_name']} (ID: {target_station['id']})")
        context_lines.append(f"• Agency: {target_station.get('agency', 'CGWB')} Digital Water Level Recorder (DWLR)")
        context_lines.append(f"• Administrative: State: {target_station['state']} | District: {target_station['district']} | Tehsil/Block: {target_station.get('tehsil') or target_station.get('block') or '-'}")
        if target_station.get("latitude") and target_station.get("longitude"):
            context_lines.append(f"• Coordinates: {target_station['latitude']:.4f}° N, {target_station['longitude']:.4f}° E | Elevation (RL_MSL): {target_station.get('rl_msl') or 'N/A'} m")
        if target_station.get("basin") and target_station.get("basin") != "-":
            context_lines.append(f"• Hydrographic Basin / River: {target_station['basin']} / {target_station.get('river', '-')}")

        context_lines.append(f"• Total Cached Observations in DB: {target_station.get('total_observations', len(obs_records))}")
        if latest_level is not None:
            context_lines.append(f"• Latest Measured Water Level: {latest_level} m bgl (meters below ground level)")
            context_lines.append(f"• Latest Observation Timestamp: {latest_date or 'N/A'}")
        else:
            context_lines.append("• Latest Water Level: Not recorded / No valid observation readings.")

        if earliest_date and earliest_date != latest_date:
            context_lines.append(f"• Earliest Observation Timestamp: {earliest_date}")

        # Trend and Risk status
        if latest_level is not None:
            risk_calc = classify_groundwater_risk(water_level=latest_level, expected_change=0.0)
            context_lines.append(f"• Calculated Risk Classification: {risk_calc['risk_level']} (Score: {risk_calc['score']}/100, Badge: {risk_calc['badge']})")
            context_lines.append(f"• System Recommendation: {risk_calc['ai_recommendation']}")
        else:
            context_lines.append("• Risk Classification: Undefined / Unavailable (insufficient valid water level measurements).")

        # Explain if data is sparse (e.g., Bhiwani single reading)
        if target_station.get("total_observations", len(obs_records)) <= 1:
            context_lines.append("• Data Limitation Note: This station has only 1 historical observation record in the local cache. Without a multi-date seasonal time-series, historical depletion rate and trend cannot be definitively calculated.")

        if obs_records:
            context_lines.append("\nRecent Telemetry Readings (Newest to Oldest):")
            for r in obs_records[:5]:
                context_lines.append(f"  - [{r['observation_time']}] {r['groundwater_level_m']} m bgl ({r.get('data_quality', 'telemetry')})")

    # 2. Location/State/District Query Detection
    # If the user asks about a specific state or district (e.g. "Haryana", "Bhiwani", "Patna", "Punjab")
    states_mentioned = [st for st in ["Haryana", "Punjab", "Bihar", "Delhi", "Gujarat", "Rajasthan", "Karnataka"] if st.lower() in msg_lower]
    districts_mentioned = [d for d in ["Bhiwani", "Kaithal", "Kurukshetra", "Patna", "Sangrur", "Ludhiana", "Patiala", "North"] if d.lower() in msg_lower]

    if not target_station and (states_mentioned or districts_mentioned or location):
        target_state = states_mentioned[0] if states_mentioned else location
        target_district = districts_mentioned[0] if districts_mentioned else None

        conn = get_db()
        cursor = conn.cursor()

        if target_district:
            cursor.execute("""
                SELECT s.id, s.station_name, s.state, s.district,
                       COUNT(o.id) as obs_count,
                       MAX(o.observation_time) as latest_date,
                       (SELECT o2.groundwater_level_m FROM dwlr_observations o2
                        WHERE o2.station_id = s.id ORDER BY o2.observation_time DESC LIMIT 1) as latest_gwl
                FROM dwlr_stations s
                LEFT JOIN dwlr_observations o ON o.station_id = s.id
                WHERE LOWER(s.district) = LOWER(?)
                GROUP BY s.id
            """, (target_district,))
            dist_stations = cursor.fetchall()

            context_lines.append(f"=== VERIFIED DATABASE LOOKUP FOR DISTRICT: {target_district} ===")
            if dist_stations:
                context_lines.append(f"Found {len(dist_stations)} monitoring station(s) in {target_district}:")
                for ds in dist_stations:
                    context_lines.append(f"• Station: {ds['station_name']} (ID: {ds['id']}, State: {ds['state']})")
                    context_lines.append(f"  - Records: {ds['obs_count']} | Latest: {ds['latest_gwl']} m bgl on {ds['latest_date']}")
                    if ds["obs_count"] <= 1:
                        context_lines.append(f"  - Reason for Undefined/Limited Risk: Only {ds['obs_count']} record in local database snapshot; dynamic multi-month time series is required to calculate decline rate.")
            else:
                context_lines.append(f"No DWLR stations currently indexed in local cache for district '{target_district}'.")

        elif target_state:
            cursor.execute("""
                SELECT s.district, COUNT(DISTINCT s.id) as station_count
                FROM dwlr_stations s
                WHERE LOWER(s.state) = LOWER(?)
                GROUP BY s.district
            """, (target_state,))
            state_dists = cursor.fetchall()

            context_lines.append(f"=== VERIFIED DATABASE LOOKUP FOR STATE: {target_state} ===")
            if state_dists:
                context_lines.append(f"Cached DWLR stations in {target_state} are located across districts:")
                for sd in state_dists:
                    context_lines.append(f"• {sd['district']}: {sd['station_count']} DWLR station(s)")
            else:
                context_lines.append(f"No DWLR telemetry stations currently cached in local database for state '{target_state}'.")

    # 3. Check Legacy City Records (e.g. Ahmedabad, Bengaluru, Delhi, Jaipur)
    legacy_cities = ["Ahmedabad", "Bengaluru", "Chennai", "Delhi", "Hyderabad", "Jaipur", "Lucknow", "Kolkata"]
    for city in legacy_cities:
        if city.lower() in msg_lower or (location and city.lower() == location.lower()):
            rec = get_latest_record(city)
            if rec:
                context_lines.append(f"=== REFERENCE OBSERVATION FOR {city.upper()} ===")
                context_lines.append(f"• Location: {rec['location']} ({rec['state']})")
                context_lines.append(f"• Observation Date: {rec['date']}")
                context_lines.append(f"• Water Level Depth: {rec['water_level']} meters below ground")
                context_lines.append(f"• Monthly Rainfall: {rec['rainfall']} mm | Temperature: {rec['temperature']}°C")
                context_lines.append(f"• Extraction Rate vs Recharge Rate: {rec['extraction_rate']} vs {rec['recharge_rate']} index")
                context_lines.append(f"• Evaluated Risk Tier: {rec['risk_level']}")
                context_lines.append("• Source: Historical reference dataset (AquaSense data repository)")
                break

    return {
        "context_text": "\n".join(context_lines) if context_lines else "",
        "metadata": metadata
    }


def get_ai_response(
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None,
    station_id: Optional[Any] = None,
    context_location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main generative AI response generator using Google Gemini API (google-genai SDK).

    Accepts:
    - user_message: Current question from user
    - history: Optional list of previous conversation turns [{'role': 'user'|'model', 'content': '...'}]
    - station_id: Optional selected DWLR station ID
    - context_location: Optional selected location/state/district
    """
    clean_msg = (user_message or "").strip()
    if not clean_msg:
        return {
            "success": False,
            "error": "User message cannot be empty.",
            "error_type": "empty_message"
        }

    # 1. Initialize Gemini Client
    client, err = get_gemini_client()
    if err or not client:
        return {
            "success": False,
            "error": err,
            "error_type": "api_client_error"
        }

    # 2. Extract verified data from SQLite database
    grounding = build_groundwater_context(
        user_message=clean_msg,
        station_id=station_id,
        location=context_location
    )
    grounding_text = grounding.get("context_text", "")

    # 3. Assemble Conversation Contents for Gemini
    contents = []

    # Include sanitized previous history (up to last 10 messages)
    if history and isinstance(history, list):
        for turn in history[-10:]:
            role = turn.get("role", "user")
            # Map role: 'assistant' -> 'model'
            gemini_role = "model" if role in ("assistant", "model", "bot") else "user"
            text_content = (turn.get("content") or turn.get("text") or "").strip()
            if text_content:
                contents.append(
                    types.Content(
                        role=gemini_role,
                        parts=[types.Part.from_text(text=text_content)]
                    )
                )

    # Prepare final user query with verified database context
    final_user_text = clean_msg
    if grounding_text:
        final_user_text = f"{clean_msg}\n\n[VERIFIED SYSTEM CONTEXT FROM AQUASENSE DATABASE]:\n{grounding_text}"

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=final_user_text)]
        )
    )

    # 4. Resolve Model Name
    model_name = os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
    # Strip any extraneous quotes if entered in .env
    model_name = model_name.strip("\"' ")

    # 5. Generate Response via google-genai SDK
    try:
        config = types.GenerateContentConfig(
            system_instruction=AQUA_AI_SYSTEM_INSTRUCTION,
            temperature=0.4,
            max_output_tokens=1200,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )

        reply_text = response.text or ""
        if not reply_text:
            return {
                "success": False,
                "error": "Gemini returned an empty response. Please try rephrasing your question.",
                "error_type": "empty_model_response"
            }

        return {
            "success": True,
            "response": reply_text.strip(),
            "model": model_name,
            "source": "gemini_generative_ai",
            "context_included": bool(grounding_text),
            "metadata": grounding.get("metadata", {})
        }

    except errors.APIError as api_err:
        logger.error(f"Gemini API Error: {api_err}")
        err_msg = str(api_err)
        if "API_KEY_INVALID" in err_msg or "403" in err_msg or "INVALID_ARGUMENT" in err_msg:
            friendly = "Your GEMINI_API_KEY appears to be invalid or unauthorized. Please verify your key at https://aistudio.google.com/."
        elif "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
            friendly = "Gemini API rate limit or quota exceeded. Please wait a moment and try again."
        else:
            friendly = f"Gemini API Error: {err_msg[:200]}"

        return {
            "success": False,
            "error": friendly,
            "error_type": "gemini_api_error"
        }

    except Exception as exc:
        logger.error(f"Unexpected error calling Gemini API: {exc}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to generate response: {str(exc)[:200]}",
            "error_type": "system_error"
        }
