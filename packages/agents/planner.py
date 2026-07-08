from __future__ import annotations

import re
from dataclasses import dataclass

from packages.agents.state import AgentIntent, ExperimentContext, RequiredAgent

PLANNER_RULE_VERSION = "deterministic_v1"

_SUMMARY_TERMS = (
    "executive summary",
    "for executives",
    "for leadership",
    "summarize",
    "summary",
    "brief me",
)
_RISK_TERMS = (
    "risk",
    "risks",
    "risky",
    "concern",
    "concerns",
    "downside",
    "downsides",
    "failure mode",
    "failure modes",
)
_DECISION_TERMS = (
    "should we",
    "roll out",
    "rollout",
    "launch",
    "ship",
    "approve",
    "greenlight",
    "go live",
    "release",
)
_BUSINESS_IMPACT_TERMS = (
    "business impact",
    "commercial impact",
    "revenue",
    "conversion",
    "retention",
    "roi",
    "arr",
    "gmv",
    "sales",
    "business case",
)
_LOOKUP_TERMS = (
    "what happened",
    "tell me about",
    "show me",
    "look up",
    "find",
    "status of",
    "what did we learn",
    "how did",
    "compare",
)
_DOMAIN_TERMS = (
    "experiment",
    "experiments",
    "launch",
    "rollout",
    "decision",
    "risk",
    "impact",
    "summary",
    "executive",
)
_EXPERIMENT_HINT_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("payment recommendation", ("payment recommendation",)),
    ("hotel image quality", ("hotel image quality",)),
    ("checkout ux", ("checkout ux", "checkout user experience")),
    ("search ranking", ("search ranking",)),
    ("loyalty", ("loyalty", "loyalty program", "loyalty programme")),
    ("crm", ("crm", "customer relationship management")),
    ("premium subscription", ("premium subscription",)),
    ("recommendation system", ("recommendation system",)),
    ("search filters", ("search filters",)),
)
_REQUIRED_AGENTS: dict[AgentIntent, list[RequiredAgent]] = {
    "general_question": ["retrieval"],
    "experiment_lookup": ["retrieval"],
    "decision_support": [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "executive_summary",
    ],
    "risk_assessment": [
        "retrieval",
        "experiment_analysis",
        "risk_assessment",
    ],
    "business_impact": [
        "retrieval",
        "experiment_analysis",
        "business_impact",
    ],
    "executive_summary": [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "executive_summary",
    ],
    "unknown": [],
}


@dataclass(frozen=True, slots=True)
class PlannerPlan:
    intent: AgentIntent
    required_agents: list[RequiredAgent]
    experiment_context: ExperimentContext
    planner_notes: str
    metrics: dict[str, object]
    experiment_hints: list[str]


def plan_question(question: str) -> PlannerPlan:
    normalized = _normalize(question)
    experiment_hints = extract_experiment_hints(normalized)
    intent = classify_intent(normalized, experiment_hints)
    required_agents = required_agents_for_intent(intent)
    experiment_context = build_experiment_context(experiment_hints)
    planner_notes = build_planner_notes(intent, required_agents, experiment_hints)
    metrics = {
        "planner_rule_version": PLANNER_RULE_VERSION,
        "planner_required_agent_count": len(required_agents),
        "planner_experiment_hint_count": len(experiment_hints),
    }
    return PlannerPlan(
        intent=intent,
        required_agents=required_agents,
        experiment_context=experiment_context,
        planner_notes=planner_notes,
        metrics=metrics,
        experiment_hints=experiment_hints,
    )


def classify_intent(normalized_question: str, experiment_hints: list[str]) -> AgentIntent:
    if _contains_any(normalized_question, _SUMMARY_TERMS):
        return "executive_summary"
    if _contains_any(normalized_question, _RISK_TERMS):
        return "risk_assessment"
    if _contains_any(normalized_question, _DECISION_TERMS):
        return "decision_support"
    if _contains_any(normalized_question, _BUSINESS_IMPACT_TERMS):
        return "business_impact"
    if experiment_hints and (
        _contains_any(normalized_question, _LOOKUP_TERMS)
        or "experiment" in normalized_question
        or "experiments" in normalized_question
    ):
        return "experiment_lookup"
    if experiment_hints or _contains_any(normalized_question, _DOMAIN_TERMS):
        return "general_question"
    return "unknown"


def required_agents_for_intent(intent: AgentIntent) -> list[RequiredAgent]:
    return list(_REQUIRED_AGENTS[intent])


def extract_experiment_hints(normalized_question: str) -> list[str]:
    hints: list[str] = []
    for canonical_name, aliases in _EXPERIMENT_HINT_ALIASES:
        if any(alias in normalized_question for alias in aliases):
            hints.append(canonical_name)
    return hints


def build_experiment_context(experiment_hints: list[str]) -> ExperimentContext:
    filters: dict[str, object] = {}
    if experiment_hints:
        filters["experiment_hints"] = experiment_hints
    return {
        "experiment_ids": [],
        "filters": filters,
    }


def build_planner_notes(
    intent: AgentIntent,
    required_agents: list[RequiredAgent],
    experiment_hints: list[str],
) -> str:
    required_agents_text = ", ".join(required_agents) if required_agents else "none"
    experiment_hint_text = ", ".join(experiment_hints) if experiment_hints else "none"
    return (
        f"Applied {PLANNER_RULE_VERSION}; classified intent as {intent}; "
        f"selected downstream agents: {required_agents_text}; "
        f"experiment hints: {experiment_hint_text}."
    )


def _contains_any(value: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in value for phrase in phrases)


def _normalize(question: str) -> str:
    lowered = question.strip().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", lowered)).strip()
