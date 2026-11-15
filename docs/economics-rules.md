# How the money estimate is calculated

This document lists every rule behind the "Money per hectare a year" block on a plan. The
code is `services/engine/fieldshift/evaluator/economics.py`; the data is built by
`services/engine/tools/build_economics_ro.py` into
`services/engine/fieldshift/evaluator/rules/economics/ro_2026.json`. The design background is
in [economics-design.md](economics-design.md).

**What it is:** a rough estimate in lei per hectare per year, from official statistics and
published cost budgets. **What it is not:** a forecast, a yield or price prediction, or advice.
It never changes the ranking of the plans. Unknown values are shown as unknown, never as zero.

## 1. The calculation in one line

For each crop in the plan (one season each):

```
income  = expected yield × price
costs   = crop budget (indexed) − nitrogen saved by a legume before it
```

Then, for the whole plan:

```
per year = (sum over the 3 crops) ÷ years the plan covers
margin   = income − costs + subsidies
```

Every figure is a **range**: bad year / typical / good year. The page shows the typical value
in bold and the range under it.

## 2. Where the plan's length comes from

`years = (last harvest end − first sowing start) ÷ 365.25`, at least 0.5. Three crops do not
mean three years: a plan of winter wheat, sunflower and barley covers about 2.8 years, so its
totals are divided by 2.8. Months of bare soil are inside the period and earn nothing.

## 3. Yield (tonnes per hectare)

| Rule | Value |
|---|---|
| Source | INS TEMPO tables AGR108A, AGR109A (area and production by county and type of holding) and AGR110A (average yield) |
| Which county | The county that contains the field point (Eurostat county boundaries, offline) |
| Which farms | **Commercial farms** = (total − individual holdings) production ÷ area. Years with too little commercial area (under 200 ha or under 10 % of the county's area of that crop) are dropped. If fewer than 5 years remain, **all farms** are used instead, and the card says so |
| Years used | The last 10 years (2016–2025 in the 2026 data file) |
| Bad / typical / good | 20th percentile, median, 80th percentile of those years |
| No county series | The Romanian national yield from Eurostat apro_cpsh1 (last 10 completed years), and the card says so. Today this applies to triticale everywhere, and to crops such as sugar beet in counties that do not grow them |
| Spring barley | AGR110A has no column of its own: its yield is "barley and two-row barley" minus "barley" from AGR108A/AGR109A, county by county |
| Minimum data | At least 5 yearly values, otherwise the yield is unknown |
| Irrigation | If the farmer says irrigated: yield × (ICEADR irrigated yield ÷ ICEADR rainfed yield) of that crop, because county averages are mostly rainfed |

Drought years stay in the data on purpose: they are what the "bad year" end of the range shows.

### Previous-crop effect on yield

The regional rules (`ro_south.json`, table `successor`) rate every "previous crop → crop" pair
as good, ok, poor or forbidden, with yield factors 1.0, 0.95, 0.85 and 0.75. County averages
mix fields after every kind of previous crop, so they are treated as the **ok** level:

```
yield after a good previous crop = county yield × 1.0 ÷ 0.95   (about +5 %)
yield after an ok previous crop  = county yield                (no change)
yield after a poor previous crop = county yield × 0.85 ÷ 0.95  (about −10 %)
```

The first crop of a plan uses the **last crop in the farmer's history** as its previous crop
(the entry with the latest harvest year, or the last one listed). With no history, no effect
is applied to the first crop.

These factors are the project's own agronomic assumptions and need review by a local agronomist.

## 4. Price (lei per tonne)

| Rule | Value |
|---|---|
| Source | INS TEMPO table PPA102C, average farm-gate prices by development region, lei/kg × 1,000 |
| Which region | The region of the field's county; if the region has no series, the national average is used and the card says so |
| Years used | The last 3 data years (2023–2025 in the 2026 data file). A crop with no price in those years may use its latest price from up to 5 years back, and the card says from which year ("the latest official price is from 2022"). Older prices count as unknown |
| Value used for income | **Median** of those years (typical). The range of the 3 years is listed in the details, but it does not widen the income range |
| Farmer's own price | Replaces the price for that crop completely |
| No official series | A labelled **market estimate** is used (see section 9): pea (INS stopped dry pea prices in 2007), grain sorghum and rye (no INS or Eurostat price), and sugar beet (latest official price 2022). Without any figure, the crop's income and the plan's totals are unknown |

Income range: `yield (bad year / typical / good year) × typical price`. Price swings are shown
separately so that one bad year of weather and one bad year of prices are not stacked.

## 5. Costs (lei per hectare)

| Rule | Value |
|---|---|
| Source | ICEADR income and cost budgets per hectare, conventional system, production year 2022–2023 (Ursu et al.), for wheat, barley, maize, sunflower, rapeseed and soybean |
| Budget total | The budget's production cost per tonne × its planned yield, rainfed or irrigated |
| Indexing | × a cost index built from Eurostat apri_ap_ina (Romanian purchase prices): fertiliser nitrogen (average of ammonium nitrate 33 % and urea, per kg N) and diesel, from the 2022–2023 average to the latest year (2024) |
| Index shares | Nitrogen fertiliser 37.3 % and mechanised work 38.2 % of the budget (from the ICEADR rainfed wheat budget); mechanised work follows the diesel price; the remaining 24.5 % is kept as it is |
| Index now | Nitrogen +8.4 %, diesel −7.9 %, so the factor is **1.001** (costs barely change) |
| Farmer's own cost | Replaces the budget cost for that crop |
| Stand-in budget ("proxy") | Crops ICEADR has no budget for use the budget of the closest crop, and the card says so: oats and spring barley ← winter barley; triticale and rye ← winter wheat; grain sorghum ← maize; dry beans ← soybean. These pairings are expert choices pending agronomist review |
| No budget | Costs are unknown. Pea now uses the soybean budget as a stand-in |
| Yield far below the budget | If the yields used are under 70 % of the yield the budget is written for (for example all-farm potato yields of about 10 t/ha against a 16.7 t/ha budget), the card warns that the margin is probably too low for a commercial farm |

Other costs are not counted: land rent, loans, taxes, storage, drying, transport and the
farmer's own labour beyond what the budgets include.

### Nitrogen saved by a legume before the crop

If the previous crop is a legume (**pea, soybean or dry beans**) and the crop itself is not a legume, its cost is
lowered by the fertiliser it no longer needs:

```
saving = kg N left by the legume × nitrogen price (lei per kg N)
kg N   = 20 (low) / 35 (typical) / 50 (high)
price  = 5.34 lei per kg N (Eurostat, 2024)
```

So the typical saving is 35 × 5.34 ≈ 187 lei per hectare. The kilograms come from Romanian
fertilisation practice (a 30–50 kg N/ha lower dose after soybean or pea, with 35 as a worked
example) and a long-term study that found about 20 kg N/ha less fertiliser for wheat after pea
(Soon, 2005). No saving applies to a legume after a legume, or to the first crop without
history.

The saving widens the cost range: low cost pairs with the high saving.

## 6. Subsidies (CAP payments, lei per hectare per year)

Rates are in euro and converted at the ECB EUR/RON reference rate of 30 September of the
campaign year (**5.2788** for 2026).

| Payment | Rate | How it is counted |
|---|---|---|
| Basic income support, BISS (PD-01) | 101.03 €/ha | Counted fully, every year, in every plan. About 530 lei |
| Soybean coupled support (PD-09) | 141.98 €/ha (2025 claim year) | Counted for each soybean season in the plan, divided by the plan's years |
| Eco-scheme for arable land (PD-04) | 56.28 €/ha | **Only in the high estimate**, because it depends on the whole farm meeting the scheme. The card says whether the plan grows a legume or 3 different crops, which helps meet its optional requirements |
| Coupled support for legumes for processing (PD-11) | 209.70 €/ha (2025 claim year) | Dry beans only; **only in the high estimate**, because it needs a processing contract |
| Coupled support for sugar beet (PD-16) | 818.19 €/ha (as reported for 2025; sources disagree) | Counted for each sugar-beet season, divided by the plan's years: sugar beet is only grown under a factory contract |
| Redistributive payment, CRISS (PD-02) | depends on farm size | Listed, **never counted**: farm size is not asked |

Low and typical subsidies are the sure payments; high adds the eco-scheme.
Sunflower and the cereals have no crop-specific payment. Young-farmer support and one-off aids
(drought aid, fertiliser grants) are not included.

Rates marked "reported" come from the farming press and the APIA application instructions and
still need checking against the ministerial order. Eligibility is decided by APIA for the whole
farm; the estimate only says what a plan helps with.

**Rotation warning (GAEC 7):** if a plan puts the same crop twice in a row, the card warns that
the EU crop-rotation standard may reduce payments. No amount is deducted.

## 7. Putting it together

Per crop (one season):

```
income (bad / typical / good) = yield (bad / typical / good, after previous-crop factor) × typical price
costs  (low / typical / high) = indexed budget − nitrogen saving (high / typical / low)
```

Per plan, per year:

```
income  = Σ income over the 3 crops ÷ years
costs   = Σ costs  over the 3 crops ÷ years
subsidies = BISS + soybean support ÷ years  (+ eco-scheme in the high case)
margin low     = income low     − costs high + subsidies low
margin typical = income typical − costs typical + subsidies typical
margin high    = income high    − costs low  + subsidies high
```

If any crop's income or costs is unknown, the plan's income, costs and margin are unknown; its
subsidies are still shown. A plan is never partly summed.

### Crop-order effect shown on the card

For each crop after a previous crop:

```
effect = (yield with the previous-crop factor − yield without it) × typical price
         + typical nitrogen saving
```

The plan's "of which from crop order" is the sum of the three effects ÷ years. It is already
inside the margin; the line only shows how much of it comes from the order of the crops.

### Rounding

Per-crop amounts are rounded to 10 lei; per-year amounts to 50 lei. Yields are shown to 0.01 t/ha.

## 8. A worked example (Călărași county, rainfed, 2026 data)

Winter wheat **after maize** (an "ok" previous crop):

| Step | Value |
|---|---|
| Yield, commercial farms, typical | 5.56 t/ha |
| Price, SUD-MUNTENIA median 2023–25 | 940 lei/t |
| Income | 5.56 × 940 ≈ **5,230 lei** |
| Cost | 5,417 × 1.001 ≈ **5,420 lei** |

The same wheat **after pea** (a good previous crop):

| Step | Value |
|---|---|
| Yield | 5.56 ÷ 0.95 ≈ 5.86 t/ha |
| Income | 5.86 × 940 ≈ **5,510 lei** |
| Nitrogen saving | 35 kg × 5.34 ≈ 187 lei |
| Cost | 5,423 − 187 ≈ **5,230 lei** |
| Crop-order effect | (5.86 − 5.56) × 940 + 187 ≈ **+470 lei** for this season |

## 9. Coverage by crop (2026 data file)

| Crop | Yield | Price | Cost |
|---|---|---|---|
| Winter wheat, winter barley, maize, sunflower, rapeseed, soybean | County (commercial farms) | Regional | ICEADR |
| Pea | County | Market estimate (feed-pea listings, 2026) | Proxy (soybean) |
| Oats | County | National | Proxy (winter barley) |
| Spring barley | County (derived) | Regional | Proxy (winter barley) |
| Triticale | **National** | National (2025 only) | Proxy (winter wheat) |
| Winter rye | County (mostly all farms) | Market estimate (derived from wheat) | Proxy (winter wheat) |
| Grain sorghum | County (mostly all farms) | Market estimate (reference price and listings, 2026) | Proxy (maize) |
| Dry beans | County (all farms) | National | Proxy (soybean) |
| Sugar beet | County where grown, else national | Market estimate (factory contracts 2025-2026) | ICEADR |
| Potato (main crop) | County (mostly all farms) | Regional | ICEADR |

Every crop now has a figure. "Market estimate" means no recent official price exists: the value comes
from contracts, reference prices or sale listings, is labelled on the plan, and should be replaced by
the farmer's own price where known:

| Crop | Low / typical / high (lei/t) | Basis |
|---|---|---|
| Field pea | 1,100 / 1,300 / 1,800 | Feed-pea sale listings for the 2026 harvest, mostly 1.30-2.00 lei/kg asking prices |
| Grain sorghum | 900 / 1,000 / 1,200 | 2026 county reference price 1.00 lei/kg; listings 1.10-1.20 lei/kg; close to maize |
| Winter rye | 750 / 850 / 1,000 | No rye quote found; derived from bread wheat (850-1,017 lei/t on the exchange, July 2025), which rye trades below |
| Sugar beet | 140 / 160 / 190 | Factory contracts 2025-2026: 26.2 EUR/t base, up to about 36 EUR/t with sugar bonuses |

Price order: a recent official price (last 3 data years) wins; otherwise the market estimate;
otherwise an official price up to 5 years old, with its year shown; otherwise unknown.

## 10. Known limits

- **Averages, not your field.** County and regional statistics; a good farm can do better and
  a poor soil worse. Use your own prices and costs where you know them.
- **Market estimates are not statistics.** Pea, sorghum, rye and sugar beet prices come from contracts,
  reference prices and sale listings (asking prices run above what farmers are paid); the rye price is
  derived from wheat. Replace them with your own prices where you know them.
- **Costs are from 2022–2023**, indexed only for nitrogen and diesel up to 2024. Fertiliser
  prices rose again in 2026 (press reports of +40 %), which the data does not yet show.
- **The farmer's own cost and the nitrogen saving can overlap.** If a farmer enters a cost for
  wheat that already assumes a legume before it, the saving is subtracted a second time. Enter
  the cost as for a field without a legume predecessor.
- **Price and yield are not linked.** A drought year usually also raises prices; the range does
  not model that.
- **Subsidy rates** for 2026 are as reported, and eligibility depends on the whole farm.
- **Previous-crop factors and the nitrogen credit** are assumptions that a local agronomist
  should confirm.
- **Romania only.** Outside the Romanian county data the estimate is not produced.

## 11. Sources

- INS TEMPO: AGR108A, AGR109A, AGR110A, PPA102C (statistici.insse.ro).
- ICEADR: *Ghid practic tehnico-economic … estimări pentru anul de producție 2022–2023*
  ([PDF](https://iceadr.ro/wp-content/uploads/2024/02/2023_ghid-veget.pdf)).
- Eurostat: apri_ap_ina (purchase prices of agricultural inputs), apro_cpsh1 (national crop yields) and
  GISCO NUTS 2021 county boundaries.
- ICEADR 2022–2023 budgets also cover potato and sugar beet; the 2021 guide has no budgets for the other new crops.
- ECB EUR/RON reference rate.
- APIA 2026 application instructions
  ([Annex 2](https://apia.org.ro/wp-content/uploads/2026/03/Anexa-2.pdf)) and press reports of the 2026 and
  coupled-support rates
  ([Revista Ferma](https://revista-ferma.ro/plata-avans-apia-2026-sume-pe-hectar-si-cap-de-animal/),
  [BZI](https://www.bzi.ro/s-a-stabilit-cuantumul-pe-hectar-pentru-sprijinul-cuplat-vegetal-fermierii-asteapta-banii-de-anul-trecut-5517994)).
- Nitrogen credit: [BZI, nitrogen need of maize](https://www.bzi.ro/ce-influenteaza-necesarul-de-azot-la-porumb-si-cum-se-stabileste-fertilizarea-culturii-5571958);
  Soon (2005), field pea–wheat rotation and soil nitrogen balance.

To refresh the numbers once a season, run `services/engine/tools/build_economics_ro.py`, check
the payment rates in `PAYMENTS` against the new ministerial order, and commit the new data file.
