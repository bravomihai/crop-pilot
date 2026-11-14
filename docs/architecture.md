# Arhitectura curentă

```text
Browser (React în Next.js)
  POST /api/recommendations
        │ validează cererea și generează request_id
        ▼
Backend Next.js ── HTTP + token intern ──► FastAPI
        │                                  pipeline
        │                       data_service → evaluator → recommender
        ◄──────── rezultat JSON validat ────────┘
        │
        ▼
Trei planuri + calendare + compromisuri + surse + lipsuri

PostgreSQL/Prisma: cache opțional de date publice, accesat numai prin Next.js.
```

Nu există conturi, sesiuni persistente, ferme salvate sau analize de recuperat din istoric.
Nu există coadă de joburi în această versiune: calculul este request/response, cu timeout
explicit și date reutilizabile în cache. O coadă poate fi adăugată dacă duratele reale o cer;
nu persistăm datele fermierului anticipând un caz care nu a fost cerut.

## Timpul agricol

`crop_count=3` înseamnă trei culturi principale succesive, nu trei ani și nu trei recolte
ale aceleiași culturi. O cultură de toamnă traversează anul calendaristic. Verificăm
sfârșitul recoltării înainte de începutul semănatului următor. Nu presupunem repetabilitate
C→A după ultimul pas. Culturile de acoperire și plantele multianuale sunt extensii ulterioare.

## Date și incertitudine

Fermierul poate trimite un contur GeoJSON de tip Polygon; limita este verificată să rămână
în România. Sistemul acceptă puncte din întreaga țară. NASA POWER, SoilGrids și SRTM sunt
interogate pentru punctul reprezentativ, nu agregate pe întreaga parcelă; răspunsul semnalează
această limitare.
POWER este context regional. Datele zilnice și metadatele sunt păstrate pentru ferestre
specifice culturilor; mediile anuale nu înlocuiesc expunerea din perioade sensibile.
Solul introdus de utilizator își păstrează sursa. Istoricul absent duce la reguli neverificate,
nu la presupunerea unui teren fără culturi anterioare.
Panta este estimată dintr-un vecin de 3×3 puncte SRTM de aproximativ 30 m, prin OpenTopoData;
API-ul primește coordonatele, are limite publice de utilizare și nu reprezintă panta întregii parcele.

## Moduri

- `NEXT_PUBLIC_USE_MOCK_API=true`: frontend independent cu fixture fix, vizibil demonstrativ.
- `ENGINE_MODE=demo`: backend real și Python, dar planuri fictive etichetate explicit.
- `ENGINE_MODE=computed`: folosește NASA POWER, ET0 FAO-56, reguli regionale și clasare
  transparentă; cere `ENABLE_NASA_POWER=true`. Fără fallback automat către rezultate demo.

## Screening-ul rotațiilor

Modelul transparent, fără ML, acoperă România și verifică coordonatele cu limita
geoBoundaries ADM0.
Un profil termic cald, temperat sau răcoros este ales din media NASA POWER aprilie–septembrie;
aceste benzi și ajustările lunilor de semănat/fazelor sensibile sunt estimări de proiect,
nu zonare oficială sau calendare validate local. Păstrează cele cinci culturi inițiale și
coeficienți FAO-56 generali. Clasarea combină adecvarea istorică precipitații/ETc, percentila 10 a
observațiilor pe sezoane și un proxy structural pentru diversitatea familiilor/faza de
leguminoase. Ultimele două scoruri de apă/climă sunt corelate, nu predicții independente.
Răspunsul calculat include rezumate lunare ale temperaturilor zilnice maxime și minime;
pentru culturile selectate, adaugă și numărul istoric al zilelor peste pragurile de screening
din lunile sensibile estimate, cu numărul anilor observați. Pragurile sunt literatură generală,
ferestrele sunt estimări provizorii pentru profilul termic selectat; aceste avertismente explicative nu schimbă
clasarea și nu reprezintă predicții validate ale vătămării termice.
SoilGrids oferă estimări modelate pentru profilul 0–30 cm. Textura și capacitatea de apă
disponibilă estimată intră în bilanțul hidric, iar pH-ul în potențialul relativ de producție;
carbonul organic influențează estimarea capacității de apă, nu un scor al schimbării
fertilității. Valorile SoilGrids nu înlocuiesc analiza de laborator. Nu se estimează producția
sau profitul; precipitația efectivă și scurgerea nu sunt încă modelate.
SRTMGL1 v003 acoperă latitudinile 60°S–60°N, inclusiv toată România. Accesul public
OpenTopoData este limitat la 1 cerere/secundă și 1000 cereri/zi; pentru trafic mai mare
va fi necesară o strategie de date cu capacitate potrivită.

## Date păstrate

Prisma deține doar `DataCache`: cheie, namespace, payload public și expirare. Căutările
geografice și seriile NASA pot fi reutilizate. Nu salvăm requesturi, rezultate, istorice,
telefon, email sau identificatori de utilizatori. Nu logăm payloaduri sau tokenuri.
