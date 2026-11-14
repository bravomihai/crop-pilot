# Starea implementării

## Scris în repo

- Workspace pnpm: o aplicație Next.js pentru interfață și backend, un serviciu Python.
- Contract Zod și scheme JSON generate, request/result fără entități de utilizator.
- Formular cu localitate/punct, dată de disponibilitate, istoric și sol opțional, priorități.
- Hartă Leaflet/OpenStreetMap, căutare Open-Meteo/GeoNames, trei carduri cu calendare.
- Adapter frontend pentru lucru independent și mod demo vizibil.
- Frontend foundation: English navigation, responsive styles, reusable UI
  components, help content, and explicit empty/loading/error/result states.
- Endpoint stateless Next.js cu validare, timeout și verificarea rezultatului.
- Prisma/PostgreSQL pentru cache public opțional, cu migrație inițială.
- API Python intern, pipeline și interfețe pentru P2/P3/P4.
- Adaptor NASA POWER pentru descărcarea datelor zilnice; nu a fost verificat live în refacere.
- Generator demonstrativ, care respectă ordinea temporală și excluderile, fără scoruri fictive.
- Configurație Compose, instrucțiuni AWS și model de verificări CI neactivat.

## De implementat de echipă

- P2: verificare live POWER, indicatori și control de calitate, integrarea altor surse justificată.
- P3: reguli regionale citate, praguri, bilanț hidric, compatibilitate și calendare validate.
- P4: generare și selecție reală, compromisuri, robustețe la scenarii, explicații din dovezi.
- P1: confirm final input details with the team; review the interface visually
  in a browser and continue accessibility testing.
- P5: configurarea deploymentului AWS și a secretelor reale.

## Intenționat în afara versiunii

Conturi, email/login, sesiuni persistente, profiluri de fermieri, analize salvate, SMS,
WhatsApp, contur de parcelă, predicții exacte de producție/profit, ML antrenat și CMIP6.

## Limitele verificării acestei refaceri

Utilizatorul a cerut să nu verificăm pornirea aplicației. Nu am pornit Next.js, FastAPI,
Docker, PostgreSQL sau migrații și nu am făcut deploy. Verificările statice/contractele
nu demonstrează că serviciile externe ori evaluarea agronomică sunt validate.

Verificat în refacere: generarea schemelor JSON și a clientului Prisma, verificarea
tipurilor TypeScript pentru web și contracte, sintaxa Python și patru verificări locale
de contract/calendar. Lockfile-uri Node și Python generate. Fără pornire/deploy.

CI este păstrat ca exemplu în `infra/ci/checks.yml.example`. Tokenul GitHub disponibil
nu permite publicarea workflow-urilor. Pentru activare, mutați fișierul în
`.github/workflows/checks.yml` folosind un acces care permite administrarea workflow-urilor.

## Frontend foundation update — 2026-11-14

Implemented on `andrei`, after syncing with `main`:

- English page shell, in-page navigation, skip link, help, and footer.
- Shared button, notice, and form-section components; CSS variables, mobile
  layouts, keyboard focus styles, and reduced-motion support.
- Separate results component for idle, loading, error, complete, limited, and
  insufficient-data responses. Each returned plan shows three successive crops;
  the interface does not add missing alternatives.
- Location errors stay near the search. Form entries remain after failed
  calculations; changing entries clears the previous result. Inputs are disabled
  during a calculation, with a separate control to stop waiting.
- English crop labels, date formatting, API messages, and fictional demo output.
  English location searches use a language-specific cache key. Request/response
  shapes and agronomic behavior are unchanged.
- Local frontend instructions are in `docs/frontend.md`.

Validation: dependencies installed from the frozen lockfile, JSON schemas and
Prisma client generated, and TypeScript checks passed for web and contracts.
React components were rendered in memory with local fixtures to check the result
states, English page content and dates, demo labels, plan/crop counts, empty
metadata, loading buttons, unique IDs, and navigation anchors. CSS syntax parsed
successfully. Direct Python checks confirmed demo syntax, consistency with the
English fixture, request ID preservation, crop ordering, and limited/insufficient
responses. The full Python pytest suite could not run because pytest is not
installed in the available interpreter.
No Next.js/FastAPI server, browser preview, Docker, database migration, live
external-service verification, or deployment was run for this update.
