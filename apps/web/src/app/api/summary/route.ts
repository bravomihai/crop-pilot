import { NextResponse } from "next/server";
import { resultSchema } from "@croppilot/contracts";
import { apiRoute, ApiError, readJson } from "@/lib/server/http";
import { summarize, summaryConfigured } from "@/lib/server/summary";
export const runtime = "nodejs";

/** POST { result } → English-only AI summary of a computed result. */
export async function POST(req: Request) {
  return apiRoute("summary", async () => {
    if (!summaryConfigured())
      throw new ApiError(503, "summary_not_configured", "The AI summary is not set up on this server.");
    // The page sends a trimmed result (see summaryPayload); the gateway allows 256 KB here.
    const body = (await readJson(req, 256 * 1024)) as { result?: unknown; language?: unknown };
    if (body?.language !== undefined && body.language !== "en")
      throw new ApiError(400, "unsupported_language", "Summaries are available in English only.");
    const parsed = resultSchema.safeParse(body?.result);
    if (!parsed.success) throw new ApiError(400, "validation_error", "Send a complete result to summarise.");
    if (parsed.data.mode !== "computed" || !parsed.data.plans.length)
      throw new ApiError(400, "validation_error", "Only calculated results with plans can be summarised.");
    return NextResponse.json(await summarize(parsed.data, undefined, req.signal));
  });
}
