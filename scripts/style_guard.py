#!/usr/bin/env python3
"""Жёсткий guard художественной прозы проекта shardsoftheabyss.

Версия 2.

Главное отличие от версии 1: guard проверяет не только словарь, но и **ритм**.
Практика показала, что лексические баны текст проходит легко, а разваливается
он на другом — на рубленом синтаксисе, анафорах и самоповторе. Именно эти
дефекты автор ловит глазами, а guard v1 их не видел вообще.

Категории проверок:
  1. LEX     — запрещённая лексика и конструкции (было в v1)
  2. RHYTHM  — рубленый синтаксис, анафоры, назывные цепочки (новое)
  3. REPEAT  — самоповтор внутри файла и между файлами (новое)
  4. FORM    — одиночные слова-абзацы, плотность образности

Опорная норма ритма взята из `03-manuscript/arc-01-v4-combined.md` —
текста, который автор признал живым.
"""

from __future__ import annotations

import argparse
import bisect
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


# ---------------------------------------------------------------------------
# Модель находки
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    severity: str  # BLOCKER | WARN
    code: str
    line: int
    excerpt: str
    message: str


SEVERITY_ORDER = {"BLOCKER": 0, "WARN": 1}


# ---------------------------------------------------------------------------
# 1. LEX — лексические блокеры
# ---------------------------------------------------------------------------

BLOCKER_PATTERNS = [
    ("NEG_CONTRAST_A", re.compile(r"\bне\b[^\n.!?;]{0,80},\s*а\b", re.IGNORECASE),
     "отрицательная контрастная конструкция `не ..., а ...`"),
    ("NEG_CONTRAST_PROSTO", re.compile(r"\bне\b[^\n.!?;]{0,80},\s*просто\b", re.IGNORECASE),
     "отрицательная конструкция `не ..., просто ...`"),
    ("NEG_CONTRAST_TOLKO", re.compile(r"\bне\b[^\n.!?;]{0,80},\s*только\b", re.IGNORECASE),
     "отрицательная конструкция `не ..., только ...`"),
    ("NEG_CONTRAST_ZATO", re.compile(r"\bне\b[^\n.!?;]{0,80},\s*зато\b", re.IGNORECASE),
     "отрицательная конструкция `не ..., зато ...`"),
    ("NEG_CONTRAST_SKOREE", re.compile(r"\bне\b[^\n.!?;]{0,80},?\s*скорее\b", re.IGNORECASE),
     "отрицательная конструкция `не ..., скорее ...`"),
    # Тире-контраст `Не резало — тянуло`. Запятая перед тире означает слова автора
    # в диалоге («— Ты не ела, — сказала она»), поэтому такие случаи исключены.
    ("NEG_CONTRAST_DASH", re.compile(
        r"\bне\b[^\n.!?;,—]{0,50}\s+—\s+(?!сказал|спросил|ответил|проговорил|бросил|отозвал|"
        r"добавил|повторил|начал|продолжил|перебил|заметил|уточнил|позвал|крикнул|пробормотал)[а-яё]",
        re.IGNORECASE),
     "отрицательная контрастная конструкция через тире `не X — Y`"),
    ("NEG_SPLIT_ETO", re.compile(r"Это\s+(?:была\s+|был\s+|было\s+)?не\b[^\n.!?]{0,70}[.!?]\s+Это\s", re.IGNORECASE),
     "дробная отрицательная конструкция `Это не X. Это Y.`"),
    ("NEG_SPLIT_DOUBLE", re.compile(r"(?:^|[.!?»]\s)\s*Не\b[^\n.!?]{0,40}[.!?]\s+Не\b[^\n.!?]{0,40}[.!?]"),
     "дробный отрицательный кластер `Не X. Не Y.`"),
    ("BANNED_KOSTYASHKI", re.compile(r"костяш", re.IGNORECASE), "запрещённый маркер `костяшки`"),
    ("BANNED_UGOLKI_GUB", re.compile(r"уголк\w* губ", re.IGNORECASE), "запрещённый маркер `уголки губ`"),
    ("BANNED_KRAESHKI_GUB", re.compile(r"краешк\w* губ", re.IGNORECASE), "запрещённый маркер `краешки губ`"),
    ("BANNED_GLUBOKIY_VZDOH", re.compile(r"глубок\w* вздох", re.IGNORECASE), "запрещённый маркер `глубокий вздох`"),
    ("BANNED_POVISLA_TISHINA", re.compile(r"повисл\w* тишин", re.IGNORECASE), "запрещённый маркер `повисла тишина`"),
    ("BANNED_NECHTO", re.compile(r"\bнечто\b", re.IGNORECASE), "запрещённый маркер `нечто`"),
    ("BANNED_CHTO_TO_VNUTRI", re.compile(r"что-то внутри", re.IGNORECASE), "запрещённый маркер `что-то внутри`"),
    ("BANNED_V_ETOT_MOMENT", re.compile(r"в этот момент", re.IGNORECASE), "запрещённый маркер `в этот момент`"),
    ("BANNED_KAKIM_TO_OBRAZOM", re.compile(r"каким-то образом", re.IGNORECASE), "запрещённый маркер `каким-то образом`"),
    ("BANNED_PO_NASTOYASHCHEMU", re.compile(r"по-настоящему", re.IGNORECASE), "запрещённый маркер `по-настоящему`"),
    ("BANNED_OSOZNAL_CHTO", re.compile(r"осознал\w*,? что", re.IGNORECASE), "запрещённый маркер `осознал, что`"),
    ("BANNED_POCHUVSTVOVAL_CHTO", re.compile(r"почувствовал\w*,? что", re.IGNORECASE), "запрещённый маркер `почувствовал, что`"),
    ("BANNED_SERDTSE_SJALOS", re.compile(r"сердце сжал\w*", re.IGNORECASE), "запрещённый маркер `сердце сжалось`"),
    ("BANNED_SERDTSE_YOK", re.compile(r"сердце [её]кнул\w*", re.IGNORECASE), "запрещённый маркер `сердце ёкнуло`"),
    ("BANNED_SLOVNO_BY", re.compile(r"словно бы", re.IGNORECASE), "подозрительный маркер `словно бы`"),
]

# Псевдотелесная абстракция: состояние подаётся как самостоятельный субъект.
PSEUDO_BODY = re.compile(
    r"\b(?:пришл[аио]|вернул(?:ся|ась|ось)|вошл[аио]|ушл[аио]|поднял(?:ся|ась)|"
    r"накрыл[аио]?|отпустил[аио]?)\s+(?:голова|боль|воздух|тело|темнота|страх|тошнота|слабость)\b",
    re.IGNORECASE,
)

# Метатекстовые метафоры — герой не знает, что он в книге.
METATEXT = re.compile(r"\b(?:черновик\w*|сюжет\w*|эт[ао]й? истори[ие]|глав[аеы] жизни|сценари\w+)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 2. RHYTHM — ритмические блокеры
# ---------------------------------------------------------------------------

# Норма, снятая с арки 1 (текст, признанный живым):
#   средняя длина предложения наррации ~7.6 слова
#   доля предложений <= 4 слов ~20%
STACCATO_WINDOW = 40          # предложений в скользящем окне
STACCATO_WARN_RATIO = 0.34    # выше — предупреждение
STACCATO_BLOCK_RATIO = 0.42   # выше — блокер

# Глаголы: для поиска назывных (безглагольных) цепочек.
VERB_ENDINGS = re.compile(
    r"\w+(?:ал|ала|али|ало|ил|ила|или|ило|ел|ела|ели|ело|ул|ула|ули|уло|"
    r"ыл|ыла|ыли|ыло|ёл|шла|шли|шло|ет|ёт|ут|ют|ит|ат|ят|ешь|ишь|ем|им|ете|ите|"
    r"ть|ться|тся|л[ao]сь|лись|ло|ла)\b",
    re.IGNORECASE,
)

# Вводные слова — их нельзя считать элементом ритмической тройки.
PARENTHETICALS = {
    "скорее", "всего", "судя", "похоже", "надеюсь", "кажется", "конечно", "например",
    "возможно", "наверное", "видимо", "правда", "впрочем", "значит", "пожалуй",
    "разумеется", "по-моему", "к счастью", "к сожалению", "может",
}

ANAPHORA_MIN_RUN = 3          # сколько одинаковых зачинов подряд считать нарушением
ANAPHORA_MAX_WORDS = 7        # только для коротких фраз

NOMINATIVE_MIN_RUN = 3        # сколько безглагольных предложений подряд
NOMINATIVE_MAX_WORDS = 5


# ---------------------------------------------------------------------------
# 3. REPEAT — самоповтор
# ---------------------------------------------------------------------------

DIALOGUE_TAG = re.compile(r"^—\s*(?:спросил|сказал|ответил|проговорил|бросил|отозвал)\w*\s+\w+\.?$", re.IGNORECASE)
TAG_LIMIT_PER_10K = 8         # сколько раз один и тот же тег допустим на 10k слов
SENTENCE_MIN_WORDS_FOR_DUPE = 4


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------


def build_line_index(text: str) -> List[int]:
    starts = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            starts.append(idx + 1)
    return starts


def offset_to_line(offset: int, starts: List[int]) -> int:
    return bisect.bisect_right(starts, offset)


def excerpt_at(text: str, start: int, end: int) -> str:
    s = max(0, start - 40)
    e = min(len(text), end + 50)
    return text[s:e].replace("\n", " ").strip()


def is_prose_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return not s.startswith(("#", ">", "```", "|", "- ", "* ", "1.", "2."))


def is_dialogue_line(line: str) -> bool:
    return line.strip().startswith("—")


def split_sentences(block: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", block) if s.strip()]


def word_count(s: str) -> int:
    return len(re.findall(r"[А-Яа-яЁёA-Za-z0-9-]+", s))


def first_word(s: str) -> str:
    m = re.search(r"[А-Яа-яЁёA-Za-z]+", s)
    return m.group(0).lower() if m else ""


def has_verb(s: str) -> bool:
    return bool(VERB_ENDINGS.search(s))


# ---------------------------------------------------------------------------
# Сканеры
# ---------------------------------------------------------------------------


def scan_lexical(text: str, starts: List[int]) -> Iterable[Finding]:
    for code, pattern, message in BLOCKER_PATTERNS:
        for m in pattern.finditer(text):
            yield Finding("BLOCKER", code, offset_to_line(m.start(), starts),
                          excerpt_at(text, m.start(), m.end()), message)
    for m in PSEUDO_BODY.finditer(text):
        yield Finding("BLOCKER", "PSEUDO_BODY", offset_to_line(m.start(), starts),
                      excerpt_at(text, m.start(), m.end()),
                      "псевдотелесная абстракция: состояние подано как самостоятельный субъект")
    for m in METATEXT.finditer(text):
        yield Finding("WARN", "METATEXT_METAPHOR", offset_to_line(m.start(), starts),
                      excerpt_at(text, m.start(), m.end()),
                      "возможная метатекстовая метафора; герой не знает, что он в книге")


def iter_narration_sentences(text: str):
    """Возвращает (offset, sentence) только для наррации, без реплик и заголовков."""
    offset = 0
    for line in text.splitlines(keepends=True):
        if is_prose_line(line) and not is_dialogue_line(line):
            base = offset
            for s in split_sentences(line):
                pos = line.find(s, base - offset)
                yield offset + (pos if pos >= 0 else 0), s
                base = offset + (pos if pos >= 0 else 0) + len(s)
        offset += len(line)


def scan_staccato(text: str, starts: List[int]) -> Iterable[Finding]:
    items = [(o, s) for o, s in iter_narration_sentences(text) if word_count(s) > 0]
    if len(items) < STACCATO_WINDOW:
        return
    flags = [1 if word_count(s) <= 4 else 0 for _, s in items]
    worst = None
    for i in range(0, len(items) - STACCATO_WINDOW + 1):
        ratio = sum(flags[i:i + STACCATO_WINDOW]) / STACCATO_WINDOW
        if worst is None or ratio > worst[0]:
            worst = (ratio, i)
    total_ratio = sum(flags) / len(flags)
    avg = sum(word_count(s) for _, s in items) / len(items)

    if total_ratio >= STACCATO_BLOCK_RATIO:
        sev, msg = "BLOCKER", "рубленый синтаксис по всему файлу"
    elif total_ratio >= STACCATO_WARN_RATIO:
        sev, msg = "WARN", "синтаксис заметно рубленее нормы проекта"
    else:
        sev = None
        msg = ""
    if sev:
        yield Finding(sev, "STACCATO_GLOBAL", 1,
                      f"средняя длина предложения наррации {avg:.1f} сл., коротких (<=4 сл.) {total_ratio:.0%}",
                      f"{msg}; ориентир арки 1 — ~7.6 сл. и ~20% коротких")

    if worst and worst[0] >= STACCATO_BLOCK_RATIO:
        o = items[worst[1]][0]
        yield Finding("BLOCKER", "STACCATO_WINDOW", offset_to_line(o, starts),
                      items[worst[1]][1][:110],
                      f"локальный участок с долей коротких предложений {worst[0]:.0%} на {STACCATO_WINDOW} подряд")


def scan_anaphora(text: str, starts: List[int]) -> Iterable[Finding]:
    offset = 0
    for line in text.splitlines(keepends=True):
        if is_prose_line(line):
            sents = split_sentences(line)
            run: List[str] = []
            run_word = ""
            for s in sents:
                fw = first_word(s)
                short = word_count(s) <= ANAPHORA_MAX_WORDS
                if short and fw and fw == run_word:
                    run.append(s)
                else:
                    if len(run) >= ANAPHORA_MIN_RUN:
                        yield Finding("BLOCKER", "ANAPHORA_RUN", offset_to_line(offset, starts),
                                      " ".join(run)[:140],
                                      f"анафорическая цепочка из {len(run)} коротких фраз с одним зачином — ритмическая тройка")
                    run = [s] if short and fw else []
                    run_word = fw if short else ""
            if len(run) >= ANAPHORA_MIN_RUN:
                yield Finding("BLOCKER", "ANAPHORA_RUN", offset_to_line(offset, starts),
                              " ".join(run)[:140],
                              f"анафорическая цепочка из {len(run)} коротких фраз с одним зачином — ритмическая тройка")
        offset += len(line)


def scan_nominative_chain(text: str, starts: List[int]) -> Iterable[Finding]:
    offset = 0
    for line in text.splitlines(keepends=True):
        if is_prose_line(line) and not is_dialogue_line(line):
            sents = split_sentences(line)
            run: List[str] = []
            for s in sents:
                short = word_count(s) <= NOMINATIVE_MAX_WORDS
                if short and not has_verb(s):
                    tokens = {w.lower() for w in re.findall(r"[А-Яа-яЁё]+", s)}
                    if tokens & PARENTHETICALS:
                        run = []
                        continue
                    run.append(s)
                else:
                    if len(run) >= NOMINATIVE_MIN_RUN:
                        yield Finding("BLOCKER", "NOMINATIVE_CHAIN", offset_to_line(offset, starts),
                                      " ".join(run)[:140],
                                      f"цепочка из {len(run)} безглагольных назывных предложений подряд")
                    run = []
            if len(run) >= NOMINATIVE_MIN_RUN:
                yield Finding("BLOCKER", "NOMINATIVE_CHAIN", offset_to_line(offset, starts),
                              " ".join(run)[:140],
                              f"цепочка из {len(run)} безглагольных назывных предложений подряд")
        offset += len(line)


def scan_repeats(text: str, starts: List[int]) -> Iterable[Finding]:
    total_words = len(re.findall(r"[А-Яа-яЁёA-Za-z]+", text))
    scale = max(1.0, total_words / 10000)

    # 3.1 однообразные атрибуции диалога
    tags = Counter()
    for line in text.splitlines():
        s = line.strip()
        if DIALOGUE_TAG.match(s):
            tags[s.lower()] += 1
    for tag, count in tags.items():
        if count > TAG_LIMIT_PER_10K * scale:
            yield Finding("BLOCKER", "MONOTONE_DIALOGUE_TAG", 1, tag,
                          f"атрибуция повторяется {count} раз на {total_words} слов — диалог ведётся на автопилоте")

    # 3.2 дословные повторы предложений внутри файла
    seen: dict[str, int] = {}
    dupes: dict[str, list[int]] = {}
    offset = 0
    for line in text.splitlines(keepends=True):
        if is_prose_line(line):
            for s in split_sentences(line):
                if word_count(s) < SENTENCE_MIN_WORDS_FOR_DUPE:
                    continue
                key = re.sub(r"\s+", " ", s.lower()).strip()
                if key in seen:
                    dupes.setdefault(key, [seen[key]]).append(offset)
                else:
                    seen[key] = offset
        offset += len(line)
    for key, positions in dupes.items():
        if len(positions) >= 2:
            yield Finding("WARN", "SELF_DUPLICATE", offset_to_line(positions[-1], starts),
                          key[:130],
                          f"предложение повторяется {len(positions)} раз(а) — вероятный след послойной редактуры")


def scan_form(text: str, starts: List[int]) -> Iterable[Finding]:
    paragraphs = re.split(r"\n\s*\n", text)
    offset = 0
    for para in paragraphs:
        stripped = para.strip()
        if stripped and is_prose_line(stripped):
            if len(stripped.split()) == 1 and not stripped.startswith("—"):
                pos = text.find(para, offset)
                yield Finding("WARN", "SINGLE_WORD_PARAGRAPH", offset_to_line(max(pos, 0), starts),
                              stripped, "одиночное слово-абзац; почти всегда подозрительная драматизация")
            lowered = stripped.lower()
            for word in ("словно", "будто"):
                if lowered.count(word) > 1:
                    pos = text.find(para, offset)
                    yield Finding("WARN", f"DENSITY_{word.upper()}", offset_to_line(max(pos, 0), starts),
                                  stripped[:130],
                                  f"`{word}` встречается {lowered.count(word)} раз(а) в одном абзаце")
        offset += len(para) + 2


# ---------------------------------------------------------------------------
# Кросс-файловая проверка
# ---------------------------------------------------------------------------


def cross_file_duplicates(paths: List[Path]) -> List[str]:
    """Ищет дословные предложения, общие для разных глав."""
    per_file = {}
    for p in paths:
        text = p.read_text(encoding="utf-8")
        acc = set()
        for line in text.splitlines():
            if is_prose_line(line):
                for s in split_sentences(line):
                    if word_count(s) >= 5:
                        acc.add(re.sub(r"\s+", " ", s.lower()).strip())
        per_file[p] = acc
    report: List[str] = []
    names = list(per_file)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            common = per_file[names[i]] & per_file[names[j]]
            for s in sorted(common, key=len, reverse=True)[:12]:
                report.append(f"{names[i].name} <-> {names[j].name}: {s[:110]}")
    return report


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------


def run_guard(path: Path) -> List[Finding]:
    text = path.read_text(encoding="utf-8")
    starts = build_line_index(text)
    findings: List[Finding] = []
    findings.extend(scan_lexical(text, starts))
    findings.extend(scan_staccato(text, starts))
    findings.extend(scan_anaphora(text, starts))
    findings.extend(scan_nominative_chain(text, starts))
    findings.extend(scan_repeats(text, starts))
    findings.extend(scan_form(text, starts))
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.line, f.code))
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
    parser = argparse.ArgumentParser(
        description="Guard художественной прозы проекта shardsoftheabyss (v2: лексика + ритм + самоповтор)")
    parser.add_argument("paths", nargs="+", help="файлы для проверки")
    parser.add_argument("--cross", action="store_true",
                        help="дополнительно искать дословные совпадения между указанными файлами")
    parser.add_argument("--quiet", action="store_true", help="печатать только сводку")
    args = parser.parse_args(argv)

    all_findings: List[Finding] = []
    paths: List[Path] = []
    for raw in args.paths:
        path = Path(raw)
        if not path.exists():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            return 2
        paths.append(path)
        findings = run_guard(path)
        if not args.quiet:
            print_findings(path, findings)
        all_findings.extend(findings)

    if args.cross and len(paths) > 1:
        print("\n=== кросс-файловые дословные повторы ===")
        rep = cross_file_duplicates(paths)
        if not rep:
            print("OK: пересечений не найдено")
        for line in rep:
            print("  " + line)

    blockers = [f for f in all_findings if f.severity == "BLOCKER"]
    warns = [f for f in all_findings if f.severity == "WARN"]

    print("\n--- summary ---")
    print(f"blockers: {len(blockers)}")
    print(f"warnings: {len(warns)}")
    if blockers:
        by_code = Counter(f.code for f in blockers)
        print("по кодам: " + ", ".join(f"{c}={n}" for c, n in by_code.most_common()))

    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
