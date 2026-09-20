import runSamples from "./run-samples.json";
import initialProfile from "./profile.json";
import extractionSample from "./POST_extract.json";
import economicsSample from "./POST_evaluate.json";
import type {
  TruckProfile,
  Load,
  LoadEconomics,
  Chain,
  ExplainRequest,
} from "../types";
export const defaultProfile = initialProfile as TruckProfile;
let profile = structuredClone(defaultProfile);
const board = runSamples.loads as Load[];
const advanced = new Set<string>();
const remembered = new Map<string, Load>();
// Fixed fixtures deliberately match the backend stubs. Never use these as live financial calculations.
const economics = (id: string): LoadEconomics => ({...economicsSample, load_id: id}) as LoadEconomics;
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
      return {...structuredClone(extractionSample), load: {...extractionSample.load, id: `P${crypto.randomUUID().slice(0,6)}`, source: (body as FormData).has("image") ? "screenshot" : "pasted"}, warnings: ["Fixed demo example; your input is not analyzed.", ...extractionSample.warnings]};
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
      // Recorded backend responses, never recomputed financial values.
      if (request.include_board === false) return [];
      return structuredClone(runSamples.runs.map(r => r.chain));
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
    case "cashflow": {
      const { chain } = body as { chain: Chain };
      const sample = runSamples.runs.find(r => r.chain.loads.join() === chain.loads.join());
      if (!sample) throw new Error("No cash-flow fixture for this run.");
      return structuredClone(advanced.has(chain.loads.join()) ? sample.success : sample.cash);
    }
    case "advance": {
      const { chain, load_id } = body as { chain: Chain; load_id: string };
      const sample = runSamples.runs.find(r => r.chain.loads.join() === chain.loads.join());
      if (!sample || sample.cash.advance_offer?.load_id !== load_id) throw new Error("No advance fixture for this load.");
      advanced.add(chain.loads.join());
      return structuredClone(sample.success);
    }
    case "demo/reset-bank": {
      const removed = advanced.size;
      advanced.clear();
      return { removed };
    }
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
