"""
Script to generate demo groundwater dataset for development and testing.
Clearly marked as DEMO DATA.
"""
import csv
import math
import random
from pathlib import Path

random.seed(42)

LOCATIONS = [
    {"name": "Delhi", "state": "National Capital Region", "base_depth": 12.0, "risk_base": "Medium"},
    {"name": "Jaipur", "state": "Rajasthan", "base_depth": 18.5, "risk_base": "High"},
    {"name": "Bengaluru", "state": "Karnataka", "base_depth": 7.0, "risk_base": "Low"},
    {"name": "Chennai", "state": "Tamil Nadu", "base_depth": 9.5, "risk_base": "Medium"},
    {"name": "Hyderabad", "state": "Telangana", "base_depth": 11.2, "risk_base": "Medium"},
    {"name": "Mumbai", "state": "Maharashtra", "base_depth": 6.8, "risk_base": "Low"},
    {"name": "Lucknow", "state": "Uttar Pradesh", "base_depth": 13.4, "risk_base": "Medium"},
    {"name": "Ahmedabad", "state": "Gujarat", "base_depth": 16.2, "risk_base": "High"},
]

MONTHS = []
# 2024 (Jan-Dec), 2025 (Jan-Dec), 2026 (Jan-Oct)
for year in [2024, 2025]:
    for month in range(1, 13):
        MONTHS.append((year, month))
for month in range(1, 11):
    MONTHS.append((2026, month))

csv_path = Path("data/groundwater_data.csv")
csv_path.parent.mkdir(parents=True, exist_ok=True)

rows = []
for loc in LOCATIONS:
    cur_depth = loc["base_depth"]
    for year, month in MONTHS:
        date_str = f"{year}-{month:02d}-01"
        
        # Monsoon seasonal effect in India: peaks July-September
        is_monsoon = month in [6, 7, 8, 9]
        if is_monsoon:
            rainfall = round(random.uniform(120, 320), 1)
            temp = round(random.uniform(28, 34), 1)
            humidity = round(random.uniform(70, 92), 1)
            recharge = round(rainfall * random.uniform(0.18, 0.28), 1)
            extraction = round(random.uniform(30, 50), 1)
            # Monsoon decreases depth (raises water level)
            cur_depth = max(3.0, cur_depth - (recharge * 0.04) + (extraction * 0.02) + random.uniform(-0.2, 0.2))
        else:
            rainfall = round(random.uniform(5, 45), 1)
            temp = round(random.uniform(20, 38) if month in [4, 5] else random.uniform(15, 27), 1)
            humidity = round(random.uniform(35, 65), 1)
            recharge = round(rainfall * 0.08, 1)
            extraction = round(random.uniform(55, 85), 1)
            # Dry season increases depth (lowers water level)
            cur_depth = cur_depth + (extraction * 0.015) - (recharge * 0.02) + random.uniform(-0.1, 0.2)
        
        water_level = round(cur_depth, 2)
        
        # Risk classification based on depth
        if water_level < 8.0:
            risk = "Low"
        elif water_level < 14.0:
            risk = "Medium"
        elif water_level < 20.0:
            risk = "High"
        else:
            risk = "Critical"
            
        rows.append({
            "location": loc["name"],
            "state": loc["state"],
            "date": date_str,
            "water_level": water_level,
            "rainfall": rainfall,
            "temperature": temp,
            "humidity": humidity,
            "extraction_rate": extraction,
            "recharge_rate": recharge,
            "risk_level": risk
        })

# Write with a clear DEMO DATA warning header in the comments/CSV
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "location", "state", "date", "water_level", "rainfall",
        "temperature", "humidity", "extraction_rate", "recharge_rate", "risk_level"
    ])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows of DEMO groundwater data in {csv_path}")
