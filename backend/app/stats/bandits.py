"""
Adaptive allocation over the exposure log.

A policy decision a committee cannot reproduce months later is not a policy
decision, which is why the seed is a blocking check and why freeze_and_report
exists.

Three things are worth reading before the code.

**The randomness is ours, not the interpreter's.** The Beta draws come from a
Marsaglia-Tsang gamma sampler driven only by `random.Random(seed).random()`,
rather than from `random.betavariate`. The Mersenne Twister's uniform stream is
a fixed, documented sequence; the distribution helpers layered on top of it are
implementation detail and have changed between releases. A committee asking in
2029 why the system chose Tuesday evening WhatsApp reminders should get the same
allocation back, not a different one because the interpreter was upgraded.

**The floor is not a rounding convention, it is a decision.** Pure Thompson
sampling can starve an arm on early noise, and in a community setting that means
a channel is silently abandoned: nobody ever finds out that the notice board
works for the people who do not read WhatsApp. The floor keeps every arm at 5%
of traffic, and it costs regret, exactly `floor * gap * T` in the long run. That
is a price the envelope states rather than hides.

**The allocation is a decision, not an estimate.** It carries no interval. The
per-arm conversion posteriors carry intervals; the split does not, because there
is no true split for it to be an estimate of.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""

import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, params_hash
from app.stats.experiments import two_proportion_p
from app.stats.numeric import betainc
from app.stats.streams.participation import EXPOSURE_KINDS

CONVERSION_KIND = "nudge_acted"

# docs/STATS_CATALOG.md: no floor to run, but the pack does not ACT on an
# allocation until every arm has been tried enough to have said anything.
MIN_EXPOSURES_TO_ACT = 30

# Below this the two halves of an arm's history are too short for the
# stationarity test to say anything, and a test that cannot fail is noise.
MIN_HISTORY_FOR_STATIONARITY = 40


# ---------------------------------------------------------------------------
# Seeded sampling. Deterministic given the seed, and derived only from the
# uniform stream so it stays stable across interpreter versions.
# ---------------------------------------------------------------------------


def _std_normal(rng: random.Random) -> float:
    """Box-Muller, from two uniforms. One value per call: the discarded second
    value would make the stream depend on call parity, which is a reproducibility
    trap rather than a saving."""
    u1 = rng.random()
    while u1 <= 0.0:
        u1 = rng.random()
    u2 = rng.random()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def gamma_sample(rng: random.Random, shape: float) -> float:
    """Marsaglia and Tsang (2000), unit scale. Exact, not an approximation."""
    if shape <= 0.0:
        raise ValueError("gamma shape must be positive, got " + repr(shape))
    if shape < 1.0:
        return gamma_sample(rng, shape + 1.0) * (rng.random() ** (1.0 / shape))
    d = shape - 1.0 / 3.0
    c = 1.0 / math.sqrt(9.0 * d)
    while True:
        x = _std_normal(rng)
        v = (1.0 + c * x) ** 3
        if v <= 0.0:
            continue
        u = rng.random()
        if u < 1.0 - 0.0331 * (x ** 4):
            return d * v
        if u > 0.0 and math.log(u) < 0.5 * x * x + d * (1.0 - v + math.log(v)):
            return d * v


def beta_sample(rng: random.Random, a: float, b: float) -> float:
    """A Beta draw as the ratio of two Gammas, which is the definition."""
    x = gamma_sample(rng, a)
    y = gamma_sample(rng, b)
    total = x + y
    return 0.5 if total <= 0.0 else x / total


def beta_ppf(q: float, a: float, b: float, *, iterations: int = 120) -> float:
    """Beta quantile by bisection on the regularised incomplete beta. Deterministic."""
    if not 0.0 <= q <= 1.0:
        raise ValueError("a quantile is in [0, 1], got " + repr(q))
    lo, hi = 0.0, 1.0
    for _ in range(iterations):
        mid = 0.5 * (lo + hi)
        if betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def kl_bernoulli(p: float, q: float) -> float:
    """KL(p || q) for Bernoulli means, in nats. The denominator of Lai-Robbins."""
    eps = 1e-12
    p = min(1.0 - eps, max(eps, p))
    q = min(1.0 - eps, max(eps, q))
    return p * math.log(p / q) + (1.0 - p) * math.log((1.0 - p) / (1.0 - q))


def lai_robbins_bound(true_means: Sequence[float], horizon: int) -> float:
    """
    The asymptotic regret lower bound for any consistent bandit policy.

        liminf_T  R_T / log T  >=  sum_{i : p_i < p*}  (p* - p_i) / KL(p_i, p*)

    Lai and Robbins (1985). This is a theorem about every policy, which is why
    the Method Card can cite it as an external truth where no published table of
    Thompson-sampling outputs exists. Thompson sampling is known to attain it
    asymptotically (Kaufmann, Korda and Munos, 2012), so a run whose regret sits
    far below this line is a bug in the simulation, not a better algorithm.
    """
    if horizon < 2:
        return 0.0
    best = max(true_means)
    total = 0.0
    for p in true_means:
        if p < best:
            total += (best - p) / kl_bernoulli(p, best)
    return total * math.log(horizon)


def simulate_regret(
    true_means: Sequence[float],
    *,
    horizon: int,
    seed: int,
    floor: float = 0.0,
    prior: tuple[float, float] = (1.0, 1.0),
) -> dict:
    """
    Run the policy against known arms and return its cumulative regret.

    Not a service and it returns no Evidence: it is the harness the Method Card's
    theoretical claim is checked with, and it is here rather than in the test
    file because the thing being checked is the sampler and the update rule that
    `thompson_sampling_policy` uses, not a re-implementation of them.

    With `floor > 0` a fraction `k * floor` of rounds is allocated uniformly at
    random. That makes regret linear in T by construction, at the rate
    `floor * sum(gaps)`, which the tests assert rather than hand-wave: a floor
    buys recoverability and pays for it in regret.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive, got " + repr(horizon))
    k = len(true_means)
    if k < 2:
        raise ValueError("a bandit needs at least two arms, got " + str(k))
    rng = random.Random(seed)
    alphas = [prior[0]] * k
    betas = [prior[1]] * k
    best = max(true_means)
    regret = 0.0
    pulls = [0] * k
    forced = 0
    trace = []
    explore_probability = k * floor
    for t in range(horizon):
        if explore_probability > 0.0 and rng.random() < explore_probability:
            chosen = int(rng.random() * k)
            chosen = min(k - 1, chosen)
            forced += 1
        else:
            draws = [beta_sample(rng, alphas[i], betas[i]) for i in range(k)]
            chosen = max(range(k), key=lambda i: draws[i])
        reward = 1.0 if rng.random() < true_means[chosen] else 0.0
        alphas[chosen] += reward
        betas[chosen] += 1.0 - reward
        pulls[chosen] += 1
        regret += best - true_means[chosen]
        if (t + 1) % max(1, horizon // 20) == 0:
            trace.append((t + 1, regret))
    return {
        "regret": regret,
        "pulls": tuple(pulls),
        "posteriors": tuple((alphas[i], betas[i]) for i in range(k)),
        "forced_explorations": forced,
        "trace": tuple(trace),
        "bound": lai_robbins_bound(true_means, horizon),
    }


# ---------------------------------------------------------------------------
# Arm state, from whatever shape the caller honestly has.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmState:
    """One arm's Beta posterior and the exposures behind it."""

    arm_ref: str
    alpha: float
    beta: float
    exposures: int = 0
    conversions: int = 0
    outcomes: tuple[float, ...] = ()
    last_exposure: datetime | None = None

    def __post_init__(self) -> None:
        if self.alpha <= 0 or self.beta <= 0:
            raise ValueError(
                "arm " + self.arm_ref + " has a degenerate posterior Beta("
                + repr(self.alpha) + ", " + repr(self.beta) + "); both parameters are positive"
            )

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)


def _state_from_pair(arm_ref: str, pair) -> ArmState:
    """A bare (alpha, beta) pair is read as a posterior, never as counts. The
    two are not distinguishable from the numbers, so only one reading is
    allowed and the caller passes counts under their own names."""
    return ArmState(arm_ref=arm_ref, alpha=float(pair[0]), beta=float(pair[1]))


def _state_from_counts(
    arm_ref: str, conversions: int, exposures: int, prior: tuple[float, float], **extra
) -> ArmState:
    return ArmState(
        arm_ref=arm_ref,
        alpha=prior[0] + conversions,
        beta=prior[1] + exposures - conversions,
        exposures=exposures,
        conversions=conversions,
        **extra,
    )


def _states_from_events(events, prior: tuple[float, float]) -> list[ArmState]:
    """Exposure rows to one trial per member per arm, in exposure order."""
    seen: dict[tuple[str, str], Any] = {}
    acted: set[tuple[str, str]] = set()
    for event in events:
        kind = getattr(event, "kind", None)
        if kind not in EXPOSURE_KINDS:
            continue
        arm_ref = getattr(event, "arm_ref", None)
        if not arm_ref:
            raise ValueError(
                "exposure-log row of kind " + str(kind) + " carries no arm_ref, so it cannot be "
                "attributed to an arm"
            )
        key = (str(arm_ref), str(getattr(event, "member_ref", "")))
        at = getattr(event, "at", None)
        known = seen.get(key, "missing")
        if known == "missing" or (at is not None and (known is None or at < known)):
            seen[key] = at
        if kind == CONVERSION_KIND:
            acted.add(key)

    by_arm: dict[str, list[tuple[Any, float]]] = {}
    for key, at in seen.items():
        by_arm.setdefault(key[0], []).append((at, 1.0 if key in acted else 0.0))

    states = []
    for arm_ref in sorted(by_arm):
        rows = sorted(by_arm[arm_ref], key=lambda r: (r[0] is None, r[0]))
        outcomes = tuple(outcome for _, outcome in rows)
        times = [at for at, _ in rows if at is not None]
        states.append(_state_from_counts(
            arm_ref,
            int(sum(outcomes)),
            len(outcomes),
            prior,
            outcomes=outcomes,
            last_exposure=max(times) if times else None,
        ))
    return states


def arm_states(arm_posteriors, *, prior: tuple[float, float] = (1.0, 1.0)) -> list[ArmState]:
    """
    Accept the shapes a caller honestly has, and refuse anything else.

    1. A mapping `arm_ref -> (alpha, beta)`, or to counts, or to an object.
    2. A sequence of `ArmState`, or of anything carrying `arm_ref` with either
       `alpha`/`beta` or `conversions`/`exposures`.
    3. A flat iterable of exposure-log `ParticipationEvent` rows across arms.
    """
    if isinstance(arm_posteriors, Mapping):
        states = []
        for arm_ref in sorted(arm_posteriors, key=str):
            entry = arm_posteriors[arm_ref]
            if isinstance(entry, ArmState):
                states.append(entry)
            elif isinstance(entry, Mapping):
                if "alpha" in entry and "beta" in entry:
                    states.append(ArmState(
                        arm_ref=str(arm_ref),
                        alpha=float(entry["alpha"]), beta=float(entry["beta"]),
                        exposures=int(entry.get("exposures", 0)),
                        conversions=int(entry.get("conversions", 0)),
                        outcomes=tuple(entry.get("outcomes", ()) or ()),
                    ))
                else:
                    states.append(_state_from_counts(
                        str(arm_ref), int(entry["conversions"]), int(entry["exposures"]), prior,
                        outcomes=tuple(entry.get("outcomes", ()) or ()),
                    ))
            elif isinstance(entry, (tuple, list)) and len(entry) == 2:
                states.append(_state_from_pair(str(arm_ref), entry))
            elif hasattr(entry, "alpha") and hasattr(entry, "beta"):
                states.append(ArmState(
                    arm_ref=str(arm_ref), alpha=float(entry.alpha), beta=float(entry.beta),
                    exposures=int(getattr(entry, "exposures", 0)),
                    conversions=int(getattr(entry, "conversions", 0)),
                    outcomes=tuple(getattr(entry, "outcomes", ()) or ()),
                ))
            else:
                raise ValueError(
                    "arm " + str(arm_ref) + " maps to " + type(entry).__name__
                    + ", which is neither a Beta pair nor a count pair nor a posterior"
                )
        return states

    rows = list(arm_posteriors)
    if not rows:
        return []
    first = rows[0]
    if isinstance(first, ArmState):
        return list(rows)
    if hasattr(first, "kind") and getattr(first, "kind", None) in EXPOSURE_KINDS:
        return _states_from_events(rows, prior)
    if hasattr(first, "kind") or hasattr(first, "member_ref"):
        return _states_from_events(rows, prior)
    states = []
    for entry in rows:
        arm_ref = str(getattr(entry, "arm_ref", ""))
        if hasattr(entry, "alpha") and hasattr(entry, "beta"):
            states.append(ArmState(
                arm_ref=arm_ref, alpha=float(entry.alpha), beta=float(entry.beta),
                exposures=int(getattr(entry, "exposures", 0)),
                conversions=int(getattr(entry, "conversions", 0)),
                outcomes=tuple(getattr(entry, "outcomes", ()) or ()),
            ))
        elif hasattr(entry, "conversions") and hasattr(entry, "exposures"):
            states.append(_state_from_counts(
                arm_ref, int(entry.conversions), int(entry.exposures), prior,
                outcomes=tuple(getattr(entry, "outcomes", ()) or ()),
            ))
        else:
            raise ValueError(
                "bandits.* takes arm posteriors, arm counts or exposure-log rows; got "
                + type(entry).__name__
            )
    return states


# ---------------------------------------------------------------------------
# The policy
# ---------------------------------------------------------------------------


def sample_allocation(
    states: Sequence[ArmState], *, seed: int, n_draws: int = 10000, floor: float = 0.05
) -> dict:
    """
    The allocation itself: win probabilities from posterior draws, then the floor.

    Thompson sampling allocates to each arm the posterior probability that it is
    the best arm, which is what a Monte Carlo over the joint posterior measures
    directly. The floor is applied afterwards by shrinking towards uniform:

        allocation_i = floor + (1 - k * floor) * win_i

    so every arm keeps at least `floor` and the shares still sum to one.

    Exposed separately from the service because `freeze_and_report` replays it
    and must get an identical answer without re-running the checks.
    """
    k = len(states)
    if k < 2:
        raise ValueError("an allocation needs at least two arms, got " + str(k))
    if not 0.0 <= floor < 1.0 / k:
        raise ValueError(
            "floor must leave room for " + str(k) + " arms: it is below " + "{:.3f}".format(1.0 / k)
            + ", got " + repr(floor)
        )
    if n_draws < 1:
        raise ValueError("n_draws must be positive, got " + repr(n_draws))

    rng = random.Random(seed)
    wins = [0] * k
    regret_draws = 0.0
    means = [s.mean for s in states]
    for _ in range(n_draws):
        draws = [beta_sample(rng, s.alpha, s.beta) for s in states]
        best = 0
        for i in range(1, k):
            if draws[i] > draws[best]:
                best = i
        wins[best] += 1
        regret_draws += draws[best]

    win_probability = [w / n_draws for w in wins]
    allocation = [floor + (1.0 - k * floor) * w for w in win_probability]
    # Expected instantaneous regret of this split: the posterior mean of the best
    # arm's rate minus the rate the split will actually earn.
    expected_best = regret_draws / n_draws
    earned = math.fsum(a * m for a, m in zip(allocation, means))
    return {
        "win_probability": win_probability,
        "allocation": allocation,
        "regret_estimate": max(0.0, expected_best - earned),
        "expected_reward": earned,
        "seed": seed,
        "n_draws": n_draws,
        "floor": floor,
    }


def _stationarity_check(states: Sequence[ArmState]) -> tuple[Check, list[ArmState]]:
    """
    A changepoint in any arm's reward series, by the crudest test that can
    actually fail: first half against second half.

    On a FAIL the posteriors are refitted on the recent half only and the
    discount is disclosed. Discounting silently would be worse than not
    discounting: the n on the screen would no longer be the n behind the number.
    """
    testable = [s for s in states if len(s.outcomes) >= MIN_HISTORY_FOR_STATIONARITY]
    if not testable:
        return Check(
            id="non-stationarity",
            label="Each arm's conversion rate is stable over its own history",
            status="SKIPPED",
            detail=(
                "The arm posteriors were supplied as counts rather than as an ordered reward "
                "series, so a shift over time cannot be seen. A bandit is blind to seasonality "
                "by construction, and this check is the only thing that would notice."
            ),
        ), list(states)

    worst_p = 1.0
    worst_arm = ""
    worst_stat = 0.0
    for state in testable:
        half = len(state.outcomes) // 2
        early, late = state.outcomes[:half], state.outcomes[half:]
        z, p = two_proportion_p(
            int(sum(early)), len(early), int(sum(late)), len(late)
        )
        if p < worst_p:
            worst_p, worst_arm, worst_stat = p, state.arm_ref, z
    adjusted = min(1.0, worst_p * len(testable))
    shifted = adjusted < 0.01

    if not shifted:
        return Check(
            id="non-stationarity",
            label="Each arm's conversion rate is stable over its own history",
            status="PASS",
            statistic=worst_stat,
            p_value=adjusted,
        ), list(states)

    discounted = []
    for state in states:
        if len(state.outcomes) >= MIN_HISTORY_FOR_STATIONARITY:
            half = len(state.outcomes) // 2
            recent = state.outcomes[half:]
            discounted.append(ArmState(
                arm_ref=state.arm_ref,
                alpha=state.alpha - sum(state.outcomes[:half]),
                beta=state.beta - (half - sum(state.outcomes[:half])),
                exposures=len(recent),
                conversions=int(sum(recent)),
                outcomes=tuple(recent),
                last_exposure=state.last_exposure,
            ))
        else:
            discounted.append(state)
    return Check(
        id="non-stationarity",
        label="Each arm's conversion rate is stable over its own history",
        status="FAIL",
        statistic=worst_stat,
        p_value=adjusted,
        blocking=False,
        detail=(
            "Arm " + worst_arm + " converted at a different rate in the first half of its history "
            "than in the second (z = " + "{:.2f}".format(worst_stat) + ", Bonferroni p = "
            + "{:.2g}".format(adjusted) + "). The posteriors have therefore been refitted on the "
            "most recent half of each arm's exposures only, and the counts shown are those. A "
            "stationary bandit that has seen one festival will keep sending festival messages "
            "in March."
        ),
    ), discounted


def thompson_sampling_policy(
    arm_posteriors,
    *,
    seed,
    n_draws=10000,
    floor=0.05,
    prior=(1.0, 1.0),
    as_of=None,
    credible=0.95,
) -> Evidence:
    """bandits.thompson_sampling_policy. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "bandits.thompson_sampling_policy"
    states = arm_states(arm_posteriors, prior=prior)
    phash = params_hash(method, 1, {
        "seed": seed, "n_draws": n_draws, "floor": floor, "prior": list(prior),
        "arms": [s.arm_ref for s in states],
    })

    when = as_of
    if when is None:
        times = [s.last_exposure for s in states if s.last_exposure is not None]
        if not times:
            raise ValueError(
                "bandits.thompson_sampling_policy cannot read a clock (spine rule S6). Pass "
                "as_of, or pass exposure rows carrying timestamps"
            )
        when = max(times)

    seed_check = Check(
        id="seed-recorded",
        label="The seed that produced this allocation is recorded",
        status="PASS" if seed is not None else "FAIL",
        statistic=float(seed) if isinstance(seed, int) else None,
        blocking=seed is None,
        detail="" if seed is not None else (
            "No seed was supplied, so this allocation could never be reproduced or explained. "
            "A policy decision a committee cannot reproduce months later is not a policy "
            "decision, so no allocation is returned."
        ),
    )
    if seed is None:
        return Evidence(
            value={"allocation": [], "arm_win_probability": [], "posteriors": [],
                   "regret_estimate": None, "seed": None, "acting": False},
            n=sum(s.exposures for s in states),
            method=method,
            as_of=when,
            interval=None,
            interval_kind="credible-95",
            assumptions=("Seeded randomness only; nothing here reads a global generator.",),
            checks=(seed_check,),
            caveats=("No allocation is returned without a seed.",),
            unit="share of traffic",
            params_hash=phash,
        )

    if len(states) < 2:
        raise ValueError(
            "bandits.thompson_sampling_policy allocates between arms and was given "
            + str(len(states)) + "; with one arm there is no decision to make"
        )

    stationarity, effective = _stationarity_check(states)
    result = sample_allocation(effective, seed=seed, n_draws=n_draws, floor=floor)

    n = sum(s.exposures for s in effective)
    thin = [s.arm_ref for s in effective if s.exposures < MIN_EXPOSURES_TO_ACT]
    acting = not thin
    k = len(effective)
    if not acting:
        allocation = [1.0 / k] * k
    else:
        allocation = result["allocation"]

    lifted = [
        s.arm_ref for s, w, a in zip(effective, result["win_probability"], allocation)
        if a > w + 1e-12
    ]
    floor_check = Check(
        id="floor-applied",
        label="Every arm keeps at least the declared share of traffic",
        status="PASS" if floor > 0 else "WARN",
        statistic=float(len(lifted)),
        detail="" if floor > 0 else (
            "The traffic floor is zero, so an arm that got unlucky early can be starved to nothing "
            "and will never recover. In a community setting that means a channel is abandoned "
            "without anyone deciding to abandon it."
        ),
    )
    act_check = Check(
        id="enough-exposure-to-act",
        label="Every arm has been tried enough for the allocation to be acted on",
        status="PASS" if acting else "WARN",
        statistic=float(min((s.exposures for s in effective), default=0)),
        detail="" if acting else (
            "Arms " + ", ".join(sorted(thin)) + " have fewer than " + str(MIN_EXPOSURES_TO_ACT)
            + " exposures. A UNIFORM allocation is returned instead of the sampled one: the "
            "posterior differences at this size are noise, and acting on them is how an arm gets "
            "starved before it has said anything."
        ),
    )

    tail = (1.0 - credible) / 2.0
    posteriors = []
    for state, win, share in zip(effective, result["win_probability"], allocation):
        posteriors.append({
            "arm_ref": state.arm_ref,
            "alpha": state.alpha,
            "beta": state.beta,
            "mean": state.mean,
            "lo": beta_ppf(tail, state.alpha, state.beta),
            "hi": beta_ppf(1.0 - tail, state.alpha, state.beta),
            "exposures": state.exposures,
            "conversions": state.conversions,
            "win_probability": win,
            "allocation": share,
        })

    return Evidence(
        value={
            "allocation": [
                {"arm_ref": p["arm_ref"], "share": p["allocation"]} for p in posteriors
            ],
            "arm_win_probability": [
                {"arm_ref": p["arm_ref"], "probability": p["win_probability"]} for p in posteriors
            ],
            "posteriors": posteriors,
            "regret_estimate": result["regret_estimate"],
            "expected_reward": math.fsum(
                p["allocation"] * p["mean"] for p in posteriors
            ),
            "seed": seed,
            "n_draws": n_draws,
            "floor": floor,
            "acting": acting,
        },
        n=n,
        method=method,
        as_of=when,
        interval=None,
        interval_kind="credible-95" if abs(credible - 0.95) < 1e-9 else "credible-89",
        assumptions=(
            "Arm rewards are stationary over the window.",
            "Exposures are independent and one member counts once per arm.",
            "The reward is observed promptly relative to the decision cadence.",
            "A traffic floor of " + "{:.0%}".format(floor) + " keeps every arm alive.",
        ),
        checks=(seed_check, stationarity, floor_check, act_check),
        caveats=(
            "The allocation is a DECISION and carries no interval. The intervals shown are on "
            "each arm's conversion rate, which is what is being estimated.",
            "Reproducible from seed " + str(seed) + " and " + str(n_draws) + " draws. Replaying "
            "the same posteriors with the same seed returns the identical split; "
            "bandits.freeze_and_report is the record that proves it.",
            "Expected regret of this split against always playing the best arm is "
            + "{:.4f}".format(result["regret_estimate"]) + " conversions per exposure, of which "
            "the " + "{:.0%}".format(floor) + " floor is a deliberate part.",
        ),
        unit="share of traffic",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# The governance feature
# ---------------------------------------------------------------------------


def _reason_for(entry: Mapping[str, Any], *, arms: int, floor: float, acting: bool) -> str:
    """A plain sentence assembled from the numbers, never from a template guess."""
    share = entry["allocation"]
    parts = [
        "Arm " + entry["arm_ref"] + " was given " + "{:.0%}".format(share) + " of the next batch."
    ]
    if entry["exposures"]:
        parts.append(
            "It converted " + str(entry["conversions"]) + " of " + str(entry["exposures"])
            + " exposures (" + "{:.1%}".format(entry["conversions"] / entry["exposures"])
            + ", 95% credible " + "{:.1%}".format(entry["lo"]) + " to "
            + "{:.1%}".format(entry["hi"]) + ")."
        )
    else:
        parts.append("It has no exposures yet, so its posterior is the prior.")
    if acting:
        against = (
            "the other arm." if arms == 2 else "the other " + str(arms - 1) + " arms."
        )
        parts.append(
            "It was the best arm in " + "{:.0%}".format(entry["win_probability"])
            + " of the posterior draws against " + against
        )
        if share > entry["win_probability"] + 1e-9:
            parts.append(
                "The " + "{:.0%}".format(floor) + " floor lifted it from "
                + "{:.0%}".format(entry["win_probability"]) + " so it keeps learning."
            )
    else:
        parts.append(
            "The split is uniform because at least one arm has too few exposures to act on."
        )
    return " ".join(parts)


def freeze_and_report(policy_state, *, as_of) -> Evidence:
    """bandits.freeze_and_report. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "bandits.freeze_and_report"

    state = policy_state
    if isinstance(state, Evidence):
        state = state.value
    if not isinstance(state, Mapping):
        state = {
            "posteriors": getattr(state, "posteriors", None),
            "seed": getattr(state, "seed", None),
            "n_draws": getattr(state, "n_draws", 10000),
            "floor": getattr(state, "floor", 0.05),
            "acting": getattr(state, "acting", True),
        }
    posteriors = state.get("posteriors") or []
    if not posteriors:
        raise ValueError(
            "bandits.freeze_and_report records a policy state that already exists; this one "
            "carries no posteriors, so there is nothing to explain"
        )

    seed = state.get("seed")
    n_draws = int(state.get("n_draws", 10000))
    floor = float(state.get("floor", 0.05))
    acting = bool(state.get("acting", True))
    phash = params_hash(method, 1, {
        "seed": seed, "n_draws": n_draws, "floor": floor,
        "arms": [p["arm_ref"] for p in posteriors], "as_of": as_of,
    })

    frozen_states = [
        ArmState(
            arm_ref=str(p["arm_ref"]), alpha=float(p["alpha"]), beta=float(p["beta"]),
            exposures=int(p.get("exposures", 0)), conversions=int(p.get("conversions", 0)),
        )
        for p in posteriors
    ]
    stored_allocation = [float(p["allocation"]) for p in posteriors]

    replay_note = ""
    if seed is None:
        replay = None
        matched = False
        replay_note = "The stored state carries no seed, so it cannot be replayed at all."
    else:
        replay = sample_allocation(
            frozen_states, seed=seed, n_draws=n_draws, floor=floor,
        )
        replayed = replay["allocation"] if acting else [1.0 / len(frozen_states)] * len(frozen_states)
        matched = all(
            abs(a - b) <= 0.0 for a, b in zip(stored_allocation, replayed)
        )
        if not matched:
            worst = max(abs(a - b) for a, b in zip(stored_allocation, replayed))
            replay_note = (
                "Replaying the stored posteriors with seed " + str(seed) + " produced a different "
                "allocation, off by " + "{:.6f}".format(worst) + ". Either the record is not the "
                "one that produced the decision, or something in app/stats/ is carrying state "
                "between calls. Either way this record does not explain the decision that was "
                "taken, so it is not presented as one."
            )

    replay_check = Check(
        id="replay-matches",
        label="Replaying the frozen state with its seed reproduces the identical allocation",
        status="PASS" if matched else "FAIL",
        statistic=None,
        blocking=not matched,
        detail=replay_note,
    )

    rows = []
    for entry, share in zip(posteriors, stored_allocation):
        row = dict(entry)
        row["allocation"] = share
        row["reason"] = _reason_for(
            row, arms=len(posteriors), floor=floor, acting=acting
        )
        rows.append(row)

    total_exposures = sum(int(p.get("exposures", 0)) for p in posteriors)
    return Evidence(
        value={
            "frozen_at": as_of.isoformat().replace("+00:00", "Z") if as_of else None,
            "seed": seed,
            "n_draws": n_draws,
            "floor": floor,
            "acting": acting,
            "arms": rows if matched else [],
            "replayed": matched,
        },
        n=total_exposures,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="credible-95",
        assumptions=(
            "The stored state and seed are the ones that produced the allocation.",
            "Nothing is recomputed here: this is a record, not an estimate.",
        ),
        checks=(replay_check,),
        caveats=(
            "These are the posteriors and the credible intervals AS THEY STOOD at the freeze, "
            "not as they stand now. The policy has kept learning since.",
            "If the arm set or the reward definition changed after the freeze, this record stays "
            "accurate and the comparison to today stops being meaningful.",
        ),
        unit="share of traffic",
        params_hash=phash,
    )


__all__ = [
    "ArmState",
    "MIN_EXPOSURES_TO_ACT",
    "arm_states",
    "beta_ppf",
    "beta_sample",
    "freeze_and_report",
    "gamma_sample",
    "kl_bernoulli",
    "lai_robbins_bound",
    "sample_allocation",
    "simulate_regret",
    "thompson_sampling_policy",
]
