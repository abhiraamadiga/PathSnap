# PathSnap

Map matching and route reconstruction from noisy vehicle GPS observations.

## Status

Dataset loading and structural validation are implemented, with an inventory of all 90 provided development trips. EDA statistics, plots and two interactive Folium maps are also available. Model training, feature engineering, decoding, API and UI remain pending. No trained artifacts or model performance claims are included.

## Local setup

Requires Python 3.11 or newer. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The package currently has no runtime dependencies. Add dependencies as components are implemented. The original material remains in the sibling `Provided_Material` folder; datasets are not committed.

## Structure

| Folder | Responsibility |
| --- | --- |
| `configs/` | Reproducible experiment and inference configuration |
| `data/raw/`, `data/processed/` | Local source data and derived datasets (ignored) |
| `notebooks/` | Exploration and supporting experiments |
| `src/pathsnap/data/` | Parsing, validation and preprocessing |
| `src/pathsnap/features/` | Candidate generation and feature engineering |
| `src/pathsnap/models/` | Training and model comparison |
| `src/pathsnap/optimization/` | Bayesian hyperparameter search |
| `src/pathsnap/decoding/` | HMM and Viterbi reconstruction |
| `src/pathsnap/evaluation/` | Classification and route metrics; isolated reference scoring |
| `src/pathsnap/visualization/` | Folium maps and result plots |
| `api/`, `ui/` | FastAPI backend and evaluator interface |
| `scripts/`, `tests/` | Workflow commands and verification |
| `artifacts/` | Local model/preprocessing/decoder assets (ignored initially) |
| `results/experiments/`, `results/figures/`, `results/maps/` | Actual logs, plots and interactive maps |
| `docs/report/` | Consolidated technical report sources and final PDF |

## Required workflow

Explore and validate data; engineer candidates/features; compare at least five models; select using measured results; perform Bayesian tuning; compare classifier-only and HMM/Viterbi routes; export inference assets; implement API/UI; test deployment; complete report. See [requirements checklist](docs/requirements-checklist.md).

Use 80 training trips for fitting and group-aware cross-validation and 10 student-testing trips for development comparisons. The 10 reserved evaluator trips are final-evaluation-only. Never feed evaluator labels into prediction or expose them to the UI.

## Planned two-laptop deployment

Laptop 1 will host FastAPI, trained assets, road networks, HMM/Viterbi and isolated server-side scoring. Laptop 2 will run the UI, list ten evaluation trips and submit a selected trip ID over the network. It will display the returned route and metrics. Set its API URL to Laptop 1's reachable LAN address; `.env.example` documents proposed settings only.

No run commands or endpoints exist yet. Add exact startup commands and network setup when implemented. Demonstrate real requests for all ten trips and show receiving-laptop API logs.

## Submission

Deliver a public GitHub repository and one consolidated PDF report. Commit all implementation code and genuine experimental evidence. Generated model binaries are ignored during development; explicitly arrange their versioned delivery subject to repository size limits before submission. Do not commit secrets or evaluator ground truth. Every team member must understand and explain the work.

## Dataset validation

See [dataset understanding](docs/dataset-understanding.md) for file relationships, reproduction commands, validation results and limitations. The loader supports the supplied ZIP and extracted directories without third-party dependencies.

## Exploratory analysis

See [EDA findings and reproduction commands](docs/eda-findings.md) for partition summaries, data-quality diagnostics, figures and interactive maps. Install the `eda` extra to reproduce this stage.

## Phase 1 review

Install `pip install -e ".[eda,features]"` for preprocessing and EDA dependencies. See [phase-one review](docs/phase1-review.md) for feature auditing, coverage diagnostics, maps and the demonstration checklist.

## Model experiments

See [five-model experiment design](docs/model-experiments.md) and [measured results](docs/model-results.md). Install the `models` extra along with `eda,features`. All classification results measure weak geometric reference labels and require the limitations described in the report.
