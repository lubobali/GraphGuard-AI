"""The access policy (S5.6d): who may touch which layer -- checked without a server."""

import pytest

from graphguard.lakehouse import governance as gov
from graphguard.lakehouse.identity import IDENTITIES

pytestmark = pytest.mark.unit


def _grants(identity):
    return {(g.target, g.privilege) for g in gov.grant_plan() if g.identity == identity}


def test_trainer_and_reader_get_nothing_on_sealed_or_the_whole_warehouse():
    for who in ("trainer", "reader"):
        targets = {t for t, _ in _grants(who)}
        assert gov.SEALED not in targets and gov.WAREHOUSE not in targets, who


def test_bronze_is_metadata_only_for_trainer_and_reader_because_it_holds_the_test_window():
    # FINDING-011: bronze is the raw CSV, test window included.
    for who in ("trainer", "reader"):
        assert {p for t, p in _grants(who) if t == gov.BRONZE} == {"describe"}, who


def test_trainer_reads_exactly_silver_and_gold():
    assert {t for t, p in _grants("trainer") if p == "select"} == {"silver", "gold"}


def test_only_builder_can_write():
    writers = {g.identity for g in gov.grant_plan() if g.privilege in ("write", "modify", "create")}
    assert writers == {"builder"}
    assert _grants("builder") == {(gov.WAREHOUSE, "create"), (gov.WAREHOUSE, "modify")}


def test_policy_names_only_known_identities():
    assert set(gov.POLICY) <= set(IDENTITIES)


@pytest.mark.parametrize(
    "bad",
    [
        {"trainer": {"sealed": ("select",)}},
        {"reader": {"sealed": ("describe",)}},
        {"trainer": {gov.WAREHOUSE: ("select",)}},  # inherits down into sealed
        {"reader": {"bronze": ("select",)}},
        {"trainer": {"bronze": ("modify",)}},
    ],
)
def test_an_unsafe_policy_is_refused_before_anything_is_sent(bad):
    with pytest.raises(gov.UnsafePolicy):
        gov.grant_plan(bad)


def test_grant_requests_are_one_call_per_target_and_deterministic():
    users = {n: f"oidc~{n}-id" for n in IDENTITIES}
    nss = {"bronze": "nb", "silver": "ns", "gold": "ng", "sealed": "nx"}
    calls = gov.grant_requests(gov.grant_plan(), users, "wh", nss)
    assert calls == gov.grant_requests(gov.grant_plan(), users, "wh", nss)
    paths = [p for p, _ in calls]
    assert len(paths) == len(set(paths))
    assert "/management/v1/warehouse/wh/grants" in paths
    assert not any("/namespace/nx/" in p for p in paths)  # nothing is ever granted on sealed
    for _, body in calls:
        assert body["deletes"] == [] and body["writes"]
        for w in body["writes"]:
            assert set(w) == {"principal", "privilege"} and set(w["principal"]) == {"user"}
