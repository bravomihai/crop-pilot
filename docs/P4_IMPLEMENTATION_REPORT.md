# P4 — Recommendation engine: implementation report

Branch: `alexia` · Date: 2026-11-14 · Scope: `services/engine/fieldshift/recommender/`,
`services/engine/fieldshift/pipeline.py`, `services/engine/tests/`.

## Summary

The P4 recommender is implemented as deterministic Python code inside the existing engine
service. It generates candidate sequences, calls the P3 evaluator, rejects infeasible or
under-documented candidates, ranks them by the farmer's priorities, runs Pareto analysis,
picks up to three distinct alternatives, compares climate scenarios against a baseline
when P3 supports that, and writes explanations based only on what the evaluator returned.

**Computed mode is not functional yet.** P3 (`load_rules`, `evaluate`) and the P2 data
switch are still stubs. `ENGINE_MODE=computed` keeps returning HTTP 503, and a test checks
this. All algorithm tests use a **synthetic evaluator** (`tests/fake_evaluator.py`).
Its outputs are marked `fixture: true`, and the pipeline refuses to return them as
computed results. The tests check the P4 algorithms. They do not show that any crop,
calendar or score is agronomically correct.

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
| `fieldshift/recommender/scenarios.py` | new | Scenario detection, baseline request, robustness record |
| `fieldshift/recommender/explanations.py` | new | Benefits, trade-offs, explanation, labels and qualitative confidence |
| `fieldshift/recommender/engine.py` | new | Orchestration; returns `RecommendationOutcome` |
| `fieldshift/pipeline.py` | modified | Computed mode uses the full outcome (sources, assumptions, data gaps), refuses fixture evaluations, checks result semantics. Same function interface, `request_id`, modes and status rules |
| `tests/fake_evaluator.py` | new | Synthetic, clearly labelled P3 replacement for tests |
| `tests/test_recommender.py` | new | 47 test cases for P4 |
| `tests/test_p4_english.py` | new | 25 test cases checking that P4 output contains no Romanian |
| `docs/status.md` | modified | Status updated |

No changes to Zod, the JSON Schemas, the examples, P2/P3 modules, the web app or the infrastructure.

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
- `criteria`: for each of water, soil and climate:
  - `score`: 0–1 or null (higher is better)
  - `basis`: `observed | derived | estimated | assumed`
  - `summary`
  - `source_ids`
- `calendar`: three steps, each with `crop_id`, `crop_name`, `sowing_window`,
  `harvest_window`, `source_ids` and `reason`
- `warnings`: strings or `{message, severity}`
- `data_gaps`
- `source_ids`
- `sources`
- `scenario_applied`: bool
- `fixture`: bool (test evaluators only)

Questions for P3:

1. Is a 0–1 "higher is better" score per criterion acceptable, or does P3 prefer
   physical indicators (mm deficit, stress days) that P4 would rank directly?
2. Can P3 confirm `scenario_applied` on every reply, infeasible ones included?
3. Can the rules expose crop families, so diversity can account for agronomic similarity?

No change to the public Zod/JSON contracts is needed or proposed. One optional future
extension would need approval from P1, P3 and P5: structured robustness and score
fields on the plan. Today that information is carried in plan text.

## Tests

Command (Windows, project environment):

```
uv sync --project services/engine --frozen --extra dev
services/engine/.venv/Scripts/python.exe -m pytest services/engine/tests
```

`uv` was not installed on this machine. The pinned `uv==0.9.5` was installed into a
temporary folder only to run the sync. The `.venv` it created is gitignored.

**Result: 76 passed**: 4 existing contract tests, 47 P4 algorithm test cases, and 25
English-output regression test cases. The one warning is a Starlette deprecation notice
for `TestClient`.

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
| English output | `tests/test_p4_english.py`: detector self-check, static scan of 12 P4 source files, 11 generated-output paths, computed-result disclaimer |

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
  - agree on or amend the proposal above.
- **P2:**
  - `build_environment` must be enabled and validated, and must return `sources` (plus
    optional `assumptions` and `data_gaps`), which the pipeline merges.
- **P5/P1:**
  - nothing is required. The result contract is unchanged. P1 may want to show the score
    interval and robustness notes, which are already in the plan text.

## Remaining work

1. Agree on the P3–P4 contract, then replace the fake evaluator in an integration test
   with P3's real evaluator on the Fundulea case.
2. Calibrate the selection thresholds with P3 and real candidate pools. Add crop families
   to the diversity metric.
3. Enable computed mode only after P2 and P3 are verified. Then update `docs/status.md`
   with what was actually checked.
