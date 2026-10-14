"""One request per CLI invocation; conversation memory comes later."""

import argparse
import asyncio
import sys
import sqlite3

from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError
from agents import AgentsException

from marketpilot.agent import run_marketing_agent


def main(argv: list[str] | None = None) -> int:
    """Parse terminal arguments, run the agent, and display the result."""
    parser = argparse.ArgumentParser(description="MarketPilot AI — marketing tools and drafts")
    parser.add_argument("prompt", help="Marketing request in quotes")
    parser.add_argument("--model", help="Override MARKETPILOT_MODEL and the default model")
    parser.add_argument("--quiet-tools", action="store_true", help="Hide status messages; still save execution logs")
    parser.add_argument("--campaign", action="store_true", help="Return a structured campaign report rendered as Markdown")
    args = parser.parse_args(argv)

    try:
        # stderr keeps progress separate from the final answer on stdout.
        notify = None if args.quiet_tools else lambda message: print(message, file=sys.stderr, flush=True)
        output = asyncio.run(run_marketing_agent(args.prompt, args.model, notify=notify, campaign=args.campaign))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except AuthenticationError:
        print("API authentication failed. Check your local OPENAI_API_KEY.", file=sys.stderr)
        return 1
    except RateLimitError:
        print("API quota or rate limit reached. Check your API account billing and limits.", file=sys.stderr)
        return 1
    except APIConnectionError:
        print("Could not connect to OpenAI. Check network access.", file=sys.stderr)
        return 1
    except APIStatusError as exc:
        # Avoid dumping raw API errors, headers, or credentials.
        print(f"OpenAI request failed (HTTP {exc.status_code}). Check model access and API configuration.", file=sys.stderr)
        return 1
    except AgentsException as exc:
        print(f"Agent execution failed ({type(exc).__name__}). Inspect the execution log.", file=sys.stderr)
        return 1
    except OSError:
        print("Could not save the execution log. Check write access to data/runs.", file=sys.stderr)
        return 1
    except sqlite3.Error:
        print("Could not save workflow state in SQLite. Check data/workflows.db and write access.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Request interrupted.", file=sys.stderr)
        return 130

    print(output)
    return 0

