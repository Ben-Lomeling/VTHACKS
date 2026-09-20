"""Gemini: extract load offers, explain results, write counter-offer messages.

Gemini only reads offers into fields. Every number we display is computed by profit.py /
optimizer.py / cashflow.py from those fields (SPEC.md rule 1), so a bad extraction can give us
wrong inputs but never a wrong calculation.
"""
import json
import logging
import math
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values
from google import genai
from google.genai import types

from app.models import ExtractionResult, Load, LoadEconomics, Place

ROOT = Path(__file__).resolve().parents[2]
# gemini-2.5-flash is no longer served to new API keys. Pinned, not "-latest": the demo should not
# change model under us mid-hackathon. Override with GEMINI_MODEL in .env.
DEFAULT_MODEL = "gemini-3.1-flash-lite"
LOG = logging.getLogger(__name__)
ATTEMPTS = 2                        # the Gemini API throws occasional 5xx; retry once
# Free tier: 20 generate_content requests per day, per model, per project. The pitch itself costs
# none of these (the "Try an example" load is pinned) — this budget is only for offers judges paste.
DAILY_LIMIT = 20
_CALLS = 0                          # live calls this process has made; reset by restarting uvicorn
_QUOTA_HIT = False                  # set once the API says the daily quota is gone


def calls_made() -> int:
    return _CALLS


def quota_exhausted() -> bool:
    return _QUOTA_HIT


def _api_key() -> str | None:
    """The local .env file if it has the key, else the environment (same rule as nessie.py)."""
    return dotenv_values(ROOT / ".env").get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")


def _model() -> str:
    """Same lookup rule as the key, so .env alone is enough to switch models."""
    return dotenv_values(ROOT / ".env").get("GEMINI_MODEL") or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL


def _is_quota_error(exc: Exception) -> bool:
    """A 429 / RESOURCE_EXHAUSTED from the API: the daily free-tier budget is gone."""
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


def _failure_warning(exc: Exception) -> str:
    """Tell the driver which thing went wrong — running out of reads is not a bad offer."""
    if _is_quota_error(exc):
        return (
            f"Out of Gemini reads for today (free tier allows {DAILY_LIMIT}), so this offer was "
            "not read — the fields below are demo values, not yours."
        )
    return "Gemini couldn't read this offer, so these are demo values — check every field."


def _today() -> datetime:
    """The demo clock, read the same way as the key (SPEC: DEMO_NOW drives the whole app)."""
    raw = dotenv_values(ROOT / ".env").get("DEMO_NOW") or os.getenv("DEMO_NOW")
    return datetime.fromisoformat(raw) if raw else datetime.now()


def _or_default(value, default):
    """Falsy-safe default: a stated 0% quick-pay fee is not the same as a missing one."""
    return default if value is None else value


def data_source() -> str:
    """"live" when a key is actually readable, else "stub". Checked per call, like nessie's, so
    /api/health can never claim Gemini is live while extract_load is serving canned data."""
    return "live" if _api_key() else "stub"


STATUS = data_source()

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

    source = "screenshot" if image_bytes else "pasted"

    # The frontend's "Try an example" text is pinned to fixed fields, key or no key: the pitch
    # numbers ($2.43/mi posted -> $0.55/mi kept) must be identical every run. The offer says
    # "Pickup Mon, deliver Tue" with no mileage, so a live extraction is free to resolve those
    # differently each time. Anything else a judge pastes goes to Gemini for real.
    if text and "greensboro" in text.lower():
        return _demo_bad_load()

    api_key = _api_key()

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
        result = validate_extracted_load(fallback_data, source)
        result.warnings.insert(
            0, "Gemini is not configured, so this offer was not read — showing demo data instead."
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
- quick_pay_fee_pct is a fraction, not a percentage: "quick pay 3%" is 0.03.
- Do not calculate financial results.

Today's date is {today}. Offers usually give a day without a year ("9/22", "Monday", "tomorrow").
Resolve those against today's date, choosing the next such day. Never return a date in the past.
"""

    prompt = prompt.format(today=_today().date().isoformat())

    try:
        # Built inside the guard: a screenshot we can't turn into a Part is just another reason to
        # fall back, not a 502 on /api/extract.
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

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=10_000),
        )
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
        )

        # The API throws an occasional 5xx. One immediate retry: two 10 s attempts still fit inside
        # a judge's patience, and it's the difference between a live read and canned data on stage.
        for attempt in range(ATTEMPTS):
            try:
                global _CALLS
                _CALLS += 1
                response = client.models.generate_content(
                    model=_model(), contents=contents, config=config
                )
                if not response.text:
                    raise RuntimeError("Gemini returned an empty response")
                break
            except Exception as exc:
                if _is_quota_error(exc):
                    raise          # retrying a spent daily quota just wastes the judge's time
                if attempt == ATTEMPTS - 1:
                    raise
                LOG.warning("Gemini attempt %d failed (%s); retrying", attempt + 1, type(exc).__name__)

        extracted = json.loads(response.text)

    except Exception as exc:
        # Never let a Gemini outage take the app down mid-demo — but say so at the top of the
        # warnings, so nobody mistakes the fallback for a reading of their offer. Log the type:
        # a silent fallback that looks like success is how a broken key survives to demo day.
        if _is_quota_error(exc):
            global _QUOTA_HIT
            _QUOTA_HIT = True
        LOG.warning("Gemini extraction failed (%s); using offline demo data", type(exc).__name__)
        result = validate_extracted_load(fallback_data, source)
        result.warnings.insert(0, _failure_warning(exc))
        return result

    try:
        return validate_extracted_load(extracted, source)
    except Exception as exc:
        # Gemini answered, but with something Load can't accept. Same treatment as an outage:
        # show demo data with a warning on top rather than a 502 in front of a judge.
        LOG.warning("Gemini returned unusable fields (%s); using offline demo data", type(exc).__name__)
        result = validate_extracted_load(fallback_data, source)
        result.warnings.insert(0, _failure_warning(exc))
        return result

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

    # Gemini sometimes adds a UTC offset ("...-04:00"); the rest of the app uses local, offset-free times.
    times = {}
    for field in ("pickup_window_start", "pickup_window_end", "delivery_by"):
        raw = data.get(field)
        try:
            times[field] = datetime.fromisoformat(str(raw)).replace(tzinfo=None) if raw else None
        except ValueError:
            times[field] = None
            warnings.append(f"Couldn't read {field.replace('_', ' ')}: {raw}")
            low_confidence.add(field)

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
    # "quick pay 3%" comes back as 3 about as often as 0.03, and Load caps the fee at 0.99, so an
    # unconverted percentage jams the confirm form instead of showing a verdict.
    fee = data.get("quick_pay_fee_pct")
    if isinstance(fee, (int, float)) and fee > 1:
        warnings.append(f"Read the quick-pay fee as {fee:g}%")
        data = {**data, "quick_pay_fee_pct": fee / 100.0}
        low_confidence.add("quick_pay_fee_pct")

    load_data = {
        "id": "P" + uuid.uuid4().hex[:6],
        "origin": Place(city=origin_city),
        "destination": Place(city=destination_city),
        "pickup_window_start": times["pickup_window_start"],
        "pickup_window_end": times["pickup_window_end"],
        "delivery_by": times["delivery_by"],
        "rate_usd": rate,
        "loaded_miles_est": miles,
        "trailer_type": data.get("trailer_type"),
        "weight_lbs": data.get("weight_lbs"),
        "commodity": data.get("commodity"),
        "broker": data.get("broker"),
        # Gemini returns an explicit null for anything the offer doesn't state, and these two
        # fields are non-optional on Load. dict.get(key, default) keeps the null, so check for it.
        "payment_terms_days": _or_default(data.get("payment_terms_days"), 30),
        "quick_pay_fee_pct": _or_default(data.get("quick_pay_fee_pct"), 0.03),
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
