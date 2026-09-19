// Money on the map: one color rule for the route, the timeline strip and the legend.
export const BUFFER = 500;
export const MONEY_COLORS = { green: "#1f8a4c", amber: "#d98e04", red: "#c03937" };
export const balanceColor = (balance: number) =>
  balance < 0
    ? MONEY_COLORS.red
    : balance < BUFFER
      ? MONEY_COLORS.amber
      : MONEY_COLORS.green;
export const MONEY_ICONS = { fuel: "⛽", bill: "🧾", pay: "💵", advance: "💵" };
