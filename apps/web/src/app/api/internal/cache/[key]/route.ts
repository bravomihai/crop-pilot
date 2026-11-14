import { NextResponse } from "next/server";
import { readCache, writeCache } from "@/lib/server/cache";
import {
  ApiError,
  apiRoute,
  readJson,
  requireInternalToken,
} from "@/lib/server/http";
export const runtime = "nodejs";
type Context = { params: Promise<{ key: string }> };
async function keyFor(ctx: Context) {
  const { key } = await ctx.params;
  if (!/^environment:[a-f0-9]{64}$/.test(key))
    throw new ApiError(400, "invalid_key", "Invalid cache key.");
  return key;
}
export async function GET(req: Request, ctx: Context) {
  return apiRoute("cache_read", async () => {
    requireInternalToken(req);
    const value = await readCache(await keyFor(ctx));
    return value !== null
      ? NextResponse.json(value)
      : new Response(null, { status: 404 });
  });
}
export async function PUT(req: Request, ctx: Context) {
  return apiRoute("cache_write", async () => {
    requireInternalToken(req);
    const key = await keyFor(ctx);
    const value = await readJson(req, 2_000_000);
    if (value === null || typeof value !== "object" || Array.isArray(value))
      throw new ApiError(
        400,
        "invalid_cache_value",
        "Cache entries must be JSON objects containing public data.",
      );
    const stored = await writeCache(key, "environment", value, 86400 * 30);
    if (!stored)
      throw new ApiError(
        503,
        "cache_unavailable",
        "The public-data cache is unavailable or disabled.",
      );
    return new Response(null, { status: 204 });
  });
}
