from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    version: str
    relative_path: str
    case_count: int


def build_dataset_manifest(
    path: Path,
    *,
    dataset_id: str,
    case_count: int,
) -> DatasetManifest:
    try:
        relative_path = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        relative_path = path.name
    return build_payload_manifest(
        path.read_bytes(),
        dataset_id=dataset_id,
        relative_path=relative_path,
        case_count=case_count,
    )


def build_payload_manifest(
    payload: bytes,
    *,
    dataset_id: str,
    relative_path: str,
    case_count: int,
) -> DatasetManifest:
    return DatasetManifest(
        dataset_id=dataset_id,
        version=f"sha256:{hashlib.sha256(payload).hexdigest()}",
        relative_path=relative_path,
        case_count=case_count,
    )
