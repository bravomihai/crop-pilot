import { NextResponse } from "next/server";
import { CONTRACT_VERSION } from "@fieldshift/contracts";
import { apiRoute } from "@/lib/server/http";
export const dynamic = "force-dynamic";
export async function GET() {
  return apiRoute("health", async () =>
    NextResponse.json({
      service: "fieldshift-web",
      contract_version: CONTRACT_VERSION,
      cache_enabled: process.env.CACHE_ENABLED === "true",
    }),
  );
}
