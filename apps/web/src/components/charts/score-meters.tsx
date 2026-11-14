import type { CriterionScores } from "@fieldshift/contracts";
import { SCORE_CRITERIA, scorePercent } from "@/lib/chart-data";

export function ScoreMeter({
  label,
  value,
  baseline = false,
}: {
  label: string;
  value: number | null | undefined;
  baseline?: boolean;
}) {
  const percent = scorePercent(value);
  return (
    <div className={`score-meter ${baseline ? "score-baseline" : ""}`}>
      <div className="score-meter-label">
        <span>{label}</span>
        <strong>{percent === null ? "Unknown" : `${percent} / 100`}</strong>
      </div>
      <div
        className={`score-meter-track ${percent === null ? "unknown-pattern" : ""}`}
        role="img"
        aria-label={`${label}: ${percent === null ? "Unknown" : `${percent} out of 100`}`}
      >
        {percent !== null && <span style={{ width: `${percent}%` }} />}
      </div>
    </div>
  );
}

export default function ScoreMeters({
  scores,
  baseline = false,
}: {
  scores?: CriterionScores;
  baseline?: boolean;
}) {
  if (!scores) return null;
  return (
    <div className="plan-score-meters" aria-label="Criterion scores">
      {SCORE_CRITERIA.map(([key, label]) => (
        <ScoreMeter
          key={key}
          label={label}
          value={scores[key]}
          baseline={baseline}
        />
      ))}
    </div>
  );
}
