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
    assumptions: z.array(z.string()),
    data_gaps: z.array(z.string()),
    sources: z.array(sourceSchema),
    disclaimer: z.string(),
  })
  .strict();
export type RecommendationRequest = z.infer<typeof requestSchema>;
export type RecommendationResult = z.infer<typeof resultSchema>;
export type RotationPlan = z.infer<typeof planSchema>;
export type CriterionScores = z.infer<typeof criterionScoresSchema>;
export type HistorySource = z.infer<typeof historySourceSchema>;
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
  return errors;
}
