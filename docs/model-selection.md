# Step 6: select the baseline for Bayesian tuning

## Decision

Select **Random Forest** as the untuned baseline and next Bayesian-optimisation target. The predeclared primary criterion is highest mean three-fold **trip-grouped CV candidate Macro F1**. This uses held-out training trips rather than training accuracy or student-testing performance.

Retain Histogram Gradient Boosting as the principal alternative: the score difference is small and its training/model-storage costs are substantially lower. The decision follows the declared criterion; it does not establish statistically significant superiority or an optimal accuracy/cost tradeoff.

The chosen configuration and feature order are frozen in `configs/selected_model.json`. Step 5 outputs remain unchanged. The numerical review, paired-fold differences and source SHA-256 hashes are in `results/experiments/model_selection/review.json`.

## Evidence from all five baseline experiments

| Model | CV Macro F1 mean / fold SD | Student Macro F1 | Student weak Top-1 | Student log loss |
| --- | ---: | ---: | ---: | ---: |
| Logistic Regression | 0.880862 / 0.029248 | 0.910791 | 0.877508 | 0.143143 |
| Gaussian Naive Bayes | 0.807482 / 0.005671 | 0.808200 | 0.884114 | 0.596648 |
| Decision Tree | 0.889789 / 0.029156 | 0.922675 | 0.880281 | 0.142034 |
| Random Forest | **0.894849 / 0.029644** | 0.927905 | 0.890801 | 0.099792 |
| Histogram Gradient Boosting | 0.893637 / 0.029952 | 0.926331 | 0.888925 | 0.100001 |

Student-test values are supporting development evidence, not inputs to the primary ranking. Candidate Macro F1 balances the positive/negative candidate classes better than accuracy alone; it is not identical to observation-level road selection. Top-1 and continuity remain separate diagnostics.

### Generalisation and fold stability

Training used every eligible observation: 126,824 observations and 752,315 candidate rows from 79 labelled trip groups. All 80 training trips remain in the coverage inventory; trip 00000011 provides no usable weak labels. Learned scaling in applicable models was fitted inside each fold's training pipeline. Exact fold membership is recorded in the Step 5 manifest.

Random Forest beats boosting in two of three paired folds. Its fold differences are -0.000499, +0.003578 and +0.000559, averaging +0.001213. Fold SDs around 0.03 mainly describe variation across held-out trip sets; they are not confidence intervals or an independent statistical test of model differences. Three overlapping-training CV folds do not establish significance.

The forest's mean training F1 is 0.918249 versus CV F1 0.894849 (gap about 0.0234); boosting's corresponding gap is about 0.0154. This supports investigating forest complexity/regularisation during tuning, not claiming that overfitting has been definitively diagnosed. Gaussian NB is stable across folds but has lower candidate F1 and poorer measured log loss; stability alone would not make it the preferred model.

### Probability quality, sequence behaviour and efficiency

Forest and boosting have similar student-test log loss (0.099792 vs 0.100001). This measures probabilistic loss against weak labels, not a complete calibration assessment. Gaussian NB's higher Top-1 than Logistic Regression coexists with worse Macro F1/log loss, showing why one metric is insufficient.

Forest direct continuity is 0.894355 versus boosting 0.897018. Boosting has a slight advantage on that diagnostic. Direct endpoint continuity is not final sequence accuracy: GPS sampling can skip intervening segments. Neither model has yet been tested with HMM/Viterbi.

Final baseline fitting took 70.522 seconds for the forest versus 4.122 seconds for boosting, a ratio of 17.11. Predicting probabilities for all student candidate rows took 0.237 seconds versus 0.253 seconds on the originating machine. These timings exclude input loading, candidate generation, decoding, API and network overhead. Locally serialized artifacts are approximately 30.15 MiB for the forest and 0.19 MiB for boosting; exact byte counts are in the review JSON. These are measured deployment considerations, not files added to this commit.

The forest retains 80 trees, max depth 14 and minimum leaf size 5, with random state 42 and four fitting threads. Boosting uses 100 iterations, up to 15 leaves and learning rate 0.1. The forest's probability interface, original candidate IDs and fixed feature order support later sequential decoding, but binary candidate probabilities are not automatically normalized HMM emissions. The decoder must define and validate that adaptation later.

## Limitations and next-stage contract

All scores above compare against distance-derived **weak geometric labels**. Distance-based features can reproduce that labelling heuristic, causing optimistic agreement. Abstentions, absent reference candidates, chronology/direction ambiguity and reference-route defects remain unresolved. Forest's equal-trip mean student Top-1 is 0.903963, versus pooled 0.890801; both are conditional on accepted weak labels and neither is verified physical route accuracy.

No evaluator data, reference labels or results were used for selection. No new training, Bayesian search, HMM decoding or deployment was performed in this selection step.

Step 7 should consume the selected untuned configuration, define a justified Bayesian search space/objective and use group-aware training CV. Preserve the baseline results/artifact for a like-for-like tuned/untuned comparison, retain trial records and cost, refit the chosen settings, and evaluate on the same ten student-test trips. Candidate-generation, reference-alignment and scoring definitions should stay fixed for that comparison; changing them requires a separately identified experiment.
