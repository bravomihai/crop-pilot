import { NextResponse } from "next/server";
import { CONTRACT_VERSION } from "@croppilot/contracts";
import { apiRoute } from "@/lib/server/http";
export const dynamic = "force-dynamic";
export async function GET() {
  return apiRoute("health", async () =>
    NextResponse.json({
      service: "croppilot-web",
      revision: process.env.DEPLOYMENT_SHA ?? null,
      contract_version: CONTRACT_VERSION,
      cache_enabled: process.env.CACHE_ENABLED === "true",
    }),
  );
}
