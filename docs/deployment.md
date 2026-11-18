# Step 12: integration and two-laptop demonstration

The full-screen UI and frozen v0.1.1 API are integrated locally. All ten student-test trips reproduce the Step 8 predictions and aggregate scores: 19,160 observations. UI assets, default API address, allowed-origin GET and POST preflight, and rejection of an unexpected browser origin are verified by `scripts/verify_deployment.py`. The verifier makes metadata/asset requests only and never requests evaluator predictions.

**Physical two-laptop validation is deferred at the user's request.** A loopback check cannot establish Wi-Fi reachability. No reserved evaluator payloads or predictions were used in this step. The final report remains Step 13; do not describe the event demonstration as complete until the checklist below is performed.

## Laptop 1: model, API and private scoring

Use the source checkout with the trusted `artifacts/releases/pathsnap-v0.1.1` bundle and original dataset archive. Keep datasets, reference routes and weights on this laptop. The release requires Python 3.14 and its pinned runtime dependencies; follow `docs/api.md` for initial installation. From the repository root in Bash:

```bash
source .venv/bin/activate
python -m pip install -r artifacts/releases/pathsnap-v0.1.1/requirements.txt
python -m pip install -r configs/api-requirements.txt
python -m pip install -e .
export PATHSNAP_PARTITION=student_test
export PATHSNAP_DATA_ARCHIVE="../Provided_Material/Student folder.zip"
export PATHSNAP_TRIP_REGISTRY=configs/student_registry.json
export PATHSNAP_ENABLE_EVALUATOR_INFERENCE=false
export PATHSNAP_CORS_ORIGINS=http://localhost:8501,http://127.0.0.1:8501
python -m pathsnap.api --host 0.0.0.0 --port 8000
```

Leave this terminal visible for receiving API logs. Use a second terminal to run `hostname -I` (Linux) or `ipconfig` (Windows) and choose the Wi-Fi IPv4 address. On this machine the observed address was `10.20.204.165`; it may change, so check it again before the demonstration. Never enter `0.0.0.0` or Laptop 2's localhost as the API address.

Readiness validates bundle hashes, runtime source and dependencies before serving. A mismatch should be resolved using the matching trusted bundle/environment, not by bypassing validation.

## Laptop 2: UI only

Use a source checkout of the same local commit, transferred or fetched after the team publishes it. This step does not push any commits. No dataset ZIP, model binary or private reference file is required on Laptop 2. Python 3.11+ is sufficient for the UI. From the source checkout, replace the example IP with Laptop 1's current Wi-Fi address:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pathsnap.ui --host 127.0.0.1 --port 8501 --api-url http://10.20.204.165:8000
```

On Windows create the environment with `py -3 -m venv .venv`, activate with `.venv\Scripts\activate`, then use the same `python` commands. Open `http://localhost:8501` on Laptop 2. Local UI binding suffices because its browser calls Laptop 1 directly. In Trips, confirm the API address: an earlier address may be remembered by the browser and can be replaced with **Connect**.

From another terminal on Laptop 2, run this check (only the standard library is needed):

```bash
python scripts/verify_deployment.py --api-url http://10.20.204.165:8000 --ui-url http://localhost:8501 --report results/experiments/integration/laptop2-connectivity.json
```

The UI server's default API address must match the checked API. A successful report establishes reachability from the machine executing it; record which machine was used. If the UI is opened through a LAN URL instead of localhost, add that **exact UI origin** to Laptop 1's `PATHSNAP_CORS_ORIGINS` and restart the API.

## Demonstration checklist (pending on two devices)

- [ ] Both laptops use the same reachable network. Verify Laptop 1's `/readyz` from Laptop 2.
- [ ] Run the connectivity command on Laptop 2 and retain its genuine report.
- [ ] Open Trips, connect, inspect the ten trip IDs and select a trip.
- [ ] Reconstruct each of the ten development trips. Show matching request IDs in Results and receiving Laptop 1 logs. Capture real UI and receiving-terminal screenshots.
- [ ] Open Results: explain the accuracy denominator, weak-reference limitation, coverage, sequence similarity, road F1, runtime and route breaks.
- [ ] Open Layers: toggle GPS/route; try street or satellite if internet is available. Offline grid still draws predictions.
- [ ] Change trips: the old score and route clear. Download a public result JSON and confirm it matches the selected trip.
- [ ] Every member can explain their contribution and the RF → HMM/Viterbi → private scoring flow.

Network troubleshooting: localhost in the API field points to Laptop 2 and will fail. Connection refused generally means the server is stopped or bound only to loopback. A timeout may indicate different Wi-Fi networks, firewall rules or campus client isolation; use an approved shared hotspot/network if devices cannot reach each other. An exact-origin CORS failure requires the correct allowlist and API restart. Check existing firewall policy rather than disabling protections. Satellite tiles can fail independently of inference; switch to the offline grid.

## Final evaluator mode

Finish integration and freeze code/model/configuration first. Use the explicit evaluator configuration in `docs/api.md`; keep `PATHSNAP_ENABLE_EVALUATOR_INFERENCE=false` while listing IDs or checking connectivity. Only activate final inference at the intended final evaluation. Do not tune models, preprocessing or decoding from reserved scores. The connectivity verifier never posts `/predict`, including when evaluator inference is enabled.

## Evidence and reproduction

- `results/experiments/integration/connectivity.json`: local UI/API configuration and CORS checks.
- `results/experiments/integration/predictions.json`: ten development trips, all per-observation predictions and aggregate scores match Step 8.
- `results/experiments/integration/verification.json`: UI checks and explicit physical-test limitation.
- `results/experiments/integration/request-log.txt`: receiving API log from local verification.

```bash
node --test tests/test_ui.mjs
python -m unittest discover -s tests -v
python scripts/verify_deployment.py --api-url http://127.0.0.1:8000 --ui-url http://127.0.0.1:8501
python scripts/verify_api.py --base-url http://127.0.0.1:8000 --report results/experiments/integration/predictions.json
```

The final command is a development-only ten-trip regression check and refuses evaluator mode. Run it while no one is requesting predictions: the API intentionally permits one prediction at a time. These checks reproduce evidence, not new model experiments.
