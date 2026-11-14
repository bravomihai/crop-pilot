// Calls the Python engine (contracts/api.md, "Internal API").
// Without ENGINE_URL it returns the contract example, so the frontend can integrate early.
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { AnalysisResult, FarmRequest } from "./types";
import { newId } from "./store";

const ENGINE_URL = process.env.ENGINE_URL;
const CONTRACTS_DIR = process.env.CONTRACTS_DIR ?? path.join(process.cwd(), "..", "contracts");
const TIMEOUT_MS = 60_000;

export class EngineError extends Error {
  constructor(message: string, public status = 502, public code = "engine_error") {
    super(message);
  }
}

export async function analyze(farm: FarmRequest): Promise<AnalysisResult> {
  if (!ENGINE_URL) return mockAnalyze(farm);

  const res = await fetch(`${ENGINE_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(farm),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  const body = await res.json().catch(() => ({}));
  if (res.status === 422) throw new EngineError(JSON.stringify(body.detail ?? body), 400, "validation_error");
  if (!res.ok) throw new EngineError(`Engine returned ${res.status}`);
  return body as AnalysisResult;
}

async function mockAnalyze(farm: FarmRequest): Promise<AnalysisResult> {
  const file = path.join(CONTRACTS_DIR, "examples", "analysis-result.example.json");
  const example = JSON.parse(await readFile(file, "utf-8")) as AnalysisResult;
  return { ...example, analysis_id: newId("an"), farm_id: farm.farm_id ?? example.farm_id, created_at: new Date().toISOString() };
}
