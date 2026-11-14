import "server-only";
import { z } from "zod";
import { cacheKey, readCache, writeCache } from "./cache";
import { ApiError } from "./http";
import { upstreamJson } from "./upstream";

const coordinate = {
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
};
const providerSchema = z.object({
  results: z
    .array(
      z.object({
        id: z.number().int(),
        name: z.string().min(1),
        admin1: z.string().optional(),
        country: z.string().optional(),
        ...coordinate,
      }),
    )
    .max(100)
    .optional(),
  error: z.literal(false).optional(),
});
const outputSchema = z.object({
  locations: z
    .array(
      z.object({
        id: z.number().int(),
        name: z.string().min(1),
        ...coordinate,
      }),
    )
    .max(100),
  attribution: z.literal("Open-Meteo / GeoNames"),
});

export async function findLocations(query: string) {
  const q = query.trim();
  if (q.length < 2 || q.length > 100)
    throw new ApiError(
      400,
      "validation_error",
      "Enter between 2 and 100 characters for the location.",
    );
  const key = cacheKey("geocoding", q.toLowerCase());
  const cached = outputSchema.safeParse(await readCache(key));
  if (cached.success) return cached.data;
  const url = new URL("https://geocoding-api.open-meteo.com/v1/search");
  url.search = new URLSearchParams({
    name: q,
    count: "8",
    language: "ro",
    format: "json",
  }).toString();
  const data = providerSchema.safeParse(
    await upstreamJson(url, {
      timeoutMs: 10000,
      prefix: "geocoding",
      invalidCode: "invalid_geocoding_result",
      maxBytes: 128_000,
    }),
  );
  if (!data.success)
    throw new ApiError(
      502,
      "invalid_geocoding_result",
      "The location service returned an invalid response.",
    );
  const output = {
    locations: (data.data.results ?? []).map((r) => ({
      id: r.id,
      name: [r.name, r.admin1, r.country].filter(Boolean).join(", "),
      latitude: r.latitude,
      longitude: r.longitude,
    })),
    attribution: "Open-Meteo / GeoNames" as const,
  };
  await writeCache(key, "geocoding", output, 86400 * 7);
  return output;
}
