"""Problems for the coding room: write a fresh one with the model, or load one from exercises/.

A problem folder holds exercise.json (title, module, parts, answer_key), the starting code
as <module>.py, and optionally hidden_tests.py and reference.py. Every generated problem is
saved the same way, so a good one can be run again.
"""
import json
import os
import re
import time

import backend
import prompts_coding
import runner

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "exercises")
TEST_STARTER = '''import unittest
from {module} import *


class Test{cls}(unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()
'''


def listing():
    out = []
    if os.path.isdir(ROOT):
        for name in sorted(os.listdir(ROOT), reverse=True):
            meta = os.path.join(ROOT, name, "exercise.json")
            if os.path.isfile(meta):
                try:
                    with open(meta, encoding="utf-8") as f:
                        d = json.load(f)
                    out.append({"id": name, "title": d.get("title", name),
                                "hidden": os.path.isfile(os.path.join(ROOT, name, "hidden_tests.py"))})
                except (ValueError, OSError):
                    pass
    return out


def _read(folder, name):
    p = os.path.join(folder, name)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return f.read()
    return None


def load(ex_id):
    folder = os.path.join(ROOT, os.path.basename(ex_id))
    with open(os.path.join(folder, "exercise.json"), encoding="utf-8") as f:
        d = json.load(f)
    module = d["module"]
    starter = {module + ".py": _read(folder, module + ".py") or ""}
    starter["test_" + module + ".py"] = _read(folder, "test_" + module + ".py") or TEST_STARTER.format(
        module=module, cls="".join(w.title() for w in module.split("_")))
    return {"id": ex_id, "title": d["title"], "module": module, "parts": d["parts"],
            "answer_key": d.get("answer_key", ""), "starter": starter,
            "hidden": _read(folder, "hidden_tests.py"), "skip": d.get("skip", [])}


def _parse(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("the writer did not return JSON")
    d = json.loads(m.group(0))
    for k in ("title", "module", "parts", "starter", "answer_key", "reference", "hidden_tests"):
        if not d.get(k):
            raise ValueError("the writer left out " + k)
    if len(d["parts"]) < 2:
        raise ValueError("the writer returned fewer than two parts")
    d["module"] = re.sub(r"\W", "_", d["module"]).strip("_").lower() or "solution"
    return d


def generate(topic="", difficulty="medium", tries=2):
    ask = f"Difficulty: {difficulty}. " + (f"Theme: {topic}." if topic.strip() else "Pick any practical theme.")
    ask += " Make it different from the most common interview problems."
    last = "no attempt"
    for _ in range(tries):
        text, err = backend.ask(prompts_coding.WRITER, ask, "writer", timeout=420)
        if err:
            last = text
            continue
        try:
            d = _parse(text)
        except ValueError as e:
            last = str(e)
            continue
        # Keep only hidden tests the reference solution passes, so a wrong test never fails the candidate.
        ref = {d["module"] + ".py": d["reference"]}
        results = runner.run_hidden(ref, d["hidden_tests"], len(d["parts"]))
        if results and results[0]["name"] in ("import", "hidden tests"):
            last = "hidden tests did not load: " + results[0]["detail"]
            continue
        skip = [r["name"] for r in results if not r["ok"]]
        if len(skip) > len(results) // 3:
            last = f"{len(skip)} of {len(results)} hidden tests failed the reference"
            continue
        return _save(d, skip, len(results))
    raise RuntimeError("Could not write a problem: " + last[-400:])


def _save(d, skip, total):
    ex_id = time.strftime("%Y-%m-%d_%H%M_") + d["module"]
    folder = os.path.join(ROOT, ex_id)
    os.makedirs(folder, exist_ok=True)
    meta = {"title": d["title"], "module": d["module"], "parts": d["parts"], "answer_key": d["answer_key"],
            "skip": skip, "hidden_total": total}
    files = {"exercise.json": json.dumps(meta, indent=1), d["module"] + ".py": d["starter"],
             "hidden_tests.py": d["hidden_tests"], "reference.py": d["reference"]}
    for name, text in files.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text.rstrip("\n") + "\n")
    return load(ex_id)
