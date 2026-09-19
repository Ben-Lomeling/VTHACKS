"""Gemini: extract load offers, explain results, write counter-offer messages.

Owner: GEMINI teammate. STUB (Phase 0) — replace the internals, keep the signatures (SPEC.md
"Module interfaces"). Set STATUS = "live" once the real Gemini calls are in.
"""
import json
import math
import os
import uuid


from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.models import ExtractionResult, Load, LoadEconomics, Place

load_dotenv()

STATUS = "stub"

def _demo_bad_load() -> ExtractionResult:
    """Return the bad-load example used by the frontend demo."""
    load = Load(
        id="P" + uuid.uuid4().hex[:6],
        origin=Place(city="Greensboro, NC"),
        destination=Place(city="Jacksonville, FL"),
        rate_usd=1200.0,
        trailer_type="dry_van",
        weight_lbs=40000,
        broker="Coastal Brokerage",
        source="pasted",
    )

    confidence = {
        field: "high"
        for field in Load.model_fields
        if field not in ("id", "source")
    }

    for field in (
        "loaded_miles_est",
        "pickup_window_start",
        "pickup_window_end",
        "delivery_by",
    ):
        confidence[field] = "low"

    return ExtractionResult(
        load=load,
        confidence=confidence,
        warnings=[
            "Loaded miles not stated in the offer; estimated",
            'Pickup and delivery times are vague ("Mon", "Tue"); check them',
        ],
    )

def extract_load(
    text: str | None,
    image_bytes: bytes | None,
    mime_type: str | None,
) -> ExtractionResult:
    """Extract load information from pasted text, an image, or both."""

    if not text and not image_bytes:
        raise ValueError("Provide pasted text, an image, or both")

    api_key = os.getenv("GEMINI_API_KEY")
    source = "screenshot" if image_bytes else "pasted"

    fallback_data = {
        "origin": {"city": "Roanoke, VA"},
        "destination": {"city": "Charlotte, NC"},
        "pickup_window_start": "2026-09-22T08:00:00",
        "pickup_window_end": "2026-09-22T12:00:00",
        "delivery_by": "2026-09-23T08:00:00",
        "rate_usd": 1200.0,
        "loaded_miles_est": 500.0,
        "trailer_type": "dry_van",
        "weight_lbs": 38000,
        "commodity": "paper products",
        "broker": "Blue Ridge Logistics",
        "payment_terms_days": 30,
        "quick_pay_fee_pct": 0.03,
    }

    if not api_key:
        if text and "greensboro" in text.lower():
            return _demo_bad_load()

        result = validate_extracted_load(fallback_data, source)
        result.warnings.append(
            "Gemini API key is not configured; using offline demo data"
        )
        return result

    schema = {
        "type": "OBJECT",
        "properties": {
            "origin": {
                "type": "STRING",
                "nullable": True,
            },
            "destination": {
                "type": "STRING",
                "nullable": True,
            },
            "pickup_window_start": {
                "type": "STRING",
                "nullable": True,
            },
            "pickup_window_end": {
                "type": "STRING",
                "nullable": True,
            },
            "delivery_by": {
                "type": "STRING",
                "nullable": True,
            },
            "rate_usd": {
                "type": "NUMBER",
                "nullable": True,
            },
            "loaded_miles_est": {
                "type": "NUMBER",
                "nullable": True,
            },
            "trailer_type": {
                "type": "STRING",
                "nullable": True,
            },
            "weight_lbs": {
                "type": "INTEGER",
                "nullable": True,
            },
            "commodity": {
                "type": "STRING",
                "nullable": True,
            },
            "broker": {
                "type": "STRING",
                "nullable": True,
            },
            "payment_terms_days": {
                "type": "INTEGER",
                "nullable": True,
            },
            "quick_pay_fee_pct": {
                "type": "NUMBER",
                "nullable": True,
            },
        },
    }

    prompt = """
Extract the truck-load offer into the provided JSON schema.

Rules:
- Never invent information.
- Return null for any information that is not present.
- Format every location as "City, ST" when both are available.
- Keep a location without a state exactly as written.
- rate_usd should be the total linehaul payment.
- If the offer only provides a per-mile rate, return that original
  per-mile number. Python validation will convert it when possible.
- Use ISO 8601 date and time strings when dates are present.
- Do not calculate financial results.
"""

    contents = [prompt]

    if text:
        contents.append(f"LOAD OFFER TEXT:\n{text}")

    if image_bytes:
        contents.append(
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type or "image/png",
            )
        )

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=10_000),
        )

        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
            ),
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response")

        extracted = json.loads(response.text)

    except Exception:
        if text and "greensboro" in text.lower():
            result = _demo_bad_load()
        else:
            result = validate_extracted_load(fallback_data, source)

        result.warnings.append(
            "Gemini unavailable; using offline demo data"
        )
        return result

    return validate_extracted_load(extracted, source)

def explain(payload: dict) -> str:
    econ = payload.get("economics") or {}
    verdict = econ.get("verdict", "negotiate")
    cpm = econ.get("true_net_cpm", 0.53)
    return f"Verdict: {verdict}. After the empty miles and your costs, you keep about ${cpm:.2f} a mile."


def counter_message(economics: LoadEconomics, broker: str | None) -> str:
    rate = int(math.ceil(economics.counter_offer_rate / 25.0) * 25)
    who = broker or "there"
    return f"Hi {who}, thanks for the offer on this load. I can run it for ${rate:,} all in. Let me know."


def validate_extracted_load(data: dict, source: str) -> ExtractionResult:
    """Validate Gemini-style data without calling the Gemini API."""
    warnings = []
    low_confidence = set()

    origin_data = data.get("origin") or {}
    destination_data = data.get("destination") or {}

    origin_city = origin_data.get("city", "") if isinstance(origin_data, dict) else str(origin_data)
    destination_city = (
        destination_data.get("city", "")
        if isinstance(destination_data, dict)
        else str(destination_data)
    )

    if not origin_city:
        warnings.append("Origin is missing")
        low_confidence.add("origin")
    elif "," not in origin_city:
        warnings.append(f"State missing for {origin_city}")
        low_confidence.add("origin")

        if not destination_city:
            warnings.append("Destination is missing")
        low_confidence.add("destination")
    elif "," not in destination_city:
        warnings.append(f"State missing for {destination_city}")
        low_confidence.add("destination")

    raw_rate = data.get("rate_usd")
    raw_miles = data.get("loaded_miles_est")

    try:
        rate = float(raw_rate)
    except (TypeError, ValueError):
        rate = 0.0

    try:
        miles = float(raw_miles) if raw_miles is not None else None
    except (TypeError, ValueError):
        miles = None
        warnings.append("Loaded miles are invalid")
        low_confidence.add("loaded_miles_est")

    if rate <= 0:
        warnings.append("Rate is missing or invalid")
        low_confidence.add("rate_usd")
        rate = 0.0
    elif rate < 20:
        if miles:
            original_rate = rate
            rate = rate * miles
            warnings.append(
                f"Converted ${original_rate:.2f}/mi to total rate"
            )
        else:
            warnings.append(
                "Rate may be per-mile, but loaded miles are missing"
            )
        low_confidence.add("rate_usd")
    load_data = {
        "id": "P" + uuid.uuid4().hex[:6],
        "origin": Place(city=origin_city),
        "destination": Place(city=destination_city),
        "pickup_window_start": data.get("pickup_window_start"),
        "pickup_window_end": data.get("pickup_window_end"),
        "delivery_by": data.get("delivery_by"),
        "rate_usd": rate,
        "loaded_miles_est": miles,
        "trailer_type": data.get("trailer_type"),
        "weight_lbs": data.get("weight_lbs"),
        "commodity": data.get("commodity"),
        "broker": data.get("broker"),
        "payment_terms_days": data.get("payment_terms_days", 30),
        "quick_pay_fee_pct": data.get("quick_pay_fee_pct", 0.03),
        "source": source,
    }

    load = Load(**load_data)

    if (
        load.pickup_window_start
        and load.delivery_by
        and load.pickup_window_start > load.delivery_by
    ):
        warnings.append("Pickup time is after delivery time")
        low_confidence.add("pickup_window_start")
        low_confidence.add("delivery_by")

    confidence = {}

    for field in Load.model_fields:
        if field in ("id", "source"):
            continue

        value = load_data.get(field)
        confidence[field] = (
            "low"
            if field in low_confidence or value is None or value == ""
            else "high"
        )

    return ExtractionResult(
        load=load,
        confidence=confidence,
        warnings=warnings,
    )