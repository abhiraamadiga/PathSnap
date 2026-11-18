export class APIError extends Error {
  constructor(message, { status = 0, requestId = null, cancelled = false } = {}) {
    super(message); this.name = 'APIError'; this.status = status; this.requestId = requestId; this.cancelled = cancelled;
  }
}

export function normaliseApiUrl(value) {
  let url;
  try { url = new URL(value); } catch { throw new APIError('Enter a complete API address, such as http://192.168.1.10:8000.'); }
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.username || url.password || !['', '/'].includes(url.pathname) || url.search || url.hash) {
    throw new APIError('Use only the API server address, without a path, credentials or query.');
  }
  return url.origin;
}

export function percent(value) {
  return typeof value === 'number' && Number.isFinite(value) ? new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 2 }).format(value) : '—';
}

export function rejectPrivateFields(value) {
  if (Array.isArray(value)) { value.forEach(rejectPrivateFields); return; }
  if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (['weak_reference_arc', 'reference_route', 'reference_labels', 'labels'].includes(key)) throw new APIError('The API returned private reference fields. The result was not displayed.');
      rejectPrivateFields(child);
    }
  }
}

export function validateTrips(health, trips) {
  if (health.status !== 'ready' || !['student_test', 'evaluator_test'].includes(health.partition) || trips.partition !== health.partition ||
      !Array.isArray(trips.trip_ids) || trips.trip_ids.length !== 10 || new Set(trips.trip_ids).size !== 10 || trips.trip_ids.some(id => !/^[0-9]{8}$/.test(id)) ||
      typeof trips.inference_enabled !== 'boolean' || trips.inference_enabled !== health.inference_enabled) throw new APIError('The server did not return a consistent ten-trip registry.');
  return trips;
}

export function validatePrediction(body, tripId, partition) {
  rejectPrivateFields(body);
  if (!body || body.trip_id !== tripId || body.partition !== partition || !body.request_id || body.prediction?.schema_version !== 1 ||
      !Array.isArray(body.prediction.observations) || !Array.isArray(body.prediction.route_parts) || !Array.isArray(body.gps_observations) ||
      body.gps_observations.length !== body.prediction.observations.length || !body.evaluation ||
      typeof body.prediction.bundle_version !== 'string' || !Number.isFinite(body.prediction.prediction_seconds) || body.prediction.prediction_seconds < 0 ||
      !body.prediction.diagnostics || typeof body.evaluation.note !== 'string' || !['ok', 'disabled', 'reference_unavailable', 'invalid_reference'].includes(body.evaluation.status)) throw new APIError('The API returned an incomplete or mismatched prediction.');
  const coordinate = c => Array.isArray(c) && c.length === 2 && c.every(Number.isFinite) && Math.abs(c[0]) <= 180 && Math.abs(c[1]) <= 90;
  body.gps_observations.forEach((point, i) => {
    if (body.prediction.observations[i]?.observation_id !== i || (point !== null && (!coordinate([point.longitude, point.latitude]) || point.observation_id !== i))) throw new APIError('The API returned invalid observation coordinates or IDs.');
  });
  body.prediction.route_parts.forEach(part => {
    if (!Array.isArray(part.arc_ids) || part.geometry?.type !== 'MultiLineString' || !Array.isArray(part.geometry.coordinates) || part.arc_ids.length !== part.geometry.coordinates.length ||
        part.geometry.coordinates.some(line => !Array.isArray(line) || line.length < 2 || line.some(c => !coordinate(c)))) throw new APIError('The API returned invalid route geometry.');
  });
  return body;
}

export async function requestJSON(base, path, { method = 'GET', body, signal, timeoutMs = 10000, fetchImpl = globalThis.fetch } = {}) {
  const controller = new AbortController(); let timedOut = false;
  const cancel = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', cancel, { once: true });
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  try {
    const response = await fetchImpl(normaliseApiUrl(base) + path, { method, cache: 'no-store', credentials: 'omit', signal: controller.signal,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    let data;
    try { data = await response.json(); } catch { throw new APIError('The address did not return API JSON. Check the server address.', { status: response.status }); }
    if (!response.ok) {
      const message = response.status === 503 && response.headers.get('Retry-After') ? 'The API is busy. Wait a moment, then run again.' :
        response.status === 409 ? 'Final evaluation is disabled on the API server.' : typeof data.detail === 'string' ? data.detail : 'The API rejected this request.';
      throw new APIError(message, { status: response.status, requestId: data.request_id || response.headers.get('X-Request-ID') });
    }
    return data;
  } catch (error) {
    if (timedOut) throw new APIError('The request timed out. The server may still be working; wait before retrying.');
    if (signal?.aborted) throw new APIError('Request cancelled locally. The server may still be working.', { cancelled: true });
    if (error instanceof APIError) throw error;
    throw new APIError('Cannot reach Laptop 1. Check the API address, server and allowed UI origins.');
  } finally { clearTimeout(timer); signal?.removeEventListener('abort', cancel); }
}
