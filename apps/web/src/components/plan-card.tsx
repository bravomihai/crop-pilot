import type { RotationPlan } from "@croppilot/contracts";
import ScoreMeters from "./charts/score-meters";
import { firstSentence } from "@/lib/result-glance";
const date = (value: string) =>
  new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
export default function PlanCard({
  plan,
  number,
  baseline = false,
}: {
  plan: RotationPlan;
  number?: number;
  baseline?: boolean;
}) {
  return (
    <article className={baseline ? "plan baseline-plan" : "plan"}>
      <p className="eyebrow">
        {baseline
          ? "BASELINE · NOT COUNTED AS AN ALTERNATIVE"
          : `ALTERNATIVE ${String(number).padStart(2, "0")}`}
      </p>
      <h3>{baseline ? "Your current rotation" : plan.label}</h3>
      {baseline && <p>{plan.label}</p>}
      <ol className="sequence">
        {plan.steps.map((step) => (
          <li key={step.order}>
            <span className="crop-order">Crop {step.order}</span>
            <strong>{step.crop_name}</strong>
            <span>
              Sowing: {date(step.sowing_window.start)} –{" "}
              {date(step.sowing_window.end)}
            </span>
            <span>
              Harvest: {date(step.harvest_window.start)} –{" "}
              {date(step.harvest_window.end)}
            </span>
          </li>
        ))}
      </ol>
      <ScoreMeters scores={plan.scores} baseline={baseline} />
      <p className="plan-summary">{firstSentence(plan.explanation)}</p>
      <p className="confidence">
        Confidence level:{" "}
        {{ low: "low", medium: "medium", high: "high" }[plan.confidence]}
      </p>
      {baseline &&
        plan.violations !== undefined &&
        (plan.violations.length > 0 ? (
          <div className="baseline-violations">
            <h4>Rules your current rotation breaks</h4>
            <ul>
              {plan.violations.map((text, index) => (
                <li key={index}>{text}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="baseline-no-violations">
            No rule violations were reported.
          </p>
        ))}
      <details className="plan-why">
        <summary>
          {baseline ? "How your rotation scores" : "Why this plan?"} Benefits,
          risks and checks
        </summary>
        <p>{plan.explanation}</p>
        <h4>Benefits</h4>
        <ul>
          {plan.benefits.map((text, i) => (
            <li key={i}>{text}</li>
          ))}
        </ul>
        <h4>Trade-offs and risks</h4>
        <ul>
          {plan.tradeoffs.map((text, i) => (
            <li key={i}>{text}</li>
          ))}
        </ul>
        <h4>Why each crop</h4>
        <ul>
          {plan.steps.map((step) => (
            <li key={step.order}>
              <strong>{step.crop_name}:</strong> {step.reason}
            </li>
          ))}
        </ul>
        {plan.local_checks !== undefined && (
          <div className="local-checks">
            <h4>Check locally before you decide</h4>
            {plan.local_checks.length ? (
              <ul>
                {plan.local_checks.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            ) : (
              <p>No additional local checks were supplied.</p>
            )}
          </div>
        )}
      </details>
    </article>
  );
}
