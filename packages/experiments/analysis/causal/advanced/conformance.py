"""Canonical configuration identity shared by causal execution and reliability."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from ..dml.models import DMLExecutionRequest
    from ..dowhy.models import DoWhyExecutionRequest
    from ..hte.models import HTEExecutionRequest
    from .models import AdvancedEstimatorConfig


def canonical_digest(value: object) -> str:
    """Hash canonical finite JSON; do not fall back to repr for unsupported values."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def configuration_fingerprint(
    execution: DMLExecutionRequest | HTEExecutionRequest | DoWhyExecutionRequest,
    adapter_id: str,
    configuration: AdvancedEstimatorConfig | None = None,
    *,
    nuisance_fingerprints: tuple[str, ...] = (),
) -> str:
    """Identify bounded configuration, never source rows or fitted model state."""
    from ..dowhy.graph import graph_fingerprint

    settings = execution.configuration.model_dump(mode="json")
    payload: dict[str, object] = {
        "schema": "advanced-causal-configuration-v1",
        "adapter_id": adapter_id,
        "adapter_version": "1",
        "configuration": settings,
        "nuisance_fingerprints": nuisance_fingerprints,
    }
    if configuration is not None:
        payload["adapter_configuration"] = configuration.model_dump(mode="json")
    identification = execution.identification_result
    payload["method"] = identification.identification_request.design.method
    payload["estimand"] = (
        identification.estimand.estimand_type.value if identification.estimand else None
    )
    # Bindings/definitions can contain domain-sensitive names: only digest references escape.
    payload["binding_reference"] = canonical_digest(execution.binding.model_dump(mode="json"))
    modifier = getattr(execution, "modifier", None)
    if isinstance(modifier, BaseModel):
        payload["modifier_reference"] = canonical_digest(
            modifier.model_dump(
                mode="json", exclude={"definition_provenance", "registration_provenance"}
            )
        )
    if identification.causal_graph is not None:
        payload["graph_reference"] = graph_fingerprint(identification.causal_graph)
    return canonical_digest(payload)


def supplied_nuisance_fingerprints(*adapters: object) -> tuple[str, ...]:
    """Record explicitly supplied owned nuisance configurations, not fitted state."""
    from ..dml.protocols import NuisanceAdapterMetadata

    values: list[str] = []
    for adapter in adapters:
        if adapter is None:
            values.append("repository-default-v1")
            continue
        recorded = getattr(adapter, "metadata", None)
        values.append(
            recorded.configuration_fingerprint_sha256
            if isinstance(recorded, NuisanceAdapterMetadata)
            else "invalid-nuisance-contract"
        )
    # Default behavior has no overrides and keeps the shared request-only fingerprint.
    return () if all(adapter is None for adapter in adapters) else tuple(values)


def execution_metadata(result: BaseModel, adapter_id: str) -> dict[str, object]:
    """Bounded provenance for existing emitters, including unsuccessful operations."""
    from importlib import metadata

    package = (
        "econml"
        if adapter_id.startswith("econml")
        else "dowhy"
        if adapter_id == "experimentos_dowhy"
        else None
    )
    version = None
    state = "not_required"
    if package:
        try:
            version = metadata.version(package)
            state = "installed"
        except metadata.PackageNotFoundError:
            state = "unavailable"
        except Exception:
            state = "broken"
    codes = {str(d.code) for d in getattr(result, "diagnostics", ())}
    if "INCOMPATIBLE_DEPENDENCY_RUNTIME" in codes:
        state = "broken"
    return {
        "adapter_id": adapter_id,
        "adapter_version": "1",
        "configuration_fingerprint": getattr(result, "configuration_fingerprint_sha256", None),
        "dependency_state": state,
        "dependency_version": version,
    }
