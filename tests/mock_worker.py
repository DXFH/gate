#!/usr/bin/env python3
"""Mock CheckSocks5 Worker for fault-injection. Usage: mock_worker.py PORT MODE
MODE: ok | timeout | http500 | garbage | flaky | http403"""
import json, random, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote
PORT, MODE = int(sys.argv[1]), sys.argv[2]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="application/json"):
        b = body.encode(); self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query); tgt = unquote((q.get("sstp") or ["x"])[0])
        m = MODE
        if m == "flaky": m = "http500" if random.random() < 0.4 else "ok"
        if m == "timeout": time.sleep(30); return
        if m == "http500": return self._send(500, "{}")
        if m == "http403": return self._send(403, "{}")
        if m == "garbage": return self._send(200, "<html>oops</html>", "text/html")
        ok = hash(tgt) % 3 != 0  # ~2/3 succeed
        res = {"success": ok, "responseTime": 120 + hash(tgt) % 300, "colo": "SJC"}
        if ok: res["exit"] = {"ip": "203.0.113.7", "country": "Japan", "country_code": "JP", "asn": {"asn": 4713, "org": "NTT Communications"}}
        else: res["error"] = "connect failed"
        self._send(200, json.dumps(res))
ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()