"""The investigator's tools over MCP (S7.10), so any MCP client can use them.

    python -m graphguard.agent.mcp_server          # stdio; reads as demo_reader

The same four read-only tools as `agent/tools.py`, here taking the alert id (an MCP client
works across alerts; the eval runner binds each tool to one alert instead). Nothing else is
exposed: no resources, no prompts, no write.
"""

from __future__ import annotations

import functools
import json
import sys

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from graphguard.agent import tools
from graphguard.demo.queries import to_json

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)


@functools.cache
def _repo():
    from graphguard.demo.queries import PgRepo

    return PgRepo()


def build(repo_factory=_repo) -> MCPServer:
    server = MCPServer(
        "graphguard-investigator",
        instructions="Read-only tools over one synthetic AML alert (IBM AMLworld). "
        "Each takes the alert's transaction id.",
    )

    def register(name: str, doc: str):
        fn = getattr(tools, name)

        def tool(event_id: int) -> dict:
            # dates and decimals as plain JSON, as the API sends them
            return json.loads(to_json(fn(repo_factory(), event_id)))

        tool.__name__, tool.__doc__ = name, doc
        server.tool(name=name, description=doc, annotations=READ_ONLY)(tool)

    register("get_alert", "The alerted payment: who paid whom, amount, time, rank, rules.")
    register("get_reasons", "Why the model ranked it: plain reasons, top contributions.")
    register("get_ring", "The money flow around the alert, as it was before the alert.")
    register("get_history", "Each account's 20 most recent earlier payments.")
    return server


def main(argv: list[str]) -> int:
    build().run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
