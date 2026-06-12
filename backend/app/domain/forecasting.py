"""Short-horizon demand forecasting from a per-zone history of daily counts."""

from __future__ import annotations

from collections.abc import Sequence


def moving_average(history: Sequence[float], window: int = 7) -> float:
    if not history:
        return 0.0
    window = min(window, len(history))
    return sum(history[-window:]) / window


def exponential_smoothing(history: Sequence[float], alpha: float = 0.4) -> float:
    """Level estimate giving more weight to recent observations."""
    if not history:
        return 0.0
    level = history[0]
    for value in history[1:]:
        level = alpha * value + (1 - alpha) * level
    return level


def seasonal_indices(history: Sequence[float], period: int = 7) -> list[float]:
    """Average demand for each phase of the cycle, normalised to mean 1.0.

    A returned value of 1.3 means that phase runs 30% above the typical day.
    """
    if len(history) < period:
        return [1.0] * period
    buckets: list[list[float]] = [[] for _ in range(period)]
    for i, value in enumerate(history):
        buckets[i % period].append(value)
    overall = sum(history) / len(history)
    if overall == 0:
        return [1.0] * period
    return [(sum(b) / len(b) / overall) if b else 1.0 for b in buckets]


def forecast(
    history: Sequence[float], horizon_phase: int, period: int = 7, alpha: float = 0.4
) -> float:
    """Forecast the next day by scaling the smoothed level by its seasonal index.

    ``horizon_phase`` is the cycle position of the day being predicted, i.e.
    ``len(history) % period`` for the very next day.
    """
    level = exponential_smoothing(history, alpha)
    index = seasonal_indices(history, period)[horizon_phase % period]
    return max(0.0, level * index)
