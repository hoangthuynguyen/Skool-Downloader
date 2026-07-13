"""
Cloudflare R2 (S3-compatible) client.

Can: pip install boto3
Cau hinh trong app/.settings.json -> cloud.r2
"""
from __future__ import annotations

from pathlib import Path


def _client(cfg):
    import boto3
    from botocore.config import Config as BotoConfig
    account = (cfg.get("account_id") or "").strip()
    access = (cfg.get("access_key") or "").strip()
    secret = (cfg.get("secret_key") or "").strip()
    endpoint = (cfg.get("endpoint") or "").strip()
    if not endpoint and account:
        endpoint = f"https://{account}.r2.cloudflarestorage.com"
    if not (endpoint and access and secret):
        raise RuntimeError("Thieu R2 endpoint/access_key/secret_key trong cai dat cloud.")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=cfg.get("region") or "auto",
        config=BotoConfig(signature_version="s3v4"),
    )


def test_connection(cfg):
    """List bucket (1 lan) de kiem tra key. Tra ve (ok, message)."""
    try:
        c = _client(cfg)
        bucket = (cfg.get("bucket") or "").strip()
        if not bucket:
            return False, "Chưa nhập bucket."
        c.head_bucket(Bucket=bucket)
        return True, f"OK — bucket `{bucket}` truy cập được."
    except Exception as e:
        return False, str(e)


def upload_file(cfg, local_path, key, extra_args=None):
    c = _client(cfg)
    bucket = (cfg.get("bucket") or "").strip()
    local_path = Path(local_path)
    kwargs = {"Filename": str(local_path), "Bucket": bucket, "Key": key}
    if extra_args:
        kwargs["ExtraArgs"] = extra_args
    c.upload_file(**kwargs)
    return key


def download_file(cfg, key, local_path):
    """Tai object R2 ve local (Sprint D restore)."""
    c = _client(cfg)
    bucket = (cfg.get("bucket") or "").strip()
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    c.download_file(bucket, key, str(local_path))
    return local_path


def object_exists(cfg, key):
    c = _client(cfg)
    bucket = (cfg.get("bucket") or "").strip()
    try:
        c.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def remote_key(course_name, rel_path, prefix=""):
    """courses/<course>/<rel> tren R2."""
    course_name = course_name or "SkoolCourse"
    rel = str(rel_path).replace("\\", "/").lstrip("/")
    base = f"courses/{course_name}/{rel}"
    prefix = (prefix or "").strip().strip("/")
    return f"{prefix}/{base}" if prefix else base
