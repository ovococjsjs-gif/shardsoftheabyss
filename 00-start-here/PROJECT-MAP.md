# PROJECT-MAP (обновлено 2026-07-24)

## 1. Логика
Проект разделен на 5 папок, работает в 3 контекстных уровнях.

Папки:
- `00-start-here/` — короткий вход
- `01-canon/` — канон и мир
- `02-writing-system/` — голос, процесс, фильтры
- `03-manuscript/` — рукопись (теперь с подпапками arc-01 и arc-02)
- `90-archive/` — старые исходники и дубли

Контекстные уровни:
- Уровень 1 — короткий сессионный пакет: SESSION-BRIEF, ESSENCE, HARD-BLOCKERS, VOICE-SYSTEM, LIVE-REALITY-CONTRACT, WORKFLOW-AND-QUALITY-GATE
- Уровень 2 — рабочее углубление: PROJECT-MAP, STYLE-EXAMPLES, IDEAL-CHAPTER-TEMPLATE, MANUSCRIPT-STATUS
- Уровень 3 — длинная база: 01-canon/*, 03-manuscript/*, архив

## 2. Что где лежит

### `00-start-here/`
- `SESSION-BRIEF.md` — что сейчас актуально, риски, что читать первым
- `ESSENCE.md` — суть проекта в 1-2 страницы, дистиллят библии, голосов, центральной драмы (новое)
- `PROJECT-MAP.md` — этот файл

### `01-canon/`
- `PROJECT-STATUS.md` — краткое состояние
- `project-bible.md` — главный канон (184к символов)
- `world-expansion-v0.1.md` — рабочие предложения, не весь канон

### `02-writing-system/`
- `PRIMARY-WORK-INSTRUCTION.md` — что такое один проход = рекурсивный цикл
- `HARD-BLOCKERS.md` — короткий закон, абсолютные запреты, порядок перед показом прозы
- `VOICE-SYSTEM.md` — авторский голос vs голоса персонажей, гейт различимости
- `LIVE-REALITY-CONTRACT.md` — пишем по живому, а не просто прозу, эффект реальности (новое, Level 1 обязателен)
- `WORKFLOW-AND-QUALITY-GATE.md` — процесс, 4 режима чтения, gate A-D
- `IDEAL-CHAPTER-TEMPLATE.md` — паспорт главы, пространственный контур, голоса, блокеры
- `STYLE-EXAMPLES.md` — реальные правки было→стало

### `03-manuscript/`
#### Корень
- `arc-01-v4-combined.md` — собранная арка 1, гл.1-4, 27.4к слов, сильная фиксация
- `ARC-01-AUDIT.md`, `CH01-AUDIT` — аудиты арки 1
- `ARC-02-PLAN.md` — архитектура арки 2 (гл.5-9)
- `CH05-SCENE-MAP.md`, `CH06-DRAFT-BRIEF.md` — старые файлы для совместимости
- `ch-05-draft.md`, `ch-06-draft.md` — старые черновики 5-6 (оставлены)
- `MANUSCRIPT-STATUS.md` — единый статус по всем главам (новое)
- `ARC-02-AUDIT.md` — аудит 5-6 (новое)
- `README.md` — правило работы с рукописью

#### `arc-02/` — чистая папка второй арки (новое)
- `ch05-scene-map.md`, `ch05-draft-brief.md`, `ch05-draft.md`
- `ch06-scene-map.md`, `ch06-draft-brief.md`, `ch06-draft.md`
- дальнейшие главы 7-9 будут добавляться сюда

### `90-archive/`
- `legacy-source-docs/` — старые отдельные документы
- `duplicates/` — полные дубли SKILL и т.д.

### `scripts/`
- `style_guard.py` — автогвард блокеров: не X а Y, костяшки, уголки губ, тройки и тд.

## 3. Что считать главным

Канон: project-bible + PROJECT-STATUS
Рабочая система: PRIMARY-WORK-INSTRUCTION, HARD-BLOCKERS, VOICE-SYSTEM, LIVE-REALITY-CONTRACT, WORKFLOW-AND-QUALITY-GATE
Рукопись: arc-01-v4-combined + arc-02/ch05-06 draft + v5/ переписывание с нуля
Суть: ESSENCE.md

## 4. Что делать перед разными задачами

Если пишешь новую сцену/главу (особенно после 4-й):
1. SESSION-BRIEF.md
2. ESSENCE.md
3. PRIMARY-WORK-INSTRUCTION.md
4. HARD-BLOCKERS.md
5. VOICE-SYSTEM.md
6. WORKFLOW-AND-QUALITY-GATE.md
7. При необходимости — scene-map + draft-brief конкретной главы из arc-02/ + канон по спорному месту

Если проверяешь арку 1:
1-5 как выше + arc-01-v4-combined + библя по спорным местам + CH01-CH04-AUDIT

Если проверяешь арку 2 (гл.5-6):
1-5 как выше + MANUSCRIPT-STATUS + ARC-02-PLAN + ARC-02-AUDIT + ch05/06-scene-map + ch05/06-draft + style_guard

## 5. Что изменилось 2026-07-24 чтобы убрать бардак после 4-й
- Удален мусорный файл «1» в корне
- Создана папка 03-manuscript/arc-02/ с единым неймингом ch05/ch06
- Добавлены недостающие ch05-draft-brief и ch06-scene-map для симметрии
- Созданы ESSENCE.md (дистиллят библии), MANUSCRIPT-STATUS.md (единый статус), ARC-02-AUDIT.md (аудит 5-6)
- Обновлены README рукописи и PROJECT-MAP
- Все текущие черновики 5-6 проходят style_guard 0 блокеров

## 6. Главный результат структуры
Короткий вход (ESSENCE+SESSION-BRIEF+HARD-BLOCKERS+VOICE) → рабочая система → только потом длинный канон и рукопись.
После 4-й главы теперь ясно: где план арки 2, где черновики, где аудиты, что осталось доделать.
