"""Summarise actual Bayesian trials and like-for-like development evaluation."""
import argparse
import csv
import json
from pathlib import Path


def write_report(results, output):
    results=Path(results);output=Path(output)
    trials=json.loads((results/'trials.json').read_text())
    manifest=json.loads((results/'manifest.json').read_text())
    best=json.loads((results/'best_trial.json').read_text())
    rows=list(csv.DictReader((results/'tuned_vs_untuned.csv').open()))
    if len(trials)!=manifest['search']['n_trials'] or any(t['state']!='COMPLETE' for t in trials):
        raise ValueError('Report requires the complete declared trial budget')
    by_name={r['model']:r for r in rows};before=by_name['untuned'];after=by_name['tuned']
    fit_seconds=sum(f['fit_seconds'] for t in trials for f in t['user_attributes']['folds'])
    infer_seconds=sum(f['inference_seconds'] for t in trials for f in t['user_attributes']['folds'])
    unique_configurations=len({json.dumps(t['parameters'],sort_keys=True) for t in trials})
    delta={key:float(after[key])-float(before[key]) for key in ['cv_macro_f1','student_macro_f1','student_weak_reference_top1','student_log_loss']}
    lines=['# Step 7: measured Bayesian optimisation results','',
           'All reported scores use weak geometric reference labels, not verified observation-level road ground truth. The reserved evaluator archive was not used.','',
           '## Search and best configuration','',
           f"Completed {len(trials)} trials with Optuna TPE: one untuned control, {manifest['search']['n_startup_trials']-1} additional startup trials and {len(trials)-manifest['search']['n_startup_trials']} adaptive trials. Each used the same three training-trip folds and all 126,824 eligible observations (752,315 candidate rows, 79 labelled groups). All 80 training trips remain inventoried; one provides no usable labels.",'',
           f"Best trial: **{best['trial']}**, mean CV Macro F1 **{best['cv_macro_f1']:.6f}**, fold SD **{best['cv_macro_f1_std']:.6f}**.",'',
           '```json',json.dumps(best['parameters'],indent=2),'```','',
           f'The {len(trials)} evaluations contain {unique_configurations} unique parameter configurations; repeated TPE proposals are retained with their actual fitting costs.', '',
           'The decision was frozen from training CV before student-test inputs were loaded. Seed, ranges, input hashes and fold assignments are retained in the manifest. The bounded search is not a global optimality claim.','',
           '| Model | CV Macro F1 | Student Macro F1 | Student weak Top-1 | Student log loss | Direct continuity | Fresh fit (s) | Probability inference (s) |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in rows:
        lines.append(f"| {row['model']} | {float(row['cv_macro_f1']):.6f} | {float(row['student_macro_f1']):.6f} | {float(row['student_weak_reference_top1']):.6f} | {float(row['student_log_loss']):.6f} | {float(row['direct_route_continuity']):.6f} | {float(row['fit_seconds']):.3f} | {float(row['inference_seconds']):.3f} |")
    lines+=['','## Did tuning help?','',
            f"Tuned minus untuned: CV Macro F1 {delta['cv_macro_f1']:+.6f}; student Macro F1 {delta['student_macro_f1']:+.6f}; student weak Top-1 {delta['student_weak_reference_top1']:+.6f}; student log loss {delta['student_log_loss']:+.6f} (lower log loss is better).",'',
            ('The search increased the declared CV objective.' if delta['cv_macro_f1']>1e-12 else 'The search did not improve the declared CV objective beyond the enqueued baseline.'),
            ('Student Macro F1 also increased.' if delta['student_macro_f1']>1e-12 else 'Student Macro F1 did not increase; do not describe this as a uniform improvement.'),'',
            'Small changes on these labels do not establish statistical superiority or reliable real-world route accuracy. Do not retune the search based on evaluator results or silently change the scoring definition.','',
            '## Computational cost','',
            f"Summed measured CV fit time across {len(trials)*3} fold fits: {fit_seconds:.3f} seconds ({fit_seconds/60:.2f} minutes). Summed CV predict_proba time: {infer_seconds:.3f} seconds. The two final refits together took {sum(float(r['fit_seconds']) for r in rows):.3f} seconds.",'',
            'These sums exclude archive parsing, input hashing, sampling proposals, SQLite writes, scoring, serialization and plotting. They are not end-to-end wall time or API latency. All timing measurements are machine/load dependent.','',
            '## Traceability and limitations','',
            'Trial parameters, per-fold objectives/log losses/timings and study context are retained. Baseline and tuned final models are refitted on identical training data, then scored on the same ten student-test trips with identical thresholds and metric definitions. Candidate misses remain in accepted-label Top-1; abstained weak labels remain outside its denominator.','',
            'The evaluator ZIP was checked only for structure and kept outside the development pipeline. No evaluator features, routes or scores informed this search. Local SQLite/weights remain in ignored artifacts; source and result evidence are versioned.','',
            'Next: HMM/Viterbi reconstruction and classifier-only versus decoded comparisons, still using development data. Freeze those decisions before final evaluation.','']
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text('\n'.join(lines))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=Path('results/experiments/bayesian_optimization'))
    parser.add_argument('--output',type=Path,default=Path('docs/bayesian-results.md'))
    args=parser.parse_args();write_report(args.results,args.output)


if __name__=='__main__':main()
