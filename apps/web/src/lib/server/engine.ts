import "server-only";
import {
  requestSchema,
  resultSchema,
  validateResultSemantics,
  type RecommendationResult,
} from "@fieldshift/contracts";
import { ApiError } from "./http";
import { engineConfig, upstreamJson } from "./upstream";

export async function recommend(
  input: unknown,
  requestId: string,
  signal?: AbortSignal,
): Promise<RecommendationResult> {
  const parsed = requestSchema.safeParse(input);
  if (
    !parsed.success ||
    Object.values(parsed.data.priorities).every((value) => value === 0)
  )
    throw new ApiError(
      400,
      "validation_error",
      "Check the form and choose at least one positive priority.",
    );
  const config = engineConfig("recommendations");
  const body = await upstreamJson(config.url, {
    prefix: "engine",
    notReady: true,
    unsupported: true,
    signal,
    invalidCode: "invalid_engine_result",
    timeoutMs: config.timeoutMs,
    init: {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${config.token}`,
        "x-request-id": requestId,
      },
      body: JSON.stringify(parsed.data),
    },
  });
  const result = resultSchema.safeParse(body);
  if (
    !result.success ||
    result.data.request_id !== requestId ||
    validateResultSemantics(result.data).length
  )
    throw new ApiError(
      502,
      "invalid_engine_result",
      "The analysis engine returned an invalid result.",
    );
  if (
    result.data.location.latitude !== parsed.data.location.latitude ||
    result.data.location.longitude !== parsed.data.location.longitude ||
    result.data.plans.some((plan) =>
      plan.steps.some(
        (step) =>
          step.sowing_window.start < parsed.data.available_from ||
          parsed.data.constraints.excluded_crops.includes(step.crop_id),
      ),
    )
  )
    throw new ApiError(
      502,
      "invalid_engine_result",
      "The result does not match the request constraints.",
    );
  return result.data;
}
