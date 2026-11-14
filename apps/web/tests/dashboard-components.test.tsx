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
