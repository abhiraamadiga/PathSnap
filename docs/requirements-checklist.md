# Requirements checklist

Source: all five PDFs in the supplied PathSnap_student_materials.zip. Unchecked items are requirements, not completed work.

## Main Guidelines
- [ ] Build the full GPS-to-road-route ML pipeline, FastAPI backend and evaluator UI.
- [ ] Deploy backend/model/decoder/scoring on Laptop 1 and UI on Laptop 2.
- [ ] Complete exploration, independent feature engineering, experiments, tuning, decoding, export, integration and report.

## Dataset Exploration
- [ ] Inventory 80 training and 10 student-test trips; reserve 10 evaluator trips for final evaluation only.
- [ ] Validate filenames, sizes, row counts/types, coordinates, missing values, timestamps/gaps, extent, network size/connectivity, isolated nodes/components and anomalies.
- [ ] Parse headerless track (longitude, latitude, seconds), nodes (longitude, latitude), arcs (from/to node IDs) and route (chronological arc IDs); IDs are zero-based row indices.
- [ ] Investigate GPS/reference alignment; route rows are not GPS labels by row position. Document reference limitations and assumptions.
- [ ] Justify projected/geodesic distances, coordinate order, candidate generation and features.
- [ ] Keep trips separate across partitions and CV folds; fit learned preprocessing on training data only.
- [ ] Retain inventory, summary statistics, trajectory/network plots, Folium maps and quality decisions; identify partitions used.

## Models and Training Guidelines
- [ ] Train at least five distinct models; record families, configurations, seeds, logs and practical training/inference times.
- [ ] Compare training/CV and student-test performance; explain primary selection metric and technical rationale beyond training accuracy.
- [ ] Report applicable accuracy, precision, recall, Macro F1, log loss, Top-1 accuracy, candidate miss rate, continuity and sequence performance; explain N/A metrics. Confusion matrices are optional report diagnostics.
- [ ] Explain probability adaptation for models needing it; do not treat unmapped cluster IDs as labels.
- [ ] Run Bayesian search with justified space/objective and group-aware training CV; retain trials, best settings and cost; refit and compare tuned/untuned on identical partitions and metrics.
- [ ] Explain HMM states, emissions, transitions and Viterbi recurrence; preserve candidate/segment mapping.
- [ ] Handle missing candidates, disconnected/invalid transitions and GPS gaps; predict segments for relevant observations.
- [ ] Compare classifier-only and decoded routes using pointwise/sequence metrics and continuity, including failures; tune decoder only on development data.
- [ ] Export model, preprocessing, decoder configuration and necessary inference assets.
- [ ] UI lists all ten reserved trips and sends trip IDs to real API inference; backend calculates accuracy with isolated references.
- [ ] Keep evaluator labels out of model/UI; show receiving-laptop API logs; no hardcoding or API bypass.

## Deliverables
- [ ] Prepare for first-phase evaluation before lunch; exact phase scope is unspecified.
- [ ] Submit exactly a public GitHub repository and one consolidated PDF report.
- [ ] Commit all processing/features/training/evaluation/tuning/decoder/API/UI/deployment/map code, dependencies, configurations, logs and relevant CSV/results.
- [ ] Include saved weights and inference assets subject to size constraints; provide clear installation, execution and deployment instructions; exclude secrets.
- [ ] Report EDA, preprocessing, observed patterns, feature justification, missing values and GPS/network plots, with dataset partitions identified.
- [ ] Document EVERY tried model: suitability, strengths/limitations, initial hyperparameters, loss/objective, student-test results and over/underfitting evidence.
- [ ] Provide comparison table: family/configuration, CV Macro F1, Top-1, continuity, student-test Macro F1, log loss and inference time.
- [ ] Plot CV Macro F1, student-test Top-1/Macro F1 and applicable log loss comparisons; use genuine epoch curves only for models producing histories.
- [ ] Report Bayesian space/distributions, objective, trial count, best settings and tuned/untuned CV F1, test Top-1/F1, log loss and inference time.
- [ ] Report HMM implementation, edge cases, improvements and cases where decoding did not help.
- [ ] Mandatory actual Folium maps: original GPS, network geometry, reference where available and prediction; distinct colours/markers, legend/labels, suitable extent/zoom and appropriate layer controls.
- [ ] Include representative map screenshot/export in PDF and map-generation code plus HTML or regeneration support in GitHub.
- [ ] Include working UI and successful API-response screenshots from receiving laptop terminal.
- [ ] Ensure report results are reproducible from repository and submitted code matches demo.

## Assessment and Plagiarism Policy
- [ ] Independently develop, train and evaluate; do not share code, weights, configurations, derived datasets or results across teams.
- [ ] Keep evaluator data untouched during development; no label leakage, evaluation-driven tuning or manual prediction alteration.
- [ ] Retain authentic evidence; no fabricated metrics, plots, execution results, citations or implementation claims.
- [ ] AI assistance must not substitute for experiments, understanding or independent analysis; disclose it as event policy requires.
- [ ] Every member can explain and reproduce data processing, features, comparisons, tuning, decoding, API/UI and conclusions.
- [ ] Expect comparison of code/history, architectures, weights, configurations, results and reports; missing components affect assessment even with high accuracy.
