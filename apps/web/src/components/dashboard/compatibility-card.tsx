import {
  type ClimateScenario,
  type DemoCropId,
} from "@/lib/dashboard-scenario";
import {
  DEFAULT_FARMING_PRIORITIES,
  rankDemoCrops,
  type DemoCropRanking,
} from "@/lib/demo-priorities";
import Icon from "./icon";

export default function CompatibilityCard({
  cropId,
  scenario,
  selected,
  pdfCount,
  onSelectCrop,
  ranking,
}: {
  cropId: DemoCropId;
  scenario: ClimateScenario;
  selected: boolean;
  pdfCount: number;
  onSelectCrop: (id: DemoCropId) => void;
  ranking?: DemoCropRanking;
}) {
  const preview =
    ranking ?? rankDemoCrops(DEFAULT_FARMING_PRIORITIES, scenario);
  const crop = preview.ranked.find((item) => item.id === cropId)!;
  const fit = !crop.eligible
    ? "low"
    : crop.score >= 80
      ? "strong"
      : crop.score >= 60
        ? "moderate"
        : "low";
  return (
    <section
      className={`dashboard-card compatibility-card ${selected ? `fit-${fit}` : ""}`}
      aria-labelledby="compatibility-title"
    >
      <div className="card-heading">
        <div>
          <span className="heading-icon">
            <Icon name="leaf" />
          </span>
          <h2 id="compatibility-title">Crop compatibility preview</h2>
        </div>
      </div>
      <span className="sample-label">DEMO · NOT AN AGRONOMIC ASSESSMENT</span>
      <a className="adjust-priorities-link" href="#farming-priorities">
        Adjust farming priorities <Icon name="arrow" size={13} />
      </a>
      {selected ? (
        <>
          <div className="compatibility-score">
            <div>
              <p>{crop.name}</p>
              <h3>
                {!crop.eligible
                  ? "Outside your current settings"
                  : fit === "strong"
                    ? "Strong"
                    : fit === "moderate"
                      ? "Moderate"
                      : "Low"}
                {crop.eligible && " illustrative fit"}
              </h3>
            </div>
            <strong>
              {crop.score}
              <span>%</span>
            </strong>
          </div>
          <div className="score-track">
            <span style={{ width: `${crop.score}%` }} />
          </div>
          <p className="compatibility-explanation">
            {crop.eligible
              ? "This sample score follows your five priorities and climate scenario. It does not predict profit or evaluate NASA observations or regional agronomic rules."
              : crop.reasons.join(" ")}
          </p>
          <p className="local-documents">
            <Icon name="file" size={15} />
            {pdfCount
              ? `${pdfCount} PDF${pdfCount > 1 ? "s" : ""} selected locally · not parsed or used in scores`
              : "No documents selected · optional"}
          </p>
          <div className="alternatives-heading">
            <h3>Recommended alternatives</h3>
            <span>
              {preview.eligible.filter((item) => item.id !== cropId).length}{" "}
              matching · demo
            </span>
          </div>
          <div className="crop-alternatives">
            {preview.eligible
              .filter((item) => item.id !== cropId)
              .slice(0, 3)
              .map((item) => (
                <button
                  type="button"
                  key={item.id}
                  onClick={() => onSelectCrop(item.id)}
                >
                  <span>
                    <strong>{item.name}</strong>
                    <small>
                      {item.matches[0] ??
                        "Standard demo profit & rotation profile"}
                    </small>
                  </span>
                  <b>{item.score}%</b>
                  <Icon name="arrow" size={15} />
                </button>
              ))}
          </div>
          {preview.eligible.filter((item) => item.id !== cropId).length ===
            0 && (
            <p className="no-crop-alternatives">
              No alternative crop matches these settings. Adjust the five
              priorities or reset them to 50.
            </p>
          )}
          <p className="preview-limit">
            Rankings update locally. The demo rotation check only excludes an
            exact repeat of the last entered crop. Use the rotation planner
            below for the engine response and its limitations.
          </p>
        </>
      ) : (
        <div className="compatibility-empty">
          <Icon name="leaf" size={28} />
          <h3>Start with your field</h3>
          <p>
            Draw a boundary or use a point on the map to explore this
            illustrative crop preview.
          </p>
        </div>
      )}
    </section>
  );
}
