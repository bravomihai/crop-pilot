import assert from "node:assert/strict";
import { test } from "node:test";
import { requestSchema } from "@croppilot/contracts";
import {
  addCorner,
  addFreehand,
  createParcel,
  MAX_BOUNDARY_POINTS,
  validateFieldPart,
  tracePoints,
  type Coordinate,
  type DrawSegment,
} from "../src/lib/parcel-geometry";
import { DEMO_CROPS, visualScenario } from "../src/lib/dashboard-scenario";
import { pdfSelectionError } from "../src/lib/pdf-file";
import {
  DEFAULT_FARMING_PRIORITIES,
  normalisePriorities,
  rankDemoCrops,
} from "../src/lib/demo-priorities";

const rectangle: Coordinate[] = [
  [26, 44],
  [26.001, 44],
  [26.001, 44.001],
  [26, 44.001],
];

test("WGS84 polygon gives hectares and a centre in latitude/longitude contract order", () => {
  const field = createParcel(rectangle);
  assert.ok(field.areaHectares! > 0.88 && field.areaHectares! < 0.9);
  assert.ok(Math.abs(field.location.latitude - 44.0005) < 1e-8);
  assert.ok(Math.abs(field.location.longitude - 26.0005) < 1e-8);
  assert.deepEqual(field.boundary?.[0], field.boundary?.at(-1));
  assert.deepEqual(rectangle.length, 4);
});

test("a drawn field can be sent in the recommendation request", () => {
  const field = createParcel(rectangle);
  assert.ok(field.boundary);
  const request = requestSchema.parse({
    location: field.location,
    field_boundary: { type: "Polygon", coordinates: [field.boundary] },
    available_from: "2026-11-15",
    priorities: { water: 3, soil: 3, climate: 3 },
    constraints: { irrigated: false, excluded_crops: [] },
    scenario: { temp_change_c: 0, rain_change_pct: 0 },
  });
  assert.deepEqual(request.field_boundary?.coordinates[0], field.boundary);
  assert.deepEqual(request.location, field.location);
});

test("field parts must stay inside the field and not overlap", () => {
  const field = createParcel(rectangle);
  const left = createParcel([[26, 44], [26.0005, 44], [26.0005, 44.001], [26, 44.001]]);
  const right = createParcel([[26.0005, 44], [26.001, 44], [26.001, 44.001], [26.0005, 44.001]]);
  const overlapping = createParcel([[26.0004, 44], [26.0009, 44], [26.0009, 44.001], [26.0004, 44.001]]);
  const outside = createParcel([[25.9998, 44], [26.0002, 44], [26.0002, 44.001], [25.9998, 44.001]]);
  assert.doesNotThrow(() => validateFieldPart(field, left, []));
  assert.doesNotThrow(() => validateFieldPart(field, right, [left]));
  assert.throws(() => validateFieldPart(field, overlapping, [left]), /cannot overlap/);
  assert.throws(() => validateFieldPart(field, outside, []), /inside the field/);
  assert.throws(() => validateFieldPart(field, right, Array(5).fill(left)), /at most 5/);
});

test("concave field boundaries keep the NASA representative point inside the parcel", () => {
  const field = createParcel([
    [26, 44],
    [26.004, 44],
    [26.004, 44.001],
    [26.001, 44.001],
    [26.001, 44.004],
    [26, 44.004],
  ]);
  const [longitude, latitude] = [
    field.location.longitude,
    field.location.latitude,
  ];
  assert.ok(longitude > 26 && longitude < 26.004);
  assert.ok(latitude > 44 && latitude < 44.004);
  assert.ok(latitude < 44.001 || longitude < 26.001);
});

test("field boundaries respect the request contract's point limit", () => {
  const detailed = Array.from(
    { length: MAX_BOUNDARY_POINTS + 1 },
    (_, index) => {
      const angle = (2 * Math.PI * index) / (MAX_BOUNDARY_POINTS + 1);
      return [
        26 + 0.001 * Math.cos(angle),
        44 + 0.001 * Math.sin(angle),
      ] as Coordinate;
    },
  );
  assert.throws(
    () => createParcel(detailed),
    new RegExp(`at most ${MAX_BOUNDARY_POINTS} points`),
  );
});

test("clockwise and counterclockwise outlines measure the same field", () => {
  const first = createParcel(rectangle);
  const reversed = createParcel([...rectangle].reverse());
  const closed = createParcel([...rectangle, rectangle[0]]);
  assert.ok(Math.abs(first.areaHectares! - reversed.areaHectares!) < 1e-8);
  assert.equal(first.areaHectares, closed.areaHectares);
});

test("crossed, touching, collapsed, incomplete, and invalid-coordinate outlines are rejected", () => {
  assert.throws(
    () =>
      createParcel([
        [26, 44],
        [26.002, 44.002],
        [26, 44.002],
        [26.002, 44],
      ]),
    /crosses itself/,
  );
  assert.throws(
    () => createParcel([...rectangle, rectangle[1]]),
    /touches itself/,
  );
  assert.throws(
    () =>
      createParcel([
        [26, 44],
        [26.001, 44],
        [26.002, 44],
      ]),
    /no usable area/,
  );
  assert.throws(() => createParcel(rectangle.slice(0, 2)), /at least three/);
  assert.throws(() =>
    createParcel([
      [181, 44],
      [26, 44],
      [26, 45],
    ]),
  );
});

test("freehand simplification preserves the straight corners and the curve endpoints", () => {
  let trace: DrawSegment[] = [];
  trace = addCorner(trace, [26, 44]);
  trace = addCorner(trace, [26.001, 44]);
  const straightCorners = tracePoints(trace);
  const curve: Coordinate[] = [
    [26.001, 44],
    [26.00101, 44.0002],
    [26.00099, 44.0004],
    [26.00101, 44.0006],
    [26.001, 44.001],
  ];
  trace = addFreehand(trace, curve, 0.00005);
  assert.deepEqual(
    trace.slice(0, 2).flatMap((segment) => segment.points),
    straightCorners,
  );
  assert.deepEqual(trace.at(-1)?.points[0], curve[0]);
  assert.deepEqual(trace.at(-1)?.points.at(-1), curve.at(-1));
  assert.ok(trace.at(-1)!.points.length < curve.length);
  trace = addCorner(trace, [26, 44.001]);
  assert.ok(createParcel(tracePoints(trace)).areaHectares! > 0);
  assert.deepEqual(tracePoints(trace.slice(0, -2)), straightCorners);
});

test("repeated clicks are deduplicated and a curve can start a fresh outline", () => {
  const trace = addCorner([], [26, 44]);
  assert.equal(addCorner(trace, [26, 44]), trace);
  assert.equal(
    tracePoints(
      addFreehand(
        [],
        [
          [26, 44],
          [26.001, 44.001],
        ],
        0.00001,
      ),
    ).length,
    2,
  );
  assert.deepEqual(addFreehand([], [], 0.00001), []);
});

test("visual scenarios retain all demo crops and update all four illustrative indicators", () => {
  const baseline = visualScenario({ temperature: 0, rainfall: 0 });
  const extreme = visualScenario({ temperature: 5, rainfall: -50 });
  assert.equal(baseline.waterSaving, 75);
  assert.equal(baseline.moisture, 68);
  assert.equal(baseline.temperature, "25.3");
  assert.equal(baseline.ndvi, "0.72");
  assert.equal(baseline.color, "#22c55e");
  assert.equal(extreme.color, "#ef4444");
  assert.ok(extreme.opacity > baseline.opacity);
  assert.ok(extreme.waterSaving < baseline.waterSaving);
  assert.ok(extreme.moisture < baseline.moisture);
  assert.ok(Number(extreme.temperature) > Number(baseline.temperature));
  assert.ok(Number(extreme.ndvi) < Number(baseline.ndvi));
  assert.equal(extreme.crops.length, DEMO_CROPS.length);
  for (const crop of extreme.crops)
    assert.ok(
      crop.score <= baseline.crops.find((item) => item.id === crop.id)!.score,
    );
  assert.equal(
    visualScenario({ temperature: 3, rainfall: 0 }).level,
    "moderate",
  );
  assert.equal(visualScenario({ temperature: 5, rainfall: 0 }).level, "high");
});

const baselineScenario = { temperature: 0, rainfall: 0 };

test("all five defaults are 50 and leave the existing demo baseline unchanged", () => {
  assert.deepEqual(
    Object.values(DEFAULT_FARMING_PRIORITIES),
    [50, 50, 50, 50, 50],
  );
  for (const scenario of [
    baselineScenario,
    { temperature: 5, rainfall: -50 },
  ]) {
    const actual = rankDemoCrops(DEFAULT_FARMING_PRIORITIES, scenario);
    const baseline = visualScenario(scenario).crops;
    assert.equal(actual.changed, 0);
    assert.equal(actual.excluded.length, 0);
    assert.deepEqual(
      actual.eligible.map(({ id, score }) => ({ id, score })),
      baseline.map(({ id, score }) => ({ id, score })),
    );
  }
});

test("a low investment budget filters intensive crops and promotes low-input examples", () => {
  const result = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES, investment: 0 },
    baselineScenario,
  );
  assert.ok(result.eligible.some((crop) => crop.id === "oats"));
  assert.ok(result.eligible.some((crop) => crop.id === "pea"));
  assert.equal(result.eligible[0].id, "oats");
  for (const id of ["maize", "sugar_beet"])
    assert.match(
      result.excluded.find((crop) => crop.id === id)!.reasons.join(" "),
      /investment/,
    );
  const intensive = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES, investment: 100 },
    baselineScenario,
  );
  assert.ok(["maize", "sugar_beet"].includes(intensive.eligible[0].id));
});

test("water scarcity filters thirsty profiles; sufficient water admits them", () => {
  const dry = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES, water: 0 },
    baselineScenario,
  );
  assert.ok(dry.eligible.some((crop) => crop.id === "sorghum"));
  assert.ok(dry.eligible.some((crop) => crop.id === "sunflower"));
  assert.equal(dry.eligible[0].id, "sorghum");
  for (const id of ["maize", "soybean"])
    assert.match(
      dry.excluded.find((crop) => crop.id === id)!.reasons.join(" "),
      /water/,
    );
  const wet = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES, water: 100 },
    baselineScenario,
  );
  assert.ok(wet.eligible.some((crop) => crop.id === "maize"));
  assert.ok(wet.eligible.some((crop) => crop.id === "soybean"));
});

test("soil regeneration promotes legumes and the low end favours the sample cash-crop baseline", () => {
  const soil = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES, regeneration: 100 },
    baselineScenario,
  );
  assert.deepEqual(
    new Set(soil.eligible.slice(0, 3).map((crop) => crop.id)),
    new Set(["alfalfa", "soybean", "pea"]),
  );
  const cash = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES, regeneration: 0 },
    baselineScenario,
  );
  assert.ok(!["alfalfa", "soybean", "pea"].includes(cash.eligible[0].id));
});

test("time allowance and cleanup pressure apply independent filters with reasons", () => {
  const lowTime = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES, logistics: 0 },
    baselineScenario,
  );
  assert.ok(lowTime.eligible.some((crop) => crop.id === "winter_wheat"));
  assert.ok(
    lowTime.excluded.some(
      (crop) =>
        crop.id === "maize" &&
        crop.reasons.some((reason) => reason.includes("field operations")),
    ),
  );
  const cleanup = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES, cleanup: 100 },
    baselineScenario,
  );
  assert.ok(cleanup.eligible.length > 0);
  assert.ok(
    cleanup.eligible.every((crop) =>
      ["maize", "sunflower", "soybean", "sorghum", "sugar_beet"].includes(
        crop.id,
      ),
    ),
  );
  assert.ok(
    cleanup.excluded.every((crop) =>
      crop.reasons.some((reason) => reason.includes("cleanup")),
    ),
  );
  const normalPressure = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES, cleanup: 0 },
    baselineScenario,
  );
  assert.deepEqual(
    normalPressure.eligible.map((crop) => crop.id),
    visualScenario(baselineScenario).crops.map((crop) => crop.id),
  );
});

test("conflicting priorities return an honest empty list, without fallback recommendations", () => {
  const result = rankDemoCrops(
    { investment: 0, water: 0, regeneration: 100, logistics: 0, cleanup: 100 },
    baselineScenario,
  );
  assert.equal(result.eligible.length, 0);
  assert.equal(result.excluded.length, DEMO_CROPS.length);
  assert.ok(result.excluded.every((crop) => crop.reasons.length > 0));
});

test("reset restores the neutral ranking while retaining the last-crop demo rotation check", () => {
  const result = rankDemoCrops(
    { ...DEFAULT_FARMING_PRIORITIES },
    baselineScenario,
    "maize",
  );
  assert.ok(!result.eligible.some((crop) => crop.id === "maize"));
  assert.match(
    result.excluded.find((crop) => crop.id === "maize")!.reasons[0],
    /last entered crop/,
  );
  assert.deepEqual(
    result.eligible.map((crop) => crop.id),
    visualScenario(baselineScenario)
      .crops.filter((crop) => crop.id !== "maize")
      .map((crop) => crop.id),
  );
});

test("priority inputs are bounded, finite, and never mutate caller state", () => {
  const malformed = {
    investment: -10,
    water: 200,
    regeneration: NaN,
    logistics: Infinity,
    cleanup: 40.7,
  };
  assert.deepEqual(normalisePriorities(malformed), {
    investment: 0,
    water: 100,
    regeneration: 50,
    logistics: 50,
    cleanup: 41,
  });
  const input = { ...DEFAULT_FARMING_PRIORITIES, water: 0 };
  const before = { ...input };
  rankDemoCrops(input, baselineScenario);
  assert.deepEqual(input, before);
  for (let mask = 0; mask < 32; mask++) {
    const settings = Object.fromEntries(
      Object.keys(DEFAULT_FARMING_PRIORITIES).map((key, index) => [
        key,
        mask & (1 << index) ? 100 : 0,
      ]),
    ) as typeof input;
    const result = rankDemoCrops(settings, { temperature: 5, rainfall: -50 });
    assert.ok(
      result.ranked.every(
        (crop) =>
          Number.isInteger(crop.score) && crop.score >= 0 && crop.score <= 100,
      ),
    );
  }
});

test("PDF selection checks extension, size, and header without parsing document contents", async () => {
  assert.equal(
    await pdfSelectionError(new File(["%PDF-1.7\n"], "soil.PDF")),
    null,
  );
  assert.match(
    (await pdfSelectionError(new File(["not a PDF"], "soil.pdf")))!,
    /PDF header/,
  );
  assert.match(
    (await pdfSelectionError(new File(["%PDF-1.7"], "soil.txt")))!,
    /one PDF/,
  );
  assert.match(
    (await pdfSelectionError(
      new File([new Uint8Array(10 * 1024 * 1024 + 1)], "soil.pdf"),
    ))!,
    /10 MB/,
  );
});


test("autumn sowing hint covers 6 November to the end of February only", async () => {
  const { afterAutumnSowing } = await import("../src/lib/planning-dates");
  assert.equal(afterAutumnSowing("2026-11-05"), false);
  assert.equal(afterAutumnSowing("2026-11-06"), true);
  assert.equal(afterAutumnSowing("2027-02-28"), true);
  assert.equal(afterAutumnSowing("2027-03-01"), false);
  assert.equal(afterAutumnSowing("2026-09-20"), false);
  assert.equal(afterAutumnSowing("not a date"), false);
});

test("a page link can center the map inside Romania only", async () => {
  const { fieldFromQuery } = await import("../src/lib/planning-dates");
  assert.deepEqual(fieldFromQuery("?lat=44.45&lon=26.5&name=Example%20field"), { name: "Example field", latitude: 44.45, longitude: 26.5 });
  assert.equal(fieldFromQuery("?lat=44.45&lon=26.5")?.name, "Your field");
  assert.equal(fieldFromQuery("?lat=40&lon=26.5"), null);
  assert.equal(fieldFromQuery("?lat=abc&lon=26.5"), null);
  assert.equal(fieldFromQuery(""), null);
});
