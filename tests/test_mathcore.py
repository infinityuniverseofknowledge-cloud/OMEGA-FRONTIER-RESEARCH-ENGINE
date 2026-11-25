"""Offline, reproducible checks for the experimental mathematical core."""
import itertools
import random
import unittest
from fractions import Fraction

from omega.mathcore import (
    MAX_DIGITS, MAX_TSP_N, digit_frequency, first_anchor_loss_counterexample,
    hamming_distance, held_karp_cycle, inverse_difference, modular_difference,
    nearest_neighbor_2opt_cycle, optimality_gap, validate_digits,
)


class DigitTests(unittest.TestCase):
    def test_leading_zeros_and_one_digit(self):
        self.assertEqual(modular_difference('00109'), '0199')
        self.assertEqual(inverse_difference('0199', '0'), '00109')
        self.assertEqual(modular_difference('0'), '')
        self.assertEqual(inverse_difference('', '0'), '0')
        self.assertEqual(modular_difference('0101', 2), '111')
        self.assertEqual(inverse_difference('111', '0', 2), '0101')

    def test_exhaustive_roundtrips_and_preimage_multiplicity(self):
        for base in range(2, 6):
            for length in range(1, 5):
                seen = {}
                for digits in itertools.product('0123456789'[:base], repeat=length):
                    s = ''.join(digits)
                    delta = modular_difference(s, base)
                    self.assertEqual(inverse_difference(delta, s[0], base), s)
                    seen.setdefault(delta, []).append(s)
                self.assertTrue(all(len(group) == base for group in seen.values()))
                collisions = sorted((a, b) for group in seen.values()
                                    for a, b in itertools.combinations(group, 2))
                result = first_anchor_loss_counterexample(length, base)
                self.assertEqual((result['first'], result['second']), collisions[0])
                self.assertEqual(result['difference'], modular_difference(result['first'], base))
                self.assertEqual(result['preimage_count'], base)

    def test_frequency_and_hamming(self):
        self.assertEqual(digit_frequency('001209'), (3, 1, 1, 0, 0, 0, 0, 0, 0, 1))
        self.assertEqual(digit_frequency('0011', 2), (2, 2))
        self.assertEqual(hamming_distance('00109', '01100'), 2)
        with self.assertRaises(ValueError):
            hamming_distance('00', '0')

    def test_invalid_digits_and_bases(self):
        for bad in ('', '12a', '-12', ' 01', '１', '²', '2\n', 101, ['0'], None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_digits(bad, 2)
        for bad in (1, 11, True, 2.0, '10', None):
            with self.subTest(base=bad), self.assertRaises(ValueError):
                modular_difference('01', bad)
        for anchor in ('', '00', 'a', 0):
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                inverse_difference('', anchor)
        with self.assertRaises(ValueError):
            inverse_difference('9', '0', 2)
        for length in (0, -1, True, 1.5, MAX_DIGITS + 1):
            with self.assertRaises(ValueError):
                first_anchor_loss_counterexample(length)
        with self.assertRaises(ValueError):
            validate_digits('0' * (MAX_DIGITS + 1))
        with self.assertRaises(ValueError):
            inverse_difference('0' * MAX_DIGITS, '0')
        self.assertEqual(inverse_difference('0' * (MAX_DIGITS - 1), '0'), '0' * MAX_DIGITS)


def brute_force(d):
    n = len(d)
    if n == 1:
        return (0, 0), 0
    solutions = []
    for tail in itertools.permutations(range(1, n)):
        route = (0,) + tail + (0,)
        cost = sum(d[a][b] for a, b in zip(route, route[1:]))
        solutions.append((cost, route))
    cost, route = min(solutions)
    return route, cost


def nearest_only(d):
    route, remaining = [0], set(range(1, len(d)))
    while remaining:
        v = min(remaining, key=lambda j: (d[route[-1]][j], j))
        route.append(v)
        remaining.remove(v)
    route.append(0)
    return sum(d[a][b] for a, b in zip(route, route[1:]))


class TSPTests(unittest.TestCase):
    def assert_valid_cycle(self, d, result):
        route, cost = result
        n = len(d)
        self.assertEqual((route[0], route[-1]), (0, 0))
        self.assertEqual(len(route), n + 1)
        self.assertEqual(set(route[:-1]), set(range(n)))
        self.assertEqual(cost, sum(d[a][b] for a, b in zip(route, route[1:])))

    def test_edges_and_zero(self):
        for solve in (held_karp_cycle, nearest_neighbor_2opt_cycle):
            self.assertEqual(solve([[0]]), ((0, 0), 0))
            self.assertEqual(solve([[0, 7], [7, 0]]), ((0, 1, 0), 14))
            matrix = [[0] * 4 for _ in range(4)]
            self.assertEqual(solve(matrix), ((0, 1, 2, 3, 0), 0))

    def test_seeded_exact_against_brute_force_and_heuristic(self):
        rng = random.Random(413)
        for n in range(1, 8):
            for sample in range(12):
                matrix = [[0] * n for _ in range(n)]
                for i in range(n):
                    for j in range(i):
                        matrix[i][j] = matrix[j][i] = rng.randrange(0, 30)
                with self.subTest(n=n, sample=sample):
                    exact = held_karp_cycle(matrix)
                    self.assertEqual(exact, brute_force(matrix))
                    self.assert_valid_cycle(matrix, exact)
                    heuristic = nearest_neighbor_2opt_cycle(matrix)
                    self.assertEqual(heuristic, nearest_neighbor_2opt_cycle(matrix))
                    self.assert_valid_cycle(matrix, heuristic)
                    self.assertGreaterEqual(heuristic[1], exact[1])
                    self.assertLessEqual(heuristic[1], nearest_only(matrix))
                    route, cost = heuristic
                    for i in range(1, n - 1):
                        for k in range(i + 1, n):
                            changed = route[:i] + tuple(reversed(route[i:k + 1])) + route[k + 1:]
                            self.assertGreaterEqual(sum(matrix[a][b] for a, b in zip(changed, changed[1:])), cost)

    def test_2opt_strictly_improves_suitable_instance(self):
        matrix = [[0, 1, 2, 10], [1, 0, 1, 2], [2, 1, 0, 1], [10, 2, 1, 0]]
        self.assertLess(nearest_neighbor_2opt_cycle(matrix)[1], nearest_only(matrix))
        self.assertEqual(nearest_neighbor_2opt_cycle(matrix)[1], 6)

    def test_bad_matrices(self):
        invalid = [None, [], [[0, 1]], [[0, 1], [2, 0]], [[1]],
                   [[0, -1], [-1, 0]], [[0, True], [True, 0]],
                   [[0, float('inf')], [float('inf'), 0]],
                   [[0, float('nan')], [float('nan'), 0]],
                   [[0, 1.0], [1.0, 0]], [[0], None],
                   [[0] * (MAX_TSP_N + 1) for _ in range(MAX_TSP_N + 1)]]
        for matrix in invalid:
            for solve in (held_karp_cycle, nearest_neighbor_2opt_cycle):
                with self.subTest(matrix=repr(matrix)[:100], solve=solve.__name__):
                    with self.assertRaises(ValueError):
                        solve(matrix)

    def test_exact_integer_gap(self):
        self.assertEqual(optimality_gap(8, 10), {'absolute': 2, 'relative': Fraction(1, 4)})
        self.assertEqual(optimality_gap(0, 0), {'absolute': 0, 'relative': Fraction(0)})
        self.assertEqual(optimality_gap(0, 7), {'absolute': 7, 'relative': None})
        self.assertEqual(optimality_gap(10**400, 10**400 + 1)['relative'], Fraction(1, 10**400))
        for a, b in ((-1, 0), (1, 0), (True, 1), (0, False), (0., 1), (1, None)):
            with self.assertRaises(ValueError):
                optimality_gap(a, b)


if __name__ == '__main__':
    unittest.main()
