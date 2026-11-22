"""The MCP server exposes exactly the four read-only tools, nothing else (S7.10)."""

import asyncio
import datetime as dt
import json

import pytest

from graphguard.agent import mcp_server, tools

pytestmark = pytest.mark.unit
ALERT = {"event_id": 10, "event_time": "2022-09-07 12:00:00", "to_name": "Corp B",
         "amount_paid": 9500.0}  # fmt: skip
GET_ALERT_KEYS = ("from_name", "from_bank_name", "to_bank_name", "payment_currency",
                  "amount_received", "receiving_currency", "payment_format", "rank",
                  "percentile", "cold_policy", "rules", "rule_text")  # fmt: skip


class Repo:
    def alert(self, event_id):
        return {**dict.fromkeys(GET_ALERT_KEYS), **ALERT} if event_id == 10 else None


def test_exactly_the_four_read_only_tools():
    s = mcp_server.build(Repo)
    listed = asyncio.run(s.list_tools())
    assert [t.name for t in listed] == list(tools.TOOLS)
    for t in listed:
        assert t.annotations.read_only_hint and not t.annotations.destructive_hint
        assert list(t.input_schema["properties"]) == ["event_id"]
    assert asyncio.run(s.list_resources()) == [] and asyncio.run(s.list_prompts()) == []


def test_a_call_returns_the_same_data_as_the_tool_as_plain_json(monkeypatch):
    class DatedRepo(Repo):
        def alert(self, event_id):
            a = super().alert(event_id)
            return a and {**a, "event_time": dt.datetime(2022, 9, 7, 12, 0)}

    res = asyncio.run(mcp_server.build(DatedRepo).call_tool("get_alert", {"event_id": 10}))
    got = json.loads(res.content[0].text)
    assert got["event_time"] == "2022-09-07 12:00:00"
    assert got["amount_paid"] == ALERT["amount_paid"] and got["to_name"] == "Corp B"
