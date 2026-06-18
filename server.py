import os
import sys
from pathlib import Path


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    threads = int(os.environ.get("WAITRESS_THREADS", "1"))
    database_path = os.environ.get("DATABASE_PATH", "")

    if database_path:
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    print(
        f"LAUNCH BlackSquare CRM host={host} port={port} "
        f"database={database_path or 'default'} threads={threads}",
        flush=True,
    )

    from waitress import serve

    print("BOOTSTRAP BlackSquare CRM importing Flask application", flush=True)
    from app import DB, app

    print(
        f"STARTING BlackSquare CRM host={host} port={port} "
        f"database={DB} threads={threads}",
        flush=True,
    )

    print("READY BlackSquare CRM is handing requests to Waitress", flush=True)

    serve(
        app,
        host=host,
        port=port,
        threads=threads,
        ident="BlackSquare CRM",
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL BlackSquare CRM failed to start: {exc}", file=sys.stderr, flush=True)
        raise
