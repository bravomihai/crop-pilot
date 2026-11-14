import "server-only";
import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import type { RecommendationResult, RotationPlan } from "@fieldshift/contracts";
import { ApiError } from "./http";

/**
 * AI summary of a calculated result, in plain words (English or Romanian).
 *
 * The engine decides; the model only rewords what the engine computed. Every number the
 * model writes must appear in the input, otherwise the summary is rejected and the page
 * keeps the engine's own texts. Nothing is stored and no coordinates are sent.
 */

export const SUMMARY_MODEL = "claude-opus-5-5";
export type SummaryLanguage = "en" | "ro";

export const aiSummarySchema = z.object({
  headline: z.string().min(1).max(400),
  plans: z
    .array(
      z.object({
        id: z.string().min(1),
        in_short: z.string().min(1).max(400),
        why: z.string().min(1).max(600),
        watch_out: z.array(z.string().min(1).max(300)).max(4),
        ask_your_agronomist: z.array(z.string().min(1).max(300)).max(4),
      }),
    )
    .max(4),
});
export type AiSummary = z.infer<typeof aiSummarySchema>;

const PLAN_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["id", "in_short", "why", "watch_out", "ask_your_agronomist"],
  properties: {
    id: { type: "string", description: "The plan id from the input, unchanged." },
    in_short: { type: "string", description: "One sentence a farmer understands." },
    why: { type: "string", description: "Two or three sentences: why this plan, from the evidence." },
    watch_out: { type: "array", items: { type: "string" }, description: "Up to 3 risks from the input." },
    ask_your_agronomist: { type: "array", items: { type: "string" }, description: "Up to 3 checks from the input." },
  },
} as const;

export const OUTPUT_JSON_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["headline", "plans"],
  properties: {
    headline: { type: "string", description: "One or two sentences comparing the plans with the current rotation." },
    plans: { type: "array", items: PLAN_SCHEMA },
  },
} as const;

const ROMANIAN_TERMS =
  "Use these Romanian terms: crop rotation = rotația culturilor; winter wheat = grâu de toamnă; " +
  "winter barley = orz de toamnă; winter rapeseed = rapiță de toamnă; maize = porumb; " +
  "sunflower = floarea-soarelui; soybean = soia; pea = mazăre; current rotation = rotația actuală; " +
  "soil = sol; water need = necesarul de apă; frost = îngheț; heat = arșiță; agronomist = agronom; " +
  "cover crop = cultură de acoperire; legume = leguminoasă.";

export function systemPrompt(language: SummaryLanguage) {
  return [
    "You explain crop rotation plans to a farmer in Romania, in plain words, for someone with no technical background.",
    "The plans, scores and evidence below were calculated by a rule-based engine from NASA weather data, soil data and crop rules.",
    "Rules:",
    "- Use only facts that are in the input. Do not add crop advice, yields, prices, dates or numbers of your own.",
    "- Every number you write must appear in the input exactly (scores are out of 100). Prefer words over numbers.",
    "- Never rank the plans differently from the input, and never recommend something the input does not.",
    "- Mention the farmer's current rotation in the headline if the input has one.",
    "- watch_out comes from the trade-offs and warnings; ask_your_agronomist comes from the local checks.",
    "- Keep each sentence short. No jargon: no 'score median', 'Pareto', 'evaluator'.",
    language === "ro"
      ? `- Write in Romanian, with correct diacritics (ă, â, î, ș, ț). ${ROMANIAN_TERMS}`
      : "- Write in English.",
  ].join("\n");
}

const clip = (items: string[] | undefined, count: number) => (items ?? []).slice(0, count);

function planInput(plan: RotationPlan) {
  return {
    id: plan.id,
    label: plan.label,
    crops: plan.steps.map((step) => ({
      crop: step.crop_name,
      sowing: `${step.sowing_window.start} to ${step.sowing_window.end}`,
      harvest: `${step.harvest_window.start} to ${step.harvest_window.end}`,
    })),
    scores_out_of_100: Object.fromEntries(
      Object.entries(plan.scores ?? {}).map(([name, value]) => [name, value == null ? null : Math.round(value * 100)]),
    ),
    benefits: clip(plan.benefits, 6),
    tradeoffs: clip(plan.tradeoffs, 6),
    local_checks: clip(plan.local_checks, 6),
    rule_violations: plan.violations ?? [],
    confidence: plan.confidence,
  };
}

/** What the model sees: the computed result without coordinates, ids or sources. */
export function summaryInput(result: RecommendationResult) {
  const trends = result.climate_context?.trends ?? {};
  const pick = (key: string) =>
    trends[key] ? { mean: Math.round(trends[key].mean), per_decade: Math.round(trends[key].per_decade) } : undefined;
  return {
    place: result.location.name ?? "the selected field",
    status: result.status,
    plans: result.plans.map(planInput),
    current_rotation: result.baseline ? planInput(result.baseline) : null,
    climate_trends: result.climate_context
      ? {
          period: `${result.climate_context.period.start_year} to ${result.climate_context.period.end_year}`,
          days_above_32C: pick("hot_days_gt32"),
          yearly_rain_mm: pick("rain_mm"),
        }
      : null,
    missing_data: clip(result.data_gaps, 6),
  };
}

const NUMBER = /\d+(?:[.,]\d+)?/g;
const normalise = (value: string) => String(Number(value.replace(",", ".")));

/** Numbers the model wrote that do not appear in the input (empty = grounded). */
export function ungroundedNumbers(summary: AiSummary, input: unknown): string[] {
  const allowed = new Set((JSON.stringify(input).match(NUMBER) ?? []).map(normalise));
  const written = JSON.stringify({ ...summary, plans: summary.plans.map(({ id: _id, ...rest }) => rest) }).match(NUMBER) ?? [];
  return [...new Set(written.map(normalise))].filter((value) => !allowed.has(value));
}

type MessagesClient = Pick<Anthropic, "beta">;

export function summaryConfigured() {
  return Boolean(process.env.ANTHROPIC_API_KEY) && process.env.AI_SUMMARY_ENABLED !== "false";
}

export async function summarize(
  result: RecommendationResult,
  language: SummaryLanguage,
  client: MessagesClient = new Anthropic(),
  signal?: AbortSignal,
): Promise<AiSummary> {
  const input = summaryInput(result);
  const response = await client.beta.messages.create(
    {
      model: SUMMARY_MODEL,
      max_tokens: 8000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      system: systemPrompt(language),
      output_config: { effort: "low", format: { type: "json_schema", schema: OUTPUT_JSON_SCHEMA } },
      messages: [{ role: "user", content: JSON.stringify(input) }],
    },
    { signal, timeout: 60_000 },
  );
  if (response.stop_reason === "refusal")
    throw new ApiError(502, "summary_declined", "The AI summary is not available for this result.");
  const text = response.content.flatMap((block) => (block.type === "text" ? [block.text] : [])).join("");
  let parsed: AiSummary;
  try {
    parsed = aiSummarySchema.parse(JSON.parse(text));
  } catch {
    throw new ApiError(502, "summary_invalid", "The AI summary could not be read. The calculated results are unchanged.");
  }
  const ids = new Set([...result.plans.map((plan) => plan.id), ...(result.baseline ? [result.baseline.id] : [])]);
  parsed = { ...parsed, plans: parsed.plans.filter((plan) => ids.has(plan.id)) };
  const extra = ungroundedNumbers(parsed, input);
  if (extra.length)
    throw new ApiError(
      422,
      "summary_unverified",
      "The AI summary mentioned numbers that are not in the results, so it is not shown. The calculated results are unchanged.",
    );
  return parsed;
}
