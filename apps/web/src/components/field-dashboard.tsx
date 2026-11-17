"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import type { HistorySource, Location, RecommendationRequest } from "@croppilot/contracts";
import { useRecommendations } from "@/lib/use-recommendations";
import { RULE_CROPS, HISTORY_SOURCES } from "@/lib/crop-options";
import { afterAutumnSowing, fieldFromQuery } from "@/lib/planning-dates";
import CurrentRotationInput from "./current-rotation-input";
import Icon from "./dashboard/icon";
import LocationSearch from "./dashboard/location-search";
import FieldMap from "./dashboard/field-map";
import RecommendationResults from "./recommendation-results";

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <a className={`map-brand${compact ? " map-brand--compact" : ""}`} href="#main" aria-label="CropPilot home">
      <span className="map-brand-symbol"><Icon name="leaf" size={23} /></span>
      <span>CropPilot<small>Crop planning</small></span>
    </a>
  );
}

type Focus = "balanced" | "water" | "soil" | "climate" | "productivity";

type Panel = "details" | "results" | null;

export function PreferredCropInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <label htmlFor="preferred-crop">
      Crop to check (optional)
      <select id="preferred-crop" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Recommend the best rotations</option>
        {RULE_CROPS.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select>
    </label>
  );
}

// Same ranges and steps as the what-if controls on the results panel.
const TEMPERATURE_STEPS = Array.from({ length: 17 }, (_, i) => -3 + i * 0.5);
const RAINFALL_STEPS = Array.from({ length: 21 }, (_, i) => -50 + i * 5);

export default function FieldDashboard() {
  // Opens on the whole of Romania; a search result or a shared link zooms to the place.
  const [view, setView] = useState<Location>({ name: "Romania", latitude: 45.9, longitude: 24.97 });
  const [mapZoom, setMapZoom] = useState(7);
  const [selection, setSelection] = useState<Location | null>(null);
  const [panel, setPanel] = useState<Panel>("details");
  const [availableFrom, setAvailableFrom] = useState("");
  const [previousCrop, setPreviousCrop] = useState("");
  const [preferredCrop, setPreferredCrop] = useState("");
  const [texture, setTexture] = useState<NonNullable<RecommendationRequest["soil"]>["texture"]>("unknown");
  const [irrigated, setIrrigated] = useState(false);
  const [focus, setFocus] = useState<Focus>("balanced");
  const [currentRotation, setCurrentRotation] = useState<NonNullable<RecommendationRequest["current_rotation"]>>([]);
  const [historySource, setHistorySource] = useState<HistorySource>("typed");
  const [harvestYear, setHarvestYear] = useState("");
  const [ph, setPh] = useState("");
  const [excludedCrops, setExcludedCrops] = useState<string[]>([]);
  const [temperature, setTemperature] = useState(0);
  const [rainfall, setRainfall] = useState(0);
  const [today, setToday] = useState("");
  const [fullscreen, setFullscreen] = useState(false);
  const { result, lastRequest, busy, error, calculate, recalculate, recalculateMoney, cancel, clear } = useRecommendations();
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const detailsHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const date = new Date();
    const isoToday = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    setToday(isoToday);
    setAvailableFrom(isoToday);
    // A shared or demo link can open with a field already chosen: /?lat=44.45&lon=26.5&name=Example%20field
    const field = fieldFromQuery(window.location.search);
    if (field) {
      setSelection(field);
      setView(field);
      setMapZoom(13);
    }
  }, []);
  // A what-if recalculation changes the scenario of the shown result; keep the form in step,
  // so "Edit details" then "Calculate" does not silently return to the old scenario.
  useEffect(() => {
    if (!lastRequest) return;
    setTemperature(lastRequest.scenario.temp_change_c);
    setRainfall(lastRequest.scenario.rain_change_pct);
  }, [lastRequest]);
  useEffect(() => {
    if (panel === "results") resultsHeading.current?.focus();
  }, [panel]);

  function selectField(value: Location | null) {
    clear();
    setSelection(value);
    if (value) setPanel("details");
  }
  function chooseLocation(location: Location) {
    clear();
    setSelection(location);
    setView(location);
    setMapZoom(13);
    setPanel("details");
  }
  async function analyse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selection || (preferredCrop && excludedCrops.includes(preferredCrop))) return;
    const priorities = { water: 3, soil: 3, climate: 3, productivity: 3 };
    if (focus !== "balanced") priorities[focus] = 5;
    const input: RecommendationRequest = {
      schema_version: "1.0",
      location: selection,
      available_from: availableFrom,
      crop_count: 3,
      history: previousCrop ? [{ crop_id: previousCrop, source: historySource, ...(harvestYear ? { harvest_year: Number(harvestYear) } : {}) }] : [],
      ...(preferredCrop ? { preferred_crop: preferredCrop, assessment_crops: [preferredCrop] } : {}),
      ...(currentRotation.length ? { current_rotation: currentRotation } : {}),
      soil: { texture, source: ph || texture !== "unknown" ? "farmer_estimate" : "unknown", ...(ph ? { ph: Number(ph) } : {}) },
      priorities,
      constraints: { irrigated, excluded_crops: excludedCrops },
      scenario: { temp_change_c: temperature, rain_change_pct: rainfall },
    };
    setPanel("results");
    await calculate(input);
  }

  return (
    <main className={`map-experience ${panel ? "is-panel-open" : ""}`} id="main">
      <a className="skip-link" href="#field-details" onClick={() => setPanel("details")}>Skip to field details</a>
      <FieldMap view={view} zoom={mapZoom} selection={selection} onSelect={selectField} />

      <header className="map-header">
        <Brand />
        <LocationSearch onSelect={chooseLocation} />
      </header>

      <section className={`map-planner ${selection ? "has-field" : ""}`} id="field-details" aria-labelledby="planner-title" hidden={panel !== "details"}>
        <div className="planner-heading">
          <div><h1 id="planner-title" ref={detailsHeading} tabIndex={-1}>{selection ? "Field details" : "Pick your field."}</h1></div>
          <button className="quiet-icon" type="button" aria-label="Minimise field details" onClick={() => setPanel(null)}><Icon name="close" size={18} /></button>
        </div>
        {!selection ? (
          <div className="planner-welcome">
            <p>Search for a place or click the map.</p>
            <div className="planner-steps" aria-label="Planning steps"><span className="active"><b>1</b>Field</span><i /><span><b>2</b>Details</span><i /><span><b>3</b>Plans</span></div>
            <span className="local-note">No account. Nothing saved.</span>
          </div>
        ) : (
          <>
            <div className="selected-field" role="status">
              <span className="selected-field-icon"><Icon name="field" size={22} /></span>
              <div><strong>{selection.name ?? "Your field"}</strong><small>{Math.abs(selection.latitude).toFixed(4)}° {selection.latitude < 0 ? "S" : "N"} · {Math.abs(selection.longitude).toFixed(4)}° {selection.longitude < 0 ? "W" : "E"}</small></div>
              <Icon name="check" size={18} />
            </div>
            <form className="map-plan-form" onSubmit={analyse} onChange={clear}>
              <div className="planner-fields">
                <PreferredCropInput value={preferredCrop} onChange={setPreferredCrop} />
                {preferredCrop && excludedCrops.includes(preferredCrop) && (
                  <p className="field-hint" role="status">This crop is excluded. Choose another or update Crops to avoid.</p>
                )}
                <label htmlFor="available-from">Available from<input id="available-from" type="date" required min={today || undefined} aria-describedby="available-from-hint" value={availableFrom} onChange={e => setAvailableFrom(e.target.value)} /></label>
                {afterAutumnSowing(availableFrom) && <p className="field-hint" id="available-from-hint">Autumn sowing has ended. Plans start with spring crops.</p>}
                <label htmlFor="previous-crop">Previous crop<select id="previous-crop" value={previousCrop} onChange={e => setPreviousCrop(e.target.value)}><option value="">Not sure / no previous crop</option>{RULE_CROPS.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
                <CurrentRotationInput prefix="map-rotation" badge="Recommended" value={currentRotation} onChange={value => { clear(); setCurrentRotation(value); }} />
                <div className="planner-field-row">
                  <label htmlFor="soil-texture">Soil type<select id="soil-texture" value={texture} onChange={e => setTexture(e.target.value as typeof texture)}><option value="unknown">Not sure</option><option value="sandy">Sandy</option><option value="loamy">Loamy</option><option value="clay">Clay</option><option value="silty">Silty</option></select></label>
                  <label htmlFor="irrigation">Irrigation<select id="irrigation" value={irrigated ? "yes" : "no"} onChange={e => setIrrigated(e.target.value === "yes")}><option value="no">Rain-fed</option><option value="yes">Available</option></select></label>
                </div>
                <label htmlFor="planning-focus">What matters most?<select id="planning-focus" value={focus} onChange={e => setFocus(e.target.value as Focus)}><option value="balanced">A balanced plan</option><option value="water">Saving water</option><option value="soil">Soil health</option><option value="climate">Climate resilience</option><option value="productivity">Productivity potential</option></select></label>
                <details className="planner-options">
                  <summary>More options <span>Optional</span></summary>
                  <div className="planner-extra-fields">
                    <label htmlFor="soil-ph">Soil pH<input id="soil-ph" type="number" min={0} max={14} step={0.1} placeholder="Unknown" value={ph} onChange={e => setPh(e.target.value)} /></label>
                    <div className="planner-field-row">
                      <label htmlFor="history-source">History source<select id="history-source" value={historySource} onChange={e => setHistorySource(e.target.value as HistorySource)}>{HISTORY_SOURCES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
                      <label htmlFor="harvest-year">Harvest year<input id="harvest-year" type="number" min={1950} max={today ? Number(today.slice(0, 4)) : 2150} placeholder="Unknown" value={harvestYear} onChange={e => setHarvestYear(e.target.value)} /></label>
                    </div>
                    <fieldset className="crop-exclusions"><legend>Crops to avoid</legend><div>{RULE_CROPS.map(([id, label]) => <label key={id}><input type="checkbox" aria-label={`Avoid ${label}`} checked={excludedCrops.includes(id)} onChange={e => setExcludedCrops(old => e.target.checked ? [...old, id] : old.filter(crop => crop !== id))} /><span>{label}</span></label>)}</div></fieldset>
                    <fieldset className="climate-options"><legend>Climate scenario <small>Hypothetical</small></legend><div className="planner-field-row">
                      <label htmlFor="scenario-temperature">Temperature<select id="scenario-temperature" value={temperature} onChange={e => setTemperature(Number(e.target.value))}>{TEMPERATURE_STEPS.map(n => <option key={n} value={n}>{n === 0 ? "Unchanged" : `${n > 0 ? "+" : ""}${n}°C`}</option>)}</select></label>
                      <label htmlFor="scenario-rainfall">Rainfall<select id="scenario-rainfall" value={rainfall} onChange={e => setRainfall(Number(e.target.value))}>{RAINFALL_STEPS.map(n => <option key={n} value={n}>{n === 0 ? "Unchanged" : `${n > 0 ? "+" : ""}${n}%`}</option>)}</select></label>
                    </div></fieldset>
                  </div>
                </details>
              </div>
              <footer className="planner-action"><button className="calculate-button" type="submit" disabled={busy || !availableFrom || !!(preferredCrop && excludedCrops.includes(preferredCrop))}>{busy ? "Calculating…" : "Calculate"}<Icon name="arrow" size={18} /></button></footer>
            </form>
          </>
        )}
      </section>

      {panel === null && <button className="reopen-planner" type="button" onClick={() => { setPanel("details"); requestAnimationFrame(() => detailsHeading.current?.focus()); }}><Icon name="field" size={18} />{selection ? "Field details" : "Plan your field"}</button>}
      {(result || error || busy) && panel !== "results" && <button type="button" className="reopen-results" onClick={() => setPanel("results")}><Icon name="leaf" size={17} />{busy ? "Calculating…" : error ? "View calculation" : "View plans"}</button>}

      <section
        className={fullscreen && panel === "results" ? "map-results-panel is-fullscreen" : "map-results-panel"}
        hidden={panel !== "results"}
        aria-labelledby="plans-heading"
        onKeyDown={(event) => { if (event.key === "Escape" && fullscreen) { event.stopPropagation(); setFullscreen(false); } }}
      >
        <header className="results-panel-header">
          <div className="results-panel-title">
            <h2 id="plans-heading" tabIndex={-1} ref={resultsHeading}>Your crop plans</h2>
          </div>
          <div className="results-panel-actions">
            <button type="button" className="fullscreen-toggle" aria-pressed={fullscreen} onClick={() => setFullscreen((value) => !value)}>
              <Icon name={fullscreen ? "shrink" : "expand"} size={16} />{fullscreen ? "Exit full screen" : "Full screen"}
            </button>
            <button type="button" className="map-back-button" onClick={() => { setFullscreen(false); setPanel("details"); }}>Edit details<Icon name="close" size={17} /></button>
          </div>
        </header>
        <div className="map-results-scroll" tabIndex={0} role="region" aria-label="Crop plan results">
          {busy && result && <button className="cancel-calculation" type="button" onClick={cancel}>Cancel calculation</button>}
          <RecommendationResults result={result} busy={busy} error={error} request={lastRequest} onRecalculate={recalculate} onRecalculateMoney={recalculateMoney} onCancel={cancel} />
        </div>
      </section>
    </main>
  );
}
