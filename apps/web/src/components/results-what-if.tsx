"use client";
import { useEffect, useState } from "react";
import type { RecommendationRequest } from "@croppilot/contracts";

export default function ResultsWhatIf({
  request,
  busy,
  onRecalculate,
  onCancel,
}: {
  request: RecommendationRequest;
  busy: boolean;
  onRecalculate: (scenario: RecommendationRequest["scenario"]) => void;
  onCancel?: () => void;
}) {
  const [scenario, setScenario] = useState(request.scenario);
  useEffect(() => setScenario({ ...request.scenario }), [request]);
  return (
    <section
      className="results-what-if analysis-chart"
      aria-labelledby="what-if-title"
    >
      <h3 id="what-if-title">What if conditions change?</h3>
      <p>
        This is a hypothetical scenario applied to past weather, not a forecast.
      </p>
      <div className="what-if-sliders">
        <label htmlFor="results-temperature">
          Temperature change{" "}
          <output htmlFor="results-temperature">
            {scenario.temp_change_c > 0 ? "+" : ""}
            {scenario.temp_change_c} °C
          </output>
          <input
            id="results-temperature"
            type="range"
            min={-3}
            max={5}
            step={0.5}
            value={scenario.temp_change_c}
            onChange={(event) =>
              setScenario({
                ...scenario,
                temp_change_c: Number(event.target.value),
              })
            }
          />
        </label>
        <label htmlFor="results-rain">
          Rainfall change{" "}
          <output htmlFor="results-rain">
            {scenario.rain_change_pct > 0 ? "+" : ""}
            {scenario.rain_change_pct}%
          </output>
          <input
            id="results-rain"
            type="range"
            min={-50}
            max={50}
            step={5}
            value={scenario.rain_change_pct}
            onChange={(event) =>
              setScenario({
                ...scenario,
                rain_change_pct: Number(event.target.value),
              })
            }
          />
        </label>
      </div>
      <div className="what-if-actions">
        <button
          className="button button--primary"
          type="button"
          aria-busy={busy}
          onClick={() => onRecalculate({ ...scenario })}
        >
          {busy && <span className="spinner" aria-hidden="true" />}Recalculate
        </button>
        {busy && onCancel && (
          <button
            type="button"
            className="button button--secondary"
            onClick={onCancel}
          >
            Stop waiting
          </button>
        )}
        <span role="status">
          {busy
            ? "Recalculating. Previous results remain visible."
            : "Adjust the sliders, then recalculate."}
        </span>
      </div>
    </section>
  );
}
