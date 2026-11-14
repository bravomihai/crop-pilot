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

## De implementat de echipă

- P2: verificare live POWER, indicatori și control de calitate, integrarea altor surse justificată.
- P3: reguli regionale citate, praguri, bilanț hidric, compatibilitate și calendare validate.
- P4: generare și selecție reală, compromisuri, robustețe la scenarii, explicații din dovezi.
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
