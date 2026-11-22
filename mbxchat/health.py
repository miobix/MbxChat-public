import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg

from mbxchat import config


def db_ok(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        ok = db_ok(config.DATABASE_URL)
        body = json.dumps({"status": "ok" if ok else "db unavailable"}).encode()
        self.send_response(200 if ok else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # the Docker healthcheck polls every 30 s; access lines would drown real logs


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _Handler)
