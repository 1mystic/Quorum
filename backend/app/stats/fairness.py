"""
Workload distribution and assignment over request_flow.

Per-person rows pass the tenant k-anonymity floor before they can leave.

Two things here are deliberately not statistics. The assignment suggestion is an
optimisation result and carries no interval, because giving one would be a
category error, and its min_n is 1 because there is no inference in it. The
Method Card says both out loud, since a service with `interval_kind="none"` and
`min_n=1` looks suspicious next to the rest of the pack and the reason should be
visible rather than inferred.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import bootstrap_bca, chi2_sf, mean

MIN_RESOLVERS = 10
MIN_ASSIGNED = 50
BIG_COST = 1e6


# ---------------------------------------------------------------------------
# Concentration
# ---------------------------------------------------------------------------


def gini(values: Sequence[float]) -> float:
    """
    The Gini coefficient of a non-negative vector.

    G = (2 * sum(i * x_i)) / (n * sum(x)) - (n + 1) / n, over x sorted ascending
    with i counted from 1. Three exact values follow from that formula and are
    the known-answer test: a perfectly equal vector gives 0, the vector
    (0, ..., 0, 1) gives (n-1)/n, and the discrete uniform 1..n gives (n-1)/(3n).
    """
    xs = sorted(float(v) for v in values)
    n = len(xs)
    if n == 0:
        raise ValueError("gini of an empty vector")
    if any(x < 0 for x in xs):
        raise ValueError("gini is not defined for negative quantities")
    total = math.fsum(xs)
    if total <= 0.0:
        return 0.0
    weighted = math.fsum((i + 1) * x for i, x in enumerate(xs))
    return (2.0 * weighted) / (n * total) - (n + 1.0) / n


def lorenz(values: Sequence[float]) -> dict[str, list[float]]:
    """Cumulative share of people against cumulative share of work, both from 0 to 1."""
    xs = sorted(float(v) for v in values)
    n = len(xs)
    total = math.fsum(xs)
    people = [0.0]
    work = [0.0]
    running = 0.0
    for i, x in enumerate(xs):
        running += x
        people.append((i + 1) / n)
        work.append(running / total if total > 0 else 0.0)
    return {"cum_share_people": people, "cum_share_work": work}


def _load_by_person(spells: Sequence[Any], by: str, weight: str) -> dict[str, float]:
    loads: dict[str, float] = {}
    for spell in spells:
        key = getattr(spell, by, None)
        if key is None:
            continue
        if weight == "hours":
            amount = float(getattr(spell, "duration_hours", 0.0))
        else:
            amount = 1.0
        loads[key] = loads.get(key, 0.0) + amount
    return loads


def _category_mix(spells: Sequence[Any], by: str) -> dict[str, dict[str, int]]:
    mix: dict[str, dict[str, int]] = {}
    for spell in spells:
        key = getattr(spell, by, None)
        if key is None:
            continue
        category = getattr(spell, "category", "unknown")
        mix.setdefault(key, {})
        mix[key][category] = mix[key].get(category, 0) + 1
    return mix


def _mix_divergence_p(mix: Mapping[str, Mapping[str, int]]) -> tuple[float, int]:
    """Chi-square test of independence between resolver and category."""
    people = sorted(mix)
    categories = sorted({c for row in mix.values() for c in row})
    if len(people) < 2 or len(categories) < 2:
        return 1.0, 0
    table = [[mix[p].get(c, 0) for c in categories] for p in people]
    total = sum(sum(row) for row in table)
    if total == 0:
        return 1.0, 0
    row_sums = [sum(row) for row in table]
    col_sums = [sum(table[i][j] for i in range(len(people))) for j in range(len(categories))]
    stat = 0.0
    for i in range(len(people)):
        for j in range(len(categories)):
            expected = row_sums[i] * col_sums[j] / total
            if expected <= 0:
                continue
            stat += (table[i][j] - expected) ** 2 / expected
    df = (len(people) - 1) * (len(categories) - 1)
    return chi2_sf(stat, df), df


def workload_gini(spells, window, *, by="assignee_ref", weight="count",
                  include_zero_workers=False, k_anonymity=5, seed=0,
                  roster=None) -> Evidence:
    """fairness.workload_gini. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "fairness.workload_gini"
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None),
        "window_end": getattr(window, "end", None),
        "by": by, "weight": weight, "include_zero_workers": include_zero_workers,
        "k_anonymity": k_anonymity, "seed": seed,
    })
    as_of = getattr(window, "end", None)
    assigned = [s for s in spells if getattr(s, by, None) is not None]
    loads = _load_by_person(assigned, by, weight)
    if include_zero_workers and roster:
        for person in roster:
            loads.setdefault(person, 0.0)
    n_assigned = len(assigned)
    n_people = len(loads)
    empty = {"gini": None, "lorenz": {"cum_share_people": [], "cum_share_work": []},
             "top_share": None, "rows": []}
    if n_people < MIN_RESOLVERS or n_assigned < MIN_ASSIGNED:
        return insufficient(
            method, n=n_assigned, as_of=as_of, empty_value=empty, params_hash=phash,
            unit="concentration",
            caveats=(
                "needs " + str(MIN_RESOLVERS) + " resolvers and " + str(MIN_ASSIGNED)
                + " assigned requests; has " + str(n_people) + " and " + str(n_assigned)
                + ". A Gini over three people is a description of three people, not a statistic.",
            ),
        )

    values = list(loads.values())
    coefficient = gini(values)
    lo, hi = bootstrap_bca(values, gini, seed=seed, n_boot=1000)
    ordered = sorted(loads.items(), key=lambda kv: -kv[1])
    total = math.fsum(values)
    top_share = (ordered[0][1] / total) if total > 0 else 0.0

    counts = _load_by_person(assigned, by, "count")
    rows = [
        {"key": person, "load": load, "share": load / total if total else 0.0,
         "n": int(counts.get(person, 0)), "suppressed": counts.get(person, 0) < k_anonymity}
        for person, load in ordered
    ]
    suppressed = [r for r in rows if r["suppressed"]]
    for row in suppressed:
        row["load"] = None
        row["share"] = None
        row["key"] = "suppressed"

    mix = _category_mix(assigned, by)
    mix_p, mix_df = _mix_divergence_p(mix)
    checks = [
        Check(
            id="k-anonymity-rows",
            label="No per-person row is small enough to identify anyone",
            status="FAIL" if suppressed else "PASS",
            statistic=float(k_anonymity),
            blocking=bool(suppressed),
            detail=(
                str(len(suppressed)) + " resolvers handled fewer than " + str(k_anonymity)
                + " requests, so their rows are suppressed. The aggregate coefficient is still "
                "reported, because it identifies nobody."
            ) if suppressed else "",
        ),
        Check(
            id="zero-workers-included",
            label="Whether resolvers with no assignments were counted is declared",
            status="PASS",
            statistic=1.0 if include_zero_workers else 0.0,
            detail=(
                ("Resolvers with zero assignments are included" if include_zero_workers
                 else "Only resolvers with at least one assignment are counted")
                + ". This single choice moves the coefficient enormously, so it is a declared "
                "parameter and it is in params_hash."
            ),
        ),
        Check(
            id="unequal-difficulty",
            label="A unit of work means the same for everyone",
            status="WARN" if (mix_p < 0.05 and weight == "count") else "PASS",
            statistic=mix_p,
            p_value=mix_p,
            detail=(
                "the category mix differs materially across resolvers (chi-square p="
                + format(mix_p, ".4f") + " on " + str(mix_df) + " df), so counting a lift "
                "breakdown and a noisy-dog complaint as equal work flatters somebody. Ask for "
                "the hours-weighted variant."
            ) if (mix_p < 0.05 and weight == "count") else "",
        ),
    ]
    value = {
        "gini": coefficient,
        "lorenz": lorenz(values),
        "top_share": top_share,
        "n_people": n_people,
        "weight": weight,
        "rows": rows,
    }
    return Evidence(
        value=value,
        n=n_assigned,
        method=method,
        as_of=as_of,
        interval=(lo, hi),
        interval_kind="bootstrap-bca-95",
        assumptions=(
            "The unit of work is comparable across people.",
            "Every resolver was available for the whole window, which part-time volunteers "
            "break.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        unit="concentration",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


def hungarian(cost: Sequence[Sequence[float]]) -> list[int]:
    """
    The Kuhn-Munkres assignment algorithm, in the O(n^3) shortest-augmenting-path
    form (Jonker and Volgenant's arrangement of it).

    Takes an n x m cost matrix with n <= m and returns, for each row, the column
    it is assigned to. Exact, not a heuristic: the test checks it against
    exhaustive enumeration on small matrices, which is an independent oracle.
    """
    n = len(cost)
    if n == 0:
        return []
    m = len(cost[0])
    if m < n:
        raise ValueError("hungarian needs at least as many columns as rows")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)          # p[j] = row assigned to column j
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [math.inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = math.inf
            j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                current = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if current < minv[j]:
                    minv[j] = current
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    assignment = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            assignment[p[j] - 1] = j - 1
    return assignment


def _resolver_fields(resolver: Any) -> tuple[str, tuple[str, ...], float]:
    if isinstance(resolver, Mapping):
        ref = str(resolver.get("ref"))
        skills = tuple(resolver.get("skills") or ())
        load = float(resolver.get("current_load", 0.0))
    else:
        ref = str(getattr(resolver, "ref", getattr(resolver, "member_ref", "")))
        skills = tuple(getattr(resolver, "skills", ()) or ())
        load = float(getattr(resolver, "current_load", 0.0))
    return ref, skills, load


def balanced_assignment(open_requests, resolvers, *, capacity, cost="load_and_skill",
                        seed=0) -> Evidence:
    """fairness.balanced_assignment. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "fairness.balanced_assignment"
    phash = params_hash(method, 1, {"cost": cost, "capacity": dict(capacity), "seed": seed})
    as_of = None
    for request in open_requests:
        as_of = getattr(request, "opened_at", None)
        break
    parsed = [_resolver_fields(r) for r in resolvers]
    n_requests = len(open_requests)
    if n_requests < 1 or len(parsed) < 2:
        return insufficient(
            method, n=n_requests, as_of=as_of, empty_value=[], params_hash=phash,
            caveats=("needs at least one open request and two resolvers",),
        )

    # One column per unit of declared capacity: a resolver who can take three
    # requests is three interchangeable slots.
    slots: list[tuple[int, str]] = []
    for index, (ref, _, _) in enumerate(parsed):
        for _ in range(int(capacity.get(ref, 0))):
            slots.append((index, ref))
    feasible = len(slots) >= n_requests
    checks: list[Check] = [
        Check(
            id="capacity-feasible",
            label="Declared capacity covers the open requests",
            status="PASS" if feasible else "FAIL",
            statistic=float(len(slots)),
            blocking=not feasible,
            detail=(
                "declared capacity is " + str(len(slots)) + " requests against " + str(n_requests)
                + " open, so no complete assignment exists. What follows is the best partial "
                "assignment plus the shortfall of " + str(n_requests - len(slots)) + "."
            ) if not feasible else "",
        ),
    ]

    loads = {ref: load for ref, _, load in parsed}
    skills = {ref: set(sk) for ref, sk, _ in parsed}
    uncovered = sorted({
        getattr(r, "category", "unknown") for r in open_requests
        if not any((not skills[ref]) or getattr(r, "category", "unknown") in skills[ref]
                   for _, ref in slots)
    })
    checks.append(Check(
        id="skill-coverage",
        label="Every open category has someone who can take it",
        status="WARN" if uncovered else "PASS",
        statistic=float(len(uncovered)),
        detail=(
            "no available resolver lists these categories as a skill: " + ", ".join(uncovered)
            + ". They are surfaced here rather than silently handed to whoever is least busy."
        ) if uncovered else "",
    ))

    # The cost of putting request i on slot j: the resolver's projected load
    # after taking it, plus a large penalty for a category they cannot do. Ties
    # are broken by the request reference so the result is deterministic without
    # needing randomness at all; `seed` is accepted for signature symmetry and
    # enters params_hash.
    ordered = sorted(open_requests, key=lambda r: str(getattr(r, "request_ref", "")))
    projected: dict[str, float] = dict(loads)
    matrix: list[list[float]] = []
    for request in ordered:
        category = getattr(request, "category", "unknown")
        row = []
        for resolver_index, ref in slots:
            penalty = 0.0
            if skills[ref] and category not in skills[ref]:
                penalty = BIG_COST
            row.append(loads[ref] + penalty)
        matrix.append(row)
    if not feasible:
        # Pad with dummy slots so the algorithm can run; padded assignments are
        # reported as unassigned rather than quietly dropped.
        pad = n_requests - len(slots)
        for row in matrix:
            row.extend([BIG_COST * 10.0] * pad)

    # Each slot is used at most once, so within a resolver the second slot costs
    # one more than the first: that is what makes the result balanced rather
    # than piling everything on the least busy person.
    per_resolver_seen: dict[str, int] = {}
    for column, (resolver_index, ref) in enumerate(slots):
        occurrence = per_resolver_seen.get(ref, 0)
        per_resolver_seen[ref] = occurrence + 1
        for row in matrix:
            row[column] += occurrence

    assignment = hungarian(matrix)
    table: list[dict[str, Any]] = []
    after: dict[str, float] = dict(loads)
    for row_index, column in enumerate(assignment):
        request = ordered[row_index]
        ref_out = slots[column][1] if column < len(slots) else None
        entry = {
            "request_ref": getattr(request, "request_ref", ""),
            "category": getattr(request, "category", "unknown"),
            "suggested_assignee_ref": ref_out,
            "cost": matrix[row_index][column],
            "reason": "",
        }
        if ref_out is None:
            entry["reason"] = "no capacity left; this request is the shortfall"
        elif skills[ref_out] and entry["category"] not in skills[ref_out]:
            entry["reason"] = (
                "assigned outside the declared skill set because nobody else was available"
            )
        else:
            entry["reason"] = (
                "lowest projected load among resolvers who can take " + str(entry["category"])
            )
            after[ref_out] = after.get(ref_out, 0.0) + 1.0
        table.append(entry)

    before_gini = gini(list(loads.values())) if len(loads) > 1 else 0.0
    after_gini = gini(list(after.values())) if len(after) > 1 else 0.0
    checks.append(Check(
        id="balance-improved",
        label="The suggestion spreads the work more evenly than the status quo",
        status="PASS" if after_gini <= before_gini + 1e-12 else "WARN",
        statistic=after_gini - before_gini,
        detail=(
            "workload concentration would go from " + format(before_gini, ".3f") + " to "
            + format(after_gini, ".3f") + " on the Gini scale"
            + (". It rises because the skill constraint binds: the people who can take these "
               "categories are already the busy ones." if after_gini > before_gini else ".")
        ),
    ))
    return Evidence(
        value=table,
        n=n_requests,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="none",
        assumptions=(
            "The cost matrix reflects real preferences and real capacity. This is a "
            "recommendation, and a committee overriding it is not an error.",
            "There is no inference here, only optimisation, which is why there is no interval "
            "and why the floor is one request rather than a statistical minimum.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        unit="assignment",
        params_hash=phash,
    )


__all__ = [
    "balanced_assignment",
    "gini",
    "hungarian",
    "lorenz",
    "workload_gini",
]
