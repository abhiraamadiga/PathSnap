# Step 7: measured Bayesian optimisation results

All reported scores use weak geometric reference labels, not verified observation-level road ground truth. The reserved evaluator archive was not used.

## Search and best configuration

Completed 10 trials with Optuna TPE: one untuned control, 2 additional startup trials and 7 adaptive trials. Each used the same three training-trip folds and all 126,824 eligible observations (752,315 candidate rows, 79 labelled groups). All 80 training trips remain inventoried; one provides no usable labels.

Best trial: **4**, mean CV Macro F1 **0.895335**, fold SD **0.029228**.

```json
{
  "n_estimators": 80,
  "max_depth": 10,
  "min_samples_leaf": 5,
  "max_features": "sqrt"
}
```

The 10 evaluations contain 9 unique parameter configurations; repeated TPE proposals are retained with their actual fitting costs.

The decision was frozen from training CV before student-test inputs were loaded. Seed, ranges, input hashes and fold assignments are retained in the manifest. The bounded search is not a global optimality claim.

| Model | CV Macro F1 | Student Macro F1 | Student weak Top-1 | Student log loss | Direct continuity | Fresh fit (s) | Probability inference (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| untuned | 0.894849 | 0.927905 | 0.890801 | 0.099792 | 0.894355 | 90.968 | 0.340 |
| tuned | 0.895335 | 0.925863 | 0.888517 | 0.107259 | 0.896026 | 79.032 | 0.282 |

## Did tuning help?

Tuned minus untuned: CV Macro F1 +0.000486; student Macro F1 -0.002041; student weak Top-1 -0.002283; student log loss +0.007468 (lower log loss is better).

The search increased the declared CV objective.
Student Macro F1 did not increase; do not describe this as a uniform improvement.

Small changes on these labels do not establish statistical superiority or reliable real-world route accuracy. Do not retune the search based on evaluator results or silently change the scoring definition.

## Computational cost

Summed measured CV fit time across 30 fold fits: 1208.914 seconds (20.15 minutes). Summed CV predict_proba time: 15.072 seconds. The two final refits together took 170.000 seconds.

These sums exclude archive parsing, input hashing, sampling proposals, SQLite writes, scoring, serialization and plotting. They are not end-to-end wall time or API latency. All timing measurements are machine/load dependent.

## Traceability and limitations

Trial parameters, per-fold objectives/log losses/timings and study context are retained. Baseline and tuned final models are refitted on identical training data, then scored on the same ten student-test trips with identical thresholds and metric definitions. Candidate misses remain in accepted-label Top-1; abstained weak labels remain outside its denominator.

The evaluator ZIP was checked only for structure and kept outside the development pipeline. No evaluator features, routes or scores informed this search. Local SQLite/weights remain in ignored artifacts; source and result evidence are versioned.

Next: HMM/Viterbi reconstruction and classifier-only versus decoded comparisons, still using development data. Freeze those decisions before final evaluation.
