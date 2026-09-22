"""Core workflow commands must not require optional causal dependencies."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("operation", ["validation", "unavailable_adapter"])
def test_core_commands_without_optional_causal_dependencies(operation: str) -> None:
    prelude = """
import runpy
import sys

for name in ('pandas', 'dowhy', 'econml'):
    sys.modules[name] = None
"""
    commands = {
        "validation": """
sys.argv = [
    'run_prompt_experiment', 'validate',
    '--experiment', 'rag-answer-abstention-v1-v2',
]
runpy.run_module('packages.evals.run_prompt_experiment', run_name='__main__')
""",
        "unavailable_adapter": """
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch
from packages.experiments.analysis.causal.dowhy import DoWhyAdapter
from tests.causal_identification_fixtures import provenance
from tests.dowhy_fixtures import execution

with patch('importlib.metadata.version', side_effect=PackageNotFoundError('dowhy')):
    result = DoWhyAdapter().analyze(execution(), provenance=provenance())
assert result.status.value == 'abstained', result
assert result.abstention_reason.code.value == 'OPTIONAL_DEPENDENCY_UNAVAILABLE', result
""",
    }
    result = subprocess.run(
        [sys.executable, "-c", prelude + commands[operation]],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "LLM_PROVIDER": "mock", "EMBEDDING_PROVIDER": "fake"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
