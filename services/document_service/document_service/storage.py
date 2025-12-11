from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.client import Config


class StorageClient:
    def __init__(
        self,
        bucket: Optional[str],
        endpoint: Optional[str],
        access_key: Optional[str],
        secret_key: Optional[str],
        region: Optional[str],
        secure: bool,
        local_storage_path: Optional[Path],
        default_expiry: int = 300,
    ) -> None:
        self.bucket = bucket
        self.default_expiry = default_expiry
        self.local_storage_path = local_storage_path
        if self.local_storage_path:
            self.local_storage_path.mkdir(parents=True, exist_ok=True)

        self._s3_client = None
        if bucket and access_key and secret_key:
            session = boto3.session.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region or "us-east-1",
            )
            self._s3_client = session.client(
                "s3",
                endpoint_url=endpoint,
                config=Config(signature_version="s3v4"),
                use_ssl=secure,
                verify=secure,
            )

    def generate_download_url(self, storage_uri: str, expires_in: Optional[int] = None) -> str:
        if not storage_uri:
            raise ValueError("storage URI is empty")
        parsed = urlparse(storage_uri)
        scheme = parsed.scheme or "file"

        if scheme == "s3":
            if self._s3_client is None:
                raise RuntimeError("S3 storage is not configured")
            bucket = parsed.netloc or self.bucket
            if not bucket:
                raise RuntimeError("S3 bucket is not configured")
            key = parsed.path.lstrip("/")
            return self._s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in or self.default_expiry,
            )

        if scheme == "file":
            return storage_uri

        if scheme == "local":
            if not self.local_storage_path:
                raise RuntimeError("Local storage path is not configured")
            relative = (parsed.netloc + parsed.path).lstrip("/")
            target = (self.local_storage_path / relative).resolve()
            return target.as_uri()

        raise ValueError(f"Unsupported storage scheme: {scheme}")
