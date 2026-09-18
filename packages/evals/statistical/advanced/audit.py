"""Independent input-to-evidence audits without exporting row identities."""

from .checks import check


def record_nuisance_calls(stack):
    """Observe real adapter inputs; retain identities only in this ephemeral audit."""
    from unittest.mock import patch

    from packages.experiments.analysis.causal.dml.adapter import (
        SklearnLogisticTreatmentAdapter,
        SklearnRidgeOutcomeAdapter,
    )
    from packages.experiments.analysis.causal.dml.folds import canonical_observation_key

    calls = []
    by_instance = {}
    instances = []  # Prevent object-id reuse within the execution.

    def wrap(original, role, operation):
        def observed(instance, batch, *args, **kwargs):
            keys = tuple(canonical_observation_key(v) for v in batch.observation_ids)
            if operation == "fit":
                record = {"role": role, "train": keys, "score": ()}
                calls.append(record)
                by_instance[id(instance)] = record
                instances.append(instance)
            else:
                record = by_instance.get(id(instance))
                if record is None:
                    record = {"role": role, "train": (), "score": ()}
                    calls.append(record)
                record["score"] += keys
            return original(instance, batch, *args, **kwargs)

        return observed

    for adapter, role, prediction in (
        (SklearnRidgeOutcomeAdapter, "outcome", "predict"),
        (SklearnLogisticTreatmentAdapter, "treatment", "predict_probability"),
    ):
        for method in ("fit", prediction):
            stack.enter_context(
                patch.object(adapter, method, wrap(getattr(adapter, method), role, method))
            )
    return calls


def audit_execution(execution, request, table, capability):
    result = execution.result
    source = request.identification_result
    if capability.capability_id == "repository_dml":
        request_matches = (
            result.request_id == request.request_id
            and result.analysis_request.identification == source.identification_request
            and result.binding == request.binding
            and result.configuration == request.configuration
        )
    else:
        request_matches = result.execution_request == request
        if not request_matches:
            try:
                # Public validators canonicalize unordered variable/assumption
                # declarations; that normalization is not a contract change.
                request_matches = result.execution_request == type(request).model_validate(
                    request.model_dump(mode="python")
                )
            except (ValueError, TypeError):
                request_matches = False
    checks = [check("request_integrity", "identification", request_matches)]
    if result.status.value != "completed":
        return checks
    if capability.capability_id in {"repository_dml", "repository_hte", "econml_hte"}:
        checks.append(check("executed_estimand", "estimand", result.estimand == source.estimand))
    if capability.capability_id.startswith("dowhy"):
        return checks
    from packages.experiments.analysis.causal.dml.folds import (
        FoldObservation,
        validate_fold_plan_integrity,
    )
    from packages.experiments.analysis.causal.dml.validation import validate_dml_input
    from packages.experiments.analysis.causal.hte.assignment import assign_subgroups
    from packages.experiments.analysis.causal.hte.validation import validate_hte_input

    hte = "hte" in capability.capability_id
    validated = (
        validate_hte_input(
            request,
            table,
            supported_method=(
                "doubly_robust_subgroup_effects"
                if capability.dependency
                else "partialling_out_dml_subgroup_interactions"
            ),
        )
        if hte
        else validate_dml_input(request, table)
    )
    try:
        validate_fold_plan_integrity(
            tuple(
                FoldObservation(observation_id=r.observation_id, treated=r.treated)
                for r in validated.rows
            ),
            result.fold_plan,
        )
        fold_ok = len(result.fold_fits) == result.fold_plan.fold_count
        for fit, summary in zip(result.fold_fits, result.fold_plan.summaries, strict=True):
            fold_ok &= (
                fit.fold_index == summary.fold_index
                and fit.train_count == summary.train_count
                and fit.score_count == summary.score_count
                and fit.outcome_fit.training_count == summary.train_count
                and fit.treatment_fit.training_count == summary.train_count
            )
    except (ValueError, AttributeError, TypeError):
        fold_ok = False
    checks.append(check("fold_audit", "data_leakage", fold_ok))
    if capability.dependency is None:
        from packages.experiments.analysis.causal.dml.folds import canonical_observation_key

        expected_scores = [
            frozenset(
                canonical_observation_key(a.observation_id)
                for a in result.fold_plan.assignments
                if a.fold_index == index
            )
            for index in range(result.fold_plan.fold_count)
        ]
        universe = frozenset().union(*expected_scores)
        observed_ok = True
        for role in ("outcome", "treatment"):
            calls = [c for c in execution.nuisance_calls if c["role"] == role]
            observed_ok &= len(calls) == len(expected_scores)
            for call, expected_score in zip(calls, expected_scores, strict=False):
                train, score = call["train"], call["score"]
                observed_ok &= (
                    len(train) == len(set(train))
                    and len(score) == len(set(score))
                    and set(score) == expected_score
                    and set(train) == universe - expected_score
                    and not set(train).intersection(score)
                )
        checks.append(check("observed_cross_fitting", "data_leakage", observed_ok))
    if hte:
        assignment = assign_subgroups(request, table)
        checks.append(
            check(
                "group_audit",
                "heterogeneity_safety",
                assignment.fingerprint_sha256 == result.assignment_fingerprint_sha256
                and tuple(c.as_public_counts() for c in validated.subgroup_counts)
                == tuple(g.sample_counts for g in result.subgroup_results),
            )
        )
    return checks
