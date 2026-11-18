from http.server import ThreadingHTTPServer
from pathlib import Path
import json
import mimetypes
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen
from pathsnap.ui.server import handler_for,api_address


class UIServerTests(unittest.TestCase):
    def test_asset_root_and_public_configuration_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);assets=root/'ui';assets.mkdir();(assets/'index.html').write_text('<h1>UI fixture</h1>')
            for name in ('app.js', 'client.mjs'):
                (assets / name).write_text('export const ready = true;')
            secret=root/'private.route';secret.write_text('DO NOT EXPOSE')
            try:(assets/'symlink.route').symlink_to(secret);symlink=True
            except OSError:symlink=False
            (assets/'folder').mkdir()
            handler=handler_for(assets,'http://127.0.0.1:8000')
            handler.log_message=lambda *args:None
            server=ThreadingHTTPServer(('127.0.0.1',0),handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base+'/config.json') as response:
                    self.assertEqual(json.load(response),{'api_url':'http://127.0.0.1:8000'})
                    self.assertEqual(response.headers['Cache-Control'],'no-store')
                with urlopen(base+'/') as response:self.assertIn(b'UI fixture',response.read())
                with (patch.object(mimetypes, 'guess_type', return_value=('text/plain', None)),
                      patch.object(mimetypes, 'guess_file_type', return_value=('text/plain', None), create=True)):
                    for name in ('app.js', 'client.mjs'):
                        with urlopen(f'{base}/{name}') as response:
                            self.assertEqual(response.headers.get_content_type(), 'text/javascript')
                            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                            self.assertEqual(response.read(), b'export const ready = true;')
                paths=['/../private.route','/%2e%2e/private.route','/folder/']+(['/symlink.route'] if symlink else [])
                for path in paths:
                    with self.assertRaises(HTTPError) as error:urlopen(base+path)
                    self.assertEqual(error.exception.code,404);error.exception.close()
            finally:server.shutdown();server.server_close();thread.join()

    def test_invalid_api_addresses_fail_before_serving(self):
        for value in ['file:///tmp/private','http://user:secret@localhost','http://localhost/api?token=secret']:
            with self.assertRaises(ValueError):api_address(value)
        self.assertEqual(api_address('http://localhost:8000/'),'http://localhost:8000')
