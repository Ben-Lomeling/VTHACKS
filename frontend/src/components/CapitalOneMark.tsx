import logo from "../assets/capital-one.svg";

// The Capital One mark, shown next to the four places Nessie data actually surfaces: the advance
// card, the cash-flow panel, the costs-from-bank button and the header. One component so the
// treatment stays identical everywhere and swapping the asset file touches nothing else.
//
// Deliberately quiet: this is a "powered by" credit, not a banner. The numbers next to it are the
// point; the mark is there so a judge can see where the bank data comes from.
export function CapitalOneMark({
  label,
  size = 16,
  className = "",
}: {
  label?: string;
  size?: number;
  className?: string;
}) {
  return (
    <span className={`capone-mark ${className}`.trim()}>
      {label && <span className="capone-mark-label">{label}</span>}
      <img src={logo} alt="Capital One" height={size} />
    </span>
  );
}
