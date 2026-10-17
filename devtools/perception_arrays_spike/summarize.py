"""Summarize perception-arrays spike rows: per op, per-observer ms (median, p95, sum), old vs arrays.

Usage: summarize.py <rows.jsonl> [<rows.jsonl> ...]
"""

import json
import statistics
import sys


def stats(values):
    values = sorted(values)
    if not values:
        return 'n/a'
    p95 = values[min(len(values) - 1, round(0.95 * (len(values) - 1)))]
    return f'med {statistics.median(values):.3f} p95 {p95:.3f} sum {sum(values):.2f}'


def phase_medians(observers, key, scale):
    phases = {}
    for row in observers:
        for name, value in row[key].items():
            phases.setdefault(name, []).append(value * scale)
    return {name: round(statistics.median(values), 3) for name, values in phases.items()}


for path in sys.argv[1:]:
    print(f'== {path}')
    for line in open(path):
        op = json.loads(line)
        observers = op['observers']
        if not observers:
            continue
        hits = sum(row['fov_cache_hit_first'] for row in observers)
        print(f"op {op['op']} {op['kind']}: observers {len(observers)}, world {op['world_ms']:.2f} ms "
              f"{ {k: round(v, 2) for k, v in op['world_phases_ms'].items()} }")
        print(f"  visible/observer {stats([row['visible'] for row in observers])}")
        print(f"  array (warm FOV rows)  {stats([row['array_ms'] for row in observers])}")
        print(f"  array (first call)     {stats([row['array_first_ms'] for row in observers])}  FOV-row cache hits {hits}")
        print(f"  materialize to dicts   {stats([row['materialize_ms'] for row in observers])}")
        print(f"  old recompute_observer {stats([row['old_ms'] for row in observers])}")
        print(f"  array phases med ms    {phase_medians(observers, 'array_phases_us', 1e-3)}")
        print(f"  old phases med ms      {phase_medians(observers, 'old_phases_ms', 1.0)}")
