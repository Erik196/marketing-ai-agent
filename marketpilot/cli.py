"""One request per CLI invocation; conversation memory comes later."""

import argparse
import asyncio
import sys

from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

from marketpilot.agent import run_marketing_agent


"""
Parses the arguments:
after python -m you have the prompt and then an optional --model with the name of the model to override the default model.
Then it runs the Agent harness function.
"""
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MarketPilot AI — Phase 1 marketing drafts")
    parser.add_argument("prompt", help="Marketing request in quotes")
    parser.add_argument("--model", help="Override MARKETPILOT_MODEL and the default model")
    args = parser.parse_args(argv)

    try:
        output = asyncio.run(run_marketing_agent(args.prompt, args.model))
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
    except KeyboardInterrupt:
        print("Request interrupted.", file=sys.stderr)
        return 130

    print(output)
    return 0

