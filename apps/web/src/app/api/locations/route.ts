import { NextResponse } from "next/server";
import { cacheKey, readCache, writeCache } from "@/lib/server/cache";
import { ApiError, errorResponse } from "@/lib/server/http";
export const runtime = "nodejs";
export async function GET(req: Request) {
  try {
    const q = new URL(req.url).searchParams.get("q")?.trim() ?? "";
    if (q.length < 2 || q.length > 100)
      throw new ApiError(
        400,
        "validation_error",
        "Introdu cel puțin două caractere pentru localitate.",
      );
    const key = cacheKey("geocoding", q.toLowerCase());
    const cached = await readCache(key);
    if (cached) return NextResponse.json(cached);
    const url = new URL("https://geocoding-api.open-meteo.com/v1/search");
    url.search = new URLSearchParams({
      name: q,
      count: "8",
      language: "ro",
      format: "json",
    }).toString();
    const response = await fetch(url, {
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    if (!response.ok)
      throw new ApiError(
        502,
        "geocoding_unavailable",
        "Căutarea localităților nu este disponibilă. Poți introduce coordonatele.",
      );
    const data = (await response.json()) as {
      results?: {
        id: number;
        name: string;
        admin1?: string;
        country?: string;
        latitude: number;
        longitude: number;
      }[];
    };
    const output = {
      locations: (data.results ?? []).map((r) => ({
        id: r.id,
        name: [r.name, r.admin1, r.country].filter(Boolean).join(", "),
        latitude: r.latitude,
        longitude: r.longitude,
      })),
      attribution: "Open-Meteo / GeoNames",
    };
    await writeCache(key, "geocoding", output, 86400 * 7);
    return NextResponse.json(output);
  } catch (error) {
    return errorResponse(error);
  }
}
