"""Interview Room: a local server for the practice rooms. Run it with Start.bat or `python server.py`.

Serves the pages in web/, keeps each session's hidden state (prompts, answer keys) on this side,
sends model turns through backend.py, and saves every session to sessions/.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import backend
import candidate
import prompts_call

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
SESSIONS = os.path.join(HERE, "sessions")
PORT = int(os.environ.get("ROOM_PORT", "8660"))
URL = "http://127.0.0.1:%d/" % PORT
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml"}

STATE = {}  # session id -> {"room", "mode", ...}
SAVE_LOCK = threading.Lock()


def find_chrome():
    for p in (os.environ.get("ROOM_CHROME"),
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if p and os.path.isfile(p):
            return p
    return shutil.which("google-chrome") or shutil.which("chromium")


def launch_browser():
    exe = find_chrome()
    if not exe:
        print("Open %s in Chrome or Edge (speech recognition needs one of them)." % URL)
        return
    # Its own profile so the mic and camera prompts are answered once, and app mode so it looks like a call.
    subprocess.Popen([exe, "--app=" + URL, "--user-data-dir=" + os.path.join(HERE, ".chrome-profile"),
                      "--no-first-run", "--no-default-browser-check", "--use-fake-ui-for-media-stream",
                      "--autoplay-policy=no-user-gesture-required", "--start-maximized",
                      "--disable-features=Translate"])


def history(room):
    out = []
    if os.path.isdir(SESSIONS):
        for name in sorted(os.listdir(SESSIONS)):
            if name.startswith(room + "_") and name.endswith(".json"):
                try:
                    with open(os.path.join(SESSIONS, name), encoding="utf-8") as f:
                        d = json.load(f)
                    if d.get("score") is not None:
                        out.append({"name": name[len(room) + 1:-5], "score": d["score"]})
                except (ValueError, OSError):
                    pass
    return out[-12:]


def save(b):
    os.makedirs(SESSIONS, exist_ok=True)
    name = re.sub(r"[^\w.-]", "_", str(b.get("name") or "session"))
    base = os.path.join(SESSIONS, name)
    with SAVE_LOCK:
        tmp = base + ".json.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(b, f, indent=1)
        os.replace(tmp, base + ".json")
        if b.get("report"):
            with open(base + "-report.md", "w", encoding="utf-8") as f:
                f.write(b["report"])


def call_start(b):
    prof = candidate.load()
    m = prompts_call.mode(b.get("mode"))
    sid = str(uuid.uuid4())
    STATE[sid] = {"room": "call", "mode": m["id"], "first": True,
                  "system": prompts_call.interviewer(m["id"], prof),
                  "grader": prompts_call.grader(m["id"], prof)}
    name = prof["interviewer"] or "Jordan"
    return {"sid": sid, "mode": m, "interviewer": name, "candidate": prof["name"] or "You",
            "company": prof["company"]}


def turn(b):
    st = STATE.get(b.get("sid"))
    if not st:
        return {"text": "This session expired. Start a new one.", "error": True}
    text, err = backend.ask(st["system"], b["message"], "interviewer", b["sid"], st["first"])
    if not err:
        st["first"] = False
    return {"text": text, "error": err}


def grade(b):
    st = STATE.get(b.get("sid"))
    if not st:
        return {"text": "This session expired, so it cannot be graded.", "error": True}
    text, err = backend.ask(st["grader"], b["message"], "grader", timeout=420)
    return {"text": text, "error": err}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes):
            body = (body if isinstance(body, str) else json.dumps(body)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def file(self, rel):
        path = os.path.realpath(os.path.join(WEB, rel))
        if not path.startswith(os.path.realpath(WEB) + os.sep) or not os.path.isfile(path):
            return self.send(404, {"error": "not found"})
        with open(path, "rb") as f:
            self.send(200, f.read(), TYPES.get(os.path.splitext(path)[1], "application/octet-stream"))

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self.file("index.html")
        elif path == "/call":
            self.file("call.html")
        elif path.startswith("/web/"):
            self.file(path[5:])
        elif path == "/api/profile":
            self.send(200, candidate.load())
        elif path == "/api/history":
            room = (self.path.split("room=") + ["call"])[1].split("&")[0]
            self.send(200, history(room))
        elif path == "/api/modes":
            self.send(200, prompts_call.MODES)
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        b = json.loads(self.rfile.read(n) or b"{}")
        routes = {
            "/api/profile": lambda: candidate.save(b),
            "/api/call/start": lambda: call_start(b),
            "/api/turn": lambda: turn(b),
            "/api/grade": lambda: grade(b),
            "/api/save": lambda: save(b) or {"ok": True},
        }
        if self.path == "/api/quit":
            self.send(200, {"ok": True})
            threading.Timer(0.5, lambda: os._exit(0)).start()
        elif self.path in routes:
            self.send(200, routes[self.path]())
        else:
            self.send(404, {"error": "not found"})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    if "--no-browser" not in sys.argv:
        launch_browser()
    print("Interview Room on %s using the %s CLI. Close this window to stop." % (URL, backend.BACKEND))
    srv.serve_forever()
