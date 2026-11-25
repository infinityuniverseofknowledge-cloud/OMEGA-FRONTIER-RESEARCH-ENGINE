#!/usr/bin/env python3
"""Reproducible small demo; synthetic inputs, no network or scientific validation."""
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from omega.mathcore import modular_difference, inverse_difference, hamming_distance, held_karp_cycle, nearest_neighbor_2opt_cycle, optimality_gap
from omega.knowledge import KnowledgeStore
from omega.simulation import simulate

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
RESULTS.mkdir(exist_ok=True)
DB = ROOT / 'data' / 'frontier_demo.sqlite3'
DB.parent.mkdir(exist_ok=True)
seed = 20261125
words = ['0502', '0503', '1503', '9903', '9902']
matrix = [[hamming_distance(x, y) for y in words] for x in words]
route, optimum = held_karp_cycle(matrix)
heuristic, cost = nearest_neighbor_2opt_cycle(matrix)
gap = optimality_gap(optimum, cost)
with KnowledgeStore(str(DB)) as store:
    store.seed_scenarios()
    scenarios = store.list_scenarios()
    params = scenarios[0]['parameters']
    ecological = simulate(params, seed=seed)
digits = '0502'
delta = modular_difference(digits)
inputs = {'seed': seed, 'words': words, 'digits': digits, 'parameters': params}
outputs = {'digits': {'anchor': digits[0], 'differences': delta,
                      'reconstructed': inverse_difference(delta, digits[0])},
           'tsp': {'matrix': matrix, 'exact_route': route, 'exact_cost': optimum,
                   'heuristic_route': heuristic, 'heuristic_cost': cost,
                   'absolute_gap': gap['absolute'],
                   'relative_gap': str(gap['relative']) if gap['relative'] is not None else None},
           'ecology': ecological}
def digest(obj):
    raw = json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()
record = {'experiment_id': 'frontier-demo-001', 'status': '[PROPOSED]',
          'timestamp_utc': datetime.now(timezone.utc).isoformat(),
          'software_version': 'frontier-first-cycle-1', 'python_version': platform.python_version(),
          'algorithm': ['modular differences', 'Held-Karp', 'nearest-neighbor + 2-opt', 'bounded stochastic population toy model'],
          'inputs': inputs, 'input_sha256': digest(inputs), 'outputs': outputs,
          'output_sha256': digest(outputs), 'scenario_count': len(scenarios),
          'limitations': ['Synthetic inputs only; results are not biological evidence.',
                          'TSP result applies only to the supplied finite instance.',
                          'Quantiles represent assumed model noise, not empirical confidence intervals.',
                          'Hashes apply to canonical JSON as produced by this Python runtime.']}
path = RESULTS / 'demo.json'
path.write_text(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
print(f"Digit: {digits} -> {digits[0]}|{delta} -> {outputs['digits']['reconstructed']}")
print(f"TSP optimum={optimum}, heuristic={cost}; absolute gap={gap['absolute']}")
print(f"Synthetic scenarios={len(scenarios)}; seed={seed}; final median={ecological['trajectory'][-1]['median']:.4f}")
print(f"Results: {path.relative_to(ROOT)}; database: {DB.relative_to(ROOT)}")
print(f"Input SHA-256: {record['input_sha256']}; output SHA-256: {record['output_sha256']}")
