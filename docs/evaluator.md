# P3 evaluator

Code: `services/engine/fieldshift/evaluator/`. Rules: `evaluator/rules/ro_south.json`.
Tests: `services/engine/tests/test_evaluator.py`, using a Bărăgan fixture
(`tests/fixtures/environment-ro-south.json`); the fixture is not a geographic coverage limit.

```python
rules = load_rules(request["location"])           # zone rules, or no crops outside covered zones
result = evaluate(rotation, request, environment, rules)
```

`evaluate` does not read `priorities`; P4 applies them.

## What it does

1. **Calendar.** Places each crop in the first regional sowing window still open after
   the field is free: `available_from` for the first crop, then harvest + 7 days. It uses
   the optimal window, or the late window with a warning. Autumn crops cross the year.
2. **Rules.** Successor matrix (good / ok / poor / forbidden, with the reason: white mould,
   cereal diseases, Fusarium, legume after legume), return intervals (sunflower 6 years,
   rapeseed and pea 4, soybean 3), maximum consecutive seasons, and the farmer's excluded
   crops. The last history crop counts for the first step. A forbidden succession, interval
   or exclusion makes the plan `infeasible`, and the reason is listed in `violations`.
3. **Replay.** The whole plan is moved back over every past season that fits in the
   weather record (18 seasons with 21 years of data). For each one:
   - **FAO-56 daily soil water balance:** Kc curve by growth stage, roots that deepen,
     the p depletion fraction, and a stress coefficient Ks. One 1.5 m profile carries water
     from crop to crop, so a crop that dries the soil affects the next one.
   - **Crop hazards:** heat in flowering and grain fill, winterkill, frost at flowering or
     on seedlings, drought at sowing, and maize degree days.
   - **EcoCrop temperature fit.**
   - **The what-if scenario** shifts every day's temperature and scales its rain.
     Reference ET is recomputed (Penman-Monteith), so warmer air also means more demand.
4. **Scores** from 0 to 1, higher is better. Seasons are combined as 0.7 × mean + 0.3 ×
   20th percentile, so plans that fail in dry years are penalised.

| Criterion | Method | Basis |
|---|---|---|
| `water` | Water-limited relative yield, 1 − Ky (1 − ETa/ETc) (FAO-33 Ky), rainfed | derived |
| `climate` | (1 − combined hazard risk) × EcoCrop temperature fit | derived |
| `soil` | Index from succession, families and legumes, months with a main crop, residues; erosion when slope is known | estimated |
| `productivity` | Irrigated yield if irrigated × (1 − climate risk) × previous-crop factor × sowing-date factor × pH fit | estimated |

Missing weather gives `null` for water, climate and productivity, never a neutral value.
Missing soil texture, pH or slope is listed in `data_gaps` and in `local_checks`.

## Output (for P4)

Everything `recommender/evaluation.py` reads: `feasibility`, `violations`,
`criteria.{water,soil,climate}` and `productivity` (score, basis, summary, source_ids),
`calendar`, `warnings` (with severity), `data_gaps`, `sources`, `source_ids`,
`scenario_applied` and `fixture: false`.

Extra keys that the contract allows for plans and P4 can pass on:

- `local_checks`: what to verify with an agronomist. Maps to `plan.local_checks`.
- `criteria.*.score`: maps to `plan.scores`.
- `violations`: for the `baseline` plan.
- `assumptions`: method assumptions for `result.assumptions`.
- `details[]` per step: water need and season rain (mm), mean and worst WRSI, seasons with
  severe water shortage, number of seasons with each hazard, temperature fit, irrigation
  need, succession class, late sowing.
- `replay[]` per past season, oldest first: scores and per-crop values. It is in the contract
  as `plan.replay`, and the recommender passes it through for plans and the baseline. For charts ("how this plan would
  have done in 2007, 2012, …").
- `soil_inputs`, `soil_components`: where the soil values came from.

## What it needs from P2 (`build_environment`)

| Key | Required | Notes |
|---|---|---|
| `daily[]` with `date`, `tmin`, `tmax`, `tmean`, `precip` | **yes** | P2 cleans NASA POWER names into °C and mm/day; missing values stay `None`. At least ~6 complete years; 20 is better. |
| `daily[]` humidity, dewpoint, wind, radiation, `et0` | recommended | P2 computes FAO-56 Penman-Monteith ET0 when inputs are available, otherwise Hargreaves. P3 recomputes ET0 when a temperature scenario is applied. |
| `static.elevation_m` | recommended | Read from NASA POWER; used in Penman-Monteith ET0. |
| `static.soil` (SoilGrids, depth-weighted 0–30 cm) | recommended | Clay, sand, silt, pH and organic carbon are modelled estimates. Texture and estimated available water capacity affect the water balance; pH affects relative productivity. SoilGrids is not a field analysis. |
| `static.slope_pct` (SRTM) | optional | A 3×3 point-neighborhood estimate; adds erosion to the soil score, not a field-wide measurement. |
| `sources[]` with `id` and **`title`** | yes | Without a title, the dataset name is used. |
| `data_gaps[]` at the top level | yes | The pipeline reads it from there. |
| `quality` | recommended | Daily row count, missing source values, and ET0 method counts; used to describe coverage, not as a substitute for field validation. |

Not used yet: SMAP soil moisture (could set the starting soil water), CMIP6 deltas
(scenario presets), GAEZ attainable yields (productivity), Sentinel-2 crop history.

## Review status

**Verified against the source** (2026-11-14):
- FAO-56 Kc mid and end values, stage lengths, root depth, depletion fraction, Ky and available water;
- EcoCrop temperature and pH ranges.

**Expert estimates waiting for an agronomist** (listed in the rules file under
`review_status`):
- regional sowing and harvest windows;
- the successor matrix and return intervals;
- hazard thresholds;
- soil-index weights;
- succession and late-sowing yield factors;
- some Kc ini and stage values that FAO-56 doesn't give per crop.

Change the JSON, not the code.

## Climate context (`result.climate_context`)

`data_service.climate_context(daily, source_ids)` turns cleaned daily data into one row per
complete calendar year. The pipeline prefers this P2 result and retains the evaluator version
as a fallback for older environment fixtures. The values are observed only; the scenario never
touches them. Annual fields remain `null` when their input series has missing days.

| Field | Meaning |
|---|---|
| `rain_mm`, `et0_mm` | Yearly rain and reference evapotranspiration (FAO-56) |
| `tmean_c` | Mean temperature |
| `hot_days_gt32` | Days with a maximum above 32 °C |
| `frost_days` | Days with a minimum at or below 0 °C |
| `heavy_rain_days_gt20mm` | Days with more than 20 mm of rain |
| `dry_spell_max_days_apr_sep` | Longest run of days with less than 1 mm of rain, April–September |
| `last_spring_frost_doy`, `first_autumn_frost_doy` | Day of year of the last frost before July and the first from July; `null` = none |

`trends` gives the mean and a simple linear slope per decade for each field, when there are at
least 10 years. Over a short record they swing with the first and last years, so show them as
a direction, not a rate.

On the Bărăgan test point (NASA POWER, 2005–2025):
- temperature +1.0 °C per decade;
- days above 32 °C +14 per decade;
- rain −79 mm per decade;
- ET0 +82 mm per decade.

This is crop-independent and could move to the data service (P2) later; the output would not change.
