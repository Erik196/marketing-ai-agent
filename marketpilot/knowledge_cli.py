"""Index or inspect knowledge retrieval independently of the marketing agent."""

import argparse
import asyncio
import json
import sys

from openai import APIConnectionError, APIStatusError

from marketpilot.retrieval import build_index, retrieve_knowledge


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MarketPilot Markdown knowledge base")
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="Build real embeddings; reuse an unchanged index")
    index.add_argument("--force", action="store_true", help="Re-embed even when the index is current")
    search = commands.add_parser("search", help="Inspect retrieved passages without generating an answer")
    search.add_argument("query")
    search.add_argument("--mode", choices=["keyword", "semantic", "hybrid"], default="hybrid")
    search.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        if args.command == "index":
            result = asyncio.run(build_index(force=args.force))
        else:
            result = asyncio.run(retrieve_knowledge(args.query, args.mode, args.top_k))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except APIConnectionError:
        print("Could not connect to OpenAI for embeddings. Check network access.", file=sys.stderr)
        return 1
    except APIStatusError as exc:
        print(f"Embedding request failed (HTTP {exc.status_code}). Check API credentials, credits, and model access.",
              file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
