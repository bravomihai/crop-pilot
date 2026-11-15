"use client";
import type { MouseEvent } from "react";
import type { RecommendationResult } from "@croppilot/contracts";
import {
  compareWithCurrent,
  cropsOf,
  keyChecks,
  keyGaps,
  mainRisks,
  strongest,
} from "@/lib/result-glance";
import PlainWordsSummary, { PrintSheetButton } from "./ai-summary";

/**
 * Scrolls only the results list to a section. A plain anchor jump also scrolls the
 * panel around the list, which pushed the panel header (full screen, edit) out of view.
 */
function jumpTo(event: MouseEvent<HTMLAnchorElement>, id: string) {
  const target = document.getElementById(id);
  const list = target?.closest<HTMLElement>(".map-results-scroll");
  if (!target || !list) return;
  event.preventDefault();
  const top = target.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop - 12;
  const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  list.scrollTo({ top, behavior: smooth ? "smooth" : "auto" });
  target.focus({ preventScroll: true });
}

const date = (value: string) =>
  new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric" }).format(
    new Date(`${value}T12:00:00`),
  );

/**
 * The result in a few lines, at the top of the results. The facts below come straight from
 * the result; a plain-words explanation is added above them when the server can write one.
 */
export default function ResultsAtAGlance({ result }: { result: RecommendationResult }) {
  const [best, ...others] = result.plans;
  if (!best) return null;
  const comparison = compareWithCurrent(best, result.baseline);
  const better = comparison.filter((item) => item.plan > item.current);
  const worse = comparison.filter((item) => item.plan < item.current);
  const risks = mainRisks(best);
  const checks = keyChecks(best, others);
  const gaps = keyGaps(result);
  const first = best.steps[0];
  const list = (items: typeof comparison) =>
    items.map((item) => `${item.label.toLowerCase()} (${item.plan} vs ${item.current})`).join(", ");
  return (
    <section className="at-a-glance" id="results-summary" tabIndex={-1} aria-labelledby="at-a-glance-title">
      <p className="eyebrow">AT A GLANCE</p>
      <h3 id="at-a-glance-title">
        Best match: <span className="glance-crops">{cropsOf(best)}</span>
      </h3>
      {first && (
        <p className="glance-start">
          Start by sowing {first.crop_name.toLowerCase()} between {date(first.sowing_window.start)} and{" "}
          {date(first.sowing_window.end)}.
        </p>
      )}
      <PlainWordsSummary result={result} />
      <dl className="glance-facts">
        {result.baseline && comparison.length > 0 && (
          <div>
            <dt>Compared with your current rotation</dt>
            <dd>
              {better.length > 0 && <>Better on {list(better)}. </>}
              {worse.length > 0 && <>Worse on {list(worse)}. </>}
              {!better.length && !worse.length && "The same scores on every criterion. "}
              <span className="glance-note">Scores out of 100.</span>
            </dd>
          </div>
        )}
        {risks.length > 0 && (
          <div>
            <dt>Main risk</dt>
            <dd>
              <ul>
                {risks.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            </dd>
          </div>
        )}
        {checks.length > 0 && (
          <div>
            <dt>Before you decide</dt>
            <dd>
              <ul>
                {checks.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            </dd>
          </div>
        )}
        {others.length > 0 && (
          <div>
            <dt>Other options</dt>
            <dd>
              <ul>
                {others.map((plan) => {
                  const top = strongest(plan);
                  return (
                    <li key={plan.id}>
                      <strong>{cropsOf(plan)}</strong>
                      {top && <> · strongest on {top.label.toLowerCase()} ({top.value}/100)</>}
                    </li>
                  );
                })}
              </ul>
            </dd>
          </div>
        )}
        {gaps.length > 0 && (
          <div>
            <dt>Good to know</dt>
            <dd>
              <ul>
                {gaps.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            </dd>
          </div>
        )}
      </dl>
      <div className="glance-actions">
        <a className="glance-link" href="#plan-details" onClick={(event) => jumpTo(event, "plan-details")}>
          See the plans in detail
        </a>
        {result.mode === "computed" && <PrintSheetButton />}
      </div>
    </section>
  );
}
