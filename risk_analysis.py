"""
Groundwater Risk Classification & Environmental Impact Module
AquaSense AI - BTech Mini Project

Classifies groundwater status into LOW, MEDIUM, HIGH, or CRITICAL.
Thresholds are kept fully configurable in RISK_CONFIG so students
and project mentors can adapt them to Central Ground Water Board (CGWB)
or regional standards.
"""

from typing import Any, Dict, List, Optional

# ============================================================================
# CONFIGURABLE THRESHOLDS (Easily modifiable by student or mentor)
# Water level represents depth below ground level (meters):
#  - Shallow depth (< 8m) means high/safe water table (LOW risk)
#  - Moderate depth (8m - 14m) means moderate stress (MEDIUM risk)
#  - Deep water table (14m - 20m) means over-exploited (HIGH risk)
#  - Very deep (> 20m) means critical depletion (CRITICAL risk)
# ============================================================================
RISK_CONFIG = {
    # Depth in meters below ground level
    "LOW_MAX_DEPTH": 8.0,
    "MEDIUM_MAX_DEPTH": 14.0,
    "HIGH_MAX_DEPTH": 20.0,

    # Seasonal rainfall thresholds in mm
    "LOW_RAINFALL_THRESHOLD": 50.0,
    "HIGH_RAINFALL_THRESHOLD": 150.0,

    # Temperature threshold (°C) above which evapotranspiration increases
    "HIGH_TEMPERATURE_THRESHOLD": 35.0,

    # Rate of monthly decline that triggers stress alert (meters)
    "ALERT_MONTHLY_DECLINE": 0.5,
}


def classify_groundwater_risk(
    water_level: float,
    expected_change: float = 0.0,
    rainfall: Optional[float] = None,
    temperature: Optional[float] = None,
    extraction_rate: Optional[float] = None,
    recharge_rate: Optional[float] = None
) -> Dict[str, Any]:
    """
    Compute risk classification, risk score (0-100), detailed scientific reasoning,
    and tailored sustainability recommendations.
    """
    water_level = float(water_level)
    expected_change = float(expected_change)

    # 1. Base Score & Level from Water Table Depth
    if water_level < RISK_CONFIG["LOW_MAX_DEPTH"]:
        base_level = "LOW"
        badge_text = "SAFE"
        base_score = 25.0 + (water_level / RISK_CONFIG["LOW_MAX_DEPTH"]) * 20.0  # ~25-45
        color_var = "var(--success)"
    elif water_level < RISK_CONFIG["MEDIUM_MAX_DEPTH"]:
        base_level = "MEDIUM"
        badge_text = "MODERATE"
        # Scale between 46 and 70
        fraction = (water_level - RISK_CONFIG["LOW_MAX_DEPTH"]) / (
            RISK_CONFIG["MEDIUM_MAX_DEPTH"] - RISK_CONFIG["LOW_MAX_DEPTH"]
        )
        base_score = 46.0 + fraction * 24.0
        color_var = "var(--warning)"
    elif water_level < RISK_CONFIG["HIGH_MAX_DEPTH"]:
        base_level = "HIGH"
        badge_text = "HIGH"
        # Scale between 71 and 88
        fraction = (water_level - RISK_CONFIG["MEDIUM_MAX_DEPTH"]) / (
            RISK_CONFIG["HIGH_MAX_DEPTH"] - RISK_CONFIG["MEDIUM_MAX_DEPTH"]
        )
        base_score = 71.0 + fraction * 17.0
        color_var = "var(--danger)"
    else:
        base_level = "CRITICAL"
        badge_text = "CRITICAL"
        base_score = min(98.0, 89.0 + (water_level - RISK_CONFIG["HIGH_MAX_DEPTH"]) * 1.5)
        color_var = "var(--danger)"

    # 2. Adjustments based on trend and environmental signals
    reasons: List[str] = []
    
    # Trend adjustment (if predicted water level is dropping deeper)
    if expected_change > 0.3:
        base_score = min(100.0, base_score + 6.0)
        reasons.append("Projected depth decline suggests increased extraction stress.")
    elif expected_change < -0.3:
        base_score = max(10.0, base_score - 5.0)
        reasons.append("Favorable replenishment trend anticipated in the next period.")

    # Rainfall signal
    rainfall_signal = "Seasonal average"
    if rainfall is not None:
        if rainfall > RISK_CONFIG["HIGH_RAINFALL_THRESHOLD"]:
            rainfall_signal = "Above seasonal average — promoting recharge"
            base_score = max(10.0, base_score - 4.0)
        elif rainfall < RISK_CONFIG["LOW_RAINFALL_THRESHOLD"]:
            rainfall_signal = "Below seasonal average — low recharge input"
            base_score = min(100.0, base_score + 4.0)
            reasons.append("Low rainfall restricts natural aquifer replenishment.")

    # Temperature signal
    temp_signal = "Moderate evaporation"
    if temperature is not None:
        if temperature > RISK_CONFIG["HIGH_TEMPERATURE_THRESHOLD"]:
            temp_signal = f"{temperature}°C — elevated surface evapotranspiration"
            base_score = min(100.0, base_score + 3.0)
        else:
            temp_signal = f"{temperature}°C — moderate evaporation"

    # Final score and badge normalization
    final_score = int(round(base_score))
    if final_score < 40:
        level_label = "Low"
        badge_label = "SAFE"
    elif final_score < 70:
        level_label = "Medium"
        badge_label = "MODERATE"
    elif final_score < 88:
        level_label = "High"
        badge_label = "HIGH"
    else:
        level_label = "Critical"
        badge_label = "CRITICAL"

    # Scientific description matching dashboard
    if level_label == "Low":
        description = (
            "Aquifer storage is in healthy condition with shallow water table depth. "
            "Continue standard monitoring and preserve natural catchment areas."
        )
        ai_recommendation = (
            "Maintain current sustainable extraction practices and safeguard recharge zones from unmanaged paving."
        )
    elif level_label == "Medium":
        description = (
            "Current groundwater conditions are stable, but the predicted trend "
            "suggests increased monitoring and conservation should be prioritized."
        )
        ai_recommendation = (
            "Increase rainwater harvesting and reduce unnecessary groundwater extraction during periods of low recharge."
        )
    elif level_label == "High":
        description = (
            "Significant groundwater stress observed. Water table depth is critically low "
            "and demand exceeds natural seasonal recharge."
        )
        ai_recommendation = (
            "Implement mandatory rainwater harvesting, restrict non-essential borewell pumping, and adopt micro-irrigation."
        )
    else:
        description = (
            "Critical aquifer depletion detected. Immediate policy intervention and artificial "
            "aquifer replenishment are required to prevent dry-well risks."
        )
        ai_recommendation = (
            "Urgent moratorium on deep drilling, full adoption of treated wastewater recycling, and prioritized artificial recharge shafts."
        )

    if reasons:
        primary_reason = " ".join(reasons)
    else:
        primary_reason = f"Groundwater depth is {water_level:.1f}m with stable seasonal parameters."

    return {
        "risk_level": level_label,
        "badge": badge_label,
        "score": final_score,
        "score_percentage": f"{final_score}%",
        "reason": primary_reason,
        "description": description,
        "ai_recommendation": ai_recommendation,
        "signals": {
            "rainfall": rainfall_signal,
            "temperature": temp_signal
        },
        "color_token": color_var,
        "thresholds_used": RISK_CONFIG
    }
