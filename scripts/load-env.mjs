import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";

const rootEnv = new URL("../.env", import.meta.url);

/** Inherited environment wins, including Compose's internal service URLs. */
export function loadRootEnv(env = process.env, envFile = rootEnv) {
  try {
    const values = parseEnv(readFileSync(envFile, "utf8"));
    for (const [name, value] of Object.entries(values)) {
      if (env[name] === undefined) env[name] = value;
    }
  } catch (error) {
    // Images and CI receive configuration through their environment, without a .env.
    if (error.code !== "ENOENT") throw error;
  }
  if (!env.DATABASE_URL && env.POSTGRES_PASSWORD) {
    const user = encodeURIComponent(env.POSTGRES_USER || "croppilot");
    const password = encodeURIComponent(env.POSTGRES_PASSWORD);
    const database = encodeURIComponent(env.POSTGRES_DB || "croppilot");
    env.DATABASE_URL = `postgresql://${user}:${password}@127.0.0.1:5432/${database}`;
  }
  if (env.CROPPILOT_CACHE_DIR === undefined) {
    env.CROPPILOT_CACHE_DIR = fileURLToPath(new URL("../services/engine/cache", import.meta.url));
  }
  return env;
}

loadRootEnv();
