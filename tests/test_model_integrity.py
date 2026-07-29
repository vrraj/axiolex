from hashlib import sha256

import pytest

from axiolex.retrieval.model_integrity import ModelArtifact, verify_model_artifacts


def test_verify_model_artifacts_accepts_matching_file(tmp_path) -> None:
    contents = b"verified"
    (tmp_path / "model.onnx").write_bytes(contents)

    verify_model_artifacts(
        tmp_path,
        (ModelArtifact("model.onnx", len(contents), sha256(contents).hexdigest()),),
    )


def test_verify_model_artifacts_rejects_hash_mismatch(tmp_path) -> None:
    (tmp_path / "model.onnx").write_bytes(b"unexpected")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_model_artifacts(tmp_path, (ModelArtifact("model.onnx", 10, "0" * 64),))
