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

Localizarea este un punct, deci nu pretindem măsurători pe parcelă sau analiză subparcelară.
POWER este context regional. Datele zilnice și metadatele sunt păstrate pentru ferestre
specifice culturilor; mediile anuale nu înlocuiesc expunerea din perioade sensibile.
Solul introdus de utilizator își păstrează sursa. Istoricul absent duce la reguli neverificate,
nu la presupunerea unui teren fără culturi anterioare.

## Moduri

- `NEXT_PUBLIC_USE_MOCK_API=true`: frontend independent cu fixture fix, vizibil demonstrativ.
- `ENGINE_MODE=demo`: backend real și Python, dar planuri fictive etichetate explicit.
- `ENGINE_MODE=computed`: contract pentru implementarea reală; P3/P4 sunt încă neimplementate
  și răspund 503. Nu există fallback automat către rezultate fictive.

## Date păstrate

Prisma deține doar `DataCache`: cheie, namespace, payload public și expirare. Căutările
geografice și seriile NASA pot fi reutilizate. Nu salvăm requesturi, rezultate, istorice,
telefon, email sau identificatori de utilizatori. Nu logăm payloaduri sau tokenuri.
