# Step 3: exploratory data analysis

## Reproduce

From the repository root:

```bash
source .venv/bin/activate
python -m pip install -e '.[eda]'
python -m pathsnap.visualization.eda --source '../Provided_Material/Student folder.zip'
python -m unittest discover -s tests -v
```

The exact environment used is recorded in `configs/eda-environment.txt`. Outputs use all 80 training and 10 student-testing trips, separately summarised. No evaluator trips are accessed. This stage does not fit preprocessing, construct labels or train models.

## Outputs

- `results/experiments/eda/trip_statistics.csv`: exact per-trip sizes, durations, GPS displacement sums, gaps, repeated values and apparent speeds.
- `results/experiments/eda/summary.json`: per-partition min, quartiles, median, 95th percentile, max and mean; includes sampling intervals.
- `results/experiments/eda/reference_breaks.csv`: all 14 nonjoining reference pairs, arc IDs, route row and endpoint separation.
- `results/figures/trip_distributions.png`: GPS counts, duration, network size and displacement by partition; log scales expose the wide range.
- `results/figures/sampling_and_network.png`: sampling buckets and GPS count versus road-network size.
- `results/maps/student_test_00000007.html`: example with uninterrupted one-second sampling; a baseline illustration, not a claim of statistical representativeness.
- `results/maps/train_00000090.html`: largest-gap example, chosen specifically for anomaly inspection.

Open the HTML files in a browser. Maps contain all trip road arcs, GPS markers, individual reference arcs, gap endpoints and layer controls. Basemap tiles and JavaScript assets need internet access. Maps fit to GPS extent; pan/zoom to inspect the broader network. Reference labels here belong only to development trips. Predicted-route layers will be added after inference exists.

## Measured findings

| Measure | Training | Student testing |
| --- | ---: | ---: |
| GPS points per trip: min / median / max | 361 / 1,529 / 19,313 | 262 / 1,420 / 3,958 |
| Road arcs per trip: min / median / max | 649 / 19,526.5 / 307,392 | 3,577 / 13,145 / 56,027 |
| Elapsed seconds: min / median / max | 451 / 1,710.0015 / 154,030 | 265 / 1,809.5 / 4,000 |
| Largest adjacent-point apparent speed (m/s) | 180.14 | 72.88 |

Across both partitions: zero exact duplicate GPS rows and zero missing/malformed rows; 578 repeated GPS positions beyond the first occurrence within each trip; 92 duplicate node positions; 1,903 duplicate directed arc pairs; 24 self-loop arcs. Repeated positions may reflect stationary periods or coordinate rounding; they are not automatically errors. Duplicate counts are summed within trips, not across globally unique roads.

The 14 reference breaks have endpoint separations from 10.62 to 595.81 metres. None is simply a repeated arc entry. Their causes remain unresolved; endpoint separation does not establish a valid connecting route.

Step 2's inventory also establishes 7,550 timestamp gaps over one second, a maximum 153,064-second gap and networks with 1 to 421 weak components. No isolated nodes were found by endpoint incidence.

## Interpretation and limits

GPS-to-GPS distances use spherical Haversine with mean Earth radius 6,371,008.8 m. They are suitable for exploratory diagnostics, not exact road lengths. Their sum includes displacement across gaps and is not actual driven distance. Apparent speed divides adjacent GPS displacement by elapsed time; extreme values flag possible noise or jumps, not verified vehicle speed. No speed cutoff or removal rule has been selected.

Training contains larger networks and longer trips than the small student-test partition. This makes per-trip reporting and trip-aware validation important; no claim of a statistically established distribution shift is made.

Preserve all node/arc IDs: removing duplicates would change the meaning of reference arc indices. Establish observation/reference alignment before generating labels. Investigate disconnected reference pairs, GPS gaps and suspicious speeds before selecting split/reset rules. The next stage should choose a spatial representation and candidate-generation approach, quantify candidate coverage, and document label uncertainty. This stage deliberately leaves those choices open to evidence.
