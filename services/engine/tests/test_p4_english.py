"""Regression tests: P4 user-facing output must be English.

Two layers:
1. Static scan of every string literal in the P4 source files (recommender package and
   pipeline.py) for Romanian diacritics and common Romanian words.
2. Dynamic scan of every user-facing field produced across many engine paths.

Heuristic by design: it catches accidental Romanian templates, not every possible word.
Values from the synthetic evaluator (tests/fake_evaluator.py) are English too.
"""

import io
import re
import tokenize
from pathlib import Path

import pytest

from fake_evaluator import FakeEvaluator, fake_rules
from fieldshift import pipeline
from fieldshift.contracts import example
from fieldshift.recommender import RecommenderConfig, recommend

ENGINE = Path(__file__).resolve().parents[1] / "fieldshift"
P4_FILES = sorted((ENGINE / "recommender").glob("*.py")) + [ENGINE / "pipeline.py"]
DIACRITICS = re.compile(r"[ăâîșțşţĂÂÎȘȚŞŢ]")
ROMANIAN_WORDS = re.compile(
    # Whole Romanian words only; stems such as "scor" would also match English "score".
    r"\b(nu|sau|pentru|este|sunt|din|fără|cultura|culturi|culturilor|fezabil|fezabile|"
    r"nefezabil|varianta|scor|scorul|ponderat|semănat|recoltare|încredere|lipsă|surse|"
    r"istoricul|solul|terenul|prioritățile|evaluatorul|scenariul|ipoteză|planul|calendarul)\b",
    re.IGNORECASE,
)


def romanian_hits(text: str) -> list[str]:
    hits = DIACRITICS.findall(text)
    hits += [m.group(0) for m in ROMANIAN_WORDS.finditer(text)]
    return hits


def string_literals(path: Path):
    source = path.read_text(encoding="utf-8")
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.STRING or token.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
            yield token.start[0], token.string


def test_detector_flags_romanian_samples():
    assert romanian_hits("Selectat ca plan cu cel mai mare scor ponderat")
    assert romanian_hits("Istoricul culturilor nu a fost completat")
    assert not romanian_hits("Selected as the plan with the highest guaranteed weighted score.")
    assert not romanian_hits("Soil properties are not known; the score becomes an interval.")


@pytest.mark.parametrize("path", P4_FILES, ids=lambda p: p.name)
def test_p4_source_strings_contain_no_romanian(path):
    offenders = [
        f"{path.name}:{line}: {text[:80]}"
        for line, text in string_literals(path)
        if DIACRITICS.search(text)
    ]
    assert not offenders, "Romanian text in P4 source:\n" + "\n".join(offenders)


def _request(**changes):
    request = example("recommendation-request")
    request.update(changes)
    return request


def _paths():
    """Outcomes covering every text-producing branch that P4 has."""
    rules = fake_rules()
    yield "baseline", recommend(_request(), {"sources": []}, rules, FakeEvaluator())
    yield "scenario_computed", recommend(
        _request(scenario={"temp_change_c": 3, "rain_change_pct": -20}),
        {"sources": []}, rules, FakeEvaluator(scenario_aware=True),
    )
    yield "scenario_unsupported", recommend(
        _request(scenario={"temp_change_c": 2, "rain_change_pct": 0}), {"sources": []}, rules, FakeEvaluator()
    )
    yield "missing_soil_score", recommend(_request(), {"sources": []}, rules, FakeEvaluator(missing=("soil",)))
    yield "low_coverage", recommend(_request(), {"sources": []}, rules, FakeEvaluator(missing=("water", "soil")))
    request = _request(history=[{"crop_id": "unlisted", "harvest_year": 2030}])
    request["constraints"] = {"irrigated": True, "excluded_crops": ["delta", "epsilon"]}
    request["soil"] = {"texture": "loamy", "source": "farmer_estimate"}
    yield "history_irrigation", recommend(request, {"sources": []}, rules, FakeEvaluator())
    excluded = _request()
    excluded["constraints"]["excluded_crops"] = [c["id"] for c in rules["crops"]]
    yield "all_excluded", recommend(excluded, {"sources": []}, rules, FakeEvaluator())
    yield "no_rules", recommend(_request(), {"sources": []}, {}, FakeEvaluator())
    yield "truncated", recommend(
        _request(), {"sources": []}, rules, FakeEvaluator(), RecommenderConfig(max_candidates=20)
    )
    tight = RecommenderConfig(max_score_gap=0.0, min_distance=1.0)
    yield "score_gap_low_diversity", recommend(_request(), {"sources": []}, rules, FakeEvaluator(), tight)

    inner = FakeEvaluator()

    def odd(rotation, req, environment, r):
        result = inner(rotation, req, environment, r)
        if result.get("feasibility") == "feasible":
            result["source_ids"] = ["fake-p3", "ghost"]
            result["warnings"] = [{"message": "synthetic warning", "severity": "high"}]
            result["data_gaps"] = ["synthetic gap"]
            result["calendar"][0]["sowing_window"]["start"] = "2027-01-01"
            result["criteria"]["climate"]["basis"] = "estimated"
        return result

    yield "warnings_clipping_unresolved", recommend(_request(), {"sources": []}, rules, odd)


def _user_facing(outcome) -> list[str]:
    texts = list(outcome.assumptions) + list(outcome.data_gaps)
    for plan in outcome.plans:
        texts += [plan["label"], plan["explanation"], *plan["benefits"], *plan["tradeoffs"]]
        texts += [step["reason"] for step in plan["steps"]]
    return texts


@pytest.mark.parametrize("name,outcome", list(_paths()), ids=lambda v: v if isinstance(v, str) else "")
def test_generated_output_is_english(name, outcome):
    offenders = [t for t in _user_facing(outcome) if romanian_hits(t)]
    assert not offenders, f"{name}: Romanian output:\n" + "\n".join(offenders)


def test_computed_result_disclaimer_and_texts_are_english():
    result = pipeline.computed_result(_request(), "req-en", {"sources": []}, fake_rules(), FakeEvaluator(fixture=False))
    assert not romanian_hits(result["disclaimer"])
    assert result["plans"] and result["plans"][0]["label"].startswith("Option 1")
    assert "confidence" in result["plans"][0]["explanation"]
