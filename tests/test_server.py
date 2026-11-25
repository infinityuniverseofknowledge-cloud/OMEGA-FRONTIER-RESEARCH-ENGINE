"""End-to-end local HTTP and security regression tests; no external network."""
import http.client
import json
import socket
import threading
import time
import unittest

from omega.server import LocalServer, MAX_BODY


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer(0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def post(self, endpoint, obj):
        status, _, data = self.req('POST', '/api/' + endpoint, json.dumps(obj), {'Content-Type': 'application/json'})
        return status, json.loads(data)

    def test_bind_and_static(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        for path in ('/', '/app.js', '/styles.css'):
            status, headers, data = self.req('GET', path)
            self.assertEqual(status, 200)
            self.assertTrue(data)
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
        for path in ('/../omega/server.py', '/%2e%2e/omega/server.py', '//etc/passwd', '/?x=1', '/index.html'):
            self.assertEqual(self.req('GET', path)[0], 404)

    def test_rebinding_and_cross_origin(self):
        for headers in ({'Host': 'evil.example'}, {'Host': 'localhost:' + str(self.port)},
                        {'Origin': 'https://evil.example'}, {'Origin': 'null'},
                        {'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(self.req('GET', '/', headers=headers)[0], 403)
        self.assertEqual(self.req('POST', '/api/digits', '{"digits":"1","base":10}',
                                  {'Content-Type': 'application/json', 'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.req('GET', '/', headers={'Origin': 'http://127.0.0.1:' + str(self.port)})[0], 200)
        with socket.create_connection(('127.0.0.1', self.port)) as sock:
            sock.sendall((f'GET / HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\nHost: evil.example\r\n\r\n').encode())
            self.assertIn(b' 403 ', sock.recv(1024))

    def test_digits(self):
        status, body = self.post('digits', {'digits': '001904', 'base': 10})
        self.assertEqual(status, 200)
        self.assertEqual(body['result']['reconstructed'], '001904')
        self.assertEqual(body['result']['anchor'], '0')
        for obj in ({'digits': '', 'base': 10}, {'digits': '012', 'base': 2},
                    {'digits': '1' * 4097, 'base': 10}, {'digits': '1', 'base': True}):
            self.assertEqual(self.post('digits', obj)[0], 400)

    def test_sat_verified(self):
        for clauses, answer in (([[1], [-1]], 'UNSAT'), ([[1, 2]], 'SAT')):
            status, body = self.post('sat', {'num_vars': 2, 'clauses': clauses})
            self.assertEqual(status, 200)
            self.assertEqual(body['result']['status'], answer)
            self.assertTrue(body['result']['certificate_verified'])
        for obj in ({'num_vars': 11, 'clauses': []}, {'num_vars': 1, 'clauses': [[2]]},
                    {'num_vars': 1, 'clauses': [[1]] * 65}, {'num_vars': True, 'clauses': []}):
            self.assertEqual(self.post('sat', obj)[0], 400)

    def test_tsp(self):
        matrix = [[0,10,15,20],[10,0,35,25],[15,35,0,30],[20,25,30,0]]
        status, body = self.post('tsp', {'matrix': matrix})
        self.assertEqual(status, 200)
        self.assertEqual(body['result']['exact']['cost'], 80)
        self.assertGreaterEqual(body['result']['absolute_gap'], 0)
        for m in ([[0,1],[2,0]], [[0,1001],[1001,0]], [[0] * 11] * 11, [[True]]):
            self.assertEqual(self.post('tsp', {'matrix': m})[0], 400)

    def test_synthetic_models(self):
        status, body = self.post('soil', {'first': [0,0], 'second': [1,1]})
        self.assertEqual(status, 200)
        self.assertEqual(body['result']['similarity'], 0)
        self.assertEqual(self.post('soil', {'first': [2], 'second': [0]})[0], 400)
        example = {'rows': 8, 'columns': 8, 'initial_probability': .3, 'steps': 5, 'seed': 42}
        first = self.post('cellular', example)
        self.assertEqual(first[0], 200)
        self.assertEqual(first, self.post('cellular', example))
        self.assertEqual(len(first[1]['result']['counts']), 6)
        self.assertEqual(self.post('cellular', dict(example, rows=25, columns=25, steps=50))[0], 400)
        self.assertEqual(self.post('cellular', dict(example, initial_probability=2))[0], 400)

    def test_absolute_deadline_stops_slow_drip(self):
        # Keep supplying bytes faster than the inactivity timeout; the absolute
        # deadline must still release the single worker for the next request.
        server = LocalServer(0)
        server.request_deadline = 0.35
        port = server.server_address[1]
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for prefix in (f'GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Fill: ',
                           f'POST /api/digits HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n'):
                with socket.create_connection(('127.0.0.1', port), timeout=2) as client:
                    client.sendall(prefix.encode())
                    start = time.monotonic()
                    while time.monotonic() - start < 0.7:
                        try:
                            client.sendall(b'x')
                        except OSError:
                            break
                        time.sleep(0.04)
                    # Even if the peer's close is not immediately observable,
                    # a new request should not wait for the drip to end.
                    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=0.25)
                    try:
                        conn.request('GET', '/')
                        response = conn.getresponse()
                        self.assertEqual(response.status, 200)
                        response.read()
                    finally:
                        conn.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_duplicate_security_headers(self):
        for header in ('Origin: http://127.0.0.1:{port}\r\nOrigin: null',
                       'Sec-Fetch-Site: same-origin\r\nSec-Fetch-Site: cross-site'):
            with socket.create_connection(('127.0.0.1', self.port), timeout=2) as sock:
                text = (f'GET / HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n' +
                        header.format(port=self.port) + '\r\n\r\n')
                sock.sendall(text.encode())
                self.assertIn(b' 403 ', sock.recv(1024))

    def test_bad_http_and_json(self):
        self.assertEqual(self.req('POST', '/api/digits', '{}', {'Content-Type': 'text/plain'})[0], 400)
        self.assertEqual(self.req('POST', '/api/digits', 'x' * (MAX_BODY + 1), {'Content-Type': 'application/json'})[0], 413)
        for raw in ('{', '{"digits":"1","digits":"2","base":10}', '{"digits":"1","base":NaN}'):
            self.assertEqual(self.req('POST', '/api/digits', raw, {'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(self.post('unknown', {})[0], 404)
        self.assertEqual(self.post('digits', {'digits': '1', 'base': 10, 'extra': 1})[0], 400)
        self.assertEqual(self.req('OPTIONS', '/api/digits')[0], 501)
        with socket.create_connection(('127.0.0.1', self.port)) as sock:
            sock.sendall((f'POST /api/digits HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\nContent-Type: application/json\r\nContent-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n{{}}').encode())
            self.assertIn(b' 400 ', sock.recv(1024))


if __name__ == '__main__':
    unittest.main()
