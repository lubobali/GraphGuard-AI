"""What each lakehouse identity may do (S5.6d). This file IS the access policy.

Lakekeeper enforces it through OpenFGA. Grants flow *down*: a privilege on the
warehouse reaches every namespace in it, `sealed` included. So readers are
granted namespace by namespace, and `check_plan()` refuses any plan that gives
`trainer` or `reader` a warehouse-level privilege, anything on `sealed`, or data
access to `bronze`.

**Bronze holds the test window too.** It is the raw CSV, all 5,078,345 rows. Read
access to bronze is read access to the test set, so `sealed` alone would be a
hollow lock (FINDING-011). Trainer and reader get `describe` on bronze -- enough
to record its snapshot id in a run's lineage, no data.

    builder  create + modify on the warehouse   (writes every layer, incl. sealed)
    trainer  select on silver, gold; describe on bronze
    reader   select on silver, gold; describe on bronze
    admin    the operator that bootstrapped the server; owns everything

`apply_grants()` is idempotent: Lakekeeper applies a grant diff atomically and a
repeated write changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

WAREHOUSE = "@warehouse"  # grant target: the whole warehouse
SEALED = "sealed"
BRONZE = "bronze"  # raw: contains the test window as well
NO_SEALED = ("trainer", "reader")  # identities that must never read the test window
METADATA_ONLY = ("describe",)  # what NO_SEALED identities may hold on bronze

POLICY: dict[str, dict[str, tuple[str, ...]]] = {
    "builder": {WAREHOUSE: ("create", "modify")},
    "trainer": {BRONZE: METADATA_ONLY, "silver": ("select",), "gold": ("select",)},
    "reader": {BRONZE: METADATA_ONLY, "silver": ("select",), "gold": ("select",)},
}


@dataclass(frozen=True)
class Grant:
    identity: str
    target: str  # WAREHOUSE or a namespace name
    privilege: str


def grant_plan(policy: dict[str, dict[str, tuple[str, ...]]] = POLICY) -> list[Grant]:
    plan = [
        Grant(identity, target, privilege)
        for identity, targets in sorted(policy.items())
        for target, privileges in sorted(targets.items())
        for privilege in privileges
    ]
    check_plan(plan)
    return plan


class UnsafePolicy(ValueError):
    pass


def check_plan(plan: list[Grant]) -> None:
    """Refuse a plan that would let trainer or reader read the test window:
    through `sealed`, through bronze's raw rows, or by inheritance from the
    warehouse."""
    for g in plan:
        if g.identity not in NO_SEALED:
            continue
        reaches = g.target in (SEALED, WAREHOUSE) or (
            g.target == BRONZE and g.privilege not in METADATA_ONLY
        )
        if reaches:
            raise UnsafePolicy(
                f"{g.identity} would get {g.privilege!r} on {g.target}: "
                "that reaches the test window (contract rule 4)"
            )


def grant_requests(
    plan: list[Grant], user_ids: dict[str, str], warehouse_id: str, namespace_ids: dict[str, str]
) -> list[tuple[str, dict]]:
    """Turn the plan into (path, body) Grants API calls, one per target."""
    by_target: dict[str, list[dict]] = {}
    for g in plan:
        by_target.setdefault(g.target, []).append(
            {"principal": {"user": user_ids[g.identity]}, "privilege": g.privilege}
        )
    calls = []
    for target, writes in sorted(by_target.items()):
        base = f"/management/v1/warehouse/{warehouse_id}"
        path = (
            f"{base}/grants"
            if target == WAREHOUSE
            else (f"{base}/namespace/{namespace_ids[target]}/grants")
        )
        calls.append((path, {"writes": writes, "deletes": []}))
    return calls
