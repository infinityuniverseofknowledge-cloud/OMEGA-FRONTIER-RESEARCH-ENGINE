"""Bounded, local-only experimental HTTP API. Run: python -m omega.server."""
from __future__ import annotations

import argparse
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from omega import mathcore, models, sat

ROOT = Path(__file__).resolve().parent.parent / 'apps' / 'dashboard'
MAX_BODY = 16384
STATIC = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/styles.css': ('styles.css', 'text/css; charset=utf-8')}


def integer(value, lo, hi, name):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f'{name} must be an integer in {lo}..{hi}')
    return value


def fields(data, keys):
    if not isinstance(data, dict) or set(data) != set(keys):
        raise ValueError('expected exactly these fields: ' + ', '.join(keys))


def calculate(path, data):
    if path == '/api/digits':
        fields(data, ('digits', 'base'))
        digits, base = data['digits'], data['base']
        if not isinstance(digits, str) or len(digits) > 4096:
            raise ValueError('digits must be a string of at most 4096 characters')
        mathcore.validate_digits(digits, base)
        diff = mathcore.modular_difference(digits, base)
        return {'anchor': digits[0], 'differences': diff,
                'reconstructed': mathcore.inverse_difference(diff, digits[0], base),
                'frequencies': mathcore.digit_frequency(digits, base)}
    if path == '/api/sat':
        fields(data, ('num_vars', 'clauses'))
        integer(data['num_vars'], 0, 10, 'num_vars')
        clauses = data['clauses']
        if not isinstance(clauses, list) or len(clauses) > 64:
            raise ValueError('clauses must be a list with at most 64 clauses')
        if any(not isinstance(c, list) for c in clauses) or sum(map(len, clauses)) > 512:
            raise ValueError('clauses must be lists with at most 512 literals total')
        answer = sat.solve(data['num_vars'], clauses)
        return {**answer, 'certificate_verified': sat.verify_certificate(data['num_vars'], clauses, answer)}
    if path == '/api/tsp':
        fields(data, ('matrix',))
        matrix = data['matrix']
        if not isinstance(matrix, list) or not 1 <= len(matrix) <= 10:
            raise ValueError('matrix must contain 1..10 rows')
        n = len(matrix)
        if any(not isinstance(row, list) or len(row) != n for row in matrix):
            raise ValueError('matrix must be square')
        for row in matrix:
            for item in row:
                integer(item, 0, 1000, 'distance')
        exact_path, exact_cost = mathcore.held_karp_cycle(matrix)
        approx_path, approx_cost = mathcore.nearest_neighbor_2opt_cycle(matrix)
        return {'exact': {'cycle': exact_path, 'cost': exact_cost},
                'heuristic': {'cycle': approx_path, 'cost': approx_cost},
                'absolute_gap': approx_cost - exact_cost}
    if path == '/api/soil':
        fields(data, ('first', 'second'))
        a, b = data['first'], data['second']
        if not isinstance(a, list) or not isinstance(b, list) or not 1 <= len(a) <= 32 or len(a) != len(b):
            raise ValueError('vectors must have equal lengths in 1..32')
        return models.soil_similarity(a, b)
    if path == '/api/cellular':
        fields(data, ('rows', 'columns', 'initial_probability', 'steps', 'seed'))
        r = integer(data['rows'], 1, 25, 'rows')
        c = integer(data['columns'], 1, 25, 'columns')
        steps = integer(data['steps'], 0, 50, 'steps')
        if r * c * steps > 20000:
            raise ValueError('at most 20000 cell updates')
        return models.simulate_cellular(r, c, data['initial_probability'], steps, seed=data['seed'])
    raise LookupError('unknown endpoint')


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def bad_constant(value):
    raise ValueError('non-finite JSON number')


class LocalServer(HTTPServer):
    allow_reuse_address = False
    # A per-read timeout alone permits slow clients to monopolize this single
    # worker indefinitely by sending one byte before each timeout.
    request_deadline = 5.0

    def __init__(self, port=8765):
        integer(port, 0, 65535, 'port')
        super().__init__(('127.0.0.1', port), Handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(self.request_deadline)
        return connection, address

    def finish_request(self, request, client_address):
        expired = threading.Event()

        def expire():
            expired.set()
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # peer already closed

        timer = threading.Timer(self.request_deadline, expire)
        timer.daemon = True
        timer.start()
        try:
            super().finish_request(request, client_address)
        except OSError:
            if not expired.is_set():
                raise
        finally:
            timer.cancel()
            # Ensure the callback cannot touch a subsequently reused descriptor.
            timer.join()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass  # no user data in logs

    def respond(self, status, content, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        self.wfile.write(content)

    def json_response(self, status, value):
        self.respond(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8'), 'application/json; charset=utf-8')

    def permitted(self):
        port = self.server.server_address[1]
        host = f'127.0.0.1:{port}'
        # A default-port browser may omit :80. All other Host forms are rejected.
        allowed_hosts = {host} | ({'127.0.0.1'} if port == 80 else set())
        hosts = self.headers.get_all('Host', [])
        origins = self.headers.get_all('Origin', [])
        sites = self.headers.get_all('Sec-Fetch-Site', [])
        if (self.client_address[0] != '127.0.0.1' or len(hosts) != 1 or hosts[0] not in allowed_hosts
                or len(origins) > 1 or (origins and origins[0] not in {f'http://{h}' for h in allowed_hosts})
                or len(sites) > 1 or (sites and sites[0] not in ('same-origin', 'none'))):
            self.json_response(403, {'error': 'local origin required'})
            return False
        return True

    def do_GET(self):
        if not self.permitted():
            return
        if self.path not in STATIC:
            self.json_response(404, {'error': 'not found'})
            return
        name, mime = STATIC[self.path]
        try:
            content = (ROOT / name).read_bytes()
        except OSError:
            self.json_response(503, {'error': 'dashboard unavailable'})
            return
        self.respond(200, content, mime)

    def do_POST(self):
        if not self.permitted():
            return
        if self.path not in {'/api/digits', '/api/sat', '/api/tsp', '/api/soil', '/api/cellular'}:
            self.json_response(404, {'error': 'not found'})
            return
        lengths = self.headers.get_all('Content-Length', [])
        types = self.headers.get_all('Content-Type', [])
        if (self.headers.get_all('Transfer-Encoding', []) or len(lengths) != 1
                or not lengths[0].isascii() or not lengths[0].isdigit() or len(lengths[0]) > 6
                or len(types) != 1 or types[0].strip().lower() != 'application/json'):
            self.json_response(400, {'error': 'one Content-Length and application/json required; transfer encoding forbidden'})
            return
        size = int(lengths[0])
        if size > MAX_BODY:
            self.json_response(413, {'error': 'body exceeds 16384 bytes'})
            return
        try:
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError('incomplete body')
            data = json.loads(raw.decode('utf-8'), object_pairs_hook=no_duplicates, parse_constant=bad_constant)
            result = calculate(self.path, data)
            self.json_response(200, {'ok': True, 'result': result})
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError, socket.timeout):
            self.json_response(400, {'error': 'invalid input or computation limit exceeded'})


def main():
    parser = argparse.ArgumentParser(description='Local-only OMEGA FRONTIER API')
    parser.add_argument('--port', type=int, default=8765, help='local TCP port (default 8765; 0 selects a free port)')
    args = parser.parse_args()
    with LocalServer(args.port) as server:
        print(f'Local only: http://127.0.0.1:{server.server_address[1]}/', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
