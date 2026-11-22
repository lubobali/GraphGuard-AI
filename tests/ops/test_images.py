"""Image retention (S7.0): keep what runs and one rollback, remove the rest of OUR images."""

import pytest

from graphguard.ops import images as im

pytestmark = pytest.mark.unit

TAGS = ["0.1.2", "0.1.10", "0.1.9", "0.1.11", "0.1.12", "latest-thing"]


def test_keeps_the_running_tag_and_the_one_before_it():
    keep, remove = im.choose(TAGS, running={"0.1.12"})
    assert keep == ["0.1.11", "0.1.12", "latest-thing"]
    assert remove == ["0.1.2", "0.1.9", "0.1.10"]  # version order, not string order


def test_never_removes_a_tag_something_still_runs():
    keep, remove = im.choose(TAGS, running={"0.1.12", "0.1.9"})
    assert "0.1.9" in keep and "0.1.9" not in remove


def test_tags_that_are_not_versions_are_never_touched():
    keep, remove = im.choose(TAGS, running={"0.1.12"})
    assert "latest-thing" not in remove


def test_nothing_running_means_nothing_removed():
    # if we cannot see what runs, we cannot know what is safe
    keep, remove = im.choose(TAGS, running=set())
    assert remove == [] and set(keep) == set(TAGS)


def test_only_our_repository_is_parsed():
    refs = ["docker.io/graphguard/serving:0.1.9", "docker.io/library/redis:7", "graphguard/ci:1",
            "docker.io/graphguard/serving:0.1.12"]  # fmt: skip
    assert im.our_tags(refs) == {"0.1.9", "0.1.12"}
