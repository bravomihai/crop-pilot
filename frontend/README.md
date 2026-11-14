# Frontend (React + Vite, P1)

Three screens: **select the field → farm profile → results** (existing rotation vs alternatives, season strip, what-if sliders).

```
src/
  App.tsx                    screen flow, /r/<analysis_id> links from SMS
  api.ts                     backend calls (or the example result)
  types.ts                   TypeScript views of /contracts/schemas
  screens/FarmScreen.tsx     TODO: map + polygon drawing
  screens/ProfileScreen.tsx  priorities done; TODO: history, rotation, constraints, phone
  screens/ResultsScreen.tsx  strategy cards + what-if controls
  components/SeasonStrip.tsx season calendar per strategy
```

## Run

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

With `VITE_USE_EXAMPLE=true` the app shows `contracts/examples/analysis-result.example.json` and needs no backend. Set it to `false` to use the backend (Vite proxies `/api` to `localhost:3000`).

## Suggested next steps

- Map: `react-leaflet` + `leaflet-draw` (or MapLibre) with a satellite base layer; write the polygon to `farm.field.boundary`.
- Charts: per-criterion bars per strategy (e.g. Recharts).
- Keep `src/types.ts` in sync with the schemas.
