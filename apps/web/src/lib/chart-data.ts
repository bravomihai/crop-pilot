import type { CriterionScores, RotationPlan } from "@fieldshift/contracts";

export const SCORE_CRITERIA = [
  ["water", "Water"],
  ["soil", "Soil"],
  ["climate", "Climate"],
  ["productivity", "Productivity"],
] as const satisfies readonly (readonly [keyof CriterionScores, string])[];

export function scorePercent(value: number | null | undefined): number | null {
  return value == null || !Number.isFinite(value)
    ? null
    : Math.round(value * 100);
}
export const DAY = 86_400_000;
export const utcDate = (value: string) => Date.parse(`${value}T00:00:00Z`);
export const formatDate = (value: string) =>
  new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(utcDate(value));

export function timelineData(plans: RotationPlan[]) {
  const steps = plans.flatMap((plan) => plan.steps);
  if (!steps.length) return null;
  const first = new Date(
    Math.min(...steps.map((step) => utcDate(step.sowing_window.start))),
  );
  const last = new Date(
    Math.max(...steps.map((step) => utcDate(step.harvest_window.end))),
  );
  const start = Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), 1);
  const end = Date.UTC(last.getUTCFullYear(), last.getUTCMonth() + 1, 1);
  const months: { date: number; month: string; year: number }[] = [];
  for (
    let date = new Date(start);
    date.getTime() < end;
    date.setUTCMonth(date.getUTCMonth() + 1)
  )
    months.push({
      date: date.getTime(),
      month: new Intl.DateTimeFormat("en", {
        month: "short",
        timeZone: "UTC",
      }).format(date),
      year: date.getUTCFullYear(),
    });
  return {
    start,
    end,
    months,
    percent: (date: number) => ((date - start) / (end - start)) * 100,
  };
}

export function bareGaps(plan: RotationPlan) {
  return plan.steps
    .slice(1)
    .map((step, index) => {
      const previous = plan.steps[index];
      const start = utcDate(previous.harvest_window.end) + DAY;
      const end = utcDate(step.sowing_window.start);
      const fourMonths = new Date(utcDate(previous.harvest_window.end));
      // Preserve day-of-month when possible and clamp to the target month's last day.
      const target = new Date(
        Date.UTC(fourMonths.getUTCFullYear(), fourMonths.getUTCMonth() + 5, 0),
      );
      target.setUTCDate(Math.min(fourMonths.getUTCDate(), target.getUTCDate()));
      return { start, end, long: end > target.getTime() };
    })
    .filter((gap) => gap.end > gap.start);
}

/** Ordinary least squares over known observations only; unknown is not zero. */
export function linearTrend(points: { year: number; value: number | null }[]) {
  const known = points.filter(
    (point): point is { year: number; value: number } =>
      point.value != null && Number.isFinite(point.value),
  );
  if (known.length < 2) return null;
  const meanX =
    known.reduce((sum, point) => sum + point.year, 0) / known.length;
  const meanY =
    known.reduce((sum, point) => sum + point.value, 0) / known.length;
  const denominator = known.reduce(
    (sum, point) => sum + (point.year - meanX) ** 2,
    0,
  );
  if (!denominator) return null;
  const slope =
    known.reduce(
      (sum, point) => sum + (point.year - meanX) * (point.value - meanY),
      0,
    ) / denominator;
  return { slope, at: (year: number) => meanY + slope * (year - meanX) };
}
