import { useEffect, useState, useRef } from "react";
import type { CashflowCheck } from "../types";

const money = (v: number) =>
  `${v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
const day = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

// Feature B: when the run goes red, offer a Capital One advance. Every number comes from the backend
// (advance_offer); this only asks the driver to confirm and shows what Nessie recorded.
export function AdvanceOffer({
  cash,
  busy,
  onAdvance,
}: {
  cash?: CashflowCheck;
  busy: boolean;
  onAdvance: (loadId: string) => void;
}) {
  const confirmButton = useRef<HTMLButtonElement>(null);
  const successPanel = useRef<HTMLDivElement>(null);
  const wasSubmitting = useRef(false);
  useEffect(() => { if(wasSubmitting.current && !busy) { successPanel.current?.focus(); wasSubmitting.current=false; } }, [busy, cash]);
  const [confirming, setConfirming] = useState(false);
  useEffect(() => { if(confirming) confirmButton.current?.focus(); }, [confirming]);
  useEffect(() => setConfirming(false), [cash]);
  if (!cash) return null;
  const taken = cash.advances ?? [];
  const offer = cash.advance_offer;

  if (taken.length && !cash.shortfall)
    return (
      <div className="advance advance-done" ref={successPanel} tabIndex={-1} role="status" aria-live="polite">
        <h3><span aria-hidden="true">✓</span> Advance recorded · run covered</h3>
        {taken.map((a) => (
          <div className="advance-record" key={a.load_id}>
            <strong>
              Capital One advance on {a.load_id}: +{money(a.amount)} on{" "}
              {day(a.on)}.
            </strong>{" "}
            Scheduled repayment {money(a.repay_amount)} on {day(a.repay_on)} when the broker
            pays.
            <br />
            {a.source === "live" ? <div className="advance-receipt"><span>Capital One sandbox · pending deposit</span><code>Deposit {a.deposit_id}</code><code>Repayment bill {a.bill_id}</code></div> : <p className="advance-fixture">Offline demo only · no Nessie deposit created.</p>}

          </div>
        ))}
      </div>
    );

  if (!cash.shortfall) return null;
  if (!offer)
    return (
      <div className="advance advance-red" aria-busy={busy}>
        <p>
          <strong>You'd be overdrawn on the road.</strong> A Capital One advance
          on these loads doesn't cover it; this run needs a different plan.
        </p>
      </div>
    );

  return (
    <div className="advance advance-red" aria-busy={busy}>
      <p>
        <strong>
          You'd be overdrawn by {money(-cash.lowest_balance)} on{" "}
          {day(cash.lowest_balance_date)}.
        </strong>{" "}
        Get paid for {offer.load_id} the day you deliver it.
      </p>
      {confirming ? (
        <div className="advance-confirm" role="group" aria-label="Confirm sandbox advance">
          <h3>Confirm advance</h3>
          <p>
            Capital One deposits <strong>{money(offer.amount)}</strong> on{" "}
            {day(offer.on)} when {offer.load_id} delivers. Fee{" "}
            <strong>{money(offer.fee)}</strong>. Paid back automatically (
            {money(offer.repay_amount)}) on {day(offer.repay_on)}
            {offer.broker
              ? ` when ${offer.broker} pays`
              : " when the broker pays"}
            .
          </p>
          <div className="advance-actions">
            <button
              className="primary"
              ref={confirmButton}
              disabled={busy}
              onClick={() => {
                wasSubmitting.current = true;
                onAdvance(offer.load_id);
              }}
            >
              {busy ? "Recording advance…" : "Confirm advance"}
            </button>
            <button
              className="text-button"
              disabled={busy}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          className="primary"
          disabled={busy}
          onClick={() => setConfirming(true)}
        >
          Get a Capital One advance on {offer.load_id} ({money(offer.fee)}) →
        </button>
      )}
    </div>
  );
}
