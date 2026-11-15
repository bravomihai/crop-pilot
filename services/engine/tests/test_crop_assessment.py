from fieldshift.recommender.crop_assessment import assess_crops


def _crop(crop_id, name):
    return {
        "id": crop_id,
        "name": name,
        "ecocrop": {"ph_abs": [5, 8], "ph_opt": [6, 7]},
    }


def test_selected_crop_is_compared_to_better_alternatives():
    rules = {"crops": [_crop("potato", "Potato"), _crop("pea", "Pea")]}
    request = {"assessment_crops": ["potato"], "constraints": {}}

    def evaluate(rotation, request, environment, rules):
        return {
            "feasibility": "feasible",
            "criteria": {"productivity": {"score": 0.6 if rotation[0] == "potato" else 0.8}},
            "soil_inputs": {"ph": 6.5, "texture": "loamy"},
        }

    result = assess_crops(request, {}, rules, evaluate)
    assert result["selected"][0]["status"] == "assessed"
    assert "higher estimated" in result["selected"][0]["message"]
    assert result["alternatives"][0]["crop_id"] == "pea"


def test_unknown_soil_and_exclusions_are_not_presented_as_proven_fit():
    rules = {"crops": [_crop("potato", "Potato"), _crop("pea", "Pea")]}
    request = {
        "assessment_crops": ["potato", "unknown_crop"],
        "constraints": {"excluded_crops": ["pea"]},
    }

    def evaluate(rotation, request, environment, rules):
        return {
            "feasibility": "feasible",
            "criteria": {"productivity": {"score": 0.8}},
            "soil_inputs": {"ph": None},
        }

    result = assess_crops(request, {}, rules, evaluate)
    assert result["selected"][0]["status"] == "uncertain"
    assert "pH is unknown" in result["selected"][0]["message"]
    assert result["selected"][1]["score"] is None
    assert result["alternatives"] == []


def test_violations_and_out_of_range_ph_are_not_recommended():
    rules = {"crops": [_crop("potato", "Potato"), _crop("pea", "Pea")]}
    request = {"assessment_crops": ["potato", "pea"], "constraints": {}}

    def evaluate(rotation, request, environment, rules):
        return {
            "feasibility": "infeasible" if rotation[0] == "pea" else "feasible",
            "violations": ["Rotation restriction."] if rotation[0] == "pea" else [],
            "criteria": {"productivity": {"score": 0.2}},
            "soil_inputs": {"ph": 4.0},
        }

    result = assess_crops(request, {}, rules, evaluate)
    assert [item["status"] for item in result["selected"]] == [
        "not_recommended", "not_recommended",
    ]


def test_missing_texture_or_uncertain_land_cover_cannot_confirm_crop_fit():
    rules = {"crops": [_crop("potato", "Potato")]}
    request = {"assessment_crops": ["potato"], "constraints": {}}

    def evaluate(rotation, request, environment, rules):
        return {
            "feasibility": "feasible",
            "criteria": {"productivity": {"score": 0.8}},
            "soil_inputs": {"ph": 6.5, "texture": environment.get("texture")},
        }

    assert assess_crops(request, {}, rules, evaluate)["selected"][0]["status"] == "uncertain"
    environment = {"texture": "loamy", "land_cover": {"status": "uncertain"}}
    assert assess_crops(request, environment, rules, evaluate)["selected"][0]["status"] == "uncertain"


def test_higher_scoring_alternative_is_qualified_when_soil_is_unknown():
    rules = {"crops": [_crop("potato", "Potato"), _crop("pea", "Pea")]}
    request = {"assessment_crops": ["potato"], "constraints": {}}

    def evaluate(rotation, request, environment, rules):
        return {
            "feasibility": "feasible",
            "criteria": {"productivity": {"score": 0.3 if rotation[0] == "potato" else 0.7}},
            "soil_inputs": {"ph": None},
        }

    selected = assess_crops(request, {}, rules, evaluate)["selected"][0]
    assert selected["status"] == "uncertain"
    assert "scored higher" in selected["message"]
    assert "also needs checking" in selected["message"]


def test_selected_crops_are_also_compared_with_each_other():
    rules = {"crops": [_crop("potato", "Potato"), _crop("pea", "Pea")]}
    request = {"assessment_crops": ["potato", "pea"], "constraints": {}}

    def evaluate(rotation, request, environment, rules):
        return {
            "feasibility": "feasible",
            "criteria": {"productivity": {"score": 0.3 if rotation[0] == "potato" else 0.7}},
            "soil_inputs": {"ph": 6.5, "texture": "loamy"},
        }

    result = assess_crops(request, {}, rules, evaluate)
    assert "higher estimated" in result["selected"][0]["message"]
    assert result["alternatives"] == []
