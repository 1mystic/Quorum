"""
Participatory budgeting over the decision stream.

The Method of Equal Shares ships with the utilitarian greedy baseline alongside it,
never instead of it, so a committee sees the trade-off between total satisfaction and
proportional fairness explicitly.

The guarantee MES exists for is extended justified representation, and this
module verifies it computationally on the actual result rather than citing it.
That verification is what makes the greedy comparison honest: the same checker
runs on the greedy allocation and, on a minority-preference instance, finds the
violation. A property checker that has never been watched fail proves nothing.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import itertools
import math
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import bootstrap_bca

MIN_BALLOTS = 20
MIN_OPTIONS = 3
# Above this, enumerating every cohesive group is not affordable, so the EJR
# check runs over groups cohesive for at most this many projects and says so.
EXHAUSTIVE_PROJECT_LIMIT = 12
PARTIAL_COHESIVE_SIZE = 3


# ---------------------------------------------------------------------------
# Instance handling
# ---------------------------------------------------------------------------


def _instance(ballots, options):
    """Approval sets per voter and cost per project, with invalid ballots counted."""
    costs: dict[str, int] = {}
    for option in options:
        cost = getattr(option, "cost_minor", None)
        if cost is None:
            continue
        costs[str(option.option_ref)] = int(cost)
    known = set(costs)

    approvals: list[frozenset[str]] = []
    excluded = 0
    for ballot in ballots:
        raw = set(getattr(ballot, "approvals", frozenset()) or frozenset())
        if not raw:
            allocation = getattr(ballot, "allocation", {}) or {}
            raw = {ref for ref, amount in allocation.items() if amount and amount > 0}
        if raw - known:
            excluded += 1
            continue
        approvals.append(frozenset(raw))
    return approvals, costs, excluded


def _supporters(approvals: Sequence[frozenset[str]], project: str) -> list[int]:
    return [i for i, a in enumerate(approvals) if project in a]


def _utility(approvals: Sequence[frozenset[str]], funded: Sequence[str]) -> list[int]:
    chosen = set(funded)
    return [len(a & chosen) for a in approvals]


# ---------------------------------------------------------------------------
# Extended justified representation
# ---------------------------------------------------------------------------


def ejr_violations(approvals: Sequence[frozenset[str]], costs: Mapping[str, int],
                   budget: int, funded: Sequence[str]) -> tuple[list[dict], bool]:
    """
    Every cohesive group whose entitlement the allocation failed to honour.

    A group N' is T-cohesive when every voter in it approves every project in T
    and the group's collective budget share, |N'|/n * B, covers the cost of T.
    EJR says at least one voter in such a group must receive utility |T| or
    more. A violation is therefore a group that could have paid for T out of its
    own share and got less than T's worth of anything it wanted.

    Returns the violations and whether the search was exhaustive. With few
    enough projects every subset T is enumerated; above that, subsets up to
    PARTIAL_COHESIVE_SIZE are checked and the caller must say so, because an
    incomplete search finding nothing is not a proof.
    """
    n = len(approvals)
    projects = sorted(costs)
    if n == 0 or not projects:
        return [], True

    exhaustive = len(projects) <= EXHAUSTIVE_PROJECT_LIMIT
    max_size = len(projects) if exhaustive else PARTIAL_COHESIVE_SIZE
    utilities = _utility(approvals, funded)

    violations: list[dict] = []
    seen: set[tuple[str, ...]] = set()
    for size in range(1, max_size + 1):
        for subset in itertools.combinations(projects, size):
            cost = sum(costs[p] for p in subset)
            group = [i for i, a in enumerate(approvals) if all(p in a for p in subset)]
            if not group:
                continue
            if len(group) * budget < cost * n:
                continue  # not cohesive: the group's share does not cover T
            if max(utilities[i] for i in group) >= size:
                continue
            key = tuple(subset)
            if key in seen:
                continue
            seen.add(key)
            violations.append({
                "projects": list(subset),
                "cost_minor": cost,
                "n_voters": len(group),
                "entitlement_minor": len(group) * budget / n,
                "best_utility_in_group": max(utilities[i] for i in group),
                "required_utility": size,
            })
    return violations, exhaustive


def _ejr_check(violations, exhaustive, *, blocking: bool, rule: str) -> Check:
    scope = (
        "every cohesive group was enumerated"
        if exhaustive else
        "groups cohesive for up to " + str(PARTIAL_COHESIVE_SIZE) + " projects were enumerated; "
        "the instance is too large to check every subset, so this is a sound but incomplete search"
    )
    if not violations:
        return Check(
            id="ejr-satisfied",
            label="Every group that could have paid for something got something",
            status="PASS",
            statistic=0.0,
            detail=scope,
        )
    worst = violations[0]
    return Check(
        id="ejr-satisfied",
        label="Every group that could have paid for something got something",
        status="FAIL",
        statistic=float(len(violations)),
        blocking=blocking,
        detail=(
            str(len(violations)) + " groups were entitled to more than they received. The "
            "clearest: " + str(worst["n_voters"]) + " voters all approved "
            + ", ".join(worst["projects"]) + ", their share of the budget covers it, and the "
            "best-served voter among them got " + str(worst["best_utility_in_group"])
            + " of the " + str(worst["required_utility"]) + " they were entitled to. "
            + (
                "Equal Shares guarantees this cannot happen, so a violation here is an "
                "implementation bug and the allocation is not shown."
                if blocking else
                "The greedy rule offers no such guarantee, which is exactly the trade-off this "
                "comparison exists to make visible."
            ) + " (" + scope + ", rule " + rule + ".)"
        ),
    )


# ---------------------------------------------------------------------------
# budgeting.method_of_equal_shares
# ---------------------------------------------------------------------------


def equal_shares(approvals: Sequence[frozenset[str]], costs: Mapping[str, int],
                 per_voter_budget: float) -> tuple[list[str], list[dict], list[float]]:
    """
    One run of the Method of Equal Shares at a given per-voter budget.

    At each step, for every unfunded project, find the smallest rho such that
    its supporters can jointly pay its cost when each contributes at most rho.
    Fund the project with the smallest such rho, charge its supporters, repeat
    until no project is affordable. Peters and Skowron (2020).
    """
    n = len(approvals)
    purses = [float(per_voter_budget)] * n
    funded: list[str] = []
    rounds: list[dict] = []
    remaining = set(costs)

    while remaining:
        best_rho = None
        best_project = None
        for project in sorted(remaining):
            cost = costs[project]
            supporters = _supporters(approvals, project)
            if not supporters:
                continue
            wallets = sorted(purses[i] for i in supporters)
            if math.fsum(wallets) < cost - 1e-9:
                continue
            # Smallest rho with sum(min(purse, rho)) >= cost. The function is
            # piecewise linear in rho with breakpoints at the purse values.
            paid = 0.0
            rho = None
            for index, wallet in enumerate(wallets):
                payers_left = len(wallets) - index
                if paid + wallet * payers_left >= cost - 1e-12:
                    rho = (cost - paid) / payers_left
                    break
                paid += wallet
            if rho is None:
                continue
            if best_rho is None or rho < best_rho - 1e-12 or (
                abs(rho - best_rho) <= 1e-12 and project < best_project
            ):
                best_rho, best_project = rho, project
        if best_project is None:
            break
        supporters = _supporters(approvals, best_project)
        charged = 0.0
        for i in supporters:
            pay = min(purses[i], best_rho)
            purses[i] -= pay
            charged += pay
        funded.append(best_project)
        remaining.discard(best_project)
        rounds.append({
            "round": len(rounds) + 1,
            "funded": best_project,
            "cost_minor": costs[best_project],
            "rho": best_rho,
            "n_supporters": len(supporters),
            "charged_minor": charged,
        })
    return funded, rounds, purses


def method_of_equal_shares(ballots, options, spec, *, completion="add1") -> Evidence:
    """budgeting.method_of_equal_shares. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "budgeting.method_of_equal_shares"
    phash = params_hash(method, 1, {
        "decision_ref": getattr(spec, "decision_ref", None), "completion": completion,
    })
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    approvals, costs, excluded = _instance(ballots, options)
    budget = getattr(spec, "budget_minor", None)
    n = len(approvals)

    empty = {"funded": [], "not_funded": sorted(costs), "spent_minor": 0,
             "remaining_minor": budget, "per_voter_spend": None, "rounds": []}
    if n < MIN_BALLOTS or len(costs) < MIN_OPTIONS or not budget:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="minor units",
            caveats=(
                "Needs " + str(MIN_BALLOTS) + " ballots, " + str(MIN_OPTIONS) + " costed options "
                "and a declared budget; has " + str(n) + " and " + str(len(costs)) + ". Below "
                "that the proportionality guarantee is vacuous, since one voter's budget share "
                "funds nothing.",
            ),
        )

    base = budget / n
    funded, rounds, purses = equal_shares(approvals, costs, base)
    completion_steps = 0

    if completion == "add1":
        # Peters and Skowron's completion: raise every voter's share uniformly
        # and rerun from scratch, keeping the last outcome that still fits the
        # budget. Uniform raising is what preserves the fairness argument; a
        # greedy top-up of the leftovers would not.
        multiplier = base
        step = max(base * 0.02, 1.0)
        best = funded
        best_rounds = rounds
        while completion_steps < 500:
            multiplier += step
            candidate, candidate_rounds, _ = equal_shares(approvals, costs, multiplier)
            spend = sum(costs[p] for p in candidate)
            completion_steps += 1
            if spend > budget:
                break
            if len(candidate) > len(best) or spend > sum(costs[p] for p in best):
                best, best_rounds = candidate, candidate_rounds
            if spend == budget:
                break
        funded, rounds = best, best_rounds
    elif completion != "none":
        raise ValueError(
            "budgeting.method_of_equal_shares completion must be 'add1' or 'none', got "
            + repr(completion)
        )

    spent = sum(costs[p] for p in funded)
    remaining = budget - spent
    violations, exhaustive = ejr_violations(approvals, costs, budget, funded)

    checks = [
        _ejr_check(violations, exhaustive, blocking=True, rule="equal shares"),
        Check(
            id="budget-exhausted",
            label="How much of the budget the rule managed to allocate",
            status="WARN" if remaining > budget * 0.1 else "PASS",
            statistic=spent / budget if budget else 0.0,
            detail=(
                "{:.1%}".format(remaining / budget) + " of the budget is unspent. Equal Shares "
                "stops when no project's supporters can jointly afford it, which is a feature "
                "and not a failure to allocate."
            ) if remaining > budget * 0.1 else "",
        ),
        Check(
            id="completion-rule-applied",
            label="The declared method for leftover budget, and whether it fired",
            status="PASS",
            statistic=float(completion_steps),
            detail=(
                "Completion rule " + repr(completion) + ". The per-voter share was raised "
                "uniformly " + str(completion_steps) + " times, each a full rerun, and the last "
                "outcome that fit the budget was kept."
                if completion_steps else "Completion rule " + repr(completion) + "."
            ),
        ),
        Check(
            id="ballot-validity",
            label="Ballots approving options not on the paper are excluded and counted",
            status="WARN" if excluded else "PASS",
            statistic=float(excluded),
            detail=(str(excluded) + " ballots approved an option not on this paper.")
            if excluded else "",
        ),
    ]

    value: dict[str, Any] = {
        "funded": sorted(funded),
        "not_funded": sorted(set(costs) - set(funded)),
        "spent_minor": spent,
        "remaining_minor": remaining,
        "per_voter_spend": spent / n,
        "rounds": rounds,
        "budget_minor": budget,
        "ejr_violations": violations,
    }
    if violations:
        # A blocking failure empties the value: an allocation that breaks the
        # guarantee it is named for must not be printed as one.
        value = {**value, "funded": [], "not_funded": sorted(costs), "spent_minor": None,
                 "per_voter_spend": None}

    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Each voter has an equal share of the budget, " + "{:.2f}".format(base)
            + " minor units.",
            "Approvals express genuine support rather than strategic bundling.",
        ),
        checks=tuple(checks),
        caveats=(
            "An allocation rule, not an estimate. There is no interval because nothing here is "
            "being inferred about anyone who did not vote.",
            "Splitting one physical project across several options games this rule. "
            "budgeting.fairness_report is where that shows up, as one stratum taking a "
            "disproportionate share.",
        ),
        n_excluded=excluded,
        exclusion_reason=("ballot approved an option not on the paper" if excluded else ""),
        unit="minor units",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# budgeting.greedy_knapsack
# ---------------------------------------------------------------------------


def knapsack_optimum(values: Sequence[int], weights: Sequence[int], capacity: int) -> int:
    """
    Exact 0/1 knapsack by dynamic programming over the capacity.

    Here so the greedy rule can be scored against the real optimum on small
    instances rather than against another heuristic.
    """
    table = [0] * (capacity + 1)
    for value, weight in zip(values, weights):
        if weight > capacity:
            continue
        for c in range(capacity, weight - 1, -1):
            candidate = table[c - weight] + value
            if candidate > table[c]:
                table[c] = candidate
    return table[capacity]


def greedy_knapsack(ballots, options, spec) -> Evidence:
    """budgeting.greedy_knapsack. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "budgeting.greedy_knapsack"
    phash = params_hash(method, 1, {"decision_ref": getattr(spec, "decision_ref", None)})
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    approvals, costs, excluded = _instance(ballots, options)
    budget = getattr(spec, "budget_minor", None)
    n = len(approvals)

    empty = {"funded": [], "not_funded": sorted(costs), "spent_minor": 0,
             "remaining_minor": budget, "total_approvals": 0, "rounds": []}
    if n < MIN_BALLOTS or len(costs) < MIN_OPTIONS or not budget:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="minor units",
            caveats=(
                "Needs " + str(MIN_BALLOTS) + " ballots, " + str(MIN_OPTIONS) + " costed options "
                "and a declared budget; has " + str(n) + " and " + str(len(costs)) + ".",
            ),
        )

    support = {p: len(_supporters(approvals, p)) for p in costs}

    # Density greedy alone has no approximation guarantee: one cheap popular
    # project can crowd out the single item that is worth almost everything.
    # The half-optimal rule is the better of density greedy and the best single
    # affordable project, so that comparison is part of the shipped rule and is
    # disclosed rather than left as a footnote.
    ordered = sorted(costs, key=lambda p: (-(support[p] / costs[p]) if costs[p] else 0.0, p))
    greedy: list[str] = []
    spent = 0
    rounds = []
    for project in ordered:
        if spent + costs[project] <= budget:
            greedy.append(project)
            spent += costs[project]
            rounds.append({
                "round": len(rounds) + 1, "funded": project, "cost_minor": costs[project],
                "approvals": support[project],
                "approvals_per_minor_unit": support[project] / costs[project] if costs[project] else 0.0,
            })
    greedy_value = sum(support[p] for p in greedy)

    affordable = [p for p in costs if costs[p] <= budget]
    best_single = max(affordable, key=lambda p: (support[p], p)) if affordable else None
    single_value = support[best_single] if best_single else 0

    if single_value > greedy_value:
        funded, total, variant = [best_single], single_value, "best-single-project"
        spent = costs[best_single]
        rounds = [{
            "round": 1, "funded": best_single, "cost_minor": costs[best_single],
            "approvals": support[best_single],
            "approvals_per_minor_unit": support[best_single] / costs[best_single],
        }]
    else:
        funded, total, variant = greedy, greedy_value, "density-greedy"

    violations, exhaustive = ejr_violations(approvals, costs, budget, funded)

    checks = [
        _ejr_check(violations, exhaustive, blocking=False, rule="greedy"),
        Check(
            id="greedy-variant",
            label="Which of the two greedy candidates was served, and why that matters",
            status="PASS",
            statistic=1.0 if variant == "density-greedy" else 0.0,
            detail=(
                "Served the " + variant + " allocation. Density greedy on its own has no "
                "approximation guarantee; taking the better of it and the best single "
                "affordable project is what buys the one-half bound against the exact optimum."
            ),
        ),
        Check(
            id="budget-exhausted",
            label="How much of the budget the rule managed to allocate",
            status="PASS",
            statistic=spent / budget if budget else 0.0,
        ),
    ]

    return Evidence(
        value={
            "funded": sorted(funded),
            "not_funded": sorted(set(costs) - set(funded)),
            "spent_minor": spent,
            "remaining_minor": budget - spent,
            "total_approvals": total,
            "rounds": rounds,
            "variant": variant,
            "budget_minor": budget,
            "ejr_violations": violations,
        },
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Total approval is the objective, which is a choice and not the only defensible one.",
        ),
        checks=tuple(checks),
        caveats=(
            "Shown ALONGSIDE the Method of Equal Shares, never instead of it. The comparison is "
            "the point: this rule buys total satisfaction and can leave a minority with nothing.",
            "An allocation rule, not an estimate.",
        ),
        n_excluded=excluded,
        exclusion_reason=("ballot approved an option not on the paper" if excluded else ""),
        unit="minor units",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# budgeting.fairness_report
# ---------------------------------------------------------------------------


def _stratum_of(ballot) -> str:
    strata = getattr(ballot, "strata", {}) or {}
    if not strata:
        return "unstated"
    return ":".join(str(strata[name]) for name in sorted(strata))


def _attribution(voters: Sequence[tuple[str, frozenset[str]]], funded: Sequence[str],
                 costs: Mapping[str, int]) -> dict[str, float]:
    """
    Budget won per stratum: each funded project's cost is split across the
    strata of its supporters, in proportion to how many supporters each
    contributed. A project nobody voting approved is attributed to nobody.
    """
    won: dict[str, float] = {}
    for project in funded:
        backers = [s for s, approvals in voters if project in approvals]
        if not backers:
            continue
        share = costs[project] / len(backers)
        for stratum in backers:
            won[stratum] = won.get(stratum, 0.0) + share
    return won


def fairness_report(ballots, options, funded, roster, *, k_anonymity=5, seed=0) -> Evidence:
    """budgeting.fairness_report. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "budgeting.fairness_report"
    phash = params_hash(method, 1, {
        "funded": sorted(str(f) for f in funded), "k_anonymity": k_anonymity, "seed": seed,
    })
    as_of = getattr(roster, "as_of", None)

    costs: dict[str, int] = {}
    for option in options:
        cost = getattr(option, "cost_minor", None)
        if cost is not None:
            costs[str(option.option_ref)] = int(cost)
    known = set(costs)

    voters: list[tuple[str, frozenset[str]]] = []
    excluded = 0
    for ballot in ballots:
        raw = set(getattr(ballot, "approvals", frozenset()) or frozenset())
        if not raw:
            allocation = getattr(ballot, "allocation", {}) or {}
            raw = {ref for ref, amount in allocation.items() if amount and amount > 0}
        if raw - known:
            excluded += 1
            continue
        voters.append((_stratum_of(ballot), frozenset(raw)))

    n = len(voters)
    funded = [str(f) for f in funded if str(f) in known]
    spent = sum(costs[p] for p in funded)
    if n < MIN_BALLOTS or not funded or spent <= 0:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=[], unit="utilisation",
            caveats=(
                "Needs " + str(MIN_BALLOTS) + " ballots and a non-empty funded set; has "
                + str(n) + " and " + str(len(funded)) + ".",
            ),
        )

    sizes: dict[str, int] = {}
    for stratum, _ in voters:
        sizes[stratum] = sizes.get(stratum, 0) + 1

    # Small strata are POOLED, not dropped. Dropping them hides exactly the
    # group this report exists to protect.
    small = {s for s, size in sizes.items() if size < k_anonymity}
    pooled = [
        ("other" if stratum in small else stratum, approvals)
        for stratum, approvals in voters
    ]
    pooled_sizes: dict[str, int] = {}
    for stratum, _ in pooled:
        pooled_sizes[stratum] = pooled_sizes.get(stratum, 0) + 1

    won = _attribution(pooled, funded, costs)
    total_attributed = math.fsum(won.values())

    def utilisation_from(indices: Sequence[float]) -> dict[str, float]:
        sample = [pooled[int(i)] for i in indices]
        counts: dict[str, int] = {}
        for stratum, _ in sample:
            counts[stratum] = counts.get(stratum, 0) + 1
        sample_won = _attribution(sample, funded, costs)
        sample_total = math.fsum(sample_won.values())
        out = {}
        for stratum, size in counts.items():
            electorate = size / len(sample)
            budget_share = (sample_won.get(stratum, 0.0) / sample_total) if sample_total else 0.0
            out[stratum] = budget_share / electorate if electorate else 0.0
        return out

    indices = [float(i) for i in range(len(pooled))]
    rows = []
    for stratum in sorted(pooled_sizes):
        size = pooled_sizes[stratum]
        electorate = size / n
        budget_share = (won.get(stratum, 0.0) / total_attributed) if total_attributed else 0.0
        utilisation = budget_share / electorate if electorate else 0.0
        lo, hi = bootstrap_bca(
            indices,
            lambda sample, s=stratum: utilisation_from(sample).get(s, 0.0),
            seed=seed, n_boot=300,
        )
        rows.append({
            "stratum": stratum,
            "n_voters": size,
            "share_of_electorate": electorate,
            "share_of_budget_won": budget_share,
            "budget_won_minor": won.get(stratum, 0.0),
            "utilisation": utilisation,
            "lo": lo,
            "hi": hi,
            "n": size,
            "pooled": stratum == "other" and bool(small),
            "suppressed": False,
        })

    pooled_share = sum(sizes[s] for s in small) / n if small else 0.0
    gap = max(
        (abs(r["share_of_budget_won"] - r["share_of_electorate"]) for r in rows), default=0.0
    )

    checks = [
        Check(
            id="k-anonymity-rows",
            label="No published row describes fewer than k voters",
            status="FAIL" if small else "PASS",
            statistic=float(k_anonymity),
            blocking=False,
            detail=(
                str(len(small)) + " strata had fewer than " + str(k_anonymity) + " voters and "
                "were pooled into 'other' rather than dropped. Dropping them would hide exactly "
                "the group this report exists to protect."
            ) if small else "",
        ),
        Check(
            id="strata-coverage",
            label="Share of voters sitting in the pooled 'other' row",
            status="WARN" if pooled_share > 0.2 else "PASS",
            statistic=pooled_share,
            detail=(
                "{:.1%}".format(pooled_share) + " of voters are inside the pooled row, so the "
                "per-stratum picture is coarser than it looks."
            ) if pooled_share > 0.2 else "",
        ),
        Check(
            id="proportionality-gap",
            label="Largest gap between a group's share of voters and its share of budget",
            status="WARN" if gap > 0.1 else "PASS",
            statistic=gap,
            detail=(
                "The widest gap is " + "{:.1%}".format(gap) + " of the budget. Utilisation "
                "describes what happened; it is not an entitlement and must not be read as one."
            ) if gap > 0.1 else "",
        ),
    ]

    return Evidence(
        value=rows,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="bootstrap-bca-95",
        assumptions=(
            "The strata are the ones the vertical declared.",
            "A funded project's cost is attributed to the strata of its supporters, split "
            "evenly across them.",
        ),
        checks=tuple(checks),
        caveats=(
            "Utilisation of 1.0 means a group won budget in exact proportion to its share of "
            "voters. Below 1.0 means less, above means more. It describes the allocation, not "
            "what anyone was owed.",
            "The interval is a seeded bootstrap over voters with the funded set held fixed, so "
            "it answers how stable this split is to who turned out, not to which projects won.",
        ),
        n_excluded=excluded,
        exclusion_reason=("ballot approved an option not on the paper" if excluded else ""),
        unit="utilisation",
        params_hash=phash,
    )


__all__ = [
    "ejr_violations",
    "equal_shares",
    "fairness_report",
    "greedy_knapsack",
    "knapsack_optimum",
    "method_of_equal_shares",
]
