import { APIError, normaliseApiUrl, percent, requestJSON, validateTrips, validatePrediction } from './client.mjs';

const $ = id => document.getElementById(id);
const state = { api: null, health: null, trips: [], enabled: false, connecting: false, predicting: false, result: null, controller: null };
let map = null, gpsLayer = null, routeLayer = null, tiles = null, bounds = null;

function message(text, kind = 'info') {
  $('message').textContent = text; $('message').className = `message ${kind}`; $('message').hidden = !text;
}
function controls() {
  $('api-url').disabled = state.connecting || state.predicting;
  $('connect-button').disabled = state.connecting || state.predicting;
  $('connect-button').textContent = state.connecting ? 'Connecting…' : 'Connect';
  $('trip-select').disabled = state.connecting || state.predicting || !state.trips.length;
  $('run-button').disabled = state.connecting || state.predicting || !state.enabled || !state.trips.length;
  $('run-label').textContent = state.predicting ? 'Reconstructing…' : 'Reconstruct route';
  $('cancel-button').hidden = !state.predicting; $('progress').hidden = !state.predicting;
  $('run-button').setAttribute('aria-busy', String(state.predicting));
}
function clearResult() {
  state.result = null; bounds = null;
  gpsLayer?.clearLayers(); routeLayer?.clearLayers();
  for (const id of ['metric-gps', 'metric-agreement', 'metric-parts', 'metric-time']) $(id).textContent = '—';
  $('metric-agreement-note').textContent = 'Run a trip to see its score';
  $('accuracy-trip').textContent = state.trips.length ? `Trip ${$('trip-select').value}` : 'Select a trip';
  $('metric-gps-note').textContent = 'Original observation count';
  $('evaluation-card').hidden = true; $('download-button').disabled = true;
  $('fit-button').disabled = true; $('layer-gps').disabled = true; $('layer-route').disabled = true;
  $('map-empty').hidden = false;
  if (map) {
    $('map-empty').querySelector('strong').textContent = 'Your route will appear here';
    $('map-empty').querySelector('p').textContent = 'Open Trips to choose a trip and run reconstruction.';
  }
  $('map-summary').textContent = 'No trip loaded · choose a trip in Trips';
  $('result-title').textContent = state.trips.length ? `Trip ${$('trip-select').value}` : 'Ready for a trip.';
  $('result-subtitle').textContent = state.trips.length ? 'Ready to reconstruct from the original GPS observations.' : 'Connect to the API to begin.';
}
const basemaps = {
  street: {
    label: 'OpenStreetMap',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  satellite: {
    label: 'Esri World Imagery',
    url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Imagery © Esri, Vantor/Maxar, Earthstar Geographics, GIS User Community',
  },
};

function setBasemap(mode) {
  const previous = tiles;
  tiles = null;
  // Leaflet uses the layer's own "remove" listener to unhook map events.
  previous?.remove();
  const provider = basemaps[mode];
  if (!provider) {
    $('basemap-status').textContent = 'Offline grid · no external tiles';
    return;
  }

  const layer = L.tileLayer(provider.url, {
    attribution: provider.attribution,
    maxNativeZoom: 19,
    maxZoom: 19,
  });
  let failed = false;
  layer.on('loading', () => {
    if (tiles !== layer) return;
    failed = false;
    $('basemap-status').textContent = `Loading ${provider.label}…`;
  });
  layer.on('tileerror', () => {
    if (tiles !== layer) return;
    failed = true;
    $('basemap-status').textContent = `${provider.label}: some tiles could not load. The route and offline grid are still available.`;
  });
  layer.on('load', () => {
    if (tiles === layer && !failed) $('basemap-status').textContent = `${provider.label} · online`;
  });
  tiles = layer;
  layer.addTo(map);
}

function fitRoute() {
  if (bounds?.isValid()) map.fitBounds(bounds.pad(.08), { maxZoom: 18, animate: false });
}

function initialiseMap() {
  if (!globalThis.L) {
    $('basemap-select').disabled = true;
    $('map-empty').querySelector('strong').textContent = 'Map could not load';
    $('map-empty').querySelector('p').textContent = 'Reload the page or check that the local Leaflet files are installed.';
    return;
  }
  map = L.map('map', { preferCanvas: true, minZoom: 1, maxZoom: 19 }).setView([20, 0], 2);
  gpsLayer = L.featureGroup().addTo(map);
  routeLayer = L.featureGroup().addTo(map);
  $('layer-gps').addEventListener('change', () => $('layer-gps').checked ? gpsLayer.addTo(map) : gpsLayer.remove());
  $('layer-route').addEventListener('change', () => $('layer-route').checked ? routeLayer.addTo(map) : routeLayer.remove());
  $('fit-button').addEventListener('click', fitRoute);
  const select = $('basemap-select');
  select.value = 'street';
  select.addEventListener('change', () => setBasemap(select.value));
  setBasemap(select.value);
}
function tooltip(text) { const element = document.createElement('span'); element.textContent = text; return element; }
function drawMap(body) {
  if (!map) return;
  gpsLayer.clearLayers(); routeLayer.clearLayers(); bounds = L.latLngBounds([]);
  let plotted = 0;
  for (const point of body.gps_observations) {
    if (!point) continue;
    const location = [point.latitude, point.longitude]; bounds.extend(location); plotted++;
    L.circleMarker(location, { radius: 2.5, color: '#2166d1', weight: 1, fillOpacity: .65 }).bindTooltip(tooltip(`GPS row ${point.observation_id} · ${point.timestamp} s`)).addTo(gpsLayer);
  }
  body.prediction.route_parts.forEach((part, index) => {
    const layer = L.geoJSON({ type: 'Feature', properties: {}, geometry: part.geometry }, { style: { color: '#7b2cbf', weight: 4, opacity: .9 } });
    layer.bindTooltip(tooltip(`Route part ${index + 1} · ${part.arc_ids.length} road segments`));
    routeLayer.addLayer(layer);
    for (const line of part.geometry.coordinates) for (const [lon, lat] of line) bounds.extend([lat, lon]);
  });
  if (bounds.isValid()) { fitRoute(); $('map-empty').hidden = true; }
  else { $('map-empty').hidden = false; $('map-empty').querySelector('strong').textContent = 'No drawable GPS or route points'; $('map-empty').querySelector('p').textContent = 'Open Results for the observation diagnostics.'; }
  $('fit-button').disabled = !bounds.isValid(); $('layer-gps').disabled = !plotted;
  $('layer-route').disabled = !body.prediction.route_parts.length;
  $('layer-gps').checked = true; $('layer-route').checked = true; gpsLayer.addTo(map); routeLayer.addTo(map);
  $('map-summary').textContent = `${plotted.toLocaleString()} GPS points · ${body.prediction.route_parts.length.toLocaleString()} separate route ${body.prediction.route_parts.length === 1 ? 'part' : 'parts'}`;
  map.invalidateSize();
}
function render(body) {
  state.result = body; const prediction = body.prediction, evaluation = body.evaluation;
  $('result-title').textContent = `Trip ${body.trip_id}`;
  $('accuracy-trip').textContent = `Trip ${body.trip_id}`;
  $('result-subtitle').textContent = `Reconstructed with ${prediction.bundle_version} · ${body.partition === 'student_test' ? 'Student-test development trip' : 'Final evaluator trip'}`;
  $('metric-gps').textContent = prediction.observations.length.toLocaleString();
  $('metric-gps-note').textContent = `${prediction.diagnostics.invalid_observations || 0} invalid observations retained`;
  $('metric-agreement').textContent = percent(evaluation.hmm_weak_reference_top1);
  $('metric-agreement-note').textContent = evaluation.status === 'ok' ? `${(evaluation.evaluated_observations || 0).toLocaleString()} scored / ${prediction.observations.length.toLocaleString()} GPS · ${percent(evaluation.reference_coverage)} coverage` : 'Reference scoring unavailable';
  $('metric-parts').textContent = prediction.route_parts.length.toLocaleString();
  $('metric-time').textContent = `${prediction.prediction_seconds.toFixed(2)} s`;
  $('scoring-status').textContent = { ok: 'Aggregate scoring', disabled: 'Scoring disabled', reference_unavailable: 'No reference available', invalid_reference: 'Reference could not be scored' }[evaluation.status] || 'Scoring unavailable';
  $('evaluation-note').textContent = evaluation.note;
  $('eval-classifier').textContent = percent(evaluation.classifier_weak_reference_top1);
  $('eval-hmm').textContent = percent(evaluation.hmm_weak_reference_top1);
  const before = evaluation.classifier_weak_reference_top1;
  const after = evaluation.hmm_weak_reference_top1;
  const delta = Number.isFinite(before) && Number.isFinite(after) ? (after - before) * 100 : null;
  $('eval-delta').textContent = delta === null ? '—' : `${new Intl.NumberFormat(undefined, {
    signDisplay: 'exceptZero', maximumFractionDigits: 2,
  }).format(delta)} pp`;
  $('eval-coverage').textContent = percent(evaluation.reference_coverage);
  $('eval-sequence').textContent = percent(evaluation.reference_sequence_edit_similarity);
  $('eval-overlap').textContent = typeof evaluation.reference_arc_set_f1 === 'number' ? evaluation.reference_arc_set_f1.toFixed(3) : '—';
  $('diagnostics').replaceChildren();
  const details = { 'Request ID': body.request_id, 'Model bundle': prediction.bundle_version, 'Partition': body.partition,
    'Scoring status': evaluation.status, 'Unscored observations': evaluation.abstained_observations ?? 'Unavailable',
    'No-candidate observations': prediction.diagnostics.no_candidate_observations ?? 'Unavailable', 'Transition resets': prediction.diagnostics.no_valid_transition_resets ?? 'Unavailable' };
  for (const [key, value] of Object.entries(details)) { const term = document.createElement('dt'), data = document.createElement('dd'); term.textContent = key; data.textContent = String(value); $('diagnostics').append(term, data); }
  $('evaluation-card').hidden = false; $('download-button').disabled = false;
  try {
    drawMap(body);
  } catch (error) {
    console.error('Route map rendering failed', error);
    message('The map could not draw this route. Scores and the result download are available in Results.', 'error');
    return;
  }
  message(evaluation.status === 'ok' ? '' : 'Reference scoring is unavailable for this trip.');
}
async function connect(event) {
  event?.preventDefault(); if (state.connecting || state.predicting) return;
  state.connecting = true; state.trips = []; state.enabled = false; clearResult(); controls(); message('');
  $('connection-pill').textContent = 'Connecting…'; $('connection-pill').className = 'pill';
  $('trip-select').replaceChildren(new Option('Connecting…', '')); $('evaluation-gate').hidden = true;
  try {
    const api = normaliseApiUrl($('api-url').value.trim());
    const health = await requestJSON(api, '/readyz'); const trips = validateTrips(health, await requestJSON(api, '/trips'));
    state.api = api; state.health = health; state.trips = trips.trip_ids; state.enabled = trips.inference_enabled;
    $('api-url').value = api; try { localStorage.setItem('pathsnap.apiBase', api); } catch { /* Storage is optional. */ }
    $('trip-select').replaceChildren(...trips.trip_ids.map(id => new Option(id, id)));
    $('connection-pill').replaceChildren(); const dot = document.createElement('i'); $('connection-pill').append(dot, document.createTextNode('Connected')); $('connection-pill').className = 'pill connected';
    $('connection-help').textContent = `Bundle ${health.bundle_version} · ${trips.trip_ids.length} trips available`;
    $('partition-note').textContent = health.partition === 'student_test' ? 'Student-test trips · development mode' : 'Reserved final-evaluator trips';
    $('mode-pill').hidden = false; $('mode-pill').textContent = health.partition === 'student_test' ? 'Development' : 'Final evaluator';
    $('mode-pill').className = `mode-pill ${health.partition === 'evaluator_test' ? 'evaluator' : ''}`;
    $('evaluation-gate').hidden = trips.inference_enabled;
    $('api-docs').hidden = false; $('api-docs').href = `${api}/docs`;
    clearResult();
    if (!state.enabled) message('The API has final evaluation disabled. You can inspect the trip list, but reconstruction is unavailable.', 'info');
  } catch (error) {
    state.api = null; state.health = null; state.trips = []; state.enabled = false;
    $('trip-select').replaceChildren(new Option('Connect to load trips', ''));
    $('connection-pill').textContent = 'Not connected'; $('connection-help').textContent = 'Check Laptop 1 and its API address.';
    $('mode-pill').hidden = true; $('api-docs').hidden = true; message(error.message, 'error');
  } finally { state.connecting = false; controls(); }
}
async function run() {
  if (!state.enabled || state.predicting || !state.trips.includes($('trip-select').value)) return;
  $('trips-drawer').close();
  const tripId = $('trip-select').value; state.predicting = true; state.controller = new AbortController(); clearResult(); message(''); controls();
  try {
    const body = await requestJSON(state.api, '/predict', { method: 'POST', body: { trip_id: tripId }, signal: state.controller.signal, timeoutMs: 180000 });
    render(validatePrediction(body, tripId, state.health.partition));
  } catch (error) { clearResult(); message(error.message + (error.requestId ? ` Request: ${error.requestId}` : ''), error.cancelled ? 'info' : 'error'); }
  finally { state.predicting = false; state.controller = null; controls(); }
}
$('connection-form').addEventListener('submit', connect);
$('trip-select').addEventListener('change', () => { clearResult(); message(''); });
$('run-button').addEventListener('click', run);
$('cancel-button').addEventListener('click', () => state.controller?.abort());
$('download-button').addEventListener('click', () => {
  if (!state.result) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(state.result, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = `pathsnap-trip-${state.result.trip_id}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
for (const trigger of document.querySelectorAll('[data-drawer]')) {
  trigger.addEventListener('click', () => {
    const drawer = $(trigger.dataset.drawer);
    drawer.showModal();
    for (const button of document.querySelectorAll('[data-drawer]')) button.setAttribute('aria-expanded', String(button.dataset.drawer === drawer.id));
  });
}
for (const drawer of document.querySelectorAll('dialog.drawer')) {
  drawer.querySelector('.close-drawer').addEventListener('click', () => drawer.close());
  drawer.addEventListener('close', () => {
    for (const button of document.querySelectorAll('[data-drawer]')) button.setAttribute('aria-expanded', 'false');
  });
  drawer.addEventListener('click', event => {
    const rect = drawer.getBoundingClientRect();
    if (event.target === drawer && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) drawer.close();
  });
}
initialiseMap();
try {
  const config = await fetch('/config.json', { cache: 'no-store' }).then(response => { if (!response.ok) throw new Error('UI configuration unavailable'); return response.json(); });
  let saved; try { saved = localStorage.getItem('pathsnap.apiBase'); } catch { /* Storage is optional. */ }
  $('api-url').value = saved || config.api_url; await connect();
} catch (error) { message(error.message || 'Could not load UI configuration.', 'error'); controls(); }
