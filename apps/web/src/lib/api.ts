import {
  requestSchema,
  resultSchema,
  type RecommendationRequest,
  type RecommendationResult,
} from "@fieldshift/contracts";
import demoResult from "@fieldshift/contracts/demo-result";
export async function getRecommendations(
  input: RecommendationRequest,
  signal?: AbortSignal,
): Promise<RecommendationResult> {
  const request = requestSchema.parse(input);
  if (process.env.NEXT_PUBLIC_USE_MOCK_API === "true") {
    return resultSchema.parse({
      ...demoResult,
      request_id: crypto.randomUUID(),
      location: request.location,
      generated_at: new Date().toISOString(),
      assumptions: [
        ...demoResult.assumptions,
        "Mod frontend independent: calendarul exemplului este fix, iar formularul nu este evaluat.",
      ],
    });
  }
  const response = await fetch("/api/recommendations", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  const body = await response.json();
  if (!response.ok)
    throw new Error(body.error ?? "Analiza nu a putut fi finalizată.");
  return resultSchema.parse(body);
}
