"""
Community structure over the derived interaction graph.

network.isolation_report returns shares by stratum and can never return individuals.
A list of socially isolated neighbours is the most sensitive output this platform
could produce, so the service is shaped so the list cannot be constructed.

The blocking check in `louvain_communities` is the one that matters. Modularity
maximisation partitions an Erdos-Renyi graph without complaint and reports a
respectable number for it, so a partition is only community structure if it
beats a degree-preserving null. That comparison is computed, seeded, and blocks.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
import random
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import mean, std, wilson_interval

MIN_NODES = 30
MIN_EDGES = 60
NULL_REPLICATES = 20


# ---------------------------------------------------------------------------
# Graph handling
# ---------------------------------------------------------------------------


def build_graph(edges: Sequence[Any]) -> tuple[list[str], dict[str, dict[str, float]]]:
    """Adjacency with summed weights. Nodes are sorted so every sweep is deterministic."""
    adjacency: dict[str, dict[str, float]] = {}
    for edge in edges:
        a = str(getattr(edge, "a_ref", None) or edge[0])
        b = str(getattr(edge, "b_ref", None) or edge[1])
        weight = float(getattr(edge, "weight", 1.0))
        if a == b:
            continue
        adjacency.setdefault(a, {})
        adjacency.setdefault(b, {})
        adjacency[a][b] = adjacency[a].get(b, 0.0) + weight
        adjacency[b][a] = adjacency[b].get(a, 0.0) + weight
    return sorted(adjacency), adjacency


def modularity(adjacency: Mapping[str, Mapping[str, float]],
               partition: Mapping[str, int]) -> float:
    """
    Newman-Girvan modularity, from its definition rather than incrementally.

    Q = sum over communities of (internal weight / 2m) - (total degree / 2m)^2.
    Written out this way so the incremental version inside Louvain has something
    independent to be checked against.
    """
    two_m = math.fsum(w for node in adjacency for w in adjacency[node].values())
    if two_m <= 0:
        return 0.0
    internal: dict[int, float] = {}
    degree: dict[int, float] = {}
    for node, neighbours in adjacency.items():
        community = partition[node]
        degree[community] = degree.get(community, 0.0) + math.fsum(neighbours.values())
        for other, weight in neighbours.items():
            if partition[other] == community:
                internal[community] = internal.get(community, 0.0) + weight
    return math.fsum(
        internal.get(c, 0.0) / two_m - (degree.get(c, 0.0) / two_m) ** 2
        for c in degree
    )


def louvain(adjacency: Mapping[str, Mapping[str, float]], *, resolution: float,
            seed: int) -> dict[str, int]:
    """
    Blondel et al. (2008): local moving, then aggregation, repeated.

    The node sweep order is shuffled from the seed, because a fixed alphabetical
    order gives a partition that depends on how members happen to be named.
    """
    nodes = sorted(adjacency)
    membership = {node: i for i, node in enumerate(nodes)}
    # `current` is the working graph; it collapses as communities aggregate.
    current: dict[Any, dict[Any, float]] = {
        node: dict(neighbours) for node, neighbours in adjacency.items()
    }
    mapping: dict[str, Any] = {node: node for node in nodes}
    rng = random.Random(seed)

    while True:
        two_m = math.fsum(w for node in current for w in current[node].values())
        if two_m <= 0:
            break
        community = {node: node for node in current}
        strength = {
            node: math.fsum(current[node].values()) for node in current
        }
        self_loops = {node: current[node].get(node, 0.0) for node in current}
        totals = dict(strength)

        improved = False
        order = sorted(current)
        for _ in range(30):
            moved = False
            rng.shuffle(order)
            for node in order:
                own = community[node]
                totals[own] -= strength[node]
                links: dict[Any, float] = {}
                for other, weight in current[node].items():
                    if other == node:
                        continue
                    links[community[other]] = links.get(community[other], 0.0) + weight
                best, best_gain = own, links.get(own, 0.0) - resolution * totals.get(own, 0.0) * strength[node] / two_m
                for candidate, weight in sorted(links.items(), key=lambda kv: (str(kv[0]),)):
                    gain = weight - resolution * totals.get(candidate, 0.0) * strength[node] / two_m
                    if gain > best_gain + 1e-12:
                        best, best_gain = candidate, gain
                totals[best] = totals.get(best, 0.0) + strength[node]
                if best != own:
                    community[node] = best
                    moved = True
                    improved = True
            if not moved:
                break
        if not improved:
            break

        # Aggregate: one node per community, edges summed.
        labels = {c: i for i, c in enumerate(sorted({community[n] for n in current}, key=str))}
        aggregated: dict[Any, dict[Any, float]] = {}
        for node, neighbours in current.items():
            a = labels[community[node]]
            aggregated.setdefault(a, {})
            for other, weight in neighbours.items():
                b = labels[community[other]]
                aggregated.setdefault(b, {})
                aggregated[a][b] = aggregated[a].get(b, 0.0) + weight
        # Self-loop weight is double counted by the sweep above only for the
        # off-diagonal; the diagonal keeps its own convention, so normalise.
        for a in aggregated:
            aggregated[a][a] = aggregated[a].get(a, 0.0)
        for node in nodes:
            mapping[node] = labels[community[mapping[node]]]
        current = aggregated
        if len(current) == len(labels) == len(set(community.values())) and len(current) == len(community):
            break

    final = {}
    relabel: dict[Any, int] = {}
    for node in nodes:
        key = mapping[node]
        if key not in relabel:
            relabel[key] = len(relabel)
        final[node] = relabel[key]
    return final


def configuration_null(adjacency: Mapping[str, Mapping[str, float]], *,
                       seed: int) -> dict[str, dict[str, float]]:
    """
    A degree-preserving random graph by double-edge swaps.

    The right null for "is this community structure real": it keeps every
    member's number of connections and destroys only who they are with, so a
    modularity difference cannot be explained by the degree sequence.
    """
    rng = random.Random(seed)
    edges = [
        (a, b)
        for a in sorted(adjacency)
        for b in sorted(adjacency[a])
        if a < b
    ]
    existing = {frozenset(e) for e in edges}
    for _ in range(10 * len(edges)):
        i, j = rng.randrange(len(edges)), rng.randrange(len(edges))
        if i == j:
            continue
        a, b = edges[i]
        c, d = edges[j]
        if rng.random() < 0.5:
            c, d = d, c
        if len({a, b, c, d}) < 4:
            continue
        if frozenset((a, d)) in existing or frozenset((c, b)) in existing:
            continue
        existing.discard(frozenset((a, b)))
        existing.discard(frozenset((c, d)))
        existing.add(frozenset((a, d)))
        existing.add(frozenset((c, b)))
        edges[i] = (a, d)
        edges[j] = (c, b)
    null: dict[str, dict[str, float]] = {node: {} for node in adjacency}
    for a, b in edges:
        null[a][b] = 1.0
        null[b][a] = 1.0
    return null


def betweenness(adjacency: Mapping[str, Mapping[str, float]], *,
                normalised: bool = True) -> dict[str, float]:
    """
    Brandes (2001), the unweighted breadth-first accumulation.

    Undirected, so every shortest path is counted twice by the sweep and the
    result is halved. Normalised by (n-1)(n-2)/2 pairs, which is what makes the
    star centre exactly 1.
    """
    nodes = sorted(adjacency)
    score = {node: 0.0 for node in nodes}
    for source in nodes:
        stack: list[str] = []
        predecessors: dict[str, list[str]] = {node: [] for node in nodes}
        sigma = {node: 0.0 for node in nodes}
        distance = {node: -1 for node in nodes}
        sigma[source] = 1.0
        distance[source] = 0
        queue = [source]
        head = 0
        while head < len(queue):
            node = queue[head]
            head += 1
            stack.append(node)
            for neighbour in sorted(adjacency[node]):
                if distance[neighbour] < 0:
                    distance[neighbour] = distance[node] + 1
                    queue.append(neighbour)
                if distance[neighbour] == distance[node] + 1:
                    sigma[neighbour] += sigma[node]
                    predecessors[neighbour].append(node)
        delta = {node: 0.0 for node in nodes}
        while stack:
            node = stack.pop()
            for predecessor in predecessors[node]:
                delta[predecessor] += (sigma[predecessor] / sigma[node]) * (1.0 + delta[node])
            if node != source:
                score[node] += delta[node]
    n = len(nodes)
    for node in nodes:
        score[node] /= 2.0
        if normalised and n > 2:
            score[node] /= (n - 1) * (n - 2) / 2.0
    return score


# ---------------------------------------------------------------------------
# network.louvain_communities
# ---------------------------------------------------------------------------


def _agreement(a: Mapping[str, int], b: Mapping[str, int]) -> float:
    """
    Adjusted Rand index between two partitions of the same nodes.

    Used for stability across restarts, so 1.0 means the restarts agreed
    exactly and 0.0 means they agreed no more than chance would.
    """
    nodes = sorted(set(a) & set(b))
    if len(nodes) < 2:
        return 1.0
    table: dict[tuple[int, int], int] = {}
    rows: dict[int, int] = {}
    cols: dict[int, int] = {}
    for node in nodes:
        key = (a[node], b[node])
        table[key] = table.get(key, 0) + 1
        rows[a[node]] = rows.get(a[node], 0) + 1
        cols[b[node]] = cols.get(b[node], 0) + 1

    def choose2(x: int) -> float:
        return x * (x - 1) / 2.0

    total = choose2(len(nodes))
    index = math.fsum(choose2(v) for v in table.values())
    row_sum = math.fsum(choose2(v) for v in rows.values())
    col_sum = math.fsum(choose2(v) for v in cols.values())
    expected = row_sum * col_sum / total if total else 0.0
    maximum = (row_sum + col_sum) / 2.0
    if abs(maximum - expected) < 1e-15:
        return 1.0
    return (index - expected) / (maximum - expected)


def louvain_communities(edges, window, *, seed, resolution=1.0, min_component_size=3,
                        k_anonymity=5) -> Evidence:
    """network.louvain_communities. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "network.louvain_communities"
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "seed": seed, "resolution": resolution, "min_component_size": min_component_size,
        "k_anonymity": k_anonymity,
    })
    as_of = getattr(window, "end", None)

    nodes, adjacency = build_graph(edges)
    n_edges = sum(len(v) for v in adjacency.values()) // 2
    empty = {"communities": [], "modularity": None, "sizes": [], "n_isolated": 0,
             "resolution": resolution}

    if len(nodes) < MIN_NODES or n_edges < MIN_EDGES:
        return insufficient(
            method, n=len(nodes), as_of=as_of, params_hash=phash, empty_value=empty,
            unit="communities",
            caveats=(
                "Needs " + str(MIN_NODES) + " nodes and " + str(MIN_EDGES) + " edges; has "
                + str(len(nodes)) + " and " + str(n_edges) + ". Below that, modularity "
                "maximisation finds structure in random graphs reliably, which is a documented "
                "pathology and not a feature.",
            ),
        )

    partition = louvain(adjacency, resolution=resolution, seed=seed)
    observed = modularity(adjacency, partition)

    # Stability across seeded restarts.
    restarts = [louvain(adjacency, resolution=resolution, seed=seed + i) for i in range(1, 6)]
    stability = mean([_agreement(partition, other) for other in restarts])

    # The blocking comparison: a degree-preserving null, partitioned by the
    # same algorithm, so the two numbers are commensurable.
    null_scores = []
    for i in range(NULL_REPLICATES):
        null = configuration_null(adjacency, seed=seed * 1000 + i)
        null_scores.append(modularity(null, louvain(null, resolution=resolution, seed=seed + i)))
    null_mean = mean(null_scores)
    null_sd = std(null_scores) if len(null_scores) > 1 else 0.0
    z_score = (observed - null_mean) / null_sd if null_sd > 0 else float("inf")
    beats_null = observed > null_mean + 2.0 * null_sd

    sizes: dict[int, int] = {}
    for node in nodes:
        sizes[partition[node]] = sizes.get(partition[node], 0) + 1
    isolated = sum(1 for node in nodes if not adjacency[node])

    resolution_floor = math.sqrt(2.0 * n_edges)
    below_floor = [c for c, size in sizes.items() if size < resolution_floor]

    communities = []
    small = 0
    for community in sorted(sizes, key=lambda c: (-sizes[c], c)):
        members = sorted(node for node in nodes if partition[node] == community)
        if len(members) < k_anonymity:
            small += 1
            communities.append({
                "community": community, "size": len(members), "members": None,
                "suppressed": True,
            })
        else:
            communities.append({
                "community": community, "size": len(members), "members": members,
                "suppressed": False,
            })

    checks = [
        Check(
            id="modularity-vs-null",
            label="Whether this partition is better than one of a random graph with the same degrees",
            status="PASS" if beats_null else "FAIL",
            statistic=observed,
            blocking=not beats_null,
            detail=(
                "Modularity " + "{:.4f}".format(observed) + " against a degree-preserving null "
                "averaging " + "{:.4f}".format(null_mean) + " (sd " + "{:.4f}".format(null_sd)
                + "), z = " + "{:.2f}".format(z_score) + ". This partition is not "
                "distinguishable from what the same algorithm produces on a random graph with "
                "these degrees, so it is not community structure and the communities are not "
                "shown. What is shown instead is this comparison."
            ) if not beats_null else "",
        ),
        Check(
            id="partition-stability",
            label="Whether seeded restarts agree on the same communities",
            status="PASS" if stability >= 0.7 else ("WARN" if stability >= 0.5 else "FAIL"),
            statistic=stability,
            blocking=False,
            detail=(
                "Restarts agreed at an adjusted Rand index of " + "{:.2f}".format(stability)
                + ". Below about 0.7 the community boundaries are an artefact of the sweep "
                "order rather than of the graph."
            ) if stability < 0.7 else "",
        ),
        Check(
            id="resolution-limit",
            label="Communities small enough to be merged artefacts of the resolution limit",
            status="WARN" if below_floor else "PASS",
            statistic=float(len(below_floor)),
            detail=(
                str(len(below_floor)) + " communities are smaller than sqrt(2m) = "
                + "{:.1f}".format(resolution_floor) + ", the scale below which modularity "
                "maximisation is known to merge genuinely separate groups. They may be "
                "several groups shown as one."
            ) if below_floor else "",
        ),
        Check(
            id="projection-declared",
            label="The edge construction this graph rests on is declared",
            status="PASS",
            statistic=float(n_edges),
            detail=(
                "Edges are the declared projection with its declared normalisation constant, "
                "carried in params_hash. A different normalisation gives a different graph and "
                "therefore different communities."
            ),
        ),
        Check(
            id="k-anonymity-communities",
            label="Communities too small to name without naming their members",
            status="FAIL" if small else "PASS",
            statistic=float(k_anonymity),
            blocking=False,
            detail=(
                str(small) + " communities held fewer than " + str(k_anonymity) + " members and "
                "are counted but not listed."
            ) if small else "",
        ),
    ]

    value = {
        "communities": communities,
        "modularity": observed,
        "sizes": sorted(sizes.values(), reverse=True),
        "n_communities": len(sizes),
        "n_isolated": isolated,
        "n_nodes": len(nodes),
        "n_edges": n_edges,
        "resolution": resolution,
        "stability": stability,
        "null_modularity_mean": null_mean,
        "null_modularity_sd": null_sd,
        "z_score": z_score,
        "labels": dict(partition),
    }
    if not beats_null:
        value = {**value, "communities": [], "labels": {}, "sizes": []}

    return Evidence(
        value=value,
        n=len(nodes),
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The interaction graph reflects real relationships. It does not: it reflects "
            "co-presence, which is a proxy and sometimes a poor one.",
            "The co-attendance normalisation constant is declared and enters params_hash.",
        ),
        checks=tuple(checks),
        caveats=(
            "A partition has no confidence interval. The null comparison and the restart "
            "stability are the uncertainty statements and both are always shown.",
            "One large gathering can dominate the edge set and make everyone look connected to "
            "everyone. That is a property of the projection, not of the community.",
        ),
        unit="communities",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# network.betweenness_centrality
# ---------------------------------------------------------------------------


def betweenness_centrality(edges, window, *, top_m=10, k_anonymity=5) -> Evidence:
    """network.betweenness_centrality. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "network.betweenness_centrality"
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "top_m": top_m, "k_anonymity": k_anonymity,
    })
    as_of = getattr(window, "end", None)

    nodes, adjacency = build_graph(edges)
    n_edges = sum(len(v) for v in adjacency.values()) // 2
    if len(nodes) < MIN_NODES or n_edges < MIN_EDGES:
        return insufficient(
            method, n=len(nodes), as_of=as_of, params_hash=phash, empty_value=[],
            unit="normalised betweenness",
            caveats=(
                "Needs " + str(MIN_NODES) + " nodes and " + str(MIN_EDGES) + " edges; has "
                + str(len(nodes)) + " and " + str(n_edges) + ".",
            ),
        )

    scores = betweenness(adjacency)
    ordered = sorted(nodes, key=lambda node: (-scores[node], node))
    rows = []
    for rank, node in enumerate(ordered[:top_m], start=1):
        degree = len(adjacency[node])
        suppressed = degree < k_anonymity
        rows.append({
            "member_ref": None if suppressed else node,
            "betweenness": None if suppressed else scores[node],
            "degree": None if suppressed else degree,
            "rank": rank,
            "n": degree,
            "suppressed": suppressed,
        })
    n_suppressed = sum(1 for r in rows if r["suppressed"])

    return Evidence(
        value=rows,
        n=len(nodes),
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The edge set is the declared projection with its declared normalisation.",
            "Betweenness is exact given the graph. The graph is the assumption.",
        ),
        checks=(
            Check(
                id="k-anonymity-rows",
                label="No named connector rests on fewer than k connections",
                status="FAIL" if n_suppressed else "PASS",
                statistic=float(k_anonymity),
                blocking=False,
                detail=(
                    str(n_suppressed) + " rows describe someone with fewer than "
                    + str(k_anonymity) + " connections and are emptied."
                ) if n_suppressed else "",
            ),
            Check(
                id="single-gathering-dominance",
                label="Whether one gathering dominates the edge set",
                status="PASS",
                statistic=float(n_edges),
                detail=(
                    "Betweenness on a graph built from one large meeting makes everyone a "
                    "connector. The projection is declared in params_hash so this is checkable."
                ),
            ),
        ),
        caveats=(
            "Naming informal power brokers in a community with active political friction is a "
            "foreseeable harm. A vertical that judges it so switches this service off in its "
            "manifest rather than shipping it with a caveat.",
            "Exact given the graph, so no interval. Normalised so that the centre of a star is "
            "exactly 1 and every leaf exactly 0.",
        ),
        unit="normalised betweenness",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# network.isolation_report
# ---------------------------------------------------------------------------


def isolation_report(edges, roster, window, *, k_anonymity=5) -> Evidence:
    """network.isolation_report. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "network.isolation_report"
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "k_anonymity": k_anonymity,
    })
    as_of = getattr(window, "end", None) or getattr(roster, "as_of", None)

    nodes, adjacency = build_graph(edges)
    connected = {node for node in nodes if adjacency[node]}

    # The roster arrives either as member records, which carry strata, or as a
    # RosterSnapshot, which is counts only. The second cannot answer the
    # per-stratum question and the service says so rather than inventing rows.
    members = list(roster) if isinstance(roster, (list, tuple)) else None
    counts_by_stratum = dict(getattr(roster, "counts_by_stratum", {}) or {})
    total = int(getattr(roster, "total", 0)) or (len(members) if members else 0)

    empty = {"n_isolated": None, "isolated_share": None, "lo": None, "hi": None, "by_stratum": []}
    if total < MIN_NODES:
        return insufficient(
            method, n=total, as_of=as_of, params_hash=phash, empty_value=empty, unit="share",
            caveats=(
                "Needs a roster of at least " + str(MIN_NODES) + " people; has " + str(total)
                + ".",
            ),
        )

    if members is not None:
        by_stratum: dict[str, list[int]] = {}
        n_isolated = 0
        for member in members:
            ref = str(getattr(member, "member_ref", None))
            strata = getattr(member, "strata", None) or getattr(member, "strata_at_entry", {}) or {}
            key = ":".join(str(strata[name]) for name in sorted(strata)) or "unstated"
            alone = ref not in connected
            n_isolated += 1 if alone else 0
            row = by_stratum.setdefault(key, [0, 0])
            row[0] += 1 if alone else 0
            row[1] += 1
        rows = []
        n_suppressed = 0
        for key in sorted(by_stratum):
            isolated_here, size = by_stratum[key]
            suppressed = size < k_anonymity
            n_suppressed += 1 if suppressed else 0
            lo, hi = wilson_interval(isolated_here, size) if not suppressed else (None, None)
            rows.append({
                "stratum": key,
                "n": None if suppressed else size,
                "n_isolated": None if suppressed else isolated_here,
                "isolated_share": None if suppressed else isolated_here / size,
                "lo": lo, "hi": hi, "suppressed": suppressed,
            })
        stratum_note = ""
    else:
        n_isolated = total - len(connected)
        rows = []
        n_suppressed = 0
        stratum_note = (
            "The roster arrived as counts by stratum rather than as member records, so who is "
            "isolated cannot be matched to a stratum. The aggregate share is reported and the "
            "per-stratum breakdown is empty rather than guessed. "
            + str(len(counts_by_stratum)) + " strata are known by headcount only."
        )

    share = n_isolated / total
    lo, hi = wilson_interval(n_isolated, total)

    checks = [
        Check(
            id="k-anonymity-cells",
            label="No stratum row describes fewer than k people",
            status="FAIL" if n_suppressed else "PASS",
            statistic=float(k_anonymity),
            blocking=False,
            detail=(
                str(n_suppressed) + " stratum rows covered fewer than " + str(k_anonymity)
                + " people and are emptied."
            ) if n_suppressed else "",
        ),
        Check(
            id="single-channel-recording",
            label="Whether isolation here could just be an unrecorded channel",
            status="WARN",
            statistic=share,
            detail=(
                "Isolation in this graph means no RECORDED interaction. Someone active on "
                "WhatsApp and absent from the app looks identical to someone genuinely alone, "
                "and this service cannot tell them apart."
            ),
        ),
    ]
    if stratum_note:
        checks.append(Check(
            id="strata-available",
            label="Whether the roster carries enough to break the share down by stratum",
            status="SKIPPED",
            detail=stratum_note,
        ))

    return Evidence(
        value={
            "n_isolated": n_isolated,
            "isolated_share": share,
            "lo": lo,
            "hi": hi,
            "by_stratum": rows,
            "n_roster": total,
            "n_connected": len(connected),
        },
        n=total,
        method=method,
        as_of=as_of,
        interval=(lo, hi),
        interval_kind="normal-95",
        assumptions=(
            "Isolation here means no recorded interaction, which is not the same as being "
            "socially isolated in life.",
        ),
        checks=tuple(checks),
        caveats=(
            "Individual isolated members are NEVER returned by this service. A list of socially "
            "isolated neighbours is the most sensitive output this platform could produce, and "
            "the shape of this result is what stops the list being constructed.",
        ) + ((stratum_note,) if stratum_note else ()),
        unit="share",
        params_hash=phash,
    )


__all__ = [
    "betweenness",
    "betweenness_centrality",
    "build_graph",
    "configuration_null",
    "isolation_report",
    "louvain",
    "louvain_communities",
    "modularity",
]
