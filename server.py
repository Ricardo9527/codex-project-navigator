"""Loopback-only service. All Codex data access remains read-only."""
import argparse
import json
import os
import mimetypes
from pathlib import Path
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from library import Library

ROOT = Path(__file__).resolve().parent


def serve(hub, port, parent_pid=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if args and str(args[1]).startswith('5'):
                super().log_message(fmt, *args)

        def respond(self, status, data, mime='application/json; charset=utf-8'):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                # The caller closed its view; the request has already completed.
                print('Client disconnected during response', flush=True)

        def allowed(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host') == expected and self.headers.get('Origin') in (None, 'http://'+expected)

        def do_GET(self):
            if not self.allowed():
                return self.respond(403, {'error': '请求来源不允许。'})
            route = urlparse(self.path).path
            if route == '/health':
                return self.respond(200, {'service': 'codex-library', 'version': 1, 'pid': os.getpid()})
            if route == '/markdown-it.js':
                return self.respond(200, (ROOT/'node_modules/markdown-it/dist/markdown-it.min.js').read_bytes(), 'text/javascript; charset=utf-8')
            files = {'/': 'index.html', '/hub.js': 'hub.js', '/hub.css': 'hub.css', '/content-page.js': 'content-page.js', '/content-page.css': 'content-page.css', '/standalone.js': 'standalone.js', '/fixture': 'fixture.html', '/native.js': 'native.js'}
            if route not in files:
                return self.respond(404, {'error': '页面不存在。'})
            path = ROOT/'web'/files[route]
            return self.respond(200, path.read_bytes(), (mimetypes.guess_type(path)[0] or 'text/plain')+'; charset=utf-8')

        def do_POST(self):
            if not self.allowed() or self.path != '/api' or self.headers.get_content_type() != 'application/json':
                return self.respond(403, {'error': '请求来源不允许。'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 32 * 1024 * 1024:
                    return self.respond(413, {'error': '请求为空或超过 32 MB，记录未写入。'})
                payload = json.loads(self.rfile.read(size))
                result = hub.dispatch(payload['action'], payload.get('args', {}))
                self.respond(200, {'result': result})
            except (ValueError, KeyError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
                self.respond(400, {'error': str(error)})
            except Exception as error:
                import traceback
                traceback.print_exc()
                self.respond(500, {'error': str(error)})

    if parent_pid:
        def parent_watch():
            while True:
                time.sleep(3)
                if os.getppid() != parent_pid:
                    os._exit(0)
        threading.Thread(target=parent_watch, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'Library ready: http://127.0.0.1:{port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=47832)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--codex-db', type=Path)
    parser.add_argument('--parent-pid', type=int)
    args = parser.parse_args()
    serve(Library(args.codex_db, args.data_dir), args.port, args.parent_pid)
