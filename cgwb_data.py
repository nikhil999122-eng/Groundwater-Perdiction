"""
CGWB DWLR Telemetry Data Ingestion Module
AquaSense AI - BTech Mini Project Upgrade

Downloads and ingests real groundwater telemetry data from the
National Water Data Portal (NWDP / NWIC) CKAN catalog.

Data Source:
  Organization: Central Ground Water Board (CGWB)
  Dataset: Ground Water Level (Telemetry - Hourly)
  Portal: https://nwdp.nwic.gov.in
  License: Other (Open)

CSV Columns (actual from source):
  SlNo, Station, Agency, State LGD Code, State, District LGD Code, District,
  Tehsil, Block, Village, River, Basin, Tributary, Subtributary,
  SubSubtributary, Local River, Latitude, Longitude, RL_MSL,
  Data Acquisition Time, Groundwater Level Telemetry Quadridaily (meter)
"""

import csv
import io
import os
import sqlite3
import urllib.request
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "backend" / "groundwater.db"
CGWB_CACHE_DIR = ROOT_DIR / "data" / "cgwb_cache"

# NWDP CKAN API endpoint for the CGWB telemetry dataset
NWDP_CKAN_DATASET_ID = "ground-water-level-telemetry-hourly-central-ground-water-board-cgwb"
NWDP_CKAN_API_URL = f"https://nwdp.nwic.gov.in/api/3/action/package_show?id={NWDP_CKAN_DATASET_ID}"

# State code to full name mapping for normalization
STATE_CODE_MAP = {
    "AS": "Assam",
    "BR": "Bihar",
    "DL": "Delhi",
    "HR": "Haryana",
    "KL": "Kerala",
    "MH": "Maharashtra",
    "PB": "Punjab",
    "PY": "Puducherry",
    "TS": "Telangana",
}

# All Indian states and UTs for the location search dropdown
INDIA_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]


def get_db() -> sqlite3.Connection:
    """Get database connection with Row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_dwlr_tables():
    """Create tables for DWLR stations and observations if they don't exist."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dwlr_stations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_name TEXT NOT NULL,
        agency TEXT DEFAULT 'CGWB',
        state_lgd_code INTEGER,
        state TEXT NOT NULL,
        district_lgd_code INTEGER,
        district TEXT NOT NULL,
        tehsil TEXT,
        block TEXT,
        village TEXT,
        latitude REAL,
        longitude REAL,
        rl_msl REAL,
        basin TEXT,
        river TEXT,
        data_source TEXT DEFAULT 'NWDP-CGWB',
        source_csv TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(station_name, state, district)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dwlr_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id INTEGER NOT NULL,
        observation_time TEXT NOT NULL,
        groundwater_level_m REAL,
        measurement_type TEXT DEFAULT 'depth_below_ground_level',
        unit TEXT DEFAULT 'm bgl',
        data_quality TEXT DEFAULT 'telemetry',
        source_csv TEXT,
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (station_id) REFERENCES dwlr_stations(id),
        UNIQUE(station_id, observation_time)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_ingestion_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_name TEXT NOT NULL,
        resource_url TEXT,
        state_code TEXT,
        records_ingested INTEGER DEFAULT 0,
        stations_found INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        error_message TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    );
    """)

    # Indexes for fast lookups
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_stations_state
    ON dwlr_stations(state);
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_stations_district
    ON dwlr_stations(state, district);
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_obs_station
    ON dwlr_observations(station_id);
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_obs_time
    ON dwlr_observations(station_id, observation_time);
    """)

    conn.commit()
    conn.close()
    print("DWLR database tables initialized.")


def get_nwdp_resources() -> List[Dict[str, Any]]:
    """
    Fetch the list of CSV resources from NWDP CKAN API.
    Returns list of dicts with name, url, format, state_code.
    """
    try:
        req = urllib.request.Request(
            NWDP_CKAN_API_URL,
            headers={"User-Agent": "AquaSenseAI/1.0 (BTech Mini Project)"}
        )
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        resources = data.get("result", {}).get("resources", [])

        result = []
        for r in resources:
            name = r.get("name", "")
            url = r.get("url", "")
            fmt = r.get("format", "").upper()

            # Extract state code from filename pattern
            state_code = _extract_state_code(url, name)

            result.append({
                "resource_id": r.get("id", ""),
                "name": name,
                "url": url,
                "format": fmt,
                "state_code": state_code,
                "state_name": STATE_CODE_MAP.get(state_code, state_code),
            })

        return result
    except Exception as e:
        print(f"Error fetching NWDP resources: {e}")
        return []


def _extract_state_code(url: str, name: str) -> str:
    """Extract 2-letter state code from NWDP CSV filename."""
    # Pattern: gwl_tel_6_hourly_cgwb_XX_YYYY_YYYY.csv
    url_lower = url.lower()
    for code in STATE_CODE_MAP:
        if f"_cgwb_{code.lower()}_" in url_lower or f"_{code.lower()}_" in url_lower:
            return code
    # Also check name
    name_upper = name.upper()
    for code in STATE_CODE_MAP:
        if code in name_upper:
            return code
    return "UNKNOWN"


def download_csv(url: str, cache_name: str = None) -> Optional[str]:
    """
    Download a CSV from NWDP. Optionally cache to disk.
    Returns CSV content as string, or None on failure.
    """
    # Check cache first
    if cache_name:
        CGWB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = CGWB_CACHE_DIR / cache_name
        if cache_path.exists():
            print(f"Using cached CSV: {cache_path}")
            return cache_path.read_text(encoding="utf-8", errors="replace")

    print(f"Downloading CSV: {url[:80]}...")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AquaSenseAI/1.0 (BTech Mini Project)"}
        )
        resp = urllib.request.urlopen(req, timeout=120)
        content = resp.read().decode("utf-8", errors="replace")

        # Save to cache
        if cache_name:
            CGWB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path = CGWB_CACHE_DIR / cache_name
            cache_path.write_text(content, encoding="utf-8")
            print(f"Cached to: {cache_path}")

        return content
    except Exception as e:
        print(f"CSV download error: {e}")
        return None


def parse_observation_time(time_str: str) -> Optional[str]:
    """
    Parse CGWB datetime format: 'DD-MM-YYYY HH:MM' -> ISO format.
    Returns ISO string or None.
    """
    if not time_str or time_str.strip() == "":
        return None
    time_str = time_str.strip()
    formats = [
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def ingest_csv_resource(resource: Dict[str, Any], max_rows: int = 50000) -> Dict[str, Any]:
    """
    Download and ingest a single NWDP CSV resource into the database.

    Returns summary dict with counts and status.
    """
    url = resource["url"]
    name = resource.get("name", "unknown")
    state_code = resource.get("state_code", "XX")

    # Cache filename
    cache_name = url.split("/")[-1] if "/" in url else f"{state_code}.csv"

    conn = get_db()
    cursor = conn.cursor()

    # Log ingestion start
    cursor.execute("""
        INSERT INTO data_ingestion_log (resource_name, resource_url, state_code, status)
        VALUES (?, ?, ?, 'downloading')
    """, (name, url, state_code))
    log_id = cursor.lastrowid
    conn.commit()

    result = {
        "resource": name,
        "state_code": state_code,
        "records_ingested": 0,
        "stations_found": 0,
        "errors": [],
        "status": "pending",
    }

    # Download
    content = download_csv(url, cache_name)
    if not content:
        result["status"] = "download_failed"
        cursor.execute("""
            UPDATE data_ingestion_log
            SET status='failed', error_message='Download failed', completed_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (log_id,))
        conn.commit()
        conn.close()
        return result

    cursor.execute("""
        UPDATE data_ingestion_log SET status='parsing' WHERE id=?
    """, (log_id,))
    conn.commit()

    # Parse CSV
    reader = csv.DictReader(io.StringIO(content))
    station_cache = {}
    rows_processed = 0
    rows_ingested = 0
    skipped = 0

    for row in reader:
        if rows_processed >= max_rows:
            break
        rows_processed += 1

        try:
            station_name = (row.get("Station") or "").strip()
            state = (row.get("State") or "").strip()
            district = (row.get("District") or "").strip()

            if not station_name or not state:
                skipped += 1
                continue

            # Normalize district
            district = district.title() if district else "Unknown"

            # Get or create station
            station_key = (station_name, state, district)
            if station_key not in station_cache:
                # Check if exists
                cursor.execute("""
                    SELECT id FROM dwlr_stations
                    WHERE station_name=? AND state=? AND district=?
                """, station_key)
                existing = cursor.fetchone()

                if existing:
                    station_cache[station_key] = existing["id"]
                else:
                    lat = _safe_float(row.get("Latitude"))
                    lon = _safe_float(row.get("Longitude"))
                    rl_msl = _safe_float(row.get("RL_MSL"))
                    state_lgd = _safe_int(row.get("State LGD Code"))
                    dist_lgd = _safe_int(row.get("District LGD Code"))

                    cursor.execute("""
                        INSERT OR IGNORE INTO dwlr_stations
                        (station_name, agency, state_lgd_code, state,
                         district_lgd_code, district, tehsil, block, village,
                         latitude, longitude, rl_msl, basin, river,
                         data_source, source_csv)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NWDP-CGWB', ?)
                    """, (
                        station_name,
                        (row.get("Agency") or "CGWB").strip(),
                        state_lgd,
                        state,
                        dist_lgd,
                        district,
                        (row.get("Tehsil") or "").strip() or None,
                        (row.get("Block") or "").strip() or None,
                        (row.get("Village") or "").strip() or None,
                        lat, lon, rl_msl,
                        (row.get("Basin") or "").strip() or None,
                        (row.get("River") or "").strip() or None,
                        cache_name,
                    ))
                    conn.commit()

                    cursor.execute("""
                        SELECT id FROM dwlr_stations
                        WHERE station_name=? AND state=? AND district=?
                    """, station_key)
                    new_station = cursor.fetchone()
                    station_cache[station_key] = new_station["id"] if new_station else None
                    result["stations_found"] += 1

            station_id = station_cache.get(station_key)
            if not station_id:
                skipped += 1
                continue

            # Parse observation
            obs_time_raw = (row.get("Data Acquisition Time") or "").strip()
            obs_time = parse_observation_time(obs_time_raw)
            if not obs_time:
                skipped += 1
                continue

            # Dynamic measurement column lookup from CGWB CSVs
            gwl_raw = None
            for col_name, val in row.items():
                if col_name and ("groundwater level" in col_name.lower() or "water level" in col_name.lower()):
                    gwl_raw = val
                    break

            gwl_value = _safe_float(gwl_raw)

            # Skip null readings
            if gwl_value is None:
                skipped += 1
                continue

            # Some CGWB DWLR telemetry sensors record depth as negative (-11.04 m)
            # In hydrology (m bgl), depth below ground surface is represented as positive
            gwl_value = round(abs(gwl_value), 2)

            # Insert observation (ignore duplicates)
            cursor.execute("""
                INSERT OR IGNORE INTO dwlr_observations
                (station_id, observation_time, groundwater_level_m,
                 measurement_type, unit, data_quality, source_csv)
                VALUES (?, ?, ?, 'depth_below_ground_level', 'm bgl', 'telemetry', ?)
            """, (station_id, obs_time, gwl_value, cache_name))

            if cursor.rowcount > 0:
                rows_ingested += 1

        except Exception as e:
            result["errors"].append(str(e)[:100])
            if len(result["errors"]) > 10:
                break

    conn.commit()

    result["records_ingested"] = rows_ingested
    result["rows_processed"] = rows_processed
    result["rows_skipped"] = skipped
    result["status"] = "completed"

    # Update log
    cursor.execute("""
        UPDATE data_ingestion_log
        SET status='completed', records_ingested=?, stations_found=?,
            completed_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (rows_ingested, result["stations_found"], log_id))
    conn.commit()
    conn.close()

    print(f"Ingested {rows_ingested} observations, {result['stations_found']} new stations from {name}")
    return result


def ingest_all_resources(max_rows_per_csv: int = 50000) -> List[Dict[str, Any]]:
    """Download and ingest all NWDP CSV resources."""
    init_dwlr_tables()
    resources = get_nwdp_resources()

    if not resources:
        print("No resources found from NWDP CKAN API.")
        return []

    results = []
    for r in resources:
        if r["format"] == "CSV":
            print(f"\n--- Processing: {r['name']} ---")
            result = ingest_csv_resource(r, max_rows=max_rows_per_csv)
            results.append(result)

    return results


# ============================================================================
# QUERY FUNCTIONS (used by routes.py)
# ============================================================================

def get_states_with_data() -> List[Dict[str, Any]]:
    """Get list of states that have DWLR station data."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT s.state,
               COUNT(DISTINCT s.id) as station_count,
               COUNT(DISTINCT s.district) as district_count,
               MAX(o.observation_time) as latest_observation
        FROM dwlr_stations s
        LEFT JOIN dwlr_observations o ON o.station_id = s.id
        GROUP BY s.state
        ORDER BY s.state
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_districts_in_state(state: str) -> List[Dict[str, Any]]:
    """Get districts with DWLR data in a given state."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT s.district,
               COUNT(DISTINCT s.id) as station_count,
               MAX(o.observation_time) as latest_observation
        FROM dwlr_stations s
        LEFT JOIN dwlr_observations o ON o.station_id = s.id
        WHERE LOWER(s.state) = LOWER(?)
        GROUP BY s.district
        ORDER BY s.district
    """, (state,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stations_in_district(state: str, district: str) -> List[Dict[str, Any]]:
    """Get DWLR stations in a specific state/district."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*,
               s.id as station_id,
               COUNT(o.id) as observation_count,
               MAX(o.observation_time) as latest_observation,
               (SELECT o2.groundwater_level_m FROM dwlr_observations o2
                WHERE o2.station_id = s.id
                ORDER BY o2.observation_time DESC LIMIT 1) as latest_water_level
        FROM dwlr_stations s
        LEFT JOIN dwlr_observations o ON o.station_id = s.id
        WHERE LOWER(s.state) = LOWER(?) AND LOWER(s.district) = LOWER(?)
        GROUP BY s.id
        ORDER BY s.station_name
    """, (state, district))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_station_detail(station_id: int) -> Optional[Dict[str, Any]]:
    """Get full details for a single DWLR station with latest observation."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*,
               COUNT(o.id) as total_observations,
               MIN(o.observation_time) as earliest_observation,
               MAX(o.observation_time) as latest_observation,
               MAX(o.observation_time) as latest_date,
               (SELECT o2.groundwater_level_m FROM dwlr_observations o2
                WHERE o2.station_id = s.id
                ORDER BY o2.observation_time DESC LIMIT 1) as latest_gwl,
               (SELECT o2.groundwater_level_m FROM dwlr_observations o2
                WHERE o2.station_id = s.id
                ORDER BY o2.observation_time DESC LIMIT 1) as latest_water_level
        FROM dwlr_stations s
        LEFT JOIN dwlr_observations o ON o.station_id = s.id
        WHERE s.id = ?
        GROUP BY s.id
    """, (station_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_station_observations(
    station_id: int,
    start_date: str = None,
    end_date: str = None,
    limit: int = 500
) -> List[Dict[str, Any]]:
    """Get observations for a station, optionally filtered by date range."""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT o.id, o.station_id, o.observation_time,
               o.groundwater_level_m, o.measurement_type, o.unit,
               o.data_quality
        FROM dwlr_observations o
        WHERE o.station_id = ?
    """
    params: list = [station_id]

    if start_date:
        query += " AND o.observation_time >= ?"
        params.append(start_date)
    if end_date:
        query += " AND o.observation_time <= ?"
        params.append(end_date)

    query += " ORDER BY o.observation_time DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_station_history_for_chart(
    station_id: int,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """
    Get chronologically ordered daily-aggregated observations for charts.
    Aggregates 6-hourly readings into daily averages.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(o.observation_time) as date,
               AVG(o.groundwater_level_m) as avg_gwl,
               MIN(o.groundwater_level_m) as min_gwl,
               MAX(o.groundwater_level_m) as max_gwl,
               COUNT(*) as reading_count
        FROM dwlr_observations o
        WHERE o.station_id = ?
          AND o.groundwater_level_m > 0
        GROUP BY DATE(o.observation_time)
        ORDER BY date ASC
    """, (station_id,))
    rows = cursor.fetchall()
    conn.close()

    data = [dict(r) for r in rows]
    # Return last `limit` days
    if len(data) > limit:
        data = data[-limit:]
    return data


def get_data_source_info() -> Dict[str, Any]:
    """Return metadata about the ingested data for the Data Sources panel."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM dwlr_stations")
    station_count = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM dwlr_observations")
    obs_count = cursor.fetchone()["cnt"]

    cursor.execute("SELECT MIN(observation_time) as earliest, MAX(observation_time) as latest FROM dwlr_observations")
    time_range = dict(cursor.fetchone())

    cursor.execute("""
        SELECT * FROM data_ingestion_log
        ORDER BY completed_at DESC LIMIT 5
    """)
    recent_ingestions = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "source_organization": "Central Ground Water Board (CGWB)",
        "dataset_name": "Ground Water Level (Telemetry - Hourly/Six-Hourly)",
        "portal": "National Water Data Portal (NWDP)",
        "portal_url": "https://nwdp.nwic.gov.in",
        "dataset_url": f"https://nwdp.nwic.gov.in/en/dataset/{NWDP_CKAN_DATASET_ID}",
        "data_type": "DWLR Telemetry Observations",
        "measurement_unit": "meters below ground level (m bgl)",
        "total_stations": station_count,
        "total_observations": obs_count,
        "earliest_observation": time_range.get("earliest"),
        "latest_observation": time_range.get("latest"),
        "data_freshness": "Historical cached data — not live telemetry",
        "states_covered": list(STATE_CODE_MAP.values()),
        "recent_ingestions": recent_ingestions,
        "license": "Other (Open)",
        "note": (
            "This data is downloaded from the NWDP CKAN portal as published CSV files. "
            "Observations are historical/cached and NOT live real-time readings. "
            "The timestamps reflect the original CGWB DWLR recording times."
        ),
    }


def has_dwlr_data() -> bool:
    """Check if any DWLR data has been ingested."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM dwlr_stations")
        count = cursor.fetchone()["cnt"]
        conn.close()
        return count > 0
    except Exception:
        conn.close()
        return False


# ============================================================================
# HELPERS
# ============================================================================

def _safe_float(val) -> Optional[float]:
    """Safely convert a value to float."""
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """Safely convert a value to int."""
    if val is None or val == "" or val == "-":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  AquaSense AI — CGWB DWLR Data Ingestion")
    print("=" * 60)
    init_dwlr_tables()
    results = ingest_all_resources(max_rows_per_csv=50000)
    print("\n\n=== INGESTION SUMMARY ===")
    for r in results:
        print(f"  {r['resource']}: {r['records_ingested']} records, "
              f"{r['stations_found']} stations — {r['status']}")
    info = get_data_source_info()
    print(f"\nTotal stations: {info['total_stations']}")
    print(f"Total observations: {info['total_observations']}")
    print(f"Time range: {info['earliest_observation']} to {info['latest_observation']}")
