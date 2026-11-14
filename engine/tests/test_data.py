from datetime import datetime, timedelta

import httpx

from fieldshift.contracts import validate
from fieldshift.data import _cache, fetch_field_data


def _response(url, params, payload):
    request = httpx.Request("GET", url, params=params)
    return httpx.Response(200, json=payload, request=request)


def test_fetch_field_data_normalizes_power_and_soilgrids(monkeypatch):
    _cache.clear()
    dates = [
        (datetime(2024, 1, 1) + timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(2)
    ]
    observations = {
        "PRECTOTCORR": {dates[0]: 0.02, dates[1]: 1.45},
        "T2M": {dates[0]: 6.92, dates[1]: 4.61},
        "T2M_MAX": {dates[0]: 12.75, dates[1]: 7.57},
        "T2M_MIN": {dates[0]: 4.23, dates[1]: 1.25},
        "T2MDEW": {dates[0]: 5.37, dates[1]: 3.88},
        "WS2M": {dates[0]: 2.78, dates[1]: 2.47},
        "ALLSKY_SFC_SW_DWN": {dates[0]: 5.28, dates[1]: 3.51},
    }
    soil_layers = []
    for name, value, factor in (("phh2o", 75, 10), ("soc", 180, 10)):
        soil_layers.append(
            {
                "name": name,
                "unit_measure": {"d_factor": factor},
                "depths": [
                    {"label": "0-5cm", "values": {"mean": value}}
                ],
            }
        )
    calls = []

    def fake_get(url, params, timeout):
        calls.append(url)
        if "power.larc" in url:
            payload = {
                "geometry": {"coordinates": [27.333, 44.202, 38]},
                "header": {"fill_value": -999},
                "properties": {"parameter": observations},
            }
        else:
            payload = {"properties": {"layers": soil_layers}}
        return _response(url, params, payload)

    monkeypatch.setattr("fieldshift.data.httpx.get", fake_get)

    result = fetch_field_data(44.202, 27.333, 2024, 2024)

    assert validate("field-data", result) == []
    assert result["years"][0]["precip_mm"] == 1.47
    assert result["years"][0]["monthly"]["precip_mm"][0] == 1.47
    assert result["years"][0]["monthly"]["tmean_c"][0] == 5.77
    assert result["years"][0]["et0_mm"] > 0
    assert result["static"]["elevation_m"] == 38
    assert result["static"]["soil"]["ph"] == 7.5
    assert result["static"]["soil"]["organic_carbon_pct"] == 1.8
    assert [source["id"] for source in result["sources"]] == [
        "nasa_power",
        "soilgrids",
    ]
    assert len(calls) == 2


def test_fetch_field_data_caches_provider_responses(monkeypatch):
    _cache.clear()
    observations = {
        name: {"20240101": value}
        for name, value in {
            "PRECTOTCORR": 1,
            "T2M": 10,
            "T2M_MAX": 12,
            "T2M_MIN": 8,
            "T2MDEW": 7,
            "WS2M": 2,
            "ALLSKY_SFC_SW_DWN": 4,
        }.items()
    }
    calls = []

    def fake_get(url, params, timeout):
        calls.append(url)
        if "power.larc" in url:
            payload = {
                "geometry": {"coordinates": [27.33, 44.2, 38]},
                "header": {"fill_value": -999},
                "properties": {"parameter": observations},
            }
        else:
            payload = {
                "properties": {
                    "layers": [
                        {
                            "name": name,
                            "unit_measure": {"d_factor": 10},
                            "depths": [
                                {"label": "0-5cm", "values": {"mean": None}}
                            ],
                        }
                        for name in ("phh2o", "soc")
                    ]
                }
            }
        return _response(url, params, payload)

    monkeypatch.setattr("fieldshift.data.httpx.get", fake_get)
    first = fetch_field_data(44.2, 27.33, 2024, 2024)
    second = fetch_field_data(44.2, 27.33, 2024, 2024)

    assert len(calls) == 2
    assert first["sources"][0]["from_cache"] is False
    assert second["sources"][0]["from_cache"] is True
    assert second["sources"][0]["retrieved_at"] == first["sources"][0]["retrieved_at"]


def test_fetch_field_data_surfaces_optional_soil_unavailability(monkeypatch):
    _cache.clear()

    def fake_get(url, params, timeout):
        if "power.larc" in url:
            payload = {
                "geometry": {"coordinates": [27.33, 44.2, 38]},
                "header": {"fill_value": -999},
                "properties": {
                    "parameter": {
                        name: {"20240101": 1}
                        for name in (
                            "PRECTOTCORR",
                            "T2M",
                            "T2M_MAX",
                            "T2M_MIN",
                            "T2MDEW",
                            "WS2M",
                            "ALLSKY_SFC_SW_DWN",
                        )
                    }
                },
            }
            return _response(url, params, payload)
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(503, request=request)

    monkeypatch.setattr("fieldshift.data.httpx.get", fake_get)

    result = fetch_field_data(44.2, 27.33, 2024, 2024)

    assert validate("field-data", result) == []
    assert "static.soil" in result["quality"]["missing"]
    assert any("SoilGrids unavailable" in note for note in result["quality"]["notes"])
    assert [source["id"] for source in result["sources"]] == ["nasa_power"]
