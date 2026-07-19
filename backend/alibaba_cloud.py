"""Alibaba Cloud integration — this is the project's Alibaba Cloud
deployment-proof file, referenced prominently from README.md. It is the only
place the `oss2` SDK is used: uploaded PDFs and FAISS index backups both flow
through OSSClient below. See docs/deploy.md for provisioning a free-tier OSS
bucket + ECS instance to run this for real.
"""

from __future__ import annotations

import os
from typing import Optional


class OSSClient:
    """Wraps an Alibaba Cloud OSS bucket for two jobs: storing uploaded PDFs
    and backing up local FAISS indexes. `is_configured()` lets the rest of
    the app fall back to local disk storage when no OSS credentials are
    present (local dev, CI, this sandboxed build) without changing any
    calling code — the same upload/download calls just target a different
    backend."""

    def __init__(
        self,
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        endpoint: Optional[str] = None,
        bucket_name: Optional[str] = None,
    ):
        self.access_key_id = access_key_id or os.environ.get("OSS_ACCESS_KEY_ID")
        self.access_key_secret = access_key_secret or os.environ.get("OSS_ACCESS_KEY_SECRET")
        self.endpoint = endpoint or os.environ.get("OSS_ENDPOINT", "https://oss-cn-hangzhou.aliyuncs.com")
        self.bucket_name = bucket_name or os.environ.get("OSS_BUCKET_NAME", "memorybench-storage")
        self._bucket = None

    def is_configured(self) -> bool:
        return bool(self.access_key_id and self.access_key_secret)

    @property
    def bucket(self):
        if self._bucket is None:
            import oss2

            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self._bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
        return self._bucket

    def upload_bytes(self, key: str, data: bytes) -> str:
        if not self.is_configured():
            raise RuntimeError("OSS not configured — set OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET")
        self.bucket.put_object(key, data)
        return f"oss://{self.bucket_name}/{key}"

    def download_bytes(self, key: str) -> bytes:
        if not self.is_configured():
            raise RuntimeError("OSS not configured — set OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET")
        return self.bucket.get_object(key).read()

    def upload_file(self, key: str, local_path: str) -> str:
        if not self.is_configured():
            raise RuntimeError("OSS not configured — set OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET")
        self.bucket.put_object_from_file(key, local_path)
        return f"oss://{self.bucket_name}/{key}"

    def download_file(self, key: str, local_path: str) -> None:
        if not self.is_configured():
            raise RuntimeError("OSS not configured — set OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET")
        self.bucket.get_object_to_file(key, local_path)

    def backup_faiss_index(self, session_id: str, index_path: str, meta_path: str) -> dict[str, str]:
        """Pushes one session's FAISS index + metadata JSON to OSS. Called
        after document ingest when OSS is configured (see
        backend/documents/faiss_index.py)."""
        index_uri = self.upload_file(f"faiss-backups/{session_id}/index.faiss", index_path)
        meta_uri = self.upload_file(f"faiss-backups/{session_id}/meta.json", meta_path)
        return {"index": index_uri, "meta": meta_uri}
