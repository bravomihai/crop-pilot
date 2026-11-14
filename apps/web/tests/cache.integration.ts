import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { db } from "../src/lib/server/db";
import {
  cacheKey,
  readCache,
  writeCache,
  pruneCache,
} from "../src/lib/server/cache";
const url = new URL(process.env.DATABASE_URL ?? "");
assert.ok(
  ["localhost", "127.0.0.1", "postgres"].includes(url.hostname),
  "Run only against the local/CI database",
);
assert.equal(process.env.CACHE_ENABLED, "true");
const expired = cacheKey("environment", randomUUID());
const active = cacheKey("environment", randomUUID());
try {
  assert.equal(await readCache(active), null);
  assert.equal(
    await writeCache(active, "environment", { public_test: 1 }, 3600),
    true,
  );
  assert.deepEqual(await readCache(active), { public_test: 1 });
  assert.equal(
    await writeCache(active, "environment", { public_test: 2 }, 3600),
    true,
  );
  assert.deepEqual(await readCache(active), { public_test: 2 });
  await writeCache(expired, "environment", { public_test: "expired" }, 3600);
  await db().dataCache.update({
    where: { key: expired },
    data: { expiresAt: new Date(Date.now() - 1000) },
  });
  assert.equal(await readCache(expired), null);
  const deleted = await pruneCache();
  assert.ok(deleted !== null && deleted >= 1);
  assert.equal(
    await db().dataCache.findUnique({ where: { key: expired } }),
    null,
  );
  assert.deepEqual(await readCache(active), { public_test: 2 });
  console.info(
    "PASS PostgreSQL: miss, write, read, overwrite, expiry and cleanup preserve active entries",
  );
} finally {
  await db().dataCache.deleteMany({
    where: { key: { in: [expired, active] } },
  });
  await db().$disconnect();
}
