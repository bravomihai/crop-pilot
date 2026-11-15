import type { RecommendationResult, RotationPlan } from "@croppilot/contracts";
import { SCORE_CRITERIA, scorePercent } from "./chart-data";

/**
 * A short, deterministic digest of a result for the "At a glance" card. Everything comes
 * from the calculated result as it is; nothing is re-scored or invented here.
 */

export const cropsOf = (plan: RotationPlan) => plan.steps.map((step) => step.crop_name).join(" → ");

export type Comparison = { label: string; plan: number; current: number };

/** Criteria where the plan and the current rotation both have a score. */
export function compareWithCurrent(plan: RotationPlan, current?: RotationPlan): Comparison[] {
  if (!current) return [];
  return SCORE_CRITERIA.flatMap(([key, label]) => {
    const a = scorePercent(plan.scores?.[key]);
    const b = scorePercent(current.scores?.[key]);
    return a === null || b === null ? [] : [{ label, plan: a, current: b }];
  });
}

/** The plan's strongest known criterion, for the one-line view of other plans. */
export function strongest(plan: RotationPlan): { label: string; value: number } | null {
  let best: { label: string; value: number } | null = null;
  for (const [key, label] of SCORE_CRITERIA) {
    const value = scorePercent(plan.scores?.[key]);
    if (value !== null && (!best || value > best.value)) best = { label, value };
  }
  return best;
}

const WATCH = /^Watch out:\s*/;

/** Weather and water warnings first; otherwise the first trade-off. */
export function mainRisks(plan: RotationPlan, count = 2): string[] {
  const warnings = plan.tradeoffs.filter((text) => WATCH.test(text)).map((text) => text.replace(WATCH, ""));
  return (warnings.length ? warnings : plan.tradeoffs.slice(0, 1)).slice(0, count);
}

/** Checks specific to this plan's crops first; general ones only to fill the list. */
export function keyChecks(plan: RotationPlan, others: RotationPlan[], count = 3): string[] {
  const checks = plan.local_checks ?? [];
  const shared = (text: string) => others.length > 0 && others.every((other) => other.local_checks?.includes(text));
  return [...checks.filter((text) => !shared(text)), ...checks.filter(shared)].slice(0, count);
}

const FARMER_GAP = /soil analysis|soil texture|crop history|history entr|current rotation|winterkill/i;
const TECHNICAL_GAP = /adapter|queried|offline|test fixture|search space|evaluator/i;

/** The missing data a farmer can act on or should know; technical notes stay in the details. */
export function keyGaps(result: RecommendationResult, count = 3): string[] {
  return result.data_gaps
    .filter((text) => FARMER_GAP.test(text) && !TECHNICAL_GAP.test(text))
    .slice(0, count);
}

/** First sentence of an explanation, for the short plan card. */
export function firstSentence(text: string): string {
  const match = text.match(/^.+?[.!?](?=\s|$)/);
  return match ? match[0] : text;
}
