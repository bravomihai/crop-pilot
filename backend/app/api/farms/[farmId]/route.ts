import { NextResponse } from "next/server";
import { apiError, readJson } from "@/lib/http";
import { getFarm, saveFarm } from "@/lib/store";
import type { FarmRequest } from "@/lib/types";

type Ctx = { params: Promise<{ farmId: string }> };

// GET /api/farms/{farmId} → FarmRequest
export async function GET(_req: Request, { params }: Ctx) {
  const { farmId } = await params;
  const farm = await getFarm(farmId);
  return farm ? NextResponse.json(farm) : apiError(404, "not_found", `Farm ${farmId} not found`);
}

// PUT /api/farms/{farmId}: FarmRequest → { farm_id }
export async function PUT(req: Request, { params }: Ctx) {
  const { farmId } = await params;
  if (!(await getFarm(farmId))) return apiError(404, "not_found", `Farm ${farmId} not found`);
  const farm = await readJson<FarmRequest>(req);
  if (!farm) return apiError(400, "validation_error", "Body must be a FarmRequest");
  await saveFarm({ ...farm, farm_id: farmId });
  return NextResponse.json({ farm_id: farmId });
}
