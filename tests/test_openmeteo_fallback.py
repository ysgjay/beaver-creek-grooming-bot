"""Our own Open-Meteo answers multi-point calls with a JSON list; that is real data, not a miss."""
from bcbot.sources import openmeteo


class _R:
    def __init__(self, j):
        self._j = j

    def json(self):
        return self._j


def test_multi_point_list_counts_as_data():
    pt = {"hourly": {"time": ["t"], "snowfall": [0.0]}}
    assert openmeteo._has_data(_R([pt, pt]))
    assert openmeteo._has_data(_R(pt))


def test_empty_or_null_points_fall_back():
    assert not openmeteo._has_data(_R([]))
    assert not openmeteo._has_data(_R([{"hourly": {"time": ["t"], "snowfall": [None]}}]))
    assert not openmeteo._has_data(_R({"hourly": {"time": ["t"], "snowfall": [None]}}))
