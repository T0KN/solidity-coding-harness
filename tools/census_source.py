#!/usr/bin/env python3
"""Compiler-derived source denominator for checkpoint_census.py.

Only compiler output bound to the current source bytes is accepted. Enumeration
is not a proof of callee trust or of economic correctness.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess


def digest(data):
    return hashlib.sha256(data).hexdigest()


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def local_path(root, value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'path must stay inside the repository: {value}')
    result = (root / path).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f'path escapes repository: {value}')
    return result


def compile_source(root, work):
    command = ['forge', 'build', 'src', '--offline', '--ast', '--build-info',
               '--build-info-path', str(work / 'build-info'), '--out', str(work / 'out'),
               '--cache-path', str(work / 'cache')]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    (work / 'compiler-command.json').write_text(json.dumps(command) + '\n')
    (work / 'compiler.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError('compiler failed; see compiler.log (no empty census accepted)')
    builds = sorted((work / 'build-info').glob('*.json'))
    if len(builds) != 1:
        raise ValueError('expected one complete compiler build-info file')
    return json.loads(builds[0].read_text())


def census(build, root):
    root = Path(root).resolve()
    inputs = build.get('input', {}).get('sources', {})
    outputs = build.get('output', {}).get('sources', {})
    production = sorted(str(p.relative_to(root)) for p in (root / 'src').rglob('*.sol'))
    if set(production) - inputs.keys():
        raise ValueError('compiler census is missing production source files')
    nodes, location, contracts, functions, hashes = {}, {}, {}, {}, {}
    for path, source in inputs.items():
        actual = local_path(root, path).read_bytes()
        if source.get('content', '').encode() != actual:
            raise ValueError(f'stale compiler input: {path}')
        hashes[path] = digest(actual)
        ast = outputs.get(path, {}).get('ast')
        if not isinstance(ast, dict):
            raise ValueError(f'compiler AST missing: {path}')
        for node in walk(ast):
            if 'id' not in node:
                continue
            nodes[node['id']] = node
            location[node['id']] = path
            if node.get('nodeType') == 'ContractDefinition':
                contracts[node['id']] = node
            if node.get('nodeType') in ('FunctionDefinition', 'ModifierDefinition'):
                functions[node['id']] = node

    def signature(fn):
        name = fn.get('name') or fn.get('kind', 'constructor')
        types = []
        for parameter in fn.get('parameters', {}).get('parameters', []):
            value = parameter.get('typeDescriptions', {}).get('typeString')
            if not value:
                raise ValueError('compiler parameter type missing')
            value = re.sub(r'\b(memory|calldata|storage|ref|pointer)\b', '', value)
            value = re.sub(r'^(struct|enum|contract)\s+', '', value).strip()
            types.append(re.sub(r'\s+', ' ', value))
        return name + '(' + ','.join(types) + ')'

    def symbol(fn_id):
        fn = functions[fn_id]
        owner = contracts.get(fn.get('scope'), {})
        return location[fn_id] + ':' + owner.get('name', '<file>') + '.' + signature(fn)

    # Resolve helper and modifier edges by declaration ID, including dependencies.
    graph = {key: set() for key in functions}
    direct = {key: set() for key in functions}
    unresolved = {key: set() for key in functions}
    primitive = re.compile(r'^_*(mint|credit|lock|burn|take|settle|fund)(?:$|[A-Z_])')
    for fn_id, fn in functions.items():
        if fn.get('stateMutability') == 'payable':
            direct[fn_id].add('receive')
        named = primitive.match(fn.get('name', ''))
        if named and fn.get('stateMutability') not in ('pure', 'view'):
            direct[fn_id].add(named[1])
        for node in walk(fn):
            kind = node.get('nodeType')
            if kind == 'YulFunctionCall':
                name = node.get('functionName', {}).get('name')
                if name in ('call', 'callcode', 'delegatecall', 'create', 'create2', 'selfdestruct'):
                    direct[fn_id].add('assembly-value-call')
                    unresolved[fn_id].add('assembly:' + name)
                continue
            if kind == 'ModifierInvocation':
                expression = node.get('modifierName', {})
            elif kind == 'FunctionCall' and node.get('kind') not in ('typeConversion', 'structConstructorCall'):
                expression = node.get('expression', {})
            elif node.get('userFunction') in functions:
                graph[fn_id].add(node['userFunction'])
                continue
            else:
                continue
            while expression.get('nodeType') == 'FunctionCallOptions':
                expression = expression.get('expression', {})
            target = expression.get('referencedDeclaration')
            if target in contracts:
                for constructor in contracts[target].get('nodes', []):
                    if constructor.get('kind') == 'constructor':
                        graph[fn_id].add(constructor['id'])
            if target in functions:
                graph[fn_id].add(target)
                callee = functions[target]
                if not callee.get('body') and callee.get('visibility') in ('public', 'external'):
                    unresolved[fn_id].add('external:' + symbol(target))
                    if callee.get('stateMutability') not in ('pure', 'view'):
                        direct[fn_id].add('external-value-call')
            elif target in nodes and nodes[target].get('nodeType') == 'VariableDeclaration' and nodes[target].get('functionSelector'):
                # A compiler-resolved public getter, not an indirect function pointer.
                pass
            else:
                call_type = expression.get('typeDescriptions', {}).get('typeIdentifier', '')
                member = expression.get('memberName', '')
                if member in ('call', 'delegatecall', 'callcode', 'send', 'transfer'):
                    direct[fn_id].add('transfer')
                    unresolved[fn_id].add('low-level:' + member)
                elif 'function_internal' in call_type or 'function_external' in call_type:
                    unresolved[fn_id].add('indirect:' + expression.get('name', member or '<unknown>'))
                elif expression.get('nodeType') == 'NewExpression' and expression.get('typeName', {}).get('nodeType') == 'UserDefinedTypeName':
                    direct[fn_id].add('create')
    effects = {key: set(value) for key, value in direct.items()}
    unknown = {key: set(value) for key, value in unresolved.items()}
    changed = True
    while changed:
        changed = False
        for key, callees in graph.items():
            new = effects[key].union(*(effects[c] for c in callees))
            missing = unknown[key].union(*(unknown[c] for c in callees))
            if new != effects[key] or missing != unknown[key]:
                effects[key], unknown[key], changed = new, missing, True

    rows, contract_rows = {}, []

    def row(entry, node, canonical=None, inherited=False):
        path = location[node['id']]
        start, length, _ = map(int, node['src'].split(':'))
        raw = inputs[path]['content'].encode()
        selector = node.get('functionSelector')
        name = canonical or signature(node)
        key = entry + '.' + name
        fn_id = node['id']
        is_function = node['nodeType'] == 'FunctionDefinition'
        required = (node['nodeType'] == 'VariableDeclaration' or (is_function and (
            node.get('visibility') in ('public', 'external')
            or node.get('kind') in ('constructor', 'receive', 'fallback')
            or node.get('stateMutability') not in ('pure', 'view')
            or contract['contractKind'] == 'library' or bool(effects.get(fn_id)))))
        return {
            'function_id': key, 'contract': entry, 'canonical_signature': name,
            'source_signature': signature(node) if node['nodeType'] != 'VariableDeclaration' else name,
            'selector': '0x' + selector if selector else None,
            'source_file': path, 'source_hash': hashes[path],
            'start_line': raw[:start].count(b'\n') + 1,
            'end_line': raw[:start + length].count(b'\n') + 1,
            'visibility': node.get('visibility'), 'mutability': node.get('stateMutability', 'view'),
            'kind': 'getter' if node['nodeType'] == 'VariableDeclaration' else (
                'modifier' if node['nodeType'] == 'ModifierDefinition' else node.get('kind', 'function')),
            'required': required,
            'inherited': inherited, 'declaration_only': node['nodeType'] == 'FunctionDefinition' and not node.get('body'),
            'value_operations': sorted(effects.get(fn_id, set())),
            'direct_value_operations': sorted(direct.get(fn_id, set())),
            'resolved_callees': sorted(symbol(c) for c in graph.get(fn_id, set())),
            'unresolved_calls': sorted(unknown.get(fn_id, set())),
        }

    for contract_id, contract in contracts.items():
        path = location[contract_id]
        if path not in production:
            continue
        entry = path + ':' + contract['name']
        contract_rows.append({'contract': entry, 'source_file': path, 'source_hash': hashes[path],
                              'kind': contract['contractKind'], 'abstract': contract.get('abstract', False),
                              'bases': [location[b] + ':' + contracts[b]['name'] for b in contract.get('linearizedBaseContracts', []) if b != contract_id]})
        artifact = build['output'].get('contracts', {}).get(path, {}).get(contract['name'], {})
        methods = artifact.get('evm', {}).get('methodIdentifiers', {})
        by_selector = {value: name for name, value in methods.items()}
        if len(by_selector) != len(methods):
            raise ValueError('ambiguous ABI selector mapping for ' + entry)
        # C3 order chooses the effective implementation, including overrides/getters.
        seen = set()
        for base_id in contract.get('linearizedBaseContracts', [contract_id]):
            for node in contracts[base_id].get('nodes', []):
                selector = node.get('functionSelector')
                if not selector or selector not in by_selector or selector in seen:
                    continue
                seen.add(selector)
                item = row(entry, node, by_selector[selector], base_id != contract_id)
                rows[item['function_id']] = item
        if seen != set(by_selector):
            raise ValueError('ABI denominator could not be resolved for ' + entry)
        # Enumerate all own definitions. Pure/view helpers and modifier definitions
        # remain visible; their effects propagate to required caller rows.
        for node in contract.get('nodes', []):
            if node.get('nodeType') not in ('FunctionDefinition', 'ModifierDefinition'):
                continue
            if node.get('functionSelector') in seen:
                continue
            item = row(entry, node)
            rows[item['function_id']] = item
        # A value-moving inherited internal helper is part of the denominator too.
        roots = [node['id'] for base_id in contract.get('linearizedBaseContracts', [contract_id])
                 for node in contracts[base_id].get('nodes', []) if node['id'] in functions]
        reached, pending = set(), list(roots)
        while pending:
            key = pending.pop()
            if key in reached:
                continue
            reached.add(key)
            pending.extend(graph[key])
        for key in reached:
            fn = functions[key]
            # Library callees are recorded on their production caller. Inherited
            # value-moving methods are definitions of this contract's surface.
            if (location[key] in production or not effects[key] or not fn.get('body')
                    or fn.get('scope') not in contract.get('linearizedBaseContracts', [])):
                continue
            item = row(entry, fn, signature(fn), True)
            # Different dependency owners with the same internal signature remain distinct.
            item['function_id'] = entry + '.inherited[' + symbol(key) + ']'
            rows[item['function_id']] = item
    # One conservative candidate per operation per function. The checker supplies
    # concrete value edges (accounts, amounts, inventory, sink policy) for each.
    # A candidate is an obligation to review, not a claim that a name proves a flow.
    for item in rows.values():
        item['value_candidates'] = [item['function_id'] + '#' + op for op in item['value_operations']]
    return {'contracts': sorted(contract_rows, key=lambda item: item['contract']),
            'functions': sorted(rows.values(), key=lambda item: item['function_id']),
            'source_hashes': {path: hashes[path] for path in production},
            'dependency_hashes': {path: value for path, value in hashes.items() if path not in production},
            'compiler_version': build.get('solcLongVersion'),
            'compiler_settings_hash': digest(json.dumps(build['input'].get('settings', {}), sort_keys=True).encode())}
