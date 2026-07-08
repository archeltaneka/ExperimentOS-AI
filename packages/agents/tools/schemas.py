from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from packages.agents.state import ToolCallRecord


@dataclass(frozen=True)
class ToolSpec[InputModelT: BaseModel, OutputModelT: BaseModel]:
    name: str
    input_model: type[InputModelT]
    output_model: type[OutputModelT]
    handler: Callable[[InputModelT], OutputModelT]


@dataclass(frozen=True)
class ExecutedToolCall[OutputModelT]:
    output: OutputModelT | None
    record: ToolCallRecord
