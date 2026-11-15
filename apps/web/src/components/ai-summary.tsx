"use client";
import { useEffect, useRef, useState } from "react";
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

export default function AiSummary({ result }: { result: RecommendationResult }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  useEffect(() => {
    setSummary(null);
    setError("");
    return () => request.current?.abort();
  }, [result]);
  if (result.mode !== "computed" || !result.plans.length) return null;
  const names = new Map([
    ...result.plans.map((plan) => [plan.id, plan.label] as const),
    ...(result.baseline ? [[result.baseline.id, "Your current rotation"] as const] : []),
  ]);

  async function run() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/summary", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ result: summaryPayload(result) }),
        signal: controller.signal,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || "The summary is not available right now.");
      setSummary(body as Summary);
    } catch (caught) {
      if (!controller.signal.aborted)
        setError(caught instanceof Error ? caught.message : "The summary is not available right now.");
    } finally {
      if (request.current === controller) setBusy(false);
    }
  }

  return (
    <section className="ai-summary" aria-labelledby="ai-summary-heading" aria-busy={busy}>
      <div className="evidence-heading">
        <h3 id="ai-summary-heading">AI summary of the calculated results</h3>
        <div className="ai-summary-controls">
          <button type="button" className="ai-summary-button" onClick={run} disabled={busy}>
            {busy ? "Writing the summary…" : "Summarise in plain words"}
          </button>
        </div>
      </div>
      {error && <p className="ai-summary-error" role="status">{error}</p>}
      {summary && (
        <div className="ai-summary-body" lang="en">
          <p className="ai-summary-headline">{summary.headline}</p>
          {summary.plans.map((plan) => (
            <article key={plan.id}>
              <h4>{names.get(plan.id) ?? plan.id}</h4>
              <p>{plan.in_short}</p>
              <p><strong>Why:</strong> {plan.why}</p>
              {plan.watch_out.length > 0 && (
                <p><strong>Watch out for:</strong> {plan.watch_out.join(" ")}</p>
              )}
              {plan.ask_your_agronomist.length > 0 && (
                <p><strong>Ask your agronomist:</strong> {plan.ask_your_agronomist.join(" ")}</p>
              )}
            </article>
          ))}
          <p className="evidence-note">Written by AI from the calculated results. Numbers are checked against those results; the detailed plans remain the reference.</p>
        </div>
      )}
    </section>
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
