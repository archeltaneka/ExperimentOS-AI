"""Best-effort adapter telemetry through existing providers, without numerical arrays."""

from __future__ import annotations

from packages.observability.base import BaseObservabilityProvider

from ..advanced.conformance import execution_metadata
from ..advanced.models import AdvancedCausalResult
from ..hte.results import HeterogeneousEffectResult


def observe_result(
    provider: BaseObservabilityProvider,
    result: AdvancedCausalResult | HeterogeneousEffectResult,
    *,
    estimator: str,
    category: str,
    inference: str,
    duration_ms: float,
) -> None:
    identification = result.execution_request.identification_result
    codes = tuple(d.code for d in result.diagnostics)
    available = (
        False
        if "OPTIONAL_DEPENDENCY_UNAVAILABLE" in codes
        else (True if result.adapter_provenance is not None else None)
    )
    try:
        span = provider.start_root_span(
            "advanced_causal_estimator",
            run_type="chain",
            metadata={
                **execution_metadata(
                    result,
                    "econml_linear_dml" if category == "dml" else "econml_linear_dr_subgroups",
                ),
                "adapter": "econml",
                "estimator": estimator,
                "estimator_category": category,
                "estimand": identification.estimand.estimand_type.value
                if identification.estimand
                else "missing",
                "inference_mode": inference if inference == "statsmodels_hc1" else "unsupported",
                "dependency_available": available,
                "status": result.status.value,
                "diagnostic_codes": codes,
                "duration_ms": duration_ms,
            },
        )
        span.finish(outputs={"status": result.status.value})
    except Exception:
        # Telemetry transport failure cannot turn a valid abstention into an exception.
        pass
