import "server-only";
import { createHash } from "node:crypto";
import { db } from "./db";
import type { Prisma } from "@/generated/prisma/client";
export const cacheKey = (namespace: string, value: unknown) =>
  `${namespace}:${createHash("sha256").update(JSON.stringify(value)).digest("hex")}`;

export async function readCache(key: string): Promise<unknown | null> {
  if (process.env.CACHE_ENABLED !== "true") return null;
  try {
    const entry = await db().dataCache.findUnique({ where: { key } });
    return entry && entry.expiresAt > new Date() ? entry.payload : null;
  } catch {
    console.warn(
      JSON.stringify({ event: "cache_unavailable", operation: "read" }),
    );
    return null;
  }
}

export async function writeCache(
  key: string,
  namespace: string,
  payload: unknown,
  ttlSeconds: number,
): Promise<boolean> {
  if (process.env.CACHE_ENABLED !== "true") return false;
  try {
    const data = {
      namespace,
      payload: payload as Prisma.InputJsonValue,
      expiresAt: new Date(Date.now() + ttlSeconds * 1000),
    };
    await db().dataCache.upsert({
      where: { key },
      create: { key, ...data },
      update: data,
    });
    return true;
  } catch {
    console.warn(
      JSON.stringify({ event: "cache_unavailable", operation: "write" }),
    );
    return false;
  }
}

/** Bounded batch: repeated calls drain expired public data without long table locks. */
export async function pruneCache(): Promise<number | null> {
  if (process.env.CACHE_ENABLED !== "true") return 0;
  try {
    return await db().$executeRaw`
      DELETE FROM "DataCache" WHERE "key" IN (
        SELECT "key" FROM "DataCache" WHERE "expiresAt" <= NOW()
        ORDER BY "expiresAt" LIMIT 1000
      )`;
  } catch {
    console.warn(
      JSON.stringify({ event: "cache_unavailable", operation: "prune" }),
    );
    return null;
  }
}
