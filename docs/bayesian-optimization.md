# Step 7: Bayesian hyperparameter optimisation

## Run

From the PathSnap root, with the Step 4 generated data and Step 5 evidence available:

```bash
python -m pip install -e '.[eda,features,models,optimization]'
python -m unittest discover -s tests -v
python -m pathsnap.optimization.bayesian --source '../Provided_Material/Student folder.zip'
python -m pathsnap.optimization.reporting
```

If processed data are absent, first run the Step 4 build and audit commands. Source must be the original **development** ZIP, not `evaluator_test.zip`. Hash checks require exactly the processed inputs used in the original comparison, with identical trip folds. Do not change preprocessing or regenerate with different settings and then call it a like-for-like tuning comparison.

Configuration: `configs/bayesian_search.json`. Outputs: `results/experiments/bayesian_optimization/`. Local SQLite study and fitted untuned/tuned forests: ignored `artifacts/bayesian_optimization/`. Selected inference parameters: `configs/tuned_model.json`.

The notebook is unrelated to this search and is not needed to run it.

## Method and search space

Optuna's Tree-structured Parzen Estimator (TPE) is a sequential model-based Bayesian search strategy. It models parameter regions associated with better/worse previous objective values and proposes subsequent configurations accordingly. It is not a Gaussian-process search and this finite budget does not establish a global optimum.

Ten total trials use seed 42: trial 0 is the enqueued untuned control; two further startup trials precede seven adaptive TPE trials. Trial evaluation is sequential with four forest-fitting threads. No pruning is applied; every completed trial evaluates all three folds. TPE can propose a configuration more than once; repeats are retained and evaluated, and the report distinguishes total trials from unique configurations.

| Hyperparameter | Search values | Reason |
| --- | --- | --- |
| `n_estimators` | 40, 80 | Explore lower ensemble cost while retaining the original 80-tree control |
| `max_depth` | 8, 10, 12, 14, 16, 18 | Test capacity around the baseline depth 14 and its observed train/CV gap |
| `min_samples_leaf` | 5, 10, 15, 20, 25, 30 | Test stronger leaf regularisation than the baseline minimum 5 |
| `max_features` | sqrt, 0.5 | Vary feature subsampling with ten available features |

The bounded search balances measured full-training forest cost with coverage of regularisation and feature-sampling choices. Ten trials are a computational budget, not a claim that all combinations were explored. The space is derived from the baseline model/cost evidence, not evaluator trips. Bootstrap, Gini criterion, binary threshold 0.5, preprocessing, weak-reference labels and feature order remain fixed.

## Objective and partitions

Maximise mean candidate Macro F1 over the original three training-trip folds. Every eligible training observation is retained: 126,824 observations and 752,315 candidate rows across 79 labelled trip groups. The 80th training trip remains inventoried but has no usable labels. No observations from one trip cross fitting/validation folds.

The objective receives only training data and fold indices. Student testing is not an objective input. Compressed input files from both development partitions are hashed for provenance before the search; their student-test feature/reference records are decoded only after selection. Once the best trial is chosen, its parameters are written to `best_trial.json` **before** loading student-test features/references. The untuned control and best configuration are then independently refitted on the same full eligible training data and scored on the same ten student-test trips.

The evaluator ZIP is completely excluded from optimisation, feature calculations and score computation. Registry inspection and its later deployment role are documented separately in `evaluator-data-plan.md`.

## Results and evidence

- `manifest.json`: configuration, versions, original input hashes, folds and study-context fingerprint.
- `trials.csv` / `trials.json`: every trial's parameters, objective, fold F1/log loss, variability and measured fitting/inference times.
- `best_trial.json`: training-CV-only decision frozen before student-test loading.
- `tuned_vs_untuned.csv`: identical-metric comparison of CV F1, student Top-1/F1/log loss, direct continuity and fresh measured fit/inference timings.
- Untuned/tuned metrics JSON and observation prediction CSV files: development evidence, with weak references retained for verification only.
- `optimization_history.png`: actual completed-trial objectives and best-so-far values. It is not an artificial epoch learning curve.
- `docs/bayesian-results.md`: readable report generated from the actual outputs, including whether tuning helped and the computational cost.

All classification and Top-1 metrics still measure **weak-label agreement**, not verified per-GPS physical truth. Candidate misses count as incorrect in accepted-label Top-1; unlabelled observations are excluded from accuracy-like denominators and remain coverage concerns. Direct continuity is a local endpoint diagnostic, not final sequence correctness. Refer to the Step 5 metric definitions for precise denominators.

## Persistence and reproducibility

SQLite preserves trial history. Re-running the same command resumes the existing study up to the ten-trial budget after matching the context fingerprint. A changed search space, seed, environment or baseline context requires a separate study name/artifact directory. Failed or incomplete trials are retained and block final student evaluation until investigated; do not delete evidence and silently claim a complete search.

The sampler seed makes a fresh uninterrupted run reproducible in the same environment. SQLite preserves completed trials but this implementation does not serialize sampler RNG state; a resumed search can propose a different continuation from an uninterrupted run. Wall-clock timings also vary by machine/load. Original trials/results remain the evidence for the recorded run.

Final fit/inference timings are measured anew for both models in this stage. Summed CV fitting/inference time and study trial duration are reported separately; neither is end-to-end API latency. Local fitted artifacts are not committed. Arrange their final delivery later under the event's size constraints.

## Next stage

Use the selected tuned forest and fixed feature order for HMM/Viterbi development. Compare classifier-only and decoded predictions using permitted development trips, document emissions/transitions and handle absent candidates, gaps and disconnected roads. Freeze the decoder before final evaluator inference. No HMM, API or evaluator run is part of Step 7.
