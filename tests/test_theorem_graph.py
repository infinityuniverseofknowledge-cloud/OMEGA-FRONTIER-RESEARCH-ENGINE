"""Exact, offline tests for the bounded educational theorem navigator."""
import itertools
import unittest

from omega.theorem_graph import Concept, TheoremGraph, curated_graph


def node(key, score=0):
    return Concept(key, 'test statement', 'test citation', score, 0, 0, 0, 0)


def reference(nodes, edges, start, end, weights, max_hops, max_distance, max_penalty):
    """Independent oracle: enumerate permutations, rather than DFS/pruning."""
    lookup = {x.key: x for x in nodes}
    cost = {frozenset((a, b)): w for a, b, w in edges}
    others = sorted(set(lookup) - {start, end})
    candidates = []
    if start == end:
        paths = [(start,)]
    else:
        paths = [(start,) + p + (end,) for length in range(len(others) + 1)
                 for p in itertools.permutations(others, length)]
    for path in paths:
        links = [frozenset(pair) for pair in zip(path, path[1:])]
        if any(link not in cost for link in links):
            continue
        distance = sum(cost[link] for link in links)
        penalty = sum(sum(getattr(lookup[k], f) * v for f, v in weights.items()) for k in path)
        if len(path) - 1 <= max_hops and distance <= max_distance and penalty <= max_penalty:
            candidates.append((distance + penalty, path, distance, penalty))
    return min(candidates) if candidates else None


class TheoremGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = curated_graph()

    def test_curated_metadata_and_study_order(self):
        self.assertEqual(len(self.graph.concepts), 6)
        self.assertTrue(all('doi.org/' in x.source for x in self.graph.concepts))
        self.assertEqual(self.graph.preparation_order('tree_edge_theorem'),
                         ('graph', 'walk', 'path', 'connected', 'tree', 'tree_edge_theorem'))
        self.assertEqual(self.graph.preparation_order('graph'), ('graph',))
        theorem = next(n for n in self.graph.concepts if n.key == 'tree_edge_theorem')
        self.assertIn('n >= 1', theorem.statement)
        self.assertIn('if and only if', theorem.statement)

    def test_route_is_undirected_not_prerequisite_proof(self):
        a = self.graph.route('graph', 'tree_edge_theorem')
        b = self.graph.route('tree_edge_theorem', 'graph')
        self.assertEqual(a.status, 'optimal')
        self.assertEqual(a.path, ('graph', 'walk', 'path', 'connected', 'tree', 'tree_edge_theorem'))
        self.assertEqual(a.distance, 8)
        self.assertEqual(b.path, tuple(reversed(a.path)))
        self.assertEqual(b.distance, a.distance)
        # A prerequisite need not be an edge in the semantic path.
        self.assertEqual(self.graph.route('graph', 'path').path, ('graph', 'walk', 'path'))

    def test_node_penalties_change_optimum_and_include_endpoints(self):
        nodes = [node('a', 1), node('b', 5), node('c', 0), node('d', 1)]
        edges = [('a', 'b', 1), ('b', 'd', 1), ('a', 'c', 2), ('c', 'd', 2)]
        g = TheoremGraph(nodes, [], edges)
        self.assertEqual(g.route('a', 'd').path, ('a', 'b', 'd'))
        result = g.route('a', 'd', weights={'H': 1})
        self.assertEqual((result.path, result.distance, result.penalty, result.total),
                         (('a', 'c', 'd'), 4, 2, 6))
        self.assertEqual(g.route('a', 'a', weights={'H': 3}).total, 3)
        self.assertEqual(g.route('a', 'a', weights={'H': 3}, max_penalty=2).status,
                         'no_feasible_route')

    def test_constraints_no_feasible_disconnected_and_exact_boundaries(self):
        g = TheoremGraph([node(x) for x in 'abcd'], [], [('a', 'b', 2), ('b', 'c', 3)])
        self.assertEqual(g.route('a', 'c', max_hops=2, max_distance=5).total, 5)
        for args in ({'max_hops': 1}, {'max_distance': 4}):
            r = g.route('a', 'c', **args)
            self.assertEqual(r.status, 'no_feasible_route')
            self.assertIsNone(r.path)
            self.assertGreater(r.pruned_states, 0)
        self.assertEqual(g.route('a', 'd').status, 'no_feasible_route')
        self.assertEqual(g.route('a', 'a', max_hops=0).path, ('a',))
        self.assertEqual(g.route('a', 'b', max_hops=0).status, 'no_feasible_route')

    def test_tie_is_lexicographic_and_deterministic(self):
        g = TheoremGraph([node(x) for x in 'dcba'], [],
                         [('a', 'c', 1), ('c', 'd', 1), ('a', 'b', 1), ('b', 'd', 1)])
        result = g.route('a', 'd')
        self.assertEqual(result.path, ('a', 'b', 'd'))
        self.assertEqual(result, g.route('a', 'd'))
        self.assertEqual(result.complete_paths_evaluated, 2)

    def test_independent_permutation_oracle_multiple_constraints(self):
        nodes = [node(x, i % 4) for i, x in enumerate('abcde')]
        edges = [('a', 'b', 1), ('a', 'c', 3), ('a', 'e', 9), ('b', 'c', 2),
                 ('b', 'd', 2), ('c', 'd', 1), ('c', 'e', 2), ('d', 'e', 3)]
        g = TheoremGraph(nodes, [], edges)
        for start, end in itertools.product('abcde', repeat=2):
            for weight, hops, dist, penalty in itertools.product((0, 2), (0, 2, 4), (0, 4, 20), (0, 4, 20)):
                weights = {'H': weight}
                expected = reference(nodes, edges, start, end, weights, hops, dist, penalty)
                result = g.route(start, end, weights=weights, max_hops=hops,
                                 max_distance=dist, max_penalty=penalty)
                if expected is None:
                    self.assertEqual(result.status, 'no_feasible_route')
                else:
                    self.assertEqual(result.status, 'optimal')
                    self.assertEqual((result.total, result.path, result.distance, result.penalty), expected)

    def test_topological_branch_tie_and_cycle_rejection(self):
        nodes = [node(x) for x in 'abcd']
        g = TheoremGraph(nodes, [('a', 'd'), ('c', 'd'), ('b', 'c')], [])
        self.assertEqual(g.preparation_order('d'), ('a', 'b', 'c', 'd'))
        with self.assertRaisesRegex(ValueError, 'prerequisite cycle'):
            TheoremGraph(nodes, [('a', 'b'), ('b', 'a'), ('b', 'd')], [])
        with self.assertRaises(ValueError):
            TheoremGraph(nodes, [('a', 'a')], [])

    def test_rejects_malformed_graphs(self):
        nodes = [node('a'), node('b')]
        cases = [([], [], []), ([node('a'), node('a')], [], []),
                 ([node(str(i)) for i in range(9)], [], []),
                 (nodes, [('a', 'z')], []), (nodes, [('a', 'b'), ('a', 'b')], []),
                 (nodes, [('a',)], []), (nodes, [], [('a', 'a', 1)]),
                 (nodes, [], [('a', 'b', 1), ('b', 'a', 2)]),
                 (nodes, [], [('a', 'b', 0)]), (nodes, [], [('a', 'b', 101)]),
                 (nodes, [], [('a', 'b', True)]), (nodes, [], [('a', [], 1)]),
                 (nodes, [], [('a', 'b')]), (iter(nodes), [], [])]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                TheoremGraph(*args)

    def test_rejects_invalid_nodes_and_parameters(self):
        for score in (-1, 6, True, 1.0, 10**100):
            with self.subTest(score=score), self.assertRaises(ValueError):
                node('a', score)
        for key in ('', ' a', 'a' * 65, 123):
            with self.subTest(key=key), self.assertRaises(ValueError):
                node(key)
        for args in ({'weights': {'Q': 1}}, {'weights': {'H': -1}},
                     {'weights': {'H': 11}}, {'weights': {'H': True}},
                     {'weights': [('H', 1)]}, {'max_hops': True}, {'max_hops': 6},
                     {'max_distance': 10**100}, {'max_penalty': -1},
                     {'max_penalty': float('inf')}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.graph.route('graph', 'tree', **args)
        with self.assertRaises(ValueError):
            self.graph.route('missing', 'tree')
        with self.assertRaises(ValueError):
            self.graph.preparation_order('missing')

    def test_immutable_concept_and_snapshot_edges(self):
        nodes = [node('a'), node('b')]
        edges = [['a', 'b', 1]]
        g = TheoremGraph(nodes, [], edges)
        edges[0][2] = 99
        nodes.clear()
        self.assertEqual(g.route('a', 'b').distance, 1)
        with self.assertRaises(AttributeError):
            g.concepts[0].H = 4


if __name__ == '__main__':
    unittest.main()
