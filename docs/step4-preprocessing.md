# Step 4: preprocessing, candidates, features and weak reference alignment

## Status and responsibility

Prepared as an uncommitted handoff for Abhinav to inspect, run, adjust where needed and explain before committing. This is assisted implementation, not evidence that a team member independently authored or experimentally validated it. Follow event disclosure rules. No model training or final observation-ground-truth reconstruction is claimed.

## Run from repository root

```bash
source .venv/bin/activate
python -m pip install -e '.[eda]'
python -m pip install -r requirements-step4.txt
python -m unittest discover -s tests -v
python -m pathsnap.features.build --source '../Provided_Material/Student folder.zip'
```

On Windows activate `.venv\Scripts\activate` and supply your own ZIP path. If needed create the environment with `python -m venv .venv` first. For a fast smoke run, append `--trip 00000007 --output data/processed/step4-smoke --summary data/processed/step4-smoke-summary`; this keeps the full-run summary intact. Both CLI paths accept `--output` and `--summary` overrides.

## Data flow and boundaries

1. Existing loader reads development partitions only. Validation rejects malformed inputs and invalid references before the CLI processes them.
2. `prepare(track, nodes, arcs, config)` receives no reference route. Node/arc row IDs remain intact, including duplicate positions/arc pairs and self-loops.
3. WGS84 longitude/latitude is projected using a per-trip azimuthal equidistant CRS anchored at the first road node. This uses metres and avoids assuming a single UTM zone across geographically different trips. It is a local planar approximation: distortion away from the origin must be assessed if applied to much wider networks. No learned transform is fitted.
4. Road segments are sampled at intervals no greater than 50 m and indexed with a KD-tree. Every point along an arc is within 25 m of a sample. Searching at radius + 25 m retrieves a superset, followed by exact planar point-to-segment distances, a 75 m cutoff and top eight ranking. Ties use original arc ID. These are baseline engineering settings, not experimentally optimised hyperparameters.
5. GPS observations are retained in original order; no interpolation, deduplication or speed-based removal. Invalid observations have empty candidates. Missing predecessors, invalid rows, nonpositive timestamps and gaps above 60 seconds reset motion features. Trips remain separate. Threshold selection needs later development-only sensitivity analysis.
6. Separate `align_reference` produces weak development labels from the nearest *unique reference arc ID*, only within 75 m and with at least a 5 m lead over the second-nearest reference arc. It abstains for ambiguous or distant matches, including direction ambiguity from coincident opposite arcs. It does not infer reference chronology, resolve repeated route occurrences, repair the 14 breaks or recover verified physical ground truth. Matching the nearest reference road can still assign a wrong label. Do not report its agreement metrics as verified ground-truth accuracy.

## Features and reasons

Each candidate retains `arc_id` and includes:

| Feature | Purpose |
| --- | --- |
| `distance_m` | GPS proximity to candidate geometry |
| `projection_fraction` | Position along the segment, clipped to endpoints |
| `arc_length_m` | Segment scale |
| `heading_difference_rad`, `heading_available` | Motion agreement with directed arc; unavailable for stationary/reset/zero-length cases |
| `speed_m_s` | Observed displacement/time, not verified vehicle speed |
| `dt_s`, `gap_reset` | Sampling context and temporal discontinuity |
| `previous_distance_m` | Previous GPS point's proximity to this candidate; current distance on reset |
| `candidate_rank` | Relative proximity ordering |

Projected motion headings use one local frame per trip. Reset or unavailable motion values use documented zero defaults and flags. Large apparent speeds remain visible, without treating them as physical truths.

## Output contract

- `data/processed/step4/<partition>/<trip_id>/observations.jsonl.gz`: one row per original observation with ID, status and zero or more candidate feature dictionaries. Contains no reference labels.
- Same directory, `weak_labels.jsonl.gz`: observation ID, accepted weak arc ID or null, reason and available distance/margin diagnostics. This file belongs only to development/training/scoring; it must never enter model features or the evaluator UI.
- `results/experiments/preprocessing/trip_summary.csv` and `summary.json`: actual coverage counts, weak-label acceptance/abstention and candidate misses, with configuration and feature list.

Only accepted weak labels can define binary candidate targets (`candidate.arc_id == weak_label.arc_id`). Never turn abstentions into all-negative observations. If the accepted arc is absent from the top-eight set, count the miss, retain it in coverage reporting, and exclude the observation from naive supervised training unless a later training method explicitly supports missing-positive cases. Never inject reference arcs into inference candidates. Group splits by trip before any learned scaling/selection; do not use IDs as numeric predictive features.

The reported miss count is **conditional on accepted weak labels**, not the true reference candidate miss rate. Missing candidates, ambiguity, geometry approximation and reference limitations remain separate concerns. Future sequence-level metrics can use the ordered reference route directly, with a justified comparison method.

## Verification

Tests cover long-segment interiors, radius and top-K, duplicate arc ID preservation, zero-length arcs, invalid observations, temporal resets, weak-label abstention and feature independence from references. Full-development-run counts are in the included summary; raw derived records are deliberately ignored by Git. Evaluator data is not used. No threshold optimisation, classification or HMM experiment is part of this step.

## Full-run evidence (all 90 development trips)

| Count | Training | Student testing |
| --- | ---: | ---: |
| GPS observations | 208,417 | 19,160 |
| Candidate feature rows | 1,241,685 | 125,519 |
| Observations without candidates | 13,608 | 0 |
| Accepted weak labels | 128,237 | 12,262 |
| Accepted weak labels missing from candidates | 1,413 | 6 |
| Ambiguous reference abstentions | 59,350 | 6,882 |
| Reference too far abstentions | 20,830 | 16 |

Training trip `00000054` accounts for 12,892 of 13,608 no-candidate observations at the 75 m radius. This is a major diagnostic requiring map-based investigation of GPS/network coverage before deciding whether a wider radius, segmentation, exclusion or another method is justified. Trip `00000011` has no accepted weak labels under the baseline ambiguity rule. Do not present this baseline as a final reliable training dataset. The implementation makes these limitations measurable instead of silently generating labels or expanding candidates with reference information.

Twelve tests passed, and the full run produced 227,577 observation records and 1,367,204 candidate feature rows. Raw derived files remain in ignored `data/processed/`.
