import { useId, useState, type ReactNode } from "react";
import { cityValidation } from "../mapGeometry";
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
  const id = useId();
  const [touched, setTouched] = useState(false);
  const message = cityValidation(place.city);
  return (
    <div className="place-fields">
      <Field label={label} low={low}>
        <input
          required
          pattern="[ ]*[^,\s][^,]*,[ ]*[A-Za-z]{2}[ ]*"
          aria-describedby={id}
          aria-invalid={touched && !!message}
          onBlur={(e) => { setTouched(true); e.currentTarget.setCustomValidity(cityValidation(e.currentTarget.value)); }}
          onInvalid={() => setTouched(true)}
          value={place.city}
          onChange={(e) => {
            e.currentTarget.setCustomValidity(cityValidation(e.currentTarget.value));
            onChange({ city: e.target.value, lat: null, lng: null });
          }}
          placeholder="City, ST"
        />
      </Field>
      <small id={id} className={touched && message ? "field-error" : "field-hint"}>{touched && message ? message : "City and two-letter state, e.g. Richmond, VA. Locations are checked when you submit."}</small>
    </div>
  );
}
