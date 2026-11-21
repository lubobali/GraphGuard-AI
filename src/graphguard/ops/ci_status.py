"""Wait for CI on a commit (so nobody has to watch the Forgejo page).

    python -m graphguard.ops.ci_status wait [<sha>] [--timeout 1800]   # exit 0 green, 1 red

Reads the commit's combined status from Forgejo with a READ-ONLY repository token
(`.secrets/forgejo-ci-read.env`). It cannot push or change anything.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request

from graphguard.config import REPO_ROOT, secrets_dir

API = "https://git.lubot.ai/api/v1/repos/lubo/GraphGuard-AI"
DONE = {"success": 0, "failure": 1, "error": 1}


def verdict(status: dict) -> str:
    """Combined state, but only once every job has reported (pure, tested)."""
    statuses = status.get("statuses") or []
    if not statuses:
        return "pending"
    states = {s.get("status") or s.get("state") for s in statuses}
    if states & {"failure", "error"}:
        return "failure"
    if states <= {"success"}:
        return "success"
    return "pending"


def failed_jobs(status: dict) -> list[str]:
    return [s.get("context", "?") for s in status.get("statuses") or []
            if (s.get("status") or s.get("state")) in {"failure", "error"}]  # fmt: skip


def _token() -> str:
    text = (secrets_dir() / "forgejo-ci-read.env").read_text()
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)["FORGEJO_TOKEN"]


def fetch(sha: str) -> dict:
    req = urllib.request.Request(f"{API}/commits/{sha}/status",
                                 headers={"Authorization": f"token {_token()}"})  # fmt: skip
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 (fixed https URL)
        return json.load(r)


def wait(sha: str, timeout: int = 1800, every: int = 20) -> int:
    end = time.time() + timeout
    while time.time() < end:
        status = fetch(sha)
        v = verdict(status)
        if v != "pending":
            print(f"CI {sha[:10]}: {v.upper()}" + (f" -- failed: {failed_jobs(status)}"
                                                   if v == "failure" else ""))  # fmt: skip
            return DONE[v]
        time.sleep(every)
    print(f"CI {sha[:10]}: still pending after {timeout}s")
    return 2


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args or args[0] != "wait":
        print(f"usage: {argv[0]} wait [<sha>] [--timeout N]")
        return 2
    sha = (
        args[1]
        if len(args) > 1
        else subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    timeout = int(argv[argv.index("--timeout") + 1]) if "--timeout" in argv else 1800
    return wait(sha, timeout)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
