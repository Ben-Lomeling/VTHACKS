"""Gemini: extract load offers, explain results, write counter-offer messages.

Owner: GEMINI teammate. STUB (Phase 0) — replace the internals, keep the signatures (SPEC.md
"Module interfaces"). Set STATUS = "live" once the real Gemini calls are in.
"""
import math
import uuid

from app.models import ExtractionResult, Load, LoadEconomics, Place

STATUS = "stub"


def extract_load(text: str | None, image_bytes: bytes | None, mime_type: str | None) -> ExtractionResult:
    load = Load(
        id="P" + uuid.uuid4().hex[:6],
        origin=Place(city="Roanoke, VA", lat=37.271, lng=-79.9414),
        destination=Place(city="Charlotte, NC", lat=35.2271, lng=-80.8431),
        pickup_window_start="2026-09-22T08:00:00",
        pickup_window_end="2026-09-22T12:00:00",
        delivery_by="2026-09-23T08:00:00",
        rate_usd=1200.0,
        loaded_miles_est=500.0,
        trailer_type="dry_van",
        weight_lbs=38000,
        commodity="paper products",
        broker="Blue Ridge Logistics",
        source="screenshot" if image_bytes else "pasted",
    )
    confidence = {f: "high" for f in Load.model_fields if f not in ("id", "source")}
    confidence["loaded_miles_est"] = "low"
    return ExtractionResult(
        load=load, confidence=confidence,
        warnings=["Loaded miles not stated in the offer; estimated"],
    )


def explain(payload: dict) -> str:
    econ = payload.get("economics") or {}
    verdict = econ.get("verdict", "negotiate")
    cpm = econ.get("true_net_cpm", 0.53)
    return f"Verdict: {verdict}. After the empty miles and your costs, you keep about ${cpm:.2f} a mile."


def counter_message(economics: LoadEconomics, broker: str | None) -> str:
    rate = int(math.ceil(economics.counter_offer_rate / 25.0) * 25)
    who = broker or "there"
    return f"Hi {who}, thanks for the offer on this load. I can run it for ${rate:,} all in. Let me know."
