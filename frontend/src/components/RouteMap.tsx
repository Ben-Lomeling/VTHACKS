import { useEffect } from "react";
import type { Chain, Load, Place, TruckProfile } from "../types";
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  Popup,
  useMap,
} from "react-leaflet";
import { divIcon, latLngBounds } from "leaflet";
export function RouteMap({
  chain,
  loads,
  profile,
}: {
  chain: Chain;
  loads: Load[];
  profile: TruckProfile;
}) {
  const coordinate = (p: Place): [number, number] | null =>
    p.lat != null && p.lng != null ? [p.lat, p.lng] : null;
  const points: [number, number][] = [];
  const lines: { positions: [number, number][]; kind: string }[] = [];
  const pins: { point: [number, number]; label: string; text: string }[] = [];
  const addPin = (p: Place, label: string) => {
    const point = coordinate(p);
    if (point) {
      points.push(point);
      pins.push({ point, label, text: p.city });
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
      if (points.length)
        map.fitBounds(latLngBounds(points), { padding: [45, 45], maxZoom: 9 });
    }, [map, chain, profile]);
    return null;
  }
  return (
    <>
      <div className="map">
        <MapContainer center={[37, -80]} zoom={6} scrollWheelZoom={false}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {lines.map((line, i) => (
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
                iconSize: [32, 32],
              })}
            >
              <Popup>{pin.text}</Popup>
            </Marker>
          ))}
          <Fit />
        </MapContainer>
      </div>
      <p className="map-legend">
        ━ Loaded　┄ Empty　<span>┄ Home</span> · P pickup / D delivery
      </p>
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
