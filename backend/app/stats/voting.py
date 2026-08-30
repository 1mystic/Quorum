"""
Social choice over the decision stream.

Disclosure over tidiness. A Condorcet cycle is the finding, not an inconvenience.
Hiding one behind whichever tie-break happens to fire is the governance equivalent of
dropping open tickets.

The shape of this module follows from that. `condorcet_winner` returns
`winner=None` when a cycle exists, together with the cycle written out as an
actual sequence of options and the Smith set named, and it does not fall through
to a completion rule. `schulze` does produce a winner in that case, because that
is what Schulze is for, but it flags the winner as the resolution of a cycle
rather than as a Condorcet winner and carries the cycle alongside. The two are
different claims and the envelope keeps them different.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
import random
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import chi2_sf, wilson_interval

MIN_TURNOUT_BALLOTS = 30
LOW_TURNOUT_THRESHOLD = 0.30


# ---------------------------------------------------------------------------
# Ballot handling
# ---------------------------------------------------------------------------


def _option_refs(options: Sequence[Any]) -> tuple[str, ...]:
    refs = []
    for option in options:
        ref = getattr(option, "option_ref", None)
        refs.append(str(ref) if ref is not None else str(option))
    return tuple(refs)


def _ranks(ballot: Any, refs: tuple[str, ...], unranked: str) -> dict[str, float] | None:
    """
    Position of each option on one ballot, smaller is better.

    Returns None when the ballot is invalid: it ranks something that is not on
    the ballot paper. An invalid ballot is excluded and counted, never repaired.
    `Ballot.__post_init__` already refuses a duplicate within a ranking, so that
    class of invalidity cannot reach here at all.

    `unranked="last"` puts every unranked option in one tier below the ranked
    ones, which is the usual reading of a truncated ballot. `unranked="excluded"`
    leaves them with no position at all, so the ballot expresses no preference
    between an unranked option and anything else.
    """
    known = set(refs)
    positions: dict[str, float] = {}
    tier_index = 0
    for tier in getattr(ballot, "ranking", ()) or ():
        for option_ref in tier:
            if option_ref not in known:
                return None
            positions[option_ref] = float(tier_index)
        tier_index += 1
    if unranked == "last":
        for ref in refs:
            positions.setdefault(ref, float(tier_index))
    return positions


def _prepare(ballots, options, unranked):
    """Valid ranked ballots, the option list, and the exclusion count."""
    refs = _option_refs(options)
    ranked: list[dict[str, float]] = []
    excluded = 0
    truncated = 0
    for ballot in ballots:
        positions = _ranks(ballot, refs, unranked)
        if positions is None:
            excluded += 1
            continue
        n_ranked = sum(len(tier) for tier in (getattr(ballot, "ranking", ()) or ()))
        if n_ranked < len(refs):
            truncated += 1
        ranked.append(positions)
    return refs, ranked, excluded, truncated


def pairwise_counts(ranked: Sequence[Mapping[str, float]], refs: Sequence[str]) -> list[list[int]]:
    """d[i][j] = ballots ranking option i strictly above option j."""
    size = len(refs)
    matrix = [[0] * size for _ in range(size)]
    for positions in ranked:
        for i, a in enumerate(refs):
            pa = positions.get(a)
            if pa is None:
                continue
            for j, b in enumerate(refs):
                if i == j:
                    continue
                pb = positions.get(b)
                if pb is not None and pa < pb:
                    matrix[i][j] += 1
    return matrix


def _beats(matrix, i, j) -> bool:
    return matrix[i][j] > matrix[j][i]


def smith_set(matrix: Sequence[Sequence[int]], refs: Sequence[str]) -> list[str]:
    """
    The smallest non-empty set whose every member beats every non-member.

    Computed as the top strongly connected component of the beats-or-ties
    tournament, which is the standard construction: the condensation of a
    complete relation is a total order, so the source component is the Smith
    set. Tarjan, iteratively, so a large decision cannot blow the stack.
    """
    size = len(refs)
    adjacency = [
        [j for j in range(size) if j != i and matrix[i][j] >= matrix[j][i]]
        for i in range(size)
    ]
    index = [None] * size
    low = [0] * size
    on_stack = [False] * size
    stack: list[int] = []
    components: list[list[int]] = []
    counter = 0

    for root in range(size):
        if index[root] is not None:
            continue
        work = [(root, 0)]
        while work:
            node, child = work[-1]
            if child == 0:
                index[node] = counter
                low[node] = counter
                counter += 1
                stack.append(node)
                on_stack[node] = True
            recursed = False
            for offset in range(child, len(adjacency[node])):
                nxt = adjacency[node][offset]
                if index[nxt] is None:
                    work[-1] = (node, offset + 1)
                    work.append((nxt, 0))
                    recursed = True
                    break
                if on_stack[nxt]:
                    low[node] = min(low[node], index[nxt])
            if recursed:
                continue
            if low[node] == index[node]:
                component = []
                while True:
                    top = stack.pop()
                    on_stack[top] = False
                    component.append(top)
                    if top == node:
                        break
                components.append(component)
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    # Tarjan yields components in reverse topological order, so the last one is
    # the source: nothing outside it points into it.
    top_component = components[-1]
    return sorted(refs[i] for i in top_component)


def find_cycle(matrix: Sequence[Sequence[int]], refs: Sequence[str],
               within: Sequence[str]) -> list[str] | None:
    """
    A shortest directed cycle in the strict beats relation, restricted to a set.

    Returned as the actual sequence a beats b beats c beats a, because "there is
    a cycle" is not a disclosure and "Repaint beats Lift, Lift beats Gate, Gate
    beats Repaint" is.
    """
    position = {ref: i for i, ref in enumerate(refs)}
    nodes = [position[r] for r in within]
    node_set = set(nodes)
    best: list[int] | None = None
    for start in nodes:
        # Breadth-first back to the start gives the shortest cycle through it.
        queue = [[start]]
        seen = {start}
        while queue:
            path = queue.pop(0)
            if best is not None and len(path) >= len(best):
                break
            tail = path[-1]
            for nxt in nodes:
                if nxt == tail or not _beats(matrix, tail, nxt):
                    continue
                if nxt == start and len(path) >= 3:
                    if best is None or len(path) < len(best):
                        best = list(path)
                    continue
                if nxt in seen or nxt not in node_set:
                    continue
                seen.add(nxt)
                queue.append(path + [nxt])
    if best is None:
        return None
    return [refs[i] for i in best]


def _matrix_checks(matrix, refs, excluded, truncated, n_ballots, unranked) -> list[Check]:
    ties = sum(
        1
        for i in range(len(refs))
        for j in range(i + 1, len(refs))
        if matrix[i][j] == matrix[j][i]
    )
    return [
        Check(
            id="ballot-validity",
            label="Ballots naming options that were not on the paper are excluded and counted",
            status="WARN" if excluded else "PASS",
            statistic=float(excluded),
            detail=(
                str(excluded) + " ballots named an option that was not on this decision's paper "
                "and were excluded. They are counted, never silently repaired."
            ) if excluded else "",
        ),
        Check(
            id="truncation-share",
            label="How many ballots ranked only some of the options",
            status="WARN" if n_ballots and truncated / n_ballots > 0.2 else "PASS",
            statistic=(truncated / n_ballots) if n_ballots else 0.0,
            detail=(
                str(truncated) + " of " + str(n_ballots) + " ballots ranked only some options. "
                "The unranked policy in force is " + repr(unranked) + " and it materially "
                "changes this matrix, which is why it is in params_hash."
            ) if truncated else "",
        ),
        Check(
            id="pairwise-ties",
            label="Exact head-to-head ties, which break naive implementations",
            status="WARN" if ties else "PASS",
            statistic=float(ties),
            detail=(
                str(ties) + " pairs of options tied exactly. A tie is not a win, and no rule "
                "here treats it as one."
            ) if ties else "",
        ),
    ]


# ---------------------------------------------------------------------------
# voting.pairwise_matrix
# ---------------------------------------------------------------------------


def pairwise_matrix(ballots, options, spec, *, unranked="last") -> Evidence:
    """voting.pairwise_matrix. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "voting.pairwise_matrix"
    phash = params_hash(method, 1, {
        "decision_ref": getattr(spec, "decision_ref", None), "unranked": unranked,
    })
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    refs, ranked, excluded, truncated = _prepare(ballots, options, unranked)
    n = len(ranked)
    if n < 1 or len(refs) < 2:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash,
            empty_value={"options": list(refs), "matrix": [], "margins": [],
                         "n_ballots": n, "n_truncated": truncated},
            caveats=("A pairwise matrix needs at least one valid ballot and two options.",),
        )

    matrix = pairwise_counts(ranked, refs)
    margins = [
        [matrix[i][j] - matrix[j][i] for j in range(len(refs))]
        for i in range(len(refs))
    ]

    return Evidence(
        value={
            "options": list(refs),
            "matrix": matrix,
            "margins": margins,
            "n_ballots": n,
            "n_truncated": truncated,
        },
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Ballots are rankings, with ties expressed as tiers.",
            "Unranked options are handled by the declared policy " + repr(unranked) + ".",
        ),
        checks=tuple(_matrix_checks(matrix, refs, excluded, truncated, n, unranked)),
        caveats=(
            "This is an exact count of the ballots cast. It says nothing about the people who "
            "did not vote; that is voting.turnout_representativeness and the two must not be "
            "conflated.",
        ),
        n_excluded=excluded,
        exclusion_reason=(
            "ballot named an option not on this decision's paper" if excluded else ""
        ),
        unit="ballots",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# voting.condorcet_winner
# ---------------------------------------------------------------------------


def _cycle_check(cycle: Sequence[str] | None, smith: Sequence[str]) -> Check:
    """
    The disclosure. Not blocking, and deliberately not an error: a cycle is a
    real property of the ballots, not a failure of the count.
    """
    if not cycle:
        return Check(
            id="condorcet-cycle-present",
            label="Whether the community's preferences cycle",
            status="PASS",
            statistic=0.0,
            blocking=False,
            detail="",
        )
    written = " beats ".join(list(cycle) + [cycle[0]])
    return Check(
        id="condorcet-cycle-present",
        label="Whether the community's preferences cycle",
        status="FAIL",
        statistic=float(len(cycle)),
        blocking=False,
        detail=(
            "There is no Condorcet winner because the preferences cycle: " + written + ". "
            "Any single winner shown for this decision is the output of a completion rule "
            "resolving that cycle, not an option the community preferred to every other. "
            "The Smith set, the smallest group that beats everything outside it, is "
            + ", ".join(smith) + "."
        ),
    )


def condorcet_winner(ballots, options, spec, *, unranked="last") -> Evidence:
    """voting.condorcet_winner. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "voting.condorcet_winner"
    phash = params_hash(method, 1, {
        "decision_ref": getattr(spec, "decision_ref", None), "unranked": unranked,
    })
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    refs, ranked, excluded, truncated = _prepare(ballots, options, unranked)
    n = len(ranked)
    if n < 1 or len(refs) < 2:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash,
            empty_value={"winner": None, "cycle": None, "smith_set": [], "matrix_ref": None},
            caveats=("Needs at least one valid ballot and two options.",),
        )

    matrix = pairwise_counts(ranked, refs)
    winner = None
    for i, ref in enumerate(refs):
        if all(_beats(matrix, i, j) for j in range(len(refs)) if j != i):
            winner = ref
            break

    smith = smith_set(matrix, refs)
    cycle = None if winner is not None else find_cycle(matrix, refs, smith)

    checks = [_cycle_check(cycle, smith)]
    checks.extend(_matrix_checks(matrix, refs, excluded, truncated, n, unranked))

    caveats = [
        "An exact combinatorial result on the ballots cast. There is no interval because "
        "there is nothing here being estimated.",
    ]
    if winner is None and cycle is None:
        caveats.append(
            "No option beat every other, and no strict cycle exists either: the top group ties "
            "somewhere. The Smith set is " + ", ".join(smith) + "."
        )
    if cycle:
        caveats.append(
            "This decision has no Condorcet winner. The cycle is shown above and must be "
            "displayed, in words, above any result produced by a completion rule."
        )

    return Evidence(
        value={
            "winner": winner,
            "cycle": list(cycle) if cycle else None,
            "smith_set": smith,
            "matrix_ref": params_hash("voting.pairwise_matrix", 1, {
                "decision_ref": getattr(spec, "decision_ref", None), "unranked": unranked,
            }),
        },
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Ballots are rankings.",
            "Unranked options are handled by the declared policy " + repr(unranked) + ".",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        n_excluded=excluded,
        exclusion_reason=(
            "ballot named an option not on this decision's paper" if excluded else ""
        ),
        unit="option",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# voting.schulze
# ---------------------------------------------------------------------------


def strongest_paths(matrix: Sequence[Sequence[int]]) -> list[list[int]]:
    """
    Schulze's widest-path strengths, by the Floyd-Warshall variant in his paper.

    p[i][j] starts at d[i][j] where i beats j and 0 otherwise, then
    p[i][j] = max(p[i][j], min(p[i][k], p[k][j])) over every intermediate k.
    """
    size = len(matrix)
    p = [[0] * size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            if i != j and matrix[i][j] > matrix[j][i]:
                p[i][j] = matrix[i][j]
    for k in range(size):
        for i in range(size):
            if i == k:
                continue
            for j in range(size):
                if j == i or j == k:
                    continue
                candidate = min(p[i][k], p[k][j])
                if candidate > p[i][j]:
                    p[i][j] = candidate
    return p


def schulze(ballots, options, spec, *, unranked="last", tie_break_seed=0) -> Evidence:
    """voting.schulze. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "voting.schulze"
    phash = params_hash(method, 1, {
        "decision_ref": getattr(spec, "decision_ref", None),
        "unranked": unranked, "tie_break_seed": tie_break_seed,
    })
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    refs, ranked, excluded, truncated = _prepare(ballots, options, unranked)
    n = len(ranked)
    if n < 1 or len(refs) < 2:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash,
            empty_value={"ranking": [], "strongest_paths": [], "winner": None,
                         "is_condorcet_winner": False, "cycle_disclosed": None},
            caveats=("Needs at least one valid ballot and two options.",),
        )

    matrix = pairwise_counts(ranked, refs)
    paths = strongest_paths(matrix)
    size = len(refs)

    # Schulze's binary relation, then a total order from it. Ties in the
    # beatpath relation are broken by the declared seeded rule and disclosed.
    wins = [sum(1 for j in range(size) if j != i and paths[i][j] > paths[j][i])
            for i in range(size)]
    rng = random.Random(tie_break_seed)
    jitter = {ref: rng.random() for ref in refs}
    order = sorted(range(size), key=lambda i: (-wins[i], jitter[refs[i]], refs[i]))
    ranking = [refs[i] for i in order]
    winner = ranking[0]

    tied = sorted({wins[i] for i in range(size)})
    n_tied_groups = sum(1 for w in tied if sum(1 for i in range(size) if wins[i] == w) > 1)

    condorcet = None
    for i, ref in enumerate(refs):
        if all(_beats(matrix, i, j) for j in range(size) if j != i):
            condorcet = ref
            break
    smith = smith_set(matrix, refs)
    cycle = None if condorcet is not None else find_cycle(matrix, refs, smith)

    checks = [_cycle_check(cycle, smith)]
    checks.append(Check(
        id="schulze-tie",
        label="Whether the beatpath relation left a tie for the declared rule to break",
        status="WARN" if n_tied_groups else "PASS",
        statistic=float(n_tied_groups),
        detail=(
            str(n_tied_groups) + " groups of options were exactly level on beatpaths and were "
            "ordered by the declared seeded tie-break (seed " + str(tie_break_seed) + "), which "
            "is in params_hash so the count can be reproduced identically."
        ) if n_tied_groups else "",
    ))
    checks.extend(_matrix_checks(matrix, refs, excluded, truncated, n, unranked))

    caveats = []
    if cycle:
        caveats.append(
            "The winner shown is the RESOLUTION OF A CYCLE, not a Condorcet winner. No option "
            "beat every other head to head. The cycle is " + " beats ".join(list(cycle) + [cycle[0]])
            + " and it must be displayed alongside this result."
        )
    else:
        caveats.append(
            "The Schulze winner here is also the Condorcet winner: it beat every other option "
            "head to head."
        )
    declared = getattr(spec, "declared_rule", None)
    if declared and declared != "schulze":
        caveats.append(
            "Schulze was not this decision's declared rule (" + str(declared) + "). This result "
            "is shown for sensitivity only; the declared rule's result is the binding one."
        )

    return Evidence(
        value={
            "ranking": ranking,
            "strongest_paths": paths,
            "winner": winner,
            "is_condorcet_winner": bool(condorcet is not None and condorcet == winner),
            "cycle_disclosed": list(cycle) if cycle else None,
            "options": list(refs),
        },
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The declared rule was Schulze before ballots were cast (spine rule D1).",
            "Unranked options are handled by the declared policy " + repr(unranked) + ".",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        n_excluded=excluded,
        exclusion_reason=(
            "ballot named an option not on this decision's paper" if excluded else ""
        ),
        unit="option",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# voting.borda, voting.approval, voting.score
# ---------------------------------------------------------------------------


def borda(ballots, options, spec, *, unranked="last") -> Evidence:
    """voting.borda. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "voting.borda"
    phash = params_hash(method, 1, {
        "decision_ref": getattr(spec, "decision_ref", None), "unranked": unranked,
    })
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    refs, ranked, excluded, truncated = _prepare(ballots, options, unranked)
    n = len(ranked)
    size = len(refs)
    if n < 1 or size < 2:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=[],
            caveats=("Needs at least one valid ballot and two options.",),
        )

    # Tournament-style Borda: an option scores, from each ballot, the number of
    # options it is ranked above, with half a point for each it ties. That is
    # exactly the classic m-1, m-2, ... scale on a strict ballot and it extends
    # to tiers and truncation without a special case.
    points = {ref: 0.0 for ref in refs}
    for positions in ranked:
        for i, a in enumerate(refs):
            pa = positions.get(a)
            if pa is None:
                continue
            for j, b in enumerate(refs):
                if i == j:
                    continue
                pb = positions.get(b)
                if pb is None:
                    continue
                if pa < pb:
                    points[a] += 1.0
                elif pa == pb:
                    points[a] += 0.5

    ordered = sorted(refs, key=lambda r: (-points[r], r))
    rows = [
        {"option": ref, "points": points[ref], "mean_points": points[ref] / n,
         "rank": index + 1, "n": n}
        for index, ref in enumerate(ordered)
    ]

    checks = _matrix_checks(
        pairwise_counts(ranked, refs), refs, excluded, truncated, n, unranked
    )
    declared = getattr(spec, "declared_rule", None)
    caveats = [
        "Borda is shown for sensitivity: how much the outcome depends on the rule. "
        + ("It is this decision's declared rule." if declared == "borda"
           else "The declared rule for this decision is " + str(declared) + " and that result "
                "is the binding one."),
        "Borda rewards broad acceptability rather than first preferences, so it can differ from "
        "the plurality winner even when it agrees with the Condorcet winner.",
    ]

    return Evidence(
        value=rows,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Ties within a ballot split the point between the tied options.",
            "Unranked options are handled by the declared policy " + repr(unranked) + ".",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        n_excluded=excluded,
        exclusion_reason=(
            "ballot named an option not on this decision's paper" if excluded else ""
        ),
        unit="borda points",
        params_hash=phash,
    )


def approval(ballots, options, spec) -> Evidence:
    """voting.approval. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "voting.approval"
    phash = params_hash(method, 1, {"decision_ref": getattr(spec, "decision_ref", None)})
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    refs = _option_refs(options)
    known = set(refs)
    counts = {ref: 0 for ref in refs}
    n = 0
    excluded = 0
    abstentions = 0
    for ballot in ballots:
        approvals = set(getattr(ballot, "approvals", frozenset()) or frozenset())
        if approvals - known:
            excluded += 1
            continue
        n += 1
        if not approvals:
            abstentions += 1
        for ref in approvals:
            counts[ref] += 1

    if n < 1 or len(refs) < 2:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=[],
            caveats=("Needs at least one valid ballot and two options.",),
        )

    ordered = sorted(refs, key=lambda r: (-counts[r], r))
    rows = []
    for index, ref in enumerate(ordered):
        lo, hi = wilson_interval(counts[ref], n)
        rows.append({
            "option": ref, "approvals": counts[ref], "share": counts[ref] / n,
            "share_lo": lo, "share_hi": hi, "rank": index + 1, "n": n,
        })

    return Evidence(
        value=rows,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "An approval is a genuine statement of support rather than a strategic bundle.",
            "A blank ballot is an abstention and is counted as a cast ballot with no approvals.",
        ),
        checks=(
            Check(
                id="ballot-validity",
                label="Ballots approving options not on the paper are excluded and counted",
                status="WARN" if excluded else "PASS",
                statistic=float(excluded),
                detail=(str(excluded) + " ballots approved an option not on this paper.")
                if excluded else "",
            ),
            Check(
                id="abstention-share",
                label="How many cast ballots approved nothing",
                status="WARN" if abstentions / n > 0.1 else "PASS",
                statistic=abstentions / n,
                detail=(
                    str(abstentions) + " of " + str(n) + " ballots approved no option. They are "
                    "counted in the denominator, which is what makes the share readable."
                ) if abstentions else "",
            ),
        ),
        caveats=(
            "The counts are exact. The per-option share interval is a Wilson interval on the "
            "share of BALLOTS CAST, and is only about the electorate if turnout was high.",
        ),
        n_excluded=excluded,
        exclusion_reason=("ballot approved an option not on the paper" if excluded else ""),
        unit="approvals",
        params_hash=phash,
    )


def score(ballots, options, spec) -> Evidence:
    """voting.score. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "voting.score"
    phash = params_hash(method, 1, {"decision_ref": getattr(spec, "decision_ref", None)})
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    refs = _option_refs(options)
    known = set(refs)
    totals = {ref: 0.0 for ref in refs}
    scored = {ref: 0 for ref in refs}
    n = 0
    excluded = 0
    for ballot in ballots:
        scores = dict(getattr(ballot, "scores", {}) or {})
        if set(scores) - known:
            excluded += 1
            continue
        n += 1
        for ref, value in scores.items():
            totals[ref] += float(value)
            scored[ref] += 1

    if n < 1 or len(refs) < 2:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=[],
            caveats=("Needs at least one valid ballot and two options.",),
        )

    ordered = sorted(refs, key=lambda r: (-totals[r], r))
    rows = [
        {"option": ref, "total_score": totals[ref], "n_scored": scored[ref],
         "mean_score_of_scorers": (totals[ref] / scored[ref]) if scored[ref] else None,
         "mean_score_of_all_ballots": totals[ref] / n,
         "rank": index + 1, "n": n}
        for index, ref in enumerate(ordered)
    ]

    partial = sum(1 for ref in refs if scored[ref] < n)
    return Evidence(
        value=rows,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The score scale means the same thing to every voter, which is the assumption "
            "score voting rests on and cannot check.",
            "An unscored option is treated as unscored, not as a zero. Both readings are "
            "reported so the difference is visible.",
        ),
        checks=(
            Check(
                id="ballot-validity",
                label="Ballots scoring options not on the paper are excluded and counted",
                status="WARN" if excluded else "PASS",
                statistic=float(excluded),
                detail=(str(excluded) + " ballots scored an option not on this paper.")
                if excluded else "",
            ),
            Check(
                id="partial-scoring",
                label="Options that some ballots left unscored",
                status="WARN" if partial else "PASS",
                statistic=float(partial),
                detail=(
                    str(partial) + " options were left unscored by some ballots, so the mean "
                    "over scorers and the mean over all ballots differ. Both are in the table "
                    "because choosing one silently is choosing the winner."
                ) if partial else "",
            ),
        ),
        caveats=(
            "Score voting has no interval here: the totals are exact counts of what was cast.",
        ),
        n_excluded=excluded,
        exclusion_reason=("ballot scored an option not on the paper" if excluded else ""),
        unit="score points",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# voting.stv
# ---------------------------------------------------------------------------


def stv(ballots, options, spec, *, seats, tie_break_seed, quota="droop",
        transfer="gregory") -> Evidence:
    """voting.stv. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "voting.stv"
    phash = params_hash(method, 1, {
        "decision_ref": getattr(spec, "decision_ref", None), "seats": seats,
        "quota": quota, "transfer": transfer, "tie_break_seed": tie_break_seed,
    })
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    if transfer != "gregory":
        raise ValueError(
            "voting.stv implements the Gregory (ERS97) fractional transfer. Meek's method "
            "reweights every ballot at every stage and needs an iterative solve; it is "
            "specified in docs/STATS_CATALOG.md and is not implemented here. Naming the limit "
            "beats quietly running a different transfer rule than the one declared."
        )

    refs = _option_refs(options)
    ranked: list[list[str]] = []
    excluded = 0
    known = set(refs)
    for ballot in ballots:
        order: list[str] = []
        invalid = False
        for tier in getattr(ballot, "ranking", ()) or ():
            # A tie inside an STV ballot cannot be transferred without inventing
            # a preference, so a tied tier ends the usable part of the ballot.
            if len(tier) != 1:
                break
            if tier[0] not in known:
                invalid = True
                break
            order.append(tier[0])
        if invalid:
            excluded += 1
            continue
        ranked.append(order)

    n = len(ranked)
    if n < max(seats, 1) or len(refs) < seats + 1:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash,
            empty_value={"elected": [], "rounds": [], "quota": None},
            caveats=(
                "An STV count needs at least " + str(seats + 1) + " options and " + str(seats)
                + " valid ballots; it has " + str(len(refs)) + " and " + str(n) + ".",
            ),
        )

    if quota == "droop":
        quota_value = math.floor(n / (seats + 1)) + 1
    elif quota == "hare":
        quota_value = n / seats
    else:
        raise ValueError("voting.stv quota must be 'droop' or 'hare', got " + repr(quota))

    rng = random.Random(tie_break_seed)
    jitter = {ref: rng.random() for ref in refs}

    # Each ballot is a (weight, order, cursor). Gregory transfers scale weight.
    papers = [[1.0, order, 0] for order in ranked]
    elected: list[str] = []
    eliminated: list[str] = []
    continuing = list(refs)
    rounds: list[dict[str, Any]] = []
    tie_breaks = 0
    exhausted_weight = 0.0

    def advance(paper) -> str | None:
        weight, order, cursor = paper
        while cursor < len(order):
            candidate = order[cursor]
            if candidate in continuing:
                paper[2] = cursor
                return candidate
            cursor += 1
        paper[2] = cursor
        return None

    def tally() -> dict[str, float]:
        counts = {ref: 0.0 for ref in continuing}
        nonlocal exhausted_weight
        exhausted_weight = 0.0
        for paper in papers:
            target = advance(paper)
            if target is None:
                exhausted_weight += paper[0]
            else:
                counts[target] += paper[0]
        return counts

    round_number = 0
    while len(elected) < seats and continuing:
        round_number += 1
        counts = tally()
        elected_this_round: list[str] = []
        eliminated_this_round: str | None = None
        transfers: dict[str, float] = {}

        if len(elected) + len(continuing) <= seats:
            # Everyone still standing is needed to fill the seats.
            for ref in sorted(continuing, key=lambda r: (-counts[r], jitter[r], r)):
                elected.append(ref)
                elected_this_round.append(ref)
            continuing = []
            rounds.append({
                "round": round_number,
                "counts": {r: counts[r] for r in sorted(counts)},
                "elected_this_round": elected_this_round,
                "eliminated": None,
                "transfers": {},
                "exhausted": exhausted_weight,
                "reason": "as many candidates remained as seats, so all were elected",
            })
            break

        over_quota = [r for r in continuing if counts[r] >= quota_value]
        if over_quota:
            best = max(counts[r] for r in over_quota)
            leaders = [r for r in over_quota if counts[r] == best]
            if len(leaders) > 1:
                tie_breaks += 1
            chosen = sorted(leaders, key=lambda r: (jitter[r], r))[0]
            elected.append(chosen)
            elected_this_round.append(chosen)
            continuing = [r for r in continuing if r != chosen]
            surplus = counts[chosen] - quota_value
            ratio = surplus / counts[chosen] if counts[chosen] > 0 else 0.0
            for paper in papers:
                if paper[2] < len(paper[1]) and paper[1][paper[2]] == chosen:
                    paper[0] *= ratio
                    paper[2] += 1
            transfers = {"from": chosen, "surplus": surplus, "ratio": ratio}
        else:
            worst = min(counts[r] for r in continuing)
            trailers = [r for r in continuing if counts[r] == worst]
            if len(trailers) > 1:
                tie_breaks += 1
            chosen = sorted(trailers, key=lambda r: (jitter[r], r))[0]
            eliminated.append(chosen)
            eliminated_this_round = chosen
            continuing = [r for r in continuing if r != chosen]
            for paper in papers:
                if paper[2] < len(paper[1]) and paper[1][paper[2]] == chosen:
                    paper[2] += 1
            transfers = {"from": chosen, "votes": worst, "ratio": 1.0}

        rounds.append({
            "round": round_number,
            "counts": {r: counts[r] for r in sorted(counts)},
            "elected_this_round": elected_this_round,
            "eliminated": eliminated_this_round,
            "transfers": transfers,
            "exhausted": exhausted_weight,
            "reason": "",
        })

    final_counts = rounds[-1]["counts"] if rounds else {}
    below_quota = [
        r for r in elected
        if not any(
            rd["counts"].get(r, 0.0) >= quota_value
            for rd in rounds
            if r in rd["elected_this_round"]
        )
    ]
    exhausted_share = exhausted_weight / n if n else 0.0

    checks = [
        Check(
            id="quota-reached",
            label="Whether every elected candidate actually reached the quota",
            status="WARN" if below_quota else "PASS",
            statistic=float(len(below_quota)),
            detail=(
                ", ".join(below_quota) + " were elected without reaching the quota of "
                + repr(quota_value) + ", because as many candidates remained as seats. This is "
                "normal in an STV count and is labelled rather than hidden."
            ) if below_quota else "",
        ),
        Check(
            id="tie-break-invoked",
            label="Whether the declared seeded tie-break decided anything",
            status="WARN" if tie_breaks else "PASS",
            statistic=float(tie_breaks),
            detail=(
                "The tie-break was invoked " + str(tie_breaks) + " times. Seed "
                + str(tie_break_seed) + " is in params_hash, so a contested election recounts "
                "identically."
            ) if tie_breaks else "",
        ),
        Check(
            id="exhausted-ballots",
            label="Share of ballots exhausted before the last seat was filled",
            status="WARN" if exhausted_share > 0.1 else "PASS",
            statistic=exhausted_share,
            detail=(
                "{:.1%}".format(exhausted_share) + " of the ballot weight was exhausted. This is "
                "the quality measure for an STV count: a heavily truncated electorate leaves the "
                "last seat to a small remnant."
            ) if exhausted_share > 0 else "",
        ),
        Check(
            id="ballot-validity",
            label="Ballots naming options not on the paper are excluded and counted",
            status="WARN" if excluded else "PASS",
            statistic=float(excluded),
            detail=(str(excluded) + " ballots named an option not on this paper.")
            if excluded else "",
        ),
    ]

    return Evidence(
        value={
            "elected": elected,
            "rounds": rounds,
            "quota": quota_value,
            "quota_rule": quota,
            "transfer": transfer,
            "eliminated_order": eliminated,
            "final_counts": final_counts,
        },
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The transfer method and quota were declared in advance and have not changed.",
            "Ties are broken by the declared seeded rule, disclosed every time it fires.",
        ),
        checks=tuple(checks),
        caveats=(
            "Every round is returned because in an STV election the count IS the "
            "accountability, not a working step towards it.",
            "STV is non-monotonic, so a confidence interval on this result would be meaningless "
            "even in principle. There is none.",
        ),
        n_excluded=excluded,
        exclusion_reason=("ballot named an option not on the paper" if excluded else ""),
        unit="seats",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# voting.turnout_representativeness
# ---------------------------------------------------------------------------


def _stratum_key(strata: Mapping[str, str]) -> tuple[str, ...]:
    """A ballot's stratum as a tuple, ordered by field name so it matches the roster's."""
    return tuple(str(strata[name]) for name in sorted(strata))


def _quorum(rule: str | None, n_ballots: int, eligible: int) -> tuple[bool | None, str]:
    if not rule or rule == "none":
        return None, "no quorum rule was declared for this decision"
    if rule.startswith("fraction:"):
        needed = float(rule.split(":", 1)[1]) * eligible
        return n_ballots >= needed, "needs " + "{:.0f}".format(needed) + " ballots"
    if rule.startswith("count:"):
        needed = float(rule.split(":", 1)[1])
        return n_ballots >= needed, "needs " + "{:.0f}".format(needed) + " ballots"
    return None, "quorum rule " + repr(rule) + " is not one this service understands"


def turnout_representativeness(ballots, spec, roster, *, k_anonymity=5) -> Evidence:
    """voting.turnout_representativeness. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "voting.turnout_representativeness"
    phash = params_hash(method, 1, {
        "decision_ref": getattr(spec, "decision_ref", None), "k_anonymity": k_anonymity,
    })
    as_of = getattr(spec, "closed_at", None) or getattr(spec, "opened_at", None)

    eligible_by_stratum = dict(getattr(spec, "eligible_strata", {}) or {})
    if not eligible_by_stratum:
        eligible_by_stratum = dict(getattr(roster, "counts_by_stratum", {}) or {})
    eligible_total = int(getattr(roster, "total", 0)) or sum(eligible_by_stratum.values())

    voters: dict[tuple[str, ...], int] = {}
    n = 0
    for ballot in ballots:
        n += 1
        voters[_stratum_key(getattr(ballot, "strata", {}) or {})] = (
            voters.get(_stratum_key(getattr(ballot, "strata", {}) or {}), 0) + 1
        )

    empty = {"turnout": None, "turnout_lo": None, "turnout_hi": None, "by_stratum": [],
             "chi_square": None, "p_value": None, "design_effect_if_weighted": None,
             "n_eligible": eligible_total}
    if n < MIN_TURNOUT_BALLOTS or eligible_total <= 0:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="share",
            caveats=(
                "Needs " + str(MIN_TURNOUT_BALLOTS) + " ballots and a non-empty eligible roll; "
                "has " + str(n) + " and " + str(eligible_total) + ".",
            ),
        )

    turnout = n / eligible_total
    lo, hi = wilson_interval(n, eligible_total)

    keys = sorted(set(eligible_by_stratum) | set(voters))
    rows = []
    chi_square = 0.0
    df = 0
    for key in keys:
        eligible = int(eligible_by_stratum.get(key, 0))
        cast = int(voters.get(key, 0))
        expected = eligible * turnout
        if eligible > 0:
            row_lo, row_hi = wilson_interval(cast, eligible)
            row_turnout = cast / eligible
        else:
            row_lo = row_hi = row_turnout = None
        if expected > 0:
            chi_square += (cast - expected) ** 2 / expected
            df += 1
        suppressed = cast < k_anonymity or (0 < eligible < k_anonymity)
        rows.append({
            "stratum": ":".join(key) if key else "unstated",
            "n_eligible": None if suppressed else eligible,
            "n_voted": None if suppressed else cast,
            "turnout": None if suppressed else row_turnout,
            "lo": None if suppressed else row_lo,
            "hi": None if suppressed else row_hi,
            "n": None if suppressed else cast,
            "suppressed": suppressed,
        })
    df = max(df - 1, 0)
    p_value = chi2_sf(chi_square, df) if df > 0 else None

    n_suppressed = sum(1 for r in rows if r["suppressed"])
    quorum_met, quorum_detail = _quorum(getattr(spec, "quorum_rule", None), n, eligible_total)
    low_turnout = turnout < LOW_TURNOUT_THRESHOLD

    # Kish design effect if the sample were post-stratified back to the roll.
    deff = None
    weights: list[float] = []
    for key in keys:
        cast = int(voters.get(key, 0))
        eligible = int(eligible_by_stratum.get(key, 0))
        if cast > 0 and eligible > 0:
            weights.extend([eligible / cast] * cast)
    if weights:
        total = math.fsum(weights)
        deff = len(weights) * math.fsum(w * w for w in weights) / (total * total)

    checks = [
        Check(
            id="quorum-met",
            label="Whether the decision reached its declared quorum",
            status="PASS" if quorum_met else ("SKIPPED" if quorum_met is None else "FAIL"),
            statistic=float(n),
            blocking=False,
            detail=(
                "Quorum was NOT reached (" + quorum_detail + ", " + str(n) + " cast). The "
                "tabulation below is still correct and is shown; what cannot be said is that "
                "this decision is binding."
            ) if quorum_met is False else (quorum_detail if quorum_met is None else ""),
        ),
        Check(
            id="low-turnout-generalisation",
            label="Whether the result may be read as the community's view",
            status="FAIL" if low_turnout else "PASS",
            statistic=turnout,
            blocking=False,
            detail=(
                "Turnout was " + "{:.1%}".format(turnout) + ", below the "
                + "{:.0%}".format(LOW_TURNOUT_THRESHOLD) + " floor. This result describes the "
                "people who voted and must not be phrased as a community preference. The "
                "tabulation is shown; the generalisation is what is refused."
            ) if low_turnout else "",
        ),
        Check(
            id="strata-representative",
            label="Whether voters look like the eligible population",
            status="PASS" if (p_value is None or p_value >= 0.05) else "FAIL",
            statistic=chi_square,
            p_value=p_value,
            blocking=False,
            detail=(
                "Turnout differed significantly across strata (chi-square "
                + "{:.2f}".format(chi_square) + " on " + str(df) + " df, p = "
                + "{:.4f}".format(p_value) + "). The voters are not a scale model of the "
                "electorate, so any population claim needs survey.raking_weights and the "
                "design effect alongside it."
            ) if (p_value is not None and p_value < 0.05) else "",
        ),
        Check(
            id="k-anonymity-cells",
            label="No stratum row is small enough to identify a household",
            status="FAIL" if n_suppressed else "PASS",
            statistic=float(k_anonymity),
            blocking=False,
            detail=(
                str(n_suppressed) + " stratum rows covered fewer than " + str(k_anonymity)
                + " people and are emptied. There is no admin override: a per-block vote "
                "breakdown over a handful of households identifies those households."
            ) if n_suppressed else "",
        ),
    ]

    caveats = [
        "The turnout interval is a Wilson interval on the share of the eligible roll that "
        "voted. The chi-square has no interval, because a p-value is not one.",
    ]
    if deff is not None and deff > 2.0:
        caveats.append(
            "Post-stratifying this sample back to the roll would give a design effect of "
            + "{:.2f}".format(deff) + ", so the effective sample size is about "
            + "{:.0f}".format(n / deff) + ", not " + str(n) + "."
        )

    return Evidence(
        value={
            "turnout": turnout,
            "turnout_lo": lo,
            "turnout_hi": hi,
            "by_stratum": rows,
            "chi_square": chi_square,
            "df": df,
            "p_value": p_value,
            "design_effect_if_weighted": deff,
            "n_eligible": eligible_total,
        },
        n=n,
        method=method,
        as_of=as_of,
        interval=(lo, hi),
        interval_kind="normal-95",
        assumptions=(
            "The eligible frame was frozen at opened_at and is accurate, so a later move-in "
            "cannot change a past turnout figure.",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        unit="share of eligible",
        params_hash=phash,
    )


__all__ = [
    "approval",
    "borda",
    "condorcet_winner",
    "find_cycle",
    "pairwise_counts",
    "pairwise_matrix",
    "schulze",
    "score",
    "smith_set",
    "strongest_paths",
    "stv",
    "turnout_representativeness",
]
