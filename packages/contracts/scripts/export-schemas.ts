import { mkdir, writeFile } from "node:fs/promises";
import { z } from "zod";
import { requestSchema, resultSchema } from "../src/index";
const target = new URL("../schemas/", import.meta.url);
await mkdir(target, { recursive: true });
for (const [name, schema] of [
  ["recommendation-request", requestSchema],
  ["recommendation-result", resultSchema],
] as const) {
  await writeFile(
    new URL(`${name}.schema.json`, target),
    JSON.stringify(z.toJSONSchema(schema), null, 2) + "\n",
  );
}
