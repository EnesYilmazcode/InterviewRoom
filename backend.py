"""Talk to a model through a coding agent CLI you are already signed in to.

No API key: every reply is one non-interactive run of `claude -p` (Claude Code)
or `codex exec` (Codex CLI). Pick one with ROOM_BACKEND=claude|codex.
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BACKEND = os.environ.get("ROOM_BACKEND", "claude").lower()

# Which Claude model plays each role. Override with ROOM_MODEL_<ROLE>.
CLAUDE_MODELS = {"interviewer": "sonnet", "agent": "sonnet", "writer": "sonnet", "grader": "opus"}


def model_for(role):
    return os.environ.get("ROOM_MODEL_" + role.upper()) or CLAUDE_MODELS.get(role, "sonnet")


def _claude(system, message, role, session_id, first, timeout):
    exe = shutil.which("claude")
    if not exe:
        return "Claude Code was not found. Install it and run `claude` once to sign in.", True
    fd, sysfile = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(system)
    args = [exe, "-p", "--output-format", "json", "--model", model_for(role),
            "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
            "--system-prompt-file", sysfile]
    if session_id:
        args += ["--session-id", session_id] if first else ["--resume", session_id]
    try:
        r = subprocess.run(args, input=message, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           cwd=tempfile.gettempdir(), creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return "The model timed out.", True
    finally:
        os.remove(sysfile)
    try:
        out = json.loads(r.stdout)
        return out.get("result") or "", bool(out.get("is_error"))
    except ValueError:
        return (r.stderr or r.stdout or "no output")[-800:], True


# Codex has no resumable text session here, so we keep the last turns ourselves.
_history, _locks, _guard = {}, {}, threading.Lock()


def _codex(system, message, role, session_id, first, timeout):
    exe = shutil.which("codex.cmd") or shutil.which("codex")
    if not exe:
        return "Codex CLI was not found. Install it and run `codex login`.", True
    key = session_id or os.urandom(8).hex()
    with _guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        prior = [] if first else _history.get(key, [])
        prompt = ("You are a text-only component of an interview practice app. Do not use tools, "
                  "read files or run commands. Reply only as the role below.\n\n" + system
                  + "\n\nCONVERSATION:\n" + "\n\n".join(prior[-16:] + ["USER: " + message]))
        with tempfile.TemporaryDirectory(prefix="room-") as work:
            answer = os.path.join(work, "answer.txt")
            args = [exe, "exec", "--skip-git-repo-check", "--ephemeral", "--sandbox", "read-only",
                    "--color", "never", "-c", 'approval_policy="never"',
                    "-c", 'model_reasoning_effort="low"', "--output-last-message", answer, "-"]
            if os.environ.get("ROOM_CODEX_MODEL"):
                args[2:2] = ["--model", os.environ["ROOM_CODEX_MODEL"]]
            try:
                r = subprocess.run(args, input=prompt, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=timeout,
                                   cwd=work, creationflags=NO_WINDOW)
            except (OSError, subprocess.TimeoutExpired) as e:
                return str(e), True
            if r.returncode or not os.path.isfile(answer):
                return (r.stderr or r.stdout or "no output")[-1200:], True
            with open(answer, encoding="utf-8") as f:
                text = f.read().strip()
        if session_id:
            _history[key] = (prior + ["USER: " + message, "ASSISTANT: " + text])[-16:]
        return text, False


def ask(system, message, role="interviewer", session_id=None, first=False, timeout=240):
    """One model turn. Returns (text, is_error). session_id keeps a conversation going."""
    fn = _codex if BACKEND == "codex" else _claude
    return fn(system, message, role, session_id, first, timeout)
