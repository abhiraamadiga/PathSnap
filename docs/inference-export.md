# Step 9: inference asset export

## What is exported

`pathsnap-v0.1.1.zip` contains a standalone runtime directory with:

- The selected Step 7 Random Forest weights (`model.joblib`), with exact parameters and feature order.
- Frozen candidate-generation settings and selected Step 8 HMM settings. Development-trip IDs, search grids and scores are stripped from runtime configs.
- The label-free feature, graph-routing, Viterbi and inference modules plus a launcher.
- An exact runtime dependency lock, environment metadata and per-file SHA-256 integrity manifest.
- Instructions for predicting from a trip folder containing only `.track`, `.nodes` and `.arcs`.

There is no learned scaler for this Random Forest: all ten features remain unscaled. The per-trip projection is deterministic and reconstructed from the supplied road nodes. Road-network/GPS datasets are not baked into the bundle. No reference files, weak labels, evaluator data, experiment predictions or scoring code are bundled.

Reference alignment was moved to `features/reference.py`, while inference uses `features/candidates.py`. The original `features/preprocessing.py` imports remain compatible for notebooks and training code. Existing trained estimators contain only sklearn state and require no custom training-module deserialization.

## Export from the project

With the trained Step 7 artifact available locally:

```bash
python -m pip install -e '.[inference,export]'
python -m pathsnap.inference.export --version v0.1.1
```

Outputs are an ignored directory and ZIP under `artifacts/releases/`. The exporter refuses to overwrite an existing version; use a new tag for changed code/configurations. It stages and verifies the contents before publishing the local release. This is local artifact creation, not a GitHub release or deployment.

`results/experiments/inference_export/export.json` records archive/model hashes and runtime versions. The manifest's `base_git_revision` is the parent revision used to construct the snapshot; actual runtime file hashes bind the exported code, including pending Step 9 changes. It does not falsely claim those new files were already committed in the parent revision.

## Run the extracted ZIP without the repository

The supplied artifact was built and tested with Python **3.14.4** on Linux. Its loader requires Python **3.14** and the exact recorded package versions. Use a Python 3.14 environment on the model-hosting laptop:

```bash
cd /path/to/extracted/pathsnap-v0.1.1
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_inference.py --bundle . --trip-dir /path/to/00000007 --output prediction.json
```

On Windows activate `.venv\Scripts\activate`. Compatible package wheels must exist for the target OS; the originating verification was on Linux, not a certification of other platforms. The UI laptop will call the future API and does not need to load these model binaries.

The input folder name is the trip ID and files must follow that name: `00000007.track`, `00000007.nodes`, `00000007.arcs`. Columns remain the original headerless formats. The reader deliberately never opens `.route`, even if it exists next to the inputs. GPS rows with invalid values are preserved as null predictions; invalid road geometry or fractional/out-of-range node references are errors.

Only load trusted bundles: joblib/pickle deserialization can execute code. Manifest hashes detect corruption but do not authenticate a replaced manifest. Integrity, dependency, feature-order and configuration checks occur before model deserialization. Python/package mismatches produce explicit installation errors rather than quietly loading an unverified combination.

## Prediction interface

```python
from pathsnap.inference.bundle import load_bundle
predictor = load_bundle('/path/to/pathsnap-v0.1.1')
result = predictor.predict(track, nodes, arcs)
```

There is no route/reference argument. Output schema version 1 includes:

- `bundle_version` and one observation result per original row: status, candidate count, classifier arc ID, HMM arc ID, segment ID and reset reason.
- Separate route parts, each with original arc IDs and GeoJSON MultiLineString road geometry. No straight lines bridge resets or disconnected components.
- Diagnostics for missing/invalid observations and transition resets, plus prediction runtime excluding bundle loading and file IO.

The predictor does not output accuracy, weak labels or reference routes. Later API scoring must remain separate and server-side after prediction. It must not feed references back into this interface or expose them to the UI.

## Verification

```bash
python -m unittest discover -s tests -v
python scripts/verify_inference_bundle.py \
  --bundle-zip artifacts/releases/pathsnap-v0.1.1.zip \
  --source '../Provided_Material/Student folder.zip'
```

The integration verifier extracts the trusted runtime snapshot, starts isolated Python processes (`-I`) outside the repository and creates input folders containing only the three inference file types. It requires the original development ZIP checksum and rejects the evaluator ZIP. For all ten student-development trips, it compares classifier/HMM IDs and route parts with Step 8 snapshots, preserving observation counts. No reference file is extracted or read by the predictor; historical prediction snapshots are used only by the external verifier.

`results/experiments/inference_export/verification.json` records actual outcomes. The 38-test suite covers damaged/missing bundle files, environment/feature-order mismatch, geometry validation, label-free IO, invalid GPS retention and release overwrite prevention, alongside all earlier pipeline checks.

Evaluator data remains unused. The next step is FastAPI integration: load the bundle once on Laptop 1, look up the selected trip's GPS/network data, run this interface, then perform isolated server-side reference scoring. UI and two-laptop integration follow afterward.
