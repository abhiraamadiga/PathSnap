# Phase 1: preprocessing and feature engineering review

Phase 1 scope follows the team's clarification: preprocessing and feature engineering before lunch. In the team's thirteen-step work breakdown, this covers Steps 1–4 (setup, validation, EDA, preprocessing/features). Model comparison is Step 5 and is not part of this handoff. The original PDF does not define this detailed phase-one checklist; this document records the team's clarified scope.

## Reproduce on a clean checkout

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[eda,features]'
python -m unittest discover -s tests -v
python -m pathsnap.features.build --source '../Provided_Material/Student folder.zip'
python -m pathsnap.features.audit
python -m pathsnap.visualization.phase1 --source '../Provided_Material/Student folder.zip'
```

On Windows activate `.venv\Scripts\activate`; replace the dataset path with its actual location. The build requires the original dataset and can take several minutes. Audit reads the generated files, not the raw ZIP. Missing files are errors; do not mix outputs from different build configurations. Keep large generated files in ignored `data/processed/`. The `features` extra and restored `requirements-step4.txt` fix the merged baseline's missing dependency-install file.

## What Anagha's changes add

- Streaming checks of observation/label ID alignment, candidate ID uniqueness, expected schemas, finite numeric features and per-trip feature moments.
- Counts of observations that have both an accepted weak label and the matching candidate; this is eligibility for later supervised experiments, not correctness of the weak label.
- Explicit separation of zero-candidate observations, abstained labels and accepted labels missing from the candidate set.
- Coverage chart and targeted diagnostic maps for training trips 00000054 and 00000011.
- A concise demonstration sequence and limitations for the team to explain.

No feature scaling, selection or model fitting is performed. Later model comparisons must fit learned transformations separately inside trip-aware training folds. Student-test and evaluator data must not fit those transformations.

## Measured feature audit

The audit examined every generated observation for 80 training and 10 student-test trips, across 1,367,204 candidate rows. All ten feature values were finite in every candidate row; schemas and observation/label alignment checks passed.

| Result | Training | Student testing |
| --- | ---: | ---: |
| Observations | 208,417 | 19,160 |
| No candidates within baseline radius | 13,608 | 0 |
| Accepted weak labels with matching candidates | 126,824 | 12,256 |
| Accepted labels absent from top-eight candidates | 1,413 | 6 |
| Invalid/nonfinite feature values | 0 | 0 |

Trip `train/00000011` has no usable weak labels. Trip `train/00000054` contributes 12,892 missing-candidate observations. The generated case-diagnostic JSON reports how many GPS points fall outside each trip's road-node bounding box. This is only a coarse network-coverage diagnostic; being inside the box does not imply proximity to a road.

Nearest-reference weak labels remain approximate and do not establish true observation-level ground truth. Radius 75 m, top eight candidates, 5 m reference ambiguity margin and 60 s reset are baseline choices, not tuned or proven optimal. The maps support investigating these assumptions; this handoff does not silently change them or remove difficult trips. These are open methodological issues to disclose, not solved by passing numeric/schema tests.

## Evidence to open during phase-one review

1. `docs/dataset-understanding.md`: explain four file types and row-based node/arc IDs; route rows are not GPS labels by row index.
2. `results/figures/trip_distributions.png` and the original Folium maps: show EDA and noisy GPS versus road geometry.
3. `configs/preprocessing.json` and `docs/step4-preprocessing.md`: explain projection, spatial candidate lookup, each feature, temporal reset and reference separation.
4. `results/phase1/coverage.png`: explain missing candidates and weak-label eligibility without calling either accuracy.
5. Open `results/phase1/train_00000054.html` and `train_00000011.html` locally in a browser. Use layer controls, pan/zoom and GPS point tooltips. Internet access is required for Folium assets and basemap tiles.
6. Show `results/experiments/feature_audit/summary.json` and the sixteen passing tests. Re-run the smoke build command in the Step 4 document if a short live processing demonstration is needed.

## Completion checklist before presenting

- [ ] Team members can explain every input, feature and assumption.
- [ ] Fresh checkout can install dependencies and reproduce processing/audit.
- [ ] All tests pass; actual logs and summaries are retained.
- [ ] Maps and figures are accessible, with partitions labelled.
- [ ] Difficult trips, weak-label limitations and coverage failures are explained honestly.
- [ ] No evaluator data or reference labels enter inference features or UI.
- [ ] Anagha reviews and reruns this assisted implementation before committing her work; disclose assistance as required.

These checks prepare the clarified phase-one scope; they do not imply that models, HMM, API, deployment or final report are complete.
