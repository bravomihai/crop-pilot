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
| `apps/web/src/components/calculator.tsx` | Previous standalone calculator, retained for reference; not mounted on the dashboard |
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
