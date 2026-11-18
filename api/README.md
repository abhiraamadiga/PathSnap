# PathSnap backend

Backend source is the installable `src/pathsnap/api/` package; private scoring is in
`src/pathsnap/evaluation/scoring.py`. This directory holds deployment orientation
rather than duplicating package code.

See [API setup, contracts and demonstration](../docs/api.md).

From the repository root after installing the bundle requirements and API extra:

```bash
python -m pathsnap.api --host 0.0.0.0 --port 8000
```

The default mode serves ten student-development trips. Reserved evaluator IDs can
be listed in evaluator mode, while inference remains disabled until the system is
frozen. Model/decoder source, weights and runtime configuration are checked against
the Step 9 bundle. Nothing is trained or tuned while serving requests.
