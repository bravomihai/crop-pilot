# Architecture

## Components

```
                 ┌────────────── backend (Next.js) ──────────────┐
React frontend ─►│ /api/farms  /api/analyses  /api/sms/inbound   │◄─ Twilio (SMS / WhatsApp)
                 │ storage (in-memory → DynamoDB)                │
                 └───────────────┬───────────────────────────────┘
                                 │ POST /analyze (FarmRequest)
                 ┌───────────────▼──────────── engine (Python) ───────────────┐
                 │ pipeline.analyze                                           │
                 │   data.fetch_field_data ─► FieldData                (P2)   │
                 │   evaluator.load_rules  ─► CropRules                (P3)   │
                 │   recommender.recommend                             (P4)   │
                 │       generate rotations → evaluator.evaluate (P3)         │
                 │       → rank by priorities → explain → AnalysisResult      │
                 └────────────────────────────────────────────────────────────┘
```

The three Python parts run in **one process**: no network calls between them, one thing to deploy. Only the backend and engine talk over HTTP. Formats: [contracts/](../contracts/README.md).

## Pipeline

| Step | Owner | What happens |
|---|---|---|
| 1. Field input | P1 | Boundary, crop history (APIA / spray records / typed / satellite / none), current rotation, priorities, constraints, scenario |
| 2. Field data | P2 | NASA POWER daily → yearly and monthly indicators (rain, ET₀, GDD, frost, heat, heavy rain); SRTM slope; SoilGrids; SMAP; CMIP6 deltas; later Sentinel-2 NDVI |
| 3. Candidates | P4 | Sequences of `rotation_years` crops from the crop set, optional cover crops in bare windows, minus excluded crops |
| 4. Rule filter | P3 | Return intervals, forbidden successors, maximum share. Alternatives that break a rule are dropped; the existing rotation is kept and its violations shown |
| 5. Scoring | P3 | Nine criteria, 0–1, each with sources: suitability (EcoCrop), yield (GAEZ), water (FAO-56 Kc × ET₀ vs rain and soil moisture), soil, erosion (slope × bare months × heavy rain), pest break, succession (successor matrix), forage, income |
| 6. Replay and scenarios | P3 | Each rotation is played over the observed weather years ("what would have happened") and under CMIP6 deltas + slider changes |
| 7. Ranking | P4 | Normalised farmer weights × scores. Diverse alternatives are preferred over near-duplicates |
| 8. Explanation and confidence | P4 | Template text built only from the evaluation's numbers and sources; confidence from four signals (history source, rotation evidence, satellite coverage, climate sensitivity); low confidence → questions for a local agronomist |
| 9. Delivery | P1, P5 | Results page with season strips and what-if controls; SMS summary with a link |

## Decisions

- **Transparent scoring, not a trained model, decides.** There's no dataset of the "right" rotation, the answer depends on the farmer's priorities, and outcome data is confounded. Rules and weighted scores with sources can be explained and checked.
- **ML only where labels exist:** the Sentinel-2 crop-history classifier (EuroCrops Romania), as a stretch goal. In v1 the farmer types the history.
- **LLM only for wording, later.** Explanations start as templates. An LLM may rephrase them but must not add facts that aren't in the evaluation.
- **Unknown is not neutral.** Missing data gives `null` scores and lowers confidence instead of defaulting to 0.5.
- **The evaluator doesn't know the priorities; the recommender doesn't know crops.** That keeps P3 and P4 independently testable.
- **Coarse data is used as context only.** SMAP, POWER, GRACE and CMIP6 describe the area, not the field; sub-field claims need Sentinel-2, Landsat or ECOSTRESS.

## Demo scope

The farmer enters the field, history and priorities. The app compares the existing rotation with two alternatives and shows, for each, what supports the evaluation, its benefits and what still needs local checking. Demo region: one county in southern Romania, 8–10 crops plus 1–2 cover crops, data precomputed for the demo field.
