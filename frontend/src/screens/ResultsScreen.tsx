import { useState } from "react";
import SeasonStrip from "../components/SeasonStrip";
import type { AnalysisResult, FarmRequest, Scenario } from "../types";

type Props = {
  result: AnalysisResult;
  farm: FarmRequest;
  busy: boolean;
  onWhatIf: (overrides: { scenario: Scenario }) => void;
};

// TODO(P1): score charts per criterion, evidence with source links, nicer comparison layout.
export default function ResultsScreen({ result, farm, busy, onWhatIf }: Props) {
  const [scenario, setScenario] = useState<Scenario>(result.scenario ?? farm.scenario);
  const strategies = [...result.strategies].sort((a, b) => a.rank - b.rank);

  return (
    <section>
      <h2>Comparația rotațiilor</h2>

      <div className="whatif">
        <label>
          Climă
          <select value={scenario.climate}
            onChange={(e) => setScenario({ ...scenario, climate: e.target.value as Scenario["climate"], horizon: e.target.value === "historical" ? undefined : 2050 })}>
            <option value="historical">Anii recenți</option>
            <option value="ssp245">2050, scenariu moderat</option>
            <option value="ssp585">2050, scenariu sever</option>
          </select>
        </label>
        <label className="slider">
          Ploaie {scenario.rain_change_pct ?? 0}%
          <input type="range" min={-50} max={50} step={10} value={scenario.rain_change_pct ?? 0}
            onChange={(e) => setScenario({ ...scenario, rain_change_pct: Number(e.target.value) })} />
        </label>
        <label className="slider">
          Temperatură +{scenario.temp_change_c ?? 0} °C
          <input type="range" min={0} max={4} step={0.5} value={scenario.temp_change_c ?? 0}
            onChange={(e) => setScenario({ ...scenario, temp_change_c: Number(e.target.value) })} />
        </label>
        <button disabled={busy} onClick={() => onWhatIf({ scenario })}>{busy ? "…" : "Recalculează"}</button>
      </div>

      <div className="strategies">
        {strategies.map((s) => (
          <article key={s.id} className={`card ${s.kind}`}>
            <header>
              <span className="rank">#{s.rank}</span>
              <h3>{s.label}</h3>
              <span className="score">{Math.round(s.total_score * 100)}/100</span>
            </header>
            {s.kind === "existing" && <p className="tag">Rotația actuală</p>}
            <p>{s.why}</p>
            {s.calendar && <SeasonStrip calendar={s.calendar} />}
            {!!s.violations?.length && <p className="warn">{s.violations.join(" ")}</p>}
            <h4>Ce o susține</h4>
            <ul>{s.evidence.map((e, i) => <li key={i}>{e.claim} <small>[{e.source}]</small></li>)}</ul>
            <h4>Avantaje</h4>
            <ul>{s.benefits.map((b) => <li key={b}>{b}</li>)}</ul>
            <h4>Riscuri</h4>
            <ul>{s.risks.map((r) => <li key={r}>{r}</li>)}</ul>
            <h4>De verificat local</h4>
            <ul>{s.local_checks.map((q) => <li key={q}>{q}</li>)}</ul>
            <p className="muted">Încredere: {s.confidence.level}</p>
          </article>
        ))}
      </div>

      {!!result.data_gaps.length && (
        <>
          <h3>Ce nu știm încă</h3>
          <ul>{result.data_gaps.map((g) => <li key={g}>{g}</li>)}</ul>
        </>
      )}
      <p className="disclaimer">{result.disclaimer}</p>
    </section>
  );
}
