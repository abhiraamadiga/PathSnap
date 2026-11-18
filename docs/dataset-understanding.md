# Dataset loading and validation

This is a structural inventory, before feature engineering or EDA. Results were generated from the supplied `Student folder.zip`, without extracting or changing the original material. Only training and student-test partitions are loaded.

## Reproduce

From the repository root (Python 3.11+, no third-party dependencies required):

```bash
PYTHONPATH=src python3 -m pathsnap.data.validation --source '../Provided_Material/Student folder.zip'
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

`--source` also accepts an extracted directory containing `train/` and `student_test/`, or their parent containing `Student folder/`. `--output` changes the inventory destination. The command checks the expected partition counts and rejects overlapping trip IDs. Detailed per-trip counts, file sizes, bounds, connectivity and issues are in `results/experiments/dataset_inventory/` as JSON and CSV. Quality issues are recorded for inspection rather than silently removed.

## How the files relate

- `.track`: three headerless whitespace-separated floating-point columns: longitude, latitude, timestamp in seconds. Each row is an observed GPS point.
- `.nodes`: two floating-point coordinate columns. Its zero-based row number is a node ID.
- `.arcs`: two integer columns: source and destination node IDs. Its zero-based row number is an arc ID. These define directed road segments.
- `.route`: one integer arc ID per row, giving the chronological reference traversal.

Identifiers are local to each trip. Reference-route rows and GPS observations have different counts and must not be joined by row number. Establishing observation-level reference alignment is a separate, unresolved implementation step. A reference route may include limitations and must not be assumed error-free.

The loader preserves malformed rows as placeholders rather than deleting them and shifting node/arc IDs. It reports missing/empty files and invalid fields; the validator checks finite/plausible coordinates, timestamp ordering, node and arc references, gaps and reference adjacency. Network components are **weak components**, ignoring direction; they do not establish directed routing reachability. Geometric distances and projection choices are deferred to feature engineering.

## Actual inventory

- 80 training trips and 10 student-testing trips; 360 expected files total.
- 227,577 GPS observations; 2,024,174 node rows; 4,061,945 arc rows; 34,813 reference arc entries. These totals sum per-trip networks and do not count globally unique roads.
- No missing/empty files, malformed rows, invalid/nonfinite coordinates, invalid node/arc references or nonincreasing timestamps were detected.
- 96.68% of adjacent timestamp steps are exactly one second. There are 7,550 steps longer than one second.
- Largest gap: 153,064 seconds (about 42.52 hours), training trip `00000090`. Do not assume every file is one uninterrupted journey.
- 14 consecutive reference-arc pairs do not join directly under the supplied arc direction. Inspect these before deciding whether they reflect omitted connectors, direction conventions or reference errors.
- Networks have between 1 and 421 weak components; no isolated nodes under the endpoint-incidence definition.
- 68 trips have at least one gap or reference-adjacency warning. A warning is not a declaration that the trip is unusable.

## Decisions for the next stage

Keep raw observations and IDs intact. Inspect gap distributions and affected reference sequences with maps before choosing cleaning, splitting or reference-alignment rules. Candidate generation must account for disconnected components and report when a reference segment is missing. Use appropriate projected/geodesic distances; never interpret degrees as metres. Fit learned transformations only on training trips and use group-aware CV. Evaluator data remains excluded.
