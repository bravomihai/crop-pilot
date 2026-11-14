# Starea implementării

## Scris în repo

- Workspace pnpm: o aplicație Next.js pentru interfață și backend, un serviciu Python.
- Contract Zod și scheme JSON generate, request/result fără entități de utilizator.
- Formular cu localitate/punct, dată de disponibilitate, istoric și sol opțional, priorități.
- Hartă Leaflet/OpenStreetMap, căutare Open-Meteo/GeoNames, trei carduri cu calendare.
- Adapter frontend pentru lucru independent și mod demo vizibil.
- Endpoint stateless Next.js cu validare, timeout și verificarea rezultatului.
- Prisma/PostgreSQL pentru cache public opțional, cu migrație inițială.
- API Python intern, pipeline și interfețe pentru P2/P3/P4.
- Adaptor NASA POWER pentru descărcarea datelor zilnice; nu a fost verificat live în refacere.
- Generator demonstrativ, care respectă ordinea temporală și excluderile, fără scoruri fictive.
- Configurație Compose, instrucțiuni AWS și model de verificări CI neactivat.
- P4 (branch `alexia`): motor de recomandare determinist în `recommender/` — generare
  limitată a secvențelor din regulile P3, clasificare fezabil/nefezabil/necunoscut,
  verificarea calendarului (inclusiv culturi de toamnă și `available_from`), ponderi
  normalizate, intervale pentru scoruri lipsă, analiză Pareto, selecție diversă cu
  dezvăluirea compromisurilor, comparație scenariu–referință când P3 o confirmă,
  explicații și încredere calitativă din dovezi. Integrat în `pipeline.py` fără fallback.
  Verificat numai cu un evaluator SINTETIC de test (51 teste pytest trec); nu este
  validare agronomică. Detalii: [P4_IMPLEMENTATION_REPORT.md](P4_IMPLEMENTATION_REPORT.md).

## De implementat de echipă

- P2: verificare live POWER, indicatori și control de calitate, integrarea altor surse justificată.
- P3: reguli regionale citate, praguri, bilanț hidric, compatibilitate și calendare validate.
- P3/P4: acord asupra contractului intermediar de evaluare propus în raportul P4
  (`criteria` 0–1 cu proveniență, `calendar`, `scenario_applied`, `sources`).
- P4: test de integrare cu evaluatorul real P3 (Fundulea), calibrarea pragurilor de
  selecție, familii de culturi pentru diversitate. `computed` rămâne 503 până la P2/P3.
- P1: rafinare UX și accesibilitate, prezentarea comparațiilor și a detaliilor surselor.
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
