"""Independent synthetic soil-vector and discrete cellular toy models.

No calibration, empirical evidence, agriculture advice, or biological/medical
interpretation is implied. See research/models.md for units and assumptions.
"""
from __future__ import annotations

import math
import random

MAX_FEATURES = 128
MAX_DIMENSION = 100
MAX_STEPS = 1000
MAX_CELL_UPDATES = 1_000_000
_MAX_RAW = 1e12


def _number(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return value


def _integer(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def _sequence(name, value):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= MAX_FEATURES:
        raise ValueError(f"{name} must be a list or tuple of 1..{MAX_FEATURES} entries")
    return value


def normalize_soil(values, ranges):
    """Map ordered numeric features to [0,1] using explicit inclusive ranges.

    Values and each (low, high) pair use the same caller-defined units. Out of
    range values and zero-width ranges are rejected, never silently clipped.
    All raw numbers are limited to [-1e12, 1e12]. Returns a tuple.
    """
    values = _sequence('values', values)
    ranges = _sequence('ranges', ranges)
    if len(values) != len(ranges):
        raise ValueError('values and ranges must have equal length')
    result = []
    for value, limits in zip(values, ranges):
        if not isinstance(limits, (tuple, list)) or len(limits) != 2:
            raise ValueError('each range must be a pair (low, high)')
        low = _number('low', limits[0], -_MAX_RAW, _MAX_RAW)
        high = _number('high', limits[1], -_MAX_RAW, _MAX_RAW)
        if low >= high:
            raise ValueError('each low must be strictly less than high')
        value = _number('value', value, low, high)
        result.append((value - low) / (high - low))
    return tuple(result)


def soil_similarity(first, second):
    """Compare equal-length normalized feature vectors using Euclidean distance.

    Returns distance d in [0,sqrt(n)] and 1-d/sqrt(n) in [0,1]. The distance
    is a metric for vectors of a fixed dimension; the similarity is a score,
    not a probability or an empirically validated soil-quality indicator.
    """
    first = _sequence('first', first)
    second = _sequence('second', second)
    if len(first) != len(second):
        raise ValueError('vectors must have equal length')
    a = tuple(_number('first feature', x, 0, 1) for x in first)
    b = tuple(_number('second feature', x, 0, 1) for x in second)
    distance = math.dist(a, b)
    return {'distance': distance, 'similarity': 1.0 - distance / math.sqrt(len(a)),
            'features': len(a)}


def _grid(grid):
    if not isinstance(grid, (list, tuple)) or not 1 <= len(grid) <= MAX_DIMENSION:
        raise ValueError(f'grid must have 1..{MAX_DIMENSION} rows')
    if not isinstance(grid[0], (list, tuple)) or not 1 <= len(grid[0]) <= MAX_DIMENSION:
        raise ValueError(f'grid must have 1..{MAX_DIMENSION} columns')
    width = len(grid[0])
    result = []
    for row in grid:
        if not isinstance(row, (list, tuple)) or len(row) != width:
            raise ValueError('grid rows must be rectangular lists or tuples')
        if any(type(cell) is not int or cell not in (0, 1) for cell in row):
            raise ValueError('cells must be integers 0 or 1, not booleans')
        result.append(tuple(row))
    return tuple(result)


def _step(grid):
    rows, columns = len(grid), len(grid[0])
    next_grid = []
    for r in range(rows):
        row = []
        for c in range(columns):
            neighbors = sum(grid[rr][cc]
                            for rr in range(max(0, r-1), min(rows, r+2))
                            for cc in range(max(0, c-1), min(columns, c+2))
                            if (rr, cc) != (r, c))
            row.append(int(neighbors == 3 or (grid[r][c] == 1 and neighbors == 2)))
        next_grid.append(tuple(row))
    return tuple(next_grid)


def cellular_step(grid):
    """One synchronous B3/S23 Moore-neighborhood update, fixed dead exterior."""
    return _step(_grid(grid))


def evolve_cellular(grid, steps):
    """Return initial/final grids and counts at each integer t=0..steps.

    Time is abstract and has no specified physical duration. All cells update
    simultaneously. Grid dimensions are 1..100, and steps are 0..1000. The
    product rows * columns * steps cannot exceed 1,000,000.
    """
    grid = _grid(grid)
    steps = _integer('steps', steps, 0, MAX_STEPS)
    if len(grid) * len(grid[0]) * steps > MAX_CELL_UPDATES:
        raise ValueError(f'cell updates cannot exceed {MAX_CELL_UPDATES}')
    initial = grid
    counts = [{'t': 0, 'active': sum(map(sum, grid))}]
    for t in range(1, steps + 1):
        grid = _step(grid)
        counts.append({'t': t, 'active': sum(map(sum, grid))})
    return {'initial_grid': initial, 'final_grid': grid, 'counts': counts}


def simulate_cellular(rows, columns, initial_probability, steps, *, seed=0):
    """Seed independent Bernoulli cells then evolve using the stated toy rule.

    A local random.Random(seed) draws in row-major order, even for p=0 or p=1.
    Seed is an integer in [0, 2**32-1]; p is a finite number in [0,1].
    """
    rows = _integer('rows', rows, 1, MAX_DIMENSION)
    columns = _integer('columns', columns, 1, MAX_DIMENSION)
    probability = _number('initial_probability', initial_probability, 0, 1)
    steps = _integer('steps', steps, 0, MAX_STEPS)
    seed = _integer('seed', seed, 0, 2**32 - 1)
    if rows * columns * steps > MAX_CELL_UPDATES:
        raise ValueError(f'cell updates cannot exceed {MAX_CELL_UPDATES}')
    rng = random.Random(seed)
    grid = tuple(tuple(int(rng.random() < probability) for _ in range(columns))
                 for _ in range(rows))
    result = evolve_cellular(grid, steps)
    return {'rows': rows, 'columns': columns, 'initial_probability': probability,
            'steps': steps, 'seed': seed, **result}


def synthetic_scenarios():
    """Return small explicitly invented inputs and model outputs, not observations."""
    # Arbitrary illustrative bounds, NOT reference/calibration intervals.
    ranges = ((0, 14), (0, 1), (0, 1))
    reference = (7, .5, .1)
    samples = ((7, .5, .1), (7, .5, .2), (0, 0, 0), (14, 1, 1))
    normalized_reference = normalize_soil(reference, ranges)
    soil = [{'raw': raw, 'normalized': normalize_soil(raw, ranges),
             **soil_similarity(normalized_reference, normalize_soil(raw, ranges))}
            for raw in samples]
    cellular = simulate_cellular(8, 8, .3, 5, seed=42)
    return {'provenance': 'synthetic invented examples, not observations',
            'feature_names': ('pH', 'water volume fraction', 'organic matter mass fraction'),
            'units': ('dimensionless pH', 'm3/m3', 'kg/kg'),
            'ranges': ranges, 'reference': reference, 'soil': soil,
            'cellular': cellular}
