#!/usr/bin/env python3
"""Проверка канона и хронологии по реестру фактов.

Ловит класс дефектов, невидимый для style_guard: текст написан правильно,
но противоречит установленному факту или собственному календарю.

Основано на разборе книги (AUDIT-book-triple-review.md), где найдено:
  DEF-01  улица «Серебряной ложки» меняется между главами;
  DEF-04  «пять недель» и «пятнадцать дней» об одном сроке в одной главе;
  DEF-05  дата «13 червня» против «трёх месяцев» внутри главы;
  DEF-12  «двадцать лет назад» о восемнадцатилетней Агнис.

Все четыре находятся автоматически. Раньше не находились, потому что
такой проверки не существовало.

Использование:
    python3 scripts/canon_check.py 03-manuscript/arc-*/ch-*.md
    python3 scripts/canon_check.py --timeline 03-manuscript/arc-*/ch-*.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FACTS_PATH = Path("01-canon/FACTS.tsv")

MONTHS = ["цветень", "травень", "червень", "липень"]
MONTH_STEMS = {"цветн": 1, "травн": 2, "червн": 3, "липн": 4}
DAYS_IN_MONTH = 30
ATTACK_ABS = 14  # 14 цветня

NUMERALS = {
    "один": 1, "одна": 1, "одну": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
    "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
    "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18,
    "девятнадцать": 19, "двадцать": 20, "тридцать": 30, "сорок": 40,
    "полтора": 1.5, "полторы": 1.5, "полутора": 1.5,
}


def load_facts(path: Path):
    facts = []
    if not path.exists():
        print(f"ERROR: нет реестра {path}", file=sys.stderr)
        return facts
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = raw.split("\t")
        key = parts[0].strip()
        good = parts[1].strip() if len(parts) > 1 else ""
        bad = parts[2].strip() if len(parts) > 2 else ""
        note = parts[3].strip() if len(parts) > 3 else ""
        if not key:
            continue
        bad_list = [b.strip() for b in bad.split("|") if b.strip()]
        facts.append((key, good, bad_list, note))
    return facts


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def excerpt(text: str, pos: int, width: int = 95) -> str:
    s = max(0, pos - 35)
    e = min(len(text), pos + width)
    return " ".join(text[s:e].split())


def check_forbidden(text: str, path: Path, facts) -> list[str]:
    """Запрещённые варианты факта: прямое противоречие канону.

    Возрастные ключи проверяются отдельно (см. check_ages): голое числительное
    без контекста даёт мусор — «девятнадцать минут» не возраст, а «семнадцать»
    встречается внутри «восемнадцать».
    """
    out = []
    for key, good, bad_list, note in facts:
        if key.startswith("возраст"):
            continue
        for bad in bad_list:
            pat = r"(?<![А-Яа-яЁё])" + re.escape(bad) + r"(?![А-Яа-яЁё])"
            for m in re.finditer(pat, text, re.IGNORECASE):
                out.append(
                    f"[CANON] {path.name}:{line_of(text, m.start())} "
                    f"«{bad}» противоречит канону «{good}» ({key})\n"
                    f"         {excerpt(text, m.start())}"
                )
    return out


AGE_CTX = re.compile(
    r"(?:(?<![А-Яа-яЁё])(?P<num>[а-яё]+)(?![А-Яа-яЁё])\s+(?:лет|года|год)\b"
    r"|\b(?:лет|года|год)\s+(?P<num2>[а-яё]+)(?![А-Яа-яЁё]))",
    re.IGNORECASE)


def check_ages(text: str, path: Path, facts) -> list[str]:
    """Возраст: числительное рядом со словом «лет/года» и именем в окне."""
    ages = {}
    for key, good, bad_list, _n in facts:
        if key.startswith("возраст"):
            who = key.split("_", 1)[1]
            val = parse_number(good)
            if val:
                ages[who] = (val, bad_list)
    who_names = {"сильвии": ("Сильви", "Дюваль", "я "), "агнис": ("Агнис",),
                 "кайра": ("Кайр", "Кёниг")}
    out = []
    for m in AGE_CTX.finditer(text):
        word = m.group("num") or m.group("num2")
        n = parse_number(word)
        if n is None or n > 60:
            continue
        window = text[max(0, m.start() - 200):m.start() + 120]
        for who, (val, _bad) in ages.items():
            markers = who_names.get(who, ())
            if not any(mk in window for mk in markers):
                continue
            if n != val and abs(n - val) <= 6:
                out.append(
                    f"[AGE]   {path.name}:{line_of(text, m.start())} "
                    f"«{word} лет» рядом с упоминанием «{who}», "
                    f"канон — {val}\n         {excerpt(text, m.start())}")
    return out


def parse_number(word: str):
    w = word.lower().strip()
    if w.isdigit():
        return int(w)
    return NUMERALS.get(w)


def collect_dates(text: str):
    """Явные даты вида «тринадцатого числа месяца червня»."""
    ordinals = {
        "первого": 1, "второго": 2, "третьего": 3, "четвёртого": 4, "пятого": 5,
        "шестого": 6, "седьмого": 7, "восьмого": 8, "девятого": 9, "десятого": 10,
        "одиннадцатого": 11, "двенадцатого": 12, "тринадцатого": 13,
        "четырнадцатого": 14, "пятнадцатого": 15, "двадцатого": 20,
    }
    found = []
    pat = re.compile(
        r"(" + "|".join(ordinals) + r")\s+числа\s+месяца\s+(\w+)", re.IGNORECASE)
    for m in pat.finditer(text):
        day = ordinals[m.group(1).lower()]
        mon_word = m.group(2).lower()
        month = None
        for stem, num in MONTH_STEMS.items():
            if mon_word.startswith(stem):
                month = num
                break
        if month:
            abs_day = (month - 1) * DAYS_IN_MONTH + day
            found.append((m.start(), day, mon_word, abs_day, abs_day - ATTACK_ABS))
    return found


def collect_spans(text: str):
    """Упоминания сроков: «три месяца», «пять недель», «двенадцать дней»."""
    words = "|".join(list(NUMERALS) + [r"\d+"])
    pat = re.compile(
        rf"\b({words})\s+(дн(?:я|ей|и)|недел(?:ю|и|ь|ей)|месяц(?:|а|ев))\b",
        re.IGNORECASE)
    out = []
    for m in pat.finditer(text):
        n = parse_number(m.group(1))
        if n is None:
            continue
        unit = m.group(2).lower()
        if unit.startswith("дн"):
            days = n
        elif unit.startswith("недел"):
            days = n * 7
        else:
            days = n * 30
        out.append((m.start(), m.group(0), days))
    return out


def check_timeline(text: str, path: Path) -> list[str]:
    """Сверка явной даты со сроками «от нападения», названными в той же главе."""
    out = []
    dates = collect_dates(text)
    if not dates:
        return out
    for pos, day, mon, abs_day, since in dates:
        out.append(
            f"[DATE]  {path.name}:{line_of(text, pos)} "
            f"{day} {mon} = абсолютный день {abs_day}, "
            f"от нападения {since} дн.\n         {excerpt(text, pos)}")
        # ищем в главе сроки «N месяцев/недель», близкие по смыслу к «от начала»
        for spos, sword, sdays in collect_spans(text):
            if sdays < 45:
                continue  # короткие сроки почти всегда о другом
            delta = abs(sdays - since)
            if delta > 20:
                out.append(
                    f"[!TIME] {path.name}:{line_of(text, spos)} "
                    f"«{sword}» ≈ {sdays} дн. расходится с датой главы "
                    f"({since} дн. от нападения) на {delta} дн.\n"
                    f"         {excerpt(text, spos)}")
    return out


def check_span_conflicts(text: str, path: Path) -> list[str]:
    """Внутри главы: разные сроки об одном и том же (эвристика по контексту).

    Ловит DEF-04: «пять недель» и «пятнадцать дней» в одной главе про жизнь
    до нападения. Сигнал — два срока с разбросом больше чем вдвое,
    оба длиннее недели.
    """
    spans = [(p, w, d) for p, w, d in collect_spans(text) if d >= 7]
    out = []
    seen = set()
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            p1, w1, d1 = spans[i]
            p2, w2, d2 = spans[j]
            if d1 == d2:
                continue
            lo, hi = min(d1, d2), max(d1, d2)
            if hi >= lo * 2 and lo >= 14:
                key = (w1.lower(), w2.lower())
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    f"[?SPAN] {path.name}: «{w1}» (стр. {line_of(text, p1)}) "
                    f"и «{w2}» (стр. {line_of(text, p2)}) — "
                    f"разброс {lo}→{hi} дн. Проверить, об одном ли сроке речь")
    return out


def check_first_mentions(text: str, path: Path, facts) -> list[str]:
    """Имена собственные: где встречаются впервые в этой главе."""
    out = []
    names = [good for key, good, _b, _n in facts
             if key.startswith(("возраст",)) is False
             and good and good[0].isupper() and " " not in good]
    for name in sorted(set(names)):
        m = re.search(rf"\b{re.escape(name)}\w*\b", text)
        if m:
            out.append(f"    {name:14} впервые строка {line_of(text, m.start()):5}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Проверка канона и хронологии")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--timeline", action="store_true",
                    help="дополнительно печатать разбор дат и сроков")
    ap.add_argument("--names", action="store_true",
                    help="печатать первые упоминания имён")
    ap.add_argument("--facts", default=str(FACTS_PATH))
    args = ap.parse_args(argv)

    facts = load_facts(Path(args.facts))
    if not facts:
        return 2

    problems = 0
    for raw in args.paths:
        p = Path(raw)
        if not p.exists():
            print(f"ERROR: нет файла {p}", file=sys.stderr)
            return 2
        text = p.read_text(encoding="utf-8")

        found = check_forbidden(text, p, facts)
        found += check_ages(text, p, facts)
        found += check_timeline(text, p)
        found += check_span_conflicts(text, p)

        hard = [f for f in found if f.startswith(("[CANON]", "[!TIME]", "[AGE]"))]
        problems += len(hard)

        if found or args.names:
            print(f"\n=== {p} ===")
        for f in found:
            if f.startswith("[DATE]") and not args.timeline:
                continue
            if f.startswith("[?SPAN]") and not args.timeline:
                continue
            print(f)
        if args.names:
            print("  первые упоминания:")
            for line in check_first_mentions(text, p, facts):
                print(line)

    print("\n--- итог ---")
    print(f"жёстких расхождений с каноном: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
