# PathSnap evaluator interface

A dataset-free static UI served on Laptop 2. From the repository root:

```bash
python -m pip install -e .
python -m pathsnap.ui --api-url http://LAPTOP1-LAN-IP:8000
```

Open `http://localhost:8501`. Start the FastAPI backend separately on Laptop 1.
The UI requests trip IDs, predictions and aggregate scores through HTTP; it never
opens raw datasets, reference files or weights.

See [UI setup and verification](../docs/ui.md). Static assets are in this directory;
the standard-library serving code is `src/pathsnap/ui/`. Leaflet's original BSD
license and npm integrity metadata are preserved under `vendor/leaflet/`.
