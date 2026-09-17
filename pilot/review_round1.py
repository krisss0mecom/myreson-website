"""Operator reproduction of a submitted PMC-001 counterexample, not submitted code."""

import hashlib
import json
from pathlib import Path

from evaluate import resolve


def run():
    first = {'id': 'a', 'type': 'assert', 'entity': 'mira', 'property': 'city', 'value': 'Porto', 'valid_from': 1, 'source': 's1'}
    second = {**first, 'id': 'b', 'value': 'Oslo', 'valid_from': 2, 'source': 's2'}
    tombstone = {'id': 'r', 'type': 'retract', 'target': 'b'}
    changed = {**second, 'valid_from': 3, 'source': 's9'}
    query = {'entity': 'mira', 'property': 'city'}
    full = [first, second, tombstone]
    compact = [first, tombstone]
    unrelated = {**first, 'id': 'x', 'entity': 'lea', 'value': 'Oslo'}
    retract_tombstone = {'id': 'q', 'type': 'retract', 'target': 'r'}
    cases = [
        ('full_initial', full, 'known'),
        ('compact_initial', compact, 'known'),
        ('full_duplicate', full + [second], 'known'),
        ('compact_duplicate', compact + [second], 'known'),
        ('full_mutated_id', full + [changed], 'invalid'),
        ('compact_mutated_id', compact + [changed], 'known'),
        ('unrelated_collision', [first, unrelated, {**unrelated, 'value': 'Rome'}], 'invalid'),
        ('retract_of_retract', full + [retract_tombstone], 'invalid'),
    ]
    results = []
    for name, records, expected in cases:
        actual = resolve(records, query)
        assert actual['status'] == expected, (name, actual)
        if expected == 'known':
            assert actual['value'] == 'Porto'
        results.append({'case': name, 'records': records, 'query': query, 'actual': actual, 'expected_status': expected, 'passed': True})
    root = Path(__file__).parent
    return {'schema': 'reson-pmc-review/1', 'method': 'Operator-authored deterministic reproduction; no submitted code execution or model call', 'dataset_sha256': hashlib.sha256((root / 'cases.json').read_bytes()).hexdigest(), 'reader_sha256': hashlib.sha256((root / 'evaluate.py').read_bytes()).hexdigest(), 'checks': results, 'conclusion': 'Dropping retracted bodies loses collision detection in this example; unrelated invalidity is explicitly part of the current contract.', 'not_proven': ['Minimal storage lower bound', 'General correctness of a hash-based export', 'Safety or equivalence of changing global invalidity into per-entity invalidity', 'Any model-migration or scientific breakthrough claim']}


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2))
