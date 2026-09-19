import { useState } from "react";
import type { FormEvent } from "react";
import type { Load, ExtractionResult } from "../types";
import { Field, PlaceFields } from "./Fields";
export function LoadForm({
  extraction,
  onCalculate,
  busy,
}: {
  extraction: ExtractionResult;
  onCalculate: (load: Load) => void;
  busy: boolean;
}) {
  const [load, setLoad] = useState(extraction.load);
  const update = (key: keyof Load, value: unknown) =>
    setLoad((old) => ({ ...old, [key]: value }));
  const fields: [keyof Load, string, string][] = [
    ["id", "Offer ID", "text"],
    ["rate_usd", "Total load pay ($)", "number"],
    ["loaded_miles_est", "Loaded miles", "number"],
    ["pickup_window_start", "Pickup window starts", "datetime-local"],
    ["pickup_window_end", "Pickup window ends", "datetime-local"],
    ["delivery_by", "Delivery deadline", "datetime-local"],
    ["trailer_type", "Trailer type", "text"],
    ["weight_lbs", "Weight (lbs)", "number"],
    ["commodity", "Commodity", "text"],
    ["broker", "Broker", "text"],
    ["payment_terms_days", "Payment terms (days)", "number"],
    ["quick_pay_fee_pct", "Quick-pay fee (0.03 = 3%)", "number"],
  ];
  function submit(e: FormEvent) {
    e.preventDefault();
    if (
      load.pickup_window_start &&
      load.pickup_window_end &&
      load.pickup_window_start > load.pickup_window_end
    ) {
      alert("Pickup end must be after pickup start.");
      return;
    }
    onCalculate(load);
  }
  return (
    <form className="card" onSubmit={submit}>
      <div className="section-heading">
        <div>
          <p className="eyebrow">02 / YOUR FINAL SAY</p>
          <h2>Check the details.</h2>
        </div>
        <span className="badge amber">Confirmation required</span>
      </div>
      {extraction.warnings.map((w, i) => (
        <p className="notice" key={i}>
          {w}
        </p>
      ))}
      <div className="form-grid">
        <PlaceFields
          label="Pickup city"
          place={load.origin}
          low={extraction.confidence.origin === "low"}
          onChange={(p) => update("origin", p)}
        />
        <PlaceFields
          label="Delivery city"
          place={load.destination}
          low={extraction.confidence.destination === "low"}
          onChange={(p) => update("destination", p)}
        />
        {fields.map(([key, label, type]) => (
          <Field
            key={key}
            label={label}
            low={extraction.confidence[key] === "low"}
          >
            <input
              type={type}
              value={String(load[key] ?? "")}
              required={[
                "id",
                "rate_usd",
                "payment_terms_days",
                "quick_pay_fee_pct",
              ].includes(key)}
              min={key === "rate_usd" || key === "loaded_miles_est" ? 0.01 : 0}
              max={key === "quick_pay_fee_pct" ? 0.99 : undefined}
              step={
                key === "weight_lbs" || key === "payment_terms_days"
                  ? "1"
                  : "any"
              }
              onChange={(e) =>
                update(
                  key,
                  e.target.value === ""
                    ? null
                    : type === "number"
                      ? Number(e.target.value)
                      : e.target.value,
                )
              }
            />
          </Field>
        ))}
        <Field label="Offer source">
          <select
            value={load.source}
            onChange={(e) => update("source", e.target.value)}
          >
            <option value="pasted">Pasted text</option>
            <option value="screenshot">Screenshot</option>
            <option value="simulated">Simulated</option>
          </select>
        </Field>
      </div>
      <button className="primary" disabled={busy}>
        Calculate what I keep →
      </button>
    </form>
  );
}
