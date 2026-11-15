import assert from "node:assert/strict";
import { afterEach, beforeEach, mock, test } from "node:test";
import { GET } from "../src/app/api/engine/status/route";

const originalFetch = globalThis.fetch;
const originalUrl = process.env.ENGINE_URL;
const originalToken = process.env.INTERNAL_API_TOKEN;
const originalTimeout = process.env.ENGINE_TIMEOUT_MS;
const token = "test-internal-token-with-at-least-32-characters";
const health = {
  service: "croppilot-engine",
  contract_version: "1.0",
  mode: "demo",
};
let fetchMock: ReturnType<typeof mock.fn<typeof fetch>>;

beforeEach(() => {
  process.env.ENGINE_URL = "http://engine:8000/";
  process.env.INTERNAL_API_TOKEN = token;
  process.env.ENGINE_TIMEOUT_MS = "1000";
  fetchMock = mock.fn<typeof fetch>(async () => Response.json(health));
  globalThis.fetch = fetchMock;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalTimeout === undefined) delete process.env.ENGINE_TIMEOUT_MS;
  else process.env.ENGINE_TIMEOUT_MS = originalTimeout;
  if (originalUrl === undefined) delete process.env.ENGINE_URL;
  else process.env.ENGINE_URL = originalUrl;
  if (originalToken === undefined) delete process.env.INTERNAL_API_TOKEN;
  else process.env.INTERNAL_API_TOKEN = originalToken;
});

async function result(status: number, code?: string) {
  const response = await GET();
  const body = await response.json();
  assert.equal(response.status, status);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-request-id"), body.request_id);
  assert.match(body.request_id, /^[0-9a-f-]{36}$/);
  if (code) assert.equal(body.code, code);
  assert.ok(!JSON.stringify(body).includes(token));
  assert.ok(!JSON.stringify(body).includes("http://engine"));
  return body;
}

test("reports demo connectivity and sends only a bounded health request", async () => {
  const body = await result(200);
  assert.equal(body.status, "reachable");
  assert.equal(body.mode, "demo");
  assert.equal(body.contract_version, "1.0");
  assert.equal(fetchMock.mock.callCount(), 1);
  const [url, options] = fetchMock.mock.calls[0].arguments;
  assert.equal(String(url), "http://engine:8000/health");
  assert.equal(
    new Headers(options?.headers).get("authorization"),
    `Bearer ${token}`,
  );
  assert.equal(options?.cache, "no-store");
  assert.equal(options?.redirect, "error");
  assert.ok(options?.signal instanceof AbortSignal);
});

test("computed describes configuration without claiming scientific readiness", async () => {
  fetchMock.mock.mockImplementation(async () =>
    Response.json({ ...health, mode: "computed" }),
  );
  const body = await result(200);
  assert.equal(body.mode, "computed");
  assert.equal(body.status, "reachable");
  assert.equal(body.ready, undefined);
});

for (const [name, url, secret] of [
  ["missing URL", undefined, token],
  ["missing token", "http://engine:8000", undefined],
  ["short token", "http://engine:8000", "short"],
  ["invalid URL", "invalid", token],
  ["unsupported protocol", "file:///private", token],
  ["embedded credentials", "http://user:password@engine:8000", token],
] as const) {
  test(`rejects ${name} without contacting the engine`, async () => {
    if (url === undefined) delete process.env.ENGINE_URL;
    else process.env.ENGINE_URL = url;
    if (secret === undefined) delete process.env.INTERNAL_API_TOKEN;
    else process.env.INTERNAL_API_TOKEN = secret;
    await result(503, "engine_not_configured");
    assert.equal(fetchMock.mock.callCount(), 0);
  });
}

test("connection failures do not expose internal errors", async () => {
  fetchMock.mock.mockImplementation(async () => {
    throw new Error(`connection failed: ${token}`);
  });
  await result(502, "engine_unavailable");
});

test("timeouts have a distinct error", async () => {
  fetchMock.mock.mockImplementation(async () => {
    throw new DOMException("timed out", "TimeoutError");
  });
  await result(504, "engine_timeout");
});

test("timeouts while reading the response body are handled", async () => {
  fetchMock.mock.mockImplementation(async () => {
    return new Response(
      new ReadableStream({
        start(controller) {
          controller.error(new DOMException("timed out", "TimeoutError"));
        },
      }),
    );
  });
  await result(504, "engine_timeout");
});

test("unhealthy HTTP responses are unavailable", async () => {
  fetchMock.mock.mockImplementation(
    async () => new Response("private error", { status: 503 }),
  );
  await result(502, "engine_unavailable");
});

test("non-JSON responses are invalid", async () => {
  fetchMock.mock.mockImplementation(
    async () => new Response("<html>proxy error</html>"),
  );
  await result(502, "invalid_engine_status");
});

for (const [name, body] of [
  ["wrong service", { ...health, service: "other-service" }],
  ["wrong contract version", { ...health, contract_version: "2.0" }],
  ["unknown mode", { ...health, mode: "unknown" }],
  ["incomplete status", { service: "croppilot-engine" }],
  ["null status", null],
] as const) {
  test(`rejects ${name}`, async () => {
    fetchMock.mock.mockImplementation(async () => Response.json(body));
    await result(502, "invalid_engine_status");
  });
}
