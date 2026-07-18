"""ExperimentOS-owned statistical input validation contracts."""

from .bindings import AnalysisDataBinding, MetricColumnBinding, OutcomeDataBinding
from .capabilities import MethodCapabilityRegistry
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
from .service import AnalysisEligibilityService, aggregate_status
from .table import AnalysisTable, AnalysisTableError

__all__ = [
    "AnalysisDataBinding",
    "AnalysisEligibilityService",
    "AnalysisTable",
    "AnalysisTableError",
    "DatasetSummary",
    "DiagnosticContextEntry",
    "DiagnosticDisposition",
    "EligibilityDiagnostic",
    "EligibilityValidationResult",
    "MetricColumnBinding",
    "MethodContractStatus",
    "MethodCapabilityRegistry",
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
    "aggregate_status",
]
