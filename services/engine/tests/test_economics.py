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
    # A crop the season file has no data for at all (hemp) keeps the totals unknown.
    result = plan_economics(plan(("hemp", "Hemp"), ("winter_wheat", "Winter wheat"), ("maize", "Maize")),
                            REQUEST, "calarasi", DATA)
    assert result["per_year"]["income"] is None and result["per_year"]["margin"] is None
    assert result["per_year"]["subsidies"] is not None
    hemp = result["crops"][0]
    assert hemp["price_lei_per_t"] is None and hemp["income"] is None and hemp["costs"] is None
    assert any(n.startswith("Hemp: no official recent price series") for n in result["notes"])
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


from fieldshift.evaluator.rules import load_rules  # noqa: E402

RULES = load_rules({"latitude": 44.45, "longitude": 26.5})


def test_a_legume_before_a_cereal_saves_nitrogen_and_raises_the_yield():
    after_pea = plan_economics(plan(("pea", "Pea"), ("winter_wheat", "Winter wheat"), ("maize", "Maize")),
                               REQUEST, "calarasi", DATA, RULES)
    after_barley = plan_economics(plan(("winter_barley", "Winter barley"), ("winter_wheat", "Winter wheat"),
                                       ("maize", "Maize")), REQUEST, "calarasi", DATA, RULES)
    wheat_after_pea, wheat_after_barley = after_pea["crops"][1], after_barley["crops"][1]
    assert wheat_after_pea["previous_rating"] == "good" and wheat_after_barley["previous_rating"] == "poor"
    kg = DATA["nitrogen_credit_kg_per_ha"]["pea"][1]
    assert wheat_after_pea["nitrogen_saving"]["typical"] == round(kg * DATA["nitrogen_price_lei_per_kg"]["value"] / 10) * 10
    assert wheat_after_barley["nitrogen_saving"] is None
    assert wheat_after_pea["costs"]["typical"] < wheat_after_barley["costs"]["typical"]
    assert wheat_after_pea["yield_t_per_ha"]["typical"] > wheat_after_barley["yield_t_per_ha"]["typical"]
    assert wheat_after_pea["crop_order_effect"] > 0 > wheat_after_barley["crop_order_effect"]
    # A legume after a legume gets no nitrogen saving.
    soy_after_pea = plan_economics(plan(("pea", "Pea"), ("soybean", "Soybean"), ("maize", "Maize")),
                                   REQUEST, "calarasi", DATA, RULES)["crops"][1]
    assert soy_after_pea["nitrogen_saving"] is None


def test_the_last_crop_in_the_history_is_the_first_previous_crop():
    request = {"constraints": {}, "history": [{"crop_id": "maize", "harvest_year": 2024},
                                              {"crop_id": "pea", "harvest_year": 2026}]}
    result = plan_economics(plan(("winter_wheat", "Winter wheat"), ("sunflower", "Sunflower"), ("maize", "Maize")),
                            request, "calarasi", DATA, RULES)
    assert result["crops"][0]["previous_crop"] == "Pea" and result["crops"][0]["nitrogen_saving"] is not None


def test_farmer_prices_and_costs_replace_estimates_and_complete_unknown_crops():
    crops = (("hemp", "Hemp"), ("winter_wheat", "Winter wheat"), ("maize", "Maize"))
    assert plan_economics(plan(*crops), REQUEST, "calarasi", DATA, RULES)["per_year"]["margin"] is None
    own = {"constraints": {}, "money_inputs": {"prices_lei_per_t": {"pea": 1500}, "costs_lei_per_ha": {"pea": 4000}}}
    known = plan_economics(plan(("pea", "Pea"), ("winter_wheat", "Winter wheat"), ("maize", "Maize")),
                           own, "calarasi", DATA, RULES)
    pea = known["crops"][0]
    assert pea["price_basis"] == "farmer" and pea["price_lei_per_t"]["typical"] == 1500
    assert pea["cost_basis"] == "farmer" and pea["costs"]["typical"] == 4000
    assert known["per_year"]["margin"] is not None
    assert not any(n.startswith("Pea:") for n in known["notes"])


def test_commercial_farm_yields_are_used_when_available_and_the_range_is_weather_only():
    result = plan_economics(plan(("winter_wheat", "Winter wheat"), ("sunflower", "Sunflower"), ("maize", "Maize")),
                            REQUEST, "calarasi", DATA, RULES)
    wheat = result["crops"][0]
    assert wheat["yield_basis"] == "commercial_farms"
    price = wheat["price_lei_per_t"]["typical"]
    assert abs(wheat["income"]["low"] - wheat["yield_t_per_ha"]["low"] * price) <= 10
    assert abs(wheat["income"]["high"] - wheat["yield_t_per_ha"]["high"] * price) <= 10
    factor = DATA["cost_index"]["factor"]
    assert abs(wheat["costs"]["typical"] - DATA["costs_lei_per_ha"]["winter_wheat"]["rainfed"] * factor) <= 10


def test_the_eight_new_crops_have_data_or_say_why_not():
    # Oats, spring barley, triticale: proxy budgets, county or national yields, INS prices.
    cereals = plan_economics(plan(("oats", "Oats"), ("triticale", "Triticale"), ("spring_barley", "Spring barley")),
                             REQUEST, "calarasi", DATA)
    oats, triticale, spring = cereals["crops"]
    assert oats["cost_basis"] == "proxy" and triticale["cost_basis"] == "proxy" and spring["cost_basis"] == "proxy"
    assert triticale["yield_basis"] == "national"
    assert all(c["yield_t_per_ha"] and c["price_lei_per_t"] for c in cereals["crops"])
    assert cereals["per_year"]["margin"] is not None
    assert any("winter barley budget stands in" in n for n in cereals["notes"])
    # Sorghum and rye have no official price: a labelled market estimate completes the plan.
    estimated = plan_economics(plan(("sorghum", "Grain sorghum"), ("winter_rye", "Winter rye"), ("maize", "Maize")),
                               REQUEST, "calarasi", DATA)
    sorghum, rye, _ = estimated["crops"]
    assert sorghum["price_basis"] == rye["price_basis"] == "market_estimate"
    assert sorghum["price_lei_per_t"]["typical"] == DATA["market_prices_lei_per_t"]["sorghum"]["typical"]
    assert estimated["per_year"]["margin"] is not None
    assert any(n.startswith("Winter rye: no recent official price; a market estimate") for n in estimated["notes"])


def test_a_recent_market_estimate_beats_an_old_official_price():
    beet = plan_economics(plan(("sugar_beet", "Sugar beet"), ("winter_wheat", "Winter wheat"), ("maize", "Maize")),
                          REQUEST, "calarasi", DATA)
    price = beet["crops"][0]["price_lei_per_t"]
    assert beet["crops"][0]["price_basis"] == "market_estimate"
    assert price == {k: DATA["market_prices_lei_per_t"]["sugar_beet"][k] for k in ("low", "typical", "high")}
    # Sugar beet is only grown under a factory contract, so its coupled support always counts.
    pd16 = next(p for p in beet["payments"] if p["id"] == "PD-16")
    assert pd16["included"] == "always"
    assert beet["per_year"]["subsidies"]["typical"] > 530 + pd16["lei_per_ha_year"] - 20


def test_pea_now_has_a_market_price_and_the_soybean_budget():
    result = plan_economics(plan(("pea", "Pea"), ("winter_wheat", "Winter wheat"), ("maize", "Maize")),
                            REQUEST, "calarasi", DATA, RULES)
    pea = result["crops"][0]
    assert pea["price_basis"] == "market_estimate" and pea["cost_basis"] == "proxy"
    assert result["per_year"]["margin"] is not None


def test_dry_beans_leave_nitrogen_and_get_contract_support_only_in_the_high_case():
    beans = plan_economics(plan(("dry_beans", "Dry beans"), ("winter_wheat", "Winter wheat"), ("maize", "Maize")),
                           REQUEST, "calarasi", DATA)
    assert beans["crops"][1]["nitrogen_saving"] is not None
    pd11 = next(p for p in beans["payments"] if p["id"] == "PD-11")
    assert pd11["included"] == "if_eligible"
    subsidies = beans["per_year"]["subsidies"]
    assert subsidies["high"] - subsidies["typical"] > pd11["lei_per_ha_year"] - 20  # PD-11 is only in the high case


def test_a_cost_budget_far_above_the_yields_used_is_flagged():
    potato = plan_economics(plan(("potato", "Potato"), ("winter_wheat", "Winter wheat"), ("maize", "Maize")),
                            REQUEST, "calarasi", DATA)
    if potato["crops"][0]["yield_basis"] != "commercial_farms":
        assert any(n.startswith("Potato: the yields used") for n in potato["notes"])
