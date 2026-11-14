import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { resultSchema } from "@fieldshift/contracts";
import {
  OUTPUT_JSON_SCHEMA,
  summarize,
  summaryConfigured,
  summaryInput,
  systemPrompt,
  ungroundedNumbers,
} from "../src/lib/server/summary";
import { POST } from "../src/app/api/summary/route";

const full = resultSchema.parse(
  JSON.parse(
    readFileSync(new URL("../../../packages/contracts/examples/recommendation-result.full.json", import.meta.url), "utf8"),
  ),
);

function fakeClient(reply: unknown, stop_reason = "end_turn") {
  const calls: unknown[] = [];
  return {
    calls,
    beta: {
      messages: {
        create: async (params: unknown) => {
          calls.push(params);
          return { stop_reason, content: [{ type: "text", text: typeof reply === "string" ? reply : JSON.stringify(reply) }] };
        },
      },
    },
  } as never as { calls: unknown[]; beta: never };
}

const grounded = {
  headline: "Plan 1 keeps your soil healthier than your current rotation.",
  plans: [
    {
      id: "plan-1",
      in_short: "Wheat, then pea, then wheat.",
      why: "Water scores 61 out of 100 and soil 68.",
      watch_out: ["The field is bare for some months."],
      ask_your_agronomist: ["Check pea root diseases."],
    },
  ],
};

test("the model sees the computed result without coordinates or source ids", () => {
  const input = summaryInput(full);
  const text = JSON.stringify(input);
  assert.doesNotMatch(text, /latitude|longitude|44\.56|27\.36/);
  assert.equal(input.plans[0].scores_out_of_100.water, 61);
  assert.ok(input.current_rotation);
});

test("numbers not in the result are caught", () => {
  const input = summaryInput(full);
  assert.deepEqual(ungroundedNumbers(grounded, input), []);
  const invented = { ...grounded, headline: "Plan 1 yields 7.5 tonnes per hectare." };
  assert.deepEqual(ungroundedNumbers(invented, input), ["7.5"]);
});

test("a grounded reply is returned and the request uses the documented options", async () => {
  const client = fakeClient(grounded);
  const out = await summarize(full, "ro", client as never);
  assert.equal(out.plans[0].id, "plan-1");
  const params = client.calls[0] as Record<string, unknown>;
  assert.equal(params.model, "claude-opus-5-5");
  assert.equal(params.fallbacks, "default");
  assert.deepEqual(params.betas, ["server-side-fallback-2026-07-01"]);
  assert.deepEqual(params.output_config, { effort: "low", format: { type: "json_schema", schema: OUTPUT_JSON_SCHEMA } });
  assert.match(String(params.system), /Romanian/);
});

test("invented numbers, refusals and unreadable replies never reach the farmer", async () => {
  await assert.rejects(
    summarize(full, "en", fakeClient({ ...grounded, headline: "Expect 7.5 t/ha." }) as never),
    (error: { code?: string }) => error.code === "summary_unverified",
  );
  await assert.rejects(summarize(full, "en", fakeClient(grounded, "refusal") as never), (error: { code?: string }) => error.code === "summary_declined");
  await assert.rejects(summarize(full, "en", fakeClient("not json") as never), (error: { code?: string }) => error.code === "summary_invalid");
});

test("unknown plan ids from the model are dropped", async () => {
  const out = await summarize(full, "en", fakeClient({ ...grounded, plans: [...grounded.plans, { ...grounded.plans[0], id: "made-up" }] }) as never);
  assert.deepEqual(out.plans.map((plan) => plan.id), ["plan-1"]);
});

test("the route says when the AI summary is not set up", async () => {
  const saved = process.env.ANTHROPIC_API_KEY;
  delete process.env.ANTHROPIC_API_KEY;
  try {
    assert.equal(summaryConfigured(), false);
    const response = await POST(new Request("http://localhost/api/summary", { method: "POST", headers: { "content-type": "application/json" }, body: "{}" }));
    assert.equal(response.status, 503);
    assert.equal((await response.json()).code, "summary_not_configured");
  } finally {
    if (saved !== undefined) process.env.ANTHROPIC_API_KEY = saved;
  }
});

test("the prompt forbids new facts and keeps English by default", () => {
  const prompt = systemPrompt("en");
  assert.match(prompt, /Use only facts that are in the input/);
  assert.match(prompt, /Every number you write must appear in the input/);
  assert.match(prompt, /Write in English/);
});

test("the page sends a trimmed result that summarises the same and fits the gateway limit", async () => {
  const { summaryPayload } = await import("../src/lib/summary-payload");
  // A realistic size: 60 replayed seasons per plan, 240 monthly rows, 40 climate years.
  const seasons = Array.from({ length: 60 }, (_, i) => ({
    season_start_year: 1966 + i,
    scores: { water: 0.6, climate: 0.5, productivity: 0.4 },
  }));
  const big = resultSchema.parse({
    ...full,
    plans: full.plans.map((plan) => ({ ...plan, replay: seasons })),
    monthly_climate: Array.from({ length: 240 }, (_, i) => ({
      month: `${2006 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, "0")}`,
      mean_daily_max_c: 20, max_daily_max_c: 30, mean_daily_min_c: 10, min_daily_min_c: 0,
      max_temp_observations: 30, min_temp_observations: 30,
    })),
  });
  const payload = summaryPayload(big);
  assert.ok(resultSchema.safeParse(payload).success, "still a valid result");
  assert.deepEqual(summaryInput(payload), summaryInput(big), "the model sees exactly the same input");
  assert.ok(JSON.stringify(big).length > 32 * 1024);
  assert.ok(JSON.stringify({ result: payload, language: "ro" }).length < 256 * 1024);
  assert.ok(payload.plans.every((plan) => plan.replay === undefined));
  assert.equal(payload.monthly_climate.length, 0);
});
