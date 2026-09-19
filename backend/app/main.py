"""FastAPI routes only; no business logic. Owner: Nischal.

Run from backend/:  uvicorn app.main:app --reload
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import cashflow, gemini, geo, nessie, optimizer, profit
from app.models import (
    CashflowCheck, CashflowRequest, Chain, ChainsRequest, CostsFromBank, CounterRequest,
    EvaluateRequest, ExplainRequest, ExtractionResult, Load, LoadEconomics, OffersRequest,
    TextResponse, TruckProfile,
)

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"
load_dotenv(BACKEND.parent / ".env")
load_dotenv(BACKEND / ".env")


def demo_now() -> datetime:
    """The app's clock. DEMO_NOW in .env pins it so the simulated board's dates line up."""
    raw = os.getenv("DEMO_NOW", "2026-09-21T06:00")
    return datetime.fromisoformat(raw) if raw else datetime.now()


def _read_board() -> list[Load]:
    raw = json.loads((DATA / "seed_loads.json").read_text())
    return [Load.model_validate(x) for x in raw["loads"]]


PROFILE: TruckProfile = TruckProfile.model_validate_json((DATA / "profile.json").read_text())
BOARD: dict[str, Load] = {l.id: l for l in _read_board()}
PASTED: dict[str, Load] = {}   # pasted/screenshot loads seen by /evaluate or /offers, by id

app = FastAPI(title="LoadCheck API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _all_loads() -> dict[str, Load]:
    return {**BOARD, **PASTED}


def _evaluate(load: Load) -> LoadEconomics:
    """Resolve places, fill loaded miles if missing, then hand off to profit.evaluate_load."""
    here, _ = geo.resolve(PROFILE.current_location)
    origin, _ = geo.resolve(load.origin)
    dest, _ = geo.resolve(load.destination)
    try:
        loaded = load.loaded_miles_est or geo.distance_miles(origin, dest)
        deadhead = geo.distance_miles(here, origin)
        return profit.evaluate_load(load, PROFILE, deadhead, loaded)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _remember(load: Load) -> None:
    if load.source != "simulated":
        PASTED[load.id] = load


@app.get("/api/health")
def health() -> dict:
    return {
        "modules": {
            "profit": profit.STATUS, "geo": geo.STATUS, "optimizer": optimizer.STATUS,
            "cashflow": cashflow.STATUS, "gemini": gemini.STATUS, "nessie": nessie.STATUS,
        },
        "demo_now": demo_now().isoformat(),
        "board_loads": len(BOARD),
        "pasted_loads": len(PASTED),
    }


@app.get("/api/profile", response_model=TruckProfile)
def get_profile() -> TruckProfile:
    return PROFILE


@app.put("/api/profile", response_model=TruckProfile)
def put_profile(profile: TruckProfile) -> TruckProfile:
    """Save the profile. Home and current location can be any US city; we look up their coordinates."""
    global PROFILE
    home, w1 = geo.resolve(profile.home)
    here, w2 = geo.resolve(profile.current_location)
    if home.lat is None or here.lat is None:
        raise HTTPException(status_code=422, detail="; ".join(w1 + w2) or "Couldn't place that city")
    PROFILE = profile.model_copy(update={"home": home, "current_location": here})
    return PROFILE


@app.post("/api/extract", response_model=ExtractionResult)
async def extract(text: str | None = Form(None), image: UploadFile | None = File(None)) -> ExtractionResult:
    if not text and image is None:
        raise HTTPException(status_code=400, detail="Send pasted text, an image, or both.")
    image_bytes = await image.read() if image is not None else None
    mime = image.content_type if image is not None else None
    try:
        result = gemini.extract_load(text, image_bytes, mime)
    except Exception as e:  # Gemini errors/timeouts surface to the UI
        raise HTTPException(status_code=502, detail=f"Extraction failed: {e}")
    # Gemini reads city names, not coordinates. Place them here so the confirm form and the map have them.
    origin, w1 = geo.resolve(result.load.origin)
    destination, w2 = geo.resolve(result.load.destination)
    load = result.load.model_copy(update={"origin": origin, "destination": destination})
    return result.model_copy(update={"load": load, "warnings": result.warnings + w1 + w2})


@app.post("/api/evaluate", response_model=LoadEconomics)
def evaluate(req: EvaluateRequest) -> LoadEconomics:
    _remember(req.load)
    return _evaluate(req.load)


@app.post("/api/offers", response_model=list[LoadEconomics])
def offers(req: OffersRequest) -> list[LoadEconomics]:
    for l in req.loads:
        _remember(l)
    results = [_evaluate(l) for l in req.loads]
    return sorted(results, key=lambda e: e.true_net_cpm, reverse=True)


@app.post("/api/chains", response_model=list[Chain])
def chains(req: ChainsRequest) -> list[Chain]:
    known = _all_loads()
    missing = [i for i in req.seed_load_ids if i not in known]
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown load ids (evaluate them first): {missing}")
    pool = {i: known[i] for i in req.seed_load_ids}
    if req.include_board:
        pool.update(BOARD)
    start, _ = geo.resolve(PROFILE.current_location)
    resolved = [
        l.model_copy(update={"origin": geo.resolve(l.origin)[0], "destination": geo.resolve(l.destination)[0]})
        for l in pool.values()
    ]
    return optimizer.best_chains(PROFILE, start, demo_now(), resolved, top_k=3)


@app.get("/api/board", response_model=list[Load])
def board() -> list[Load]:
    return list(BOARD.values())


@app.get("/api/costs/from-bank", response_model=CostsFromBank)
def costs_from_bank() -> CostsFromBank:
    return CostsFromBank.model_validate(nessie.get_costs_from_bank(PROFILE))


@app.post("/api/cashflow", response_model=CashflowCheck)
def cashflow_check(req: CashflowRequest) -> CashflowCheck:
    return cashflow.simulate(
        req.chain, _all_loads(), nessie.get_checking_balance(),
        nessie.get_upcoming_bills(60), demo_now().date(),
    )


@app.post("/api/explain", response_model=TextResponse)
def explain(req: ExplainRequest) -> TextResponse:
    return TextResponse(text=gemini.explain(req.model_dump(mode="json")))


@app.post("/api/counter-message", response_model=TextResponse)
def counter_message(req: CounterRequest) -> TextResponse:
    load = _all_loads().get(req.economics.load_id)
    return TextResponse(text=gemini.counter_message(req.economics, load.broker if load else None))
