"""Deterministic closed interval operations; ranges never imply distributions."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Bounds:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.lower) or not math.isfinite(self.upper):
            raise ValueError("nonfinite interval arithmetic")
        if self.lower > self.upper:
            raise ValueError("unordered interval")


def multiply(a: Bounds, b: Bounds) -> Bounds:
    endpoints = (a.lower * b.lower, a.lower * b.upper, a.upper * b.lower, a.upper * b.upper)
    return Bounds(min(endpoints), max(endpoints))


def add(a: Bounds, b: Bounds) -> Bounds:
    return Bounds(a.lower + b.lower, a.upper + b.upper)


def subtract(a: Bounds, b: Bounds) -> Bounds:
    return Bounds(a.lower - b.upper, a.upper - b.lower)
