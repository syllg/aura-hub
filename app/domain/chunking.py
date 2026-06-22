from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

POINT_NAMESPACE = uuid.UUID("5d18983d-e18d-4ed1-9cb9-174ad5d97d87")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
VERSION_RE = re.compile(r"Versi\s+Dokumen\s*:\s*([\w.-]+)", re.IGNORECASE)


@dataclass(slots=True)
class ParsedPage:
    page_number: int | None
    text: str


@dataclass(slots=True)
class ParsedDocument:
    filename: str
    content_type: str
    pages: list[ParsedPage]
    detected_version: str | None = None


@dataclass(slots=True)
class Block:
    type: str
    content: str
    heading_path: list[str]
    page_number: int | None


@dataclass(slots=True)
class Chunk:
    id: str
    document_id: str
    index: int
    type: str
    content: str
    embedding_text: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    token_count: int
    content_hash: str


def estimate_tokens(text: str) -> int:
    return max(1, len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)))


def detect_version(text: str) -> str | None:
    match = VERSION_RE.search(text)
    return match.group(1) if match else None


def _is_table_start(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and lines[index].count("|") >= 2
        and bool(TABLE_SEPARATOR_RE.match(lines[index + 1]))
    )


def _flush_buffer(
    blocks: list[Block],
    buffer: list[str],
    heading_path: list[str],
    page_number: int | None,
) -> None:
    if not buffer:
        return
    content = "\n".join(buffer).strip()
    if content:
        block_type = (
            "list"
            if all(re.match(r"^\s*(?:[-*+] |\d+[.)] )", line) for line in buffer if line.strip())
            else "paragraph"
        )
        blocks.append(Block(block_type, content, heading_path.copy(), page_number))
    buffer.clear()


def parse_blocks(document: ParsedDocument) -> list[Block]:
    blocks: list[Block] = []
    heading_stack: list[str] = []
    markdown = document.content_type in {"text/markdown", "text/x-markdown"}
    for page in document.pages:
        text = page.text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
        lines = text.split("\n")
        buffer: list[str] = []
        index = 0
        while index < len(lines):
            line = lines[index].rstrip()
            heading_match = HEADING_RE.match(line) if markdown else None
            if heading_match:
                _flush_buffer(blocks, buffer, heading_stack, page.page_number)
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(title)
                index += 1
                continue
            if markdown and _is_table_start(lines, index):
                _flush_buffer(blocks, buffer, heading_stack, page.page_number)
                table_lines = [line, lines[index + 1].rstrip()]
                index += 2
                while index < len(lines) and lines[index].count("|") >= 2:
                    table_lines.append(lines[index].rstrip())
                    index += 1
                blocks.append(
                    Block("table", "\n".join(table_lines), heading_stack.copy(), page.page_number)
                )
                continue
            if not line.strip():
                _flush_buffer(blocks, buffer, heading_stack, page.page_number)
            else:
                normalized = line if markdown and "|" in line else re.sub(r"\s+", " ", line).strip()
                buffer.append(normalized)
            index += 1
        _flush_buffer(blocks, buffer, heading_stack, page.page_number)
    return blocks


def _split_long_text(text: str, maximum: int, overlap: int) -> list[str]:
    tokens = text.split()
    if len(tokens) <= maximum:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(1, maximum - overlap)
    while start < len(tokens):
        chunks.append(" ".join(tokens[start : start + maximum]))
        start += step
    return chunks


def _split_table(content: str, maximum: int) -> list[str]:
    lines = content.splitlines()
    if len(lines) < 3 or estimate_tokens(content) <= maximum:
        return [content]
    header = lines[:2]
    rows = lines[2:]
    result: list[str] = []
    current = header.copy()
    for row in rows:
        proposed = current + [row]
        if len(current) > 2 and estimate_tokens("\n".join(proposed)) > maximum:
            result.append("\n".join(current))
            current = header + [row]
        else:
            current = proposed
    if len(current) > 2:
        result.append("\n".join(current))
    return result


def build_chunks(
    document: ParsedDocument,
    *,
    document_id: str,
    document_checksum: str,
    target_tokens: int = 420,
    maximum_tokens: int = 520,
    overlap_tokens: int = 60,
) -> list[Chunk]:
    blocks = parse_blocks(document)
    raw_chunks: list[tuple[str, str, list[str], int | None]] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if (
            block.type in {"paragraph", "list"}
            and index + 1 < len(blocks)
            and blocks[index + 1].type == "table"
            and blocks[index + 1].heading_path == block.heading_path
        ):
            table = blocks[index + 1]
            combined = f"{block.content}\n\n{table.content}"
            if estimate_tokens(combined) <= maximum_tokens:
                raw_chunks.append(("table", combined, table.heading_path, table.page_number))
                index += 2
                continue
        if block.type == "table":
            for table_part in _split_table(block.content, maximum_tokens):
                raw_chunks.append(("table", table_part, block.heading_path, block.page_number))
        else:
            combined_parts = [block.content]
            combined_type = block.type
            lookahead = index + 1
            while lookahead < len(blocks):
                following = blocks[lookahead]
                if (
                    following.type == "table"
                    or following.heading_path != block.heading_path
                    or following.page_number != block.page_number
                ):
                    break
                current = "\n\n".join(combined_parts)
                proposed = f"{current}\n\n{following.content}"
                if (
                    estimate_tokens(proposed) > maximum_tokens
                    or estimate_tokens(current) >= target_tokens
                ):
                    break
                combined_parts.append(following.content)
                if following.type != combined_type:
                    combined_type = "paragraph"
                lookahead += 1
            combined_content = "\n\n".join(combined_parts)
            for text_part in _split_long_text(combined_content, maximum_tokens, overlap_tokens):
                raw_chunks.append((combined_type, text_part, block.heading_path, block.page_number))
            index = lookahead - 1
        index += 1

    chunks: list[Chunk] = []
    for chunk_index, (chunk_type, content, heading_path, page_number) in enumerate(raw_chunks):
        content = content.strip()
        if not content:
            continue
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        point_id = str(
            uuid.uuid5(
                POINT_NAMESPACE,
                f"{document_checksum}:{chunk_index}:{content_hash}",
            )
        )
        heading = " > ".join(heading_path)
        embedding_text = f"{heading}\n\n{content}" if heading else content
        chunks.append(
            Chunk(
                id=point_id,
                document_id=document_id,
                index=chunk_index,
                type=chunk_type,
                content=content,
                embedding_text=embedding_text,
                heading_path=heading_path,
                page_start=page_number,
                page_end=page_number,
                token_count=estimate_tokens(content),
                content_hash=content_hash,
            )
        )
    return chunks
