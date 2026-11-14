"use client";
import { useState } from "react";
import type { RecommendationResult } from "@fieldshift/contracts";
import ReplayChart from "./charts/replay-chart";
import ClimateTrendChart from "./charts/climate-trend-chart";
import {
  CLIMATE_INDICATORS,
  REPLAY_METRICS,
  climateSeries,
  replaySeries,
  type ClimateIndicator,
  type ReplayMetric,
} from "@/lib/chart-data";

/** "How each plan would have done" over the past seasons replayed by the engine. */
export function PlanReplay({ result }: { result: RecommendationResult }) {
  const [metric, setMetric] = useState<ReplayMetric>("water");
  const series = replaySeries(result.plans, result.baseline, metric);
  if (!series.length) return null;
  const years = series.flatMap((entry) => entry.points.map((point) => point.year));
  const first = Math.min(...years);
  const last = Math.max(...years);
  return (
    <section className="results-evidence" aria-labelledby="replay-heading">
      <div className="evidence-heading">
        <h3 id="replay-heading">How each plan would have done</h3>
        <label htmlFor="replay-metric">
          Score
          <select id="replay-metric" value={metric} onChange={(event) => setMetric(event.target.value as ReplayMetric)}>
            {REPLAY_METRICS.map(([id, label]) => (
              <option key={id} value={id}>{label}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="evidence-note">
        Each plan replayed over the real weather of {first}–{last} at this point (NASA POWER), season by season.
        Lines that stay high in dry or hot years are the safer choice.
      </p>
      <ReplayChart series={series} title={`${REPLAY_METRICS.find(([id]) => id === metric)?.[1]} score by starting season (out of 100)`} />
    </section>
  );
}

function trendSentence(perDecade: number | null, unit: string) {
  if (perDecade == null) return "Not enough years for a trend.";
  if (Math.abs(perDecade) < 0.05) return "No clear trend.";
  const rounded = Math.abs(perDecade) >= 10 ? Math.round(perDecade) : Math.round(perDecade * 10) / 10;
  return `Trend: ${rounded > 0 ? "+" : ""}${rounded} ${unit} per decade.`;
}

/** Observed yearly climate at the field (`climate_context`), never scenario-adjusted. */
export function ClimateCard({ result }: { result: RecommendationResult }) {
  const [indicator, setIndicator] = useState<ClimateIndicator>("hot_days_gt32");
  const context = result.climate_context;
  if (!context || !context.years.length) return null;
  const [, label, unit] = CLIMATE_INDICATORS.find(([id]) => id === indicator)!;
  const { points, perDecade } = climateSeries(context, indicator);
  return (
    <section className="results-evidence" aria-labelledby="climate-heading">
      <div className="evidence-heading">
        <h3 id="climate-heading">Your field&apos;s climate, {context.period.start_year}–{context.period.end_year}</h3>
        <label htmlFor="climate-indicator">
          Show
          <select id="climate-indicator" value={indicator} onChange={(event) => setIndicator(event.target.value as ClimateIndicator)}>
            {CLIMATE_INDICATORS.map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="evidence-note">
        Observed values from NASA POWER for the area around your field, not a forecast. {trendSentence(perDecade, unit)}{" "}
        Over a short record a trend changes with the first and last years, so read it as a direction.
      </p>
      <ClimateTrendChart points={points} title={`${label} per year`} unit={unit} />
    </section>
  );
}
