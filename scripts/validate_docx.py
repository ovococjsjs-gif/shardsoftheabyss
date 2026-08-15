#!/usr/bin/env python3
"""Structural and content validation for exported manuscript DOCX files."""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "03-manuscript"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

REQUIRED = {
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
    "word/styles.xml",
    "word/settings.xml",
    "word/_rels/document.xml.rels",
    "docProps/core.xml",
    "docProps/app.xml",
}


def chapter_files() -> list[Path]:
    files = sorted(
        MANUSCRIPT.glob("arc-*/ch-*.md"),
        key=lambda p: int(re.search(r"ch-(\d+)", p.name).group(1)),
    )
    numbers = [int(re.search(r"ch-(\d+)", p.name).group(1)) for p in files]
    if numbers != list(range(1, 37)):
        raise AssertionError(f"Неверный порядок глав: {numbers}")
    return files


def strip_inline_markdown(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text


def expected_body() -> tuple[list[str], int]:
    paragraphs: list[str] = []
    italic_segments = 0
    for path in chapter_files():
        source = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        if "\ufffd" in source:
            raise AssertionError(f"Повреждённый символ в {path}")
        for index, raw in enumerate(source.splitlines()):
            line = raw.strip()
            if not line:
                continue
            if index == 0:
                paragraphs.append(line.removeprefix("# "))
                continue
            if line == "---":
                paragraphs.append("* * *")
                continue
            italic_segments += len(re.findall(r"(?<!\*)\*([^*]+)\*(?!\*)", line))
            paragraphs.append(strip_inline_markdown(line))
    return paragraphs, italic_segments


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.iter(f"{W}t"))


def validate(path: Path) -> list[str]:
    messages: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise AssertionError(f"Повреждённый ZIP entry: {bad}")
        names = set(archive.namelist())
        missing = REQUIRED - names
        if missing:
            raise AssertionError(f"Нет обязательных частей DOCX: {sorted(missing)}")
        if not any(name.startswith("word/header") for name in names):
            raise AssertionError("Нет колонтитула")
        if not any(name.startswith("word/footer") for name in names):
            raise AssertionError("Нет нижнего колонтитула")

        parsed: dict[str, ET.Element] = {}
        for name in names:
            if name.endswith((".xml", ".rels")):
                try:
                    parsed[name] = ET.fromstring(archive.read(name))
                except ET.ParseError as exc:
                    raise AssertionError(f"Невалидный XML {name}: {exc}") from exc

        document = parsed["word/document.xml"]
        paragraphs = [paragraph_text(p) for p in document.iter(f"{W}p")]
        if any("\ufffd" in text for text in paragraphs):
            raise AssertionError("В DOCX остался U+FFFD")
        if any("TODO" in text or "[Company Name]" in text for text in paragraphs):
            raise AssertionError("В DOCX остался placeholder")

        expected, italic_expected = expected_body()
        starts = [i for i, text in enumerate(paragraphs) if text == "Глава 1"]
        if len(starts) < 2:
            raise AssertionError("Не найдены отдельные записи главы 1 в содержании и тексте")
        start = starts[-1]
        actual = [text for text in paragraphs[start:] if text]
        if actual != expected:
            limit = min(len(actual), len(expected))
            mismatch = next((i for i in range(limit) if actual[i] != expected[i]), limit)
            raise AssertionError(
                "Текст DOCX расходится с Markdown на блоке "
                f"{mismatch}: actual={actual[mismatch:mismatch+1]!r}, expected={expected[mismatch:mismatch+1]!r}; "
                f"blocks {len(actual)} != {len(expected)}"
            )

        chapter_headings = [text for text in actual if re.fullmatch(r"Глава \d+", text)]
        if chapter_headings != [f"Глава {i}" for i in range(1, 37)]:
            raise AssertionError("Заголовки глав отсутствуют или стоят не по порядку")
        links = [node.get(f"{W}anchor") for node in document.iter(f"{W}hyperlink") if node.get(f"{W}anchor")]
        if links != [f"chapter_{i}" for i in range(1, 37)]:
            raise AssertionError("Кликабельное содержание отсутствует или нарушено")

        raw_document = archive.read("word/document.xml").decode("utf-8")
        italic_actual = len(re.findall(r"<w:i(?:\s|/|>)", raw_document))
        if italic_actual < italic_expected:
            raise AssertionError(f"Потерян курсив: {italic_actual} < {italic_expected}")
        if "**" in "".join(actual):
            raise AssertionError("В тексте остались маркеры **")

        settings = archive.read("word/settings.xml").decode("utf-8")
        if "updateFields" not in settings:
            messages.append("WARN: updateFields не найден")

        messages.extend(
            [
                f"OK: ZIP/XML ({len(names)} частей)",
                f"OK: {len(actual)} блоков прозы совпадают с Markdown",
                f"OK: 36 глав по порядку",
                f"OK: кликабельное содержание (36 ссылок)",
                f"OK: курсивных сегментов не меньше исходника ({italic_actual}/{italic_expected})",
                f"OK: размер {path.stat().st_size / 1024 / 1024:.2f} MiB",
            ]
        )
    return messages


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv[1:]]
    if not paths:
        paths = sorted((ROOT / "exports").glob("*.docx"))
    if not paths:
        print("Нет DOCX для проверки", file=sys.stderr)
        return 2
    failed = False
    for path in paths:
        print(f"\n=== {path} ===")
        try:
            for message in validate(path):
                print(message)
        except Exception as exc:  # validation CLI should report all files
            failed = True
            print(f"FAIL: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
