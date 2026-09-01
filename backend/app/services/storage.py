from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Protocol

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings


class ObjectStorage(Protocol):
    def ensure_bucket(self) -> None: ...
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


class InMemoryStorage:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def ensure_bucket(self) -> None:
        return None

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._objects[key] = data

    def get(self, key: str) -> bytes:
        if key not in self._objects:
            raise FileNotFoundError(key)
        return self._objects[key]

    def exists(self, key: str) -> bool:
        return key in self._objects

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)


class MinioStorage:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.minio_access_key or not settings.minio_secret_key:
            raise RuntimeError("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set")
        self._bucket = settings.minio_bucket
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.ensure_bucket()
        self._client.put_object(
            self._bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type or "application/octet-stream",
        )

    def get(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def exists(self, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except S3Error:
            return False

    def delete(self, key: str) -> None:
        self._client.remove_object(self._bucket, key)


_memory = InMemoryStorage()
_minio: MinioStorage | None = None


def get_storage() -> ObjectStorage:
    settings = get_settings()
    if settings.storage_backend == "memory":
        return _memory
    global _minio
    if _minio is None:
        _minio = MinioStorage()
    return _minio


def object_key_for(*, faculty_id: str, cycle_id: str, activity_id: str, evidence_id: str, filename: str) -> str:
    suffix = Path(filename).suffix.lower() or ".bin"
    return f"{faculty_id}/{cycle_id}/{activity_id}/{evidence_id}{suffix}"
