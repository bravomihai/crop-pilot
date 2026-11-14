import { visualScenario, type ClimateScenario } from "@/lib/dashboard-scenario";
import Icon from "./icon";

export default function ScenarioPanel({
  scenario,
  onChange,
}: {
  scenario: ClimateScenario;
  onChange: (scenario: ClimateScenario) => void;
}) {
  const preview = visualScenario(scenario);
  return (
    <section
      className="dashboard-card scenario-card"
      aria-labelledby="scenario-title"
    >
      <div className="card-heading">
        <div>
          <span className="heading-icon">
            <Icon name="temperature" />
          </span>
          <h2 id="scenario-title">What if the climate changes?</h2>
        </div>
        <button
          className="text-button"
          type="button"
          onClick={() => onChange({ temperature: 0, rainfall: 0 })}
        >
          Reset
        </button>
      </div>
      <p className="card-description">
        Explore a hypothetical scenario. The colours and values below are
        illustrative, not a forecast.
      </p>
      <div className="scenario-controls">
        <label htmlFor="temperature-scenario">
          <span>
            Temperature increase{" "}
            <output htmlFor="temperature-scenario">
              +{scenario.temperature.toFixed(1)}°C
            </output>
          </span>
          <input
            id="temperature-scenario"
            type="range"
            min={0}
            max={5}
            step={0.1}
            value={scenario.temperature}
            onChange={(event) =>
              onChange({ ...scenario, temperature: Number(event.target.value) })
            }
          />
          <span className="range-limits">
            <span>Baseline · 0°C</span>
            <span>+5°C</span>
          </span>
        </label>
        <label htmlFor="rainfall-scenario">
          <span>
            Rainfall change{" "}
            <output htmlFor="rainfall-scenario">
              {scenario.rainfall > 0 ? "+" : ""}
              {scenario.rainfall}%
            </output>
          </span>
          <input
            id="rainfall-scenario"
            type="range"
            min={-50}
            max={50}
            step={5}
            value={scenario.rainfall}
            onChange={(event) =>
              onChange({ ...scenario, rainfall: Number(event.target.value) })
            }
          />
          <span className="range-limits">
            <span>−50% · drier</span>
            <span>+50% · wetter</span>
          </span>
        </label>
      </div>
      <div className="scenario-legend">
        <span className={`scenario-state state-${preview.level}`}>
          <i style={{ background: preview.color }} />
          {preview.label}
        </span>
        <div>
          <span>
            <i style={{ background: "#22c55e" }} />
            Baseline
          </span>
          <span>
            <i style={{ background: "#eab308" }} />
            Moderate
          </span>
          <span>
            <i style={{ background: "#f97316" }} />
            High
          </span>
          <span>
            <i style={{ background: "#ef4444" }} />
            Severe
          </span>
        </div>
      </div>
    </section>
  );
}
