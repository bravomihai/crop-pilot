import type {
  RecommendationResult,
  RecommendationRequest,
} from "@croppilot/contracts";
import PlanCard from "./plan-card";
import Notice from "./ui/notice";
import ScoreComparison from "./charts/score-comparison";
import RotationTimeline from "./charts/rotation-timeline";
import ResultsWhatIf from "./results-what-if";
import { ClimateCard, PlanReplay } from "./results-evidence";
import Glossary from "./glossary";
import { PrintSheetButton } from "./ai-summary";
import ResultsAtAGlance, { BackToSummary } from "./results-at-a-glance";
import RequestSummary from "./request-summary";
import SurvivalMode from "./survival-mode";

function formatWindow(window: { start: string; end: string }) {
  const format = (value: string) =>
    new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" })
      .format(new Date(`${value}T12:00:00`));
  return `${format(window.start)} – ${format(window.end)}`;
}

export default function RecommendationResults({
  result,
  busy,
  error,
  request,
  onRecalculate,
  onCancel,
}: {
  result?: RecommendationResult;
  busy: boolean;
  error: string;
  request?: RecommendationRequest;
  onRecalculate?: (scenario: RecommendationRequest["scenario"]) => void;
  onCancel?: () => void;
}) {
  return (
    <section className="results" id="results" aria-labelledby="results-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">YOUR ALTERNATIVES</p>
          <h2 id="results-title">
            {result
              ? `Plans for ${result.location.name ?? "the selected point"}`
              : "A place for your next plan."}
          </h2>
        </div>
        {result && (
          <span className="count-badge">{result.plans.length} / 3 plans</span>
        )}
      </div>
      <p className="sr-only" role="status">
        {busy
          ? "Preparing results. You can stop waiting using the form."
          : result
            ? `${result.plans.length} plans available.`
            : ""}
      </p>
      {error && (
        <Notice title="We couldn't complete your request" tone="error" announce>
          {error}
        </Notice>
      )}
      {!result && (
        <div className="empty-state">
          {busy ? (
            <span className="spinner spinner--large" aria-hidden="true" />
          ) : (
            <span className="empty-state-symbol" aria-hidden="true">
              ↗
            </span>
          )}
          <h3>
            {busy
              ? "Preparing your comparison…"
              : error
                ? "Plans aren't available yet"
                : "Your plans will appear here"}
          </h3>
          <p>
            {busy
              ? "Your form entries are retained while the planner responds."
              : error
                ? "Check the message above and try again. Your entries are still in the form."
                : "Submit the planning form to see the available rotation alternatives."}
          </p>
        </div>
      )}
      {result && (
        <div
          className={busy ? "result-body is-recalculating" : "result-body"}
          aria-busy={busy}
        >
          <RequestSummary request={request} result={result} />
          {result.mode === "demo" && (
            <Notice title="Demo · fictional results">
              The crops, dates, and explanations are examples. They are not
              agronomic recommendations calculated for your field. Selected
              crops are not assessed in demo mode.
            </Notice>
          )}
          {result.land_cover && (
            <Notice
              title={
                result.land_cover.status === "incompatible"
                  ? "Field may not be suitable for planting"
                  : "Land-cover information"
              }
              tone={result.land_cover.status === "incompatible" ? "warning" : "info"}
              announce
            >
              {result.land_cover.message}
            </Notice>
          )}
          {result.status !== "complete" && result.land_cover?.status !== "incompatible" && (
            <Notice
              title={
                result.status === "limited"
                  ? "Fewer alternatives available"
                  : "Insufficient data"
              }
            >
              {result.status === "limited"
                ? "Fewer than three alternatives are available. See “How this was calculated” below for what is missing."
                : "No crop plans could be generated from the available data and constraints. Review the missing information below."}
            </Notice>
          )}
          {result.mode === "computed" && result.crop_assessment && (
            <section aria-labelledby="crop-comparison-title" className="crop-comparison">
              <div className="crop-comparison-heading">
                <p className="eyebrow">START HERE</p>
                <h3 id="crop-comparison-title">
                  {result.crop_assessment.selected.length ? "Your crop choices" : "Crops to consider"}
                </h3>
                <p>Explore what the available data suggests for this field.</p>
              </div>
              {result.crop_assessment.selected.length > 0 && (
                <div className="crop-assessment-list">
                  {result.crop_assessment.selected.map((crop) => (
                    <article className="crop-assessment-card" key={crop.crop_id}>
                      <div className="crop-assessment-top">
                        <h4>{crop.crop_name}</h4>
                        <span className={`crop-assessment-status crop-assessment-status--${crop.status}`}>
                          {crop.status === "not_recommended" ? "Not recommended" :
                            crop.status === "uncertain" ? "Needs checking" : "Assessment available"}
                        </span>
                      </div>
                      <p className="crop-assessment-message">{crop.message}</p>
                      {(crop.score !== null || crop.sowing_window || crop.harvest_window) && (
                        <dl className="crop-assessment-details">
                          {crop.score !== null && <div><dt>Estimated potential</dt><dd>{Math.round(crop.score * 100)} / 100</dd></div>}
                          {crop.sowing_window && <div><dt>Next sowing</dt><dd>{formatWindow(crop.sowing_window)}</dd></div>}
                          {crop.harvest_window && <div><dt>Harvest</dt><dd>{formatWindow(crop.harvest_window)}</dd></div>}
                        </dl>
                      )}
                    </article>
                  ))}
                </div>
              )}
              <div className="crop-alternative-section">
                <h4>{result.crop_assessment.selected.length ? "Other crops to consider" : "Suggested crops"}</h4>
                {result.crop_assessment.alternatives.length > 0 && (
                  <p className="crop-alternative-intro">Compare estimated potential and check suitability locally before planting.</p>
                )}
                {result.crop_assessment.alternatives.length > 0 ? (
                  <div className="crop-alternative-list">
                    {result.crop_assessment.alternatives.map((crop) => (
                      <article className="crop-alternative-card" key={crop.crop_id}>
                        <div className="crop-assessment-top">
                          <h5>{crop.crop_name}</h5>
                          <span>{Math.round(crop.score * 100)} / 100</span>
                        </div>
                        <p>Estimated potential</p>
                        {crop.sowing_window && <p>Next sowing: {formatWindow(crop.sowing_window)}</p>}
                        {crop.harvest_window && <p>Harvest: {formatWindow(crop.harvest_window)}</p>}
                      </article>
                    ))}
                  </div>
                ) : (
                  <p>No other comparable crops are available from this assessment.</p>
                )}
              </div>
              <p className="crop-assessment-disclaimer">{result.crop_assessment.disclaimer}</p>
            </section>
          )}
          <RotationTimeline
            plans={result.plans}
            baseline={result.baseline}
            availableFrom={request?.available_from}
          />
          {result.plans.length > 0 && !result.baseline &&
            (request?.current_rotation?.length ? (
              <p className="baseline-hint">
                Your current rotation could not be evaluated for comparison. See “How
                this was calculated” below for the reason.
              </p>
            ) : (
              <p className="baseline-hint">
                Add your current rotation to compare the plans with what you do
                today.
              </p>
            ))}
          <ResultsAtAGlance result={result} />
          <SurvivalMode result={result} request={request} />
          <section className="plan-details" id="plan-details" tabIndex={-1} aria-labelledby="plan-details-title">
            <h3 id="plan-details-title" className="details-title">The plans in detail</h3>
            {result.baseline && (
              <div className="baseline-container">
                <PlanCard plan={result.baseline} baseline />
              </div>
            )}
            {result.plans.length > 0 && (
              <div className="plans">
                {result.plans.map((plan, index) => (
                  <PlanCard key={plan.id} plan={plan} number={index + 1} />
                ))}
              </div>
            )}
            <ScoreComparison plans={result.plans} baseline={result.baseline} />
            <PlanReplay result={result} scenario={request?.scenario} />
            <ClimateCard result={result} />
            {result.plans.length > 0 && <BackToSummary />}
          </section>
          {request && onRecalculate && (
            <details className="result-scenario">
              <summary>Explore a different climate scenario</summary>
              <ResultsWhatIf
                request={request}
                busy={busy}
                onRecalculate={onRecalculate}
                onCancel={onCancel}
              />
            </details>
          )}
          <details className="how-calculated">
            <summary>How this was calculated: assumptions, all missing data and sources</summary>
            <div className="result-context">
              <section aria-labelledby="assumptions-title">
                <h3 id="assumptions-title">Assumptions</h3>
                {result.assumptions.length ? (
                  <ul>
                    {result.assumptions.map((text, index) => (
                      <li key={index}>{text}</li>
                    ))}
                  </ul>
                ) : (
                  <p>No additional assumptions are reported.</p>
                )}
              </section>
              <section aria-labelledby="gaps-title">
                <h3 id="gaps-title">Missing data</h3>
                {result.data_gaps.length ? (
                  <ul>
                    {result.data_gaps.map((text, index) => (
                      <li key={index}>{text}</li>
                    ))}
                  </ul>
                ) : (
                  <p>No missing data is reported in this response.</p>
                )}
              </section>
            </div>
            <section className="source-details" aria-labelledby="sources-title">
              <h3 id="sources-title">Sources</h3>
              {result.sources.length ? (
                <ul>
                  {result.sources.map((source) => (
                    <li key={source.id}>
                      {source.url ? (
                        <a href={source.url} target="_blank" rel="noreferrer">
                          {source.title}
                          <span className="sr-only"> (opens in a new tab)</span>
                        </a>
                      ) : (
                        source.title
                      )}
                      {source.resolution && ` · ${source.resolution}`}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No sources are reported in this response.</p>
              )}
              <p className="request-id">Request reference: {result.request_id}</p>
            </section>
            {result.plans.length > 0 && <BackToSummary />}
          </details>
          <Glossary />
          <p className="result-disclaimer">{result.disclaimer}</p>
          <div className="results-end">
            {result.plans.length > 0 && <BackToSummary />}
            {result.mode === "computed" && result.plans.length > 0 && <PrintSheetButton />}
          </div>
        </div>
      )}
    </section>
  );
}
