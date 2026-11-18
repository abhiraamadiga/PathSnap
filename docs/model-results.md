# Measured five-model comparison

All results below come from the submitted experiment files. Scores measure agreement with weak geometric reference labels, not verified physical GPS ground truth.

Training used 126,824 eligible observations, 752,315 candidate rows and 79 labelled trip groups from the 80-trip training partition. Trip 00000011 has no usable labels. Training cap: None (null/None means all eligible observations).

Three-fold trip-grouped CV was followed by refitting each baseline on all eligible training observations and evaluation on all ten student-test trips. Fold-specific scaling is inside the relevant pipelines.

| Model | CV Macro F1 mean ± fold SD | Student Macro F1 | Weak-reference Top-1 | Log loss | Direct continuity | Final fit (s) | Predict probabilities (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| logistic_regression | 0.8809 ± 0.0292 | 0.9108 | 0.8775 | 0.1431 | 0.8911 | 1.170 | 0.015 |
| gaussian_nb | 0.8075 ± 0.0057 | 0.8082 | 0.8841 | 0.5966 | 0.8951 | 0.515 | 0.041 |
| decision_tree | 0.8898 ± 0.0292 | 0.9227 | 0.8803 | 0.1420 | 0.8728 | 8.666 | 0.011 |
| random_forest | 0.8948 ± 0.0296 | 0.9279 | 0.8908 | 0.0998 | 0.8944 | 70.522 | 0.237 |
| hist_gradient_boosting | 0.8936 ± 0.0300 | 0.9263 | 0.8889 | 0.1000 | 0.8970 | 4.122 | 0.253 |

## Baseline selection

Selected baseline: **random_forest**, using the highest mean grouped-CV candidate Macro F1 under the predeclared criterion. This is an initial model choice for review and subsequent Bayesian tuning, not a final tuned inference artifact.

Fold SD measures variation across these three folds, not a confidence interval. All timing values are measured wall time on the originating machine; final prediction timing excludes candidate generation, loading, decoding and networking.

## Per-model evidence

### logistic_regression

Mean fold-training Macro F1: 0.8820; held-out-trip CV Macro F1: 0.8809; training-minus-validation gap: 0.0012. Student-test Macro F1: 0.9108; weak-reference Top-1: 0.8775; log loss: 0.1431.

A positive training/validation gap is evidence consistent with reduced generalisation to held-out trips; its magnitude must be considered alongside fold variation. These measurements alone do not prove overfitting or underfitting. Model strengths, limitations, objectives and initial hyperparameters are documented in model-experiments.md.

### gaussian_nb

Mean fold-training Macro F1: 0.8112; held-out-trip CV Macro F1: 0.8075; training-minus-validation gap: 0.0037. Student-test Macro F1: 0.8082; weak-reference Top-1: 0.8841; log loss: 0.5966.

A positive training/validation gap is evidence consistent with reduced generalisation to held-out trips; its magnitude must be considered alongside fold variation. These measurements alone do not prove overfitting or underfitting. Model strengths, limitations, objectives and initial hyperparameters are documented in model-experiments.md.

### decision_tree

Mean fold-training Macro F1: 0.9104; held-out-trip CV Macro F1: 0.8898; training-minus-validation gap: 0.0206. Student-test Macro F1: 0.9227; weak-reference Top-1: 0.8803; log loss: 0.1420.

A positive training/validation gap is evidence consistent with reduced generalisation to held-out trips; its magnitude must be considered alongside fold variation. These measurements alone do not prove overfitting or underfitting. Model strengths, limitations, objectives and initial hyperparameters are documented in model-experiments.md.

### random_forest

Mean fold-training Macro F1: 0.9182; held-out-trip CV Macro F1: 0.8948; training-minus-validation gap: 0.0234. Student-test Macro F1: 0.9279; weak-reference Top-1: 0.8908; log loss: 0.0998.

A positive training/validation gap is evidence consistent with reduced generalisation to held-out trips; its magnitude must be considered alongside fold variation. These measurements alone do not prove overfitting or underfitting. Model strengths, limitations, objectives and initial hyperparameters are documented in model-experiments.md.

### hist_gradient_boosting

Mean fold-training Macro F1: 0.9090; held-out-trip CV Macro F1: 0.8936; training-minus-validation gap: 0.0154. Student-test Macro F1: 0.9263; weak-reference Top-1: 0.8889; log loss: 0.1000.

A positive training/validation gap is evidence consistent with reduced generalisation to held-out trips; its magnitude must be considered alongside fold variation. These measurements alone do not prove overfitting or underfitting. Model strengths, limitations, objectives and initial hyperparameters are documented in model-experiments.md.

## Selection uncertainty

The first two CV means differ by 0.0012. The ranking follows the declared criterion; this small difference is not evidence of statistical superiority. Compare inference/fitting costs and probability quality before finalising the Bayesian-tuning target.

## Coverage and interpretation

Student testing includes 19,160 observations. Top-1 is evaluated on 12,262 accepted weak labels, including 6 candidate misses as incorrect. There are 0 no-candidate observations in this partition. Candidate metrics exclude abstained labels; direct continuity uses available predictions independently of label acceptance.

Distance-derived weak labels and distance-related features can reproduce the same heuristic, yielding optimistic agreement. Neither high F1 nor high Top-1 resolves direction ambiguity, omitted labels or reference-route defects. Review the per-trip tables and Phase 1 coverage maps before drawing route-quality conclusions.

## Next work

Review and justify the selected baseline, retain all five experiments, then perform Bayesian hyperparameter optimisation using trip-grouped training CV and compare tuned/untuned performance on the same student-test partition. HMM/Viterbi and classifier-only versus decoded sequence evaluation follow later. No evaluator data was used.
