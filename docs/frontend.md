# Frontend development

The interface lives in `apps/web`. It uses Next.js, React, TypeScript, and plain
CSS. Start with the existing shared contract; confirm input details with the
team before adding fields or changing request shapes. Interface text is English.

## Where to work

| File | Responsibility |
| --- | --- |
| `src/app/page.tsx` | Entry point: the single full-screen map page |
| `src/components/field-dashboard.tsx` | Map page state, planning form, request building and the results panel |
| `src/components/dashboard/parcel-map.tsx` | Full-screen Leaflet map with field-boundary drawing and outline validation |
| `src/components/dashboard/location-search.tsx` | Place search through `/api/locations` |
| `src/components/recommendation-results.tsx` | Loading, error, complete, limited and insufficient-data states |
| `src/components/plan-card.tsx` | One plan or the current rotation: crops, windows, scores, violations, local checks |
| `src/components/results-what-if.tsx` | Hypothetical scenario recalculation from the results panel |
| `src/components/results-evidence.tsx` | Past-season replay (`plan.replay`) and observed yearly climate with trends (`climate_context`) |
| `src/components/ai-summary.tsx` | Optional English-only OpenAI summary and the print button; `lib/summary-payload.ts` trims what is sent |
| `src/components/glossary.tsx` | Plain explanations of the terms used in the results |
| `src/components/charts/` | Score meters and comparison, rotation timeline, replay and climate charts |
| `src/components/regional-map-context.tsx` | Optional NASA GIBS layers, POWER cell and rule-zone outlines |
| `src/lib/api.ts` | The only frontend entry for calculations; explicit mock mode |
| `src/lib/use-recommendations.ts` | Calculation state, cancellation and debounced recalculation |
| `src/lib/planning-dates.ts` | Autumn-sowing hint and the `?lat=&lon=&name=` demo field link |
| `tests/` | Pure-data, server and in-memory component checks |

`/calculator` and `/chart-previews` redirect to `/`. The components of the earlier
dashboard and calculator (`calculator.tsx`, `dashboard/field-map.tsx`,
`priority-panel.tsx`, `compatibility-card.tsx`, `kpi-cards.tsx`, `pdf-upload.tsx`,
`scenario-panel.tsx`, `theme-control.tsx`, `lib/demo-priorities.ts`,
`lib/dashboard-scenario.ts`, `location-map.tsx`) are no
longer used by any page. They are kept until the open `maria` branch, which edits
some of them, is settled; then they should be removed together with their tests.

## Preview the frontend locally

From the repository root, with Node.js and Corepack available:

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @croppilot/contracts generate
corepack pnpm --filter @croppilot/web db:generate
```

Use the single repository-root `.env` (copy the root `.env.example` for a new checkout).
Preserve existing local settings. For a real calculation, keep:

```dotenv
NEXT_PUBLIC_USE_MOCK_API=false
```

Start the engine with `pnpm dev:engine` in another terminal, then start the web application:

```powershell
corepack pnpm --filter @croppilot/web dev
```

Open the URL printed in the terminal, normally `http://localhost:3000`. Keep the
terminal open; saving source files updates the preview. Stop it with Ctrl+C.
Restart it after changing the root `.env`.

These direct workspace commands also work when `pnpm` is not on PATH and
`corepack enable` cannot write to `C:\Program Files\nodejs`.

The real calculation path requires Python and internet access to public environmental
data. A frontend fixture is not a calculation of the submitted field. The optional
PostgreSQL cache stores public data only.

## Map page behaviour

- Search for a place to center the map, then draw the field boundary with corner
  clicks and freehand drags. Finish, undo or cancel the outline; up to 100 boundary
  points are accepted, and invalid or self-intersecting polygons are rejected. The
  map derives an interior representative coordinate and submits both it and the
  closed GeoJSON `field_boundary`.
  A shared link such as `/?lat=44.45&lon=26.5&name=Fundulea` centers the map but
  still requires the farmer to draw the field. The engine samples up to three
  distributed interior points for SoilGrids and SRTM; NASA POWER remains
  representative-point weather context.
- The form sends the shared request: availability date (not before today), previous
  crop with source and harvest year (not after the current year), current rotation,
  soil texture and pH, irrigation, excluded crops and a hypothetical scenario.
- **What matters most?** maps to the four engine priorities: all at 3, with the chosen
  focus at 5 ("A balanced plan" keeps all four at 3).
- Scenario steps are the same in the form and in the results what-if (−3…+5 °C in
  0.5 °C steps, −50…+50 % rain in 5 % steps). After a what-if recalculation the form
  shows the scenario of the displayed result.
- Changing any form input clears older results. A calculation can be cancelled.

## Results panel

- Up to three alternatives and, when a current rotation was given and could be
  evaluated, a separate **Your current rotation** card with any rule violations.
  If a given rotation could not be evaluated, the panel says so and points to
  **Missing data** instead of asking for a rotation again.
- Scores are shown on a 0–100 scale; unknown is labelled **Unknown**, never 0.
- **How each plan would have done** charts each plan's per-season score (water,
  climate or productivity) from `plan.replay`. When a hypothetical scenario was
  applied, the note says every season includes it. **Your field's climate** charts
  observed yearly indicators from `climate_context` (hot days, rain, ET₀, dry spells,
  frost days) with the engine's trend; it is never scenario-adjusted.
- **Survival Mode** ("Challenge my plan", below the at-a-glance summary): picks the worst
  drought, heat and erratic-rain year from observed `climate_context`, compares every
  rotation on the same replayed season (`plan.replay[].field_free_from`), and lets the
  farmer choose and see the modelled historical result. Logic in `src/lib/survival.ts`,
  interface in `src/components/survival-mode.tsx`; details in `docs/survival-mode.md`.
- **AI summary** (optional, computed results only): on request, rewords the calculated
  result in English. It needs `OPENAI_API_KEY`; without it the page reports that the
  summary is unavailable and everything else works. The model receives the field name
  and a trimmed result, but not coordinates or source IDs. Numbers not found in the
  result make the server reject the summary.
- **Print for your agronomist** prints only the results (plans, current rotation,
  scores, calendar, charts, local checks, sources, assumptions, missing data and the
  disclaimer); the map, form, what-if and buttons are left out, and the AI summary is
  printed only when one was written.
- `mode: demo` results carry a visible **Demo · fictional results** notice.
- `monthly_climate` is returned by the engine but not displayed yet.

## Check changes

```powershell
corepack pnpm --recursive typecheck
corepack pnpm --filter @croppilot/web test:ui
corepack pnpm --filter @croppilot/web test:backend
git diff --check
```

The automated checks do not verify browser gestures, layout, tile services, or
external integrations; check those manually in a browser at narrow and wide widths.

## NASA regional context layers

`RegionalMapContext` opens from the map page's **NASA layers** menu. It reads the EPSG:3857
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
measurement.**

The weather-cell rectangle snaps to 0.5° latitude / 0.625° longitude and extends
±0.25° / ±0.3125°. Four dashed crop-rule boxes are copied into
`src/lib/regional-context.ts` from `ro_south.json` (`region.boxes`), with a source
comment. An outside-zone point displays a warning that plans there use provisional
Romania-wide temperature-profile rules and need local review. Capabilities, legend, and tile failures
are isolated from the base map and form.

## Check changes

```powershell
corepack pnpm --recursive typecheck
corepack pnpm --filter @croppilot/web test:ui
corepack pnpm --filter @croppilot/web test:backend
git diff --check
```

The automated checks do not verify browser gestures, layout, tile services, or
external integrations; check those manually in a browser at narrow and wide widths.
