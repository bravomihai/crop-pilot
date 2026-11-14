"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import type {
  Location,
  RecommendationRequest,
  RecommendationResult,
} from "@fieldshift/contracts";
import { getRecommendations } from "@/lib/api";
import {
  DEMO_CROPS,
  visualScenario,
  type ClimateScenario,
  type DemoCropId,
} from "@/lib/dashboard-scenario";
import type { FieldSelection } from "@/lib/parcel-geometry";
import {
  DEFAULT_FARMING_PRIORITIES,
  rankDemoCrops,
  type FarmingPriorities,
} from "@/lib/demo-priorities";
import CompatibilityCard from "./dashboard/compatibility-card";
import Icon from "./dashboard/icon";
import KpiCards from "./dashboard/kpi-cards";
import LocationSearch from "./dashboard/location-search";
import ParcelMap from "./dashboard/parcel-map";
import PdfUpload from "./dashboard/pdf-upload";
import ScenarioPanel from "./dashboard/scenario-panel";
import PriorityPanel from "./dashboard/priority-panel";
import RecommendationResults from "./recommendation-results";
import Button from "./ui/button";

const REGIONS: Location[] = [
  { name: "Cluj", latitude: 46.77, longitude: 23.59 },
  { name: "Bărăgan", latitude: 44.567, longitude: 27.35 },
  { name: "Timiș", latitude: 45.7, longitude: 21.23 },
  { name: "Iași", latitude: 47.16, longitude: 27.58 },
  { name: "Dolj", latitude: 44.25, longitude: 23.8 },
];
function today() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export default function FieldDashboard() {
  const [view, setView] = useState<Location>(REGIONS[1]);
  const [selection, setSelection] = useState<FieldSelection | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [scenario, setScenario] = useState<ClimateScenario>({
    temperature: 0,
    rainfall: 0,
  });
  const [cropId, setCropId] = useState<DemoCropId>("maize");
  const [priorities, setPriorities] = useState<FarmingPriorities>(() => ({
    ...DEFAULT_FARMING_PRIORITIES,
  }));
  const [availableFrom, setAvailableFrom] = useState(today);
  const [historyPdf, setHistoryPdf] = useState<File | null>(null);
  const [soilPdf, setSoilPdf] = useState<File | null>(null);
  const [previousCrop, setPreviousCrop] = useState("");
  const [harvestYear, setHarvestYear] = useState("");
  const [texture, setTexture] =
    useState<NonNullable<RecommendationRequest["soil"]>["texture"]>("unknown");
  const [ph, setPh] = useState("");
  const [irrigated, setIrrigated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RecommendationResult>();
  const request = useRef<AbortController | null>(null);
  const voiceDialog = useRef<HTMLDialogElement>(null);
  const preview = visualScenario(scenario);
  const cropRanking = rankDemoCrops(priorities, scenario, previousCrop);
  useEffect(
    () => () => {
      request.current?.abort();
    },
    [],
  );

  function invalidate() {
    request.current?.abort();
    request.current = null;
    setBusy(false);
    setResult(undefined);
    setError("");
  }
  function chooseRegion(location: Location) {
    invalidate();
    setSelection(null);
    setView(location);
  }
  function chooseCrop(id: DemoCropId) {
    invalidate();
    setCropId(id);
  }
  function openContext() {
    const details = document.getElementById(
      "field-context",
    ) as HTMLDetailsElement | null;
    if (details) {
      details.open = true;
      details.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
        block: "center",
      });
      details.querySelector("summary")?.focus();
    }
  }
  async function analyse(event: FormEvent) {
    event.preventDefault();
    if (!selection || drawing) {
      setError(
        "Draw a field or select a map point before starting the analysis.",
      );
      return;
    }
    invalidate();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    const input: RecommendationRequest = {
      schema_version: "1.0",
      location: selection.location,
      available_from: availableFrom,
      crop_count: 3,
      history: previousCrop
        ? [
            {
              crop_id: previousCrop,
              ...(harvestYear ? { harvest_year: Number(harvestYear) } : {}),
            },
          ]
        : [],
      soil: {
        texture,
        source: ph || texture !== "unknown" ? "farmer_estimate" : "unknown",
        ...(ph ? { ph: Number(ph) } : {}),
      },
      priorities: { water: 3, soil: 3, climate: 3 },
      constraints: { irrigated, excluded_crops: [] },
      scenario: {
        temp_change_c: scenario.temperature,
        rain_change_pct: scenario.rainfall,
      },
    };
    try {
      const output = await getRecommendations(input, controller.signal);
      if (request.current === controller && !controller.signal.aborted)
        setResult(output);
    } catch (cause) {
      if (request.current === controller && !controller.signal.aborted)
        setError(
          cause instanceof Error
            ? cause.message
            : "The analysis could not be completed. Please try again.",
        );
    } finally {
      if (request.current === controller) setBusy(false);
    }
  }
  return (
    <div className="dashboard-shell" id="dashboard-home">
      <a className="skip-link" href="#field-analysis">
        Skip to field analysis
      </a>
      <aside className="dashboard-sidebar">
        <a className="dashboard-brand" href="#dashboard-home">
          <span>
            <Icon name="leaf" size={25} />
          </span>
          <div>
            Field<span>Shift</span>
            <small>EARTH DATA, SMARTER FARMS</small>
          </div>
        </a>
        <p className="nav-group-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          <a href="#dashboard-home" title="Home">
            <Icon name="home" />
            Home
          </a>
          <a
            className="is-active"
            href="#field-analysis"
            aria-current="page"
            title="Field analysis & planning"
          >
            <Icon name="field" />
            <span>
              Field analysis
              <br />& planning
            </span>
          </a>
          <a href="#farming-priorities" title="Farming priorities">
            <Icon name="budget" />
            Farming priorities
          </a>
          <button type="button" onClick={openContext} title="History & soil">
            <Icon name="history" />
            History & soil
          </button>
          <button
            type="button"
            onClick={() => voiceDialog.current?.showModal()}
            title="AI voice assistant — coming soon"
          >
            <Icon name="phone" />
            <span>
              AI voice assistant<small>Coming soon</small>
            </span>
          </button>
          <a href="#nasa-data" title="NASA data sources">
            <Icon name="satellite" />
            NASA data
          </a>
        </nav>
        <div className="sidebar-bottom">
          <div className="orbit-mark">
            <Icon name="satellite" size={28} />
          </div>
          <strong>
            A bigger picture.
            <br />A better starting point.
          </strong>
          <p>Earth data for your next farming decision.</p>
          <span>SPACE APPS 2026 · PROTOTYPE</span>
        </div>
      </aside>

      <div className="dashboard-workspace">
        <header className="dashboard-topbar">
          <LocationSearch onSelect={chooseRegion} />
          <div className="topbar-tools">
            <span className="nasa-status">
              <i />
              NASA SOURCES · DEMO
            </span>
            <div
              className="language-selector"
              role="group"
              aria-label="Interface language"
            >
              <button
                type="button"
                disabled
                title="Romanian translation is not available yet"
              >
                RO
              </button>
              <span>|</span>
              <button
                type="button"
                aria-pressed="true"
                aria-label="English selected"
              >
                EN
              </button>
            </div>
          </div>
        </header>
        <main className="dashboard-main" id="field-analysis">
          <div className="breadcrumb">
            <span>Field analysis</span>
            <span aria-hidden="true">›</span>
            <span>{view.name ?? "Map"}</span>
            <span aria-hidden="true">›</span>
            <span>{selection ? "Selected field" : "Choose a field"}</span>
          </div>
          <section className="field-header" aria-labelledby="field-title">
            <div className="field-title-row">
              <div>
                <h1 id="field-title">Field-1</h1>
                <span
                  className={`field-status ${selection ? "is-selected" : ""}`}
                >
                  <i />
                  {drawing
                    ? "Drawing boundary"
                    : selection
                      ? "Field selected"
                      : "Ready to explore"}
                </span>
              </div>
              <span className="session-note">
                <Icon name="info" size={15} />
                No account. Nothing saved.
              </span>
            </div>
            <div className="field-metadata">
              <span>
                <Icon name="pin" size={16} />
                {selection?.location.name ?? view.name ?? "Selected location"}
              </span>
              <span>
                <Icon name="field" size={16} />
                {selection
                  ? `${selection.location.latitude.toFixed(5)}, ${selection.location.longitude.toFixed(5)}`
                  : "GPS: select on map"}
              </span>
              <span>
                <Icon name="area" size={16} />
                {selection?.areaHectares != null
                  ? `${selection.areaHectares.toFixed(2)} ha`
                  : "Area: not measured"}
              </span>
              <span>
                <Icon name="calendar" size={16} />
                NASA POWER · SMAP <b>planned sources</b>
              </span>
            </div>
            <div className="region-shortcuts">
              <span>Explore Romania</span>
              {REGIONS.map((region) => (
                <button
                  key={region.name}
                  className={view.name === region.name ? "is-active" : ""}
                  type="button"
                  onClick={() => chooseRegion(region)}
                >
                  <Icon name="pin" size={12} />
                  {region.name}
                </button>
              ))}
            </div>
          </section>

          <div className="dashboard-demo-notice">
            <Icon name="info" size={18} />
            <p>
              <strong>Interactive prototype.</strong> Map geometry is calculated
              from your outline. KPI values and crop scores are fictional
              examples, not live NASA measurements or agronomic recommendations.
            </p>
          </div>
          <div className="field-grid">
            <div className="field-map-column">
              <ParcelMap
                view={view}
                selection={selection}
                color={preview.color}
                opacity={preview.opacity}
                onSelect={(value) => {
                  invalidate();
                  setSelection(value);
                }}
                onDrawingChange={(value) => {
                  invalidate();
                  setDrawing(value);
                }}
              />
              <ScenarioPanel
                scenario={scenario}
                onChange={(value) => {
                  invalidate();
                  setScenario(value);
                }}
              />
              <KpiCards scenario={scenario} />
              <PriorityPanel
                ranking={cropRanking}
                cropId={cropId}
                onChange={setPriorities}
                onSelectCrop={chooseCrop}
              />
            </div>
            <div className="field-planning-column">
              <section
                className="dashboard-card planning-card"
                aria-labelledby="planning-title"
              >
                <div className="card-heading">
                  <div>
                    <span className="heading-icon">
                      <Icon name="leaf" />
                    </span>
                    <h2 id="planning-title">Plan your next crop</h2>
                  </div>
                  <span className="step-badge">STEP 02</span>
                </div>
                <p
                  className={`selection-summary ${selection && !drawing ? "is-selected" : ""}`}
                >
                  <Icon
                    name={selection && !drawing ? "check" : "draw"}
                    size={16}
                  />
                  {drawing
                    ? "Finish your field outline first"
                    : selection
                      ? selection.boundary
                        ? "Field boundary selected"
                        : "Map point selected · area unknown"
                      : "Step 1: draw a field or select a map point"}
                </p>
                <form onSubmit={analyse} onChange={invalidate}>
                  <label htmlFor="planned-crop">
                    What would you like to plant?
                  </label>
                  <select
                    id="planned-crop"
                    value={cropId}
                    onChange={(event) =>
                      chooseCrop(event.target.value as DemoCropId)
                    }
                  >
                    {DEMO_CROPS.map((crop) => (
                      <option key={crop.id} value={crop.id}>
                        {crop.name}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="available-from">Field available from</label>
                  <input
                    id="available-from"
                    type="date"
                    required
                    value={availableFrom}
                    onChange={(event) => setAvailableFrom(event.target.value)}
                  />
                  <div className="documents-divider">
                    <span>ADD CONTEXT</span>
                    <span>Optional</span>
                  </div>
                  <PdfUpload
                    id="crop-history-pdf"
                    label="Previous crop history"
                    file={historyPdf}
                    onChange={setHistoryPdf}
                  />
                  <PdfUpload
                    id="soil-report-pdf"
                    label="Soil analysis report"
                    file={soilPdf}
                    onChange={setSoilPdf}
                  />
                  <details className="field-context" id="field-context">
                    <summary>Enter known history & soil manually</summary>
                    <p>
                      Only these manual entries are sent to the planner. PDF
                      content is not read.
                    </p>
                    <label htmlFor="previous-crop">Most recent crop</label>
                    <select
                      id="previous-crop"
                      value={previousCrop}
                      onChange={(event) => setPreviousCrop(event.target.value)}
                    >
                      <option value="">Unknown / not provided</option>
                      {DEMO_CROPS.map((crop) => (
                        <option key={crop.id} value={crop.id}>
                          {crop.name}
                        </option>
                      ))}
                    </select>
                    <label htmlFor="harvest-year">Harvest year, if known</label>
                    <input
                      id="harvest-year"
                      type="number"
                      min={1950}
                      max={2150}
                      value={harvestYear}
                      onChange={(event) => setHarvestYear(event.target.value)}
                    />
                    <label htmlFor="soil-texture">Soil texture</label>
                    <select
                      id="soil-texture"
                      value={texture}
                      onChange={(event) =>
                        setTexture(event.target.value as typeof texture)
                      }
                    >
                      <option value="unknown">Unknown</option>
                      <option value="sandy">Sandy</option>
                      <option value="loamy">Loamy</option>
                      <option value="clay">Clay</option>
                      <option value="silty">Silty</option>
                    </select>
                    <label htmlFor="soil-ph">Soil pH, if known</label>
                    <input
                      id="soil-ph"
                      type="number"
                      min={0}
                      max={14}
                      step={0.1}
                      value={ph}
                      onChange={(event) => setPh(event.target.value)}
                    />
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={irrigated}
                        onChange={(event) => setIrrigated(event.target.checked)}
                      />
                      I have access to irrigation
                    </label>
                  </details>
                  <Button
                    type="submit"
                    loading={busy}
                    disabled={!selection || drawing}
                    className="analyse-button"
                  >
                    {busy
                      ? "Requesting rotation plans…"
                      : "Analyse compatibility & plan"}
                    {!busy && <Icon name="arrow" size={17} />}
                  </Button>
                  {busy && (
                    <button
                      type="button"
                      className="stop-button"
                      onClick={invalidate}
                    >
                      Stop waiting
                    </button>
                  )}
                  <div className="planner-feedback" role="status">
                    {result && (
                      <a href="#results">
                        View {result.plans.length} rotation{" "}
                        {result.plans.length === 1 ? "plan" : "plans"}{" "}
                        <Icon name="arrow" size={13} />
                      </a>
                    )}
                    {error && (
                      <a href="#results">
                        The planner could not return results. View details.
                      </a>
                    )}
                  </div>
                  <p className="planning-note">
                    Crop scores are a local visual preview. The planner receives
                    the field centre, start date, scenario, and manual context;
                    crop choice, the five preview priorities, and PDFs are not
                    evaluated.
                  </p>
                  {process.env.NEXT_PUBLIC_USE_MOCK_API === "true" && (
                    <p className="mock-note">
                      Mock planner enabled · fictional plans with a fixed
                      calendar.
                    </p>
                  )}
                </form>
              </section>
              <CompatibilityCard
                cropId={cropId}
                scenario={scenario}
                selected={Boolean(selection) && !drawing}
                pdfCount={
                  Number(Boolean(historyPdf)) + Number(Boolean(soilPdf))
                }
                onSelectCrop={chooseCrop}
                ranking={cropRanking}
              />
              <button
                className="voice-banner"
                type="button"
                onClick={() => voiceDialog.current?.showModal()}
              >
                <span className="voice-icon">
                  <Icon name="phone" size={21} />
                </span>
                <span>
                  <strong>Out in the field?</strong>
                  <small>Voice reports by phone · coming soon</small>
                </span>
                <Icon name="arrow" size={16} />
              </button>
            </div>
          </div>

          <section
            className="rotation-section"
            aria-label="Rotation planner response"
          >
            <div className="rotation-intro">
              <span className="eyebrow">ROTATION PLANNER</span>
              <p>
                Each returned alternative contains three successive main crops.
                Three crops do not automatically mean three years.
              </p>
            </div>
            <RecommendationResults result={result} busy={busy} error={error} />
          </section>
          <section
            className="nasa-data-section"
            id="nasa-data"
            aria-labelledby="nasa-data-title"
          >
            <div className="sources-heading">
              <div>
                <span className="eyebrow">EARTH DATA, IN CONTEXT</span>
                <h2 id="nasa-data-title">The science behind the next step</h2>
              </div>
              <span className="subtle-badge">Source documentation</span>
            </div>
            <p>
              These are the intended data sources. The indicator cards above
              currently use presentation fixtures, and the satellite basemap is
              supplied by Esri.
            </p>
            <div className="source-cards">
              <a
                href="https://power.larc.nasa.gov/"
                target="_blank"
                rel="noreferrer"
              >
                <span className="source-pill">NASA POWER</span>
                <strong>
                  Weather & solar context <Icon name="arrow" size={16} />
                </strong>
                <span>
                  Solar and meteorological datasets. The repository includes a
                  POWER adapter; this dashboard does not display its
                  observations.
                </span>
              </a>
              <a
                href="https://smap.jpl.nasa.gov/"
                target="_blank"
                rel="noreferrer"
              >
                <span className="source-pill">NASA SMAP</span>
                <strong>
                  Soil moisture context <Icon name="arrow" size={16} />
                </strong>
                <span>
                  Soil Moisture Active Passive mission. Integration with this
                  dashboard is planned.
                </span>
              </a>
              <a
                href="https://modis.gsfc.nasa.gov/data/dataprod/mod13.php"
                target="_blank"
                rel="noreferrer"
              >
                <span className="source-pill">NASA MODIS</span>
                <strong>
                  Vegetation context <Icon name="arrow" size={16} />
                </strong>
                <span>
                  Vegetation index products. The NDVI card is an example, not a
                  retrieved observation.
                </span>
              </a>
            </div>
          </section>
          <footer className="dashboard-footer">
            <span>FieldShift · Space Apps 2026</span>
            <span>Prototype · local agronomic review required</span>
          </footer>
        </main>
      </div>
      <dialog
        ref={voiceDialog}
        className="voice-dialog"
        aria-labelledby="voice-title"
      >
        <div className="dialog-heading">
          <span className="heading-icon">
            <Icon name="phone" />
          </span>
          <button
            type="button"
            aria-label="Close voice assistant details"
            onClick={() => voiceDialog.current?.close()}
          >
            <Icon name="close" />
          </button>
        </div>
        <span className="sample-label">COMING SOON</span>
        <h2 id="voice-title">A field report, just a call away.</h2>
        <p>
          Phone-based voice reports are a planned extension. No phone service or
          number is connected yet, and no calls or messages are sent from this
          dashboard.
        </p>
        <Button type="button" onClick={() => voiceDialog.current?.close()}>
          Back to your field
        </Button>
      </dialog>
    </div>
  );
}
