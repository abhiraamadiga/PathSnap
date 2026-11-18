# Step 8: HMM/Viterbi route reconstruction

## Reproduce

Use the repository's Python environment, original development ZIP, Step 4 candidate files and locally regenerated Step 7 tuned forest:

```bash
python -m pip install -e '.[eda,features,models,optimization]'
python -m unittest discover -s tests -v
python -m pathsnap.decoding.experiments --source '../Provided_Material/Student folder.zip'
python -m pathsnap.decoding.reporting
```

If required, regenerate Step 4 features and Step 7 artifacts using their documented commands first. Only load model binaries produced by this project. Input fingerprints must match the original baseline; `evaluator_test.zip` is rejected. No evaluator observations, networks or reference labels enter this experiment.

`configs/hmm_search.json` declares the search and fixed engineering parameters. `configs/hmm.json` freezes the selected beta and settings for later inference. Comparison evidence is in `results/experiments/hmm_viterbi/`; all ten interactive maps are in `results/maps/hmm_viterbi/`. See `hmm-results.md` for actual outcomes and failures.

## Hidden states and emissions

At each GPS observation, hidden states are the original directed road-arc IDs in its candidate list. Their projection fractions locate the snapped point along each arc. No arc IDs are renumbered and no reference arc is injected into candidates.

The selected tuned Random Forest produces a binary positive-class score for each candidate. Clip scores at epsilon 1e-9 and normalize over that observation's candidates. These are emission proxies from a discriminative classifier, not calibrated physical GPS likelihoods or HMM posterior probabilities. A uniform initial prior applies at each independent sequence boundary.

## Directed graph and transitions

Project coordinates into the same local metre CRS as preprocessing. Routing uses directed node connectivity, with metric arc lengths. Duplicate endpoint pairs use their minimum length for shortest-path calculations rather than CSR's default sum; original candidate IDs remain distinct. Equal-weight connector edges use the lowest original ID. No coordinate-based merging or geometric bridge is invented between disconnected node IDs.

For previous arc a at fraction f and next arc b at fraction g, the general route distance is:

```text
(1-f) * length(a) + shortest_path(end(a), start(b)) + g * length(b)
```

On the same arc, forward movement uses `(g-f)*length(a)`. Up to 20 m of backwards projection is treated as stationary GPS jitter with distance zero. Larger backwards movement requires a valid directed road loop; otherwise the transition is invalid.

Shortest-path lookup uses bounded SciPy Dijkstra, with an LRU cache of 128 source nodes per trip. Global route distance is capped at 5,000 m. A step is additionally invalid if its network distance exceeds `80 m/s * dt + 150 m`; the 150 m allowance corresponds to two 75 m candidate radii. These generous engineering bounds do not certify a vehicle's physical speed.

For valid candidate pairs:

```text
raw_transition(j,k) = -abs(network_distance(j,k) - GPS_displacement) / beta
log_transition(j,k) = raw_transition(j,k) - logsumexp(valid destinations from j)
```

Invalid pairs have log probability negative infinity; rows without destinations remain invalid. Transitions are candidate-conditioned and time-varying. Beta controls distance-consistency strength. Search values 25, 50 and 100 m span scales around the existing candidate radius; they use development data only.

## Viterbi recurrence and failure handling

```text
delta_0(k) = log_uniform_prior(k) + log_emission_0(k)
delta_t(k) = log_emission_t(k) + max_j(delta_(t-1)(j) + log_transition_t(j,k))
```

Store maximizing predecessors and backtrack each completed segment. This is global sequence decoding within each segment, not greedy observation selection.

- No candidates: return null at that original observation ID and terminate the segment.
- Missing predecessor, nonpositive timestamp interval or gap above 60 s: begin a new segment.
- No finite transition from any reachable state: close the previous segment and restart with the current emissions, recording `no_valid_transition`.
- Nonfinite/out-of-range classifier scores and inconsistent candidate IDs are errors; never quietly score them as genuine probabilities.

Every relevant observation with candidates receives a selected original arc ID. Missing observations and boundaries remain explicit. Malformed GPS observations from preprocessing have no candidates; they are preserved with null output.

## Reconstructing route parts

Expand each valid transition with its directed shortest-path connector. Keep separate route parts at gaps, missing observations and invalid transitions. Draw each road arc rather than drawing straight lines across boundaries. Apply the same expansion and routing limits to classifier-only states for a fair comparison. Every reconstructed part is checked for directed endpoint continuity.

Distinct duplicate arc IDs can still cause identity ambiguity: geometric equivalence is not independently resolved. All candidate-to-arc mapping is preserved. The supplied reference route may also contain breaks, and no automatic reference repair is performed.

## Parameter selection and review

The first five declared student-development IDs (00, 07, 09, 40, 52) choose beta by highest **mean-trip weak-reference Top-1**. List order breaks exact beta ties. The configuration is written before running the other five trips (56, 65, 76, 77, 91). Their scores do not influence parameter selection.

The split is fixed in the config before computing results. Both subsets were already used during prior classifier development; the review subset is a decoder-development review, not an independent final model test. No repeated adjustment of beta or other settings based on review scores was performed.

## Metrics and honest denominators

- Pointwise weak Top-1: accepted weak-label matches divided by all accepted labels; missing candidates count as incorrect. Pooled and mean-trip values are both reported.
- Direct continuity: consecutive state IDs stay on the same arc or share directed endpoints. Denominator includes invalid-transition reset boundaries when GPS time remains valid, preventing resets from silently hiding discontinuities. Missing predictions and temporal gaps are excluded for both methods equally.
- Arc-set precision/recall/F1: compare expanded predicted arc sets with supplied reference sets. This ignores traversal order.
- Normalized edit similarity: `1 - Levenshtein(predicted expanded arc sequence, reference sequence) / max(lengths)`. Flatten parts chronologically for this diagnostic without adding connector edges across breaks. It penalizes order/missing/extra arcs but is affected by sampling and imperfect references.
- Route-part counts and no-valid-transition resets: expose fragmentation separately from within-part connectivity, which is enforced by construction.

Sequence metrics use all predicted route parts, including observations without accepted weak labels. Pointwise metrics remain conditional on accepted weak labels. None is verified physical ground truth. Cases where HMM does not help must remain visible in tables, maps and analysis.

No model fitting, new Bayesian search, API or evaluator inference is performed in Step 8. The selected forest and preprocessing remain fixed. Next: export inference assets (Step 9), then FastAPI, UI and two-laptop integration.
