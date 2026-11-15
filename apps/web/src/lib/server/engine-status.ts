import "server-only";
import { z } from "zod";
import { CONTRACT_VERSION } from "@croppilot/contracts";
import { ApiError } from "./http";
import { engineConfig, upstreamJson } from "./upstream";

const healthSchema = z.object({
  service: z.literal("croppilot-engine"),
  contract_version: z.literal(CONTRACT_VERSION),
  mode: z.enum(["demo", "computed"]),
});

/** Connectivity and protocol compatibility only; does not run an analysis. */
export async function getEngineStatus() {
  const config = engineConfig("health");
  const body = await upstreamJson(config.url, {
    timeoutMs: 3000,
    prefix: "engine",
    invalidCode: "invalid_engine_status",
    maxBytes: 16000,
    init: { headers: { authorization: `Bearer ${config.token}` } },
  });
  const parsed = healthSchema.safeParse(body);
  if (!parsed.success)
    throw new ApiError(
      502,
      "invalid_engine_status",
      "The analysis engine returned an incompatible status.",
    );
  return { status: "reachable" as const, ...parsed.data };
}
