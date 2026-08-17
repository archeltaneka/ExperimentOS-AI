"""Public-boundary tests for Bayesian analysis contracts and service."""

from __future__ import annotations


def test_bayesian_contracts_are_exported_from_randomized_and_analysis_boundaries() -> None:
    from packages.experiments.analysis import (
        BayesianAnalysisExecutionRequest,
        BayesianAnalysisResult,
        BayesianAnalysisService,
        BayesianComputationConfig,
        BetaPrior,
        NormalInverseGammaPrior,
        bayesian_analysis_result_from_json,
    )
    from packages.experiments.analysis.randomized import (
        BayesianAnalysisExecutionRequest as RandomizedExecutionRequest,
    )
    from packages.experiments.analysis.randomized import (
        BayesianAnalysisResult as RandomizedResult,
    )
    from packages.experiments.analysis.randomized import (
        BayesianAnalysisService as RandomizedService,
    )
    from packages.experiments.analysis.randomized.bayesian import (
        BayesianAnalysisExecutionRequest as BayesianExecutionRequest,
    )
    from packages.experiments.analysis.randomized.bayesian import (
        BayesianAnalysisResult as BayesianResult,
    )
    from packages.experiments.analysis.randomized.bayesian import (
        BayesianAnalysisService as BayesianService,
    )

    assert BayesianAnalysisExecutionRequest is RandomizedExecutionRequest
    assert BayesianAnalysisExecutionRequest is BayesianExecutionRequest
    assert BayesianAnalysisResult is RandomizedResult
    assert BayesianAnalysisResult is BayesianResult
    assert BayesianAnalysisService is RandomizedService
    assert BayesianAnalysisService is BayesianService
    assert BayesianComputationConfig.__name__ == "BayesianComputationConfig"
    assert BetaPrior.__name__ == "BetaPrior"
    assert NormalInverseGammaPrior.__name__ == "NormalInverseGammaPrior"
    assert callable(bayesian_analysis_result_from_json)
