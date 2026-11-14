import exampleResult from "../../contracts/examples/analysis-result.example.json";
import type { Analysis, AnalysisResult, FarmRequest } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "";
const USE_EXAMPLE = import.meta.env.VITE_USE_EXAMPLE === "true";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
  return body as T;
}

export async function saveFarm(farm: FarmRequest): Promise<string> {
  if (USE_EXAMPLE) return "farm_demo_001";
  if (farm.farm_id) {
    await call(`/api/farms/${farm.farm_id}`, { method: "PUT", body: JSON.stringify(farm) });
    return farm.farm_id;
  }
  const { farm_id } = await call<{ farm_id: string }>("/api/farms", { method: "POST", body: JSON.stringify(farm) });
  return farm_id;
}

/** Runs an analysis. Handles both an inline result and a "running" status (polls until done). */
export async function analyze(
  farm_id: string,
  overrides: Pick<Partial<FarmRequest>, "priorities" | "scenario"> = {},
): Promise<AnalysisResult> {
  if (USE_EXAMPLE) return exampleResult as AnalysisResult;
  let analysis = await call<Analysis>("/api/analyses", {
    method: "POST",
    body: JSON.stringify({ farm_id, ...overrides }),
  });
  while (analysis.status === "running") {
    await new Promise((r) => setTimeout(r, 1500));
    analysis = await call<Analysis>(`/api/analyses/${analysis.analysis_id}`);
  }
  if (analysis.status === "failed" || !analysis.result) throw new Error(analysis.error ?? "Analysis failed");
  return analysis.result;
}

export async function getAnalysis(analysis_id: string): Promise<AnalysisResult> {
  if (USE_EXAMPLE) return exampleResult as AnalysisResult;
  const analysis = await call<Analysis>(`/api/analyses/${analysis_id}`);
  if (!analysis.result) throw new Error(analysis.error ?? "Analysis not ready");
  return analysis.result;
}
