"""Throwaway mock of the ESP32's /env endpoint, for local testing only.
Not part of the shipped app -- the real deployment always talks to the
actual sensor node.
"""
import http.server
import json
import random


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/env":
            self.send_response(404)
            self.end_headers()
            return
        payload = {
            "ok": True,
            "iaq": round(random.uniform(40, 90), 1),
            "iaq_accuracy": random.choice([2, 3]),
            "co2_equivalent_ppm": round(random.uniform(450, 900), 1),
            "breath_voc_equivalent_ppm": round(random.uniform(0.5, 3.0), 2),
            "temperature_c": round(random.uniform(21, 25), 2),
            "humidity_pct": round(random.uniform(35, 55), 1),
            "pressure_hpa": round(random.uniform(1005, 1020), 1),
            "gas_resistance_ohm": round(random.uniform(50000, 150000), 0),
            "stabilization_status": 1,
            "run_in_status": 1,
            "age_ms": 120,
            "uptime_ms": 123456,
        }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # quiet


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9099
    http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
