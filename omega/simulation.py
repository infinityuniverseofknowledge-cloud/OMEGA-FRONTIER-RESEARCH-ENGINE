"""Seeded, bounded ecological toy model, not a validated forecasting tool.

P[t+1] = P[t] * max(0, 1 + r*(1-P[t]/K) - pressure + noise).
Noise is independent uniform variation in [-noise_fraction, noise_fraction].
Population is continuous, abstract, and clipped to 10*K for numerical safety.
Uncertainty bands reflect only this assumed noise, not empirical confidence.
"""
from __future__ import annotations

import math
import random
from typing import Any


def _number(name: str, value: Any, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a finite number")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return value


def _integer(name: str, value: Any, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def _quantile(ordered: list[float], q: float) -> float:
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def simulate(parameters: dict[str, Any], *, seed: int = 0) -> dict[str, Any]:
    """Simulate independent realizations and return per-step 5/50/95% quantiles.

    Required keys: initial_population, carrying_capacity, growth_rate, pressure,
    noise_fraction, steps and replicates.  Rates are dimensionless per time step;
    K and initial population are abstract population units. Seed is 0..2**32-1.
    At most 200,000 replicate-steps are allowed. Threshold <1 is an arbitrary
    quasi-extinction indicator, not species extinction or a real risk estimate.
    """
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be a dict")
    required = {"initial_population", "carrying_capacity", "growth_rate", "pressure",
                "noise_fraction", "steps", "replicates"}
    missing = required - parameters.keys()
    extra = parameters.keys() - required
    if missing or extra:
        raise ValueError(f"parameter keys: missing={sorted(missing)}, unexpected={sorted(extra)}")
    k = _number("carrying_capacity", parameters["carrying_capacity"], 0.001, 1e9)
    initial = _number("initial_population", parameters["initial_population"], 0, 2*k)
    r = _number("growth_rate", parameters["growth_rate"], 0, 1)
    pressure = _number("pressure", parameters["pressure"], 0, 1)
    noise = _number("noise_fraction", parameters["noise_fraction"], 0, 0.5)
    steps = _integer("steps", parameters["steps"], 1, 1000)
    replicates = _integer("replicates", parameters["replicates"], 1, 1000)
    seed = _integer("seed", seed, 0, 2**32 - 1)
    if steps * replicates > 200000:
        raise ValueError("steps * replicates must not exceed 200000")
    rng = random.Random(seed)
    series = [[initial] * replicates]
    populations = [initial] * replicates
    cap_count = 0
    for _ in range(steps):
        for i, pop in enumerate(populations):
            variation = rng.uniform(-noise, noise)
            factor = max(0.0, 1.0 + r * (1.0 - pop / k) - pressure + variation)
            next_pop = pop * factor
            if next_pop > 10 * k:
                next_pop = 10 * k
                cap_count += 1
            populations[i] = next_pop
        series.append(populations.copy())
    trajectory = []
    for step, values in enumerate(series):
        values.sort()
        trajectory.append({"step": step, "p05": _quantile(values, .05),
                           "median": _quantile(values, .5), "p95": _quantile(values, .95)})
    return {
        "seed": seed, "parameters": dict(parameters), "trajectory": trajectory,
        "final_below_one_fraction": sum(x < 1 for x in populations) / replicates,
        "population_cap_events": cap_count,
        "caveats": ["Synthetic single-population model; not empirically calibrated or validated.",
                    "Quantiles reflect only the chosen uniform noise, not real-world confidence intervals.",
                    "Population is continuous, pressure is constant, and values are capped at 10 times carrying capacity.",
                    "Below one unit is an arbitrary quasi-extinction threshold, not a biological extinction estimate."],
    }
