/**
 * Survival Mode: challenge the plans with the hardest past seasons at the field.
 *
 * Pure, deterministic transformations of an engine result. Nothing here is a new model:
 * - The challenge season is chosen from OBSERVED yearly weather (`climate_context`, NASA
 *   POWER, never scenario-adjusted), so the same year is chosen with or without a scenario.
 * - Every rotation is then read from its own P3 replay (`plan.replay`) for the SAME past
 *   season: the replay that started from the same historical field-free date.
 * - Scores are P3's per-season scores (0–1 shown as 0–100); crop evidence is P3's per-crop
 *   replay values (WRSI, heat days, climate risk). Unknown stays unknown, never zero.
 */
import type {
  ClimateYear,
  RecommendationRequest,
  RecommendationResult,
  ReplaySeason,
  RotationPlan,
} from "@croppilot/contracts";
import { RULE_CROPS } from "./crop-options";
import { scorePercent, SCORE_CRITERIA, utcDate } from "./chart-data";

export type ChallengeId = "drought" | "heat" | "rainfall";
export type SeasonCriterion = "water" | "climate" | "productivity";

export const CHALLENGES: readonly {
  id: ChallengeId;
  title: string;
  noun: string;
  description: string;
  criterion: SeasonCriterion;
}[] = [
  {
    id: "drought",
    title: "Worst drought",
    noun: "drought",
    description: "The year the air demanded the most water beyond the rain that fell.",
    criterion: "water",
  },
  {
    id: "heat",
    title: "Extreme heat",
    noun: "heat year",
    description: "The year with the most days above 32 °C.",
    criterion: "climate",
  },
  {
    id: "rainfall",
    title: "Unpredictable rainfall",
    noun: "erratic-rain year",
    description: "Long summer dry spells together with many heavy-rain days.",
    criterion: "water",
  },
];

export const SURVIVAL_DISCLAIMER =
  "This compares historical conditions, not a prediction of future harvests.";

const CRITERION_NAME: Record<string, string> = Object.fromEntries(
  SCORE_CRITERIA.map(([id, name]) => [id, name.toLowerCase()]),
);

export const cropName = (id: string) =>
  RULE_CROPS.find(([crop]) => crop === id)?.[1] ?? id.replace(/_/g, " ");

export type Contender = {
  /** Stable key: "baseline" or the plan id. */
  key: string;
  label: string;
  plan: RotationPlan;
  baseline: boolean;
};

/** The farmer's current rotation first (when evaluated), then the recommended plans. */
export function contenders(result: RecommendationResult): Contender[] {
  return [
    ...(result.baseline
      ? [{ key: "baseline", label: "Your current rotation", plan: result.baseline, baseline: true }]
      : []),
    ...result.plans.map((plan, index) => ({
      key: plan.id,
      label: `Plan ${index + 1}`,
      plan,
      baseline: false,
    })),
  ];
}

export const sequenceText = (plan: RotationPlan) =>
  plan.steps.map((step) => step.crop_name || cropName(step.crop_id)).join(" → ");

const isoYear = (iso: string) => Number(iso.slice(0, 4));

/** ISO date moved back `years` whole years; 29 February becomes 28 February (as P3 does). */
export function shiftIso(iso: string, years: number) {
  const year = isoYear(iso) - years;
  const rest = iso.slice(4) === "-02-29" ? "-02-28" : iso.slice(4);
  return `${String(year).padStart(4, "0")}${rest}`;
}

/** The first April–September growing season on or after the field-free date. */
export const firstSummer = (fieldFree: string) =>
  fieldFree.slice(5) <= "04-01" ? isoYear(fieldFree) : isoYear(fieldFree) + 1;

export type AlignedSeason = {
  /** Historical date the replay started from (request date moved back `shift` years). */
  fieldFree: string;
  /** Year of the first April–September period after that date. */
  summer: number;
  /** Whole years between the plan's calendar and this replay. */
  shift: number;
  /** False when the start date was derived from the plan calendar (engine omitted it). */
  exact: boolean;
  season: ReplaySeason;
};

/**
 * Each replay season with the historical date it started from.
 *
 * Uses `field_free_from` when the engine reports it. Older results only carry
 * `season_start_year` (the first sowing year), from which the date can be derived when the
 * request's availability date is known; otherwise the season cannot be aligned and is skipped.
 */
export function alignedSeasons(plan: RotationPlan, availableFrom?: string): AlignedSeason[] {
  const firstSowingYear = isoYear(plan.steps[0].sowing_window.start);
  return (plan.replay ?? []).flatMap((season): AlignedSeason[] => {
    if (season.field_free_from) {
      // P3: season_start_year = first sowing year − shift. Independent of the request, whose
      // availability date the engine may have moved (for example a past date to today).
      const shift = firstSowingYear - season.season_start_year;
      return [
        {
          fieldFree: season.field_free_from,
          summer: firstSummer(season.field_free_from),
          shift,
          exact: true,
          season,
        },
      ];
    }
    if (!availableFrom) return [];
    const shift = firstSowingYear - season.season_start_year;
    const fieldFree = shiftIso(availableFrom, shift);
    return [{ fieldFree, summer: firstSummer(fieldFree), shift, exact: false, season }];
  });
}

export type CropEvidence = {
  order: number;
  cropId: string;
  cropName: string;
  /** Share of the crop's water need met by rain and stored soil water, percent (P3 WRSI). */
  wrsiPct: number | null;
  seasonRainMm: number | null;
  /** P3 combined weather risk for the crop that season, 0–1. */
  climateRisk: number | null;
  /** Days above the crop's own heat threshold during flowering and grain fill (P3). */
  heatDays: number | null;
  /** Rain around sowing, mm (P3 sowing-drought hazard), when the crop has that hazard. */
  sowingRainMm: number | null;
  /** True when the planned calendar, moved back to that season, overlaps April–September. */
  inSummer: boolean;
};

const known = (value: number | null | undefined): number | null =>
  value == null || !Number.isFinite(value) ? null : value;

function cropEvidence(plan: RotationPlan, aligned: AlignedSeason): CropEvidence[] {
  const summerStart = utcDate(`${aligned.summer}-04-01`);
  const summerEnd = utcDate(`${aligned.summer}-09-30`);
  return plan.steps.map((step, index) => {
    const replayStep = aligned.season.steps?.[index];
    const from = utcDate(shiftIso(step.sowing_window.start, aligned.shift));
    const to = utcDate(shiftIso(step.harvest_window.end, aligned.shift));
    return {
      order: step.order,
      cropId: step.crop_id,
      cropName: step.crop_name || cropName(step.crop_id),
      wrsiPct: known(replayStep?.wrsi_pct),
      seasonRainMm: known(replayStep?.season_rain_mm),
      climateRisk: known(replayStep?.climate_risk),
      heatDays: known(replayStep?.hazards?.heat),
      sowingRainMm: known(replayStep?.hazards?.sowing_drought),
      inSummer: from <= summerEnd && to >= summerStart,
    };
  });
}

/** The crop that the evaluator found most affected, among crops in the field that summer. */
function mostExposed(crops: CropEvidence[], id: ChallengeId): CropEvidence | null {
  const inField = crops.filter((crop) => crop.inSummer);
  const pick = (value: (crop: CropEvidence) => number | null, highest: boolean) => {
    const scored = inField.filter((crop) => value(crop) !== null);
    if (!scored.length) return null;
    // Stable: the earlier crop wins ties.
    return scored.reduce((best, crop) =>
      (highest ? value(crop)! > value(best)! : value(crop)! < value(best)!) ? crop : best,
    );
  };
  if (id === "heat") {
    const byHeat = pick((crop) => crop.heatDays, true);
    if (byHeat && byHeat.heatDays! > 0) return byHeat;
    return pick((crop) => crop.climateRisk, true);
  }
  return pick((crop) => crop.wrsiPct, false);
}

export type Outcome = {
  contender: Contender;
  season: AlignedSeason | null;
  /** The challenge criterion for that season, 0–100; null = unknown. */
  score: number | null;
  /** All replay criteria for that season, 0–100. */
  seasonScores: Record<SeasonCriterion, number | null>;
  crops: CropEvidence[];
  exposed: CropEvidence | null;
  /** Why this rotation has no score, when it has none. */
  missing?: string;
};

export type EvidenceMetric = {
  label: string;
  value: number | null;
  unit: string;
  /** Median over the observed record, for context. */
  typical: number | null;
};

export type Challenge =
  | {
      id: ChallengeId;
      available: true;
      title: string;
      noun: string;
      criterion: SeasonCriterion;
      year: number;
      /** Historical date every compared replay started from. */
      fieldFree: string;
      headline: EvidenceMetric;
      metrics: EvidenceMetric[];
      why: string;
      limitation: string;
      outcomes: Outcome[];
      /** Outcomes with the highest known score (more than one on a tie). */
      best: Outcome[];
      notes: string[];
      period: { start: number; end: number };
      sourceIds: string[];
    }
  | { id: ChallengeId; available: false; title: string; reason: string };

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

type Indicator = {
  /** Severity for ranking; null when the year lacks the data. Higher = harder. */
  severity: (year: ClimateYear, record: ClimateYear[]) => number | null;
  /** Deterministic tie-break, higher = harder. */
  tieBreak: (year: ClimateYear) => number;
};

const deficit = (year: ClimateYear) =>
  year.et0_mm != null && year.rain_mm != null ? year.et0_mm - year.rain_mm : null;

/** Mid-rank percentile (0–1) of `value` among the known record values. */
function percentile(value: number, values: number[]) {
  const below = values.filter((v) => v < value).length;
  const equal = values.filter((v) => v === value).length;
  return (below + (equal - 1) / 2) / Math.max(1, values.length - 1);
}

const INDICATORS: Record<ChallengeId, Indicator> = {
  drought: {
    severity: deficit,
    tieBreak: (year) => -(year.rain_mm ?? Infinity),
  },
  heat: {
    severity: (year) => year.hot_days_gt32 ?? null,
    tieBreak: (year) => year.tmean_c ?? -Infinity,
  },
  rainfall: {
    // Both observed extremes at once: rank of the longest dry spell plus rank of heavy-rain days.
    severity: (year, record) => {
      if (year.dry_spell_max_days_apr_sep == null || year.heavy_rain_days_gt20mm == null) return null;
      const both = record.filter(
        (y) => y.dry_spell_max_days_apr_sep != null && y.heavy_rain_days_gt20mm != null,
      );
      return (
        percentile(year.dry_spell_max_days_apr_sep, both.map((y) => y.dry_spell_max_days_apr_sep!)) +
        percentile(year.heavy_rain_days_gt20mm, both.map((y) => y.heavy_rain_days_gt20mm!))
      );
    },
    tieBreak: (year) => year.dry_spell_max_days_apr_sep ?? -Infinity,
  },
};

const typicalOf = (record: ClimateYear[], value: (y: ClimateYear) => number | null | undefined) =>
  median(record.map(value).filter((v): v is number => v != null && Number.isFinite(v)));

const round = (value: number | null) => (value == null ? null : Math.round(value));
const tenth = (value: number | null) => (value == null ? null : Math.round(value * 10) / 10);

function evidence(id: ChallengeId, year: ClimateYear, record: ClimateYear[], candidates: number) {
  const among = `among the ${candidates} past seasons every rotation could be replayed over`;
  const typical = (value: number | null, unit: string) =>
    value == null ? "" : ` (typical: ${Math.round(value)}${unit})`;
  if (id === "drought") {
    const d = deficit(year)!;
    const typicalDeficit = typicalOf(record, deficit);
    const metrics: EvidenceMetric[] = [
      { label: "Rain", value: round(year.rain_mm ?? null), unit: "mm", typical: round(typicalOf(record, (y) => y.rain_mm)) },
      { label: "Water demand of the air (ET₀)", value: round(year.et0_mm ?? null), unit: "mm", typical: round(typicalOf(record, (y) => y.et0_mm)) },
      { label: "Longest dry spell, April–September", value: year.dry_spell_max_days_apr_sep ?? null, unit: "days", typical: round(typicalOf(record, (y) => y.dry_spell_max_days_apr_sep)) },
    ];
    return {
      headline: { label: "Water deficit (ET₀ − rain)", value: Math.round(d), unit: "mm", typical: round(typicalDeficit) },
      metrics,
      why:
        `In ${year.year} the air could have evaporated ${Math.round(year.et0_mm!)} mm of water but only ` +
        `${Math.round(year.rain_mm!)} mm of rain fell: a deficit of ${Math.round(d)} mm${typical(typicalDeficit, " mm")}, ` +
        `the largest ${among}.`,
      limitation:
        "The deficit is a calendar-year total for the NASA POWER grid cell, not a field measurement. " +
        "The scores come from P3's FAO-56 water balance replay; they are not yield or loss estimates.",
    };
  }
  if (id === "heat") {
    const typicalHot = typicalOf(record, (y) => y.hot_days_gt32);
    return {
      headline: { label: "Days above 32 °C", value: year.hot_days_gt32!, unit: "days", typical: round(typicalHot) },
      metrics: [
        { label: "Mean temperature", value: tenth(year.tmean_c ?? null), unit: "°C", typical: tenth(typicalOf(record, (y) => y.tmean_c)) },
        { label: "Longest dry spell, April–September", value: year.dry_spell_max_days_apr_sep ?? null, unit: "days", typical: round(typicalOf(record, (y) => y.dry_spell_max_days_apr_sep)) },
        { label: "Rain", value: round(year.rain_mm ?? null), unit: "mm", typical: round(typicalOf(record, (y) => y.rain_mm)) },
      ],
      why:
        `${year.year} had ${year.hot_days_gt32} days above 32 °C${typical(typicalHot, " days")}, the most ${among}.`,
      limitation:
        "Days above 32 °C are yearly context only. Crop-level heat evidence is P3's count of days above " +
        "each crop's own threshold during flowering and grain fill; no yield loss is estimated.",
    };
  }
  const typicalDry = typicalOf(record, (y) => y.dry_spell_max_days_apr_sep);
  const typicalHeavy = typicalOf(record, (y) => y.heavy_rain_days_gt20mm);
  return {
    headline: {
      label: "Longest dry spell, April–September",
      value: year.dry_spell_max_days_apr_sep!,
      unit: "days",
      typical: round(typicalDry),
    },
    metrics: [
      { label: "Days with more than 20 mm of rain", value: year.heavy_rain_days_gt20mm!, unit: "days", typical: round(typicalHeavy) },
      { label: "Rain", value: round(year.rain_mm ?? null), unit: "mm", typical: round(typicalOf(record, (y) => y.rain_mm)) },
    ],
    why:
      `${year.year} combined a ${year.dry_spell_max_days_apr_sep}-day dry spell between April and September` +
      `${typical(typicalDry, " days")} with ${year.heavy_rain_days_gt20mm} days of more than 20 mm of rain` +
      `${typical(typicalHeavy, " days")}: the most uneven rainfall ${among}.`,
    limitation:
      "Heavy-rain days are observed weather only: the evaluator does not model flooding, waterlogging " +
      "or erosion, so no damage from them is shown. The scores reflect water supply (including dry spells) " +
      "in P3's water balance replay.",
  };
}

function hasHypotheticalScenario(result: RecommendationResult, request?: RecommendationRequest) {
  if (request) return request.scenario.temp_change_c !== 0 || request.scenario.rain_change_pct !== 0;
  return result.assumptions.some((text) => /hypothetical scenario/i.test(text));
}

const signed = (value: number, unit: string) => `${value > 0 ? "+" : ""}${value}${unit}`;

/** Build one challenge from the result, or explain why it cannot be shown fairly. */
export function buildChallenge(
  id: ChallengeId,
  result: RecommendationResult,
  request?: RecommendationRequest,
): Challenge {
  const meta = CHALLENGES.find((challenge) => challenge.id === id)!;
  const unavailable = (reason: string): Challenge => ({ id, available: false, title: meta.title, reason });
  const all = contenders(result);
  if (!all.length) return unavailable("There are no rotations to compare.");
  const record = result.climate_context?.years ?? [];
  if (!record.length)
    return unavailable("The result has no observed yearly weather for this location, so no season can be chosen.");
  const aligned = new Map(all.map((c) => [c.key, alignedSeasons(c.plan, request?.available_from)]));
  const replayed = all.filter((c) => aligned.get(c.key)!.length);
  if (!replayed.length)
    return unavailable(
      "No rotation was replayed over past seasons (not enough daily weather), so there is nothing to compare.",
    );

  const indicator = INDICATORS[id];
  const ranked = record
    .map((year) => ({ year, severity: indicator.severity(year, record) }))
    .filter((entry): entry is { year: ClimateYear; severity: number } => entry.severity !== null)
    .sort(
      (a, b) =>
        b.severity - a.severity ||
        indicator.tieBreak(b.year) - indicator.tieBreak(a.year) ||
        a.year.year - b.year.year,
    );
  if (!ranked.length)
    return unavailable(
      id === "drought"
        ? "Rain and evapotranspiration are not both available for any year, so the driest season cannot be identified."
        : id === "heat"
          ? "Hot-day counts are not available for any year, so the hottest season cannot be identified."
          : "Dry-spell and heavy-rain counts are not both available for any year, so this challenge cannot be identified.",
    );

  // A year is fair only when every replayed rotation has a season that started from the
  // same historical date with that year as its first summer.
  const fairStart = (summer: number) => {
    const seasons = replayed.map((c) => aligned.get(c.key)!.find((s) => s.summer === summer));
    if (seasons.some((s) => !s)) return null;
    const dates = new Set(seasons.map((s) => s!.fieldFree));
    return dates.size === 1 ? seasons[0]!.fieldFree : null;
  };
  const candidates = ranked.filter((entry) => fairStart(entry.year.year) !== null);
  if (!candidates.length)
    return unavailable(
      "No past season was replayed for every rotation from the same starting date, so a fair head-to-head comparison is not possible.",
    );
  const chosen = candidates[0];
  const fieldFree = fairStart(chosen.year.year)!;

  const outcomes: Outcome[] = all.map((contender) => {
    const season = aligned.get(contender.key)!.find((s) => s.fieldFree === fieldFree) ?? null;
    if (!season)
      return {
        contender,
        season: null,
        score: null,
        seasonScores: { water: null, climate: null, productivity: null },
        crops: [],
        exposed: null,
        missing: "Not replayed over past seasons; its score for this season is unknown.",
      };
    const seasonScores = {
      water: scorePercent(season.season.scores.water),
      climate: scorePercent(season.season.scores.climate),
      productivity: scorePercent(season.season.scores.productivity),
    };
    const crops = cropEvidence(contender.plan, season);
    return {
      contender,
      season,
      score: seasonScores[meta.criterion],
      seasonScores,
      crops,
      exposed: mostExposed(crops, id),
      missing:
        seasonScores[meta.criterion] === null
          ? `The engine did not compute a ${meta.criterion} score for this season.`
          : undefined,
    };
  });
  const scored = outcomes.filter((o) => o.score !== null);
  const top = scored.length ? Math.max(...scored.map((o) => o.score!)) : null;
  const best = top === null ? [] : scored.filter((o) => o.score === top);

  const notes: string[] = [];
  const recordTop = ranked[0];
  if (recordTop.year.year !== chosen.year.year)
    notes.push(
      `The record's most extreme year for this challenge, ${recordTop.year.year}, could not be replayed for every rotation ` +
        "(a full rotation would run past the end of the weather record), so the hardest fair season is shown.",
    );
  if (hasHypotheticalScenario(result, request)) {
    const scenario = request?.scenario;
    notes.push(
      `Scenario-adjusted: the scores include the hypothetical scenario` +
        (scenario
          ? ` (${signed(scenario.temp_change_c, " °C")}, ${signed(scenario.rain_change_pct, "% rain")})`
          : "") +
        ` applied to ${chosen.year.year}'s weather. The weather evidence above is what was observed; the scores are not.`,
    );
  }
  if (result.mode === "demo")
    notes.push("Demo mode: the weather values and scores are fictional examples, not NASA observations for your field.");
  if (outcomes.some((o) => o.season && !o.season.exact))
    notes.push(
      "The engine did not report each replay's start date; it was derived from the plan calendar and the field availability date.",
    );
  for (const outcome of outcomes)
    if (outcome.contender.plan.confidence === "low")
      notes.push(`${outcome.contender.label}: confidence is low (regional rules are provisional or data is missing).`);
  if (scored.length < 2)
    notes.push("Fewer than two rotations have a score for this season, so there is no head-to-head comparison.");

  const ev = evidence(id, chosen.year, record, candidates.length);
  return {
    id,
    available: true,
    title: meta.title,
    noun: meta.noun,
    criterion: meta.criterion,
    year: chosen.year.year,
    fieldFree,
    ...ev,
    outcomes,
    best,
    notes,
    period: { start: result.climate_context!.period.start_year, end: result.climate_context!.period.end_year },
    sourceIds: result.climate_context!.source_ids,
  };
}

export const buildChallenges = (result: RecommendationResult, request?: RecommendationRequest) =>
  CHALLENGES.map(({ id }) => buildChallenge(id, result, request));

/** The default "your rotation": the current rotation when evaluated, else Plan 1. */
export const defaultMine = (result: RecommendationResult) =>
  result.baseline ? "baseline" : result.plans[0]?.id;

type AvailableChallenge = Extract<Challenge, { available: true }>;

/** The decision question, from the season scores only. */
export function decisionQuestion(challenge: AvailableChallenge, mineKey: string) {
  const mine = challenge.outcomes.find((o) => o.contender.key === mineKey);
  const subject = mine?.contender.baseline ? "your current rotation" : `your chosen rotation (${mine?.contender.label})`;
  if (!mine || mine.score === null)
    return `We cannot score ${subject} for this ${challenge.noun}. Which rotation would you trust?`;
  if (challenge.best.some((o) => o.contender.key === mineKey))
    return `${capitalise(subject)} held up best in this ${challenge.noun} (${mine.score}/100). Would you keep it, or still switch?`;
  const leader = challenge.best[0];
  if (isSmallDifference(leader.score! - mine.score))
    return (
      `${capitalise(subject)} scored close to ${leader.contender.label} in this ${challenge.noun}: ` +
      `${mine.score}/100 against ${leader.score}/100, a small difference for a single season. Would you keep it or switch?`
    );
  return (
    `${capitalise(subject)} scored lower in this ${challenge.noun}: ${mine.score}/100 against ${leader.score}/100 ` +
    `for ${leader.contender.label}. Would you keep it or switch to the higher-scoring alternative?`
  );
}

/**
 * Season scores are rounded relative indices from one replayed season, not measurements;
 * a gap below this many points out of 100 is described as small rather than as a lead.
 * A wording threshold only: it does not change any score, ranking or "best" marker.
 */
export const SMALL_DIFFERENCE_POINTS = 5;
export const isSmallDifference = (points: number) => Math.abs(points) < SMALL_DIFFERENCE_POINTS;

const capitalise = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

export type Verdict = "better" | "worse" | "equal" | "unknown";

export type Reveal = {
  mine: Outcome;
  pick: Outcome;
  switched: boolean;
  /** pick − mine on the challenge criterion, in displayed points; null when unknown. */
  difference: number | null;
  verdict: Verdict;
  /** The rotation compared with "mine" (the pick, or the season's best when kept). */
  other: Outcome | null;
  tradeoffs: string[];
  /** P4 trade-off text of the other rotation. */
  engineTradeoffs: string[];
  unknowns: string[];
  takeaway: string;
};

/** Where `other` is weaker than `mine`: overall P3 scores and the other season scores. */
function tradeoffsOf(challenge: AvailableChallenge, mine: Outcome, other: Outcome) {
  const tradeoffs: string[] = [];
  const unknowns: string[] = [];
  for (const [key] of SCORE_CRITERIA) {
    const a = scorePercent(other.contender.plan.scores?.[key]);
    const b = scorePercent(mine.contender.plan.scores?.[key]);
    if (a === null || b === null) {
      if (other.contender.plan.scores?.[key] !== undefined || mine.contender.plan.scores?.[key] !== undefined)
        unknowns.push(`Overall ${CRITERION_NAME[key]} score unknown for ${a === null ? other.contender.label : mine.contender.label}.`);
      continue;
    }
    if (a < b) tradeoffs.push(`its overall ${CRITERION_NAME[key]} score is lower (${a} vs ${b})`);
  }
  for (const key of ["water", "climate", "productivity"] as const) {
    if (key === challenge.criterion) continue;
    const a = other.seasonScores[key];
    const b = mine.seasonScores[key];
    if (a !== null && b !== null && a < b)
      tradeoffs.push(`its ${CRITERION_NAME[key]} score in ${challenge.year} is lower (${a} vs ${b})`);
  }
  return { tradeoffs, unknowns };
}

const joinClauses = (items: string[]) =>
  items.length <= 1 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;

/** Compare the farmer's pick with their rotation for the same past season. */
export function revealChoice(challenge: AvailableChallenge, mineKey: string, pickKey: string): Reveal | null {
  const mine = challenge.outcomes.find((o) => o.contender.key === mineKey);
  const pick = challenge.outcomes.find((o) => o.contender.key === pickKey);
  if (!mine || !pick) return null;
  const switched = mineKey !== pickKey;
  const kind = `${CRITERION_NAME[challenge.criterion]} score`;
  const when = `in the ${challenge.year} ${challenge.noun}`;
  // Kept: compare with the strongest alternative of the season, if any beat it.
  const other = switched
    ? pick
    : (challenge.best.find((o) => o.contender.key !== mineKey && (mine.score === null || o.score! > mine.score)) ?? null);
  const difference =
    other && other.score !== null && mine.score !== null ? other.score - mine.score : null;
  const verdict: Verdict =
    difference === null ? "unknown" : difference > 0 ? "better" : difference < 0 ? "worse" : "equal";
  const { tradeoffs, unknowns } = other ? tradeoffsOf(challenge, mine, other) : { tradeoffs: [], unknowns: [] };
  const engineTradeoffs = other ? other.contender.plan.tradeoffs.slice(0, 2) : [];

  let takeaway: string;
  if (!switched && !other) {
    takeaway =
      mine.score === null
        ? `No rotation has a known ${kind} ${when}, so this season cannot rank them.`
        : `You kept ${mine.contender.baseline ? "your current rotation" : mine.contender.label}, and it had the highest ${kind} of the compared rotations ${when} (${mine.score}/100).`;
  } else if (verdict === "unknown") {
    const who = (other ?? pick).score === null ? (other ?? pick).contender.label : mine.contender.label;
    takeaway = `No fair comparison: the ${kind} of ${who} ${when} is unknown.`;
  } else {
    const o = other!;
    const name = o.contender.label;
    const minePhrase = mine.contender.baseline ? "your current rotation" : mine.contender.label;
    if (verdict === "equal")
      takeaway = `${name} and ${minePhrase} had the same ${kind} ${when} (${o.score}/100).`;
    else if (verdict === "better")
      takeaway =
        (isSmallDifference(difference!)
          ? `${name} scored slightly higher than ${minePhrase} ${when}: ${o.score} vs ${mine.score} (${signed(difference!, " points")}, a small difference for a single season)`
          : `${name} performed better than ${minePhrase} ${when}: ${o.score} vs ${mine.score} (${signed(difference!, " points")})`) +
        (tradeoffs.length ? `, but ${joinClauses(tradeoffs)}.` : ", and none of its other known scores is lower.");
    else
      takeaway = isSmallDifference(difference!)
        ? `${name} scored slightly lower than ${minePhrase} ${when}: ${o.score} vs ${mine.score} (${signed(difference!, " points")}), a small difference for a single season.`
        : `${name} performed worse than ${minePhrase} ${when}: ${o.score} vs ${mine.score} (${signed(difference!, " points")}).` +
          " Keeping your rotation would have done better in this season.";
    if (!switched && verdict === "better") takeaway = `You kept your rotation. ${takeaway}`;
  }
  return { mine, pick, switched, difference, verdict, other, tradeoffs, engineTradeoffs, unknowns, takeaway };
}
