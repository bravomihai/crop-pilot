import assert from "node:assert/strict";
import { db } from "../src/lib/server/db";
import { readCache, writeCache, pruneCache } from "../src/lib/server/cache";
const url = new URL(process.env.DATABASE_URL ?? "");
assert.ok(["localhost", "127.0.0.1"].includes(url.hostname));
assert.equal(process.env.CACHE_ENABLED, "true");
const started = performance.now();
try {
  assert.equal(await readCache("outage-test"), null);
  assert.equal(
    await writeCache("outage-test", "environment", { public_test: true }, 60),
    false,
  );
  assert.equal(await pruneCache(), null);
  assert.ok(
    performance.now() - started < 5000,
    "Cache outage must not cause long waits",
  );
  console.info(
    "PASS PostgreSQL outage: read, write and cleanup fail gracefully within bounded time",
  );
} finally {
  await db().$disconnect();
}
