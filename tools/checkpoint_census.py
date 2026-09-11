#!/usr/bin/env python3
"""Merge gate for source-bound, independently authored checkpoint obligations.

This checks coverage and evidence records, not the truth of a security proof.
See tools/CHECKPOINT_CENSUS.md for the adapters and the trust boundary.
"""
import argparse
from datetime import datetime, timezone
import fnmatch
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

from census_documents import COLUMNS, DATASETS, bind_row, read_document, state
from census_source import census, compile_source, digest, local_path

VERSION = '1'
IMPLEMENTED = {'built', 'closed'}
STATUSES = IMPLEMENTED | {'planned', 'not_implemented', 'in_progress'}
POLICIES = {'withdrawable', 'convert-and-forward', 'burn', 'permanent-lock'}
SUPPRESSIBLE = {'CELL_OUTCOME', 'OBLIGATION_OUTCOME', 'UNRESOLVED_CALL'}


def present(value):
    return value is not None and str(value).strip() not in ('', '-', '…', '...', 'TODO', 'TBD')


def strings(value):
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and present(v) for v in value)


def integer(value):
    return type(value) is int and value >= 0


def utc(value):
    if not isinstance(value, str):
        raise ValueError('expiry must be a timezone-aware ISO string')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('expiry must have a timezone')
    return parsed.astimezone(timezone.utc)


class Gate:
    def __init__(self, root, manifest, source, now=None, allow_synthetic=False):
        self.root, self.manifest, self.source = Path(root).resolve(), manifest, source
        self.now = now or datetime.now(timezone.utc)
        self.findings, self.modules, self.rows, self.datasets = [], [], {}, {k: [] for k in DATASETS}
        self.hashes = source['source_hashes'] | source['dependency_hashes']
        self.functions = {f['function_id']: f for f in source['functions']}
        self.contracts = {c['contract']: c for c in source['contracts']}
        self.snapshots = manifest.get('snapshots', [])
        self.evidence_cache = {}
        self.allow_synthetic = allow_synthetic
        self.chain_id = manifest.get('chain_id')  # required in the manifest for fork evidence (project-agnostic)

    def issue(self, rule, symbol, message, level='hard', source_hash=None):
        item = self.functions.get(symbol, self.contracts.get(symbol, {}))
        self.findings.append({'rule': rule, 'symbol': symbol, 'message': message, 'level': level,
                              'status': 'ADVISORY' if level == 'advisory' else 'FAIL',
                              'source_hash': source_hash or item.get('source_hash')})

    def bound(self, metadata, paths, symbol, rule='SOURCE_CURRENCY'):
        hashes = metadata.get('source_hashes', {})
        dependencies = metadata.get('dependency_hashes', {})
        if not hashes and metadata.get('reviewed_commit'):
            commit = str(metadata['reviewed_commit'])
            candidates = [s for s in self.snapshots if re.fullmatch(r'[0-9a-f]{7,40}', commit)
                          and s.get('commit', '').startswith(commit)]
            if len(candidates) == 1:
                hashes, dependencies = candidates[0]['source_hashes'], candidates[0]['dependency_hashes']
        if not isinstance(hashes, dict) or not isinstance(dependencies, dict):
            self.issue(rule, symbol, 'source_hashes/dependency_hashes must be objects')
            return False
        missing = [p for p in paths if hashes.get(p, dependencies.get(p)) != self.hashes.get(p)]
        stale = [p for p, h in (hashes | dependencies).items() if self.hashes.get(p) != h]
        # Dependency currency cannot be silently omitted from a review snapshot.
        missing_dependencies = set(self.source['dependency_hashes']) - dependencies.keys()
        if missing or stale or missing_dependencies:
            self.issue(rule, symbol, 'missing/stale review binding: ' + ', '.join(sorted(set(missing + stale) | missing_dependencies)))
            return False
        return True

    def document(self, spec):
        spec = {'path': spec} if isinstance(spec, str) else spec
        path = local_path(self.root, spec['path'])
        if not path.is_file():
            self.issue('PLAN_MISSING', spec['path'], 'checker-authored input has not landed')
            return None
        doc = read_document(path.read_text(), spec['path'])
        # A manifest can declare the lens/context, never manufacture missing rows.
        for key in ('author_lens', 'default_contract'):
            if key in spec:
                doc['metadata'].setdefault(key, spec[key])
        for dataset in DATASETS:
            if dataset != 'functions':
                self.datasets[dataset].extend(doc[dataset])
        return doc

    def audit_citation(self, value, catalog):
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
        if re.search(r'novel\s*[—–-]\s*no prior audit', text, re.I):
            return True
        # A Pons source citation or DR alone is not a prior-audit citation.
        refs = re.findall(r'\baudit\[([\w.-]+)\]', text, re.I)
        if refs and all(present(catalog.get(ref)) for ref in refs):
            return True
        return bool(re.search(r'(?:prior[ -]audit|audit citation)\s*:\s*\S+', text, re.I)
                    and re.search(r'https?://[^\s)]+|[\w/.-]+\.(?:md|pdf)(?::\d+|#\S+)?', text))

    def enumerate_modules(self, release):
        modules = self.manifest.get('modules', [])
        if not modules:
            raise ValueError('module manifest is empty')
        ids = [m['id'] for m in modules]
        if len(set(ids)) != len(ids):
            raise ValueError('duplicate module id')
        selected = self.manifest.get('releases', {}).get(release)
        if not strings(selected) or set(selected) - set(ids):
            raise ValueError('release must name a nonempty set of known modules')
        assigned = {}
        for module in modules:
            name, status = module['id'], module['status'].lower()
            if status not in STATUSES or not strings(module.get('sources')):
                raise ValueError(name + ': invalid status/source patterns')
            paths = [p for p in self.source['source_hashes']
                     if any(fnmatch.fnmatchcase(p, pattern) for pattern in module['sources'])]
            info = {'module': name, 'declared_status': status, 'source_files': paths,
                    'status': 'PRESENT' if paths else 'NOT_IMPLEMENTED', 'release_required': name in selected}
            self.modules.append(info)
            if not paths:
                if status in IMPLEMENTED or name in selected:
                    self.issue('NOT_IMPLEMENTED', name, 'required module has no source')
                continue
            for path in paths:
                if path in assigned:
                    self.issue('MODULE_OVERLAP', path, 'source assigned to multiple modules')
                assigned[path] = name
            if name in selected and status not in IMPLEMENTED:
                self.issue('MODULE_NOT_BUILT', name, 'release includes an unfinished module')
            if status not in IMPLEMENTED:
                continue
            functions = [f for f in self.source['functions'] if f['contract'].split(':')[0] in paths
                         and not f['declaration_only']]
            if not functions:
                info['status'] = 'NOT_IMPLEMENTED'
                self.issue('NOT_IMPLEMENTED', name, 'source contains no implemented functions')
            declarations = [f for f in self.source['functions'] if f['contract'].split(':')[0] in paths
                            and f['declaration_only']]
            for declaration in declarations:
                implementations = [f for f in functions
                                   if declaration['contract'] in self.contracts[f['contract']].get('bases', [])
                                   and f['canonical_signature'] == declaration['canonical_signature']]
                if not implementations:
                    self.issue('UNIMPLEMENTED_SURFACE', declaration['function_id'], 'production declaration has no implementing function in this module')
            for function in functions:
                function['module'] = name
                function['builder_lens'] = module.get('builder_lens', '')
            documents = [self.document(p) for p in module.get('plans', [])]
            if not documents:
                self.issue('PLAN_MISSING', name, 'built/closed module has no plan')
            for doc in filter(None, documents):
                author = str(doc['metadata'].get('author_lens', '')).strip().casefold()
                if not author or not module.get('builder_lens') or author == module['builder_lens'].strip().casefold():
                    self.issue('PLAN_AUTHOR', doc['origin'], 'plan lens must be identified and differ from builder')
                self.bound(doc['metadata'], paths, doc['origin'])
                for row in doc['functions']:
                    try:
                        matches = bind_row(row, doc, functions)
                    except ValueError as error:
                        self.issue('CENSUS_DRIFT', row['origin'], str(error))
                        continue
                    for function in matches:
                        key = function['function_id']
                        annotation = doc['metadata'].get('row_annotations', {}).get(key, {})
                        if set(annotation) & (set(COLUMNS) | {'function', 'function_id', 'selector'}):
                            self.issue('ANNOTATION_OVERRIDE', key, 'annotations may add evidence bindings, not replace the human plan')
                            annotation = {}
                        if key in self.rows:
                            self.issue('CENSUS_DRIFT', key, 'duplicate plan row: ' + row['origin'])
                        else:
                            self.rows[key] = (row | annotation, doc)
            for function in functions:
                if function['required'] and function['function_id'] not in self.rows:
                    self.issue('PLAN_ROW_MISSING', function['function_id'], 'compiler surface has no plan row')
        for path in set(self.source['source_hashes']) - assigned.keys():
            self.issue('MODULE_UNASSIGNED', path, 'production source has no module manifest entry')

    def provenance(self):
        path = self.manifest.get('audit_ledger', 'docs/deep/AUDIT_PROVENANCE.md')
        if path != 'docs/deep/AUDIT_PROVENANCE.md':
            self.issue('AUDIT_LEDGER_CANON', path, 'canonical audit ledger must be docs/deep/AUDIT_PROVENANCE.md')
            return
        file = local_path(self.root, path)
        if not file.is_file():
            self.issue('AUDIT_LEDGER_MISSING', path, 'canonical ledger has not landed; research is not a substitute')
            rows, metadata = [], {}
        else:
            doc = read_document(file.read_text(), path)
            rows, metadata = doc['provenance'], doc['metadata']
            self.bound(metadata, list(self.source['source_hashes']), path, 'AUDIT_SOURCE_CURRENCY')
        for key, contract in self.contracts.items():
            matches = [r for r in rows if str(r.get('contract', '')).strip('` *') == key]
            if len(matches) != 1 or not present(matches[0].get('pattern')):
                self.issue('AUDIT_PATTERN_MISSING', key, 'requires exactly one explicit contract pattern-provenance row')
            elif not self.audit_citation(matches[0].get('prior_audit', ''), metadata.get('audit_citations', {})):
                self.issue('AUDIT_PATTERN_CITATION', key, 'pattern needs a prior-audit citation or explicit novel marker')
            elif matches[0].get('source_hash', contract['source_hash']) != contract['source_hash']:
                self.issue('AUDIT_SOURCE_CURRENCY', key, 'pattern row source hash is stale')
        for row in rows:
            if str(row.get('contract', '')).strip('` *') not in self.contracts:
                self.issue('AUDIT_CENSUS_DRIFT', row.get('contract', path), 'provenance row names a missing contract')

    def index(self, dataset, key):
        result = {}
        for row in self.datasets[dataset]:
            identifier = row.get(key)
            if not present(identifier) or identifier in result:
                self.issue('RECORD_ID', row['origin'], f'missing/duplicate {key}')
            else:
                result[identifier] = row
        return result

    def evidence(self, identifier, symbol):
        if identifier in self.evidence_cache:
            return self.evidence_cache[identifier]
        record = self.evidence_index.get(identifier)
        if not record:
            self.issue('EVIDENCE_MISSING', symbol, 'no evidence record: ' + str(identifier))
            return None
        try:
            raw = local_path(self.root, record['artifact_path']).read_bytes()
            if digest(raw) != record['artifact_sha256']:
                raise ValueError('artifact hash mismatch')
            data = json.loads(raw)
            if data.get('synthetic_fixture') and not self.allow_synthetic:
                raise ValueError('synthetic fixture records are never production evidence')
            if data.get('evidence_id') != identifier or not present(data.get('run_id')):
                raise ValueError('artifact needs matching evidence_id and a run_id')
            if record.get('run_id') != data['run_id']:
                raise ValueError('record/artifact run_id mismatch')
            if data.get('execution_status') != 'PASS' or data.get('assertion_result') is not True:
                raise ValueError('assertion was not executed successfully')
            if not present(data.get('test_or_rule_id')):
                raise ValueError('test_or_rule_id is absent')
            self.bound(data, list(self.source['source_hashes']), identifier, 'EVIDENCE_SOURCE_CURRENCY')
            test_hashes = data.get('test_source_hashes', {})
            if not test_hashes:
                raise ValueError('test source hashes are absent')
            for path, expected in test_hashes.items():
                if digest(local_path(self.root, path).read_bytes()) != expected:
                    raise ValueError('stale test source: ' + path)
            if data.get('substrate') == 'fork':
                if (not integer(self.chain_id) or data.get('chain_id') != self.chain_id
                        or not integer(data.get('fork_block_number'))
                        or data['fork_block_number'] == 0 or data.get('pinned_at_run_start') is not True
                        or not re.fullmatch(r'0x[0-9a-fA-F]{64}', data.get('fork_block_hash', ''))):
                    raise ValueError('fork evidence must declare the manifest chain_id and a run-start block number/hash')
            elif data.get('substrate') != 'static':
                raise ValueError('evidence substrate must be fork or static')
            if not isinstance(data.get('raw_artifacts'), dict) or not data['raw_artifacts']:
                raise ValueError('raw output artifacts are absent')
            for path, expected in data['raw_artifacts'].items():
                if digest(local_path(self.root, path).read_bytes()) != expected:
                    raise ValueError('raw output hash mismatch: ' + path)
        except (KeyError, OSError, ValueError, TypeError) as error:
            self.issue('EVIDENCE_INVALID', symbol, str(identifier) + ': ' + str(error))
            self.evidence_cache[identifier] = None
            return None
        self.evidence_cache[identifier] = data
        return data

    def actions(self, data, actions, symbol, fuzz=False):
        counts = data.get('successful_action_counts', {})
        if not strings(actions) or not isinstance(counts, dict) or any(
                not integer(counts.get(action)) or counts[action] == 0 for action in actions):
            self.issue('EVIDENCE_ACTION_COUNTS', symbol, 'every intended action needs an integer successful_action_counts[action] > 0')
        if fuzz and data.get('mechanism') not in ('fuzz', 'invariant'):
            self.issue('FUZZ_EVIDENCE', symbol, 'a directed/static test cannot satisfy a fuzz cell')

    def plan_rows(self):
        for key, (row, doc) in self.rows.items():
            function = self.functions[key]
            for col in COLUMNS:
                if not present(row.get(col)):
                    self.issue('PLAN_CELL_MISSING', key, 'missing column: ' + col)
            if not self.audit_citation(row.get('intent_source', ''), doc['metadata'].get('audit_citations', {})):
                self.issue('FUNCTION_AUDIT_CITATION', key, 'intent + source needs prior-audit citation or “novel — no prior audit”')
            status = state(row.get('status', ''))
            if status not in ('PASS', 'NA_REVIEWED'):
                self.issue('CELL_OUTCOME', key, 'row outcome is ' + status)
            if status == 'NA_REVIEWED':
                reason = str(row.get('status', '')).replace('NA_REVIEWED', '').strip(' .—-()')
                if not reason and not present(row.get('na_rationale')):
                    self.issue('NA_RATIONALE', key, 'NA_REVIEWED needs a reason')
                if function['value_operations']:
                    self.issue('VALUE_NA', key, 'value movement cannot waive its outcome obligations with N/A')
            pending = [col for col in COLUMNS[:-1] if re.search(r'\b(NOT_RUN|NOT_IMPLEMENTED|UNKNOWN|PARTIAL)\b', str(row.get(col, '')))]
            if status == 'PASS' and pending:
                self.issue('CELL_OUTCOME', key, 'PASS row retains unfinished cells: ' + ', '.join(pending))
            evidence_ids = row.get('evidence_ids', [])
            if status == 'PASS' and not strings(evidence_ids):
                self.issue('EVIDENCE_MISSING', key, 'PASS prose/test names need source-bound evidence records')
            for identifier in evidence_ids:
                data = self.evidence(identifier, key)
                if data:
                    self.actions(data, row.get('required_actions'), key)
                    if function['mutability'] not in ('view', 'pure') and data['substrate'] != 'fork':
                        self.issue('FORK_REQUIRED', key, 'logic/reentrancy/differential evidence requires the live fork')
            fuzzy = re.search(r'\b(?:fuzz\w*|invariant\w*)\b', str(row.get('logic', '')) + str(row.get('classes', '')), re.I)
            if fuzzy and not row.get('fuzz_cells'):
                self.issue('FUZZ_CELLS_MISSING', key, 'name the fuzz cells, intended actions and evidence IDs explicitly')
            for cell in row.get('fuzz_cells', []):
                if not present(cell.get('cell_id')) or not strings(cell.get('evidence_ids')):
                    self.issue('FUZZ_EVIDENCE', key, 'fuzz cell needs cell_id and evidence_ids')
                for identifier in cell.get('evidence_ids', []):
                    data = self.evidence(identifier, key)
                    if data:
                        self.actions(data, cell.get('required_actions'), key, fuzz=True)
            for call in function['unresolved_calls']:
                matches = [r for r in self.datasets['call_resolutions'] if r.get('function_id') == key and r.get('call') == call]
                if (len(matches) != 1 or matches[0].get('source_hash') != function['source_hash']
                        or not all(present(matches[0].get(k)) for k in ('resolved_target', 'rationale', 'reviewer'))):
                    self.issue('UNRESOLVED_CALL', key, 'UNKNOWN callee: ' + call)

    def obligations(self):
        edges = self.index('value_edges', 'edge_id')
        obligations = self.index('obligations', 'obligation_id')
        known_candidates = {v for f in self.functions.values() if f.get('module') and f['required'] for v in f['value_candidates']}
        covered = set()
        for edge_id, edge in edges.items():
            function = self.functions.get(edge.get('function_id'))
            if not function or not function.get('module'):
                self.issue('EDGE_DRIFT', edge_id, 'edge names no built function')
                continue
            for field in ('source_account', 'destination_account', 'entitlement_owner', 'asset_expression',
                          'amount_expression', 'authorized_executor'):
                if not present(edge.get(field)):
                    self.issue('EDGE_INCOMPLETE', function['function_id'], edge_id + ': missing ' + field)
            candidates = edge.get('candidate_ids', [])
            if (not strings(candidates) or any(v not in function['value_candidates'] for v in candidates)
                    or edge.get('source_hash') != function['source_hash']):
                self.issue('EDGE_DRIFT', function['function_id'], edge_id + ': stale/unbound operation candidates')
            else:
                covered.update(candidates)
            policy = edge.get('sink_policy')
            if policy not in POLICIES or not strings(edge.get('inventory_kinds')) or not strings(edge.get('currencies')):
                self.issue('SINK_POLICY', function['function_id'], edge_id + ': explicit sink policy, currencies and inventory kinds required')
                continue
            relevant = [o for o in obligations.values() if edge_id in o.get('edge_ids', [])]
            expected = 'conservation' if policy in ('burn', 'permanent-lock') else 'round_trip'
            if not any(o.get('kind') == expected for o in relevant):
                self.issue('SINK_OBLIGATION_MISSING', function['function_id'], edge_id + ': no paired ' + expected + ' obligation')
        for candidate in sorted(known_candidates - covered):
            self.issue('VALUE_EDGE_MISSING', candidate.rsplit('#', 1)[0], 'unreviewed operation candidate: ' + candidate)
        for module in self.manifest['modules']:
            if module['status'].lower() not in IMPLEMENTED:
                continue
            declared = {kind for e in edges.values()
                        if self.functions.get(e.get('function_id'), {}).get('module') == module['id']
                        for kind in e.get('inventory_kinds', [])}
            for kind in set(module.get('required_inventory_kinds', [])) - declared:
                self.issue('MODULE_INVENTORY_MISSING', module['id'], 'module inventory omitted from all edges: ' + kind)

        for key, function in self.functions.items():
            if not function.get('module') or not function['required'] or not function['value_operations']:
                continue
            relevant = [o for o in obligations.values() if key in o.get('function_ids', [])]
            for kind in ('conservation', 'double_assignment'):
                if not any(o.get('kind') == kind and o.get('mechanism') in ('fuzz', 'invariant') for o in relevant):
                    self.issue('OUTCOME_TWIN_MISSING', key, kind + ' fuzz is the hard outcome twin; CEI patterns alone never gate')

        for identifier, obligation in obligations.items():
            function_ids, edge_ids = obligation.get('function_ids', []), obligation.get('edge_ids', [])
            if (not strings(function_ids) or any(f not in self.functions or not self.functions[f].get('module') for f in function_ids)
                    or any(e not in edges for e in edge_ids)):
                self.issue('OBLIGATION_DRIFT', identifier, 'obligation names missing functions/edges')
                continue
            if any(edges[e]['function_id'] not in function_ids for e in edge_ids):
                self.issue('OBLIGATION_DRIFT', identifier, 'edge function is not in the obligation function set')
            for field in ('exact_assertion', 'reviewer', 'kind', 'mechanism'):
                if not present(obligation.get(field)):
                    self.issue('OBLIGATION_INCOMPLETE', identifier, 'missing ' + field)
            if state(obligation.get('status')) != 'PASS':
                self.issue('OBLIGATION_OUTCOME', function_ids[0], identifier + ' is not PASS')
            if not strings(obligation.get('evidence_ids')):
                self.issue('EVIDENCE_MISSING', identifier, 'obligation needs evidence_ids')
            all_witnesses = []
            for evidence_id in obligation.get('evidence_ids', []):
                data = self.evidence(evidence_id, identifier)
                if not data:
                    continue
                self.actions(data, obligation.get('required_actions'), identifier,
                             fuzz=obligation.get('mechanism') in ('fuzz', 'invariant'))
                if data['substrate'] != 'fork':
                    self.issue('FORK_REQUIRED', identifier, 'value outcome evidence must run on the live fork')
                if identifier not in data.get('obligation_ids', []):
                    self.issue('EVIDENCE_OBLIGATION', identifier, 'artifact does not identify this obligation')
                if data.get('assertion_hashes', {}).get(identifier) != digest(str(obligation.get('exact_assertion', '')).encode()):
                    self.issue('EVIDENCE_OBLIGATION', identifier, 'artifact is not bound to this exact assertion')
                if obligation.get('top_severity'):
                    builders = {self.functions[f]['builder_lens'].strip().casefold() for f in function_ids}
                    lens = str(data.get('oracle_lens', '')).strip().casefold()
                    if not lens or lens in builders:
                        self.issue('ORACLE_AUTHOR', identifier, 'top-severity oracle must differ from implementation lens')
                all_witnesses.extend(data.get('witnesses', []))
            for edge_id in edge_ids:
                edge = edges[edge_id]
                for inventory in edge.get('inventory_kinds', []):
                    for currency in edge.get('currencies', []):
                        witnesses = [w for w in all_witnesses if w.get('edge_id') == edge_id
                                     and w.get('inventory_kind') == inventory and w.get('currency') == currency]
                        if not witnesses:
                            self.issue('INVENTORY_WITNESS_MISSING', identifier, f'{edge_id}: no {inventory}/{currency} witness')
                        for witness in witnesses:
                            self.witness(witness, edge, obligation)
        for advisory in self.datasets['advisories']:
            self.issue(advisory.get('rule', 'CEI'), advisory.get('symbol', '<advisory>'),
                       advisory.get('message', ''), level='advisory')

    def witness(self, w, edge, obligation):
        key = obligation['obligation_id']
        if not present(w.get('currency')):
            self.issue('WITNESS_CURRENCY', key, 'witness must reconcile an identified currency')
        if edge['sink_policy'] in ('burn', 'permanent-lock'):
            outcome = 'burned' if edge['sink_policy'] == 'burn' else 'locked'
            if (any(not integer(w.get(k)) for k in ('minted', outcome, 'residue'))
                    or w['minted'] == 0 or w['minted'] != w[outcome] or w['residue'] != 0):
                self.issue('SINK_RECONCILIATION', key, f'per-currency minted == {outcome} > 0 and residue == 0 required')
            if obligation.get('distinct_transactions'):
                tx = w.get('transactions', [])
                if (len(tx) != 2 or not all(re.fullmatch(r'0x[0-9a-fA-F]{64}', t.get('hash', '')) for t in tx)
                        or tx[0]['hash'] == tx[1]['hash']
                        or not re.fullmatch(r'0x[0-9a-fA-F]{64}', tx[0].get('block_hash', ''))
                        or tx[0]['block_hash'] != tx[1].get('block_hash')
                        or not all(integer(t.get('index')) for t in tx) or tx[0]['index'] >= tx[1]['index']):
                    self.issue('DISTINCT_TX_WITNESS', key, 'requires ordered distinct tx hashes in one block')
        else:
            actor = w.get('actor', {})
            if (actor.get('mechanism') != 'self_call' or actor.get('impersonated') is not False
                    or not all(present(actor.get(k)) for k in ('holder', 'entrypoint', 'kind'))):
                self.issue('LEGITIMATE_ACTOR', key, 'exit witness requires the legitimate holder calling as itself; no prank(holder)')
            if (any(not integer(w.get(k)) for k in ('owed', 'delivered', 'debit', 'sender_extra_debit'))
                    or w['owed'] == 0 or not w['delivered'] == w['owed'] == w['debit'] or w['sender_extra_debit'] != 0):
                self.issue('DELIVERED_OWED', key, 'requires delivered == owed == debit > 0 and no sender-extra debit')

    def suppress(self):
        for suppression in self.datasets['suppressions']:
            rule, symbol = suppression.get('rule'), suppression.get('symbol')
            function = self.functions.get(symbol, {})
            try:
                reviewers = suppression['signers']
                valid = (rule in SUPPRESSIBLE and function and suppression.get('source_hash') == function['source_hash']
                         and present(suppression.get('rationale')) and strings(reviewers)
                         and len({v.strip().lower() for v in reviewers}) >= 2
                         and utc(suppression['expires_at']) > self.now
                         and suppression.get('milestone') == self.manifest['milestone']
                         and present(suppression.get('re_review_trigger')))
            except (KeyError, ValueError, TypeError):
                valid = False
            if not valid:
                self.issue('SUPPRESSION_INVALID', symbol or '<missing>', 'hard suppression needs exact rule/symbol/hash, rationale, two signers, future expiry and current milestone/re-review trigger')
                continue
            matches = [f for f in self.findings if f['rule'] == rule and f['symbol'] == symbol and f['level'] == 'hard']
            if not matches:
                self.issue('SUPPRESSION_STALE', symbol, 'suppression no longer matches a finding')
            for finding in matches:
                finding['status'] = 'SUPPRESSED'
                finding['suppression'] = suppression

    def run(self, release):
        self.enumerate_modules(release)
        self.provenance()
        self.evidence_index = self.index('evidence', 'evidence_id')
        self.plan_rows()
        self.obligations()
        self.suppress()
        failed = sum(f['level'] == 'hard' and f['status'] == 'FAIL' for f in self.findings)
        return {'schema_version': VERSION, 'release': release, 'status': 'FAIL' if failed else 'PASS',
                'hard_failures': failed, 'modules': self.modules, 'findings': self.findings,
                'plan_rows_bound': len(self.rows), 'compiler_functions': len(self.functions),
                'required_functions': sum(f.get('module') is not None and f['required'] for f in self.functions.values()),
                'compiler_contracts': len(self.contracts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--manifest', default='tools/census_manifest.json')
    parser.add_argument('--release')
    parser.add_argument('--build-info', type=Path, help='optional fresh compiler capture; bytes are still verified')
    parser.add_argument('--output', type=Path, help='new report directory (default: temporary directory)')
    parser.add_argument('--run-id')
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest:
        return subprocess.call([sys.executable, str(Path(__file__).with_name('census_selftest.py'))])
    run_id = args.run_id or 'checkpoint-census-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', run_id):
        parser.error('invalid run id')
    print(f'[{run_id}] checking checkpoint census', flush=True)
    output = args.output or Path(tempfile.mkdtemp(prefix=run_id + '-'))
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'report.json').exists():
        parser.error('refusing to overwrite an existing run report')
    root = args.root.resolve()
    manifest = {}
    try:
        manifest = json.loads(local_path(root, args.manifest).read_text())
        if not isinstance(manifest, dict):
            manifest = {}
            raise ValueError('manifest must be an object')
        snapshots_path = manifest.get('snapshots_path')
        if snapshots_path:
            manifest['snapshots'] = json.loads(local_path(root, snapshots_path).read_text())
        build = json.loads(args.build_info.read_text()) if args.build_info else compile_source(root, output)
        source = census(build, root)
        (output / 'source-census.json').write_text(json.dumps(source, indent=2) + '\n')
        report = Gate(root, manifest, source).run(args.release or manifest['default_release'])
    except (ValueError, KeyError, TypeError, OSError, AttributeError, IndexError) as error:
        report = {'status': 'FAIL', 'hard_failures': 1, 'findings': [
            {'rule': 'CENSUS_INPUT', 'level': 'hard', 'status': 'FAIL', 'message': str(error)}]}
        # Even a failed compile must keep missing modules visible.
        release = args.release or manifest.get('default_release')
        selected = manifest.get('releases', {}).get(release, [])
        paths = [str(p.relative_to(root)) for p in (root / 'src').rglob('*.sol')]
        modules = manifest.get('modules', [])
        report['modules'] = []
        if isinstance(modules, list):
            for module in modules:
                if not isinstance(module, dict):
                    continue
                patterns = module.get('sources', [])
                exists = isinstance(patterns, list) and any(fnmatch.fnmatchcase(p, pattern)
                         for p in paths for pattern in patterns if isinstance(pattern, str))
                report['modules'].append({'module': module.get('id'), 'release_required': module.get('id') in selected,
                                          'status': 'UNKNOWN' if exists else 'NOT_IMPLEMENTED'})
    report.update(run_id=run_id, tool_version=VERSION)
    (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(f'[{run_id}] {report["status"]}: {report["hard_failures"]} hard failure(s); report: {output / "report.json"}')
    for module in report.get('modules', []):
        print(f'[{run_id}] {module["module"]}: {module["status"]} (release_required={module["release_required"]})')
    groups = {}
    for finding in report['findings']:
        key = (finding['rule'], finding.get('status', 'FAIL'))
        groups[key] = groups.get(key, 0) + 1
    for (rule, status), count in sorted(groups.items()):
        print(f'[{run_id}] {status} {rule}: {count}')
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
