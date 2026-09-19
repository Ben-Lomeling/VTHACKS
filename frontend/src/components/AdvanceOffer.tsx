import { useState } from "react";
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
  const [confirming, setConfirming] = useState(false);
  if (!cash) return null;
  const taken = cash.advances ?? [];
  const offer = cash.advance_offer;

  if (taken.length && !cash.shortfall)
    return (
      <div className="advance advance-done">
        {taken.map((a) => (
          <p key={a.load_id}>
            <strong>
              Capital One advance on {a.load_id}: +{money(a.amount)} on{" "}
              {day(a.on)}.
            </strong>{" "}
            Repaid {money(a.repay_amount)} on {day(a.repay_on)} when the broker
            pays.
            <br />
            <small>
              {a.source === "live"
                ? `Deposit created in Capital One · id ${a.deposit_id.slice(0, 8)} · repayment bill ${a.bill_id.slice(0, 8)}`
                : "Bank sandbox unreachable: advance kept on this laptop for the demo"}
            </small>
          </p>
        ))}
      </div>
    );

  if (!cash.shortfall) return null;
  if (!offer)
    return (
      <div className="advance advance-red">
        <p>
          <strong>You'd be overdrawn on the road.</strong> A Capital One advance
          on these loads doesn't cover it; this run needs a different plan.
        </p>
      </div>
    );

  return (
    <div className="advance advance-red">
      <p>
        <strong>
          You'd be overdrawn by {money(-cash.lowest_balance)} on{" "}
          {day(cash.lowest_balance_date)}.
        </strong>{" "}
        Get paid for {offer.load_id} the day you deliver it.
      </p>
      {confirming ? (
        <div className="advance-confirm">
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
              disabled={busy}
              onClick={() => {
                setConfirming(false);
                onAdvance(offer.load_id);
              }}
            >
              Confirm advance →
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
