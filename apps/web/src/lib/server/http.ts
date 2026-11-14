import "server-only";
import { NextResponse } from "next/server";
import { timingSafeEqual } from "node:crypto";
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export function errorResponse(error: unknown, requestId?: string) {
  const known = error instanceof ApiError;
  return NextResponse.json(
    {
      code: known ? error.code : "internal_error",
      error: known ? error.message : "The request could not be processed.",
      request_id: requestId,
    },
    { status: known ? error.status : 500 },
  );
}
export async function readJson(
  req: Request,
  maxBytes = 32768,
): Promise<unknown> {
  const reader = req.body?.getReader();
  if (!reader) throw new ApiError(400, "invalid_json", "The request body is missing.");
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        throw new ApiError(
          413,
          "request_too_large",
          "The request body is too large.",
        );
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new ApiError(400, "invalid_json", "The request body is not valid JSON.");
  }
}
export function requireInternalToken(req: Request) {
  const expected = process.env.INTERNAL_API_TOKEN;
  if (!expected || expected.length < 32)
    throw new ApiError(
      503,
      "not_configured",
      "The internal integration is not configured.",
    );
  const supplied =
    req.headers.get("authorization")?.replace(/^Bearer /, "") ?? "";
  if (
    Buffer.byteLength(supplied) !== Buffer.byteLength(expected) ||
    !timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))
  )
    throw new ApiError(401, "unauthorized", "Internal access denied.");
}
