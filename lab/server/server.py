import argparse
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        received_ns = time.monotonic_ns()
        received_at = datetime.now(timezone.utc).isoformat()

        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length)

        record = {
            "received_at": received_at,
            "received_monotonic_ns": received_ns,
            "client_ip": self.client_address[0],
            "client_port": self.client_address[1],
            "path": self.path,
            "run_id": self.headers.get("X-Lab-Run-ID", ""),
            "sequence": self.headers.get("X-Lab-Sequence", ""),
            "request_body_bytes": len(payload),
        }

        # Khóa để các request không ghi chồng lên nhau.
        with self.server.log_lock:
            with self.server.log_path.open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(json.dumps(record) + "\n")

        response = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        # Giảm log mặc định trên terminal.
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()

    args.log.parent.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.log_path = args.log
    server.log_lock = threading.Lock()

    print(f"Listening: http://127.0.0.1:{args.port}")
    print(f"Appending log to: {args.log}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()