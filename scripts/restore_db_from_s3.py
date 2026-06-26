#!/usr/bin/env python3
"""Restore SQLite DB from Timeweb S3 on app startup (migration / disaster recovery)."""
import os
import sys
from pathlib import Path


def main() -> int:
    endpoint = os.environ.get("S3_ENDPOINT", "").strip()
    bucket = os.environ.get("S3_BUCKET", "").strip()
    key = os.environ.get("S3_DB_KEY", "").strip()
    db_path = Path(os.environ.get("DATABASE_PATH", "/app/data/blacksquare_stock_crm_v2.db"))

    if not (endpoint and bucket and key):
        print("S3 restore skipped: S3_ENDPOINT/S3_BUCKET/S3_DB_KEY not set", flush=True)
        return 0

    access = os.environ.get("S3_ACCESS_KEY", "").strip()
    secret = os.environ.get("S3_SECRET_KEY", "").strip()
    if not (access and secret):
        print("S3 restore skipped: S3 credentials missing", flush=True)
        return 0

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        fallback = Path("/app/data/blacksquare_stock_crm_v2.db")
        print(f"S3 restore: {db_path.parent} not writable, using {fallback}", flush=True)
        db_path = fallback
        db_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ["DATABASE_PATH"] = str(db_path)
    force = os.environ.get("S3_RESTORE_ON_START", "").strip() in ("1", "true", "yes")
    if db_path.exists() and db_path.stat().st_size > 0 and not force:
        print(f"S3 restore skipped: database already exists ({db_path.stat().st_size} bytes)", flush=True)
        return 0

    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        print("S3 restore failed: boto3 not installed", file=sys.stderr, flush=True)
        return 1

    region = os.environ.get("S3_REGION", "ru-1")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
        config=Config(signature_version="s3v4"),
    )
    tmp = db_path.with_suffix(".db.download")
    print(f"S3 restore: s3://{bucket}/{key} -> {db_path}", flush=True)
    client.download_file(bucket, key, str(tmp))
    tmp.replace(db_path)
    print(f"S3 restore OK ({db_path.stat().st_size} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
