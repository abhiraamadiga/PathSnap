# Evaluator UI (Steps 11–12)

## Run on Laptop 2

The UI is a static browser application with a small Python standard-library server. It does not import ML packages, open dataset archives, load model weights or calculate reference scores. From a source checkout on Laptop 2 (Python 3.11+):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pathsnap.ui --api-url http://LAPTOP1-LAN-IP:8000
```

Open `http://localhost:8501`. On Windows activate `.venv\Scripts\activate`. Replace `LAPTOP1-LAN-IP` with the reachable address of the API laptop. The API address can also be edited in the Trips drawer, or configured through `PATHSNAP_API_URL`. Only that address is remembered in browser local storage, not GPS/results.

For a same-machine development preview, run the API in another terminal and use:

```bash
python -m pathsnap.api --host 127.0.0.1 --port 8000
python -m pathsnap.ui --host 127.0.0.1 --port 8501 --api-url http://127.0.0.1:8000
```

These are two long-running commands for separate terminals. `--directory` can specify another UI asset directory. Keep the source checkout: a package wheel alone does not include the top-level `ui/` assets.

The UI server serves only its asset root and a public `/config.json` containing the API address. Directory listing, path traversal and symlink escapes are rejected. It offers no prediction proxy, file upload or data/model endpoint. The browser communicates directly with FastAPI, so its exact origin must be allowed by the API's CORS configuration. Local browser origins on port 8501 are already allowed by default.

## Workflow and visible results

1. Connect to Laptop 1. The UI reads `/readyz` and `/trips`, validates a consistent ten-trip registry and displays partition/bundle information.
2. Select a trip and click **Reconstruct route**. Only `{ "trip_id": "..." }` is posted to `/predict`; there are no client labels, paths, model settings or raw-file inputs.
3. Inspect original GPS points and the HMM/Viterbi road route. Separate parts remain separate, with no artificial connectors. Toggle GPS/route layers or fit the complete trip.
4. Open Results to read weak-reference agreement with its scored-observation denominator, route parts, prediction runtime, classifier agreement, reference coverage, sequence edit similarity and arc-set F1.
5. In Results, expand request/diagnostics to correlate the request ID with the receiving API logs. Download the public result JSON if needed.

Scores are explicitly weak-reference agreement, not verified physical GPS accuracy. Unavailable scores display a dash rather than zero; evaluation notes explain the denominator and reference limitations. Reference routes and per-point labels never appear in the interface or its downloads.

Changing a trip or connection clears prior results and disables the old download. Inputs are disabled during a prediction to prevent a mismatched trip/result. There is no automatic prediction cache and no automatic retry of expensive requests. Timeouts, busy APIs and network/CORS errors give actionable messages. Cancel stops the browser wait only; the API may continue working and return busy if retried too soon.

## Development versus final evaluation

The UI takes partition and availability from the API. In student-test mode it lists the ten development IDs. In final-evaluator mode it lists the reserved ten IDs. When the API reports inference disabled, the run button is disabled and a visible message explains the state. The UI has no override to activate evaluator inference.

This metadata-only evaluator flow was checked against the real archive registry with inference disabled; no evaluator prediction was run. Final evaluator activation remains a server-side configuration decision after the complete system is frozen.

## Maps and dependencies

Leaflet 1.9.4 is vendored locally from the official npm package, with its BSD license, source integrity and per-file checksums under `ui/vendor/leaflet/`. No CDN, web font or JavaScript package download is needed to run the UI. GPS and route vector layers work without an internet basemap.

The map fills the browser viewport. A floating **Accuracy** card highlights HMM weak-reference agreement, with scored/total observations and coverage. Trips, Results and Layers are modal drawers with keyboard focus containment, Escape/close buttons and focus return. Starting a reconstruction closes Trips to reveal the map. No score appears before a prediction or when scoring is unavailable.

In **Layers → Basemap**, choose **Offline grid**, **Street · OpenStreetMap**, or **Satellite · Esri World Imagery**. Offline is the initial setting. Online providers receive viewport tile requests and require internet; no labels are sent. Tile failures show a message in Layers and leave the vector overlays usable. Imagery attribution is displayed on the map; provider details are linked in the drawer. Source: [Esri World Imagery documentation](https://doc.arcgis.com/en/data-appliance/2025/maps/world-imagery.htm); the live MapServer copyright names Esri, Vantor, Earthstar Geographics and the GIS User Community. Satellite loading was checked at the initial world view, without sending a trip viewport.

The UI uses browser-native modules, fetch, cancellation and downloads. Node is only needed to run developer tests, not on either runtime laptop. No Streamlit, frontend build chain or model dependencies are needed for the UI server.

## Verification and limits

```bash
node --test tests/test_ui.mjs
python -m unittest discover -s tests -v
```

There are eight JavaScript tests for origin validation, missing-score display, registry/prediction consistency, private-field rejection, exact request bodies, API errors, timeouts and cancellation without retries. The Python suite totals 54 tests, including UI asset serving, configuration and path isolation alongside the model/API tests; install the relevant development extras to run the full suite.

Actual Brave-browser checks covered API connection, a deliberate unreachable address, metadata-only evaluator listing with a disabled run button, loading/cancellation feedback, trip changes clearing results, GPS layer toggling and real development reconstructions. The saved screenshots show the actual UI, not a mockup. JSON download is implemented using the validated public response; its browser download-event wait timed out, so a completed download was not verified.

Step 12 browser checks also verified the full-screen accuracy card, three drawers, Escape/focus return, trip-ID/denominator display, automatic drawer dismissal, layer toggling and online satellite tiles at world view. The updated screenshots and local ten-trip integration evidence are in `results/experiments/integration/`.

This verifies local browser-to-API integration on one machine. See `docs/deployment.md` for Step 12 integration checks and exact two-laptop commands. Physical testing is deferred at the user’s request. The local development API/UI may stay running for preview; the temporary metadata-only evaluator server is stopped after verification.
