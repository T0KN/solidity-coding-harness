#!/usr/bin/env python3
"""Adapters for checker-authored Markdown matrices and JSON census records.

Prose stays prose: parsing a test name or the word PASS never creates evidence.
Unknown optional JSON fields are retained for later plan-format revisions.
"""
import json
import re


COLUMNS = ('intent_source', 'logic', 'reentrancy', 'intended_vs_actual',
           'value_flow', 'classes', 'discrepancies', 'status')
DATASETS = ('functions', 'value_edges', 'obligations', 'evidence', 'suppressions',
            'call_resolutions', 'provenance', 'advisories')
STATES = ('NOT_IMPLEMENTED', 'NA_REVIEWED', 'NOT_RUN', 'UNKNOWN', 'FAIL', 'PASS')


def column(text):
    text = re.sub(r'\([^)]*\)', '', text).strip().lower()
    key = re.sub(r'[^a-z]', '', text)
    return {'function': 'function', 'functionid': 'function_id',
            'intentsource': 'intent_source', 'intendedvsactual': 'intended_vs_actual',
            'valueflow': 'value_flow', 'pattern': 'pattern', 'contract': 'contract',
            'sourcehash': 'source_hash', 'sourcefile': 'source_file',
            'prioraudit': 'prior_audit', 'auditcitation': 'prior_audit'}.get(key, key)


def cells(line):
    """Split a GFM row, respecting escaped pipes and inline-code pipe operators."""
    result, buffer, ticks, escaped = [], '', 0, False
    for part in re.findall(r'`+|.', line.strip().strip('|')):
        if escaped:
            buffer += part
            escaped = False
        elif part == '\\':
            buffer += part
            escaped = True
        elif part.startswith('`'):
            ticks = 0 if len(part) == ticks else (len(part) if not ticks else ticks)
            buffer += part
        elif part == '|' and not ticks:
            result.append(buffer.strip())
            buffer = ''
        else:
            buffer += part
    return result + [buffer.strip()]


def state(value):
    if isinstance(value, dict):
        value = value.get('status', value.get('execution_status', ''))
    match = re.match(r'^\W*(' + '|'.join(STATES) + r')\b', str(value), re.I)
    return match[1].upper() if match else 'UNKNOWN'


def normalize_row(row, origin):
    result = dict(row)
    for key, value in row.items():
        normalized = column(key)
        if normalized in COLUMNS or normalized in ('function', 'function_id'):
            result[normalized] = value
    result.setdefault('origin', origin)
    return result


def read_document(text, origin):
    doc = {key: [] for key in DATASETS}
    doc.update({'origin': origin, 'source_text': text, 'metadata': {}})

    def ingest(data):
        if not isinstance(data, dict):
            raise ValueError(origin + ': census input must be an object')
        for key in DATASETS:
            values = data.get(key, data.get('rows', []) if key == 'functions' else [])
            if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
                raise ValueError(origin + ': ' + key + ' must be an array of objects')
            doc[key].extend(normalize_row(v, origin) if key == 'functions'
                            else dict(v, origin=origin) for v in values)
        doc['metadata'].update({k: v for k, v in data.items() if k not in DATASETS and k != 'rows'})

    if origin.endswith('.json') or text.lstrip().startswith('{'):
        ingest(json.loads(text))
        return doc

    # Machine-only details (hashes, evidence pointers, signers, etc.) may be
    # appended by the checker without rewriting the human-readable matrix.
    fence = re.compile(r'^```(?:checkpoint-census|json checkpoint-census)\s*\n(.*?)^```\s*$', re.M | re.S)
    for match in fence.finditer(text):
        ingest(json.loads(match[1]))
    prose = fence.sub('', text)
    preamble = re.split(r'^#{2,3} ', prose, maxsplit=1, flags=re.M)[0]
    commits = re.findall(r'(?<![0-9a-f])([0-9a-f]{7,40})(?![0-9a-f])', preamble)
    if 'reviewed_commit' not in doc['metadata'] and commits:
        doc['metadata']['reviewed_commit'] = commits[0]
    sources = re.findall(r'src/[\w/]+\.sol', preamble)
    if sources:
        doc['metadata'].setdefault('default_contract', sources[0].rsplit('/', 1)[1][:-4])
    if re.search(r'\bClaude\b', preamble):
        doc['metadata'].setdefault('author_lens', 'claude')

    lines = prose.splitlines()
    index = 0
    while index < len(lines):
        if lines[index].lstrip().startswith('|') and index + 1 < len(lines):
            headings = [column(v) for v in cells(lines[index])]
            if re.fullmatch(r'[\s|:\-]+', lines[index + 1]):
                dataset = 'functions' if 'function' in headings else (
                    'provenance' if 'contract' in headings and 'pattern' in headings else None)
                index += 2
                while index < len(lines) and lines[index].lstrip().startswith('|'):
                    values = cells(lines[index])
                    if dataset:
                        if len(values) != len(headings):
                            raise ValueError(f'{origin}:{index + 1}: malformed {dataset} table row')
                        row = dict(zip(headings, values), origin=f'{origin}:{index + 1}')
                        doc[dataset].append(row)
                    index += 1
                continue
        index += 1

    # Claude's other two matrices use ### `signature` and labelled fields.
    headings = list(re.finditer(r'^###\s+(.+)$', prose, re.M))
    for index, heading in enumerate(headings):
        if '`' not in heading[1]:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(prose)
        body = re.split(r'^##\s', prose[heading.end():end], maxsplit=1, flags=re.M)[0]
        markers = [m for m in re.finditer(r'\*\*([^*\n]+?):\*\*', body)
                   if any(column(label) in COLUMNS for label in m[1].split('/'))]
        row = {'function': heading[1], 'origin': f'{origin}:{prose[:heading.start()].count(chr(10)) + 1}'}
        for offset, marker in enumerate(markers):
            stop = markers[offset + 1].start() if offset + 1 < len(markers) else len(body)
            value = body[marker.end():stop].strip().removesuffix('-').strip()
            for label in marker[1].split('/'):
                key = column(label)
                if key in COLUMNS:
                    row[key] = value
        if any(key in row for key in COLUMNS):
            doc['functions'].append(row)
    return doc


def compact_signature(value):
    """Normalize human type names; selectors remain the authoritative ABI key."""
    value = re.sub(r'\b(memory|calldata|storage|ref|pointer|payable)\b', '', value)
    value = re.sub(r'\b(?:[A-Za-z_]\w*\.)+([A-Za-z_]\w*)', r'\1', value)
    value = re.sub(r'\b(struct|enum|contract)\s+', '', value)
    value = re.sub(r'([\w\]\)])\s+[A-Za-z_]\w*(?=\s*[,\)])', r'\1', value)
    return re.sub(r'\s+', '', value)


def bind_row(row, doc, functions):
    """Return exact compiler IDs; ambiguous names/overloads never expand silently."""
    by_id = {f['function_id']: f for f in functions}
    if row.get('function_id'):
        key = row['function_id']
        if key not in by_id:
            raise ValueError('function_id does not exist: ' + str(key))
        if 'selector' in row and row['selector'] != by_id[key]['selector']:
            raise ValueError('selector disagrees with compiler: ' + str(key))
        return [by_id[key]]
    header = row.get('function', '')
    fragments = re.findall(r'`([^`]+)`', header) or [header]
    contract = row.get('contract') or doc['metadata'].get('default_contract')
    result = []
    type_words = {word for f in functions for word in re.findall(r'\b[A-Za-z_]\w*\b', f['source_signature'].split('(', 1)[-1])}
    for index, fragment in enumerate(fragments):
        match = re.match(r'^(?:(\w+)\.)?([A-Za-z_]\w*)(\(.*\))?', fragment)
        if not match or match[2] in ('internal', 'private', 'public', 'external', 'payable', 'pure', 'view') or fragment.startswith('0x'):
            continue
        owner, name, signature = match.groups()
        # Table function cells can include explanatory inline code after the
        # signature (e.g. ABI `address`, source type `Currency`, `forge inspect`).
        if result and not signature and not owner and (name in type_words or ' ' in fragment):
            continue
        if owner:
            contract = owner
        if not contract:
            raise ValueError('function has no contract context: ' + fragment)
        candidates = [f for f in functions if (f['contract'] == contract or f['contract'].split(':')[-1] == contract)
                      and f['canonical_signature'].split('(')[0] == name]
        explicit = re.search(r'0x[0-9a-fA-F]{8}\b', fragment)
        if not explicit and index + 1 < len(fragments):
            explicit = re.fullmatch(r'0x[0-9a-fA-F]{8}', fragments[index + 1])
        if explicit:
            candidates = [f for f in candidates if f['selector'] == explicit[0].lower()]
        elif signature and signature != '(...)':
            expected = compact_signature(name + signature)
            candidates = [f for f in candidates if expected in (
                compact_signature(f['canonical_signature']), compact_signature(f['source_signature']))]
        if len(candidates) != 1:
            raise ValueError(f'{fragment}: expected one compiler function, found {len(candidates)}')
        result.extend(candidates)
    if not result:
        raise ValueError('no function signature in row: ' + header)
    return list({f['function_id']: f for f in result}.values())
