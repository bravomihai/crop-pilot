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
        "Independent frontend mode: the example calendar is fixed and form entries are not evaluated.",
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
    throw new Error(body.error ?? "The analysis could not be completed.");
  return resultSchema.parse(body);
}
