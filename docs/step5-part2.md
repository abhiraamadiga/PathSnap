# Step 5 Part 2: restore missing handoff files

Amrutha's Step 5 implementation was merged through PR #3. This follow-up restores
16 files present in the original local handoff but absent from that merge. The
already-uploaded handoff files matched their local source copies byte for byte.
No training or model-selection logic is changed and no experiments are rerun.

Restored files:

- `requirements-step4.txt`
- `results/experiments/model_comparison/comparison.csv`
- `results/experiments/model_comparison/comparison.png`
- `results/experiments/model_comparison/cv_results.csv`
- `results/experiments/model_comparison/decision_tree_metrics.json`
- `results/experiments/model_comparison/decision_tree_predictions.csv`
- `results/experiments/model_comparison/hist_gradient_boosting_metrics.json`
- `results/experiments/model_comparison/hist_gradient_boosting_per_trip.csv`
- `results/experiments/model_comparison/hist_gradient_boosting_predictions.csv`
- `results/experiments/model_comparison/logistic_regression_metrics.json`
- `results/experiments/model_comparison/logistic_regression_per_trip.csv`
- `results/experiments/model_comparison/logistic_regression_predictions.csv`
- `results/experiments/model_comparison/manifest.json`
- `results/experiments/model_comparison/random_forest_metrics.json`
- `results/experiments/model_comparison/random_forest_per_trip.csv`
- `results/experiments/model_comparison/random_forest_predictions.csv`

The results are from the previously recorded full eligible-training comparison:
five models, three trip-grouped folds, 126,824 training observations and 79 labelled
trip groups. All 80 training trip folders remain in the coverage manifest. Scores
measure weak-reference agreement, not verified per-observation GPS ground truth.
The extra requirements file repairs the older Step 4 installation instructions;
the current pyproject optional extras also provide the dependencies.
