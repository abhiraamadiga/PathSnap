# PathSnap

Map matching and route reconstruction from noisy vehicle GPS observations.

## Status

Dataset validation, EDA, preprocessing, candidate generation, feature auditing and five-model experiments are implemented. Random Forest is selected as the untuned baseline using trip-grouped CV; a ten-trial TPE search and matched untuned/tuned development comparison are complete. Metrics measure weak-reference agreement, not verified GPS ground truth. HMM/Viterbi reconstruction and development comparisons are implemented. Inference-asset export and FastAPI serving with separate server-side aggregate scoring are implemented. The evaluator UI has a full-screen map, highlighted weak-reference accuracy, drawers and optional satellite imagery. Local integration passed for all ten development trips. The evaluator release scored all ten reserved trips, and the two-laptop rehearsal recorded successful LAN predictions for trips 00000017 and 00000023.

## Local setup

Requires Python 3.11 or newer. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[eda,features,models]"
```

Component dependencies are provided through the `eda`, `features` and `models` optional extras. The original material remains in the sibling `Provided_Material` folder; datasets are not committed.

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

Laptop 1 will host FastAPI, trained assets, road networks, HMM/Viterbi and isolated server-side scoring. Laptop 2 will run the UI, list ten evaluation trips and submit a selected trip ID over the network. It will display the returned route and metrics. Set its API URL to Laptop 1's reachable LAN address; `.env.example` documents settings.

API startup is documented in `docs/api.md` and UI startup in `docs/ui.md`; [Step 12 deployment guide](docs/deployment.md) provides commands, a connectivity verifier and the pending physical LAN checklist. Demonstrate real requests for all ten trips and show receiving-laptop API logs.

## Submission

Deliver a public GitHub repository and one consolidated PDF report. Commit all implementation code and genuine experimental evidence. The versioned model weights and runtime configuration are available under GitHub Releases. Do not commit secrets or evaluator ground truth. Every team member must understand and explain the work.

## Dataset validation

See [dataset understanding](docs/dataset-understanding.md) for file relationships, reproduction commands, validation results and limitations. The loader supports the supplied ZIP and extracted directories without third-party dependencies.

## Exploratory analysis

See [EDA findings and reproduction commands](docs/eda-findings.md) for partition summaries, data-quality diagnostics, figures and interactive maps. Install the `eda` extra to reproduce this stage.

## Phase 1 review

Install `pip install -e ".[eda,features]"` for preprocessing and EDA dependencies. See [phase-one review](docs/phase1-review.md) for feature auditing, coverage diagnostics, maps and the demonstration checklist.

## Model experiments

See [five-model experiment design](docs/model-experiments.md) and [measured results](docs/model-results.md). Install the `models` extra along with `eda,features`. All classification results measure weak geometric reference labels and require the limitations described in the report.

## Model selection (Step 6)

See [selection decision and tradeoffs](docs/model-selection.md). The selected untuned configuration is `configs/selected_model.json`; the numerical review and evidence hashes are in `results/experiments/model_selection/review.json`. This untuned baseline is preserved for the Step 7 comparison.

## Evaluator archive and Bayesian tuning

The reserved evaluator ZIP is available for final evaluation only; see [data-isolation plan](docs/evaluator-data-plan.md). Step 7 uses training-trip CV and freezes parameters before student-test evaluation. Install the `optimization` extra and follow [Bayesian optimisation](docs/bayesian-optimization.md); measured results are in [Bayesian results](docs/bayesian-results.md).

## HMM/Viterbi reconstruction (Step 8)

See [decoder method and reproduction](docs/hmm-viterbi.md) and [measured results including failures](docs/hmm-results.md). The selected runtime settings are in `configs/hmm.json`. Evaluator data remains excluded; the ten committed route maps show development trips only.

## Inference bundle

Download the [PathSnap inference bundle v0.1.3 ZIP](https://raw.githubusercontent.com/abhiraamadiga/PathSnap/main/release-assets/pathsnap-v0.1.3.zip) or open the [release notes](https://github.com/abhiraamadiga/PathSnap/releases/tag/v0.1.3). Extract the ZIP into `artifacts/releases/` on the API laptop. The ZIP includes the trained Random Forest, HMM and preprocessing settings, a manifest, and pinned runtime dependencies. Use the handout datasets locally for inference and evaluation.

Archive SHA-256: `41fe868104acda8658bef508618d00691a77a2646ce69468d4e1100ba6416a96`.

See [export, standalone prediction and verification](docs/inference-export.md). Export a versioned model/config/runtime ZIP with `python -m pathsnap.inference.export --version v0.1.2` after installing `.[inference,export]`. The verified release contains no datasets or reference labels; the supplied bundle requires Python 3.14 and its pinned dependencies.

## FastAPI backend (Step 10)

See [API setup, public contract, evaluation modes and logs](docs/api.md). Start with `python -m pathsnap.api` after installing the pinned bundle/API dependencies. Endpoints are `/healthz`, `/readyz`, `/trips` and `/predict`. Default serving uses development trips; evaluator inference remains disabled until the full system is frozen.

## Evaluator UI (Step 11)

See [UI setup, data boundaries and verification](docs/ui.md). Start Laptop 2 with `python -m pathsnap.ui --api-url http://LAPTOP1-LAN-IP:8000`, then open port 8501 in its browser. Trip lists, predictions and aggregate evaluation results come from the API; no model or dataset is loaded by the UI.

## Integration and deployment (Step 12)

See [local verification and two-laptop instructions](docs/deployment.md). All ten development trips reproduce 19,160 earlier predictions and aggregate scores. Browser/UI, asset and CORS checks pass locally. See the evaluator demonstration guide below for the final release, evaluator results, and two-laptop setup.

The [decoder refinement](docs/hmm-results.md#decoder-refinement-v012) raises pooled development weak-reference agreement to 92.42%. The API defaults to inference bundle v0.1.2.

For the ten demonstration trips from the supplied evaluator archive, see [evaluator demo setup and scoring](docs/evaluator-demonstration.md). This uses a separate evaluator API configuration and a frozen model release.
