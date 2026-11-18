"""Check a UI/API pair from either laptop; evaluator mode is metadata-only."""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def origin(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTP(S) origin without credentials, paths or queries')
    _ = parsed.port
    return value.rstrip('/')


def fetch(url, *, method='GET', headers=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = Request(url, data=data, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=180) as response:
            return response.status, response.headers, response.read()
    except HTTPError as error:
        with error:
            return error.code, error.headers, error.read()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(api_url, ui_url):
    api_url, ui_url = origin(api_url), origin(ui_url)
    status, _, content = fetch(ui_url + '/')
    require(status == 200 and b'id="map"' in content and b'id="metric-agreement"' in content, 'UI assets unavailable or wrong application')
    status, _, content = fetch(ui_url + '/config.json')
    require(status == 200, 'UI configuration unavailable')
    configured_api = origin(json.loads(content)['api_url'])
    require(configured_api == api_url, f'UI defaults to {configured_api}, but test targets {api_url}; restart UI with the intended --api-url')
    for asset in ['/app.js', '/client.mjs', '/styles.css', '/vendor/leaflet/leaflet.js', '/vendor/leaflet/leaflet.css']:
        status, _, content = fetch(ui_url + asset)
        require(status == 200 and bool(content), f'UI asset unavailable: {asset}')
    status, headers, content = fetch(api_url + '/readyz', headers={'Origin': ui_url})
    require(status == 200, 'API not ready')
    require(headers.get('Access-Control-Allow-Origin') == ui_url, 'API must allow the exact browser UI origin in PATHSNAP_CORS_ORIGINS')
    health = json.loads(content)
    status, _, content = fetch(api_url + '/trips', headers={'Origin': ui_url})
    require(status == 200, 'Trip registry unavailable')
    registry = json.loads(content)
    ids = registry['trip_ids']
    require(len(ids) == len(set(ids)) == 10 and all(len(i) == 8 and i.isdigit() for i in ids), 'Expected ten unique eight-digit trip IDs')
    require(registry['partition'] == health['partition'] and registry['inference_enabled'] == health['inference_enabled'], 'Readiness/registry mode mismatch')
    status, headers, _ = fetch(api_url + '/predict', method='OPTIONS', headers={'Origin': ui_url, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
    require(status == 200 and headers.get('Access-Control-Allow-Origin') == ui_url and 'POST' in headers.get('Access-Control-Allow-Methods', ''), 'Prediction CORS preflight failed')
    _, headers, _ = fetch(api_url + '/readyz', headers={'Origin': 'http://untrusted.invalid'})
    require(headers.get('Access-Control-Allow-Origin') is None, 'Unexpected origin is allowed; use an explicit origin list')
    return {'api_url': api_url, 'ui_url': ui_url, 'bundle_version': health['bundle_version'], 'partition': health['partition'],
            'trip_ids': ids, 'inference_enabled': health['inference_enabled'], 'assets_available': True,
            'ui_default_api_matches': True, 'cors_get_and_post_preflight': True, 'unexpected_origin_rejected': True,
            'predictions_requested': 0, 'evaluator_payloads_requested': False,
            'scope': 'Connectivity from the machine running this command; does not prove a second physical laptop was used'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', required=True)
    parser.add_argument('--ui-url', default='http://localhost:8501')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.api_url, args.ui_url)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Deployment check failed: {error}\n')
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
