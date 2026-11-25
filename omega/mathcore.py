"""Small, reproducible mathematical experiments; no P-versus-NP claim.

The modular difference here is a discrete sequence transform, not the
standard electrical Y-Delta network transformation. Digits are ASCII strings
in bases 2 through 10, so leading zeros are never converted away.

The TSP functions handle *symmetric*, complete, non-negative integer distance
matrices, not arbitrary directed graphs. Held-Karp is exponential and capped;
nearest-neighbor plus 2-opt is a heuristic, with no optimality guarantee.
"""
from __future__ import annotations

from fractions import Fraction

MAX_DIGITS = 100_000
MAX_TSP_N = 14


def _base(base):
    if isinstance(base, bool) or not isinstance(base, int) or not 2 <= base <= 10:
        raise ValueError("base must be an integer from 2 through 10")
    return base


def validate_digits(digits, base=10, *, allow_empty=False):
    """Validate and return an ASCII digit string, without stripping zeros.

    Empty strings are permitted only for a difference sequence, which is
    needed to represent a one-digit input.
    """
    base = _base(base)
    if not isinstance(allow_empty, bool):
        raise ValueError("allow_empty must be a boolean")
    if (not isinstance(digits, str) or len(digits) > MAX_DIGITS
            or (not digits and not allow_empty)):
        raise ValueError("digits must be a bounded, nonempty string")
    if any(ch < '0' or ch >= chr(ord('0') + base) for ch in digits):
        raise ValueError("digits must be ASCII digits within the base")
    return digits


def modular_difference(digits, base=10):
    """Return consecutive (next - previous) mod base, one character each.

    The output has length n-1 and omits the first digit, the anchor.
    """
    digits = validate_digits(digits, base)
    values = [ord(ch) - 48 for ch in digits]
    return ''.join(str((b - a) % base) for a, b in zip(values, values[1:]))


def inverse_difference(differences, anchor, base=10):
    """Reconstruct exactly with one explicit anchor digit; preserve zeros."""
    validate_digits(differences, base, allow_empty=True)
    validate_digits(anchor, base)
    if len(anchor) != 1 or len(differences) >= MAX_DIGITS:
        raise ValueError("anchor must be one digit and output within MAX_DIGITS")
    value = ord(anchor) - 48
    result = [anchor]
    for ch in differences:
        value = (value + ord(ch) - 48) % base
        result.append(str(value))
    return ''.join(result)


def first_anchor_loss_counterexample(length=1, base=10):
    """Return the lexicographically first distinct pair with equal differences.

    At fixed length, the all-zero word is first, and its first distinct
    collision is the all-one word. Each difference sequence has exactly base
    preimages, one for each anchor. This is an information-loss observation,
    not a complexity-theoretic result.
    """
    _base(base)
    if isinstance(length, bool) or not isinstance(length, int) or not 1 <= length <= MAX_DIGITS:
        raise ValueError("length must be an integer from 1 through MAX_DIGITS")
    first, second = '0' * length, '1' * length
    return {"first": first, "second": second, "difference": '0' * (length - 1),
            "preimage_count": base}


def hamming_distance(first, second, base=10):
    """Count unequal positions in equally long digit sequences."""
    validate_digits(first, base)
    validate_digits(second, base)
    if len(first) != len(second):
        raise ValueError("sequences must have the same length")
    return sum(a != b for a, b in zip(first, second))


def digit_frequency(digits, base=10):
    """Return counts for digits 0 through base-1, in order."""
    validate_digits(digits, base)
    counts = [0] * base
    for ch in digits:
        counts[ord(ch) - 48] += 1
    return tuple(counts)


def _matrix(distances):
    """Validate and freeze an undirected, complete, integer metric-like input.

    No triangle inequality is required. Self-distances must be zero. The
    limitation on n applies to both solvers for predictable resource usage.
    """
    if not isinstance(distances, (list, tuple)) or not 1 <= len(distances) <= MAX_TSP_N:
        raise ValueError(f"matrix must have 1..{MAX_TSP_N} rows")
    n = len(distances)
    rows = []
    for i, row in enumerate(distances):
        if not isinstance(row, (list, tuple)) or len(row) != n:
            raise ValueError("matrix must be square")
        for j, weight in enumerate(row):
            if isinstance(weight, bool) or not isinstance(weight, int) or weight < 0:
                raise ValueError("distances must be non-negative integers")
            if i == j and weight != 0:
                raise ValueError("diagonal must be zero")
        rows.append(tuple(row))
    frozen = tuple(rows)
    if any(frozen[i][j] != frozen[j][i] for i in range(n) for j in range(i)):
        raise ValueError("matrix must be symmetric")
    return frozen


def held_karp_cycle(distances):
    """Return (cycle, exact cost) from vertex 0, using Held-Karp DP.

    A one-vertex cycle is (0, 0) at cost 0; for two vertices the edge is
    traversed twice. Ties are resolved deterministically by lexicographic path.
    This solves only the provided bounded instance and says nothing about P=NP.
    """
    d = _matrix(distances)
    n = len(d)
    if n == 1:
        return (0, 0), 0
    # A state maps (subset of vertices 1..n-1, last) to (cost, path).
    states = {(1 << (j - 1), j): (d[0][j], (0, j)) for j in range(1, n)}
    for mask in range(1, 1 << (n - 1)):
        for last in range(1, n):
            bit = 1 << (last - 1)
            if not mask & bit or mask == bit:
                continue
            prev_mask = mask ^ bit
            candidates = ((states[(prev_mask, k)][0] + d[k][last],
                           states[(prev_mask, k)][1] + (last,))
                          for k in range(1, n) if prev_mask & (1 << (k - 1)))
            states[(mask, last)] = min(candidates)
    full = (1 << (n - 1)) - 1
    cost, path = min((states[(full, j)][0] + d[j][0], states[(full, j)][1])
                     for j in range(1, n))
    return path + (0,), cost


def nearest_neighbor_2opt_cycle(distances):
    """Return a deterministic nearest-neighbor cycle improved by 2-opt.

    Start at zero, break nearest ties by vertex id, and repeatedly apply the
    first strictly improving 2-opt reversal in ascending index order. This
    terminates for integer costs; it does not certify global optimality.
    """
    d = _matrix(distances)
    n = len(d)
    if n == 1:
        return (0, 0), 0
    route = [0]
    remaining = set(range(1, n))
    while remaining:
        v = min(remaining, key=lambda j: (d[route[-1]][j], j))
        route.append(v)
        remaining.remove(v)
    route.append(0)
    while True:
        improved = False
        for i in range(1, n - 1):
            for k in range(i + 1, n):
                a, b, c, e = route[i - 1], route[i], route[k], route[k + 1]
                if d[a][c] + d[b][e] < d[a][b] + d[c][e]:
                    route[i:k + 1] = reversed(route[i:k + 1])
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return tuple(route), sum(d[a][b] for a, b in zip(route, route[1:]))


def optimality_gap(optimal_cost, candidate_cost):
    """Return absolute and relative gaps for a candidate vs a known optimum.

    Relative gap is exact Fraction (candidate-optimal)/optimal. When both
    costs are zero it is Fraction(0); when optimum=0 and candidate>0 it is
    None (undefined), not infinity or a fabricated percentage. Inputs must be
    non-negative integer costs and candidate >= optimum.
    """
    for value in (optimal_cost, candidate_cost):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("costs must be non-negative integers")
    if candidate_cost < optimal_cost:
        raise ValueError("candidate cost cannot be less than the optimum")
    absolute = candidate_cost - optimal_cost
    relative = (Fraction(absolute, optimal_cost) if optimal_cost else
                (Fraction(0) if not absolute else None))
    return {"absolute": absolute, "relative": relative}
