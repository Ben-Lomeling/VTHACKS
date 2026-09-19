from app.gemini import validate_extracted_load


def test_converts_per_mile_rate_to_total():
    data = {
        "origin": {"city": "Richmond, VA"},
        "destination": {"city": "Charlotte, NC"},
        "rate_usd": 2.10,
        "loaded_miles_est": 500,
    }

    result = validate_extracted_load(data, "pasted")

    assert result.load.rate_usd == 1050.0
    assert result.confidence["rate_usd"] == "low"
    assert "Converted $2.10/mi to total rate" in result.warnings


def test_warns_when_state_is_missing():
    data = {
        "origin": {"city": "Springfield"},
        "destination": {"city": "Richmond, VA"},
        "rate_usd": 1200,
        "loaded_miles_est": 400,
    }

    result = validate_extracted_load(data, "pasted")

    assert result.confidence["origin"] == "low"
    assert "State missing for Springfield" in result.warnings


def test_warns_when_rate_is_missing():
    data = {
        "origin": {"city": "Richmond, VA"},
        "destination": {"city": "Charlotte, NC"},
        "rate_usd": None,
        "loaded_miles_est": 300,
    }

    result = validate_extracted_load(data, "pasted")

    assert result.load.rate_usd == 0.0
    assert result.confidence["rate_usd"] == "low"
    assert "Rate is missing or invalid" in result.warnings


def test_warns_when_pickup_is_after_delivery():
    data = {
        "origin": {"city": "Richmond, VA"},
        "destination": {"city": "Charlotte, NC"},
        "rate_usd": 1200,
        "loaded_miles_est": 300,
        "pickup_window_start": "2026-09-24T08:00:00",
        "delivery_by": "2026-09-23T08:00:00",
    }

    result = validate_extracted_load(data, "pasted")

    assert "Pickup time is after delivery time" in result.warnings
    assert result.confidence["pickup_window_start"] == "low"
    assert result.confidence["delivery_by"] == "low"