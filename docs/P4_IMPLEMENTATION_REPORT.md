# P4 — Recommendation engine: implementation report

Branch: `alexia` · Date: 2026-11-14 · Scope: `services/engine/fieldshift/recommender/`,
`services/engine/fieldshift/pipeline.py`, `services/engine/tests/`.

## Summary

The P4 recommender is implemented as deterministic Python code inside the existing engine
service. It generates candidate sequences, calls the P3 evaluator, rejects infeasible or
under-documented candidates, ranks them by the farmer's priorities, runs Pareto analysis,
picks up to three distinct alternatives, compares climate scenarios against the reference
climate when P3 supports that, and writes explanations based only on what the evaluator
returned. Since the merge of `main` (contract update of 2026-11-14) it also supports the
optional `productivity` priority, `current_rotation` → `baseline`, `history[].source`,
and the plan fields `scores`, `local_checks` and `violations` (see section 9).

**Computed mode is still not available over HTTP**, because P2's `build_environment` is
disabled and `ENGINE_MODE=computed` keeps returning HTTP 503. A test checks this.

P3's real evaluator is now merged. With the historical NASA POWER fixture standing in for
P2, the real P3 and P4 modules work together and produce contract-valid results; see "P3–P4
integration audit" below.

The merged API and frontend accept and display these real results without loss. One display issue remains and belongs to P1; see "Full-stack integration audit".

P4's algorithm tests still use a **synthetic evaluator** (`tests/fake_evaluator.py`).
Its outputs are marked `fixture: true`, and the pipeline refuses to return them as
computed results. No test shows that any crop, calendar or score is agronomically correct.

## Files

| File | Status | Purpose |
| --- | --- | --- |
| `fieldshift/recommender/__init__.py` | modified | Public entry point; `recommend_rotations` keeps its signature and also exports `recommend` and `RecommenderConfig` |
| `fieldshift/recommender/config.py` | new | Criteria names, contract constants, search and selection limits (none of them agronomic) |
| `fieldshift/recommender/evaluation.py` | new | Defensive parser for the **proposed** P3 evaluation shape |
| `fieldshift/recommender/generation.py` | new | Crop catalog from rules; bounded, deterministic candidate generation |
| `fieldshift/recommender/validation.py` | new | Calendar checks, history checks, Python port of `validateResultSemantics` |
| `fieldshift/recommender/ranking.py` | new | Priority normalization; interval scoring for missing data; ranking |
| `fieldshift/recommender/pareto.py` | new | Dominance check and Pareto status (pruned, same result as the naive check) |
| `fieldshift/recommender/selection.py` | new | Picks diverse alternatives (MMR-style, with disclosure tiers) |
| `fieldshift/recommender/scenarios.py` | new | Scenario detection, reference-climate request, robustness record |
| `fieldshift/recommender/rotation.py` | new | Continues `current_rotation` from the crop history (sequence bookkeeping only) |
| `fieldshift/recommender/explanations.py` | new | Benefits, trade-offs, explanation, labels and qualitative confidence |
| `fieldshift/recommender/engine.py` | new | Orchestration; returns `RecommendationOutcome` (with optional `baseline`) and `PlanList` |
| `fieldshift/pipeline.py` | modified | Calls the team interface `recommend_rotations`; uses `PlanList.outcome` for sources, assumptions, data gaps and `baseline`, or falls back to environment/rules metadata for a plain list. Refuses fixture evaluations, checks result semantics. Same function interface, `request_id`, modes and status rules |
| `tests/fake_evaluator.py` | new | Synthetic, clearly labelled P3 replacement for tests |
| `tests/test_recommender.py` | new | 47 test cases for P4 |
| `tests/test_p4_english.py` | new | 29 test cases checking that P4 output (including baseline, local checks and violations) contains no Romanian |
| `tests/test_p4_contract_extensions.py` | new | 28 test cases for the old request format and every new optional field |
| `docs/status.md` | modified | Status updated |

No changes to Zod, the JSON Schemas, the examples, P2/P3 modules, the P5 tests, the web app or the infrastructure.

## Algorithms

### 1. Candidate generation (`generation.py`)

- The supported crops come only from `rules["crops"]` (a dict keyed by id, or a list of
  `{id, name}`). IDs must match the contract regex. Duplicates are merged.
- Excluded crops are removed before any sequence is built, so they are never evaluated.
- Sequences are all ordered triples with replacement over the sorted crop IDs, in
  lexicographic order. P4 does **not** reject repeats, previous-crop conflicts or
  seasonal clashes. Those are agronomic rules that P3 owns.
- Bound: when `n³ > max_candidates` (default 1500), P4 evaluates a deterministic sample:
  the sequences with the smallest SHA-256 digest, so crop names don't bias the choice.
  The truncation is reported in `data_gaps`.
- There is no assumed three-year horizon and no cyclic repetition. Dates come from the
  evaluator's calendar.

### 2. Evaluation and feasibility (`evaluation.py`, `engine._classify`)

Each candidate is evaluated once per climate condition with
`evaluate(list(rotation), deepcopy(request), environment, rules)`. Each candidate ends up
in one of these classes:

- `feasible`: P3 says `feasible`, lists no violations, and the calendar passes P4's
  temporal checks.
- `infeasible`: P3 says so, or a `feasible` reply also lists violations (the violation wins).
- `unknown`: the reply is malformed, the status is missing or `unknown`, or the calendar is
  missing. **Unknown is never treated as passing.**
- `calendar_invalid`: P3 says feasible, but the dates overlap, are out of order, or the
  first sowing window has closed before `available_from`.

`NotImplementedError` and any other exception raised by the evaluator propagate. The API
maps them to 503 and 502. Errors are never swallowed or turned into synthetic results.

A feasible candidate becomes **eligible** to be a plan only if:

- known P3 scores cover at least `min_coverage` (default 50%) of the normalized priority
  weight, and
- it cites at least one source ID that exists in the response's source list.

### 3. Ranking with missing data (`ranking.py`)

- Weights are the priorities divided by their sum. Negative, non-numeric, boolean or
  missing priorities raise `ValueError`.
- **All-zero priorities** raise `ValueError("At least one priority must be positive")`.
  This matches `docs/api.md` and the existing check in `api.py`. P4 does not invent
  equal weights.
- An unknown score is never replaced by 0 or 0.5. Each plan gets an interval instead:
  `lower = Σ_known wᵢsᵢ`, `upper = lower + Σ_unknown wᵢ`, and `coverage = Σ_known wᵢ`.
  When coverage is 100%, the interval is a single value.
- Ranking key: `(-lower, -coverage, -upper, sequence)`. This is deterministic, and a
  sparsely evaluated plan can't outrank a fully evaluated one just because data is missing.
  Zero-weight criteria do not affect the score.

### 4. Pareto analysis (`pareto.py`)

- The objectives are the criteria with positive weight.
- Dominance is only decided when **both** candidates know every objective. Otherwise the
  pair is incomparable.
- Statuses:
  - `nondominated`: no fully evaluated candidate dominates it.
  - `dominated`: listed with the candidates that dominate it.
  - `undetermined`: some objectives are missing.
- `nondominated` is never presented as global optimality.
- Pruning: a candidate can only be dominated by candidates with a larger coordinate sum.
  A test against the naive pairwise definition shows the results are identical. A
  15-crop search (1,500 candidates, scenario plus baseline) dropped from about 6 s to
  about 0.9 s.

### 5. Diverse selection (`selection.py`)

- Plan 1 is the top-ranked eligible candidate.
- Each later slot uses a greedy MMR step with disclosure tiers:
  1. `diverse`: sequence distance ≥ 0.4 and guaranteed-score gap to plan 1 ≤ 0.15.
  2. `score_gap`: distance ≥ 0.4 but the score is lower. The gap is stated in the plan's
     trade-offs.
  3. `low_diversity`: similar to an already chosen plan. The nearest plan and the
     distance are stated.
- Within a tier the order is:
  1. not Pareto-dominated by an already selected plan;
  2. utility `(1−λ)·lower + λ·distance + bonus`, where λ = 0.3 and the bonus is 0.05 if
     the plan's strongest criterion isn't yet the strongest criterion of a selected plan;
  3. Pareto-nondominated first;
  4. rank.
- Distance `= ½·positional Hamming/3 + ½·(1 − Jaccard of crop sets)`. **Limitation:**
  this is structural only. It does not know crop families (two cereals count as
  different crops). Crop families from P3 would make it better.
- When fewer than three eligible candidates exist, fewer plans are returned. Status
  becomes `limited` or `insufficient_data`, and a data gap says no options were invented.

### 6. Climate scenarios (`scenarios.py`, `engine.py`)

- `temp_change_c` and `rain_change_pct` reach P3 unchanged inside the request. P4 never
  changes scores based on them.
- If the scenario is non-zero and **every** evaluation returns `scenario_applied: true`,
  P4:
  - ranks candidates on the scenario evaluations;
  - re-evaluates the **same** candidates with a baseline copy of the request (both
    deltas 0);
  - reports, per plan, baseline feasibility, rank in the scenario vs. in the baseline,
    and the change in each criterion score.
- If any evaluation does not confirm `scenario_applied`, robustness is `unsupported`. In
  that case there is no baseline pass, a data gap says the ranking doesn't reflect the
  scenario, and confidence is capped at medium.
- Assumptions always state that the scenario is hypothetical and not a NASA forecast.

### 7. Calendar checks (`validation.py`)

The checks are:

- exactly three steps whose crops match the rotation order;
- valid ISO `YYYY-MM-DD` dates (checked with a strict regex);
- sowing window start ≤ end, and harvest window start ≤ end;
- sowing end ≤ harvest start;
- harvest end of step i is **strictly** before sowing start of step i+1, so main crops
  never overlap;
- the first sowing window must not close before `available_from`. If it opens before
  that date, its start is moved to `available_from`, and the step's reason says so.

Crops sown in autumn and harvested the next year are handled as real dates. History
entries with `harvest_year` later than the availability year, or with crops missing from
the rules, are reported as data gaps. The history is passed to P3 unchanged for
previous-crop checks.

### 8. Explanations and confidence (`explanations.py`)

All text is generated deterministically **in English** (see "English-language output"
below) and draws only on evaluator fields and P4 comparisons:

- **Benefits:** each weighted criterion at or above the median of the eligible pool,
  plus P3's own summary; Pareto non-dominance; staying feasible without the scenario.
- **Trade-offs:** criteria below the median; unknown criteria; evaluator warnings; score
  gap, similarity or dominance disclosures; ranking or feasibility changes under the
  scenario.
- **Explanation:** why the plan was selected; its score or interval with the normalized
  weights; its Pareto status; the scenario status; data gaps P3 reported; what a local
  agronomist should check; and the confidence reasons.

Confidence is a qualitative grade of the evidence. **It is not a calibrated probability.**

- **low**
  - the evaluation is a fixture;
  - weighted coverage is below 100%;
  - a weighted criterion is based on `assumed` evidence or cites no source.
- **medium**
  - a zero-weight criterion is unknown;
  - some evidence is `estimated`;
  - there is no crop history;
  - the soil was not measured in a lab;
  - the scenario was not applied;
  - feasibility differs between scenario and baseline;
  - P3 gave a high-severity warning;
  - P3 reported data gaps.
- **high:** none of the above.

Every plan `source_id` exists in `sources`. Sources the evaluation provides are added to
the response only when a plan cites them. IDs that can't be resolved are dropped and
reported.

### 9. Contract extensions from `main` (2026-11-14)

All of these are optional in the contract. Requests without them behave exactly as
before, and tests check that.

**`priorities.productivity`**
- A 4th criterion in parsing, weights, ranking intervals, Pareto objectives, selection
  strengths, confidence, explanations and scenario score changes.
- Absent means weight 0. An old request's ranking is identical even when P3 returns
  productivity scores.
- Productivity-only priorities are valid. All-zero priorities are still rejected.
- When weighted, an assumption states that it is a relative production-potential score,
  not a yield or profit forecast.

**`current_rotation` → `baseline`**
- `rotation.py` continues the cycle from the crop history, ordered by `harvest_year` when
  every entry has one, otherwise in the farmer's list order.
- It takes the cycle position with the longest consecutive match against the most recent
  history crops.
- With no match, it starts from the first listed crop. That case is disclosed, adds a
  local check, and caps confidence at medium. A tie between positions is reported as
  ambiguous.
- The sequence is evaluated by P3 with the same request. The candidate evaluation is
  reused if the sequence was already in the search.
- It never enters selection and never counts toward `status`. It may repeat a plan's
  sequence, and it is shown even if it contains excluded crops (disclosed).
- An **infeasible** current rotation is shown with P3's `violations`, a "Breaks an
  agronomic rule" trade-off and an explicit sentence. This happens only if P3 supplied a
  temporally valid calendar and at least one resolvable source.
- If the feasibility is unknown, the calendar is missing or invalid, or no source can be
  resolved, the baseline is **omitted**. A data gap then explains why and repeats any
  violations. Nothing is fabricated.
- Recommended plans compare their weighted score with the current rotation's ("Higher",
  "Lower", "Not clearly different"), using intervals when data is missing.

**`history[].source`**
- `typed`, `apia` and `spray_records` count as documented.
- `satellite` on the most recent entry caps confidence at medium, adds a data gap, and
  adds a local check.
- `unknown` or absent does **not** lower confidence, because that would assume the record
  is wrong. It adds a data gap and a local check asking the farmer to confirm the
  previous crop.

**Plan fields**
- `scores` holds all four criteria, with `null` when P3 gave no score (never a neutral
  value). Recommended plans and the baseline both carry it.
- `local_checks` lists P4's checks (windows, previous crop, soil, irrigation, estimated
  criteria, current-rotation position) followed by P3's own checks.
- `violations` is set only on `baseline`. Recommended plans omit it, because P4 never
  recommends a sequence with violations.

**Two separate comparisons**
- The climate-scenario comparison now uses the term **reference climate** in code
  (`reference_request`, `CandidateRobustness.reference_*`) and in text.
- "Baseline" and "current rotation" refer only to the farmer's rotation. A test checks
  that plan text never says "baseline" and that the current rotation is never ranked.

**Pipeline and P5 tests**
- `pipeline.computed_result` calls `recommend_rotations`. P5's `tests/test_api.py`
  monkeypatches that function and needs it.
- The P4 implementation returns a `PlanList`: a real `list` of plans with an `.outcome`
  attribute. For a plain list, as from P5's stubs, the pipeline uses the original
  assembly from environment and rules metadata.
- The full P4 engine is still the default. The stubs only replace it inside that test.

**Validator**
- `validate_result_semantics` now also ports the Zod rules "Recommended plans cannot break
  agronomic rules", "Unknown source reference in baseline" and "Baseline steps must be
  ordered 1, 2, 3".

## P3–P4 integration audit (real modules, 2026-11-14)

Branch `alexia` at `main` (`1e96016`, P3 merged). The test file is
`services/engine/tests/test_p3_p4_integration.py`, with 23 tests. Every test uses:

- the real `fieldshift.evaluator.load_rules` and `evaluate`;
- the real P4 recommender and `pipeline.computed_result`;
- the historical NASA POWER fixture `tests/fixtures/environment-ro-south.json` (Bărăgan
  test point, 2005–2025), standing in for P2.

No fake evaluator and no synthetic scores are involved. These are software integration
results, **not agronomic validation**: P3's calendars, successions and thresholds are
expert estimates awaiting review (`docs/evaluator.md`).

### What was verified

| Area | Result |
| --- | --- |
| Contract | Every result passes the JSON Schema and `validate_result_semantics`: three distinct plans, three ordered crops each, all sources resolvable (`nasa-power`, `fao56`, `ro-agronomy`, …) |
| Feasibility | Every recommended sequence is `feasible` with no violations when re-evaluated directly by P3 |
| Scores | `plan.scores` equal P3's criterion scores exactly. The weighted score in the explanation equals Σ wᵢ·sᵢ recomputed from P3's scores |
| Priorities | With a single priority (water, soil, climate or productivity), plan 1 has the highest P3 score for that criterion among all feasible sequences (checked over all 343). Different priorities give different top plans |
| Unknown scores | With too little weather to replay, P3 returns `null` for water, climate and productivity. P4 keeps `null`. Equal priorities give `insufficient_data`; soil-only priorities still give plans |
| Scenario | Both scenario and reference-climate requests reach P3. P3's water scores fall under +2 °C / −20 % rain. Plan text uses "reference climate", never "baseline" |
| Current rotation | `["maize", "winter_wheat"]` after maize gives a separate `baseline` (winter wheat → maize → winter wheat) with P3's scores, not counted in `status` |
| Infeasible rotation | `["sunflower"]` gives a baseline with P3's violation ("Sunflower after sunflower …") preserved and explained, never recommended |
| Exclusions and history | Excluded crops never appear. Sunflower harvested in 2026 (`source: apia`) keeps sunflower out of every plan, through P3's 6-year return interval |
| Texts | P3's local checks (prefixed "P3:"), warnings, data gaps and method assumptions all reach the result. Confidence is never "high", because P3 marks soil and productivity as estimates. Text is English |
| Unsupported region and missing data | Outside P3's zones: `insufficient_data` with P3's reason. Without `daily` weather: `insufficient_data` with "No daily weather…". No plans are invented |
| Repeatability | Two identical requests, the second with a fresh environment object, give identical results apart from `generated_at` |

### Example plans (equal priorities water/soil/climate 3/3/3)

Request: available from 2026-10-01, maize harvested in 2026, rainfed, no scenario. These
are the real P3 scores, with no agronomic claim attached.

| Plan | Sequence | water | soil | climate | productivity |
| --- | --- | --- | --- | --- | --- |
| 1 | pea → winter rapeseed → winter barley | 0.789 | 0.863 | 0.518 | 0.398 |
| 2 | sunflower → winter wheat → winter wheat | 0.662 | 0.614 | 0.529 | 0.333 |
| 3 | soybean → winter barley → sunflower | 0.651 | 0.769 | 0.545 | 0.343 |
| baseline (`maize, winter_wheat`) | winter wheat → maize → winter wheat | 0.591 | 0.564 | 0.495 | 0.270 |

**Priorities change the result:**

- water only: plan 1 is winter rapeseed → winter barley → winter barley (water 0.820);
- productivity only: plan 1 is pea → winter barley → sunflower (productivity 0.421).

**The scenario changes it too.** Under +2 °C / −20 % rain:

- plan 1 becomes pea → winter barley → winter rapeseed (water 0.607, climate 0.432);
- plans 2 and 3 change.

Confidence is "medium" for all of these.

### Timing (cold caches, one process; `ENGINE_TIMEOUT_MS` = 90 000)

| Request | Total | P3 `evaluate` | P4 |
| --- | --- | --- | --- |
| rainfed, no scenario (343 calls) | 1.4 s | 1.4 s | 0.05 s |
| rainfed, scenario + reference climate (686 calls) | 7.4 s | 7.2 s | 0.20 s |
| irrigated, no scenario | 8.3 s | 8.2 s | 0.13 s |
| irrigated, scenario, current rotation | 14–16 s | 15.5 s | 0.25 s |

The heaviest request uses about 18 % of the timeout. P3's replay accounts for more than
98 % of the time. The scenario's reference-climate comparison doubles the P3 calls by
design. The integration test fails if a cold full request exceeds 25 % of the timeout.
The integration file takes about 80 s; the whole Python suite takes about 81 s.

### P4 bugs found by the integration tests and fixed

1. **A current-rotation crop unknown to P3 disabled the scenario analysis.**
   - Cause: P3 returns `unknown` with `scenario_applied: false` for crops it has no rules
     for (for example `rice`). P4 required every evaluation to confirm the scenario.
   - Effect: P4 declared the scenario "not applied" for the whole result, although all
     343 candidates applied it.
   - Fix: scenario support is now judged only on sequences P3 actually evaluated.
2. **Outside the covered zones, P3's explanation was lost.**
   - Cause: `load_rules` puts the reason in `rules.data_gaps`, which P4 ignored. P4 also
     added a misleading "previous crop is not in the regional rules" note.
   - Fix: P4 forwards `rules.data_gaps` and skips that note when there are no rules at all.
3. **Empty results did not say why.** P4 copied P3's data gaps only from *selected*
   plans, so an `insufficient_data` result dropped P3's reasons (for example "No daily
   weather…"). Fix: when no plan is shown, P4 adds the data gaps P3 reported for every
   evaluated sequence.
4. **P3's method assumptions were dropped**, for example the number of replayed seasons
   and the ET method. Fix: P4 reads `assumptions` from evaluations (now part of the
   proposed shape) and adds those of the shown plans and baseline to `result.assumptions`.
5. **Rounding contradiction in plan text.** A plan could say "P3 score 0.52, below the
   median (0.52)". Fix: both numbers are printed with enough decimals (up to 4) to show
   a real difference.

None of these fixes changed generation, feasibility filtering, scoring, ranking, Pareto
analysis, selection or calendar checks. The example rankings above are the same before
and after.

### P3-side observations (not changed, for Tudor)

No P3 defect was confirmed. These are notes, each with a way to reproduce it:

- **Unknown evaluations report `scenario_applied: false`.** Reproduce:
  `evaluate(["maize", "rice", "maize"], request_with_scenario, env, rules)`. This is fine
  semantically, and P4 now handles it. Worth documenting in `docs/evaluator.md`.
- **Confidence can never reach "high" with P3.** Every evaluation has soil
  `basis: "estimated"` and a fixed winterkill data gap. This is consistent with the
  evidence; it is reported only so that nobody expects "high".
- **Cost of scenario and irrigated replays.** A cold request with irrigation and a
  scenario spends about 15 s in `evaluate`. Reproduce with the timing case above. It
  fits the timeout, but more crops (n³ sequences) or zones would grow it quickly.
- **The weather cache is keyed on `id(environment)`.** If a freed environment's id were
  reused by a different environment with the same dates, cached weather could be stale.
  I tried to trigger this (30 attempts) and could not, so it is a theoretical risk only.
- **P3 output with no contract field.** `details`, `replay`, `soil_inputs` and
  `soil_components` are not passed on, because the result contract has no fields for
  them. Charts of past seasons would need a contract change agreed with P1 and P5.

### Still depends on others

- **P2:** a validated `build_environment`, returning `daily`, `static`, `sources` with
  titles, and `data_gaps`. Until then computed mode returns 503 over HTTP. The fixture
  covers one test point with no SoilGrids, SMAP or SRTM data.
- **P3:** agronomist review of calendars, successions and thresholds. Coverage is one
  zone (southern plains) with 7 crops.

## Full-stack integration audit (real P3–P4 → API → frontend, 2026-11-14)

Branch `alexia` after the frontend merge (`951bd96`). Goal: check that the merged API and
frontend can consume real computed results before P2 is live. P2 is replaced only by the
historical NASA POWER fixture. No fake evaluator, servers, browser, Docker or external
service was used.

### Method

1. **Real results.** `computed_result` with the real `load_rules`, `evaluate` and
   `recommend_rotations` produced 11 results:
   - complete, with and without baseline;
   - infeasible baseline;
   - +2 °C / −20 % scenario;
   - limited (2 plans);
   - two kinds of `insufficient_data`: no feasible sequence, and outside the zones (also
     with a current rotation);
   - unknown (`null`) scores;
   - the exact request shape the dashboard builds;
   - the shared full example the calculator loads.
2. **Python boundary.** `tests/test_p4_web_integration.py` (14 tests, kept in the repo)
   covers the internal FastAPI endpoint in computed mode, the Next.js post-checks
   mirrored in Python, priorities, text regressions and P2's output shape.
3. **Node boundary.** A Node test harness ran outside the repo, against the installed web
   dependencies, because `apps/web` belongs to P1/P5. For each real result it checked:
   - Zod `resultSchema` parsing is lossless (deep-equal before and after);
   - `validateResultSemantics` passes;
   - the real `POST /api/recommendations` handler, with only the engine `fetch` stubbed,
     returns 200 with the body unchanged except `request_id`, and forwards the priorities
     exactly as entered;
   - the real `RecommendationResults` component, rendered with `renderToStaticMarkup`,
     shows every returned element.

   It can be added to `apps/web/tests/` with P1/P5's agreement.

**What this does not verify:** the browser flow (clicks, sliders, debounce/abort in a real
page), running Next.js/FastAPI servers, NGINX, live NASA/P2 data, touch or screen-reader
use, and agronomic correctness.

### Results

| Check | Result |
| --- | --- |
| JSON Schema + semantic rules (Python) | 11/11 |
| Zod parse, lossless (Node) | 11/11 |
| Next.js route accepts the result unchanged; priorities forwarded as sent | 11/11 |
| Internal FastAPI `/recommendations`, computed, real P3–P4, `X-Request-ID` echoed | pass (dashboard, calculator, outside zone) |
| Rendering: crop names; sowing and harvest windows; 4 scores ("Unknown" for `null`); baseline card and violations; local checks; benefits, trade-offs, explanation; assumptions, data gaps, sources, disclaimer; what-if block; limited/insufficient notices; no demo banner; unique DOM ids | 10/11 (the failure is finding P1-2) |
| Result size | 2–26 KB (Next.js limit 2 MB) |
| Scenario recalculation | `ResultsWhatIf` → `recalculate({...lastRequest, scenario})` → same endpoint. Real output changes with the scenario. Browser interaction not tested |

### Confirmed findings

Severity reflects the effect on farmers and integration, not effort.

**Fixed (P4):**

| ID | Severity | Finding | Fix |
| --- | --- | --- | --- |
| P4-1 | Medium | Comparison with the current rotation printed equal numbers: "Higher weighted score than your current rotation (0.55 vs 0.55)" | Complete scores use `_pair` (2–4 decimals until the difference is visible) |
| P4-2 | Low | Raw crop IDs in user text: "Your current rotation (maize → winter_wheat)…", "…you excluded…: winter_wheat" | `crop_label`: rules display name, or the readable ID ("Winter wheat") when there are no rules |
| P4-3 | Low | Each explanation repeated the full data-gap and local-check lists, which the UI already shows (result "Missing data", plan "Check locally before you decide"), with "..", ".;" glitches | Explanation gives counts and points to those lists. `join_sentences` removes doubled punctuation. Nothing is lost: plan gaps are in `result.data_gaps`, checks in `plan.local_checks` |
| P4-4 | Low | Out of zone: three overlapping reasons | P4's "no candidate crops" line is dropped when P3's rules already explain |

The ranking, selection and scores are unchanged. Each fix has a regression test that
fails on the previous code.

**Not changed: to report to their owners.**

| ID | Owner | Severity | Finding (cause, file) | Suggestion |
| --- | --- | --- | --- | --- |
| P2-1 | P2 (Maria) | Medium | `fetch_power` returns no `static.elevation_m` and no `T2MDEW`; the fixture has both (`data_service/power.py`). P3 accepts the shape but estimates ET0 at sea-level pressure without dew point. On the same request, plan 1 water rises 0.789 → 0.830 and productivity 0.398 → 0.422. The plans stay the same; the missing elevation is disclosed, the dew point is not | Add `T2MDEW` to `PARAMETERS` and the POWER response elevation to `static.elevation_m` |
| P1-1 | P1 | Medium | The dashboard always sends `water: 3, soil: 3, climate: 3` (`field-dashboard.tsx:140`). Its five 0–100 sliders (investment, water reserve, regeneration, logistics, cleanup) only re-rank the fictional preview; only productivity 0–5 reaches P4. "Water reserve" describes availability, not how much water fit matters. Disclosed in small print (`field-dashboard.tsx:567`, `priority-panel.tsx:44`) | Add the calculator's four 0–5 engine priorities to the dashboard form, or send users to `/calculator` to weight criteria; label the five sliders "preview only, not sent" at the panel |
| P5-1 | P5 | Medium (load) | Cancelling in the browser ("Stop waiting", a newer what-if) aborts only browser → Next.js. `recommend()` does not get `req.signal` (`lib/server/engine.ts`), `upstreamJson` uses only its timeout signal (`upstream.ts`), and the FastAPI handler is synchronous. Abandoned P3/P4 runs (1.5–16 s each) keep running | Pass `AbortSignal.any([req.signal, timeout])`; consider limiting concurrent computed jobs |
| P1-2 | P1 | Low | "Add your current rotation to compare…" is shown whenever `result.baseline` is absent (`recommendation-results.tsx:116`), even when the farmer gave one and the engine explained in `data_gaps` why it could not be evaluated (out of zone) | Show the hint only when `request.current_rotation` is empty; otherwise point to "Missing data" |
| P1-3 | P1 | Low | Demo output is clearly marked (`mode: demo` banner, mock notes, "DEMO · NOT AN AGRONOMIC ASSESSMENT" on the preview). Computed results carry no positive provenance label, while the dashboard's top notice says "crop scores are fictional examples" and real plan scores use the same 0–100 scale | When `mode: computed`, add a tag like "Computed from NASA POWER history and regional rules · not agronomically validated"; call the preview values "demo preview scores" |
| P1-4 | P1/P5 | Low | `getRecommendations` calls `response.json()` before checking `ok` (`lib/api.ts`), so a non-JSON gateway error page shows a JSON parse error | Parse defensively and fall back to a generic message |
| P1-5 | P1 | Low | Dashboard temperature slider covers 0…+5 °C (`scenario-panel.tsx:47`), the results what-if −3…+5 °C | Align with the contract range |
| P5-2 | P5 | Low | NGINX allows 5 calculations/min (burst 3) per IP, and each what-if Recalculate is a full calculation. More than about 8 scenarios a minute gives 429 (the previous result stays visible) | Note it in the UI, or give scenario recalculation its own allowance |
| P3-1 | P3 (Tudor) | Low | An excluded crop is reported as a baseline *violation* ("Winter wheat is on the farmer's list of excluded crops.", `evaluator/schedule.py:129`). It appears under "Rules your current rotation breaks", but the contract defines violations as agronomic rules | Report it as a warning, or agree the meaning in `docs/api.md` |
| P3-2 | P3 | Low | Warnings for a crop that occurs twice do not say which occurrence ("Maize: severe water shortage … in 5 of 17" and "… in 6 of 17") | Add the step number |
| P3-3 | P3/P4 | Low | Per-sequence assumptions with different season counts ("18 past seasons", "17 past seasons") appear as separate result assumptions | Word it per plan, or P4 merges them (open P4 item) |

### Remaining dependencies before live computed mode

1. **P2:** enable and validate `build_environment` (`ENABLE_NASA_POWER`), fix P2-1, and
   add soil/slope data if the team wants them. Until then the HTTP computed path returns
   503.
2. **P5:** fix P5-1 before public computed use. Run one end-to-end check with real
   servers (Next.js → FastAPI → P2 → P3 → P4) and a browser, which this audit did not do.
3. **P1:** fix P1-1 and P1-2 so that the weights farmers set and the baseline message
   match what the engine did.
4. **P3:** agronomist review of the rules. Coverage is still one zone with 7 crops.
5. **Team:** agree the P3–P4 intermediate contract (below) and the meaning of `violations`.

## Proposed P3–P4 intermediate contract (team approval needed)

`docs/team.md` asks P3 and P4 to agree on this contract. P4 currently reads the shape
below. It is documented in `evaluation.py`, and anything missing is treated as unknown.
**This is a proposal. P3's code was not changed.**

**`load_rules(location)` returns:**

- `crops`: `{crop_id: {name}}` or `[{id, name}]`
- `sources`: `[source]`

**`evaluate(rotation, request, environment, rules)` returns:**

- `feasibility`: `"feasible" | "infeasible" | "unknown"`
- `violations`: `[str]`
- `criteria`: for each of water, soil, climate and productivity:
  - `score`: 0–1 or null (higher is better; productivity = relative production potential,
    not a yield or profit forecast)
  - `basis`: `observed | derived | estimated | assumed`
  - `summary`
  - `source_ids`
- `calendar`: three steps, each with `crop_id`, `crop_name`, `sowing_window`,
  `harvest_window`, `source_ids` and `reason`
- `warnings`: strings or `{message, severity}`
- `data_gaps`
- `local_checks`: `[str]` (optional; shown to the farmer prefixed with "P3:")
- `source_ids`
- `sources`
- `scenario_applied`: bool
- `fixture`: bool (test evaluators only)

Questions for P3:

1. Is a 0–1 "higher is better" score per criterion acceptable, or does P3 prefer
   physical indicators (mm deficit, stress days) that P4 would rank directly?
2. Can P3 confirm `scenario_applied` on every reply, infeasible ones included?
3. Can the rules expose crop families, so diversity can account for agronomic similarity?
4. For an infeasible sequence (for example the farmer's current rotation), can P3 still
   return its calendar, criterion scores and sources? Without them P4 can only report the
   violations in `data_gaps`, not show the rotation as `baseline`.

No change to the public Zod/JSON contracts is needed or proposed. Criterion scores now go
in `plan.scores`. Score intervals and climate robustness are still carried only in plan
text; structured fields for them would need approval from P1, P3 and P5.

## Tests

Command (Windows, project environment):

```
uv sync --project services/engine --frozen --extra dev
services/engine/.venv/Scripts/python.exe -m pytest services/engine/tests
```

`uv` was not installed on this machine. The pinned `uv==0.9.5` was installed into a
temporary folder only to run the sync. The `.venv` it created is gitignored.

**Latest result (full-stack audit, 2026-11-14): 176 passed, 0 failed** in about 43 s. That is the 162 below plus `test_p4_web_integration.py` (14). Web checks in the same audit: contracts and web TypeScript passed, `test:backend` 82/82, `test:ui` 25/25. Schema regeneration produced identical content; only line endings differed, so the committed files were restored.

Previous result (P3–P4 audit): 162 passed, 0 failed, in about 81 s:

- `test_evaluator.py`: 18 (P3);
- `test_p3_p4_integration.py`: 23 (real P3 and P4);
- `test_recommender.py`: 48;
- `test_p4_contract_extensions.py`: 28;
- `test_p4_english.py`: 29;
- `test_api.py`: 8 (P5);
- contract tests: 8.

Earlier result, kept for history: **120 passed** after merging `main`, across these files:

- `test_contracts.py`: 4 original contract tests;
- `test_contract_extensions.py`: 4 tests from P5;
- `test_api.py`: 8 HTTP/API tests from P5;
- `test_recommender.py`: 47 P4 algorithm test cases;
- `test_p4_contract_extensions.py`: 28 P4 contract-extension test cases;
- `test_p4_english.py`: 29 English-output test cases.

The one warning is a Starlette deprecation notice for `TestClient`.

Not run: `pnpm contracts:generate`, `pnpm typecheck` and `pnpm test:backend`. pnpm and
`node_modules` are not installed on this machine, and the contracts and web code were
not changed. The Python contract tests validate the generated JSON Schemas, including
the new full examples.

| Required area | Tests |
| --- | --- |
| 1 Candidate generation | `test_generation_enumerates_ordered_triples_deterministically`, `..._truncation_...`, `test_catalog_derives_crops_from_rules_only` |
| 2 Exactly three crops | `test_every_plan_has_exactly_three_ordered_steps` |
| 3 Duplicates | `test_duplicates_are_eliminated` |
| 4 Excluded crops | `test_excluded_crops_are_never_generated_or_evaluated` |
| 5 Feasibility filtering | `test_infeasible_unknown_and_bad_calendar_candidates_are_rejected`, `test_feasible_with_violations_is_treated_as_infeasible` |
| 6 Empty/insufficient sets | `test_empty_and_insufficient_candidate_sets` |
| 7 Priority normalization | `test_priority_normalization`, `test_priorities_change_the_top_plan` |
| 8 All-zero priorities | `test_invalid_or_all_zero_priorities_are_rejected` (4 cases) |
| 9 Missing scores | `test_missing_scores_produce_interval_not_substitute`, `test_partial_evidence_cannot_outrank_by_luck`, `test_low_coverage_candidates_are_not_proposed` |
| 10 Determinism | `test_identical_inputs_give_identical_outputs` |
| 11 Pareto | `test_pareto_dominance_rules`, `test_pruned_pareto_matches_naive_pairwise_definition` |
| 12 Diverse selection | `test_diverse_selection_skips_near_duplicates`, `test_inferior_diverse_plan_is_disclosed_as_score_gap`, `test_end_to_end_alternatives_are_distinct` |
| 13 Sources | `test_source_references_are_preserved_and_resolvable`, `test_unknown_cited_sources_are_dropped_and_reported`, `test_plans_without_resolvable_sources_are_not_proposed` |
| 14 Confidence | `test_confidence_levels_follow_evidence_rules` |
| 15 Autumn/winter transitions | `test_autumn_crops_cross_the_year_boundary` |
| 16 `available_from` | `test_available_from_is_enforced`, `test_sowing_start_before_availability_is_clipped_with_note` |
| 17 Crop history | `test_crop_history_is_passed_to_p3_and_checked`, `test_request_is_not_mutated_by_evaluator` |
| 18 Scenarios | `test_scenario_triggers_baseline_reevaluation_of_same_candidates`, `test_unsupported_scenario_is_reported_not_simulated`, `test_no_scenario_means_single_pass` |
| 19 Evaluator unavailable | `test_unimplemented_evaluator_propagates`, `test_computed_mode_is_unavailable_until_p2_p3_exist`, `test_api_returns_503_in_computed_mode`, `test_fixture_evaluations_cannot_back_computed_results` |
| 20 Contract output | `test_computed_result_matches_contract_and_semantics`, `test_semantic_validator_matches_typescript_rules` |
| 21 Status for 0/1/2/3 plans | `test_status_semantics_for_each_plan_count` (4 cases) |
| 22 `request_id` | `test_request_id_is_preserved_in_both_modes` |
| English output | `tests/test_p4_english.py`: detector self-check, static scan of 13 P4 source files, 14 generated-output paths, computed-result disclaimer |
| Old request format | `test_old_request_format_is_unchanged_in_behaviour`, `test_old_request_ranking_ignores_productivity_scores` |
| `productivity` | weight and ranking, productivity-only and all-zero priorities, null score and interval, confidence when requested but unweighted, Pareto participation |
| `history[].source` | documented sources, satellite, unknown or absent source, most recent entry and ordering |
| `current_rotation` → `baseline` | alignment rules, separate and not counted, infeasible with violations, omitted without calendar, unknown or sources, position assumed, excluded crops, evaluation reuse, kept separate from the scenario comparison, full contract example |
| `scores` / `local_checks` / validator | null scores, evaluator checks, new Zod semantic rules, `PlanList` compatibility |
| P5 integration | `tests/test_api.py` (module stubs returning plain lists) now passes against the P4 pipeline |

Not run: `pnpm` typechecks and contract generation (contracts unchanged), Next.js,
FastAPI server, Docker, PostgreSQL, live NASA calls.

## Known limitations

- Every agronomic result depends on P3. With the stub evaluator, computed mode returns 503.
- The search is exhaustive only up to 1,500 sequences per climate condition. Beyond that
  it evaluates a deterministic sample, which is disclosed. There is no prefix pruning,
  because the evaluator only scores full rotations.
- The thresholds (`min_coverage` 0.5, `max_score_gap` 0.15, `min_distance` 0.4, λ 0.3)
  are documented heuristics. They have not been tuned or validated with users or
  agronomists.
- Diversity is measured on crop identity only, not agronomic similarity.
- Scenario comparison doubles the number of evaluator calls. There is no cache across
  requests (by design: stateless).
- Robustness and score intervals appear in plan text only, because the public contract
  has no structured fields for them.
- User-facing text is English only. There is no localization layer.
- The Romanian-detection tests are heuristic. They catch Romanian diacritics and a list of
  common Romanian words, not every possible Romanian word.
- Current-rotation alignment is sequence matching on crop IDs. It cannot tell winter and
  spring sowing apart unless P3 uses distinct crop IDs for them. It cannot read numeric
  APIA crop codes: the contract's `crop_id` pattern requires them to be mapped to crop
  IDs first, for example in P3's rules. `source: "apia"` only marks where an entry came
  from.
- The current rotation is shown only when P3 returns a calendar and sources for it. If
  P3 returns infeasible replies without a calendar, only the violations appear, in
  `data_gaps`.
- `history[].source` is used only for the most recent entry (the previous crop). Older
  entries' sources do not change confidence.

## English-language output

All user-facing text P4 produces is now English:

- plan labels ("Option 1 — highest weighted score");
- benefits and trade-offs;
- explanations, including selection reasons, ranking and score intervals, Pareto status,
  scenario analysis, evaluator data gaps, and local agronomist checks;
- confidence reasons;
- calendar step reasons;
- assumptions and data gaps, including insufficient-data and search-limit messages;
- crop-history and rule-catalog notices;
- the computed-mode disclaimer in `pipeline.py`.

The translation kept the meaning of every statement. Algorithms, thresholds, scoring,
ranking, Pareto analysis, selection and calendar validation are unchanged. So are crop
IDs, API field names, source IDs and internal interfaces. The only rename is the internal
constant `CONFIDENCE_RO`, now `CONFIDENCE_TEXT`. The synthetic test evaluator's crop names
and messages were translated as well.

`tests/test_p4_english.py` guards this in two ways:

- it scans every string literal in the P4 source files for Romanian diacritics;
- it checks every user-facing field across 11 engine paths for Romanian diacritics and
  common Romanian words. The paths include scenario computed or unsupported, missing data,
  low coverage, insufficient data, search truncation, score-gap and similar-plan
  disclosures, evaluator warnings, clipped sowing windows, and unresolved sources.

The surrounding product is not yet English. Files outside P4's scope that still contain
user-facing Romanian, for the owners to translate:

- **P1:**
  - `apps/web/src/app/page.tsx`
  - `apps/web/src/app/layout.tsx` (also `<html lang="ro">`)
  - `apps/web/src/components/calculator.tsx` (form labels, errors, crop display names)
  - `apps/web/src/components/plan-card.tsx` (also confidence labels and the `ro-RO` date format)
  - `apps/web/src/components/location-map.tsx`
  - `apps/web/src/lib/api.ts`
- **P5:**
  - `apps/web/src/lib/server/engine.ts`
  - `apps/web/src/lib/server/http.ts`
  - `apps/web/src/app/api/locations/route.ts` (also the geocoder's `language: "ro"`)
  - `apps/web/src/app/api/internal/cache/[key]/route.ts`
- **Shared demo and fixtures** (needs agreement, because the contract tests use them):
  - `services/engine/fieldshift/demo.py`
  - `packages/contracts/examples/recommendation-request.json`
  - `packages/contracts/examples/recommendation-result.json`
- **Documentation:**
  - `AGENTS.md`, `README.md`, `CONTRIBUTING.md`
  - `docs/api.md`, `docs/architecture.md`, `docs/status.md`, `docs/team.md`
  - `apps/web/README.md`, `infra/README.md`, `packages/contracts/README.md`, `services/engine/README.md`

## Dependencies on other roles

- **P3:**
  - implement `load_rules` with `crops` and `sources`;
  - implement `evaluate` with the fields above, including regional calendars, criterion
    scores with provenance, `scenario_applied`, and source IDs that resolve to
    `rules.sources`, `environment.sources` or `evaluation.sources`;
  - agree on or amend the proposal above;
  - return `productivity` scores when available, `local_checks` when useful, and a
    calendar plus sources for infeasible sequences, so the current rotation can be shown
    with its violations.
- **P2:**
  - `build_environment` must be enabled and validated, and must return `sources` (plus
    optional `assumptions` and `data_gaps`), which the pipeline merges.
- **P5/P1:**
  - nothing is required. The result contract is unchanged.
  - P1 may want to render `baseline`, `scores`, `local_checks` and `violations`. The
    score interval and robustness notes are already in the plan text.

## Remaining work

1. Agree on the P3–P4 contract, then replace the fake evaluator in an integration test
   with P3's real evaluator on the Fundulea case.
2. Calibrate the selection thresholds with P3 and real candidate pools. Add crop families
   to the diversity metric.
3. Enable computed mode only after P2 and P3 are verified. Then update `docs/status.md`
   with what was actually checked.
