# Current architecture

```text
Browser (React in Next.js)
  POST /api/recommendations
        │ validates the request and generates request_id
        ▼
Next.js backend ── HTTP + internal token ──► FastAPI
        │                                    pipeline
        │                         data_service → evaluator → recommender
        ◄──────── validated JSON result ─────────┘
        │
        ▼
Three plans + calendars + trade-offs + sources + data gaps

PostgreSQL/Prisma: optional public-data cache, accessed only through Next.js.
```

There are no accounts, persistent sessions, saved farms, or historical analyses to retrieve.
This version has no job queue: calculation uses request/response, an explicit timeout,
and reusable cached data. Add a queue only if actual execution times require it;
do not persist farmer data in anticipation of an unrequested use case.

## Agricultural time

`crop_count=3` means three successive main crops, not three years or three harvests
of the same crop. An autumn crop crosses calendar years. Check the end of harvest
before the next sowing starts. Do not assume a repeating C→A transition after the last
step. Cover crops and perennial crops are future extensions.

## Data and uncertainty

The current map interface submits a point; the API can also validate an optional GeoJSON
field boundary against Romania. NASA POWER remains regional context from the representative
point's grid cell. For a boundary, SoilGrids and SRTM use up to three distributed interior
samples and average available values. This sparse sampling is not parcel-wide raster zonal
statistics, and the response reports the limitation.

Daily POWER data and metadata are retained for crop-specific windows; annual averages do
not replace exposure during sensitive periods. User-entered soil retains its source.
Missing crop history leaves predecessor rules unverified; it does not imply that the field
had no previous crops. Slope is estimated from a roughly 30 m SRTM 3×3 neighborhood at
each sampled point through OpenTopoData; it is not the slope of the entire parcel.

## Modes

- `NEXT_PUBLIC_USE_MOCK_API=true`: independent frontend using a fixed, visibly labelled fixture.
- `ENGINE_MODE=demo`: real backend and Python service, but explicitly labelled fictional plans.
- `ENGINE_MODE=computed`: real-data integration; returns 503 when required data/modules
  are unavailable. It never falls back automatically to fictional results.

## Retained data

Prisma contains only `DataCache`: key, namespace, public payload, and expiration.
Geographic search results and NASA series may be reused. Do not save requests,
results, crop histories, phone numbers, email addresses, or user identifiers.
Do not log payloads or tokens.

The transparent, non-ML screening covers Romania and validates coordinates against the
geoBoundaries ADM0 boundary. Outside the locally described southern/south-eastern plains,
it selects a warm, temperate, or cool thermal band using April–September NASA POWER
temperatures and shifts calendars provisionally. These bands and adjustments are project
estimates, not official zoning or locally validated crop calendars.

The rules currently include 15 crops. General FAO-56 parameters feed the water balance;
Romanian calendars, crop suitability ranges, hazards, and rotation guidance remain
estimates requiring agronomist validation. Ranking combines historical precipitation/ETc
suitability, a lower-tail seasonal score, and a structural proxy for family diversity and
legume presence. Water and climate scores are correlated, not independent predictions.

Computed responses include monthly daily-temperature summaries and, for selected crops,
historical counts of days above screening thresholds during estimated sensitive months,
along with the number of observed years. These explanatory thresholds do not change
ranking and are not validated damage predictions.

SoilGrids provides modeled 0–30 cm profile estimates. Texture and estimated available
water inform the water balance; pH informs relative production potential. Organic carbon
influences the available-water estimate, not a soil-fertility-change score. SoilGrids does
not replace laboratory analysis. Yield and profit are not predicted, and effective rainfall
and runoff are not yet modeled.

SRTMGL1 v003 covers 60°S–60°N, including Romania. Slope uses the mean Horn 3×3 estimate
at up to three field samples, not the slope of the whole parcel. Public OpenTopoData has
published limits of one request per second and 1,000 per day; field samples are batched
into one request, but higher traffic will require a suitably scaled data strategy.

## Language

Project documentation, interface text, and generated explanations use English.
Localized provider responses use English and language-specific cache keys.
Geographic proper names and original source identifiers retain their spelling.
