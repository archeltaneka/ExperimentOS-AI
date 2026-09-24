"""Owned optional-runtime fixtures and honest dependency classification."""

from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import patch

from .models import WorkflowExpectations

PACKAGES = {"econml_dml": "econml", "econml_hte": "econml", "dowhy": "dowhy"}


def dependency_state(package):
    """Resolve the current probe without retaining an import-time override."""
    from ..advanced.harness import dependency_state as current_dependency_state

    return current_dependency_state(package)


@contextmanager
def dependency_override(method, scenario):
    from packages.experiments.analysis.causal.dowhy import dependency as dd
    from packages.experiments.analysis.causal.econml import dependency as ed

    dependency = dd if method == "dowhy" else ed
    name = "load_dowhy" if method == "dowhy" else "load_econml"
    code = (
        "OPTIONAL_DEPENDENCY_UNAVAILABLE"
        if scenario == "absent"
        else "INCOMPATIBLE_DEPENDENCY_RUNTIME"
    )
    with patch.object(
        dependency, name, side_effect=dependency.AdapterError(code, "Controlled runtime case")
    ):
        yield


@contextmanager
def case_runtime(case):
    scenario = "absent" if case.optional_unavailable else case.optional_scenario
    if scenario:
        with dependency_override(case.expected_method, scenario):
            yield
    else:
        yield


def effective_case(case):
    package = PACKAGES.get(case.expected_method)
    if not package:
        return case, "not_required", None
    if case.optional_unavailable or case.optional_scenario:
        return case, "controlled", None
    state, version = dependency_state(package)
    if state == "unavailable":
        return (
            case.model_copy(
                update={
                    "expected_status": "unavailable",
                    "expectations": WorkflowExpectations(),
                }
            ),
            state,
            version,
        )
    return case, state, version


def build_optional_cases(core):
    from packages.experiments.analysis.causal.advanced.models import AdvancedEstimatorConfig
    from packages.experiments.analysis.causal.models import ObservationalAnalysisRequest

    from ..advanced.references.dowhy import execution, known_effect_table
    from .fixtures import _case

    cases = []
    for method in PACKAGES:
        if method == "dowhy":
            native = execution(run_estimation=True)
            declaration = ObservationalAnalysisRequest(
                request_id=native.identification_result.request_id,
                identification=native.identification_result.identification_request,
            )
            case = _case(
                method + "-real",
                method,
                {
                    "dataset": {"reference": "sample", "version": "1"},
                    "analysis_request": declaration.model_dump(mode="json"),
                    "binding": native.binding.model_dump(mode="json"),
                    "configuration": native.configuration.model_dump(mode="json"),
                },
                known_effect_table(),
            )
        else:
            source = next(
                c for c in core if c.case_id == method.removeprefix("econml_") + "-success"
            )
            payload = deepcopy(source.ask_payload)
            if method == "econml_hte":
                from ..advanced.references.econml import dr_execution

                native = dr_execution(fold_count=4)
                payload["analysis"]["parameters"]["configuration"] = (
                    native.configuration.model_dump(mode="json")
                )
                payload["analysis"]["parameters"]["analysis_request"] = (
                    ObservationalAnalysisRequest(
                        request_id=native.identification_result.request_id,
                        identification=native.identification_result.identification_request,
                    ).model_dump(mode="json")
                )
            payload["analysis"]["method"] = method
            payload["analysis"]["parameters"]["adapter_configuration"] = AdvancedEstimatorConfig(
                constant_effect_assumption=True
            ).model_dump(mode="json")
            case = source.model_copy(
                update={
                    "case_id": method + "-real",
                    "expected_method": method,
                    "ask_payload": payload,
                }
            )
        case = case.model_copy(update={"family": "adapter"})
        cases.extend(
            (
                case,
                case.model_copy(
                    update={
                        "case_id": method + "-absent",
                        "optional_unavailable": True,
                        "expected_status": "unavailable",
                    }
                ),
                case.model_copy(
                    update={
                        "case_id": method + "-broken",
                        "optional_scenario": "broken",
                        "expected_status": "failed",
                    }
                ),
            )
        )
    return tuple(cases)
