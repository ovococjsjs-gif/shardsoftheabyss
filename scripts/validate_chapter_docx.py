#!/usr/bin/env python3
"""Validate separately exported chapter DOCX files against Markdown sources."""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "03-manuscript"
CHAPTER_DIR = ROOT / "exports" / "chapters"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REQUIRED = {
    "[Content_Types].xml", "_rels/.rels", "word/document.xml",
    "word/styles.xml", "word/settings.xml", "word/_rels/document.xml.rels",
    "docProps/core.xml", "docProps/app.xml",
}


def source_path(number: int) -> Path:
    found = list(MANUSCRIPT.glob(f"arc-*/ch-{number:02d}.md"))
    if len(found) != 1:
        raise AssertionError(f"Для главы {number} найдено Markdown-файлов: {len(found)}")
    return found[0]


def strip_inline(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return re.sub(r"\*([^*]+)\*", r"\1", text)


def expected(number: int) -> tuple[list[str], int]:
    source = source_path(number).read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    blocks: list[str] = []
    italics = 0
    for index, raw in enumerate(source.splitlines()):
        line = raw.strip()
        if not line:
            continue
        if index == 0:
            blocks.append(line.removeprefix("# "))
        elif line == "---":
            blocks.append("* * *")
        else:
            italics += len(re.findall(r"(?<!\*)\*([^*]+)\*(?!\*)", line))
            blocks.append(strip_inline(line))
    return blocks, italics


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.iter(f"{W}t"))


def validate_one(path: Path, number: int) -> tuple[int, int]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise AssertionError(f"Глава {number}: повреждён ZIP entry {bad}")
        names = set(archive.namelist())
        missing = REQUIRED - names
        if missing:
            raise AssertionError(f"Глава {number}: нет частей {sorted(missing)}")
        if not any(name.startswith("word/header") for name in names):
            raise AssertionError(f"Глава {number}: нет колонтитула")
        if not any(name.startswith("word/footer") for name in names):
            raise AssertionError(f"Глава {number}: нет нижнего колонтитула")
        try:
            document = ET.fromstring(archive.read("word/document.xml"))
        except ET.ParseError as exc:
            raise AssertionError(f"Глава {number}: невалидный document.xml: {exc}") from exc
        actual = [paragraph_text(p) for p in document.iter(f"{W}p")]
        actual = [text for text in actual if text]
        wanted, italic_expected = expected(number)
        if actual != wanted:
            limit = min(len(actual), len(wanted))
            mismatch = next((i for i in range(limit) if actual[i] != wanted[i]), limit)
            raise AssertionError(
                f"Глава {number}: расхождение на блоке {mismatch}: "
                f"actual={actual[mismatch:mismatch+1]!r}, expected={wanted[mismatch:mismatch+1]!r}"
            )
        raw = archive.read("word/document.xml").decode("utf-8")
        italic_actual = len(re.findall(r"<w:i(?:\s|/|>)", raw))
        if italic_actual < italic_expected:
            raise AssertionError(f"Глава {number}: потерян курсив {italic_actual} < {italic_expected}")
        if "**" in "".join(actual) or "\ufffd" in "".join(actual):
            raise AssertionError(f"Глава {number}: остались маркеры или U+FFFD")
        return len(actual), path.stat().st_size


def main() -> int:
    files = sorted(CHAPTER_DIR.glob("Глава_*.docx"))
    expected_names = [f"Глава_{number:02d}.docx" for number in range(1, 37)]
    if [path.name for path in files] != expected_names:
        print("FAIL: ожидались отдельные файлы глав 01–36", file=sys.stderr)
        return 1
    blocks = 0
    size = 0
    try:
        for number, path in enumerate(files, 1):
            count, bytes_count = validate_one(path, number)
            blocks += count
            size += bytes_count
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: 36 отдельных DOCX")
    print(f"OK: {blocks} блоков совпадают с Markdown")
    print(f"OK: общий размер {size / 1024 / 1024:.2f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
