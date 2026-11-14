# FieldShift: reguli pentru agenți și colegi

## Scopul actual — sursa de adevăr pentru produs

Aplicația este un calculator agricol web, fără conturi, autentificare publică, email,
profiluri de fermieri sau sesiuni anonime persistente. La fiecare utilizare se completează
un formular nou. Nu implementa users, farms salvate, login, istoric de analize ori SMS
fără o cerință nouă explicită. SMS prin Anveo și WhatsApp direct prin Meta sunt posibile
extensii viitoare; nu fac parte din versiunea curentă. Nu folosi Twilio.

Intrări: localitate/un punct WGS84, data de la care terenul este disponibil, istoricul
culturilor dacă există, solul cunoscut, irigații, excluderi, priorități și un scenariu
ipotetic opțional. Nu cerem poligon de parcelă.

Ieșire: trei planuri alternative, fiecare cu TREI culturi principale succesive, ferestre
de semănat/recoltare, avantaje și compromisuri. Nu există o rotație actuală obligatorie
în rezultate. Trei culturi nu înseamnă automat trei ani. Planul nu se repetă automat.
Dacă nu există trei variante valide, întoarce limited/insufficient_data; nu inventa opțiuni.

## Stack și directoare

- `apps/web/`: Next.js App Router + React + TypeScript, interfață și backend în aceeași aplicație.
- `apps/web/src/app/`: pagină, layout și Route Handlers.
- `apps/web/src/components/`: calculator, hartă Leaflet, carduri de plan.
- `apps/web/src/lib/api.ts`: singura intrare frontend pentru calcul; poate folosi fixture.
- `apps/web/src/lib/server/`: apelul motorului, validare HTTP, cache și client Prisma.
- `apps/web/prisma/`: schema, migrația PostgreSQL și configurația Prisma din directorul părinte.
- `services/engine/fieldshift/api.py`: API Python intern FastAPI.
- `services/engine/fieldshift/pipeline.py`: orchestrarea modulelor Python.
- `services/engine/fieldshift/data_service/`: P2, date NASA și cache de date publice.
- `services/engine/fieldshift/evaluator/`: P3, reguli și evaluarea unui plan.
- `services/engine/fieldshift/recommender/`: P4, generare, comparație și explicații.
- `services/engine/fieldshift/demo.py`: numai exemple fictive pentru integrare.
- `services/engine/tests/`: verificări de contract și cazuri limită.
- `packages/contracts/src/index.ts`: contractul Zod și tipurile TypeScript comune.
- `packages/contracts/schemas/`: JSON Schema GENERAT pentru Python; nu modifica manual.
- `packages/contracts/examples/`: cerere și rezultat fictive pentru lucru independent.
- `docs/`: arhitectură, API, starea implementării și împărțirea muncii.
- `infra/`: instrucțiuni AWS, reverse proxy și configurație de publicare și copia CI din `infra/ci/checks.yml.example`.
- `.github/workflows/checks.yml`: verificări backend, contracte, PostgreSQL și builduri Docker, pregătite pentru push/PR.
- `compose.yaml`: mediu local PostgreSQL, migrare, motor și web.

## Cine lucrează unde

P1: componentele și UX-ul din web. P5: Route Handlers, integrare, Prisma și infrastructură.
P2: `data_service`, P3: `evaluator` și regulile regionale, P4: `recommender` și orchestrare.
P3 calculează criterii independent de ponderi; P4 aplică prioritățile și selectează planuri.
Colegii Python livrează module în același serviciu; nu construi trei API-uri separate.
Schimbările contractelor se discută cu producătorii și consumatorii lor.

## Implementat și limite reale

Sunt scrise formularul fără cont, localizare prin căutare/punct pe hartă, adapterul frontend
cu mod mock explicit, validarea API, apelul HTTP Next.js–Python, schema/migrația cache-ului,
API intern de cache și adaptorul NASA POWER cu păstrarea valorilor zilnice și a metadatelor.
Există schelet pentru cele trei module Python și generator demonstrativ de calendare.

NU sunt implementate evaluarea agronomică, reguli regionale validate, optimizarea reală,
scorurile de apă/sol/climă, predicția producției sau profitului. `computed` returnează 503
până la completarea modulelor; nu cade automat pe demo. Adaptorul POWER nu înseamnă că
întregul motor este validat științific. Integrarea cu servicii externe cere verificare
separată. Nu declara funcțional un flux doar pentru că exemplul trece schema.

## Contracte și reguli de implementare

- Modifică sursa Zod, rulează `pnpm contracts:generate`, actualizează exemplele în același commit.
- Nu duplica interfețe TS manual în backend/frontend. Importă `@fieldshift/contracts`.
- Coordonatele sunt `latitude`, `longitude`; Leaflet primește `[lat, lon]`.
- Datele sunt ISO `YYYY-MM-DD`, unitățile sunt explicite. Necunoscut nu înseamnă zero.
- Păstrează istoricul de dinaintea planului și verifică tranzițiile/calendarul, inclusiv culturile de toamnă.
- Separă date observate, estimări și scenarii ipotetice. Nu prezenta scenariul ca prognoză.
- `mode: demo` trebuie afișat vizibil. Nu prezenta fixture-urile drept date NASA reale.
- Păstrează `request_id` de la Next.js până la răspuns. Rezultatul trebuie să corespundă cererii.
- Python nu scrie direct în PostgreSQL. Cache-ul public este accesat prin API intern.
- Nu persista formulare, istorice, date de sol introduse sau rezultate asociate fermierilor.
- `INTERNAL_API_TOKEN` este secret între servicii, nu autentificare a fermierului. Nu îl expune în browser.
- Cache-ul este opțional; căderea lui nu trebuie să împiedice calculul sau căutarea localității.
- Nu apela servicii SMS/WhatsApp și nu trimite mesaje în timpul testării acestui repo.

## Comenzi și verificări

Node 22, pnpm 10.11.0, Python 3.11+, uv 0.9.5. Rulează comenzile de la rădăcină dacă nu se precizează altfel.
`pnpm install --frozen-lockfile`, `pnpm contracts:generate`, `pnpm db:generate`, `pnpm typecheck`.
Pentru Python: `uv sync --project services/engine --frozen --extra dev`, apoi
`services/engine/.venv/bin/python -m pytest services/engine/tests`.
Nu porni servere, Docker, migrații pe o bază reală sau deploy fără autorizare în sarcină.
În această refacere utilizatorul a cerut explicit să NU verificăm pornirea aplicației.
Verificările statice nu sunt echivalente cu teste de pornire sau validare agronomică.

## Git

Nu suprascrie `main`. Lucrul curent este pe `mihail`, iar utilizatorul integrează ulterior.
Nu folosi force push fără o cerință explicită pentru branchul vizat.
Păstrează modificările altor colegi. Nu comite `.env`, parole, tokenuri, cache sau dependențe.
Actualizează `docs/status.md` când o componentă devine reală, cu ce a fost efectiv verificat.
