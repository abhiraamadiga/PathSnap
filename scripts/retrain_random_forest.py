"""Select Random Forest parameters on training trips and export one frozen model."""
import argparse
import json
from pathlib import Path
from statistics import mean

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold

from pathsnap.inference.export import export_bundle
from pathsnap.models.dataset import load_dataset
from pathsnap.models.experiments import score
from pathsnap.optimization.bayesian import validate_inputs


def trip_scores(data, probabilities, groups):
    correct = dict.fromkeys(groups, 0)
    for row in data.observations:
        trip = row['trip_id']
        if trip in correct:
            winner = np.argmax(probabilities[row['begin']:row['end']])
            correct[trip] += row['arc_ids'][winner] == row['reference']
    return {
        row['trip_id']: int(correct[row['trip_id']]) / row['accepted_labels']
        for row in data.coverage if row['trip_id'] in correct
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    root = Path.cwd()
    features = root / 'data/processed/step4'
    baseline = json.loads(Path('results/experiments/model_comparison/manifest.json').read_text())
    validate_inputs(features, args.source, baseline)
    config = json.loads(Path('configs/tuned_model.json').read_text())
    base = config['model_parameters']
    candidates = {
        'current': base,
        'larger_feature_subset': {**base, 'max_features': 0.6, 'min_samples_leaf': 8},
        'regularized_deeper': {**base, 'max_depth': 12, 'min_samples_leaf': 12},
    }

    training = load_dataset(features, 'train')
    if len(training.coverage) != 80:
        raise ValueError('Expected 80 training trips')
    folds = list(GroupKFold(3).split(training.X, training.y, training.groups))
    records = {}
    for name, parameters in candidates.items():
        results = []
        for fold, (fit, validation) in enumerate(folds):
            groups = set(training.groups[validation])
            if groups & set(training.groups[fit]):
                raise ValueError('Training and validation share a trip')
            model = RandomForestClassifier(**parameters).fit(training.X[fit], training.y[fit])
            probability = np.zeros(len(training.y))
            probability[validation] = model.predict_proba(training.X[validation])[:, 1]
            per_trip = trip_scores(training, probability, groups)
            results.append({
                'fold': fold, 'per_trip_top1': per_trip,
                'mean_trip_top1': mean(per_trip.values()),
                'validation_macro_f1': score(training.y[validation], probability[validation])['macro_f1'],
                'fit_macro_f1': score(training.y[fit], model.predict_proba(training.X[fit])[:, 1])['macro_f1'],
            })
            print(name, fold, round(results[-1]['mean_trip_top1'], 6), flush=True)
        records[name] = {
            'parameters': parameters, 'folds': results,
            'mean_trip_top1': mean(x for r in results for x in r['per_trip_top1'].values()),
            'mean_validation_macro_f1': mean(r['validation_macro_f1'] for r in results),
            'mean_fit_macro_f1': mean(r['fit_macro_f1'] for r in results),
        }

    winner = max(records, key=lambda name: records[name]['mean_trip_top1'])
    # Keep the incumbent if the gain is below 0.1 percentage points.
    if records[winner]['mean_trip_top1'] - records['current']['mean_trip_top1'] < 0.001:
        winner = 'current'
    output = Path('results/experiments/random_forest_retraining')
    output.mkdir(parents=True, exist_ok=True)
    report = {'selected': winner, 'candidates': records, 'training_trips': 80,
              'usable_training_groups': len(set(training.groups)),
              'selection': 'Grouped training CV mean-trip weak-reference Top-1. Required gain over incumbent: 0.1 percentage points.',
              'training_source_sha256': baseline['raw_source_sha256']}
    (output / 'selection.json').write_text(json.dumps(report, indent=2) + '\n')
    options = records[winner]['parameters']
    model = RandomForestClassifier(**options).fit(training.X, training.y)
    model_path = Path('artifacts/random_forest_retraining') / f'{args.version}.joblib'
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    config['model_parameters'] = options
    config['stage'] = 'retrained_training_trip_cv'
    config['selection_metric'] = report['selection']
    config['evidence'] = str(output / 'selection.json')
    config.pop('next_stage', None)
    frozen = Path('configs/retrained_model.json')
    frozen.write_text(json.dumps(config, indent=2) + '\n')
    bundle, archive, manifest = export_bundle(root, model_path, root / 'artifacts/releases',
                                              args.version, model_config_path=frozen)
    print(winner, bundle, archive, manifest['bundle_version'], flush=True)


if __name__ == '__main__':
    main()
