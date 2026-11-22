"""Scorer image retention (S7.0): keep what runs plus one rollback; remove our older tags.

    python -m graphguard.ops.images            # dry run: what would be kept / removed
    python -m graphguard.ops.images --apply    # unpin + remove from k3s, then from Docker

Every consumer code change gets a new tag (never rebuild a tag the scorer runs), so old
~2.4 GB images pile up twice: in Docker (where they are built) and in k3s's containerd
(imported and pinned, S5.2). Only `graphguard/serving` is ever touched -- never another
project's image, never Docker's shared build cache.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

REPO = "graphguard/serving"
_VERSION = re.compile(r"^\d+(\.\d+)*$")
_REF = re.compile(r"^(?:docker\.io/)?graphguard/serving:(?P<tag>[^@\s]+)$")


def _key(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.split("."))


def our_tags(refs: list[str]) -> set[str]:
    return {m["tag"] for r in refs if (m := _REF.match(r.strip()))}


def choose(tags: list[str], running: set[str]) -> tuple[list[str], list[str]]:
    """(keep, remove). Keeps every running tag and the newest version below the newest
    running one (the rollback). Non-version tags are never removed. Nothing running seen
    -> nothing removed: without knowing what runs, nothing is known to be safe."""
    versions = sorted((t for t in tags if _VERSION.match(t)), key=_key)
    run = sorted((t for t in running if _VERSION.match(t)), key=_key)
    if not run:
        return list(tags), []
    below = [t for t in versions if _key(t) < _key(run[-1]) and t not in running]
    keep_set = set(running) | ({below[-1]} if below else set())
    keep = [t for t in versions if t in keep_set] + [t for t in tags if not _VERSION.match(t)]
    remove = [t for t in versions if t not in keep_set]
    return keep, remove


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def running_tags() -> set[str]:
    """Tags any pod (any namespace) or any Docker container (even stopped) uses."""
    pods = json.loads(_run(["k3s", "kubectl", "get", "pods", "-A", "-o", "json"]))
    refs = [
        c["image"]
        for p in pods["items"]
        for c in p["spec"].get("containers", []) + p["spec"].get("initContainers", [])
    ]
    refs += _run(["docker", "ps", "-a", "--format", "{{.Image}}"]).splitlines()
    return our_tags(refs)


def k3s_tags() -> set[str]:
    return our_tags(_run(["k3s", "ctr", "-n", "k8s.io", "images", "ls", "-q"]).splitlines())


def docker_tags() -> set[str]:
    out = _run(["docker", "images", REPO, "--format", "{{.Repository}}:{{.Tag}}"])
    return our_tags(out.splitlines())


def plan() -> dict:
    running = running_tags()
    tags = sorted(k3s_tags() | docker_tags())
    keep, remove = choose(tags, running)
    return {"running": sorted(running), "keep": keep, "remove": remove}


def apply(remove: list[str]) -> None:
    k3s, docker = k3s_tags(), docker_tags()
    for tag in remove:
        ref = f"docker.io/{REPO}:{tag}"
        if tag in k3s:
            _run(["k3s", "ctr", "-n", "k8s.io", "images", "label", ref,
                  "io.cri-containerd.pinned-"])  # fmt: skip
            # crictl, not `ctr images rm`: ctr drops the tag but leaves the image behind
            # under its sha256 name (~700 MB each, found in S7.0); crictl removes it whole.
            _run(["k3s", "crictl", "rmi", ref])
        if tag in docker:
            _run(["docker", "rmi", f"{REPO}:{tag}"])


def main(argv: list[str]) -> int:
    p = plan()
    print(json.dumps(p, indent=2))
    if "--apply" in argv and p["remove"]:
        if set(p["remove"]) & set(p["running"]):  # belt and braces: choose() already excludes
            print("refusing: a running tag is in the remove list")
            return 1
        apply(p["remove"])
        print(f"removed {len(p['remove'])} tags")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
