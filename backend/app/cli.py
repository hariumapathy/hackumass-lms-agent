"""Command-line entry point: `uv run app <command>`.

Commands are added by their specs: `openapi` (S02), `seed` (S03), `evals` (S26), `worker` (S10).
"""

import json
import sys


def _openapi() -> int:
    from app.main import create_app

    print(json.dumps(create_app().openapi(), indent=2))
    return 0


def _evals(argv: list[str]) -> int:
    """S26: golden questions against the real agent (mock semester until the S03 seed)."""
    import argparse
    import asyncio
    import os

    parser = argparse.ArgumentParser(prog="app evals")
    parser.add_argument("--only", help="comma-separated golden ids, e.g. G01,G05")
    parser.add_argument("--model", help="Gemini model id (overrides GEMINI_MODEL)")
    parser.add_argument("--delay", type=float, default=4.0, help="seconds between questions")
    opts = parser.parse_args(argv)
    if opts.model:
        os.environ["GEMINI_MODEL"] = opts.model
    os.environ["CHAT_MODE"] = "agent"

    from app.core.settings import get_settings
    from app.evals import EVALS_DIR, format_table, load_cases, run_all, summarize, write_report
    from app.main import create_app

    get_settings.cache_clear()
    settings = get_settings()
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set in .env", file=sys.stderr)
        return 2
    runtime = create_app().state.chat_runtime
    cases = load_cases()
    if opts.only:
        wanted = set(opts.only.split(","))
        cases = [c for c in cases if c.id in wanted]
    results = asyncio.run(run_all(runtime, cases, delay_s=opts.delay))
    summary = summarize(results, f"gemini/{settings.gemini_model}")
    print(format_table(results, summary))
    print(f"report: {write_report(results, summary, EVALS_DIR / 'reports')}.json/.md")
    return 0


COMMANDS = {"openapi": lambda _argv: _openapi(), "evals": _evals}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in {"-h", "--help"}:
        print("usage: app <command>\n\ncommands: openapi (S02), evals (S26); seed, worker later")
        return 0
    command = COMMANDS.get(args[0])
    if command is None:
        print(f"unknown command: {args[0]}", file=sys.stderr)
        return 2
    return command(args[1:])


if __name__ == "__main__":
    raise SystemExit(main())
