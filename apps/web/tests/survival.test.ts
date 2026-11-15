import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  requestSchema,
  resultSchema,
  type ClimateYear,
  type RecommendationResult,
  type RotationPlan,
} from "@fieldshift/contracts";
import {
  alignedSeasons,
  buildChallenge,
  buildChallenges,
  decisionQuestion,
  defaultMine,
  firstSummer,
  revealChoice,
  shiftIso,
  SURVIVAL_DISCLAIMER,
  type Challenge,
} from "../src/lib/survival";
import { fullExampleRequest } from "../src/lib/api";

// ---------------------------------------------------------------- synthetic result
// Field free on 2026-10-01. Plan 1 sows winter wheat that autumn; Plan 2 and the current
// rotation start with maize in spring 2027. Their `season_start_year` therefore differ by
// one for the same historical start date; only `field_free_from` lines them up.

const AVAILABLE = "2026-10-01";
const step = (order: number, crop: string, name: string, sow: [string, string], harvest: [string, string]) => ({
  order,
  crop_id: crop,
  crop_name: name,
  sowing_window: { start: sow[0], end: sow[1] },
  harvest_window: { start: harvest[0], end: harvest[1] },
  reason: "Test calendar.",
});
const WHEAT_FIRST = [
  step(1, "winter_wheat", "Winter wheat", ["2026-10-01", "2026-10-20"], ["2027-07-01", "2027-07-20"]),
  step(2, "sunflower", "Sunflower", ["2028-04-10", "2028-04-30"], ["2028-09-01", "2028-09-20"]),
  step(3, "winter_wheat", "Winter wheat", ["2028-10-01", "2028-10-20"], ["2029-07-01", "2029-07-20"]),
];
const MAIZE_FIRST = (third: [string, string]) => [
  step(1, "maize", "Maize", ["2027-04-15", "2027-05-05"], ["2027-09-20", "2027-10-10"]),
  step(2, "winter_wheat", "Winter wheat", ["2027-10-15", "2027-10-30"], ["2028-07-01", "2028-07-20"]),
  step(3, third[0], third[1], ["2029-04-20", "2029-05-10"], ["2029-09-10", "2029-09-30"]),
];

type Scores = { water: number | null; climate: number | null; productivity: number | null };
/** Season scores by first summer; anything not listed gets `fallback`. */
function replay(steps: ReturnType<typeof step>[], special: Record<number, Scores>, fallback: Scores, withDate = true) {
  const firstSowingYear = Number(steps[0].sowing_window.start.slice(0, 4));
  const rows = [];
  for (let shift = 21; shift >= 6; shift--) {
    const fieldFree = shiftIso(AVAILABLE, shift);
    const summer = Number(fieldFree.slice(0, 4)) + 1;
    rows.push({
      season_start_year: firstSowingYear - shift,
      ...(withDate ? { field_free_from: fieldFree } : {}),
      scores: special[summer] ?? fallback,
      steps: steps.map((s, i) => ({
        crop_id: s.crop_id,
        wrsi_pct: summer === 2012 ? 40 + 10 * i : 85,
        season_rain_mm: 250,
        climate_risk: summer === 2007 ? 0.2 + 0.2 * i : 0.1,
        hazards: { heat: summer === 2007 ? 3 + 4 * i : 1 },
      })),
    });
  }
  return rows;
}

const plan = (
  id: string,
  steps: ReturnType<typeof step>[],
  overall: RotationPlan["scores"],
  special: Record<number, Scores>,
  extra: Partial<RotationPlan> = {},
  withDate = true,
): RotationPlan => ({
  id,
  label: id,
  steps,
  benefits: [],
  tradeoffs: [`${id} trade-off from the recommender.`],
  explanation: "Test plan.",
  confidence: "medium",
  source_ids: ["nasa-power"],
  scores: overall,
  replay: replay(steps, special, { water: 0.6, climate: 0.6, productivity: 0.5 }, withDate),
  ...extra,
});

function climateYears(): ClimateYear[] {
  const years: ClimateYear[] = [];
  for (let year = 2005; year <= 2024; year++)
    years.push({
      year,
      rain_mm: year === 2012 ? 350 : year === 2023 ? 300 : 550,
      et0_mm: year === 2012 ? 1150 : year === 2023 ? 1200 : 900,
      tmean_c: 11.5,
      hot_days_gt32: year === 2007 ? 55 : year === 2024 ? 70 : 20,
      frost_days: 80,
      heavy_rain_days_gt20mm: year === 2010 ? 7 : 3,
      dry_spell_max_days_apr_sep: year === 2010 ? 35 : 18,
    });
  return years;
}

function makeResult(options: { baseline?: boolean; plans?: number; withDate?: boolean; mode?: "demo" | "computed" } = {}) {
  const { baseline = true, plans = 3, withDate = true, mode = "computed" } = options;
  const all = [
    plan("plan-1", WHEAT_FIRST, { water: 0.7, soil: 0.62, climate: 0.6, productivity: 0.55 }, {
      2012: { water: 0.71, climate: 0.5, productivity: 0.4 },
      2007: { water: 0.6, climate: 0.45, productivity: 0.5 },
    }, {}, withDate),
    plan("plan-2", MAIZE_FIRST(["soybean", "Soybean"]), { water: 0.6, soil: 0.75, climate: 0.6, productivity: 0.5 }, {
      2012: { water: 0.55, climate: 0.6, productivity: 0.45 },
      2007: { water: 0.6, climate: 0.62, productivity: 0.5 },
    }, { confidence: "low" }, withDate),
    plan("plan-3", MAIZE_FIRST(["sunflower", "Sunflower"]), { water: 0.5, soil: 0.7, climate: 0.5, productivity: 0.5 }, {
      2012: { water: 0.5, climate: 0.5, productivity: 0.5 },
    }, {}, withDate),
  ].slice(0, plans);
  const result = {
    schema_version: "1.0",
    request_id: "survival-test",
    mode,
    generated_at: "2026-11-15T10:00:00+00:00",
    status: plans === 3 ? "complete" : "limited",
    location: { name: "Fundulea", latitude: 44.45, longitude: 26.52 },
    plans: all,
    ...(baseline
      ? {
          baseline: plan("baseline", MAIZE_FIRST(["maize", "Maize"]), { water: 0.55, soil: 0.7, climate: 0.55, productivity: 0.5 }, {
            2012: { water: 0.4, climate: 0.52, productivity: 0.42 },
            2007: { water: 0.6, climate: 0.4, productivity: 0.5 },
          }, {}, withDate),
        }
      : {}),
    monthly_climate: [],
    climate_context: { basis: "observed", period: { start_year: 2005, end_year: 2024 }, years: climateYears(), source_ids: ["nasa-power"] },
    assumptions: [],
    data_gaps: [],
    sources: [{ id: "nasa-power", title: "NASA POWER" }],
    disclaimer: "Test.",
  };
  return resultSchema.parse(result);
}

const request = requestSchema.parse({
  ...fullExampleRequest,
  available_from: AVAILABLE,
  scenario: { temp_change_c: 0, rain_change_pct: 0 },
});
const available = (challenge: Challenge) => {
  assert.equal(challenge.available, true, challenge.available ? "" : challenge.reason);
  return challenge as Extract<Challenge, { available: true }>;
};

// ---------------------------------------------------------------- tests

test("challenge seasons come from observed weather: largest deficit, most hot days, most erratic rain", () => {
  const result = makeResult();
  const drought = available(buildChallenge("drought", result, request));
  assert.equal(drought.year, 2012);
  assert.equal(drought.headline.value, 800); // 1150 mm ET0 − 350 mm rain
  assert.equal(drought.headline.typical, 350);
  assert.match(drought.why, /deficit of 800 mm/);
  assert.equal(available(buildChallenge("heat", result, request)).year, 2007);
  const rain = available(buildChallenge("rainfall", result, request));
  assert.equal(rain.year, 2010);
  assert.match(rain.limitation, /does not model flooding/);
});

test("a more extreme year that no rotation can be replayed over is disclosed, not used", () => {
  const drought = available(buildChallenge("drought", makeResult(), request));
  assert.ok(drought.notes.some((note) => note.includes("2023") && note.includes("could not be replayed")));
  const heat = available(buildChallenge("heat", makeResult(), request));
  assert.ok(heat.notes.some((note) => note.includes("2024")));
});

test("every rotation is read from the same historical start date, even when first sowing years differ", () => {
  const drought = available(buildChallenge("drought", makeResult(), request));
  assert.equal(drought.fieldFree, "2011-10-01");
  const byKey = Object.fromEntries(drought.outcomes.map((o) => [o.contender.key, o]));
  for (const outcome of drought.outcomes) assert.equal(outcome.season?.fieldFree, "2011-10-01");
  // Same start, different `season_start_year`: pairing by that year would have been unfair.
  assert.equal(byKey["plan-1"].season?.season.season_start_year, 2011);
  assert.equal(byKey["plan-2"].season?.season.season_start_year, 2012);
  assert.deepEqual(
    drought.outcomes.map((o) => [o.contender.label, o.score]),
    [["Your current rotation", 40], ["Plan 1", 71], ["Plan 2", 55], ["Plan 3", 50]],
  );
  assert.deepEqual(drought.best.map((o) => o.contender.key), ["plan-1"]);
});

test("the most exposed crop is the evaluator's, among crops in the field that summer", () => {
  const drought = available(buildChallenge("drought", makeResult(), request));
  const plan1 = drought.outcomes.find((o) => o.contender.key === "plan-1")!;
  // Wheat sown Oct 2011, harvested Jul 2012: in the field in summer 2012. Sunflower (2013) is not.
  assert.deepEqual(plan1.crops.map((c) => c.inSummer), [true, false, false]);
  assert.equal(plan1.exposed?.cropName, "Winter wheat");
  assert.equal(plan1.exposed?.wrsiPct, 40);
  const heat = available(buildChallenge("heat", makeResult(), request));
  const baseline = heat.outcomes.find((o) => o.contender.baseline)!;
  // Only maize (April–October 2007) is in the field that summer; wheat is sown in mid-October,
  // so its higher heat count (next year) is not attributed to the 2007 heat.
  assert.deepEqual(baseline.crops.map((c) => c.inSummer), [true, false, false]);
  assert.equal(baseline.exposed?.cropName, "Maize");
  assert.equal(baseline.exposed?.heatDays, 3);
});

test("results are deterministic and ties resolve the same way every time", () => {
  const result = makeResult();
  assert.deepEqual(buildChallenges(result, request), buildChallenges(result, request));
  const tied = structuredClone(result);
  for (const year of tied.climate_context!.years) if (year.year === 2015) year.hot_days_gt32 = 55;
  // 2007 and 2015 tie on hot days and mean temperature: the earlier year wins.
  assert.equal(available(buildChallenge("heat", tied, request)).year, 2007);
});

test("score differences use the displayed 0–100 values and name the trade-offs", () => {
  const drought = available(buildChallenge("drought", makeResult(), request));
  const reveal = revealChoice(drought, "baseline", "plan-1")!;
  assert.equal(reveal.difference, 31);
  assert.equal(reveal.verdict, "better");
  assert.ok(reveal.tradeoffs.includes("its overall soil score is lower (62 vs 70)"));
  assert.ok(reveal.tradeoffs.includes("its climate score in 2012 is lower (50 vs 52)"));
  assert.equal(
    reveal.takeaway,
    "Plan 1 performed better than your current rotation in the 2012 drought: 71 vs 40 (+31 points), " +
      "but its overall soil score is lower (62 vs 70), its climate score in 2012 is lower (50 vs 52) " +
      "and its productivity score in 2012 is lower (40 vs 42).",
  );
  assert.deepEqual(reveal.engineTradeoffs, ["plan-1 trade-off from the recommender."]);
  const worse = revealChoice(drought, "plan-1", "plan-2")!;
  assert.equal(worse.difference, -16);
  assert.equal(worse.verdict, "worse");
  assert.match(worse.takeaway, /Keeping your rotation would have done better/);
});

test("keeping a rotation compares it with the season's best, or confirms it led", () => {
  const drought = available(buildChallenge("drought", makeResult(), request));
  const kept = revealChoice(drought, "baseline", "baseline")!;
  assert.equal(kept.switched, false);
  assert.equal(kept.other?.contender.key, "plan-1");
  assert.match(kept.takeaway, /^You kept your rotation\. Plan 1 performed better/);
  const led = revealChoice(drought, "plan-1", "plan-1")!;
  assert.equal(led.other, null);
  assert.match(led.takeaway, /highest water score .* \(71\/100\)/);
  assert.match(decisionQuestion(drought, "baseline"), /struggled in this drought: 40\/100 against 71\/100 for Plan 1/);
  assert.match(decisionQuestion(drought, "plan-1"), /held up best/);
});

test("unknown scores stay unknown and block the comparison instead of counting as zero", () => {
  const result = makeResult();
  const season = result.plans[1].replay!.find((s) => s.field_free_from === "2011-10-01")!;
  season.scores.water = null;
  const drought = available(buildChallenge("drought", result, request));
  const plan2 = drought.outcomes.find((o) => o.contender.key === "plan-2")!;
  assert.equal(plan2.score, null);
  assert.match(plan2.missing!, /did not compute a water score/);
  const reveal = revealChoice(drought, "baseline", "plan-2")!;
  assert.equal(reveal.difference, null);
  assert.equal(reveal.verdict, "unknown");
  assert.match(reveal.takeaway, /No fair comparison: the water score of Plan 2 .* is unknown/);
});

test("without a current rotation, Plan 1 is the farmer's rotation", () => {
  const result = makeResult({ baseline: false });
  assert.equal(defaultMine(result), "plan-1");
  const drought = available(buildChallenge("drought", result, request));
  assert.equal(drought.outcomes.length, 3);
  assert.match(decisionQuestion(drought, "plan-1"), /your chosen rotation \(Plan 1\) held up best/i);
});

test("a single plan is shown honestly, without a head-to-head", () => {
  const drought = available(buildChallenge("drought", makeResult({ baseline: false, plans: 1 }), request));
  assert.equal(drought.outcomes.length, 1);
  assert.ok(drought.notes.some((note) => note.includes("Fewer than two rotations")));
  assert.equal(revealChoice(drought, "plan-1", "plan-1")!.other, null);
});

test("a rotation without replay is listed as unknown; seasons are still chosen fairly", () => {
  const result = makeResult();
  delete result.plans[2].replay;
  const drought = available(buildChallenge("drought", result, request));
  const plan3 = drought.outcomes.find((o) => o.contender.key === "plan-3")!;
  assert.equal(plan3.season, null);
  assert.equal(plan3.score, null);
  assert.match(plan3.missing!, /Not replayed/);
});

test("missing data disables a challenge with a reason", () => {
  const noEt0 = makeResult();
  for (const year of noEt0.climate_context!.years) year.et0_mm = null;
  const drought = buildChallenge("drought", noEt0, request);
  assert.equal(drought.available, false);
  assert.match(drought.available ? "" : drought.reason, /evapotranspiration/);
  assert.equal(buildChallenge("heat", noEt0, request).available, true);

  const noClimate = makeResult();
  delete noClimate.climate_context;
  for (const challenge of buildChallenges(noClimate, request)) assert.equal(challenge.available, false);

  const noReplay = makeResult();
  for (const p of [...noReplay.plans, noReplay.baseline!]) delete p.replay;
  const none = buildChallenge("heat", noReplay, request);
  assert.match(none.available ? "" : none.reason, /No rotation was replayed/);
});

test("different replay periods: only seasons shared by every rotation are eligible", () => {
  const result = makeResult();
  // The current rotation lacks the 2012 season: 2012 is no longer a fair drought year.
  result.baseline!.replay = result.baseline!.replay!.filter((s) => s.field_free_from !== "2011-10-01");
  const drought = available(buildChallenge("drought", result, request));
  assert.notEqual(drought.year, 2012);
  for (const outcome of drought.outcomes) assert.equal(outcome.season?.fieldFree, drought.fieldFree);
  // No shared season at all: refuse rather than compare different years.
  const disjoint = makeResult({ plans: 1 });
  disjoint.baseline!.replay = disjoint.baseline!.replay!.slice(0, 8);
  disjoint.plans[0].replay = disjoint.plans[0].replay!.slice(8);
  const refused = buildChallenge("drought", disjoint, request);
  assert.equal(refused.available, false);
  assert.match(refused.available ? "" : refused.reason, /fair head-to-head/);
});

test("older results without start dates are aligned from the calendar and say so", () => {
  const result = makeResult({ withDate: false });
  const drought = available(buildChallenge("drought", result, request));
  assert.equal(drought.year, 2012);
  assert.equal(drought.fieldFree, "2011-10-01");
  assert.ok(drought.notes.some((note) => note.includes("derived from the plan calendar")));
  // Without the request's availability date they cannot be aligned at all.
  assert.equal(buildChallenge("drought", result).available, false);
});

test("uncertainty: low confidence and the disclaimer are reported", () => {
  const drought = available(buildChallenge("drought", makeResult(), request));
  assert.ok(drought.notes.some((note) => note.startsWith("Plan 2: confidence is low")));
  assert.equal(SURVIVAL_DISCLAIMER, "This compares historical conditions, not a prediction of future harvests.");
});

test("a hypothetical scenario changes the scores' label, never the observed season", () => {
  const result = makeResult();
  const hot = requestSchema.parse({ ...request, scenario: { temp_change_c: 2, rain_change_pct: 0 } });
  const observed = available(buildChallenge("drought", result, request));
  const adjusted = available(buildChallenge("drought", result, hot));
  assert.equal(adjusted.year, observed.year);
  assert.deepEqual(adjusted.headline, observed.headline);
  assert.ok(adjusted.notes.some((note) => note.startsWith("Scenario-adjusted") && note.includes("+2 °C")));
  assert.ok(!observed.notes.some((note) => note.startsWith("Scenario-adjusted")));
  // Without the request, the engine's assumption text is enough to flag it.
  const flagged = { ...result, assumptions: ["Hypothetical scenario applied to every past season: temperature +2.0 °C."] };
  assert.ok(available(buildChallenge("drought", flagged)).notes.some((n) => n.startsWith("Scenario-adjusted")));
});

test("demo results are labelled fictional", () => {
  const full = resultSchema.parse(
    JSON.parse(readFileSync(new URL("../../../packages/contracts/examples/recommendation-result.full.json", import.meta.url), "utf8")),
  ) as RecommendationResult;
  const drought = available(buildChallenge("drought", full, fullExampleRequest));
  assert.ok(drought.notes.some((note) => note.startsWith("Demo mode")));
  assert.equal(drought.year, 2012);
  assert.equal(drought.fieldFree, "2011-10-01");
  assert.equal(makeResult({ mode: "computed" }).mode, "computed");
});

test("date helpers follow P3's year shift", () => {
  assert.equal(shiftIso("2028-02-29", 3), "2025-02-28");
  assert.equal(shiftIso("2026-10-01", 15), "2011-10-01");
  assert.equal(firstSummer("2011-10-01"), 2012);
  assert.equal(firstSummer("2012-03-01"), 2012);
  const result = makeResult();
  assert.equal(alignedSeasons(result.plans[0]).length, 16);
});

test("crop calendars follow the engine's replay even when the request date was moved by the engine", () => {
  // The engine may move a past availability date (here to a different year); the shift
  // comes from the replay itself, so crops are placed in the right historical summer.
  const moved = requestSchema.parse({ ...request, available_from: "2025-12-01" });
  const drought = available(buildChallenge("drought", makeResult(), moved));
  assert.equal(drought.fieldFree, "2011-10-01");
  const plan1 = drought.outcomes.find((o) => o.contender.key === "plan-1")!;
  assert.equal(plan1.season?.shift, 15);
  assert.deepEqual(plan1.crops.map((c) => c.inSummer), [true, false, false]);
});
