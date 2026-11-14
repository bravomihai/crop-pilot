import { NextResponse } from "next/server";
import { runAnalysis, type AnalysisOverrides } from "@/lib/analyses";
import { apiError, readJson } from "@/lib/http";

// POST /api/analyses: { farm_id, priorities?, scenario? }
// → 200 { analysis_id, status: "done", result } (inline) or 202 { analysis_id, status: "running" }
export async function POST(req: Request) {
  const body = await readJson<{ farm_id?: string } & AnalysisOverrides>(req);
  if (!body?.farm_id) return apiError(400, "validation_error", "farm_id is required");

  const rec = await runAnalysis(body.farm_id, { priorities: body.priorities, scenario: body.scenario });
  if (!rec) return apiError(404, "not_found", `Farm ${body.farm_id} not found`);
  if (rec.status === "failed") return apiError(502, "engine_error", rec.error ?? "Analysis failed");
  return NextResponse.json(rec, { status: rec.status === "running" ? 202 : 200 });
}
