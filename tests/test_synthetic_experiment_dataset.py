import csv
import json
from pathlib import Path

DATASET_ROOT = Path("data/synthetic/experiments")
REQUIRED_FILES = {"metadata.json", "metrics.csv", "report.md", "events.csv"}
REQUIRED_REPORT_SECTIONS = [
    "Background",
    "Hypothesis",
    "Experiment Design",
    "Results",
    "Limitations",
    "Risks",
    "Recommendation",
    "Future Work",
]
REQUIRED_AREAS = {
    "payment recommendation",
    "hotel image quality",
    "search ranking",
    "checkout ux",
    "pricing",
    "loyalty",
    "crm notifications",
    "recommendation systems",
    "search filters",
    "premium subscriptions",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def test_synthetic_experiment_dataset_contract() -> None:
    experiment_dirs = sorted(path for path in DATASET_ROOT.iterdir() if path.is_dir())

    assert len(experiment_dirs) == 10

    covered_areas: set[str] = set()
    for experiment_dir in experiment_dirs:
        assert {path.name for path in experiment_dir.iterdir() if path.is_file()} == REQUIRED_FILES

        metadata = json.loads((experiment_dir / "metadata.json").read_text(encoding="utf-8"))
        metrics = read_csv(experiment_dir / "metrics.csv")
        events = read_csv(experiment_dir / "events.csv")
        report = (experiment_dir / "report.md").read_text(encoding="utf-8")

        assert metadata["experiment_id"] == experiment_dir.name
        assert metadata["area"] in REQUIRED_AREAS
        assert metadata["status"] in {"completed", "monitoring", "stopped", "rolled_out"}
        assert metadata["business_decision"]
        assert metadata["owner"]["name"]
        assert metadata["owner"]["team"]
        assert metadata["hypothesis"]
        assert metadata["primary_metric"]
        assert len(metadata["secondary_metrics"]) >= 2
        assert len(metadata["imperfections"]) >= 1
        covered_areas.add(metadata["area"])

        assert {row["variant"] for row in metrics} == {"control", "treatment"}
        assert all(row["experiment_id"] == metadata["experiment_id"] for row in metrics)
        assert all(row["metric_name"] for row in metrics)
        assert all(float(row["value"]) >= 0 for row in metrics)

        variant_counts = {
            "control": sum(1 for row in events if row["variant"] == "control"),
            "treatment": sum(1 for row in events if row["variant"] == "treatment"),
        }
        assert len(events) >= 100
        assert all(row["experiment_id"] == metadata["experiment_id"] for row in events)
        assert all(row["event_id"] for row in events)
        assert all(row["user_id"] for row in events)
        assert all(row["country"] for row in events)
        assert all(row["event_name"] for row in events)
        assert all(row["timestamp"] for row in events)
        assert set(variant_counts) == {"control", "treatment"}
        assert min(variant_counts.values()) > 0

        sample_size_rows = [row for row in metrics if row["metric_name"] == "sample_size"]
        assert len(sample_size_rows) == 2
        assert {
            row["variant"]: int(float(row["value"]))
            for row in sample_size_rows
        } == variant_counts

        words = report.split()
        assert 600 <= len(words) <= 1000
        for section in REQUIRED_REPORT_SECTIONS:
            assert f"## {section}" in report
        assert metadata["primary_metric"] in report

    assert covered_areas == REQUIRED_AREAS
