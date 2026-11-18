# Evaluator demonstration

The demo uses the ten trips from the supplied `evaluator_test.zip`, verified against `configs/evaluator_registry.json`. The API runs the frozen Random Forest and HMM/Viterbi bundle. It reads each reference route privately after prediction and returns aggregate metrics. The UI shows the after-HMM weak-reference Top-1 score and compares it with the Random Forest score in Results. Check coverage alongside both scores.

## Local demo

Extract the v0.1.3 release into `artifacts/releases/` on the API laptop and install the pinned requirements as described in `docs/api.md`. Run the following commands from the repository root in separate terminals.

Terminal 1 serves the evaluator archive:

```bash
source .venv/bin/activate
export PATHSNAP_BUNDLE_DIR=artifacts/releases/pathsnap-v0.1.3
export PATHSNAP_PARTITION=evaluator_test
export PATHSNAP_DATA_ARCHIVE="$HOME/Downloads/evaluator_test.zip"
export PATHSNAP_TRIP_REGISTRY=configs/evaluator_registry.json
export PATHSNAP_ENABLE_EVALUATOR_INFERENCE=true
export PATHSNAP_CORS_ORIGINS=http://127.0.0.1:8502,http://localhost:8502
export PATHSNAP_CORS_ALLOW_PRIVATE_NETWORK=true
python -m pathsnap.api --host 127.0.0.1 --port 8001
```

Terminal 2 serves the UI:

```bash
source .venv/bin/activate
python -m pathsnap.ui --host 127.0.0.1 --port 8502 --api-url http://127.0.0.1:8001
```

On Windows, run the UI directly from the checkout with PowerShell and a working Python 3.11 or newer. Replace `LAPTOP1_IP` with the address that served `/readyz` on this laptop.

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m pathsnap.ui --host 127.0.0.1 --port 8502 --api-url http://LAPTOP1_IP:8001
```

Open `http://127.0.0.1:8502` and choose a trip from Trips. For the two-laptop setup, bind the API to `0.0.0.0` on the API laptop and use its reachable LAN address in the UI command instead of `127.0.0.1`. Keep the UI open from its localhost address on the second laptop. Match the allowlist to its actual browser origin.

## Training and scoring

The retraining command tries three Random Forest settings, including the deployed control, with three whole-trip training folds. It scores candidate ranking equally across trips and counts observations with a missing correct candidate as misses. Train and validation candidate Macro F1 are recorded to show the generalization gap. The chosen setting is refitted on the eligible observations from all original training trips. The HMM configuration and scorer remain fixed for this comparison.

```bash
PYTHONPATH=src python scripts/retrain_random_forest.py \
  --source '../Provided_Material/Student folder.zip' --version v0.1.3
```

Enable the evaluator API after freezing the release. The following command saves one row per trip and both pooled and equally weighted trip averages. It requires the API test dependencies from `configs/api-test-requirements.txt`.

```bash
python scripts/check_evaluator.py --bundle-version v0.1.3 --output /tmp/pathsnap-evaluation
```

Evaluator scores describe the frozen release. Keep this archive outside training, threshold selection, and feature or decoder tuning.

## Measured release results

Grouped training validation selected the 80-tree Random Forest with maximum depth 12, minimum leaf size 12 and square-root feature sampling. Mean-trip weak-reference Top-1 was 86.40% versus 86.25% for the previous settings. Mean training and validation candidate Macro F1 were 90.97% and 89.51% for the selected settings. The 1.46 percentage point gap is a diagnostic, and its comparison with the prior 0.97 point gap shows the trade-off. Fold scores and release hashes are in `results/experiments/random_forest_retraining/`.

The frozen v0.1.3 release scored 93.27% pooled and 96.92% averaged across the ten evaluator trips after HMM. The v0.1.2 control scored 93.11% pooled and 96.85% averaged across trips. Nine trips exceeded 93% under both releases. The figures cover 12,251 of 19,674 GPS observations. Trip 00000015 scored 84.61% with 68.05% reference coverage and 19.62% route edit similarity. Both bundles were frozen before evaluator scoring. The results describe the project's weak-reference metric.
