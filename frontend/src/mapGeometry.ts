import type { Chain, Load, Place, TruckProfile } from "./types";

export const validCoordinate = (lat: unknown, lng: unknown) =>
  typeof lat === "number" && Number.isFinite(lat) && Math.abs(lat) <= 90 &&
  typeof lng === "number" && Number.isFinite(lng) && Math.abs(lng) <= 180;

const coordinate = (p: Place): [number, number] | null =>
  validCoordinate(p.lat, p.lng) ? [p.lat!, p.lng!] : null;

export function routeGeometry(chain: Chain, loads: Load[], profile: TruckProfile) {
  const points: [number, number][] = [];
  const lines: { positions: [number, number][]; kind: string }[] = [];
  const pins: { point: [number, number]; label: string; text: string }[] = [];
  const missingLocations: string[] = [];
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
    if (!point) missingLocations.push(`${label}: ${p.city || "Unnamed city"}`);
    return point;
  };
  addPin(profile.home, "H");
  let last = addPin(profile.current_location, "●");
  chain.loads.forEach((id, i) => {
    const load = loads.find((l) => l.id === id);
    if (!load) {
      missingLocations.push(`Load ${id} is unavailable`);
      last = null;
      return;
    }
    const a = addPin(load.origin, `${i + 1}P`);
    const b = addPin(load.destination, `${i + 1}D`);
    if (last && a) lines.push({ positions: [last, a], kind: "empty" });
    if (a && b) lines.push({ positions: [a, b], kind: "loaded" });
    last = b;
  });
  const home = coordinate(profile.home);
  if (last && home) lines.push({ positions: [last, home], kind: "home" });
  return { points, lines, pins, missingLocations, routeKey: JSON.stringify([chain.loads, points]) };
}

export function cityValidation(city: string) {
  if (!city.trim()) return "Enter a city and state.";
  return /^[^,\s][^,]*,\s*[a-zA-Z]{2}$/.test(city.trim()) ? "" : "Use City, ST, for example Richmond, VA.";
}
