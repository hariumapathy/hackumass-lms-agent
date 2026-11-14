"""Command-line entry point: `uv run app <command>`.

Commands are added by their specs: `openapi` (S02), `seed` (S03), `evals` (S26), `worker` (S10).
"""

import json
import sys


def _openapi() -> int:
    from app.main import create_app

    print(json.dumps(create_app().openapi(), indent=2))
    return 0


COMMANDS = {"openapi": _openapi}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in {"-h", "--help"}:
        print("usage: app <command>\n\ncommands: openapi (S02); seed, worker, evals come later")
        return 0
    command = COMMANDS.get(args[0])
    if command is None:
        print(f"unknown command: {args[0]}", file=sys.stderr)
        return 2
    return command()


if __name__ == "__main__":
    raise SystemExit(main())
