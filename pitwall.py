#!/usr/bin/env python3
"""Pit Wall Debrief - local server. Serves index.html and proxies/caches OpenF1 (https://api.openf1.org/v1).
Run:  python3 pitwall.py   then open http://127.0.0.1:8765   (Python 3.8+, no packages needed)"""
import hashlib, json, os, re, ssl, sys, threading, time, urllib.error, urllib.parse, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
UPSTREAM = os.environ.get("OPENF1_BASE", "https://api.openf1.org/v1").rstrip("/")
PORT = int(os.environ.get("PORT", "8765"))
CACHE = os.path.join(HERE, "cache")
ENDPOINTS = {"meetings", "sessions", "drivers", "laps", "stints", "pit", "position", "race_control",
             "weather", "session_result", "starting_grid", "car_data", "location", "intervals", "overtakes"}
MIN_GAP = 0.4            # seconds between upstream calls (OpenF1 rate limits)
_lock, _last = threading.Lock(), [0.0]
os.makedirs(CACHE, exist_ok=True)

def make_ssl():
    """Python on macOS (python.org installer) often has no CA bundle. Try certifi, then the system store."""
    if os.environ.get("PITWALL_INSECURE") or "--insecure" in sys.argv:
        print("WARNING: TLS verification is OFF (public read-only data only).")
        c = ssl.create_default_context(); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE; return c
    try:
        import certifi; return ssl.create_default_context(cafile=certifi.where())
    except Exception: pass
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/opt/homebrew/etc/ca-certificates/cert.pem", "/usr/local/etc/openssl@3/cert.pem"):
        if os.path.exists(p) and not ssl.get_default_verify_paths().cafile:
            return ssl.create_default_context(cafile=p)
    return ssl.create_default_context()
CTX = make_ssl()

def clean_query(qs):
    """Re-encode the query so operators like date>=... survive, dropping our own flags."""
    parts, fresh = [], False
    for tok in qs.split("&"):
        if not tok: continue
        tok = re.sub(r"%3[CcEe]", lambda m: urllib.parse.unquote(m.group(0)), tok)  # browsers encode < and >
        if tok.startswith("nocache"): fresh = True; continue
        m = re.match(r"^([a-z_]+)(>=|<=|>|<|=)(.*)$", tok)
        if not m: raise ValueError("bad query token: " + tok)
        k, op, v = m.groups()
        parts.append(k + op + urllib.parse.quote(urllib.parse.unquote(v), safe=":+-._~"))
    return "&".join(parts), fresh

def fetch_upstream(url):
    err = None
    for attempt in range(4):
        with _lock:
            wait = MIN_GAP - (time.time() - _last[0])
            if wait > 0: time.sleep(wait)
            _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pit-wall-debrief/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            if e.code == 404:  # OpenF1 answers 404 when a filter matches nothing
                return b"[]"
            err = "OpenF1 HTTP %d %s" % (e.code, body)
            if e.code not in (429, 500, 502, 503, 504): break
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            err = "Could not reach OpenF1: %s" % e
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                err += (" - Python has no CA certificates. On macOS run 'Install Certificates.command' in /Applications/Python 3.x/, "
                        "or 'pip3 install certifi', or start with: python3 pitwall.py --insecure")
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(err)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f: return self.send(200, f.read(), "text/html; charset=utf-8")
        if u.path.startswith("/api/"):
            ep = u.path[5:]
            if ep not in ENDPOINTS: return self.send(404, b'{"error":"unknown endpoint"}')
            try: q, fresh = clean_query(u.query)
            except ValueError as e: return self.send(400, json.dumps({"error": str(e)}).encode())
            url = UPSTREAM + "/" + ep + ("?" + q if q else "")
            f = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")
            if not fresh and os.path.exists(f):
                with open(f, "rb") as fh: return self.send(200, fh.read())
            try: data = fetch_upstream(url)
            except Exception as e: return self.send(502, json.dumps({"error": str(e)}).encode())
            try:
                if not isinstance(json.loads(data), list): raise ValueError("unexpected reply: " + data[:200].decode("utf-8", "replace"))
            except Exception as e: return self.send(502, json.dumps({"error": "OpenF1 sent something unexpected: %s" % e}).encode())
            # do not cache sessions/laps that may still be filling in: only cache non-empty replies
            if data.strip() not in (b"[]", b""):
                tmp = f + ".tmp"
                with open(tmp, "wb") as fh: fh.write(data)
                os.replace(tmp, f)
            return self.send(200, data)
        self.send(404, b"not found", "text/plain")

def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = "http://127.0.0.1:%d" % PORT
    print("Pit Wall Debrief running at", url, "(upstream %s)\nCtrl+C to stop. Cached data: %s" % (UPSTREAM, CACHE))
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nbye")
if __name__ == "__main__": main()
