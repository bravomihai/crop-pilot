import type { RecommendationResult } from "@fieldshift/contracts";
import PlanCard from "./plan-card";
import Notice from "./ui/notice";

export default function RecommendationResults({
  result,
  busy,
  error,
}: {
  result?: RecommendationResult;
  busy: boolean;
  error: string;
}) {
  return (
    <section
      className="results"
      id="results"
      aria-labelledby="results-title"
      aria-busy={busy}
    >
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
            <span className="empty-state-symbol" aria-hidden="true">↗</span>
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
        <>
          {result.mode === "demo" && (
            <Notice title="Demo · fictional results" tone="warning">
              The crops, dates, and explanations are examples. They are not
              agronomic recommendations calculated for your field.
            </Notice>
          )}
          {result.status !== "complete" && (
            <Notice
              title={result.status === "limited"
                ? "Fewer alternatives available"
                : "Insufficient data"}
              tone="warning"
            >
              {result.status === "limited"
                ? "Fewer than three alternatives are available. Review the missing data and assumptions below."
                : "The available data cannot support any plans. Review the missing information before trying again."}
            </Notice>
          )}
          {result.plans.length > 0 && (
            <div className="plans">
              {result.plans.map((plan, index) => (
                <PlanCard key={plan.id} plan={plan} number={index + 1} />
              ))}
            </div>
          )}
          <div className="result-context">
            <section aria-labelledby="assumptions-title">
              <h3 id="assumptions-title">Assumptions</h3>
              {result.assumptions.length ? (
                <ul>{result.assumptions.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}</ul>
              ) : <p>No additional assumptions are reported.</p>}
            </section>
            <section aria-labelledby="gaps-title">
              <h3 id="gaps-title">Missing data</h3>
              {result.data_gaps.length ? (
                <ul>{result.data_gaps.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}</ul>
              ) : <p>No missing data is reported in this response.</p>}
            </section>
          </div>
          <details className="source-details">
            <summary>Sources and result details</summary>
            {result.sources.length ? (
              <ul>{result.sources.map((source) => (
                <li key={source.id}>
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {source.title}
                      <span className="sr-only"> (opens in a new tab)</span>
                    </a>
                  ) : source.title}
                  {source.resolution && ` · ${source.resolution}`}
                </li>
              ))}</ul>
            ) : <p>No sources are reported in this response.</p>}
            <p className="request-id">
              Request reference: {result.request_id}
            </p>
          </details>
          <p className="result-disclaimer">{result.disclaimer}</p>
        </>
      )}
    </section>
  );
}
