# Step 10: FastAPI backend

## Install and start on Laptop 1

Use the Python 3.14 environment matching the inference bundle. If needed, extract the trusted inference ZIP into `artifacts/releases/` so `pathsnap-v0.1.2/manifest.json` and `model.joblib` exist. From the repository root:

```bash
python -m pip install -r artifacts/releases/pathsnap-v0.1.2/requirements.txt
python -m pip install -r configs/api-requirements.txt
python -m pip install -e '.[api]'
cp .env.example .env
set -a
source .env
set +a
python -m pathsnap.api
```

The API reads process environment variables; it does not automatically load `.env`. The Bash commands above load it explicitly. On other shells, set equivalent variables directly. Do not commit `.env` or credentials.

Default binding is `0.0.0.0:8000` for the planned LAN demonstration. For local testing use `python -m pathsnap.api --host 127.0.0.1 --port 8000`. One server worker loads the bundle once at startup. Dataset, model, dependency or runtime-source mismatch fails startup rather than serving unverified predictions.

Open `http://127.0.0.1:8000/docs` for the interactive API schema. Laptop 2 uses Laptop 1's reachable LAN address instead of localhost. Configure `PATHSNAP_CORS_ORIGINS` with the actual browser UI origin if it makes direct cross-origin requests. This is a local/LAN demonstration backend without authentication; internet deployment is outside this step.

## Public endpoints

| Endpoint | Behaviour |
| --- | --- |
| `GET /healthz` | Process health, loaded bundle version, partition and mode flags |
| `GET /readyz` | Readiness after successful bundle/dataset startup validation |
| `GET /trips` | Ten configured trip IDs and whether inference is enabled; metadata only |
| `POST /predict` | Accepts exactly `{ "trip_id": "00000007" }`; runs full prediction, then private reference scoring |

Successful prediction response contains request/trip IDs, partition, original GPS observations, classifier/HMM arc IDs, segmented GeoJSON route geometry, diagnostics and aggregate evaluation results. It never contains reference routes, per-observation labels or scoring files. Response schemas filter unexpected internal fields.

The API does not accept client-provided coordinates, labels, paths, models, thresholds or reference data. IDs must match the configured registry; no arbitrary server file access is offered.

## Prediction and scoring boundary

1. Validate the trip ID and mode, then acquire the single prediction slot.
2. Read only `.track`, `.nodes` and `.arcs` from the server-owned archive. Original row IDs remain intact; no ZIP members are extracted to paths supplied by a client.
3. Invoke the frozen Step 9 `predict(track, nodes, arcs)` interface. Verify installed inference source against the bundle snapshot at startup.
4. Only after prediction completes, read `.route` privately if scoring is enabled.
5. Calculate aggregate weak pointwise agreement and reference-sequence diagnostics. Return only those aggregates.

Pointwise fields are explicitly `hmm_weak_reference_top1` and `classifier_weak_reference_top1`. They use the existing nearest-reference alignment with abstention; they are **not independently verified per-GPS accuracy**. `reference_coverage`, evaluated/abstained counts and a note make the denominator explicit. Sequence edit similarity and arc-set F1 compare with the supplied chronological route. No scoring result changes the prediction or tunes the model.

A missing or invalid reference yields `reference_unavailable` or `invalid_reference` with null scores, while preserving the prediction. It never fabricates zero accuracy. With `PATHSNAP_REFERENCE_SCORING=false`, scoring is marked disabled and neither reference files nor reference configuration are read. Invalid prediction inputs produce a generic service error and details stay in server logs.

## Development and final-evaluator modes

Default mode is `student_test`, using the original development ZIP and `configs/student_registry.json`. The live integration test uses all ten development trips. Registry/archive checksums, required input member names and duplicate ZIP entries are checked at startup. Archive changes after startup require a service restart.

For **metadata-only final mode**, configure all relevant variables together:

```bash
export PATHSNAP_PARTITION=evaluator_test
export PATHSNAP_DATA_ARCHIVE=/path/to/evaluator_test.zip
export PATHSNAP_TRIP_REGISTRY=configs/evaluator_registry.json
export PATHSNAP_ENABLE_EVALUATOR_INFERENCE=false
python -m pathsnap.api
```

`GET /trips` then lists the ten reserved IDs, but `/predict` returns 409 before any payload is read. This allows interface integration without opening held-out trips. Only after the model, preprocessing, decoder and complete system are frozen should final evaluation set `PATHSNAP_ENABLE_EVALUATOR_INFERENCE=true` and restart the server. Do not use resulting evaluator scores to tune anything. No evaluator inference was run during Step 10.

## Error behaviour and logs

- 422: malformed/extra request fields; rejected before inference.
- 404: valid-format ID absent from the active registry.
- 409: final-evaluator inference intentionally disabled.
- 503 with `Retry-After: 1`: another prediction is running; readiness remains responsive.
- 503: dataset/prediction error, with generic public detail and private server traceback.

Every request gets `X-Request-ID`; successful bodies include the same ID. Receiving-laptop logs include method/path/status/duration, inference start/completion and scoring start. They do not log raw payloads or reference arrays. These real request logs are the evidence to show evaluators; there are no hardcoded routes or cached prediction responses.

## Demonstration

```bash
curl --fail http://127.0.0.1:8000/readyz
curl --fail http://127.0.0.1:8000/trips
curl --fail http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  --data '{"trip_id":"00000007"}' \
  --output data/processed/api-demo.json
```

Keep the receiving server terminal visible. The saved JSON contains public prediction/evaluation output and can be inspected without flooding the terminal with all route coordinates. Do not commit generated response files under `data/processed/`.

## Verification

```bash
python -m pip install -r configs/api-test-requirements.txt
python -m pip install -e '.[api-test]'
python -m unittest discover -s tests -v
# Run the baseline check against an API started with the v0.1.1 bundle.
python scripts/verify_api.py --base-url http://127.0.0.1:8000
```

The 49-test suite covers label filtering, prediction-before-scoring order, a single loaded model, real repeated pipeline invocation, input/path rejection, busy/failure lock release, missing references, explicit CORS and metadata-only evaluator gating using synthetic fixtures.

The live verifier refuses evaluator mode. On a real Uvicorn loopback server it exercised all ten development IDs and compared all 19,160 predictions plus aggregate scores with Step 8. Evidence is in `results/experiments/api/verification.json` and receiving-server `request-log.txt`. The temporary test server was stopped afterward. A physical two-laptop connection has not yet been verified; UI implementation and full integration remain Steps 11–12.
