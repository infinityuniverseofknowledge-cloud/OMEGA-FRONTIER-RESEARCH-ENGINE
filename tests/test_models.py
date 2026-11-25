"""Offline tests: PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v"""
import itertools
import math
import random
import unittest

from omega.models import (cellular_step, evolve_cellular, normalize_soil,
                          simulate_cellular, soil_similarity, synthetic_scenarios)


class SoilModelTests(unittest.TestCase):
    def test_normalization_explicit_units_and_inclusive_endpoints(self):
        self.assertEqual(normalize_soil((7, .25, .1), ((0, 14), (0, 1), (0, 1))),
                         (.5, .25, .1))
        self.assertEqual(normalize_soil((-3, 3), ((-3, 7), (-7, 3))), (0, 1))
        self.assertEqual(normalize_soil((0,), ((-10, 10),)), (.5,))

    def test_similarity_zero_identical_and_opposite(self):
        self.assertEqual(soil_similarity((0, 0, 0), (0, 0, 0)),
                         {'distance': 0, 'similarity': 1, 'features': 3})
        answer = soil_similarity((0, 0, 0), (1, 1, 1))
        self.assertAlmostEqual(answer['distance'], math.sqrt(3))
        self.assertEqual(answer['similarity'], 0)
        self.assertEqual(soil_similarity((.25,), (.75,))['similarity'], .5)
        # Naive squared differences underflow; the distance must stay nonzero.
        self.assertGreater(soil_similarity((0.0,), (1e-200,))['distance'], 0)

    def test_metric_and_score_properties_exhaustive_small_vectors(self):
        vectors = list(itertools.product((0, .5, 1), repeat=2))
        for a, b, c in itertools.product(vectors, repeat=3):
            ab = soil_similarity(a, b)
            ba = soil_similarity(b, a)
            self.assertEqual(ab, ba)
            self.assertGreaterEqual(ab['distance'], 0)
            self.assertLessEqual(ab['distance'], math.sqrt(2))
            self.assertGreaterEqual(ab['similarity'], 0)
            self.assertLessEqual(ab['similarity'], 1)
            self.assertLessEqual(ab['distance'], soil_similarity(a, c)['distance'] +
                                 soil_similarity(c, b)['distance'] + 1e-15)
            if a != b:
                self.assertGreater(ab['distance'], 0)

    def test_invalid_normalization(self):
        cases = [([], []), ([1], []), ([1, 2], [(0, 2)]),
                 ([1], [(0, 0)]), ([1], [(3, 2)]), ([3], [(0, 2)]),
                 ([-1], [(0, 2)]), ([True], [(0, 2)]), ([1], [(False, 2)]),
                 ([float('nan')], [(0, 2)]), ([float('inf')], [(0, 2)]),
                 ([1], [(0, float('inf'))]), ([10**1000], [(0, 2)]),
                 ([1], [(0,)]), ('a', [(0, 2)]),
                 ([1] * 129, [(0, 2)] * 129)]
        for values, ranges in cases:
            with self.subTest(values=str(values)[:40], ranges=str(ranges)[:40]):
                with self.assertRaises(ValueError):
                    normalize_soil(values, ranges)

    def test_invalid_vectors(self):
        cases = [([], []), ([0], [0, 1]), ([True], [0]), ([1.01], [0]),
                 ([-.01], [0]), ([float('nan')], [0]), ([0], [float('inf')]),
                 ([10**1000], [0]), ('x', [0]), ([0] * 129, [0] * 129)]
        for first, second in cases:
            with self.subTest(first=str(first)[:40], second=str(second)[:40]):
                with self.assertRaises(ValueError):
                    soil_similarity(first, second)


class CellularModelTests(unittest.TestCase):
    def test_known_still_life_and_blinker(self):
        block = ((0, 0, 0, 0), (0, 1, 1, 0), (0, 1, 1, 0), (0, 0, 0, 0))
        self.assertEqual(cellular_step(block), block)
        horizontal = ((0, 0, 0, 0, 0), (0, 0, 0, 0, 0), (0, 1, 1, 1, 0),
                      (0, 0, 0, 0, 0), (0, 0, 0, 0, 0))
        vertical = ((0, 0, 0, 0, 0), (0, 0, 1, 0, 0), (0, 0, 1, 0, 0),
                    (0, 0, 1, 0, 0), (0, 0, 0, 0, 0))
        self.assertEqual(cellular_step(horizontal), vertical)
        self.assertEqual(cellular_step(vertical), horizontal)
        result = evolve_cellular(horizontal, 2)
        self.assertEqual(result['final_grid'], horizontal)
        self.assertEqual(result['counts'], [{'t': 0, 'active': 3},
                                            {'t': 1, 'active': 3}, {'t': 2, 'active': 3}])

    def test_fixed_dead_boundary_and_degenerate_grids(self):
        self.assertEqual(cellular_step(((1,),)), ((0,),))
        self.assertEqual(cellular_step(((1, 1, 1),)), ((0, 1, 0),))
        # A wraparound rule would count extra neighbors here.
        self.assertEqual(cellular_step(((1, 0, 1), (0, 0, 0), (1, 0, 0))),
                         ((0, 0, 0), (0, 1, 0), (0, 0, 0)))
        self.assertEqual(cellular_step(((0, 0), (0, 0))), ((0, 0), (0, 0)))

    def test_all_3x3_states_against_independent_reference(self):
        offsets = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                   if (dr, dc) != (0, 0)]
        for flat in itertools.product((0, 1), repeat=9):
            grid = tuple(tuple(flat[r*3:(r+1)*3]) for r in range(3))
            expected = []
            for r in range(3):
                row = []
                for c in range(3):
                    n = sum(grid[r+dr][c+dc] for dr, dc in offsets
                            if 0 <= r+dr < 3 and 0 <= c+dc < 3)
                    row.append(int(n == 3 or (grid[r][c] == 1 and n == 2)))
                expected.append(tuple(row))
            self.assertEqual(cellular_step(grid), tuple(expected))

    def test_seeded_repeatability_global_rng_and_time(self):
        random.seed(100)
        state = random.getstate()
        a = simulate_cellular(8, 8, .3, 5, seed=42)
        self.assertEqual(random.getstate(), state)
        self.assertEqual(a, simulate_cellular(8, 8, .3, 5, seed=42))
        self.assertNotEqual(a['initial_grid'], simulate_cellular(8, 8, .3, 5, seed=43)['initial_grid'])
        self.assertEqual([x['t'] for x in a['counts']], list(range(6)))
        self.assertTrue(all(0 <= x['active'] <= 64 for x in a['counts']))
        self.assertEqual(a['counts'][0]['active'], sum(map(sum, a['initial_grid'])))
        self.assertEqual(a['counts'][-1]['active'], sum(map(sum, a['final_grid'])))

    def test_zero_steps_and_extreme_probabilities(self):
        zero = simulate_cellular(3, 4, 0, 2, seed=0)
        self.assertEqual([x['active'] for x in zero['counts']], [0, 0, 0])
        full = simulate_cellular(3, 4, 1, 0, seed=2**32-1)
        self.assertEqual(full['initial_grid'], full['final_grid'])
        self.assertEqual(full['counts'], [{'t': 0, 'active': 12}])
        self.assertEqual(evolve_cellular([[1]], 0)['final_grid'], ((1,),))

    def test_invalid_grid(self):
        for grid in ([], [[]], [[0], [0, 0]], [[True]], [[1.0]], [[2]],
                     [[-1]], [[float('nan')]], '0', [[0]] * 101,
                     [[0] * 101], [None]):
            with self.subTest(grid=str(grid)[:30]), self.assertRaises(ValueError):
                cellular_step(grid)

    def test_invalid_parameters_and_work_limit(self):
        calls = [lambda: simulate_cellular(0, 1, .5, 1),
                 lambda: simulate_cellular(True, 1, .5, 1),
                 lambda: simulate_cellular(1, 101, .5, 1),
                 lambda: simulate_cellular(1, 1, -.01, 1),
                 lambda: simulate_cellular(1, 1, 1.01, 1),
                 lambda: simulate_cellular(1, 1, True, 1),
                 lambda: simulate_cellular(1, 1, float('nan'), 1),
                 lambda: simulate_cellular(1, 1, .5, -1),
                 lambda: simulate_cellular(1, 1, .5, 1001),
                 lambda: simulate_cellular(1, 1, .5, True),
                 lambda: simulate_cellular(1, 1, .5, 1, seed=-1),
                 lambda: simulate_cellular(1, 1, .5, 1, seed=True),
                 lambda: simulate_cellular(1, 1, .5, 1, seed=2**32),
                 lambda: simulate_cellular(100, 100, .5, 101),
                 lambda: evolve_cellular([[0]*100 for _ in range(100)], 101)]
        for call in calls:
            with self.assertRaises(ValueError):
                call()

    def test_synthetic_scenarios_reproducible_and_labeled(self):
        a = synthetic_scenarios()
        self.assertEqual(a, synthetic_scenarios())
        self.assertIn('synthetic', a['provenance'])
        self.assertEqual(len(a['soil']), 4)
        self.assertEqual(a['soil'][0]['distance'], 0)
        self.assertEqual(a['soil'][0]['similarity'], 1)
        self.assertEqual(a['cellular']['seed'], 42)


if __name__ == '__main__':
    unittest.main()
