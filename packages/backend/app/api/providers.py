import asyncio
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import (
    get_interaction_repository,
    get_provider_repository,
    require_firebase_role,
)
from app.components.component1.service import (
    HybridRecommendationEngine,
    get_recommendation_engine,
)
from app.components.component4.provider_trust import ProviderTrustProfileService
from app.components.component4.service import (
    ArtifactsUnavailableError,
    ArtifactValidationError,
    Component4RankingEngine,
    UnknownProviderError,
    get_component4_engine,
)
from app.core.config import Settings, get_settings
from app.repositories.concurrency import ProfileConcurrencyError
from app.repositories.interactions import InteractionRepository
from app.repositories.providers import ProviderProfileExistsError, ProviderRepository
from app.schemas.auth import UserPublic
from app.schemas.common import UserRole, new_public_id, utc_now
from app.schemas.provider import (
    ProviderCreate,
    ProviderDocumentCategory,
    ProviderDocumentCreate,
    ProviderDocumentItem,
    ProviderDocumentsPrivate,
    ProviderDocumentUpload,
    ProviderPrivate,
    ProviderProfileUpdate,
    ProviderPublic,
    ProviderTrustProfile,
)
from app.services.file_storage import (
    FileStorageConfigurationError,
    FirebaseDocumentStorage,
    InvalidDocumentUploadError,
    StoredDocumentIntegrityError,
    StoredDocumentNotFoundError,
)

router = APIRouter(prefix="/providers", tags=["providers"])
provider_user = require_firebase_role(UserRole.PROVIDER)


def document_storage_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FirebaseDocumentStorage:
    return FirebaseDocumentStorage(settings)


def component1_engine_dependency(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HybridRecommendationEngine:
    engine = get_recommendation_engine(settings.component1_artifact_dir)
    if not engine.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component 1 artifacts are not loaded",
        )
    return engine


def component4_engine_dependency(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Component4RankingEngine:
    try:
        return get_component4_engine(
            settings.component4_artifact_dir,
            settings.component4_category_priors_path,
        )
    except (ArtifactsUnavailableError, ArtifactValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


@router.post("/me", response_model=ProviderPrivate, status_code=status.HTTP_201_CREATED)
async def create_my_provider_profile(
    payload: ProviderCreate,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPrivate:
    now = utc_now()
    document = {
        **payload.model_dump(),
        "provider_id": new_public_id("P"),
        "user_id": current_user.user_id,
        "rating": 0.0,
        "review_count": 0,
        "booking_success_rate": 0.0,
        "interaction_count": 0,
        "phone": None,
        "location": None,
        "provider_image": None,
        "preferred_language": "English",
        "nic": None,
        "working_hours": None,
        "verified": False,
        "documents": {
            "status": False,
            "verified": False,
            "identity_document": [],
            "certification": [],
            "business_registration": [],
            "experience_proof": [],
            "portfolio_work": [],
        },
        "created_at": now,
        "updated_at": now,
    }
    try:
        await repository.create(document)
    except ProviderProfileExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provider profile already exists",
        ) from error
    return ProviderPrivate.model_validate(document)


def active_document_count(document: dict) -> int:
    documents = document.get("documents")
    if not isinstance(documents, dict):
        return 0
    return sum(
        1
        for category in ProviderDocumentCategory
        for item in documents.get(category.value, [])
        if isinstance(item, dict) and item.get("deleted_at") is None
    )


def ensure_document_actions_unlocked(document: dict) -> None:
    documents = document.get("documents") or {}
    if document.get("verified") or documents.get("status"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document actions are locked during or after verification",
        )


def find_active_document(
    provider: dict,
    category: ProviderDocumentCategory,
    file_id: str,
) -> dict | None:
    documents = provider.get("documents") or {}
    for item in documents.get(category.value, []):
        if (
            isinstance(item, dict)
            and item.get("file_id") == file_id
            and item.get("deleted_at") is None
        ):
            return item
    return None


async def private_document_response(
    item: dict,
    storage: FirebaseDocumentStorage,
) -> Response:
    file_url = item.get("current_url") or item.get("file_url")
    if not isinstance(file_url, str):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        downloaded = await asyncio.to_thread(
            storage.download,
            file_url,
            item.get("content_sha256"),
        )
    except StoredDocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Legacy document requires the controlled storage-copy transition",
        ) from error
    except StoredDocumentIntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stored document failed its integrity check",
        ) from error
    except FileStorageConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private document storage is unavailable",
        ) from error
    file_name = str(item.get("file_name") or "document")
    disposition = f"inline; filename*=UTF-8''{quote(file_name, safe='')}"
    return Response(
        content=downloaded.content,
        media_type=downloaded.content_type,
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/me/documents", response_model=ProviderDocumentsPrivate)
async def get_my_provider_documents(
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderDocumentsPrivate:
    document = await repository.find_by_user_id(current_user.user_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return ProviderDocumentsPrivate.model_validate(document.get("documents") or {})


@router.post("/me/documents/{category}", response_model=ProviderPrivate)
async def add_my_provider_document(
    category: ProviderDocumentCategory,
    payload: ProviderDocumentCreate,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPrivate:
    existing = await repository.find_by_user_id(current_user.user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    ensure_document_actions_unlocked(existing)
    item_data = payload.model_dump(exclude={"file_id"})
    if item_data.get("current_url") is None:
        item_data["current_url"] = payload.file_url
    if item_data.get("legacy_url") is None and payload.file_url.startswith(("http://", "https://")):
        item_data["legacy_url"] = payload.file_url
    item = ProviderDocumentItem(
        **item_data,
        file_id=payload.file_id or new_public_id("D"),
        uploaded_at=utc_now(),
    )
    document = await repository.add_document(
        current_user.user_id,
        category.value,
        item.model_dump(),
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document actions became locked; reload the provider profile",
        )
    return ProviderPrivate.model_validate(document)


@router.post("/me/documents/{category}/upload", response_model=ProviderPrivate)
async def upload_my_provider_document(
    category: ProviderDocumentCategory,
    payload: ProviderDocumentUpload,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
    storage: Annotated[FirebaseDocumentStorage, Depends(document_storage_service)],
) -> ProviderPrivate:
    existing = await repository.find_by_user_id(current_user.user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    ensure_document_actions_unlocked(existing)
    file_id = new_public_id("D")
    try:
        stored = await asyncio.to_thread(
            storage.upload,
            provider_id=str(existing["provider_id"]),
            user_id=current_user.user_id,
            category=category.value,
            file_id=file_id,
            file_name=payload.file_name,
            data_url=payload.data_url,
        )
    except InvalidDocumentUploadError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except FileStorageConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private document storage is unavailable",
        ) from error
    item = ProviderDocumentItem(
        file_id=file_id,
        file_name=payload.file_name,
        file_url=stored.file_url,
        current_url=stored.current_url,
        storage_path=stored.storage_path,
        content_sha256=stored.content_sha256,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        format=stored.format,
        uploaded_at=utc_now(),
    )
    document = await repository.add_document(
        current_user.user_id,
        category.value,
        item.model_dump(),
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document metadata could not be attached; uploaded object was preserved",
        )
    return ProviderPrivate.model_validate(document)


@router.get("/me/documents/{category}/{file_id}/content")
async def download_my_provider_document(
    category: ProviderDocumentCategory,
    file_id: str,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
    storage: Annotated[FirebaseDocumentStorage, Depends(document_storage_service)],
) -> Response:
    provider = await repository.find_by_user_id(current_user.user_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    item = find_active_document(provider, category, file_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return await private_document_response(item, storage)


@router.delete("/me/documents/{category}/{file_id}", response_model=ProviderPrivate)
async def delete_my_provider_document(
    category: ProviderDocumentCategory,
    file_id: str,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPrivate:
    existing = await repository.find_by_user_id(current_user.user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    ensure_document_actions_unlocked(existing)
    document = await repository.soft_delete_document(
        current_user.user_id,
        category.value,
        file_id,
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return ProviderPrivate.model_validate(document)


@router.post("/me/request-document-verification", response_model=ProviderPrivate)
async def request_my_document_verification(
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPrivate:
    existing = await repository.find_by_user_id(current_user.user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    ensure_document_actions_unlocked(existing)
    if active_document_count(existing) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one active document is required before verification",
        )
    document = await repository.request_document_verification(current_user.user_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document actions became locked; reload the provider profile",
        )
    return ProviderPrivate.model_validate(document)


@router.get("/me", response_model=ProviderPrivate)
async def get_my_provider_profile(
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPrivate:
    document = await repository.find_by_user_id(current_user.user_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return ProviderPrivate.model_validate(document)


@router.patch("/me", response_model=ProviderPrivate)
async def update_my_provider_profile(
    payload: ProviderProfileUpdate,
    current_user: Annotated[UserPublic, Depends(provider_user)],
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPrivate:
    existing = await repository.find_by_user_id(current_user.user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    updates = {
        **payload.model_dump(exclude_unset=True, exclude={"expected_updated_at"}),
        "updated_at": utc_now(),
    }
    try:
        if payload.expected_updated_at is None:
            document = await repository.update_by_user_id(current_user.user_id, updates)
        else:
            document = await repository.update_by_user_id(
                current_user.user_id,
                updates,
                expected_updated_at=payload.expected_updated_at,
            )
    except ProfileConcurrencyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provider profile changed; reload it before saving",
        ) from error
    if document is None:
        raise RuntimeError("Provider profile disappeared during update")
    return ProviderPrivate.model_validate(document)


@router.get("/{provider_id}/trust-profile", response_model=ProviderTrustProfile)
async def get_provider_trust_profile(
    provider_id: str,
    providers: Annotated[ProviderRepository, Depends(get_provider_repository)],
    interactions: Annotated[
        InteractionRepository,
        Depends(get_interaction_repository),
    ],
    component1: Annotated[
        HybridRecommendationEngine,
        Depends(component1_engine_dependency),
    ],
    component4: Annotated[
        Component4RankingEngine,
        Depends(component4_engine_dependency),
    ],
) -> ProviderTrustProfile:
    live_provider = await providers.find_by_id(provider_id)
    try:
        return await ProviderTrustProfileService(
            component1,
            component4,
            interactions,
        ).build(provider_id, live_provider)
    except UnknownProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except OSError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component 4 review evidence is unavailable",
        ) from error


@router.get("/{provider_id}", response_model=ProviderPublic)
async def get_provider(
    provider_id: str,
    repository: Annotated[ProviderRepository, Depends(get_provider_repository)],
) -> ProviderPublic:
    document = await repository.find_by_id(provider_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return ProviderPublic.model_validate(document)
