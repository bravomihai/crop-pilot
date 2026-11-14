import { NextResponse } from "next/server";

export type ErrorCode = "validation_error" | "not_found" | "engine_error" | "data_unavailable";

export function apiError(status: number, code: ErrorCode, error: string) {
  return NextResponse.json({ error, code }, { status });
}

export async function readJson<T>(req: Request): Promise<T | null> {
  try {
    return (await req.json()) as T;
  } catch {
    return null;
  }
}
