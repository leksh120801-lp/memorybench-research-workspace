"""Tests for the Alibaba Cloud OSS integration. oss2 itself is mocked —
these never make a real network call, per project cost-discipline rules."""

from unittest.mock import MagicMock, patch

from backend.alibaba_cloud import OSSClient


def test_unconfigured_client_reports_not_configured():
    client = OSSClient(access_key_id=None, access_key_secret=None)
    assert client.is_configured() is False


def test_configured_client_reports_configured():
    client = OSSClient(access_key_id="ak", access_key_secret="sk")
    assert client.is_configured() is True


def test_upload_bytes_raises_when_unconfigured():
    client = OSSClient(access_key_id=None, access_key_secret=None)
    try:
        client.upload_bytes("key", b"data")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "not configured" in str(e)


@patch("oss2.Bucket")
@patch("oss2.Auth")
def test_upload_bytes_calls_oss2_bucket_put_object(mock_auth, mock_bucket_cls):
    mock_bucket = MagicMock()
    mock_bucket_cls.return_value = mock_bucket

    client = OSSClient(access_key_id="ak", access_key_secret="sk", bucket_name="my-bucket")
    uri = client.upload_bytes("documents/x.pdf", b"pdf-bytes")

    mock_auth.assert_called_once_with("ak", "sk")
    mock_bucket.put_object.assert_called_once_with("documents/x.pdf", b"pdf-bytes")
    assert uri == "oss://my-bucket/documents/x.pdf"


@patch("oss2.Bucket")
@patch("oss2.Auth")
def test_backup_faiss_index_uploads_both_files(mock_auth, mock_bucket_cls, tmp_path):
    mock_bucket = MagicMock()
    mock_bucket_cls.return_value = mock_bucket

    index_file = tmp_path / "index.faiss"
    meta_file = tmp_path / "meta.json"
    index_file.write_bytes(b"fake-index")
    meta_file.write_text("{}")

    client = OSSClient(access_key_id="ak", access_key_secret="sk", bucket_name="my-bucket")
    result = client.backup_faiss_index("session-1", str(index_file), str(meta_file))

    assert mock_bucket.put_object_from_file.call_count == 2
    assert result == {
        "index": "oss://my-bucket/faiss-backups/session-1/index.faiss",
        "meta": "oss://my-bucket/faiss-backups/session-1/meta.json",
    }
