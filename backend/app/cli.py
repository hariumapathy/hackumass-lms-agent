"""Command-line entry point: `uv run app <command>`.

Commands are added by their specs: `openapi` (S02), `seed` (S03), `evals` (S26), `worker` (S10).
"""

import argparse
import asyncio
import json
import os
import sys
import time


def _openapi() -> int:
    from app.main import create_app

    print(json.dumps(create_app().openapi(), indent=2))
    return 0


def _seed(argv: list[str]) -> int:
    """S03: load the demo semester for one student account."""
    parser = argparse.ArgumentParser(prog="app seed", description="Load the S03 seed semester.")
    parser.add_argument("--user-email", default=None, help="account to seed (default demo)")
    parser.add_argument("--password", default=os.environ.get("SEED_PASSWORD"))
    parser.add_argument("--reset", action="store_true", help="replace this account's data")
    parser.add_argument("--embeddings", choices=["fake", "gemini"], default=None)
    args = parser.parse_args(argv)
    return _run_async(_seed_async(args))


async def _seed_async(args: argparse.Namespace) -> int:
    import psycopg
    from psycopg.rows import dict_row

    from app.core.embeddings import EmbeddingsConfigError, get_embeddings
    from app.core.settings import get_settings
    from app.db import seed

    settings = get_settings()
    if args.embeddings:
        settings = settings.model_copy(update={"embeddings_provider": args.embeddings})
    email = args.user_email or seed.DEMO_EMAIL
    try:
        embedder = get_embeddings(settings)  # fail before touching the database
        seed.load_fixtures()
    except (EmbeddingsConfigError, seed.SeedError) as exc:
        print(f"seed: {exc}", file=sys.stderr)
        return 1
    started = time.monotonic()
    key = settings.supabase_service_role_key
    try:
        async with await psycopg.AsyncConnection.connect(
            settings.database_url,
            autocommit=True,
            row_factory=dict_row,  # type: ignore[arg-type]
        ) as conn:
            user_id = await seed.ensure_auth_user(
                conn,
                email,
                args.password,
                supabase_url=settings.supabase_url,
                service_key=key.get_secret_value() if key else None,
            )
            result = await seed.seed_user(conn, user_id, embedder, reset=args.reset)
    except seed.SeedError as exc:
        print(f"seed: {exc}", file=sys.stderr)
        return 1
    counts = ", ".join(f"{k} {v}" for k, v in sorted(result.counts.items()))
    print(
        f"Seeded {email} ({user_id}) with {embedder.name} embeddings in "
        f"{time.monotonic() - started:.1f}s: {counts}"
    )
    if seed.is_local(settings.supabase_url) and args.password is None:
        print(f"Local sign-in: {email} / {seed.LOCAL_DEFAULT_PASSWORD}")
    return 0


def _worker(argv: list[str]) -> int:
    """S10: run the Procrastinate worker (queues `sync` + `process`) with the periodic schedule."""
    from app.core.crypto import CryptoError
    from app.sync.jobs import app as queue_app
    from app.sync.jobs import check_worker_config

    try:
        check_worker_config()  # refuses to start without ENCRYPTION_KEY
    except CryptoError as exc:
        print(f"worker: {exc}", file=sys.stderr)
        return 1
    import app.connectors.registry  # noqa: F401  (registers available connectors)

    async def run() -> None:
        async with queue_app.open_async():
            await queue_app.run_worker_async(queues=["sync", "process"], concurrency=4)

    return _run_async(run())


def _evals(argv: list[str]) -> int:
    """S26: golden questions against the real agent (mock semester until the S03 seed)."""
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
    results: list = []

    async def go() -> None:
        results.extend(await run_all(runtime, cases, delay_s=opts.delay))

    _run_async(go())
    summary = summarize(results, f"gemini/{settings.gemini_model}")
    print(format_table(results, summary))
    print(f"report: {write_report(results, summary, EVALS_DIR / 'reports')}.json/.md")
    return 0


def _run_async(coro) -> int:  # noqa: ANN001
    if sys.platform == "win32":  # psycopg async needs a selector loop on Windows
        return asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)
    return asyncio.run(coro)


COMMANDS = {
    "openapi": lambda _argv: _openapi(),
    "seed": _seed,
    "worker": _worker,
    "evals": _evals,
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in {"-h", "--help"}:
        print(
            "usage: app <command>\n\ncommands: openapi (S02), seed (S03), worker (S10), evals (S26)"
        )
        return 0
    command = COMMANDS.get(args[0])
    if command is None:
        print(f"unknown command: {args[0]}", file=sys.stderr)
        return 2
    return command(args[1:])


if __name__ == "__main__":
    raise SystemExit(main())
