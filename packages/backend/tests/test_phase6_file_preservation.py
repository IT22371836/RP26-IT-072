import base64
import json
from pathlib import Path

import pytest

from app.main import app
from app.schemas.integration import IntegrationProviderDocument
from app.schemas.provider import ProviderDocumentItem, ProviderPublic
from app.services.file_storage import (
    InvalidDocumentUploadError,
    decode_document_data_url,
    safe_storage_filename,
)
from scripts.verify_phase6_file_preservation import (
    inventory_export,
    verify_copy_manifest,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_document_data_url_is_validated_and_hashed_by_server_path() -> None:
    content = b"phase-6-private-document"
    encoded = base64.b64encode(content).decode()
    decoded, content_type, document_format = decode_document_data_url(
        f"data:application/pdf;base64,{encoded}",
        1024,
    )
    assert decoded == content
    assert content_type == "application/pdf"
    assert document_format == "PDF"
    assert safe_storage_filename("../../NIC copy (final).pdf") == "NIC_copy_final_.pdf"

    with pytest.raises(InvalidDocumentUploadError):
        decode_document_data_url("data:text/plain;base64,SGVsbG8=", 1024)
    with pytest.raises(InvalidDocumentUploadError):
        decode_document_data_url(f"data:application/pdf;base64,{encoded}", 2)


def test_document_models_keep_legacy_and_current_urls_additively() -> None:
    document = ProviderDocumentItem.model_validate(
        {
            "file_id": "doc-1",
            "fileName": "NIC.pdf",
            "fileUrl": "https://legacy.example/NIC.pdf",
            "legacyUrl": "https://legacy.example/NIC.pdf",
            "currentUrl": "gs://bucket/private/providers/P1/identity/doc-1.pdf",
            "contentSha256": "a" * 64,
            "contentType": "application/pdf",
            "sizeBytes": 123,
            "format": "PDF",
            "uploaded_at": "2026-08-05T00:00:00Z",
        }
    )
    assert document.file_url == "https://legacy.example/NIC.pdf"
    assert document.legacy_url == document.file_url
    assert document.current_url.startswith("gs://")

    integration = IntegrationProviderDocument.model_validate(
        {"fileUrl": document.file_url, "futureStorageAttribute": {"keep": True}}
    )
    dumped = integration.model_dump(by_alias=True)
    assert dumped["fileUrl"] == document.file_url
    assert dumped["futureStorageAttribute"] == {"keep": True}


def test_copy_manifest_requires_equal_file_hashes_and_dual_urls(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    copy = tmp_path / "copy.bin"
    source.write_bytes(b"same bytes")
    copy.write_bytes(b"same bytes")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "copies": [
                    {
                        "legacy_url": "https://legacy.example/object",
                        "current_url": "gs://bucket/private/object",
                        "source_path": str(source),
                        "current_path": str(copy),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = verify_copy_manifest(manifest)
    assert result["status"] == "verified"
    assert result["copies_verified"] == 1

    copy.write_bytes(b"changed bytes")
    result = verify_copy_manifest(manifest)
    assert result["status"] == "failed"
    assert result["failures"] == ["copies[0]:sha256_mismatch"]


def test_public_provider_and_customer_firebase_adapter_exclude_private_data() -> None:
    assert "nic" not in ProviderPublic.model_fields
    assert "documents" not in ProviderPublic.model_fields
    customer_source = (
        REPOSITORY_ROOT / "WEB" / "src" / "components" / "CustomerDashboard.tsx"
    ).read_text(encoding="utf-8")
    firebase_source = (
        REPOSITORY_ROOT / "WEB" / "src" / "config" / "firebase.ts"
    ).read_text(encoding="utf-8")
    assert "fetchPublicProviders" in customer_source
    assert "selectedProviderModal.nic" not in customer_source
    assert "nic: _nic" in firebase_source
    assert "documents: _documents" in firebase_source


def test_private_storage_routes_and_rules_exist() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/v1/providers/me/documents/{category}/upload" in paths
    assert "/api/v1/providers/me/documents/{category}/{file_id}/content" in paths
    assert (
        "/api/v1/admin/providers/{provider_id}/documents/{category}/{file_id}/content"
        in paths
    )
    rules = (REPOSITORY_ROOT / "WEB" / "storage.rules").read_text(encoding="utf-8")
    assert "match /private/providers/" in rules
    assert "allow read, write: if false" in rules


def test_checked_in_export_inventory_never_emits_urls() -> None:
    payload = json.loads(
        (
            REPOSITORY_ROOT
            / "WEB"
            / "src"
            / "data"
            / "service-e333a-default-rtdb-export.json"
        ).read_text(encoding="utf-8")
    )
    inventory = inventory_export(payload)
    assert inventory["private_document_urls"] > 0
    assert inventory["tokenized_private_document_urls"] > 0
    assert inventory["values_modified"] == 0
    assert inventory["urls_or_tokens_in_report"] == 0
