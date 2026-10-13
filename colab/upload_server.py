# Colab cell: tiny authenticated upload endpoint on :8001 behind a second Cloudflare quick tunnel.
import subprocess, threading, time, re, os
from http.server import BaseHTTPRequestHandler, HTTPServer
KEY = "<VLLM_API_KEY from .env>"
class H(BaseHTTPRequestHandler):
    def do_PUT(self):
        if self.headers.get("X-Key") != KEY:
            self.send_response(403); self.end_headers(); return
        n = int(self.headers["Content-Length"]); left = n
        with open("/content/swm_upload.tgz", "wb") as f:
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left)); f.write(chunk); left -= len(chunk)
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok %d" % n)
    def log_message(self, *a): pass
threading.Thread(target=lambda: HTTPServer(("0.0.0.0", 8001), H).serve_forever(), daemon=True).start()
subprocess.Popen("./cloudflared tunnel --url http://localhost:8001 > cf2.log 2>&1", shell=True)
for _ in range(30):
    time.sleep(3)
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", open("cf2.log").read())
    if m: print("SWM_UPLOAD", m.group(0)); break
