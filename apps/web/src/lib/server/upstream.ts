import "server-only";
import { ApiError } from "./http";

type Options = {
  timeoutMs: number;
  prefix: "engine" | "geocoding";
  invalidCode: string;
  maxBytes?: number;
  notReady?: boolean;
  init?: RequestInit;
};

/** The deadline includes headers AND the full, size-bounded response body. */
export async function upstreamJson(
  url: URL,
  options: Options,
): Promise<unknown> {
  const signal = AbortSignal.timeout(options.timeoutMs);
  try {
    const response = await fetch(url, {
      ...options.init,
      signal,
      cache: "no-store",
      redirect: "error",
    });
    if (options.notReady && response.status === 503)
      throw new ApiError(
        503,
        "engine_not_ready",
        "The analysis engine is not ready.",
      );
    if (!response.ok)
      throw new ApiError(
        502,
        `${options.prefix}_unavailable`,
        "The external service is unavailable.",
      );
    const reader = response.body?.getReader();
    if (!reader)
      throw new ApiError(
        502,
        options.invalidCode,
        "The external service returned an invalid response.",
      );
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > (options.maxBytes ?? 2_000_000)) {
          await reader.cancel();
          throw new ApiError(
            502,
            options.invalidCode,
            "The external response is too large.",
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
        502,
        options.invalidCode,
        "The external service returned invalid JSON.",
      );
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (
      signal.aborted ||
      (error instanceof Error &&
        ["TimeoutError", "AbortError"].includes(error.name))
    )
      throw new ApiError(
        504,
        `${options.prefix}_timeout`,
        "The external service did not respond in time.",
      );
    throw new ApiError(
      502,
      `${options.prefix}_unavailable`,
      "The external service is unavailable.",
    );
  }
}

export function engineConfig(path: string) {
  const base = process.env.ENGINE_URL;
  const token = process.env.INTERNAL_API_TOKEN;
  const timeoutMs = Number(process.env.ENGINE_TIMEOUT_MS ?? 90000);
  try {
    if (
      !base ||
      !token ||
      token.length < 32 ||
      !Number.isSafeInteger(timeoutMs) ||
      timeoutMs < 100 ||
      timeoutMs > 90000
    )
      throw new Error();
    const url = new URL(`${base.replace(/\/+$/, "")}/${path}`);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    )
      throw new Error();
    return { url, token, timeoutMs };
  } catch {
    throw new ApiError(
      503,
      "engine_not_configured",
      "The analysis engine configuration is invalid.",
    );
  }
}
