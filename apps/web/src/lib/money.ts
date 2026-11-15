import type { MoneyRange, PlanEconomics } from "@croppilot/contracts";

const number = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });

/** "4,300 lei" */
export const lei = (value: number) => `${number.format(value)} lei`;

/** "4,300 – 7,250 lei" (typical shown separately), or "Unknown". */
export function leiRange(range: MoneyRange | null | undefined): string {
  if (!range) return "Unknown";
  if (range.low === range.high) return lei(range.low);
  return `${number.format(range.low)} – ${lei(range.high)}`;
}

/** One line for "At a glance": typical margin per year, or why it is unknown. */
export function marginLine(economics: PlanEconomics | undefined): string | null {
  if (!economics) return null;
  const margin = economics.per_year.margin;
  if (margin) return `about ${lei(margin.typical)} per hectare a year (range ${leiRange(margin)})`;
  const unknown = economics.crops.filter((crop) => !crop.income || !crop.costs).map((crop) => crop.crop_name.toLowerCase());
  const crops = [...new Set(unknown)].join(" and ");
  return crops ? `unknown, because there are no official prices or costs for ${crops}` : "unknown";
}
