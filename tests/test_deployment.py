"""Deployment checks fail on the network/configuration mistakes they diagnose."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('verify_deployment', Path(__file__).resolve().parents[1] / 'scripts/verify_deployment.py')
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


class DeploymentTests(unittest.TestCase):
    def replies(self, *, wrong_api=False, allow_origin=True, allow_untrusted=False, partition='student_test'):
        ui = 'http://localhost:8501'
        health = {'bundle_version': 'v0.1.1', 'partition': partition, 'inference_enabled': partition == 'student_test'}
        registry = {**health, 'trip_ids': [f'{i:08d}' for i in range(10)]}
        return [(200, {}, b'<div id="map"></div><strong id="metric-agreement"></strong>'),
                (200, {}, json.dumps({'api_url': 'http://wrong:8000' if wrong_api else 'http://localhost:8000'}).encode()),
                *[(200, {}, b'asset') for _ in range(5)],
                (200, {'Access-Control-Allow-Origin': ui} if allow_origin else {}, json.dumps(health).encode()),
                (200, {}, json.dumps(registry).encode()),
                (200, {'Access-Control-Allow-Origin': ui, 'Access-Control-Allow-Methods': 'POST'}, b''),
                (200, {'Access-Control-Allow-Origin': '*'} if allow_untrusted else {}, b'')]

    def test_evaluator_check_is_metadata_only(self):
        with patch.object(deployment, 'fetch', side_effect=self.replies(partition='evaluator_test')) as fetch:
            report = deployment.verify('http://localhost:8000', 'http://localhost:8501')
            self.assertEqual(report['predictions_requested'], 0)
            self.assertFalse(report['inference_enabled'])
            self.assertTrue(all(call.kwargs.get('method', 'GET') in {'GET', 'OPTIONS'} for call in fetch.call_args_list))
            self.assertFalse(any(call.kwargs.get('body') for call in fetch.call_args_list))

    def test_wrong_ui_api_and_cors_fail(self):
        for options in [{'wrong_api': True}, {'allow_origin': False}, {'allow_untrusted': True}]:
            with self.subTest(options=options), patch.object(deployment, 'fetch', side_effect=self.replies(**options)):
                with self.assertRaises(ValueError):
                    deployment.verify('http://localhost:8000', 'http://localhost:8501')

    def test_non_origin_urls_are_rejected(self):
        for url in ['https://user:secret@host', 'http://host/path', 'http://host?key=secret', 'file:///tmp/data']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                deployment.origin(url)
