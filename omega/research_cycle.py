"""Bounded offline research cycle; instance results are not general proofs."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from omega import mathcore, optimization, sat

SCHEMA_VERSION = 1
MAX_WORDS = 20_000
MAX_LENGTH = 8
MAX_TSP_N = 8
MAX_SEED = 2**64 - 1
FIXED_CNFS = [
    {"name": "satisfiable", "num_vars": 2, "clauses": [[1, 2], [-1, 2]]},
    {"name": "contradictory_units", "num_vars": 1, "clauses": [[1], [-1]]},
]
CONSTRAINTS = [
    "Only ASCII digits in bases 2..10; all words of each length 1..max_length, including leading zeros.",
    "Digit-sum hypothesis applies to anchor concatenated with modular differences, not differences alone.",
    "CNFs are fixed tiny examples; UNSAT certificate is exhaustive only for its input.",
    "TSP is a seeded symmetric nonnegative integer matrix; brute force and Held-Karp are exponential and limited to n<=8.",
    "Tests and instances do not establish P=NP or P!=NP, nor any biological conclusion.",
    "Digests detect accidental changes when independently compared; they are not signatures or tamper-proof storage.",
]


def canonical_bytes(value):
    """UTF-8 JSON: sorted keys, no extra whitespace, non-ASCII retained, no NaN."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_parameters(seed, base, max_length, tsp_n, max_weight):
    def integer(name, value, low, high):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{name} must be an integer in {low}..{high}')
    integer('seed', seed, 0, MAX_SEED)
    integer('base', base, 2, 10)
    integer('max_length', max_length, 1, MAX_LENGTH)
    integer('tsp_n', tsp_n, 2, MAX_TSP_N)
    integer('max_weight', max_weight, 0, 1000)
    words = sum(base**n for n in range(1, max_length + 1))
    if words > MAX_WORDS:
        raise ValueError(f'exhaustive search exceeds {MAX_WORDS} words')
    return words


def make_inputs(seed=42, base=10, max_length=4, tsp_n=6, max_weight=100):
    words = validate_parameters(seed, base, max_length, tsp_n, max_weight)
    return {
        'parameters': {'seed': seed, 'base': base, 'max_length': max_length,
                       'tsp_n': tsp_n, 'max_weight': max_weight, 'word_count': words},
        'digit_domain': 'all base-b strings of lengths 1..max_length in lexicographic order',
        'cnfs': json.loads(json.dumps(FIXED_CNFS)),
        'tsp_matrix': optimization.random_matrix(tsp_n, seed, max_weight),
        'tsp_distribution': 'independent uniform integer edge weights; symmetric; no triangle inequality required',
    }


def run_experiments(inputs):
    """Execute deterministic bounded experiments; exceptions prevent a success record."""
    p = inputs['parameters']
    expected = validate_parameters(p['seed'], p['base'], p['max_length'], p['tsp_n'], p['max_weight'])
    # Input is constructed by this module; prevent changes from disguising experimental setup.
    if canonical_bytes(inputs) != canonical_bytes(make_inputs(p['seed'], p['base'], p['max_length'], p['tsp_n'], p['max_weight'])):
        raise ValueError('inputs do not match the defined experimental setup')
    base = p['base']
    digest = hashlib.sha256()
    count = 0
    first_counterexample = None
    per_length = []
    for length in range(1, p['max_length'] + 1):
        length_count = 0
        for digits in itertools.product(map(str, range(base)), repeat=length):
            word = ''.join(digits)
            diff = mathcore.modular_difference(word, base)
            decoded = mathcore.inverse_difference(diff, word[0], base)
            if decoded != word:
                raise RuntimeError(f'round-trip failed for {word!r}')
            encoded = word[0] + diff
            record = {'word': word, 'anchor': word[0], 'differences': diff, 'decoded': decoded}
            digest.update(canonical_bytes(record) + b'\n')
            before, after = sum(map(int, word)), sum(map(int, encoded))
            if first_counterexample is None and after > before:
                first_counterexample = {'input': word, 'anchor': word[0], 'differences': diff,
                                        'anchored_output': encoded, 'input_digit_sum': before,
                                        'output_digit_sum': after}
            count += 1
            length_count += 1
        per_length.append({'length': length, 'checked': length_count})
    if count != expected:
        raise RuntimeError('unexpected number of words checked')
    sat_results = []
    for cnf in inputs['cnfs']:
        cert = sat.solve(cnf['num_vars'], cnf['clauses'])
        verified = sat.verify_certificate(cnf['num_vars'], cnf['clauses'], cert)
        if not verified:
            raise RuntimeError('SAT certificate did not verify')
        sat_results.append({'name': cnf['name'], 'certificate': cert, 'verified': True})
    matrix = inputs['tsp_matrix']
    exact_route, exact_cost = mathcore.held_karp_cycle(matrix)
    heuristic_route, heuristic_cost = mathcore.nearest_neighbor_2opt_cycle(matrix)
    if optimization.route_cost(matrix, exact_route) != exact_cost or optimization.route_cost(matrix, heuristic_route) != heuristic_cost:
        raise RuntimeError('TSP route or cost invalid')
    brute_cost, brute_route = min(
        (optimization.route_cost(matrix, (0,) + tail + (0,)), (0,) + tail + (0,))
        for tail in itertools.permutations(range(1, p['tsp_n'])))
    if exact_cost != brute_cost or heuristic_cost < exact_cost:
        raise RuntimeError('TSP solvers disagree with brute-force optimum')
    return {
        'anchored_roundtrip': {'status': 'passed_on_exhaustive_bounded_domain', 'checked': count,
                               'per_length': per_length, 'stream_sha256': digest.hexdigest(),
                               'stream_format': 'canonical JSON records word/anchor/differences/decoded, each followed by LF, lexicographic length-first'},
        'digit_sum_hypothesis': {'hypothesis': 'sum(anchor + differences) <= sum(input)',
                                 'status': 'refuted' if first_counterexample else 'not_refuted_in_bounded_domain',
                                 'first_counterexample': first_counterexample, 'checked': count},
        'sat': {'status': 'certificates_verified_on_fixed_instances', 'instances': sat_results},
        'tsp': {'status': 'verified_on_one_instance', 'exact_route': exact_route, 'exact_cost': exact_cost,
                'brute_force_route': brute_route, 'brute_force_cost': brute_cost,
                'permutations_checked': __import__('math').factorial(p['tsp_n'] - 1),
                'heuristic_route': heuristic_route, 'heuristic_cost': heuristic_cost,
                'absolute_gap': heuristic_cost - exact_cost},
    }


def code_versions():
    modules = {'research_cycle': __file__, 'mathcore': mathcore.__file__,
               'optimization': optimization.__file__, 'sat': sat.__file__}
    return {'python': platform.python_version(), 'implementation': platform.python_implementation(),
            'schema': SCHEMA_VERSION,
            'module_source_sha256': {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                                     for name, path in modules.items()}}


def build_record(seed=42, base=10, max_length=4, tsp_n=6, max_weight=100):
    inputs = make_inputs(seed, base, max_length, tsp_n, max_weight)
    outputs = run_experiments(inputs)
    return {'schema_version': SCHEMA_VERSION, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'versions': code_versions(), 'inputs': inputs, 'input_sha256': sha256(inputs),
            'outputs': outputs, 'output_sha256': sha256(outputs), 'constraints': CONSTRAINTS,
            'evidence_status': 'bounded_computational_experiments_not_general_proofs'}


def verify_hashes(record):
    """Check the two data hashes, not the semantic correctness or metadata authenticity."""
    try:
        return (record['input_sha256'] == sha256(record['inputs']) and
                record['output_sha256'] == sha256(record['outputs']))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def save_record(record, reports_dir=None):
    """Create a fresh unique report exclusively; never overwrite an existing run."""
    directory = Path(reports_dir) if reports_dir is not None else Path(__file__).resolve().parent.parent / 'reports'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ('generated_' + uuid.uuid4().hex + '.json')
    payload = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n'
    # Exclusive create fails on a collision; partial files are removed if writing fails.
    try:
        with path.open('x', encoding='utf-8', newline='\n') as out:
            try:
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())
            except BaseException:
                path.unlink(missing_ok=True)
                raise
    except FileExistsError:
        raise FileExistsError('run ID collision; existing report was not overwritten') from None
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--base', type=int, default=10)
    parser.add_argument('--max-length', type=int, default=4)
    parser.add_argument('--tsp-n', type=int, default=6)
    parser.add_argument('--max-weight', type=int, default=100)
    args = parser.parse_args(argv)
    try:
        record = build_record(args.seed, args.base, args.max_length, args.tsp_n, args.max_weight)
        path = save_record(record)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f'error: {exc}\n')
    print(json.dumps({'report': str(path), 'input_sha256': record['input_sha256'],
                      'output_sha256': record['output_sha256'],
                      'status': record['evidence_status']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
