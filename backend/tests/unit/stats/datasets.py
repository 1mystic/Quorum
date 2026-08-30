"""
The published datasets the known-answer tests are checked against.

Vendored as CSV under `data/` so the whole suite runs offline, which is the
point of the purity rule. Each loader says where the file came from and which
published figures it is used to reproduce.

- `lung.csv`   NCCTG lung cancer, R `survival::lung` (the `cancer` object).
               228 rows. Published: median survival 310 days, 95% CI 285 to 363;
               survdiff by sex chi-square 10.3 on 1 df, p = 0.001.
- `rossi.csv`  Rossi et al. recidivism, the standard lifelines and
               Klein-Moeschberger Cox fixture. 432 rows, 114 arrests. Published
               coefficients: fin -0.379, age -0.057, race 0.314, wexp -0.150,
               mar -0.434, paro -0.085, prio 0.091.
- `heart.csv`  Stanford heart transplant, R `survival::heart`, the canonical
               left-truncation (start, stop, event) example.
- `nile.csv`   Annual Nile flow at Aswan 1871-1970, the canonical changepoint
               benchmark: one level shift at 1898.
- `mgus2.csv`  R `survival::mgus2`, the competing-risks vignette dataset.
"""
from __future__ import annotations

import csv
import pathlib
from datetime import datetime, timedelta, timezone

from app.stats.streams.request import RequestSpell
from app.stats.streams.window import StreamWindow

DATA = pathlib.Path(__file__).resolve().parent / "data"

EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def window_of(days: float = 4000.0) -> StreamWindow:
    end = EPOCH + timedelta(days=days)
    return StreamWindow(start=EPOCH, end=end, timezone="UTC", complete_through=end)


def spell(
    ref: str,
    *,
    days: float,
    observed: bool,
    entry_days: float = 0.0,
    covariates: dict | None = None,
    category: str = "general",
    outcome: str | None = None,
    first_response_hours: float | None = None,
    **extra,
) -> RequestSpell:
    """
    One RequestSpell in the shape the reducer would produce.

    `entry_days` is delayed entry (rule C3): the age the request had already
    reached when the window opened.
    """
    opened_at = EPOCH - timedelta(days=entry_days)
    if outcome is None:
        outcome = "resolved" if observed else None
    defaults = {
        "censoring": "none" if observed else "administrative",
        "interval_lo_hours": None,
        "interval_hi_hours": None,
        "terminal_at": opened_at + timedelta(days=entry_days + days) if observed else None,
    }
    defaults.update(extra)
    return RequestSpell(
        request_ref=ref,
        opened_at=opened_at,
        at_risk_from=EPOCH,
        left_truncated=entry_days > 0.0,
        duration_hours=days * 24.0,
        duration_active_hours=None,
        event_observed=observed,
        outcome=outcome,
        first_response_hours=first_response_hours,
        paused_hours=0.0,
        reopened_count=0,
        duplicate_count=0,
        category=category,
        covariates=covariates or {},
        **defaults,
    )


def lung_spells(*, with_sex: bool = False) -> list[RequestSpell]:
    """
    `lung` as request spells. status 2 is a death (the observed event), status 1
    is censoring. Time is in days and maps straight onto resolution time.
    """
    out: list[RequestSpell] = []
    for i, row in enumerate(read_csv("lung.csv")):
        observed = row["status"] == "2"
        covariates = {"sex": ("male" if row["sex"] == "1" else "female")} if with_sex else {}
        out.append(spell(
            "lung-" + str(i),
            days=float(row["time"]),
            observed=observed,
            covariates=covariates,
            category=("male" if row["sex"] == "1" else "female"),
        ))
    return out


ROSSI_COVARIATES = ("fin", "age", "race", "wexp", "mar", "paro", "prio")

# Published Cox coefficients for rossi, reproduced in lifelines' documentation
# and in Klein and Moeschberger.
ROSSI_PUBLISHED = {
    "fin": -0.379,
    "age": -0.057,
    "race": 0.314,
    "wexp": -0.150,
    "mar": -0.434,
    "paro": -0.085,
    "prio": 0.091,
}


def rossi_spells() -> list[RequestSpell]:
    """
    `rossi` as request spells. `arrest` is the event, `week` the duration. The
    covariates ride in `covariates`, which is where the spine puts them.
    """
    out: list[RequestSpell] = []
    for i, row in enumerate(read_csv("rossi.csv")):
        out.append(spell(
            "rossi-" + str(i),
            days=float(row["week"]),
            observed=row["arrest"] == "1",
            covariates={name: float(row[name]) for name in ROSSI_COVARIATES},
        ))
    return out


def heart_rows() -> list[tuple[float, float, bool]]:
    """(entry, exit, event) triples: the canonical delayed-entry example."""
    return [
        (float(r["start"]), float(r["stop"]), r["event"] == "1")
        for r in read_csv("heart.csv")
    ]


def nile_series() -> list[tuple[int, float]]:
    return [(int(r["year"]), float(r["flow"])) for r in read_csv("nile.csv")]


def mgus2_rows() -> list[dict[str, str]]:
    return read_csv("mgus2.csv")
