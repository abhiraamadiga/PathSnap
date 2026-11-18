# Step 5: five-model experiments

## Run

From a clean PathSnap checkout with Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[eda,features,models]'
python -m unittest discover -s tests -v
python -m pathsnap.features.build --source '../Provided_Material/Student folder.zip'
python -m pathsnap.features.audit
python -m pathsnap.models.experiments --source '../Provided_Material/Student folder.zip'
python -m pathsnap.models.reporting
```

On Windows activate `.venv\Scripts\activate` and adjust the dataset path. If Step 4 outputs already exist and the audit passes, the build need not be repeated. Training may take several minutes. The configuration, environment snapshot, input fingerprints and actual measured results are included. Never reuse untrusted joblib files: regenerate artifacts with the provided source.

`--data`, `--config`, `--output` and `--artifacts` override defaults. In a separate copied config, an integer `max_training_observations_per_trip` can make a smoke run smaller; use a separate output directory and do not present that run as full-data results. The shipped full-run config uses null (no cap).

## Experimental design

- Inventory covers 80 training trips and 10 student-test trips; no evaluator data is accessed.
- Training retains all observations with accepted weak labels whose matching arc is actually in the generated candidate set. It retains every candidate for these observations, with binary target one for the accepted reference arc and zero for the other candidates.
- Unlabelled/ambiguous observations and missing-positive candidate sets are excluded from fitting; their counts remain in coverage records. Training trip 00000011 has zero usable labels, leaving 79 labelled trip groups. This is a label-availability limitation, not an invented train/test split.
- Three-fold GroupKFold splits whole trips. The exact trip assignments are retained in the manifest. No trip crosses a fold boundary.
- Each model is cloned and refitted per fold. Logistic Regression and Gaussian Naive Bayes use a StandardScaler inside their pipeline, so it fits only the corresponding fold's training data. Tree models use unscaled features. No learned transform is fitted on student-test data.
- Final baseline models are refitted on all eligible training observations, then evaluated on all ten student-test trips. A fixed 0.5 threshold defines binary candidate predictions; the maximum positive-candidate probability defines the observation's selected arc.
- Model choice uses the predeclared mean CV candidate Macro F1, never training accuracy or student-test score. Student-test comparisons are development results, not untouched final evaluation.
- The five configurations are initial baselines, not Bayesian-tuned models. Every randomised estimator uses seed 42. Parallelism is bounded to four threads.

## Models and initial objectives

| Model | Why test it | Important limitations | Objective / configuration |
| --- | --- | --- | --- |
| Logistic Regression | Fast, interpretable probability baseline for geometric and motion features | Linear log odds may miss interactions | Logistic loss; C=1; max_iter=1000; fold-local scaling |
| Gaussian Naive Bayes | Fast probabilistic baseline with a different assumption set | Correlated distance/rank/motion features violate conditional independence; probability confidence can be poor | Gaussian class likelihood; var_smoothing=1e-9; fold-local scaling |
| Decision Tree | Learns nonlinear thresholds and feature interactions | Can overfit; probabilities depend on leaf composition | Gini splits; max_depth=12; min_samples_leaf=10 |
| Random Forest | Tests variance reduction through bagged trees | Greater fitting cost and model size; probability calibration still needs assessment | 80 trees; max_depth=14; min_samples_leaf=5; Gini splits |
| HistGradientBoosting | Tests sequential boosted nonlinear decisions | More complex behaviour; probability quality and generalisation require evidence | Binary log loss; 100 iterations; 15 leaves; learning_rate=0.1; early_stopping=false |

Histogram boosting's internal early stopping is disabled to avoid a random observation-level validation holdout that would ignore trip grouping. Configuration values are also retained in machine-readable JSON.

## Metric definitions and denominators

Candidate accuracy, macro precision, macro recall, Macro F1, log loss and confusion matrices compare binary scores with **weak geometric labels**. Student candidate metrics include candidates for every accepted-label observation, even if its accepted arc is absent. They exclude abstained-label observations. Class order in confusion matrices is [not-reference, reference]. Candidate class imbalance makes accuracy alone unsuitable for model selection.

Observation Top-1 divides matches by all accepted weak-label observations; missing candidates count as incorrect, rather than being dropped. It excludes unlabelled observations. Per-trip Top-1 tables are included, alongside the pooled score, so long trips do not hide all variation.

Direct route continuity is the fraction of consecutive predicted arc pairs that stay on the same arc or share the directed endpoint. It is computed on all student observations, including those without accepted labels, but excludes absent predictions and temporal resets. It is a local diagnostic, not shortest-path connectivity or final sequence accuracy: observations can legitimately skip intervening road arcs. HMM/sequence-level evaluation is a later step.

Reported inference time measures predict_proba over all student candidate rows; it excludes loading, candidate generation, decoding and API latency. Final fit time and per-fold fit/inference times are separately logged. No artificial epoch/loss curves are generated for these estimators. The comparison graph uses measured CV F1, student Top-1/F1 and log loss.

## Outputs

`results/experiments/model_comparison/` contains:

- `manifest.json`: input hashes, seed/config, feature order, trip counts and exact fold membership.
- `cv_results.csv`: training/validation F1, validation log loss and timings for every fold/model.
- `comparison.csv` / `comparison.png`: consolidated results and four metric comparisons.
- `<model>_metrics.json`: configurations, candidate confusion matrix and sequence diagnostics.
- `<model>_per_trip.csv` and `<model>_predictions.csv`: development-trip evidence. These predictions include weak references for verification; do not serve these files to an evaluator UI.
- `selection.json`: baseline winner under the predeclared CV criterion. It is not the final tuned model.

All five fitted pipelines are saved locally under ignored `artifacts/model_comparison/`. The handoff ZIP deliberately supplies reproducible source/results instead of binaries; regenerate them locally. Final event submission still requires arranging delivery of required trained inference assets subject to repository size constraints.

## Critical limits to explain

Weak labels are derived from distance to reference geometry; distance-related features can therefore reproduce the labelling heuristic and produce optimistic scores. They do not establish verified observation-level accuracy or correct travel direction. The substantial abstention and coverage issues documented in Phase 1 still apply. Do not describe the baseline winner as a validated real-world map matcher.

Interpret fold variability and training/validation F1 gaps using actual results in `model-results.md`. No scores from evaluator trips are available or permitted in selection. The next work is to review the baseline selection and label limitations, then perform Bayesian optimisation on training-trip CV, followed by HMM/Viterbi comparison. This package does not implement those later stages.
