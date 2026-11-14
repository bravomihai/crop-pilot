import { z } from "zod";

export const CONTRACT_VERSION = "1.0" as const;
export const locationSchema = z
  .object({
    name: z.string().trim().min(1).max(160).optional(),
    latitude: z.number().min(-90).max(90),
    longitude: z.number().min(-180).max(180),
  })
  .strict();
export const dateSchema = z.iso.date();
export const cropHistorySchema = z
  .object({
    crop_id: z.string().regex(/^[a-z][a-z0-9_]*$/),
    harvest_year: z.number().int().min(1950).max(2150).optional(),
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
    available_from: dateSchema,
    crop_count: z.literal(3).default(3),
    history: z.array(cropHistorySchema).max(30).default([]),
    soil: soilSchema.optional(),
    priorities: z
      .object({
        water: z.number().min(0).max(5),
        soil: z.number().min(0).max(5),
        climate: z.number().min(0).max(5),
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
    assumptions: z.array(z.string()),
    data_gaps: z.array(z.string()),
    sources: z.array(sourceSchema),
    disclaimer: z.string(),
  })
  .strict();
export type RecommendationRequest = z.infer<typeof requestSchema>;
export type RecommendationResult = z.infer<typeof resultSchema>;
export type RotationPlan = z.infer<typeof planSchema>;
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
  }
  return errors;
}
