import { NextResponse } from "next/server";
import { apiError, readJson } from "@/lib/http";
import { saveFarm } from "@/lib/store";
import type { FarmRequest } from "@/lib/types";

// POST /api/farms: FarmRequest (without farm_id) → 201 { farm_id }
export async function POST(req: Request) {
  const farm = await readJson<FarmRequest>(req);
  if (!farm || !Array.isArray(farm.current_rotation) || !farm.priorities || !farm.scenario) {
    return apiError(400, "validation_error", "Body must be a FarmRequest (see contracts/schemas/farm-request.schema.json)");
  }
  // Full schema validation happens in the engine on /analyze.
  const { farm_id: _ignored, ...rest } = farm;
  const farm_id = await saveFarm(rest as FarmRequest);
  return NextResponse.json({ farm_id }, { status: 201 });
}
