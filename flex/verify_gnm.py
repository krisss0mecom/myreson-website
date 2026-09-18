"""FLEX-001: recompute the no-training baselines for per-residue flexibility on the public 20-domain packet.
Pure Python + math only (no numpy), so it runs in the sandboxed packet runner. Deterministic shuffles (seeded LCG)."""

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CUTOFF = 7.3


def rank(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb) if va and vb else 0.0


def contacts(xyz, cutoff):
    n = len(xyz)
    adj = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = math.dist(xyz[i], xyz[j])
            if d < cutoff:
                adj[i][j] = adj[j][i] = 1
    return adj


def pinv_diag(adj):
    """diag of the Moore-Penrose pseudo-inverse of the Kirchhoff (Laplacian) matrix.
    For a connected graph, Gamma+ = (L + J/n)^-1 - J/n with J the all-ones matrix; Gauss-Jordan on n x n."""
    n = len(adj)
    m = [[(sum(adj[i]) if i == j else -adj[i][j]) + 1.0 / n for j in range(n)] for i in range(n)]
    inv = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    singular = 0
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-9:
            singular += 1
            continue
        m[col], m[pivot] = m[pivot], m[col]
        inv[col], inv[pivot] = inv[pivot], inv[col]
        f = m[col][col]
        m[col] = [x / f for x in m[col]]
        inv[col] = [x / f for x in inv[col]]
        for r in range(n):
            if r != col and m[r][col]:
                g = m[r][col]
                m[r] = [a - g * b for a, b in zip(m[r], m[col])]
                inv[r] = [a - g * b for a, b in zip(inv[r], inv[col])]
    zero_modes = 1 + singular  # one zero mode is the Laplacian's own; extra singular pivots mean a disconnected graph
    return [inv[i][i] - 1.0 / n for i in range(n)], zero_modes


def lcg(seed):
    state = seed & 0xFFFFFFFF
    while True:
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        yield state


def degree_preserving_shuffle(adj, seed):
    n = len(adj)
    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if adj[i][j]]
    a = [row[:] for row in adj]
    gen = lcg(seed)
    swaps, tries, target = 0, 0, 10 * len(edges)
    while swaps < target and tries < 100 * target:
        tries += 1
        x, y = next(gen) % len(edges), next(gen) % len(edges)
        if x == y:
            continue
        (i, j), (k, l) = edges[x], edges[y]
        if next(gen) % 2:
            k, l = l, k
        if len({i, j, k, l}) < 4 or a[i][l] or a[k][j]:
            continue
        a[i][j] = a[j][i] = 0
        a[k][l] = a[l][k] = 0
        a[i][l] = a[l][i] = 1
        a[k][j] = a[j][k] = 1
        edges[x], edges[y] = (min(i, l), max(i, l)), (min(k, j), max(k, j))
        swaps += 1
    return a


def run():
    data = json.loads((ROOT / 'cases.json').read_text())
    rows = []
    for case in data['cases']:
        xyz, idx = case['ca_xyz_angstrom'], case['torsion_residue_indices']
        adj = contacts(xyz, CUTOFF)
        fl, zero_modes = pinv_diag(adj)
        deg = [sum(row) for row in adj]
        sub = lambda values: [values[i] for i in idx]
        target_t, target_md = case['torsion_rmsf_target'], case['md_rmsf_calpha_348K']
        shuffled = [pinv_diag(degree_preserving_shuffle(adj, 1000 * s + 7))[0] for s in range(3)]
        rows.append({'domain': case['domain'], 'n_residues': case['n_residues'], 'edges': sum(deg) // 2, 'zero_modes': zero_modes,
                     'v7_torsion': case['v7_spearman_torsion_target'], 'aa_torsion': case['aa_baseline_spearman_torsion_target'],
                     'gnm_torsion': round(spearman(sub(fl), target_t), 4), 'gnm_md': round(spearman(fl, target_md), 4),
                     'negdegree_torsion': round(spearman([-d for d in sub(deg)], target_t), 4), 'negdegree_md': round(spearman([-d for d in deg], target_md), 4),
                     'shuffle_torsion_mean': round(sum(spearman(sub(f), target_t) for f in shuffled) / 3, 4), 'shuffle_md_mean': round(sum(spearman(f, target_md) for f in shuffled) / 3, 4)})
    mean = lambda key: round(sum(r[key] for r in rows) / len(rows), 4)
    wins = sum(r['v7_torsion'] > r['gnm_torsion'] for r in rows)
    summary = {key: mean(key) for key in ('v7_torsion', 'aa_torsion', 'gnm_torsion', 'gnm_md', 'negdegree_torsion', 'negdegree_md', 'shuffle_torsion_mean', 'shuffle_md_mean')}
    summary['v7_beats_gnm_on_torsion_target'] = f'{wins}/{len(rows)}'
    checks = [{'case': 'gnm_below_v7_on_torsion_target_mean', 'passed': summary['gnm_torsion'] < summary['v7_torsion'], 'values': {'gnm': summary['gnm_torsion'], 'v7': summary['v7_torsion']}},
              {'case': 'gnm_far_above_aa_baseline', 'passed': summary['gnm_torsion'] > 2 * summary['aa_torsion'], 'values': {'gnm': summary['gnm_torsion'], 'aa': summary['aa_torsion']}},
              {'case': 'degree_shuffle_matches_gnm_on_md_target', 'passed': abs(summary['shuffle_md_mean'] - summary['gnm_md']) < 0.08 and abs(summary['negdegree_md'] - summary['gnm_md']) < 0.08, 'values': {'gnm_md': summary['gnm_md'], 'shuffle_md': summary['shuffle_md_mean'], 'negdegree_md': summary['negdegree_md']}},
              {'case': 'all_contact_graphs_connected', 'passed': all(r['zero_modes'] == 1 for r in rows), 'values': {'zero_modes': [r['zero_modes'] for r in rows]}}]
    return {'schema': 'reson-flex-review/1', 'dataset_sha256': hashlib.sha256((ROOT / 'cases.json').read_bytes()).hexdigest(), 'cutoff_angstrom': CUTOFF, 'method': 'Pure-Python GNM (Kirchhoff pseudo-inverse via Jacobi), degree-preserving edge swaps with a seeded LCG (3 seeds), Spearman on two targets; operator-authored, no contributor code, no network.', 'per_domain': rows, 'summary': summary, 'checks': checks,
            'not_proven': ['That V7 uses more than contact-degree information (needs V7 evaluated against the Cartesian MD RMSF target, never done)', 'Any statement about domains longer than 50 residues', 'That 7.3 A is the best cutoff (10 A gave similar means on 2026-09-16)', 'Statistical significance beyond n=20 (Wilcoxon p=0.29 for V7 vs GNM on 2026-09-16)']}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
