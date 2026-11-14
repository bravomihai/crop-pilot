# API v1

Sursa contractului: `packages/contracts/src/index.ts`.
Python consumă schemele generate din `packages/contracts/schemas/`.
Exemple: `packages/contracts/examples/`.

| Metodă | Rută web                    | Scop                                                                  |
| ------ | --------------------------- | --------------------------------------------------------------------- |
| GET    | `/api/locations?q=Fundulea` | Opțiuni de localitate cu coordonate, Open-Meteo/GeoNames              |
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

## Integrare viitoare

SMS/WhatsApp nu sunt implementate. Viitoarele adaptoare trebuie să colecteze aceleași
intrări și să folosească acest contract. Nu introduce conturi sau API-uri Twilio ca
presupuneri. Nu trimite mesaje și nu modifica webhookurile existente din alte servicii.
