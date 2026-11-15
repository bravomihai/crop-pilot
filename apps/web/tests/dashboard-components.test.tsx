import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { resultSchema } from "@croppilot/contracts";
import FieldDashboard from "../src/components/field-dashboard";
import FieldMap from "../src/components/dashboard/field-map";
import CompatibilityCard from "../src/components/dashboard/compatibility-card";
import RecommendationResults from "../src/components/recommendation-results";
import PriorityPanel from "../src/components/dashboard/priority-panel";
import PlanCard from "../src/components/plan-card";
import Calculator from "../src/components/calculator";
import CurrentRotationInput from "../src/components/current-rotation-input";
import ReplayChart from "../src/components/charts/replay-chart";
import ClimateTrendChart from "../src/components/charts/climate-trend-chart";
import { fullExampleRequest } from "../src/lib/api";
import { compareWithCurrent, firstSentence, keyChecks, keyGaps, mainRisks } from "../src/lib/result-glance";
import { leiRange, marginLine, signedLei } from "../src/lib/money";
import { moneyCrops } from "../src/components/money-inputs";
import {
  DEFAULT_FARMING_PRIORITIES,
  rankDemoCrops,
} from "../src/lib/demo-priorities";

test("main page starts with location search and a point map without dashboard clutter", () => {
  const html = renderToStaticMarkup(createElement(FieldDashboard));
  const textContent = html.replace(/<[^>]+>/g, "");
  for (const text of [
    "CropPilot",
    "Prototype",
    "Pick your field.",
    "Search for a place or click the map.",
    "Use map centre",
    "stays in this tab",
  ])
    assert.ok(textContent.includes(text), text);
  assert.doesNotMatch(html, /NASA LIVE DATA|Calibrated with|tel:|Draw field|Draw a field|COMING SOON|KPI|href="\/calculator"|dashboard-sidebar/);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(ids.length, new Set(ids).size);
  for (const match of html.matchAll(/href="#([^"]+)"/g))
    assert.ok(ids.includes(match[1]), match[1]);
});

test("field map offers point relocation and clear controls without polygon drawing", () => {
  const html = renderToStaticMarkup(createElement(FieldMap, {
    view: { latitude: 44.56, longitude: 27.35 },
    selection: { latitude: 44.56, longitude: 27.35 },
    onSelect: () => {},
  }));
  assert.match(html, /Click anywhere to move your pin/);
  assert.match(html, /Clear field location/);
  assert.doesNotMatch(html, /Draw|Finish outline|hectares|polygon/);
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

test("the plain-words explanation loads by itself, without a button or language selector", () => {
  const result = resultSchema.parse({ ...fullFixture, mode: "computed" });
  const html = renderToStaticMarkup(createElement(RecommendationResults, { result, busy: false, error: "" }));
  assert.doesNotMatch(html, /Summarise in plain words|ai-summary-button/);
  assert.doesNotMatch(html, /ai-summary-language|Rezumat|Română/);
});

test("results open with an At a glance summary and keep technical notes collapsed", () => {
  const result = resultSchema.parse({ ...fullFixture, mode: "computed" });
  const html = renderToStaticMarkup(
    createElement(RecommendationResults, { result, busy: false, error: "", request: fullExampleRequest, onRecalculate: () => {} }),
  );
  const glance = html.indexOf('id="results-summary"');
  assert.ok(glance > 0 && glance < html.indexOf('id="plan-details"'), "summary comes before the details");
  assert.ok(html.indexOf('id="plan-details"') < html.indexOf('class="how-calculated"'));
  assert.match(html, /Best match:/);
  assert.match(html, /Compared with your current rotation/);
  assert.match(html, /Before you decide/);
  assert.match(html, /href="#results-summary"/);
  assert.match(html, /Print for your agronomist/);
  assert.match(html, /<details class="how-calculated"><summary>How this was calculated/);
  assert.match(html, /<details class="plan-why"><summary>Why this plan\?/);
});

test("the glance helpers use the result as it is", () => {
  const [plan] = fullFixture.plans;
  const baseline = fullFixture.baseline!;
  const rows = compareWithCurrent(plan, baseline);
  for (const row of rows) {
    assert.ok(Number.isInteger(row.plan) && Number.isInteger(row.current));
  }
  assert.deepEqual(compareWithCurrent(plan, undefined), []);
  assert.equal(firstSentence("Chosen first. Then more."), "Chosen first.");
  assert.equal(firstSentence("No full stop"), "No full stop");
  const tradeoffs = ["Climate: 52/100.", "Watch out: Pea: heat in 11 of 18 past seasons."];
  assert.deepEqual(mainRisks({ ...plan, tradeoffs }), ["Pea: heat in 11 of 18 past seasons."]);
  const shared = "Confirm the sowing and harvest windows for this location.";
  const checks = keyChecks(
    { ...plan, local_checks: [shared, "Check pea root-disease history."] },
    [{ ...plan, local_checks: [shared] }],
  );
  assert.deepEqual(checks, ["Check pea root-disease history.", shared]);
  assert.deepEqual(
    keyGaps({
      ...fullFixture,
      data_gaps: [
        "SoilGrids not queried (offline test).",
        "No field-level measurements, soil moisture or soil analysis are supplied by this adapter.",
        "No crop history was provided; x.",
      ],
    }),
    ["No crop history was provided; x."],
  );
});

test("plan cards show money per hectare a year as an estimate, with unknowns spelled out", () => {
  const [plan] = fullFixture.plans;
  const baseline = fullFixture.baseline!;
  assert.ok(plan.economics && baseline.economics, "the full example carries economics");
  const html = renderToStaticMarkup(createElement(PlanCard, { plan, number: 1 }));
  assert.match(html, /Money per hectare a year/);
  assert.match(html, /estimate/);
  assert.match(html, /Subsidies and their conditions/);
  // The example plan includes pea, which has no official price: totals are unknown, not 0.
  assert.equal(plan.economics.per_year.margin, null);
  assert.match(html, /plan-money-unknown/);
  assert.match(html, /Pea: no official recent price series/);
  assert.match(marginLine(plan.economics)!, /^unknown, because there are no official prices or costs for pea$/);
  assert.match(marginLine(baseline.economics)!, /^about -?[\d,]+ lei per hectare a year \(range -?[\d,]+ – -?[\d,]+ lei\)$/);
  assert.equal(marginLine(undefined), null);
  assert.equal(leiRange(null), "Unknown");
  assert.equal(leiRange({ low: 1200, typical: 1500, high: 2300 }), "1,200 – 2,300 lei");
  const results = renderToStaticMarkup(
    createElement(RecommendationResults, { result: resultSchema.parse({ ...fullFixture, mode: "computed" }), busy: false, error: "" }),
  );
  assert.match(results, /Money \(estimate\)/);
  assert.match(results, /Your current rotation: about/);
});

test("crops without official figures get a price and cost form; crop order is spelled out", () => {
  const result = resultSchema.parse({ ...fullFixture, mode: "computed" });
  const crops = moneyCrops(result);
  assert.equal(crops[0].id, "pea");
  assert.ok(crops[0].missing && crops[0].price === undefined);
  assert.ok(crops.slice(1).every((crop) => !crop.missing));
  const html = renderToStaticMarkup(
    createElement(RecommendationResults, {
      result,
      busy: false,
      error: "",
      request: fullExampleRequest,
      onRecalculate: () => {},
      onRecalculateMoney: () => {},
    }),
  );
  assert.match(html, /id="money-inputs"/);
  assert.match(html, /There are no official recent figures for pea/);
  assert.match(html, /Price you get \(lei\/t\)/);
  assert.match(html, /Add your prices/);
  // Without a handler (for example the static calculator) the form is not shown.
  assert.doesNotMatch(
    renderToStaticMarkup(createElement(RecommendationResults, { result, busy: false, error: "" })),
    /id="money-inputs"/,
  );
  const baseline = renderToStaticMarkup(createElement(PlanCard, { plan: result.baseline!, baseline: true }));
  assert.match(baseline, /a good previous crop|an acceptable previous crop|a poor previous crop/);
  assert.match(baseline, /commercial farms in the county/);
  assert.equal(signedLei(350), "+350 lei");
  assert.equal(signedLei(-120), "-120 lei");
});
