"""Object storage adapter (S3 API). The only place allowed to import boto3 (ADR-0011).

SeaweedFS locally and in CI, Cloudflare R2 in production; any S3-API store works. Callers use `ObjectStore`.
"""

from __future__ import annotations

from typing import Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, *, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


class S3ObjectStore:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        access_key_id: str,
        secret_access_key: str,
        region: str = "auto",
    ) -> None:
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
        )

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        body = self._client.get_object(Bucket=self.bucket, Key=key)["Body"]
        return bytes(body.read())

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        return True

    def ensure_bucket(self) -> None:
        """Create the bucket if missing. Local and CI only: production buckets are provisioned by hand."""
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self.bucket)
