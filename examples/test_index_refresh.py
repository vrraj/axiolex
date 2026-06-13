#!/usr/bin/env python3
"""Refresh and inspect the caller-owned Axiolex Redis tool catalog."""

import argparse
import asyncio
import json

from axiolex import ToolIndexingService
from dotenv import load_dotenv


load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Axiolex indexing from local YAML configuration"
    )
    parser.add_argument("--tools-file", required=True)
    parser.add_argument("--providers-file", required=True)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow enabled MCP providers to return no tools",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    service = ToolIndexingService(
        tools_file=args.tools_file,
        providers_file=args.providers_file,
        allow_partial=args.allow_partial,
    )

    result = await service.refresh()
    print("Refresh result:")
    print(json.dumps(result.to_dict(), indent=2))

    status = service.status()
    print("\nCatalog status:")
    print(json.dumps(status, indent=2))

    assert status["tool_count"] == result.total_tools
    assert status["incomplete_runtime_tools"] == []
    assert status["catalog_version"]
    print("\nIndex refresh test passed.")


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
