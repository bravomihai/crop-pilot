import { NextResponse } from "next/server";
import { pruneCache } from "@/lib/server/cache";
import { ApiError, apiRoute, requireInternalToken } from "@/lib/server/http";
export const runtime = "nodejs";
export async function DELETE(req: Request) {
  return apiRoute("cache_prune", async () => {
    requireInternalToken(req);
    const deleted = await pruneCache();
    if (deleted === null)
      throw new ApiError(
        503,
        "cache_unavailable",
        "The public-data cache is unavailable.",
      );
    return NextResponse.json({ deleted, batch_size: 1000 });
  });
}
