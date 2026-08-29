import pytest
from unittest.mock import MagicMock
from fastapi import UploadFile
from app.core.storage import Storage, MAX_IMAGE_BYTES
from app.exceptions import (
    StorageNotConfiguredError, InvalidFileTypeError, FileTooLargeError
)


def test_key_from_url():
    """Verify that _key_from_url extracts the S3 key from a valid S3 URL"""
    storage = Storage()
    storage.bucket = "test-bucket"
    storage.region = "us-east-1"
    url = "https://test-bucket.s3.us-east-1.amazonaws.com/avatars/my-avatar.jpg"
    assert storage._key_from_url(url) == "avatars/my-avatar.jpg"


def test_key_from_invalid_url():
    """Verify that _key_from_url returns None for invalid or mismatched URLs"""
    storage = Storage()
    storage.bucket = "test-bucket"
    storage.region = "us-east-1"
    url = "https://other-bucket.s3.us-east-1.amazonaws.com/avatars/my-avatar.jpg"
    assert storage._key_from_url(url) is None


def test_get_url_unconfigured():
    """Verify that get_url raises StorageNotConfiguredError when the bucket name is empty"""
    storage = Storage()
    storage.bucket = ""
    with pytest.raises(StorageNotConfiguredError):
        storage.get_url("avatars/my-avatar.jpg")


def test_get_url():
    """Verify that get_url formats the public S3 URL correctly when configured"""
    storage = Storage()
    storage.bucket = "test-bucket"
    storage.region = "us-east-1"
    assert storage.get_url("avatars/my-avatar.jpg") == "https://test-bucket.s3.us-east-1.amazonaws.com/avatars/my-avatar.jpg"


@pytest.mark.asyncio
async def test_upload_invalid_type():
    """Verify that upload raises InvalidFileTypeError for non-allowed MIME types"""
    storage = Storage()
    with pytest.raises(InvalidFileTypeError):
        await storage.upload(b"bytes", "avatars", "application/zip")


@pytest.mark.asyncio
async def test_upload_image_invalid_type():
    """Verify that upload_image raises InvalidFileTypeError for non-image MIME types"""
    storage = Storage()
    file = MagicMock(spec=UploadFile)
    file.content_type = "application/pdf"
    with pytest.raises(InvalidFileTypeError):
        await storage.upload_image(file, "avatars")


@pytest.mark.asyncio
async def test_upload_image_too_large():
    """Verify that upload_image raises FileTooLargeError when image size exceeds the limit"""
    storage = Storage()
    file = MagicMock(spec=UploadFile)
    file.content_type = "image/jpeg"
    async def mock_read():
        return b"A" * (MAX_IMAGE_BYTES + 1)
    file.read = mock_read
    with pytest.raises(FileTooLargeError):
        await storage.upload_image(file, "avatars")


@pytest.mark.asyncio
async def test_upload_cert_invalid_type():
    """Verify that upload_certificate raises InvalidFileTypeError for non-PDF files"""
    storage = Storage()
    file = MagicMock(spec=UploadFile)
    file.content_type = "image/png"
    file.filename = "certificate.png"
    with pytest.raises(InvalidFileTypeError):
        await storage.upload_certificate(file)


@pytest.mark.asyncio
async def test_upload_cert_wrong_ext():
    """Verify that upload_certificate raises InvalidFileTypeError if filename extension is not .pdf"""
    storage = Storage()
    file = MagicMock(spec=UploadFile)
    file.content_type = "application/pdf"
    file.filename = "certificate.txt"
    with pytest.raises(InvalidFileTypeError):
        await storage.upload_certificate(file)
