import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, mock, test } from "node:test";
import { POST } from "../src/app/api/recommendations/route";
import { GET as locations } from "../src/app/api/locations/route";
import {
  PUT as cachePut,
  GET as cacheGet,
} from "../src/app/api/internal/cache/[key]/route";
import { DELETE as prune } from "../src/app/api/internal/cache/route";
import { readCache, writeCache, pruneCache } from "../src/lib/server/cache";

const input = JSON.parse(
  readFileSync(
    new URL(
      "../../../packages/contracts/examples/recommendation-request.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
const fixture = JSON.parse(
  readFileSync(
    new URL(
      "../../../packages/contracts/examples/recommendation-result.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
const envKeys = [
  "ENGINE_URL",
  "INTERNAL_API_TOKEN",
  "ENGINE_TIMEOUT_MS",
  "CACHE_ENABLED",
] as const;
const originalEnv = Object.fromEntries(
  envKeys.map((key) => [key, process.env[key]]),
);
const originalFetch = globalThis.fetch;
const originalInfo = console.info;
const token = "backend-test-secret-at-least-32-characters";
let fetchMock: ReturnType<typeof mock.fn<typeof fetch>>;
let infoMock: ReturnType<typeof mock.fn<typeof console.info>>;
let changeResult: (result: typeof fixture) => void;

beforeEach(() => {
  process.env.ENGINE_URL = "http://engine:8000";
  process.env.INTERNAL_API_TOKEN = token;
  process.env.ENGINE_TIMEOUT_MS = "1000";
  process.env.CACHE_ENABLED = "false";
  changeResult = () => {};
  fetchMock = mock.fn<typeof fetch>(async (_url, options) => {
    const result = structuredClone(fixture);
    result.request_id = new Headers(options?.headers).get("x-request-id");
    result.location = structuredClone(input.location);
    changeResult(result);
    return Response.json(result);
  });
  globalThis.fetch = fetchMock;
  infoMock = mock.fn<typeof console.info>();
  console.info = infoMock;
});
afterEach(() => {
  globalThis.fetch = originalFetch;
  console.info = originalInfo;
  for (const key of envKeys) {
    if (originalEnv[key] === undefined) delete process.env[key];
    else process.env[key] = originalEnv[key];
  }
});

function request(value: unknown = input) {
  return new Request("http://web/api/recommendations", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(value),
  });
}
async function check(response: Response, status: number, code?: string) {
  assert.equal(response.status, status);
  assert.equal(response.headers.get("cache-control"), "no-store");
  const id = response.headers.get("x-request-id");
  assert.match(id ?? "", /^[a-f0-9-]{36}$/);
  const body = await response.json();
  if (code) {
    assert.equal(body.code, code);
    assert.equal(body.request_id, id);
  }
  assert.ok(!JSON.stringify(body).includes(token));
  return body;
}

test("recommendations propagate the ID and keep logs free of form values and secrets", async () => {
  const body = await check(await POST(request()), 200);
  const [, options] = fetchMock.mock.calls[0].arguments;
  assert.equal(
    body.request_id,
    new Headers(options?.headers).get("x-request-id"),
  );
  assert.equal(
    new Headers(options?.headers).get("authorization"),
    `Bearer ${token}`,
  );
  assert.equal(options?.redirect, "error");
  const log = JSON.parse(String(infoMock.mock.calls[0].arguments[0]));
  assert.equal(log.request_id, body.request_id);
  assert.equal(log.operation, "recommendations");
  assert.equal(log.status, 200);
  assert.equal(typeof log.duration_ms, "number");
  assert.deepEqual(
    Object.keys(log).sort(),
    ["event", "operation", "request_id", "status", "duration_ms"].sort(),
  );
});

for (const [label, value] of [
  ["missing fields", {}],
  [
    "zero priorities",
    { ...input, priorities: { water: 0, soil: 0, climate: 0 } },
  ],
]) {
  test(`rejects ${label} before contacting Python`, async () => {
    await check(await POST(request(value)), 400, "validation_error");
    assert.equal(fetchMock.mock.callCount(), 0);
  });
}

test("malformed JSON is 400", async () => {
  await check(
    await POST(
      new Request("http://web/api/recommendations", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{",
      }),
    ),
    400,
    "invalid_json",
  );
});
test("non-JSON input is 415", async () => {
  await check(
    await POST(
      new Request("http://web/api/recommendations", {
        method: "POST",
        body: "form",
      }),
    ),
    415,
    "unsupported_media_type",
  );
});
test("oversized streamed input is 413 even without Content-Length", async () => {
  const response = await POST(
    new Request("http://web/api/recommendations", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify("x".repeat(33000)),
    }),
  );
  await check(response, 413, "request_too_large");
  assert.equal(fetchMock.mock.callCount(), 0);
});

for (const timeout of ["NaN", "0", "-1", "100000", "1.5"]) {
  test(`invalid timeout configuration ${timeout} is 503`, async () => {
    process.env.ENGINE_TIMEOUT_MS = timeout;
    await check(await POST(request()), 503, "engine_not_configured");
    assert.equal(fetchMock.mock.callCount(), 0);
  });
}

test("network failures are 502 and logged with safe error codes", async () => {
  fetchMock.mock.mockImplementation(async () => {
    throw new Error(token);
  });
  await check(await POST(request()), 502, "engine_unavailable");
  const log = JSON.stringify(infoMock.mock.calls);
  assert.ok(log.includes("engine_unavailable"));
  assert.ok(!log.includes(token));
});
test("engine timeout is 504", async () => {
  fetchMock.mock.mockImplementation(async () => {
    throw new DOMException("timeout", "TimeoutError");
  });
  await check(await POST(request()), 504, "engine_timeout");
});
test("timeout while streaming the engine body is 504", async () => {
  fetchMock.mock.mockImplementation(
    async () =>
      new Response(
        new ReadableStream({
          start(controller) {
            controller.error(new DOMException("timeout", "TimeoutError"));
          },
        }),
      ),
  );
  await check(await POST(request()), 504, "engine_timeout");
});
test("unimplemented computed mode remains 503 without fallback", async () => {
  fetchMock.mock.mockImplementation(
    async () => new Response(null, { status: 503 }),
  );
  await check(await POST(request()), 503, "engine_not_ready");
  assert.equal(fetchMock.mock.callCount(), 1);
});
test("engine 422 for an unsupported location is a 422, not 'unavailable'", async () => {
  fetchMock.mock.mockImplementation(async () =>
    Response.json(
      { detail: "The computed crop-screening model currently supports locations inside Romania." },
      { status: 422 },
    ),
  );
  const body = await check(await POST(request()), 422, "unsupported_location");
  assert.equal(body.error, "The computed crop-screening model currently supports locations inside Romania.");
});
test("engine 422 with a structured or odd detail falls back to a generic message", async () => {
  for (const detail of [{ code: "validation_error", errors: ["x"] }, "<script>alert(1)</script>", "x".repeat(400)]) {
    fetchMock.mock.mockImplementation(async () => Response.json({ detail }, { status: 422 }));
    const body = await check(await POST(request()), 422, "unsupported_location");
    assert.equal(body.error, "Computed plans are currently available only for points inside Romania.");
  }
});
test("browser cancellation aborts the engine call instead of waiting for it", async () => {
  let engineSignal: AbortSignal | undefined;
  fetchMock.mock.mockImplementation(
    (_url, options) =>
      new Promise<Response>((_resolve, reject) => {
        engineSignal = options?.signal ?? undefined;
        engineSignal?.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      }),
  );
  const browser = new AbortController();
  const pending = POST(
    new Request("http://web/api/recommendations", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
      signal: browser.signal,
    }),
  );
  await new Promise((resolve) => setTimeout(resolve, 20));
  browser.abort();
  await check(await pending, 499, "request_cancelled");
  assert.equal(engineSignal?.aborted, true);
});
test("invalid upstream JSON is 502", async () => {
  fetchMock.mock.mockImplementation(async () => new Response("not json"));
  await check(await POST(request()), 502, "invalid_engine_result");
});
test("oversized upstream result is rejected", async () => {
  fetchMock.mock.mockImplementation(
    async () => new Response("x".repeat(2_000_001)),
  );
  await check(await POST(request()), 502, "invalid_engine_result");
});
for (const [label, mutate] of [
  [
    "wrong request ID",
    (r: typeof fixture) => {
      r.request_id = "wrong";
    },
  ],
  [
    "wrong location",
    (r: typeof fixture) => {
      r.location.latitude = -70;
    },
  ],
  [
    "incomplete result",
    (r: typeof fixture) => {
      r.plans = [];
    },
  ],
  [
    "overlapping calendar",
    (r: typeof fixture) => {
      r.plans[0].steps[1].sowing_window.start =
        r.plans[0].steps[0].harvest_window.start;
    },
  ],
  [
    "sowing before availability",
    (r: typeof fixture) => {
      r.plans[0].steps[0].sowing_window.start = "2000-01-01";
    },
  ],
] as const) {
  test(`rejects ${label}`, async () => {
    changeResult = mutate;
    await check(await POST(request()), 502, "invalid_engine_result");
  });
}
test("rejects excluded crops returned by engine", async () => {
  const value = structuredClone(input);
  value.constraints.excluded_crops = [fixture.plans[0].steps[0].crop_id];
  await check(await POST(request(value)), 502, "invalid_engine_result");
});
for (const count of [0, 1, 2, 3]) {
  test(`accepts computed contract with ${count} valid plans`, async () => {
    changeResult = (r) => {
      r.mode = "computed";
      r.plans = r.plans.slice(0, count);
      r.status =
        count === 3
          ? "complete"
          : count === 0
            ? "insufficient_data"
            : "limited";
    };
    const body = await check(await POST(request()), 200);
    assert.equal(body.mode, "computed");
    assert.equal(body.plans.length, count);
  });
}

const locationRequest = () =>
  new Request("http://web/api/locations?q=Lehliu");
test("geocoding requests English labels and preserves attribution", async () => {
  fetchMock.mock.mockImplementation(async () =>
    Response.json({
      results: [{
        id: 1,
        name: "Lehliu",
        admin1: "Calarasi",
        country: "Romania",
        latitude: 44.4,
        longitude: 26.5,
      }],
    }),
  );
  const body = await check(await locations(locationRequest()), 200);
  assert.equal(body.locations[0].name, "Lehliu, Calarasi, Romania");
  const [providerUrl] = fetchMock.mock.calls[0].arguments;
  assert.equal(new URL(String(providerUrl)).searchParams.get("language"), "en");
  assert.equal(body.attribution, "Open-Meteo / GeoNames");
  const [url] = fetchMock.mock.calls[0].arguments;
  assert.equal(new URL(String(url)).searchParams.get("countryCode"), "RO");
});
test("no geocoding matches is a valid empty result", async () => {
  fetchMock.mock.mockImplementation(async () =>
    Response.json({ generationtime_ms: 0.2 }),
  );
  const body = await check(await locations(locationRequest()), 200);
  assert.deepEqual(body.locations, []);
});
for (const bad of [
  null,
  { results: "invalid" },
  { error: true, reason: "upstream failure" },
  { results: [{ id: 1, name: "bad", latitude: 100, longitude: 3 }] },
]) {
  test(`malformed geocoding response ${JSON.stringify(bad)} is 502`, async () => {
    fetchMock.mock.mockImplementation(async () => Response.json(bad));
    await check(
      await locations(locationRequest()),
      502,
      "invalid_geocoding_result",
    );
  });
}
test("geocoding timeout is 504", async () => {
  fetchMock.mock.mockImplementation(async () => {
    throw new DOMException("timeout", "TimeoutError");
  });
  await check(await locations(locationRequest()), 504, "geocoding_timeout");
});
test("invalid location search does not contact provider", async () => {
  await check(
    await locations(new Request("http://web/api/locations?q=x")),
    400,
    "validation_error",
  );
  assert.equal(fetchMock.mock.callCount(), 0);
});

test("disabled cache does not touch the database", async () => {
  assert.equal(await readCache("test"), null);
  assert.equal(await writeCache("test", "test", {}, 30), false);
  assert.equal(await pruneCache(), 0);
});
const keyContext = {
  params: Promise.resolve({ key: "environment:" + "a".repeat(64) }),
};
for (const [name, fn] of [
  ["read", cacheGet],
  ["write", cachePut],
] as const) {
  test(`internal cache ${name} requires bearer authentication`, async () => {
    await check(
      await fn(new Request("http://web/api/internal/cache/test"), keyContext),
      401,
      "unauthorized",
    );
  });
}
test("raw secret without Bearer prefix is refused", async () => {
  await check(
    await cacheGet(
      new Request("http://web/api/internal/cache/test", {
        headers: { authorization: token },
      }),
      keyContext,
    ),
    401,
    "unauthorized",
  );
});
test("cleanup requires authentication", async () => {
  await check(
    await prune(
      new Request("http://web/api/internal/cache", { method: "DELETE" }),
    ),
    401,
    "unauthorized",
  );
});
test("cache write does not claim success when disabled", async () => {
  await check(
    await cachePut(
      new Request("http://web/api/internal/cache/test", {
        method: "PUT",
        headers: {
          authorization: `Bearer ${token}`,
          "content-type": "application/json",
        },
        body: "{}",
      }),
      keyContext,
    ),
    503,
    "cache_unavailable",
  );
});

test("real fetch deadline also aborts a stalled response body", async (t) => {
  const server = createServer((_req, response) => {
    response.writeHead(200, { "content-type": "application/json" });
    response.write('{"schema_version":"1.0",');
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(async () => {
    server.closeAllConnections();
    await new Promise<void>((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
  });
  globalThis.fetch = originalFetch;
  process.env.ENGINE_URL = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  process.env.ENGINE_TIMEOUT_MS = "100";
  const started = performance.now();
  await check(await POST(request()), 504, "engine_timeout");
  assert.ok(performance.now() - started < 2000);
});
