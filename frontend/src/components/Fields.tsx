import type { ReactNode } from "react";
import type { Place } from "../types";
export function Field({
  label,
  hint,
  low,
  children,
}: {
  label: string;
  hint?: string;
  low?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={`field ${low ? "low" : ""}`}>
      <span>
        {label}
        {low && <small> · Check this</small>}
      </span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function PlaceFields({
  label,
  place,
  onChange,
  low = false,
}: {
  label: string;
  place: Place;
  onChange: (p: Place) => void;
  low?: boolean;
}) {
  return (
    <div className="place-fields">
      <Field label={label} low={low}>
        <input
          required
          value={place.city}
          onChange={(e) =>
            onChange({ city: e.target.value, lat: null, lng: null })
          }
          placeholder="City, ST"
        />
      </Field>
    </div>
  );
}
