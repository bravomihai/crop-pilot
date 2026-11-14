import { NextResponse } from "next/server";
import { findLocations } from "@/lib/server/locations";
import { apiRoute } from "@/lib/server/http";

export const runtime = "nodejs";

export async function GET(req: Request) {
  return apiRoute("locations", async () =>
    NextResponse.json(
      await findLocations(new URL(req.url).searchParams.get("q") ?? ""),
    ),
  );
}
