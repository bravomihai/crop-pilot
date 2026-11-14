import { NextResponse } from "next/server";
import { resultSchema } from "@fieldshift/contracts";
import { apiRoute, ApiError, readJson } from "@/lib/server/http";
import { summarize, summaryConfigured, type SummaryLanguage } from "@/lib/server/summary";
export const runtime = "nodejs";

/** POST { result, language: "en" | "ro" } → plain-language AI summary of a computed result. */
export async function POST(req: Request) {
  return apiRoute("summary", async () => {
    if (!summaryConfigured())
      throw new ApiError(503, "summary_not_configured", "The AI summary is not set up on this server.");
    const body = (await readJson(req, 2 * 1024 * 1024)) as { result?: unknown; language?: unknown };
    const parsed = resultSchema.safeParse(body?.result);
    if (!parsed.success) throw new ApiError(400, "validation_error", "Send a complete result to summarise.");
    if (parsed.data.mode !== "computed" || !parsed.data.plans.length)
      throw new ApiError(400, "validation_error", "Only calculated results with plans can be summarised.");
    const language: SummaryLanguage = body?.language === "ro" ? "ro" : "en";
    return NextResponse.json(await summarize(parsed.data, language, undefined, req.signal));
  });
}
