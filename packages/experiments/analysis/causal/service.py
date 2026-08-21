"""Deterministic causal-identification validation without estimator execution."""

from __future__ import annotations

from collections import Counter
from time import perf_counter

from packages.observability.base import BaseObservabilityProvider
from packages.observability.noop import NoOpObservabilityProvider

from ..provenance import DiagnosticSeverity
from .adjustment import AdjustmentSet, AdjustmentValidationStatus
from .assumptions import (
    CausalAssumption,
    CausalAssumptionCode,
    CausalAssumptionStatus,
)
from .diagnostics import (
    CausalDiagnostic,
    CausalDiagnosticCategory,
    CausalDiagnosticCode,
    CausalDiagnosticContext,
    CausalDiagnosticStatus,
    EvidenceLimitation,
    EvidenceLimitationCode,
)
from .estimands import CausalEstimandKind
from .models import (
    CausalAbstentionReason,
    CausalIdentificationRequest,
    IdentificationResult,
    IdentificationStatus,
    ObservationalAnalysisRequest,
)
from .variables import CausalVariable, MeasurementTiming, VariableRole

_COMMON_REQUIRED_ASSUMPTIONS = frozenset(
    {
        CausalAssumptionCode.CONSISTENCY,
        CausalAssumptionCode.INTERFERENCE_LIMITATION,
        CausalAssumptionCode.EXCHANGEABILITY,
        CausalAssumptionCode.POSITIVITY,
        CausalAssumptionCode.TEMPORAL_ORDERING,
        CausalAssumptionCode.STABLE_TREATMENT_DEFINITION,
        CausalAssumptionCode.STABLE_UNIT_POPULATION,
    }
)
_DID_REQUIRED_ASSUMPTIONS = frozenset(
    {CausalAssumptionCode.PARALLEL_TRENDS, CausalAssumptionCode.NO_ANTICIPATION}
)


def _diagnostic(
    code: CausalDiagnosticCode,
    category: CausalDiagnosticCategory,
    message: str,
    *,
    severity: DiagnosticSeverity = DiagnosticSeverity.FATAL,
    unavailable: bool = False,
    context: dict[str, str] | None = None,
) -> CausalDiagnostic:
    return CausalDiagnostic(
        code=code,
        category=category,
        severity=severity,
        status=(
            CausalDiagnosticStatus.UNAVAILABLE if unavailable else CausalDiagnosticStatus.FAILED
        ),
        message=message,
        context=tuple(
            CausalDiagnosticContext(key=key, value=value)
            for key, value in sorted((context or {}).items())
        ),
    )


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    counts = Counter(values)
    return tuple(sorted(value for value, count in counts.items() if count > 1))


class CausalIdentificationService:
    """Validate declarations and return identification status without fitting anything."""

    def __init__(
        self,
        *,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def identify(self, request: ObservationalAnalysisRequest) -> IdentificationResult:
        started = perf_counter()
        identification = request.identification
        diagnostics = [
            *self._validate_required_declarations(identification),
            *self._validate_variables(identification),
            *self._validate_adjustment(identification),
            *self._validate_effect_modifiers(identification),
            *self._validate_graph(identification),
            *self._validate_design(identification),
            *self._validate_assumptions(identification),
        ]
        status = self._derive_status(identification, tuple(diagnostics))
        limitations = self._limitations(identification)
        abstention = self._abstention(status, tuple(diagnostics))
        validated_adjustment = self._validated_adjustment_set(
            identification.adjustment_set,
            tuple(diagnostics),
        )
        result = IdentificationResult(
            request_id=request.request_id,
            identification_request=identification,
            status=status,
            diagnostics=tuple(diagnostics),
            warnings=tuple(
                item for item in diagnostics if item.severity is DiagnosticSeverity.WARNING
            ),
            adjustment_set=validated_adjustment,
            evidence_limitations=limitations,
            provenance=identification.provenance,
            abstention_reason=abstention,
        )
        span = self.observability_provider.start_root_span(
            "causal_identification",
            run_type="chain",
            metadata={
                "design_type": identification.design.design_type.value,
                "estimand": (
                    identification.estimand.estimand_type.value
                    if identification.estimand is not None
                    else "missing"
                ),
                "identification_status": result.status.value,
                "adjustment_variable_count": (
                    len(identification.adjustment_set.variable_ids)
                    if identification.adjustment_set is not None
                    else 0
                ),
                "effect_modifier_count": len(identification.effect_modifiers),
                "assumption_codes": tuple(
                    item.code.value for item in identification.assumptions
                ),
                "diagnostic_codes": tuple(item.code.value for item in result.diagnostics),
                "abstention_state": result.abstention_reason is not None,
                "duration_ms": (perf_counter() - started) * 1000.0,
            },
        )
        span.finish(outputs={"status": result.status.value})
        return result

    @staticmethod
    def _validate_required_declarations(
        request: CausalIdentificationRequest,
    ) -> tuple[CausalDiagnostic, ...]:
        diagnostics: list[CausalDiagnostic] = []
        if request.estimand is None:
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.MISSING_ESTIMAND,
                    CausalDiagnosticCategory.ESTIMAND,
                    "An explicit observational estimand is required.",
                    severity=DiagnosticSeverity.ERROR,
                    unavailable=True,
                )
            )
        if request.treatment is None:
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.MISSING_TREATMENT,
                    CausalDiagnosticCategory.REQUEST,
                    "An explicit treatment contrast is required.",
                    severity=DiagnosticSeverity.ERROR,
                    unavailable=True,
                )
            )
        if request.outcome is None:
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.MISSING_OUTCOME,
                    CausalDiagnosticCategory.REQUEST,
                    "An explicit outcome is required.",
                    severity=DiagnosticSeverity.ERROR,
                    unavailable=True,
                )
            )
        if request.units is None:
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.MISSING_UNIT_SEMANTICS,
                    CausalDiagnosticCategory.REQUEST,
                    "Analysis and observation units are required.",
                    severity=DiagnosticSeverity.ERROR,
                    unavailable=True,
                )
            )
        if request.adjustment_set is None and request.causal_graph is None:
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.MISSING_ADJUSTMENT_INFORMATION,
                    CausalDiagnosticCategory.EVIDENCE,
                    "An explicit adjustment set or causal graph is required.",
                    severity=DiagnosticSeverity.ERROR,
                    unavailable=True,
                )
            )
        if request.estimand is not None:
            mismatches: list[str] = []
            if (
                request.treatment is not None
                and request.estimand.treatment_contrast != request.treatment
            ):
                mismatches.append("treatment_contrast")
            if (
                request.outcome is not None
                and request.estimand.outcome_variable != request.outcome.variable_id
            ):
                mismatches.append("outcome_variable")
            if request.estimand.target_population.population != request.population:
                mismatches.append("target_population")
            for mismatch in mismatches:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.ESTIMAND_REQUEST_MISMATCH,
                        CausalDiagnosticCategory.ESTIMAND,
                        "Estimand declarations must match the identification request.",
                        context={"field": mismatch},
                    )
                )
        return tuple(diagnostics)

    @staticmethod
    def _validate_variables(
        request: CausalIdentificationRequest,
    ) -> tuple[CausalDiagnostic, ...]:
        diagnostics: list[CausalDiagnostic] = []
        variable_ids = tuple(item.variable_id for item in request.variables)
        for duplicate in _duplicates(variable_ids):
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.DUPLICATE_VARIABLE,
                    CausalDiagnosticCategory.VARIABLE,
                    "Variable identifiers must be unique.",
                    context={"variable_id": duplicate},
                )
            )

        allowed_dual_role = {VariableRole.ADJUSTMENT, VariableRole.EFFECT_MODIFIER}
        by_id = {item.variable_id: item for item in request.variables}
        for variable in request.variables:
            role_set = set(variable.roles)
            if len(variable.roles) != len(role_set):
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.CONTRADICTORY_ROLE,
                        CausalDiagnosticCategory.VARIABLE,
                        "Duplicate variable roles are invalid.",
                        context={"variable_id": variable.variable_id},
                    )
                )
            if len(role_set) > 1 and role_set != allowed_dual_role:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.CONTRADICTORY_ROLE,
                        CausalDiagnosticCategory.VARIABLE,
                        "The variable has contradictory analytical roles.",
                        context={"variable_id": variable.variable_id},
                    )
                )
            diagnostics.extend(CausalIdentificationService._validate_timing(variable))

        references: tuple[tuple[str | None, VariableRole, str], ...] = (
            (
                request.treatment.treatment_variable if request.treatment is not None else None,
                VariableRole.TREATMENT,
                "treatment",
            ),
            (
                request.outcome.variable_id if request.outcome is not None else None,
                VariableRole.OUTCOME,
                "outcome",
            ),
            (request.time.time_variable, VariableRole.TIME, "time"),
        )
        for variable_id, expected_role, reference in references:
            if variable_id is None:
                continue
            referenced_variable = by_id.get(variable_id)
            if referenced_variable is None or expected_role not in referenced_variable.roles:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.CONTRADICTORY_ROLE,
                        CausalDiagnosticCategory.VARIABLE,
                        "A referenced variable is missing its required analytical role.",
                        context={"reference": reference, "variable_id": variable_id},
                    )
                )

        for duplicate in _duplicates(request.covariates):
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.DUPLICATE_COVARIATE,
                    CausalDiagnosticCategory.VARIABLE,
                    "Covariate references must be unique.",
                    context={"variable_id": duplicate},
                )
            )
        for variable_id in request.covariates:
            if variable_id not in by_id:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MISSING_ADJUSTMENT_VARIABLE,
                        CausalDiagnosticCategory.VARIABLE,
                        "Every covariate must reference a declared variable.",
                        context={"variable_id": variable_id},
                    )
                )

        if request.treatment is not None and request.outcome is not None:
            if request.treatment.treatment_variable == request.outcome.variable_id:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.CONTRADICTORY_ROLE,
                        CausalDiagnosticCategory.VARIABLE,
                        "Treatment and outcome variables must differ.",
                        context={"variable_id": request.outcome.variable_id},
                    )
                )
        return tuple(diagnostics)

    @staticmethod
    def _validate_timing(variable: CausalVariable) -> tuple[CausalDiagnostic, ...]:
        timing = variable.timing
        if timing.reference_period is None or timing.treatment_start is None:
            return ()
        invalid = False
        if timing.measurement_timing is MeasurementTiming.PRE_TREATMENT:
            invalid = timing.reference_period.end > timing.treatment_start
        elif timing.measurement_timing is MeasurementTiming.POST_TREATMENT:
            invalid = timing.reference_period.start < timing.treatment_start
        elif timing.measurement_timing is MeasurementTiming.AT_TREATMENT:
            invalid = not (
                timing.reference_period.start
                <= timing.treatment_start
                <= timing.reference_period.end
            )
        if not invalid:
            return ()
        return (
            _diagnostic(
                CausalDiagnosticCode.REVERSED_TIMING,
                CausalDiagnosticCategory.TIMING,
                "Measurement timing contradicts the declared treatment start.",
                context={"variable_id": variable.variable_id},
            ),
        )

    @staticmethod
    def _validate_adjustment(
        request: CausalIdentificationRequest,
    ) -> tuple[CausalDiagnostic, ...]:
        adjustment = request.adjustment_set
        if adjustment is None:
            return ()
        diagnostics: list[CausalDiagnostic] = []
        for duplicate in _duplicates(adjustment.variable_ids):
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.DUPLICATE_ADJUSTMENT_VARIABLE,
                    CausalDiagnosticCategory.ADJUSTMENT,
                    "Adjustment variables must be unique.",
                    context={"variable_id": duplicate},
                )
            )
        by_id = {item.variable_id: item for item in request.variables}
        for variable_id in adjustment.variable_ids:
            variable = by_id.get(variable_id)
            if variable is None:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MISSING_ADJUSTMENT_VARIABLE,
                        CausalDiagnosticCategory.ADJUSTMENT,
                        "The adjustment variable is not declared in the request.",
                        context={"variable_id": variable_id},
                    )
                )
                continue
            roles = set(variable.roles)
            if VariableRole.TREATMENT in roles:
                code = CausalDiagnosticCode.TREATMENT_LEAKAGE
                message = "The treatment variable cannot be used for adjustment."
            elif VariableRole.OUTCOME in roles:
                code = CausalDiagnosticCode.OUTCOME_LEAKAGE
                message = "The outcome variable cannot be used for adjustment."
            elif VariableRole.IDENTIFIER in roles:
                code = CausalDiagnosticCode.IDENTIFIER_MISUSE
                message = "Identifiers cannot be used for causal adjustment."
            elif VariableRole.POST_TREATMENT in roles:
                code = CausalDiagnosticCode.POST_TREATMENT_ADJUSTMENT
                message = "Post-treatment variables cannot be used for adjustment."
            elif VariableRole.ADJUSTMENT not in roles:
                code = CausalDiagnosticCode.INVALID_ADJUSTMENT_ROLE
                message = "The selected variable lacks an adjustment role."
            elif variable.timing.measurement_timing is MeasurementTiming.POST_TREATMENT:
                code = CausalDiagnosticCode.POST_TREATMENT_ADJUSTMENT
                message = "Adjustment variables measured after treatment are invalid."
            elif variable.timing.measurement_timing is MeasurementTiming.UNKNOWN:
                code = CausalDiagnosticCode.UNKNOWN_COVARIATE_TIMING
                message = "Unknown timing prevents causal adjustment."
            else:
                continue
            diagnostics.append(
                _diagnostic(
                    code,
                    CausalDiagnosticCategory.ADJUSTMENT,
                    message,
                    context={"variable_id": variable_id},
                )
            )
        if request.estimand is not None:
            if adjustment.estimand_type is not request.estimand.estimand_type:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MALFORMED_ADJUSTMENT_SET,
                        CausalDiagnosticCategory.ADJUSTMENT,
                        "Adjustment-set estimand must match the requested estimand.",
                    )
                )
        return tuple(diagnostics)

    @staticmethod
    def _validate_effect_modifiers(
        request: CausalIdentificationRequest,
    ) -> tuple[CausalDiagnostic, ...]:
        diagnostics: list[CausalDiagnostic] = []
        for duplicate in _duplicates(request.effect_modifiers):
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.DUPLICATE_EFFECT_MODIFIER,
                    CausalDiagnosticCategory.VARIABLE,
                    "Effect modifiers must be unique.",
                    context={"variable_id": duplicate},
                )
            )
        by_id = {item.variable_id: item for item in request.variables}
        for variable_id in request.effect_modifiers:
            variable = by_id.get(variable_id)
            if variable is None or VariableRole.EFFECT_MODIFIER not in variable.roles:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MISSING_EFFECT_MODIFIER,
                        CausalDiagnosticCategory.VARIABLE,
                        "The effect modifier is missing or lacks its declared role.",
                        context={"variable_id": variable_id},
                    )
                )
                continue
            if variable.timing.measurement_timing is MeasurementTiming.POST_TREATMENT:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.POST_TREATMENT_EFFECT_MODIFIER,
                        CausalDiagnosticCategory.TIMING,
                        "Effect modifiers must be measured before treatment.",
                        context={"variable_id": variable_id},
                    )
                )
            elif variable.timing.measurement_timing is MeasurementTiming.UNKNOWN:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.UNKNOWN_EFFECT_MODIFIER_TIMING,
                        CausalDiagnosticCategory.TIMING,
                        "Unknown timing prevents heterogeneous-effect identification.",
                        context={"variable_id": variable_id},
                    )
                )
        if request.estimand is not None:
            if request.effect_modifiers != request.estimand.effect_modifiers:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.ESTIMAND_DESIGN_MISMATCH,
                        CausalDiagnosticCategory.ESTIMAND,
                        "Request effect modifiers must match the CATE estimand.",
                    )
                )
        return tuple(diagnostics)

    @staticmethod
    def _validate_graph(
        request: CausalIdentificationRequest,
    ) -> tuple[CausalDiagnostic, ...]:
        graph = request.causal_graph
        if graph is None:
            return ()
        diagnostics: list[CausalDiagnostic] = []
        node_ids = tuple(node.node_id for node in graph.nodes)
        variable_ids = {item.variable_id for item in request.variables}
        for duplicate in _duplicates(node_ids):
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.GRAPH_DUPLICATE_NODE,
                    CausalDiagnosticCategory.GRAPH,
                    "Graph node identifiers must be unique.",
                    context={"node_id": duplicate},
                )
            )
        node_id_set = set(node_ids)
        for node in graph.nodes:
            if node.variable_id not in variable_ids:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.GRAPH_UNKNOWN_VARIABLE,
                        CausalDiagnosticCategory.GRAPH,
                        "Every graph node must reference a declared variable.",
                        context={"node_id": node.node_id},
                    )
                )
        edge_pairs = tuple((edge.cause, edge.effect) for edge in graph.edges)
        for cause, effect in edge_pairs:
            if cause == effect:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.GRAPH_SELF_LOOP,
                        CausalDiagnosticCategory.GRAPH,
                        "Causal graph self-loops are invalid.",
                        context={"node_id": cause},
                    )
                )
            if cause not in node_id_set or effect not in node_id_set:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.GRAPH_UNKNOWN_NODE,
                        CausalDiagnosticCategory.GRAPH,
                        "Every edge endpoint must reference a graph node.",
                        context={"cause": cause, "effect": effect},
                    )
                )
        for duplicate in _duplicates(tuple(f"{cause}->{effect}" for cause, effect in edge_pairs)):
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.GRAPH_DUPLICATE_EDGE,
                    CausalDiagnosticCategory.GRAPH,
                    "Causal graph edges must be unique.",
                    context={"edge": duplicate},
                )
            )
        if graph.is_dag and CausalIdentificationService._has_cycle(node_id_set, edge_pairs):
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.GRAPH_CYCLE,
                    CausalDiagnosticCategory.GRAPH,
                    "A graph declared as a DAG cannot contain a directed cycle.",
                )
            )
        if request.adjustment_set is not None:
            graph_variables = {node.variable_id for node in graph.nodes}
            for variable_id in request.adjustment_set.variable_ids:
                if variable_id not in graph_variables:
                    diagnostics.append(
                        _diagnostic(
                            CausalDiagnosticCode.GRAPH_ADJUSTMENT_INCONSISTENCY,
                            CausalDiagnosticCategory.GRAPH,
                            "Adjustment variables must be represented in the supplied graph.",
                            context={"variable_id": variable_id},
                        )
                    )
        return tuple(diagnostics)

    @staticmethod
    def _has_cycle(nodes: set[str], edges: tuple[tuple[str, str], ...]) -> bool:
        adjacency: dict[str, set[str]] = {node: set() for node in nodes}
        for cause, effect in edges:
            if cause in adjacency and effect in adjacency:
                adjacency[cause].add(effect)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(visit(effect) for effect in sorted(adjacency[node])):
                return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in sorted(nodes) if node not in visited)

    @staticmethod
    def _validate_design(
        request: CausalIdentificationRequest,
    ) -> tuple[CausalDiagnostic, ...]:
        diagnostics: list[CausalDiagnostic] = []
        design = request.design
        if design.design_type.value == "custom":
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.UNSUPPORTED_DESIGN,
                    CausalDiagnosticCategory.DESIGN,
                    "The requested observational design is not currently supported.",
                    severity=DiagnosticSeverity.ERROR,
                    unavailable=True,
                    context={"method": design.method},
                )
            )
            return tuple(diagnostics)
        estimand = request.estimand
        if design.design_type.value == "difference_in_differences":
            if estimand is not None and estimand.estimand_type is not CausalEstimandKind.DID_ATT:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.ESTIMAND_DESIGN_MISMATCH,
                        CausalDiagnosticCategory.ESTIMAND,
                        "Difference-in-Differences requires the DiD ATT estimand.",
                    )
                )
            if request.time.pre_period is None:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MISSING_PRE_PERIOD,
                        CausalDiagnosticCategory.TIMING,
                        "Difference-in-Differences requires a pre-period.",
                    )
                )
            if request.time.post_period is None:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MISSING_POST_PERIOD,
                        CausalDiagnosticCategory.TIMING,
                        "Difference-in-Differences requires a post-period.",
                    )
                )
            if request.time.treatment_start is None:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MISSING_TREATMENT_TIME,
                        CausalDiagnosticCategory.TIMING,
                        "Difference-in-Differences requires treatment timing.",
                    )
                )
            if design.treated_group is None or design.comparison_group is None:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MISSING_DID_GROUP,
                        CausalDiagnosticCategory.DESIGN,
                        "Difference-in-Differences requires treated and comparison groups.",
                    )
                )
            if design.stable_treatment_adoption is None:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MISSING_STABLE_ADOPTION,
                        CausalDiagnosticCategory.DESIGN,
                        "Difference-in-Differences requires stable treatment adoption semantics.",
                    )
                )
            pre = request.time.pre_period
            post = request.time.post_period
            if pre is not None and post is not None and pre.end > post.start:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.REVERSED_TIMING,
                        CausalDiagnosticCategory.TIMING,
                        "The DiD pre-period must end no later than the post-period starts.",
                    )
                )
        elif estimand is not None and estimand.estimand_type is CausalEstimandKind.DID_ATT:
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.ESTIMAND_DESIGN_MISMATCH,
                    CausalDiagnosticCategory.ESTIMAND,
                    "The DiD ATT estimand requires a Difference-in-Differences design.",
                )
            )
        if design.design_type.value == "heterogeneous_effects":
            if estimand is not None and estimand.estimand_type is not CausalEstimandKind.CATE:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.ESTIMAND_DESIGN_MISMATCH,
                        CausalDiagnosticCategory.ESTIMAND,
                        "Heterogeneous-effects designs require a CATE estimand.",
                    )
                )
        return tuple(diagnostics)

    @staticmethod
    def _validate_assumptions(
        request: CausalIdentificationRequest,
    ) -> tuple[CausalDiagnostic, ...]:
        diagnostics: list[CausalDiagnostic] = []
        required = set(_COMMON_REQUIRED_ASSUMPTIONS)
        if request.design.design_type.value == "difference_in_differences":
            required.update(_DID_REQUIRED_ASSUMPTIONS)
        codes = tuple(item.code for item in request.assumptions)
        for duplicate in _duplicates(tuple(code.value for code in codes)):
            diagnostics.append(
                _diagnostic(
                    CausalDiagnosticCode.CONTRADICTORY_ASSUMPTION,
                    CausalDiagnosticCategory.ASSUMPTION,
                    "Each causal assumption code must be declared once.",
                    context={"assumption": duplicate},
                )
            )
        by_code: dict[CausalAssumptionCode, CausalAssumption] = {
            item.code: item for item in request.assumptions
        }
        for code in sorted(required, key=lambda item: item.value):
            assumption = by_code.get(code)
            if assumption is None:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.MISSING_REQUIRED_ASSUMPTION,
                        CausalDiagnosticCategory.ASSUMPTION,
                        "A design-required causal assumption is missing.",
                        severity=DiagnosticSeverity.ERROR,
                        unavailable=True,
                        context={"assumption": code.value},
                    )
                )
            elif assumption.status is CausalAssumptionStatus.VIOLATED:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.VIOLATED_ASSUMPTION,
                        CausalDiagnosticCategory.ASSUMPTION,
                        "A required causal assumption is declared violated.",
                        context={"assumption": code.value},
                    )
                )
            elif assumption.status in {
                CausalAssumptionStatus.UNVERIFIED,
                CausalAssumptionStatus.NOT_APPLICABLE,
            }:
                diagnostics.append(
                    _diagnostic(
                        CausalDiagnosticCode.UNVERIFIED_ASSUMPTION,
                        CausalDiagnosticCategory.ASSUMPTION,
                        "A required causal assumption remains unverified.",
                        severity=DiagnosticSeverity.WARNING,
                        unavailable=True,
                        context={"assumption": code.value},
                    )
                )
        return tuple(diagnostics)

    @staticmethod
    def _derive_status(
        request: CausalIdentificationRequest,
        diagnostics: tuple[CausalDiagnostic, ...],
    ) -> IdentificationStatus:
        codes = {item.code for item in diagnostics}
        insufficient_codes = {
            CausalDiagnosticCode.MISSING_ESTIMAND,
            CausalDiagnosticCode.MISSING_TREATMENT,
            CausalDiagnosticCode.MISSING_OUTCOME,
            CausalDiagnosticCode.MISSING_UNIT_SEMANTICS,
            CausalDiagnosticCode.MISSING_ADJUSTMENT_INFORMATION,
            CausalDiagnosticCode.MISSING_REQUIRED_ASSUMPTION,
        }
        unsupported_codes = {
            CausalDiagnosticCode.UNSUPPORTED_DESIGN,
            CausalDiagnosticCode.UNSUPPORTED_ESTIMAND,
        }
        partial_codes = {CausalDiagnosticCode.UNVERIFIED_ASSUMPTION}
        fatal_codes = codes - insufficient_codes - unsupported_codes - partial_codes
        if fatal_codes:
            return IdentificationStatus.INVALID
        if codes & unsupported_codes:
            return IdentificationStatus.UNSUPPORTED
        if codes & insufficient_codes:
            return IdentificationStatus.INSUFFICIENT_EVIDENCE
        if codes & partial_codes:
            return IdentificationStatus.PARTIALLY_IDENTIFIED
        if request.estimand is None:
            return IdentificationStatus.INSUFFICIENT_EVIDENCE
        return IdentificationStatus.IDENTIFIED

    @staticmethod
    def _limitations(
        request: CausalIdentificationRequest,
    ) -> tuple[EvidenceLimitation, ...]:
        provenance = request.provenance
        limitations = list(request.evidence_limitations)
        assumption_codes = {item.code for item in request.assumptions}
        if CausalAssumptionCode.EXCHANGEABILITY in assumption_codes:
            limitations.extend(
                [
                    EvidenceLimitation(
                        code=EvidenceLimitationCode.EXCHANGEABILITY_ASSERTED,
                        description=(
                            "Exchangeability is declared and cannot be proven from observed data."
                        ),
                        assumption_codes=(CausalAssumptionCode.EXCHANGEABILITY,),
                        provenance=provenance,
                    ),
                    EvidenceLimitation(
                        code=EvidenceLimitationCode.UNMEASURED_CONFOUNDING_POSSIBLE,
                        description="Unmeasured confounding remains possible.",
                        assumption_codes=(CausalAssumptionCode.EXCHANGEABILITY,),
                        provenance=provenance,
                    ),
                ]
            )
        if CausalAssumptionCode.POSITIVITY in assumption_codes:
            limitations.append(
                EvidenceLimitation(
                    code=EvidenceLimitationCode.OVERLAP_NOT_EVALUATED,
                    description="Positivity and propensity overlap have not been evaluated.",
                    assumption_codes=(CausalAssumptionCode.POSITIVITY,),
                    provenance=provenance,
                )
            )
        if CausalAssumptionCode.PARALLEL_TRENDS in assumption_codes:
            limitations.append(
                EvidenceLimitation(
                    code=EvidenceLimitationCode.PARALLEL_TRENDS_UNVERIFIED,
                    description="Parallel trends have not been tested or proven.",
                    assumption_codes=(CausalAssumptionCode.PARALLEL_TRENDS,),
                    provenance=provenance,
                )
            )
        limitations.append(
            EvidenceLimitation(
                code=EvidenceLimitationCode.NO_SENSITIVITY_ANALYSIS,
                description="No sensitivity analysis has been performed.",
                provenance=provenance,
            )
        )
        if request.adjustment_set is not None and request.causal_graph is None:
            limitations.append(
                EvidenceLimitation(
                    code=EvidenceLimitationCode.ADJUSTMENT_SET_NOT_GRAPH_VALIDATED,
                    description="The supplied adjustment set has not been graph-validated.",
                    provenance=request.adjustment_set.provenance,
                )
            )
        if request.causal_graph is not None:
            limitations.append(
                EvidenceLimitation(
                    code=EvidenceLimitationCode.USER_SUPPLIED_GRAPH,
                    description=(
                        "The causal graph was supplied rather than empirically established."
                    ),
                    provenance=request.causal_graph.provenance,
                )
            )
        by_code = {item.code: item for item in limitations}
        return tuple(by_code[code] for code in sorted(by_code, key=lambda item: item.value))

    @staticmethod
    def _validated_adjustment_set(
        adjustment: AdjustmentSet | None,
        diagnostics: tuple[CausalDiagnostic, ...],
    ) -> AdjustmentSet | None:
        if adjustment is None:
            return None
        adjustment_diagnostics = tuple(
            sorted(
                item.code.value
                for item in diagnostics
                if item.category in {
                    CausalDiagnosticCategory.ADJUSTMENT,
                    CausalDiagnosticCategory.TIMING,
                }
                and (
                    not item.context
                    or any(
                        entry.value in adjustment.variable_ids
                        for entry in item.context
                        if entry.key == "variable_id"
                    )
                )
            )
        )
        status = (
            AdjustmentValidationStatus.INVALID
            if adjustment_diagnostics
            else AdjustmentValidationStatus.VALID
        )
        return adjustment.model_copy(
            update={
                "validation_status": status,
                "diagnostics": adjustment_diagnostics,
            }
        )

    @staticmethod
    def _abstention(
        status: IdentificationStatus,
        diagnostics: tuple[CausalDiagnostic, ...],
    ) -> CausalAbstentionReason | None:
        if status is IdentificationStatus.IDENTIFIED:
            return None
        ordered = tuple(sorted(diagnostics, key=lambda item: item.code.value))
        primary = ordered[0] if ordered else None
        code = (
            primary.code
            if primary is not None
            else CausalDiagnosticCode.INSUFFICIENT_IDENTIFICATION_EVIDENCE
        )
        message = (
            primary.message
            if primary is not None
            else "The request does not provide a supported identification path."
        )
        information = tuple(sorted({item.code.value for item in diagnostics})) or (code.value,)
        return CausalAbstentionReason(
            code=code,
            message=message,
            missing_or_invalid_information=information,
        )


__all__ = ["CausalIdentificationService"]
