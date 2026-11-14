import { NextResponse } from "next/server";
export function GET() {
  return NextResponse.json({
    service: "fieldshift-web",
    contract_version: "1.0",
    cache_enabled: process.env.CACHE_ENABLED === "true",
  });
}
