import { NextResponse } from "next/server";
import { recommend } from "@/lib/server/engine";
import { apiRoute, readJson } from "@/lib/server/http";
export const runtime = "nodejs";
export async function POST(req: Request) {
  return apiRoute("recommendations", async (requestId) =>
    NextResponse.json(await recommend(await readJson(req), requestId, req.signal)),
  );
}
