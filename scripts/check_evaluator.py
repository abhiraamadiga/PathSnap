"""Score the ten evaluator trips through an explicitly enabled, frozen local API."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean

import httpx

from verify_api import no_private_fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8001')
    parser.add_argument('--bundle-version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(Path('configs/evaluator_registry.json').read_text())
    rows = []
    with httpx.Client(base_url=args.base_url, timeout=180) as client:
        health = client.get('/readyz').raise_for_status().json()
        trips = client.get('/trips').raise_for_status().json()
        if (health['bundle_version'] != args.bundle_version or health['partition'] != 'evaluator_test'
                or trips['partition'] != 'evaluator_test' or not trips['inference_enabled']
                or trips['trip_ids'] != registry['trip_ids']):
            raise ValueError('Expected the frozen bundle and all ten enabled evaluator IDs')
        for trip in trips['trip_ids']:
            response = client.post('/predict', json={'trip_id': trip}).raise_for_status()
            body = response.json()
            no_private_fields(body)
            if (body['trip_id'] != trip or body['partition'] != 'evaluator_test'
                    or body['prediction']['bundle_version'] != args.bundle_version
                    or response.headers['X-Request-ID'] != body['request_id']):
                raise ValueError(f'Unexpected response for trip {trip}')
            evaluation = body['evaluation']
            rows.append({
                'trip_id': trip, 'request_id': body['request_id'],
                'scoring_status': evaluation['status'],
                'scored_observations': evaluation['evaluated_observations'],
                'total_observations': evaluation['total_observations'],
                'coverage': evaluation['reference_coverage'],
                'before_hmm': evaluation['classifier_weak_reference_top1'],
                'after_hmm': evaluation['hmm_weak_reference_top1'],
                'route_edit_similarity': evaluation['reference_sequence_edit_similarity'],
            })
            print(trip, evaluation['status'], evaluation['hmm_weak_reference_top1'], flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'evaluator_scores.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    scored = [row for row in rows if row['after_hmm'] is not None]
    denominator = sum(row['scored_observations'] for row in scored)
    aggregates = {
        'bundle_version': args.bundle_version,
        'archive_sha256': registry['archive_sha256'],
        'trips_scored': len(scored),
        'trips_at_or_above_92_percent': sum(row['after_hmm'] >= .92 for row in scored),
        'trips_at_or_above_93_percent': sum(row['after_hmm'] >= .93 for row in scored),
        'scored_observations': denominator,
        'total_observations': sum(row['total_observations'] for row in rows),
    }
    for key in ('before_hmm', 'after_hmm'):
        aggregates[f'mean_trip_{key}'] = mean(row[key] for row in scored) if scored else None
        aggregates[f'pooled_{key}'] = (
            sum(round(row[key] * row['scored_observations']) for row in scored) / denominator
            if denominator else None
        )
    (args.output / 'evaluator_summary.json').write_text(json.dumps(aggregates, indent=2) + '\n')
    print(json.dumps(aggregates, indent=2))


if __name__ == '__main__':
    main()
