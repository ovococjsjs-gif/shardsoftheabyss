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
            bad = limit is not None and total > limit
            norm = str(limit)
        flag = "  ❌" if bad else ""
        if bad:
            over += 1
        print(f"{name:32} {total:6} {rate:7.1f} {norm:>7}{flag}  {per_file}")

    # Тень зовёт POV по фамилии — норма 4 на главу
    shadow_name = 0
    per_sn = []
    for p in paths:
        n = sum(len(re.findall(r"Дюваль", m))
                for m in re.findall(r"\*[^*\n]+\*", texts[p]))
        shadow_name += n
        per_sn.append(n)
    limit_sn = 4 * len(paths)
    bad = shadow_name > limit_sn
    if bad:
        over += 1
    print(f"{'Тень зовёт «Дюваль»':32} {shadow_name:6} {shadow_name/max(len(paths),1):7.1f} "
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
            c = sum(1 for ln in dialogue_lines(texts[p]) if rx.search(ln))
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
