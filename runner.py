"""Run code from the editor in a throwaway folder: the candidate's own tests, and the hidden tests.

Hidden tests are a plain unittest file with one TestCase class per part (TestPart1, TestPart2, ...).
The candidate never sees that file; they only see which behaviors passed or failed.
"""
import json
import os
import subprocess
import sys
import tempfile

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MARKER = "@@RESULTS@@"

# Runs inside the temp folder. Prints MARKER + [{name, ok, detail}] for every test up to the part.
HIDDEN_RUNNER = r'''
import json, sys, unittest
part, skip = int(sys.argv[1]), set(json.loads(sys.argv[2]))
results = []
try:
    import hidden_tests
except Exception as e:
    print("@@RESULTS@@" + json.dumps([{"name": "import", "ok": False, "detail": f"{type(e).__name__}: {e}"}])); sys.exit()
loader = unittest.TestLoader()
for n in range(1, part + 1):
    cls = getattr(hidden_tests, f"TestPart{n}", None)
    if cls is None:
        continue
    for t in loader.loadTestsFromTestCase(cls):
        name = f"part{n}.{t._testMethodName}"
        if name in skip:
            continue
        r = unittest.TestResult()
        t.run(r)
        bad = r.failures or r.errors
        detail = ""
        if bad:
            detail = bad[0][1].strip().splitlines()[-1][:300]
        doc = (t._testMethodDoc or "").strip().splitlines()
        results.append({"name": name, "ok": not bad, "detail": detail, "doc": doc[0] if doc else ""})
print("@@RESULTS@@" + json.dumps(results))
'''


def _write(folder, files):
    for name, text in files.items():
        safe = os.path.basename(name)
        if safe.endswith(".py"):
            with open(os.path.join(folder, safe), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)


def run_tests(files, timeout=30):
    """The candidate's own test_*.py files, exactly as they would run them locally."""
    with tempfile.TemporaryDirectory(prefix="room-run-") as d:
        _write(d, {n: t for n, t in files.items() if n != "hidden_tests.py"})
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-v", "-p", "test_*.py"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, cwd=d, creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired:
            return {"output": f"Timed out after {timeout} seconds.", "ok": False}
        out = (r.stdout + r.stderr)[-6000:]
        if "Ran 0 tests" in out:
            out += "\nNo tests ran. Add test methods with real assertions.\n"
        return {"output": out, "ok": r.returncode == 0 and "Ran 0 tests" not in out}


def run_hidden(files, hidden, part, skip=(), timeout=90):
    """Hidden tests for parts 1..part against the given files. Returns [{name, ok, detail, doc}]."""
    with tempfile.TemporaryDirectory(prefix="room-hidden-") as d:
        _write(d, {n: t for n, t in files.items() if not n.startswith("test_")})
        _write(d, {"hidden_tests.py": hidden, "_hidden_runner.py": HIDDEN_RUNNER})
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", "_hidden_runner.py", str(part), json.dumps(list(skip))],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, cwd=d, creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired:
            return [{"name": "hidden tests", "ok": False, "detail": f"Timed out after {timeout} seconds.", "doc": ""}]
        if MARKER not in r.stdout:
            return [{"name": "hidden tests", "ok": False, "detail": (r.stderr or r.stdout or "no output")[-600:], "doc": ""}]
        return json.loads(r.stdout.split(MARKER)[-1])
