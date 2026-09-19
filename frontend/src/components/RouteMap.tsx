import { MapTiles } from "./MapTiles";
import { useEffect, useState } from "react";
import type { CashflowCheck, Chain, Load, Place, TruckProfile } from "../types";
import { BUFFER, MONEY_ICONS, balanceColor } from "../money";
import {
  MapContainer,
  Polyline,
  Marker,
  Popup,
  Tooltip,
  useMap,
} from "react-leaflet";
import { divIcon, latLngBounds } from "leaflet";
const money = (v: number) =>
  `${v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const clock = (iso: string) =>
  new Date(iso).toLocaleString("en-US", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });

export function RouteMap({
  chain,
  loads,
  profile,
  cash,
}: {
  chain: Chain;
  loads: Load[];
  profile: TruckProfile;
  cash?: CashflowCheck;
}) {
  const [offline, setOffline] = useState(!navigator.onLine);
  // Feature A: when the cash flow is in, the line is colored by his projected balance.
  const route = cash?.route ?? [];
  const stops = cash?.money_stops ?? [];
  const coordinate = (p: Place): [number, number] | null =>
    p.lat != null && p.lng != null ? [p.lat, p.lng] : null;
  const points: [number, number][] = [];
  const lines: { positions: [number, number][]; kind: string }[] = [];
  const pins: { point: [number, number]; label: string; text: string }[] = [];
  const addPin = (p: Place, label: string) => {
    const point = coordinate(p);
    if (point) {
      points.push(point);
      // Stops in the same city share one pin (e.g. "H · 1P · 3D" at home).
      const same = pins.find(
        (pin) => pin.point[0] === point[0] && pin.point[1] === point[1],
      );
      if (same) same.label += ` · ${label}`;
      else pins.push({ point, label, text: p.city });
    }
    return point;
  };
  addPin(profile.home, "H");
  let last = addPin(profile.current_location, "●");
  let missing = 0;
  chain.loads.forEach((id, i) => {
    const load = loads.find((l) => l.id === id);
    if (!load) {
      missing++;
      last = null;
      return;
    }
    const a = addPin(load.origin, `${i + 1}P`);
    const b = addPin(load.destination, `${i + 1}D`);
    if (last && a) lines.push({ positions: [last, a], kind: "empty" });
    if (a && b) lines.push({ positions: [a, b], kind: "loaded" });
    else missing++;
    last = b;
  });
  const home = coordinate(profile.home);
  if (last && home) lines.push({ positions: [last, home], kind: "home" });
  function Fit() {
    const map = useMap();
    useEffect(() => {
      const fit = () => {
        if (points.length) map.fitBounds(latLngBounds(points), {
          paddingTopLeft: matchMedia('(max-width:700px)').matches ? [35,150] : [440,60],
          paddingBottomRight: matchMedia('(max-width:700px)').matches ? [35,250] : [70,100], maxZoom: 9, animate: false,
        });
      };
      fit();
      map.on('resize', fit);
      return () => { map.off('resize', fit); };
    }, [map, chain, profile]);
    return null;
  }
  return (
    <>
      <div className="map-mode"><span role="status">{offline ? "Offline map · city locations and estimated route" : "Online map"}</span><button type="button" onClick={() => setOffline(!offline)}>{offline ? "Retry map tiles" : "Use offline map"}</button></div>
      <div className="map">
        <MapContainer center={[37, -80]} zoom={6} scrollWheelZoom={false} zoomAnimation={false} fadeAnimation={false} markerZoomAnimation={false}>
          <MapTiles offline={offline} onOffline={() => setOffline(true)} />
          {route.map((r, i) => (
            <Polyline
              key={`m${i}`}
              positions={[r.from, r.to]}
              pathOptions={{
                color: balanceColor(r.balance),
                weight: r.balance < 0 ? 7 : 5,
                dashArray: r.loaded ? undefined : "8 8",
              }}
            >
              <Tooltip sticky>
                {money(r.balance)} in the bank · {clock(r.start)} →{" "}
                {clock(r.end)}
                {r.loaded ? " · loaded" : " · empty"}
              </Tooltip>
            </Polyline>
          ))}
          {stops.map((m, i) => (
            <Marker
              key={`s${i}`}
              position={[m.lat, m.lng]}
              zIndexOffset={1000}
              icon={divIcon({
                className: `money-pin money-${m.kind}${m.balance < 0 ? " money-red" : ""}`,
                html: `<span>${MONEY_ICONS[m.kind]}</span>`,
                iconSize: [44, 44],
                // sit just above-left of the spot so city pins (1P, 2D…) stay readable
                iconAnchor: [30, 30],
              })}
            >
              <Popup>
                <strong>{m.label}</strong>
                <br />
                {clock(m.at)} · {money(m.amount)} → {money(m.balance)}
              </Popup>
            </Marker>
          ))}
          {!route.length &&
            lines.map((line, i) => (
              <Polyline
                key={i}
                positions={line.positions}
                pathOptions={{
                  color:
                    line.kind === "home"
                      ? "#936ed4"
                      : line.kind === "loaded"
                        ? "#183d40"
                        : "#6b7b8b",
                  weight: 4,
                  dashArray: line.kind === "loaded" ? undefined : "8 8",
                }}
              />
            ))}
          {pins.map((pin, i) => (
            <Marker
              key={i}
              position={pin.point}
              icon={divIcon({
                className: "map-pin",
                html: `<span>${pin.label}</span>`,
                iconSize: [44, 44],
              })}
            >
              <Tooltip permanent direction="bottom">{pin.text}</Tooltip><Popup>{pin.text}</Popup>
            </Marker>
          ))}
          <Fit />
        </MapContainer>
      </div>
      {route.length ? (
        <p className="map-legend money-legend">
          <i className="swatch green" /> Covered　
          <i className="swatch amber" /> Under {money(BUFFER)}　
          <i className="swatch red" /> Overdrawn · ━ Loaded ┄ Empty ·{" "}
          {"⛽ fuel · 🧾 bill · 💵 money in"}
        </p>
      ) : (
        <p className="map-legend">
          ━ Loaded　┄ Empty　<span>┄ Home</span> · P pickup / D delivery
        </p>
      )}
      <small>
        Estimated connections, not road directions. Road miles use straight-line
        distance × 1.2; simplified hours of service.
      </small>
      {missing > 0 && (
        <p className="notice">
          Some locations have no coordinates. Those legs cannot be drawn on the
          map.
        </p>
      )}
    </>
  );
}
