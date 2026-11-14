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
    console.warn("Public-data cache unavailable");
    return null;
  }
}
export async function writeCache(
  key: string,
  namespace: string,
  payload: unknown,
  ttlSeconds: number,
) {
  if (process.env.CACHE_ENABLED !== "true") return;
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
  } catch {
    console.warn("Public-data cache write unavailable");
  }
}
