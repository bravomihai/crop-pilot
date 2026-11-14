import { NextResponse } from "next/server";
import { apiError } from "@/lib/http";
import { getAnalysis } from "@/lib/store";

type Ctx = { params: Promise<{ analysisId: string }> };

// GET /api/analyses/{analysisId} → { analysis_id, status, result?, error? }
export async function GET(_req: Request, { params }: Ctx) {
  const { analysisId } = await params;
  const rec = await getAnalysis(analysisId);
  return rec ? NextResponse.json(rec) : apiError(404, "not_found", `Analysis ${analysisId} not found`);
}
