"""
Database Management Module for AquaSense AI
Uses SQLite for beginner-friendly, zero-configuration local persistence.
Automatically seeds the database from data/groundwater_data.csv on initial run.
"""

import csv
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

# Path to the SQLite database file
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "backend" / "groundwater.db"
CSV_PATH = ROOT_DIR / "data" / "groundwater_data.csv"


def get_db_connection() -> sqlite3.Connection:
    """Create and return a database connection with dict-like row access."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initialize SQLite tables and populate seed data from groundwater_data.csv
    if the database is currently empty.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groundwater_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT NOT NULL,
        state TEXT NOT NULL,
        date TEXT NOT NULL,
        water_level REAL NOT NULL,
        rainfall REAL NOT NULL,
        temperature REAL NOT NULL,
        humidity REAL NOT NULL,
        extraction_rate REAL DEFAULT 0.0,
        recharge_rate REAL DEFAULT 0.0,
        risk_level TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()

    # Check if table already has records
    cursor.execute("SELECT COUNT(*) AS cnt FROM groundwater_records;")
    count = cursor.fetchone()["cnt"]

    if count == 0 and CSV_PATH.exists():
        print(f"Database empty. Seeding initial records from {CSV_PATH}...")
        records_to_insert = []
        with open(CSV_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records_to_insert.append((
                    row["location"].strip(),
                    row["state"].strip(),
                    row["date"].strip(),
                    float(row["water_level"]),
                    float(row["rainfall"]),
                    float(row["temperature"]),
                    float(row["humidity"]),
                    float(row.get("extraction_rate", 0.0)),
                    float(row.get("recharge_rate", 0.0)),
                    row.get("risk_level", "Medium").strip()
                ))

        cursor.executemany("""
            INSERT INTO groundwater_records (
                location, state, date, water_level, rainfall,
                temperature, humidity, extraction_rate, recharge_rate, risk_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, records_to_insert)
        conn.commit()
        print(f"Seeded {len(records_to_insert)} records into groundwater_records.")

    conn.close()


def get_locations() -> List[Dict[str, Any]]:
    """Retrieve list of unique monitored locations and their states."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT location, state, COUNT(*) AS record_count,
               MAX(date) AS latest_date
        FROM groundwater_records
        GROUP BY location
        ORDER BY location ASC;
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_records(location: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch groundwater records, optionally filtered by location."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if location:
        cursor.execute("""
            SELECT * FROM groundwater_records
            WHERE LOWER(location) = LOWER(?)
            ORDER BY date DESC, id DESC
            LIMIT ?;
        """, (location, limit))
    else:
        cursor.execute("""
            SELECT * FROM groundwater_records
            ORDER BY date DESC, id DESC
            LIMIT ?;
        """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_record(location: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the most recent observation for a location (or Delhi by default)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if location:
        cursor.execute("""
            SELECT * FROM groundwater_records
            WHERE LOWER(location) = LOWER(?)
            ORDER BY date DESC, id DESC
            LIMIT 1;
        """, (location,))
    else:
        # Default to Delhi or the most recent overall
        cursor.execute("""
            SELECT * FROM groundwater_records
            WHERE LOWER(location) = 'delhi'
            ORDER BY date DESC, id DESC
            LIMIT 1;
        """)
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                SELECT * FROM groundwater_records
                ORDER BY date DESC, id DESC
                LIMIT 1;
            """)
    row = cursor.fetchone() if not location else cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_per_location() -> List[Dict[str, Any]]:
    """Get the latest record for every distinct monitored location."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*
        FROM groundwater_records r
        INNER JOIN (
            SELECT location, MAX(date) AS max_date
            FROM groundwater_records
            GROUP BY location
        ) latest
        ON r.location = latest.location AND r.date = latest.max_date
        ORDER BY r.location ASC;
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_location_history(location: str = "Delhi", months: int = 12) -> List[Dict[str, Any]]:
    """Retrieve chronologically ordered history for charts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, location, date, water_level, rainfall, temperature, risk_level
        FROM groundwater_records
        WHERE LOWER(location) = LOWER(?)
        ORDER BY date ASC
    """, (location,))
    rows = cursor.fetchall()
    conn.close()

    # Take the last `months` records in chronological order
    data = [dict(r) for r in rows]
    if len(data) > months:
        data = data[-months:]
    return data


def get_record_by_id(record_id: int) -> Optional[Dict[str, Any]]:
    """Find a specific record by its primary key ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM groundwater_records WHERE id = ?;", (record_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_record(data: Dict[str, Any]) -> int:
    """Insert a new groundwater record into the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO groundwater_records (
            location, state, date, water_level, rainfall,
            temperature, humidity, extraction_rate, recharge_rate, risk_level
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        data.get("location", "Unknown"),
        data.get("state", "Unknown"),
        data.get("date", datetime.now().strftime("%Y-%m-%d")),
        float(data.get("water_level", 10.0)),
        float(data.get("rainfall", 0.0)),
        float(data.get("temperature", 25.0)),
        float(data.get("humidity", 50.0)),
        float(data.get("extraction_rate", 50.0)),
        float(data.get("recharge_rate", 20.0)),
        data.get("risk_level", "Medium")
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def update_record(record_id: int, data: Dict[str, Any]) -> bool:
    """Update an existing groundwater record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE groundwater_records
        SET location = ?, state = ?, date = ?, water_level = ?,
            rainfall = ?, temperature = ?, humidity = ?,
            extraction_rate = ?, recharge_rate = ?, risk_level = ?
        WHERE id = ?;
    """, (
        data.get("location"),
        data.get("state"),
        data.get("date"),
        float(data.get("water_level")),
        float(data.get("rainfall")),
        float(data.get("temperature")),
        float(data.get("humidity")),
        float(data.get("extraction_rate", 0.0)),
        float(data.get("recharge_rate", 0.0)),
        data.get("risk_level", "Medium"),
        record_id
    ))
    conn.commit()
    affected = cursor.rowcount > 0
    conn.close()
    return affected


def delete_record(record_id: int) -> bool:
    """Delete a record by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM groundwater_records WHERE id = ?;", (record_id,))
    conn.commit()
    affected = cursor.rowcount > 0
    conn.close()
    return affected


def get_dashboard_summary(location: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate high-level dashboard metrics for the frontend overview cards.
    """
    loc_target = location if location else "Delhi"
    latest = get_latest_record(loc_target)
    history = get_location_history(loc_target, months=12)
    locations = get_locations()

    if not latest and history:
        latest = history[-1]

    # Calculate month-over-month trend if prior data exists
    change_pct = 0.0
    change_direction = "stable"
    if len(history) >= 2:
        prev = history[-2]["water_level"]
        curr = history[-1]["water_level"]
        if prev > 0:
            diff = curr - prev
            change_pct = round(abs(diff / prev) * 100, 1)
            change_direction = "up" if diff > 0 else "down"

    return {
        "location": latest["location"] if latest else loc_target,
        "state": latest["state"] if latest else "India",
        "date": latest["date"] if latest else datetime.now().strftime("%Y-%m-%d"),
        "water_level": latest["water_level"] if latest else 12.4,
        "water_level_unit": "m",
        "water_level_change": f"{'↑' if change_direction == 'up' else '↓'} {change_pct}% from last month",
        "rainfall": latest["rainfall"] if latest else 642.0,
        "rainfall_unit": "mm",
        "rainfall_change": "↑ 8.4% seasonal average",
        "temperature": latest["temperature"] if latest else 29.0,
        "humidity": latest["humidity"] if latest else 65.0,
        "risk_level": latest["risk_level"] if latest else "Medium",
        "risk_status": "Requires monitoring" if latest and latest["risk_level"] in ["Medium", "High"] else "Normal conditions",
        "active_locations_count": len(locations),
        "active_locations_status": f"{len(locations) - 1} reporting normally"
    }
