# Step 8: measured HMM/Viterbi results

Transition beta selected: **25 metres**, using the declared five selection trips and mean-trip weak-reference Top-1. Review-trip scores were computed after selection and did not choose beta. Both subsets were used in earlier classifier work, so neither is an independent final model test.

| Subset / method | Pooled weak Top-1 | Mean-trip weak Top-1 | Direct continuity | Mean route edit similarity | Mean arc-set F1 | Route parts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| selection / classifier_only | 0.924947 | 0.929174 | 0.939814 | 0.483919 | 0.823120 | 291 |
| selection / hmm_viterbi | 0.941105 | 0.939170 | 0.976587 | 0.820277 | 0.927011 | 8 |
| review / classifier_only | 0.845745 | 0.872778 | 0.863525 | 0.322657 | 0.731960 | 688 |
| review / hmm_viterbi | 0.888652 | 0.920255 | 0.955145 | 0.675426 | 0.878989 | 10 |
| all / classifier_only | 0.888517 | 0.900976 | 0.896026 | 0.403288 | 0.777540 | 979 |
| all / hmm_viterbi | 0.916979 | 0.929712 | 0.964280 | 0.747852 | 0.903000 | 18 |

## Per-trip comparison

| Trip | Subset | Classifier weak Top-1 | HMM weak Top-1 | Change | Classifier parts | HMM parts |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 00000000 | selection | 0.961109 | 0.973178 | +0.012070 | 73 | 3 |
| 00000007 | selection | 0.905032 | 0.841721 | -0.063312 | 72 | 1 |
| 00000009 | selection | 0.885529 | 0.920086 | +0.034557 | 15 | 1 |
| 00000040 | selection | 0.904952 | 0.960863 | +0.055911 | 122 | 2 |
| 00000052 | selection | 0.989247 | 1.000000 | +0.010753 | 9 | 1 |
| 00000056 | review | 0.932610 | 0.947459 | +0.014849 | 322 | 3 |
| 00000065 | review | 0.950904 | 0.987080 | +0.036176 | 56 | 4 |
| 00000076 | review | 0.886392 | 0.980025 | +0.093633 | 53 | 1 |
| 00000077 | review | 0.736595 | 0.784102 | +0.047507 | 211 | 1 |
| 00000091 | review | 0.857391 | 0.902609 | +0.045217 | 46 | 1 |

## Interpretation and failure analysis

Pointwise weak-reference agreement, direct continuity and supplied-reference sequence diagnostics improve in aggregate. Shortest-path expansion is applied to both classifier and HMM states using the same graph/limits. Route parts remain separate at gaps or invalid transitions; no artificial straight connectors are inserted.

Trips with lower weak Top-1 after decoding: 00000007. Inspect their committed maps and prediction CSVs; the figures do not justify claiming uniform improvement. Sequential smoothing can prefer a connected route over individual weak geometric labels. The present experiment does not establish whether each disagreement is a decoder error, weak-label error or graph/reference limitation.

The HMM has 7 explicit no-valid-transition resets. Gaps and missing candidates also create boundaries. These boundaries are reported rather than hidden by claiming a single connected trajectory.

Top-1 is conditional on accepted weak geometric labels (12,262 observations in this dataset), with absent positive candidates counted as incorrect. It is not verified physical ground-truth accuracy. Sequence edit similarity compares the expanded chronological arc list with the supplied route; arc-set F1 ignores order. These use imperfect supplied references and are diagnostic, not proof of correct movement.

## Runtime evidence

Summed classifier predict_proba time across ten trips: 0.446 seconds. Transition preparation including bounded shortest-path queries: 15.136 seconds. Selected Viterbi passes: 4.263 seconds.

These timings exclude file loading, graph construction, route expansion, reference-sequence metrics and map generation; they are not API latency. Transition preparation is reused across beta candidates.

Maps are in results/maps/hmm_viterbi/. Blue: GPS, green: supplied reference, orange: classifier reconstruction, purple: HMM reconstruction. Internet is required for Folium assets and tiles.

No evaluator data was read or scored. Next: export the model/preprocessing/decoder inference assets, then implement and test the two-laptop API/UI.

## Decoder refinement (v0.1.2)

A follow-up search compared 10, 15, 20, and 35 metres with the original 25-metre setting. It selected **15 metres** by mean-trip weak-reference Top-1 on the same five selection trips. The other five development trips were checked after selection. Both groups have been used in earlier development. The reserved evaluator partition was excluded. The classifier weights and weak-label scoring procedure are the same as in v0.1.1.

| Development metric | v0.1.1 (25 m) | v0.1.2 (15 m) |
| --- | ---: | ---: |
| Pooled weak-reference Top-1, all ten trips | 91.70% | 92.42% |
| Mean-trip weak-reference Top-1, five selection trips | 93.92% | 94.38% |
| Mean-trip weak-reference Top-1, five review trips | 92.03% | 92.66% |
| Mean route edit similarity, all ten trips | 74.79% | 79.72% |
| Direct continuity, all ten trips | 96.43% | 96.96% |

Trip 00000077 rises from 78.41% to 80.62%. Trip 00000007 remains at 84.17% after decoding, down from 90.50% before HMM. Its sequence edit similarity rises from 44.16% before HMM to 96.77% afterward, and its route goes from 72 parts to one. Per-observation road IDs and the overall route sequence measure different aspects of the result. Trip 00000077 has only one candidate miss among 2,126 scored observations, so expanding the candidate search alone would have limited effect on that trip. Its reference coverage is 54.36%.

Search and release evidence are stored in `results/experiments/hmm_refinement/`.
