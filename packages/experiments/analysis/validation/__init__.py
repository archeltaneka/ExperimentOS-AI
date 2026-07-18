"""ExperimentOS-owned statistical input validation contracts."""

from .bindings import AnalysisDataBinding, MetricColumnBinding, OutcomeDataBinding
from .models import (
    DatasetSummary,
    DiagnosticContextEntry,
    DiagnosticDisposition,
    EligibilityDiagnostic,
    EligibilityValidationResult,
    MethodContractStatus,
    MethodImplementationStatus,
    MethodSupportAssessment,
    MissingnessSummary,
    OutcomeSummary,
    SegmentEligibilitySummary,
    TimeDesignSummary,
    TreatmentSummary,
    UnitIntegritySummary,
    ValidationCategory,
)
from .policy import ValidationPolicy
from .table import AnalysisTable, AnalysisTableError

__all__ = [
    "AnalysisDataBinding",
    "AnalysisTable",
    "AnalysisTableError",
    "DatasetSummary",
    "DiagnosticContextEntry",
    "DiagnosticDisposition",
    "EligibilityDiagnostic",
    "EligibilityValidationResult",
    "MetricColumnBinding",
    "MethodContractStatus",
    "MethodImplementationStatus",
    "MethodSupportAssessment",
    "MissingnessSummary",
    "OutcomeDataBinding",
    "OutcomeSummary",
    "SegmentEligibilitySummary",
    "TimeDesignSummary",
    "TreatmentSummary",
    "UnitIntegritySummary",
    "ValidationPolicy",
    "ValidationCategory",
]
