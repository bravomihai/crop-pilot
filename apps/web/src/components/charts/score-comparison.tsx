import type { RotationPlan } from "@croppilot/contracts";
import { SCORE_CRITERIA, scorePercent } from "@/lib/chart-data";

export default function ScoreComparison({
  plans,
  baseline,
}: {
  plans: RotationPlan[];
  baseline?: RotationPlan;
}) {
  const entries = [
    ...(baseline ? [{ plan: baseline, baseline: true }] : []),
    ...plans.map((plan) => ({ plan, baseline: false })),
  ];
  if (!entries.some(({ plan }) => plan.scores !== undefined)) return null;
  return (
    <section
      className="analysis-chart score-comparison"
      aria-labelledby="score-comparison-title"
    >
      <h3 id="score-comparison-title">Compare criterion scores</h3>
      <p className="chart-legend">
        Higher is better · dashed outline: current rotation · hatching: Unknown
        · productivity is relative potential, not a yield or profit forecast.
      </p>
      <div className="score-axis" aria-hidden="true">
        <span>0</span>
        <span>25</span>
        <span>50</span>
        <span>75</span>
        <span>100</span>
      </div>
      {SCORE_CRITERIA.map(([key, title]) => (
        <div className="criterion-group" key={key}>
          <h4>{title}</h4>
          {entries.map(({ plan, baseline }, index) => {
            const value = scorePercent(plan.scores?.[key]);
            const label = baseline ? "Your current rotation" : plan.label;
            return (
              <div
                className={`comparison-row chart-tone-${index} ${baseline ? "comparison-baseline" : ""}`}
                key={`${baseline ? "baseline" : "plan"}-${plan.id}`}
              >
                <span className="comparison-label">{label}</span>
                <div
                  className={`comparison-track ${value === null ? "unknown-pattern" : ""}`}
                  role="img"
                  aria-label={`${title}, ${label}: ${value === null ? "Unknown" : `${value} out of 100`}`}
                >
                  {value !== null && <span style={{ width: `${value}%` }} />}
                </div>
                <strong>{value === null ? "Unknown" : `${value} / 100`}</strong>
              </div>
            );
          })}
        </div>
      ))}
    </section>
  );
}
