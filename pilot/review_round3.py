"""Operator reproduction of round-2 claims about retired-ID state, not submitted code."""

import hashlib
import json
from pathlib import Path

from evaluate import resolve


def run():
    query = {'entity': 'synthetic-person', 'property': 'city'}

    def assertion(source, valid_from=0):
        return {'id': 'a', 'type': 'assert', 'entity': 'synthetic-person', 'property': 'city', 'value': 'Porto', 'valid_from': valid_from, 'source': source}

    tombstone = {'id': 'r', 'type': 'retract', 'target': 'a'}
    big = 9007199254740992  # 2**53: the largest integer a binary64 double represents exactly with unit spacing
    cases = [
        ('retired_history_s', [assertion('s'), tombstone], 'unknown'),
        ('retired_history_t', [assertion('t'), tombstone], 'unknown'),
        ('retired_s_then_same_event', [assertion('s'), tombstone, assertion('s')], 'unknown'),
        ('retired_t_then_same_event', [assertion('t'), tombstone, assertion('s')], 'invalid'),
        ('large_valid_from_exact_duplicate', [assertion('s', big), tombstone, assertion('s', big)], 'unknown'),
        ('large_valid_from_off_by_one', [assertion('s', big), tombstone, assertion('s', big + 1)], 'invalid'),
    ]
    results = []
    for name, records, expected in cases:
        actual = resolve(records, query)
        assert actual['status'] == expected, (name, actual)
        assert actual['value'] is None and actual['evidence'] == []
        results.append({'case': name, 'records': records, 'query': query, 'actual': actual, 'expected_status': expected, 'passed': True})
    canonical = lambda record: json.dumps(record, sort_keys=True, separators=(',', ':'))
    exact_digest_differs = hashlib.sha256(canonical(assertion('s', big)).encode()).hexdigest() != hashlib.sha256(canonical(assertion('s', big + 1)).encode()).hexdigest()
    float_collapses = float(big) == float(big + 1)
    results.append({'case': 'integer_canonical_json_keeps_off_by_one_distinct', 'records': [assertion('s', big), assertion('s', big + 1)], 'query': query, 'actual': {'exact_integer_digests_differ': exact_digest_differs, 'binary64_conversion_collapses': float_collapses}, 'expected_status': 'digests_differ_and_double_collapses', 'passed': bool(exact_digest_differs and float_collapses)})
    root = Path(__file__).parent
    return {'schema': 'reson-pmc-review/1', 'method': 'Operator-authored deterministic reproduction on the published reference reader; no submitted code execution or model call', 'dataset_sha256': hashlib.sha256((root / 'cases.json').read_bytes()).hexdigest(), 'reader_sha256': hashlib.sha256((root / 'evaluate.py').read_bytes()).hexdigest(), 'checks': results, 'conclusion': 'Two retired histories that differ only in the assertion source give unknown versus invalid after the same later event, so an exact importer must keep them distinguishable. Exact-integer canonical JSON keeps 2**53 and 2**53+1 apart; converting to binary64 does not.', 'not_proven': ['The ceil(n*log2 M) bit bound for general n and M (only n=1, two sources, is exercised)', 'Any statement about a specific exporter, JCS implementation or deployed RESON code', 'Sufficiency of any compact representation', 'Any model-migration or scientific breakthrough claim']}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
