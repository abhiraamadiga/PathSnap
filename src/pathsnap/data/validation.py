"""Structural and data-quality inventory; reference routes are not GPS labels."""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from .loading import load_trips, PARTITIONS


def validate_trip(trip):
    rows = trip.rows
    issues = Counter(trip.issues)
    def coordinates(kind):
        valid = []
        for row in rows[kind]:
            if row is None:
                continue
            if not all(math.isfinite(x) for x in row) or not (-180 <= row[0] <= 180 and -90 <= row[1] <= 90):
                issues[f'invalid {kind} coordinates or nonfinite values'] += 1
            else:
                valid.append(row)
        return valid
    gps, nodes = coordinates('track'), coordinates('nodes')
    deltas = [b[2] - a[2] for a, b in zip(rows['track'], rows['track'][1:])
              if a is not None and b is not None and math.isfinite(a[2]) and math.isfinite(b[2])]
    for key, count in [('nonincreasing timestamps', sum(d <= 0 for d in deltas)),
                       ('gaps over one second', sum(d > 1 for d in deltas))]:
        if count:
            issues[key] += count
    # Weak connectivity ignores direction; routing will need directed reachability.
    count = len(rows['nodes'])
    parent = list(range(count))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    used = set()
    valid_arcs = {}
    for i, arc in enumerate(rows['arcs']):
        if arc is None:
            continue
        u, v = arc
        if not (0 <= u < count and 0 <= v < count) or rows['nodes'][u] is None or rows['nodes'][v] is None:
            issues['arcs with invalid node references'] += 1
            continue
        valid_arcs[i] = arc
        used.update(arc)
        parent[find(u)] = find(v)
    route = []
    for row in rows['route']:
        if row is not None:
            arc_id = row[0]
            if arc_id not in valid_arcs:
                issues['route with invalid arc references'] += 1
            route.append(arc_id)
    breaks = sum(valid_arcs[a][1] != valid_arcs[b][0] for a, b in zip(route, route[1:]) if a in valid_arcs and b in valid_arcs)
    if breaks:
        issues['nonjoining consecutive reference arcs'] += breaks
    result = {'partition': trip.partition, 'trip_id': trip.trip_id}
    for kind in rows:
        result[f'{kind}_rows'] = len(rows[kind])
        result[f'{kind}_bytes'] = trip.sizes[kind]
    result.update(valid_gps_rows=len(gps), valid_node_rows=len(nodes),
                  duration_seconds=gps[-1][2]-gps[0][2] if gps else None,
                  timestamp_steps=len(deltas), one_second_steps=sum(d == 1 for d in deltas),
                  max_gap_seconds=max(deltas, default=None),
                  weak_components=len({find(i) for i in range(count)}), isolated_nodes=count-len(used),
                  gps_bounds=[min(r[0] for r in gps), min(r[1] for r in gps), max(r[0] for r in gps), max(r[1] for r in gps)] if gps else None,
                  issues=dict(issues))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('results/experiments/dataset_inventory'))
    args = parser.parse_args()
    results = [validate_trip(t) for t in load_trips(args.source)]
    counts = Counter(r['partition'] for r in results)
    if dict(counts) != PARTITIONS:
        raise SystemExit(f'Expected {PARTITIONS}, found {dict(counts)}; check dataset root')
    ids = {p: {r['trip_id'] for r in results if r['partition'] == p} for p in PARTITIONS}
    if ids['train'] & ids['student_test']:
        raise SystemExit('Trip IDs overlap between partitions')
    summary = {'source_name': args.source.name, 'partition_counts': dict(counts),
               'totals': {k: sum(r[k] for r in results) for k in ['track_rows', 'nodes_rows', 'arcs_rows', 'route_rows']},
               'one_second_step_fraction': sum(r['one_second_steps'] for r in results)/sum(r['timestamp_steps'] for r in results),
               'trips_with_issues': sum(bool(r['issues']) for r in results),
               'trips': results}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'inventory.json').write_text(json.dumps(summary, indent=2)+'\n')
    with (args.output/'inventory.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=results[0].keys(), lineterminator='\n')
        writer.writeheader()
        writer.writerows({**r, 'issues': json.dumps(r['issues']), 'gps_bounds': json.dumps(r['gps_bounds'])} for r in results)
    print(json.dumps({k:v for k,v in summary.items() if k != 'trips'}, indent=2))


if __name__ == '__main__':
    main()
