import test from 'node:test';
import assert from 'node:assert/strict';
import { normaliseApiUrl, percent, validateTrips, validatePrediction, requestJSON } from '../ui/client.mjs';

const ids = Array.from({ length: 10 }, (_, i) => String(i).padStart(8, '0'));
const payload = () => ({ trip_id: '00000007', partition: 'student_test', request_id: 'request', gps_observations: [{ observation_id: 0, longitude: 1, latitude: 2 }],
  prediction: { schema_version: 1, bundle_version: 'test', prediction_seconds: .1, diagnostics: {}, observations: [{ observation_id: 0 }], route_parts: [{ arc_ids: [1], geometry: { type: 'MultiLineString', coordinates: [[[1, 2], [1.1, 2.1]]] } }] }, evaluation: { status: 'ok', note: 'Weak labels' } });

test('API origin is validated without credentials or file paths', () => {
  assert.equal(normaliseApiUrl('http://127.0.0.1:8000/'), 'http://127.0.0.1:8000');
  for (const address of ['javascript:alert(1)', 'http://user:password@localhost:8000', 'http://localhost:8000/data', 'http://localhost:8000/?token=secret', 'not-an-address']) assert.throws(() => normaliseApiUrl(address));
});
test('unavailable agreement is never formatted as zero', () => {
  assert.equal(percent(null), '—'); assert.equal(percent(undefined), '—'); assert.equal(percent(NaN), '—'); assert.notEqual(percent(0), '—');
});
test('registry validates ten trips and preserves disabled evaluator mode', () => {
  const health = { status: 'ready', partition: 'evaluator_test', inference_enabled: false };
  assert.equal(validateTrips(health, { partition: 'evaluator_test', trip_ids: ids, inference_enabled: false }).inference_enabled, false);
  assert.throws(() => validateTrips(health, { partition: 'evaluator_test', trip_ids: ids.slice(1), inference_enabled: false }));
  assert.throws(() => validateTrips(health, { partition: 'student_test', trip_ids: ids, inference_enabled: false }));
});
test('prediction must match requested trip and valid map geometry', () => {
  assert.equal(validatePrediction(payload(), '00000007', 'student_test').trip_id, '00000007');
  assert.throws(() => validatePrediction(payload(), '00000009', 'student_test'));
  const missingTime = payload(); delete missingTime.prediction.prediction_seconds;
  assert.throws(() => validatePrediction(missingTime, '00000007', 'student_test'), /incomplete/);
  const invalid = payload(); invalid.prediction.route_parts[0].geometry.coordinates[0][0][1] = 100;
  assert.throws(() => validatePrediction(invalid, '00000007', 'student_test'));
});
test('private labels are rejected before rendering or download', () => {
  const invalid = payload(); invalid.prediction.observations[0].weak_reference_arc = 99;
  assert.throws(() => validatePrediction(invalid, '00000007', 'student_test'), /private reference fields/);
});
test('prediction request sends only the trip ID and never browser credentials', async () => {
  let recorded;
  const result = await requestJSON('http://localhost:8000', '/predict', { method: 'POST', body: { trip_id: '00000007' }, fetchImpl: async (url, options) => {
    recorded = { url, options }; return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  } });
  assert.deepEqual(result, { ok: true }); assert.equal(recorded.url, 'http://localhost:8000/predict');
  assert.equal(recorded.options.credentials, 'omit'); assert.equal(recorded.options.body, '{"trip_id":"00000007"}');
});
test('busy and disabled server responses remain actionable', async () => {
  for (const [status, headers, text] of [[503, { 'Retry-After': '1' }, /busy/], [409, {}, /disabled/]]) {
    await assert.rejects(requestJSON('http://localhost:8000', '/predict', { fetchImpl: async () => new Response(JSON.stringify({ detail: 'server detail', request_id: 'r1' }), { status, headers }) }), error => error.status === status && error.requestId === 'r1' && text.test(error.message));
  }
});
test('timeouts and local cancellation do not silently retry predictions', async () => {
  let calls = 0;
  const pending = async (url, { signal }) => { calls++; return await new Promise((resolve, reject) => { signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }); }); };
  await assert.rejects(requestJSON('http://localhost:8000', '/predict', { timeoutMs: 5, fetchImpl: pending }), /timed out/);
  const controller = new AbortController(); const request = requestJSON('http://localhost:8000', '/predict', { signal: controller.signal, fetchImpl: pending });
  controller.abort(); await assert.rejects(request, error => error.cancelled === true); assert.equal(calls, 2);
});
