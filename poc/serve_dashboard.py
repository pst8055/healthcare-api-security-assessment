#!/usr/bin/env python3
"""
MedBasket Security PoC — Local Dashboard Server
Proxies API requests to bypass CORS restrictions.
Usage: python3 serve_dashboard.py
Then open: http://localhost:9090
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import json
import ssl
import os
import threading

PORT = 9090
API_BASE = "https://api.medbasket.com"
TOKEN = "<TOKEN_REDACTED>"

ctx = ssl.create_default_context()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.proxy_api()
        elif self.path == "/" or self.path == "/index.html":
            self.path = "/dashboard_poc.html"
            super().do_GET()
        else:
            super().do_GET()

    def proxy_api(self):
        api_path = self.path[4:]  # strip /api prefix
        url = API_BASE + api_path
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {TOKEN}")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            err = json.dumps({"error": str(e)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def log_message(self, format, *args):
        path = args[0].split(" ")[1] if args else ""
        if path.startswith("/api/"):
            print(f"  \033[33mPROXY\033[0m {args[0]}")
        else:
            print(f"  \033[36mSERVE\033[0m {args[0]}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = ThreadedHTTPServer(("0.0.0.0", PORT), ProxyHandler)
    print(f"\033[1;31m{'='*60}\033[0m")
    print(f"\033[1;31m  MedBasket Security PoC Dashboard\033[0m")
    print(f"\033[1;31m  CONFIDENTIAL — Security Assessment Only\033[0m")
    print(f"\033[1;31m{'='*60}\033[0m")
    print(f"\n  Open in browser: \033[1;4mhttp://localhost:{PORT}\033[0m\n")
    print(f"  Proxying API calls to {API_BASE}")
    print(f"  JWT sub: 6000000000000000000000a1 (regular user)\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.server_close()
