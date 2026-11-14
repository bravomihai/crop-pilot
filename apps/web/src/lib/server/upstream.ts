import "server-only";
import { ApiError } from "./http";

type Options = {
  timeoutMs: number;
  prefix: "engine" | "geocoding";
  invalidCode: string;
  maxBytes?: number;
  notReady?: boolean;
  /** Map an engine 422 (location/outline it cannot process) to a 422 for the farmer. */
  unsupported?: boolean;
  /** The caller's own cancellation (e.g. the browser closed the request). */
  signal?: AbortSignal;
  init?: RequestInit;
};

/** The deadline includes headers AND the full, size-bounded response body. */
export async function upstreamJson(
  url: URL,
  options: Options,
): Promise<unknown> {
  const deadline = AbortSignal.timeout(options.timeoutMs);
  const signal = options.signal
    ? AbortSignal.any([deadline, options.signal])
    : deadline;
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
    if (options.unsupported && response.status === 422)
      throw new ApiError(422, "unsupported_location", await unsupportedReason(response));
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
    if (options.signal?.aborted && !deadline.aborted)
      throw new ApiError(
        499,
        "request_cancelled",
        "The request was cancelled before the analysis finished.",
      );
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

/**
 * The engine's 422 reason is its own plain sentence (location outside Romania, or an
 * invalid field outline). Pass it on when it is a short plain string; schema-validation
 * details (objects) and anything unexpected get a generic message.
 */
async function unsupportedReason(response: Response): Promise<string> {
  const fallback = "Computed plans are currently available only for points inside Romania.";
  try {
    const text = await response.text();
    if (text.length > 2000) return fallback;
    const detail = (JSON.parse(text) as { detail?: unknown }).detail;
    return typeof detail === "string" && detail.length <= 300 && /^[\p{L}\p{N}\s.,;:()'’—-]+$/u.test(detail)
      ? detail
      : fallback;
  } catch {
    return fallback;
  }
}
