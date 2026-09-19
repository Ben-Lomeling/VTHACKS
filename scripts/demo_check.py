"""Run the whole demo flow against the API and print PASS/FAIL per step. Run before every rehearsal.

  python scripts/demo_check.py                   # against a running server (http://localhost:8000)
  python scripts/demo_check.py --base-url URL    # somewhere else
  python scripts/demo_check.py --in-process      # no server needed (uses FastAPI's TestClient)

Exit code 0 only if every step passes.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.models import (  # noqa: E402
    CashflowCheck, Chain, CostsFromBank, ExtractionResult, Load, LoadEconomics, TruckProfile,
)

DEMO_TEXT = "GREENSBORO NC -> JACKSONVILLE FL  PU 9/21 0800  $1200 all in  dry van 38k lbs"
# The demo's "bad load" (stand-in until Dad's real text): 100 empty mi from Roanoke + ~493 loaded mi, $1,200 flat.
BAD_LOAD = {"id": "DEMO-BAD", "origin": {"city": "Greensboro, NC"}, "destination": {"city": "Jacksonville, FL"},
            "rate_usd": 1200, "trailer_type": "dry_van", "broker": "Coastal Brokerage", "source": "pasted"}
GREEN, RED, DIM, END = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def client_for(args):
    if args.in_process:
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)
    import httpx
    return httpx.Client(base_url=args.base_url, timeout=30)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--in-process", action="store_true")
    args = ap.parse_args()
    c = client_for(args)
    ctx: dict = {}
    results: list[bool] = []

    def step(name: str, fn):
        started = time.perf_counter()
        try:
            detail = fn() or ""
            ok = True
        except Exception as e:  # report and keep going so we see every failure at once
            detail, ok = f"{type(e).__name__}: {e}", False
        ms = (time.perf_counter() - started) * 1000
        tag = f"{GREEN}PASS{END}" if ok else f"{RED}FAIL{END}"
        print(f"{tag}  {name:<34} {DIM}{ms:6.0f} ms{END}  {detail}")
        results.append(ok)

    def ok(r):
        if r.status_code != 200:
            raise AssertionError(f"HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    def health():
        mods = ok(c.get("/api/health"))["modules"]
        return " ".join(f"{k}={v}" for k, v in mods.items())

    def profile():
        p = TruckProfile.model_validate(ok(c.get("/api/profile")))
        ctx["profile"] = p
        return f"{p.current_location.city}, {p.trailer_type}, cost_source={p.cost_source}"

    def extract():
        x = ExtractionResult.model_validate(ok(c.post("/api/extract", data={"text": DEMO_TEXT})))
        ctx["load"] = x.load
        low = [k for k, v in x.confidence.items() if v == "low"]
        return f"{x.load.origin.city} -> {x.load.destination.city} ${x.load.rate_usd:,.0f}; low={low}"

    def evaluate():
        e = LoadEconomics.model_validate(ok(c.post("/api/evaluate", json={"load": ctx["load"].model_dump(mode="json")})))
        ctx["econ"] = e
        return f"posted ${e.posted_rpm:.2f}/mi -> true ${e.true_net_cpm:.2f}/mi, {e.verdict}, counter ${e.counter_offer_rate:,.0f}"

    def offers():
        ranked = ok(c.post("/api/offers", json={"loads": [ctx["load"].model_dump(mode="json")]}))
        assert len(ranked) == 1
        return "ranked 1 offer"

    def counter():
        text = ok(c.post("/api/counter-message", json={"economics": ctx["econ"].model_dump(mode="json")}))["text"]
        assert "$" in text, "no dollar amount in the message"
        return text[:70]

    def explain_load():
        text = ok(c.post("/api/explain", json={"economics": ctx["econ"].model_dump(mode="json")}))["text"]
        return text[:70]

    def board():
        loads = [Load.model_validate(x) for x in ok(c.get("/api/board"))]
        assert loads and all(l.source == "simulated" for l in loads), "board must be all simulated"
        return f"{len(loads)} simulated loads"

    def chains():
        body = {"seed_load_ids": [ctx["load"].id], "include_board": True}
        runs = [Chain.model_validate(x) for x in ok(c.post("/api/chains", json=body))]
        assert runs, "no chains found"
        ctx["chain"] = runs[0]
        best = runs[0]
        rests = sum("rest" in n for n in best.feasible_notes)
        return (f"{len(runs)} runs; best {'>'.join(best.loads)} ${best.total_net_profit:,.0f} "
                f"in {best.days:.1f} d, ends {best.home_deadhead_miles:.0f} mi from home, {rests} rest(s)")

    def cashflow():
        cf = CashflowCheck.model_validate(ok(c.post("/api/cashflow", json={"chain": ctx["chain"].model_dump(mode="json")})))
        ctx["cashflow"] = cf
        fix = f", quick pay fixes it for ${cf.quick_pay_cost:,.0f}" if cf.quick_pay_fixes_it else ""
        return f"lowest ${cf.lowest_balance:,.0f} on {cf.lowest_balance_date}{fix}"

    def explain_run():
        body = {"economics": ctx["econ"].model_dump(mode="json"), "chain": ctx["chain"].model_dump(mode="json"),
                "cashflow": ctx["cashflow"].model_dump(mode="json")}
        return ok(c.post("/api/explain", json=body))["text"][:70]

    def bank():
        b = CostsFromBank.model_validate(ok(c.get("/api/costs/from-bank")))
        return (f"variable ${b.current.variable_cpm:.2f} -> ${b.proposed.variable_cpm:.2f}/mi, "
                f"source={b.evidence.get('source')}")

    # ---- story checks: does the data still tell the demo story? ----
    def story_bad_load():
        e = LoadEconomics.model_validate(ok(c.post("/api/evaluate", json={"load": BAD_LOAD})))
        ctx["bad"] = e
        assert 0.45 <= e.true_net_cpm <= 0.60, f"true net ${e.true_net_cpm:.2f}/mi, want ~$0.50"
        assert e.verdict != "take", "bad load should not be a 'take'"
        return f"${e.posted_rpm:.2f}/mi on paper -> ${e.true_net_cpm:.2f}/mi, net ${e.net_profit:,.0f}, {e.verdict}"

    def story_better_run():
        runs = [Chain.model_validate(x) for x in ok(c.post("/api/chains", json={"seed_load_ids": ["DEMO-BAD"], "include_board": True}))]
        best = runs[0]
        ctx["story_chain"] = best
        assert best.total_net_profit >= 3 * ctx["bad"].net_profit, "best run should clearly beat the bad load"
        assert best.home_deadhead_miles <= 150, "best run should end near home"
        assert any("rest" in n for n in best.feasible_notes), "want at least one visible rest stop"
        return f"{'>'.join(best.loads)} ${best.total_net_profit:,.0f} vs bad ${ctx['bad'].net_profit:,.0f}"

    def story_cashflow():
        cf = CashflowCheck.model_validate(ok(c.post("/api/cashflow", json={"chain": ctx["story_chain"].model_dump(mode="json")})))
        assert cf.shortfall and cf.quick_pay_fixes_it, "want: dips below zero, quick pay fixes it"
        return f"dips to ${cf.lowest_balance:,.0f} on {cf.lowest_balance_date}; quick pay fixes it for ${cf.quick_pay_cost:,.0f}"

    print(f"LoadCheck demo check -> {'in-process' if args.in_process else args.base_url}\n")
    for name, fn in [
        ("health", health), ("setup: profile", profile), ("setup: costs from bank", bank),
        ("check: extract pasted text", extract), ("check: evaluate", evaluate), ("check: rank offers", offers),
        ("check: explain load", explain_load), ("check: counter message", counter),
        ("plan: simulated board", board), ("plan: chains", chains), ("plan: cash flow", cashflow),
        ("plan: explain run", explain_run),
        ("story: bad load ~ $0.50/mi", story_bad_load), ("story: better run, near home, rest", story_better_run),
        ("story: cash-flow dip + quick pay", story_cashflow),
    ]:
        needs = {"check: evaluate": "load", "check: rank offers": "load", "check: counter message": "econ",
                 "check: explain load": "econ", "plan: chains": "load", "plan: cash flow": "chain",
                 "plan: explain run": "cashflow", "story: better run, near home, rest": "bad",
                 "story: cash-flow dip + quick pay": "story_chain"}.get(name)
        if needs and needs not in ctx:
            print(f"{RED}SKIP{END}  {name:<34} (an earlier step failed)")
            results.append(False)
            continue
        step(name, fn)

    passed = sum(results)
    colour = GREEN if passed == len(results) else RED
    print(f"\n{colour}{passed}/{len(results)} passed{END}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
