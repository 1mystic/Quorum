"""
Turning a periodised stream unit into the numbers a chart plots.

Shared by `spc.py` and `changepoint.py`, which both take "any *Period[]" and
both have to answer the same three questions: which field is the measurement,
which periods are complete, and what timestamp does each point carry.

Rule S5 of the spine is enforced here rather than in each service: a period
whose `complete` flag is False is excluded and the exclusion is reported, never
plotted. A forecaster or a control chart fitted through a partial final bucket
reads the reporting lag as a collapse in the process.
"""
import math
from dataclasses import dataclass
from typing import Any, Sequence

# The measurement each period type carries, in the order they are looked for.
# FlowPeriod is first because Pack 1 is a request_flow pack.
VALUE_FIELDS: tuple[str, ...] = (
    "arrivals",          # FlowPeriod
    "net_minor",         # LedgerPeriod
    "active_members",    # ParticipationPeriod
)


@dataclass(frozen=True)
class PeriodSeries:
    values: tuple[float, ...]
    labels: tuple[str, ...]        # ISO period_start, or the index when there is none
    exposure: tuple[float, ...]
    field: str
    n_incomplete: int
    n_after_complete_through: int

    def __len__(self) -> int:
        return len(self.values)


def _iso(value: Any) -> str:
    isoformat = getattr(value, "isoformat", None)
    if isoformat is None:
        return str(value)
    return isoformat().replace("+00:00", "Z")


def period_series(
    series: Sequence[Any],
    window: Any = None,
    *,
    value_field: str | None = None,
    exposure_field: str = "exposure_days",
) -> PeriodSeries:
    """
    Accepts a sequence of period dataclasses or a plain sequence of numbers.

    A plain sequence is allowed because several known-answer tests are published
    as bare series (the Nile flows, Montgomery's chart examples) and forcing them
    through a dataclass would test the wrapper rather than the mathematics.
    """
    if not series:
        return PeriodSeries((), (), (), value_field or "value", 0, 0)

    first = series[0]
    if isinstance(first, (int, float)):
        values = tuple(float(v) for v in series)
        return PeriodSeries(
            values=values,
            labels=tuple(str(i) for i in range(len(values))),
            exposure=tuple(1.0 for _ in values),
            field=value_field or "value",
            n_incomplete=0,
            n_after_complete_through=0,
        )

    field = value_field
    if field is None:
        for candidate in VALUE_FIELDS:
            if hasattr(first, candidate):
                field = candidate
                break
    if field is None or not hasattr(first, field):
        raise ValueError(
            "cannot find the measurement on " + type(first).__name__ + "; pass value_field "
            "explicitly. Guessing a column is how a chart ends up plotting the wrong quantity."
        )

    complete_through = getattr(window, "complete_through", None) if window is not None else None
    values: list[float] = []
    labels: list[str] = []
    exposure: list[float] = []
    incomplete = 0
    past_lag = 0
    for period in series:
        if not getattr(period, "complete", True):
            incomplete += 1
            continue
        end = getattr(period, "period_end", None)
        if complete_through is not None and end is not None and end > complete_through:
            past_lag += 1
            continue
        values.append(float(getattr(period, field)))
        labels.append(_iso(getattr(period, "period_start", len(labels))))
        raw_exposure = getattr(period, exposure_field, None)
        exposure.append(float(raw_exposure) if raw_exposure else 1.0)
    return PeriodSeries(
        values=tuple(values),
        labels=tuple(labels),
        exposure=tuple(exposure),
        field=field,
        n_incomplete=incomplete,
        n_after_complete_through=past_lag,
    )


def moving_range_sigma(values: Sequence[float]) -> float:
    """
    The individuals-chart estimate of sigma: mean moving range over d2 = 1.128.

    Preferred to the sample standard deviation because it uses only successive
    differences, so a sustained shift inside the baseline inflates it far less
    than it inflates the sample deviation. A baseline containing the shift you
    are hunting for is the classic way to blind a control chart, and this choice
    is the first of two defences against it; the baseline-stability check is the
    second.
    """
    if len(values) < 2:
        raise ValueError("the moving-range estimate needs at least two periods")
    ranges = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return math.fsum(ranges) / len(ranges) / 1.128


def robust_sigma(values: Sequence[float]) -> float:
    """
    A median-based sigma from successive differences, for changepoint detection
    where a level shift would otherwise be absorbed into the noise estimate.
    """
    if len(values) < 2:
        raise ValueError("the robust sigma estimate needs at least two periods")
    diffs = sorted(abs(values[i] - values[i - 1]) for i in range(1, len(values)))
    mid = len(diffs) // 2
    median = diffs[mid] if len(diffs) % 2 else 0.5 * (diffs[mid - 1] + diffs[mid])
    return median / (0.6745 * math.sqrt(2.0))


def lag_autocorrelation(values: Sequence[float], lag: int = 1) -> float:
    n = len(values)
    if n <= lag + 2:
        return 0.0
    m = math.fsum(values) / n
    denominator = math.fsum((v - m) ** 2 for v in values)
    if denominator <= 0.0:
        return 0.0
    numerator = math.fsum((values[i] - m) * (values[i - lag] - m) for i in range(lag, n))
    return numerator / denominator


def ljung_box(values: Sequence[float], max_lag: int = 10) -> tuple[float, int]:
    """Ljung-Box portmanteau statistic and its degrees of freedom."""
    n = len(values)
    lags = max(1, min(max_lag, n // 5))
    stat = 0.0
    for lag in range(1, lags + 1):
        rho = lag_autocorrelation(values, lag)
        stat += rho * rho / (n - lag)
    return n * (n + 2) * stat, lags


__all__ = [
    "PeriodSeries",
    "lag_autocorrelation",
    "ljung_box",
    "moving_range_sigma",
    "period_series",
    "robust_sigma",
]
