import type { Chain, RouteStretch } from "../types";
import { balanceColor } from "../money";

type Kind = "empty" | "loaded" | "home";
interface Segment {
  kind: Kind;
  start: number;
  end: number;
  label: string;
  notes: string[];
}

const HOUR = 36e5;
const hours = (ms: number) => `${(ms / HOUR).toFixed(1)} h`;
const when = (t: number) =>
  new Date(t).toLocaleString("en-US", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });

// Lays the backend's schedule out on a time bar. No economics here: the optimizer
// decides every time; this only turns its timestamps into widths.
export function RunTimeline({ chain, route = [] }: { chain: Chain; route?: RouteStretch[] }) {
  const stops = chain.schedule.map((s) => ({
    id: String(s.load_id),
    depart: Date.parse(String(s.depart_at)),
    pickup: Date.parse(String(s.pickup_at)),
    delivered: Date.parse(String(s.delivered_at)),
  }));
  if (!stops.length || stops.some((s) => isNaN(s.depart + s.pickup + s.delivered)))
    return null;

  const start = stops[0].depart;
  const end = Math.max(
    start + chain.days * 24 * HOUR,
    stops[stops.length - 1].delivered,
  );
  const segments: Segment[] = [];
  for (const s of stops) {
    // Rests and waits come back as notes naming the load; place each on its leg.
    const notes = chain.feasible_notes.filter((n) => n.includes(s.id));
    if (s.pickup > s.depart)
      segments.push({
        kind: "empty",
        start: s.depart,
        end: s.pickup,
        label: `Empty to ${s.id}`,
        notes: notes.filter((n) => !/while hauling/i.test(n)),
      });
    segments.push({
      kind: "loaded",
      start: s.pickup,
      end: s.delivered,
      label: s.id,
      notes: notes.filter((n) => /while hauling/i.test(n)),
    });
  }
  const last = stops[stops.length - 1].delivered;
  if (end - last > 0.25 * HOUR)
    segments.push({ kind: "home", start: last, end, label: "Home", notes: [] });

  const pct = (t: number) => ((t - start) / (end - start)) * 100;
  const midnights: number[] = [];
  const d = new Date(start);
  d.setHours(24, 0, 0, 0);
  for (let t = d.getTime(); t < end; t += 24 * HOUR) midnights.push(t);

  return (
    <div className="timeline">
      <div className="timeline-head">
        <strong>Your {chain.days.toFixed(1)} days</strong>
        <span>
          {when(start)} → {when(end)}
          {chain.home_deadhead_miles < 1 ? " · home" : ""}
        </span>
      </div>
      <div className="timeline-bar">
        {segments.map((s, i) => (
          <div
            key={i}
            className={`seg seg-${s.kind}`}
            style={{ left: `${pct(s.start)}%`, width: `${pct(s.end) - pct(s.start)}%` }}
            title={[`${s.label} · ${hours(s.end - s.start)}`, ...s.notes].join("\n")}
          >
            <span>{s.kind === "loaded" ? s.label : ""}</span>
            {s.notes.some((n) => /rest/i.test(n)) && <i className="rest">10-h rest</i>}
          </div>
        ))}
        {midnights.map((t) => (
          <b key={t} className="midnight" style={{ left: `${pct(t)}%` }}>
            {new Date(t).toLocaleDateString("en-US", { weekday: "short" })}
          </b>
        ))}
      </div>
      {route.length > 0 && (
        // Same stretches as the map: his balance while driving each part of the run.
        <div className="balance-strip" aria-label="Bank balance along the run">
          {route.map((r, i) => {
            const a = Math.max(Date.parse(r.start), start);
            const b = Math.min(Date.parse(r.end), end);
            return (
              <div
                key={i}
                style={{ left: `${pct(a)}%`, width: `${pct(b) - pct(a)}%`, background: balanceColor(r.balance) }}
                title={`$${Math.round(r.balance).toLocaleString("en-US")} in the bank`}
              />
            );
          })}
        </div>
      )}
      <p className="map-legend">
        ▮ Loaded　▯ Empty / waiting　<span>▯ Home</span>　10-h rest = hours-of-service break
      </p>
    </div>
  );
}
