"use client";
import { useRef, useState, type FormEvent } from "react";
import type {
  Location,
  RecommendationRequest,
  RecommendationResult,
} from "@fieldshift/contracts";
import { getRecommendations } from "@/lib/api";
import LocationMap from "./location-map";
import PlanCard from "./plan-card";
const CROPS = [
  ["winter_wheat", "Grâu de toamnă"],
  ["maize", "Porumb"],
  ["winter_barley", "Orz de toamnă"],
  ["pea", "Mazăre"],
  ["sunflower", "Floarea-soarelui"],
] as const;
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
export default function Calculator() {
  const [query, setQuery] = useState(""),
    [locations, setLocations] = useState<Location[]>([]),
    [location, setLocation] = useState<Location>();
  const [date, setDate] = useState(today),
    [history, setHistory] = useState([
      { crop_id: "", harvest_year: "" },
      { crop_id: "", harvest_year: "" },
      { crop_id: "", harvest_year: "" },
    ]);
  const [soil, setSoil] = useState({
    texture: "unknown",
    ph: "",
    organic_carbon_pct: "",
    source: "unknown",
  });
  const [priorities, setPriorities] = useState({
      water: 3,
      soil: 3,
      climate: 3,
    }),
    [irrigated, setIrrigated] = useState(false),
    [irrigation, setIrrigation] = useState("");
  const [excluded, setExcluded] = useState<string[]>([]),
    [scenario, setScenario] = useState({
      temp_change_c: 0,
      rain_change_pct: 0,
    });
  const [searching, setSearching] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<RecommendationResult>();
  const requestRef = useRef<AbortController | null>(null),
    searchRef = useRef(0);
  async function search() {
    const seq = ++searchRef.current;
    setSearching(true);
    setError("");
    try {
      const res = await fetch(`/api/locations?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      if (seq !== searchRef.current) return;
      if (!res.ok) throw new Error(data.error);
      setLocations(data.locations);
      if (!data.locations.length)
        setError("Nu am găsit localitatea. Alege un punct pe hartă.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Căutarea a eșuat.");
    } finally {
      if (seq === searchRef.current) setSearching(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!location) {
      setError("Alege localitatea sau un punct pe hartă.");
      return;
    }
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setBusy(true);
    setError("");
    setResult(undefined);
    const input: RecommendationRequest = {
      schema_version: "1.0",
      location,
      available_from: date,
      crop_count: 3,
      history: history
        .filter((h) => h.crop_id)
        .map((h) => ({
          crop_id: h.crop_id,
          ...(h.harvest_year ? { harvest_year: Number(h.harvest_year) } : {}),
        })),
      soil: {
        texture: soil.texture as NonNullable<
          RecommendationRequest["soil"]
        >["texture"],
        source: soil.source as NonNullable<
          RecommendationRequest["soil"]
        >["source"],
        ...(soil.ph ? { ph: Number(soil.ph) } : {}),
        ...(soil.organic_carbon_pct
          ? { organic_carbon_pct: Number(soil.organic_carbon_pct) }
          : {}),
      },
      priorities,
      constraints: {
        irrigated,
        ...(irrigated && irrigation
          ? { max_irrigation_mm: Number(irrigation) }
          : {}),
        excluded_crops: excluded,
      },
      scenario,
    };
    try {
      const output = await getRecommendations(input, controller.signal);
      if (requestRef.current === controller) setResult(output);
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : "Solicitarea a eșuat.");
    } finally {
      if (requestRef.current === controller) setBusy(false);
    }
  }
  return (
    <>
      <form onSubmit={submit} className="calculator">
        {process.env.NEXT_PUBLIC_USE_MOCK_API === "true" && (
          <p className="notice">
            Mod frontend demonstrativ: formularul folosește rezultate fictive,
            fără backend.
          </p>
        )}
        <section className="panel">
          <h2>1. Unde este terenul?</h2>
          <p className="muted">
            Este suficientă localitatea sau un punct. Nu cerem cont sau contur
            de parcelă.
          </p>
          <label>
            Localitate
            <div className="inline">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="De exemplu, Fundulea"
              />
              <button
                type="button"
                onClick={search}
                disabled={searching || query.trim().length < 2}
              >
                {searching ? "Caut…" : "Caută"}
              </button>
            </div>
          </label>
          {locations.length > 0 && (
            <ul className="locations">
              {locations.map((l, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => {
                      setLocation(l);
                      setLocations([]);
                    }}
                  >
                    {l.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <LocationMap location={location} onSelect={setLocation} />
          {location && (
            <p>
              {location.name} · {location.latitude.toFixed(4)},{" "}
              {location.longitude.toFixed(4)}
            </p>
          )}
          <label>
            De când este terenul disponibil?
            <input
              required
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>
        </section>
        <section className="panel">
          <h2>2. Ce ai cultivat?</h2>
          <p className="muted">
            Opțional, de la cea mai veche la cea mai recentă cultură. Lipsurile
            vor fi semnalate.
          </p>
          {history.map((row, i) => (
            <div className="inline" key={i}>
              <label>
                Cultura {i + 1}
                <select
                  value={row.crop_id}
                  onChange={(e) =>
                    setHistory(
                      history.map((h, j) =>
                        j === i ? { ...h, crop_id: e.target.value } : h,
                      ),
                    )
                  }
                >
                  <option value="">Necunoscut / necompletat</option>
                  {CROPS.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Anul recoltării
                <input
                  type="number"
                  min={1950}
                  max={2150}
                  value={row.harvest_year}
                  onChange={(e) =>
                    setHistory(
                      history.map((h, j) =>
                        j === i ? { ...h, harvest_year: e.target.value } : h,
                      ),
                    )
                  }
                />
              </label>
            </div>
          ))}
          <details>
            <summary>Sol și irigații — dacă ai informații</summary>
            <label>
              Textura solului
              <select
                value={soil.texture}
                onChange={(e) => setSoil({ ...soil, texture: e.target.value })}
              >
                {[
                  ["unknown", "Nu știu"],
                  ["sandy", "Nisipos"],
                  ["loamy", "Lutos"],
                  ["clay", "Argilos"],
                  ["silty", "Prăfos"],
                ].map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <div className="inline">
              <label>
                pH
                <input
                  type="number"
                  min={0}
                  max={14}
                  step="0.1"
                  value={soil.ph}
                  onChange={(e) => setSoil({ ...soil, ph: e.target.value })}
                />
              </label>
              <label>
                Carbon organic (%)
                <input
                  type="number"
                  min={0}
                  max={100}
                  step="0.1"
                  value={soil.organic_carbon_pct}
                  onChange={(e) =>
                    setSoil({ ...soil, organic_carbon_pct: e.target.value })
                  }
                />
              </label>
            </div>
            <label>
              Sursa informației
              <select
                value={soil.source}
                onChange={(e) => setSoil({ ...soil, source: e.target.value })}
              >
                <option value="unknown">Necunoscută</option>
                <option value="farmer_estimate">Estimare proprie</option>
                <option value="lab">Analiză de laborator</option>
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={irrigated}
                onChange={(e) => setIrrigated(e.target.checked)}
              />
              Am acces la irigații
            </label>
            {irrigated && (
              <label>
                Apă disponibilă pe sezon (mm), dacă știi
                <input
                  type="number"
                  min={0}
                  max={10000}
                  value={irrigation}
                  onChange={(e) => setIrrigation(e.target.value)}
                />
              </label>
            )}
          </details>
        </section>
        <section className="panel">
          <h2>3. Ce contează pentru tine?</h2>
          {(
            [
              ["water", "Utilizarea apei"],
              ["soil", "Protecția solului"],
              ["climate", "Rezistența la condiții climatice"],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              {label} · {priorities[key]}
              <input
                type="range"
                min={0}
                max={5}
                value={priorities[key]}
                onChange={(e) =>
                  setPriorities({
                    ...priorities,
                    [key]: Number(e.target.value),
                  })
                }
              />
            </label>
          ))}
          <details>
            <summary>Culturi excluse și scenariu ipotetic</summary>
            {CROPS.map(([id, name]) => (
              <label className="check" key={id}>
                <input
                  type="checkbox"
                  checked={excluded.includes(id)}
                  onChange={(e) =>
                    setExcluded(
                      e.target.checked
                        ? [...excluded, id]
                        : excluded.filter((c) => c !== id),
                    )
                  }
                />
                Exclude {name.toLowerCase()}
              </label>
            ))}
            <label>
              Modificare temperatură: {scenario.temp_change_c}°C
              <input
                type="range"
                min={-3}
                max={5}
                step={0.5}
                value={scenario.temp_change_c}
                onChange={(e) =>
                  setScenario({
                    ...scenario,
                    temp_change_c: Number(e.target.value),
                  })
                }
              />
            </label>
            <label>
              Modificare precipitații: {scenario.rain_change_pct}%
              <input
                type="range"
                min={-50}
                max={50}
                step={10}
                value={scenario.rain_change_pct}
                onChange={(e) =>
                  setScenario({
                    ...scenario,
                    rain_change_pct: Number(e.target.value),
                  })
                }
              />
            </label>
            <p className="muted">
              Scenariu de sensibilitate, nu prognoză meteo.
            </p>
          </details>
        </section>
        <div className="actions">
          <button disabled={busy} type="submit">
            {busy ? "Se calculează…" : "Compară planurile"}
          </button>
          {busy && (
            <button
              className="secondary"
              type="button"
              onClick={() => {
                requestRef.current?.abort();
                setBusy(false);
              }}
            >
              Oprește așteptarea
            </button>
          )}
        </div>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {result && (
        <section className="results" aria-live="polite">
          <h2>Planuri pentru {result.location.name ?? "punctul selectat"}</h2>
          {result.mode === "demo" && (
            <p className="notice">
              DEMONSTRAȚIE: culturile, ferestrele și explicațiile de mai jos
              sunt exemple fictive. Nu sunt recomandări agronomice calculate
              pentru teren.
            </p>
          )}
          {result.status !== "complete" && (
            <p className="notice">
              {result.status === "limited"
                ? "Sunt disponibile mai puțin de trei variante."
                : "Datele nu permit generarea unor planuri."}
            </p>
          )}
          <div className="plans">
            {result.plans.map((p) => (
              <PlanCard key={p.id} plan={p} />
            ))}
          </div>
          <h3>Ipoteze</h3>
          <ul>
            {result.assumptions.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
          <h3>Date lipsă</h3>
          <ul>
            {result.data_gaps.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
          <h3>Surse</h3>
          <ul>
            {result.sources.map((s) => (
              <li key={s.id}>
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.title}
                  </a>
                ) : (
                  s.title
                )}
                {s.resolution && ` · ${s.resolution}`}
              </li>
            ))}
          </ul>
          <p className="muted">{result.disclaimer}</p>
        </section>
      )}
    </>
  );
}
