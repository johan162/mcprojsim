import numpy as np
from typing import Any


def rolling_capacity_forecast(
    completed: np.ndarray,
    team_size: np.ndarray,
    future_team_size: np.ndarray,
    window_size: int = 24,
    future_sprints: int = 5,
    posterior_samples: int = 20000,
    alpha_prior: float = 2.0,
    beta_prior: float = 2.0 / 20.0,
    full_weight_recent_sprints: int = 5,
    decay_power: float = 1.5,
    observation_model: str = "poisson",
    dispersion_k: float | None = None,
    seed: int = 42,
) -> tuple[np.ndarray, list[dict[str, float]]]:
    """Forecast completed story points for the next sprints.

    The model treats completed work in each sprint as:

      completed_t ~ Poisson(lambda_t * team_size_t)

    and uses a Gamma prior on the per-person completion rate lambda. Historical
    sprints are recency-weighted with a raised-cosine taper: the most recent
    sprints can keep full weight while older sprints smoothly decay toward zero.
    For each future sprint, the model updates the posterior from the weighted
    rolling window, samples a predictive completion value from either Poisson
    or Negative Binomial, appends that simulated sprint to the history, and
    repeats.
    """
    if len(completed) != len(team_size):
        raise ValueError("completed and team_size must have the same length")
    if len(completed) < 2:
        raise ValueError("at least two historical sprints are required")
    if future_sprints != len(future_team_size):
        raise ValueError("future_team_size length must equal future_sprints")
    if window_size < 2:
        raise ValueError("window_size must be at least 2")
    if full_weight_recent_sprints < 1:
        raise ValueError("full_weight_recent_sprints must be at least 1")
    if full_weight_recent_sprints > window_size:
        raise ValueError("full_weight_recent_sprints must be <= window_size")
    if decay_power <= 0.0:
        raise ValueError("decay_power must be positive")
    if observation_model not in {"poisson", "neg_binomial"}:
        raise ValueError("observation_model must be 'poisson' or 'neg_binomial'")
    if observation_model == "neg_binomial" and dispersion_k is None:
        raise ValueError("dispersion_k is required for neg_binomial observation model")
    if dispersion_k is not None and dispersion_k <= 0.0:
        raise ValueError("dispersion_k must be positive")

    rng = np.random.default_rng(seed)
    simulated_paths = np.zeros((posterior_samples, future_sprints), dtype=int)

    for sample_index in range(posterior_samples):
        path_completed = completed.astype(int).tolist()
        path_team_size = team_size.astype(float).tolist()

        for sprint_index in range(future_sprints):
            recent_completed = np.asarray(path_completed[-window_size:], dtype=float)
            recent_team = np.asarray(path_team_size[-window_size:], dtype=float)
            weights = build_recency_weights(
                window_size=window_size,
                full_weight_recent_sprints=full_weight_recent_sprints,
                decay_power=decay_power,
            )

            alpha_post = alpha_prior + float(np.dot(weights, recent_completed))
            beta_post = beta_prior + float(np.dot(weights, recent_team))

            lambda_next = rng.gamma(shape=alpha_post, scale=1.0 / beta_post)
            mu_pred = lambda_next * future_team_size[sprint_index]

            if observation_model == "poisson" or (
                observation_model == "neg_binomial"
                and dispersion_k is not None
                and np.isinf(dispersion_k)
            ):
                predicted_completed = rng.poisson(mu_pred)
            else:
                assert dispersion_k is not None
                success_prob = dispersion_k / (dispersion_k + mu_pred)
                predicted_completed = rng.negative_binomial(dispersion_k, success_prob)

            simulated_paths[sample_index, sprint_index] = predicted_completed
            path_completed.append(int(predicted_completed))
            path_team_size.append(float(future_team_size[sprint_index]))

    summaries: list[dict[str, float]] = []
    for sprint_index in range(future_sprints):
        forecast = simulated_paths[:, sprint_index]
        summaries.append(
            {
                "mean": float(np.mean(forecast)),
                "p10": float(np.percentile(forecast, 10)),
                "p50": float(np.percentile(forecast, 50)),
                "p80": float(np.percentile(forecast, 80)),
                "p90": float(np.percentile(forecast, 90)),
            }
        )

    return simulated_paths, summaries


def build_recency_weights(
    window_size: int,
    full_weight_recent_sprints: int,
    decay_power: float,
) -> np.ndarray:
    """Build smooth recency weights from oldest to newest sprint.

    The newest ``full_weight_recent_sprints`` observations receive weight 1.0.
    Older observations follow a raised-cosine taper down to 0.0 for the oldest
    sprint in the window.
    """
    if full_weight_recent_sprints >= window_size:
        return np.ones(window_size, dtype=float)

    taper_count = window_size - full_weight_recent_sprints
    taper_progress = np.linspace(0.0, 1.0, taper_count, endpoint=True)
    taper_weights = np.sin(0.5 * np.pi * taper_progress) ** decay_power

    return np.concatenate(
        [taper_weights, np.ones(full_weight_recent_sprints, dtype=float)]
    )


def calculate_posterior_parameters(
    completed: np.ndarray,
    team_size: np.ndarray,
    window_size: int,
    alpha_prior: float,
    beta_prior: float,
    full_weight_recent_sprints: int,
    decay_power: float,
) -> dict[str, Any]:
    recent_completed = np.asarray(completed[-window_size:], dtype=float)
    recent_team = np.asarray(team_size[-window_size:], dtype=float)
    weights = build_recency_weights(
        window_size=window_size,
        full_weight_recent_sprints=full_weight_recent_sprints,
        decay_power=decay_power,
    )

    weighted_completed_sum = float(np.dot(weights, recent_completed))
    weighted_team_sum = float(np.dot(weights, recent_team))
    alpha_post = alpha_prior + weighted_completed_sum
    beta_post = beta_prior + weighted_team_sum

    return {
        "window_size": float(window_size),
        "full_weight_recent_sprints": float(full_weight_recent_sprints),
        "decay_power": decay_power,
        "weight_sum": float(weights.sum()),
        "oldest_weight": float(weights[0]),
        "newest_weight": float(weights[-1]),
        "weights": weights,
        "observed_completed_sum": float(recent_completed.sum()),
        "observed_team_sum": float(recent_team.sum()),
        "weighted_completed_sum": weighted_completed_sum,
        "weighted_team_sum": weighted_team_sum,
        "alpha_prior": alpha_prior,
        "beta_prior": beta_prior,
        "alpha_post": alpha_post,
        "beta_post": beta_post,
        "posterior_rate_mean": alpha_post / beta_post,
    }


def fit_nb_dispersion_from_residual_variance(
    completed: np.ndarray,
    team_size: np.ndarray,
    weights: np.ndarray,
    posterior_rate_mean: float,
) -> dict[str, float]:
    """Estimate NB dispersion using weighted residual variance moments.

    Uses the moment identity Var(Y|mu) = mu + mu^2 / k.
    """
    mu = posterior_rate_mean * np.asarray(team_size, dtype=float)
    y = np.asarray(completed, dtype=float)

    numerator = float(np.dot(weights, mu**2))
    denominator = float(np.dot(weights, (y - mu) ** 2 - y))

    overdispersion_phi = 0.0
    if numerator > 0.0:
        overdispersion_phi = max(0.0, denominator / numerator)

    if overdispersion_phi <= 1e-12:
        dispersion_k = float("inf")
    else:
        dispersion_k = 1.0 / overdispersion_phi

    weighted_mean = float(np.dot(weights, y) / weights.sum())
    weighted_variance = float(np.dot(weights, (y - weighted_mean) ** 2) / weights.sum())

    return {
        "weighted_mean_completed": weighted_mean,
        "weighted_variance_completed": weighted_variance,
        "overdispersion_phi": overdispersion_phi,
        "dispersion_k": dispersion_k,
    }


def print_probability_table(
    title: str,
    simulated_paths: np.ndarray,
    thresholds: list[int],
) -> None:
    print()
    print(title)
    header = f"{'sprint':>6}" + "".join(
        f" {f'>= {threshold} SP':>12}" for threshold in thresholds
    )
    print(header)

    for sprint_index in range(simulated_paths.shape[1]):
        forecast = simulated_paths[:, sprint_index]
        row = f"{sprint_index + 1:>6}"
        for threshold in thresholds:
            probability = 100.0 * float(np.mean(forecast >= threshold))
            row += f" {f'{probability:5.1f}%':>12}"
        print(row)


def print_forecast_tables(
    variant_name: str,
    simulated_paths: np.ndarray,
    summaries: list[dict[str, float]],
    delivery_thresholds: list[int],
    commitment_levels: list[int],
) -> None:
    print()
    print(f"Forecast variant: {variant_name}")
    print("Quantile view (xth percentile threshold)")
    print("sprint  mean  p10  p50  p80  p90")
    for sprint_number, summary in enumerate(summaries, start=1):
        print(
            f"{sprint_number:>6}"
            f" {summary['mean']:>5.1f}"
            f" {summary['p10']:>4.0f}"
            f" {summary['p50']:>4.0f}"
            f" {summary['p80']:>4.0f}"
            f" {summary['p90']:>4.0f}"
        )

    print()
    print("Exceedance view (chance of reaching at least X story points)")
    print(
        f"{'sprint':>6} {'>= P10 value':>16} {'>= P50 value':>16} {'>= P80 value':>16} {'>= P90 value':>16}"
    )
    for sprint_index, summary in enumerate(summaries):
        forecast = simulated_paths[:, sprint_index]

        q10 = int(round(summary["p10"]))
        q50 = int(round(summary["p50"]))
        q80 = int(round(summary["p80"]))
        q90 = int(round(summary["p90"]))

        prob_ge_q10 = np.mean(forecast >= q10)
        prob_ge_q50 = np.mean(forecast >= q50)
        prob_ge_q80 = np.mean(forecast >= q80)
        prob_ge_q90 = np.mean(forecast >= q90)

        col_q10 = f"{100.0 * prob_ge_q10:5.1f}% (>= {q10:>3})"
        col_q50 = f"{100.0 * prob_ge_q50:5.1f}% (>= {q50:>3})"
        col_q80 = f"{100.0 * prob_ge_q80:5.1f}% (>= {q80:>3})"
        col_q90 = f"{100.0 * prob_ge_q90:5.1f}% (>= {q90:>3})"

        print(
            f"{sprint_index + 1:>6}"
            f" {col_q10:>16}"
            f" {col_q50:>16}"
            f" {col_q80:>16}"
            f" {col_q90:>16}"
        )

    print_probability_table(
        title="Probability of completing at least X story points",
        simulated_paths=simulated_paths,
        thresholds=delivery_thresholds,
    )

    print_probability_table(
        title="Probability of fully meeting commitment level C",
        simulated_paths=simulated_paths,
        thresholds=commitment_levels,
    )


if __name__ == "__main__":
    completed = np.array(
        [
            85,
            63,
            73,
            81,
            92,
            46,
            65,
            31,
            82,
            49,
            86,
            25,
            71,
            71,
            86,
            96,
            55,
            44,
            90,
            46,
            91,
            67,
            46,
            111,
        ],
        dtype=int,
    )
    team_size = np.array([5] * len(completed), dtype=float)
    committed = np.array(
        [
            105,
            68,
            84,
            93,
            102,
            90,
            63,
            67,
            80,
            39,
            66,
            48,
            74,
            87,
            67,
            92,
            87,
            53,
            97,
            94,
            146,
            104,
            111,
            129,
        ],
        dtype=int,
    )

    future_sprints = 5
    future_team_size = np.repeat(team_size[-1], future_sprints)
    window_size = 24
    alpha_prior = 2.0
    beta_prior = 2.0 / 20.0
    full_weight_recent_sprints = 5
    decay_power = 1.5
    delivery_thresholds = [50, 60, 70, 80, 90]
    commitment_levels = [60, 70, 80, 90, 100]

    posterior_params = calculate_posterior_parameters(
        completed=completed,
        team_size=team_size,
        window_size=window_size,
        alpha_prior=alpha_prior,
        beta_prior=beta_prior,
        full_weight_recent_sprints=full_weight_recent_sprints,
        decay_power=decay_power,
    )

    recent_completed = completed[-window_size:]
    recent_team_size = team_size[-window_size:]
    nb_dispersion = fit_nb_dispersion_from_residual_variance(
        completed=recent_completed,
        team_size=recent_team_size,
        weights=posterior_params["weights"],
        posterior_rate_mean=posterior_params["posterior_rate_mean"],
    )

    poisson_paths, poisson_summaries = rolling_capacity_forecast(
        completed=completed,
        team_size=team_size,
        future_team_size=future_team_size,
        window_size=window_size,
        future_sprints=future_sprints,
        posterior_samples=20000,
        alpha_prior=alpha_prior,
        beta_prior=beta_prior,
        full_weight_recent_sprints=full_weight_recent_sprints,
        decay_power=decay_power,
        observation_model="poisson",
        seed=42,
    )

    negbin_paths, negbin_summaries = rolling_capacity_forecast(
        completed=completed,
        team_size=team_size,
        future_team_size=future_team_size,
        window_size=window_size,
        future_sprints=future_sprints,
        posterior_samples=20000,
        alpha_prior=alpha_prior,
        beta_prior=beta_prior,
        full_weight_recent_sprints=full_weight_recent_sprints,
        decay_power=decay_power,
        observation_model="neg_binomial",
        dispersion_k=nb_dispersion["dispersion_k"],
        seed=42,
    )

    recent_completion_ratio = completed[-window_size:] / committed[-window_size:]

    print(f"Rolling window size: {window_size} historical sprints")
    print(
        "Recent observed completion ratio: "
        f"mean={recent_completion_ratio.mean():.2%}, "
        f"min={recent_completion_ratio.min():.2%}, "
        f"max={recent_completion_ratio.max():.2%}"
    )
    print()
    print("Calculated posterior parameters from the recency-weighted history")
    print(f"window_size: {posterior_params['window_size']:.0f}")
    print(
        "full-weight recent sprints: "
        f"{posterior_params['full_weight_recent_sprints']:.0f}"
    )
    print(f"decay_power: {posterior_params['decay_power']:.2f}")
    print(f"sum of recency weights: {posterior_params['weight_sum']:.4f}")
    print(f"oldest sprint weight: {posterior_params['oldest_weight']:.4f}")
    print(f"newest sprint weight: {posterior_params['newest_weight']:.4f}")
    print(f"completed_sum: {posterior_params['observed_completed_sum']:.0f}")
    print(f"team_size_sum: {posterior_params['observed_team_sum']:.0f}")
    print(f"weighted_completed_sum: {posterior_params['weighted_completed_sum']:.4f}")
    print(f"weighted_team_size_sum: {posterior_params['weighted_team_sum']:.4f}")
    print(f"alpha_prior: {posterior_params['alpha_prior']:.4f}")
    print(f"beta_prior: {posterior_params['beta_prior']:.4f}")
    print(f"alpha_post: {posterior_params['alpha_post']:.4f}")
    print(f"beta_post: {posterior_params['beta_post']:.4f}")
    print(
        "posterior mean completion rate per team member per sprint: "
        f"{posterior_params['posterior_rate_mean']:.4f}"
    )
    print(
        f"weighted historical mean completed: {nb_dispersion['weighted_mean_completed']:.4f}"
    )
    print(
        f"weighted historical variance completed: {nb_dispersion['weighted_variance_completed']:.4f}"
    )
    print(f"estimated overdispersion phi: {nb_dispersion['overdispersion_phi']:.6f}")
    if np.isinf(nb_dispersion["dispersion_k"]):
        print("estimated NB dispersion k: inf (falls back to Poisson)")
    else:
        print(f"estimated NB dispersion k: {nb_dispersion['dispersion_k']:.4f}")
    print()
    print("Recency weights by historical sprint (oldest -> newest)")
    print(
        f"{'idx':>3} {'completed':>9} {'team':>6} {'weight':>8} {'weighted_completed':>18} {'weighted_team':>14}"
    )
    history_completed = completed[-window_size:]
    history_team_size = team_size[-window_size:]
    for idx, (completed_value, team_value, weight) in enumerate(
        zip(
            history_completed,
            history_team_size,
            posterior_params["weights"],
            strict=False,
        ),
        start=1,
    ):
        print(
            f"{idx:>3}"
            f" {completed_value:>9}"
            f" {team_value:>6.1f}"
            f" {weight:>8.4f}"
            f" {completed_value * weight:>18.4f}"
            f" {team_value * weight:>14.4f}"
        )
    print()
    print("Predicted completion capacity for the next 5 sprints")
    print_forecast_tables(
        variant_name="Poisson observation model",
        simulated_paths=poisson_paths,
        summaries=poisson_summaries,
        delivery_thresholds=delivery_thresholds,
        commitment_levels=commitment_levels,
    )
    print_forecast_tables(
        variant_name="Negative Binomial observation model (fitted dispersion)",
        simulated_paths=negbin_paths,
        summaries=negbin_summaries,
        delivery_thresholds=delivery_thresholds,
        commitment_levels=commitment_levels,
    )
