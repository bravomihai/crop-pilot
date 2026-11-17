# Frontend development

The interface lives in `apps/web`. It uses Next.js, React, TypeScript, and plain
CSS. Start with the existing shared contract; confirm input details with the
team before adding fields or changing request shapes. Interface text is English.

## Where to work

| File | Responsibility |
| --- | --- |
| `src/app/page.tsx` | Entry point: the single full-screen map page |
| `src/components/field-dashboard.tsx` | Map page state, planning form, request building and the results panel |
| `src/components/dashboard/field-map.tsx` | Leaflet map with one draggable field point, zoom limited to 6–17 |
| `src/components/dashboard/location-search.tsx` | Place search through `/api/locations` |
| `src/components/recommendation-results.tsx` | Loading, error, complete, limited and insufficient-data states |
| `src/components/plan-card.tsx` | One plan or the current rotation: crops, windows, scores, violations, local checks |
| `src/components/results-what-if.tsx` | Hypothetical scenario recalculation from the results panel |
| `src/components/results-evidence.tsx` | Past-season replay (`plan.replay`) and observed yearly climate with trends (`climate_context`) |
| `src/components/ai-summary.tsx` | Optional English-only OpenAI summary and the print button; `lib/summary-payload.ts` trims what is sent |
| `src/components/glossary.tsx` | Plain explanations of the terms used in the results |
| `src/components/charts/` | Score meters and comparison, rotation timeline, replay and climate charts |
| `src/app/controls.css` | Shared inputs, dropdowns, buttons, disabled states and keyboard focus |
| `src/lib/api.ts` | The only frontend entry for calculations; explicit mock mode |
| `src/lib/use-recommendations.ts` | Calculation state, cancellation and debounced recalculation |
| `src/lib/planning-dates.ts` | Autumn-sowing hint and the `?lat=&lon=&name=` demo field link |
| `tests/` | Pure-data, server and in-memory component checks |

`/calculator` and `/chart-previews` redirect to `/`. The components of the earlier
dashboard and calculator (`calculator.tsx`, `dashboard/parcel-map.tsx`,
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

- Search for a place or click the map to select a point. A shared link such as
  `/?lat=44.45&lon=26.5&name=Fundulea` selects that location. Point requests do not
  include a boundary, so ESA WorldCover cannot establish land-cover suitability;
  results show that it must be checked before planting.
- The form sends the shared request: availability date (not before today), previous
  crop with source and harvest year (not after the current year), current rotation,
  soil texture and pH, irrigation, excluded crops and a hypothetical scenario.
- An optional crop selector lists the crops supported by the regional rules. The
  selected crop is assessed as the next crop and requested in a rotation; the best
  overall plan is retained. The rotation chart marks plans that include it, and the
  page explains if no eligible sampled rotation was found.
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

## Shared visual system — 2026-11-15

`src/app/ui-theme.css` defines shared theme tokens and card styles.
`src/app/controls.css` owns shared interactive controls and their planner/search
variants. Header controls share size and corner tokens; layout stylesheets position
their containers.
Light and dark appearance follows `prefers-color-scheme` automatically; the main
page offers no theme selector and stores no theme preference. Light mode uses
soft white surfaces with a slight green tint, black text and forest green
(`#123c2f`) accents. Dark mode uses deep green surfaces and readable white text.
Score bars have muted, distinct colours with darker variants in dark mode; other
chart series and geographic imagery keep their existing colours.

Planner and results panels share 16 px card corners, consistent
borders, spacing, dropdowns and keyboard focus indicators. Branding sits at the
top left of the map and results headers. The results title reads logo, CropPilot,
then Your crop plans, without the earlier THE NEXT CHAPTER eyebrow. Results retain the summary and plan
sections, without Back to summary links, a plan-count badge or a prompt to add a
rotation. A supplied rotation that cannot be evaluated still produces a warning.
Programmatic heading focus does not draw a selection-like rectangle.

The Prototype badge and project-information button/dialog are removed. Map zoom
is bounded to levels 6–17; all basemaps disable wrapping and panning is constrained
to the world bounds to prevent repeated world tiles.


### Browser branding

The tab title is `CropPilot`. The favicon keeps the dark green leaf (`#123c2f`)
on a rounded light green (`#c4dfce`) background.

### Map controls

Regional NASA imagery overlays have been removed because their resolution does not
support field-level zoom. NASA POWER weather and SRTM terrain data remain part of
the calculation engine.

Satellite imagery is the only basemap; the street-map selector and on-screen zoom
buttons are removed. Scroll, pinch and keyboard zoom remain available within levels 6–17.

The map attribution control is disabled in every build at the owner's request
for design review. Layer attribution metadata is retained. Restore the control
before publishing a version using the current imagery providers.


### Scrollbars and result surfaces

Shared scrollbar tokens in `ui-theme.css` follow the system appearance throughout
the app, including nested scroll areas. Standard scrollbar properties and a WebKit
fallback use muted green thumbs and themed tracks. The outer results scrollbar is
hidden while scrolling remains enabled; the results region is keyboard focusable.
Money cards and Survival Mode use the same surface, border and text tokens as the
other result cards.
