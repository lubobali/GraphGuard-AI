"""The transaction message on the `transactions` topic (S6.5), shared by replayer and consumer.

JSON with a `schema_version`, the transaction's own fields, `event_id` (= `source_row`, the
transaction key) and `seq` (its position in the replay). **Never the label**: whether a
transaction was laundering is not known when it happens; labels arrive later on their own
(S6.9). Amounts are written with `repr`, so they come back bit for bit.

Version 2 adds an optional `channel` field (the replayer switches mid-stream to prove that a
schema change does not break readers); every reader accepts 1 and 2.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

VERSIONS = (1, 2)
FIELDS = ("from_bank", "from_account", "to_bank", "to_account", "amount_received",
          "receiving_currency", "amount_paid", "payment_currency", "payment_format")  # fmt: skip


class MalformedRecord(ValueError):
    """A record that is not a valid transaction message. Goes to the dead-letter topic."""


@dataclass(frozen=True)
class Transaction:
    event_id: int
    seq: int
    timestamp: dt.datetime
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount_received: float
    receiving_currency: str
    amount_paid: float
    payment_currency: str
    payment_format: str
    schema_version: int = 1


def encode(row: dict, seq: int, schema_version: int = 1) -> bytes:
    body = {"schema_version": schema_version, "event_id": int(row["source_row"]), "seq": seq,
            "timestamp": row["timestamp"].isoformat()}  # fmt: skip
    body.update({f: row[f] for f in FIELDS})
    if schema_version >= 2:
        body["channel"] = "online"
    return json.dumps(body, separators=(",", ":")).encode()


def decode(raw: bytes | None) -> Transaction:
    try:
        body = json.loads(raw or b"")
    except (ValueError, UnicodeDecodeError) as e:
        raise MalformedRecord(f"not JSON: {e}") from None
    if not isinstance(body, dict):
        raise MalformedRecord("not a JSON object")
    if body.get("schema_version") not in VERSIONS:
        raise MalformedRecord(f"unknown schema_version {body.get('schema_version')!r}")
    missing = [f for f in ("event_id", "seq", "timestamp", *FIELDS) if f not in body]
    if missing:
        raise MalformedRecord(f"missing {missing}")
    try:
        return Transaction(
            event_id=int(body["event_id"]), seq=int(body["seq"]),
            timestamp=dt.datetime.fromisoformat(body["timestamp"]),
            from_bank=str(body["from_bank"]), from_account=str(body["from_account"]),
            to_bank=str(body["to_bank"]), to_account=str(body["to_account"]),
            amount_received=float(body["amount_received"]),
            receiving_currency=str(body["receiving_currency"]),
            amount_paid=float(body["amount_paid"]), payment_currency=str(body["payment_currency"]),
            payment_format=str(body["payment_format"]), schema_version=body["schema_version"],
        )  # fmt: skip
    except (TypeError, ValueError) as e:
        raise MalformedRecord(f"bad field: {e}") from None
