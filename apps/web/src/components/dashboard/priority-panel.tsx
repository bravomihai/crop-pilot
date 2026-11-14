import {
  DEFAULT_FARMING_PRIORITIES,
  PRIORITY_CONTROLS,
  type DemoCropRanking,
  type FarmingPriorities,
} from "@/lib/demo-priorities";
import type { DemoCropId } from "@/lib/dashboard-scenario";
import Icon from "./icon";

export default function PriorityPanel({
  ranking,
  cropId,
  onChange,
  onSelectCrop,
}: {
  ranking: DemoCropRanking;
  cropId: DemoCropId;
  onChange: (priorities: FarmingPriorities) => void;
  onSelectCrop: (cropId: DemoCropId) => void;
}) {
  return (
    <section
      id="farming-priorities"
      className="dashboard-card priority-card"
      aria-labelledby="priorities-title"
    >
      <div className="card-heading">
        <div>
          <span className="heading-icon">
            <Icon name="budget" />
          </span>
          <h2 id="priorities-title">Your farming priorities</h2>
        </div>
        <button
          className="text-button"
          type="button"
          disabled={ranking.changed === 0}
          onClick={() => onChange({ ...DEFAULT_FARMING_PRIORITIES })}
        >
          Reset to 50
        </button>
      </div>
      <p className="card-description">
        Move a slider to filter and reorder the demo crop recommendations
        instantly. No analysis button needed.
      </p>
      <div
        className={`priority-preset ${ranking.changed === 0 ? "is-standard" : ""}`}
      >
        <span>
          <Icon name={ranking.changed === 0 ? "check" : "field"} size={15} />
          <strong>
            {ranking.changed === 0
              ? "Safe maximum profitability"
              : "Custom farming priorities"}
          </strong>
        </span>
        <small>
          {ranking.changed === 0
            ? "Standard preset · all sliders at 50"
            : `${ranking.changed} of 5 priorities adjusted`}
        </small>
      </div>
      <div className="priority-controls">
        {PRIORITY_CONTROLS.map(
          ({ key, label, low, high, description, icon }) => (
            <div className="priority-control" key={key}>
              <label htmlFor={`priority-${key}`}>
                <span>
                  <Icon name={icon} size={16} />
                  {label}
                </span>
                <output htmlFor={`priority-${key}`}>
                  {ranking.priorities[key]}
                  <small> / 100</small>
                </output>
              </label>
              <input
                id={`priority-${key}`}
                type="range"
                min={0}
                max={100}
                step={1}
                value={ranking.priorities[key]}
                aria-describedby={`priority-${key}-help`}
                aria-valuetext={`${ranking.priorities[key]} out of 100; ${low} to ${high}`}
                style={{
                  background: `linear-gradient(to right, #2563eb ${ranking.priorities[key]}%, #e2e8f0 ${ranking.priorities[key]}%)`,
                }}
                onChange={(event) =>
                  onChange({
                    ...ranking.priorities,
                    [key]: Number(event.target.value),
                  })
                }
              />
              <div className="priority-endpoints">
                <span>0 · {low}</span>
                <span>100 · {high}</span>
              </div>
              <p id={`priority-${key}-help`}>{description}</p>
            </div>
          ),
        )}
      </div>
      <div className="priority-results-heading">
        <h3>Recommended crops</h3>
        <span role="status" aria-live="polite" aria-atomic="true">
          {ranking.eligible.length} of {ranking.ranked.length} match
          <span className="sr-only">
            {ranking.eligible[0]
              ? `. Top match: ${ranking.eligible[0].name}.`
              : ". No matching crops."}
          </span>
        </span>
      </div>
      {ranking.eligible.length > 0 ? (
        <ol className="priority-ranked-list">
          {ranking.eligible.slice(0, 3).map((crop, index) => (
            <li key={crop.id}>
              <button
                type="button"
                onClick={() => onSelectCrop(crop.id)}
                aria-pressed={crop.id === cropId}
              >
                <span className="priority-rank">{index + 1}</span>
                <span className="priority-crop-copy">
                  <strong>{crop.name}</strong>
                  <small>
                    {crop.matches[0] ??
                      "Standard demo profit & rotation profile"}
                  </small>
                </span>
                <span className="priority-crop-score">
                  {crop.score}
                  <small>demo fit</small>
                </span>
                <Icon name={crop.id === cropId ? "check" : "arrow"} size={15} />
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <div className="priority-empty" role="status">
          <Icon name="info" size={20} />
          <div>
            <strong>No crops match all your settings</strong>
            <p>
              Allow more budget, water, or field operations, or reduce the
              cleanup requirement. You can also reset the five sliders.
            </p>
          </div>
        </div>
      )}
      {ranking.excluded.length > 0 && (
        <details className="priority-exclusions">
          <summary>
            Why {ranking.excluded.length}{" "}
            {ranking.excluded.length === 1 ? "crop is" : "crops are"} filtered
            out
          </summary>
          <ul>
            {ranking.excluded.map((crop) => (
              <li key={crop.id}>
                <strong>{crop.name}</strong>
                <span>{crop.reasons.join(" ")}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="priority-demo-note">
        <strong>Demo preset, not a profit forecast.</strong> At 50, the extra
        priority weights are neutral. The sample baseline and climate scenario
        apply; the demo rotation check only skips the last entered crop. These
        settings personalise this preview, not the engine's rotation plans.
      </p>
    </section>
  );
}
