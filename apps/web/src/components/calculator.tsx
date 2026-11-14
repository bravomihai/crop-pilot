"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import type {
  Location,
  RecommendationRequest,
  HistorySource,
} from "@fieldshift/contracts";
import LocationMap from "./location-map";
import RecommendationResults from "./recommendation-results";
import Button from "./ui/button";
import FormSection from "./ui/form-section";
import Notice from "./ui/notice";
import CurrentRotationInput from "./current-rotation-input";
import { RULE_CROPS as CROPS, HISTORY_SOURCES } from "@/lib/crop-options";
import { useRecommendations } from "@/lib/use-recommendations";
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
export default function Calculator({
  initialRequest,
}: {
  initialRequest?: RecommendationRequest;
}) {
  const [query, setQuery] = useState(""),
    [locations, setLocations] = useState<Location[]>([]),
    [location, setLocation] = useState<Location | undefined>(
      initialRequest?.location,
    );
  const [date, setDate] = useState(
      () => initialRequest?.available_from ?? today(),
    ),
    [history, setHistory] = useState(() =>
      Array.from(
        { length: Math.max(3, initialRequest?.history.length ?? 0) },
        (_, index) => ({
          crop_id: initialRequest?.history[index]?.crop_id ?? "",
          harvest_year:
            initialRequest?.history[index]?.harvest_year?.toString() ?? "",
          source: (initialRequest?.history[index]?.source ??
            "typed") as HistorySource,
        }),
      ),
    );
  const [currentRotation, setCurrentRotation] = useState<
    NonNullable<RecommendationRequest["current_rotation"]>
  >(() => [...(initialRequest?.current_rotation ?? [])]);
  const [soil, setSoil] = useState({
    texture: (initialRequest?.soil?.texture ?? "unknown") as string,
    ph: initialRequest?.soil?.ph?.toString() ?? "",
    organic_carbon_pct:
      initialRequest?.soil?.organic_carbon_pct?.toString() ?? "",
    source: (initialRequest?.soil?.source ?? "unknown") as string,
  });
  const [priorities, setPriorities] = useState<
      RecommendationRequest["priorities"]
    >({
      water: 3,
      soil: 3,
      climate: 3,
      productivity: 0,
      ...initialRequest?.priorities,
    }),
    [irrigated, setIrrigated] = useState(
      initialRequest?.constraints.irrigated ?? false,
    ),
    [irrigation, setIrrigation] = useState(
      initialRequest?.constraints.max_irrigation_mm?.toString() ?? "",
    );
  const [excluded, setExcluded] = useState<string[]>(
      initialRequest?.constraints.excluded_crops ?? [],
    ),
    [scenario, setScenario] = useState({
      temp_change_c: 0,
      rain_change_pct: 0,
      ...initialRequest?.scenario,
    });
  const [searching, setSearching] = useState(false),
    [searchError, setSearchError] = useState("");
  const {
    result,
    lastRequest,
    busy,
    error,
    calculate,
    recalculate,
    cancel,
    clear: clearResults,
    reportError: setError,
  } = useRecommendations();
  const searchControllerRef = useRef<AbortController | null>(null),
    searchRef = useRef(0);
  useEffect(
    () => () => {
      searchControllerRef.current?.abort();
    },
    [],
  );
  function selectLocation(value: Location) {
    searchControllerRef.current?.abort();
    ++searchRef.current;
    setSearching(false);
    setLocations([]);
    setSearchError("");
    setError("");
    clearResults();
    setLocation(value);
  }
  async function search() {
    if (query.trim().length < 2 || busy) return;
    const seq = ++searchRef.current;
    searchControllerRef.current?.abort();
    const controller = new AbortController();
    searchControllerRef.current = controller;
    setSearching(true);
    setSearchError("");
    setLocations([]);
    try {
      const res = await fetch(
        `/api/locations?q=${encodeURIComponent(query.trim())}`,
        { signal: controller.signal },
      );
      const data = await res.json();
      if (seq !== searchRef.current) return;
      if (!res.ok) throw new Error(data.error);
      setLocations(data.locations);
      if (!data.locations.length)
        setSearchError(
          "No locations found. Try another search or choose a point on the map.",
        );
    } catch (e) {
      if (seq === searchRef.current && !controller.signal.aborted)
        setSearchError(
          e instanceof Error
            ? e.message
            : "The location search failed. Please try again.",
        );
    } finally {
      if (seq === searchRef.current) setSearching(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!location) {
      setError("Choose a location or a point on the map.");
      document.getElementById("location-query")?.focus();
      return;
    }
    searchControllerRef.current?.abort();
    ++searchRef.current;
    setSearching(false);
    setLocations([]);
    const input: RecommendationRequest = {
      schema_version: "1.0",
      location,
      available_from: date,
      crop_count: 3,
      history: history
        .filter((h) => h.crop_id)
        .map((h) => ({
          crop_id: h.crop_id,
          source: h.source,
          ...(h.harvest_year ? { harvest_year: Number(h.harvest_year) } : {}),
        })),
      ...(currentRotation.length ? { current_rotation: currentRotation } : {}),
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
    await calculate(input);
  }
  return (
    <>
      <section
        id="calculator"
        className="calculator-section"
        aria-labelledby="calculator-title"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">BUILD YOUR FIELD'S CONTEXT</p>
            <h2 id="calculator-title">Let's start with your field.</h2>
          </div>
          <a className="text-link" href="#results">
            Go to results <span aria-hidden="true">↓</span>
          </a>
        </div>
        <p className="section-description">
          Share what you know. You can leave optional details blank.
        </p>
        <form
          onSubmit={submit}
          className="calculator"
          onChange={() => {
            clearResults();
          }}
        >
          {process.env.NEXT_PUBLIC_USE_MOCK_API === "true" && (
            <Notice title="Interface demo mode" tone="warning">
              Results are fictional. The example uses a fixed calendar; your
              form entries are not evaluated agronomically.
            </Notice>
          )}
          <fieldset className="calculator-fields" disabled={busy}>
            <legend className="sr-only">
              Field information and preferences
            </legend>
            <FormSection
              id="location"
              step="01"
              title="Where is your field?"
              description="Choose a location or a point on the map. No account or field boundary is needed."
            >
              <label htmlFor="location-query">
                Location{" "}
                <span className="field-hint">or choose a point on the map</span>
              </label>
              <div className="inline location-search">
                <input
                  id="location-query"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    searchControllerRef.current?.abort();
                    ++searchRef.current;
                    setSearching(false);
                    setLocations([]);
                    setSearchError("");
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void search();
                    }
                  }}
                  aria-describedby="location-search-status"
                  placeholder="For example, Fundulea"
                />
                <Button
                  variant="secondary"
                  onClick={search}
                  loading={searching}
                  disabled={searching || query.trim().length < 2}
                >
                  {searching ? "Searching…" : "Search"}
                </Button>
              </div>
              <p
                id="location-search-status"
                className="field-hint"
                role="status"
              >
                {searching
                  ? "Searching for locations…"
                  : locations.length
                    ? `${locations.length} locations found. Choose one from the list.`
                    : "Search for a location or click on the map."}
              </p>
              {searchError && (
                <Notice title="Location search" tone="error" announce>
                  {searchError}
                </Notice>
              )}
              {locations.length > 0 && (
                <ul className="locations">
                  {locations.map((l, i) => (
                    <li key={i}>
                      <button type="button" onClick={() => selectLocation(l)}>
                        {l.name}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <LocationMap
                location={location}
                onSelect={selectLocation}
                disabled={busy}
              />
              {location && (
                <p className="selected-location">
                  <strong>{location.name ?? "Selected point"}</strong>
                  <br />
                  {location.latitude.toFixed(4)},{" "}
                  {location.longitude.toFixed(4)}
                </p>
              )}
              <label>
                When is your field available?
                <input
                  required
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </label>
            </FormSection>
            <FormSection
              id="history"
              step="02"
              title="What do you know about your field?"
              description="Crop history and soil details are optional. List crops from oldest to most recent."
            >
              {history.map((row, i) => (
                <div className="inline history-row" key={i}>
                  <label>
                    Crop {i + 1}
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
                      <option value="">Unknown / not provided</option>
                      {CROPS.map(([id, name]) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Harvest year
                    <input
                      type="number"
                      min={1950}
                      max={2150}
                      value={row.harvest_year}
                      onChange={(e) =>
                        setHistory(
                          history.map((h, j) =>
                            j === i
                              ? { ...h, harvest_year: e.target.value }
                              : h,
                          ),
                        )
                      }
                    />
                  </label>
                  <label className="history-source">
                    Source
                    <select
                      value={row.source}
                      onChange={(event) =>
                        setHistory(
                          history.map((entry, position) =>
                            position === i
                              ? {
                                  ...entry,
                                  source: event.target.value as HistorySource,
                                }
                              : entry,
                          ),
                        )
                      }
                    >
                      {HISTORY_SOURCES.map(([id, label]) => (
                        <option key={id} value={id}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ))}
              <CurrentRotationInput
                value={currentRotation}
                onChange={(value) => {
                  clearResults();
                  setCurrentRotation(value);
                }}
              />
              <details>
                <summary>Soil and irrigation — if known</summary>
                <label>
                  Soil texture
                  <select
                    value={soil.texture}
                    onChange={(e) =>
                      setSoil({ ...soil, texture: e.target.value })
                    }
                  >
                    {[
                      ["unknown", "I don't know"],
                      ["sandy", "Sandy"],
                      ["loamy", "Loamy"],
                      ["clay", "Clay"],
                      ["silty", "Silty"],
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
                    Organic carbon (%)
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
                  Information source
                  <select
                    value={soil.source}
                    onChange={(e) =>
                      setSoil({ ...soil, source: e.target.value })
                    }
                  >
                    <option value="unknown">Unknown</option>
                    <option value="farmer_estimate">My estimate</option>
                    <option value="lab">Laboratory analysis</option>
                  </select>
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={irrigated}
                    onChange={(e) => setIrrigated(e.target.checked)}
                  />
                  I have access to irrigation
                </label>
                {irrigated && (
                  <label>
                    Water available per season (mm), if known
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
            </FormSection>
            <FormSection
              id="priorities"
              step="03"
              title="What matters to you?"
              description="Set each criterion's importance, from 0 (no priority) to 5 (highest priority)."
            >
              {(
                [
                  ["water", "Water use"],
                  ["soil", "Soil protection"],
                  ["climate", "Climate resilience"],
                  ["productivity", "Productivity potential"],
                ] as const
              ).map(([key, label]) => (
                <label key={key}>
                  <span className="range-label">
                    {label}{" "}
                    <span className="range-value">
                      {priorities[key] ?? 0} / 5
                    </span>
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={5}
                    value={priorities[key] ?? 0}
                    onChange={(e) =>
                      setPriorities({
                        ...priorities,
                        [key]: Number(e.target.value),
                      })
                    }
                  />
                  {key === "productivity" && (
                    <small>
                      Relative potential, not a yield or profit forecast.
                    </small>
                  )}
                </label>
              ))}
              <details>
                <summary>Excluded crops and a hypothetical scenario</summary>
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
                  Temperature change: {scenario.temp_change_c}°C
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
                  Rainfall change: {scenario.rain_change_pct}%
                  <input
                    type="range"
                    min={-50}
                    max={50}
                    step={5}
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
                  This is a hypothetical sensitivity scenario, not a weather
                  forecast.
                </p>
              </details>
            </FormSection>
          </fieldset>
          <div className="actions">
            <p>
              Compare the available alternatives.
              <br />
              <span className="muted">
                Missing information will be highlighted in the results.
              </span>
            </p>
            <Button loading={busy} type="submit">
              {busy ? "Calculating…" : "Compare plans"}
            </Button>
            {busy && (
              <Button variant="secondary" onClick={cancel}>
                Stop waiting
              </Button>
            )}
          </div>
        </form>
      </section>
      <RecommendationResults
        result={result}
        busy={busy}
        error={error}
        request={lastRequest}
        onRecalculate={recalculate}
        onCancel={cancel}
      />
    </>
  );
}
