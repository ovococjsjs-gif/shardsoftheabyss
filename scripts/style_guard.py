#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class Finding:
    severity: str
    code: str
    line: int
    excerpt: str
    message: str


BLOCKER_PATTERNS = [
    ("NEGATION_CONTRAST_A", re.compile(r"\bне\b[^\n.!?]{0,100}\bа\b", re.IGNORECASE), "запрещённая отрицательная контрастная конструкция `не ..., а ...`"),
    ("NEGATION_CONTRAST_PROSTO", re.compile(r"\bне\b[^\n.!?]{0,100}\bпросто\b", re.IGNORECASE), "запрещённая отрицательная конструкция `не ..., просто ...`"),
    ("NEGATION_CONTRAST_TOLKO", re.compile(r"\bне\b[^\n.!?]{0,100}\bтолько\b", re.IGNORECASE), "запрещённая отрицательная конструкция `не ..., только ...`"),
    ("NEGATION_CONTRAST_ZATO", re.compile(r"\bне\b[^\n.!?]{0,100}\bзато\b", re.IGNORECASE), "запрещённая отрицательная конструкция `не ..., зато ...`"),
    ("NEGATION_CONTRAST_SKOREE", re.compile(r"\bне\b[^\n.!?]{0,100}\bскорее\b", re.IGNORECASE), "запрещённая отрицательная конструкция `не ..., скорее ...`"),
    ("NEGATION_SPLIT_ETO", re.compile(r"Это\s+не\b[^\n.!?]{0,60}[.!?]\s+Это\s+", re.IGNORECASE), "запрещённая дробная отрицательная конструкция `Это не X. Это Y.`"),
    ("NEGATION_SPLIT_DOUBLE", re.compile(r"\bНе\b[^\n.!?]{0,35}[.!?]\s+\bНе\b[^\n.!?]{0,35}[.!?]", re.IGNORECASE), "запрещённый дробный отрицательный кластер `Не X. Не Y.`"),
    ("BANNED_WORD_KOSTYASHKI", re.compile(r"костяш", re.IGNORECASE), "запрещённый маркер `костяшки`"),
    ("BANNED_PHRASE_UGOLKI_GUB", re.compile(r"уголк(?:и)? губ", re.IGNORECASE), "запрещённый маркер `уголки губ`"),
    ("BANNED_PHRASE_KRAESHKI_GUB", re.compile(r"краешк(?:и|а)? губ", re.IGNORECASE), "запрещённый маркер `краешки губ`"),
    ("BANNED_PHRASE_Gлубокий_VZDOH", re.compile(r"глубок(?:о|ий|ая|ое) вздох", re.IGNORECASE), "запрещённый маркер `глубокий вздох`"),
    ("BANNED_PHRASE_POVISLA_TISHINA", re.compile(r"повисл[ао]? тишин", re.IGNORECASE), "запрещённый маркер `повисла тишина`"),
    ("BANNED_WORD_NECHTO", re.compile(r"\bнечто\b", re.IGNORECASE), "запрещённый маркер `нечто`"),
    ("BANNED_PHRASE_CHTO_TO_VNUTRI", re.compile(r"что-то внутри", re.IGNORECASE), "запрещённый маркер `что-то внутри`"),
    ("BANNED_PHRASE_V_ETOT_MOMENT", re.compile(r"в этот момент", re.IGNORECASE), "запрещённый маркер `в этот момент`"),
    ("BANNED_PHRASE_KAKIM_TO_OBRAZOM", re.compile(r"каким-то образом", re.IGNORECASE), "запрещённый маркер `каким-то образом`"),
    ("BANNED_WORD_PO_NASTOYASHCHEMU", re.compile(r"по-настоящему", re.IGNORECASE), "запрещённый маркер `по-настоящему`"),
    ("BANNED_PHRASE_OSOZNAL_CHTO", re.compile(r"осознал[аио]?[,]? что", re.IGNORECASE), "запрещённый маркер `осознал, что`"),
    ("BANNED_PHRASE_POCHEMSTVOVAL_CHTO", re.compile(r"почувствовал[аио]?[,]? что", re.IGNORECASE), "запрещённый маркер `почувствовал, что`"),
    ("BANNED_PHRASE_SERDTSE_SJALOS", re.compile(r"сердце сжал[ао]сь", re.IGNORECASE), "запрещённый маркер `сердце сжалось`"),
    ("BANNED_PHRASE_SERDTSE_YOK", re.compile(r"сердце ёкнуло|сердце екнуло", re.IGNORECASE), "запрещённый маркер `сердце ёкнуло`"),
    ("BANNED_PHRASE_SLOVNO_BY", re.compile(r"словно бы", re.IGNORECASE), "подозрительный маркер `словно бы`"),
]

# Эвристика для ритмических троек. Здесь лучше пропустить часть случаев,
# чем заспамить весь текст ложными срабатываниями.
TRIAD_PATTERNS = [
    re.compile(r"\b[А-Яа-яA-Za-zЁё0-9-]{2,}(?:\s+[А-Яа-яA-Za-zЁё0-9-]{2,}){0,2},\s+[А-Яа-яA-Za-zЁё0-9-]{2,}(?:\s+[А-Яа-яA-Za-zЁё0-9-]{2,}){0,2},\s+[А-Яа-яA-Za-zЁё0-9-]{2,}(?:\s+[А-Яа-яA-Za-zЁё0-9-]{2,}){0,2}\b"),
    re.compile(r"\b[А-Яа-яA-Za-zЁё0-9-]{2,}(?:\s+[А-Яа-яA-Za-zЁё0-9-]{2,}){0,2},\s+[А-Яа-яA-Za-zЁё0-9-]{2,}(?:\s+[А-Яа-яA-Za-zЁё0-9-]{2,}){0,2}\s+и\s+[А-Яа-яA-Za-zЁё0-9-]{2,}(?:\s+[А-Яа-яA-Za-zЁё0-9-]{2,}){0,2}\b"),
]

VERBISH = re.compile(r"(?:ясь|вшись|лся|лась|лись|лось|ет|ют|ут|ит|ат|ят|ешь|ете|ем|им|ил|ила|или|ить|ать|ять|нуть|ется|ются)\b", re.IGNORECASE)
BAD_PART_STARTS = {"как", "будто", "словно", "если", "когда", "что", "чтобы", "где", "куда", "пока", "потом", "сверху", "только", "на", "в", "под", "по", "от", "до", "и", "или"}

WARN_WORDS = [
    "словно",
    "будто",
]


def build_line_index(text: str) -> List[int]:
    starts = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            starts.append(idx + 1)
    return starts


def offset_to_line(offset: int, starts: List[int]) -> int:
    return bisect.bisect_right(starts, offset)


def excerpt_at(text: str, start: int, end: int) -> str:
    s = max(0, start - 45)
    e = min(len(text), end + 55)
    return text[s:e].replace("\n", " ").strip()


def looks_like_prose_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return False
    if stripped.startswith("-"):
        return False
    if stripped.startswith("*"):
        return False
    if stripped.startswith(">"):
        return False
    if stripped.startswith("```"):
        return False
    return True


def scan_blockers(text: str, starts: List[int]) -> Iterable[Finding]:
    for code, pattern, message in BLOCKER_PATTERNS:
        for match in pattern.finditer(text):
            yield Finding(
                severity="BLOCKER",
                code=code,
                line=offset_to_line(match.start(), starts),
                excerpt=excerpt_at(text, match.start(), match.end()),
                message=message,
            )


def scan_triads(text: str, starts: List[int]) -> Iterable[Finding]:
    # Смотрим только короткие однотипные цепочки без явных глаголов.
    offset = 0
    for line in text.splitlines(keepends=True):
        if looks_like_prose_line(line):
            for pat in TRIAD_PATTERNS:
                for match in pat.finditer(line):
                    chunk = match.group(0).strip()
                    parts = [p.strip() for p in re.split(r",|\s+и\s+", chunk) if p.strip()]
                    if len(parts) != 3:
                        continue
                    if len(chunk) > 45:
                        continue
                    if any(len(p.split()) > 3 for p in parts):
                        continue
                    if any(len(p) > 18 for p in parts):
                        continue
                    if any(VERBISH.search(p) for p in parts):
                        continue
                    if any(p.split()[0].lower() in BAD_PART_STARTS for p in parts if p.split()):
                        continue
                    yield Finding(
                        severity="BLOCKER",
                        code="TRIAD_CANDIDATE",
                        line=offset_to_line(offset + match.start(), starts),
                        excerpt=chunk,
                        message="подозрение на тройной кластер; переписать или вручную подтвердить, что это не ритмическая тройка",
                    )
        offset += len(line)


def scan_word_density(text: str, starts: List[int]) -> Iterable[Finding]:
    # Для `будто` / `словно` даём предупреждение, если в абзаце больше одного вхождения.
    paragraphs = re.split(r"\n\s*\n", text)
    offset = 0
    for para in paragraphs:
        lowered = para.lower()
        for word in WARN_WORDS:
            count = lowered.count(word)
            if count > 1:
                pos = text.find(para, offset)
                if pos == -1:
                    pos = offset
                yield Finding(
                    severity="WARN",
                    code=f"DENSITY_{word.upper()}",
                    line=offset_to_line(pos, starts),
                    excerpt=para[:140].replace("\n", " ").strip(),
                    message=f"в одном абзаце слово `{word}` встречается {count} раз(а); проверить плотность образности",
                )
        offset += len(para) + 2


def scan_single_word_paragraphs(text: str, starts: List[int]) -> Iterable[Finding]:
    paragraphs = re.split(r"\n\s*\n", text)
    offset = 0
    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            offset += len(para) + 2
            continue
        if len(stripped.split()) == 1 and looks_like_prose_line(stripped):
            pos = text.find(para, offset)
            if pos == -1:
                pos = offset
            yield Finding(
                severity="WARN",
                code="SINGLE_WORD_PARAGRAPH",
                line=offset_to_line(pos, starts),
                excerpt=stripped,
                message="одиночное слово-абзац; для проекта это почти всегда подозрительная драматизация",
            )
        offset += len(para) + 2


def run_guard(path: Path) -> List[Finding]:
    text = path.read_text(encoding="utf-8")
    starts = build_line_index(text)
    findings: List[Finding] = []
    findings.extend(scan_blockers(text, starts))
    findings.extend(scan_triads(text, starts))
    findings.extend(scan_word_density(text, starts))
    findings.extend(scan_single_word_paragraphs(text, starts))
    findings.sort(key=lambda f: (f.severity != "BLOCKER", f.line, f.code))
    return findings


def print_findings(path: Path, findings: List[Finding]) -> None:
    print(f"\n=== {path} ===")
    if not findings:
        print("OK: блокеров и предупреждений не найдено")
        return
    for f in findings:
        print(f"[{f.severity}] {f.code} @ line {f.line}: {f.message}")
        print(f"    {f.excerpt}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Жёсткий guard художественной прозы проекта shardsoftheabyss")
    parser.add_argument("paths", nargs="+", help="файлы markdown или текстовые файлы для проверки")
    args = parser.parse_args(argv)

    all_findings: List[Finding] = []
    for raw in args.paths:
        path = Path(raw)
        if not path.exists():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            return 2
        findings = run_guard(path)
        print_findings(path, findings)
        all_findings.extend(findings)

    blockers = [f for f in all_findings if f.severity == "BLOCKER"]
    warns = [f for f in all_findings if f.severity == "WARN"]

    print("\n--- summary ---")
    print(f"blockers: {len(blockers)}")
    print(f"warnings: {len(warns)}")

    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
