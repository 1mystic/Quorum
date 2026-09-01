"""
Empirical Bayes shrinkage and ranking.

3 out of 3 is not better than 47 out of 52. Every community leaderboard ranks by raw
rate and so puts the vendor with three lucky jobs above the vendor with a year of
evidence. Shrink toward a prior estimated from the data, and rank by the posterior
lower bound, not the posterior mean: ranking by the mean still favours small samples
whenever the prior is weak.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Three notes on how this module is built.

`as_of` is derived from the observations' own window ends rather than read from a
clock, per spine rule S6. A caller with units that carry no window must pass it.

The conjugate posteriors are written out in closed form. There is no sampler in
`beta_binomial_shrink` or `gamma_poisson_shrink` and there should not be: the
posterior of Beta(a, b) after x successes in n trials is exactly Beta(a+x, b+n-x),
and an approximation to an identity is only a way to be wrong.

`hierarchical_pool` computes its posterior by deterministic quadrature over a tau
grid (Gelman et al., BDA ch. 5.4) and then draws from that grid, rather than by
MCMC. That is a deliberate choice recorded in the Method Card: the model has one
scalar hyperparameter, so the integral is cheap and exact to grid resolution, and
the R-hat the catalog asked for does not apply to a quadrature. The equivalent
stability criterion, grid refinement plus a second seeded draw stream, is run in
its place and reported under the same check id.
"""
import math
import random
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import betainc, chi2_ppf, chi2_sf, gammainc_p, mean, nelder_mead
from app.stats.privacy import compose_epsilon, laplace_sample

MIN_GROUPS = 5
MIN_TOTAL_TRIALS = 50
MIN_TENANTS = 10
MAX_TENANT_SHARE = 0.25
EXTREME_SHRINKAGE = 0.1
RANK_DRAWS = 4000
TAU_GRID = 400

# One tenant contributes at most this many successes and this many trials per
# group_key per batch. It is a declared constant rather than a quantile of the
# data, because a bound read off the data is itself a leak of the data.
DEFAULT_CONTRIBUTION_CAP = 100.0


# ---------------------------------------------------------------------------
# Quantiles for the two conjugate families. Bisection on the regularized
# incomplete functions already in numeric.py, so there is one implementation of
# each special function in this package rather than one per module.
# ---------------------------------------------------------------------------


def beta_ppf(p: float, a: float, b: float) -> float:
    """The p-quantile of Beta(a, b), by bisection on the regularized incomplete beta."""
    if not 0.0 <= p <= 1.0:
        raise ValueError("beta_ppf needs a probability, got " + repr(p))
    if a <= 0.0 or b <= 0.0:
        raise ValueError("beta_ppf needs positive parameters")
    if p == 0.0:
        return 0.0
    if p == 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def gamma_ppf(p: float, shape: float, rate: float) -> float:
    """The p-quantile of Gamma(shape, rate), parametrized by RATE, not scale."""
    if not 0.0 <= p <= 1.0:
        raise ValueError("gamma_ppf needs a probability, got " + repr(p))
    if shape <= 0.0 or rate <= 0.0:
        raise ValueError("gamma_ppf needs positive parameters")
    if p == 0.0:
        return 0.0
    lo = 0.0
    hi = max(1.0, shape / rate)
    for _ in range(200):
        if gammainc_p(shape, rate * hi) >= p:
            break
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if gammainc_p(shape, rate * mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Reading the units
# ---------------------------------------------------------------------------


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _derive_as_of(observations: Sequence[Any], as_of):
    if as_of is not None:
        return as_of
    ends = [_get(o, "window_end") for o in observations]
    ends = [e for e in ends if e is not None]
    if not ends:
        raise ValueError(
            "as_of could not be derived: these units carry no window_end, so the caller "
            "must pass as_of explicitly. Nothing in app/stats reads a clock (spine rule S6)."
        )
    return max(ends)


def _rate_rows(observations: Sequence[Any]) -> list[tuple[str, int, int, Any]]:
    rows = []
    for obs in observations:
        ref = _get(obs, "group_ref")
        successes = _get(obs, "successes")
        trials = _get(obs, "trials")
        if ref is None or successes is None or trials is None:
            raise ValueError(
                "a RateObservation needs group_ref, successes and trials; got " + repr(obs)
            )
        rows.append((str(ref), int(successes), int(trials), obs))
    return rows


def _count_rows(observations: Sequence[Any]) -> list[tuple[str, int, float, Any]]:
    rows = []
    for obs in observations:
        ref = _get(obs, "group_ref")
        events = _get(obs, "events")
        exposure = _get(obs, "exposure")
        if ref is None or events is None or exposure is None:
            raise ValueError(
                "a CountObservation needs group_ref, events and exposure; got " + repr(obs)
            )
        rows.append((str(ref), int(events), float(exposure), obs))
    return rows


# ---------------------------------------------------------------------------
# bayes.fit_beta_prior
# ---------------------------------------------------------------------------


def _lbeta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _bb_loglik(rows: Sequence[tuple[str, int, int, Any]], a: float, b: float) -> float:
    """
    Beta-Binomial marginal log-likelihood, up to the binomial coefficient.

    The dropped term does not involve (a, b), so it changes neither the maximum
    nor any likelihood-ratio difference, which is all this module uses it for.
    """
    if a <= 0.0 or b <= 0.0 or not math.isfinite(a) or not math.isfinite(b):
        return -math.inf
    total = 0.0
    base = _lbeta(a, b)
    for _, x, n, _obs in rows:
        total += _lbeta(a + x, b + n - x) - base
    return total


def _moments_prior(rows: Sequence[tuple[str, int, int, Any]]) -> tuple[float, float]:
    """Method of moments on the group rates. Also the MLE's starting point."""
    ps = [x / n for _, x, n, _o in rows if n > 0]
    if not ps:
        return 1.0, 1.0
    mu = mean(ps)
    mu = min(max(mu, 1e-6), 1.0 - 1e-6)
    if len(ps) < 2:
        return mu * 2.0, (1.0 - mu) * 2.0
    observed = math.fsum((p - mu) ** 2 for p in ps) / (len(ps) - 1)
    within = mean([mu * (1.0 - mu) / n for _, _x, n, _o in rows if n > 0])
    between = observed - within
    if between <= 1e-12:
        strength = 1e4          # the groups look identical; a very strong prior
    else:
        strength = max(mu * (1.0 - mu) / between - 1.0, 1e-3)
    strength = min(strength, 1e6)
    return mu * strength, (1.0 - mu) * strength


def _mle_prior(rows: Sequence[tuple[str, int, int, Any]]) -> tuple[float, float]:
    a0, b0 = _moments_prior(rows)
    start = [math.log(max(a0, 1e-6)), math.log(max(b0, 1e-6))]

    def negative(theta: Sequence[float]) -> float:
        return -_bb_loglik(rows, math.exp(theta[0]), math.exp(theta[1]))

    best, _score = nelder_mead(negative, start, step=0.25, max_iter=3000, tol=1e-12)
    return math.exp(best[0]), math.exp(best[1])


def _bb_pmf(x: int, n: int, a: float, b: float) -> float:
    """Beta-Binomial probability of exactly x successes in n trials."""
    return math.exp(
        math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(n - x + 1)
        + _lbeta(a + x, b + n - x) - _lbeta(a, b)
    )


def _predictive_pit(x: int, n: int, a: float, b: float) -> float:
    """
    The mid-p probability integral transform of one group under Beta-Binomial.

    u = P(X < x) + 0.5 * P(X = x). If the fitted prior describes the population,
    these are uniform on (0, 1) whatever the group sizes are, which is what makes
    them comparable across groups with very different numbers of trials.
    """
    if n <= 400:
        below = math.fsum(_bb_pmf(k, n, a, b) for k in range(x))
        return below + 0.5 * _bb_pmf(x, n, a, b)
    mu = a / (a + b)
    var = mu * (1.0 - mu) * (1.0 / n + (n - 1.0) / n / (a + b + 1.0))
    sd = math.sqrt(max(var, 1e-18))
    z = (x / n - mu) / sd
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _predictive_gof(
    rows: Sequence[tuple[str, int, int, Any]], a: float, b: float
) -> tuple[float, float, int]:
    """
    Posterior predictive chi-square on the SHAPE of the group rates.

    Binning the raw rates would be useless here, because groups differ in how
    many trials they have and a bin that is empty for a small group is not
    evidence about the prior. Each group is instead mapped through its own
    predictive distribution to a uniform score, and the scores are tested for
    uniformity in equiprobable bins. Two degrees of freedom are spent on the
    fitted (alpha, beta).

    Returns (statistic, p_value, degrees_of_freedom). A df below 1 means there
    are too few groups to test anything, and the caller reports the check as
    SKIPPED rather than as a pass: a test with no power that prints PASS is
    worse than no test at all.
    """
    scores = [_predictive_pit(x, n, a, b) for _ref, x, n, _obs in rows if n > 0]
    groups = len(scores)
    bins = max(4, min(10, groups // 5))
    df = bins - 1 - 2
    if df < 1 or groups < 5 * bins // 2:
        return 0.0, 1.0, 0
    counts = [0] * bins
    for u in scores:
        counts[min(int(u * bins), bins - 1)] += 1
    expected = groups / bins
    stat = math.fsum((c - expected) ** 2 / expected for c in counts)
    return stat, chi2_sf(stat, df), df


def _profile_mean_interval(
    rows: Sequence[tuple[str, int, int, Any]], a: float, b: float
) -> tuple[float, float]:
    """
    Profile-likelihood interval on the prior mean mu = a / (a + b).

    For each candidate mu the nuisance parameter (the prior strength) is
    re-maximised, and the interval is where twice the drop in the profile
    log-likelihood reaches the chi-square(1) 95% point. It is an interval about
    the POPULATION of groups, not about any group.
    """
    strength = a + b
    mu_hat = a / strength
    peak = _bb_loglik(rows, a, b)
    cut = 0.5 * chi2_ppf(0.95, 1)

    def profile(mu: float) -> float:
        if not 0.0 < mu < 1.0:
            return -math.inf

        def negative(theta: Sequence[float]) -> float:
            s = math.exp(theta[0])
            return -_bb_loglik(rows, mu * s, (1.0 - mu) * s)

        best, score = nelder_mead(negative, [math.log(strength)], step=0.3, max_iter=600, tol=1e-11)
        return -score

    def hunt(direction: int) -> float:
        lo, hi = mu_hat, mu_hat
        step = 0.01
        for _ in range(80):
            hi = min(max(mu_hat + direction * step, 1e-9), 1.0 - 1e-9)
            if peak - profile(hi) >= cut or hi in (1e-9, 1.0 - 1e-9):
                break
            lo = hi
            step *= 1.6
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if peak - profile(mid) < cut:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    return hunt(-1), hunt(1)


def fit_beta_prior(observations, *, method="mle", min_groups=5, as_of=None) -> Evidence:
    """bayes.fit_beta_prior. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method_id = "bayes.fit_beta_prior"
    phash = params_hash(method_id, 1, {"method": method, "min_groups": min_groups})
    rows = _rate_rows(observations)
    stamp = _derive_as_of(observations, as_of)
    groups = len(rows)
    total_trials = sum(n for _, _x, n, _o in rows)

    if groups < max(min_groups, 1) or total_trials < MIN_TOTAL_TRIALS:
        return insufficient(
            method_id,
            n=groups,
            as_of=stamp,
            unit="rate",
            params_hash=phash,
            caveats=(
                "The prior is estimated FROM the groups, so with " + str(groups) + " group(s) and "
                + str(total_trials) + " trials there is nothing to pool. The honest answer is a "
                "uniform prior, and no shrinkage worth the name.",
            ),
        )

    if method == "moments":
        alpha, beta = _moments_prior(rows)
    elif method == "mle":
        alpha, beta = _mle_prior(rows)
    else:
        raise ValueError("fit_beta_prior method must be 'mle' or 'moments', got " + repr(method))

    strength = alpha + beta
    prior_mean = alpha / strength

    rates = [x / n for _, x, n, _o in rows if n > 0]
    zero_variance = max(rates) - min(rates) < 1e-12
    lo, hi = (prior_mean, prior_mean) if zero_variance else _profile_mean_interval(rows, alpha, beta)

    # Posterior predictive check on the SHAPE of the group rates, not on their
    # spread. A spread check would be worthless here and it is worth saying why:
    # both fitting methods below match the observed variance by construction, so
    # a variance ratio computed against them can essentially never fail, and a
    # check that cannot fail is not a check. The discrepancy used instead is a
    # chi-square of the observed rates against the fitted Beta-Binomial
    # predictive distribution in bins, which does catch the failure this check
    # exists for: two trades pooled as one look bimodal, not Beta.
    dispersion, gof_p, gof_df = _predictive_gof(rows, alpha, beta)

    max_share = max(n for _, _x, n, _o in rows) / total_trials

    # How well is the prior STRENGTH identified? On a small number of groups the
    # marginal likelihood can be nearly flat in it, which means the shrinkage
    # weight is a choice rather than a measurement, and that should be said.
    peak_ll = _bb_loglik(rows, alpha, beta)
    strength_drop = min(
        peak_ll - _bb_loglik(rows, prior_mean * s, (1.0 - prior_mean) * s)
        for s in (0.5 * strength, 2.0 * strength)
    )

    checks = [
        Check(
            id="groups-sufficient",
            label="Enough groups to learn a prior from",
            status="PASS",
            statistic=float(groups),
            blocking=True,
        ),
        Check(
            id="zero-variance",
            label="The groups are not all at exactly the same rate",
            status="FAIL" if zero_variance else "PASS",
            statistic=(max(rates) - min(rates)) if rates else 0.0,
            blocking=True,
            detail=(
                "Every group sits at the same rate, so the maximum likelihood prior diverges to "
                "infinite strength and shrinkage would flatten everything onto one number. That "
                "the groups are indistinguishable is itself the finding, and it is shown instead "
                "of a prior."
            ) if zero_variance else "",
        ),
        Check(
            id="prior-fit",
            label="The observed group rates look like draws from the fitted Beta",
            status=("SKIPPED" if gof_df < 1 else "WARN" if gof_p < 0.05 else "PASS"),
            statistic=dispersion,
            p_value=gof_p if gof_df >= 1 else None,
            detail=(
                "There are too few groups spread across enough of the rate range to test the "
                "shape of the prior at all, so this check is reported as untested rather than "
                "as passed."
            ) if gof_df < 1 else (
                "The group rates do not look like draws from one Beta (posterior predictive "
                "chi-square " + format(dispersion, ".1f") + ", p = " + format(gof_p, ".2g")
                + "). The population is probably not exchangeable, so shrinkage will pull every "
                "group toward a middle that describes none of them. Stratify before pooling: "
                "pool within trade, not across."
            ) if gof_p < 0.05 else "",
        ),
        Check(
            id="strength-identified",
            label="The data pins down how strong the prior is, not just where it sits",
            status="WARN" if strength_drop < 0.5 else "PASS",
            statistic=strength_drop,
            detail=(
                "Halving or doubling the prior strength costs only "
                + format(strength_drop, ".2f") + " log-likelihood, so the strength is barely "
                "identified by " + str(groups) + " groups. The prior MEAN is well determined and "
                "its interval is shown; how hard the shrinkage pulls is not, so a shrinkage "
                "weight from this prior should be read as one defensible choice rather than as a "
                "measured quantity."
            ) if strength_drop < 0.5 else "",
        ),
        Check(
            id="heterogeneous-trials",
            label="No single group supplies most of the trials",
            status="WARN" if max_share > 0.9 else "PASS",
            statistic=max_share,
            detail=(
                "One group holds " + format(100.0 * max_share, ".0f") + "% of all trials, so the "
                "prior is mostly that group's own rate and it is being shrunk toward itself."
            ) if max_share > 0.9 else "",
        ),
    ]

    value = {
        "alpha": alpha,
        "beta": beta,
        "prior_mean": prior_mean,
        "prior_strength": strength,
        "lo": lo,
        "hi": hi,
        "n_groups": groups,
        "n_trials": total_trials,
        "fit_method": method,
    }
    if zero_variance:
        value["alpha"] = None
        value["beta"] = None
        value["prior_strength"] = None

    return Evidence(
        value=value,
        n=groups,
        method=method_id,
        as_of=stamp,
        interval=(lo, hi),
        interval_kind="profile-95",
        assumptions=(
            "Group rates are exchangeable draws from a common Beta distribution.",
            "Trials within a group are Bernoulli with that group's rate.",
        ),
        checks=tuple(checks),
        caveats=(
            "prior_strength is the number of pseudo-observations the prior is worth: "
            + format(strength, ".1f") + " here, against a typical group's "
            + format(total_trials / groups, ".1f") + " trials. That ratio is how hard the "
            "shrinkage will pull.",
            "This interval is uncertainty about the population of groups, not about any one group.",
        ),
        unit="rate",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# bayes.beta_binomial_shrink
# ---------------------------------------------------------------------------


def _prior_pair(prior, default: tuple[float, float] | None = None) -> tuple[float, float]:
    """Accept the Evidence from fit_beta_prior, a mapping, or a bare (alpha, beta)."""
    if prior is None:
        if default is None:
            raise ValueError("no prior was supplied and none could be derived")
        return default
    if isinstance(prior, Evidence):
        if prior.insufficient_data or prior.value is None:
            if default is None:
                raise ValueError("the prior Evidence carries no fitted prior")
            return default
        return _prior_pair(prior.value, default)
    if isinstance(prior, Mapping):
        alpha = prior.get("alpha")
        beta = prior.get("beta")
        if alpha is None or beta is None:
            if default is None:
                raise ValueError("the prior mapping has no alpha/beta")
            return default
        return float(alpha), float(beta)
    alpha, beta = prior
    return float(alpha), float(beta)


def _inherited_checks(prior) -> tuple[Check, ...]:
    if not isinstance(prior, Evidence):
        return ()
    out = []
    for c in prior.checks:
        out.append(
            Check(
                id="prior:" + c.id,
                label="Inherited from the prior: " + c.label,
                status=c.status,
                statistic=c.statistic,
                p_value=c.p_value,
                detail=c.detail,
                blocking=c.blocking,
            )
        )
    return tuple(out)


def _k_anonymity_rows(rows, member_counts, k, key_index=0):
    """Which group refs fall below the k-anonymity floor. Empty when no counts were given."""
    if member_counts is None:
        return None
    below = set()
    for row in rows:
        ref = row[key_index]
        count = member_counts.get(ref)
        if count is None or int(count) < int(k):
            below.add(ref)
    return below


def beta_binomial_shrink(
    observations, prior, *, credible=0.95, k_anonymity=5, member_counts=None, as_of=None
) -> Evidence:
    """bayes.beta_binomial_shrink. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method_id = "bayes.beta_binomial_shrink"
    phash = params_hash(method_id, 1, {"credible": credible, "k_anonymity": k_anonymity})
    rows = _rate_rows(observations)
    stamp = _derive_as_of(observations, as_of)
    groups = len(rows)

    if groups < MIN_GROUPS:
        return insufficient(
            method_id,
            n=groups,
            as_of=stamp,
            empty_value=[],
            unit="rate",
            params_hash=phash,
            caveats=(
                "Shrinkage needs a prior and the prior needs at least " + str(MIN_GROUPS)
                + " groups. There are " + str(groups) + ".",
            ),
        )

    alpha, beta = _prior_pair(prior, default=_moments_prior(rows))
    strength = alpha + beta
    tail = 0.5 * (1.0 - credible)
    suppressed = _k_anonymity_rows(rows, member_counts, k_anonymity)

    table = []
    extreme = 0
    for ref, x, n, _obs in rows:
        post_a = alpha + x
        post_b = beta + n - x
        weight = n / (n + strength) if (n + strength) > 0 else 0.0
        row = {
            "group_ref": ref,
            "successes": x,
            "trials": n,
            "n": n,
            "raw_rate": (x / n) if n > 0 else None,
            "shrunk_rate": post_a / (post_a + post_b),
            "lo": beta_ppf(tail, post_a, post_b),
            "hi": beta_ppf(1.0 - tail, post_a, post_b),
            "shrinkage_weight": weight,
            "posterior_alpha": post_a,
            "posterior_beta": post_b,
            "dist": "beta",
            "label": "",
            "suppressed": False,
        }
        if weight < EXTREME_SHRINKAGE:
            extreme += 1
            row["label"] = (
                "not enough evidence yet: " + format(100.0 * (1.0 - weight), ".0f")
                + "% of this figure is the prior, not this group"
            )
        if suppressed is not None and ref in suppressed:
            row = {
                "group_ref": ref,
                "successes": None,
                "trials": None,
                "n": None,
                "raw_rate": None,
                "shrunk_rate": None,
                "lo": None,
                "hi": None,
                "shrinkage_weight": None,
                "posterior_alpha": None,
                "posterior_beta": None,
                "dist": "beta",
                "label": "suppressed: fewer than " + str(k_anonymity) + " members behind this row",
                "suppressed": True,
            }
        table.append(row)

    n_suppressed = sum(1 for r in table if r["suppressed"])
    all_gone = n_suppressed == len(table) and len(table) > 0

    checks = list(_inherited_checks(prior))
    checks.append(
        Check(
            id="extreme-shrinkage",
            label="No row is being reported as essentially the prior without saying so",
            status="WARN" if extreme else "PASS",
            statistic=float(extreme),
            detail=(
                str(extreme) + " group(s) have a shrinkage weight below "
                + format(EXTREME_SHRINKAGE, ".2f") + ", so their figure is mostly the prior. Those "
                "rows are labelled 'not enough evidence yet' rather than given a number that looks "
                "like a measurement."
            ) if extreme else "",
        )
    )
    if suppressed is None:
        checks.append(
            Check(
                id="k-anonymity-rows",
                label="Every published row covers at least k members",
                status="SKIPPED",
                detail=(
                    "No member counts were supplied, so this function cannot tell how many people "
                    "sit behind a row. The floor is then the caller's to enforce, through "
                    "privacy.k_anonymity_suppress, before this table is published."
                ),
            )
        )
    else:
        checks.append(
            Check(
                id="k-anonymity-rows",
                label="Every published row covers at least k members",
                status="FAIL" if n_suppressed else "PASS",
                statistic=float(n_suppressed),
                blocking=all_gone,
                detail=(
                    str(n_suppressed) + " row(s) cover fewer than " + str(k_anonymity)
                    + " members and are emptied, not flagged: their figures are null. Suppression "
                    "is per row, so the surviving rows are still readable; the envelope only "
                    "blocks when nothing survives, which is the case here."
                    if all_gone else
                    str(n_suppressed) + " row(s) cover fewer than " + str(k_anonymity)
                    + " members and are emptied, not flagged: their figures are null. The "
                    "remaining rows are unaffected and readable."
                ) if n_suppressed else "",
            )
        )

    return Evidence(
        value=[] if all_gone else table,
        n=groups,
        method=method_id,
        as_of=stamp,
        interval_kind="credible-95" if abs(credible - 0.95) < 1e-9 else "credible-89",
        assumptions=(
            "The Beta prior fits the population of groups.",
            "Trials are exchangeable within a group.",
            "Prior Beta(" + format(alpha, ".3f") + ", " + format(beta, ".3f") + "), worth "
            + format(strength, ".1f") + " pseudo-observations.",
        ),
        checks=tuple(checks),
        caveats=(
            "Each row's interval is a CREDIBLE interval: a Bayesian statement about that group's "
            "rate given the model, not a confidence interval. The two are read differently.",
            "shrinkage_weight is n / (n + prior_strength). A group at 0.06 is being reported at "
            "94% prior, which is the honest description of three lucky jobs.",
        ),
        unit="rate",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# bayes.gamma_poisson_shrink
# ---------------------------------------------------------------------------


def _moments_gamma_prior(rows: Sequence[tuple[str, int, float, Any]]) -> tuple[float, float]:
    """Method of moments for the Gamma prior on a Poisson rate with known exposure."""
    rates = [y / e for _, y, e, _o in rows if e > 0]
    if not rates:
        return 1.0, 1.0
    mu = mean(rates)
    if mu <= 0:
        return 1.0, 1.0
    if len(rates) < 2:
        return mu, 1.0
    observed = math.fsum((r - mu) ** 2 for r in rates) / (len(rates) - 1)
    within = mean([mu / e for _, _y, e, _o in rows if e > 0])
    between = observed - within
    if between <= 1e-12:
        rate = 1e4 / mu
    else:
        rate = mu / between
    rate = min(max(rate, 1e-6), 1e8)
    return mu * rate, rate


def gamma_poisson_shrink(
    observations, prior, *, credible=0.95, k_anonymity=5, member_counts=None, as_of=None
) -> Evidence:
    """bayes.gamma_poisson_shrink. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method_id = "bayes.gamma_poisson_shrink"
    phash = params_hash(method_id, 1, {"credible": credible, "k_anonymity": k_anonymity})
    rows = _count_rows(observations)
    stamp = _derive_as_of(observations, as_of)
    groups = len(rows)

    if groups < MIN_GROUPS:
        return insufficient(
            method_id,
            n=groups,
            as_of=stamp,
            empty_value=[],
            unit="events_per_exposure",
            params_hash=phash,
            caveats=(
                "The Gamma prior is estimated from the groups; " + str(groups) + " is below the "
                "floor of " + str(MIN_GROUPS) + ".",
            ),
        )

    default = _moments_gamma_prior(rows)
    if prior is None:
        shape, rate = default
        fitted_here = True
    else:
        pair = _prior_pair(prior, default=default)
        shape, rate = pair
        fitted_here = False

    tail = 0.5 * (1.0 - credible)
    suppressed = _k_anonymity_rows(rows, member_counts, k_anonymity)

    table = []
    extreme = 0
    for ref, y, exposure, _obs in rows:
        post_shape = shape + y
        post_rate = rate + exposure
        weight = exposure / post_rate if post_rate > 0 else 0.0
        row = {
            "group_ref": ref,
            "events": y,
            "exposure": exposure,
            "n": y,
            "raw_rate": y / exposure if exposure > 0 else None,
            "shrunk_rate": post_shape / post_rate,
            "lo": gamma_ppf(tail, post_shape, post_rate),
            "hi": gamma_ppf(1.0 - tail, post_shape, post_rate),
            "shrinkage_weight": weight,
            "posterior_shape": post_shape,
            "posterior_rate": post_rate,
            "dist": "gamma",
            "label": "",
            "suppressed": False,
        }
        if weight < EXTREME_SHRINKAGE:
            extreme += 1
            row["label"] = (
                "not enough exposure yet: " + format(100.0 * (1.0 - weight), ".0f")
                + "% of this figure is the prior, not this group"
            )
        if suppressed is not None and ref in suppressed:
            row = {
                "group_ref": ref,
                "events": None,
                "exposure": None,
                "n": None,
                "raw_rate": None,
                "shrunk_rate": None,
                "lo": None,
                "hi": None,
                "shrinkage_weight": None,
                "posterior_shape": None,
                "posterior_rate": None,
                "dist": "gamma",
                "label": "suppressed: fewer than " + str(k_anonymity) + " members behind this row",
                "suppressed": True,
            }
        table.append(row)

    n_suppressed = sum(1 for r in table if r["suppressed"])
    all_gone = n_suppressed == len(table) and len(table) > 0

    checks = list(_inherited_checks(prior))
    checks.append(
        Check(
            id="extreme-shrinkage",
            label="No row is being reported as essentially the prior without saying so",
            status="WARN" if extreme else "PASS",
            statistic=float(extreme),
            detail=(
                str(extreme) + " group(s) have less exposure than the prior is worth, so their "
                "figure is mostly the prior and is labelled as such."
            ) if extreme else "",
        )
    )
    checks.append(
        Check(
            id="exposure-declared",
            label="Every group's exposure is measured rather than assumed equal",
            status="PASS",
            statistic=min(e for _, _y, e, _o in rows),
            detail=(
                "Exposure ranges from " + format(min(e for _, _y, e, _o in rows), ".3g") + " to "
                + format(max(e for _, _y, e, _o in rows), ".3g") + ". A resolver active for two "
                "weeks is not being compared against one active for a year."
            ),
        )
    )
    if suppressed is None:
        checks.append(
            Check(
                id="k-anonymity-rows",
                label="Every published row covers at least k members",
                status="SKIPPED",
                detail=(
                    "No member counts were supplied, so the floor is the caller's to enforce "
                    "through privacy.k_anonymity_suppress before this table is published."
                ),
            )
        )
    else:
        checks.append(
            Check(
                id="k-anonymity-rows",
                label="Every published row covers at least k members",
                status="FAIL" if n_suppressed else "PASS",
                statistic=float(n_suppressed),
                blocking=all_gone,
                detail=(
                    str(n_suppressed) + " row(s) are emptied, not flagged. "
                    + ("Nothing survives, so the table is withheld entirely." if all_gone
                       else "The remaining rows are unaffected.")
                ) if n_suppressed else "",
            )
        )

    return Evidence(
        value=[] if all_gone else table,
        n=groups,
        method=method_id,
        as_of=stamp,
        interval_kind="credible-95" if abs(credible - 0.95) < 1e-9 else "credible-89",
        assumptions=(
            "Group event counts are Poisson with a rate drawn from a common Gamma.",
            "Exposure is measured, not assumed equal.",
            "Prior Gamma(shape " + format(shape, ".3f") + ", rate " + format(rate, ".3f")
            + ")" + (", fitted here by moments because no prior was supplied" if fitted_here else ""),
        ),
        checks=tuple(checks),
        caveats=(
            "Each row's interval is a credible interval on that group's rate per unit of "
            "exposure, not a confidence interval.",
            "Counts overdispersed beyond what a Gamma mixture absorbs will still look tidy here. "
            "The Method Card says when that happens.",
        ),
        unit="events_per_exposure",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# bayes.rank_by_posterior_lower_bound
# ---------------------------------------------------------------------------


def _posterior_rows(posteriors) -> list[dict]:
    """Accept the Evidence from either shrink service, a list of rows, or objects."""
    if isinstance(posteriors, Evidence):
        source = posteriors.value or []
    else:
        source = posteriors
    rows = []
    for item in source:
        ref = _get(item, "group_ref")
        dist = _get(item, "dist")
        a = _get(item, "posterior_alpha")
        b = _get(item, "posterior_beta")
        shape = _get(item, "posterior_shape")
        rate = _get(item, "posterior_rate")
        if dist is None:
            dist = "gamma" if shape is not None else "beta"
        if _get(item, "suppressed", False):
            continue
        if dist == "beta":
            if a is None or b is None:
                a, b = _get(item, "alpha"), _get(item, "beta")
            if a is None or b is None:
                raise ValueError("posterior row for " + repr(ref) + " has no Beta parameters")
            p1, p2 = float(a), float(b)
        elif dist == "gamma":
            if shape is None or rate is None:
                raise ValueError("posterior row for " + repr(ref) + " has no Gamma parameters")
            p1, p2 = float(shape), float(rate)
        else:
            raise ValueError("unknown posterior family " + repr(dist))
        rows.append(
            {
                "group_ref": str(ref),
                "dist": dist,
                "p1": p1,
                "p2": p2,
                "n": _get(item, "n"),
            }
        )
    return rows


def _posterior_mean(row: Mapping[str, Any]) -> float:
    if row["dist"] == "beta":
        return row["p1"] / (row["p1"] + row["p2"])
    return row["p1"] / row["p2"]


def _posterior_quantile(row: Mapping[str, Any], q: float) -> float:
    if row["dist"] == "beta":
        return beta_ppf(q, row["p1"], row["p2"])
    return gamma_ppf(q, row["p1"], row["p2"])


def _posterior_draw(rng: random.Random, row: Mapping[str, Any]) -> float:
    if row["dist"] == "beta":
        return rng.betavariate(row["p1"], row["p2"])
    return rng.gammavariate(row["p1"], 1.0 / row["p2"])


def rank_by_posterior_lower_bound(
    posteriors, *, quantile=0.05, tie_break="posterior_mean", seed=0, as_of=None
) -> Evidence:
    """bayes.rank_by_posterior_lower_bound. See docs/STATS_CATALOG.md and its Method Card."""
    method_id = "bayes.rank_by_posterior_lower_bound"
    phash = params_hash(
        method_id, 1, {"quantile": quantile, "tie_break": tie_break, "seed": seed}
    )
    rows = _posterior_rows(posteriors)
    if as_of is None and isinstance(posteriors, Evidence):
        as_of = posteriors.as_of
    if as_of is None:
        raise ValueError("rank_by_posterior_lower_bound needs an as_of it can carry forward")

    if len(rows) < MIN_GROUPS:
        return insufficient(
            method_id,
            n=len(rows),
            as_of=as_of,
            empty_value=[],
            unit="rate",
            params_hash=phash,
            caveats=(
                "A leaderboard of " + str(len(rows)) + " is not a leaderboard, and the prior "
                "behind these posteriors needs " + str(MIN_GROUPS) + " groups anyway.",
            ),
        )

    for row in rows:
        row["lower_bound"] = _posterior_quantile(row, quantile)
        row["posterior_mean"] = _posterior_mean(row)
        row["lo"] = _posterior_quantile(row, 0.025)
        row["hi"] = _posterior_quantile(row, 0.975)

    ordered = sorted(
        rows,
        key=lambda r: (-r["lower_bound"], -r["posterior_mean"], r["group_ref"]),
    )

    # Rank stability: the seeded probability that a group holds the rank it is
    # shown at. This is the field that stops the leaderboard lying by omission.
    rng = random.Random(seed)
    holds = [0] * len(ordered)
    for _ in range(RANK_DRAWS):
        draws = [(_posterior_draw(rng, r), i) for i, r in enumerate(ordered)]
        draws.sort(key=lambda d: -d[0])
        for position, (_value, index) in enumerate(draws):
            if position == index:
                holds[index] += 1
    stability = [h / RANK_DRAWS for h in holds]

    # Tie bands: adjacent ranks whose credible intervals overlap by more than
    # half the narrower interval are not meaningfully ordered.
    band = 0
    bands = [0]
    for i in range(1, len(ordered)):
        prev, cur = ordered[i - 1], ordered[i]
        overlap = min(prev["hi"], cur["hi"]) - max(prev["lo"], cur["lo"])
        narrower = min(prev["hi"] - prev["lo"], cur["hi"] - cur["lo"])
        share = overlap / narrower if narrower > 0 else 0.0
        if share <= 0.5:
            band += 1
        bands.append(band)
    banded = len(set(bands)) < len(ordered)

    missing_n = [r["group_ref"] for r in ordered if r.get("n") is None]

    table = []
    for i, row in enumerate(ordered):
        table.append(
            {
                "rank": i + 1,
                "group_ref": row["group_ref"],
                "lower_bound": row["lower_bound"],
                "posterior_mean": row["posterior_mean"],
                "n": row["n"],
                "lo": row["lo"],
                "hi": row["hi"],
                "rank_stability": stability[i],
                "tie_band": bands[i],
            }
        )

    checks = [
        Check(
            id="n-disclosure",
            label="Every row carries the number of observations behind it",
            status="FAIL" if missing_n else "PASS",
            statistic=float(len(missing_n)),
            blocking=bool(missing_n),
            detail=(
                "These rows arrived without an n: " + ", ".join(sorted(missing_n)) + ". A rank "
                "without its n is exactly the lie this service exists to stop, so the table is "
                "withheld rather than rendered and left to the frontend to fix."
            ) if missing_n else "",
        ),
        Check(
            id="rank-separation",
            label="Adjacent ranks are separated rather than overlapping",
            status="WARN" if banded else "PASS",
            statistic=float(band + 1),
            detail=(
                "Some adjacent ranks have credible intervals overlapping by more than half. They "
                "are grouped into " + str(band + 1) + " tie band(s) and must be rendered as bands, "
                "not as positions: a rank 1 at 34% stability and a rank 2 at 31% are not ordered."
            ) if banded else "",
        ),
    ]

    return Evidence(
        value=[] if missing_n else table,
        n=len(ordered),
        method=method_id,
        as_of=as_of,
        interval_kind="credible-95",
        assumptions=(
            "The posteriors handed in were fitted on comparable groups.",
            "The reader wants a ranking robust to small samples rather than the highest point "
            "estimate.",
        ),
        checks=tuple(checks),
        caveats=(
            "Ranked by the " + format(100.0 * quantile, ".0f") + "th percentile of each posterior, "
            "not by its mean. Ranking by the mean still favours small samples whenever the prior "
            "is weak; ranking by the lower bound is what makes 'we do not know enough about this "
            "one yet' cost a place.",
            "rank_stability is the seeded probability that a group holds the rank shown. Below "
            "about 0.5 the position is not a finding.",
        ),
        unit="rate",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# bayes.hierarchical_pool
# ---------------------------------------------------------------------------


def _level_value(obs: Any, level: str) -> str | None:
    strata = _get(obs, "strata") or {}
    if level in strata:
        return str(strata[level])
    direct = _get(obs, level)
    if direct is not None:
        return str(direct)
    return None


def _noise_contributions(
    contributions: Mapping[str, Mapping[str, tuple[float, float]]],
    *,
    epsilon: float,
    cap: float,
    seed: int,
) -> dict[str, tuple[float, float]]:
    """
    The differential privacy mechanism, exactly as docs/STATS_CATALOG.md specifies it.

    `contributions` is tenant -> unit -> (successes, trials): ONE sufficient
    statistic per tenant per unit per batch, which is what bounds the mechanism's
    sensitivity by construction rather than by trust. Each pair is clamped to
    [0, cap], so one tenant can move the summed successes by at most `cap` and
    the summed trials by at most `cap`. Half the budget is spent on each of the
    two sums (sequential composition, Dwork and Roth ch. 3), giving Laplace scale
    2 * cap / epsilon on each.

    Each unit's release uses its own noise stream. A tenant's contributions to
    two different group_keys are disjoint records, so parallel composition
    applies across units and a tenant spends `epsilon` in total per batch, not
    `epsilon` per unit.

    Returned noised sums are clamped back into a legal range. Clamping is
    post-processing of a differentially private release and cannot weaken the
    guarantee.

    Private because it returns bare numbers. It is the internal step of
    `hierarchical_pool`, not a published statistic, and the tests reach for it by
    name to measure the mechanism itself rather than the model on top of it.
    """
    if epsilon <= 0.0:
        raise ValueError("epsilon must be positive; a zero budget is not a privacy setting")
    scale = 2.0 * cap / epsilon
    units = sorted({unit for by_unit in contributions.values() for unit in by_unit})
    totals: dict[str, list[float]] = {u: [0.0, 0.0] for u in units}
    for tenant in sorted(contributions):
        for unit in sorted(contributions[tenant]):
            successes, trials = contributions[tenant][unit]
            trials = min(max(float(trials), 0.0), cap)
            successes = min(max(float(successes), 0.0), trials)
            totals[unit][0] += successes
            totals[unit][1] += trials
    out: dict[str, tuple[float, float]] = {}
    for unit in units:
        # One deterministic stream per unit, keyed by the unit's own name, so
        # adding a unit does not reshuffle the noise on every other unit and
        # make two releases differenceable.
        rng = random.Random(str(seed) + "|" + unit)
        noised_successes = totals[unit][0] + laplace_sample(rng, scale)
        noised_trials = totals[unit][1] + laplace_sample(rng, scale)
        noised_trials = max(noised_trials, 1.0)
        noised_successes = min(max(noised_successes, 0.0), noised_trials)
        out[unit] = (noised_successes, noised_trials)
    return out


def _tau_grid(ys: Sequence[float], sigmas: Sequence[float], points: int):
    """
    p(tau | y) on a grid, under a uniform prior on tau (BDA ch. 5.4).

    mu is integrated out analytically at each tau, which is what makes the whole
    posterior a one-dimensional quadrature.
    """
    spread = max(sigmas) if sigmas else 1.0
    observed = math.sqrt(max(math.fsum((y - mean(ys)) ** 2 for y in ys) / max(len(ys) - 1, 1), 0.0))
    tau_max = max(4.0 * spread, 4.0 * observed, 1e-6)
    step = tau_max / points
    grid = [(i + 0.5) * step for i in range(points)]
    logs = []
    mus = []
    v_mus = []
    for tau in grid:
        precisions = [1.0 / (s * s + tau * tau) for s in sigmas]
        v_mu = 1.0 / math.fsum(precisions)
        mu_hat = v_mu * math.fsum(p * y for p, y in zip(precisions, ys))
        log_p = 0.5 * math.log(v_mu)
        for y, s, p in zip(ys, sigmas, precisions):
            log_p += 0.5 * math.log(p) - 0.5 * (y - mu_hat) ** 2 * p
        logs.append(log_p)
        mus.append(mu_hat)
        v_mus.append(v_mu)
    peak = max(logs)
    weights = [math.exp(v - peak) for v in logs]
    total = math.fsum(weights)
    weights = [w / total for w in weights]
    return grid, weights, mus, v_mus


def _quantiles(values: Sequence[float], qs: Sequence[float]) -> list[float]:
    ordered = sorted(values)
    out = []
    for q in qs:
        if not ordered:
            out.append(float("nan"))
            continue
        pos = q * (len(ordered) - 1)
        low = int(math.floor(pos))
        high = min(low + 1, len(ordered) - 1)
        out.append(ordered[low] + (pos - low) * (ordered[high] - ordered[low]))
    return out


def _pool_posterior(ys, sigmas, *, draws, seed, points):
    """Seeded draws from the exact grid posterior. Returns per-unit draws and tau draws."""
    grid, weights, mus, v_mus = _tau_grid(ys, sigmas, points)
    cumulative = []
    running = 0.0
    for w in weights:
        running += w
        cumulative.append(running)
    rng = random.Random(seed)
    tau_draws = []
    theta_draws = [[] for _ in ys]
    for _ in range(draws):
        u = rng.random()
        index = 0
        for i, c in enumerate(cumulative):
            if u <= c:
                index = i
                break
        else:
            index = len(cumulative) - 1
        tau = grid[index]
        mu = rng.gauss(mus[index], math.sqrt(v_mus[index]))
        tau_draws.append(tau)
        for j, (y, s) in enumerate(zip(ys, sigmas)):
            precision = 1.0 / (s * s) + (1.0 / (tau * tau) if tau > 0 else 1e12)
            centre = (y / (s * s) + mu * (1.0 / (tau * tau) if tau > 0 else 1e12)) / precision
            theta_draws[j].append(rng.gauss(centre, math.sqrt(1.0 / precision)))
    return grid, weights, tau_draws, theta_draws


def hierarchical_pool(
    observations,
    *,
    levels,
    seed,
    draws=4000,
    min_units_per_level=5,
    epsilon=1.0,
    refresh_cadence="weekly",
    contribution_cap=DEFAULT_CONTRIBUTION_CAP,
    tenant_budget=None,
    spent_epsilon=None,
    batch_ref="",
    as_of=None,
) -> Evidence:
    """bayes.hierarchical_pool. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method_id = "bayes.hierarchical_pool"
    phash = params_hash(
        method_id,
        1,
        {
            "levels": list(levels),
            "seed": seed,
            "draws": draws,
            "min_units_per_level": min_units_per_level,
            "epsilon": epsilon,
            "refresh_cadence": refresh_cadence,
            "contribution_cap": contribution_cap,
            "tenant_budget": tenant_budget,
        },
    )
    observations = list(observations)
    stamp = _derive_as_of(observations, as_of)
    levels = tuple(levels)
    tenant_level = next((lv for lv in levels if lv in ("tenant", "tenant_key", "tenant_ref")), None)
    unit_levels = [lv for lv in levels if lv != tenant_level]
    unit_level = unit_levels[-1] if unit_levels else "group_key"
    cross_tenant = tenant_level is not None
    batch = batch_ref or (stamp.date().isoformat() + ":" + refresh_cadence)

    empty = {
        "units": [],
        "tau": None,
        "tau_lo": None,
        "tau_hi": None,
        "pooling_factor": None,
        "epsilon_spent": 0.0,
        "as_of_batch": batch,
    }

    # ---- read the units -------------------------------------------------
    direct = [o for o in observations if _get(o, "effect") is not None]
    contributions: dict[str, dict[str, list[float]]] = {}
    verticals = set()
    if direct:
        units = []
        for obs in observations:
            ref = _level_value(obs, unit_level) or str(_get(obs, "group_ref"))
            units.append((ref, float(_get(obs, "effect")), float(_get(obs, "std_error"))))
    else:
        units = []
        for obs in observations:
            unit_ref = _level_value(obs, unit_level)
            if unit_ref is None:
                unit_ref = str(_get(obs, "group_key") or _get(obs, "group_ref"))
            tenant = _level_value(obs, tenant_level) if cross_tenant else "__single__"
            if tenant is None:
                tenant = "__unattributed__"
            vertical = _level_value(obs, "vertical")
            if vertical is not None:
                verticals.add(vertical)
            slot = contributions.setdefault(tenant, {}).setdefault(unit_ref, [0.0, 0.0])
            slot[0] += float(_get(obs, "successes", 0) or 0)
            slot[1] += float(_get(obs, "trials", 0) or 0)

    n_units = len(units) if direct else len({u for t in contributions.values() for u in t})
    tenants = sorted(contributions) if not direct else []

    if n_units < max(min_units_per_level, 2):
        return insufficient(
            method_id, n=n_units, as_of=stamp, empty_value=empty, unit="rate",
            params_hash=phash,
            caveats=(
                "Pooling needs at least " + str(min_units_per_level) + " units per level; there "
                "are " + str(n_units) + ". With fewer, the between-group variance is not "
                "identified at all and the pooled figure would be the prior wearing a number.",
            ),
        )

    checks = []
    excluded_tenants: list[str] = []

    # ---- the vertical guard --------------------------------------------
    if len(verticals) > 1:
        return Evidence(
            value=empty,
            n=n_units,
            method=method_id,
            as_of=stamp,
            checks=(
                Check(
                    id="vertical-homogeneous",
                    label="Every contributing tenant is in the same vertical",
                    status="FAIL",
                    statistic=float(len(verticals)),
                    blocking=True,
                    detail=(
                        "This pool mixes " + str(len(verticals)) + " verticals ("
                        + ", ".join(sorted(verticals)) + "). Tenants are exchangeable within a "
                        "vertical and not across one, so a housing society is not pooled with a "
                        "sports club. Nothing is published."
                    ),
                ),
            ),
            caveats=("Pooling refused: the contributing tenants are not in one vertical.",),
            unit="rate",
            params_hash=phash,
        )

    epsilon_spent = 0.0
    max_after = 0.0
    if cross_tenant and not direct:
        # ---- the privacy budget -----------------------------------------
        spent_epsilon = dict(spent_epsilon or {})
        if tenant_budget is not None:
            for tenant in list(contributions):
                if spent_epsilon.get(tenant, 0.0) + epsilon > tenant_budget + 1e-12:
                    excluded_tenants.append(tenant)
                    del contributions[tenant]
        tenants = sorted(contributions)

        trials_by_tenant = {
            t: math.fsum(v[1] for v in by_unit.values()) for t, by_unit in contributions.items()
        }
        total_trials = math.fsum(trials_by_tenant.values())
        share = (max(trials_by_tenant.values()) / total_trials) if total_trials > 0 else 1.0

        below_floor = len(tenants) < MIN_TENANTS
        concentrated = share > MAX_TENANT_SHARE

        checks.append(
            Check(
                id="min-tenants",
                label="Enough contributing tenants that no one of them is the pool",
                status="FAIL" if below_floor else "PASS",
                statistic=float(len(tenants)),
                blocking=True,
                detail=(
                    "Only " + str(len(tenants)) + " tenant(s) contribute, against a floor of "
                    + str(MIN_TENANTS) + ". Below that a tenant's own data would dominate the "
                    "'learned' prior even before noise is added. Nothing is published."
                ) if below_floor else "",
            )
        )
        checks.append(
            Check(
                id="tenant-concentration",
                label="No single tenant supplies more than a quarter of the observations",
                status="FAIL" if concentrated else "PASS",
                statistic=share,
                blocking=True,
                detail=(
                    "One tenant supplies " + format(100.0 * share, ".1f") + "% of the "
                    "observations, above the " + format(100.0 * MAX_TENANT_SHARE, ".0f")
                    + "% ceiling. The pooled prior would largely be that tenant reading its own "
                    "data back. Nothing is published."
                ) if concentrated else "",
            )
        )
        checks.append(
            Check(
                id="dp-budget-exhausted",
                label="No tenant contributes beyond its rolling privacy budget",
                status=("FAIL" if (excluded_tenants and below_floor)
                        else "WARN" if excluded_tenants else "PASS"),
                statistic=float(len(excluded_tenants)),
                blocking=bool(excluded_tenants and below_floor),
                detail=(
                    (str(len(excluded_tenants)) + " tenant(s) had spent their rolling-quarter "
                     "epsilon budget and were EXCLUDED from this pool rather than the guarantee "
                     "being silently weakened. That left too few tenants to pool at all, so "
                     "nothing is published.")
                    if (excluded_tenants and below_floor) else
                    (str(len(excluded_tenants)) + " tenant(s) had spent their rolling-quarter "
                     "epsilon budget and were excluded from this pool. Their contribution is "
                     "dropped, not noised harder: the guarantee is not negotiable.")
                ) if excluded_tenants else "",
            )
        )
        checks.append(
            Check(
                id="privacy-notice",
                label="Cross-tenant pooling is on, and every contribution is DP-protected",
                status="PASS",
                statistic=float(epsilon),
                detail=(
                    "Each tenant contributes ONE Laplace-noised sufficient statistic per group "
                    "per batch, at epsilon " + repr(float(epsilon)) + " per run, refreshed "
                    + refresh_cadence + " rather than live. A tenant admin can opt this community "
                    "out of contributing and still receive the pooled prior."
                ),
            )
        )

        if below_floor or concentrated:
            return Evidence(
                value=empty,
                n=n_units,
                method=method_id,
                as_of=stamp,
                checks=tuple(checks),
                caveats=(
                    "Cross-tenant pooling was refused by its own floors. The floors are a second "
                    "line of defense behind the DP mechanism, not a substitute for it.",
                ),
                unit="rate",
                params_hash=phash,
                n_excluded=len(excluded_tenants),
                exclusion_reason=(
                    "privacy budget exhausted for this rolling quarter" if excluded_tenants else ""
                ),
            )

        noised = _noise_contributions(
            {t: {u: (v[0], v[1]) for u, v in by_unit.items()}
             for t, by_unit in contributions.items()},
            epsilon=epsilon,
            cap=float(contribution_cap),
            seed=seed,
        )
        # Epsilon is spent PER TENANT PER RUN, not summed across tenants: DP is a
        # per-contributor guarantee. What composes, and what the budget check
        # reads, is one tenant's spend across repeated runs.
        epsilon_spent = float(epsilon)
        max_after = max(
            (compose_epsilon([spent_epsilon.get(t, 0.0), epsilon]) for t in tenants),
            default=float(epsilon),
        )
        for unit_ref in sorted(noised):
            successes, trials = noised[unit_ref]
            rate = min(max(successes / trials, 1e-6), 1.0 - 1e-6)
            units.append((unit_ref, rate, math.sqrt(rate * (1.0 - rate) / trials)))
    elif not direct:
        checks.append(
            Check(
                id="privacy-notice",
                label="Cross-tenant pooling is on, and every contribution is DP-protected",
                status="SKIPPED",
                detail=(
                    "`levels` names no tenant level, so this is a within-tenant pool. No "
                    "cross-tenant statistic is formed, no DP noise is added and epsilon_spent is "
                    "zero. The tenant floors are skipped for the same reason."
                ),
            )
        )
        for tenant_by_unit in contributions.values():
            for unit_ref in sorted(tenant_by_unit):
                successes, trials = tenant_by_unit[unit_ref]
                if trials <= 0:
                    continue
                rate = min(max(successes / trials, 1e-6), 1.0 - 1e-6)
                units.append((unit_ref, rate, math.sqrt(rate * (1.0 - rate) / trials)))
    else:
        checks.append(
            Check(
                id="privacy-notice",
                label="Cross-tenant pooling is on, and every contribution is DP-protected",
                status="SKIPPED",
                detail=(
                    "These units arrived as effects with standard errors rather than as "
                    "per-tenant counts, so there is no per-tenant contribution to noise and "
                    "epsilon_spent is zero."
                ),
            )
        )

    refs = [u[0] for u in units]
    ys = [u[1] for u in units]
    sigmas = [max(u[2], 1e-9) for u in units]
    n_units = len(units)

    # ---- the posterior --------------------------------------------------
    grid, weights, tau_draws, theta_draws = _pool_posterior(
        ys, sigmas, draws=draws, seed=seed, points=TAU_GRID
    )
    tau_mean = math.fsum(t * w for t, w in zip(grid, weights))
    tau_lo, tau_median, tau_hi = _quantiles(tau_draws, (0.025, 0.5, 0.975))

    unit_rows = []
    pooling_factors = []
    for j, ref in enumerate(refs):
        draws_j = theta_draws[j]
        lo, mid, hi = _quantiles(draws_j, (0.025, 0.5, 0.975))
        factor = (sigmas[j] ** 2) / (sigmas[j] ** 2 + tau_median ** 2) if tau_median > 0 else 1.0
        pooling_factors.append(factor)
        unit_rows.append(
            {
                "unit_ref": ref,
                "raw": ys[j],
                "std_error": sigmas[j],
                "pooled": mean(draws_j),
                "median": mid,
                "lo": lo,
                "hi": hi,
                "pooling_factor": factor,
                "n": None,
            }
        )

    # ---- convergence, by grid refinement and a second draw stream -------
    fine_grid, fine_weights, _m, _v = _tau_grid(ys, sigmas, TAU_GRID * 2)
    tau_fine = math.fsum(t * w for t, w in zip(fine_grid, fine_weights))
    grid_error = abs(tau_fine - tau_mean) / (abs(tau_mean) + 1e-12)
    _g2, _w2, _t2, theta_draws_b = _pool_posterior(
        ys, sigmas, draws=draws, seed=seed + 1, points=TAU_GRID
    )
    worst_mc = 0.0
    for j in range(n_units):
        spread = max(
            math.sqrt(max(math.fsum((d - mean(theta_draws[j])) ** 2 for d in theta_draws[j])
                          / max(len(theta_draws[j]) - 1, 1), 0.0)),
            1e-12,
        )
        worst_mc = max(worst_mc, abs(mean(theta_draws[j]) - mean(theta_draws_b[j])) / spread)
    # The tolerance on the second draw stream is the Monte Carlo error the draw
    # count itself implies, three standard errors of a difference of two means of
    # `draws` draws each, rather than a fixed number that would pass at 8000 and
    # fail at 400 for no reason but the sample size.
    mc_tolerance = 3.0 * math.sqrt(2.0 / max(draws, 1))
    converged = grid_error < 1e-3 and worst_mc < mc_tolerance

    checks.append(
        Check(
            id="convergence",
            label="The posterior is resolved, by grid refinement and a second draw stream",
            status="PASS" if converged else "FAIL",
            statistic=max(grid_error, worst_mc),
            blocking=not converged,
            detail=(
                "The posterior is computed by deterministic quadrature over tau, not by MCMC, so "
                "R-hat does not apply. The equivalent criterion failed: doubling the grid moved "
                "E[tau] by " + format(grid_error, ".2e") + " and a second seeded draw stream moved "
                "a unit mean by " + format(worst_mc, ".3f") + " posterior standard deviations, "
                "against a tolerance of " + format(mc_tolerance, ".3f") + ". "
                "Nothing is published from an unresolved posterior."
            ) if not converged else (
                "Computed by quadrature rather than MCMC: doubling the tau grid moves E[tau] by "
                + format(grid_error, ".2e") + " and a second seeded draw stream moves every unit "
                "mean by " + format(worst_mc, ".3f") + " posterior standard deviations, against a "
                "tolerance of " + format(mc_tolerance, ".3f") + "."
            ),
        )
    )

    # tau is identified only if its posterior keeps clear of zero on the scale
    # of the noise it has to be seen through. A tau grid never returns exactly
    # zero, so "tau_lo > 0" would be a check that always passes.
    noise_scale = sorted(sigmas)[len(sigmas) // 2]
    tau_identified = tau_lo > 0.2 * noise_scale and n_units >= 8
    checks.append(
        Check(
            id="tau-identified",
            label="The between-group variance is identified by the data",
            status="PASS" if tau_identified else "WARN",
            statistic=tau_median,
            detail=(
                "The posterior for tau runs down to zero (2.5% point "
                + format(tau_lo, ".4g") + ", median " + format(tau_median, ".4g") + ") on "
                + str(n_units) + " units. Complete pooling is inside the credible region, so the "
                "pooling factor is being driven by the prior on tau as much as by the data. Read "
                "the pooled figures as a smoothing, not as a measurement of how different these "
                "units are."
            ) if not tau_identified else "",
        )
    )

    value = {
        "units": unit_rows,
        "tau": tau_median,
        "tau_lo": tau_lo,
        "tau_hi": tau_hi,
        "tau_mean": tau_mean,
        "pooling_factor": mean(pooling_factors),
        "epsilon_spent": epsilon_spent,
        "max_tenant_epsilon_after": max_after,
        "as_of_batch": batch,
        "n_tenants": len(tenants),
        "n_units": n_units,
    }
    if not converged:
        value = dict(empty, epsilon_spent=epsilon_spent)

    caveats = [
        "The pooling factor says how much of each unit's figure came from the pool rather than "
        "from its own data. At " + format(mean(pooling_factors), ".2f") + " here, a unit with "
        "little data is mostly being told what everyone else looks like.",
        "Intervals are credible intervals from the posterior, read as Bayesian statements about "
        "these units given the model.",
    ]
    if epsilon_spent > 0:
        caveats.insert(
            0,
            "Every contribution to this pool was Laplace-noised before it was combined with any "
            "other tenant's, at epsilon " + repr(float(epsilon)) + " per tenant per run, and the "
            "pool refreshes " + refresh_cadence + " rather than live. The figures below are "
            "deliberately imprecise for that reason.",
        )
    if excluded_tenants:
        caveats.append(
            str(len(excluded_tenants)) + " tenant(s) were excluded for having spent their "
            "rolling-quarter privacy budget."
        )

    return Evidence(
        value=value,
        n=n_units,
        method=method_id,
        as_of=stamp,
        interval=(tau_lo, tau_hi),
        interval_kind="credible-95",
        assumptions=(
            "Tenants are exchangeable within a vertical, and not across one.",
            "Each tenant's contribution per batch is bounded to one sufficient statistic per "
            "group, clamped at " + format(float(contribution_cap), ".0f") + ", which is what makes "
            "the noise scale a guarantee rather than a hope.",
            "The pool refreshes " + refresh_cadence + ", never live, so no single tenant's update "
            "is isolable by differencing across releases.",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        unit="rate",
        params_hash=phash,
        n_excluded=len(excluded_tenants),
        exclusion_reason=(
            "privacy budget exhausted for this rolling quarter" if excluded_tenants else ""
        ),
    )


__all__ = [
    "beta_binomial_shrink",
    "beta_ppf",
    "fit_beta_prior",
    "gamma_poisson_shrink",
    "gamma_ppf",
    "hierarchical_pool",
    "rank_by_posterior_lower_bound",
]
