#!/usr/bin/env python3
"""Реестр тиков: обороты, ставшие авторским автоматизмом.

Тик отличается от ошибки тем, что каждое отдельное вхождение написано
правильно. Виден он только в массе — поэтому нужен счётчик, а не глаз.

Главная находка ревью: конструкция «это разные вещи, и вторая…» —
12 вхождений у четырёх разных персонажей и в наррации. Стала авторским
голосом, надетым на всех, и прямо противоречит цели «персонажи должны
звучать по-разному».

Использование:
    python3 scripts/tics.py 03-manuscript/arc-*/ch-*.md
    python3 scripts/tics.py --show "разные вещи" 03-manuscript/arc-03/ch-11.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# (имя, регулярка, норма на 13 глав, норма на 1000 слов или None)
TICS = [
    ("«разные вещи»",        r"разн(?:ые|ое|ая)\s+(?:вещи|полномочия)|это разное", 3, None),
    ("«единственное, что я умею»", r"единственн\w+,?\s+что я (?:умею|могу)|это я умею", 2, None),
    ("«потому что»",         r"\bпотому что\b", None, 3.0),
    ("«ровно»",              r"(?<![А-Яа-яЁё])ровно(?![А-Яа-яЁё])", 45, None),
    ("«оказалось/оказался»", r"\bоказал\w+", 60, None),
    ("«посмотрел на меня»",  r"посмотрел\w*\s+на меня", 30, None),
    ("«не сразу»",           r"\bне сразу\b", 20, None),
    ("«дольше, чем»",        r"дольше,?\s+чем", 18, None),
    ("«я поняла»",           r"(?<![А-Яа-яЁё])[Яя] понял[аи](?![А-Яа-яЁё])", 45, None),
    ("«кивнул(а)»",          r"\bкивну\w+", 30, None),
    ("«помолчал(а)»",        r"\bпомолча\w+", 25, None),
    ("«— Да.» репликой",     r"(?m)^—\s*Да\.\s*$", 45, None),  # ~3-4 на главу
    ("«Я...» в нач. абзаца", None, None, None),   # считается отдельно
    ("финал через сон",      None, None, None),   # считается отдельно
    ("стаж как аргумент",    None, None, None),   # только в репликах, §1.12
    ("«я про / ты про»",     None, None, None),   # только в репликах, §1.13
    ("«я не про X»",         None, None, None),   # запрещено вовсе, §1.13
]

# --- тики, которые считаются ТОЛЬКО в прямой речи (§1.12, §1.13) ---

# «я двадцать три года веду назначения», «я тут двадцать девять лет»
# Глаголы состояния: «он лежал тысячу лет» — не стаж, а срок хранения.
# Стаж как аргумент — это всегда деятельность говорящего.
STAZH_SKIP = re.compile(r"\b(?:лежал\w*|пролежал\w*|простоял\w*|стоял\w*|"
                        r"провалял\w*|спал\w*|проспал\w*)\b", re.IGNORECASE)

# Возраст человека — не выслуга: «я ему в двенадцать лет говорил»,
# «мне было восемнадцать лет», «сторож, шестьдесят лет».
STAZH_AGE = re.compile(
    r"\b(?:в|мне|ему|ей|нам|им)\s+(?:было\s+)?[а-яё]+(?:дцать|надцать|сят)?\s*лет\b"
    r"|\bмне\s+было\b|\b\w+,\s*[а-яё]+\s+лет,", re.IGNORECASE)

STAZH = re.compile(
    r"\b(?:я|мы|он|она|у меня|мне|у него|у неё)\b[^.!?—]{0,45}?"
    r"\b(?:двенадцать|четырнадцать|шестнадцать|восемнадцать|одиннадцать|"
    r"девятнадцать|двадцать|тридцать|сорок|пятьдесят|шестьдесят|семьдесят|"
    r"тысяч\w*)\s*\w*\s+(?:лет|года|год)\b", re.IGNORECASE)

# «я про место спрашиваю», «ты про пропажу», «я об этом думал»
PRO_PRO = re.compile(
    r"\b(?:я|ты|вы|мы)\s+(?:не\s+)?(?:про|об|о)\s+(?:это|том|то|неё|него|них|"
    r"чём|что|вес|время|место|руки|наказание)\b", re.IGNORECASE)

# «я не про X» — форма запрещённой конструкции «не X, а Y» (§1.1)
NE_PRO = re.compile(r"\b(?:я|ты|вы|мы)\s+не\s+(?:про|об|о)\b", re.IGNORECASE)

# Исключение, согласованное с автором: живое разговорное «да я не про то»
# в перебранке (гл. 22). Это не конструкция-объяснение, а перебивка спорящего:
# он не объявляет предмет речи, а отмахивается от чужого возражения.
NE_PRO_OK = re.compile(r"\bда\s+я\s+не\s+про\s+то\b", re.IGNORECASE)


def dialogue_lines(text: str):
    """Строки прямой речи (начинаются с тире)."""
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("—")]

SLEEP_END = re.compile(
    r"(?:легла|заснула|уснула|не засыпала|задула свеч|потушила лампу|"
    r"спать|засыпала)[^.\n]{0,40}\.\s*$", re.IGNORECASE)


def count_ya_paragraphs(text: str):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text)
             if p.strip() and not p.strip().startswith(("#", "---"))]
    if not paras:
        return 0, 0
    ya = sum(1 for p in paras if re.match(r"^Я(?![А-Яа-яЁё])", p))
    return ya, len(paras)


def ends_with_sleep(text: str) -> bool:
    tail = "\n".join(text.rstrip().splitlines()[-6:])
    return bool(SLEEP_END.search(tail))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Счётчик тиков")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--show", default=None,
                    help="показать все вхождения тика по имени (подстрока)")
    args = ap.parse_args(argv)

    paths = [Path(p) for p in args.paths]
    for p in paths:
        if not p.exists():
            print(f"ERROR: нет файла {p}", file=sys.stderr)
            return 2

    texts = {p: p.read_text(encoding="utf-8") for p in paths}
    total_words = sum(len(re.findall(r"[\w-]+", t)) for t in texts.values())

    if args.show:
        for name, pat, _n, _k in TICS:
            if pat and args.show.lower() in name.lower():
                print(f"=== {name} ===")
                for p, t in texts.items():
                    for m in re.finditer(pat, t):
                        ln = t.count("\n", 0, m.start()) + 1
                        s = max(0, m.start() - 60)
                        frag = " ".join(t[s:m.start() + 70].split())
                        print(f"  {p.name}:{ln}  …{frag}…")
        return 0

    print(f"Файлов: {len(paths)}, слов: {total_words}\n")
    print(f"{'тик':32} {'всего':>6} {'/1000':>7} {'норма':>7}  по главам")
    over = 0

    for name, pat, limit, per1000 in TICS:
        if pat is None:
            continue
        per_file, total = [], 0
        for p in paths:
            c = len(re.findall(pat, texts[p]))
            per_file.append(c)
            total += c
        rate = total * 1000 / max(total_words, 1)
        if per1000 is not None:
            bad = rate > per1000
            norm = f"{per1000}/1k"
        else:
            # Пороги заданы из расчёта на ОДНУ главу. При запуске по нескольким
            # файлам их надо масштабировать, иначе книга целиком всегда «в браке»:
            # 225 «ровно» на 31 главу — это 7 на главу при норме 45, то есть норма.
            scaled = limit * len(paths) if limit is not None else None
            bad = scaled is not None and total > scaled
            norm = f"{limit}/гл" if len(paths) > 1 else str(limit)
        flag = "  ❌" if bad else ""
        if bad:
            over += 1
        print(f"{name:32} {total:6} {rate:7.1f} {norm:>7}{flag}  {per_file}")

    # Фамилия отменена целиком (HARD-BLOCKERS §1.11, август 2026): в тексте её быть не должно
    surname = sum(texts[p].count("Дюваль") for p in paths)
    per_surname = [texts[p].count("Дюваль") for p in paths]
    if surname:
        over += 1
    print(f"{'фамилия «Дюваль» (запрещена)':32} {surname:6} {surname/max(len(paths),1):7.1f} "
          f"{'0':>7}{'  ❌' if surname else ''}  {per_surname}")

    # Тень зовёт POV по имени — норма 4 на главу (прежний тик переехал на имя)
    shadow_name = 0
    per_sn = []
    for p in paths:
        n = len(re.findall(r"\*[^*\n]*\bСильвия\b[^*\n]*\*", texts[p]))
        shadow_name += n
        per_sn.append(n)
    bad = any(n > 4 for n in per_sn)
    if bad:
        over += 1
    print(f"{'Тень зовёт «Сильвия»':32} {shadow_name:6} {shadow_name/max(len(paths),1):7.1f} "
          f"{'4/гл':>7}{'  ❌' if bad else ''}  {per_sn}")

    # «Я...» в начале абзаца
    ya_tot = pa_tot = 0
    per = []
    for p in paths:
        ya, pa = count_ya_paragraphs(texts[p])
        ya_tot += ya
        pa_tot += pa
        per.append(f"{ya * 100 // max(pa, 1)}%")
    pct = ya_tot * 100 // max(pa_tot, 1)
    bad = pct > 11
    if bad:
        over += 1
    print(f"{'«Я...» в начале абзаца':32} {ya_tot:6} {pct:6}% {'11%':>7}"
          f"{'  ❌' if bad else ''}  {per}")

    # Числа в прозе (директива 11.08: «правило руки» — число живёт, только
    # если его кто-то держит, чувствует телом или считает вслух; справка
    # автора читателю — тик). Слова-числительные + цифры, на 1000 слов.
    NUM_RX = re.compile(
        r"\b(\d+|один|одна|одно|одной|одному|две?|двух|двое|три|трёх|трое|"
        r"четыре|четырёх|пять|пяти|шесть|шести|семь|семи|восемь|восьми|девять|девяти|"
        r"десять|десяти|двадцат\w*|тридцат\w*|сорок\w*|пятидесят\w*|шестидесят\w*|"
        r"семидесят\w*|восьмидесят\w*|девяност\w*|(?:один|две|три|четыр|пят|шест|"
        r"сем|восем|девят)надцат\w*|сто|ста|сотн\w*|двести|триста|четыреста|пятьсот|"
        r"тысяч\w*|полтора|полторы|полутора|оба|обе|раза|раз)\b", re.IGNORECASE)
    num_tot = sum(len(NUM_RX.findall(texts[p])) for p in paths)
    per_num = [f"{len(NUM_RX.findall(texts[p])) * 1000 // max(len(texts[p].split()), 1)}"
               for p in paths]
    wd = sum(len(texts[p].split()) for p in paths)
    rate = num_tot * 1000 // max(wd, 1)
    bad = rate > 25
    if bad:
        over += 1
    print(f"{'«числа в прозе» /1000 слов':32} {num_tot:6} {rate:6.0f}  {'25':>7}"
          f"{'  ❌' if bad else ''}  {per_num}")

    # финалы через сон
    sleeps = [p.name for p in paths if ends_with_sleep(texts[p])]
    bad = len(sleeps) > 3
    if bad:
        over += 1
    print(f"{'финал главы через сон':32} {len(sleeps):6} {'':7} {'3':>7}"
          f"{'  ❌' if bad else ''}  {sleeps}")

    # --- тики прямой речи: §1.12 и §1.13 ---
    for label, rx, per_chapter in (
            ("стаж как аргумент", STAZH, 1),
            ("«я про / ты про»", PRO_PRO, 2),
            ("«я не про X» (запрещено)", NE_PRO, 0)):
        per_file, total = [], 0
        for p in paths:
            c = sum(1 for ln in dialogue_lines(texts[p])
                    if rx.search(ln)
                    and not (rx is STAZH and (STAZH_SKIP.search(ln)
                                             or STAZH_AGE.search(ln)))
                    and not (rx is NE_PRO and NE_PRO_OK.search(ln)))
            per_file.append(c)
            total += c
        limit = per_chapter * len(paths)
        bad = total > limit
        if bad:
            over += 1
        norm = f"{per_chapter}/гл" if per_chapter else "0"
        print(f"{label:32} {total:6} {total / max(len(paths), 1):7.1f} {norm:>7}"
              f"{'  ❌' if bad else ''}  {per_file}")

    print(f"\n--- итог ---\nтиков сверх нормы: {over}")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
