import type { Criterion, FarmRequest } from "../types";

type Props = { farm: FarmRequest; onChange: (farm: FarmRequest) => void; onAnalyze: () => void; busy: boolean };

const PRIORITY_LABELS: [Criterion, string][] = [
  ["water", "Economie de apă"],
  ["soil", "Sănătatea solului"],
  ["income", "Venit"],
  ["yield", "Producție"],
  ["pest_break", "Întreruperea dăunătorilor"],
  ["erosion", "Protecție la eroziune"],
  ["forage", "Furaj"],
];

// TODO(P1): crop history (table or document upload), current rotation picker,
// constraints (excluded crops, market crops, equipment, irrigation), phone number for SMS.
export default function ProfileScreen({ farm, onChange, onAnalyze, busy }: Props) {
  function setPriority(c: Criterion, value: number) {
    onChange({ ...farm, priorities: { ...farm.priorities, [c]: value } });
  }

  return (
    <section>
      <h2>Profilul fermei</h2>

      <h3>Rotația actuală</h3>
      <p>{farm.current_rotation.join(" → ")}</p>

      <h3>Istoric ({farm.history.source})</h3>
      <ul>
        {farm.history.seasons.map((s) => (
          <li key={s.year}>{s.year}: {s.crop}{s.yield_t_ha ? ` · ${s.yield_t_ha} t/ha` : ""}</li>
        ))}
      </ul>

      <h3>Priorități</h3>
      {PRIORITY_LABELS.map(([c, label]) => (
        <label key={c} className="slider">
          {label}
          <input type="range" min={0} max={5} step={1} value={farm.priorities[c] ?? 0}
            onChange={(e) => setPriority(c, Number(e.target.value))} />
          <span>{farm.priorities[c] ?? 0}</span>
        </label>
      ))}

      <button onClick={onAnalyze} disabled={busy}>{busy ? "Se analizează…" : "Analizează"}</button>
    </section>
  );
}
