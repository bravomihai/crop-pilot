# API v1

Sursa contractului: `packages/contracts/src/index.ts`.
Python consumă schemele generate din `packages/contracts/schemas/`.
Exemple: `packages/contracts/examples/`.

| Metodă | Rută web                    | Scop                                                                  |
| ------ | --------------------------- | --------------------------------------------------------------------- |
| GET    | `/api/locations?q=Slobozia` | Opțiuni de localitate cu coordonate, Open-Meteo/GeoNames              |
| POST   | `/api/recommendations`      | Formular complet → rezultat în aceeași cerere                         |
| GET    | `/api/health`               | Identitate serviciu/versiune contract; nu verifică serviciile externe |

Nu există endpoints de users, auth, farms sau rezultate salvate. Endpointul de calcul
nu cere login. Next.js validează schema și cel puțin o prioritate pozitivă.

Erori: `{code,error,request_id?}`. `400` formular invalid, `413` prea mare, `502` motor
inaccesibil/răspuns invalid, `503` motor neconfigurat/neimplementat. Răspunsurile nu conțin
stack traces sau detalii de conexiune. Rezultatele nu sunt cache-uite în browser/proxy.

## Serviciul Python intern

`POST /recommendations`: același request JSON, `Authorization: Bearer <INTERNAL_API_TOKEN>`
și `X-Request-ID`. Tokenul este configurat în ambele servicii, numai pe server.
`GET /health`: versiunea și modul configurat; nu este dovadă că există un motor validat.

Cache public pentru P2: `GET/PUT /api/internal/cache/environment:<sha256>` cu același token.
Un `404` înseamnă cache absent. Căderea cache-ului nu blochează accesul direct la sursă.

## Rezultat

`mode`: `demo` sau `computed`. `status`: `complete` (3 planuri), `limited` (1–2),
`insufficient_data` (0). Fiecare plan are trei pași, ferestre ISO, avantaje, compromisuri,
explicație, nivel de încredere și referințe la surse. Aceste niveluri nu reprezintă
probabilități calibrate de succes. Frontendul arată explicit `mode: demo`.

## Câmpuri opționale (contract 1.0, adăugate 2026-11-14)

Toate sunt opționale: cererile și rezultatele vechi rămân valide, iar cine nu le
folosește încă nu trebuie să schimbe nimic. Exemple complete:
`packages/contracts/examples/recommendation-request.full.json` și `recommendation-result.full.json`.

| Câmp | Unde | Cine îl produce / folosește |
| --- | --- | --- |
| `current_rotation: crop_id[1–5]` | cerere | P1 îl cere în formular; P4 continuă ciclul pe trei culturi și îl evaluează |
| `history[].source: typed\|apia\|spray_records\|satellite\|unknown` | cerere | P1 îl trimite; P4 scade încrederea pentru istoricul ghicit |
| `priorities.productivity: 0–5` | cerere | P1 adaugă slider; P3 dă scorul `productivity`; P4 îl ponderează |
| `baseline: plan` | rezultat | P4 îl întoarce numai dacă există `current_rotation`; nu intră în `status` |
| `plan.scores: {water, soil, climate, productivity}` | rezultat | P3 calculează 0–1 sau `null` (necunoscut); P4 le transmite; P1 le afișează |
| `plan.local_checks: string[]` | rezultat | P3/P4 scriu ce trebuie verificat local; P1 le afișează |
| `plan.violations: string[]` | rezultat | Numai pentru `baseline`: regulile încălcate de rotația actuală |

`productivity` este potențial relativ (EcoCrop, FAO GAEZ), nu prognoză de producție sau profit.

## Integrare viitoare

SMS/WhatsApp nu sunt implementate. Viitoarele adaptoare trebuie să colecteze aceleași
intrări și să folosească acest contract. Nu introduce conturi sau API-uri Twilio ca
presupuneri. Nu trimite mesaje și nu modifica webhookurile existente din alte servicii.
