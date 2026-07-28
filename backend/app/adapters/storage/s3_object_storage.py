"""S3-compatible object storage adapter.

Works against MinIO locally (see infra/docker-compose.yml) and any real
S3-compatible service in production — same client, just a different
`endpoint_url`/credentials in configuration. Implements
ObjectStorageRepository (app/domain/career_profile/storage.py).

boto3's client is synchronous; every call here runs it via
`asyncio.to_thread` so it doesn't block the event loop, rather than
pulling in aioboto3 as an extra dependency for what's currently a single
small upload path.
"""

from __future__ import annotations

import asyncio
import json

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.core.exceptions import CareerCompassError


class ObjectStorageError(CareerCompassError):
    code = "OBJECT_STORAGE_ERROR"


class S3ObjectStorageRepository:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.object_storage_bucket
        # Deliberately NOT the same value as endpoint_url below — see
        # Settings.object_storage_public_url's docstring. Using the
        # internal endpoint here would produce photo_url values the
        # browser can never load (it doesn't resolve Docker's internal
        # service names), even though uploads themselves would succeed.
        self._public_base_url = settings.object_storage_public_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            region_name="us-east-1",  # required by boto3's S3 client; MinIO ignores the value
        )
        self._bucket_checked = False

    async def _ensure_bucket_exists(self) -> None:
        """MinIO (unlike some managed S3 setups) does not create a
        bucket just because it's referenced — the first real request to
        a non-existent bucket fails with a 404/400 from MinIO's side,
        which our upload() previously surfaced as a confusing generic
        error. Checked once per process (not per request) since bucket
        existence doesn't change during a run.

        Also sets a public-read bucket policy: MinIO buckets are
        private by default, so uploads to this bucket were succeeding
        while every subsequent attempt to *view* the photo failed with
        an anonymous-access rejection from MinIO — invisible to our own
        error handling since the browser's <img> tag makes that request
        directly, never going through our API or apiClient at all. A
        profile-photo bucket is meant to be publicly viewable by design
        (there's no sensitive-access-control requirement here, unlike
        tenant data in the database), so a public-read policy is the
        correct fix, not a workaround.
        """
        if self._bucket_checked:
            return
        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)
        except (ClientError, BotoCoreError):
            try:
                await asyncio.to_thread(self._client.create_bucket, Bucket=self._bucket)
            except (ClientError, BotoCoreError) as exc:
                # The original exception (surfaced via `from exc` and
                # included in the message) is the actual diagnosis —
                # e.g. a DNS failure connecting to endpoint_url means
                # the backend can't reach the store at all (often a
                # Docker networking misconfiguration), while an auth
                # error means the store is reachable but credentials
                # are wrong. A generic message alone hid this distinction.
                raise ObjectStorageError(
                    f"Object storage bucket '{self._bucket}' does not exist and could not be "
                    f"created. Underlying error: {exc}"
                ) from exc

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self._bucket}/*"],
                }
            ],
        }
        try:
            await asyncio.to_thread(
                self._client.put_bucket_policy, Bucket=self._bucket, Policy=json.dumps(policy)
            )
        except (ClientError, BotoCoreError) as exc:
            raise ObjectStorageError(
                f"Bucket '{self._bucket}' exists but could not be made publicly readable. "
                f"Underlying error: {exc}"
            ) from exc

        self._bucket_checked = True

    async def upload(self, *, key: str, content: bytes, content_type: str) -> str:
        await self._ensure_bucket_exists()
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (ClientError, BotoCoreError) as exc:
            raise ObjectStorageError(f"Failed to upload object '{key}'.") from exc

        return f"{self._public_base_url}/{self._bucket}/{key}"

    async def delete(self, *, key: str) -> None:
        try:
            await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            # Deletion is idempotent from the caller's perspective (see
            # ObjectStorageRepository.delete's docstring) — a "not found"
            # from the provider isn't a real error here, but a transport
            # or auth failure still should surface.
            raise ObjectStorageError(f"Failed to delete object '{key}'.") from exc
