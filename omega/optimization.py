"""Bounded offline experiments on symmetric integer TSP instances.

These are implementations for empirical investigation, not general performance
claims. All tours start and end at vertex 0. See research/optimization.md.
"""
from __future__ import annotations

import json
import math
import random
import time
from fractions import Fraction

from omega.mathcore import _matrix, held_karp_cycle, nearest_neighbor_2opt_cycle, optimality_gap

MAX_WEIGHT = 1_000_000_000
MAX_ITERATIONS = 1_000
MAX_SEEDS = 10
MAX_SEED = 2**64 - 1


def _int(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def _validate_matrix(distances):
    d = _matrix(distances)
    if any(w > MAX_WEIGHT for row in d for w in row):
        raise ValueError(f"weights must be at most {MAX_WEIGHT}")
    return d


def _validate_seed(seed):
    return _int(seed, 'seed', 0, MAX_SEED)


def random_matrix(n, seed, max_weight=100):
    """Seeded complete symmetric matrix; independent uniform integer edges.

    This distribution need not satisfy the triangle inequality.
    """
    _int(n, 'n', 1, 14)
    _validate_seed(seed)
    _int(max_weight, 'max_weight', 0, MAX_WEIGHT)
    rng = random.Random(seed)
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i):
            matrix[i][j] = matrix[j][i] = rng.randint(0, max_weight)
    return tuple(tuple(row) for row in matrix)


def route_cost(distances, route):
    """Validate a 0-anchored Hamiltonian cycle and return its exact cost."""
    d = _validate_matrix(distances)
    n = len(d)
    if (not isinstance(route, (tuple, list)) or len(route) != n + 1
            or any(isinstance(x, bool) or not isinstance(x, int) for x in route)
            or route[0] != 0 or route[-1] != 0
            or set(route[:-1]) != set(range(n))):
        raise ValueError('route must be a 0-anchored Hamiltonian cycle')
    return _cost(d, route)


def _cost(d, route):
    return sum(d[a][b] for a, b in zip(route, route[1:]))


def nearest_neighbor_cycle(distances):
    """Nearest neighbor from 0, tie-breaking by vertex number."""
    d = _validate_matrix(distances)
    remaining = set(range(1, len(d)))
    route = [0]
    while remaining:
        v = min(remaining, key=lambda x: (d[route[-1]][x], x))
        route.append(v)
        remaining.remove(v)
    route.append(0)
    return tuple(route), _cost(d, route)


def _initial(n, rng):
    tail = list(range(1, n))
    rng.shuffle(tail)
    return (0, *tail, 0)


def _reverse(route, i, j):
    return route[:i] + tuple(reversed(route[i:j + 1])) + route[j + 1:]


def _setup(distances, seed, iterations):
    return (_validate_matrix(distances), random.Random(_validate_seed(seed)),
            _int(iterations, 'iterations', 1, MAX_ITERATIONS))


def simulated_annealing_cycle(distances, seed, iterations=200):
    """Random reversal moves, geometric cooling and Metropolis acceptance.

    Returns the best tour visited, including the random starting tour.
    """
    d, rng, iterations = _setup(distances, seed, iterations)
    n = len(d)
    route = _initial(n, rng)
    cost = _cost(d, route)
    best, best_cost = route, cost
    if n < 3:
        return best, best_cost
    initial_temperature = max(1, max(max(row) for row in d))
    for step in range(iterations):
        i, j = sorted(rng.sample(range(1, n), 2))
        candidate = _reverse(route, i, j)
        new_cost = _cost(d, candidate)
        delta = new_cost - cost
        temperature = initial_temperature * (0.01 ** (step / max(1, iterations - 1)))
        if delta <= 0 or rng.random() < math.exp(-delta / temperature):
            route, cost = candidate, new_cost
            if cost < best_cost:
                best, best_cost = route, cost
    return best, best_cost


def tabu_search_cycle(distances, seed, iterations=200):
    """2-opt reversal neighborhood with bounded tabu memory and aspiration.

    A move is identified by its sorted pair of endpoint vertex labels; it is
    forbidden for five subsequent moves unless it beats the global best. Ties
    between equally good admissible neighbors are broken randomly.
    """
    d, rng, iterations = _setup(distances, seed, iterations)
    n = len(d)
    route = _initial(n, rng)
    cost = _cost(d, route)
    best, best_cost = route, cost
    if n < 3:
        return best, best_cost
    tabu = {}
    for step in range(iterations):
        candidates = []
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                move = tuple(sorted((route[i], route[j])))
                trial = _reverse(route, i, j)
                trial_cost = _cost(d, trial)
                if tabu.get(move, -1) < step or trial_cost < best_cost:
                    candidates.append((trial_cost, move, trial))
        if not candidates:
            break
        lowest = min(item[0] for item in candidates)
        cost, move, route = rng.choice([x for x in candidates if x[0] == lowest])
        tabu[move] = step + 5
        if cost < best_cost:
            best, best_cost = route, cost
    return best, best_cost


def genetic_cycle(distances, seed, iterations=200):
    """Elitist genetic algorithm with tournament selection, order crossover,
    and swap mutation. Population 16; each iteration is one generation.
    """
    d, rng, iterations = _setup(distances, seed, iterations)
    n = len(d)
    population = [_initial(n, rng) for _ in range(16)]
    if n < 3:
        return population[0], _cost(d, population[0])

    def tournament():
        return min((rng.choice(population) for _ in range(3)), key=lambda p: (_cost(d, p), p))

    def child(first, second):
        a, b = sorted(rng.sample(range(1, n), 2))
        segment = first[a:b + 1]
        used = set(segment)
        rest = [v for v in second[1:-1] if v not in used]
        tail = rest[:a - 1] + list(segment) + rest[a - 1:]
        if rng.random() < 0.3:
            i, j = rng.sample(range(len(tail)), 2)
            tail[i], tail[j] = tail[j], tail[i]
        return (0, *tail, 0)

    for _ in range(iterations):
        elite = min(population, key=lambda p: (_cost(d, p), p))
        population = [elite] + [child(tournament(), tournament()) for _ in range(15)]
    best = min(population, key=lambda p: (_cost(d, p), p))
    return best, _cost(d, best)


def benchmark(distances, seeds=(0, 1, 2), iterations=200, exact=True):
    """Run all algorithms on one matrix; return measured per-run records.

    Exact relative gaps are Fractions, or None if undefined/unknown. Timings
    include solver-side validation; benchmark's post-validation is excluded.
    """
    d = _validate_matrix(distances)
    if not isinstance(seeds, (list, tuple)) or not 1 <= len(seeds) <= MAX_SEEDS:
        raise ValueError(f'seeds must contain 1..{MAX_SEEDS} integers')
    for seed in seeds:
        _validate_seed(seed)
    _int(iterations, 'iterations', 1, MAX_ITERATIONS)
    if not isinstance(exact, bool):
        raise ValueError('exact must be boolean')
    records = []

    def run(name, solver, seed=None):
        started = time.perf_counter_ns()
        route, cost = solver()
        elapsed = (time.perf_counter_ns() - started) / 1e9
        checked = route_cost(d, route)
        if isinstance(cost, bool) or not isinstance(cost, int) or cost != checked:
            raise RuntimeError(f'{name} returned an incorrect cost')
        record = {'algorithm': name, 'seed': seed, 'route': route, 'valid': True,
                  'cost': cost, 'runtime_seconds': elapsed}
        records.append(record)
        return cost

    optimum = run('held_karp', lambda: held_karp_cycle(d)) if exact else None
    run('nearest_neighbor', lambda: nearest_neighbor_cycle(d))
    run('nearest_neighbor_2opt', lambda: nearest_neighbor_2opt_cycle(d))
    for seed in seeds:
        for name, solver in (('simulated_annealing', simulated_annealing_cycle),
                             ('tabu_search', tabu_search_cycle), ('genetic', genetic_cycle)):
            run(name, lambda solver=solver, seed=seed: solver(d, seed, iterations), seed)
    for record in records:
        gap = optimality_gap(optimum, record['cost']) if optimum is not None else None
        record['absolute_gap'] = gap['absolute'] if gap is not None else None
        record['relative_gap'] = gap['relative'] if gap is not None else None
    return {'n': len(d), 'iterations': iterations, 'exact_cost': optimum, 'records': records}


def _json_default(value):
    if isinstance(value, Fraction):
        return {'numerator': value.numerator, 'denominator': value.denominator}
    raise TypeError(f'cannot serialize {type(value).__name__}')


if __name__ == '__main__':
    # Re-run this exact sample offline; timings vary across runs and machines.
    matrix_seed = 42
    result = benchmark(random_matrix(8, matrix_seed), seeds=(0, 1, 2), iterations=200)
    result['matrix_seed'] = matrix_seed
    result['max_weight'] = 100
    print(json.dumps(result, default=_json_default, indent=2))
