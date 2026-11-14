import {
  requestSchema,
  resultSchema,
  type RecommendationRequest,
  type RecommendationResult,
} from "@fieldshift/contracts";
import demoResult from "@fieldshift/contracts/demo-result";
import fullResult from "../../../../packages/contracts/examples/recommendation-result.full.json";
import fullRequest from "../../../../packages/contracts/examples/recommendation-request.full.json";

export const fullExampleRequest = requestSchema.parse(fullRequest);
export function mockFixture(
  search = typeof window === "undefined" ? "" : window.location.search,
) {
  return new URLSearchParams(search).get("fixture") === "full"
    ? "full"
    : "default";
}
export async function getRecommendations(
  input: RecommendationRequest,
  signal?: AbortSignal,
): Promise<RecommendationResult> {
  const request = requestSchema.parse(input);
  if (process.env.NEXT_PUBLIC_USE_MOCK_API === "true") {
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    const example = mockFixture() === "full" ? fullResult : demoResult;
    return resultSchema.parse({
      ...example,
      baseline:
        "baseline" in example && request.current_rotation?.length
          ? example.baseline
          : undefined,
      mode: "demo",
      request_id: crypto.randomUUID(),
      location: request.location,
      generated_at: new Date().toISOString(),
      assumptions: [
        ...example.assumptions,
        "Independent frontend mode: this fixture has a fixed calendar and fictional scores. Form entries and what-if scenarios are not evaluated. Any baseline is a fixed example, not a calculation of your entered rotation.",
      ],
    });
  }
  const response = await fetch("/api/recommendations", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  // A gateway can answer with a non-JSON error page (e.g. 502/504 HTML).
  const body: unknown = await response.json().catch(() => undefined);
  if (!response.ok) {
    const message =
      body && typeof body === "object" && "error" in body && typeof body.error === "string"
        ? body.error
        : "The analysis could not be completed. Please try again later.";
    throw new Error(message);
  }
  if (body === undefined)
    throw new Error("The analysis service returned an unreadable response.");
  return resultSchema.parse(body);
}
