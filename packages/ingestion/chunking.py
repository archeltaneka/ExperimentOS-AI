from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_TARGET_CHUNK_CHARS = 2800
DEFAULT_OVERLAP_CHARS = 350

SECTION_HEADING_PATTERN = re.compile(r"^(#{2,3})\s+(.+?)\s*$")


@dataclass(frozen=True)
class MarkdownChunk:
    text: str
    token_count: int
    metadata: dict[str, int | str | None]


@dataclass(frozen=True)
class MarkdownSection:
    title: str | None
    text: str


def _estimate_token_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _sections_from_markdown(markdown: str) -> list[MarkdownSection]:
    sections: list[MarkdownSection] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in markdown.splitlines():
        heading = SECTION_HEADING_PATTERN.match(line)
        if heading:
            if current_lines:
                sections.append(
                    MarkdownSection(title=current_title, text="\n".join(current_lines).strip())
                )
            current_title = heading.group(2).strip()
            current_lines = [line]
            continue
        current_lines.append(line)

    if current_lines:
        sections.append(MarkdownSection(title=current_title, text="\n".join(current_lines).strip()))

    return [section for section in sections if section.text]


def _split_section_text(text: str, target_chunk_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= target_chunk_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + target_chunk_chars, len(text))
        if end < len(text):
            paragraph_break = text.rfind("\n\n", start, end)
            sentence_break = text.rfind(". ", start, end)
            word_break = text.rfind(" ", start, end)
            best_break = max(paragraph_break, sentence_break, word_break)
            if best_break > start + target_chunk_chars // 2:
                end = best_break + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap_chars, 0)

    return chunks


def chunk_markdown_report(
    markdown: str,
    *,
    target_chunk_chars: int = DEFAULT_TARGET_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[MarkdownChunk]:
    if target_chunk_chars <= 0:
        raise ValueError("target_chunk_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be non-negative")
    if overlap_chars >= target_chunk_chars:
        raise ValueError("overlap_chars must be smaller than target_chunk_chars")

    chunks: list[MarkdownChunk] = []
    for section in _sections_from_markdown(markdown):
        for section_chunk_index, chunk_text in enumerate(
            _split_section_text(section.text, target_chunk_chars, overlap_chars)
        ):
            chunks.append(
                MarkdownChunk(
                    text=chunk_text,
                    token_count=_estimate_token_count(chunk_text),
                    metadata={
                        "section": section.title,
                        "section_chunk_index": section_chunk_index,
                        "chunk_index": len(chunks),
                    },
                )
            )

    return chunks
