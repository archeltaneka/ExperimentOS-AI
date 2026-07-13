from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.evals.agent_e2e import AgentE2ECase
from packages.evals.dataset import DEFAULT_DATASET_PATH, EvaluationQuestion, load_evaluation_dataset
from packages.evals.prompt_experiments.assignment import assign_prompt_experiment_variant
from packages.evals.prompt_experiments.loader import load_prompt_experiment_definition
from packages.evals.prompt_experiments.reporting import (
    prompt_experiment_report_to_json,
    render_prompt_experiment_report,
    render_prompt_experiment_report_payload,
)
from packages.evals.prompt_experiments.runner import PromptExperimentRunner
from packages.evals.prompt_experiments.validation import validate_prompt_experiment_definition
from packages.ingestion.load_experiment import run_async
from packages.llm.client import MockLLMClient
from packages.retrieval.service import RetrievalMetrics, RetrievalResult

DEFAULT_REPORT_DIR = Path("reports/phase3/prompt_experiments")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run prompt experiments.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate a prompt experiment definition.")
    _add_common_definition_args(validate)

    assign = subparsers.add_parser("assign", help="Assign a deterministic prompt variant.")
    _add_common_definition_args(assign)
    assign.add_argument("--key", required=True, help="Stable runtime randomization key.")

    run_cmd = subparsers.add_parser("run", help="Run a prompt experiment offline.")
    _add_common_definition_args(run_cmd)
    run_cmd.add_argument("--mode", choices=("offline",), default="offline")
    run_cmd.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    run_cmd.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    run_cmd.add_argument("--case-id", default=None)
    run_cmd.add_argument("--judge", action="store_true")
    run_cmd.add_argument("--fail-on-guardrail", action="store_true")
    run_cmd.add_argument("--dry-run", action="store_true")

    report = subparsers.add_parser("report", help="Render an existing JSON report as Markdown.")
    _add_common_definition_args(report)
    report.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    report.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "validate":
        definition = load_prompt_experiment_definition(args.experiment, config_dir=args.config_dir)
        validate_prompt_experiment_definition(definition)
        print(f"validated {definition.experiment_id}")
        return 0
    if args.command == "assign":
        definition = load_prompt_experiment_definition(args.experiment, config_dir=args.config_dir)
        validate_prompt_experiment_definition(definition)
        assignment = assign_prompt_experiment_variant(definition, args.key)
        print(f"{assignment.variant} -> {assignment.prompt_version}")
        return 0
    if args.command == "run":
        return run_async(_run_prompt_experiment(args))
    if args.command == "report":
        return _render_existing_report(args)
    return 2


def _render_existing_report(args: argparse.Namespace) -> int:
    json_path = args.report_dir / f"{args.experiment}.json"
    output_path = args.output or args.report_dir / f"{args.experiment}.md"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = render_prompt_experiment_report_payload(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return 0


async def _run_prompt_experiment(args: argparse.Namespace) -> int:
    definition = load_prompt_experiment_definition(args.experiment, config_dir=args.config_dir)
    validate_prompt_experiment_definition(definition)
    if args.dry_run:
        print(f"validated {definition.experiment_id}")
        return 0

    questions = _resolve_questions(args.dataset, case_id=args.case_id)
    runner = PromptExperimentRunner(
        definition=definition,
        qa_questions=questions,
        ask_cases=tuple(_build_legacy_ask_cases(questions)),
        retrieval_service=_FixtureRetrievalService(questions),
        llm_client_factory=lambda: MockLLMClient(
            model="mock-prompt-experiment",
            response_builder=_build_offline_fixture_answer,
        ),
        dataset_label=str(args.dataset),
        judge_mode=args.judge,
    )
    report = await runner.run()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = args.report_dir / f"{definition.experiment_id}.md"
    json_path = args.report_dir / f"{definition.experiment_id}.json"
    markdown_path.write_text(render_prompt_experiment_report(report), encoding="utf-8")
    json_path.write_text(prompt_experiment_report_to_json(report), encoding="utf-8")
    print(markdown_path)
    if args.fail_on_guardrail and report.recommendation.outcome == "retain_control":
        return 1
    return 0


def _add_common_definition_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--experiment", required=True, help="Experiment identifier.")
    parser.add_argument("--config-dir", type=Path, default=None)


def _resolve_questions(dataset_path: Path, *, case_id: str | None) -> list[EvaluationQuestion]:
    questions = load_evaluation_dataset(dataset_path)
    if case_id is None:
        return questions
    return [question for question in questions if question.id == case_id]


def _build_legacy_ask_cases(questions: list[EvaluationQuestion]) -> list[AgentE2ECase]:
    if not questions:
        return []
    question = questions[0]
    return [
        AgentE2ECase(
            id=f"legacy-{question.id}",
            question=question.question,
            scenario="legacy_fallback",
            ask_mode="legacy_rag",
            experiment_id=question.experiment_id,
            top_k=5,
            expected_min_citations=1,
        )
    ]


class _FixtureRetrievalService:
    def __init__(self, questions: list[EvaluationQuestion]) -> None:
        self._question_map = {question.question: question for question in questions}
        self.last_metrics = None

    async def search_by_experiment(
        self,
        experiment_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        question = self._question_map[query]
        results = [
            RetrievalResult(
                experiment_id=experiment_id,
                experiment_name=question.expected_documents[0],
                document_id=f"{question.id}-document",
                document_name=question.expected_documents[0],
                chunk_text=question.reference_answer,
                similarity=1.0,
                metadata={"source": "evaluation_dataset_fixture"},
            )
        ]
        self.last_metrics = RetrievalMetrics(
            embedding_time_ms=0.0,
            vector_search_time_ms=0.0,
            retrieved_chunks=min(len(results), top_k),
            average_similarity=1.0,
        )
        return results[:top_k]


def _build_offline_fixture_answer(prompt: str, system_instruction: str) -> str:
    if "Prefer abstaining over guessing." in system_instruction:
        return "Insufficient evidence exists to answer the question. Source: evaluation fixture."
    document_name = "evaluation fixture"
    for line in prompt.splitlines():
        if line.startswith("Document:"):
            document_name = line.split("Document:", maxsplit=1)[1].strip() or document_name
            break
    return f"{document_name}. Source: {document_name}."


if __name__ == "__main__":
    raise SystemExit(main())
