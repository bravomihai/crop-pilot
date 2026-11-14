# API v1

Sursa contractului: `packages/contracts/src/index.ts`.
Python consumă schemele generate din `packages/contracts/schemas/`.
Exemple: `packages/contracts/examples/`.

| Metodă | Rută web                    | Scop                                                                  |
| ------ | --------------------------- | --------------------------------------------------------------------- |
| GET    | `/api/locations?q=Slobozia` | Opțiuni de localitate cu coordonate, Open-Meteo/GeoNames              |
| POST   | `/api/recommendations`      | Formular complet → rezultat în aceeași cerere                         |
| GET    | `/api/engine/status`        | Conectivitate engine, mod și compatibilitatea contractului; fără calcul agronomic |
| GET    | `/api/health`               | Identitate serviciu/versiune contract; nu verifică serviciile externe |

Nu există endpoints de users, auth, farms sau rezultate salvate. Endpointul de calcul
nu cere login. Next.js validează schema și cel puțin o prioritate pozitivă.

Erori: `{code,error,request_id}`. `400` formular invalid, `413` prea mare, `502` motor
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
| `plan.replay: season[]` | rezultat | P3 rejoacă planul pe fiecare sezon trecut (cu scenariul cererii); P4 îl transmite; P1 desenează graficul „cum ar fi mers în 2012”. Sezoanele sunt în ordine crescătoare; fiecare are `scores` și, per cultură, apă (WRSI %, mm), ploaie, risc climatic și hazarde |
| `climate_context` | rezultat | Clima observată pe ani la locație (ploaie, ET0, temperatură, zile > 32 °C, îngheț, secetă apr.–sept., ploi torențiale) și tendințe pe deceniu. Fără scenariu. Calculat în pipeline din aceleași date ca evaluarea |

`productivity` este potențial relativ (EcoCrop, FAO GAEZ), nu prognoză de producție sau profit.

## Integrare viitoare

SMS/WhatsApp nu sunt implementate. Viitoarele adaptoare trebuie să colecteze aceleași
intrări și să folosească acest contract. Nu introduce conturi sau API-uri Twilio ca
presupuneri. Nu trimite mesaje și nu modifica webhookurile existente din alte servicii.

## Statusul conexiunii cu motorul

`GET /api/engine/status` verifică configurația serverului și apelează `/health` din
Python, cu o limită de 3 secunde inclusiv citirea răspunsului. Nu folosește cache și
nu efectuează calcule sau apeluri NASA. Redirecționările nu sunt urmate.

Exemplu de răspuns 200:

```json
{"status":"reachable","service":"fieldshift-engine","contract_version":"1.0","mode":"demo","request_id":"<uuid>"}
```

`reachable` confirmă numai conectivitatea și forma/versionarea răspunsului. Modul
`computed` este raportat dacă este configurat, dar nu garantează că P3/P4 sunt gata.
`/health` din Python nu autentifică tokenul; acest endpoint verifică doar prezența și
lungimea tokenului configurat în web, nu egalitatea secretelor între servicii.

Erori: `503 engine_not_configured` pentru configurație absentă/invalidă;
`502 engine_unavailable` pentru conexiune eșuată sau status HTTP nereușit;
`502 invalid_engine_status` pentru JSON invalid, alt serviciu/contract/mod;
`504 engine_timeout` la depășirea timpului. Toate răspunsurile au `Cache-Control:
no-store` și `X-Request-ID`, egal cu `request_id` din corp. URL-ul intern și tokenul
nu sunt returnate. Cache-ul PostgreSQL nu este o dependență a acestei verificări.

Teste backend fără servicii externe: `pnpm test:backend` (include un server HTTP temporar pe localhost pentru timeout).

## Comportament backend consolidat — P5

Toate Route Handlers implementate răspund cu `Cache-Control: no-store` și
`X-Request-ID`. Pentru calcul, identificatorul este transmis și către Python și
verificat în rezultat. Pentru erori este inclus și în corp. Metodele nesuportate
rămân gestionate automat de Next.js.

`POST /api/recommendations` acceptă `application/json`, cel mult 32 KiB. Configurația
`ENGINE_TIMEOUT_MS` trebuie să fie un întreg între 100 și 90000 ms; configurația
invalidă dă 503. Timeoutul include citirea corpului răspunsului. Motorul nu este
urmat prin redirect. JSON-ul rezultat este limitat la 2 MB și validat prin contract
și reguli semantice. Se resping ID/localizare nepotrivite, calendare suprapuse,
semănat înainte de `available_from` și culturi excluse.

`GET /api/locations` validează atât datele furnizorului, cât și rezultatul din cache.
Un rezultat cache invalid este ignorat. Timeoutul este 10 secunde și corpul extern
este limitat la 128 KB. Nicio potrivire este un rezultat valid cu listă goală.

Coduri suplimentare: `415 unsupported_media_type`, `504 engine_timeout`,
`504 geocoding_timeout`, `502 invalid_geocoding_result`. Erorile de conexiune sunt
502. Un engine care răspunde 503 la calcul produce `503 engine_not_ready`, fără fallback.

### Cache public intern

`GET/PUT /api/internal/cache/environment:<sha256>` necesită exact antetul
`Authorization: Bearer <token>`. PUT acceptă un obiect JSON de cel mult 2 MB și
răspunde 204 numai după scriere reușită; cache dezactivat/indisponibil produce 503.
Un GET fără date neexpirate răspunde 404. Aceste răspunsuri nu sunt cache-uite de HTTP.

`DELETE /api/internal/cache`, cu același token, șterge cel mult 1000 de intrări expirate
și răspunde `{deleted,batch_size:1000}`. Cache dezactivat înseamnă zero ștergeri;
indisponibil înseamnă 503. Serviciul Compose `cache-maintenance` îl apelează la pornire
și apoi la fiecare oră, cu cel mult 100 de loturi pe rulare. Datele active sunt păstrate.
Baza are limite de conectare/interogare de 1 secundă. Citirea nereușită se comportă ca
un cache miss; geocodarea și datele NASA pot folosi sursa externă fără cache.

### Acces public și loguri

Intrarea NGINX de pe portul local 8080 aplică limite per IP: 5 calcule/minut (burst 3),
60 căutări/minut (burst 10), 30 statusuri engine/minut (burst 5). Depășirea întoarce
429 JSON, `Retry-After: 60`, `X-Request-ID` și `no-store`. Corpurile prea mari primesc
413 JSON. `/api/internal` și subrutele sale sunt blocate la această intrare chiar cu
token valid. În producție, numai Caddy este public, iar porturile directe sunt eliminate.
Limitele nu se aplică la accesarea portului de dezvoltare 3000; acesta nu se publică.

Logurile aplicației conțin `event`, operație statică, `request_id`, status, cod de eroare
când există și `duration_ms`. Nu conțin corpul cererii, URL-uri, tokenuri sau mesaje brute
ale excepțiilor. Nu se creează istoric de analize. Logurile sunt ieșire standard cu
rotație Docker, nu un sistem de alerte sau un serviciu de monitorizare AWS.
