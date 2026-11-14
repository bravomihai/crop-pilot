import "server-only";
import { NextResponse } from "next/server";
import { randomUUID, timingSafeEqual } from "node:crypto";

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

/** Static operation names only: never log URLs, payloads, headers or error messages. */
export async function apiRoute(
  operation: string,
  action: (requestId: string) => Promise<Response>,
) {
  const requestId = randomUUID();
  const started = performance.now();
  let response: Response;
  let code: string | undefined;
  try {
    response = await action(requestId);
  } catch (error) {
    code = error instanceof ApiError ? error.code : "internal_error";
    response = errorResponse(error, requestId);
  }
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("X-Request-ID", requestId);
  console.info(
    JSON.stringify({
      event: "api_request",
      operation,
      request_id: requestId,
      status: response.status,
      code,
      duration_ms: Math.round(performance.now() - started),
    }),
  );
  return response;
}

export async function readJson(
  req: Request,
  maxBytes = 32768,
): Promise<unknown> {
  const contentType = req.headers
    .get("content-type")
    ?.split(";")[0]
    .trim()
    .toLowerCase();
  if (contentType !== "application/json")
    throw new ApiError(415, "unsupported_media_type", "Use application/json.");
  const length = req.headers.get("content-length");
  if (length && Number(length) > maxBytes)
    throw new ApiError(
      413,
      "request_too_large",
      "The request body is too large.",
    );
  const reader = req.body?.getReader();
  if (!reader)
    throw new ApiError(400, "invalid_json", "The request body is missing.");
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
    throw new ApiError(
      400,
      "invalid_json",
      "The request body is not valid JSON.",
    );
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
  const header = req.headers.get("authorization") ?? "";
  const supplied = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (
    Buffer.byteLength(supplied) !== Buffer.byteLength(expected) ||
    !timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))
  )
    throw new ApiError(401, "unauthorized", "Internal access denied.");
}
