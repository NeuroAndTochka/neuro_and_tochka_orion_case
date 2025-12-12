from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.client import Config

from ingestion_service.config import Settings


class StorageClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.local_storage_path: Optional[Path] = settings.local_storage_path if settings.mock_mode else None

        self.bucket = settings.s3_bucket
        self._s3_client = None
        if settings.s3_bucket and settings.s3_access_key and settings.s3_secret_key:
            session = boto3.session.Session(
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region or "us-east-1",
            )
            self._s3_client = session.client(
                "s3",
                endpoint_url=settings.s3_endpoint,
                config=Config(signature_version="s3v4"),
                use_ssl=settings.s3_secure,
                verify=settings.s3_secure,
            )
        if self.local_storage_path:
            self.local_storage_path.mkdir(parents=True, exist_ok=True)

    def upload(self, tenant_id: str, filename: str, content: bytes) -> str:
        ext = Path(filename).suffix or ".bin"
        key = f"{tenant_id}/{uuid.uuid4().hex}{ext}"

        if self._s3_client:
            bucket = self.bucket
            assert bucket, "S3 bucket must be configured"
            self._s3_client.put_object(Bucket=bucket, Key=key, Body=content)
            return f"s3://{bucket}/{key}"

        if self.local_storage_path:
            target = self.local_storage_path / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return f"local://{key}"

        # fallback to filesystem path
        target = Path(self.settings.storage_path) / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target.as_uri()

    def resolve_local_path(self, storage_uri: str) -> Path:
        parsed = urlparse(storage_uri)
        if parsed.scheme == "local" and self.local_storage_path:
            return (self.local_storage_path / (parsed.netloc + parsed.path).lstrip("/")).resolve()
        return Path(storage_uri.replace("file://", ""))
