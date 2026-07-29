"""Pinned Hugging Face model resolution for AXIOLEX's default ColBERT model."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import logging
from pathlib import Path


logger = logging.getLogger(__name__)

DEFAULT_COLBERT_REPOSITORY = "colbert-ir/colbertv2.0"
DEFAULT_COLBERT_REVISION = "c1e84128e85ef755c096a95bdb06b47793b13acf"


@dataclass(frozen=True)
class ModelArtifact:
    filename: str
    size_bytes: int
    sha256: str


DEFAULT_COLBERT_ARTIFACTS = (
    ModelArtifact("config.json", 743, "cbdcc01dc7772fd0e5e1d85d5de695faf8c4935ae3c7ea3fdb6c24397b284f3c"),
    ModelArtifact("model.onnx", 436_194_949, "bfe81fa313c4c2a12319ec9ef0cdf1c995daad051e9c5a1fcabcb90feb3c8286"),
    ModelArtifact("special_tokens_map.json", 112, "303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3"),
    ModelArtifact("tokenizer.json", 466_081, "5fd1c882abbd30517dced455a2c9768945ec726b96727927e4959348d9de550b"),
    ModelArtifact("tokenizer_config.json", 405, "a16a31c8d474339d7a46afe7eb8583b24f8b74806af6e25294506523f9d0acfb"),
)


def ensure_default_colbert_model(cache_dir: str | Path | None = None) -> Path:
    """Download the pinned ColBERT snapshot through huggingface_hub and verify it."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            'Install the optional ColBERT dependencies with `pip install "axiolex[colbert]"`.'
        ) from exc

    resolved_cache = Path(cache_dir).expanduser() if cache_dir else None
    logger.info(
        "Fetching pinned ColBERT model repo=%s revision=%s",
        DEFAULT_COLBERT_REPOSITORY,
        DEFAULT_COLBERT_REVISION,
    )
    snapshot_path = Path(
        snapshot_download(
            repo_id=DEFAULT_COLBERT_REPOSITORY,
            revision=DEFAULT_COLBERT_REVISION,
            allow_patterns=[artifact.filename for artifact in DEFAULT_COLBERT_ARTIFACTS],
            cache_dir=str(resolved_cache) if resolved_cache else None,
        )
    )
    verify_model_artifacts(snapshot_path, DEFAULT_COLBERT_ARTIFACTS)
    logger.info("Pinned ColBERT model verification succeeded at %s", snapshot_path)
    return snapshot_path


def verify_model_artifacts(model_dir: str | Path, artifacts: tuple[ModelArtifact, ...]) -> None:
    model_path = Path(model_dir)
    for artifact in artifacts:
        path = model_path / artifact.filename
        if not path.is_file():
            raise ValueError(f"Required ColBERT artifact is missing: {artifact.filename}")
        actual_size = path.stat().st_size
        if actual_size != artifact.size_bytes:
            raise ValueError(
                f"ColBERT artifact size mismatch for {artifact.filename}: "
                f"expected {artifact.size_bytes}, got {actual_size}."
            )
        actual_sha256 = file_sha256(path)
        if actual_sha256 != artifact.sha256:
            raise ValueError(
                f"ColBERT artifact SHA-256 mismatch for {artifact.filename}: "
                f"expected {artifact.sha256}, got {actual_sha256}."
            )
        logger.info("ColBERT artifact verified file=%s sha256=%s", artifact.filename, actual_sha256)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
