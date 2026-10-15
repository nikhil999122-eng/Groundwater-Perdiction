"""
Data Models and Validators for AquaSense AI
Provides clean validation and structure for requests and responses.
"""

from typing import Any, Dict, Optional, Tuple


def validate_groundwater_input(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate incoming groundwater observation payload.
    Ensures required fields exist and values fall within physical bounds.
    """
    required_fields = ["location", "water_level"]
    for field in required_fields:
        if field not in data or data[field] is None:
            return False, f"Missing required field: '{field}'"

    try:
        water_level = float(data["water_level"])
        if water_level < 0 or water_level > 200:
            return False, "Groundwater level must be between 0 and 200 meters."
    except (ValueError, TypeError):
        return False, "Field 'water_level' must be a valid number."

    if "rainfall" in data and data["rainfall"] is not None:
        try:
            rainfall = float(data["rainfall"])
            if rainfall < 0:
                return False, "Rainfall cannot be negative."
        except (ValueError, TypeError):
            return False, "Field 'rainfall' must be a valid number."

    if "temperature" in data and data["temperature"] is not None:
        try:
            temp = float(data["temperature"])
            if temp < -50 or temp > 65:
                return False, "Temperature must be between -50°C and 65°C."
        except (ValueError, TypeError):
            return False, "Field 'temperature' must be a valid number."

    return True, None


def validate_prediction_input(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate features sent to the prediction model.
    """
    if "water_level" not in data and "previous_water_level" not in data:
        return False, "Current or previous water level is required for prediction."

    return True, None
