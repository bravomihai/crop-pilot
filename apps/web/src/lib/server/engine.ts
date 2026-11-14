import "server-only";
import {
  requestSchema,
  resultSchema,
  validateResultSemantics,
  type RecommendationResult,
} from "@fieldshift/contracts";
import { ApiError } from "./http";
export async function recommend(
  input: unknown,
  requestId: string,
): Promise<RecommendationResult> {
  const parsed = requestSchema.safeParse(input);
  if (!parsed.success)
    throw new ApiError(
      400,
      "validation_error",
      "Check the location, availability date, and form values.",
    );
  if (Object.values(parsed.data.priorities).every((v) => v === 0))
    throw new ApiError(
      400,
      "validation_error",
      "Choose at least one priority.",
    );
  const url = process.env.ENGINE_URL,
    token = process.env.INTERNAL_API_TOKEN;
  if (!url || !token || token.length < 32)
    throw new ApiError(
      503,
      "engine_not_configured",
      "The analysis engine is not configured.",
    );
  let response: Response;
  try {
    response = await fetch(`${url.replace(/\/$/, "")}/recommendations`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${token}`,
        "x-request-id": requestId,
      },
      body: JSON.stringify(parsed.data),
      signal: AbortSignal.timeout(
        Number(process.env.ENGINE_TIMEOUT_MS ?? 90000),
      ),
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      502,
      "engine_unavailable",
      "The analysis engine is temporarily unavailable. Please try again.",
    );
  }
  if (response.status === 503)
    throw new ApiError(
      503,
      "engine_not_ready",
      "The agronomic engine is still in development. Use demo mode.",
    );
  if (!response.ok)
    throw new ApiError(
      502,
      "engine_error",
      "The engine could not complete the analysis.",
    );
  const result = resultSchema.safeParse(
    await response.json().catch(() => null),
  );
  if (
    !result.success ||
    result.data.request_id !== requestId ||
    validateResultSemantics(result.data).length
  )
    throw new ApiError(
      502,
      "invalid_engine_result",
      "The engine returned an incomplete or invalid result.",
    );
  if (
    result.data.location.latitude !== parsed.data.location.latitude ||
    result.data.location.longitude !== parsed.data.location.longitude
  )
    throw new ApiError(
      502,
      "invalid_engine_result",
      "The result location does not match the request.",
    );
  return result.data;
}
