"""Command-line entry point: `uv run app <command>`.

Commands are added by their specs: `seed` (S03), `evals` (S26), `worker` (S10).
"""

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in {"-h", "--help"}:
        print("usage: app <command>\n\ncommands come from specs S03 (seed), S10, S26")
        return 0
    print(f"unknown command: {args[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
