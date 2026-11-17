import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { resultSchema, requestSchema } from "@croppilot/contracts";
import {
  bareGaps,
  linearTrend,
  scorePercent,
  timelineData,
} from "../src/lib/chart-data";
import {
  fullExampleRequest,
  getRecommendations,
  mockFixture,
} from "../src/lib/api";
import { HISTORY_SOURCES, RULE_CROPS } from "../src/lib/crop-options";

const full = resultSchema.parse(
  JSON.parse(
    readFileSync(
      new URL(
        "../../../packages/contracts/examples/recommendation-result.full.json",
        import.meta.url,
      ),
      "utf8",
    ),
  ),
);

test("optional scores distinguish unknown from a true zero", () => {
  assert.equal(scorePercent(null), null);
  assert.equal(scorePercent(undefined), null);
  assert.equal(scorePercent(0), 0);
  assert.equal(scorePercent(0.794), 79);
  assert.equal(scorePercent(full.plans[0].scores!.productivity), null);
});
test("baseline and alternatives share the same full calendar axis and long gaps are identified", () => {
  const axis = timelineData([full.baseline!, ...full.plans])!;
  assert.equal(new Date(axis.start).toISOString().slice(0, 10), "2026-10-01");
  assert.equal(new Date(axis.end).toISOString().slice(0, 10), "2029-08-01");
  assert.equal(axis.months.length, 34);
  assert.ok(bareGaps(full.plans[0]).some((gap) => gap.long));
  assert.equal(timelineData([]), null);
});
test("the wait before the first crop is a bare-soil gap and starts the axis", () => {
  const plan = full.plans[0];
  const firstSowing = plan.steps[0].sowing_window.start;
  // Field free about ten months earlier than the first sowing.
  const freeFrom = new Date(Date.parse(`${firstSowing}T00:00:00Z`) - 300 * 86_400_000)
    .toISOString()
    .slice(0, 10);
  const gaps = bareGaps(plan, freeFrom);
  const initial = gaps.find((gap) => gap.initial);
  assert.ok(initial, "an initial gap is reported");
  assert.equal(new Date(initial.start).toISOString().slice(0, 10), freeFrom);
  assert.equal(new Date(initial.end).toISOString().slice(0, 10), firstSowing);
  assert.equal(initial.long, true);
  assert.equal(bareGaps(plan).some((gap) => gap.initial), false, "without a date, no initial gap");
  assert.equal(bareGaps(plan, firstSowing).some((gap) => gap.initial), false, "sown on the free day: no gap");
  const axis = timelineData([plan], freeFrom)!;
  assert.equal(new Date(axis.start).toISOString().slice(0, 7), freeFrom.slice(0, 7));
});
test("simple trend ignores unknown years instead of treating them as zero", () => {
  const trend = linearTrend([
    { year: 2020, value: 10 },
    { year: 2021, value: null },
    { year: 2022, value: 14 },
  ])!;
  assert.equal(trend.slope, 2);
  assert.equal(trend.at(2021), 12);
  assert.equal(linearTrend([{ year: 2020, value: null }]), null);
});
test("supported form crops and documentary history sources match the merged request contract", () => {
  const rules = JSON.parse(readFileSync(
    new URL("../../../services/engine/fieldshift/evaluator/rules/ro_south.json", import.meta.url),
    "utf8",
  )) as { crops: { id: string; name: string }[] };
  assert.deepEqual(
    RULE_CROPS.map(([id, name]) => [id, name]),
    rules.crops.map(({ id, name }) => [id, name]),
  );
  assert.ok(
    !HISTORY_SOURCES.some(([source]) => (source as string) === "satellite"),
  );
  assert.equal(
    requestSchema.parse(fullExampleRequest).priorities.productivity,
    3,
  );
  assert.equal(mockFixture("?fixture=full"), "full");
  assert.equal(mockFixture("?fixture=other"), "default");
});
test("full mock fixture stays demo, preserves request coordinates, and only exposes baseline for a supplied rotation", async (context) => {
  const oldEnv = process.env.NEXT_PUBLIC_USE_MOCK_API;
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "window");
  process.env.NEXT_PUBLIC_USE_MOCK_API = "true";
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { location: { search: "?fixture=full" } },
  });
  context.after(() => {
    if (oldEnv === undefined) delete process.env.NEXT_PUBLIC_USE_MOCK_API;
    else process.env.NEXT_PUBLIC_USE_MOCK_API = oldEnv;
    if (descriptor) Object.defineProperty(globalThis, "window", descriptor);
    else Reflect.deleteProperty(globalThis, "window");
  });
  const result = await getRecommendations(fullExampleRequest);
  assert.equal(result.mode, "demo");
  assert.equal(result.status, "limited");
  assert.equal(result.plans.length, 1);
  assert.ok(result.baseline);
  assert.deepEqual(result.location, fullExampleRequest.location);
  const { current_rotation, ...withoutRotation } = fullExampleRequest;
  assert.equal((await getRecommendations(withoutRotation)).baseline, undefined);
  await assert.rejects(
    getRecommendations(fullExampleRequest, AbortSignal.abort()),
    /Cancelled/,
  );
});
