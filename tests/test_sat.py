"""Offline tests for bounded CNF, certificates and one-step resolution."""
import itertools
import random
import unittest

from omega.sat import (MAX_CLAUSES, MAX_LITERALS, MAX_VARS,
                       minimal_unsatisfiable, resolvent, solve,
                       validate_cnf, verify_certificate)


def truth(cnf, bits):
    return all(any(bits[abs(x) - 1] if x > 0 else not bits[abs(x) - 1]
                   for x in clause) for clause in cnf)


class SATTests(unittest.TestCase):
    def test_empty_and_unused_variables(self):
        self.assertEqual(solve(0, []), {"status": "SAT", "assignment": ()})
        self.assertEqual(solve(0, [[]]), {"status": "UNSAT", "falsified_by": (0,)})
        self.assertTrue(verify_certificate(0, [[]], solve(0, [[]])))
        self.assertFalse(minimal_unsatisfiable(0, []))
        self.assertTrue(minimal_unsatisfiable(0, [[]]))
        self.assertFalse(minimal_unsatisfiable(0, [[], []]))
        self.assertEqual(solve(3, []), {"status": "SAT", "assignment": (False,) * 3})

    def test_sat_and_unsat_examples(self):
        cnf = [[1, 2], [-1, 2], [1, -2]]
        cert = solve(2, cnf)
        self.assertEqual(cert, {"status": "SAT", "assignment": (True, True)})
        self.assertTrue(verify_certificate(2, cnf, cert))
        contradictory = [[1], [-1]]
        cert = solve(1, contradictory)
        self.assertEqual(cert, {"status": "UNSAT", "falsified_by": (0, 1)})
        self.assertTrue(verify_certificate(1, contradictory, cert))
        self.assertTrue(minimal_unsatisfiable(1, contradictory))
        self.assertFalse(minimal_unsatisfiable(1, [[1], [-1], [1]]))
        self.assertFalse(minimal_unsatisfiable(1, [[1, -1]]))
        self.assertTrue(verify_certificate(1, [[1, -1, 1]], solve(1, [[1, -1, 1]])))

    def test_all_subsets_of_small_clause_pool(self):
        pool = [(), (1,), (-1,), (2,), (-2,), (1, 2), (-1, -2), (1, -1)]
        assignments = list(itertools.product((False, True), repeat=2))
        for mask in range(1 << len(pool)):
            cnf = tuple(c for i, c in enumerate(pool) if mask & (1 << i))
            expected = any(truth(cnf, a) for a in assignments)
            cert = solve(2, cnf)
            self.assertEqual(cert['status'] == 'SAT', expected, cnf)
            self.assertTrue(verify_certificate(2, cnf, cert), cnf)
            minimal = (not expected and all(any(truth(cnf[:i] + cnf[i+1:], a)
                                                for a in assignments)
                                            for i in range(len(cnf))))
            self.assertEqual(minimal_unsatisfiable(2, cnf), minimal, cnf)

    def test_random_formula_against_independent_evaluator(self):
        rng = random.Random(2601)
        for _ in range(200):
            n = rng.randrange(1, 6)
            cnf = [[rng.choice((-1, 1)) * rng.randrange(1, n + 1)
                    for _ in range(rng.randrange(5))] for _ in range(rng.randrange(8))]
            expected = any(truth(cnf, a) for a in itertools.product((False, True), repeat=n))
            cert = solve(n, cnf)
            self.assertEqual(cert['status'] == 'SAT', expected)
            self.assertTrue(verify_certificate(n, cnf, cert))

    def test_certificate_tampering(self):
        for cert in (None, {}, {'status': 'SAT'}, {'status': 'SAT', 'assignment': [1]},
                     {'status': 'SAT', 'assignment': [False]},
                     {'status': 'SAT', 'assignment': [True], 'extra': 0},
                     {'status': 'UNSAT', 'falsified_by': [0]},
                     {'status': 'UNSAT', 'falsified_by': [0, 0]},
                     {'status': 'UNSAT', 'falsified_by': [0, True]},
                     {'status': 'UNSAT', 'falsified_by': [0, -1]},
                     {'status': 'UNSAT', 'falsified_by': [0, 2]},
                     {'status': 'UNSAT', 'falsified_by': '01'},
                     {'status': 'unknown', 'falsified_by': [0, 1]}):
            with self.subTest(cert=cert):
                self.assertFalse(verify_certificate(1, [[1], [-1]], cert))
        self.assertFalse(verify_certificate(1, [], {'status': 'UNSAT', 'falsified_by': [0, 0]}))
        self.assertFalse(verify_certificate(1, [[-1]], {'status': 'SAT', 'assignment': [True]}))
        with self.assertRaises(ValueError):
            verify_certificate(1, [[0]], {})

    def test_validation_boundaries_and_types(self):
        self.assertEqual(validate_cnf(1, [[1, 1, -1], []]), ((1, 1, -1), ()))
        for n, cnf in [(True, []), (-1, []), (MAX_VARS + 1, []), (1.0, []),
                       (1, None), (1, iter([])), (1, [None]), (1, [[True]]),
                       (1, [[0]]), (1, [[2]]), (0, [[-1]]), (1, [[1.0]]),
                       (1, [[]] * (MAX_CLAUSES + 1)),
                       (1, [[1] * (MAX_LITERALS + 1)])]:
            with self.subTest(n=n, cnf=str(cnf)[:50]), self.assertRaises(ValueError):
                validate_cnf(n, cnf)
        self.assertEqual(len(validate_cnf(1, [[]] * MAX_CLAUSES)), MAX_CLAUSES)
        self.assertEqual(len(validate_cnf(1, [[1] * MAX_LITERALS])[0]), MAX_LITERALS)
        cert = solve(MAX_VARS, [[]])
        self.assertEqual(len(cert['falsified_by']), 1 << MAX_VARS)
        self.assertTrue(verify_certificate(MAX_VARS, [[]], cert))

    def test_minimality_work_budget(self):
        with self.assertRaisesRegex(ValueError, 'budget'):
            minimal_unsatisfiable(MAX_VARS, [[1] * 10] * MAX_CLAUSES)

    def test_resolvents_and_errors(self):
        self.assertEqual(resolvent(1, [1], [-1], 1), ())
        self.assertEqual(resolvent(2, [1, 2, 2], [-1, -2], 1), (-2, 2))
        self.assertEqual(resolvent(2, [-1, 2], [1], 1), (2,))
        self.assertEqual(resolvent(1, [1, -1], [1, -1], 1), (-1, 1))
        for a, b, p in [([1], [1], 1), ([1], [-1], 0), ([1], [-1], True),
                         ([1], [-1], 2), ([1], [-1], -1)]:
            with self.subTest(a=a, b=b, p=p), self.assertRaises(ValueError):
                resolvent(1, a, b, p)

    def test_resolution_entailment_exhaustively(self):
        literals = (1, -1, 2, -2)
        clauses = [tuple(x for i, x in enumerate(literals) if mask & (1 << i))
                   for mask in range(16)]
        for a, b, pivot in itertools.product(clauses, clauses, (1, 2)):
            try:
                r = resolvent(2, a, b, pivot)
            except ValueError:
                continue
            for assignment in itertools.product((False, True), repeat=2):
                if truth((a, b), assignment):
                    self.assertTrue(truth((r,), assignment), (a, b, pivot, r, assignment))


if __name__ == '__main__':
    unittest.main()
