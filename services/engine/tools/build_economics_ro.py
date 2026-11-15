"""Build the season data file for the money estimate (Romania).

Run once per season, by hand, and commit the output. Calculations never download data.

    services/engine/.venv/Scripts/python services/engine/tools/build_economics_ro.py

Downloads (all public, no keys):
- INS TEMPO AGR110A: average yield per hectare by county, last 10 years;
- INS TEMPO PPA102C: average farm-gate prices by development region, last 5 years;
- Eurostat GISCO NUTS 2021 level 3 (= Romanian counties), 1:10 million boundaries;
- ECB EUR/RON reference rate on the last business day of September.

Copied by hand (cited below): ICEADR per-hectare cost budgets (2022-2023 cost level) and
the CAP payment rates reported for the 2026 campaign (to be checked against the Order).
"""

import json
import statistics
import sys
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "fieldshift" / "evaluator" / "rules" / "economics"
TEMPO = "http://statistici.insse.ro:8077/tempo-ins"
AGENT = {"User-Agent": "croppilot-data-script", "Content-Type": "application/json"}
CAMPAIGN = 2026

# Rule crop id -> (INS yield item in AGR110A or None, INS price item in PPA102C or None).
CROPS = {
    "winter_wheat": ("Grau comun", "Grau"),
    "winter_barley": ("Orz", "Orz"),
    "winter_rapeseed": ("Rapita", "Rapita"),
    "maize": ("Porumb boabe", "Porumb boabe"),
    "sunflower": ("Floarea soarelui", "Floarea soarelui"),
    "soybean": ("Soia boabe", "Soia"),
    # INS stopped publishing dry pea purchase prices in 2007 (table PPA102B).
    "pea": ("Mazare boabe", None),
    "oats": ("Ovaz", "Ovaz"),
    # No current INS or Eurostat price for grain sorghum or rye in Romania.
    "sorghum": ("Sorg", None),
    "dry_beans": ("Fasole boabe", "Fasole boabe"),
    "sugar_beet": ("Sfecla de zahar", "Sfecla de zahar"),
    # Spring (two-row) barley: AGR110A has no column of its own; its yield is derived from
    # AGR108A/AGR109A as "Orz si orzoaica" minus "Orz" (see build_commercial_yields).
    "spring_barley": (None, "Orzoaica"),
    # INS publishes no triticale yield; the Eurostat national yield is used instead.
    "triticale": (None, "Triticale"),
    "winter_rye": ("Secara", None),
    "potato": ("Cartofi de toamna", "Cartofi de toamna"),
}

# Eurostat apro_cpsh1 national yields (EU standard humidity), a fallback when county data is thin.
EUROSTAT_YIELD = {
    "triticale": "C1600", "winter_rye": "C1210", "spring_barley": "C1320", "oats": "C1410",
    "sorghum": "C1700", "pea": "P1100", "potato": "R1000", "sugar_beet": "R2000",
}

# ICEADR, "Ghid practic tehnico-economic ... estimari pentru anul de productie 2022-2023",
# conventional system. Total cost per hectare = the budget's production cost (lei/t, "COST DE
# PRODUCTIE") times its planned yield; the yields are kept to scale county yields under irrigation.
ICEADR_COSTS = {
    "winter_wheat": {"rainfed": 5417, "irrigated": 7377, "yield_rainfed": 4440, "yield_irrigated": 6215},
    "winter_barley": {"rainfed": 4955, "irrigated": 6781, "yield_rainfed": 4440, "yield_irrigated": 6215},
    "maize": {"rainfed": 5532, "irrigated": 8056, "yield_rainfed": 6000, "yield_irrigated": 8400},
    "sunflower": {"rainfed": 5107, "irrigated": 6628, "yield_rainfed": 2630, "yield_irrigated": 3680},
    "winter_rapeseed": {"rainfed": 5777, "irrigated": 7438, "yield_rainfed": 2570, "yield_irrigated": 3600},
    "soybean": {"rainfed": 5399, "irrigated": 7113, "yield_rainfed": 2430, "yield_irrigated": 3400},
    "potato": {"rainfed": 22261, "irrigated": 26512, "yield_rainfed": 16700, "yield_irrigated": 23400},
    "sugar_beet": {"rainfed": 12268, "irrigated": 16802, "yield_rainfed": 38700, "yield_irrigated": 54200},
}

# ICEADR publishes no budget for these crops; the closest budgeted crop stands in for them
# and the estimate says so ("proxy"). Expert choices pending agronomist review.
COST_PROXIES = {
    "oats": "winter_barley", "spring_barley": "winter_barley", "triticale": "winter_wheat",
    "winter_rye": "winter_wheat", "sorghum": "maize", "dry_beans": "soybean",
}

# Shares of the ICEADR rainfed wheat budget (2022-2023) used to index costs to the latest year:
# chemical fertilisers 2,023 and mechanised work 2,069 of 5,419 lei/ha. Mechanised work follows
# the diesel price as a proxy; the rest of the budget is kept at its level.
COST_SHARES = {"fertiliser": 0.373, "mechanised_work": 0.382}

# Nitrogen a legume leaves for the next crop, kg N/ha (low, typical, high). Romanian practice
# lowers the next crop's N dose by 30-50 kg N/ha after soybean or pea (worked example: 35);
# a long-term study found about 20 kg N/ha less fertiliser for wheat after pea (Soon, 2005).
NITROGEN_CREDIT_KG = {"pea": [20, 35, 50], "soybean": [20, 35, 50], "dry_beans": [20, 35, 50]}

# CAP Strategic Plan 2023-2027 payments relevant to a single arable field (EUR/ha/year).
PAYMENTS = [
    {
        "id": "PD-01", "label": "Basic income support (BISS)", "eur_per_ha": 101.03,
        "applies": "all", "source": "apia-2026-rates",
        "condition": "Paid on every eligible hectare of an active farmer; the same for every plan.",
    },
    {
        "id": "PD-04", "label": "Eco-scheme for arable land", "eur_per_ha": 56.28,
        "applies": "eco_scheme", "source": "apia-2026-rates",
        "condition": "Only if the whole farm meets the eco-scheme: at least 85% of its arable land "
                     "covered by crops, plus the optional requirements it chooses.",
    },
    {
        "id": "PD-09", "label": "Coupled support for soybean", "eur_per_ha": 141.98, "crops": ["soybean"],
        "applies": "crop", "source": "apia-coupled-2025",
        "condition": "For each hectare of soybean declared to APIA; rate of the 2025 claim year.",
    },
    {
        "id": "PD-11", "label": "Coupled support for legumes grown for processing", "eur_per_ha": 209.70,
        "crops": ["dry_beans"], "applies": "crop_contract", "source": "apia-coupled-2025",
        "condition": "For dry beans grown for processing, usually under a contract with a processor; "
                     "rate of the 2025 claim year.",
    },
    {
        "id": "PD-16", "label": "Coupled support for sugar beet", "eur_per_ha": 818.19,
        "crops": ["sugar_beet"], "applies": "crop_contract", "source": "apia-coupled-2025",
        "condition": "For sugar beet delivered under a contract with a sugar factory; rate reported for "
                     "the 2025 claim year (sources disagree: check the Order).",
    },
    {
        "id": "PD-02", "label": "Redistributive payment (CRISS)", "eur_per_ha": None,
        "applies": "farm_size", "source": "apia-2026-rates",
        "condition": "Depends on the size of your farm, not on the plan; not included in the totals.",
    },
]


def plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().strip().lower()


def get_json(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def tempo(matrix: str, dims: list[list[int]], max_dim: int) -> list[list[str]]:
    query = ":".join(",".join(map(str, items)) for items in dims)
    body = json.dumps({"encQuery": query, "language": "ro", "matCode": matrix, "matMaxDim": max_dim,
                       "matUMSpec": 0, "matRegJ": 0}).encode()
    request = urllib.request.Request(f"{TEMPO}/pivot", data=body, headers=AGENT)
    with urllib.request.urlopen(request, timeout=300) as r:
        lines = r.read().decode("utf-8").strip().splitlines()
    return [[cell.strip() for cell in line.split(",")] for line in lines[1:]]


def options(meta: dict, index: int) -> list[dict]:
    return meta["dimensionsMap"][index]["options"]


def number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None  # ":" or "-" in TEMPO means not available


def build_yields(this_year: int):
    meta = get_json(f"{TEMPO}/matrix/AGR110A")
    crop_ids = {o["label"].strip(): o["nomItemId"] for o in options(meta, 0)}
    areas = options(meta, 2)
    counties, county_region, region = [], {}, None
    for o in areas:
        label = o["label"].strip()
        if label.upper().startswith("REGIUNEA"):
            region = label
        elif not label.upper().startswith(("TOTAL", "MACRO", "MUN")):
            counties.append(o["nomItemId"])
            county_region[plain(label)] = region
    years = [o for o in options(meta, 3) if this_year - 10 <= int(o["label"].split()[-1]) < this_year]
    rows = tempo("AGR110A", [[crop_ids[name] for name, _ in CROPS.values() if name], [5789], counties,
                             [o["nomItemId"] for o in years], [options(meta, 4)[0]["nomItemId"]]], 5)
    by_name = {name: crop for crop, (name, _) in CROPS.items() if name}
    yields: dict = {}
    for crop_name, _form, county, year, _unit, value in rows:
        kg = number(value)
        if kg is None or kg <= 0:
            continue
        entry = yields.setdefault(plain(county), {}).setdefault(by_name[crop_name], {})
        entry[year.split()[-1]] = round(kg / 1000, 2)
    return yields, county_region, meta["ultimaActualizare"]


def build_prices(this_year: int):
    meta = get_json(f"{TEMPO}/matrix/PPA102C")
    items = {o["label"].strip(): o["nomItemId"] for o in options(meta, 0)}
    years = [o for o in options(meta, 2) if o["label"].startswith("Anul ")
             and this_year - 5 <= int(o["label"].split()[-1]) < this_year]
    lei_kg = next(o["nomItemId"] for o in options(meta, 3) if o["label"].strip().lower().startswith("lei / kg"))
    wanted = {name: crop for crop, (_, name) in CROPS.items() if name}
    rows = tempo("PPA102C", [[items[n] for n in wanted], [o["nomItemId"] for o in options(meta, 1)],
                             [o["nomItemId"] for o in years], [lei_kg]], 4)
    prices: dict = {}
    for product, region, year, _unit, value in rows:
        lei = number(value)
        if lei is None or lei <= 0:
            continue
        prices.setdefault(region.strip(), {}).setdefault(wanted[product.strip()], {})[year.split()[-1]] = round(lei * 1000)
    return prices, meta["ultimaActualizare"]


def build_counties(names: set[str]) -> dict:
    url = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_10M_2021_4326_LEVL_3.geojson"
    features = []
    for feature in get_json(url)["features"]:
        props = feature["properties"]
        if props["CNTR_CODE"] != "RO":
            continue
        name = plain(props["NUTS_NAME"])
        name = "municipiul bucuresti" if name == "bucuresti" else name
        if name not in names and name != "municipiul bucuresti":
            print("county without INS match:", props["NUTS_NAME"], file=sys.stderr)
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        rings = [[[round(x, 4), round(y, 4)] for x, y in polygon[0]] for polygon in polygons]
        features.append({"county": name, "nuts": props["NUTS_ID"], "rings": rings})
    return {
        "source": "Eurostat GISCO, NUTS 2021 level 3, 1:10 million (© EuroGeographics for the administrative boundaries)",
        "counties": features,
    }


def build_commercial_yields(this_year: int) -> tuple[dict, dict]:
    """Yields of commercial farms: (total - individual holdings) production / area, per county.

    Also returns all-farm yields for spring barley, which AGR110A does not list: the
    "barley and two-row barley" row minus the "barley" row of AGR108A/AGR109A.
    """
    out: dict = {}
    derived: dict = {}
    series: dict = {}
    for matrix, key in (("AGR108A", "area"), ("AGR109A", "production")):
        meta = get_json(f"{TEMPO}/matrix/{matrix}")
        items = {" ".join(o["label"].split()): o["nomItemId"] for o in options(meta, 0)}
        wanted = {}
        names = [(crop, name) for crop, (name, _) in CROPS.items() if name] + [("_barley_all", "Orz si orzoaica")]
        for crop, name in names:
            item = items.get(name) or items.get(name.replace(" boabe", ""))
            if item:
                wanted[item] = crop
            else:
                print(f"{matrix}: no item for {name}", file=sys.stderr)
        forms = [o["nomItemId"] for o in options(meta, 1)
                 if o["label"].strip().lower().startswith(("total", "din care"))]
        counties = [o["nomItemId"] for o in options(meta, 2)
                    if not o["label"].strip().upper().startswith(("TOTAL", "MACRO", "REGIUNEA", "MUN"))]
        years = [o["nomItemId"] for o in options(meta, 3)
                 if this_year - 10 <= int(o["label"].split()[-1]) < this_year]
        labels = {o["nomItemId"]: " ".join(o["label"].split()) for o in options(meta, 0)}
        rows = tempo(matrix, [list(wanted), forms, counties, years, [options(meta, 4)[0]["nomItemId"]]], 5)
        by_label = {labels[i]: c for i, c in wanted.items()}
        for row in rows:
            crop_label, form, county, year, _unit, value = row[0], row[1], row[2], row[3], row[4], row[5]
            crop_label = " ".join(crop_label.split())
            amount = number(value)
            if amount is None:
                continue
            kind = "total" if form.lower().startswith("total") else "individual"
            cell = series.setdefault((plain(county), by_label[crop_label], year.split()[-1]), {})
            cell[f"{key}_{kind}"] = amount
    # Spring barley = (barley and two-row barley) - barley, cell by cell.
    for (county, crop, year), cell in list(series.items()):
        winter = series.get((county, "winter_barley", year))
        if crop != "_barley_all" or not winter:
            continue
        spring = {k: cell[k] - winter[k] for k in cell if k in winter}
        series[(county, "spring_barley", year)] = spring
        if spring.get("area_total", 0) >= 200 and spring.get("production_total", 0) > 0:
            derived.setdefault(county, {}).setdefault("spring_barley", {})[year] = round(
                spring["production_total"] / spring["area_total"], 2)
    for (county, crop, year), cell in series.items():
        if crop.startswith("_"):
            continue
        try:
            area = cell["area_total"] - cell["area_individual"]
            production = cell["production_total"] - cell["production_individual"]
        except KeyError:
            continue
        # Too little commercial area makes the ratio noisy; leave those years out.
        if area < max(200, 0.1 * cell["area_total"]) or production <= 0:
            continue
        out.setdefault(county, {}).setdefault(crop, {})[year] = round(production / area, 2)
    return out, derived


def eurostat_national_yields(this_year: int) -> dict:
    """Romanian national yields (t/ha) from Eurostat apro_cpsh1, completed years only."""
    url = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/apro_cpsh1"
           f"?format=JSON&lang=EN&geo=RO&strucpro=YLD_HUMD_EU_T_HA&sinceTimePeriod={this_year - 10}")
    data = get_json(url)
    ids, size = data["id"], data["size"]
    index = {k: data["dimension"][k]["category"]["index"] for k in ids}
    out: dict = {}
    for crop, code in EUROSTAT_YIELD.items():
        if code not in index["crops"]:
            continue
        for year in index["time"]:
            if int(year) >= this_year:
                continue  # the current year is provisional
            position = {"crops": index["crops"][code], "time": index["time"][year]}
            flat = 0
            for name, dim_size in zip(ids, size):
                flat = flat * dim_size + position.get(name, 0)
            value = data["value"].get(str(flat))
            if value:
                out.setdefault(crop, {})[year] = value
    return {"yields_t_per_ha": out, "updated": data.get("updated")}


def eurostat_input_prices() -> dict:
    """Romanian purchase prices of fertiliser nitrogen and diesel, national currency, by year."""
    url = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/apri_ap_ina"
           "?format=JSON&lang=EN&geo=RO&currency=NAC")
    data = get_json(url)
    ids, size = data["id"], data["size"]
    index = {k: data["dimension"][k]["category"]["index"] for k in ids}

    def value(product: str, year: str):
        position = {"currency": index["currency"]["NAC"], "prod_inp": index["prod_inp"][product],
                    "time": index["time"][year]}
        flat = 0
        for name, dim_size in zip(ids, size):
            flat = flat * dim_size + position.get(name, 0)
        return data["value"].get(str(flat))

    nitrogen, diesel = {}, {}
    for year in sorted(index["time"], key=int):
        n_prices = [v for v in (value("20311301", year), value("20311400", year)) if v]
        if n_prices:
            nitrogen[year] = round(sum(n_prices) / len(n_prices) / 100, 2)  # lei per kg N
        d = value("20232000", year)
        if d:
            diesel[year] = round(d / 100, 2)  # lei per litre
    return {"nitrogen_lei_per_kg": nitrogen, "diesel_lei_per_l": diesel, "updated": data.get("updated")}


def cost_index(inputs: dict) -> dict:
    nitrogen, diesel = inputs["nitrogen_lei_per_kg"], inputs["diesel_lei_per_l"]
    latest = max(set(nitrogen) & set(diesel), key=int)

    def base(series):
        return (series["2022"] + series["2023"]) / 2

    n_ratio, d_ratio = nitrogen[latest] / base(nitrogen), diesel[latest] / base(diesel)
    rest = 1 - COST_SHARES["fertiliser"] - COST_SHARES["mechanised_work"]
    factor = COST_SHARES["fertiliser"] * n_ratio + COST_SHARES["mechanised_work"] * d_ratio + rest
    return {"factor": round(factor, 3), "from": "2022-2023", "to": latest, "nitrogen_ratio": round(n_ratio, 3),
            "diesel_ratio": round(d_ratio, 3), "shares": COST_SHARES}


def ecb_rate(year: int) -> tuple[float, str]:
    url = (f"https://data-api.ecb.europa.eu/service/data/EXR/D.RON.EUR.SP00.A?startPeriod={year}-09-20"
           f"&endPeriod={year}-09-30&format=jsondata")
    data = get_json(url)
    series = next(iter(data["dataSets"][0]["series"].values()))["observations"]
    days = data["structure"]["dimensions"]["observation"][0]["values"]
    last = max(series, key=int)
    return series[last][0], days[int(last)]["id"]


def main() -> None:
    this_year = CAMPAIGN
    yields, county_region, yields_updated = build_yields(this_year)
    prices, prices_updated = build_prices(this_year)
    rate, rate_day = ecb_rate(CAMPAIGN)
    commercial, derived = build_commercial_yields(this_year)
    for county, crops in derived.items():
        for crop, series in crops.items():
            yields.setdefault(county, {}).setdefault(crop, series)
    national = eurostat_national_yields(this_year)
    costs = dict(ICEADR_COSTS)
    for crop, source in COST_PROXIES.items():
        costs[crop] = {**ICEADR_COSTS[source], "proxy_of": source}
    inputs = eurostat_input_prices()
    index = cost_index(inputs)
    n_year = max(inputs["nitrogen_lei_per_kg"], key=int)
    retrieved = date.today().isoformat()
    data = {
        "campaign": CAMPAIGN,
        "currency": "RON",
        "retrieved": retrieved,
        "crops": {crop: {"ins_yield_item": y, "ins_price_item": p} for crop, (y, p) in CROPS.items()},
        "county_region": county_region,
        "yields_t_per_ha": yields,
        "yields_commercial_t_per_ha": commercial,
        "yields_national_t_per_ha": national["yields_t_per_ha"],
        "prices_lei_per_t": prices,
        "costs_lei_per_ha": costs,
        "cost_level_years": "2022-2023",
        "cost_index": index,
        "input_prices": inputs,
        "nitrogen_price_lei_per_kg": {"value": inputs["nitrogen_lei_per_kg"][n_year], "year": n_year,
                                      "source": "eurostat-input-prices"},
        "nitrogen_credit_kg_per_ha": NITROGEN_CREDIT_KG,
        "eur_ron": {"rate": rate, "date": rate_day, "source": "ecb-eur-ron"},
        "payments": PAYMENTS,
        "sources": [
            {"id": "ins-agr110a", "title": f"INS TEMPO AGR110A: average yield per hectare by county (updated {yields_updated})",
             "url": "http://statistici.insse.ro:8077/tempo-online/#/pages/tables/insse-table", "resolution": "county, yearly"},
            {"id": "ins-ppa102c", "title": f"INS TEMPO PPA102C: average farm-gate prices by development region (updated {prices_updated})",
             "url": "http://statistici.insse.ro:8077/tempo-online/#/pages/tables/insse-table", "resolution": "development region, yearly"},
            {"id": "iceadr-budgets", "title": "ICEADR: income and cost budgets per hectare, conventional system, production year 2022-2023",
             "url": "https://iceadr.ro/wp-content/uploads/2024/02/2023_ghid-veget.pdf"},
            {"id": "apia-2026-rates", "title": "CAP direct payment rates reported for the 2026 campaign (OMADR 288/2026, as reported in the farming press; check the Order)",
             "url": "https://revista-ferma.ro/plata-avans-apia-2026-sume-pe-hectar-si-cap-de-animal/"},
            {"id": "apia-coupled-2025", "title": "Coupled support rates for soybean, legumes for processing and sugar beet, 2025 claim year (as reported; check the Order)",
             "url": "https://www.bzi.ro/s-a-stabilit-cuantumul-pe-hectar-pentru-sprijinul-cuplat-vegetal-fermierii-asteapta-banii-de-anul-trecut-5517994"},
            {"id": "apia-ecoscheme-2026", "title": "APIA: 2026 payment application instructions, eco-scheme PD-04 (Annex 2)",
             "url": "https://apia.org.ro/wp-content/uploads/2026/03/Anexa-2.pdf"},
            {"id": "ins-agr108a-109a", "title": "INS TEMPO AGR108A and AGR109A: cultivated area and production by county and type of holding (commercial farms = total minus individual holdings)",
             "url": "http://statistici.insse.ro:8077/tempo-online/#/pages/tables/insse-table", "resolution": "county, yearly"},
            {"id": "eurostat-crop-yields", "title": "Eurostat apro_cpsh1: crop yields in Romania (national, EU standard humidity), used where county data is missing or thin",
             "url": "https://ec.europa.eu/eurostat/databrowser/view/apro_cpsh1/default/table"},
            {"id": "eurostat-input-prices", "title": "Eurostat apri_ap_ina: purchase prices of agricultural inputs in Romania (ammonium nitrate, urea, diesel)",
             "url": "https://ec.europa.eu/eurostat/databrowser/view/apri_ap_ina/default/table"},
            {"id": "nitrogen-credit", "title": "Nitrogen left by pea and soybean for the next crop: Romanian fertilisation practice (30-50 kg N/ha) and Soon (2005), about 20 kg N/ha for wheat after pea",
             "url": "https://www.bzi.ro/ce-influenteaza-necesarul-de-azot-la-porumb-si-cum-se-stabileste-fertilizarea-culturii-5571958"},
            {"id": "ecb-eur-ron", "title": f"European Central Bank EUR/RON reference rate, {rate_day}",
             "url": "https://data.ecb.europa.eu/data/datasets/EXR"},
            {"id": "gisco-nuts3", "title": "Eurostat GISCO NUTS 2021 county boundaries (© EuroGeographics)",
             "url": "https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics"},
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"ro_{CAMPAIGN}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    counties = build_counties(set(yields))
    (OUT / "ro_counties.json").write_text(json.dumps(counties, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(yields)} counties with yields, {len(commercial)} with commercial-farm yields, "
          f"{len(prices)} price regions, EUR/RON {rate} on {rate_day}, cost index {index}")
    for crop in CROPS:
        known = sum(1 for c in yields.values() if crop in c)
        print(f"  {crop:16} yields in {known} counties, median price SUD-MUNTENIA "
              f"{statistics.median(prices.get('Regiunea SUD-MUNTENIA', {}).get(crop, {0: 0}).values())}")


if __name__ == "__main__":
    main()
