"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { RecommendationRequest, RecommendationResult } from "@fieldshift/contracts";
import { formatDate } from "@/lib/chart-data";
import {
  buildChallenges,
  decisionQuestion,
  defaultMine,
  revealChoice,
  sequenceText,
  SURVIVAL_DISCLAIMER,
  type Challenge,
  type ChallengeId,
  type EvidenceMetric,
  type Outcome,
  type Reveal,
} from "@/lib/survival";

type Available = Extract<Challenge, { available: true }>;

const CRITERION_LABEL = { water: "Water", climate: "Climate", productivity: "Productivity" } as const;

function ChallengeIcon({ id }: { id: ChallengeId }) {
  const common = { width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
  if (id === "drought")
    return (
      <svg {...common}>
        <circle cx="12" cy="8" r="3.5" />
        <path d="M12 1.5v1.5M5.5 8H4M20 8h-1.5M7.4 3.4l1 1M16.6 3.4l-1 1" />
        <path d="M3 17h18M5 21l3-4 2 2 3-3M15 21l2-4 3 4" />
      </svg>
    );
  if (id === "heat")
    return (
      <svg {...common}>
        <path d="M10 14.5V4a2 2 0 1 1 4 0v10.5a4 4 0 1 1-4 0Z" />
        <path d="M12 9v7" />
        <path d="M18 5h3M18 9h2" />
      </svg>
    );
  return (
    <svg {...common}>
      <path d="M7 15a4.5 4.5 0 1 1 1.2-8.8A5.5 5.5 0 0 1 18.5 9 3.5 3.5 0 0 1 18 15H7Z" />
      <path d="M8 18.5 7 21M12 18.5 11 21M16 18.5 15 21" />
    </svg>
  );
}

/** Whole numbers as they are, anything else to one decimal (no floating-point noise). */
const num = (value: number) => (Number.isInteger(value) ? String(value) : value.toFixed(1));
const metricText = (metric: EvidenceMetric) =>
  metric.value === null ? "Unknown" : `${num(metric.value)} ${metric.unit}`;

function exposureText(challenge: Available, outcome: Outcome) {
  if (!outcome.season) return null;
  if (!outcome.crops.some((crop) => crop.inSummer))
    return `No main crop of this rotation was in the field during April–September ${challenge.year}.`;
  const crop = outcome.exposed;
  if (!crop) return "The engine reported no crop-level values for this season.";
  if (challenge.id === "heat") {
    if (crop.heatDays !== null && crop.heatDays > 0)
      return `Most heat-exposed crop: ${crop.cropName.toLowerCase()}, ${crop.heatDays} day${crop.heatDays === 1 ? "" : "s"} above its own heat threshold during flowering and grain fill.`;
    return crop.climateRisk === null
      ? null
      : `Highest weather risk: ${crop.cropName.toLowerCase()} (${Math.round(crop.climateRisk * 100)} / 100 risk, no heat days above its threshold).`;
  }
  return (
    `Most water-stressed crop: ${crop.cropName.toLowerCase()}, ${Math.round(crop.wrsiPct!)}% of its water need met` +
    (crop.seasonRainMm !== null ? ` (${Math.round(crop.seasonRainMm)} mm of rain in its season).` : ".")
  );
}

function Comparison({ challenge, mine }: { challenge: Available; mine: string }) {
  const criterion = CRITERION_LABEL[challenge.criterion];
  const bestKeys = new Set(challenge.best.map((o) => o.contender.key));
  return (
    <section className="survival-block" aria-labelledby="survival-compare-title">
      <h4 id="survival-compare-title">
        Same season, every rotation: {criterion.toLowerCase()} score in {challenge.year}
      </h4>
      <p className="survival-small">
        Each rotation replayed from the same start, the field free on {formatDate(challenge.fieldFree)}, through the
        weather that followed. The score covers all three crops of that replay, not only the {challenge.year} summer.
        Out of 100, higher is better.
      </p>
      <ul className="survival-rows">
        {challenge.outcomes.map((outcome, index) => {
          const { contender } = outcome;
          const exposure = exposureText(challenge, outcome);
          return (
            <li
              key={contender.key}
              className={`survival-row chart-tone-${index} ${contender.baseline ? "comparison-baseline" : ""}`}
            >
              <div className="survival-row-head">
                <strong>{contender.label}</strong>
                {contender.key === mine && <span className="survival-tag">Your rotation</span>}
                {bestKeys.has(contender.key) && challenge.best.length > 0 && (
                  <span className="survival-tag survival-tag--best">
                    {challenge.best.length > 1 ? "Joint best this season" : "Best this season"}
                  </span>
                )}
                <span className="survival-sequence">{sequenceText(contender.plan)}</span>
              </div>
              <div className="survival-bar">
                <div
                  className={`comparison-track ${outcome.score === null ? "unknown-pattern" : ""}`}
                  role="img"
                  aria-label={`${criterion} score in ${challenge.year}, ${contender.label}: ${outcome.score === null ? "Unknown" : `${outcome.score} out of 100`}`}
                >
                  {outcome.score !== null && <span style={{ width: `${outcome.score}%` }} />}
                </div>
                <strong>{outcome.score === null ? "Unknown" : `${outcome.score} / 100`}</strong>
              </div>
              <p className="survival-small">
                {outcome.season
                  ? (["water", "climate", "productivity"] as const)
                      .map((key) => `${CRITERION_LABEL[key]} ${outcome.seasonScores[key] ?? "unknown"}`)
                      .join(" · ") + ` · confidence ${contender.plan.confidence}`
                  : outcome.missing}
              </p>
              {exposure && <p className="survival-small">{exposure}</p>}
              {outcome.season && outcome.missing && <p className="survival-small">{outcome.missing}</p>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

const VERDICT_TITLE = (reveal: Reveal) => {
  const other = reveal.other?.contender.label;
  if (!reveal.other) return reveal.mine.score === null ? "No score to compare" : "Your rotation led this season";
  if (reveal.verdict === "unknown") return "No fair comparison possible";
  if (reveal.verdict === "equal") return "A draw in this season";
  const points = Math.abs(reveal.difference!);
  const pts = `${points} point${points === 1 ? "" : "s"}`;
  return reveal.verdict === "better" ? `${other} did better by ${pts}` : `${other} did worse by ${pts}`;
};

/** The modelled historical comparison after the farmer's choice. */
export function RevealPanel({ challenge, reveal }: { challenge: Available; reveal: Reveal }) {
  return (
    <div className={`survival-reveal survival-reveal--${reveal.verdict}`}>
      <p className="eyebrow">{reveal.switched ? `You switched to ${reveal.pick.contender.label}` : "You kept your rotation"}</p>
      <h4>{VERDICT_TITLE(reveal)}</h4>
      <p className="survival-takeaway">
        <span className="sr-only">Key takeaway: </span>
        {reveal.takeaway}
      </p>
      {reveal.tradeoffs.length > 0 && (
        <>
          <h5>Trade-offs of {reveal.other!.contender.label}</h5>
          <ul>
            {reveal.tradeoffs.map((text) => (
              <li key={text}>{text.charAt(0).toUpperCase() + text.slice(1)}.</li>
            ))}
          </ul>
        </>
      )}
      {reveal.engineTradeoffs.length > 0 && (
        <>
          <h5>What the recommender notes</h5>
          <ul>
            {reveal.engineTradeoffs.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </>
      )}
      {reveal.unknowns.length > 0 && (
        <ul className="survival-small">
          {reveal.unknowns.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      )}
      <p className="survival-disclaimer">
        {SURVIVAL_DISCLAIMER} One past {challenge.noun} at this point; the next hard season will differ.
      </p>
    </div>
  );
}

function Decision({
  challenge,
  mine,
  setMine,
}: {
  challenge: Available;
  mine: string;
  setMine: (key: string) => void;
}) {
  const [pick, setPick] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const reveal = pick && revealed ? revealChoice(challenge, mine, pick) : null;
  const name = `survival-pick-${challenge.id}`;
  return (
    <section className="survival-block survival-decision" aria-labelledby="survival-decision-title">
      <h4 id="survival-decision-title">Your call</h4>
      {challenge.outcomes.length > 1 && (
        <label className="survival-mine" htmlFor="survival-mine">
          Your rotation
          <select
            id="survival-mine"
            value={mine}
            onChange={(event) => {
              setMine(event.target.value);
              setPick(null);
              setRevealed(false);
            }}
          >
            {challenge.outcomes.map(({ contender }) => (
              <option key={contender.key} value={contender.key}>
                {contender.label}
              </option>
            ))}
          </select>
        </label>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (pick) setRevealed(true);
        }}
      >
        <fieldset>
          <legend>{decisionQuestion(challenge, mine)}</legend>
          {challenge.outcomes.map(({ contender }) => (
            <label key={contender.key} className="survival-choice">
              <input
                type="radio"
                name={name}
                value={contender.key}
                checked={pick === contender.key}
                onChange={() => {
                  setPick(contender.key);
                  setRevealed(false);
                }}
              />
              <span>
                {contender.key === mine ? `Keep ${contender.baseline ? "my current rotation" : contender.label}` : `Switch to ${contender.label}`}
                <small>{sequenceText(contender.plan)}</small>
              </span>
            </label>
          ))}
        </fieldset>
        <button type="submit" className="button button--primary" disabled={!pick}>
          Reveal what happened in {challenge.year}
        </button>
      </form>
      <div aria-live="polite">{reveal && <RevealPanel challenge={challenge} reveal={reveal} />}</div>
    </section>
  );
}

function ChallengeView({ challenge, result, mine, setMine }: { challenge: Available; result: RecommendationResult; mine: string; setMine: (key: string) => void }) {
  const sources = challenge.sourceIds.map((id) => result.sources.find((s) => s.id === id)?.title ?? id);
  return (
    <div className="survival-challenge">
      <section className="survival-block survival-evidence" aria-labelledby="survival-evidence-title">
        <p className="eyebrow">Observed weather · {challenge.title}</p>
        <h4 id="survival-evidence-title" className="survival-headline">
          <span className="survival-year">{challenge.year}</span>
          <span className="survival-figure">
            {metricText(challenge.headline)}
            <small>
              {challenge.headline.label}
              {challenge.headline.typical !== null && ` · typical ${num(challenge.headline.typical)} ${challenge.headline.unit}`}
            </small>
          </span>
        </h4>
        <p>{challenge.why}</p>
        <dl className="survival-metrics">
          {challenge.metrics.map((metric) => (
            <div key={metric.label}>
              <dt>{metric.label}</dt>
              <dd>
                {metricText(metric)}
                {metric.typical !== null && metric.value !== null && <small> typical {num(metric.typical)}</small>}
              </dd>
            </div>
          ))}
        </dl>
        <p className="survival-small">
          Source: {sources.join(", ")} · observed {challenge.period.start}–{challenge.period.end} · calendar-year values for the
          area around the field.
        </p>
      </section>
      <Comparison challenge={challenge} mine={mine} />
      <Decision key={`${challenge.id}-${mine}`} challenge={challenge} mine={mine} setMine={setMine} />
      <section className="survival-block survival-notes" aria-labelledby="survival-notes-title">
        <h4 id="survival-notes-title">What to keep in mind</h4>
        <ul>
          <li>{challenge.limitation}</li>
          {challenge.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
          <li>{SURVIVAL_DISCLAIMER}</li>
        </ul>
      </section>
    </div>
  );
}

/** The interactive panel (rendered when the farmer asks to challenge the plan). */
export function SurvivalPanel({
  result,
  request,
  initialChallenge,
  autoFocus = false,
}: {
  result: RecommendationResult;
  request?: RecommendationRequest;
  initialChallenge?: ChallengeId;
  autoFocus?: boolean;
}) {
  const challenges = useMemo(() => buildChallenges(result, request), [result, request]);
  const [active, setActive] = useState<ChallengeId>(
    initialChallenge ?? challenges.find((c) => c.available)?.id ?? "drought",
  );
  const [mine, setMine] = useState(defaultMine(result) ?? "");
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (autoFocus) heading.current?.focus();
  }, [autoFocus]);
  const current = challenges.find((c) => c.id === active)!;
  const scenario = request && (request.scenario.temp_change_c !== 0 || request.scenario.rain_change_pct !== 0);
  return (
    <div className="survival-panel" id="survival-panel">
      <header className="survival-header">
        <h3 id="survival-title" ref={heading} tabIndex={-1}>Survival Mode</h3>
        <p>Test your crop rotation against history&apos;s toughest seasons.</p>
        {result.mode === "demo" && <p className="survival-badge survival-badge--warning">Demo · fictional weather and scores</p>}
        {scenario && (
          <p className="survival-badge">
            Scenario-adjusted scores ({request!.scenario.temp_change_c > 0 ? "+" : ""}
            {request!.scenario.temp_change_c} °C, {request!.scenario.rain_change_pct > 0 ? "+" : ""}
            {request!.scenario.rain_change_pct}% rain) · weather evidence is observed
          </p>
        )}
      </header>
      <div className="survival-cards" role="group" aria-label="Choose a historical challenge">
        {challenges.map((challenge) => (
          <button
            type="button"
            key={challenge.id}
            className="survival-card"
            aria-pressed={challenge.id === active}
            onClick={() => setActive(challenge.id)}
          >
            <span className="survival-card-icon"><ChallengeIcon id={challenge.id} /></span>
            <strong>{challenge.title}</strong>
            <span className="survival-small">
              {challenge.available
                ? `${challenge.year} · ${challenge.headline.value} ${challenge.headline.unit}`
                : "Not available"}
            </span>
          </button>
        ))}
      </div>
      {current.available ? (
        <ChallengeView challenge={current} result={result} mine={mine} setMine={setMine} />
      ) : (
        <p className="survival-block survival-unavailable" role="note">
          <strong>{current.title} cannot be tested fairly.</strong> {current.reason}
        </p>
      )}
    </div>
  );
}

/** "Challenge my plan": entry point in the results, opening the panel in place. */
export default function SurvivalMode({
  result,
  request,
}: {
  result: RecommendationResult;
  request?: RecommendationRequest;
}) {
  const [open, setOpen] = useState(false);
  if (!result.plans.length) return null;
  return (
    <section className="survival" aria-labelledby={open ? "survival-title" : "survival-cta-title"}>
      <div className="survival-cta">
        <div>
          <p className="eyebrow">SURVIVAL MODE</p>
          <h3 id="survival-cta-title">Don&apos;t just find the best rotation. See what happens when nature tests it.</h3>
          <p>Replay these plans through the worst drought, heat and rainfall in the NASA POWER record for this field.</p>
        </div>
        <button
          type="button"
          className="button button--primary survival-cta-button"
          aria-expanded={open}
          aria-controls={open ? "survival-panel" : undefined}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Close Survival Mode" : "Challenge my plan"}
        </button>
      </div>
      {open && (
        <SurvivalPanel
          key={`${result.request_id}-${result.generated_at}`}
          result={result}
          request={request}
          autoFocus
        />
      )}
    </section>
  );
}
