import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { resultSchema } from "@fieldshift/contracts";
import FieldDashboard from "../src/components/field-dashboard";
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

test("dashboard labels sample data and exposes map, planning, sources, and local-only PDFs", () => {
  const html = renderToStaticMarkup(createElement(FieldDashboard));
  const textContent = html.replace(/<[^>]+>/g, "");
  for (const text of [
    "FieldShift",
    "NASA SOURCES",
    "DEMO",
    "not live NASA measurements",
    "Your field, from above",
    "What would you like to plant?",
    "Soil analysis report",
    "stays in this tab",
    "not read",
    "COMING SOON",
  ])
    assert.ok(textContent.includes(text), text);
  assert.doesNotMatch(html, /NASA LIVE DATA|Calibrated with|tel:/);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(ids.length, new Set(ids).size);
  for (const match of html.matchAll(/href="#([^"]+)"/g))
    assert.ok(ids.includes(match[1]), match[1]);
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
