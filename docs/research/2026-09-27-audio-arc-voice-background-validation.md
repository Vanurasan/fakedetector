# M3-R3B — natural voice-message / background-confound validation: corpus gate

Дата: **2026-09-27**. **DONE / OWNER ACCEPTED BLOCKED FEASIBILITY RESULT**.
Owner disposition от 2026-09-27: текущий owner gate **CLOSED** решением
об отсрочке (§6); corpus gate не пройден, измерения не выполнены.
Baseline `c1a86d17fba5372b10990a53ac546488e22f68ea`, ветка
`feat/stage12-macro3-audio-analyzer-expansion-wave1`; начальное дерево чистое.

## 1. Что установлено и что не измерено

Пригодный primary-корпус для заданного natural voice-message scope пока
не установлен. Это ограниченный поиск доступных источников, не доказательство
отсутствия подходящего корпуса вообще. Исходное задание M3-R3B требует ≥12 независимых speakers
и ≥3 отдельных natural takes на repeated prompt; цель — 20×5×3.
Формальное число файлов не заменяет эти условия и пригодность речевой области.

Допущенных speakers, prompts, natural takes, source files и comparisons: **0**.
Corpus membership, speaker/background split и predeclaration **NOT_CREATED**.
Новых ARC outcomes, distributions, retrieval/localization/cap/resource measurements
нет; determinism/numerical checks **NOT_RUN**. Нельзя делать вывод, что gap
сохранился, исчез или что background failure narrow/fundamental.

## 2. Проверка источников: сначала существующий корпус

Ниже сохранена исходная feasibility-проверка scope M3-R3B до owner disposition
в §6; это не текущий блокер дипломной фазы. Проверялась документация поставщиков,
аудио не использовалось в измерениях.
Лицензия статьи не переносится на dataset. Числа в таблице — заявленные
поставщиками, не проверенная membership будущего M3-R3B.

| Кандидат / первичный источник | Существенный факт | Причина отсутствия допуска primary-корпуса |
|---|---|---|
| [LaMIT v2](https://data.mendeley.com/datasets/sjwb9hymhn/2), ранее использован в M3-R3A | 4 speakers, 2 takes; provenance уже в REFERENCES | Не проходит минимальные counts; продолжать малый pilot запрещено |
| [BanglaSER v5](https://data.mendeley.com/datasets/t9h6p943xy/5), [статья авторов](https://pmc.ncbi.nlm.nih.gov/articles/PMC8980634/) | Neutral subset: 27 speakers ×3 statements ×3 repetitions; CC BY 4.0. Авторы описывают enacted speech, обучение участников, преимущественно тихую комнату и удаление фонового шума | Counts достаточны по описанию; **не отклонён за малый размер**. Но это не установленная ordinary natural voice-message population. Допустимость такого primary scope требует явного решения; unprocessed mobile subset с нужными counts и session/device mapping не установлен. Возможно дополнительное clean-speech исследование, не подмена текущей задачи |
| [HI-MIA / OpenSLR85](https://www.openslr.org/85/), [статья авторов §2](https://arxiv.org/html/1912.01231v1#S2) | Apache 2.0; многократные wake-up utterances, реальные домашние TV/music условия; средняя длительность около 1 s | Короткие wake words не являются полноценными voice messages; не установлен subset ≥12 speakers с ≥3 takes, обеспечивающими неизменные полные 2L support. Микрофоны одной записи не независимые takes; padding/склейка слов не разрешены |
| [CHAINS / LDC2008S09](https://catalog.ldc.upenn.edu/LDC2008S09), [руководство](https://catalog.ldc.upenn.edu/docs/LDC2008S09/manual/html/) | 36 speakers, разные стили, LDC agreement; RSI — синхронная имитация, в release выбран один повтор | Число стилей/произнесений при сборе нельзя принять за ≥3 опубликованных обычных natural takes. Доступ и права проекта на аудио не установлены |
| [RSR2015, статья авторов §§3,6](https://www.sciencedirect.com/science/article/pii/S0167639314000156) | 300 speakers, 9 sessions, повторные фразы на mobile devices; распространение требует agreement | Перспективен по recording design; dataset agreement и доступ проекта не установлены. Открытая статья не разрешает использование записей |
| [RedDots, статья авторов](https://www.isca-archive.org/interspeech_2015/lee15_interspeech.html), [страница проекта](https://sites.google.com/site/thereddotsproject/) | Mobile repeated-session design релевантен; текущая страница проекта перенаправляет на Google sign-in | Не установлены конкретный доступный release, его права и membership ≥12×3. Лицензии replay-производных не принимаются за разрешение на оригинал |
| [DAPS, поставщик](https://zenodo.org/records/4660670) | 20 speakers, aligned studio/device/environment versions одной речи | Версии одного исходного speech материала не доказывают независимое повторное произнесение; qualifying repeated-take subset не установлен |

Read speech разрешена заданием при отдельном обосновании. Здесь всеобщая замена
primary population на enacted, denoised материал не обоснована: она оставила бы
именно естественные voice-message/background условия вне наблюдения. Даже CC BY
и достаточные counts BanglaSER не решают этот вопрос. Это оценка пригодности
к текущему scope, не заявление о недействительности лицензии или синтетичности речи.
Ссылки на поставщиков проверены; файлы аудио не получены и не измерены.
Ошибки отдельных HTTP/API запросов сохранены как ограничения доступа, не как
доказательство удаления корпуса или отсутствия у него подходящих записей.

## 3. Совместное использование корпусов и решение по acquisition

Комбинация рассмотрена после одиночных источников. Добавление LaMIT к другому
корпусу не создаёт третьего take у его speakers; matched phrase у другого
speaker не заменяет повторение тем же человеком. Каналы, device versions,
overlays и copy derivatives не увеличивают independent population.
Объединение BanglaSER с короткими HI-MIA utterances не восполняет отсутствие
подтверждённой natural voice-message primary population с полноценным support.
Корпуса с неустановленными правами не добавлены ради численного минимума.
Поэтому совместный допущенный корпус также **не установлен**.

По итогам feasibility был предложен owner gate: утверждение first-party
acquisition plan и организация сбора либо предоставление подходящего корпуса.
Этот gate закрыт решением об отсрочке (§6), а не разрешением acquisition.
Внешний `first-party-recording-plan.md` содержит пять новых prompts, 20 speakers,
три разнесённых исполнения, согласия, идентификаторы, устройства/комнаты,
натуральные фоновые условия, отдельные overlays, hash/manifest и split rules.
План сохранён как будущий calibration/acquisition design; это не утверждённая
predeclaration, не собранные данные и не разрешение first-party записи сейчас.
Ни участники, ни записи, ни их согласия не выдуманы; контакты никому не отправлены.

## 4. Сохранённые методологические границы

Frozen ARC v2 из M3-R3A проверен чтением SHA-256, без исполнения:
`04a2d54f0e5bc51c3eacf376cd797b16c178dd6a9740accb626cc77e92bfa625`.
Формула, compensated float64 accumulation, normalization, descriptor, NCC,
guard, search bounds, seed/candidate caps, overlap, support, ties и channels
не изменены. Никакого tuning, нового preprocessing или runtime dependency нет.

Текущий принятый ARC статус **NEEDS_TARGETED_RESEARCH** сохраняется;
исследовательский outcome измерительной части M3-R3B — **NOT_EVALUATED**.
Ограниченная поддержка clean-speech гипотезы из M3-R3A сохранена и не расширена.
**PERIODIC / REPEATED BACKGROUND** остаётся основным нерешённым confound;
новых свидетельств о нём эта feasibility-проверка не даёт.
**Production calibration NOT AUTHORIZED**. Production threshold, method
acceptance, analyzer implementation/registration, Finding и automatic background
gate отсутствуют; risk/correlation и public contracts не изменены.
ATD/ASC **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD** остаются unresolved;
Macro 3 **IN_PROGRESS** и его closure rule сохранены.

## 5. Артефакты и проверки

Research root: `C:\Users\Vanur\Desktop\FakeDetector-Work\research\M3-R3B-arc-voice\`.
Сохранены доступные provider/paper/license snapshots, источник и SHA каждого
snapshot, frozen ARC identity и acquisition plan. `predeclaration.md` не создана:
конкретные membership, permissions, background sources и splits ещё отсутствуют.
REFERENCES не изменён: новых источников аудио или кода в измерениях нет;
таблица выше — журнал feasibility, не новый dataset admission.

Review root: `C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-R3B-arc-voice\`.
Bundle: `complete.diff` (включает этот untracked отчёт полностью),
`review-summary.md`, `git-status.txt`, `corpus-feasibility.md`,
`provenance-summary.md`, `first-party-recording-plan.md`.
Проверки: `git diff --check`, просмотр intended diff и финального status.
Focused tests и frozen oracle suite не запускались, поскольку measurement gate
не пройден. Full quality barrier/strict certification не выполнялись.
Agent self-report не owner acceptance; Git mutations не выполнялись.

## 6. OWNER DISPOSITION — 2026-09-27

Владелец принял feasibility result: **M3-R3B — DONE / OWNER ACCEPTED BLOCKED
FEASIBILITY RESULT**. Текущий owner gate **CLOSED**; corpus gate не объявлен
пройденным. Результаты проверки источников и отсутствие измерений сохранены.

Широкая source-level validation с ≥12 speakers / ≥3 независимыми natural takes:
**DEFERRED UNTIL CALIBRATION / PRODUCTION-READINESS RESEARCH**.
Она не требуется для текущей дипломной proof-of-concept фазы.
**FIRST_PARTY_ACQUISITION_AUTHORIZED_NOW: NO**;
**FIRST_PARTY_CORPUS_REQUIRED_FOR_CURRENT_DIPLOMA_PHASE: NO**.
Внешний first-party recording plan сохранён для будущего acquisition/calibration;
ни сбор, ни recruitment сейчас не разрешены. План не удалён.

ARC-NCC-1 остаётся **NEEDS_TARGETED_RESEARCH**. Ограниченное clean-speech
свидетельство M3-R3A сохраняется в его заявленном scope. Frozen ARC v2,
формулы, numerics, search/caps/support и channel behavior не изменены.
Измерения ARC в этой acceptance-задаче не запускались.

Следующий активный scope — **M3-R3C — ARC Diploma Stress & Challenge Validation**:
разнообразная существующая речь нескольких speakers, обычная речь без известных
копий, controlled exact/gain/codec/noise copy-paste derivatives и diverse
music/TV/speech/ambience/hum/tone/repeated-background challenges. Цель — описать
границы работы frozen v2 и высокую benign correspondence. Подробный план —
в [ROADMAP](../ROADMAP.md#audio-m3r3c); M3-R3C ещё не выполнен.

Это не population calibration; same-speaker/same-phrase/three-take membership
для M3-R3C не требуется, поскольку broad natural re-speech validation отложена.
Source identity/provenance остаются обязательными; предпочтителен явно
rights-established/open материал. Производные сохраняют точные parent/recipe
hashes, raw media остаются вне Git. Production threshold/FPR claim не допускаются.
**Production calibration NOT AUTHORIZED**, production threshold **NONE**,
production analyzer **NO**. ATD/ASC сохраняют
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**, оба обязательства unresolved.
Macro 3 — **IN_PROGRESS**. Принятие feasibility не является production acceptance.

Запись owner disposition и полный intended diff проверены владельцем;
staging/commit остаются владельцу. Тесты, эксперименты, quality barrier,
certification и Git mutations в этой задаче не выполнялись.
