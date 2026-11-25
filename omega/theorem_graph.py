"""Small, offline, explicitly editorial mathematical-concept navigator.

Prerequisite arrows are directed *study suggestions*, semantic links are
undirected weighted links; neither kind of edge is a formal proof. See
research/theorem_graph.md for semantics, sources and resource bounds.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_NODES = 8
MAX_DISTANCE = 100
SCORE_FIELDS = ('H', 'C', 'I', 'P', 'B')


def _integer(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in {low}..{high}')
    return value


def _text(value, name, limit):
    if not isinstance(value, str) or len(value) > limit or not value.strip() or value != value.strip():
        raise ValueError(f'{name} must be nonempty trimmed text of at most {limit} characters')
    return value


def _sequence(value, name, limit):
    if not isinstance(value, (list, tuple)) or len(value) > limit:
        raise ValueError(f'{name} must be a list or tuple of at most {limit} items')
    return value


@dataclass(frozen=True)
class Concept:
    key: str
    statement: str
    source: str
    H: int  # editorial hypothesis burden
    C: int  # editorial conceptual complexity
    I: int  # editorial impact
    P: int  # editorial proof burden
    B: int  # editorial breadth

    def __post_init__(self):
        _text(self.key, 'key', 64)
        _text(self.statement, 'statement', 1000)
        _text(self.source, 'source', 500)
        for field in SCORE_FIELDS:
            _integer(getattr(self, field), field, 0, 5)


@dataclass(frozen=True)
class RouteResult:
    status: str  # optimal or no_feasible_route
    path: tuple[str, ...] | None
    distance: int | None
    penalty: int | None
    total: int | None
    explored_states: int
    pruned_states: int
    complete_paths_evaluated: int


class TheoremGraph:
    """Validated bounded graph. Edges are (prerequisite, dependent), or
    (endpoint, endpoint, positive distance), respectively.
    """
    def __init__(self, concepts, prerequisites, semantic_edges):
        _sequence(concepts, 'concepts', MAX_NODES)
        _sequence(prerequisites, 'prerequisites', MAX_NODES * (MAX_NODES - 1))
        _sequence(semantic_edges, 'semantic_edges', MAX_NODES * (MAX_NODES - 1) // 2)
        if not concepts or any(not isinstance(x, Concept) for x in concepts):
            raise ValueError('concepts must be a nonempty list of Concept instances')
        self._nodes = {node.key: node for node in concepts}
        if len(self._nodes) != len(concepts):
            raise ValueError('duplicate concept key')
        self._parents = {key: set() for key in self._nodes}
        self._adjacent = {key: {} for key in self._nodes}
        for edge in prerequisites:
            _sequence(edge, 'prerequisite edge', 2)
            if len(edge) != 2:
                raise ValueError('prerequisite edge must have two endpoints')
            a, b = edge
            self._endpoint(a); self._endpoint(b)
            if a == b or a in self._parents[b]:
                raise ValueError('self-loop or duplicate prerequisite')
            self._parents[b].add(a)
        # Validate the entire prerequisite graph, not only nodes on a route.
        self._topological(set(self._nodes))
        for edge in semantic_edges:
            _sequence(edge, 'semantic edge', 3)
            if len(edge) != 3:
                raise ValueError('semantic edge must have two endpoints and a distance')
            a, b, distance = edge
            self._endpoint(a); self._endpoint(b)
            _integer(distance, 'distance', 1, MAX_DISTANCE)
            if a == b or b in self._adjacent[a]:
                raise ValueError('self-loop or duplicate semantic edge')
            self._adjacent[a][b] = distance
            self._adjacent[b][a] = distance

    def _endpoint(self, key):
        _text(key, 'concept key', 64)
        if key not in self._nodes:
            raise ValueError(f'unknown concept: {key!r}')
        return key

    @property
    def concepts(self):
        return tuple(self._nodes[k] for k in sorted(self._nodes))

    def _topological(self, selected):
        remaining = set(selected)
        result = []
        while remaining:
            ready = sorted(k for k in remaining if not (self._parents[k] & remaining))
            if not ready:
                raise ValueError('prerequisite cycle: blocked concepts ' + ', '.join(sorted(remaining)))
            # Pick the lexicographically first available node at each step.
            chosen = ready[0]
            result.append(chosen)
            remaining.remove(chosen)
        return tuple(result)

    def preparation_order(self, target):
        """All transitive study prerequisites, then target, in a stable DAG order."""
        self._endpoint(target)
        selected = set()
        pending = [target]
        while pending:
            key = pending.pop()
            if key not in selected:
                selected.add(key)
                pending.extend(self._parents[key] - selected)
        return self._topological(selected)

    def route(self, start, end, *, weights=None, max_hops=None,
              max_distance=None, max_penalty=None):
        """Find the globally best simple semantic path under integer constraints.

        The weighted node penalty includes both endpoints. The optimizer is
        exhaustive apart from safe pruning by nonnegative constraint costs.
        Ties use the lexicographically smallest entire key tuple. Directed
        prerequisite arrows are not route edges or implicit constraints.
        """
        self._endpoint(start); self._endpoint(end)
        if weights is None:
            weights = {}
        if not isinstance(weights, dict) or len(weights) > len(SCORE_FIELDS):
            raise ValueError('weights must be a dictionary of score fields')
        if any(not isinstance(k, str) or k not in SCORE_FIELDS for k in weights):
            raise ValueError('unknown score field')
        for key, value in weights.items():
            _integer(value, f'weight {key}', 0, 10)
        n = len(self._nodes)
        if max_hops is None:
            max_hops = n - 1
        if max_distance is None:
            max_distance = (n - 1) * MAX_DISTANCE
        if max_penalty is None:
            max_penalty = n * len(SCORE_FIELDS) * 5 * 10
        _integer(max_hops, 'max_hops', 0, n - 1)
        _integer(max_distance, 'max_distance', 0, (n - 1) * MAX_DISTANCE)
        _integer(max_penalty, 'max_penalty', 0, n * len(SCORE_FIELDS) * 5 * 10)
        penalties = {key: sum(getattr(node, field) * weights.get(field, 0)
                              for field in SCORE_FIELDS)
                     for key, node in self._nodes.items()}
        best = None
        explored = pruned = complete = 0

        def visit(path, distance, penalty):
            nonlocal best, explored, pruned, complete
            explored += 1
            hops = len(path) - 1
            if hops > max_hops or distance > max_distance or penalty > max_penalty:
                pruned += 1
                return
            last = path[-1]
            if last == end:
                complete += 1
                candidate = (distance + penalty, path, distance, penalty)
                if best is None or candidate[:2] < best[:2]:
                    best = candidate
                return
            if hops == max_hops:
                pruned += 1
                return
            for neighbor, cost in sorted(self._adjacent[last].items()):
                if neighbor not in path:
                    visit(path + (neighbor,), distance + cost, penalty + penalties[neighbor])

        visit((start,), 0, penalties[start])
        if best is None:
            return RouteResult('no_feasible_route', None, None, None, None, explored, pruned, complete)
        total, path, distance, penalty = best
        return RouteResult('optimal', path, distance, penalty, total, explored, pruned, complete)


def curated_graph():
    """Six elementary graph-theory concepts; scores and links are editorial."""
    source = ('Reinhard Diestel, Graph Theory, 5th ed., Springer (2017), '
              'chapter 1, https://doi.org/10.1007/978-3-662-53622-3')
    nodes = (
        Concept('graph', 'A finite simple undirected graph consists of a finite vertex set and a set of two-element vertex subsets.', source, 1, 1, 5, 0, 5),
        Concept('walk', 'A walk is a finite sequence of vertices with consecutive vertices adjacent; repetitions are allowed.', source, 1, 2, 4, 0, 4),
        Concept('path', 'A path is a walk with no repeated vertex.', source, 1, 2, 5, 0, 5),
        Concept('connected', 'A graph is connected if every two distinct vertices are joined by a path.', source, 1, 2, 5, 0, 4),
        Concept('tree', 'A tree is a connected graph with no cycle.', source, 2, 3, 5, 1, 4),
        Concept('tree_edge_theorem', 'For a finite simple undirected graph with n >= 1 vertices, it is a tree if and only if it is connected and has exactly n - 1 edges.', source, 3, 4, 4, 3, 3),
    )
    prerequisites = (('graph', 'walk'), ('walk', 'path'), ('path', 'connected'),
                     ('connected', 'tree'), ('tree', 'tree_edge_theorem'))
    links = (('graph', 'walk', 2), ('graph', 'path', 4), ('walk', 'path', 1),
             ('path', 'connected', 2), ('connected', 'tree', 2),
             ('tree', 'tree_edge_theorem', 1), ('connected', 'tree_edge_theorem', 4))
    return TheoremGraph(nodes, prerequisites, links)
