"""
Paired-comparison models over head-to-heads, matches and ballots.

Two services with one relationship worth stating up front. Bradley-Terry fits one
fixed ability per item over the whole window and gives it an interval. Elo is a
filter: it tracks an ability that moves, and it has no interval, because a
recursively updated rating has no sampling distribution to report. Where both are
defensible, the choice is about whether strength changed, and the Method Cards say
so in those words.

The connectivity check is the reason this module exists rather than a twenty-line
win-rate table. If the comparison graph is disconnected, the abilities in two
components are not on one scale, and every implementation that skips the check
still prints a ranking across them.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import chi2_ppf, norm_cdf

MIN_ITEMS = 5
MIN_COMPARISONS = 30
MM_MAX_ITER = 5000
MM_TOL = 1e-12
ELO_SCALE = 400.0


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _read_results(results: Sequence[Any]):
    """
    (winner, loser, drawn, first_position, at) per comparison, in input order.

    A draw is carried as a flag rather than silently dropped or counted as a win,
    because both of those are decisions and neither is the caller's.
    """
    out = []
    for r in results:
        winner = _get(r, "winner_ref")
        loser = _get(r, "loser_ref")
        if winner is None or loser is None:
            raise ValueError("a PairwiseResult needs winner_ref and loser_ref; got " + repr(r))
        out.append(
            (
                str(winner),
                str(loser),
                bool(_get(r, "drawn", False)),
                _get(r, "first_position_ref"),
                _get(r, "at"),
            )
        )
    return out


def _derive_as_of(rows, as_of):
    if as_of is not None:
        return as_of
    stamps = [r[4] for r in rows if r[4] is not None]
    if not stamps:
        raise ValueError(
            "as_of could not be derived: these comparisons carry no timestamp, so the caller "
            "must pass as_of. Nothing in app/stats reads a clock (spine rule S6)."
        )
    return max(stamps)


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------


def _components(items: Sequence[str], pairs) -> list[list[str]]:
    """Connected components of the comparison graph, each sorted, in size order."""
    index = {item: i for i, item in enumerate(items)}
    parent = list(range(len(items)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(index[a]), find(index[b])
        if ra != rb:
            parent[ra] = rb

    groups: dict[int, list[str]] = {}
    for item in items:
        groups.setdefault(find(index[item]), []).append(item)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g[0]))


def _tiers(items: Sequence[str], rows) -> list[list[str]]:
    """
    Ford's condition, made concrete: the strongly connected components of the
    dominance digraph, in topological order.

    Ford (1957) and Hunter (2004): the Bradley-Terry maximum likelihood estimate
    is finite if and only if, for every way of splitting the items into two
    groups, someone in each group has beaten someone in the other. That is
    exactly the statement that the digraph "i beat j at least once" is strongly
    connected. When it is not, the likelihood has no interior maximum and every
    ability runs off to an infinity: an undefeated item is only the most obvious
    case of it, not the whole of it.

    What IS identified when the condition fails is the order of the components,
    since the results say a whole tier beat a whole tier without exception. That
    partial order is what this returns, so the service can publish the ordering
    it has rather than a number it does not.
    """
    successors: dict[str, set[str]] = {i: set() for i in items}
    predecessors: dict[str, set[str]] = {i: set() for i in items}
    for winner, loser, drawn, _first, _at in rows:
        pairs = ((winner, loser), (loser, winner)) if drawn else ((winner, loser),)
        for a, b in pairs:
            successors[a].add(b)
            predecessors[b].add(a)

    order: list[str] = []
    seen: set[str] = set()
    for start in sorted(items):
        if start in seen:
            continue
        stack = [(start, iter(sorted(successors[start])))]
        seen.add(start)
        while stack:
            node, children = stack[-1]
            advanced = False
            for child in children:
                if child not in seen:
                    seen.add(child)
                    stack.append((child, iter(sorted(successors[child]))))
                    advanced = True
                    break
            if not advanced:
                order.append(stack.pop()[0])

    assigned: dict[str, int] = {}
    components: list[list[str]] = []
    for node in reversed(order):
        if node in assigned:
            continue
        label = len(components)
        group = []
        stack = [node]
        assigned[node] = label
        while stack:
            current = stack.pop()
            group.append(current)
            for previous in sorted(predecessors[current]):
                if previous not in assigned:
                    assigned[previous] = label
                    stack.append(previous)
        components.append(sorted(group))

    # Kosaraju's reverse post-order already yields the components in topological
    # order of the condensation, which for this graph means strongest tier first.
    return components


# ---------------------------------------------------------------------------
# The MM fit (Hunter 2004)
# ---------------------------------------------------------------------------


def _tallies(rows, items):
    """wins[i] as a float (a draw is half a win each) and n[i][j] comparison counts."""
    wins = {i: 0.0 for i in items}
    counts: dict[str, dict[str, float]] = {i: {} for i in items}
    for winner, loser, drawn, _first, _at in rows:
        if drawn:
            wins[winner] += 0.5
            wins[loser] += 0.5
        else:
            wins[winner] += 1.0
        counts[winner][loser] = counts[winner].get(loser, 0.0) + 1.0
        counts[loser][winner] = counts[loser].get(winner, 0.0) + 1.0
    return wins, counts


def _mm_fit(items, wins, counts, *, penalizer, fixed=None):
    """
    Hunter's MM iteration: p_i <- w_i / sum_j n_ij / (p_i + p_j).

    `penalizer` adds that many pseudo-wins and pseudo-losses against a virtual
    opponent of ability 1 to every item. It is the standard ridge for this model
    and it is what keeps an undefeated item finite; at 0.0 the iteration is the
    unpenalised MLE and an undefeated item diverges, which the separation check
    catches rather than hides.

    `fixed` is a mapping of item to log-ability that the iteration holds still.
    It must pin at least TWO items to mean anything, and that is not a detail:
    the model is invariant to rescaling every ability at once, so pinning one
    item constrains nothing and the "profile" likelihood comes out exactly flat.
    The profile below therefore pins the reference at zero as well as the item it
    is profiling, which makes the interval an interval on the DIFFERENCE, which
    is the only thing the model identifies anyway.
    """
    p = {i: 1.0 for i in items}
    held = dict(fixed or {})
    for name, log_ability in held.items():
        p[name] = math.exp(log_ability)
    for _ in range(MM_MAX_ITER):
        moved = 0.0
        new = dict(p)
        for i in items:
            if i in held:
                continue
            denominator = math.fsum(
                n_ij / (p[i] + p[j]) for j, n_ij in counts[i].items()
            )
            if penalizer > 0.0:
                denominator += 2.0 * penalizer / (p[i] + 1.0)
            numerator = wins[i] + penalizer
            if denominator <= 0.0:
                continue
            value = numerator / denominator
            moved = max(moved, abs(math.log(max(value, 1e-300)) - math.log(max(p[i], 1e-300))))
            new[i] = value
        p = new
        if not held:
            # Only differences are identified, so renormalise to keep the scale put.
            geo = math.exp(math.fsum(math.log(max(v, 1e-300)) for v in p.values()) / len(p))
            p = {i: v / geo for i, v in p.items()}
        if moved < MM_TOL:
            break
    return p


def _loglik(rows, p, *, penalizer):
    total = 0.0
    for winner, loser, drawn, _first, _at in rows:
        pw, pl = max(p[winner], 1e-300), max(p[loser], 1e-300)
        if drawn:
            total += 0.5 * math.log(pw / (pw + pl)) + 0.5 * math.log(pl / (pw + pl))
        else:
            total += math.log(pw / (pw + pl))
    if penalizer > 0.0:
        for i, v in p.items():
            total += penalizer * (math.log(max(v, 1e-300)) - 2.0 * math.log(v + 1.0))
    return total


def _profile_interval(
    rows, items, wins, counts, item, anchor, centre, peak, *, penalizer, alpha
):
    """
    Profile-likelihood interval on one log-ability, on the reference's scale.

    The nuisance abilities are re-maximised at every candidate value, which is
    what distinguishes a profile interval from a Wald one; on this likelihood the
    two differ visibly for an item with few comparisons, which is exactly the
    item a reader is most likely to over-read.
    """
    cut = 0.5 * chi2_ppf(1.0 - alpha, 1)

    def profile(value: float) -> float:
        p = _mm_fit(
            items, wins, counts, penalizer=penalizer, fixed={anchor: 0.0, item: value}
        )
        return _loglik(rows, p, penalizer=penalizer)

    def hunt(direction: int) -> float | None:
        lo, hi = centre, centre
        step = 0.25
        for _ in range(40):
            hi = centre + direction * step
            if peak - profile(hi) >= cut:
                break
            lo = hi
            step *= 1.7
            if step > 60.0:
                return None
        else:
            return None
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            if peak - profile(mid) < cut:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    return hunt(-1), hunt(1)


def _intransitive_share(items, rows):
    """Share of comparison triads whose majority outcomes cycle."""
    beats: dict[tuple[str, str], float] = {}
    for winner, loser, drawn, _f, _a in rows:
        if drawn:
            beats[(winner, loser)] = beats.get((winner, loser), 0.0) + 0.5
            beats[(loser, winner)] = beats.get((loser, winner), 0.0) + 0.5
        else:
            beats[(winner, loser)] = beats.get((winner, loser), 0.0) + 1.0

    def dominates(a: str, b: str) -> bool:
        return beats.get((a, b), 0.0) > beats.get((b, a), 0.0)

    triads = 0
    cyclic = 0
    ordered = sorted(items)
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            for k in range(j + 1, len(ordered)):
                a, b, c = ordered[i], ordered[j], ordered[k]
                pairs = ((a, b), (b, c), (a, c))
                if not all(
                    beats.get(pair, 0.0) + beats.get(pair[::-1], 0.0) > 0 for pair in pairs
                ):
                    continue
                triads += 1
                if (dominates(a, b) and dominates(b, c) and dominates(c, a)) or (
                    dominates(b, a) and dominates(c, b) and dominates(a, c)
                ):
                    cyclic += 1
    return (cyclic / triads if triads else 0.0), triads


def bradley_terry(results, *, penalizer=0.0, reference=None, alpha=0.05, as_of=None) -> Evidence:
    """pairwise.bradley_terry. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method_id = "pairwise.bradley_terry"
    phash = params_hash(
        method_id, 1, {"penalizer": penalizer, "reference": reference, "alpha": alpha}
    )
    rows = _read_results(results)
    stamp = _derive_as_of(rows, as_of)
    items = sorted({r[0] for r in rows} | {r[1] for r in rows})

    if len(items) < MIN_ITEMS or len(rows) < MIN_COMPARISONS:
        return insufficient(
            method_id,
            n=len(rows),
            as_of=stamp,
            empty_value=[],
            unit="log-ability",
            params_hash=phash,
            caveats=(
                "Bradley-Terry needs " + str(MIN_ITEMS) + " items and " + str(MIN_COMPARISONS)
                + " comparisons; there are " + str(len(items)) + " and " + str(len(rows)) + ".",
            ),
        )

    components = _components(items, [(r[0], r[1]) for r in rows])
    connected = len(components) == 1

    wins, counts = _tallies(rows, items)

    table = []
    ford_holds = True
    for component in components:
        member = set(component)
        sub_rows = [r for r in rows if r[0] in member and r[1] in member]
        # Ford's condition, per component. Where it holds there is one tier and
        # the fit is the ordinary MLE; where it fails, only the order of the
        # tiers is identified and each tier is fitted on its own scale.
        tiers = _tiers(component, sub_rows)
        if len(tiers) > 1:
            ford_holds = False
        for tier_index, tier in enumerate(tiers):
            tier_member = set(tier)
            tier_rows = [r for r in sub_rows if r[0] in tier_member and r[1] in tier_member]
            tier_wins, tier_counts = _tallies(tier_rows, tier)
            fitted = (
                _mm_fit(tier, tier_wins, tier_counts, penalizer=penalizer)
                if len(tier) > 1 else {tier[0]: 1.0}
            )
            if reference is not None and reference in tier:
                anchor = reference
            else:
                anchor = tier[0]
            base = math.log(max(fitted[anchor], 1e-300))
            peak = _loglik(tier_rows, fitted, penalizer=penalizer) if len(tier) > 1 else 0.0
            for item in tier:
                played_here = int(math.fsum(counts[item].values()))
                row = {
                    "item_ref": item,
                    "ability": math.log(max(fitted[item], 1e-300)) - base,
                    "lo": None,
                    "hi": None,
                    "n_comparisons": played_here,
                    "n": played_here,
                    "wins": wins[item],
                    "losses": math.fsum(counts[item].values()) - wins[item],
                    "component": components.index(component),
                    "tier": tier_index,
                    "reference": anchor,
                    "label": "",
                    "separated": len(tiers) > 1,
                }
                if len(tiers) > 1 and penalizer <= 0.0:
                    # No finite ability exists on one scale for this component.
                    if len(tier) == 1:
                        row["ability"] = None
                        row["label"] = (
                            "no finite ability: this item's results separate it completely from "
                            "the rest (tier " + str(tier_index + 1) + " of " + str(len(tiers))
                            + "). What the data says is the tier, not a number."
                        )
                    else:
                        row["label"] = (
                            "ability is on tier " + str(tier_index + 1) + "'s own scale and is "
                            "not comparable with another tier's, because every member of this "
                            "tier beat every member of the tier below without exception."
                        )
                if row["ability"] is not None and len(tier) > 1 and item != anchor:
                    lo, hi = _profile_interval(
                        tier_rows, tier, tier_wins, tier_counts, item, anchor,
                        math.log(max(fitted[item], 1e-300)) - base, peak,
                        penalizer=penalizer, alpha=alpha,
                    )
                    row["lo"] = lo
                    row["hi"] = hi
                elif row["ability"] is not None and item == anchor:
                    row["lo"] = 0.0
                    row["hi"] = 0.0
                    row["label"] = row["label"] or (
                        "reference item: the scale's origin, fixed at zero by convention"
                    )
                table.append(row)

    # Unranked rows sort to the bottom of their tier rather than to either end of
    # the ordering, where they would read as a result.
    table.sort(
        key=lambda r: (
            r["component"],
            r["tier"],
            0 if r["ability"] is not None else 1,
            -(r["ability"] if r["ability"] is not None else 0.0),
            r["item_ref"],
        )
    )

    n_tiers = max(r["tier"] for r in table) + 1 if table else 0
    intransitive, triads = _intransitive_share(items, rows)

    # Order effect: how often the item in first position won, against what the
    # fitted abilities say should have happened.
    positioned = [r for r in rows if r[3] is not None and not r[2]]
    fitted = {r["item_ref"]: r["ability"] for r in table if r["ability"] is not None}
    order_status = "SKIPPED"
    order_stat = None
    order_p = None
    if len(positioned) >= 20 and fitted:
        observed = 0.0
        expected = 0.0
        variance = 0.0
        usable = 0
        for winner, loser, _drawn, first, _at in positioned:
            if first not in (winner, loser):
                continue
            if winner not in fitted or loser not in fitted:
                continue
            other = loser if first == winner else winner
            difference = fitted[first] - fitted[other]
            probability = 1.0 / (1.0 + math.exp(-difference))
            observed += 1.0 if first == winner else 0.0
            expected += probability
            variance += probability * (1.0 - probability)
            usable += 1
        if usable >= 20 and variance > 0:
            order_stat = (observed - expected) / math.sqrt(variance)
            order_p = 2.0 * (1.0 - norm_cdf(abs(order_stat)))
            order_status = "WARN" if order_p < 0.05 else "PASS"

    checks = [
        Check(
            id="connectivity",
            label="Every item lies in one connected comparison graph",
            status="PASS" if connected else "FAIL",
            statistic=float(len(components)),
            blocking=not connected,
            detail=(
                "The comparison graph has " + str(len(components)) + " components, so abilities "
                "in different components are not on one scale and cannot be ranked against each "
                "other. Per-component rankings are returned in `component`, and no single "
                "ordering is published."
            ) if not connected else "",
        ),
        Check(
            id="separation",
            label="The results pin every ability to a finite number (Ford's condition)",
            status="PASS" if ford_holds else ("WARN" if penalizer > 0.0 else "FAIL"),
            statistic=float(n_tiers),
            detail=(
                "" if ford_holds else
                (
                    "The results split into " + str(n_tiers) + " tiers that no result crosses in "
                    "both directions, so Ford's condition fails and no finite set of abilities "
                    "maximises the likelihood. The penalizer of "
                    + format(float(penalizer), ".3g") + " has produced finite numbers anyway, and "
                    "the size of those numbers is the penalty speaking, not the data."
                ) if penalizer > 0.0 else (
                    "The results split into " + str(n_tiers) + " tiers that no result crosses in "
                    "both directions: an undefeated item is the obvious case, but any such split "
                    "does it. Ford's condition fails, no finite set of abilities maximises the "
                    "likelihood, and a large number here would be an artefact of where the "
                    "optimiser stopped. The rows carry the TIER, which is what the results "
                    "actually determine, and abilities are on each tier's own scale."
                )
            ),
        ),
        Check(
            id="transitivity",
            label="Results are mostly transitive, so one ability per item can describe them",
            status="WARN" if intransitive > 0.1 else "PASS",
            statistic=intransitive,
            detail=(
                format(100.0 * intransitive, ".1f") + "% of the " + str(triads) + " observed "
                "triads cycle. A one-dimensional ability model is the wrong description of cyclic "
                "results, exactly as a linear preference order is the wrong description of a "
                "Condorcet cycle."
            ) if intransitive > 0.1 else "",
        ),
        Check(
            id="home-advantage",
            label="Being listed first does not by itself predict winning",
            status=order_status,
            statistic=order_stat,
            p_value=order_p,
            detail=(
                "Items in first position win more often than their fitted abilities explain "
                "(z = " + format(order_stat, ".2f") + "). The abilities are absorbing an order "
                "effect and are biased toward whoever tends to be listed first."
            ) if order_status == "WARN" else (
                "" if order_status == "PASS" else
                "Fewer than 20 comparisons carry a first position, so an order effect cannot be "
                "measured here."
            ),
        ),
    ]

    return Evidence(
        value=table,
        n=len(rows),
        method=method_id,
        as_of=stamp,
        interval_kind="profile-95",
        assumptions=(
            "A single latent ability per item.",
            "Comparison outcomes independent given the abilities.",
            "Abilities stable over the window; pairwise.elo_update is the service for when they "
            "are not.",
        ),
        checks=tuple(checks),
        caveats=(
            "Abilities are on a log scale RELATIVE to the reference item, whose ability is zero "
            "by construction. Only differences are identified, so the origin is arbitrary and a "
            "single ability read on its own means nothing.",
            "A difference of d in ability implies a win probability of 1/(1+exp(-d)) between the "
            "two items.",
        ) + (
            ("Ranked WITHIN component only. Two items in different components have never been "
             "compared, directly or transitively, and no ordering between them exists here.",)
            if not connected else ()
        ),
        unit="log-ability",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# pairwise.elo_update
# ---------------------------------------------------------------------------


def elo_expected(rating_a: float, rating_b: float) -> float:
    """The logistic expectation on Elo's base-10, 400-point scale."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / ELO_SCALE))


def elo_update(results, *, k_factor=32.0, initial=1500.0, as_of=None) -> Evidence:
    """pairwise.elo_update. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method_id = "pairwise.elo_update"
    phash = params_hash(method_id, 1, {"k_factor": k_factor, "initial": initial})
    rows = _read_results(results)
    stamp = _derive_as_of(rows, as_of)

    if not rows:
        return insufficient(
            method_id, n=0, as_of=stamp,
            empty_value={"ratings": [], "trajectory": []},
            unit="elo", params_hash=phash,
            caveats=("There are no comparisons to update from.",),
        )

    # Time order is the whole point of a filter, so it is enforced here rather
    # than assumed of the caller.
    stamped = [r for r in rows if r[4] is not None]
    out_of_order = any(
        stamped[i][4] > stamped[i + 1][4] for i in range(len(stamped) - 1)
    )
    ordered = sorted(rows, key=lambda r: (r[4] is None, r[4])) if stamped else list(rows)

    ratings: dict[str, float] = {}
    played: dict[str, int] = {}
    trajectory = []
    for step, (winner, loser, drawn, _first, at) in enumerate(ordered):
        ratings.setdefault(winner, float(initial))
        ratings.setdefault(loser, float(initial))
        played[winner] = played.get(winner, 0) + 1
        played[loser] = played.get(loser, 0) + 1
        expected_winner = elo_expected(ratings[winner], ratings[loser])
        score = 0.5 if drawn else 1.0
        delta = k_factor * (score - expected_winner)
        ratings[winner] += delta
        ratings[loser] -= delta
        trajectory.append(
            {
                "step": step,
                "at": at.isoformat() if hasattr(at, "isoformat") else None,
                "winner_ref": winner,
                "loser_ref": loser,
                "drawn": drawn,
                "expected_winner": expected_winner,
                "delta": delta,
                "winner_rating": ratings[winner],
                "loser_rating": ratings[loser],
            }
        )

    thin = sorted(i for i, c in played.items() if c < 10)
    table = [
        {
            "item_ref": item,
            "rating": ratings[item],
            "n": played[item],
            "n_comparisons": played[item],
            "label": (
                "provisional: " + str(played[item]) + " comparisons. One result moves a rating; "
                "ten do not make it reliable."
            ) if played[item] < 10 else "",
        }
        for item in sorted(ratings, key=lambda i: -ratings[i])
    ]

    total = math.fsum(ratings.values())
    conserved = abs(total - float(initial) * len(ratings))

    checks = [
        Check(
            id="time-ordered",
            label="Comparisons were applied in the order they happened",
            status="WARN" if out_of_order else ("PASS" if stamped else "SKIPPED"),
            statistic=float(len(ordered)),
            detail=(
                "The comparisons arrived out of time order and were sorted before updating. Elo "
                "is path dependent, so the ratings from an unsorted pass would have been a "
                "different number for the same data."
                if out_of_order else
                "" if stamped else
                "These comparisons carry no timestamps, so they were applied in input order. A "
                "filter applied in an arbitrary order is an arbitrary filter."
            ),
        ),
        Check(
            id="zero-sum",
            label="Total rating is conserved across every update",
            status="PASS" if conserved < 1e-6 else "FAIL",
            statistic=conserved,
            blocking=conserved >= 1e-6,
            detail=(
                "The sum of ratings drifted by " + format(conserved, ".3g") + " from its starting "
                "total, which an Elo update cannot do. Something is wrong with the arithmetic and "
                "nothing is published."
            ) if conserved >= 1e-6 else "",
        ),
        Check(
            id="thin-history",
            label="No rating rests on a handful of comparisons",
            status="WARN" if thin else "PASS",
            statistic=float(len(thin)),
            detail=(
                str(len(thin)) + " item(s) have fewer than 10 comparisons. Their ratings are "
                "labelled provisional: a rating from very few results is a starting value that "
                "has been nudged, not a measurement."
            ) if thin else "",
        ),
        Check(
            id="k-factor-declared",
            label="The K-factor was declared rather than tuned",
            status="PASS",
            statistic=float(k_factor),
            detail=(
                "K = " + format(float(k_factor), ".1f") + " sets how fast a rating forgets. It is "
                "in params_hash, so a K changed between two runs shows up as a different "
                "computation rather than as movement in the ratings."
            ),
        ),
    ]

    value = {
        "ratings": table,
        "trajectory": trajectory,
        "k_factor": float(k_factor),
        "initial": float(initial),
        "n_items": len(ratings),
    }
    if conserved >= 1e-6:
        value = {"ratings": [], "trajectory": [], "k_factor": float(k_factor),
                 "initial": float(initial), "n_items": len(ratings)}

    return Evidence(
        value=value,
        n=len(ordered),
        method=method_id,
        as_of=stamp,
        assumptions=(
            "Comparisons arrive in time order.",
            "The K-factor is declared in advance, since it sets how fast a rating forgets.",
        ),
        checks=tuple(checks),
        caveats=(
            "There is no interval here, and the absence is deliberate. Elo is a filter, not an "
            "estimator with a sampling distribution; pairwise.bradley_terry is where an interval "
            "on strength belongs.",
            "A rating difference of d implies a win probability of 1/(1 + 10^(-d/400)). At the "
            "fixed point of repeated updates that is exactly the observed win rate, which is what "
            "ties this service to the Bradley-Terry abilities.",
        ),
        unit="elo",
        params_hash=phash,
    )


__all__ = [
    "bradley_terry",
    "elo_expected",
    "elo_update",
]
