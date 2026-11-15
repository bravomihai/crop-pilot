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

# Rule crop id -> (INS yield item in AGR110A, INS price item in PPA102C or None).
CROPS = {
    "winter_wheat": ("Grau comun", "Grau"),
    "winter_barley": ("Orz", "Orz"),
    "winter_rapeseed": ("Rapita", "Rapita"),
    "maize": ("Porumb boabe", "Porumb boabe"),
    "sunflower": ("Floarea soarelui", "Floarea soarelui"),
    "soybean": ("Soia boabe", "Soia"),
    # INS stopped publishing dry pea purchase prices in 2007 (table PPA102B).
    "pea": ("Mazare boabe", None),
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
}

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
    rows = tempo("AGR110A", [[crop_ids[name] for name, _ in CROPS.values()], [5789], counties,
                             [o["nomItemId"] for o in years], [options(meta, 4)[0]["nomItemId"]]], 5)
    by_name = {name: crop for crop, (name, _) in CROPS.items()}
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
    retrieved = date.today().isoformat()
    data = {
        "campaign": CAMPAIGN,
        "currency": "RON",
        "retrieved": retrieved,
        "crops": {crop: {"ins_yield_item": y, "ins_price_item": p} for crop, (y, p) in CROPS.items()},
        "county_region": county_region,
        "yields_t_per_ha": yields,
        "prices_lei_per_t": prices,
        "costs_lei_per_ha": ICEADR_COSTS,
        "cost_level_years": "2022-2023",
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
            {"id": "apia-coupled-2025", "title": "Coupled support rates for soybean, 2025 claim year (as reported; check the Order)",
             "url": "https://www.bzi.ro/s-a-stabilit-cuantumul-pe-hectar-pentru-sprijinul-cuplat-vegetal-fermierii-asteapta-banii-de-anul-trecut-5517994"},
            {"id": "apia-ecoscheme-2026", "title": "APIA: 2026 payment application instructions, eco-scheme PD-04 (Annex 2)",
             "url": "https://apia.org.ro/wp-content/uploads/2026/03/Anexa-2.pdf"},
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
    print(f"{len(yields)} counties with yields, {len(prices)} price regions, EUR/RON {rate} on {rate_day}")
    for crop in CROPS:
        known = sum(1 for c in yields.values() if crop in c)
        print(f"  {crop:16} yields in {known} counties, median price SUD-MUNTENIA "
              f"{statistics.median(prices.get('Regiunea SUD-MUNTENIA', {}).get(crop, {0: 0}).values())}")


if __name__ == "__main__":
    main()
