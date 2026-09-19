import initialProfile from "./profile.json";
import boardData from "./board.json";
import type {
  TruckProfile,
  Load,
  LoadEconomics,
  Chain,
  ExplainRequest,
} from "../types";
export const defaultProfile = initialProfile as TruckProfile;
let profile = structuredClone(defaultProfile);
const board = boardData.loads as Load[];
const remembered = new Map<string, Load>();
// Fixed fixtures deliberately match the backend stubs. Never use these as live financial calculations.
const economics = (id: string): LoadEconomics => ({
  load_id: id,
  deadhead_miles: 100,
  loaded_miles: 500,
  total_miles: 600,
  posted_rpm: 2.4,
  fuel_cost: 342.97,
  variable_cost: 120,
  fixed_cost: 300,
  dispatch_fee: 120,
  net_profit: 317.03,
  true_net_cpm: 0.5284,
  break_even_rate: 847.75,
  counter_offer_rate: 1347.75,
  verdict: "negotiate",
});
export async function mockRequest(
  path: string,
  method: string,
  body: unknown,
): Promise<unknown> {
  switch (path) {
    case "profile":
      if (method === "PUT") profile = structuredClone(body as TruckProfile);
      return structuredClone(profile);
    case "health":
      return {
        modules: Object.fromEntries(
          ["profit", "geo", "optimizer", "cashflow", "gemini", "nessie"].map(
            (k) => [k, "stub"],
          ),
        ),
        demo_now: "2026-09-21T06:00:00",
        board_loads: board.length,
        pasted_loads: remembered.size,
      };
    case "board":
      return structuredClone(board);
    case "extract":
      return {
        load: {
          id: `P${crypto.randomUUID().slice(0, 6)}`,
          origin: { city: "Roanoke, VA", lat: 37.271, lng: -79.9414 },
          destination: { city: "Charlotte, NC", lat: 35.2271, lng: -80.8431 },
          pickup_window_start: "2026-09-22T08:00:00",
          pickup_window_end: "2026-09-22T12:00:00",
          delivery_by: "2026-09-23T08:00:00",
          rate_usd: 1200,
          loaded_miles_est: 500,
          trailer_type: "dry_van",
          weight_lbs: 38000,
          commodity: "paper products",
          broker: "Blue Ridge Logistics",
          payment_terms_days: 30,
          quick_pay_fee_pct: 0.03,
          source: (body as FormData).has("image") ? "screenshot" : "pasted",
        },
        confidence: { loaded_miles_est: "low", rate_usd: "high" },
        warnings: [
          "Demo fixture: this sample does not parse your input. Loaded miles need confirmation.",
        ],
      };
    case "evaluate": {
      const { load } = body as { load: Load };
      remembered.set(load.id, load);
      return economics(load.id);
    }
    case "offers":
      return (body as { loads: Load[] }).loads.map((load) => {
        remembered.set(load.id, load);
        return economics(load.id);
      });
    case "chains": {
      const request = body as {
        seed_load_ids?: string[];
        include_board?: boolean;
      };
      const pool = [
        ...(request.seed_load_ids || [])
          .map((id) => remembered.get(id))
          .filter((l): l is Load => !!l),
        ...(request.include_board === false ? [] : board),
      ];
      if (!pool.length) return [];
      return [0, 1, 2]
        .filter((i) => i < pool.length)
        .map((i) => {
          const picked = pool.slice(i, i + 3);
          const legs = picked.map((l) => economics(l.id));
          const total = legs.reduce((n, l) => n + l.net_profit, 0) - 95;
          return {
            loads: picked.map((l) => l.id),
            legs,
            home_deadhead_miles: 120,
            home_deadhead_cost: 95,
            total_net_profit: total,
            total_miles: legs.length * 600 + 120,
            days: 3.5,
            net_per_day: total / 3.5,
            ends_at: picked[picked.length - 1].destination,
            feasible_notes: [
              "Illustrative route fixture",
              `10-h rest before ${picked[picked.length - 1].id}`,
            ],
            schedule: picked.map((l, j) => ({
              load_id: l.id,
              depart_at: `2026-09-${21 + j}T06:00:00`,
              pickup_at: `2026-09-${21 + j}T08:00:00`,
              delivered_at: `2026-09-${21 + j}T20:00:00`,
            })),
          } satisfies Chain;
        });
    }
    case "costs/from-bank":
      return {
        current: structuredClone(profile),
        proposed: {
          ...profile,
          fuel_price: 3.92,
          variable_cpm: 0.27,
          fixed_monthly: 3315,
          cost_source: "nessie",
        },
        evidence: {
          source: "stub",
          window_days: 90,
          fuel_gallons: 4210.5,
          fuel_spend: 16505.16,
          maintenance_spend: 8100,
          miles_90d: profile.miles_per_month * 3,
        },
      };
    case "cashflow":
      return {
        starting_balance: 2500,
        lowest_balance: -494.03,
        lowest_balance_date: "2026-09-23",
        shortfall: true,
        quick_pay_fixes_it: true,
        quick_pay_cost: 36,
        timeline: [
          { date: "2026-09-21", label: "Checking balance today", amount: 0, balance: 2500 },
          { date: "2026-09-21", label: "Diesel for L027", amount: -244.95, balance: 2255.05 },
          { date: "2026-09-22", label: "Diesel for L058", amount: -417.59, balance: 1837.46 },
          { date: "2026-09-22", label: "Truck payment", amount: -2150, balance: -312.54 },
          { date: "2026-09-23", label: "Diesel for L012", amount: -181.49, balance: -494.03 },
        ],
        later: [
          { date: "2026-10-21", label: "Pay for L027 (Blue Ridge Logistics)", amount: 1080 },
          { date: "2026-10-23", label: "Pay for L058 (Summit Carrier Services)", amount: 1530 },
          { date: "2026-10-23", label: "Pay for L012 (Piedmont Transport Group)", amount: 765 },
        ],
      };
    case "explain": {
      const { economics: e } = body as ExplainRequest;
      return {
        text: `After empty miles and your costs, you keep $${e.true_net_cpm.toFixed(2)} per mile. Confirm the offer details before deciding.`,
      };
    }
    case "counter-message": {
      const { economics: e } = body as { economics: LoadEconomics };
      return {
        text: `Thanks for the offer. I can run this load for $${e.counter_offer_rate.toFixed(2)} all in. Let me know if that works.`,
      };
    }
    default:
      throw new Error(`Missing mock route: ${path}`);
  }
}
