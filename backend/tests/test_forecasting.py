from __future__ import annotations

import pytest

from app.domain.forecasting import (
    exponential_smoothing,
    forecast,
    moving_average,
    seasonal_indices,
)


def test_moving_average_uses_last_window() -> None:
    assert moving_average([1, 2, 3, 4, 5], window=2) == pytest.approx(4.5)


def test_empty_history_is_zero() -> None:
    assert moving_average([]) == 0.0
    assert exponential_smoothing([]) == 0.0
    assert forecast([], 0) == 0.0


def test_exponential_smoothing_tracks_recent_values() -> None:
    flat = exponential_smoothing([10, 10, 10, 10])
    assert flat == pytest.approx(10.0)
    rising = exponential_smoothing([0, 0, 0, 100])
    assert 0 < rising < 100


def test_seasonal_indices_average_to_one() -> None:
    history = [10, 20, 10, 20, 10, 20]
    idx = seasonal_indices(history, period=2)
    assert sum(idx) / len(idx) == pytest.approx(1.0)
    assert idx[1] > idx[0]  # the "high" phase has a larger index


def test_forecast_is_non_negative() -> None:
    history = [5, 8, 6, 9, 7, 10, 8] * 4
    assert forecast(history, horizon_phase=len(history) % 7) >= 0
