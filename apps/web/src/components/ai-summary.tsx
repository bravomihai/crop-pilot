"use client";
import { useEffect, useState } from "react";
import type { RecommendationResult } from "@croppilot/contracts";
import { summaryPayload } from "@/lib/summary-payload";

type PlanSummary = {
  id: string;
  in_short: string;
  why: string;
  watch_out: string[];
  ask_your_agronomist: string[];
};
type Summary = { headline: string; plans: PlanSummary[] };
type State =
  | { status: "idle" | "loading" | "unavailable" }
  | { status: "ready"; summary: Summary };

/**
 * Asks the server for a plain-words explanation of a calculated result as soon as it is
 * shown. When the server has no AI set up, or the explanation fails its checks, the page
 * simply keeps the calculated texts: nothing is shown in its place.
 */
function usePlainWords(result: RecommendationResult): State {
  const [state, setState] = useState<State>({ status: "idle" });
  const eligible = result.mode === "computed" && result.plans.length > 0;
  useEffect(() => {
    if (!eligible) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ status: "loading" });
    fetch("/api/summary", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ result: summaryPayload(result) }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const summary = (await response.json()) as Summary;
        if (!controller.signal.aborted) setState({ status: "ready", summary });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: "unavailable" });
      });
    return () => controller.abort();
  }, [result, eligible]);
  return state;
}

/** The explanation in plain words, inside the "At a glance" card. */
export default function PlainWordsSummary({ result }: { result: RecommendationResult }) {
  const state = usePlainWords(result);
  if (state.status === "loading")
    return (
      <div className="plain-words is-loading" role="status">
        <span className="plain-words-skeleton" aria-hidden="true" />
        <span className="plain-words-skeleton short" aria-hidden="true" />
        <span className="sr-only">Writing an explanation of these results…</span>
      </div>
    );
  if (state.status !== "ready") return null;
  const { summary } = state;
  const names = new Map<string, string>([
    ...result.plans.map((plan, index) => [plan.id, `Plan ${index + 1}`] as [string, string]),
    ...(result.baseline ? [[result.baseline.id, "Your current rotation"] as [string, string]] : []),
  ]);
  const plans = summary.plans.filter((plan) => names.has(plan.id));
  const extra = plans.some((plan) => plan.watch_out.length || plan.ask_your_agronomist.length);
  return (
    <div className="plain-words" lang="en">
      <p className="plain-words-headline">{summary.headline}</p>
      {plans.length > 0 && (
        <ul className="plain-words-plans">
          {plans.map((plan) => (
            <li key={plan.id}>
              <strong>{names.get(plan.id)}:</strong> {plan.in_short} {plan.why}
            </li>
          ))}
        </ul>
      )}
      {extra && (
        <details className="plain-words-more">
          <summary>Risks and questions for your agronomist, explained</summary>
          {plans.map((plan) =>
            plan.watch_out.length || plan.ask_your_agronomist.length ? (
              <div key={plan.id}>
                <h4>{names.get(plan.id)}</h4>
                {plan.watch_out.length > 0 && (
                  <p>
                    <strong>Watch out for:</strong> {plan.watch_out.join(" ")}
                  </p>
                )}
                {plan.ask_your_agronomist.length > 0 && (
                  <p>
                    <strong>Ask your agronomist:</strong> {plan.ask_your_agronomist.join(" ")}
                  </p>
                )}
              </div>
            ) : null,
          )}
        </details>
      )}
    </div>
  );
}

/** Opens the browser's print dialog; print styles keep only the results, as a sheet to share. */
export function PrintSheetButton() {
  return (
    <button type="button" className="print-sheet-button" onClick={() => window.print()}>
      Print for your agronomist
    </button>
  );
}
