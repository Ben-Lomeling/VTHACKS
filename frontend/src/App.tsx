import { useEffect, useState, useRef } from "react";
import { api, USE_MOCKS } from "./api";
import { defaultProfile } from "./mocks";
import type {
  TruckProfile,
  Load,
  ExtractionResult,
  LoadEconomics,
  Chain,
  CashflowCheck,
  CostsFromBank,
  Health,
} from "./types";
import { Field, PlaceFields } from "./components/Fields";
import { LoadForm } from "./components/LoadForm";
import { CapitalOneMark } from "./components/CapitalOneMark";
import { RunsWorkspace } from "./components/RunsWorkspace";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from "recharts";

const money = (n: number) =>
  n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
// The demo's "bad load": looks like $2.43/mi on paper, keeps about $0.55/mi.
const example =
  "Greensboro, NC → Jacksonville, FL. $1,200 flat. Dry van, 40,000 lbs. Coastal Brokerage. Pickup Mon, deliver Tue. Net 30.";
// Add ?dev to the URL to see which backend modules are live vs stub.
const DEV = new URLSearchParams(window.location.search).has("dev");
type Screen = "Setup" | "Check a load" | "Plan my run";
const profileNumbers: [keyof TruckProfile, string, string, number, number?][] =
  [
    ["mpg_loaded", "Loaded fuel economy", "Miles per gallon with a load", 0.1],
    ["mpg_empty", "Empty fuel economy", "Miles per gallon without a load", 0.1],
    ["fuel_price", "Diesel price ($/gal)", "Average price you pay", 0],
    [
      "variable_cpm",
      "Maintenance ($/mi)",
      "Include tires, repairs and tolls",
      0,
    ],
    [
      "fixed_monthly",
      "Fixed costs ($/month)",
      "Truck payment, insurance and permits",
      0,
    ],
    ["miles_per_month", "Monthly miles", "Used to spread fixed costs", 1],
    ["dispatch_pct", "Dispatcher share", "Decimal: 0.10 means 10%", 0, 0.99],
    [
      "target_net_cpm",
      "Target take-home ($/mi)",
      "Your minimum after every cost",
      0,
    ],
    [
      "min_posted_cpm",
      "My rule: minimum posted ($/mi)",
      "What you won't go under on the board. 0 = no rule",
      0,
    ],
  ];
export default function App() {
  const [screen, setScreen] = useState<Screen>("Check a load");   // the demo starts with a bad load
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => { headingRef.current?.focus(); }, [screen]);
  const [profile, setProfile] = useState<TruckProfile>();
  const [draft, setDraft] = useState<TruckProfile>();
  const [health, setHealth] = useState<Health>();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [text, setText] = useState("");
  const [image, setImage] = useState<File>();
  const [extraction, setExtraction] = useState<ExtractionResult>();
  const [result, setResult] = useState<LoadEconomics>();
  const [explanation, setExplanation] = useState("");
  const [message, setMessage] = useState("");
  const [offers, setOffers] = useState<Load[]>([]);
  const [ranked, setRanked] = useState<LoadEconomics[]>([]);
  const [board, setBoard] = useState<Load[]>([]);
  const [chains, setChains] = useState<Chain[]>([]);
  const [selected, setSelected] = useState(0);
  const [planned, setPlanned] = useState(false);
  const [planError, setPlanError] = useState("");
  const [includeBoard, setIncludeBoard] = useState(true);
  const [cash, setCash] = useState<CashflowCheck>();
  const [cashBusy, setCashBusy] = useState(false);
  const [cashError, setCashError] = useState("");
  const cashRequest = useRef(0);
  const [runExplanation, setRunExplanation] = useState("");
  const [bank, setBank] = useState<CostsFromBank>();
  // Accepting bank costs changes every number in the demo story, so it takes a second, explicit click.
  const [confirmBank, setConfirmBank] = useState(false);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 6000);
    return () => window.clearTimeout(timer);
  }, [toast]);
  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    setToast("");
    try {
      await fn();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setBusy("");
    }
  }
  async function connect() {
    const [p, h, b] = await Promise.all([
      api.getProfile(),
      api.health(),
      api.board(),
    ]);
    setProfile(p);
    setDraft(structuredClone(p));
    setHealth(h);
    setBoard(b);
  }
  useEffect(() => {
    void run("Connecting to LoadCheck…", connect);
  }, []);
  function invalidate() {
    setResult(undefined);
    setRanked([]);
    setChains([]);
    setCash(undefined);
    setPlanned(false);
    setPlanError("");
    setBank(undefined);
    setExplanation("");
    setMessage("");
    setRunExplanation("");
  }
  function pickImage(file?: File) {
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      setError("Choose a PNG, JPEG, or WebP screenshot.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Choose an image smaller than 10 MB.");
      return;
    }
    setImage(file);
    setError("");
  }
  useEffect(() => {
    setBank(undefined);
    setConfirmBank(false);
  }, [draft]);
  const chain = chains[selected];
  // A selection change or a newer refresh invalidates older cash-flow responses.
  async function refreshCash(selectedChain: Chain) {
    const request = ++cashRequest.current;
    setCashBusy(true);
    setCashError("");
    try {
      const value = await api.cashflow(selectedChain);
      if (request === cashRequest.current) setCash(value);
    } catch (e) {
      if (request === cashRequest.current) setCashError(e instanceof Error ? e.message : "Cash flow unavailable.");
    } finally {
      if (request === cashRequest.current) setCashBusy(false);
    }
  }
  useEffect(() => {
    setCash(undefined);
    setCashError("");
    setCashBusy(false);
    if (chain) void refreshCash(chain);
    return () => { cashRequest.current++; };
  }, [chain]);
  const allLoads = [...board, ...offers];
  const analyze = () =>
    run("Reading your offer…", async () => {
      const value = await api.extract(text, image);
      setExtraction(value);
      setResult(undefined);
      setExplanation("");
      setMessage("");
    });
  const calculate = (load: Load) =>
    run("Calculating every mile and cost…", async () => {
      const e = await api.evaluate(load);
      setResult(e);
      setExplanation("");
      setMessage("");
      setOffers((old) => [...old.filter((x) => x.id !== load.id), load]);
      setRanked([]);
      setChains([]);
      setCash(undefined);
      setPlanned(false);
      const reply = await api.explain({ economics: e });
      setExplanation(reply.text);
    });
  const plan = () =>
    run("Finding runs that bring you home…", async () => {
      setPlanError("");
      let c: Chain[];
      try {
        c = await api.chains({ seed_load_ids: offers.map(l => l.id), include_board: includeBoard });
      } catch (e) {
        setPlanError(e instanceof Error ? e.message : "Could not plan this run. Please try again.");
        return;
      }
      setChains(c);
      setSelected(0);
      setCash(undefined);
      setRunExplanation("");
      setPlanned(true);
      if (c[0]?.legs[0])
        setRunExplanation(
          await api.explain({ economics: c[0].legs[0], chain: c[0] })
            .then(reply => reply.text).catch(() => "Your run is ready. The explanation is temporarily unavailable."),
        );
    });
  return (
    <div className={`app-shell ${screen === "Plan my run" ? "runs-screen" : "secondary-screen"}`}>
      <aside className="app-navigation"><a className="brand" href="#" onClick={e=>{e.preventDefault();setScreen("Plan my run");}}>LoadCheck</a><nav aria-label="Main navigation">{(["Plan my run","Check a load","Setup"] as Screen[]).map(s=><button key={s} disabled={!!busy} className={screen===s?"nav-active":""} aria-current={screen===s?"page":undefined} onClick={()=>setScreen(s)}>{s==="Plan my run"?"Runs":s==="Setup"?"Truck settings":s}</button>)}</nav></aside>
      <main>
        <header>
          <span className="breadcrumb">
            Workspace <span>/</span> {screen}
          </span>
          <div className="header-actions">
            <span className="status-dot" />
            {USE_MOCKS ? "Mock demo" : health ? "API connected" : "API offline"}
            {/* Only when the bank really is live: the badge being here is itself the evidence. */}
            {!USE_MOCKS && health?.modules?.nessie === "live" && (
              <CapitalOneMark label="Bank data by" className="capone-mark-header" />
            )}
            <button
              className="text-button"
              disabled={!!busy || !profile}
              onClick={() =>
                void run("Resetting the demo…", async () => {
                  await api.resetBank(); // undo Capital One advances in the bank sandbox
                  const p = await api.saveProfile(
                    structuredClone(defaultProfile),
                  );
                  setProfile(p);
                  setDraft(structuredClone(p));
                  invalidate();
                  setExtraction(undefined);
                  setOffers([]);
                  setText("");
                  setImage(undefined);
                  setToast(
                    "Demo profile restored. Local offers and bank advances cleared.",
                  );
                })
              }
            >
              Reset demo ↺
            </button>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <h1 ref={headingRef} tabIndex={-1}>
              {screen === "Check a load"
                ? "Know what you keep."
                : screen === "Setup"
                  ? "Make it your truck."
                  : "Good miles. All the way home."}
            </h1>
            <p>
              {screen === "Check a load"
                ? "The posted rate is only half the story. See the full picture before you say yes."
                : screen === "Setup"
                  ? "Your costs make the difference. Set them once, check every offer."
                  : "Compare your next moves, then make sure your balance can handle the run."}
            </p>
          </div>
          {(USE_MOCKS ||
            (health &&
              Object.values(health.modules).some((x) => x !== "live"))) && (
            <div className="demo-strip">
              <span className="badge">DEMO DATA</span>
              {USE_MOCKS
                ? "Mock mode · fixed example responses; your input is not analyzed."
                : DEV
                  ? `Backend modules: ${Object.entries(health!.modules)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" · ")}`
                  : "Simulated load board."}
              <span>Nessie bank data is sandbox data.</span>
            </div>
          )}
          {busy && (
            <div className="loading" role="status">

              {busy}
            </div>
          )}
          {error && (
            <div className="error" role="alert">
              {error}{" "}
              <button
                onClick={() => void run("Reconnecting…", connect)}
                disabled={!!busy}
              >
                Reconnect
              </button>
            </div>
          )}
          {toast && (
            <div className="success" role="status">
              {toast}
            </div>
          )}
          {screen === "Check a load" && (
            <div className="check-layout">
              <div className="flow">
                <section className="card">
                  <div className="section-heading">
                    <div>
                      <p className="eyebrow">01 / THE OFFER</p>
                      <h2>What's on the table?</h2>
                    </div>
                    <button
                      className="text-button"
                      disabled={!!busy}
                      onClick={() => setText(example)}
                    >
                      Try an example ↗
                    </button>
                  </div>
                  <label className="field">
                    <span>Paste a load offer</span>
                    <textarea
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder={
                        "Pickup, delivery, pay. Paste the broker’s text or email here…"
                      }
                      rows={5}
                    />
                  </label>
                  <div
                    className="upload"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      pickImage(e.dataTransfer.files[0]);
                    }}
                  >
                    <span className="upload-icon">↑</span>
                    <label>
                      <strong>
                        {image ? image.name : "Or drop a screenshot"}
                      </strong>
                      <small>PNG, JPG or WebP · up to 10 MB</small>
                      <input
                        aria-label="Upload screenshot"
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        onChange={(e) => pickImage(e.target.files?.[0])}
                      />
                    </label>
                    {image && (
                      <button
                        className="text-button"
                        onClick={() => setImage(undefined)}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  <div className="card-footer">
                    <small>
                      You confirm the details before any calculation.
                    </small>
                    <button
                      className="primary"
                      disabled={!!busy || (!text.trim() && !image) || !profile}
                      onClick={() => void analyze()}
                    >
                      Read my offer →
                    </button>
                  </div>
                </section>
                {extraction && (
                  <LoadForm
                    key={extraction.load.id}
                    extraction={extraction}
                    onCalculate={calculate}
                    busy={!!busy}
                  />
                )}
                {result && (
                  <section className="card result">
                    <div className="section-heading">
                      <p className="eyebrow">03 / THE REAL NUMBER</p>
                      <span className={`badge ${result.verdict}`}>
                        {result.verdict}
                      </span>
                    </div>
                    <div className="result-numbers">
                      <div>
                        <small>POSTED PER LOADED MILE</small>
                        <del>{money(result.posted_rpm)}</del>
                        {result.meets_posted_rule != null && profile && (
                          <em className={result.meets_posted_rule ? "rule-ok" : "rule-no"}>
                            {result.meets_posted_rule ? "clears" : "below"} your{" "}
                            {money(profile.min_posted_cpm)}/mi rule
                          </em>
                        )}
                      </div>
                      <span>→</span>
                      <div>
                        <small>YOUR NET PER TOTAL MILE</small>
                        <strong>
                          {money(result.true_net_cpm)}
                          <small>/mi</small>
                        </strong>
                      </div>
                    </div>
                    <p>
                      {result.loaded_miles.toFixed(0)} loaded +{" "}
                      {result.deadhead_miles.toFixed(0)} empty ={" "}
                      {result.total_miles.toFixed(0)} total miles
                    </p>
                    <h3>Where the money goes</h3>
                    <p className="gross-pay">
                      Total load pay:{" "}
                      {money(
                        result.dispatch_fee +
                          result.fuel_cost +
                          result.variable_cost +
                          result.fixed_cost +
                          result.net_profit,
                      )}
                    </p>
                    <div
                      className="stacked-costs"
                      aria-label="Load pay split into costs and take-home"
                    >
                      {[
                        result.dispatch_fee,
                        result.fuel_cost,
                        result.variable_cost,
                        result.fixed_cost,
                        result.net_profit,
                      ].map((value, i) => (
                        <span
                          key={i}
                          className={`bar-${i}`}
                          style={{ flexGrow: Math.max(0, value) }}
                        />
                      ))}
                    </div>
                    <div className="cost-bars">
                      {(
                        [
                          ["Dispatcher", result.dispatch_fee],
                          ["Fuel", result.fuel_cost],
                          ["Maintenance", result.variable_cost],
                          ["Fixed costs", result.fixed_cost],
                          ["You keep", result.net_profit],
                        ] as [string, number][]
                      ).map(([label, value], i) => (
                        <div key={label}>
                          <span>{label}</span>
                          <div className="bar-track">
                            <i
                              className={`bar bar-${i}`}
                              style={{
                                width: `${Math.max(2, Math.min(100, (Math.abs(value) / Math.max(1, result.dispatch_fee + result.fuel_cost + result.variable_cost + result.fixed_cost + result.net_profit)) * 100))}%`,
                              }}
                            />
                          </div>
                          <b>{money(value)}</b>
                        </div>
                      ))}
                    </div>
                    {result.verdict === "take" ? (
                      <div className="counter">
                        <div>
                          <small>YOUR TARGET RATE</small>
                          <h3>This offer already beats your target</h3>
                          <small>
                            Target: {money(result.counter_offer_rate)} ·
                            Break-even: {money(result.break_even_rate)}
                          </small>
                        </div>
                      </div>
                    ) : (
                      <div className="counter">
                        <div>
                          <small>YOUR TARGET RATE</small>
                          <h3>Counter at {money(result.counter_offer_rate)}</h3>
                          <small>
                            Break-even: {money(result.break_even_rate)}
                          </small>
                        </div>
                        <button
                          disabled={!!busy}
                          onClick={() =>
                            void run("Writing your counter-offer…", async () =>
                              setMessage(
                                (await api.counterMessage(result)).text,
                              ),
                            )
                          }
                        >
                          Write the message ↗
                        </button>
                      </div>
                    )}
                    {message && result.verdict !== "take" && (
                      <div className="message">
                        <p>{message}</p>
                        <button
                          onClick={() =>
                            void run("Copying message…", async () => {
                              await navigator.clipboard.writeText(message);
                              setToast("Counter-offer copied.");
                            })
                          }
                        >
                          Copy message
                        </button>
                      </div>
                    )}
                    {explanation ? (
                      <blockquote>
                        <span>LOADCHECK EXPLAINS</span>
                        {explanation}
                      </blockquote>
                    ) : (
                      <button
                        disabled={!!busy}
                        onClick={() =>
                          void run("Explaining the result…", async () =>
                            setExplanation(
                              (await api.explain({ economics: result })).text,
                            ),
                          )
                        }
                      >
                        Explain this result
                      </button>
                    )}
                    <div className="card-footer">
                      <small>
                        One load is one decision. See what a full run home pays.
                      </small>
                      <button
                        className="primary"
                        disabled={!!busy || !profile}
                        onClick={() => {
                          setScreen("Plan my run");
                          void plan();
                        }}
                      >
                        Find a better run →
                      </button>
                    </div>
                  </section>
                )}
                {offers.length > 0 && (
                  <section className="card">
                    <div className="section-heading">
                      <h2>
                        Your offers <small>({offers.length})</small>
                      </h2>
                      <button
                        disabled={!!busy}
                        onClick={() =>
                          void run("Ranking your offers…", async () =>
                            setRanked(await api.offers(offers)),
                          )
                        }
                      >
                        Rank offers →
                      </button>
                    </div>
                    {ranked.length ? (
                      ranked.map((e, i) => (
                        <div className="offer-row" key={e.load_id}>
                          <b>0{i + 1}</b>
                          <span>
                            {
                              offers.find((l) => l.id === e.load_id)?.origin
                                .city
                            }{" "}
                            →{" "}
                            {
                              offers.find((l) => l.id === e.load_id)
                                ?.destination.city
                            }
                          </span>
                          <strong>{money(e.true_net_cpm)}/mi</strong>
                          <span className={`badge ${e.verdict}`}>
                            {e.verdict}
                          </span>
                        </div>
                      ))
                    ) : (
                      <p>
                        {offers.length} confirmed offer
                        {offers.length !== 1 ? "s" : ""} saved. Paste another to
                        compare, or plan your run.
                      </p>
                    )}
                  </section>
                )}
              </div>
              <div className="insight-column">
                <section className="dark-card">
                  <span className="eyebrow">LOOK BEYOND THE RATE</span>
                  <div className="road-art">
                    <span>↗</span>
                    <i />
                    <i />
                    <i />
                  </div>
                  <h2>
                    Every mile
                    <br />
                    has a cost.
                  </h2>
                  <p>
                    Empty miles. Diesel. Your truck payment. We put them all in
                    the same picture.
                  </p>
                  <div className="dark-divider" />
                  <small>THE PROCESS</small>
                  <ol>
                    <li>Read the offer</li>
                    <li>Confirm the details</li>
                    <li>See your take-home</li>
                  </ol>
                </section>
                <section className="mini-card">
                  <span className="eyebrow">YOUR COST PROFILE</span>
                  <h3>
                    {profile?.trailer_type.replace("_", " ") ||
                      "Connect your truck"}
                  </h3>
                  <p>
                    {profile?.current_location.city || "Waiting for the API"}
                  </p>
                  {profile && (
                    <div className="stat-pair">
                      <span>
                        Net target
                        <strong>{money(profile.target_net_cpm)}/mi</strong>
                      </span>
                      <span>
                        Diesel<strong>{money(profile.fuel_price)}/gal</strong>
                      </span>
                    </div>
                  )}
                  <button
                    className="text-button"
                    disabled={!!busy}
                    onClick={() => setScreen("Setup")}
                  >
                    Adjust my costs →
                  </button>
                </section>
              </div>
            </div>
          )}
          {screen === "Setup" && draft && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void run("Saving your truck profile…", async () => {
                  const p = await api.saveProfile(draft);
                  setProfile(p);
                  setDraft(structuredClone(p));
                  invalidate();
                  setToast(
                    "Profile saved. Recalculate your offers with these costs.",
                  );
                });
              }}
            >
              <section className="card">
                <div className="section-heading">
                  <h2>Your truck & operating costs</h2>
                  <span className="badge">{draft.cost_source}</span>
                </div>
                <div className="form-grid">
                  <PlaceFields
                    label="Home base"
                    place={draft.home}
                    onChange={(home) => setDraft({ ...draft, home })}
                  />
                  <PlaceFields
                    label="Current location"
                    place={draft.current_location}
                    onChange={(current_location) =>
                      setDraft({ ...draft, current_location })
                    }
                  />
                  <Field label="Trailer">
                    <select
                      value={draft.trailer_type}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          trailer_type: e.target
                            .value as TruckProfile["trailer_type"],
                        })
                      }
                    >
                      <option value="dry_van">Dry van</option>
                      <option value="reefer">Reefer</option>
                      <option value="flatbed">Flatbed</option>
                    </select>
                  </Field>
                  <Field label="Cost source">
                    <select
                      value={draft.cost_source}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          cost_source: e.target
                            .value as TruckProfile["cost_source"],
                        })
                      }
                    >
                      <option value="manual">Manual</option>
                      <option value="nessie">Nessie</option>
                    </select>
                  </Field>
                  <Field
                    label="How you get paid"
                    hint={
                      draft.pays_weekly
                        ? "Weekly payment dates affect cash flow; the dispatcher takes the share below"
                        : "Broker terms (often 30–45 days) determine when cash arrives"
                    }
                  >
                    <select
                      value={draft.pays_weekly ? "weekly" : "broker"}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          pays_weekly: e.target.value === "weekly",
                        })
                      }
                    >
                      <option value="broker">Direct with brokers</option>
                      <option value="weekly">Through a dispatcher (weekly)</option>
                    </select>
                  </Field>
                  {profileNumbers.map(([key, label, hint, min, max]) => (
                    <Field key={key} label={label} hint={hint}>
                      <input
                        required
                        type="number"
                        step="any"
                        min={min}
                        max={max}
                        value={Number(draft[key])}
                        onChange={(e) => {
                          setBank(undefined);
                          setDraft({
                            ...draft,
                            [key]: Number(e.target.value),
                            cost_source: "manual",
                          });
                        }}
                      />
                    </Field>
                  ))}
                </div>
                <button className="primary" disabled={!!busy}>
                  Save my profile →
                </button>
              </section>
              <section className="card bank-card">
                <p className="eyebrow">CAPITAL ONE · NESSIE SANDBOX</p>
                <h2>Let your bank fill in the blanks.</h2>
                <p>
                  Compare your estimates with 90 days of sandbox purchases and
                  recurring bills. Mileage is estimated from your monthly miles.
                </p>
                <button
                  type="button"
                  disabled={
                    !!busy || JSON.stringify(draft) !== JSON.stringify(profile)
                  }
                  onClick={() =>
                    void run(
                      "Reading costs from Capital One Nessie…",
                      async () => setBank(await api.bankCosts()),
                    )
                  }
                >
                  Pull my real costs from Capital One →
                </button>
                <CapitalOneMark label="Costs read from" />
                {JSON.stringify(draft) !== JSON.stringify(profile) && (
                  <p>
                    <small>
                      Save your profile before comparing bank costs.
                    </small>
                  </p>
                )}
                {bank && (
                  <>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Cost</th>
                            <th>You entered</th>
                            <th>Your bank says</th>
                            <th>Difference</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(
                            [
                              "fuel_price",
                              "variable_cpm",
                              "fixed_monthly",
                            ] as const
                          ).map((key) => (
                            <tr key={key}>
                              <th>
                                {profileNumbers.find((x) => x[0] === key)?.[1]}
                              </th>
                              <td>{money(bank.current[key])}</td>
                              <td>{money(bank.proposed[key])}</td>
                              <td className="difference">
                                {money(bank.proposed[key] - bank.current[key])}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="notice">
                      Sandbox evidence ·{" "}
                      {String(bank.evidence.source || "Nessie")} ·{" "}
                      {String(bank.evidence.window_days || 90)} days
                    </p>
                    {confirmBank && (
                      <p className="notice">
                        This replaces your costs with the bank&apos;s and
                        changes every result on Check a load and Plan my run.
                        Reset demo ↺ puts the demo profile back.
                      </p>
                    )}
                    <div className="button-row">
                      {!confirmBank ? (
                        <button
                          type="button"
                          className="primary"
                          disabled={!!busy}
                          onClick={() => setConfirmBank(true)}
                        >
                          Accept bank costs
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="primary"
                          disabled={!!busy}
                          onClick={() =>
                            void run("Applying bank costs…", async () => {
                              setConfirmBank(false);
                              const p = await api.saveProfile(bank.proposed);
                              setProfile(p);
                              setDraft(structuredClone(p));
                              invalidate();
                              setToast(
                                "Bank costs accepted. Recalculate your offers.",
                              );
                            })
                          }
                        >
                          Yes, use bank costs
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setBank(undefined);
                          setConfirmBank(false);
                        }}
                      >
                        Keep mine
                      </button>
                    </div>
                  </>
                )}
              </section>
            </form>
          )}
          {screen === "Plan my run" && <RunsWorkspace profile={profile} loads={allLoads} chains={chains} selected={selected} planError={planError} cash={cash} cashBusy={cashBusy} cashError={cashError} onRetryCash={()=>{if(chain) void refreshCash(chain);}} busy={!!busy} planned={planned} includeBoard={includeBoard} boardCount={board.length} offerCount={offers.length}
            onBoard={value=>{setIncludeBoard(value);setChains([]);setCash(undefined);setPlanned(false);}}
            onPlan={()=>void plan()} onSelect={i=>{if(i!==selected){cashRequest.current++;setSelected(i);setCash(undefined);}}}
            onAdvance={id=>{if(chain) void run("Recording sandbox advance…",async()=>{const request=++cashRequest.current;setCashBusy(false);const updated=await api.advance(chain,id);if(request===cashRequest.current){setCash(updated);setCashError("");}setToast(updated.shortfall?"Advance recorded. A shortfall remains.":"Advance recorded. Run covered.");});}}>
              {chain && (
                <section className="card">
                  <div className="section-heading">
                    <div>
                      <p className="eyebrow">CASH IN THE TANK</p>
                      <h2>Profit is one thing. Timing is another.</h2>
                    </div>
                    <button
                      className="primary"
                      disabled={!!busy || cashBusy}
                      onClick={() => void refreshCash(chain)}
                    >
                      {cashBusy ? "Checking cash flow…" : "Refresh cash flow"}
                    </button>
                  </div>
                  <p>
                    <CapitalOneMark label="Balance and bills from" />{" "}
                    sandbox, from today until you're home. Next month's bills
                    are covered by your next runs.
                  </p>
                  {cash && (
                    <>
                      <div className={cash.shortfall ? "notice" : "success"}>
                        Lowest balance:{" "}
                        <strong>{money(cash.lowest_balance)}</strong> on{" "}
                        {cash.lowest_balance_date}.{" "}
                        {cash.shortfall
                          ? cash.quick_pay_fixes_it
                            ? `A Capital One advance fixes it for ${money(cash.quick_pay_cost)}, repaid when the broker pays.`
                            : "A Capital One advance does not cover this shortfall."
                          : cash.advances.length
                            ? "Covered: your Capital One advance keeps you above $0 for the whole trip."
                            : "You stay above $0 for the whole trip; no advance needed."}
                      </div>
                      <div className="cash-chart">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart
                            data={cash.timeline.map((e) => ({
                              ...e,
                              t: Date.parse(`${String(e.date)}T12:00:00`),
                              bill:
                                /payment|insurance|bill|phone|eld/i.test(
                                  String(e.label),
                                ) && Number(e.amount) < 0,
                            }))}
                          >
                            <CartesianGrid
                              strokeDasharray="3 3"
                              vertical={false}
                            />
                            <XAxis
                              dataKey="t"
                              type="number"
                              scale="time"
                              domain={["dataMin", "dataMax"]}
                              padding={{ left: 12, right: 24 }}
                              ticks={cash.timeline
                                .map((e) =>
                                  Date.parse(`${String(e.date)}T12:00:00`),
                                )
                                .reduce<number[]>(
                                  // one tick per date, at least 3 days apart
                                  (kept, t) =>
                                    kept.length &&
                                    t - kept[kept.length - 1] < 864e5
                                      ? kept
                                      : [...kept, t],
                                  [],
                                )}
                              tick={{ fontSize: 11 }}
                              tickFormatter={(t) =>
                                new Date(t).toLocaleDateString("en-US", {
                                  month: "short",
                                  day: "numeric",
                                })
                              }
                            />
                            <YAxis tickFormatter={(v) => `$${v}`} width={65} />
                            <Tooltip
                              formatter={(v) => money(Number(v))}
                              labelFormatter={(_, payload) =>
                                `${String(payload?.[0]?.payload?.date || "")} · ${String(payload?.[0]?.payload?.label || "")}`
                              }
                            />
                            <ReferenceLine
                              y={0}
                              stroke="#c03937"
                              strokeWidth={2}
                            />
                            <Line
                              type="linear"
                              dataKey="balance"
                              stroke="#244e50"
                              strokeWidth={3}
                              isAnimationActive={false}
                              dot={(props) => {
                                const { cx, cy, index, payload } = props as {
                                  cx: number;
                                  cy: number;
                                  index: number;
                                  payload: { bill: boolean };
                                };
                                return payload.bill ? (
                                  <circle
                                    key={index}
                                    cx={cx}
                                    cy={cy}
                                    r={7}
                                    fill="#c03937"
                                    stroke="white"
                                    strokeWidth={2}
                                  />
                                ) : (
                                  <circle
                                    key={index}
                                    cx={cx}
                                    cy={cy}
                                    r={5}
                                    fill="white"
                                    stroke="#244e50"
                                    strokeWidth={2}
                                  />
                                );
                              }}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Date / event</th>
                              <th>Change</th>
                              <th>Balance</th>
                            </tr>
                          </thead>
                          <tbody>
                            {cash.timeline.map((e, i) => (
                              <tr key={i}>
                                <td>
                                  {String(e.date)} · {String(e.label)}
                                </td>
                                <td>{money(Number(e.amount))}</td>
                                <td>{money(Number(e.balance))}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      {cash.later.length > 0 && (
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>After you're home</th>
                                <th>Amount</th>
                              </tr>
                            </thead>
                            <tbody>
                              {cash.later.map((e, i) => (
                                <tr key={i}>
                                  <td>
                                    {String(e.date)} · {String(e.label)}
                                  </td>
                                  <td>{money(Number(e.amount))}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </>
                  )}
                </section>
              )}
            {runExplanation && <details><summary>Run explanation</summary><p>{runExplanation}</p></details>}
            {result && chains[0] && <CompareCard offer={result} load={offers.find(l=>l.id===result.load_id)} best={chains[0]}/>}
          </RunsWorkspace>}
          <footer>
            LOADCHECK <span>Numbers from code. Clarity for the road.</span>
            <span>VTHACKS 14 / 2026</span>
          </footer>
        </div>
      </main>
    </div>
  );
}


// This offer on its own vs. the best run the optimizer found. Every number is
// from the API; the frontend only subtracts and divides for display.
function CompareCard({
  offer,
  load,
  best,
}: {
  offer: LoadEconomics;
  load?: Load;
  best: Chain;
}) {
  const gain = best.total_net_profit - offer.net_profit;
  const bestCpm = best.total_miles
    ? best.total_net_profit / best.total_miles
    : 0;
  const inBest = best.loads.includes(offer.load_id);
  return (
    <section className="card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">THIS OFFER VS. YOUR BEST RUN</p>
          <h2>Same truck. Very different week.</h2>
        </div>
      </div>
      <div className="compare">
        <div>
          <span className="eyebrow">THIS OFFER</span>
          <strong>{money(offer.net_profit)}</strong>
          <p>
            {load
              ? `${load.origin.city} → ${load.destination.city}`
              : offer.load_id}
          </p>
          <p>
            {money(offer.true_net_cpm)}/mi net · {offer.total_miles.toFixed(0)}{" "}
            mi ·{" "}
            <span className={`badge ${offer.verdict}`}>{offer.verdict}</span>
          </p>
          <p>
            {load
              ? `Leaves you in ${load.destination.city}.`
              : "Leaves you wherever it delivers."}
          </p>
        </div>
        <span className="vs">vs</span>
        <div className={gain > 0 ? "better" : ""}>
          <span className="eyebrow">BEST RUN</span>
          <strong>{money(best.total_net_profit)}</strong>
          <p>{best.loads.join(" → ")}</p>
          <p>
            {money(bestCpm)}/mi net · {best.total_miles.toFixed(0)} mi ·{" "}
            {money(best.net_per_day)}/day
          </p>
          <p>
            {best.days.toFixed(1)} days · ends{" "}
            {best.home_deadhead_miles.toFixed(0)} mi from home
          </p>
        </div>
      </div>
      <p className="compare-verdict">
        {inBest
          ? `Your offer is part of the best run: it earns ${money(best.total_net_profit)} once the right loads are around it.`
          : gain > 0
            ? `The best run keeps ${money(gain)} more than this offer and gets you home.`
            : "This offer beats every run we found. Take it."}
      </p>
    </section>
  );
}
