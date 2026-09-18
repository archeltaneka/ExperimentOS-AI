"""Known-effect DGP and DR request shared by tests and offline evaluation."""

from __future__ import annotations

from packages.experiments.analysis.causal.hte.models import HTEConfig, HTEExecutionRequest
from packages.experiments.analysis.causal.service import CausalIdentificationService

from .hte import hte_execution, hte_request


def dr_execution(**kwargs: object) -> HTEExecutionRequest:
    request = hte_request()
    identification = request.identification.model_copy(
        update={
            "design": request.identification.design.model_copy(
                update={"method": "doubly_robust_subgroup_effects"}
            )
        }
    )
    identified = CausalIdentificationService().identify(
        request.model_copy(update={"identification": identification})
    )
    execution = hte_execution(identification_result=identified, **kwargs)
    config = HTEConfig.model_validate(
        {**execution.configuration.model_dump(), "analysis_version": "hte-dr-v1"}
    )
    return execution.model_copy(update={"configuration": config})


def linear_rows(effect: float = 2.0) -> tuple[dict[str, object], ...]:
    # Same independently known 2.0-effect DGP as the baseline service reference.
    noise = (-0.4, 0.2, 0.5, -0.3, 0.1)
    return tuple(
        {
            "account_id": f"unit-{index:03d}",
            "treated": int(treated),
            "outcome": effect * treated + 0.7 * x + noise[index % 5],
            "prior_orders": x,
        }
        for index in range(80)
        for x, treated in (((index - 39.5) / 10.0, (index * 17 + 3) % 7 < 3),)
    )
