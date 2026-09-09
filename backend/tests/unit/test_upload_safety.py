from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.datastructures import UploadFile
from app.services.candidate_import_service import CandidateImportService, validate_uploaded_images, validate_source_text
from app.services.file_storage_service import LocalFileStorageService


def png():
    stream = BytesIO()
    Image.new("RGB", (8, 8), "white").save(stream, format="PNG")
    return stream.getvalue()


async def test_invalid_second_image_cleans_up_first_image(tmp_path):
    service = CandidateImportService()
    service.storage = LocalFileStorageService(tmp_path)
    images = [
        UploadFile(filename="valid.png", file=BytesIO(png())),
        UploadFile(filename="fake.png", file=BytesIO(b"not an image")),
    ]
    with pytest.raises(HTTPException) as exc:
        await service.prepare_uploaded_images(candidate=SimpleNamespace(project_id="p", id="c"), uploaded_images=images)
    assert exc.value.status_code == 400
    assert not list(tmp_path.rglob("*.png"))


async def test_oversized_upload_is_bounded_before_reading(tmp_path):
    upload = SimpleNamespace(filename="a.png", read=AsyncMock(return_value=b"x" * (10 * 1024 * 1024 + 1)))
    with pytest.raises(HTTPException) as exc:
        await LocalFileStorageService(tmp_path).save_candidate_image(project_id="p", candidate_id="c", upload=upload)
    assert exc.value.status_code == 413
    upload.read.assert_awaited_once_with(10 * 1024 * 1024 + 1)


def test_count_total_and_text_limits():
    with pytest.raises(HTTPException):
        validate_uploaded_images([UploadFile(filename="a.png", file=BytesIO()) for _ in range(9)])
    with pytest.raises(HTTPException):
        validate_uploaded_images([UploadFile(filename="a.png", file=BytesIO(), size=8 * 1024 * 1024) for _ in range(4)])
    with pytest.raises(HTTPException):
        validate_source_text("x" * 20000, "y" * 10001)
    validate_source_text("x" * 15000, "y" * 15000)


def test_storage_cannot_escape_root(tmp_path):
    storage = LocalFileStorageService(tmp_path)
    with pytest.raises(ValueError):
        storage.resolve_path("../outside.png")
    with pytest.raises(ValueError):
        storage.resolve_path("/tmp/outside.png")
    (tmp_path / "escape").symlink_to(Path("/tmp"))
    with pytest.raises(ValueError):
        storage.resolve_path("escape/outside.png")


async def test_delete_upload_removes_file_and_is_repeatable(tmp_path):
    storage = LocalFileStorageService(tmp_path)
    saved = await storage.save_candidate_image(
        project_id="p", candidate_id="c", upload=UploadFile(filename="a.png", file=BytesIO(png()))
    )
    assert saved.absolute_path.exists()
    storage.delete_file(saved.storage_key)
    storage.delete_file(saved.storage_key)
    assert not saved.absolute_path.exists()


def test_storage_scope_is_shared_by_concurrent_process_clients_and_survives_recreation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from app.services.file_storage_service import LocalFileStorageService
    with ThreadPoolExecutor(max_workers=8) as pool:
        scopes = list(pool.map(lambda _: LocalFileStorageService(root=tmp_path).storage_scope(), range(16)))
    assert len(set(scopes)) == 1
    assert LocalFileStorageService(root=tmp_path).storage_scope() == scopes[0]
    assert LocalFileStorageService(root=tmp_path / 'other-volume').storage_scope() != scopes[0]
