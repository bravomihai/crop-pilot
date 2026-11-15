# Design note: money per year for each plan

Status: phases 1 and 2 implemented on branch `tudor` (2026-11-15), not yet reviewed by the
team. `AGENTS.md` now says the money estimate must stay labelled as an estimate and must
never change the ranking.

## What was built (and where it differs from the proposal below)

- Engine: `services/engine/fieldshift/evaluator/economics.py`, called at the end of the
  computed pipeline; any failure leaves the plans unchanged and adds a data gap.
- Data: `services/engine/fieldshift/evaluator/rules/economics/ro_2026.json` and
  `ro_counties.json`, built by `services/engine/tools/build_economics_ro.py`, which downloads:
  - INS TEMPO AGR110A, county yields 2016–2025 (updated 29-06-2026);
  - INS TEMPO PPA102C, regional farm-gate prices 2021–2025 (updated 11-11-2026);
  - Eurostat GISCO county boundaries;
  - ECB EUR/RON on 30-09-2026 (5.2788).
- Costs: ICEADR budgets for the **2022–2023** production year (total cost = budget cost per
  tonne × budget yield), not the older 2021–2022 guide.
- **Pea has no official recent price or cost** (INS stopped dry pea prices in 2007; ICEADR has
  no pea budget), so any plan with pea shows income, costs and margin as unknown, with only
  its subsidies known. This is the main limitation today; see the follow-up below.
- Payment rates are those reported in the press for 2026 (BISS 101.03 €/ha, eco-scheme
  56.28 €/ha) and the 2025 soybean coupled rate (141.98 €/ha); still to check against the
  Order. CRISS is listed but not counted (no farm-size input yet).
- No new request inputs yet (farm size, young farmer, own prices and costs).

Follow-up worth discussing: let the farmer type their own price and cost for crops without
data (pea today), and their own costs generally.

## Goal

For every plan (and the current rotation), show in lei per year:
- the expected **income** from selling the crops;
- the expected **costs** of growing them;
- the **subsidies** the plan earns or helps the farm qualify for;
- the resulting **margin**.

Farmers decide in lei. Today a plan that is better for soil and water but earns less
looks strictly better; the farmer needs to see that trade-off.

## Non-goals (first version)

- No field-level yield prediction. Yields come from county statistics, not from our model.
- No price forecast. Prices are dated past values, shown as such.
- Money does **not** change the ranking. It is shown next to the agronomic scores. An
  optional "income" priority can be discussed later, once the numbers are trusted.
- No promise of subsidy amounts: eligibility is decided at farm level by APIA.

## What the farmer sees

On each plan card, a "Money per year (estimate)" block:

```
Income        4 900 – 7 300 lei/ha/year   county yields 2016–2025 × prices 2023–2025
Costs         4 600 – 5 600 lei/ha/year   published crop cost budgets, 2025
Subsidies     ~ 1 050 lei/ha/year          basic payment + eco-scheme; see conditions
Margin          1 350 – 3 750 lei/ha/year
Compared with your current rotation: + 400 lei/ha/year (typical)
```

(Numbers above are illustrative only, not computed.)

- Ranges, never a single number: low / typical / high.
- Each line says its data year and source. Unknown parts show "unknown", never 0.
- Subsidies are listed one by one with their condition, e.g. "Soybean coupled support
  (PD-09): about 142 €/ha in the 2025 campaign; paid only if you declare soybean to APIA."
- "At a glance" gets one line: "Typical margin: X lei/ha/year (current rotation: Y)".
- Fixed label: "Estimate from county averages and past prices. Not a forecast; your
  costs and prices differ. Check subsidies with APIA."

## Calculation

Per crop in the plan, per hectare:

1. **Yield range** (t/ha): the county's yields for that crop over the last 10 years
   (INS TEMPO table AGR110A, by county). Low = 20th percentile, typical = median, high = 80th.
   Drought years are part of the range on purpose.
2. **Price range** (lei/t): yearly average producer prices for the last 3 years (INS,
   also republished on the MADR crop pages). Optionally the latest EU weekly price for
   Romania as a "current market" reference line, not used in the range.
3. **Income** = yield × price, combining low with low and high with high (a deliberately
   wide range; correlation between yield and price is ignored in v1).
4. **Costs** (lei/ha): published technology cost budgets per crop (ICEADR), rainfed vs
   irrigated, with a ±15 % band. Later: let the farmer type their own cost per crop.
5. **Subsidies** (see below), converted at the campaign's official exchange rate.

Per plan:

- Sum the three crops, then divide by the **years the plan covers** (first sowing to last
  harvest, in months / 12). Three crops do not mean three years. Rounded to 50 lei.
- Months of bare soil earn nothing and cost nothing, which is already true of the sum.
- Baseline (current rotation) is computed the same way for the comparison.

Location → county: the field point must be mapped to a county. A small offline county
boundary file (public administrative boundaries) and a point-in-polygon lookup avoid a
new network call. Outside Romania or with no county data: "unknown".

## Subsidies (CAP Strategic Plan 2023–2027, paid by APIA)

"Greening" (2015–2022) was replaced in 2023 by eco-schemes and enhanced conditionality.
What matters for a crop-rotation planner:

| Payment | Depends on the plan? | How we show it |
|---|---|---|
| Basic income support, BISS (PD-01) | No: same for any eligible arable hectare | Amount per ha, same in every plan |
| Redistributive payment, CRISS (PD-02) | No: depends on farm size | Shown only if the farmer gives farm size; else "depends on your farm size" |
| Young farmer (PD-03) | No | Only if the farmer says so (new optional input) |
| Eco-scheme for arable land (PD-04) | **Yes** | "This plan helps you meet …"; amount shown as conditional |
| Coupled support: soybean (PD-09) | **Yes** | Amount per ha of soybean in the plan |
| Coupled support: legumes for industry (PD-11), alfalfa (PD-10) | Partly | Only for eligible crops; field pea for grain: **to verify** |
| Conditionality GAEC 7 (crop rotation) | **Yes** | Warning if the plan repeats a crop on the parcel in a way GAEC 7 does not allow |
| One-off national aids (drought aid, fertiliser grant) | Sometimes | Not included: one-off, often only drafts |

Key facts found (secondary sources unless marked; **verify against the Order in
Monitorul Oficial / APIA before use**):
- 2026 campaign rates reported from OMADR 288/2026: BISS 101.03 €/ha, CRISS 55.69 €/ha,
  young farmer 55.36 €/ha, eco-scheme PD-04 56.28 €/ha. (2025: BISS 89.34, CRISS 53.52.)
- Soybean PD-09: 155 €/ha (2024 campaign, OMADR 185/2025); about 142 €/ha reported for 2025.
  Legumes for industry PD-11: 230 €/ha (2024). Sunflower has no coupled support.
- Payments are made in lei at an exchange rate fixed per campaign (4.9753 lei/€ for 2024).
- PD-04 (official APIA 2026 form instructions): at least 85 % of the farm's arable land
  must be covered by crops; optional requirements include **crop diversification**
  (computed by APIA from the farm's area declaration) and **nitrogen-fixing legumes**.
  The exact thresholds must be read from the MADR 2026 eco-scheme guide. Consultants
  disagree on them, so we will not hard-code them from press articles.

Because eligibility is assessed for the **whole farm**, and we know only one field, the
honest output is: "This plan grows a legume and 3 different crops, which helps meet the
eco-scheme's diversification and legume requirements, **if the rest of your farm also
meets them**." A per-hectare amount is shown as "up to", with the condition.

## Data: one dated table per season

`services/engine/fieldshift/economics/data/ro_<year>.json` (or under the regional rules),
checked in, refreshed once per season by hand or by a script, never fetched during a
calculation:

```json
{
  "valid_for_campaign": 2026,
  "currency": "RON",
  "exchange_rate": {"eur_ron": 4.97, "source": "apia-order-2026", "date": "2026-09-30"},
  "prices_ron_per_t": {"winter_wheat": {"years": [2023, 2024, 2025], "values": [/* … */], "source": "ins-prices"}},
  "yields_t_per_ha": {"CL": {"winter_wheat": {"years": [/* 2016–2025 */], "values": [/* … */]}}},
  "costs_ron_per_ha": {"winter_wheat": {"rainfed": 4700, "irrigated": 6200, "year": 2025, "source": "iceadr"}},
  "payments": [
    {"id": "PD-01", "eur_per_ha": 101.03, "applies": "all_arable", "source": "omadr-288-2026"},
    {"id": "PD-09", "eur_per_ha": 141.98, "crops": ["soybean"], "source": "…"}
  ],
  "sources": [{"id": "ins-prices", "title": "…", "url": "…", "retrieved": "2026-11-15"}]
}
```

Every number cites a source id and a date, like the agronomic rules do.

## Contract (optional field, needs agreement)

One new optional field per plan (and baseline), so nothing breaks for consumers that
ignore it:

```ts
economics?: {
  per_year_ron_per_ha: {
    income: Range | null; costs: Range | null; subsidies: Range | null; margin: Range | null;
  };                                   // Range = { low, typical, high }; null = unknown
  subsidies: { id: string; label: string; ron_per_ha: number | null; condition: string }[];
  covered_years: number;               // plan length used to annualise
  data_year: number;                   // campaign the prices, costs and rates are from
  source_ids: string[];
  notes: string[];                     // e.g. "No county yields for this crop."
}
```

New optional request inputs (all skippable): farm arable area (ha), young farmer (yes/no),
own cost per crop. Not stored, like every other input.

## Who does what (proposal)

- **P3 (Tudor):** subsidy and GAEC 7 rules next to the regional rules; the per-plan
  economics calculation in the evaluator (it already knows the calendar and years covered).
- **P2 (Maria):** the season table: INS yields and prices, cost budgets, county lookup.
- **P4 (Alexia):** baseline comparison text; confirm money does not enter the ranking.
- **P5 (Mihail) / P1 (Andrei):** contract field, the card block, the At a glance line, the AI
  summary input (it must be allowed to quote these numbers).

## Phases

1. **Subsidies only** (smallest, rule-based, hardest to get wrong): which payments each
   plan earns or helps qualify for, GAEC 7 warning, indicative amounts. No yields needed.
2. **Margin ranges**: county yields × past prices − cost budgets, per year.
3. **Later**: adjust the yield inside the county range using our past-season water and
   heat replay; let the farmer enter own prices and costs; optional "income" priority.

## Source findings and their status

| Need | Source | Access | Status |
|---|---|---|---|
| County yields | INS TEMPO, table AGR110A (average yield per ha, by county) | TEMPO online, CSV export | Table confirmed via county INS publications; export to test |
| Yearly prices | INS producer prices; republished on MADR crop pages (e.g. wheat 2021–2025 about 0.90–1.49 lei/kg, 2025: 0.94) | TEMPO; madr.ro **blocks automated access** (HTTP 403 WAF) | Copy by hand from MADR/INS |
| Weekly prices | European Commission Agri-food data portal, API base `https://api.tech.ec.europa.eu/agrifood` | Public API, rate-limited (hit the quota during testing) | Romania series exists for oilseeds; cereal endpoint and parameters to confirm |
| MADR weekly market bulletins | "Prețul cerealelor pe piețele reprezentative" | Latest files seen are from 2017 | Not usable as a current source |
| County lease reference prices | Yearly prices set by county councils for lease income tax | Per county, official | Fiscal values, often below market: cross-check only |
| Crop costs | ICEADR technology budgets; ICEADR guide with cost calculations (2022) | PDF | 2025/2026 per-ha tables not found yet; ask ICEADR or use RICA |
| Cost cross-check | RICA / FADN farm accounts (MADR reports; EU FADN database) | PDF / EU portal | To use for validating totals |
| Payment rates | Yearly OMADR order in Monitorul Oficial; APIA | Official text | 2026 rates seen only via press; read the Order |
| Eco-scheme rules | APIA 2026 application instructions (Annex 2); MADR 2026 eco-scheme guide | PDF | Main requirement confirmed; thresholds to read from the guide |

Press figures for orientation only (do not use as data): wheat production cost about
800–950 lei/t; maize about 6 500 lei/ha in 2026; a worked farm example with about
6 085 lei/ha average total cost across five crops.

## Risks

- **Looks precise, is not.** Mitigated by ranges, dated sources, labels, and keeping money
  out of the ranking.
- **Stale data.** Each table is tied to a campaign year; after its season the UI says the
  figures are from last year.
- **Subsidy rules change every year** and depend on the whole farm. We only say what a
  plan *helps* with, and link to APIA.
- **Legal/perception:** not financial advice; the disclaimer covers money as well.

## Open questions for the team

1. Do we change the `AGENTS.md` scope line ("No yield or profit forecast")? Who approves?
2. Phase 1 only for the demo, or phases 1 and 2?
3. Is it acceptable to ask for farm size (for CRISS and eco-scheme context)?
4. Per hectare only, or also "for your N hectares" if the farmer gives field area?
5. Should the AI summary mention money, given the numbers are rough ranges?

## Sources consulted (2026-11-15)

- [APIA, 2026 payment application instructions (Annex 2)](https://apia.org.ro/wp-content/uploads/2026/03/Anexa-2.pdf)
- [MADR, eco-scheme guide 2026 (vegetal sector)](https://www.madr.ro/docs/dezvoltare-rurala/agro-mediu/2026/Ghid-informativ-privind-aplicarea-eco-schemelor-din-sectorul-vegetal-Campania-2026.pdf)
- [Monitorul Oficial, Annex 0/2026 (PD-04 optional requirements)](https://www.infodosar.ro/monitorul-oficial/ministerul-agriculturii-si-dezvoltarii-rurale/1293-anexa-0-2026)
- [Revista Ferma, 2026 advance payment rates](https://revista-ferma.ro/plata-avans-apia-2026-sume-pe-hectar-si-cap-de-animal/)
- [Agrointel, 2026 advance payment calculation](https://agrointel.ro/359677/avans-apia-2026-calcul-pe-hectar-cati-bani-vor-intra-in-conturile-fermierilor-din-16-octombrie)
- [Revista Ferma, coupled support order (2024 campaign)](https://revista-ferma.ro/ordin-subventii-apia-in-monitorul-oficial-plati-apia-care-scad-anul-acesta/)
- [BZI, coupled support rates (soybean, legumes)](https://www.bzi.ro/s-a-stabilit-cuantumul-pe-hectar-pentru-sprijinul-cuplat-vegetal-fermierii-asteapta-banii-de-anul-trecut-5517994)
- [Revista Ferma, 2026 fertiliser grant based on ICEADR budgets](https://revista-ferma.ro/bani-pentru-ingrasaminte-2026-vezi-sumele-pentru-fiecare-cultura-si-calendarul-platilor-apia/)
- [ICEADR, crop guide with cost calculations (2022)](https://iceadr.ro/wp-content/uploads/2024/02/2022_ghid-veget.pdf)
- [MADR, wheat page (yearly INS prices)](https://www.madr.ro/culturi-de-camp/cereale/grau.html)
- [MADR, weekly cereal prices on representative markets](https://www.madr.ro/pretul-cerealelor-pe-pietele-reprezentative-din-romania.html)
- [MADR, RICA standard results](https://www.madr.ro/docs/rica/Raport-RICA-2019.pdf)
- [INS Vrancea, table AGR110A (average yield per ha by county)](https://vrancea.insse.ro/wp-content/uploads/2024/04/AGR110A-Productia-medie-la-hectar-la-principalele-culturi-pe-forme-de-proprietate-judet.pdf)
- [European Commission Agri-food data portal, cereals API](https://agridata.ec.europa.eu/extensions/API_Documentation/cereals.html)
- [Agrointel, worked farm cost example](https://agrointel.ro/357547/costurile-si-veniturile-unei-ferme-calcul-cezar-gheorghe)
- [Agro TV, maize costs 2026](https://agro-tv.ro/romania-cultiva-in-2026-peste-15-milioane-hectare-de-porumb-dar-profitul-ramane-incert-la-950-lei-tona/)
- [Agro TV, wheat cost per tonne](https://agro-tv.ro/grau-la-203-e-t-si-scade-vinzi-acum-sau-astepti-calculul-pe-care-trebuie-sa-il-faci-azi-neaparat/)
- [Focus Press, Constanța county reference prices for 2027](https://focuspress.ro/consiliul-judetean-constanta-propune-noi-preturi-medii-pentru-produsele-agricole-in-2027-cat-ar-urma-sa-coste-graul-porumbul-si-floarea-soarelui-f40e03aa1/)
- [Puterea, GAEC 7 crop rotation rules](https://www.puterea.ro/?p=519345)
