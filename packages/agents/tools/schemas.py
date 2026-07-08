from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel

from packages.agents.state import ToolCallRecord

InputModelT = TypeVar("InputModelT", bound=BaseModel)
OutputModelT = TypeVar("OutputModelT", bound=BaseModel)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    input_model: type[InputModelT]
    output_model: type[OutputModelT]
    handler: Callable[[InputModelT], OutputModelT]


@dataclass(frozen=True)
class ExecutedToolCall:
    output: OutputModelT | None
    record: ToolCallRecord
