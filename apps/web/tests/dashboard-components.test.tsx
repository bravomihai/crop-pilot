import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { resultSchema } from "@fieldshift/contracts";
import FieldDashboard from "../src/components/field-dashboard";
import ParcelMap from "../src/components/dashboard/parcel-map";
import CompatibilityCard from "../src/components/dashboard/compatibility-card";
import RecommendationResults from "../src/components/recommendation-results";
import PriorityPanel from "../src/components/dashboard/priority-panel";
import PlanCard from "../src/components/plan-card";
import Calculator from "../src/components/calculator";
import CurrentRotationInput from "../src/components/current-rotation-input";
import ReplayChart from "../src/components/charts/replay-chart";
import ClimateTrendChart from "../src/components/charts/climate-trend-chart";
import { fullExampleRequest } from "../src/lib/api";
import {
  DEFAULT_FARMING_PRIORITIES,
  rankDemoCrops,
} from "../src/lib/demo-priorities";

test("main page starts with location search and field-boundary drawing without dashboard clutter", () => {
  const html = renderToStaticMarkup(createElement(FieldDashboard));
  const textContent = html.replace(/<[^>]+>/g, "");
  for (const text of [
    "FieldShift",
    "Prototype",
    "Pick your field.",
    "Search for a place, then draw your field boundary on the map.",
    "Draw field",
    "No account. Nothing saved.",
  ])
    assert.ok(textContent.includes(text), text);
  assert.doesNotMatch(html, /NASA LIVE DATA|Calibrated with|tel:|Use map centre|COMING SOON|href="\/calculator"|dashboard-sidebar/);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(ids.length, new Set(ids).size);
  for (const match of html.matchAll(/href="#([^"]+)"/g))
    assert.ok(ids.includes(match[1]), match[1]);
});

test("field map offers boundary drawing controls and no point-selection fallback", () => {
  const html = renderToStaticMarkup(createElement(ParcelMap, {
    view: { latitude: 44.56, longitude: 27.35 },
    selection: null,
    color: "#123c2f",
    opacity: 0.2,
    onSelect: () => {},
    onDrawingChange: () => {},
  }));
  assert.match(html, /Draw field/);
  assert.match(html, /Draw the field boundary using corner clicks/);
  assert.doesNotMatch(html, /Use map centre|Selected map centre/);
});

test("compatibility cards show three interactive alternatives with explicit demo qualifications", () => {
  const html = renderToStaticMarkup(
    createElement(CompatibilityCard, {
      cropId: "maize",
      scenario: { temperature: 5, rainfall: -50 },
      selected: true,
      pdfCount: 2,
      onSelectCrop: () => {},
    }),
  );
  assert.match(html, /Low illustrative fit/);
  assert.match(html, /NOT AN AGRONOMIC ASSESSMENT/);
  assert.match(html, /2 PDFs selected locally/);
  assert.match(html, /not parsed or used in scores/);
  assert.equal((html.match(/<button/g) || []).length, 3);
});

test("missing baseline after a given rotation is explained, not requested again", () => {
  const fixture = JSON.parse(
    readFileSync(
      new URL(
        "../../../packages/contracts/examples/recommendation-result.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  const result = resultSchema.parse({ ...fixture, baseline: undefined });
  const render = (current_rotation?: string[]) =>
    renderToStaticMarkup(
      createElement(RecommendationResults, {
        result,
        busy: false,
        error: "",
        request: { ...fullExampleRequest, current_rotation },
        onRecalculate: () => {},
      }),
    );
  const given = render(["maize", "winter_wheat"]);
  assert.doesNotMatch(given, /Add your current rotation/);
  assert.match(given, /could not be evaluated for comparison/);
  assert.match(render(undefined), /Add your current rotation/);
});

test("the past-season replay says when a hypothetical scenario was applied", () => {
  const full = resultSchema.parse(
    JSON.parse(
      readFileSync(
        new URL("../../../packages/contracts/examples/recommendation-result.full.json", import.meta.url),
        "utf8",
      ),
    ),
  );
  const render = (scenario: { temp_change_c: number; rain_change_pct: number }) =>
    renderToStaticMarkup(
      createElement(RecommendationResults, {
        result: full,
        busy: false,
        error: "",
        request: { ...fullExampleRequest, scenario },
        onRecalculate: () => {},
      }),
    );
  assert.ok(
    render({ temp_change_c: 2, rain_change_pct: -20 }).includes(
      "includes the hypothetical scenario (+2 °C, -20% rain), so these are not the observed outcomes",
    ),
  );
  assert.ok(!render({ temp_change_c: 0, rain_change_pct: 0 }).includes("hypothetical scenario ("));
});

test("rotation result cards do not manufacture missing alternatives", () => {
  const fixture = JSON.parse(
    readFileSync(
      new URL(
        "../../../packages/contracts/examples/recommendation-result.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  for (const [status, count] of [
    ["complete", 3],
    ["limited", 2],
    ["limited", 1],
    ["insufficient_data", 0],
  ] as const) {
    const result = resultSchema.parse({
      ...fixture,
      status,
      plans: fixture.plans.slice(0, count),
    });
    const html = renderToStaticMarkup(
      createElement(RecommendationResults, { result, busy: false, error: "" }),
    );
    assert.equal((html.match(/class="plan"/g) || []).length, count);
    assert.equal((html.match(/class="crop-order"/g) || []).length, count * 3);
    assert.match(html, /fictional results/);
  }
});

test("five English priority sliders render with neutral defaults, labels, values, and a reset control", () => {
  const ranking = rankDemoCrops(DEFAULT_FARMING_PRIORITIES, {
    temperature: 0,
    rainfall: 0,
  });
  const html = renderToStaticMarkup(
    createElement(PriorityPanel, {
      ranking,
      cropId: "maize",
      onChange: () => {},
      onSelectCrop: () => {},
    }),
  );
  const sliders = [...html.matchAll(/<input[^>]*type="range"[^>]*>/g)].map(
    (match) => match[0],
  );
  assert.equal(sliders.length, 5);
  for (const slider of sliders) {
    assert.match(slider, /min="0"/);
    assert.match(slider, /max="100"/);
    assert.match(slider, /value="50"/);
    assert.match(slider, /aria-describedby=/);
  }
  for (const label of [
    "Investment budget",
    "Water reserve",
    "Soil regeneration",
    "Time &amp; logistics",
    "Field cleanup need",
    "Safe maximum profitability",
    "Reset to 50",
    "not a profit forecast",
  ])
    assert.ok(html.includes(label), label);
});

test("changing priorities renders a different top crop immediately and explains excluded crops", () => {
  const make = (water: number) =>
    renderToStaticMarkup(
      createElement(PriorityPanel, {
        ranking: rankDemoCrops(
          { ...DEFAULT_FARMING_PRIORITIES, water },
          { temperature: 0, rainfall: 0 },
        ),
        cropId: "maize",
        onChange: () => {},
        onSelectCrop: () => {},
      }),
    );
  assert.match(make(50), /Top match: Maize/);
  const dry = make(0);
  assert.match(dry, /Top match: Sorghum/);
  assert.match(dry, /filtered out/);
  assert.match(dry, /Needs more water/);
  assert.match(dry, /Custom farming priorities/);
});

test("excluded selections and zero eligible crops never render fabricated alternatives", () => {
  const ranking = rankDemoCrops(
    { investment: 0, water: 0, regeneration: 100, logistics: 0, cleanup: 100 },
    { temperature: 0, rainfall: 0 },
  );
  const panel = renderToStaticMarkup(
    createElement(PriorityPanel, {
      ranking,
      cropId: "maize",
      onChange: () => {},
      onSelectCrop: () => {},
    }),
  );
  assert.match(panel, /No crops match all your settings/);
  assert.doesNotMatch(panel, /class="priority-rank"/);
  const card = renderToStaticMarkup(
    createElement(CompatibilityCard, {
      ranking,
      cropId: "maize",
      scenario: { temperature: 0, rainfall: 0 },
      selected: true,
      pdfCount: 0,
      onSelectCrop: () => {},
    }),
  );
  assert.match(card, /Outside your current settings/);
  assert.match(card, /No alternative crop matches/);
  assert.equal((card.match(/<button/g) || []).length, 0);
});

const fullFixture = resultSchema.parse(
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

test("full optional result has a separate baseline, shared timeline, unknown productivity, and local checks", () => {
  const html = renderToStaticMarkup(
    createElement(RecommendationResults, {
      result: fullFixture,
      busy: false,
      error: "",
      request: fullExampleRequest,
      onRecalculate: () => {},
    }),
  );
  assert.equal((html.match(/class="plan"/g) || []).length, 1);
  assert.match(html, /class="plan baseline-plan"/);
  assert.match(html, /1 \/ 3 plans/);
  assert.match(html, /Compare criterion scores/);
  assert.match(html, /Bare soil, consider a cover crop/);
  assert.match(html, /Productivity: Unknown/);
  assert.match(html, /Check locally before you decide/);
  assert.match(html, /not a forecast/);
  assert.match(html, /min="-3" max="5" step="0.5"/);
});

test("baseline rule violations are shown without changing the alternative count", () => {
  const baseline = {
    ...fullFixture.baseline!,
    violations: ["Example rotation rule violation."],
  };
  const html = renderToStaticMarkup(
    createElement(PlanCard, { plan: baseline, baseline: true }),
  );
  assert.match(html, /Rules your current rotation breaks/);
  assert.match(html, /Example rotation rule violation/);
  const unknown = renderToStaticMarkup(
    createElement(PlanCard, {
      plan: { ...baseline, scores: { water: null, soil: 0 } },
      baseline: true,
    }),
  );
  assert.match(unknown, /Water: Unknown/);
  assert.match(unknown, /Soil: 0 out of 100/);
});

test("calculator exposes supported crops, ordered rotation, documentary sources and productivity helper", () => {
  const html = renderToStaticMarkup(
    createElement(Calculator, { initialRequest: fullExampleRequest }),
  );
  assert.match(html, /winter_rapeseed/);
  assert.match(html, /soybean/);
  assert.match(html, /Your current rotation/);
  assert.match(html, /APIA application/);
  assert.doesNotMatch(html, /value="satellite"/);
  assert.match(html, /Relative potential, not a yield or profit forecast/);
  const rotation = renderToStaticMarkup(
    createElement(CurrentRotationInput, {
      value: ["maize", "winter_wheat", "pea", "soybean", "winter_barley"],
      onChange: () => {},
    }),
  );
  assert.equal((rotation.match(/<select/g) || []).length, 5);
  assert.match(rotation, /disabled=""[^>]*>Add crop \(5\/5\)/);
});

test("future charts accept plain display props and expose text tables instead of inventing result fields", () => {
  const replay = renderToStaticMarkup(
    createElement(ReplayChart, {
      series: [
        {
          id: "b",
          label: "Baseline example",
          baseline: true,
          points: [
            { year: 2020, value: null },
            { year: 2021, value: 0 },
          ],
        },
      ],
    }),
  );
  assert.match(replay, /stroke-dasharray="7 5"/);
  assert.match(replay, /Read replay values as a table/);
  assert.match(replay, /Unknown/);
  const climate = renderToStaticMarkup(
    createElement(ClimateTrendChart, {
      title: "Example rain",
      unit: "mm",
      points: [
        { year: 2020, value: 10 },
        { year: 2021, value: null },
        { year: 2022, value: 14 },
      ],
    }),
  );
  assert.match(climate, /2.00 mm\/year/);
  assert.match(climate, /Read yearly values as a table/);
});

test("results show the past-season replay and the field's climate from the result", async () => {
  const { PlanReplay, ClimateCard } = await import("../src/components/results-evidence");
  const { replaySeries, climateSeries } = await import("../src/lib/chart-data");
  const full = resultSchema.parse(
    JSON.parse(readFileSync(new URL("../../../packages/contracts/examples/recommendation-result.full.json", import.meta.url), "utf8")),
  );
  const series = replaySeries(full.plans, full.baseline, "water");
  assert.equal(series[0].label, "Your current rotation");
  assert.equal(series[0].baseline, true);
  assert.deepEqual(series[1].points.map((p) => p.value), [81, 74, 62]);
  const climate = climateSeries(full.climate_context!, "hot_days_gt32");
  assert.deepEqual(climate.points.map((p) => p.value), [30, 40, 60]);
  const replayHtml = renderToStaticMarkup(createElement(PlanReplay, { result: full }));
  assert.match(replayHtml, /How each plan would have done/);
  assert.match(replayHtml, /2010–2012/);
  const climateHtml = renderToStaticMarkup(createElement(ClimateCard, { result: full }));
  assert.match(climateHtml, /Your field(&#x27;|')s climate, 2010–2012/);
  assert.match(climateHtml, /Trend: \+150 days per decade/);
  const bare = { ...full, climate_context: undefined, plans: full.plans.map(({ replay, ...plan }) => plan), baseline: undefined };
  assert.equal(renderToStaticMarkup(createElement(PlanReplay, { result: bare })), "");
  assert.equal(renderToStaticMarkup(createElement(ClimateCard, { result: bare })), "");
});


test("results explain the terms the challenge names, in plain words", async () => {
  const { default: Glossary, GLOSSARY, CROP_ROLES } = await import("../src/components/glossary");
  const html = renderToStaticMarkup(createElement(Glossary));
  for (const term of ["Evapotranspiration", "Water balance", "Soil moisture", "Frost risk", "NDVI", "Satellite and regional data vs your field"])
    assert.match(html, new RegExp(term));
  assert.ok(GLOSSARY.length >= 8 && CROP_ROLES.length >= 4);
  assert.ok(CROP_ROLES.some((entry) => /Legumes/.test(entry.role)));
});
