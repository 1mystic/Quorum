import asyncio
import os
import re
from typing import BinaryIO
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile

from app.core.config import settings
from app.exceptions import (
    StorageError, StorageNotConfiguredError, InvalidFileTypeError, FileTooLargeError
)


ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
}

IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024

MAX_FILENAME_LENGTH = 60
UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9._-]+")

CERTIFICATE_FOLDER = "certificates"
CERTIFICATE_CONTENT_TYPE = "application/pdf"

CLUB_FOLDER = "clubs"
EVENT_FOLDER = "events"
AVATAR_FOLDER = "avatars"


class Storage:
    def __init__(self):
        self.bucket = settings.S3_BUCKET_NAME
        self.region = settings.AWS_REGION
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.bucket:
                raise StorageNotConfiguredError()
            self._client = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    async def upload(self, file: bytes | BinaryIO, folder: str, content_type: str,
                     filename: str | None = None, key: str | None = None) -> str:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise InvalidFileTypeError()

        if key is None:
            name = uuid4().hex
            if filename:
                stem = UNSAFE_CHARS.sub("-", os.path.basename(filename))
                stem = stem.rsplit(".", 1)[0].strip("-.")[:MAX_FILENAME_LENGTH]
                if stem:
                    name = f"{name}-{stem}"
            key = f"{folder.strip('/')}/{name}{ALLOWED_CONTENT_TYPES[content_type]}"

        try:
            await asyncio.to_thread(
                self.client.put_object,
                Bucket=self.bucket,
                Key=key,
                Body=file,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError() from exc
        return key

    async def upload_image(self, file: UploadFile, folder: str) -> str:
        if file.content_type not in IMAGE_CONTENT_TYPES:
            raise InvalidFileTypeError()
        data = await file.read()
        if len(data) > MAX_IMAGE_BYTES:
            raise FileTooLargeError()
        key = await self.upload(data, folder, file.content_type, filename=file.filename)
        return self.get_url(key)

    def _key_from_url(self, url: str) -> str | None:
        prefix = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/"
        if url.startswith(prefix):
            return url[len(prefix):]
        return None

    async def delete_url(self, url: str | None) -> None:
        if not url or not self.bucket:
            return
        key = self._key_from_url(url)
        if not key:
            return
        try:
            await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError):
            pass

    async def upload_certificate(self, file: UploadFile) -> str:
        filename = file.filename or ""
        if file.content_type != CERTIFICATE_CONTENT_TYPE or not filename.lower().endswith(".pdf"):
            raise InvalidFileTypeError()
        return await self.upload(
            await file.read(), CERTIFICATE_FOLDER, CERTIFICATE_CONTENT_TYPE, filename
        )

    def get_url(self, key: str, signed: bool = False, expires_in: int = 3600) -> str:
        if signed:
            try:
                return self.client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=expires_in,
                )
            except (BotoCoreError, ClientError) as exc:
                raise StorageError() from exc

        if not self.bucket:
            raise StorageNotConfiguredError()
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"


storage = Storage()
