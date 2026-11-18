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
  $('map-empty').querySelector('strong').textContent = 'Your route will appear here';
  $('map-empty').querySelector('p').textContent = 'Open Trips to choose a trip and run reconstruction.';
  $('map-summary').textContent = 'No trip loaded · choose a trip in Trips';
  $('result-title').textContent = state.trips.length ? `Trip ${$('trip-select').value}` : 'Ready for a trip.';
  $('result-subtitle').textContent = state.trips.length ? 'Ready to reconstruct from the original GPS observations.' : 'Connect to the API to begin.';
}
function initialiseMap() {
  if (!globalThis.L) { message('The local map assets could not load. Refresh the page or check the UI installation.', 'error'); return; }
  map = L.map('map', { preferCanvas: true, zoomControl: true }).setView([20, 0], 2);
  gpsLayer = L.featureGroup().addTo(map); routeLayer = L.featureGroup().addTo(map);
  $('layer-gps').addEventListener('change', () => $('layer-gps').checked ? gpsLayer.addTo(map) : map.removeLayer(gpsLayer));
  $('layer-route').addEventListener('change', () => $('layer-route').checked ? routeLayer.addTo(map) : map.removeLayer(routeLayer));
  $('fit-button').addEventListener('click', () => { if (bounds?.isValid()) map.fitBounds(bounds.pad(.08), { maxZoom: 18 }); });
  $('basemap-select').addEventListener('change', () => {
    if (tiles) { map.removeLayer(tiles); tiles.off(); tiles = null; }
    const mode = $('basemap-select').value;
    if (mode === 'none') { $('basemap-status').textContent = 'Offline grid · no external tiles'; return; }
    const satellite = mode === 'satellite';
    const label = satellite ? 'Esri World Imagery' : 'OpenStreetMap';
    let failed = false;
    tiles = L.tileLayer(satellite
      ? 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
      : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: satellite ? 'Imagery © Esri, Vantor/Maxar, Earthstar Geographics, GIS User Community' : '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxNativeZoom: 19, maxZoom: 19,
    });
    $('basemap-status').textContent = `Loading ${label}…`;
    tiles.on('tileerror', () => { failed = true; $('basemap-status').textContent = `${label}: some tiles could not load. Check internet or use the offline grid.`; });
    tiles.on('load', () => { if (!failed) $('basemap-status').textContent = `${label} · online`; });
    tiles.addTo(map);
  });
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
  if (bounds.isValid()) { map.fitBounds(bounds.pad(.08), { maxZoom: 18 }); $('map-empty').hidden = true; }
  else { $('map-empty').hidden = false; $('map-empty').querySelector('strong').textContent = 'No drawable GPS or route points'; $('map-empty').querySelector('p').textContent = 'Inspect the observation diagnostics below.'; }
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
  $('metric-agreement-note').textContent = evaluation.status === 'ok' ? `${(evaluation.evaluated_observations || 0).toLocaleString()} scored / ${evaluation.total_observations.toLocaleString()} GPS · ${percent(evaluation.reference_coverage)} coverage` : 'Reference scoring unavailable';
  $('metric-parts').textContent = prediction.route_parts.length.toLocaleString();
  $('metric-time').textContent = `${prediction.prediction_seconds.toFixed(2)} s`;
  $('scoring-status').textContent = { ok: 'Aggregate scoring', disabled: 'Scoring disabled', reference_unavailable: 'No reference available', invalid_reference: 'Reference could not be scored' }[evaluation.status] || 'Scoring unavailable';
  $('evaluation-note').textContent = evaluation.note;
  $('eval-classifier').textContent = percent(evaluation.classifier_weak_reference_top1);
  $('eval-coverage').textContent = percent(evaluation.reference_coverage);
  $('eval-sequence').textContent = percent(evaluation.reference_sequence_edit_similarity);
  $('eval-overlap').textContent = typeof evaluation.reference_arc_set_f1 === 'number' ? evaluation.reference_arc_set_f1.toFixed(3) : '—';
  $('diagnostics').replaceChildren();
  const details = { 'Request ID': body.request_id, 'Model bundle': prediction.bundle_version, 'Partition': body.partition,
    'Scoring status': evaluation.status, 'Unscored observations': evaluation.abstained_observations ?? 'Unavailable',
    'No-candidate observations': prediction.diagnostics.no_candidate_observations ?? 'Unavailable', 'Transition resets': prediction.diagnostics.no_valid_transition_resets ?? 'Unavailable' };
  for (const [key, value] of Object.entries(details)) { const term = document.createElement('dt'), data = document.createElement('dd'); term.textContent = key; data.textContent = String(value); $('diagnostics').append(term, data); }
  $('evaluation-card').hidden = false; $('download-button').disabled = false;
  drawMap(body);
  if (evaluation.status !== 'ok') message('The route is available, but reference scoring is unavailable. No accuracy value has been invented.', 'info');
  else message('');
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
    for (const other of document.querySelectorAll('dialog[open]')) other.close();
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
