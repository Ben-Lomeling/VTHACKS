import { MapTiles } from "./MapTiles";
import { Fragment } from "react";
import { MapViewport, mapInteractionOptions } from "./MapViewport";
import { routeGeometry, validCoordinate } from "../mapGeometry";
import type { CashflowCheck, Chain, Load, TruckProfile } from "../types";
import { BUFFER, MONEY_ICONS, balanceColor } from "../money";
import {
  MapContainer,
  Polyline,
  Marker,
  Popup,
  Tooltip,
} from "react-leaflet";
import { divIcon } from "leaflet";
const money = (v: number) =>
  `${v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const stopDescription = (label: string) => label.replace(/(\d+)P/g, "Pickup $1").replace(/(\d+)D/g, "Delivery $1").replace("H", "Home").replace("●", "Current location");
const stopIcon = (label: string, city: string) => {
  const span = document.createElement("span");
  span.textContent = label;
  span.setAttribute("aria-label", `${city}: ${stopDescription(label)}`);
  return span;
};
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
  // Feature A: when the cash flow is in, the line is colored by his projected balance.
  const route = (cash?.route ?? []).filter(r => validCoordinate(...r.from) && validCoordinate(...r.to));
  const stops = (cash?.money_stops ?? []).filter(m => validCoordinate(m.lat, m.lng));
  const { points, lines, pins, missingLocations, routeKey } = routeGeometry(chain, loads, profile);
  const omittedOverlays = (cash?.route.length ?? 0) - route.length + (cash?.money_stops.length ?? 0) - stops.length;
  return (
    <>
      <div className="map">
        <MapContainer center={[37, -80]} zoom={6} {...mapInteractionOptions()}>
          <MapTiles />
          {route.map((r, i) => (
            <Fragment key={`route-${i}`}><Polyline positions={[r.from, r.to]} pathOptions={{color: "white", weight: 10, opacity: .9, interactive: false}} />
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
            </Polyline></Fragment>
          ))}
          {stops.map((m, i) => (
            <Marker
              key={`${m.at}-${m.label}-${i}`}
              position={[m.lat, m.lng]}
              title={m.label}
              zIndexOffset={1000}
              icon={divIcon({
                className: `money-pin money-${m.kind}${m.balance < 0 ? " money-red" : ""}`,
                html: `<span>${MONEY_ICONS[m.kind]}</span>`,
                iconSize: [44, 44],
                // Place money events beside, rather than on top of, the stop label.
                iconAnchor: [-(Math.max(44, (pins.find(pin => pin.point[0] === m.lat && pin.point[1] === m.lng)?.label.length ?? 0) * 7 + 16) / 2) - 4, 22],
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
              <Fragment key={`line-${i}`}><Polyline positions={line.positions} pathOptions={{color: "white", weight: 8, opacity: .9, interactive: false}} />
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
              /></Fragment>
            ))}
          {pins.map((pin) => (
            <Marker
              key={`${pin.point.join(",")}:${pin.label}`}
              position={pin.point}
              title={`${pin.text}: ${stopDescription(pin.label)}`}
              icon={divIcon({
                className: `map-pin ${pin.label.includes(" · ") ? "pin-combined" : pin.label.includes("P") ? "pin-pickup" : pin.label.includes("D") ? "pin-delivery" : "pin-base"}`,
                html: stopIcon(pin.label, pin.text),
                iconSize: [Math.max(44, pin.label.length * 7 + 16), 44], iconAnchor: [Math.max(44, pin.label.length * 7 + 16) / 2, 22],
              })}
            >
              <Tooltip direction="bottom">{pin.text}</Tooltip><Popup><strong>{pin.text}</strong><br/>{stopDescription(pin.label)}</Popup>
            </Marker>
          ))}
          <MapViewport points={points} routeKey={routeKey} />
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
      {(missingLocations.length > 0 || omittedOverlays > 0) && (
        <p className="notice map-notice" role="status">
          Some stops or overlays cannot be drawn. {missingLocations.length > 0 && `${missingLocations.join("; ")}. `}Missing or invalid coordinates are omitted; connections are not guessed.
        </p>
      )}
    </>
  );
}
