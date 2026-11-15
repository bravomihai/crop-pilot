"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import type { HistorySource, Location, RecommendationRequest } from "@fieldshift/contracts";
import { useRecommendations } from "@/lib/use-recommendations";
import { usePartRecommendations } from "@/lib/use-part-recommendations";
import { RULE_CROPS, HISTORY_SOURCES } from "@/lib/crop-options";
import { afterAutumnSowing, fieldFromQuery } from "@/lib/planning-dates";
import CurrentRotationInput from "./current-rotation-input";
import Icon from "./dashboard/icon";
import LocationSearch from "./dashboard/location-search";
import ParcelMap from "./dashboard/parcel-map";
import { MAX_FIELD_PARTS, validateFieldPart, type FieldSelection } from "@/lib/parcel-geometry";
import RecommendationResults from "./recommendation-results";

type Focus = "balanced" | "water" | "soil" | "climate" | "productivity";

type Panel = "details" | "results" | null;
type FieldPart = { field: FieldSelection; crops: string[] };

function CropChoices({ crops, onChange, label }: {
  crops: string[];
  onChange: (crops: string[]) => void;
  label: string;
}) {
  return (
    <details className="planner-options">
      <summary>{label} <span>{crops.length ? `${crops.length} selected` : "Optional"}</span></summary>
      <fieldset className="crop-exclusions">
        <legend>Crops to check</legend>
        <div>{RULE_CROPS.map(([id, name]) => (
          <label key={id}>
            <input type="checkbox" aria-label={`${label}: ${name}`} checked={crops.includes(id)}
              onChange={(event) => onChange(event.target.checked ? [...crops, id] : crops.filter((crop) => crop !== id))} />
            <span>{name}</span>
          </label>
        ))}</div>
      </fieldset>
    </details>
  );
}

// Same ranges and steps as the what-if controls on the results panel.
const TEMPERATURE_STEPS = Array.from({ length: 17 }, (_, i) => -3 + i * 0.5);
const RAINFALL_STEPS = Array.from({ length: 21 }, (_, i) => -50 + i * 5);

export default function FieldDashboard() {
  const [view, setView] = useState<Location>({ name: "Bărăgan", latitude: 44.567, longitude: 27.35 });
  const [selection, setSelection] = useState<FieldSelection | null>(null);
  const [fieldParts, setFieldParts] = useState<FieldPart[]>([]);
  const [fieldCrops, setFieldCrops] = useState<string[]>([]);
  const [activeResult, setActiveResult] = useState(0);
  const [drawing, setDrawing] = useState(false);
  const [panel, setPanel] = useState<Panel>("details");
  const [availableFrom, setAvailableFrom] = useState("");
  const [previousCrop, setPreviousCrop] = useState("");
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
  const { result, lastRequest, busy: singleBusy, error, calculate, recalculate, cancel: cancelSingle, clear: clearSingle } = useRecommendations();
  const partResults = usePartRecommendations();
  const busy = singleBusy || partResults.busy;
  const info = useRef<HTMLDialogElement>(null);
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const detailsHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const date = new Date();
    const isoToday = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    setToday(isoToday);
    setAvailableFrom(isoToday);
    // Shared links center the map; the farmer still traces the field boundary.
    const field = fieldFromQuery(window.location.search);
    if (field) setView(field);
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

  function clear() {
    clearSingle();
    partResults.clear();
  }
  function cancel() {
    cancelSingle();
    partResults.cancel();
  }
  function selectField(value: FieldSelection | null) {
    clear();
    setSelection(value);
    setFieldParts([]);
    setFieldCrops([]);
    if (value) setPanel("details");
  }
  function chooseLocation(location: Location) {
    clear();
    setSelection(null);
    setFieldParts([]);
    setFieldCrops([]);
    setView(location);
    setPanel("details");
  }
  async function analyse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (drawing) {
      return;
    }
    if (!selection?.boundary) {
      return;
    }
    const priorities = { water: 3, soil: 3, climate: 3, productivity: 3 };
    if (focus !== "balanced") priorities[focus] = 5;
    const input: RecommendationRequest = {
      schema_version: "1.0",
      location: selection.location,
      field_boundary: {
        type: "Polygon",
        coordinates: [selection.boundary],
      },
      available_from: availableFrom,
      crop_count: 3,
      history: previousCrop ? [{ crop_id: previousCrop, source: historySource, ...(harvestYear ? { harvest_year: Number(harvestYear) } : {}) }] : [],
      assessment_crops: fieldCrops,
      ...(currentRotation.length ? { current_rotation: currentRotation } : {}),
      soil: { texture, source: ph || texture !== "unknown" ? "farmer_estimate" : "unknown", ...(ph ? { ph: Number(ph) } : {}) },
      priorities,
      constraints: { irrigated, excluded_crops: excludedCrops },
      scenario: { temp_change_c: temperature, rain_change_pct: rainfall },
    };
    setPanel("results");
    if (fieldParts.length) {
      setActiveResult(0);
      await partResults.calculate(fieldParts.map(({ field, crops }, index) => ({
        ...input,
        location: { ...field.location, name: `Part ${index + 1}` },
        field_boundary: { type: "Polygon", coordinates: [field.boundary!] },
        assessment_crops: crops,
      })));
    } else {
      await calculate(input);
    }
  }

  return (
    <main className={`map-experience ${panel ? "is-panel-open" : ""}`} id="main">
      <a className="skip-link" href="#field-details" onClick={() => setPanel("details")}>Skip to field details</a>
      <ParcelMap
        view={view}
        selection={selection}
        color="#123c2f"
        opacity={0.2}
        onSelect={selectField}
        parts={fieldParts.map((part) => part.field)}
        onAddPart={(field) => {
          if (!selection) throw new Error("Draw the field boundary first.");
          validateFieldPart(selection, field, fieldParts.map((part) => part.field));
          clear();
          setFieldParts((current) => [...current, { field, crops: [] }]);
        }}
        onDrawingChange={(value) => {
          setDrawing(value);
          if (value) setPanel("details");
        }}
      />

      <header className="map-header">
        <a className="map-brand" href="#main" aria-label="FieldShift home">
          <span className="map-brand-symbol"><Icon name="leaf" size={23} /></span>
          <span>FieldShift<small>Crop planning</small></span>
        </a>
        <LocationSearch onSelect={chooseLocation} />
        <div className="map-header-end">
          <span className="prototype-pill"><i />Prototype</span>
          <button className="map-icon-button" type="button" aria-label="About FieldShift" onClick={() => info.current?.showModal()}><Icon name="info" /></button>
        </div>
      </header>

      <section className={`map-planner ${selection ? "has-field" : ""}`} id="field-details" aria-labelledby="planner-title" hidden={panel !== "details"}>
        <div className="planner-heading">
          <div><span className="planner-eyebrow">YOUR NEXT SEASON</span><h1 id="planner-title" ref={detailsHeading} tabIndex={-1}>{selection ? "Field details" : "Pick your field."}</h1></div>
          <button className="quiet-icon" type="button" aria-label="Minimise field details" onClick={() => setPanel(null)}><Icon name="close" size={18} /></button>
        </div>
        {!selection ? (
          <div className="planner-welcome">
            <p>Search for a place, then draw your field boundary on the map. The boundary is sent to Microsoft Planetary Computer for satellite land-cover screening.</p>
            <div className="planner-steps" aria-label="Planning steps"><span className="active"><b>1</b>Field</span><i /><span><b>2</b>Details</span><i /><span><b>3</b>Plans</span></div>
            <span className="local-note">No account. Nothing saved.</span>
          </div>
        ) : (
          <>
            <div className="selected-field" role="status">
              <span className="selected-field-icon"><Icon name="field" size={22} /></span>
              <div><strong>{selection.location.name ?? "Your field"}</strong><small>Approx. {selection.areaHectares?.toFixed(2) ?? "unknown"} ha · boundary drawn</small></div>
              <Icon name="check" size={18} />
            </div>
            <form className="map-plan-form" onSubmit={analyse} onChange={clear}>
              <div className="planner-fields">
                {fieldParts.length ? (
                  <div>
                    <p className="field-hint">Details below apply to every part. Only the drawn parts are analysed; undrawn land is not included. Draw up to {MAX_FIELD_PARTS} parts on the map.</p>
                    {fieldParts.map((part, index) => (
                      <div key={index}>
                        <strong>Part {index + 1} · {part.field.areaHectares?.toFixed(2)} ha</strong>{" "}
                        <button type="button" className="text-button" onClick={() => { clear(); setFieldParts((current) => current.filter((_, i) => i !== index)); }}>Remove</button>
                        <CropChoices label={`Crops for part ${index + 1}`} crops={part.crops}
                          onChange={(crops) => setFieldParts((current) => current.map((item, i) => i === index ? { ...item, crops } : item))} />
                      </div>
                    ))}
                  </div>
                ) : (
                  <>
                    <p className="field-hint">Optional: use Draw field part on the map to plan up to five separate parts.</p>
                    <CropChoices label="Crops to check" crops={fieldCrops} onChange={setFieldCrops} />
                  </>
                )}
                <label htmlFor="available-from">Available from<input id="available-from" type="date" required min={today || undefined} aria-describedby="available-from-hint" value={availableFrom} onChange={e => setAvailableFrom(e.target.value)} /></label>
                {afterAutumnSowing(availableFrom) && <p className="field-hint" id="available-from-hint">Autumn sowing usually ends in early November, so plans will start with spring crops. If the field is free earlier, pick that date.</p>}
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
              <footer className="planner-action"><button className="calculate-button" type="submit" disabled={busy || drawing || !availableFrom || !selection?.boundary}>{busy ? "Calculating…" : "Calculate"}<Icon name="arrow" size={18} /></button></footer>
            </form>
          </>
        )}
      </section>

      {panel === null && <button className="reopen-planner" type="button" onClick={() => { setPanel("details"); requestAnimationFrame(() => detailsHeading.current?.focus()); }}><Icon name="field" size={18} />{selection ? "Field details" : "Plan your field"}</button>}
      {(result || error || partResults.parts.length > 0 || busy) && panel !== "results" && <button type="button" className="reopen-results" onClick={() => setPanel("results")}><Icon name="leaf" size={17} />{busy ? "Calculating…" : error ? "View calculation" : "View plans"}</button>}

      <section className="map-results-panel" hidden={panel !== "results"} aria-labelledby="plans-heading">
        <header className="results-panel-header"><div><span className="planner-eyebrow">THE NEXT CHAPTER</span><h2 id="plans-heading" tabIndex={-1} ref={resultsHeading}>Your crop plans</h2></div><button type="button" className="map-back-button" onClick={() => setPanel("details")}>Edit details<Icon name="close" size={17} /></button></header>
        <div className="map-results-scroll">
          {busy && <button className="cancel-calculation" type="button" onClick={cancel}>Cancel calculation</button>}
          {partResults.parts.length ? (
            <>
              <div className="part-results-nav" role="group" aria-label="Select part results">
                {partResults.parts.map((part, index) => (
                  <button type="button" className="text-button" key={index} aria-pressed={activeResult === index} onClick={() => setActiveResult(index)}>
                    Part {index + 1} · {part.state === "done" ? "Ready" : part.state === "loading" ? "Calculating" : part.state === "waiting" ? "Waiting" : "Error"}
                  </button>
                ))}
              </div>
              <RecommendationResults
                result={partResults.parts[activeResult]?.result}
                busy={partResults.parts[activeResult]?.state === "loading" || partResults.parts[activeResult]?.state === "waiting"}
                error={partResults.parts[activeResult]?.error ?? ""}
                request={partResults.parts[activeResult]?.request}
              />
            </>
          ) : (
            <RecommendationResults result={result} busy={singleBusy} error={error} request={lastRequest} onRecalculate={recalculate} onCancel={cancel} />
          )}
        </div>
      </section>

      <span className="map-signature">FIELDSHIFT <i /> SPACE APPS 2026</span>
      <dialog className="map-about" ref={info} aria-labelledby="about-title">
        <div className="planner-heading"><h2 id="about-title">FieldShift</h2><button type="button" className="quiet-icon" aria-label="Close about FieldShift" onClick={() => info.current?.close()}><Icon name="close" /></button></div>
        <p>Crop planning prototype. No account; the field boundary is sent to Microsoft Planetary Computer for satellite screening.</p>
        <p>Map: Esri / OpenStreetMap. NASA layers show regional context, not field measurements.</p>
        <p>Demo results are fictional. Review computed plans with a local agronomist.</p>
        <a href="https://power.larc.nasa.gov/" target="_blank" rel="noreferrer">NASA POWER ↗</a>
      </dialog>
    </main>
  );
}
