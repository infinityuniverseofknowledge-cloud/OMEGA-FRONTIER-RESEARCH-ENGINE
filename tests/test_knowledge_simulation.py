"""Run: PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v"""
import math
import sqlite3
import unittest

from omega.knowledge import KnowledgeStore, generate_scenarios, SYNTHETIC_ORIGIN
from omega.simulation import simulate


class KnowledgeTests(unittest.TestCase):
    def test_generated_scenarios_are_deterministic_and_explicitly_synthetic(self):
        first = generate_scenarios()
        self.assertEqual(first, generate_scenarios())
        self.assertEqual(len(first), 12)
        self.assertEqual(len({s['id'] for s in first}), 12)
        self.assertTrue(all(s['evidence_status'] == 'synthetic_hypothesis' and
                            s['provenance'] == SYNTHETIC_ORIGIN and s['description']
                            for s in first))

    def test_seed_is_idempotent_and_round_trips_parameters(self):
        with KnowledgeStore() as store:
            self.assertEqual(store.seed_scenarios(), 12)
            self.assertEqual(store.seed_scenarios(), 0)
            self.assertEqual(len(store.list_scenarios()), 12)
            original = {s['id']: s for s in generate_scenarios()}
            for row in store.list_scenarios():
                self.assertEqual(row, original[row['id']])

    def test_source_evidence_provenance_and_fallback_search(self):
        with KnowledgeStore(enable_fts=False) as store:
            self.assertFalse(store.fts_enabled)
            source = store.add_source('Example', 'local:example', 'manual', 'illustration only')
            eid = store.add_evidence(source, 'Habitat pressure changes growth',
                                     'Growth declined 10%', limitations='invented test data')
            self.assertEqual(store.search_evidence('pressure')[0]['id'], eid)
            row = store.search_evidence('10%')[0]
            self.assertEqual((row['locator'], row['assessment'], row['limitations']),
                             ('local:example', 'unverified', 'invented test data'))
            self.assertEqual(store.search_evidence('_'), [])  # wildcard is literal
            with self.assertRaises(sqlite3.IntegrityError):
                store.add_evidence(9999, 'Claim', 'text')
            with self.assertRaises(sqlite3.IntegrityError):
                store.add_evidence(source, 'Claim', 'text', assessment='proven')
            with self.assertRaises(ValueError):
                store.search_evidence('  ')
            with self.assertRaises(ValueError):
                store.search_evidence('test', limit=True)

    def test_search_unicode_casefold_and_literal_substrings(self):
        # The public API must behave identically whether FTS is requested or not.
        for enable_fts in (False, True):
            with self.subTest(enable_fts=enable_fts), KnowledgeStore(enable_fts=enable_fts) as store:
                source = store.add_source('Source', 'offline:test', 'manual')
                first = store.add_evidence(source, 'AÇÃO costeira Straße', 'ΔΕΛΤΑ 10%_\\path')
                second = store.add_evidence(source, 'Outra ação', 'literal 10XX')
                for query in ('ação costeira', 'Ação costeira', 'STRASSE', 'δελτα', '10%_', '\\path'):
                    self.assertEqual([row['id'] for row in store.search_evidence(query)], [first])
                self.assertEqual([row['id'] for row in store.search_evidence(' AÇÃO ')], [first, second])
                self.assertEqual([row['id'] for row in store.search_evidence('ação', limit=1)], [first])
                # Search folds case, but does not strip accents or normalize Unicode.
                self.assertEqual(store.search_evidence('acao'), [])

    def test_fts_if_available_and_rebuild_from_preexisting_evidence(self):
        with KnowledgeStore(enable_fts=False) as store:
            source = store.add_source('Source', 'offline:test', 'manual')
            first = store.add_evidence(source, 'forest resilience', 'specific excerpt')
            store._initialize(True)
            if not store.fts_enabled:
                self.assertEqual(store.search_evidence('forest')[0]['id'], first)
                return
            found = store.connection.execute("SELECT rowid FROM evidence_fts WHERE evidence_fts MATCH ?", ('forest',)).fetchall()
            self.assertEqual([r[0] for r in found], [first])
            second = store.add_evidence(source, 'island resilience', 'another excerpt')
            store.connection.execute('UPDATE evidence SET claim=? WHERE id=?', ('changed forest', second))
            found = store.connection.execute("SELECT rowid FROM evidence_fts WHERE evidence_fts MATCH ? ORDER BY rowid", ('forest',)).fetchall()
            self.assertEqual([r[0] for r in found], [first, second])
            store.connection.execute('DELETE FROM evidence WHERE id=?', (first,))
            found = store.connection.execute("SELECT rowid FROM evidence_fts WHERE evidence_fts MATCH ?", ('forest',)).fetchall()
            self.assertEqual([r[0] for r in found], [second])

    def test_schema_and_constraints(self):
        with KnowledgeStore() as store:
            tables = {r[0] for r in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({'sources', 'evidence', 'scenarios'} <= tables)
            self.assertEqual(store.connection.execute('PRAGMA foreign_keys').fetchone()[0], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                store.add_source(' ', 'loc', 'manual')


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.params = generate_scenarios()[0]['parameters'].copy()

    def test_repeatable_seed_and_distinct_seed(self):
        a = simulate(self.params, seed=42)
        self.assertEqual(a, simulate(self.params, seed=42))
        self.assertNotEqual(a['trajectory'], simulate(self.params, seed=43)['trajectory'])
        self.assertEqual(len(a['trajectory']), self.params['steps'] + 1)
        for row in a['trajectory']:
            self.assertTrue(0 <= row['p05'] <= row['median'] <= row['p95'] <= 10*self.params['carrying_capacity'])
            self.assertTrue(all(math.isfinite(row[k]) for k in ('p05', 'median', 'p95')))
        self.assertTrue(0 <= a['final_below_one_fraction'] <= 1)
        self.assertTrue(a['caveats'])

    def test_all_generated_scenarios_run(self):
        for scenario in generate_scenarios():
            result = simulate(scenario['parameters'], seed=7)
            self.assertEqual(result['parameters'], scenario['parameters'])
            self.assertEqual(len(result['trajectory']), 41)

    def test_no_noise_and_zero_growth_pressure_are_constant(self):
        self.params.update(growth_rate=0, pressure=0, noise_fraction=0)
        result = simulate(self.params)
        self.assertTrue(all(row['median'] == self.params['initial_population'] for row in result['trajectory']))
        self.assertEqual(result['population_cap_events'], 0)

    def test_bounded_cap_is_reported(self):
        self.params.update(initial_population=200, carrying_capacity=100, growth_rate=0,
                           pressure=0, noise_fraction=.5, steps=100, replicates=20)
        result = simulate(self.params, seed=1)
        self.assertGreater(result['population_cap_events'], 0)
        self.assertTrue(all(row['p95'] <= 1000 for row in result['trajectory']))

    def test_invalid_finite_bounds_and_types(self):
        invalid = [('carrying_capacity', 0), ('initial_population', -1), ('initial_population', float('inf')),
                   ('growth_rate', float('nan')), ('growth_rate', 1.1), ('pressure', -0.01),
                   ('noise_fraction', .51), ('steps', True), ('steps', 1.5), ('replicates', 1001),
                   ('initial_population', 10**500)]
        for key, value in invalid:
            with self.subTest(key=key, value=str(value)[:20]):
                p = dict(self.params, **{key: value})
                with self.assertRaises(ValueError):
                    simulate(p)
        for seed in (-1, True, 2**32):
            with self.assertRaises(ValueError):
                simulate(self.params, seed=seed)
        with self.assertRaises(ValueError):
            simulate(dict(self.params, steps=1000, replicates=1000))
        with self.assertRaises(ValueError):
            simulate(dict(self.params, unknown=1))
        p = dict(self.params)
        del p['pressure']
        with self.assertRaises(ValueError):
            simulate(p)

    def test_zero_initial_is_absorbing(self):
        self.params['initial_population'] = 0
        result = simulate(self.params)
        self.assertEqual(result['final_below_one_fraction'], 1)
        self.assertTrue(all(row['p95'] == 0 for row in result['trajectory']))


if __name__ == '__main__':
    unittest.main()
