from __future__ import annotations

import argparse
import sys

from .env import load_env_file
from .orchestrator import SafeTripOrchestrator


DEFAULT_EXAMPLE = (
    "I booked a Phuket villa from a Facebook page and transferred 12000 THB. "
    "The real hotel says there is no booking."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SafeTrip AI agent.")
    parser.add_argument(
        "--message",
        help="Process one tourist incident message and exit.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start an interactive chat loop.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show orchestrator/tool progress while the agent runs.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Load environment variables from this file before starting.",
    )
    return parser.parse_args()


def chat_loop(orchestrator: SafeTripOrchestrator) -> None:
    print("SafeTrip AI agent is ready. Type an incident or 'exit' to quit.")
    print("Type 'reset' to start a new incident in the same session.")

    while True:
        try:
            user_input = input("\nTourist> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting SafeTrip AI agent.")
            return

        if user_input.lower() in {"exit", "quit", "q"}:
            print("Exiting SafeTrip AI agent.")
            return
        if user_input.lower() in {"reset", "/reset"}:
            orchestrator.reset()
            print("Case memory reset.")
            continue
        if not user_input:
            continue

        try:
            result = orchestrator.process(user_input)
            print(f"\nSafeTrip AI> {result.final_text}")
        except Exception as exc:
            print(f"\nSafeTrip AI error> {format_runtime_error(exc)}")


def format_runtime_error(exc: Exception) -> str:
    message = str(exc)
    if "API_KEY_INVALID" in message or "API key not valid" in message:
        return (
            "Gemini rejected the API key. Create a valid Google AI Studio key, "
            "put it in .env as GEMINI_API_KEY=..., and run again."
        )
    if "Missing GEMINI_API_KEY" in message or "Missing OPENAI_API_KEY" in message:
        return message
    if "Unsupported SAFETRIP_MODEL_PROVIDER" in message:
        return message
    return f"{exc.__class__.__name__}: {message}"


def main() -> int:
    args = parse_args()
    load_env_file(args.env_file)

    try:
        orchestrator = SafeTripOrchestrator(verbose=args.verbose)
    except Exception as exc:
        print(f"Startup error: {format_runtime_error(exc)}", file=sys.stderr)
        return 1

    if args.interactive:
        chat_loop(orchestrator)
        return 0

    try:
        result = orchestrator.process(args.message or DEFAULT_EXAMPLE)
        print(result.final_text)
        return 0
    except Exception as exc:
        print(f"SafeTrip AI error> {format_runtime_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

