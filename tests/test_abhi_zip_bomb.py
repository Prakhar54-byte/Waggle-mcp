"""Tests for zip bomb protection in .abhi imports."""

from __future__ import annotations

import io
import zipfile

import pytest

from waggle.abhi import ValidationFailure, _read_member


def test_read_member_zip_bomb_protection() -> None:
    """Ensure that _read_member rejects zip members that exceed the 500 MB limit."""
    # Create a zip archive in memory with a fake large uncompressed size
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # We write a small payload but spoof the ZipInfo.file_size
        zinfo = zipfile.ZipInfo("large_file.txt")
        zinfo.file_size = 600 * 1024 * 1024  # 600 MB (exceeds 500 MB limit)
        zf.writestr(zinfo, b"small payload")

    buf.seek(0)

    with zipfile.ZipFile(buf, "r") as archive:
        manifest = {"members": {"large_file.txt": {}}}
        
        # Reading should fail due to the spoofed large file_size
        with pytest.raises(ValidationFailure, match=r"exceeds maximum allowed uncompressed size"):
            _read_member(archive, manifest, "large_file.txt", passphrase="")


def test_read_member_normal_size_allowed() -> None:
    """Ensure that _read_member allows members within the size limit."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zinfo = zipfile.ZipInfo("normal_file.txt")
        zinfo.file_size = 100 * 1024 * 1024  # 100 MB (within 500 MB limit)
        zf.writestr(zinfo, b"small payload")

    buf.seek(0)

    with zipfile.ZipFile(buf, "r") as archive:
        manifest = {"members": {"normal_file.txt": {}}}
        
        # Reading should succeed
        result = _read_member(archive, manifest, "normal_file.txt", passphrase="")
        assert result == b"small payload"
