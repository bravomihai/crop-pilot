import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { resultSchema, requestSchema } from "@fieldshift/contracts";
import {
  bareGaps,
  linearTrend,
  scorePercent,
  timelineData,
} from "../src/lib/chart-data";
import {
  advertisedDate,
  contextMonths,
  gibsTileUrl,
  isCovered,
  powerCell,
  RULE_ZONES,
} from "../src/lib/regional-context";
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
test("POWER cell snaps latitude and longitude to the specified distinct grid spacings", () => {
  assert.deepEqual(powerCell({ latitude: 44.56, longitude: 27.36 }), [
    [44.25, 27.1875],
    [44.75, 27.8125],
  ]);
  assert.equal(RULE_ZONES.length, 4);
  assert.equal(isCovered({ latitude: 44.56, longitude: 27.36 }), true);
  assert.equal(isCovered({ latitude: 46.77, longitude: 23.59 }), false);
  assert.equal(isCovered({ latitude: 43.65, longitude: 22.6 }), true);
});
test("month snapshots respect advertised dates, interval gaps, and sampling periods", () => {
  const values = [
    "2025-01-01/2025-02-02/P1D",
    "2025-04-10/2025-06-01/P2D",
    "2025-08-13",
  ];
  assert.equal(advertisedDate(values, "2025-01"), "2025-01-31");
  assert.equal(advertisedDate(values, "2025-02"), "2025-02-02");
  assert.equal(advertisedDate(values, "2025-03"), null);
  assert.equal(advertisedDate(values, "2025-04"), "2025-04-30");
  assert.equal(advertisedDate(values, "2025-08"), "2025-08-13");
  assert.equal(advertisedDate(["2025-01-01/2025-12-01/P1M"], "2025-06"), null);
  const months = contextMonths(new Date("2026-11-14T00:00:00Z"));
  assert.equal(months.length, 60);
  assert.equal(months[0], "2021-12");
  assert.equal(months.at(-1), "2026-11");
  assert.match(
    gibsTileUrl(
      {
        id: "verified",
        matrix: "GoogleMapsCompatible_Level6",
        style: "default",
        maxNativeZoom: 6,
        tileSize: 256,
        values: [],
        defaultDate: "2025-01-01",
        title: "test",
      },
      "2025-01-01",
    ),
    /verified\/default\/2025-01-01\/GoogleMapsCompatible_Level6\/\{z\}\/\{y\}\/\{x\}\.png$/,
  );
});
test("supported form crops and documentary history sources match the merged request contract", () => {
  assert.deepEqual(
    RULE_CROPS.map(([id]) => id),
    [
      "winter_wheat",
      "winter_barley",
      "winter_rapeseed",
      "maize",
      "sunflower",
      "soybean",
      "pea",
    ],
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
