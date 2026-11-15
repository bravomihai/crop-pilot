"""Offline tests for NASA POWER cleaning and soil-data integration."""

from datetime import date, timedelta

import httpx
import pytest

from fieldshift import data_service
from fieldshift.data_service import climate, daily, land_cover, power, soil, terrain
from fieldshift.evaluator import evaluate, load_rules


@pytest.mark.parametrize(
    ("classes", "expected"),
    [
        ([10], "incompatible"),
        ([80], "incompatible"),
        ([50], "incompatible"),
        ([40], "cropland"),
        ([10, 40], "uncertain"),
        ([30], "uncertain"),
    ],
)
def test_satellite_screening_classifies_field(monkeypatch, classes, expected):
    boundary = {
        "type": "Polygon",
        "coordinates": [[[26.491, 44.441], [26.494, 44.441], [26.494, 44.444],
                         [26.491, 44.444], [26.491, 44.441]]],
    }

    def post(url, params, json, timeout):
        assert json["geometry"] == boundary
        assert params["item"] == "ESA_WorldCover_10m_2021_v200_N42E024"
        stats = {"histogram": [[10] * len(classes), classes], "count": 10 * len(classes)}
        return httpx.Response(
            200,
            json={"properties": {"statistics": {"map_b1": stats}}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(land_cover.httpx, "post", post)
    assessment, sources = land_cover.assess_land_cover(boundary)
    assert assessment["status"] == expected
    assert "2021" in assessment["message"]
    assert sources[0]["id"] == "esa-worldcover-2021"


def test_satellite_screening_does_not_hide_unavailable_or_incomplete_data(monkeypatch):
    boundary = {
        "type": "Polygon",
        "coordinates": [[[26.491, 44.441], [26.494, 44.441], [26.494, 44.444],
                         [26.491, 44.444], [26.491, 44.441]]],
    }

    def fail(url, **kwargs):
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(land_cover.httpx, "post", fail)
    assessment, sources = land_cover.assess_land_cover(boundary)
    assert assessment["status"] == "uncertain"
    assert "service failed" in assessment["message"]
    assert sources == []

    def incomplete(url, **kwargs):
        return httpx.Response(200, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(land_cover.httpx, "post", incomplete)
    assert land_cover.assess_land_cover(boundary)[0]["status"] == "uncertain"
    assert land_cover.assess_land_cover(None)[0]["status"] == "uncertain"

    def unknown_class(url, **kwargs):
        return httpx.Response(
            200,
            json={"properties": {"statistics": {"map_b1": {
                "histogram": [[10], [999]], "count": 10,
            }}}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(land_cover.httpx, "post", unknown_class)
    assert land_cover.assess_land_cover(boundary)[0]["status"] == "uncertain"


def test_satellite_screening_flags_tile_boundary_and_too_few_pixels(monkeypatch):
    boundary = {
        "type": "Polygon",
        "coordinates": [[[26.999, 44.441], [27.001, 44.441], [27.001, 44.444],
                         [26.999, 44.444], [26.999, 44.441]]],
    }
    assert "tile boundary" in land_cover.assess_land_cover(boundary)[0]["message"]
    large = {
        "type": "Polygon",
        "coordinates": [[[26.1, 44.1], [26.2, 44.1], [26.2, 44.2],
                         [26.1, 44.2], [26.1, 44.1]]],
    }
    assert "too large" in land_cover.assess_land_cover(large)[0]["message"]
    boundary["coordinates"][0] = [
        [26.491, 44.441], [26.494, 44.441], [26.494, 44.444],
        [26.491, 44.444], [26.491, 44.441],
    ]
    monkeypatch.setattr(
        land_cover.httpx,
        "post",
        lambda url, **kwargs: httpx.Response(
            200,
            json={"properties": {"statistics": {"map_b1": {
                "histogram": [[1], [10]], "count": 1,
            }}}},
            request=httpx.Request("POST", url),
        ),
    )
    assert land_cover.assess_land_cover(boundary)[0]["status"] == "uncertain"


def test_fao56_et0_uses_dewpoint_and_matches_example_18():
    raw = [
        {
            "date": "2020-07-06",
            "values": {
                "T2M_MIN": 12.3,
                "T2M_MAX": 21.5,
                "T2M": 16.9,
                "T2MDEW": 12.05,
                "PRECTOTCORR": 0.0,
                "RH2M": 60,
                "WS2M": 2.078,
                "ALLSKY_SFC_SW_DWN": 22.07,
            },
        }
    ]

    cleaned, quality = daily.clean_daily(raw, 50.8, 100)

    assert cleaned[0]["et0"] == pytest.approx(3.9, abs=0.15)
    assert cleaned[0]["et0_method"] == "penman_monteith"
    assert quality["et0_methods"]["penman_monteith"] == 1


def test_clean_daily_keeps_missing_values_and_uses_hargreaves_fallback():
    raw = [
        {
            "date": "2020-07-01",
            "values": {
                "T2M_MIN": 18,
                "T2M_MAX": 31,
                "T2M": None,
                "PRECTOTCORR": None,
                "RH2M": None,
                "WS2M": None,
                "ALLSKY_SFC_SW_DWN": None,
                "T2MDEW": None,
            },
        }
    ]

    cleaned, quality = daily.clean_daily(raw, 44.5, None)

    assert cleaned[0]["tmean"] == 24.5
    assert cleaned[0]["precip"] is None
    assert cleaned[0]["et0"] > 0
    assert cleaned[0]["et0_method"] == "hargreaves"
    assert quality["missing"]["precip"] == 1


def test_fetch_power_requests_dewpoint_and_uses_a_new_cache_version(monkeypatch):
    end_year = date.today().year - 1
    day = f"{end_year}0101"
    response_data = {
        "header": {"fill_value": -999},
        "geometry": {"coordinates": [44.5, 26.5, -999]},
        "properties": {
            "parameter": {
                name: {day: 10.0}
                for name in power.PARAMETERS
            }
        },
    }
    cache_key = {}

    monkeypatch.setattr(power.cache, "read", lambda key: None)
    monkeypatch.setattr(power.cache, "write", lambda key, value: None)
    monkeypatch.setattr(
        power.cache,
        "key_for",
        lambda value: cache_key.update(value) or "test-key",
    )
    monkeypatch.setattr(
        power.httpx,
        "get",
        lambda url, params, timeout: httpx.Response(
            200, json=response_data, request=httpx.Request("GET", url)
        ),
    )

    result = power.fetch_power(44.5, 26.5, end_year, end_year)

    assert "T2MDEW" in power.PARAMETERS
    assert result["daily"][0]["values"]["T2MDEW"] == 10.0
    assert result["elevation_m"] is None
    assert cache_key["provider"] == "power-daily-v2"


def _soilgrids_payload():
    def layer(name, values, factor):
        labels = ("0-5cm", "5-15cm", "15-30cm")
        return {
            "name": name,
            "unit_measure": {"d_factor": factor},
            "depths": [
                {"label": label, "values": {"mean": value}}
                for label, value in zip(labels, values)
            ],
        }

    return {
        "properties": {
            "layers": [
                layer("clay", [440, 450, 460], 10),
                layer("sand", [90, 80, 80], 10),
                layer("silt", [470, 470, 460], 10),
                layer("phh2o", [66, 66, 67], 10),
                layer("soc", [250, 200, 170], 10),
            ]
        }
    }


def _mock_soil_request(monkeypatch, payload):
    monkeypatch.setattr(soil.cache, "read", lambda key: None)
    monkeypatch.setattr(soil.cache, "write", lambda key, value: None)
    monkeypatch.setattr(
        soil.httpx,
        "get",
        lambda url, params, timeout: httpx.Response(
            200, json=payload, request=httpx.Request("GET", url)
        ),
    )


def test_fetch_soil_depth_weights_units_and_available_water(monkeypatch):
    _mock_soil_request(monkeypatch, _soilgrids_payload())

    values, sources, gaps = soil.fetch_soil(44.45, 26.5)

    assert values["clay_pct"] == pytest.approx(45.33, abs=0.01)
    assert values["ph"] == pytest.approx(6.65, abs=0.01)
    assert values["organic_carbon_pct"] == pytest.approx(1.93, abs=0.01)
    assert values["texture"] == "clay"
    assert 0.1 < values["awc_m3_m3"] < 0.2
    assert [source["id"] for source in sources] == [
        "soilgrids",
        "saxton-rawls-2006",
    ]
    assert gaps == []


def test_null_soilgrids_values_are_reported_as_data_gaps(monkeypatch):
    payload = _soilgrids_payload()
    for layer in payload["properties"]["layers"]:
        for depth in layer["depths"]:
            depth["values"]["mean"] = None
    _mock_soil_request(monkeypatch, payload)

    values, sources, gaps = soil.fetch_soil(44.56, 27.36)

    assert values is None
    assert sources == []
    assert any("no complete texture profile" in gap for gap in gaps)


def test_soilgrids_outage_is_a_data_gap(monkeypatch):
    monkeypatch.setattr(soil.cache, "read", lambda key: None)
    monkeypatch.setattr(
        soil.httpx,
        "get",
        lambda url, params, timeout: (_ for _ in ()).throw(
            httpx.ConnectError("unavailable")
        ),
    )

    values, sources, gaps = soil.fetch_soil(44.45, 26.5)

    assert values is None
    assert sources == []
    assert "unavailable" in gaps[0]


def test_slope_percent_uses_a_3_by_3_surface_and_accounts_for_latitude():
    flat = [[42.0, 42.0, 42.0] for _ in range(3)]
    east_rising = [[0.0, 3.0, 6.0] for _ in range(3)]

    assert terrain.slope_percent(flat, 45.0) == 0
    assert terrain.slope_percent(east_rising, 45.0) == pytest.approx(13.73, abs=0.1)
    assert terrain.slope_percent([[1.0, 2.0]], 45.0) is None


def test_fetch_slope_queries_and_caches_a_srtm30m_neighborhood(monkeypatch):
    results = [
        {"dataset": "srtm30m", "elevation": value}
        for value in (0, 3, 6, 0, 3, 6, 0, 3, 6)
    ]
    cache_key = {}
    writes = []
    monkeypatch.setattr(terrain.cache, "read", lambda key: None)
    monkeypatch.setattr(
        terrain.cache,
        "write",
        lambda key, value: writes.append((key, value)),
    )
    monkeypatch.setattr(
        terrain.cache,
        "key_for",
        lambda value: cache_key.update(value) or "terrain-key",
    )
    requests = []

    def mock_get(url, params, timeout):
        requests.append((url, params, timeout))
        return httpx.Response(
            200,
            json={"status": "OK", "results": results},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(terrain.httpx, "get", mock_get)

    slope, sources, gaps = terrain.fetch_slope(45.0, 25.0)

    assert slope == pytest.approx(13.73, abs=0.1)
    assert sources[0]["id"] == "srtm30m-opentopodata"
    assert gaps == []
    assert requests[0][0] == terrain.URL
    assert requests[0][1]["locations"].count("|") == 8
    assert requests[0][1]["interpolation"] == "bilinear"
    assert requests[0][2] == 30
    assert cache_key["provider"] == "srtm30m-opentopodata-v1"
    assert len(writes) == 1


def test_fetch_slopes_batches_field_samples_and_caches_each_neighborhood(monkeypatch):
    rising = [
        {"dataset": "srtm30m", "elevation": value}
        for value in (0, 3, 6, 0, 3, 6, 0, 3, 6)
    ]
    flat = [{"dataset": "srtm30m", "elevation": 100} for _ in range(9)]
    requests = []
    writes = []
    monkeypatch.setattr(terrain.cache, "read", lambda key: None)
    monkeypatch.setattr(terrain.cache, "write", lambda key, value: writes.append(value))
    monkeypatch.setattr(terrain.cache, "key_for", lambda value: str(value["lat"]))

    def mock_get(url, params, timeout):
        requests.append(params)
        return httpx.Response(
            200,
            json={"status": "OK", "results": rising + flat},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(terrain.httpx, "get", mock_get)

    slopes, sources, gaps = terrain.fetch_slopes([(45.0, 25.0), (45.1, 25.1)])

    assert slopes == [pytest.approx(13.73, abs=0.1), 0]
    assert sources[0]["id"] == "srtm30m-opentopodata"
    assert gaps == []
    assert requests[0]["locations"].count("|") == 17
    assert len(writes) == 2


def test_fetch_slope_reports_missing_samples_and_provider_errors(monkeypatch):
    monkeypatch.setattr(terrain.cache, "read", lambda key: None)
    monkeypatch.setattr(terrain.cache, "write", lambda key, value: None)
    monkeypatch.setattr(
        terrain.httpx,
        "get",
        lambda url, params, timeout: httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {"dataset": "srtm30m", "elevation": None}
                    for _ in range(9)
                ],
            },
            request=httpx.Request("GET", url),
        ),
    )

    slope, sources, gaps = terrain.fetch_slope(45.0, 25.0)
    assert slope is None
    assert sources == []
    assert "missing elevation samples" in gaps[0]

    monkeypatch.setattr(
        terrain.httpx,
        "get",
        lambda url, params, timeout: (_ for _ in ()).throw(
            httpx.ConnectError("unavailable")
        ),
    )
    slope, sources, gaps = terrain.fetch_slope(45.0, 25.0)
    assert slope is None
    assert sources == []
    assert "ConnectError" in gaps[0]


def _year(year: int, hot_days: int = 0) -> list[dict]:
    days = []
    current = date(year, 1, 1)
    while current.year == year:
        summer = current.month in (6, 7, 8)
        is_hot = summer and hot_days > 0
        days.append(
            {
                "date": current.isoformat(),
                "tmin": -5.0 if current.month in (1, 2) else 10.0,
                "tmax": 34.0 if is_hot else 25.0,
                "tmean": 15.0,
                "precip": 2.0 if current.day == 1 else 0.0,
                "et0": 3.0,
            }
        )
        if is_hot:
            hot_days -= 1
        current += timedelta(days=1)
    return days


def test_climate_context_summarizes_complete_years_and_trends():
    daily_rows = [
        day
        for year in range(2010, 2022)
        for day in _year(year, hot_days=(year - 2010) * 3)
    ]

    result = climate.climate_context(daily_rows, ["nasa-power"])

    assert result["basis"] == "observed"
    assert result["period"] == {"start_year": 2010, "end_year": 2021}
    assert [row["hot_days_gt32"] for row in result["years"][:3]] == [0, 3, 6]
    assert result["trends"]["hot_days_gt32"]["per_decade"] == pytest.approx(
        30, abs=0.01
    )
    assert result["years"][0]["last_spring_frost_doy"] == 59


def test_climate_context_does_not_fill_missing_annual_rainfall():
    daily_rows = _year(2020)
    daily_rows[10]["precip"] = None

    result = climate.climate_context(daily_rows, ["nasa-power"])

    assert result["years"][0]["rain_mm"] is None
    assert result["years"][0]["dry_spell_max_days_apr_sep"] is None


def test_build_environment_normalizes_data_and_preserves_monthly_summary(monkeypatch):
    end_year = date.today().year - 1
    first_year = end_year - 10
    raw_daily = []
    for year in range(first_year, end_year + 1):
        for day in _year(year):
            raw_daily.append(
                {
                    "date": day["date"],
                    "values": {
                        "T2M_MIN": day["tmin"],
                        "T2M_MAX": day["tmax"],
                        "T2M": day["tmean"],
                        "PRECTOTCORR": day["precip"],
                        "RH2M": 60,
                        "WS2M": 2,
                        "ALLSKY_SFC_SW_DWN": 18,
                        "T2MDEW": 6,
                    },
                }
            )
    monkeypatch.setenv("ENABLE_NASA_POWER", "true")
    monkeypatch.setenv("HISTORY_YEARS", "11")
    monkeypatch.setattr(
        data_service,
        "fetch_power",
        lambda lat, lon, start, end: {
            "period": {"start_year": start, "end_year": end},
            "daily": raw_daily,
            "elevation_m": 70,
            "sources": [
                {
                    "id": "nasa-power",
                    "title": "NASA POWER Daily API",
                    "url": "https://power.larc.nasa.gov/",
                }
            ],
            "data_gaps": [],
        },
    )
    soil_calls = []

    def fake_soil(lat, lon):
        index = len(soil_calls)
        soil_calls.append((lat, lon))
        return (
            {
                "clay_pct": 30 + index * 2,
                "sand_pct": 40 - index * 2,
                "silt_pct": 30,
                "ph": 7.0 + index * 0.1,
                "organic_carbon_pct": 1.0,
                "texture": "loamy",
                "awc_m3_m3": 0.15,
                "source": "soilgrids",
            },
            [{"id": "soilgrids", "title": "ISRIC SoilGrids"}],
            [],
        )

    monkeypatch.setattr(data_service.soil_service, "fetch_soil", fake_soil)
    slope_calls = []

    def fake_slopes(points):
        slope_calls.append(points)
        return (
            [2.0, 3.0, 4.0],
            [{"id": "srtm30m-opentopodata", "title": "SRTM"}],
            [],
        )

    monkeypatch.setattr(data_service, "fetch_slopes", fake_slopes)

    request = {
        "location": {"latitude": 44.45, "longitude": 26.5},
        "field_boundary": {
            "type": "Polygon",
            "coordinates": [
                [
                    [26.4, 44.4],
                    [26.5, 44.4],
                    [26.5, 44.5],
                    [26.4, 44.5],
                    [26.4, 44.4],
                ]
            ],
        },
        "available_from": f"{end_year + 1}-10-01",
        "history": [],
        "constraints": {"irrigated": False, "excluded_crops": []},
        "scenario": {"temp_change_c": 0, "rain_change_pct": 0},
    }
    environment = data_service.build_environment(request)

    assert environment["quality"]["days"] == len(raw_daily)
    assert environment["quality"]["et0_methods"]["penman_monteith"] == len(raw_daily)
    assert len(environment["monthly_climate"]) == 11 * 12
    assert environment["daily"][0]["tmin"] == -5.0
    assert environment["static"]["elevation_m"] == 70
    assert len(soil_calls) == 3
    assert len(slope_calls[0]) == 3
    assert environment["static"]["soil"]["clay_pct"] == 32
    assert environment["static"]["soil"]["ph"] == 7.1
    assert environment["static"]["slope_pct"] == 3.0
    assert any("sparse" in item.lower() for item in environment["assumptions"])
    assert environment["climate_context"]["period"] == {
        "start_year": first_year,
        "end_year": end_year,
    }
    assert all(source.get("title") for source in environment["sources"])

    rules = load_rules(request["location"])
    result = evaluate(["pea", "winter_wheat", "maize"], request, environment, rules)
    assert result["criteria"]["water"]["score"] is not None
    assert result["soil_inputs"]["texture_from"] == "regional"
    assert result["soil_inputs"]["awc"] == environment["static"]["soil"]["awc_m3_m3"]


def test_local_cache_serves_repeat_requests_without_network(tmp_path, monkeypatch):
    from fieldshift.data_service import cache

    monkeypatch.setenv("CROPPILOT_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("CACHE_BACKEND_URL", raising=False)
    key = cache.key_for({"provider": "test", "lat": 1})
    assert cache.read(key) is None
    cache.write(key, {"value": 42})
    assert cache.read(key) == {"value": 42}
    monkeypatch.delenv("CROPPILOT_CACHE_DIR")
    assert cache.read(key) is None  # no directory configured: cache is off


def test_soilgrids_uses_a_short_timeout(monkeypatch):
    from fieldshift.data_service import soil as soil_service

    seen = []

    def slow(url, params, timeout):
        seen.append(timeout)
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(soil_service.httpx, "get", slow)
    monkeypatch.delenv("CROPPILOT_CACHE_DIR", raising=False)
    values, _, gaps = soil_service.fetch_soil(44.45, 26.5)
    assert values is None and seen and seen[0] <= 10
    assert "unavailable" in gaps[0]
