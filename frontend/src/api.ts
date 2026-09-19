import type {
  TruckProfile,
  Load,
  LoadEconomics,
  ExtractionResult,
  Chain,
  CashflowCheck,
  CostsFromBank,
  ExplainRequest,
  TextResponse,
  Health,
  ChainsRequest,
} from "./types";
import { mockRequest } from "./mocks";
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";
const base = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");
async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  if (USE_MOCKS) return mockRequest(path, method, body) as Promise<T>;
  const multipart = body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(`${base}/api/${path}`, {
      method,
      headers:
        body && !multipart ? { "Content-Type": "application/json" } : undefined,
      body: body ? (multipart ? body : JSON.stringify(body)) : undefined,
      signal: AbortSignal.timeout(60000),
    });
  } catch {
    throw new Error(
      "Cannot reach the API. Check that the backend is running on port 8000, then try again.",
    );
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      typeof error?.detail === "string"
        ? error.detail
        : `Request failed (${response.status}). Check the fields and try again.`,
    );
  }
  return response.json();
}
export const api = {
  getProfile: () => request<TruckProfile>("profile"),
  saveProfile: (profile: TruckProfile) =>
    request<TruckProfile>("profile", "PUT", profile),
  extract: (text: string, image?: File) => {
    const body = new FormData();
    if (text.trim()) body.append("text", text);
    if (image) body.append("image", image);
    return request<ExtractionResult>("extract", "POST", body);
  },
  evaluate: (load: Load) =>
    request<LoadEconomics>("evaluate", "POST", { load }),
  offers: (loads: Load[]) =>
    request<LoadEconomics[]>("offers", "POST", { loads }),
  chains: (body: ChainsRequest) => request<Chain[]>("chains", "POST", body),
  board: () => request<Load[]>("board"),
  bankCosts: () => request<CostsFromBank>("costs/from-bank"),
  cashflow: (chain: Chain) =>
    request<CashflowCheck>("cashflow", "POST", { chain }),
  explain: (body: ExplainRequest) =>
    request<TextResponse>("explain", "POST", body),
  counterMessage: (economics: LoadEconomics) =>
    request<TextResponse>("counter-message", "POST", { economics }),
  health: () => request<Health>("health"),
};
