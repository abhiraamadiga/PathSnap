# Evaluator ZIP: review and plan update

The teacher's message supplies the test file for the next phase; it does not specify new model requirements or relax the original evaluation-isolation rules.

## Archive inspection

The supplied `evaluator_test.zip` has 40 files under `evaluator_test/`: ten trip folders, each with `.track`, `.nodes`, `.arcs` and `.route`. No additional README, PDF or text instructions are present. Its ten trip IDs are disjoint from the 90 development-trip IDs, giving 100 distinct trips in total. Inspection used member names, sizes and counts; no GPS/network payloads or reference labels were decoded. The archive checksum and trip-ID registry are recorded in `configs/evaluator_registry.json`. Hashing identifies the compressed archive without interpreting its contents.

## Plan changes

- The reserved evaluator partition is now available. Retain it locally outside version control for final evaluation; its presence does not make it development data.
- Keep the existing Step 7 Bayesian-tuning plan, training inputs, fold assignments and metric definitions. The evaluator archive does not inform the search space or objective.
- Step 8 remains HMM/Viterbi development and classifier-only comparison using training/student-testing data.
- Later backend integration should use the registry's ten IDs for evaluator selection. Prediction may receive only GPS/road inputs; `.route` is isolated server-side reference information for scoring after prediction.
- UI receives predicted routes and aggregate evaluation results, never reference labels or reference files. Final accuracy still needs a justified observation/reference association; the current weak geometric labels are not verified observation ground truth.
- Freeze model, preprocessing, thresholds and decoder choices before evaluator inference. Do not use evaluator results to revise them or hardcode routes.

No evaluator accuracy, candidate coverage or model inference was computed during this inspection. The registry is a deployment contract for later work; API/UI loading is not implemented by this change.
