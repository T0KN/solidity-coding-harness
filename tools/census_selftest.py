#!/usr/bin/env python3
"""Synthetic acceptance/mutation tests. Never produces module audit evidence."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

from census_documents import bind_row, read_document
from census_source import census, compile_source, digest
from checkpoint_census import Gate

FIXTURES = Path(__file__).resolve().parent / 'fixtures/checkpoint_census'
RUN_ID = 'checkpoint-census-selftest-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class CensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix=RUN_ID + '-')
        cls.base = Path(cls.scratch.name)
        cls.builds = {}
        for name in ('Fixture', 'Surface'):
            root = cls.base / name
            (root / 'src').mkdir(parents=True)
            (root / 'foundry.toml').write_text('[profile.default]\nsolc_version = "0.8.35"\nevm_version = "cancun"\n')
            shutil.copyfile(FIXTURES / (name + '.sol.txt'), root / 'src' / (name + '.sol'))
            work = root / 'capture'
            work.mkdir()
            build = compile_source(root, work)
            cls.builds[name] = (build, census(build, root))

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='census-case-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'src').mkdir()
        shutil.copyfile(FIXTURES / 'Fixture.sol.txt', self.root / 'src/Fixture.sol')
        self.source = deepcopy(self.builds['Fixture'][1])
        self.manifest = {'milestone': 'FIXTURE', 'default_release': 'fixture', 'chain_id': 8453,
                         'releases': {'fixture': ['fixture'], 'future-release': ['fixture', 'future']},
                         'modules': [
                             {'id': 'fixture', 'status': 'built', 'sources': ['src/Fixture.sol'],
                              'builder_lens': 'builder', 'plans': ['plan.json']},
                             {'id': 'future', 'status': 'planned', 'sources': ['src/Future.sol']} ]}
        self.plan = {'author_lens': 'checker', 'source_hashes': self.source['source_hashes'],
                     'dependency_hashes': {}, 'functions': [], 'value_edges': [], 'obligations': [],
                     'evidence': [], 'call_resolutions': []}
        self.audit = {'source_hashes': self.source['source_hashes'], 'dependency_hashes': {}, 'provenance': [
            {'contract': c['contract'], 'pattern': 'Synthetic pull ledger',
             'prior_audit': 'novel — no prior audit', 'source_hash': c['source_hash']}
            for c in self.source['contracts']]}
        for f in self.source['functions']:
            key = f['function_id']
            action = f['canonical_signature'].split('(')[0]
            self.plan['functions'].append({
                'function_id': key, 'selector': f['selector'],
                'intent + source': 'Synthetic holder ledger, novel — no prior audit.',
                'logic': 'Check successful credit and claim, including boundaries.',
                'reentrancy': 'Exercise the recipient callback with an independent actor.',
                'intended-vs-actual': 'Compare receipt and delivery with the fixture model.',
                'value-flow': 'withdrawable; delivered == owed by a legitimate actor, physical inventory.',
                'classes': '2 and 3: independent conservation and double-assignment fuzz.',
                'discrepancies': 'none', 'status': 'PASS', 'evidence_ids': ['result'],
                'required_actions': [action], 'fuzz_cells': [
                    {'cell_id': key + ':2-3', 'required_actions': [action], 'evidence_ids': ['result']}]})
            self.plan['call_resolutions'].extend(
                {'function_id': key, 'call': call, 'source_hash': f['source_hash'],
                 'resolved_target': 'recipient actor', 'rationale': 'Explicit synthetic callback target.', 'reviewer': 'checker'}
                for call in f['unresolved_calls'])
            self.plan['value_edges'].append({
                'edge_id': key + ':sink', 'function_id': key, 'source_hash': f['source_hash'],
                'candidate_ids': f['value_candidates'], 'source_account': 'payer', 'destination_account': 'holder',
                'entitlement_owner': 'holder', 'asset_expression': 'native', 'amount_expression': 'amount',
                'authorized_executor': 'holder calls itself', 'sink_policy': 'withdrawable',
                'inventory_kinds': ['physical'], 'currencies': ['native']})
        for kind in ('round_trip', 'conservation', 'double_assignment'):
            self.plan['obligations'].append({
                'obligation_id': kind, 'kind': kind, 'mechanism': 'invariant',
                'function_ids': [f['function_id'] for f in self.source['functions']],
                'edge_ids': [e['edge_id'] for e in self.plan['value_edges']],
                'exact_assertion': 'Synthetic ' + kind + ' assertion, no protocol evidence.',
                'status': 'PASS', 'reviewer': 'checker', 'evidence_ids': ['result'],
                'required_actions': ['credit', 'claim'], 'top_severity': True})
        test = self.root / 'test/witness.txt'
        test.parent.mkdir()
        test.write_text('SYNTHETIC SELFTEST INPUT; not an executed security test.\n')
        raw = self.root / 'raw.log'
        raw.write_text('SYNTHETIC SELFTEST INPUT; not a fork run.\n')
        self.artifact = {'synthetic_fixture': True, 'evidence_id': 'result', 'run_id': 'fixture-only',
                         'execution_status': 'PASS', 'assertion_result': True, 'mechanism': 'invariant',
                         'test_or_rule_id': 'fixture witness', 'oracle_lens': 'checker',
                         'source_hashes': self.source['source_hashes'], 'dependency_hashes': {},
                         'test_source_hashes': {'test/witness.txt': digest(test.read_bytes())},
                         'raw_artifacts': {'raw.log': digest(raw.read_bytes())},
                         'successful_action_counts': {'credit': 10, 'claim': 10},
                         'substrate': 'fork', 'chain_id': 8453, 'fork_block_number': 1,
                         'fork_block_hash': '0x' + '1' * 64, 'pinned_at_run_start': True,
                         'obligation_ids': [o['obligation_id'] for o in self.plan['obligations']],
                         'assertion_hashes': {o['obligation_id']: digest(o['exact_assertion'].encode()) for o in self.plan['obligations']},
                         'witnesses': [
                             {'edge_id': e['edge_id'], 'inventory_kind': 'physical', 'currency': 'native',
                              'owed': 10, 'delivered': 10, 'debit': 10, 'sender_extra_debit': 0,
                              'actor': {'mechanism': 'self_call', 'holder': 'fixture holder',
                                        'entrypoint': 'fixture holder.claim()', 'kind': 'contract', 'impersonated': False}}
                             for e in self.plan['value_edges']]}

    def run_gate(self, release='fixture', synthetic=True):
        write_json(self.root / 'artifact.json', self.artifact)
        self.plan['evidence'] = [{'evidence_id': 'result', 'run_id': self.artifact['run_id'],
                                 'artifact_path': 'artifact.json', 'artifact_sha256': digest((self.root / 'artifact.json').read_bytes())}]
        write_json(self.root / 'plan.json', self.plan)
        write_json(self.root / 'docs/deep/AUDIT_PROVENANCE.md', self.audit)
        return Gate(self.root, deepcopy(self.manifest), deepcopy(self.source), NOW, allow_synthetic=synthetic).run(release)

    def rejects(self, rule, **kwargs):
        report = self.run_gate(**kwargs)
        self.assertEqual(report['status'], 'FAIL', report)
        self.assertIn(rule, [f['rule'] for f in report['findings']], report)

    def test_complete_fixture_and_unselected_absent_module(self):
        report = self.run_gate()
        self.assertEqual(report['status'], 'PASS', report)
        self.assertEqual(report['modules'][1]['status'], 'NOT_IMPLEMENTED')

    def test_release_cannot_omit_required_source(self):
        self.rejects('NOT_IMPLEMENTED', release='future-release')

    def test_closed_missing_source_never_passes(self):
        self.manifest['modules'][1]['status'] = 'closed'
        self.rejects('NOT_IMPLEMENTED')

    def test_missing_plan_and_unassigned_source(self):
        self.manifest['modules'][0]['plans'] = []
        self.source['source_hashes']['src/Other.sol'] = '0' * 64
        self.rejects('PLAN_ROW_MISSING')
        self.rejects('MODULE_UNASSIGNED')

    def test_missing_row_in_built_and_closed_modules(self):
        self.plan['functions'].pop()
        for status in ('built', 'closed'):
            with self.subTest(status=status):
                self.manifest['modules'][0]['status'] = status
                self.rejects('PLAN_ROW_MISSING')

    def test_every_missing_column_fails(self):
        baseline = deepcopy(self.plan['functions'][0])
        for column in ('intent + source', 'logic', 'reentrancy', 'intended-vs-actual', 'value-flow', 'classes', 'discrepancies', 'status'):
            with self.subTest(column=column):
                self.plan['functions'][0] = deepcopy(baseline)
                del self.plan['functions'][0][column]
                self.rejects('PLAN_CELL_MISSING')

    def test_same_author_is_not_checker(self):
        self.plan['author_lens'] = ' BUILDER '
        self.rejects('PLAN_AUTHOR')

    def test_pending_status_is_not_green_evidence(self):
        self.plan['functions'][0]['status'] = 'NOT_RUN'
        self.rejects('CELL_OUTCOME')

    def test_pass_row_cannot_hide_pending_cell(self):
        self.plan['functions'][0]['classes'] = '2 PASS, 3 NOT_RUN'
        self.rejects('CELL_OUTCOME')

    def test_selector_drift(self):
        self.plan['functions'][0]['selector'] = '0xffffffff'
        self.rejects('CENSUS_DRIFT')

    def test_stale_plan_binding(self):
        self.plan['source_hashes'] = {'src/Fixture.sol': '0' * 64}
        self.rejects('SOURCE_CURRENCY')

    def test_missing_and_stale_audit_pattern(self):
        self.audit['provenance'][0]['source_hash'] = '0' * 64
        self.rejects('AUDIT_SOURCE_CURRENCY')
        self.audit['provenance'] = []
        self.rejects('AUDIT_PATTERN_MISSING')

    def test_prior_source_is_not_prior_audit(self):
        self.plan['functions'][0]['intent + source'] = 'Fork of Original.sol:10; DR-001.'
        self.rejects('FUNCTION_AUDIT_CITATION')

    def test_stranded_credit_mutant_has_no_round_trip(self):
        self.plan['obligations'] = [o for o in self.plan['obligations'] if o['kind'] != 'round_trip']
        self.rejects('SINK_OBLIGATION_MISSING')

    def test_missing_edge_and_unknown_callee(self):
        self.plan['value_edges'] = []
        self.plan['call_resolutions'] = []
        self.rejects('VALUE_EDGE_MISSING')
        self.rejects('UNRESOLVED_CALL')

    def test_vacuous_fuzz_zero_missing_boolean_and_wrong_action(self):
        for counts in ({'credit': 0, 'claim': 10}, {}, {'credit': True, 'claim': 10}, {'other_action': 99}):
            with self.subTest(counts=counts):
                self.artifact['successful_action_counts'] = counts
                self.rejects('EVIDENCE_ACTION_COUNTS')

    def test_unnamed_fuzz_cells_are_not_coverage(self):
        self.plan['functions'][0]['fuzz_cells'] = []
        self.rejects('FUZZ_CELLS_MISSING')

    def test_directed_run_cannot_satisfy_fuzz(self):
        self.artifact['mechanism'] = 'directed'
        self.rejects('FUZZ_EVIDENCE')

    def test_legitimate_holder_not_prank(self):
        self.artifact['witnesses'][0]['actor']['mechanism'] = 'prank(holder)'
        self.rejects('LEGITIMATE_ACTOR')

    def test_delivered_debit_and_sender_extra_each_gate(self):
        for key in ('delivered', 'debit', 'sender_extra_debit'):
            with self.subTest(key=key):
                original = self.artifact['witnesses'][0][key]
                self.artifact['witnesses'][0][key] = original + 1
                self.rejects('DELIVERED_OWED')
                self.artifact['witnesses'][0][key] = original

    def test_each_inventory_and_currency_required(self):
        self.plan['value_edges'][0]['inventory_kinds'] += ['claims', 'mixed']
        self.rejects('INVENTORY_WITNESS_MISSING')
        self.plan['value_edges'][0]['inventory_kinds'] = ['physical']
        self.plan['value_edges'][0]['currencies'].append('second-currency')
        self.rejects('INVENTORY_WITNESS_MISSING')

    def test_declared_edges_cannot_omit_module_inventory(self):
        self.manifest['modules'][0]['required_inventory_kinds'] = ['physical', 'claims', 'mixed']
        self.rejects('MODULE_INVENTORY_MISSING')

    def burn_fixture(self, policy='burn'):
        for e in self.plan['value_edges']:
            e['sink_policy'] = policy
        for w in self.artifact['witnesses']:
            w.update(minted=10, burned=10, locked=10, residue=0)

    def test_burn_and_lock_need_conservation_no_residue(self):
        for policy in ('burn', 'permanent-lock'):
            with self.subTest(policy=policy):
                self.burn_fixture(policy)
                self.assertEqual(self.run_gate()['status'], 'PASS')
                self.artifact['witnesses'][0]['residue'] = 1
                self.rejects('SINK_RECONCILIATION')

    def test_burn_minted_mismatch_and_missing_conservation(self):
        self.burn_fixture()
        self.artifact['witnesses'][0]['burned'] = 9
        self.rejects('SINK_RECONCILIATION')
        self.plan['obligations'] = [o for o in self.plan['obligations'] if o['kind'] != 'conservation']
        self.rejects('SINK_OBLIGATION_MISSING')

    def test_distinct_transaction_obligation(self):
        self.burn_fixture()
        self.plan['obligations'][1]['distinct_transactions'] = True
        self.rejects('DISTINCT_TX_WITNESS')
        for w in self.artifact['witnesses']:
            w['transactions'] = [{'hash': '0x' + '1' * 64, 'block_hash': '0x' + '3' * 64, 'index': 0},
                                 {'hash': '0x' + '2' * 64, 'block_hash': '0x' + '3' * 64, 'index': 1}]
        self.assertEqual(self.run_gate()['status'], 'PASS')
        self.artifact['witnesses'][0]['transactions'][1]['hash'] = '0x' + '1' * 64
        self.rejects('DISTINCT_TX_WITNESS')

    def test_cei_is_advisory_outcomes_gate(self):
        self.plan['advisories'] = [{'rule': 'CEI', 'symbol': self.plan['functions'][0]['function_id'], 'message': 'write after call'}]
        self.assertEqual(self.run_gate()['status'], 'PASS')
        self.plan['obligations'] = [o for o in self.plan['obligations'] if o['kind'] != 'double_assignment']
        self.rejects('OUTCOME_TWIN_MISSING')

    def valid_suppression(self):
        key = self.plan['functions'][0]['function_id']
        self.plan['functions'][0]['status'] = 'UNKNOWN'
        self.plan['suppressions'] = [{'rule': 'CELL_OUTCOME', 'symbol': key,
            'source_hash': self.source['functions'][0]['source_hash'], 'rationale': 'Synthetic reviewed exception.',
            'signers': ['reviewer-one', 'reviewer-two'], 'expires_at': '2026-09-12T00:00:00Z',
            'milestone': 'FIXTURE', 're_review_trigger': 'Before the next milestone or source change.'}]

    def test_two_signer_expiry_binding(self):
        self.valid_suppression()
        self.assertEqual(self.run_gate()['status'], 'PASS')
        original = deepcopy(self.plan['suppressions'][0])
        mutations = {'signers': ['same', 'Same'], 'expires_at': '2026-09-10T00:00:00Z',
                     'source_hash': '0' * 64, 'milestone': 'OTHER', 'rationale': '', 'symbol': '*',
                     'rule': 'PLAN_ROW_MISSING', 're_review_trigger': ''}
        for key, value in mutations.items():
            with self.subTest(field=key):
                self.plan['suppressions'][0] = original | {key: value}
                self.rejects('SUPPRESSION_INVALID')

    def test_unpinned_fork_and_reused_test_artifact(self):
        self.artifact['pinned_at_run_start'] = False
        self.rejects('EVIDENCE_INVALID')
        self.artifact['pinned_at_run_start'] = True
        (self.root / 'test/witness.txt').write_text('different harness')
        self.rejects('EVIDENCE_INVALID')

    def test_evidence_exact_assertion_and_independent_oracle(self):
        self.artifact['assertion_hashes']['conservation'] = '0' * 64
        self.rejects('EVIDENCE_OBLIGATION')
        self.artifact['oracle_lens'] = ' Builder '
        self.rejects('ORACLE_AUTHOR')

    def test_synthetic_artifacts_cannot_pass_real_cli_gate(self):
        self.rejects('EVIDENCE_INVALID', synthetic=False)

    def test_compiler_denominator_and_effects(self):
        source = self.builds['Surface'][1]
        rows = {f['canonical_signature']: f for f in source['functions'] if f['contract'].endswith(':Surface')}
        for signature in ('NUMBER()', 'owner()', 'inheritedEntry()', 'receive()', 'fallback()',
                          'overloaded(address)', 'overloaded(uint256)', 'mintFirst(Peer)', '_helper(Peer)'):
            self.assertIn(signature, rows)
        self.assertTrue(rows['inheritedEntry()']['inherited'])
        self.assertTrue(rows['inheritedEntry()']['required'])
        self.assertFalse(rows['mintFirst(Peer)']['required'])
        self.assertIn('transfer', rows['inheritedEntry()']['value_operations'])
        self.assertIn('mint', rows['withModifier(address)']['value_operations'])
        self.assertIn('mint', rows['viaHelper(address)']['value_operations'])
        self.assertTrue(rows['viaHelper(address)']['unresolved_calls'])
        self.assertEqual(rows['allocate(uint256)']['value_operations'], [])
        self.assertEqual(rows['transferOwnership(address)']['value_operations'], [])
        self.assertIn('transfer', rows['constructor(address)']['value_operations'])
        self.assertTrue(any('indirect:' in call for f in rows.values() for call in f['unresolved_calls']))

    def test_stale_compiler_and_new_source_rejected(self):
        build = self.builds['Fixture'][0]
        (self.root / 'src/Fixture.sol').write_text('// changed\n')
        with self.assertRaisesRegex(ValueError, 'stale compiler'):
            census(build, self.root)
        shutil.copyfile(FIXTURES / 'Fixture.sol.txt', self.root / 'src/Fixture.sol')
        (self.root / 'src/New.sol').write_text('pragma solidity ^0.8.26; contract New {}')
        with self.assertRaisesRegex(ValueError, 'missing production'):
            census(build, self.root)

    def test_table_and_labelled_adapters(self):
        text = '''# Plan\n**Scope:** src/Fixture.sol @ `abcdef0`. Claude checker.\n\n### `credit(address recipient)` — `0xd5d44d80`\n- **intent + source:** fixture.\n- **logic (all branches):** happy; **Branch:** keep this text.\n- **reentrancy/value-flow:** reviewed. **classes:** 2. **discrepancies:** none. **status:** NOT_RUN.\n\n| function | intent + source | logic | reentrancy | intended-vs-actual | value-flow | classes | discrepancies | status |\n|---|---|---|---|---|---|---|---|---|\n| `Fixture.claim()` `0x4e71d92d` | fixture | `a || b` | none | oracle | withdrawable | 2 | none | NOT_RUN |\n'''
        doc = read_document(text, 'plan.md')
        self.assertEqual(len(doc['functions']), 2)
        bindings = [bind_row(row, doc, self.source['functions']) for row in doc['functions']]
        self.assertEqual(sum(map(len, bindings)), 2)
        credit = next(row for row in doc['functions'] if 'credit' in row['function'])
        self.assertIn('keep this text', credit['logic'])
        self.assertEqual(credit['reentrancy'], credit['value_flow'])

    def test_overloaded_bare_name_is_ambiguous(self):
        source = self.builds['Surface'][1]
        doc = {'metadata': {'default_contract': 'Surface'}}
        with self.assertRaisesRegex(ValueError, 'found 2'):
            bind_row({'function': '`overloaded`'}, doc, source['functions'])

    def test_table_explanation_is_not_a_function(self):
        row = {'function': '`Fixture.credit(address)` `0xd5d44d80` (ABI shows `address`, inspect with `forge inspect Fixture abi`)'}
        result = bind_row(row, {'metadata': {}}, self.source['functions'])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['canonical_signature'], 'credit(address)')

    def test_interface_only_module_is_not_implemented(self):
        for function in self.source['functions']:
            function['declaration_only'] = True
        self.rejects('NOT_IMPLEMENTED')
        self.rejects('UNIMPLEMENTED_SURFACE')


if __name__ == '__main__':
    print('run_id: ' + RUN_ID, flush=True)
    unittest.main(verbosity=2)
