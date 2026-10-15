"""
REST API Routes for AquaSense AI
Provides clean JSON endpoints for frontend interactions, charts,
database CRUD, ML predictions, risk classification, and chatbot.

UPGRADED: Added DWLR location search endpoints for real CGWB data.
"""

import os
from flask import Blueprint, jsonify, request
from backend.chatbot import get_ai_response
from backend.database import (
    create_record,
    delete_record,
    get_all_records,
    get_dashboard_summary,
    get_latest_per_location,
    get_latest_record,
    get_location_history,
    get_locations,
    get_record_by_id,
    update_record
)
from backend.models import validate_groundwater_input, validate_prediction_input
from backend.prediction import predict_water_level
from backend.risk_analysis import classify_groundwater_risk
from backend.cgwb_data import (
    get_states_with_data,
    get_districts_in_state,
    get_stations_in_district,
    get_station_detail,
    get_station_observations,
    get_station_history_for_chart,
    get_data_source_info,
    has_dwlr_data,
    ingest_all_resources,
    init_dwlr_tables,
    INDIA_STATES,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ============================================================================
# 1. DWLR LOCATION SEARCH ENDPOINTS (NEW)
# ============================================================================

@api_bp.route("/locations/states", methods=["GET"])
def list_states():
    """
    Returns all Indian states/UTs.
    States with available DWLR data are flagged with has_data=true.
    """
    states_with_data = get_states_with_data()
    data_state_names = {s["state"].lower() for s in states_with_data}

    # Build lookup for data stats
    data_lookup = {}
    for s in states_with_data:
        data_lookup[s["state"].lower()] = s

    result = []
    for state_name in sorted(INDIA_STATES):
        state_key = state_name.lower()
        info = data_lookup.get(state_key, {})
        result.append({
            "state": state_name,
            "has_data": state_key in data_state_names,
            "station_count": info.get("station_count", 0),
            "district_count": info.get("district_count", 0),
            "latest_observation": info.get("latest_observation"),
        })

    return jsonify({
        "success": True,
        "count": len(result),
        "states_with_data": len(states_with_data),
        "data": result,
    }), 200


@api_bp.route("/locations/districts", methods=["GET"])
def list_districts():
    """
    Returns districts with DWLR data for a given state.
    Query: ?state=Delhi
    """
    state = request.args.get("state", "").strip()
    if not state:
        return jsonify({
            "success": False,
            "error": "Query parameter 'state' is required."
        }), 400

    districts = get_districts_in_state(state)

    if not districts:
        return jsonify({
            "success": True,
            "count": 0,
            "data": [],
            "message": f"No DWLR monitoring data is currently available for {state}. "
                       "The NWDP/CGWB telemetry dataset covers select states: "
                       "Assam, Bihar, Delhi, Haryana, Kerala, Maharashtra, Punjab, Puducherry, Telangana."
        }), 200

    return jsonify({
        "success": True,
        "state": state,
        "count": len(districts),
        "data": districts,
    }), 200


@api_bp.route("/locations/stations", methods=["GET"])
def list_stations():
    """
    Returns DWLR monitoring stations for a state/district.
    Query: ?state=Delhi&district=North
    """
    state = request.args.get("state", "").strip()
    district = request.args.get("district", "").strip()

    if not state:
        return jsonify({
            "success": False,
            "error": "Query parameter 'state' is required."
        }), 400

    if not district:
        # Return all stations in the state
        districts = get_districts_in_state(state)
        all_stations = []
        for d in districts:
            stations = get_stations_in_district(state, d["district"])
            all_stations.extend(stations)
        return jsonify({
            "success": True,
            "state": state,
            "count": len(all_stations),
            "data": all_stations,
        }), 200

    stations = get_stations_in_district(state, district)
    return jsonify({
        "success": True,
        "state": state,
        "district": district,
        "count": len(stations),
        "data": stations,
    }), 200


# ============================================================================
# 2. DWLR GROUNDWATER OBSERVATIONS (NEW)
# ============================================================================

@api_bp.route("/groundwater/station/<int:station_id>", methods=["GET"])
def get_station_data(station_id):
    """
    Get details and latest observations for a specific DWLR station.
    """
    station = get_station_detail(station_id)
    if not station:
        return jsonify({
            "success": False,
            "error": f"Station with ID {station_id} not found."
        }), 404

    # Get recent observations
    observations = get_station_observations(station_id, limit=20)

    station_dict = dict(station)
    data_payload = {**station_dict, **{
        "station": station_dict,
        "recent_observations": observations,
        "data_source": "NWDP-CGWB DWLR Telemetry",
        "measurement_description": "Depth to groundwater below ground level",
        "unit": "meters below ground level (m bgl)",
    }}

    return jsonify({
        "success": True,
        "data": data_payload
    }), 200


@api_bp.route("/groundwater/history", methods=["GET"])
def get_groundwater_history():
    """
    Returns time-series data for charts.
    Supports both DWLR station_id and legacy location parameter.
    Query: ?station_id=123 OR ?location=Delhi&months=12
    """
    station_id = request.args.get("station_id")
    location = request.args.get("location")

    if station_id:
        # DWLR mode: return daily aggregated data
        try:
            sid = int(station_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid station_id"}), 400

        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        limit = int(request.args.get("limit", 200))

        history = get_station_history_for_chart(sid, limit=limit)

        station = get_station_detail(sid)
        station_name = station["station_name"] if station else f"Station #{sid}"

        return jsonify({
            "success": True,
            "station_id": sid,
            "station_name": station_name,
            "count": len(history),
            "data": history,
            "measurement_type": "depth_below_ground_level",
            "unit": "m bgl",
            "data_source": "NWDP-CGWB DWLR Telemetry",
        }), 200

    elif location:
        # Legacy mode: use old database
        months = int(request.args.get("months", 12))
        history = get_location_history(location=location, months=months)
        return jsonify({
            "success": True,
            "location": location,
            "count": len(history),
            "data": history,
            "data_source": "Local demonstration dataset",
        }), 200

    return jsonify({
        "success": False,
        "error": "Either 'station_id' or 'location' parameter is required."
    }), 400


@api_bp.route("/groundwater/observations", methods=["GET"])
def get_observations():
    """
    Get paginated observations for a DWLR station.
    Query: ?station_id=123&start_date=2020-01-01&end_date=2020-12-31&limit=100
    """
    station_id = request.args.get("station_id")
    if not station_id:
        return jsonify({"success": False, "error": "station_id is required."}), 400

    try:
        sid = int(station_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid station_id."}), 400

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    limit = min(int(request.args.get("limit", 200)), 1000)

    observations = get_station_observations(sid, start_date, end_date, limit)
    station = get_station_detail(sid)

    return jsonify({
        "success": True,
        "station_id": sid,
        "station_name": station["station_name"] if station else None,
        "count": len(observations),
        "data": observations,
    }), 200


# ============================================================================
# 3. DATA SOURCE INFO (NEW)
# ============================================================================

@api_bp.route("/data/status", methods=["GET"])
def data_status():
    """Returns info about the ingested CGWB data and source metadata."""
    info = get_data_source_info()
    return jsonify({
        "success": True,
        "data": info,
    }), 200


@api_bp.route("/data/ingest", methods=["POST"])
def trigger_ingestion():
    """
    Trigger CGWB data ingestion from NWDP.
    Protected with a simple secret key (from env var DATA_INGEST_KEY).
    """
    import os
    expected_key = os.getenv("DATA_INGEST_KEY", "aquasense2024")
    provided_key = request.json.get("key", "") if request.is_json else ""

    if provided_key != expected_key:
        return jsonify({
            "success": False,
            "error": "Invalid ingestion key. Set DATA_INGEST_KEY in .env"
        }), 403

    max_rows = int(request.json.get("max_rows", 50000)) if request.is_json else 50000
    results = ingest_all_resources(max_rows_per_csv=max_rows)

    return jsonify({
        "success": True,
        "message": "Data ingestion completed.",
        "results": results,
    }), 200


# ============================================================================
# 4. DASHBOARD & OVERVIEW API (UPDATED)
# ============================================================================

@api_bp.route("/dashboard", methods=["GET"])
def get_dashboard():
    """
    Returns summarized metrics for dashboard cards.
    Supports both DWLR station_id and legacy location mode.
    Query: ?station_id=123 OR ?location=Delhi
    """
    station_id = request.args.get("station_id")
    location = request.args.get("location")

    if station_id:
        # DWLR mode
        try:
            sid = int(station_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid station_id"}), 400

        station = get_station_detail(sid)
        if not station:
            return jsonify({
                "success": False,
                "error": f"Station {station_id} not found."
            }), 404

        history = get_station_history_for_chart(sid, limit=30)

        # Calculate trend
        change_pct = 0.0
        change_direction = "stable"
        if len(history) >= 2:
            prev = history[-2]["avg_gwl"]
            curr = history[-1]["avg_gwl"]
            if prev and curr and prev > 0:
                diff = curr - prev
                change_pct = round(abs(diff / prev) * 100, 1)
                change_direction = "deeper" if diff > 0 else "shallower"

        latest_gwl = station.get("latest_gwl", 0.0)

        return jsonify({
            "success": True,
            "mode": "dwlr",
            "data": {
                "station_id": sid,
                "station_name": station["station_name"],
                "state": station["state"],
                "district": station["district"],
                "latitude": station.get("latitude"),
                "longitude": station.get("longitude"),
                "water_level": latest_gwl,
                "water_level_unit": "m bgl",
                "water_level_label": "Depth to groundwater",
                "water_level_change": f"{'↑' if change_direction == 'deeper' else '↓'} {change_pct}% from previous reading",
                "latest_observation": station.get("latest_observation"),
                "earliest_observation": station.get("earliest_observation"),
                "total_observations": station.get("total_observations", 0),
                "risk_level": _estimate_risk_label(latest_gwl),
                "risk_status": _estimate_risk_status(latest_gwl),
                "data_source": "NWDP-CGWB DWLR Telemetry",
                "data_freshness": "Historical observation (cached)",
            }
        }), 200

    else:
        # Legacy mode
        data = get_dashboard_summary(location=location)
        return jsonify({
            "success": True,
            "mode": "legacy",
            "data": data,
        }), 200


@api_bp.route("/locations", methods=["GET"])
def list_locations():
    """Returns all monitored locations (legacy)."""
    locs = get_locations()
    return jsonify({
        "success": True,
        "count": len(locs),
        "data": locs
    }), 200


# ============================================================================
# 5. GROUNDWATER DATA APIS (LEGACY CRUD)
# ============================================================================

@api_bp.route("/groundwater", methods=["GET"])
def get_groundwater():
    """Retrieve groundwater records (legacy mode)."""
    location = request.args.get("location")
    latest_only = request.args.get("latest", "false").lower() == "true"

    if location:
        records = get_all_records(location=location, limit=50)
    elif latest_only or not request.args:
        records = get_latest_per_location()
    else:
        records = get_all_records(limit=100)

    return jsonify({
        "success": True,
        "count": len(records),
        "data": records
    }), 200


@api_bp.route("/groundwater/<int:record_id>", methods=["GET"])
def get_groundwater_by_id(record_id: int):
    """Retrieve a single observation by ID."""
    record = get_record_by_id(record_id)
    if not record:
        return jsonify({
            "success": False,
            "error": f"Record with ID {record_id} not found."
        }), 404

    return jsonify({
        "success": True,
        "data": record
    }), 200


@api_bp.route("/groundwater", methods=["POST"])
def add_groundwater():
    """Insert a new groundwater observation record into the database."""
    payload = request.get_json(silent=True) or {}
    is_valid, error_msg = validate_groundwater_input(payload)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400

    if "risk_level" not in payload:
        risk_calc = classify_groundwater_risk(
            water_level=payload["water_level"],
            rainfall=payload.get("rainfall"),
            temperature=payload.get("temperature")
        )
        payload["risk_level"] = risk_calc["risk_level"]

    new_id = create_record(payload)
    created_record = get_record_by_id(new_id)

    return jsonify({
        "success": True,
        "message": "Groundwater observation created successfully.",
        "id": new_id,
        "data": created_record
    }), 201


@api_bp.route("/groundwater/<int:record_id>", methods=["PUT"])
def edit_groundwater(record_id: int):
    """Update an existing groundwater record."""
    existing = get_record_by_id(record_id)
    if not existing:
        return jsonify({
            "success": False,
            "error": f"Record with ID {record_id} not found."
        }), 404

    payload = request.get_json(silent=True) or {}
    is_valid, error_msg = validate_groundwater_input(payload)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400

    success = update_record(record_id, payload)
    updated_record = get_record_by_id(record_id)

    return jsonify({
        "success": success,
        "message": "Groundwater observation updated successfully.",
        "data": updated_record
    }), 200


@api_bp.route("/groundwater/<int:record_id>", methods=["DELETE"])
def remove_groundwater(record_id: int):
    """Delete a groundwater record."""
    existing = get_record_by_id(record_id)
    if not existing:
        return jsonify({
            "success": False,
            "error": f"Record with ID {record_id} not found."
        }), 404

    deleted = delete_record(record_id)
    return jsonify({
        "success": deleted,
        "message": f"Record {record_id} deleted successfully."
    }), 200


# ============================================================================
# 6. PREDICTION API (UPDATED)
# ============================================================================

@api_bp.route("/predict", methods=["POST"])
def predict():
    """
    Run ML prediction.
    Supports DWLR station_id or legacy location mode.
    """
    payload = request.get_json(silent=True) or {}

    station_id = payload.get("station_id")
    location = payload.get("location")

    if station_id:
        # DWLR mode: use station history
        try:
            sid = int(station_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid station_id"}), 400

        history = get_station_history_for_chart(sid, limit=100)
        if len(history) < 6:
            return jsonify({
                "success": True,
                "data": {
                    "available": False,
                    "reason": "Prediction unavailable: insufficient historical data. "
                              f"Only {len(history)} daily observations found. "
                              "At least 6 data points are needed for a meaningful prediction.",
                    "station_id": sid,
                    "observations_available": len(history),
                }
            }), 200

        # Use last observation as current level
        latest = history[-1]["avg_gwl"]
        payload["water_level"] = latest

    elif location:
        # Legacy mode
        if ("water_level" not in payload and "previous_water_level" not in payload):
            latest = get_latest_record(location)
            if latest:
                payload["water_level"] = latest["water_level"]
                payload.setdefault("rainfall", latest["rainfall"])
                payload.setdefault("temperature", latest["temperature"])
                payload.setdefault("humidity", latest["humidity"])
                payload.setdefault("extraction_rate", latest.get("extraction_rate", 55.0))
                payload.setdefault("recharge_rate", latest.get("recharge_rate", 20.0))

    is_valid, error_msg = validate_prediction_input(payload)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": error_msg
        }), 400

    prediction_result = predict_water_level(payload)
    prediction_result["available"] = True

    # Risk assessment for predicted level
    risk_info = classify_groundwater_risk(
        water_level=prediction_result["predicted_groundwater_level"],
        expected_change=prediction_result["expected_change"],
        rainfall=payload.get("rainfall"),
        temperature=payload.get("temperature")
    )
    prediction_result["risk_assessment"] = risk_info

    if station_id:
        prediction_result["data_source"] = "DWLR telemetry observations"
        prediction_result["note"] = (
            "This prediction is based on historical DWLR observations. "
            "The model uses depth-to-groundwater measurements and may not account for "
            "local hydrogeological conditions specific to this monitoring station."
        )

    return jsonify({
        "success": True,
        "data": prediction_result
    }), 200


# ============================================================================
# 7. RISK ASSESSMENT API (UPDATED)
# ============================================================================

@api_bp.route("/risk", methods=["GET", "POST"])
def get_risk():
    """
    Classify groundwater risk level.
    Supports DWLR station_id or legacy mode.
    """
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = request.args.to_dict()

    station_id = payload.get("station_id")
    location = payload.get("location")
    water_level = payload.get("water_level")

    if station_id:
        try:
            sid = int(station_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid station_id"}), 400

        station = get_station_detail(sid)
        if not station or not station.get("latest_gwl"):
            return jsonify({
                "success": True,
                "data": {
                    "available": False,
                    "reason": "Risk assessment unavailable: no observations found for this station.",
                }
            }), 200
        water_level = station["latest_gwl"]
    elif water_level is None and location:
        latest = get_latest_record(location)
        if latest:
            water_level = latest["water_level"]
            payload.setdefault("rainfall", latest["rainfall"])
            payload.setdefault("temperature", latest["temperature"])

    if water_level is None:
        return jsonify({
            "success": True,
            "data": {
                "available": False,
                "reason": "Risk assessment unavailable: no water level data provided.",
            }
        }), 200

    try:
        wl_float = float(water_level)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Water level must be a numeric value."
        }), 400

    rainfall = float(payload["rainfall"]) if payload.get("rainfall") is not None else None
    temp = float(payload["temperature"]) if payload.get("temperature") is not None else None
    expected_change = float(payload.get("expected_change", 0.0))

    risk_result = classify_groundwater_risk(
        water_level=wl_float,
        expected_change=expected_change,
        rainfall=rainfall,
        temperature=temp
    )

    risk_result["available"] = True

    if station_id:
        risk_result["note"] = (
            "This risk classification is based on configurable depth thresholds "
            "and does not represent an official CGWB assessment. "
            "A deeper water table generally indicates more stress, but local "
            "conditions, aquifer type, and seasonal variation should be considered."
        )

    return jsonify({
        "success": True,
        "data": risk_result
    }), 200


# ============================================================================
# 8. AI CHATBOT API
# ============================================================================

@api_bp.route("/chat", methods=["POST"])
def chat():
    """
    Groundwater Conservation and Intelligence Assistant endpoint (Powered by Gemini AI).
    Accepts:
    - message: str (required)
    - history: list of turns [{'role': 'user'|'model', 'content': '...'}] (optional)
    - station_id: int/str (optional)
    - location: str (optional)
    """
    payload = request.get_json(silent=True) or {}
    user_message = payload.get("message", "").strip()

    if not user_message:
        return jsonify({
            "success": False,
            "error": "Message is required."
        }), 400

    history = payload.get("history")
    station_id = payload.get("station_id")
    context_location = payload.get("location")

    ai_result = get_ai_response(
        user_message=user_message,
        history=history,
        station_id=station_id,
        context_location=context_location
    )

    if not ai_result.get("success"):
        # Return 200 with success: False so the UI can gracefully display the error in the chat bubble
        return jsonify(ai_result), 200

    return jsonify(ai_result), 200


@api_bp.route("/config/api-key", methods=["POST"])
def set_api_key():
    """Allows user to set or update GEMINI_API_KEY directly from UI."""
    payload = request.get_json(silent=True) or {}
    key = payload.get("gemini_api_key", "").strip()
    if not key:
        return jsonify({"success": False, "error": "API key cannot be empty."}), 400

    os.environ["GEMINI_API_KEY"] = key

    # Persist in local .env file
    env_path = ROOT_DIR / ".env"
    try:
        lines = []
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        updated = False
        new_lines = []
        for line in lines:
            if line.startswith("GEMINI_API_KEY="):
                new_lines.append(f"GEMINI_API_KEY={key}\n")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f"\nGEMINI_API_KEY={key}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"Warning: Failed to update .env: {e}")

    return jsonify({
        "success": True,
        "message": "Gemini API key saved and activated successfully!"
    }), 200


# ============================================================================
# 9. CSV EXPORT (NEW)
# ============================================================================

@api_bp.route("/export/csv", methods=["GET"])
def export_csv():
    """Export observations for a station as CSV download."""
    station_id = request.args.get("station_id")
    if not station_id:
        return jsonify({"success": False, "error": "station_id required"}), 400

    try:
        sid = int(station_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid station_id"}), 400

    station = get_station_detail(sid)
    if not station:
        return jsonify({"success": False, "error": "Station not found"}), 404

    observations = get_station_observations(sid, limit=5000)

    import io as _io
    import csv as _csv
    from flask import Response

    output = _io.StringIO()
    writer = _csv.writer(output)
    writer.writerow([
        "Station", "State", "District", "Observation Time",
        "Groundwater Level (m bgl)", "Measurement Type", "Data Quality"
    ])

    for obs in observations:
        writer.writerow([
            station["station_name"],
            station["state"],
            station["district"],
            obs["observation_time"],
            obs["groundwater_level_m"],
            obs["measurement_type"],
            obs["data_quality"],
        ])

    csv_content = output.getvalue()
    safe_name = station["station_name"].replace(" ", "_")[:30]

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=aquasense_{safe_name}_data.csv"}
    )


# ============================================================================
# HELPERS
# ============================================================================

def _estimate_risk_label(gwl: float) -> str:
    """Simple risk label from groundwater depth for dashboard display."""
    if gwl is None or gwl <= 0:
        return "Unknown"
    if gwl < 8:
        return "Low"
    if gwl < 14:
        return "Medium"
    if gwl < 20:
        return "High"
    return "Critical"


def _estimate_risk_status(gwl: float) -> str:
    """Risk status text for dashboard."""
    if gwl is None or gwl <= 0:
        return "Insufficient data"
    if gwl < 8:
        return "Healthy water table"
    if gwl < 14:
        return "Requires monitoring"
    if gwl < 20:
        return "Significant stress detected"
    return "Critical depletion — immediate attention needed"
