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
type Position = [number, number];

function containsPoint(point: Position, points: Position[]): boolean {
  const [longitude, latitude] = point;
  let inside = false;
  for (
    let index = 0, previous = points.length - 1;
    index < points.length;
    previous = index, index += 1
  ) {
    const [x1, y1] = points[index];
    const [x2, y2] = points[previous];
    const cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1);
    if (
      Math.abs(cross) < 1e-10 &&
      longitude >= Math.min(x1, x2) &&
      longitude <= Math.max(x1, x2) &&
      latitude >= Math.min(y1, y2) &&
      latitude <= Math.max(y1, y2)
    ) {
      return true;
    }
    if ((y1 > latitude) !== (y2 > latitude)) {
      const crossingLongitude =
        x1 + ((latitude - y1) * (x2 - x1)) / (y2 - y1);
      if (longitude < crossingLongitude) inside = !inside;
    }
  }
  return inside;
}

function polygonCenter(points: Position[]): [number, number] {
  let twiceArea = 0;
  let longitude = 0;
  let latitude = 0;
  const ring = [...points, points[0]];
  for (let index = 0; index < points.length; index += 1) {
    const [x1, y1] = ring[index];
    const [x2, y2] = ring[index + 1];
    const cross = x1 * y2 - x2 * y1;
    twiceArea += cross;
    longitude += (x1 + x2) * cross;
    latitude += (y1 + y2) * cross;
  }
  if (Math.abs(twiceArea) < 1e-10) {
    return [
      points.reduce((sum, point) => sum + point[0], 0) / points.length,
      points.reduce((sum, point) => sum + point[1], 0) / points.length,
    ];
  }
  const center: Position = [
    longitude / (3 * twiceArea),
    latitude / (3 * twiceArea),
  ];
  return containsPoint(center, points) ? center : points[0];
}

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
export default function Calculator() {
  const [query, setQuery] = useState(""),
    [locations, setLocations] = useState<Location[]>([]),
    [location, setLocation] = useState<Location>();
  const [fieldBoundary, setFieldBoundary] = useState<Position[]>([]);
  const [drawingBoundary, setDrawingBoundary] = useState(false);
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
    [selectedCrops, setSelectedCrops] = useState<string[]>([]),
    [selectedCropsOnly, setSelectedCropsOnly] = useState(false),
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
    if (drawingBoundary) {
      setError("Încheie conturul terenului înainte de calcul.");
      return;
    }
    if (fieldBoundary.length > 0 && fieldBoundary.length < 3) {
      setError("Conturul terenului trebuie să aibă cel puțin trei puncte.");
      return;
    }
    if (selectedCropsOnly && selectedCrops.length < 3) {
      setError("Selectează cel puțin trei culturi pentru a limita recomandările.");
      return;
    }
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
      ...(fieldBoundary.length >= 3
        ? {
            field_boundary: {
              type: "Polygon" as const,
              coordinates: [
                [...fieldBoundary, fieldBoundary[0]],
              ] as [Position[]],
            },
          }
        : {}),
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
        selected_crops: selectedCrops,
        selected_crops_only: selectedCropsOnly,
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
            Caută localitatea, alege un punct sau trasează conturul parcelei pe
            hartă.
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
                      setFieldBoundary([]);
                      setDrawingBoundary(false);
                      setLocations([]);
                    }}
                  >
                    {l.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="inline">
            <button
              type="button"
              onClick={() => {
                setLocation(undefined);
                setFieldBoundary([]);
                setDrawingBoundary(true);
              }}
              disabled={drawingBoundary}
            >
              Desenează conturul parcelei
            </button>
            <button
              type="button"
              onClick={() => {
                if (fieldBoundary.length < 3) return;
                const [longitude, latitude] = polygonCenter(fieldBoundary);
                setLocation({
                  name: "Punct reprezentativ al parcelei",
                  latitude: Number(latitude.toFixed(6)),
                  longitude: Number(longitude.toFixed(6)),
                });
                setDrawingBoundary(false);
              }}
              disabled={!drawingBoundary || fieldBoundary.length < 3}
            >
              Încheie conturul
            </button>
            {fieldBoundary.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  setLocation(undefined);
                  setFieldBoundary([]);
                  setDrawingBoundary(false);
                }}
              >
                Șterge conturul
              </button>
            )}
          </div>
          <p className="muted">
            {drawingBoundary
              ? `Apasă pe hartă pentru a adăuga puncte (${fieldBoundary.length}); încheie conturul după cel puțin trei puncte.`
              : fieldBoundary.length >= 3
                ? "Contur desenat. Datele climatice și de sol sunt încă preluate din punctul reprezentativ, nu agregate pe întreaga parcelă."
                : "Fără contur, analiza folosește punctul selectat."}
          </p>
          <LocationMap
            location={location}
            onSelect={(value) => {
              setLocation(value);
              setFieldBoundary([]);
            }}
            fieldBoundary={fieldBoundary}
            onBoundaryChange={setFieldBoundary}
            drawingBoundary={drawingBoundary}
          />
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
            <summary>Vreau să includ doar anumite culturi</summary>
            <p className="muted">
              Dacă nu activezi filtrul, modelul compară toate culturile
              disponibile. Catalogul actual are cinci culturi candidate.
            </p>
            <label className="check">
              <input
                type="checkbox"
                checked={selectedCropsOnly}
                onChange={(e) => setSelectedCropsOnly(e.target.checked)}
              />
              Limitează planurile la culturile bifate
            </label>
            {CROPS.map(([id, name]) => (
              <label className="check" key={id}>
                <input
                  type="checkbox"
                  checked={selectedCrops.includes(id)}
                  onChange={(e) =>
                    setSelectedCrops(
                      e.target.checked
                        ? [...selectedCrops, id]
                        : selectedCrops.filter((crop) => crop !== id),
                    )
                  }
                />
                {name}
              </label>
            ))}
            {selectedCropsOnly && selectedCrops.length < 3 && (
              <p className="muted">
                Selectează cel puțin trei culturi pentru a putea forma o rotație.
              </p>
            )}
          </details>
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
