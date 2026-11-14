import { analyze } from "./engine";
import { getFarm, newId, saveAnalysis } from "./store";
import type { AnalysisRecord, FarmRequest } from "./types";

export interface AnalysisOverrides {
  priorities?: FarmRequest["priorities"];
  scenario?: FarmRequest["scenario"];
}

/**
 * Runs an analysis inline (the engine should answer in seconds) and stores it.
 * Used by both the web API and the SMS webhook.
 * TODO(P5): if analyses get slow, start the engine call in the background
 * (e.g. SQS + worker) and return status "running"; the frontend already polls.
 */
export async function runAnalysis(farmId: string, overrides: AnalysisOverrides = {}): Promise<AnalysisRecord | null> {
  const saved = await getFarm(farmId);
  if (!saved) return null;

  const farm: FarmRequest = {
    ...saved,
    priorities: overrides.priorities ?? saved.priorities,
    scenario: overrides.scenario ?? saved.scenario,
  };

  const record: AnalysisRecord = { analysis_id: newId("an"), farm_id: farmId, status: "running" };
  try {
    const result = await analyze(farm);
    record.analysis_id = result.analysis_id ?? record.analysis_id;
    record.status = "done";
    record.result = result;
  } catch (e) {
    record.status = "failed";
    record.error = e instanceof Error ? e.message : String(e);
  }
  await saveAnalysis(record);
  return record;
}
