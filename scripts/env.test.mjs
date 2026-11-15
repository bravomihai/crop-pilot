import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { loadRootEnv } from "./load-env.mjs";

function fixture(t, contents) {
  const dir = mkdtempSync(join(tmpdir(), "croppilot-env-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const file = join(dir, ".env");
  writeFileSync(file, contents);
  return file;
}

test("one root configuration shares the token and derives the local database URL", (t) => {
  const env = loadRootEnv({}, fixture(t, 'POSTGRES_USER=farmer\nPOSTGRES_PASSWORD="p@ss:word"\nPOSTGRES_DB=public_cache\nINTERNAL_API_TOKEN=shared_mock_token\n'));
  assert.equal(env.INTERNAL_API_TOKEN, "shared_mock_token");
  assert.equal(env.DATABASE_URL, "postgresql://farmer:p%40ss%3Aword@127.0.0.1:5432/public_cache");
  assert.ok(env.CROPPILOT_CACHE_DIR.endsWith(join("services", "engine", "cache")));
});

test("container and shell settings override local values", (t) => {
  const env = loadRootEnv({ ENGINE_URL: "http://engine:8000", DATABASE_URL: "postgresql://container/cache", OPENAI_API_KEY: "inherited_mock_key", CROPPILOT_CACHE_DIR: "/tmp/cache" }, fixture(t, "ENGINE_URL=http://127.0.0.1:8000\nOPENAI_API_KEY=local_mock_key\nPOSTGRES_PASSWORD=local_mock_password\n"));
  assert.equal(env.ENGINE_URL, "http://engine:8000");
  assert.equal(env.DATABASE_URL, "postgresql://container/cache");
  assert.equal(env.OPENAI_API_KEY, "inherited_mock_key");
  assert.equal(env.CROPPILOT_CACHE_DIR, "/tmp/cache");
});

test("an image without a .env can use its injected environment", () => {
  const env = loadRootEnv({ DATABASE_URL: "postgresql://container/cache" }, new URL("./missing-test.env", import.meta.url));
  assert.equal(env.DATABASE_URL, "postgresql://container/cache");
});
