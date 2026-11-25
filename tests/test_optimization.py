"""Offline unit and integration tests for bounded TSP experiments."""
import itertools
import random
import unittest
from fractions import Fraction
from unittest.mock import patch

from omega.mathcore import nearest_neighbor_2opt_cycle
from omega.optimization import (
    MAX_ITERATIONS, MAX_SEED, MAX_WEIGHT, benchmark, genetic_cycle,
    nearest_neighbor_cycle, random_matrix, route_cost, simulated_annealing_cycle,
    tabu_search_cycle,
)

SOLVERS = (simulated_annealing_cycle, tabu_search_cycle, genetic_cycle)
MATRIX = random_matrix(8, 42)


class OptimizationTests(unittest.TestCase):
    def assert_tour(self, matrix, result):
        route, cost = result
        self.assertEqual(route_cost(matrix, route), cost)
        self.assertEqual(len(route), len(matrix) + 1)
        self.assertEqual((route[0], route[-1]), (0, 0))
        self.assertEqual(set(route[:-1]), set(range(len(matrix))))

    def test_matrix_generator_and_nn_tie_break(self):
        self.assertEqual(random_matrix(8, 42), MATRIX)
        self.assertNotEqual(random_matrix(8, 43), MATRIX)
        for i, row in enumerate(MATRIX):
            self.assertEqual(row[i], 0)
            self.assertTrue(all(row[j] == MATRIX[j][i] for j in range(8)))
        zeros = random_matrix(4, 1, max_weight=0)
        self.assertEqual(nearest_neighbor_cycle(zeros), ((0, 1, 2, 3, 0), 0))

    def test_known_optimum_against_brute_force_and_baselines(self):
        d = ((0, 10, 15, 20), (10, 0, 35, 25),
             (15, 35, 0, 30), (20, 25, 30, 0))
        brute = min(route_cost(d, (0,) + p + (0,))
                    for p in itertools.permutations(range(1, 4)))
        result = benchmark(d, seeds=(0, 1), iterations=25)
        self.assertEqual(brute, 80)
        self.assertEqual(result['exact_cost'], brute)
        self.assertEqual(len(result['records']), 9)
        for row in result['records']:
            self.assertTrue(row['valid'])
            self.assert_tour(d, (row['route'], row['cost']))
            self.assertGreaterEqual(row['runtime_seconds'], 0)
            self.assertEqual(row['absolute_gap'], row['cost'] - brute)
            self.assertEqual(row['relative_gap'], Fraction(row['cost'] - brute, brute))
        nn, opt = result['records'][1:3]
        self.assertLessEqual(opt['cost'], nn['cost'])
        self.assertEqual((opt['route'], opt['cost']), nearest_neighbor_2opt_cycle(d))

    def test_seeded_improvement_and_determinism(self):
        # Compare each heuristic to its own reproducible initial population.
        # SA/tabu initialize with the first shuffle; GA has 16 initial tours.
        rng = random.Random(0)
        starts = []
        for _ in range(16):
            tail = list(range(1, 8))
            rng.shuffle(tail)
            starts.append(route_cost(MATRIX, (0, *tail, 0)))
        for solver in SOLVERS:
            with self.subTest(solver=solver.__name__):
                first = solver(MATRIX, 0, 200)
                self.assertEqual(first, solver(MATRIX, 0, 200))
                self.assert_tour(MATRIX, first)
                baseline = min(starts) if solver is genetic_cycle else starts[0]
                self.assertLessEqual(first[1], baseline)
        self.assertLess(simulated_annealing_cycle(MATRIX, 0, 200)[1], starts[0])
        self.assertLess(tabu_search_cycle(MATRIX, 0, 200)[1], starts[0])
        self.assertLess(genetic_cycle(MATRIX, 0, 200)[1], min(starts))

    def test_many_small_instances_and_edge_cases(self):
        for n in range(1, 8):
            for matrix_seed in (0, 1):
                d = random_matrix(n, matrix_seed, 20)
                reference = benchmark(d, seeds=(3,), iterations=20)
                for record in reference['records']:
                    self.assert_tour(d, (record['route'], record['cost']))
                    self.assertGreaterEqual(record['cost'], reference['exact_cost'])
        self.assertEqual(simulated_annealing_cycle([[0]], 0), ((0, 0), 0))
        for solver in SOLVERS:
            self.assertEqual(solver([[0, 7], [7, 0]], 0), ((0, 1, 0), 14))

    def test_zero_exact_and_no_exact(self):
        zero = [[0] * 4 for _ in range(4)]
        result = benchmark(zero, seeds=(7,), iterations=3)
        self.assertEqual(result['exact_cost'], 0)
        for row in result['records']:
            self.assertEqual(row['relative_gap'], Fraction(0))
        result = benchmark(MATRIX, seeds=(0,), iterations=3, exact=False)
        self.assertIsNone(result['exact_cost'])
        self.assertEqual(len(result['records']), 5)
        self.assertTrue(all(r['relative_gap'] is None and r['absolute_gap'] is None
                            for r in result['records']))
        # Zero optimum and positive candidate has undefined relative gap.
        from omega.mathcore import optimality_gap
        self.assertIsNone(optimality_gap(0, 3)['relative'])

    def test_invalid_inputs(self):
        bad_matrices = ([], [[1]], [[0, 1]], [[0, 1], [2, 0]],
                        [[0, True], [True, 0]], [[0, -1], [-1, 0]],
                        [[0, 1.5], [1.5, 0]], [[0] * 15 for _ in range(15)],
                        [[0, MAX_WEIGHT + 1], [MAX_WEIGHT + 1, 0]])
        for d in bad_matrices:
            with self.subTest(matrix=d), self.assertRaises(ValueError):
                benchmark(d)
        for bad_route in ((), (0,), (0, 1, 0, 0), (0, 1, 1, 0),
                          (0, 1, True, 0), (0, 1, 3, 0), (1, 0, 2, 1)):
            with self.subTest(route=bad_route), self.assertRaises(ValueError):
                route_cost([[0, 1, 1], [1, 0, 1], [1, 1, 0]], bad_route)
        for seed in (-1, True, 1.5, MAX_SEED + 1):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                simulated_annealing_cycle(MATRIX, seed)
        for iterations in (0, True, 1.5, MAX_ITERATIONS + 1):
            with self.subTest(iterations=iterations), self.assertRaises(ValueError):
                benchmark(MATRIX, iterations=iterations)
        for seeds in ((), list(range(11)), [0, True], '0'):
            with self.subTest(seeds=seeds), self.assertRaises(ValueError):
                benchmark(MATRIX, seeds=seeds)
        with self.assertRaises(ValueError):
            benchmark(MATRIX, exact=1)
        for n in (0, 15, True):
            with self.assertRaises(ValueError):
                random_matrix(n, 0)
        with self.assertRaises(ValueError):
            random_matrix(3, 0, -1)

    def test_benchmark_fails_closed_on_wrong_solver_cost_or_route(self):
        with patch('omega.optimization.nearest_neighbor_cycle', return_value=((0, 1, 0), 999)):
            with self.assertRaises(RuntimeError):
                benchmark([[0, 5], [5, 0]], exact=False)
        with patch('omega.optimization.nearest_neighbor_cycle', return_value=((0, 0, 0), 0)):
            with self.assertRaises(ValueError):
                benchmark([[0, 5], [5, 0]], exact=False)


if __name__ == '__main__':
    unittest.main()
