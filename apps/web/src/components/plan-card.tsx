import type { RotationPlan } from "@fieldshift/contracts";
const date = (value: string) =>
  new Intl.DateTimeFormat("ro-RO", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
export default function PlanCard({ plan }: { plan: RotationPlan }) {
  return (
    <article className="plan">
      <h3>{plan.label}</h3>
      <p>{plan.explanation}</p>
      <ol className="sequence">
        {plan.steps.map((step) => (
          <li key={step.order}>
            <strong>{step.crop_name}</strong>
            <span>
              Semănat: {date(step.sowing_window.start)} –{" "}
              {date(step.sowing_window.end)}
            </span>
            <span>
              Recoltare: {date(step.harvest_window.start)} –{" "}
              {date(step.harvest_window.end)}
            </span>
            <small>{step.reason}</small>
          </li>
        ))}
      </ol>
      <h4>Avantaje</h4>
      <ul>
        {plan.benefits.map((text, i) => (
          <li key={i}>{text}</li>
        ))}
      </ul>
      <h4>Compromisuri și verificări</h4>
      <ul>
        {plan.tradeoffs.map((text, i) => (
          <li key={i}>{text}</li>
        ))}
      </ul>
      <p className="muted">
        Încredere:{" "}
        {{ low: "scăzută", medium: "medie", high: "ridicată" }[plan.confidence]}
      </p>
    </article>
  );
}
