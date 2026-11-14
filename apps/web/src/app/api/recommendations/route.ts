import { NextResponse } from "next/server";
import { randomUUID } from "node:crypto";
import { recommend } from "@/lib/server/engine";
import { readJson, errorResponse } from "@/lib/server/http";
export const runtime = "nodejs";
export async function POST(req: Request) {
  const requestId = randomUUID();
  try {
    return NextResponse.json(await recommend(await readJson(req), requestId), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    return errorResponse(error, requestId);
  }
}
