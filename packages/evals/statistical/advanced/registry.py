"""Deterministic inventory of implemented capabilities, not estimator selection."""

from dataclasses import dataclass

from .models import Applicability


@dataclass(frozen=True)
class Capability:
    capability_id: str
    adapter_id: str
    method: str
    implementation_version: str
    estimand: str
    dependency: str | None = None
    uncertainty: Applicability = Applicability.REQUIRED
    uncertainty_support: str = "supported"
    adapter_version: str = "1"
    treatment_types: tuple[str, ...] = ("binary",)
    outcome_types: tuple[str, ...] = ("continuous",)
    seed_support: bool = True
    checks: tuple[str, ...] = (
        "interface",
        "status",
        "provenance",
        "repeatability",
        "privacy",
        "capability",
    )


CAPABILITIES = tuple(
    sorted(
        (
            Capability("repository_dml", "repository_dml", "dml", "dml-v1", "ate"),
            Capability(
                "repository_hte",
                "repository_hte",
                "dml_orthogonal_subgroup_interactions",
                "hte-v1",
                "cate",
            ),
            Capability(
                "econml_dml", "econml_linear_dml", "partialling_out_dml", "1", "ate", "econml"
            ),
            Capability(
                "econml_hte",
                "econml_linear_dr_subgroups",
                "doubly_robust_subgroup_effects",
                "hte-dr-v1",
                "cate",
                "econml",
            ),
            Capability(
                "dowhy_identification",
                "experimentos_dowhy",
                "default_backdoor",
                "1",
                "ate",
                "dowhy",
                Applicability.NOT_APPLICABLE,
                "not_applicable",
                seed_support=False,
            ),
            Capability(
                "dowhy_estimation",
                "experimentos_dowhy",
                "backdoor.linear_regression",
                "1",
                "ate",
                "dowhy",
                Applicability.OPTIONAL,
                "unsupported",
            ),
            *(
                Capability(
                    "dowhy_" + short,
                    "experimentos_dowhy",
                    method,
                    "1",
                    "ate",
                    "dowhy",
                    Applicability.NOT_APPLICABLE,
                    "not_applicable",
                )
                for short, method in (
                    ("placebo", "placebo_treatment_refuter"),
                    ("common_cause", "random_common_cause"),
                    ("subset", "data_subset_refuter"),
                )
            ),
        ),
        key=lambda c: c.capability_id,
    )
)
REGISTRY = {c.capability_id: c for c in CAPABILITIES}
