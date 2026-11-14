import { NextResponse } from "next/server";
import { getEngineStatus } from "@/lib/server/engine-status";
import { apiRoute } from "@/lib/server/http";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function GET() {
  return apiRoute("engine_status", async (requestId) =>
    NextResponse.json({ ...(await getEngineStatus()), request_id: requestId }),
  );
}
