import pytest

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


def test_destination_is_checked_on_its_own():
    ok_dest = validate_extracted_load({"origin": "Springfield", "destination": "Richmond, VA", "rate_usd": 1200}, "pasted")
    assert ok_dest.confidence["destination"] == "high"
    missing = validate_extracted_load({"origin": "Richmond, VA", "destination": None, "rate_usd": 1200}, "pasted")
    assert "Destination is missing" in missing.warnings and missing.confidence["destination"] == "low"
    no_state = validate_extracted_load({"origin": None, "destination": "Charlotte", "rate_usd": 1200}, "pasted")
    assert "State missing for Charlotte" in no_state.warnings and no_state.confidence["destination"] == "low"


def test_times_with_a_utc_offset_do_not_crash():
    result = validate_extracted_load({
        "origin": "Richmond, VA", "destination": "Charlotte, NC", "rate_usd": 1200,
        "pickup_window_start": "2026-09-22T08:00:00-04:00", "delivery_by": "2026-09-23T08:00:00",
    }, "pasted")
    assert result.load.pickup_window_start.tzinfo is None
    assert result.load.pickup_window_start.hour == 8
    assert "Pickup time is after delivery time" not in result.warnings


def test_unreadable_time_is_flagged_not_fatal():
    result = validate_extracted_load({
        "origin": "Richmond, VA", "destination": "Charlotte, NC", "rate_usd": 1200, "delivery_by": "Tuesday-ish",
    }, "pasted")
    assert result.load.delivery_by is None and result.confidence["delivery_by"] == "low"


# --- status honesty and the pinned demo example -------------------------------------------------
# Regression guards for the two ways this module can lie: reporting "live" with no key, and letting
# the pitch's example load drift because a live model re-read it.

import app.gemini as gemini
from app.main import app
from fastapi.testclient import TestClient

EXAMPLE = (
    "Greensboro, NC → Jacksonville, FL. $1,200 flat. Dry van, 40,000 lbs. "
    "Coastal Brokerage. Pickup Mon, deliver Tue. Net 30."
)


def test_data_source_is_stub_without_a_key(monkeypatch):
    monkeypatch.setattr(gemini, "_api_key", lambda: None)
    assert gemini.data_source() == "stub"


def test_data_source_is_live_with_a_key(monkeypatch):
    monkeypatch.setattr(gemini, "_api_key", lambda: "test-key")
    assert gemini.data_source() == "live"


def test_health_reports_gemini_live_when_a_key_is_present(monkeypatch):
    monkeypatch.setattr(gemini, "_api_key", lambda: "test-key")
    assert TestClient(app).get("/api/health").json()["modules"]["gemini"] == "live"


def test_health_reports_gemini_stub_without_a_key(monkeypatch):
    monkeypatch.setattr(gemini, "_api_key", lambda: None)
    assert TestClient(app).get("/api/health").json()["modules"]["gemini"] == "stub"


def test_demo_example_is_pinned_even_with_a_key(monkeypatch):
    """The pitch numbers come off these fields; a live call must never touch the example."""
    monkeypatch.setattr(gemini, "_api_key", lambda: "test-key")
    monkeypatch.setattr(
        gemini.genai, "Client", lambda **kw: pytest.fail("Gemini was called for the demo example")
    )

    result = gemini.extract_load(EXAMPLE, None, None)

    assert result.load.origin.city == "Greensboro, NC"
    assert result.load.destination.city == "Jacksonville, FL"
    assert result.load.rate_usd == 1200.0
    assert result.load.loaded_miles_est is None


def test_fallback_warning_comes_first_when_gemini_fails(monkeypatch):
    """A judge must see "this wasn't read" above the fields, not buried under field warnings."""
    monkeypatch.setattr(gemini, "_api_key", lambda: "test-key")

    def boom(**kw):
        raise RuntimeError("no network")

    monkeypatch.setattr(gemini.genai, "Client", boom)

    result = gemini.extract_load("Dallas TX to Memphis TN, $1,900", None, None)

    assert "couldn't read" in result.warnings[0]


def test_no_key_falls_back_with_a_warning_first(monkeypatch):
    monkeypatch.setattr(gemini, "_api_key", lambda: None)

    result = gemini.extract_load("Dallas TX to Memphis TN, $1,900", None, None)

    assert "not configured" in result.warnings[0]


# --- nulls from Gemini ---------------------------------------------------------------------------
# Gemini returns an explicit null for anything the offer doesn't state. payment_terms_days and
# quick_pay_fee_pct are non-optional on Load, and dict.get(key, default) keeps a present null, so
# this used to raise ValidationError and surface as a 502 on /api/extract.

def test_null_payment_terms_fall_back_to_defaults():
    data = {
        "origin": {"city": "Richmond, VA"},
        "destination": {"city": "Charlotte, NC"},
        "rate_usd": 2400,
        "loaded_miles_est": 300,
        "payment_terms_days": None,
        "quick_pay_fee_pct": None,
    }

    result = validate_extracted_load(data, "pasted")

    assert result.load.payment_terms_days == 30
    assert result.load.quick_pay_fee_pct == 0.03


def test_a_stated_zero_fee_is_kept():
    """0% is a real answer, not a missing one — `or` would quietly overwrite it."""
    data = {
        "origin": {"city": "Richmond, VA"},
        "destination": {"city": "Charlotte, NC"},
        "rate_usd": 2400,
        "quick_pay_fee_pct": 0.0,
    }

    assert validate_extracted_load(data, "pasted").load.quick_pay_fee_pct == 0.0


def test_extract_does_not_raise_when_gemini_returns_unusable_fields(monkeypatch):
    """Gemini answered, but with a field Load rejects. A judge gets demo values, never a 502."""
    monkeypatch.setattr(gemini, "_api_key", lambda: "test-key")

    class _Response:
        text = '{"origin": "Dallas, TX", "destination": "Memphis, TN", "rate_usd": 1900, "weight_lbs": "heavy"}'

    class _Models:
        def generate_content(self, **kw):
            return _Response()

    monkeypatch.setattr(gemini.genai, "Client", lambda **kw: type("C", (), {"models": _Models()})())

    result = gemini.extract_load("Dallas TX to Memphis TN", None, None)

    assert "couldn't read" in result.warnings[0]


def test_a_transient_server_error_is_retried(monkeypatch):
    """One 5xx shouldn't drop the demo to canned data."""
    monkeypatch.setattr(gemini, "_api_key", lambda: "test-key")
    calls = []

    class _Response:
        text = '{"origin": "Dallas, TX", "destination": "Memphis, TN", "rate_usd": 1900}'

    class _Models:
        def generate_content(self, **kw):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("500 server error")
            return _Response()

    monkeypatch.setattr(gemini.genai, "Client", lambda **kw: type("C", (), {"models": _Models()})())

    result = gemini.extract_load("Dallas TX to Memphis TN, $1,900", None, None)

    assert len(calls) == 2
    assert result.load.origin.city == "Dallas, TX"
    assert result.warnings == [] or "couldn't read" not in result.warnings[0]


# --- the 20-reads-a-day budget --------------------------------------------------------------------
# Free-tier Gemini allows 20 generate_content calls per day per model. Running out must read as
# "we're out of reads", not "your offer was unreadable" — those need different reactions on stage.

class _Quota(Exception):
    def __str__(self):
        return "429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generate_content_free_tier_requests"


def test_quota_error_is_recognised():
    assert gemini._is_quota_error(_Quota())
    assert not gemini._is_quota_error(RuntimeError("connection reset"))


def test_running_out_of_reads_says_so(monkeypatch):
    monkeypatch.setattr(gemini, "_api_key", lambda: "test-key")

    class _Models:
        def generate_content(self, **kw):
            raise _Quota()

    monkeypatch.setattr(gemini.genai, "Client", lambda **kw: type("C", (), {"models": _Models()})())

    result = gemini.extract_load("Dallas TX to Memphis TN, $1,900", None, None)

    assert "Out of Gemini reads for today" in result.warnings[0]
    assert str(gemini.DAILY_LIMIT) in result.warnings[0]


def test_quota_error_is_not_retried(monkeypatch):
    """Retrying a spent daily quota just makes a judge wait twice for the same answer."""
    monkeypatch.setattr(gemini, "_api_key", lambda: "test-key")
    calls = []

    class _Models:
        def generate_content(self, **kw):
            calls.append(1)
            raise _Quota()

    monkeypatch.setattr(gemini.genai, "Client", lambda **kw: type("C", (), {"models": _Models()})())

    gemini.extract_load("Dallas TX to Memphis TN, $1,900", None, None)

    assert len(calls) == 1


def test_health_reports_the_read_budget():
    body = TestClient(app).get("/api/health").json()["gemini_reads"]

    assert body["daily_limit"] == 20
    assert "used" in body and "exhausted" in body
