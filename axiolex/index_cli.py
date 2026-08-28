"""CLI for building and inspecting the externally managed Redis tool catalog."""

import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

from .core.cache import RedisConfig, ToolCacheManager
from .services.indexing_service import ToolIndexingService


load_dotenv()


def _shipped_source_dir() -> str:
    """Return the directory containing source_files/, if available."""
    here = os.path.dirname(os.path.abspath(__file__))
    # Shipped inside the package (PyPI install)
    shipped = os.path.join(here, "source_files")
    if os.path.isdir(shipped):
        return shipped
    # Repo root (running from source)
    cwd_source = os.path.join(os.getcwd(), "source_files")
    if os.path.isdir(cwd_source):
        return cwd_source
    return ""


def _cache_manager(args: argparse.Namespace) -> ToolCacheManager:
    password = os.getenv(args.redis_password_env) if args.redis_password_env else None
    return ToolCacheManager(
        RedisConfig(
            host=args.redis_host,
            port=args.redis_port,
            db=args.redis_db,
            password=password,
        )
    )


def main() -> None:
    """Run the one-shot Axiolex index administration CLI."""
    parser = argparse.ArgumentParser(description="Axiolex Redis tool index manager")
    parser.add_argument(
        "--redis-host",
        default=os.getenv("AXIOLEX_REDIS_HOST", "localhost"),
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=int(os.getenv("AXIOLEX_REDIS_PORT", "6380")),
    )
    parser.add_argument(
        "--redis-db",
        type=int,
        default=int(os.getenv("AXIOLEX_REDIS_DB", "0")),
    )
    parser.add_argument("--redis-password-env")

    subparsers = parser.add_subparsers(dest="command", required=True)
    refresh = subparsers.add_parser(
        "refresh",
        aliases=["initialize"],
        help="Atomically rebuild Redis from YAML and enabled MCP providers",
    )
    _shipped = _shipped_source_dir()
    refresh.add_argument(
        "--tools-file",
        default=os.getenv("AXIOLEX_TOOLS_FILE")
        or (os.path.join(_shipped, "tools_list.yaml") if _shipped else None),
        help="YAML tool catalog (default: shipped source_files/tools_list.yaml, or AXIOLEX_TOOLS_FILE)",
    )
    refresh.add_argument(
        "--providers-file",
        default=os.getenv("AXIOLEX_MCP_PROVIDERS_FILE")
        or (os.path.join(_shipped, "mcp_providers.yaml") if _shipped else None),
        help="MCP provider configuration (default: shipped source_files/mcp_providers.yaml, or AXIOLEX_MCP_PROVIDERS_FILE)",
    )
    refresh.add_argument(
        "--allow-partial",
        action="store_true",
        help="Replace the index even when an enabled MCP provider returns no tools",
    )
    subparsers.add_parser("status", help="Inspect the current Redis tool catalog")

    args = parser.parse_args()
    try:
        if args.command in {"refresh", "initialize"}:
            if not args.tools_file or not args.providers_file:
                raise ValueError(
                    "Could not find source_files/tools_list.yaml or "
                    "source_files/mcp_providers.yaml. Specify them with "
                    "--tools-file and --providers-file, or set the "
                    "AXIOLEX_TOOLS_FILE and AXIOLEX_MCP_PROVIDERS_FILE "
                    "environment variables."
                )
        service = ToolIndexingService(
            tools_file=getattr(args, "tools_file", "") or "",
            providers_file=getattr(args, "providers_file", "") or "",
            cache_manager=_cache_manager(args),
            allow_partial=getattr(args, "allow_partial", False),
        )
        if args.command in {"refresh", "initialize"}:
            result = asyncio.run(service.refresh()).to_dict()
        else:
            result = service.status()
        print(json.dumps({"success": True, **result}, indent=2))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
