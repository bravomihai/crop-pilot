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
  Ieșirea P4 pentru utilizatori este în engleză. Adaptat contractului extins din `main`:
  criteriul opțional `productivity`, `current_rotation` → `baseline` evaluat prin P3 (cu
  `violations`, omis cu explicație dacă P3 nu dă calendar/surse), `history[].source` în
  încredere și `local_checks`, `plan.scores` cu `null` pentru necunoscut. Comparația cu
  scenariul climatic folosește „clima de referință”, separat de rotația actuală.
  `pipeline.py` apelează din nou `recommend_rotations`, deci `tests/test_api.py` (P5) trece.
  Integrare P3–P4 verificată cu modulele reale (`load_rules`, `evaluate`, pipeline) pe
  fixture-ul NASA POWER istoric (Bărăgan, 2005–2025) în locul P2: 23 teste în
  `test_p3_p4_integration.py` (contract, fezabilitate, scoruri P3 nemodificate, priorități,
  scenariu vs. climă de referință, rotație actuală cu încălcări, excluderi/istoric, zone
  neacoperite, date lipsă, repetabilitate). Cerere completă la rece: ~14–16 s, ~18% din
  `ENGINE_TIMEOUT_MS` (90 s); >98% din timp e replay-ul P3. Testele au găsit și am corectat
  5 erori P4 (scenariu dezactivat de o cultură necunoscută în rotația actuală, motivul P3
  pierdut în afara zonei și la rezultate goale, ipotezele P3 nepreluate, text „sub mediană”
  cu valori afișate egale). Suita Python: 162 teste trec, 0 eșuează (2026-11-14). Nu este
  validare agronomică; HTTP `computed` rămâne 503 până la P2. `pnpm` nu a rulat (lipsă
  `node_modules`; contractele neschimbate). Detalii: [P4_IMPLEMENTATION_REPORT.md](P4_IMPLEMENTATION_REPORT.md).

## De implementat de echipă

- P2: verificare live POWER, indicatori și control de calitate, integrarea altor surse justificată.
- P3: reguli regionale citate, praguri, bilanț hidric, compatibilitate și calendare validate.
- P3/P4: acord asupra contractului intermediar de evaluare propus în raportul P4
  (`criteria` 0–1 cu proveniență, inclusiv `productivity`, `calendar`, `scenario_applied`,
  `sources`, `local_checks`; calendar și surse și pentru secvențe nefezabile, ca rotația
  actuală să poată fi afișată cu încălcările ei).
- P4: test de integrare cu evaluatorul real P3 (Fundulea), calibrarea pragurilor de
  selecție, familii de culturi pentru diversitate. `computed` rămâne 503 până la P2/P3.
- P1: rafinare UX și accesibilitate, prezentarea comparațiilor și a detaliilor surselor.
- P5: publicarea efectivă pe AWS și configurarea secretelor reale la deployment; pregătirea locală este descrisă mai jos.

## Intenționat în afara versiunii

Conturi, email/login, sesiuni persistente, profiluri de fermieri, analize salvate, SMS,
WhatsApp, contur de parcelă, predicții exacte de producție/profit, ML antrenat și CMIP6.

## Limitele verificării inițiale (istoric)

Utilizatorul a cerut să nu verificăm pornirea aplicației. Nu am pornit Next.js, FastAPI,
Docker, PostgreSQL sau migrații și nu am făcut deploy. Verificările statice/contractele
nu demonstrează că serviciile externe ori evaluarea agronomică sunt validate.

Verificat în refacere: generarea schemelor JSON și a clientului Prisma, verificarea
tipurilor TypeScript pentru web și contracte, sintaxa Python și patru verificări locale
de contract/calendar. Lockfile-uri Node și Python generate. Fără pornire/deploy.

CI este păstrat ca exemplu în `infra/ci/checks.yml.example`. Tokenul GitHub disponibil
nu permite publicarea workflow-urilor. Pentru activare, mutați fișierul în
`.github/workflows/checks.yml` folosind un acces care permite administrarea workflow-urilor.

## Verificare P5 — 2026-11-14

- `GET /api/engine/status` implementat: conexiune HTTP spre engine, mod și contract,
  timeout 3 secunde, erori fără URL/token și fără cache. Nu certifică motorul agronomic.
- `pnpm test:backend`: 18 teste trecute pentru succes, configurație, răspunsuri
  incompatibile, timeout inclusiv la citirea corpului și lipsa informațiilor secrete.
- Schemele și clientul Prisma generate; TypeScript și buildul Next.js au trecut.
- Cele 4 teste Python existente au trecut cu dependențele din lockfile.
- Verificat cu procese Next.js și FastAPI reale pe localhost, în `demo`, cache
  dezactivat: status 200; recomandări 200 cu trei planuri a câte trei culturi și
  localizarea cererii; formular invalid 400; acces direct fără token la engine și
  cache intern 401; după oprirea engine, noul endpoint răspunde 502.
- Configurație locală ignorată de Git, cu token comun generat. Procesele pornite
  pentru verificare au fost oprite. Fără PostgreSQL, Docker, migrații sau deploy.
- Nu au fost verificate NASA live, funcționarea PostgreSQL sau calculul agronomic
  `computed`. Exemplul CI include testele backend, dar rămâne neactivat.

## Backend consolidat P5 — 2026-11-14

### Implementat și verificat local

- Recomandări: JSON și dimensiune limitate, configurație validată, timeout 504
  inclusiv la citirea corpului; răspunsurile incompatibile sau contrare excluderilor/
  disponibilității sunt respinse. Fără redirect și fără fallback computed → demo.
- Geocodare: validare la furnizor și la cache, coordonate verificate, răspuns limitat,
  erori de conexiune/date și timeout distincte. Open-Meteo a fost verificat live.
- Toate endpointurile implementate: `no-store`, `X-Request-ID`, loguri structurate
  cu operație, status, cod și durată; fără formulare/tokenuri/URL-uri în aceste loguri.
- PostgreSQL 17 în Docker: migrarea aplicată; scriere, citire, upsert, expirare și
  curățare verificate. DELETE intern autentificat șterge în loturi de cel mult 1000.
  Serviciu periodic configurat la pornire și apoi la fiecare oră. Limite DB de 1 secundă.
- Baza a fost oprită temporar: operațiile cache au eșuat controlat, iar geocodarea și
  calculul demo au continuat. Baza și motorul au fost restaurate după verificare.
- Gateway NGINX real: 413 pentru corp prea mare, 429 + Retry-After pentru limită,
  API intern blocat la intrarea publică. NGINX și Caddy au trecut validarea configurației.
- Imaginile web/migrare/engine construite; stack Compose pornit și verificat HTTP.
  Aplicația locală cu protecții este pe `http://localhost:8080`.
- 60 teste backend și 12 teste Python trecute; test separat PostgreSQL trecut.
  Include timeout HTTP real cu un corp blocat, nu numai o eroare simulată.
  TypeScript și buildul au trecut. CloudFormation validat cu cfn-lint 1.60.1.

### Pregătit pentru publicare, fără execuție în cloud

- `.github/workflows/checks.yml` include tipuri, contracte, teste, PostgreSQL real,
  builduri Docker, configurații ingress și lint CloudFormation. Va rula la push/PR;
  nu a fost publicat sau executat pe GitHub în această sarcină.
- Profil producție HTTPS prin Caddy, porturile serviciilor eliminate, loguri rotite.
  Certificatul și accesul public nu au fost testate: nu există domeniu/deployment ales.
- AWS: șablon EC2 + IAM/SSM + reguli de acces și disc criptat; încărcare din SecureString
  în `.env.production` ignorat de Git. Documentație în `infra/aws/README.md`.
  Configurația este pregătită; nicio resursă AWS sau secret de producție nu a fost creat.

### Dependențe de colegi și limite

- Testele de succes computed folosesc explicit module simulate și verifică numai
  contractul/orchestrarea pentru 0/1/2/3 planuri. Nu sunt o evaluare agronomică reală.
- Cu modulele actuale reale, Next.js → Python în computed a fost verificat și răspunde
  503 fără fallback. P2/P3/P4 trebuie să livreze și să valideze modelele și datele.
- NASA POWER nu a fost verificat live în această sarcină. Nu există monitorizare AWS
  sau alerte configurate; diagnosticarea implementată este locală, prin loguri.
- Livrabilul P5 este pe branchul `mihail`. Fișierele de mediu și secretele locale sunt
  ignorate de Git. Containerele locale rămân pornite pentru revizuire.

## Frontend

The English dashboard retains its explicit demo indicators, local-only PDFs, and
five preview-priority sliders. The full `/calculator` now supports optional current
rotation, history sources, productivity priority, baseline/score comparison,
local checks, shared crop timelines, and cancellable scenario recalculation.
Both maps have capability-derived GIBS context, POWER-cell and rule-zone outlines.
Replay and climate-trend charts are preview-only, waiting for future fields.
TypeScript, 82 backend/data checks, 25 UI checks, and mock production build passed;
Edge checks covered fixtures, 375/1440 px, keyboard interactions, light/dark, and
tile failure isolation. No scientific or physical-touchscreen validation is
claimed. See docs/frontend.md for exact identifiers, previews, and verification.
