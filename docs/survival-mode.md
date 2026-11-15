# Survival Mode

> Don't just find the best crop rotation. Find out what happens when nature tests it.

Survival Mode lets a farmer challenge the calculated plans with the hardest past seasons
recorded at the field. Every rotation (the current rotation when it was evaluated, and
Plans 1–3) is compared on the **same** past season, using results the engine already
computed. It is a reading of P3's historical replay, not a new model, and **not a
forecast**.

## Where it is

In the results panel, below the AI summary: a dark-green **Survival Mode** banner with a
**Challenge my plan** button (`aria-expanded` and `aria-controls` set). The panel opens
in place and moves keyboard focus to its heading. It is hidden when a result has no
plans, and it is left out of the printed sheet.

Code: `apps/web/src/lib/survival.ts` (pure, deterministic logic) and
`apps/web/src/components/survival-mode.tsx` (interface). Styles: the Survival Mode
block at the end of `apps/web/src/app/analysis.css`.

## Data it uses (nothing new is calculated)

| What | Where it comes from |
| --- | --- |
| Which year is hardest | `result.climate_context.years`: observed NASA POWER yearly indicators (P2/P3), never scenario-adjusted |
| How each rotation did that season | `plan.replay[]`: P3's per-season scores (`water`, `climate`, `productivity`, 0–1, shown as 0–100) |
| Which crop was most affected | `plan.replay[].steps[]`: P3's per-crop WRSI, season rain, heat days above the crop's own threshold, combined weather risk |
| Same-season alignment | `plan.replay[].field_free_from` (added 2026-11-15, see below) |
| Labels, sequences, trade-off text, confidence | P4's `plan.label`, `steps`, `tradeoffs`, `confidence`, overall `scores` |

The AI summary model is not used. No yields, damage percentages, losses or weather
records are produced.

## How the three challenge seasons are chosen

Only years that **every replayed rotation** covers from the same historical start date
can be chosen (see "Same season"). Among those:

| Challenge | Ranking (higher = harder) | Tie-breaks |
| --- | --- | --- |
| Worst drought | Climatic water deficit: ET₀ − rain for the calendar year (mm) | less rain, then the earlier year |
| Extreme heat | Days above 32 °C | higher mean temperature, then the earlier year |
| Unpredictable rainfall | Percentile rank of the longest April–September dry spell **plus** percentile rank of days with more than 20 mm of rain, over the record | longer dry spell, then the earlier year |

If the record's most extreme year cannot be replayed for every rotation (a three-crop
rotation would run past the end of the weather record), the panel says so and shows the
hardest fair year. If an indicator is missing for all years, or no season is shared by
every rotation, the challenge is shown as unavailable with the reason.

The selected year is the **first April–September growing season after the field
became free** in that replay. The evidence card shows the observed values next to the
record's median ("typical").

## Same season, every rotation

P3 replays each plan from the request's `available_from` moved back whole years.
`season_start_year` is the year of the plan's *first sowing*, so two plans with the same
`season_start_year` can start from different dates: autumn wheat is sown in the
availability year, spring maize the next year. Pairing by that year would compare
different weather.

The contract therefore carries `plan.replay[].field_free_from`: the historical date
the replay started from. Survival Mode compares only seasons with the **same**
`field_free_from`, so every rotation starts from the same day in history and goes
through the same weather that followed. Results without that field (older producers)
are aligned from the plan calendar and the request date, and the panel says the
alignment was derived. Without the request date such seasons are not used.

## How to read the scores

- The challenge score is P3's season score for the matching criterion: **water** for
  drought and unpredictable rainfall, **climate** for heat. 0–100, higher is better. The
  other season scores are listed next to it.
- A season score covers **all three crops of that replay**, not only the hard summer.
- *Most water-stressed crop* / *most heat-exposed crop* is chosen only among crops whose
  planned calendar, moved back to that season, overlaps April–September of the hard
  year. If no main crop was in the field then, the panel says so instead of naming one.
- Heat exposure uses P3's count of days above each crop's own threshold during
  flowering and grain fill, never the yearly hot-day count.
- Score differences use the displayed whole numbers, so the shown difference always
  equals the shown scores' difference.
- Unknown scores stay **Unknown** and block a head-to-head ("No fair comparison"); they
  are never treated as 0.

## The decision

The farmer's rotation defaults to the current rotation (or Plan 1 when there is none)
and can be changed. The question is built from the season scores: whether that rotation
led or fell behind the best rotation of that season. After a choice, the reveal states
which scored higher and by how many points, where the alternative is weaker (lower overall
P3 scores, lower other season scores) and P4's own trade-off notes. A gap of fewer than 5 points
out of 100 (`SMALL_DIFFERENCE_POINTS`) is described as a small difference for a single
season, not as one rotation struggling; this changes only the wording, never a score or
ranking. Every reveal ends with:

> This compares historical conditions, not a prediction of future harvests.

## Scenarios, demo and confidence

- With a hypothetical scenario, the challenge **year and weather evidence stay the
  observed ones**; the scores are P3's scenario-adjusted replay. The panel labels this
  ("Scenario-adjusted scores … weather evidence is observed").
- `mode: demo` results show "Demo · fictional weather and scores".
- Plans with `confidence: low` (provisional rules or missing data) are listed in
  "What to keep in mind".

## Limitations

- NASA POWER describes the grid cell around the point (about 0.5°), not the field;
  indicators are calendar-year totals.
- One past season is one sample; the next drought or heatwave will differ.
- The evaluator does not model flooding, waterlogging or erosion: heavy-rain days are
  shown as observed weather only.
- Scores are relative indices from regional rules that still await agronomist review;
  they are not yields or profits.
- A season score includes later crops of the rotation, so a rotation with no crop in
  the field during the hard summer can still score lower or higher because of later
  seasons.

## Verification

See `docs/status.md`, "Survival Mode — 2026-11-15", for what was tested automatically
and live.
