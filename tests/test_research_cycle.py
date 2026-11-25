import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omega import research_cycle as rc, sat


class ResearchCycleTests(unittest.TestCase):
    def test_canonical_and_hashes(self):
        self.assertEqual(rc.canonical_bytes({'b': 1, 'a': 'é'}), '{"a":"é","b":1}'.encode())
        record = rc.build_record(seed=7, base=3, max_length=3, tsp_n=4)
        self.assertTrue(rc.verify_hashes(record))
        self.assertEqual(record['input_sha256'], hashlib.sha256(rc.canonical_bytes(record['inputs'])).hexdigest())
        self.assertEqual(record['output_sha256'], hashlib.sha256(rc.canonical_bytes(record['outputs'])).hexdigest())
        modified = copy.deepcopy(record)
        modified['inputs']['parameters']['seed'] += 1
        self.assertFalse(rc.verify_hashes(modified))
        modified = copy.deepcopy(record)
        modified['outputs']['tsp']['exact_cost'] += 1
        self.assertFalse(rc.verify_hashes(modified))
        self.assertFalse(rc.verify_hashes({}))
        self.assertTrue(record['timestamp_utc'].endswith('+00:00'))
        self.assertIn('research_cycle', record['versions']['module_source_sha256'])

    def test_deterministic_content(self):
        a = rc.build_record(seed=123, base=3, max_length=3, tsp_n=5)
        b = rc.build_record(seed=123, base=3, max_length=3, tsp_n=5)
        for field in ('inputs', 'outputs', 'input_sha256', 'output_sha256', 'versions', 'constraints'):
            self.assertEqual(a[field], b[field])
        self.assertNotEqual(a['input_sha256'], rc.build_record(seed=124, base=3, max_length=3, tsp_n=5)['input_sha256'])

    def test_counterexample_and_roundtrips(self):
        output = rc.run_experiments(rc.make_inputs(seed=0, base=10, max_length=2, tsp_n=2))
        self.assertEqual(output['anchored_roundtrip']['checked'], 110)
        self.assertEqual([x['checked'] for x in output['anchored_roundtrip']['per_length']], [10, 100])
        hypothesis = output['digit_sum_hypothesis']
        self.assertEqual(hypothesis['status'], 'refuted')
        self.assertEqual(hypothesis['first_counterexample'], {'input': '10', 'anchor': '1',
                         'differences': '9', 'anchored_output': '19',
                         'input_digit_sum': 1, 'output_digit_sum': 10})
        short = rc.run_experiments(rc.make_inputs(base=2, max_length=1, tsp_n=2))
        self.assertEqual(short['digit_sum_hypothesis']['status'], 'not_refuted_in_bounded_domain')
        self.assertIsNone(short['digit_sum_hypothesis']['first_counterexample'])
        self.assertEqual(rc.run_experiments(rc.make_inputs(base=2, max_length=2, tsp_n=2))['digit_sum_hypothesis']['first_counterexample']['input'], '10')

    def test_certificates_and_tsp(self):
        inputs = rc.make_inputs(seed=42, base=2, max_length=2, tsp_n=5)
        output = rc.run_experiments(inputs)
        for inp, result in zip(inputs['cnfs'], output['sat']['instances']):
            self.assertTrue(sat.verify_certificate(inp['num_vars'], inp['clauses'], result['certificate']))
        self.assertEqual([x['certificate']['status'] for x in output['sat']['instances']], ['SAT', 'UNSAT'])
        self.assertEqual(output['tsp']['exact_cost'], output['tsp']['brute_force_cost'])
        self.assertEqual(output['tsp']['permutations_checked'], 24)
        self.assertGreaterEqual(output['tsp']['absolute_gap'], 0)

    def test_boundaries_and_budget(self):
        self.assertEqual(rc.validate_parameters(0, 2, 8, 8, 0), 510)
        self.assertEqual(rc.validate_parameters(rc.MAX_SEED, 10, 4, 2, 1000), 11110)
        for values in [(-1,2,1,2,0), (rc.MAX_SEED+1,2,1,2,0), (True,2,1,2,0),
                       (0,1,1,2,0), (0,11,1,2,0), (0,2,0,2,0),
                       (0,2,9,2,0), (0,2,1,1,0), (0,2,1,9,0),
                       (0,2,1,2,-1), (0,2,1,2,1001), (0,10,5,2,0)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                rc.validate_parameters(*values)
        inputs = rc.make_inputs(base=2, max_length=1, tsp_n=2)
        inputs['cnfs'][0]['clauses'][0][0] = -1
        with self.assertRaises(ValueError):
            rc.run_experiments(inputs)
        self.assertEqual(rc.make_inputs(base=2, max_length=1, tsp_n=2)['cnfs'][0]['clauses'][0][0], 1)

    def test_exclusive_reports(self):
        record = rc.build_record(base=2, max_length=1, tsp_n=2)
        with tempfile.TemporaryDirectory() as d:
            one = rc.save_record(record, d)
            two = rc.save_record(record, d)
            self.assertNotEqual(one, two)
            self.assertTrue(rc.verify_hashes(json.loads(one.read_text(encoding='utf-8'))))
            original = one.read_bytes()
            with patch.object(rc.uuid, 'uuid4') as mock_uuid:
                mock_uuid.return_value.hex = one.stem.removeprefix('generated_')
                with self.assertRaises(FileExistsError):
                    rc.save_record({'different': True}, d)
            self.assertEqual(one.read_bytes(), original)
            self.assertEqual(len(list(Path(d).glob('generated_*.json'))), 2)


if __name__ == '__main__':
    unittest.main()
