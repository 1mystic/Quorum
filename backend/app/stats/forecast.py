"""
Forecasting over any periodised series.

The MASE gate governs this module: no forecaster is served to a tenant unless it beat
seasonal-naive under rolling-origin cross-validation on that tenant's own history. A
forecast that cannot beat naive is decoration, and decoration that looks like a
forecast is worse than nothing. A blocking MASE failure returns the seasonal-naive
forecast rather than an error, so the tenant still gets a number and it is the honest one.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def seasonal_naive(series, window, *, season_length, horizon) -> Evidence:
    """forecast.seasonal_naive. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "forecast.seasonal_naive is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def stl_decompose(series, window, *, season_length, robust=True, seasonal_smoother=7) -> Evidence:
    """forecast.stl_decompose. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "forecast.stl_decompose is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def holt_winters(series, window, *, season_length, horizon, trend="add", seasonal="add", damped=True, seed=0) -> Evidence:
    """forecast.holt_winters. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "forecast.holt_winters is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def sarima(series, window, *, season_length, horizon, order=None, seasonal_order=None, auto=True, ic="aicc") -> Evidence:
    """forecast.sarima. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "forecast.sarima is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def rolling_origin_backtest(series, window, *, forecaster, season_length, horizon, initial_train, step=1, min_folds=5) -> Evidence:
    """forecast.rolling_origin_backtest. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "forecast.rolling_origin_backtest is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def dues_collection(series, window, *, season_length=12, horizon=3) -> Evidence:
    """forecast.dues_collection. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "forecast.dues_collection is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def request_volume(series, window, *, season_length=12, horizon=3) -> Evidence:
    """forecast.request_volume. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "forecast.request_volume is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def attendance(series, window, roster, *, season_length=12, horizon=3) -> Evidence:
    """forecast.attendance. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "forecast.attendance is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "seasonal_naive",
    "stl_decompose",
    "holt_winters",
    "sarima",
    "rolling_origin_backtest",
    "dues_collection",
    "request_volume",
    "attendance",
]
