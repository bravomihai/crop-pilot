import type { RecommendationResult } from "@croppilot/contracts";

/**
 * The part of the result the summary uses (see summaryInput on the server). Past-season
 * replay, monthly climate and yearly climate rows are dropped: they are not summarised,
 * and without them the request stays small (the gateway allows 256 KB) and less data
 * reaches the AI provider. The result stays valid against the shared contract.
 */
export function summaryPayload(result: RecommendationResult): RecommendationResult {
  const strip = <T extends { replay?: unknown }>(plan: T): T => {
    const { replay: _replay, ...rest } = plan;
    return rest as T;
  };
  return {
    ...result,
    plans: result.plans.map(strip),
    ...(result.baseline ? { baseline: strip(result.baseline) } : {}),
    monthly_climate: [],
    ...(result.climate_context ? { climate_context: { ...result.climate_context, years: [] } } : {}),
  };
}
