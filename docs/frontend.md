# Frontend development

The interface lives in `apps/web`. It uses Next.js, React, TypeScript, and plain
CSS. Start with the existing shared contract; confirm input details with the
team before adding fields or changing request shapes.

## Where to work

| File | Responsibility |
| --- | --- |
| `apps/web/src/app/page.tsx` | Entry point for the single-page dashboard |
| `apps/web/src/components/field-dashboard.tsx` | Dashboard state, navigation, metadata, planning form, and API submission |
| `apps/web/src/components/dashboard/` | Satellite drawing map, climate controls, KPI cards, crop preview, search, and local PDF selection |
| `apps/web/src/app/layout.tsx` | Document language, metadata, and global style imports |
| `apps/web/src/app/globals.css` | Colors, spacing, typography, responsive layouts, and focus styles |
| `apps/web/src/components/calculator.tsx` | Full contract-backed form at `/calculator`, linked from the dashboard |
| `apps/web/src/components/recommendation-results.tsx` | Empty, loading, error, complete, limited, and insufficient-data states |
| `apps/web/src/components/plan-card.tsx` | One plan's three successive crops, dates, benefits, and trade-offs |
| `apps/web/src/components/ui/` | Reusable buttons, messages, and form section headings |
| `apps/web/src/lib/api.ts` | The frontend calculation adapter and explicit mock mode |
| `apps/web/src/lib/parcel-geometry.ts` | Hybrid trace segments, freehand simplification, polygon validation, hectares, and centre |
| `apps/web/src/lib/dashboard-scenario.ts` | Explicitly fictional KPI and crop-score fixtures |
| `apps/web/tests/` | Geometry, scenario, PDF-selection, and in-memory component checks |

The interface and demonstration content use English. Values returned by future
data providers should also use English for display text. Do not translate IDs
or change shared contract keys to change presentation text.

## Preview the frontend locally

From the repository root, with Node.js and Corepack available:

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @fieldshift/contracts generate
corepack pnpm --filter @fieldshift/web db:generate
```

If `apps/web/.env.local` does not exist, copy `apps/web/.env.example` to that
path. Preserve existing local settings. Set this value in `.env.local`:

```dotenv
NEXT_PUBLIC_USE_MOCK_API=true
```

Start only the web application:

```powershell
corepack pnpm --filter @fieldshift/web dev
```

Open the URL printed in the terminal, normally `http://localhost:3000`. Keep the
terminal open; saving source files updates the preview. Stop it with Ctrl+C.
Restart it after changing `.env.local`.

These direct workspace commands also work when `pnpm` is not on PATH and
`corepack enable` cannot write to `C:\Program Files\nodejs`.

Mock mode uses fictional results with a fixed calendar; form entries are not
evaluated. It does not require Python or PostgreSQL. The map and location search
use the internet. Never present demo output as real NASA observations or
calculated agronomic advice.

## Dashboard behavior and integration boundaries

- The satellite basemap uses Esri World Imagery with road and place overlays. The layer
  control offers OpenStreetMap streets as an alternative. Imagery needs network
  access and is not supplied by NASA.
  The reference overlays are legacy services: Esri lists World Transportation
  for retirement in March 2028 and World Boundaries and Places in December 2029.
  Replace these overlays before that timeline; see the
  [provider's migration notice](https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/announcements/sunsetting-legacy-basemaps).
- Use **Draw field**: click for straight corners; hold and drag for a freehand
  segment. Finish by clicking the first point, double-clicking, pressing Enter,
  or using **Finish outline**. Ctrl/Cmd+Z undoes the last gesture; Escape cancels.
  The toolbar also offers undo, clear, redraw, and **Use map centre**.
- Only freehand segments are simplified. Crossed, self-touching, and degenerate
  outlines are rejected. Area is an approximate WGS84 measurement, not a survey.
  A point selection leaves area unknown.
- Climate sliders update the polygon colour/opacity, all four example KPI
  values, and example crop rankings locally. These formulas are presentation
  fixtures. The 75% water-saving baseline is not a measured saving.
- Each PDF selection accepts one `.pdf` up to 10 MB and checks its header. Files
  stay in tab memory and can be removed/replaced. They are not parsed, uploaded,
  persisted, or used to calibrate scores. Manual soil/history entries are
  separate from file selection.
- **Analyse compatibility & plan** calls `getRecommendations()` with the existing
  shared request shape. The selected field's centre, available date, hypothetical
  scenario, irrigation flag, and manual soil/history entries are sent. Boundaries,
  area, crop-preview choice, and files are not part of that contract. Changing
  inputs or location aborts any pending request and clears older results.
- The crop preview always remains an explicitly labelled demonstration, even if
  the planner is configured for computed mode. Planner errors and limited or
  insufficient-data results are displayed without manufacturing alternatives.
- Phone reports are an informational **Coming soon** dialog, without a phone
  number, calls, or messaging integration. The interface is English; RO is
  visibly unavailable in the language control.

Source references: [NASA POWER](https://power.larc.nasa.gov/),
[SMAP](https://smap.jpl.nasa.gov/), and
[MODIS vegetation indices](https://modis.gsfc.nasa.gov/data/dataprod/mod13.php).
Geometry uses Turf's [area](https://turfjs.org/docs/api/area),
[centre of mass](https://turfjs.org/docs/api/centerOfMass),
[simplification](https://turfjs.org/docs/api/simplify), and
[intersection checks](https://turfjs.org/docs/api/kinks).

## Check changes

```powershell
corepack pnpm --recursive typecheck
corepack pnpm --filter @fieldshift/web test:ui
git diff --check
```

For a manual browser review, check keyboard navigation and narrow and wide
screens. Try straight-only, freehand-only, and mixed outlines; close them with
each finishing method. Test undo, cancel, pointer release outside the map,
region changes while drawing, tile failures, PDF replacement/removal, and edits
during a calculation. Confirm demo notices remain visible and limited results
show only returned plans. The automated checks do not verify browser gestures,
layout, tile services, or external integrations.

## Optional rotation comparison and full fixture

Open `/calculator` for the complete form. It offers the fifteen rule-supported crop
IDs from `src/lib/crop-options.ts`, an optional ordered current rotation (1–5 crops,
add/remove/move up/move down), a documentary source on each history row, and four
0–5 engine priorities. Productivity defaults to 0 and means **Relative potential,
not a yield or profit forecast.** At least one priority must be positive. Empty
current rotation is omitted from the request; blank soil measurements remain absent.
`satellite` is not offered as a history source. The dashboard also supports a
current rotation, history source, and productivity priority. Its existing five
0–100 presentation sliders still affect only its explicitly fictional crop preview.

In mock mode, use `/calculator?fixture=full`, then **Compare plans**. This loads
the shared full request example into the form and selects the full result example
in `src/lib/api.ts`. `/calculator?fixture=default` uses the original result fixture.
The visible fixture links switch between them. Both remain `mode: demo`; dates,
scores, and any baseline are fixed examples, not calculated from the form or
scenario. The mock adapter includes the example baseline only when a current
rotation was supplied. No shared contract or example files are modified.

New result components:

- `CurrentRotationInput`: accessible ordered selectors, with keyboard-operable
  move/remove buttons and a five-crop limit.
- `ScoreMeters` / `ScoreComparison`: optional 0–1 scores displayed on a 0–100 scale.
  Null and absent criteria are labelled **Unknown** with hatching. A genuine zero
  remains `0 / 100`. No score UI is added if no score object is supplied.
- `PlanCard`: a distinct neutral/dashed **Your current rotation** baseline,
  baseline rule violations, optional compact meters, and collapsible local checks.
- `RotationTimeline`: all returned plans and the baseline use one monthly time
  axis with year labels. Light sowing segments and hatched bare-soil gaps are
  labelled, with a cover-crop suggestion for gaps longer than four calendar months.
  Horizontal scrolling stays inside the timeline at narrow widths; a text date
  alternative is provided for assistive technology.
- `ResultsWhatIf` / `useRecommendations`: temperature −3…+5°C in 0.5°C increments
  and rain −50…+50% in increments of 5, initialised from the successful request.
  Recalculate debounces clicks by 300 ms, aborts the previous request, and reuses
  every other request field. Previous results remain visible and dimmed. Failure
  or cancellation does not discard a successful earlier result. The hypothetical
  scenario warning remains visible, and fixture results do not pretend to change.
- `ThemeControl` / `analysis.css`: System, Light, and Dark options without storing
  farmer data or preferences. Charts use theme variables, labels, patterns, and
  text alternatives; no chart library was added.

Baseline is displayed separately from alternative counts. Existing empty,
loading, error, limited, and insufficient-data states remain; no result is padded.

## NASA regional context layers

`RegionalMapContext` is shared by the dashboard parcel map and the calculator's
point map. It reads the EPSG:3857
[GIBS capabilities document](https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml)
in the browser. The following exact identifiers were verified on 2026-11-14:

| Display layer | Identifier | Advertised matrix set | Default snapshot at verification |
| --- | --- | --- | --- |
| SMAP root-zone soil moisture | `SMAP_L4_Analyzed_Root_Zone_Soil_Moisture` | `GoogleMapsCompatible_Level6` | 2026-11-10 |
| MODIS daytime land surface temperature | `MODIS_Terra_Land_Surface_Temp_Day` | `GoogleMapsCompatible_Level7` | 2026-11-14 |
| GPM IMERG precipitation rate | `IMERG_Precipitation_Rate` | `GoogleMapsCompatible_Level6` | 2026-11-13 |

The chosen matrix sets advertise 256 px tiles, with native levels 0–6 / 0–7 / 0–6.
The component reads the matrix set, native zoom, tile size, default style, Time
values, and horizontal LegendURL again at runtime. No unavailable layer, date,
or matrix is guessed. The legends are the advertised
`SMAP_Analyzed_Soil_Moisture_H.svg`, `MODIS_Land_Surface_Temp_H.svg`, and
`GPM_Precipitation_Rate_H.svg` under `https://gibs.earthdata.nasa.gov/legends/`.
Their text labels are also fetched from the official SVG and displayed as text.

The month control covers the current UTC month and preceding 59 months. It shows
the last advertised daily snapshot within each month, not a monthly average.
Daily interval gaps are respected; an unavailable month shows a message and sends
no tile request. Play/pause advances months. Each layer has its own toggle,
opacity slider, and official legend. Attribution is **NASA GIBS / EOSDIS** and the
interface labels the overlays **Regional context (km-scale), not a field
measurement.** They are independent of the fictional dashboard KPI cards.

The weather-cell rectangle snaps to 0.5° latitude / 0.625° longitude and extends
±0.25° / ±0.3125°. Four dashed crop-rule boxes are copied into
`src/lib/regional-context.ts` from `ro_south.json` (`region.boxes`), with a source
comment. An outside-zone point displays the coverage warning; it does not claim
that the engine can compute a plan there. Capabilities, legend, and tile failures
are isolated from the base map and form.

## Future chart components — not wired to result fields

`ReplayChart` takes plain display series (`id`, `label`, optional `baseline`,
and `{year,value}` points on a 0–100 scale). It has labelled lines, a dashed
baseline, gaps for unknown values, a crosshair/readout, a keyboard year selector,
and a text data table. It is waiting for the engine team's optional `plan.replay`.

`ClimateTrendChart` takes plain yearly `{year,value}` points, a title, and unit.
It displays bars, hatched unknowns, and a simple least-squares trend computed
only from known observations. The year readout and data table provide text
alternatives. It is waiting for `result.climate_context` and agreed series units.

Preview both at `/chart-previews`. This route uses hard-coded, visibly labelled
sample data. These components do not inspect plans or results, do not infer
missing fields, and are not connected to recommendation results. No contract
fields or chart-library dependencies were added.

## Verification for this update

- Before feature work, the separate `Merge main into andrei` commit passed frozen
  install, contract generation, Prisma generation, TypeScript, and 75 backend
  checks. The three conflicted server files were kept exactly from main.
- The feature work passed the production mock-mode build, 82 backend/pure-data
  checks, and 25 UI/component checks. No protected contract, engine, API route,
  or server implementation was edited after the merge.
- Headless installed Edge exercised both basic and full mock fixtures; the full
  calculator and future preview pages were checked at 1440 px and 375 px in
  Light and Dark themes. No page-wide horizontal overflow was found. Timeline
  overflow is contained in its explicitly labelled scroll region.
- Browser keyboard interactions checked rotation move/remove, the five-crop
  limit, source choices (without satellite), productivity default 0, all-zero
  priority validation, local-check disclosure, and chart year inspection.
- Recalculation checks confirmed old results remain rendered and dimmed, a newer
  scenario cancels the earlier pending calculation, and both temperature and
  rainfall settings survive the successful response. The basic fixture renders
  three alternatives without optional score UI or a fabricated baseline; the
  full fixture renders exactly one alternative plus its separate baseline.
- Browser checks read the live GIBS capabilities and official legend URLs,
  verified the POWER cell and four rule-zone outlines, observed HTTP 200 snapshot
  tiles for all three advertised layers and NASA attribution, and tested month
  playback. Simulated tile and capabilities failures did not break the base map,
  form, or dashboard drawing. All three toggles issue capability-derived URLs.
- Screenshots of the narrow dark calculator and narrow dark future-chart page
  and the narrow dark dashboard were visually inspected. The pointer/mouse/keyboard tests were automated;
  physical touchscreen and screen-reader testing were not performed. NASA pixel
  values, full spatial/temporal coverage, and agronomic correctness were not
  validated. Demo scores and fixture responses are never scientific validation.
