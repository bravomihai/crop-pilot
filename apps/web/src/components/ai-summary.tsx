"use client";
import { useEffect, useRef, useState } from "react";
import type { RecommendationResult } from "@fieldshift/contracts";
import { summaryPayload } from "@/lib/summary-payload";

type PlanSummary = {
  id: string;
  in_short: string;
  why: string;
  watch_out: string[];
  ask_your_agronomist: string[];
};
type Summary = { headline: string; plans: PlanSummary[] };

const TEXT = {
  en: {
    button: "Summarise in plain words",
    busy: "Writing the summary…",
    label: "AI summary of the calculated results",
    note: "Written by AI from the results below, without adding facts; every number is checked against the results. The detailed plans stay the reference.",
    why: "Why",
    watch: "Watch out for",
    ask: "Ask your agronomist",
    current: "Your current rotation",
  },
  ro: {
    button: "Rezumat pe înțelesul tuturor",
    busy: "Se scrie rezumatul…",
    label: "Rezumat AI al rezultatelor calculate",
    note: "Scris de AI pe baza rezultatelor de mai jos, fără informații noi; fiecare număr este verificat. Planurile detaliate rămân referința.",
    why: "De ce",
    watch: "Atenție la",
    ask: "Întrebați agronomul",
    current: "Rotația actuală",
  },
} as const;

export default function AiSummary({ result }: { result: RecommendationResult }) {
  const [language, setLanguage] = useState<"en" | "ro">("en");
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
  const t = TEXT[language];
  const names = new Map([
    ...result.plans.map((plan) => [plan.id, plan.label] as const),
    ...(result.baseline ? [[result.baseline.id, t.current] as const] : []),
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
        body: JSON.stringify({ result: summaryPayload(result), language }),
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
        <h3 id="ai-summary-heading">{t.label}</h3>
        <div className="ai-summary-controls">
          <label htmlFor="ai-summary-language">
            <span className="sr-only">Language</span>
            <select id="ai-summary-language" value={language} onChange={(event) => { request.current?.abort(); setBusy(false); setLanguage(event.target.value as "en" | "ro"); setSummary(null); setError(""); }}>
              <option value="en">English</option>
              <option value="ro">Română</option>
            </select>
          </label>
          <button type="button" className="ai-summary-button" onClick={run} disabled={busy}>
            {busy ? t.busy : t.button}
          </button>
        </div>
      </div>
      {error && <p className="ai-summary-error" role="status">{error}</p>}
      {summary && (
        <div className="ai-summary-body" lang={language}>
          <p className="ai-summary-headline">{summary.headline}</p>
          {summary.plans.map((plan) => (
            <article key={plan.id}>
              <h4>{names.get(plan.id) ?? plan.id}</h4>
              <p>{plan.in_short}</p>
              <p><strong>{t.why}:</strong> {plan.why}</p>
              {plan.watch_out.length > 0 && (
                <p><strong>{t.watch}:</strong> {plan.watch_out.join(" ")}</p>
              )}
              {plan.ask_your_agronomist.length > 0 && (
                <p><strong>{t.ask}:</strong> {plan.ask_your_agronomist.join(" ")}</p>
              )}
            </article>
          ))}
          <p className="evidence-note">{t.note}</p>
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
