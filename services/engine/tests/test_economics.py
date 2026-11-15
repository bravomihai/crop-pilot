"""Money estimate per plan: data lookup, unknowns, payments and the pipeline hook."""

import copy

from fieldshift.evaluator import economics
from fieldshift.evaluator.economics import add_economics, county_at, load_data, plan_economics


def step(order, crop_id, name, sow, harvest):
    return {"order": order, "crop_id": crop_id, "crop_name": name, "reason": "",
            "sowing_window": {"start": sow, "end": sow}, "harvest_window": {"start": harvest, "end": harvest}}


def plan(*crops):
    dates = [("2027-03-10", "2027-07-10"), ("2027-10-01", "2028-07-05"), ("2028-09-01", "2029-07-01")]
    return {"id": "p", "steps": [step(i + 1, c, n, *dates[i]) for i, (c, n) in enumerate(crops)]}


DATA, COUNTIES = load_data()
REQUEST = {"constraints": {"irrigated": False}}


def test_points_map_to_their_county():
    assert county_at(44.45, 26.5, COUNTIES) == "calarasi"
    assert county_at(45.75, 21.23, COUNTIES) == "timis"
    assert county_at(48.85, 2.35, COUNTIES) is None  # Paris


def test_known_crops_give_ranges_per_year_with_low_below_high():
    result = plan_economics(plan(("winter_wheat", "Winter wheat"), ("sunflower", "Sunflower"),
                                 ("winter_barley", "Winter barley")), REQUEST, "calarasi", DATA)
    assert 2.2 < result["covered_years"] < 2.4  # 10 March 2027 to 1 July 2029
    for key in ("income", "costs", "subsidies", "margin"):
        value = result["per_year"][key]
        assert value["low"] <= value["typical"] <= value["high"], (key, value)
    assert result["county"] == "Calarasi"
    assert {p["id"] for p in result["payments"]} >= {"PD-01", "PD-04", "PD-02"}


def test_a_crop_without_price_makes_totals_unknown_not_zero():
    result = plan_economics(plan(("pea", "Pea"), ("winter_wheat", "Winter wheat"), ("maize", "Maize")),
                            REQUEST, "calarasi", DATA)
    assert result["per_year"]["income"] is None and result["per_year"]["margin"] is None
    assert result["per_year"]["subsidies"] is not None
    pea = result["crops"][0]
    assert pea["price_lei_per_t"] is None and pea["income"] is None and pea["yield_t_per_ha"] is not None
    assert any(n.startswith("Pea: no official recent price series") for n in result["notes"])
    assert result["crops"][1]["income"] is not None  # the other crops are still shown


def test_soybean_adds_coupled_support_and_legumes_help_the_eco_scheme():
    soy = plan_economics(plan(("winter_wheat", "Winter wheat"), ("soybean", "Soybean"), ("maize", "Maize")),
                         REQUEST, "calarasi", DATA)
    other = plan_economics(plan(("winter_wheat", "Winter wheat"), ("sunflower", "Sunflower"), ("maize", "Maize")),
                           REQUEST, "calarasi", DATA)
    assert any(p["id"] == "PD-09" and p["included"] == "always" for p in soy["payments"])
    assert not any(p["id"] == "PD-09" for p in other["payments"])
    assert soy["per_year"]["subsidies"]["typical"] > other["per_year"]["subsidies"]["typical"]
    eco = next(p for p in soy["payments"] if p["id"] == "PD-04")
    assert eco["included"] == "if_eligible" and "legume" in eco["condition"]
    crisis = next(p for p in soy["payments"] if p["id"] == "PD-02")
    assert crisis["lei_per_ha_year"] is None and crisis["included"] == "not_included"


def test_same_crop_twice_in_a_row_warns_about_gaec_7():
    result = plan_economics(plan(("maize", "Maize"), ("maize", "Maize"), ("winter_wheat", "Winter wheat")),
                            REQUEST, "calarasi", DATA)
    assert any("GAEC 7" in w for w in result["warnings"])


def test_irrigation_raises_yields_and_costs():
    crops = (("maize", "Maize"), ("winter_wheat", "Winter wheat"), ("sunflower", "Sunflower"))
    dry = plan_economics(plan(*crops), REQUEST, "calarasi", DATA)
    wet = plan_economics(plan(*crops), {"constraints": {"irrigated": True}}, "calarasi", DATA)
    assert wet["crops"][0]["yield_t_per_ha"]["typical"] > dry["crops"][0]["yield_t_per_ha"]["typical"]
    assert wet["per_year"]["costs"]["typical"] > dry["per_year"]["costs"]["typical"]


def test_add_economics_cites_sources_and_skips_points_outside_romania():
    base = {"location": {"latitude": 44.45, "longitude": 26.5}, "plans": [plan(("maize", "Maize"),
            ("winter_wheat", "Winter wheat"), ("sunflower", "Sunflower"))], "sources": [], "assumptions": [],
            "data_gaps": []}
    result = copy.deepcopy(base)
    add_economics(result, REQUEST)
    cited = set(result["plans"][0]["economics"]["source_ids"])
    assert cited <= {s["id"] for s in result["sources"]}
    assert any("not a forecast" in a for a in result["assumptions"])
    outside = copy.deepcopy(base)
    outside["location"] = {"latitude": 48.85, "longitude": 2.35}
    add_economics(outside, REQUEST)
    assert "economics" not in outside["plans"][0]
    assert any("outside the Romanian county data" in g for g in outside["data_gaps"])


def test_missing_data_file_is_a_data_gap(monkeypatch):
    monkeypatch.setattr(economics, "load_data", lambda: None)
    result = {"location": {"latitude": 44.45, "longitude": 26.5}, "plans": [], "sources": [],
              "assumptions": [], "data_gaps": []}
    add_economics(result, REQUEST)
    assert result["data_gaps"] == ["Money estimate unavailable: the season data file is missing."]
