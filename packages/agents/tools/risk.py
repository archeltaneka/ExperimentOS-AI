from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from packages.agents.tools.schemas import ToolSpec


class RiskFactorSeverityInput(BaseModel):
    severity: Literal["low", "medium", "high"]


class RiskScoringInput(BaseModel):
    risk_factors: list[RiskFactorSeverityInput]


class RiskScoringOutput(BaseModel):
    risk_score: int
    overall_risk_level: Literal["low", "medium", "high"]


def score_experiment_risk(input_model: RiskScoringInput) -> RiskScoringOutput:
    severity_points = {"low": 1, "medium": 2, "high": 3}
    risk_score = sum(severity_points[factor.severity] for factor in input_model.risk_factors)
    overall_risk_level: Literal["low", "medium", "high"]
    if risk_score >= 3:
        overall_risk_level = "high"
    elif risk_score >= 1:
        overall_risk_level = "medium"
    else:
        overall_risk_level = "low"
    return RiskScoringOutput(
        risk_score=risk_score,
        overall_risk_level=overall_risk_level,
    )


RISK_SCORING_TOOL = ToolSpec(
    name="score_experiment_risk",
    input_model=RiskScoringInput,
    output_model=RiskScoringOutput,
    handler=score_experiment_risk,
)
