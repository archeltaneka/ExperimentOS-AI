from __future__ import annotations

from packages.evals.prompt_experiments.models import PromptExperimentExposure


class PromptExperimentExposureRecorder:
    def __init__(self) -> None:
        self.exposures: list[PromptExperimentExposure] = []
        self._seen: set[tuple[str, str, str, str, str, str]] = set()

    def record_once(self, exposure: PromptExperimentExposure) -> bool:
        key = (
            exposure.experiment_id,
            exposure.variant,
            exposure.prompt_id,
            exposure.prompt_version,
            exposure.assignment_key_hash,
            exposure.trace_id,
        )
        if key in self._seen:
            return False
        self._seen.add(key)
        self.exposures.append(exposure)
        return True
