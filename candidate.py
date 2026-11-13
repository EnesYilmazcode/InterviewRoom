"""Who the candidate is. Lives in profile.json, which never leaves your machine."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "profile.json")
EXAMPLE = os.path.join(HERE, "profile.example.json")
FIELDS = ("name", "role", "company", "company_notes", "background", "interviewer")


def load():
    for p in (PATH, EXAMPLE):
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            out = {k: str(data.get(k) or "").strip() for k in FIELDS}
            out["saved"] = p == PATH
            return out
    return {k: "" for k in FIELDS} | {"saved": False}


def save(data):
    clean = {k: str(data.get(k) or "").strip() for k in FIELDS}
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
    os.replace(tmp, PATH)
    return clean


def describe(p):
    """The candidate block every prompt gets."""
    company = p["company"] or "a software company (unnamed, keep it generic)"
    lines = [f"CANDIDATE: {p['name'] or 'the candidate'}, interviewing for {p['role'] or 'a software engineering role'} at {company}."]
    if p["background"] and not p["background"].startswith("Paste your resume"):
        lines.append("Their background, in their own words:\n" + p["background"])
    else:
        lines.append("No background was given. Ask about it and take their word for it.")
    if p["company_notes"]:
        lines.append("WHAT YOU KNOW ABOUT THE COMPANY (use it plausibly, never invent numbers):\n" + p["company_notes"])
    return "\n".join(lines)
