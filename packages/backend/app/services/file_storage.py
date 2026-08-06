from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse

from app.core.config import Settings

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "JPG",
    "image/png": "PNG",
    "application/pdf": "PDF",
}
DATA_URL_PATTERN = re.compile(
    r"^data:(?P<content_type>[-\w.]+/[-+\w.]+);base64,(?P<data>[A-Za-z0-9+/=\r\n]+)$"
)


class FileStorageConfigurationError(Exception):
    pass


class InvalidDocumentUploadError(Exception):
    pass


class StoredDocumentNotFoundError(Exception):
    pass


class StoredDocumentIntegrityError(Exception):
    pass


@dataclass(frozen=True)
class StoredDocument:
    file_url: str
    current_url: str
    storage_path: str
    content_sha256: str
    content_type: str
    format: str
    size_bytes: int


@dataclass(frozen=True)
class DownloadedDocument:
    content: bytes
    content_type: str


def decode_document_data_url(data_url: str, max_bytes: int) -> tuple[bytes, str, str]:
    match = DATA_URL_PATTERN.fullmatch(data_url.strip())
    if match is None:
        raise InvalidDocumentUploadError("Document must be a base64 data URL")
    content_type = match.group("content_type").lower()
    document_format = ALLOWED_CONTENT_TYPES.get(content_type)
    if document_format is None:
        raise InvalidDocumentUploadError("Only JPG, PNG, and PDF documents are allowed")
    try:
        content = base64.b64decode(match.group("data"), validate=True)
    except (binascii.Error, ValueError) as error:
        raise InvalidDocumentUploadError("Document data is not valid base64") from error
    if not content:
        raise InvalidDocumentUploadError("Document is empty")
    if len(content) > max_bytes:
        raise InvalidDocumentUploadError("Document exceeds the configured size limit")
    return content, content_type, document_format


def safe_storage_filename(file_name: str) -> str:
    name = PurePosixPath(file_name.replace("\\", "/")).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return (sanitized or "document")[:180]


class FirebaseDocumentStorage:
    """Private Firebase Storage adapter; it never creates public download URLs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _firebase_app(self):
        project_id = self.settings.firebase_project_id
        bucket_name = self.settings.firebase_storage_bucket
        if not project_id or not bucket_name:
            raise FileStorageConfigurationError("Firebase document storage is not configured")
        try:
            import firebase_admin

            app_name = f"weda-auth-{project_id}"
            try:
                return firebase_admin.get_app(app_name)
            except ValueError:
                return firebase_admin.initialize_app(
                    options={"projectId": project_id, "storageBucket": bucket_name},
                    name=app_name,
                )
        except FileStorageConfigurationError:
            raise
        except Exception as error:
            raise FileStorageConfigurationError(
                "Firebase Admin could not initialize document storage"
            ) from error

    def upload(
        self,
        *,
        provider_id: str,
        user_id: str,
        category: str,
        file_id: str,
        file_name: str,
        data_url: str,
    ) -> StoredDocument:
        bucket_name = self.settings.firebase_storage_bucket
        if not bucket_name:
            raise FileStorageConfigurationError("Firebase storage bucket is not configured")
        content, content_type, document_format = decode_document_data_url(
            data_url,
            self.settings.document_upload_max_bytes,
        )
        digest = hashlib.sha256(content).hexdigest()
        storage_path = (
            f"private/providers/{provider_id}/{category}/"
            f"{file_id}_{safe_storage_filename(file_name)}"
        )
        try:
            from firebase_admin import storage

            bucket = storage.bucket(bucket_name, app=self._firebase_app())
            blob = bucket.blob(storage_path)
            blob.metadata = {
                "wedaProviderId": provider_id,
                "wedaOwnerUserId": user_id,
                "wedaCategory": category,
                "wedaContentSha256": digest,
            }
            blob.upload_from_string(content, content_type=content_type)
        except FileStorageConfigurationError:
            raise
        except Exception as error:
            raise FileStorageConfigurationError("Private document upload failed") from error

        gs_url = f"gs://{bucket_name}/{storage_path}"
        return StoredDocument(
            file_url=gs_url,
            current_url=gs_url,
            storage_path=storage_path,
            content_sha256=digest,
            content_type=content_type,
            format=document_format,
            size_bytes=len(content),
        )

    def download(self, file_url: str, expected_sha256: str | None) -> DownloadedDocument:
        bucket_name = self.settings.firebase_storage_bucket
        if not bucket_name:
            raise FileStorageConfigurationError("Firebase storage bucket is not configured")
        parsed = urlparse(file_url)
        if parsed.scheme != "gs" or parsed.netloc != bucket_name:
            raise StoredDocumentNotFoundError("Document is not in managed private storage")
        storage_path = parsed.path.lstrip("/")
        if not storage_path.startswith("private/providers/"):
            raise StoredDocumentNotFoundError("Document path is outside private storage")
        try:
            from firebase_admin import storage

            bucket = storage.bucket(bucket_name, app=self._firebase_app())
            blob = bucket.blob(storage_path)
            if not blob.exists():
                raise StoredDocumentNotFoundError("Document object does not exist")
            content = blob.download_as_bytes()
            content_type = blob.content_type or "application/octet-stream"
        except StoredDocumentNotFoundError:
            raise
        except FileStorageConfigurationError:
            raise
        except Exception as error:
            raise StoredDocumentNotFoundError("Private document download failed") from error
        if expected_sha256 and hashlib.sha256(content).hexdigest() != expected_sha256:
            raise StoredDocumentIntegrityError("Stored document hash does not match metadata")
        return DownloadedDocument(content=content, content_type=content_type)
