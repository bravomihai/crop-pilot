import type { RotationPlan } from "@fieldshift/contracts";
const date = (value: string) =>
  new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
export default function PlanCard({
  plan,
  number,
}: {
  plan: RotationPlan;
  number: number;
}) {
  return (
    <article className="plan">
      <p className="eyebrow">ALTERNATIVE {String(number).padStart(2, "0")}</p>
      <h3>{plan.label}</h3>
      <p>{plan.explanation}</p>
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
            <small>{step.reason}</small>
          </li>
        ))}
      </ol>
      <h4>Benefits</h4>
      <ul>
        {plan.benefits.map((text, i) => (
          <li key={i}>{text}</li>
        ))}
      </ul>
      <h4>Trade-offs and checks</h4>
      <ul>
        {plan.tradeoffs.map((text, i) => (
          <li key={i}>{text}</li>
        ))}
      </ul>
      <p className="confidence">
        Confidence level:{" "}
        {{ low: "low", medium: "medium", high: "high" }[plan.confidence]}
      </p>
    </article>
  );
}
