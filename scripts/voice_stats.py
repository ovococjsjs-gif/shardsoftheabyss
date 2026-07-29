#!/usr/bin/env python3
"""Замеры голосов: длина реплик по говорящим.

Существует потому, что норма «доля Тени ≥12% объёма главы» была выполнена
во всех главах арки 3 — и Тень при этом провалилась как персонаж.
Числовая норма ловит отсутствие, но не ловит невыразительность.

Ключевой замер — средняя длина реплики Тени. Ориентир (Джонни Сильверхенд)
предполагает, что она огрызается: норма ≤7 слов. Замер по написанному
дал 9,1 — самый многословный персонаж книги.

Использование:
    python3 scripts/voice_stats.py 03-manuscript/arc-03/ch-11.md
    python3 scripts/voice_stats.py --long 03-manuscript/arc-03/ch-11.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SHADOW_MAX_AVG = 7.0
SHADOW_MIN_SHARE = 0.12
SILVIA_MIN_AVG = 4.0

TAG = re.compile(r"\s—\s+[а-яё][^—]*?(?:\.|$)")


def words(s: str) -> int:
    return len(re.findall(r"[\w-]+", s))


def collect(text: str):
    shadow, spoken = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("*") and not s.startswith("**"):
            body = TAG.sub(" ", s.strip("*"))
            if words(body):
                shadow.append(body.strip())
        elif s.startswith("—"):
            body = TAG.sub(" ", s[1:])
            if words(body):
                spoken.append(body.strip())
    return shadow, spoken


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Замеры голосов")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--long", action="store_true",
                    help="показать самые длинные реплики Тени")
    args = ap.parse_args(argv)

    fail = 0
    print(f"{'файл':12} {'слов':>6} {'Тень%':>6} {'Тень ср':>8} "
          f"{'реплик':>7} {'вслух ср':>9}")

    for raw in args.paths:
        p = Path(raw)
        if not p.exists():
            print(f"ERROR: нет файла {p}", file=sys.stderr)
            return 2
        t = p.read_text(encoding="utf-8")
        total = words(t)
        shadow, spoken = collect(t)

        sh_words = sum(words(x) for x in shadow)
        share = sh_words / max(total, 1)
        sh_avg = sh_words / max(len(shadow), 1)
        sp_avg = sum(words(x) for x in spoken) / max(len(spoken), 1)

        flags = ""
        if shadow:
            if sh_avg > SHADOW_MAX_AVG:
                flags += " ❌длинно"
                fail += 1
            if share < SHADOW_MIN_SHARE:
                flags += " ❌мало"
                fail += 1
        if sp_avg < SILVIA_MIN_AVG:
            flags += " ❌реплики коротки"
            fail += 1

        print(f"{p.name:12} {total:6} {share:5.0%} {sh_avg:8.1f} "
              f"{len(shadow):7} {sp_avg:9.1f}{flags}")

        if args.long and shadow:
            print("   самые длинные реплики Тени:")
            for x in sorted(shadow, key=words, reverse=True)[:6]:
                print(f"     [{words(x):2}] {x[:96]}")

    print(f"\nнормы: Тень ср ≤{SHADOW_MAX_AVG} сл., доля ≥{SHADOW_MIN_SHARE:.0%}, "
          f"реплики вслух ср ≥{SILVIA_MIN_AVG}")
    print(f"\n--- итог ---\nнарушений: {fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
