import type { RotationPlan } from "@fieldshift/contracts";
import {
  bareGaps,
  DAY,
  formatDate,
  timelineData,
  utcDate,
} from "@/lib/chart-data";

export default function RotationTimeline({
  plans,
  baseline,
  availableFrom,
}: {
  plans: RotationPlan[];
  baseline?: RotationPlan;
  /** The request's availability date: the empty period before each first crop is shown. */
  availableFrom?: string;
}) {
  const rows = [
    ...(baseline ? [{ plan: baseline, baseline: true }] : []),
    ...plans.map((plan) => ({ plan, baseline: false })),
  ];
  const axis = timelineData(
    rows.map(({ plan }) => plan),
    availableFrom,
  );
  if (!axis) return null;
  return (
    <section className="analysis-chart" aria-labelledby="timeline-title">
      <h3 id="timeline-title">Rotation calendar</h3>
      <p className="chart-legend">
        Shared monthly axis · light segment: sowing window · labelled bar:
        growing period through harvest · hatched gap: bare soil, including the
        wait before the first crop · dashed row: current rotation.
      </p>
      <div
        className="timeline-scroll"
        tabIndex={0}
        role="region"
        aria-label="Rotation timelines. Scroll horizontally to read all months."
      >
        <div
          className="timeline-content"
          style={{ minWidth: Math.max(720, axis.months.length * 28) }}
        >
          <div className="timeline-axis">
            {axis.months.map((month, index) => (
              <div
                className="timeline-tick"
                key={month.date}
                style={{ left: `${axis.percent(month.date)}%` }}
              >
                <b>{index === 0 || month.month === "Jan" ? month.year : ""}</b>
                <span>{month.month}</span>
              </div>
            ))}
          </div>
          {rows.map(({ plan, baseline }, index) => (
            <div
              className={`timeline-row chart-tone-${index} ${baseline ? "timeline-baseline" : ""}`}
              key={`${baseline}-${plan.id}`}
            >
              <h4>{baseline ? "Your current rotation" : plan.label}</h4>
              <div
                className="timeline-track"
                style={{ backgroundSize: `${100 / axis.months.length}% 100%` }}
              >
                {bareGaps(plan, availableFrom).map((gap) => (
                  <div
                    className="timeline-gap unknown-pattern"
                    key={gap.start}
                    style={{
                      left: `${axis.percent(gap.start)}%`,
                      width: `${axis.percent(gap.end) - axis.percent(gap.start)}%`,
                    }}
                    title={
                      gap.initial
                        ? `Field empty before the first crop${gap.long ? ", consider a cover crop" : ""}`
                        : gap.long
                          ? "Bare soil, consider a cover crop"
                          : "Gap between crops"
                    }
                  >
                    {gap.long && (
                      <span>
                        {gap.initial
                          ? "Empty before the first crop, consider a cover crop"
                          : "Bare soil, consider a cover crop"}
                      </span>
                    )}
                  </div>
                ))}
                {plan.steps.map((step) => {
                  const start = utcDate(step.sowing_window.start);
                  const end = utcDate(step.harvest_window.end) + DAY;
                  return (
                    <div
                      className="timeline-crop"
                      key={step.order}
                      style={{
                        left: `${axis.percent(start)}%`,
                        width: `${axis.percent(end) - axis.percent(start)}%`,
                      }}
                      title={`${step.crop_name}: sowing ${formatDate(step.sowing_window.start)}–${formatDate(step.sowing_window.end)}; harvest ${formatDate(step.harvest_window.start)}–${formatDate(step.harvest_window.end)}`}
                    >
                      <span
                        className="timeline-sowing"
                        style={{
                          width: `${((utcDate(step.sowing_window.end) + DAY - start) / (end - start)) * 100}%`,
                        }}
                      />
                      <strong>
                        {step.order}. {step.crop_name}
                      </strong>
                    </div>
                  );
                })}
              </div>
              <ul className="sr-only">
                {plan.steps.map((step) => (
                  <li key={step.order}>
                    {step.crop_name}: sowing{" "}
                    {formatDate(step.sowing_window.start)} to{" "}
                    {formatDate(step.sowing_window.end)}; harvest{" "}
                    {formatDate(step.harvest_window.start)} to{" "}
                    {formatDate(step.harvest_window.end)}.
                  </li>
                ))}
                {bareGaps(plan, availableFrom)
                  .filter((gap) => gap.long)
                  .map((gap) => (
                    <li key={gap.start}>
                      {gap.initial
                        ? "Field empty before the first crop, consider a cover crop."
                        : "Bare soil, consider a cover crop."}{" "}
                      {new Date(gap.start).toISOString().slice(0, 10)} to{" "}
                      {new Date(gap.end - DAY).toISOString().slice(0, 10)}.
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
