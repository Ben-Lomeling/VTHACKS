import { useEffect, useState } from "react";
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
import { RouteMap } from "./components/RouteMap";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ReferenceDot,
  CartesianGrid,
} from "recharts";

const money = (n: number) =>
  n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
const example =
  "Roanoke, VA → Charlotte, NC. $1,200 total. 500 loaded miles. Dry van, 38,000 lbs of paper products. Pickup Sep 22, 8am–12pm. Deliver Sep 23 by 8am. Blue Ridge Logistics. Net 30.";
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
  ];
export default function App() {
  const [screen, setScreen] = useState<Screen>("Check a load");
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
  const [includeBoard, setIncludeBoard] = useState(true);
  const [cash, setCash] = useState<CashflowCheck>();
  const [runExplanation, setRunExplanation] = useState("");
  const [bank, setBank] = useState<CostsFromBank>();
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
  }, [draft]);
  const chain = chains[selected];
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
      const c = await api.chains({
        seed_load_ids: offers.map((l) => l.id),
        include_board: includeBoard,
      });
      setChains(c);
      setSelected(0);
      setCash(undefined);
      setRunExplanation("");
      setPlanned(true);
      if (c[0]?.legs[0])
        setRunExplanation(
          (await api.explain({ economics: c[0].legs[0], chain: c[0] })).text,
        );
    });
  return (
    <div className="app-shell">
      <aside>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setScreen("Check a load");
          }}
        >
          <span className="brand-icon">↗</span>LoadCheck
          <span className="brand-dot">.</span>
        </a>
        <p className="sidebar-caption">THE OWNER-OPERATOR'S COPILOT</p>
        <nav aria-label="Main navigation">
          {(["Setup", "Check a load", "Plan my run"] as Screen[]).map(
            (s, i) => (
              <button
                key={s}
                disabled={!!busy}
                className={screen === s ? "nav-active" : ""}
                onClick={() => setScreen(s)}
              >
                <span>0{i + 1}</span>
                {s}
                <b>↗</b>
              </button>
            ),
          )}
        </nav>
        <div className="sidebar-bottom">
          <span className="tiny-label">YOUR TRUCK. YOUR NUMBERS.</span>
          <p>
            More clarity.
            <br />
            Better miles.
          </p>
          <small>Built for the road ahead.</small>
        </div>
      </aside>
      <main>
        <header>
          <span className="breadcrumb">
            Workspace <span>/</span> {screen}
          </span>
          <div className="header-actions">
            <span className="status-dot" />
            {USE_MOCKS ? "Mock demo" : health ? "API connected" : "API offline"}
            <button
              className="text-button"
              disabled={!!busy || !profile}
              onClick={() =>
                void run("Resetting the demo…", async () => {
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
                  setToast("Demo profile restored. Local offers cleared.");
                })
              }
            >
              Reset demo ↺
            </button>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">LESS GUESSWORK. MORE TAKE-HOME.</p>
              <h1>
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
            <span className="page-number">
              {screen === "Setup"
                ? "01"
                : screen === "Check a load"
                  ? "02"
                  : "03"}
              <small> / 03</small>
            </span>
          </div>
          {(USE_MOCKS ||
            (health &&
              Object.values(health.modules).some((x) => x !== "live"))) && (
            <div className="demo-strip">
              <span className="badge">DEMO DATA</span>
              {USE_MOCKS
                ? "Mock mode · fixed example responses; your input is not analyzed."
                : `Backend modules: ${Object.entries(health!.modules)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(" · ")}`}
              <span>Nessie bank data is sandbox data.</span>
            </div>
          )}
          {busy && (
            <div className="loading" role="status">
              <span className="spinner" />
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
                      {result.loaded_miles} loaded + {result.deadhead_miles}{" "}
                      empty = {result.total_miles} total miles
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
                            setMessage((await api.counterMessage(result)).text),
                          )
                        }
                      >
                        Write the message ↗
                      </button>
                    </div>
                    {message && (
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
                    <div className="button-row">
                      <button
                        type="button"
                        className="primary"
                        disabled={!!busy}
                        onClick={() =>
                          void run("Applying bank costs…", async () => {
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
                        Accept bank costs
                      </button>
                      <button type="button" onClick={() => setBank(undefined)}>
                        Keep mine
                      </button>
                    </div>
                  </>
                )}
              </section>
            </form>
          )}
          {screen === "Plan my run" && (
            <>
              <section className="card">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">YOUR NEXT MOVES</p>
                    <h2>Find a run worth taking.</h2>
                  </div>
                  <span className="badge amber">Simulated load board</span>
                </div>
                <div className="card-footer">
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={includeBoard}
                      disabled={!!busy}
                      onChange={(e) => {
                        setIncludeBoard(e.target.checked);
                        setPlanned(false);
                        setChains([]);
                        setCash(undefined);
                        setRunExplanation("");
                      }}
                    />{" "}
                    Include {board.length} simulated board loads +{" "}
                    {offers.length} confirmed offers
                  </label>
                  <button
                    className="primary"
                    disabled={
                      !!busy || !profile || (!includeBoard && !offers.length)
                    }
                    onClick={() => void plan()}
                  >
                    Plan my run →
                  </button>
                </div>
              </section>
              {runExplanation && (
                <blockquote>
                  <span>LOADCHECK EXPLAINS</span>
                  {runExplanation}
                </blockquote>
              )}
              {!chains.length ? (
                <div className="empty-state">
                  <span>↗</span>
                  <h2>
                    {planned
                      ? "No matching runs yet."
                      : "Your next good run starts here."}
                  </h2>
                  <p>
                    {planned
                      ? "Try including the simulated board or adjusting your truck profile."
                      : "We’ll compare up to three loads, the empty miles between them, and the drive home."}
                  </p>
                </div>
              ) : (
                <div className="plan-layout">
                  <div className="chain-list">
                    {chains.map((c, i) => (
                      <button
                        key={i}
                        className={`chain-card ${selected === i ? "selected" : ""}`}
                        disabled={!!busy}
                        onClick={() => {
                          setSelected(i);
                          setCash(undefined);
                          setRunExplanation("");
                          if (c.legs[0])
                            void run("Explaining this run…", async () =>
                              setRunExplanation(
                                (
                                  await api.explain({
                                    economics: c.legs[0],
                                    chain: c,
                                  })
                                ).text,
                              ),
                            );
                        }}
                      >
                        <span className="eyebrow">
                          OPTION 0{i + 1}
                          {c.losing || c.total_net_profit <= 0
                            ? " · NO PROFIT"
                            : i === 0 ? " · HIGHEST TOTAL NET" : ""}
                        </span>
                        <strong>
                          {money(c.total_net_profit)}
                          <small> total net</small>
                        </strong>
                        <p>
                          {money(c.net_per_day)}/day · {c.days.toFixed(1)} days
                        </p>
                        <p>{c.loads.join(" → ")}</p>
                        <small>
                          Ends {c.home_deadhead_miles.toFixed(0)} mi from home ·{" "}
                          {c.ends_at.city}
                        </small>
                        <div>
                          {(c.losing || c.total_net_profit <= 0) && (
                            <p className="notice">
                              {c.losing_reason || "This run does not earn a profit after costs."}
                            </p>
                          )}
                          {c.feasible_notes.map((n, j) => (
                            <span className="note-chip" key={j}>
                              {n}
                            </span>
                          ))}
                        </div>
                      </button>
                    ))}
                  </div>
                  <section className="card map-card">
                    <div className="section-heading">
                      <h2>Your route home</h2>
                      <span className="badge amber">Simulated load board</span>
                    </div>
                    {chain && profile && (
                      <RouteMap
                        chain={chain}
                        loads={allLoads}
                        profile={profile}
                      />
                    )}
                  </section>
                </div>
              )}
              {chain && (
                <section className="card">
                  <div className="section-heading">
                    <div>
                      <p className="eyebrow">CASH IN THE TANK</p>
                      <h2>Profit is one thing. Timing is another.</h2>
                    </div>
                    <button
                      className="primary"
                      disabled={!!busy}
                      onClick={() =>
                        void run(
                          "Checking fuel, bills and payment dates…",
                          async () => setCash(await api.cashflow(chain)),
                        )
                      }
                    >
                      Can I afford this run? →
                    </button>
                  </div>
                  <p>
                    Capital One Nessie sandbox balance and bills. The chart
                    shows the original payment schedule.
                  </p>
                  {cash && (
                    <>
                      <div className={cash.shortfall ? "notice" : "success"}>
                        Lowest balance:{" "}
                        <strong>{money(cash.lowest_balance)}</strong> on{" "}
                        {cash.lowest_balance_date}.{" "}
                        {cash.shortfall
                          ? cash.quick_pay_fixes_it
                            ? `Quick pay fixes the shortfall for ${money(cash.quick_pay_cost)}.`
                            : "Quick pay does not cover this shortfall."
                          : "Your balance stays nonnegative; quick pay is not needed."}
                      </div>
                      <div className="cash-chart">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={cash.timeline}>
                            <CartesianGrid
                              strokeDasharray="3 3"
                              vertical={false}
                            />
                            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                            <YAxis tickFormatter={(v) => `$${v}`} width={65} />
                            <Tooltip
                              formatter={(v) => money(Number(v))}
                              labelFormatter={(_, payload) =>
                                String(payload?.[0]?.payload?.label || "")
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
                              dot={{ r: 5 }}
                            />
                            {cash.timeline
                              .filter(
                                (e) =>
                                  /payment|insurance|bill|phone|eld/i.test(
                                    String(e.label),
                                  ) && Number(e.amount) < 0,
                              )
                              .map((e, i) => (
                                <ReferenceDot
                                  key={i}
                                  x={String(e.date)}
                                  y={Number(e.balance)}
                                  r={7}
                                  fill="#c03937"
                                  stroke="white"
                                />
                              ))}
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
                    </>
                  )}
                </section>
              )}
            </>
          )}
          <footer>
            LOADCHECK <span>Numbers from code. Clarity for the road.</span>
            <span>VTHACKS 14 / 2026</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
