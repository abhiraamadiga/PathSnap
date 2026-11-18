"""Serve only UI assets and the public API address; no dataset/model dependencies."""
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import unquote,urlsplit


def api_address(value):
    parsed=urlsplit(value)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {'','/'} or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTP(S) API origin without credentials, paths or query')
    _=parsed.port
    return value.rstrip('/')


def handler_for(directory,api_url):
    directory=Path(directory).resolve();api_url=api_address(api_url)
    if not (directory/'index.html').is_file():raise FileNotFoundError('UI assets not found; set --directory to the project ui folder')
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(directory),**kwargs)
        def end_headers(self):
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            super().end_headers()
        def do_GET(self):
            path=unquote(urlsplit(self.path).path)
            if path=='/config.json':
                body=json.dumps({'api_url':api_url}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
            candidate=(directory/path.lstrip('/')).resolve()
            if '..' in Path(path).parts or not candidate.is_relative_to(directory):self.send_error(404);return
            if candidate.is_dir() and path!='/':self.send_error(404);return
            super().do_GET()
        def list_directory(self,path):self.send_error(404);return None
    return Handler


def serve(directory,api_url,host='0.0.0.0',port=8501):
    server=ThreadingHTTPServer((host,port),handler_for(directory,api_url))
    print(f'PathSnap UI: http://{host}:{port} | API: {api_url}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
