"""Generate a readable report from actual model experiment outputs."""
import argparse
import csv
import json
from pathlib import Path


def write_report(results,output):
    results=Path(results);output=Path(output)
    comparison=list(csv.DictReader((results/'comparison.csv').open()))
    cv=list(csv.DictReader((results/'cv_results.csv').open()))
    manifest=json.loads((results/'manifest.json').read_text())
    selection=json.loads((results/'selection.json').read_text())
    if len(comparison)!=5:raise ValueError('Expected five completed models')
    lines=['# Measured five-model comparison','',
           'All results below come from the submitted experiment files. Scores measure agreement with weak geometric reference labels, not verified physical GPS ground truth.','',
           f"Training used {manifest['training_observations']:,} eligible observations, {manifest['training_candidate_rows']:,} candidate rows and {manifest['eligible_training_trip_groups']} labelled trip groups from the 80-trip training partition. Trip 00000011 has no usable labels. Training cap: {manifest['config']['max_training_observations_per_trip']} (null/None means all eligible observations).",'',
           'Three-fold trip-grouped CV was followed by refitting each baseline on all eligible training observations and evaluation on all ten student-test trips. Fold-specific scaling is inside the relevant pipelines.','',
           '| Model | CV Macro F1 mean ± fold SD | Student Macro F1 | Weak-reference Top-1 | Log loss | Direct continuity | Final fit (s) | Predict probabilities (s) |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in comparison:
        lines.append(f"| {r['model']} | {float(r['cv_macro_f1_mean']):.4f} ± {float(r['cv_macro_f1_std']):.4f} | {float(r['student_macro_f1']):.4f} | {float(r['student_weak_reference_top1']):.4f} | {float(r['student_log_loss']):.4f} | {float(r['direct_route_continuity']):.4f} | {float(r['fit_seconds']):.3f} | {float(r['inference_seconds']):.3f} |")
    lines+=['','## Baseline selection','',
            f"Selected baseline: **{selection['selected_model']}**, using the highest mean grouped-CV candidate Macro F1 under the predeclared criterion. This is an initial model choice for review and subsequent Bayesian tuning, not a final tuned inference artifact.",'',
            'Fold SD measures variation across these three folds, not a confidence interval. All timing values are measured wall time on the originating machine; final prediction timing excludes candidate generation, loading, decoding and networking.','',
            '## Per-model evidence','']
    for r in comparison:
        folds=[f for f in cv if f['model']==r['model']]
        train=sum(float(f['train_macro_f1']) for f in folds)/len(folds)
        validation=float(r['cv_macro_f1_mean']);gap=train-validation
        lines += [f"### {r['model']}",'',
                  f"Mean fold-training Macro F1: {train:.4f}; held-out-trip CV Macro F1: {validation:.4f}; training-minus-validation gap: {gap:.4f}. Student-test Macro F1: {float(r['student_macro_f1']):.4f}; weak-reference Top-1: {float(r['student_weak_reference_top1']):.4f}; log loss: {float(r['student_log_loss']):.4f}.",'',
                  'A positive training/validation gap is evidence consistent with reduced generalisation to held-out trips; its magnitude must be considered alongside fold variation. These measurements alone do not prove overfitting or underfitting. Model strengths, limitations, objectives and initial hyperparameters are documented in model-experiments.md.','']
    ranking=sorted(comparison,key=lambda r:float(r['cv_macro_f1_mean']),reverse=True)
    lines+=['## Selection uncertainty','',f"The first two CV means differ by {float(ranking[0]['cv_macro_f1_mean'])-float(ranking[1]['cv_macro_f1_mean']):.4f}. The ranking follows the declared criterion; this small difference is not evidence of statistical superiority. Compare inference/fitting costs and probability quality before finalising the Bayesian-tuning target.",'']
    totals={key:sum(r[key] for r in manifest['student_test_coverage']) for key in ['observations','accepted_labels','candidate_misses','no_candidates']}
    lines+=['## Coverage and interpretation','',
            f"Student testing includes {totals['observations']:,} observations. Top-1 is evaluated on {totals['accepted_labels']:,} accepted weak labels, including {totals['candidate_misses']} candidate misses as incorrect. There are {totals['no_candidates']} no-candidate observations in this partition. Candidate metrics exclude abstained labels; direct continuity uses available predictions independently of label acceptance.",'',
            'Distance-derived weak labels and distance-related features can reproduce the same heuristic, yielding optimistic agreement. Neither high F1 nor high Top-1 resolves direction ambiguity, omitted labels or reference-route defects. Review the per-trip tables and Phase 1 coverage maps before drawing route-quality conclusions.','',
            '## Next work','',
            'Review and justify the selected baseline, retain all five experiments, then perform Bayesian hyperparameter optimisation using trip-grouped training CV and compare tuned/untuned performance on the same student-test partition. HMM/Viterbi and classifier-only versus decoded sequence evaluation follow later. No evaluator data was used.','']
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text('\n'.join(lines))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=Path('results/experiments/model_comparison'))
    parser.add_argument('--output',type=Path,default=Path('docs/model-results.md'))
    args=parser.parse_args();write_report(args.results,args.output)


if __name__=='__main__':main()
