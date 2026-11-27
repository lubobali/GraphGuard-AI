"""S8b.4: every headline number in the README matches the file it comes from, the README
says "synthetic" first, its images and links exist, and it names no weak spot."""

import json
import re

import pytest

from graphguard.config import REPO_ROOT

pytestmark = pytest.mark.unit

README = (REPO_ROOT / "README.md").read_text()
TOP = README.split("## The problem")[0]  # the part a stranger reads


def _json(path):
    return json.loads((REPO_ROOT / path).read_text())


def test_synthetic_comes_first():
    first = README[:800]
    assert "Synthetic data" in first and "AMLworld" in first and "validation" in first


def test_the_queue_vs_rules_numbers_match_the_capacity_file():
    r = _json("docs/analysis/s7.3-capacity.json")["rankings"]
    k = "211"
    system, rules = r["system"][k]["caught"], r["rules"][k]["caught"]
    assert (system, rules) == (167, 1)
    assert f"(**{k}** over the 2-day window): the model-led queue finds **{system}**" in TOP
    assert f"same {k} checks, find **{rules}**" in TOP
    missed = r["system"][k]["missed"]
    assert f"({missed} of {system + missed:,})" in TOP


def test_the_model_comparison_numbers_match_their_write_up():
    mc = (REPO_ROOT / "docs/model_comparison.md").read_text()
    assert "**0.28155**" in mc and "**127 / 168**" in mc
    assert re.search(r"GraphSAGE.*0\.04470.*60 / 168", mc)
    assert "**127 of 168**" in TOP and "PR-AUC **0.28155**" in TOP
    assert "PR-AUC **0.04470**, 60 of 168" in TOP


def test_the_latency_matches_finding_013():
    assert "**p99 is 13-15 ms**" in (REPO_ROOT / "docs/findings.md").read_text()
    assert "p99 **13-15 ms**" in TOP


def test_the_replay_matches_the_soak_record():
    s = _json("docs/analysis/s6.11-soak-run2.json")
    assert s["decisions"] == s["sent"] and s["missing"] == 0 and s["extra"] == 0
    assert s["score_mismatches"] == 0
    assert f"**{s['sent']:,}** payments" in TOP and "**0** score mismatches" in TOP


def test_the_ai_rates_match_the_clean_set():
    rates = {m["reporter"]: m["unsupported_rate_before_checker"]
             for m in _json("docs/analysis/s7.10-agent.json")["set2"]["models"]}  # fmt: skip
    sonnet = next(v for k, v in rates.items() if "sonnet" in k)
    deepseek = next(v for k, v in rates.items() if "deepseek" in k)
    assert f"**{deepseek:.1%}** (DeepSeek" in TOP and f"**{sonnet:.1%}** (Claude Sonnet" in TOP


def test_images_and_repo_links_exist():
    images = re.findall(r'src="([^"]+)"', README)
    links = re.findall(r"\]\((?!https?:)([^)#]+)", README)
    for path in images + links:
        assert (REPO_ROOT / path).exists(), path


def test_no_weak_spots():
    bad = [r"127\.0\.0\.1", r"\b\d{1,3}(\.\d{1,3}){3}\b", r"localhost", r":\d{4,5}\b",
           r"/srv/", r"\.secrets/\w", r"(?i)\bcve-", r"(?i)password"]  # fmt: skip
    hits = [p for p in bad if re.search(p, README)]
    assert hits == [], hits
