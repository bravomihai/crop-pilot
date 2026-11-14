import { NextResponse } from "next/server";
import { readCache, writeCache } from "@/lib/server/cache";
import {
  ApiError,
  readJson,
  errorResponse,
  requireInternalToken,
} from "@/lib/server/http";
export const runtime = "nodejs";
type Context = { params: Promise<{ key: string }> };
async function keyFor(ctx: Context) {
  const { key } = await ctx.params;
  if (!/^environment:[a-f0-9]{64}$/.test(key))
    throw new ApiError(400, "invalid_key", "Cheie cache invalidă.");
  return key;
}
export async function GET(req: Request, ctx: Context) {
  try {
    requireInternalToken(req);
    const value = await readCache(await keyFor(ctx));
    return value
      ? NextResponse.json(value)
      : new Response(null, { status: 404 });
  } catch (error) {
    return errorResponse(error);
  }
}
export async function PUT(req: Request, ctx: Context) {
  try {
    requireInternalToken(req);
    const key = await keyFor(ctx);
    await writeCache(
      key,
      "environment",
      await readJson(req, 2_000_000),
      86400 * 30,
    );
    return new Response(null, { status: 204 });
  } catch (error) {
    return errorResponse(error);
  }
}
