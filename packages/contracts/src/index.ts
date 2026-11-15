import { z } from "zod";

export const CONTRACT_VERSION = "1.0" as const;
export const locationSchema = z
  .object({
    name: z.string().trim().min(1).max(160).optional(),
    latitude: z.number().min(-90).max(90),
    longitude: z.number().min(-180).max(180),
  })
  .strict();
export const fieldBoundarySchema = z
  .object({
    type: z.literal("Polygon"),
    coordinates: z
      .array(
        z
          .array(
            z.tuple([
              z.number().min(-180).max(180),
              z.number().min(-90).max(90),
            ]),
          )
          .min(4)
          .max(101),
      )
      .length(1),
  })
  .strict()
  .refine(({ coordinates }) => {
    const ring = coordinates[0];
    return (
      ring[0][0] === ring[ring.length - 1][0] &&
      ring[0][1] === ring[ring.length - 1][1]
    );
  }, "The field boundary ring must be closed.");
export const dateSchema = z.iso.date();
export const cropIdSchema = z.string().regex(/^[a-z][a-z0-9_]*$/);
// Where a history entry came from. Typed or documented history is stronger evidence than
// a satellite classification; P4 lowers confidence accordingly. Optional: absent = unknown.
export const historySourceSchema = z.enum([
  "typed",
  "apia",
  "spray_records",
  "satellite",
  "unknown",
]);
export const cropHistorySchema = z
  .object({
    crop_id: cropIdSchema,
    harvest_year: z.number().int().min(1950).max(2150).optional(),
    source: historySourceSchema.optional(),
  })
  .strict();
export const soilSchema = z
  .object({
    texture: z.enum(["sandy", "loamy", "clay", "silty", "unknown"]).optional(),
    ph: z.number().min(0).max(14).optional(),
    organic_carbon_pct: z.number().min(0).max(100).optional(),
    source: z.enum(["farmer_estimate", "lab", "unknown"]).default("unknown"),
  })
  .strict();
export const requestSchema = z
  .object({
    schema_version: z.literal(CONTRACT_VERSION).default(CONTRACT_VERSION),
    location: locationSchema,
    field_boundary: fieldBoundarySchema.optional(),
    available_from: dateSchema,
    crop_count: z.literal(3).default(3),
    history: z.array(cropHistorySchema).max(30).default([]),
    // The rotation the farmer follows today, as one cycle (e.g. ["maize", "winter_wheat"]).
    // When present, the result also contains `baseline`: that cycle continued for the
    // next three main crops and evaluated like the plans, so they can be compared.
    current_rotation: z.array(cropIdSchema).min(1).max(5).optional(),
    // The farmer's own prices and costs for the money estimate, per crop id. Used only for
    // this calculation and never stored.
    money_inputs: z
      .object({
        prices_lei_per_t: z.record(cropIdSchema, z.number().positive().max(100000)).optional(),
        costs_lei_per_ha: z.record(cropIdSchema, z.number().positive().max(100000)).optional(),
      })
      .strict()
      .optional(),
    soil: soilSchema.optional(),
    priorities: z
      .object({
        water: z.number().min(0).max(5),
        soil: z.number().min(0).max(5),
        climate: z.number().min(0).max(5),
        // Relative production potential (EcoCrop suitability, FAO GAEZ attainable yield).
        // Not a yield or profit forecast. Optional: absent = not weighted.
        productivity: z.number().min(0).max(5).optional(),
      })
      .strict(),
    constraints: z
      .object({
        irrigated: z.boolean().default(false),
        max_irrigation_mm: z.number().min(0).max(10000).optional(),
        excluded_crops: z
          .array(z.string().regex(/^[a-z][a-z0-9_]*$/))
          .max(50)
          .default([]),
        selected_crops: z
          .array(z.string().regex(/^[a-z][a-z0-9_]*$/))
          .max(50)
          .optional(),
        selected_crops_only: z.boolean().optional(),
      })
      .strict(),
    scenario: z
      .object({
        temp_change_c: z.number().min(-3).max(5).default(0),
        rain_change_pct: z.number().min(-50).max(50).default(0),
      })
      .strict(),
  })
  .strict();
export const windowSchema = z
  .object({ start: dateSchema, end: dateSchema })
  .strict();
export const sourceSchema = z
  .object({
    id: z.string().min(1),
    title: z.string().min(1),
    url: z
      .string()
      .url()
      .regex(/^https?:\/\//)
      .optional(),
    resolution: z.string().optional(),
  })
  .strict();
export const stepSchema = z
  .object({
    order: z.number().int().min(1).max(3),
    crop_id: z.string().min(1),
    crop_name: z.string().min(1),
    sowing_window: windowSchema,
    harvest_window: windowSchema,
    reason: z.string(),
  })
  .strict();
const scoreSchema = z.number().min(0).max(1).nullable();
export const criterionScoresSchema = z
  .object({
    water: scoreSchema.optional(),
    soil: scoreSchema.optional(),
    climate: scoreSchema.optional(),
    productivity: scoreSchema.optional(),
  })
  .strict();
const yearSchema = z.number().int().min(1950).max(2150);
const dayOfYearSchema = z.number().int().min(1).max(366);
// One crop of a plan in one replayed past season (FAO-56 water balance and crop hazards).
export const replayStepSchema = z
  .object({
    crop_id: cropIdSchema,
    // Share of the crop's water need that rain and stored soil water met (WRSI), percent.
    wrsi_pct: z.number().min(0).max(100).nullable().optional(),
    water_need_mm: z.number().min(0).nullable().optional(),
    water_used_mm: z.number().min(0).nullable().optional(),
    season_rain_mm: z.number().min(0).nullable().optional(),
    // Combined weather risk for the crop that season, 0 = none, 1 = severe.
    climate_risk: z.number().min(0).max(1).nullable().optional(),
    // Hazard name → observed quantity (days above a threshold, mm of rain at sowing, ...).
    hazards: z.record(z.string(), z.number()).optional(),
  })
  .strict();
// The whole plan replayed over one past season, under the request's scenario.
// `season_start_year` is the year the first crop would have been sown.
export const replaySeasonSchema = z
  .object({
    season_start_year: yearSchema,
    // The request's `available_from` moved back to this past season: the replay starts from
    // this date. Seasons of different plans with the same date saw the same weather from
    // the same starting point (plans can sow their first crop in different years, so
    // `season_start_year` alone does not line them up). Optional: older producers omit it.
    field_free_from: dateSchema.optional(),
    scores: criterionScoresSchema,
    steps: z.array(replayStepSchema).max(3).optional(),
  })
  .strict();
// Observed weather at the location, per calendar year. Never scenario-adjusted.
export const climateYearSchema = z
  .object({
    year: yearSchema,
    rain_mm: z.number().min(0).nullable().optional(),
    et0_mm: z.number().min(0).nullable().optional(),
    tmean_c: z.number().nullable().optional(),
    hot_days_gt32: z.number().int().min(0).nullable().optional(),
    frost_days: z.number().int().min(0).nullable().optional(),
    heavy_rain_days_gt20mm: z.number().int().min(0).nullable().optional(),
    // Longest run of days with less than 1 mm of rain between April and September.
    dry_spell_max_days_apr_sep: z.number().int().min(0).nullable().optional(),
    // Last frost (minimum ≤ 0 °C) before July, first frost from July; null = none that year.
    last_spring_frost_doy: dayOfYearSchema.nullable().optional(),
    first_autumn_frost_doy: dayOfYearSchema.nullable().optional(),
  })
  .strict();
export const climateTrendSchema = z
  .object({
    mean: z.number(),
    per_decade: z.number(),
    unit: z.string(),
  })
  .strict();
export const climateContextSchema = z
  .object({
    basis: z.literal("observed"),
    period: z.object({ start_year: yearSchema, end_year: yearSchema }).strict(),
    years: z.array(climateYearSchema).max(80),
    // Linear trend per decade for each `years` field (key = field name), when ≥ 10 years.
    trends: z.record(z.string(), climateTrendSchema).optional(),
    source_ids: z.array(z.string()),
    note: z.string().optional(),
  })
  .strict();
// A money range in lei: low / typical / high. `null` in its place means unknown, never 0.
export const moneyRangeSchema = z
  .object({ low: z.number(), typical: z.number(), high: z.number() })
  .strict();
const valueRangeSchema = moneyRangeSchema;
// Rough money estimate for a plan, per hectare. An estimate from county averages, past
// prices and published cost budgets, not a forecast. It never changes the ranking.
export const economicsSchema = z
  .object({
    currency: z.literal("RON"),
    // Plan length used to turn the plan's totals into amounts per year.
    covered_years: z.number().positive(),
    county: z.string().nullable(),
    // Per hectare per year; null = unknown (for example a crop without a price series).
    per_year: z
      .object({
        income: moneyRangeSchema.nullable(),
        costs: moneyRangeSchema.nullable(),
        subsidies: moneyRangeSchema.nullable(),
        margin: moneyRangeSchema.nullable(),
        // Part of the typical margin that comes from crop order (yield effect of the previous
        // crop and nitrogen left by a legume), lei per hectare and year; null when none applies.
        crop_order_effect: z.number().nullable().optional(),
      })
      .strict(),
    // Per crop, for its one season (not per year).
    crops: z
      .array(
        z
          .object({
            crop_id: z.string(),
            crop_name: z.string(),
            previous_crop: z.string().nullable().optional(),
            // Rating of the previous crop for this crop in the regional rules.
            previous_rating: z.enum(["good", "ok", "poor", "forbidden"]).nullable().optional(),
            yield_t_per_ha: valueRangeSchema.nullable(),
            yield_basis: z.enum(["commercial_farms", "all_farms"]).nullable().optional(),
            price_lei_per_t: valueRangeSchema.nullable(),
            price_basis: z.enum(["regional", "national", "farmer"]).nullable().optional(),
            income: moneyRangeSchema.nullable(),
            costs: moneyRangeSchema.nullable(),
            cost_basis: z.enum(["iceadr", "farmer"]).nullable().optional(),
            // Fertiliser saved because a legume came before, lei per hectare.
            nitrogen_saving: moneyRangeSchema.nullable().optional(),
            // Typical lei per hectare gained (or lost) from the previous crop, for this season.
            crop_order_effect: z.number().nullable().optional(),
          })
          .strict(),
      )
      .max(3),
    // CAP payments that apply, per hectare per year, with the condition attached.
    payments: z
      .array(
        z
          .object({
            id: z.string(),
            label: z.string(),
            lei_per_ha_year: z.number().nullable(),
            included: z.enum(["always", "if_eligible", "not_included"]),
            condition: z.string(),
          })
          .strict(),
      )
      .max(12),
    warnings: z.array(z.string()),
    notes: z.array(z.string()),
    source_ids: z.array(z.string()),
  })
  .strict();
export const planSchema = z
  .object({
    id: z.string(),
    label: z.string(),
    steps: z.array(stepSchema).length(3),
    benefits: z.array(z.string()),
    tradeoffs: z.array(z.string()),
    explanation: z.string(),
    confidence: z.enum(["low", "medium", "high"]),
    source_ids: z.array(z.string()),
    // Optional additions (all producers may omit them):
    // P3 criterion scores, 0–1, higher is better; null = unknown, never a neutral 0.5.
    scores: criterionScoresSchema.optional(),
    // What a local agronomist or the farmer should verify before acting on the plan.
    local_checks: z.array(z.string()).optional(),
    // Agronomic rules the sequence breaks. Recommended plans never break rules, so this is
    // only filled for `baseline`, where the farmer's current rotation is shown as it is.
    violations: z.array(z.string()).optional(),
    // The plan replayed over past seasons at this location, oldest first.
    replay: z.array(replaySeasonSchema).max(60).optional(),
    // Rough money estimate per hectare and year (see economicsSchema).
    economics: economicsSchema.optional(),
  })
  .strict();
export const monthlyClimateSchema = z
  .object({
    month: z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/),
    mean_daily_max_c: z.number().nullable(),
    max_daily_max_c: z.number().nullable(),
    mean_daily_min_c: z.number().nullable(),
    min_daily_min_c: z.number().nullable(),
    max_temp_observations: z.number().int().min(0),
    min_temp_observations: z.number().int().min(0),
  })
  .strict();
export const resultSchema = z
  .object({
    schema_version: z.literal(CONTRACT_VERSION),
    request_id: z.string().min(1),
    mode: z.enum(["demo", "computed"]),
    generated_at: z.iso.datetime({ offset: true }),
    status: z.enum(["complete", "limited", "insufficient_data"]),
    location: locationSchema,
    plans: z.array(planSchema).max(3),
    // The farmer's current rotation continued for three main crops, evaluated the same
    // way as the plans. Present only when the request has `current_rotation`. It is not
    // counted in `status` and may repeat a plan's sequence.
    baseline: planSchema.optional(),
    monthly_climate: z.array(monthlyClimateSchema),
    // Observed yearly climate at the location (from the data the plans were evaluated on).
    climate_context: climateContextSchema.optional(),
    assumptions: z.array(z.string()),
    data_gaps: z.array(z.string()),
    sources: z.array(sourceSchema),
    disclaimer: z.string(),
  })
  .strict();
export type RecommendationRequest = z.infer<typeof requestSchema>;
export type RecommendationResult = z.infer<typeof resultSchema>;
export type RotationPlan = z.infer<typeof planSchema>;
export type PlanEconomics = z.infer<typeof economicsSchema>;
export type MoneyRange = z.infer<typeof moneyRangeSchema>;
export type CriterionScores = z.infer<typeof criterionScoresSchema>;
export type HistorySource = z.infer<typeof historySourceSchema>;
export type ReplaySeason = z.infer<typeof replaySeasonSchema>;
export type ClimateContext = z.infer<typeof climateContextSchema>;
export type ClimateYear = z.infer<typeof climateYearSchema>;
export type Location = z.infer<typeof locationSchema>;

export function validateResultSemantics(
  result: RecommendationResult,
): string[] {
  const errors: string[] = [];
  if (result.status === "complete" && result.plans.length !== 3)
    errors.push("A complete result must contain three plans.");
  if (
    result.status === "limited" &&
    (result.plans.length < 1 || result.plans.length > 2)
  )
    errors.push("A limited result must contain one or two plans.");
  if (result.status === "insufficient_data" && result.plans.length !== 0)
    errors.push("Insufficient data cannot include plans.");
  const ids = new Set(result.sources.map((s) => s.id));
  const signatures = new Set<string>();
  for (const plan of result.plans) {
    const signature = plan.steps.map((s) => s.crop_id).join(">");
    if (signatures.has(signature))
      errors.push("Plans must have distinct sequences.");
    signatures.add(signature);
    if (plan.source_ids.some((id) => !ids.has(id)))
      errors.push("Unknown source reference.");
    plan.steps.forEach((step, i) => {
      if (step.order !== i + 1) errors.push("Steps must be ordered 1, 2, 3.");
      if (
        step.sowing_window.start > step.sowing_window.end ||
        step.harvest_window.start > step.harvest_window.end ||
        step.sowing_window.end > step.harvest_window.start
      )
        errors.push("Invalid crop calendar.");
      if (
        i > 0 &&
        plan.steps[i - 1].harvest_window.end >= step.sowing_window.start
      )
        errors.push("Crop windows overlap.");
    });
    if (plan.violations?.length)
      errors.push("Recommended plans cannot break agronomic rules.");
  }
  if (result.baseline) {
    if (result.baseline.source_ids.some((id) => !ids.has(id)))
      errors.push("Unknown source reference in baseline.");
    result.baseline.steps.forEach((step, i) => {
      if (step.order !== i + 1)
        errors.push("Baseline steps must be ordered 1, 2, 3.");
    });
  }
  for (const plan of [...result.plans, ...(result.baseline ? [result.baseline] : [])]) {
    const years = (plan.replay ?? []).map((r) => r.season_start_year);
    if (years.some((y, i) => i > 0 && y <= years[i - 1]))
      errors.push("Replay seasons must be in increasing year order.");
    const crops = plan.steps.map((s) => s.crop_id);
    if (
      (plan.replay ?? []).some((r) =>
        (r.steps ?? []).some((s, i) => s.crop_id !== crops[i]),
      )
    )
      errors.push("Replay steps must follow the plan's crops.");
  }
  const climate = result.climate_context;
  if (climate) {
    if (climate.source_ids.some((id) => !ids.has(id)))
      errors.push("Unknown source reference in climate context.");
    const years = climate.years.map((y) => y.year);
    if (years.some((y, i) => i > 0 && y <= years[i - 1]))
      errors.push("Climate years must be in increasing order.");
    if (
      climate.period.start_year > climate.period.end_year ||
      years.some((y) => y < climate.period.start_year || y > climate.period.end_year)
    )
      errors.push("Climate years must lie inside the climate period.");
  }
  return errors;
}
