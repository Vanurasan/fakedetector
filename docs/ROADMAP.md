# ROADMAP.md

> Живая дорожная карта разработки и единственный источник истины о текущем состоянии реализации.
>
> Версия документа: **1.0**  
> Дата фиксации: **2026-07-24**  
> Статус документа: **ACTIVE**

---

## 0. Назначение документа

`ROADMAP.md` одновременно отвечает на два вопроса:

1. что уже выполнено;
2. что необходимо делать дальше.

Отдельный `CURRENT_STATE.md` не используется, чтобы не дублировать статусы.

Документ содержит:

- текущий этап;
- ближайшее действие;
- блокеры и открытые решения;
- этапы разработки;
- чек-листы;
- критерии завершения;
- обязательные проверки;
- границу MVP и работ после MVP.

Документ не повторяет архитектуру, общие контракты или алгоритмические
спецификации: их владельцы — `PROJECT.md`, `CONTRACTS.md` и `METHODS.md`.
Происхождение/лицензии принадлежат `REFERENCES.md`, workflow агента —
`../AGENTS.md`. Имя кандидата в плане не разрешает реализацию метода.

---

## 1. Правила ведения дорожной карты

### 1.1. Статусы

Используются только следующие статусы:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
DONE
```

Дополнительный статус для группы работ:

```text
AFTER_MVP
```

Смысл:

| Статус | Смысл |
|---|---|
| `NOT_STARTED` | Работа ещё не начата |
| `IN_PROGRESS` | Работа ведётся сейчас |
| `BLOCKED` | Продолжение невозможно без решения или внешнего условия |
| `DONE` | Все критерии завершения выполнены и проверены |
| `AFTER_MVP` | Работа сознательно отложена за границу MVP |

### 1.2. Правило единственного текущего этапа

В нормальном режиме только один этап имеет статус `IN_PROGRESS`.

Параллельная работа разрешается только когда:

- задачи не меняют одни и те же контракты;
- зависимости между ними явно отсутствуют;
- это не мешает получить проверяемый результат этапа.

### 1.3. Когда этап считается завершённым

Этап переводится в `DONE` только если:

- выполнены все обязательные задачи;
- выполнены критерии завершения;
- проходят связанные тесты;
- код соответствует применимым каноническим решениям в `PROJECT.md`,
  `CONTRACTS.md`, `METHODS.md` и `REFERENCES.md`;
- получена приёмка владельца по `../AGENTS.md`;
- обновлены чек-листы;
- принятое проектное изменение внесено в `CHANGELOG.md`, если оно было;
- отсутствуют скрытые заглушки, выданные за готовую функцию.

### 1.4. Как обновлять файл

После каждой законченной задачи агент обязан:

1. отметить выполненный пункт `[x]`;
2. обновить поле «Ближайшее действие»;
3. при завершении этапа обновить статус;
4. указать новые блокеры;
5. не переписывать описание уже выполненного этапа без причины;
6. не переносить историю изменений из `CHANGELOG.md` в дорожную карту.

### 1.5. Открытые решения

Если задача упирается в `OPEN`-решение:

- `BLOCKED` применяется только при невозможности продолжить без решения
  владельца, меняющего архитектуру, контракт или объём задачи; наличие открытого
  решения само по себе не останавливает независимую разрешённую работу;
- в разделе «Блокеры и решения» фиксируется конкретный вопрос;
- агент предлагает варианты и последствия;
- после выбора обновляется документ владельца соответствующей области
  по карте `PROJECT.md` §0.2;
- изменение вносится в `CHANGELOG.md`;
- работа продолжается.

---

## 2. Текущее состояние

```text
Общий статус: Stages 1–11 — DONE / CLOSED
Последний закрытый этап: Stage 11 — Post-MVP Normalization & Hardening
Статус Stage 10: DONE / CLOSED
Текущий этап: Stage 12 — Analyzer Expansion, Licensing & Product Validation
Статус Stage 11: DONE / CLOSED
Статус Macros 0–8 Stage 11: DONE / owner accepted
Последний завершённый Macro: Stage 12 Macro 3 — Audio Analyzer Expansion — Wave 1 (DONE / CLOSED / OWNER ACCEPTED / STRICTLY CERTIFIED — по подтверждению владельца в задании M4-R1)
Статус Stage 12: IN_PROGRESS
Текущий инкремент: DIPLOMA VRC REDESIGN RESEARCH — Sprint 1 — IN_PROGRESS / IMPLEMENTED / OWNER REVIEW PENDING (2026-10-15)
Дипломные реализации: PR #70 analyzer expansion, PR #71 ensemble, PR #72 controlled demo evaluation, PR #73 independent benign validation, PR #74 targeted VRC research — OWNER ACCEPTED / MERGED; текущий main baseline: 17843484
Macro 4: Video Analyzer Expansion — Wave 1 — IN_PROGRESS; M4-R2 VRC-DENSE-1 Stage A COMPLETE / SYNTHETIC_ONLY / OWNER ACCEPTED / COMPLETE WITH ENGINEERING FAIL (2026-10-12)
M4-R2: COMPLETE_144_CELL_MATRIX; 133 VALID / 11 LOCAL_FAIL / 0 GLOBAL_STOP / 0 NOT_EXECUTED; G1 PASS / G2 FAIL / G3 PARTIAL / G4 NOT_EVALUATED_STAGE_A / G5 DEFER
Stage B: BLOCKED / NOT AUTHORIZED; production: UNCHANGED / NO VRC PROMOTION; дальнейший полный Stage A rerun: NOT PLANNED
Ближайшее действие: owner review DIPLOMA VRC REDESIGN RESEARCH; кандидат D2__I25__K9__R10 прошёл заданные research prototype gates, но имеет ограничения поддержки/локализации; production VRC и ансамбль заморожены, прототип требует отдельного OWNER GATE
Статус Macro 0: DONE / merged
Решение владельца PROJECT_LICENSE: CLOSED — Apache-2.0
Состояние Macro 2: DONE / CLOSED; принятые результаты и основания закрытия приведены в §2.2
Исследовательская цепочка M2-R1–M2-R3D: OWNER_ACCEPTED; DQ — FINAL_HOLDOUT_PASS, Grid — DEFERRED_RESEARCH_ONLY
Реализация M2-A: DONE / OWNER ACCEPTED / PRODUCTION IMPLEMENTED
M2-BR1: DONE / OWNER_ACCEPTED_RESEARCH_CLOSURE; noise и resampling — RESEARCH_ONLY / WEAK_SIGNAL
M2-CR1: DONE / OWNER_ACCEPTED_RESEARCH_CLOSURE; thumbnail — RESEARCH_ONLY / WEAK_SIGNAL
Проверка closure commit: полный quality barrier и strict certification на clean committed SHA dbc24e32c028808f599a7d9982f6776cfe014b3c — PASS; оставшихся проверок Macro 2 нет
Слияние Macro 2: PR #67 merged в main как dee248b6ea2d7054c4e30d95c114d123a77918df; tree совпадает с сертифицированным closure tree; merge commit отдельно не сертифицировался
M3-R1: DONE / OWNER ACCEPTED RESEARCH SELECTION (2026-09-26); production audio-метод не принят
M3-ASC-D1: DONE / OWNER ACCEPTED DISPOSITION (2026-09-30); ASC — RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED, carry-forward RESOLVED; дальнейшей ASC promotion work в Macro 3 нет
M3-HYG-1: DONE / OWNER ACCEPTED (2026-10-01); hygiene gate CLOSED
M3-CR1: DONE / OWNER ACCEPTED CLOSURE (2026-10-01); CLOSURE_RECOMMENDATION: MACRO3_CLOSE / OWNER ACCEPTED; Macro 3 DONE / CLOSED / OWNER ACCEPTED
Активные исследования Macro 3: NONE; активные owner gates Macro 3: NONE
M3-ATD-D1: DONE / OWNER ACCEPTED DISPOSITION (2026-09-29); ATD — RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED, carry-forward RESOLVED; ATD не переоткрывается. Новых измерений нет. M3-R3D-F DONE / OWNER ACCEPTED RESEARCH RESULT (2026-09-29), confirmation MIXED; дальнейшее ARC retention development в текущем Macro 3 DEFERRED; production promotion ARC отложено до calibration / production-readiness research; production calibration NOT AUTHORIZED; G1–G6 CLOSED / ACCEPTED
M3-R2A: DONE / OWNER ACCEPTED RESEARCH RESULT (2026-09-26); production acceptance отсутствует
M3-R2B: DONE / OWNER ACCEPTED RESEARCH RESULT (2026-09-26); исторический outcome ARC-NCC-1 на тот момент — READY_FOR_LARGER_VALIDATION, только research readiness; текущий ARC disposition — в M3-R3D-F; статистическая независимость не установлена
Обязательный carry-forward Macro 3: ATD-LOCAL-1 и ASC-TV-1 — RESOLVED решениями владельца; MACRO3_ALL_REQUIRED_CARRY_FORWARD_RESOLVED: YES. Hygiene audit и закрытие Macro 3 приняты владельцем (см. [M3-CR1](#audio-m3-cr1))
Будущие работы: Stage 12 Macros 5–10 — NOT_STARTED; Stage 13+ ML — AFTER_MVP / NOT_STARTED
Критические блокеры принятого DQ scope M2-A: отсутствуют; остальные методы требуют собственных gates
Реализация программы: Этапы 1–11 завершены; MVP 0.1.0 DONE / CLOSED; финальная проверка Stage 11 — PASS
Документационная база: сформирована
```

### 2.1. Выполненная подготовка

- [x] подготовлен единый `PROJECT.md`;
- [x] подготовлен `CONTRACTS.md`;
- [x] подготовлена компактная живая дорожная карта;
- [x] подготовлены правила ведения `CHANGELOG.md`;
- [x] исключено отдельное дублирующее описание current state;
- [x] технологический стек первой версии зафиксирован;
- [x] архитектурные инварианты зафиксированы;
- [x] разделены серьёзность признака, риск и полнота анализа;
- [x] итоговая псевдовероятность запрещена без валидированного метода.

### 2.2. Принятое состояние и основания закрытия

Stage 12 явно разрешён владельцем 2026-09-20. Решение о лицензии закрыто:
в Pass 2 выбран Apache-2.0 (`PROJECT.md` §21.7); сведения о происхождении
и уведомлениях находятся в `REFERENCES.md`. Оформление лицензии и изменения
поставки проверены. После добавления `LICENSE` в Git владельцем повторные
release-package/release-verification тесты прошли: **47 passed**.
Macro 0 — `DONE / merged`. Macro 1 — Forensic Preprocessing Foundations —
`DONE / CLOSED / owner accepted`. M1-A–M1-G и targeted remediation —
`DONE / owner accepted / committed`. M1-H — `DONE`: независимый аудит закрытия
завершён; первичный результат — `REMEDIATE`, финальный независимый повторный
аудит — `PASS`, M1H-F01 и M1H-F02 — `CLOSED`, замечаний к исправлению — **0**.
Свидетельства закрытия и принятые ограничения приведены в разделе M1-H ниже.

Macro 1 — `DONE / CLOSED / merged`. Stage 12 / Macro 2 — **DONE / CLOSED**:
владелец принял итог по результатам независимого M2-HR6 и разрешил M2-CLOSE.
В production принят ровно один новый image-анализатор —
`image_jpeg_double_quantization@1.0.0`, метод DQ-HIST-1 / DQ-R3C-1;
M2-A — `DONE / OWNER ACCEPTED / PRODUCTION IMPLEMENTED`.
Остальные исследованные кандидаты остаются вне production:

- `image_jpeg_grid_consistency` — `DEFERRED_RESEARCH_ONLY`;
- `image_noise_residual_consistency`, N-MAD-MATCH-1 — `RESEARCH_ONLY / WEAK_SIGNAL`;
- `image_resampling_consistency`, R-D2-MATCH-1 — `RESEARCH_ONLY / WEAK_SIGNAL`;
- `image_embedded_thumbnail_consistency`, THUMB-NCC-GRAD-1 — `RESEARCH_ONLY / WEAK_SIGNAL`.

Production-каталог содержит ровно пять анализаторов (полный список — в разделе
Stage 12). Profile B и исторический enabled-пример из четырёх анализаторов
сохранены: DQ доступен через каталог, но автоматически в пример не добавлен.
Дополнительные реализация или исследование для закрытия Macro 2 не требуются;
возврат к research-only кандидатам возможен только по отдельному явному разрешению.
**M2H-D01 — DEFERRED TO MACRO 6**, не блокирует закрытие Macro 2;
корреляция, risk aggregation, DQ scoring и copy-move behavior не изменены.

Принятая последовательность: M2-R1–R4 — исследование, калибровка, holdout и
принятие DQ-метода; M2-A — production-реализация; M2-BR1 и M2-CR1 —
исследовательские закрытия. Независимый аудит M2-H, документационные исправления
M2-HR1 / HR3 / HR5 и финальная проверка готовности M2-HR6 завершены;
M2-HR6 — **PASS / OWNER ACCEPTED**, оставшихся BLOCKER/MAJOR/MINOR findings нет.

Хронология проверок: исходный аудит M2-H на clean SHA
`95296c992dbcd166ad263e785e9b14f100cefa2d` подтвердил полный quality barrier
**2792 passed / 17 skipped**, package tests, сборку sdist/wheel,
installed-wheel probe и strict package/release certification — **PASS**.
Последующие коммиты были docs-only. M2-HR6 на
`2286404e7b284daa252101000ec4685927e8852e` проверил финальную готовность
документации, без повторного полного barrier или strict certification.
После M2-CLOSE владелец выполнил полный quality barrier на clean committed
closure SHA `dbc24e32c028808f599a7d9982f6776cfe014b3c` — **PASS**:
**2792 passed / 17 skipped**, coverage **90%**, CLI smoke **PASS**.
Strict release certification командой
`uv run python scripts/verify_release.py --output-dir <external review path>`
на том же SHA — **PASS**: `overall_status=passed`, `certification_mode=strict`,
`certified=true`; `source_sha` и `source_sha_at_end` равны указанному closure SHA,
`source_sha_stable=true`, `source_tree_clean=true`,
`source_status_at_start=[]`, `source_status_at_end=[]`.
Успешно проверены сборка sdist и wheel из sdist, runtime установленного wheel
в свежем окружении, целостность release kit / ZIP, CLI, реальный HTTP runtime,
сохранение и получение результатов после перезапуска, очистка собственных процессов.
PR #67 (`feat: complete Stage 12 Macro 2 image analyzer expansion`) слит в main
как `dee248b6ea2d7054c4e30d95c114d123a77918df`. Tree обоих коммитов —
`bde328e72f7491106ad2ccafa88f495c323d04bf`: слияние не изменило содержимое
сертифицированного closure tree. Сам merge commit отдельно не проходил
сертификацию. Macro 2 остаётся **DONE / CLOSED**; оставшихся действий
по его финальной проверке нет.

#### Исторические свидетельства исследовательской цепочки

Состояния и предпосылки ниже относятся к соответствующим инкрементам,
а не к текущему закрытому Macro 2.

M2-R1 от 2026-09-23 принят владельцем как исследовательское свидетельство
(подтверждено заданием M2-R2); это не принятие production-методов.
M2-R2: по ограниченному разрешению владельца реализован research-only harness,
подготовлены controlled corpus и
[калибровочный отчёт](research/2026-09-23-jpeg-dq-grid-calibration.md) для owner review.
На завершение M2-R2 DQ/Grid сохраняли `RESEARCH_ONLY_NOT_READY`; оба калибровочных вывода —
`CALIBRATION_NOT_READY`, production thresholds не предложены. Следующая
предпосылка — независимый real corpus с правами/provenance и закрытие
calibration/profile/semantics gates из `METHODS.md`; operating target выбран ниже.
M2-R2 не снимает блокировку M2-A и не означает приёмку Stage 12 / Macro 2.

M2-R3A от 2026-09-24: [дизайн реального корпуса и operating point](research/2026-09-24-jpeg-real-corpus-operating-point-design.md)
принят владельцем согласно заданию M2-R3B; provenance/права datasets записаны в `REFERENCES.md`.
Рекомендована стратегия C: контролируемые JPEG из CC0/собственных RAW и отдельная
VISION workflow-проверка. В owner decision remediation выбран **BALANCED TRIAGE**,
target image-level FPR **≤1%** — цель калибровки, не production threshold и не
вероятность манипуляции. 0,5% — необязательная более строгая будущая проверка;
0,1% для Stage 12 не требуется. 3000 core + 600 VISION — расширенный вариант,
не обязательный acquisition и не предпосылка R3B или M2-A; требования 2000
собственных RAW нет. Целевые размеры следующей фазы зафиксированы владельцем ниже.
M2-R3B — OWNER_ACCEPTED: владелец принял pilot evidence и research implementation.
120 CC0 RAW прошли
acquisition QA, 107 проявлены разрешённым внешним rawpy, 97 masters допущены;
237 controlled JPEG измерены. VISION: 50 selected families, 43 после QA,
43 measurable groups / 55 social JPEG; native support — 0/43.
Всего 140 measurable groups / 292 JPEG. [Отчёт пилота](research/2026-09-24-jpeg-real-corpus-pilot.md)
отражает первоначальный owner freeze размеров: 200 exploration/calibration, 100 validation,
500 untouched primary holdout, 100 VISION external stress и optional challenges 50
вне primary FPR denominator. 97 RAW пилота остаются только exploration/calibration;
43 VISION пилота — exploratory external stress, не новые validation/holdout evidence.
В M2-R3D владелец до открытия исходов заменил target 500 на максимальное число
пригодных независимых PIXLS CC0 групп после полной QA, без downsampling:
зафиксированы 320 групп. Acquisition composition и endpoint записаны до открытия.
На завершение R3B DQ pilot signal был достаточен для FINAL_CALIBRATION;
production acceptance и порога тогда не было.
Grid — WEAK_SIGNAL, `RESEARCH_ONLY_NOT_READY / DEFERRED`: направление не отвергнуто
навсегда, но исключено из текущего Stage 12 primary statistical holdout.
Primary endpoint — **DQ ONLY**, одно изображение на source group, target
image-level FPR ≤1%; PASS только при односторонней 95% exact Clopper–Pearson
upper `<=0.01` по фактическому applicable n. Это statistical acceptance rule,
не DQ measurement threshold. Правило и abstention semantics заморожены в R3C;
final coverage описывается без нового числового acceptance threshold.
Grid не использует этот holdout для второй независимой ≤1% claim без
отдельного multiplicity/statistical плана. Адаптивный добор после outcomes запрещён.
Native VISION support остаётся 0/43; production resource limits не ослабляются,
native samples не уменьшаются скрыто для изменения этого результата.
VISION остаётся отдельным external stress; source grouping и все derivatives
в одной partition сохраняются. Принятие production DQ оформлено в M2-R4;
Grid остаётся `DEFERRED_RESEARCH_ONLY`.

M2-R3C — **OWNER_ACCEPTED** согласно заданию M2-R3D.
[Отчёт финальной калибровки](research/2026-09-24-jpeg-dq-final-calibration.md):
200 calibration groups (97 pilot + 103 new), 100 новых validation groups;
research rule `DQ-R3C-1` выбран только на calibration и заморожен до validation.
Validation primary: 0/98 FP, FPR 0%, one-sided 95% upper 3,0106%, abstention 2%.
Aligned40to90: 65/99 applicable detected, 65/100 unconditional; обратная,
same-DQT и close-quality истории — 0 detections. Исследовательский вывод —
`READY_FOR_FINAL_HOLDOUT`, без утверждения доказанного ≤1% FPR или production
acceptance. На момент R3C holdout не открывался.

M2-R3D — **OWNER_ACCEPTED** согласно заданию M2-R4.
[Отчёт финального holdout](research/2026-09-24-jpeg-dq-final-holdout.md):
все 320 пригодных независимых групп заморожены до первого DQ outcome;
308 applicable, 12 abstentions, 0 admission failures, 0 FP;
exact one-sided 95% upper **0,9679255009% ≤1%**, `FINAL_HOLDOUT_PASS`.
Applicability 96,25% против 98% в R3C; coverage остаётся описательным
свидетельством без нового post-hoc acceptance threshold.
Правило и hashes сохранены, adaptive supplementation отсутствует.
Focused suite 163 PASS. Повтор полного barrier после staging выполнен
владельцем: **2686 passed, 17 skipped**, **CLI smoke PASS**, `git status` clean;
R3D committed SHA — `7216fdc037e7e85fee6557cdd71bb5902c4cf2fd`.
Verification — **DONE** по свидетельству владельца в closure M2-R4;
это не strict certification и не новый запуск проверок агентом.

M2-R4 — **OWNER_ACCEPTED**, решение от **2026-09-24**. Полная спецификация
[DQ-HIST-1 / DQ-R3C-1](METHODS.md#dq-hist-1--гистограммное-измерение-dct)
получила `ACCEPTED`, DQ-G1–G4 — `CLOSED`. Разрешена реализация точного
документированного DQ scope без изменения правила, semantics и ограничений.
M2-A — `DONE / OWNER ACCEPTED / PRODUCTION IMPLEMENTED`: приёмка реализации
явно подтверждена владельцем в задании M2-BR1. Это не новая strict certification.
Grid остаётся `DEFERRED_RESEARCH_ONLY`.

---

## 3. Карта этапов

| № | Этап | Статус | Главный результат |
|---:|---|---|---|
| 0 | Документационная база | DONE | Синхронизированные источники истины |
| 1 | Каркас проекта и конфигурация | DONE | Запускаемое приложение |
| 2 | Доменные модели и репозитории | DONE | Типизированные модели контрактов |
| 3 | Приём и первичная проверка файлов | DONE | Безопасно принятый или отклонённый файл |
| 4 | Жизненный цикл задачи, хранение и маршрутизация | DONE | Управляемая задача с очисткой |
| 5 | Предварительная обработка и каркас анализаторов | DONE | Единый запуск анализаторов |
| 6 | Базовые анализаторы и формирование признаков | DONE | Реальные нормализованные признаки |
| 7 | Полнота, риск и рекомендации | DONE | Объяснимый итог без псевдовероятности |
| 8 | JSON, API и WebUI | DONE | Реализация и независимые аудиты завершены; этап закрыт |
| 9 | Надёжность, безопасность и сквозные тесты | DONE | Macro 1–4 и remediation committed; independent post-remediation audit — PASS, findings закрыты |
| 10 | Сборка и демонстрация MVP | DONE / CLOSED | Macro 1–3 DONE / owner accepted; independent post-remediation audit — PASS; S10-A01–S10-A04 CLOSED |
| 11 | Post-MVP Normalization & Hardening | DONE / CLOSED | Macros 0–8 DONE / owner accepted; финальная проверка и strict certification — PASS; actionable findings 0 |
| 12 | Analyzer Expansion, Licensing & Product Validation | IN_PROGRESS | Macro 0 DONE / merged; Macros 1–2 DONE / CLOSED; M2-HR6 PASS / OWNER ACCEPTED; лицензия проекта Apache-2.0 |
| 13+ | Дальнейшие расширения | AFTER_MVP / NOT_STARTED | ML, интеграции, история, масштабирование; отдельное решение владельца |

---

# Этап 0. Документационная база — DONE

## Цель

Создать минимальный согласованный комплект проектной памяти без повторного пересказа одной информации в нескольких файлах.

## Выполнено

- [x] `PROJECT.md` назначен владельцем архитектуры, границ и стека;
- [x] `CONTRACTS.md` назначен владельцем интерфейсов и моделей данных;
- [x] `ROADMAP.md` назначен владельцем плана и текущего состояния;
- [x] `CHANGELOG.md` назначен владельцем истории изменений;
- [x] старые MD-файлы признаны архивными;
- [x] разграничены области ответственности источников истины;
- [x] сформированы правила работы ИИ-агента.

## Критерий завершения

Комплект можно передать новому агенту без загрузки старой курсовой и архивных файлов.

---

# Этап 1. Каркас проекта и конфигурация — DONE

Дата завершения: **2026-08-01**.

## Цель

Создать минимальное Python-приложение, которое воспроизводимо устанавливается, запускается и проверяет конфигурацию.

## Обязательные задачи

### Структура проекта

- [x] создать Git-репозиторий;
- [x] добавить `.gitignore` для `.venv`, `.env`, `runtime`, моделей и кэшей;
- [x] зафиксировать Python 3.12 в `.python-version`;
- [x] инициализировать проект через `uv`;
- [x] создать `pyproject.toml` и `uv.lock`;
- [x] создать пакет приложения;
- [x] создать каталоги `src`, `tests`;
- [x] создать каталог `config` для примера конфигурации;
- [x] обеспечить автоматическое создание необходимых каталогов `runtime` при запуске приложения;
- [x] не хранить содержимое `runtime` в Git.

### Инструменты качества

- [x] подключить Ruff;
- [x] подключить mypy;
- [x] подключить pytest;
- [x] подключить pytest-cov;
- [x] подключить pre-commit после появления базовых команд;
- [x] добавить единые команды запуска проверок.

### Конфигурация

- [x] реализовать Pydantic-модели корневой конфигурации;
- [x] запретить неизвестные поля;
- [x] загрузить YAML;
- [x] объединить YAML с переменными окружения;
- [x] проверить обязательные секции;
- [x] реализовать безопасную ошибку некорректной конфигурации;
- [x] создать канонический `config.example.yaml` текущей схемы; настройки будущих модулей явно обозначить как неактивные или `EXAMPLE`;
- [x] не включать секреты в пример;
- [x] подключить загрузку и валидацию конфигурации к точке запуска приложения.

### Запуск

- [x] создать фабрику приложения FastAPI;
- [x] создать Uvicorn-команду запуска;
- [x] добавить служебный health endpoint без бизнес-логики;
- [x] добавить стартовое журналирование без секретов;
- [x] устранить BLOCKER небезопасной инициализации логирования: валидировать
  стандартные уровни до runtime и безопасно завершать CLI при ошибке открытия
  собственного log handler;
- [x] реализовать ротацию JSONL-логов.

## Обязательные тесты

- [x] корректная конфигурация загружается;
- [x] неизвестное поле отклоняется;
- [x] отсутствующий обязательный параметр отклоняется;
- [x] настройка может быть переопределена переменной окружения;
- [x] пример конфигурации не содержит буквальных значений секретов; используются только имена переменных окружения, а локальные secret/config-файлы исключены из Git.
- [x] приложение создаётся в тесте;
- [x] health endpoint возвращает успешный ответ;
- [x] Ruff и mypy проходят на каркасе.

## Findings финального аудита

Статус финального аудита: **COMPLETED**. Все первоначальные findings закрыты.

- [x] устранить несоответствие по `pydantic-settings`: владелец явно утвердил
  PyYAML + Pydantic v2 `BaseModel` + собственный env-overlay для MVP,
  документация синхронизирована с фактической реализацией;
- [x] исправить критерий запуска через официальный console script
  `uv run fakedetector --config config/config.example.yaml` и добавить целевую
  проверку `uv run poe server-smoke` с ограниченным запуском настоящего сервера;
- [x] синхронизировать naming startup events: `application_starting` является
  официальным событием непосредственно перед `uvicorn.run()` и не означает
  HTTP readiness, которая проверяется отдельно через `/health`;
- [x] добавить недостающие regression-тесты findings аудита: pytest запускает
  установленный `fakedetector --help` без runtime pipeline и параметризованно
  проверяет отсутствие каждого обязательного top-level поля `AppConfig`;
- [x] добавить validation для `token_env_var` как ASCII environment identifier
  по шаблону `^[A-Z_][A-Z0-9_]*$`.

### Повторный финальный аудит

Первоначальный результат повторного аудита: **BLOCKER: 0; MAJOR: 1; MINOR: 0**.
Все предыдущие findings были закрыты. Единственный новый finding: публичный
`README.md` был рассинхронизирован с реализацией и ошибочно описывал проект как
находящийся только на стадии проектирования, несмотря на готовый минимальный
запускаемый каркас.

- [x] устранить finding синхронизацией `README.md` с фактическим состоянием
  минимального запускаемого каркаса Этапа 1.

Статус повторного финального аудита: **COMPLETED / PASS**.

Итоговый результат: **BLOCKER: 0; MAJOR: 0; MINOR: 0**. Все первоначальные
findings и новый finding по `README.md` закрыты. Контрольная проверка после
синхронизации README прошла: полный quality pipeline и real-server smoke
завершились успешно, официальный CLI подтверждён, 106 тестов прошли, итоговое
branch coverage — 97%. Рабочее дерево Git после проверки осталось чистым.

## Критерий завершения

```text
uv sync
uv run pytest
uv run ruff check .
uv run mypy src
uv run fakedetector --config config/config.example.yaml
uv run poe server-smoke
```

выполняются без критических ошибок, приложение запускается и валидирует конфигурацию.

Критерий завершения выполнен и подтверждён 2026-08-01.

## Не делать на этом этапе

- анализ файлов;
- ML-модели;
- базу данных;
- внешний брокер задач;
- полноценную аутентификацию;
- сложный WebUI.

---

# Этап 2. Доменные модели и репозитории — DONE

Дата завершения: **2026-08-12**.

## Цель

Перенести канонические контракты в типизированный код до реализации потоков обработки.

## Обязательные задачи

### Доменные модели

- [x] реализовать enum из `CONTRACTS.md`;
- [x] реализовать `SourceContext`;
- [x] реализовать файловые дескрипторы;
  - [x] реализовать `InputFileDescriptor`;
  - [x] реализовать `ValidatedFileDescriptor` с техническими параметрами;
- [x] реализовать `ValidationResult`;
- [x] реализовать `AnalyzerResult`;
- [x] реализовать `Finding` и виды локализации;
- [x] реализовать `AnalysisCompleteness`;
- [x] реализовать `RiskAssessment`;
- [x] реализовать `Recommendation`;
- [x] реализовать `CleanupResult`;
- [x] реализовать итоговый `AnalysisResult`;
- [x] реализовать `AnalysisResultSummary`;
- [x] зафиксировать `schema_version`.

### Репозитории

- [x] определить протокол `ResultRepository`;
  - [x] определить типизированные операции `save`, `get`, `exists`;
  - [x] определить `list_recent` после фиксации полей `AnalysisResultSummary` и
    контрактного признака сортировки;
- [x] реализовать `JsonFileResultRepository`;
  - [x] реализовать файловый core для `save`, `get`, `exists`;
  - [x] реализовать `list_recent` после устранения контрактной неоднозначности;
- [x] реализовать атомарную запись;
- [x] реализовать безопасное чтение;
- [x] обработать повреждённый JSON;
- [x] в текущем production-коде сохранение `AnalysisResult` выполняется только
  через `ResultRepository`; обходные механизмы прямой записи отсутствуют.
  Соблюдение границы будущими модулями контролируется архитектурными тестами и
  code review на последующих этапах.

### Идентификаторы и время

- [x] реализовать генератор непрозрачного `analysis_id`;
- [x] реализовать единый UTC clock provider для тестируемости;
- [x] исключить персональные данные из идентификатора.

## Обязательные тесты

- [x] сериализация/десериализация каждой модели;
- [x] неверные enum отклоняются;
- [x] некорректная локализация отклоняется;
- [x] probability без метода отклоняется;
- [x] critical override без finding IDs отклоняется;
- [x] правила терминальных статусов проверяются;
- [x] результат записывается атомарно;
- [x] путь строится только по `analysis_id`.

## Findings финального аудита

- первоначальный аудит: **FAIL**;
- [x] `S2-AUD-001` — закрыт;
- [x] `S2-AUD-002` — закрыт;
- [x] `S2-AUD-003` — закрыт;
- [x] `S2-AUD-004` — закрыт;
- [x] `S2-AUD-005` — закрыт;
- repeat audit после первого remediation: **FAIL**;
- [x] `S2-AUD-001-R1` — закрыт;
- [x] `S2-AUD-003-R1` — закрыт;
- контрольный финальный аудит: **PASS**;
- итог: **BLOCKER: 0; MAJOR: 0; MINOR: 0**.

Real-symlink integration test остаётся platform-dependent skip; deterministic
tests для `get`, `exists` и `list_recent` проходят. Hardening против concurrent
symlink substitution / TOCTOU и no-follow остаётся задачей безопасности Этапа 9.

## Критерий завершения

Все доменные модели и репозиторий существуют в коде, имеют контрактные тесты и не зависят от FastAPI.

Критерий завершения выполнен и подтверждён контрольным финальным аудитом
2026-08-12.

## Не делать на этом этапе

- реальные анализаторы;
- расчёт риска;
- HTTP-маршруты анализа;
- история и SQLite.

---

# Этап 3. Безопасный приём, временное владение и первичная проверка файлов — DONE

## Цель

Реализовать законченный safe intake use case: принять недоверенный поток в
изолированный workspace, подтвердить поддерживаемый тип и безопасную читаемость,
а затем передать accepted input следующему lifecycle вместе с контролируемым
ownership либо завершить `rejected`/`failed` с фактическим cleanup.

## Обязательные задачи

### Increment 1 — Controlled intake and temporary ownership — DONE

- [x] определить прикладной сервис приёма файла;
- [x] определить adapter-neutral потоковый вход, общий для будущих WebUI и API;
- [x] создать `analysis_id` и `SourceContext`;
- [x] зафиксировать registration/received time;
- [x] создать изолированный `runtime/temp/<analysis_id>` для исходного input;
- [x] применить минимальную безопасную политику создания/доступа к каталогу без
  преждевременного Stage 9 TOCTOU/no-follow hardening;
- [x] использовать в системном пути и workspace только проверенный системный
  `analysis_id`;
- [x] создать внутреннее имя input без `original_name`, extension, MIME и
  external identifiers;
- [x] потоково читать и записывать input порциями без полной загрузки в память;
- [x] до определения `MediaType` применять hard limit, равный максимальному из
  настроенных per-media limits;
- [x] измерять фактический размер независимо от `Content-Length`;
- [x] рассчитывать SHA-256 в том же intake pass;
- [x] предоставить validator непрозрачный controlled-source handle;
- [x] определить минимальную ownership-семантику без универсального storage
  framework и без полного `AnalysisContext`;
- [x] очищать принадлежащий Stage 3 input/workspace при системном исключении до
  handoff.

После инкремента FakeDetector принимает недоверенный поток, ограничивает его
объём, безопасно размещает в isolated workspace, измеряет размер, рассчитывает
SHA-256 и удаляет данные при системном сбое до handoff.

### Increment 2 — Primary validation — DONE

- [x] проверка пустого файла;
- [x] обязательное наличие расширения с семантикой `file`/`file.`/`.mp4` →
  `missing_extension`;
- [x] нормализация обычного расширения без ведущей точки в lowercase;
- [x] проверка extension по утверждённому MVP allowlist;
- [x] принять отсутствие declared MIME без rejection;
- [x] определить фактический MIME независимо от declared MIME;
- [x] проверить обнаруженный MIME по MVP allowlist;
- [x] проверка фактической сигнатуры;
- [x] проверка согласованности extension, detected MIME, сигнатуры/контейнера и
  `MediaType` по нормативной матрице;
- [x] проверка согласованности declared и detected MIME только при наличии
  declared MIME;
- [x] после определения `MediaType` применить соответствующий per-media limit к
  фактически измеренному размеру;
- [x] полностью безопасно декодировать image;
- [x] controlled probe/open и bounded decode audio/video выполнять с timeout;
- [x] получить обязательные технические параметры без вымышленных значений;
- [x] не отклонять файл только из-за отсутствия естественно необязательных
  metadata или nullable технических параметров;
- [x] определение `MediaType`;
- [x] формирование `ValidationResult`.

После инкремента FakeDetector определяет, является ли вход поддерживаемым и
безопасно читаемым image/audio/video, и формирует `ValidatedFileDescriptor` либо
нормативный validation rejection.

### Increment 3 — Integrated Stage 3 lifecycle — DONE

- [x] WebUI/API adapters передают transport data одному intake service и не
  владеют validation business logic;
- [x] при accepted логически передавать `ValidatedFileDescriptor` вместе с
  opaque owned-source/lease/controlled handle;
- [x] после успешного handoff передавать ownership Stage 4 и не удалять accepted
  input в Stage 3;
- [x] если handoff не состоялся, сохранять ownership в Stage 3 и выполнять
  cleanup;
- [x] ожидаемые validation failures завершать как `rejected` со стабильным
  машинным кодом;
- [x] ошибки workspace, записи и неожиданные системные исключения завершать как
  `failed`, не маскируя их как invalid input;
- [x] при `rejected` не запускать анализаторы, не создавать findings и
  `RiskLevel`, сохранять completeness=`not_assessed`;
- [x] при `rejected` и `failed` до handoff выполнять cleanup и отражать его
  фактический outcome;
- [x] возвращать безопасные сообщения без внутренних путей;
- [x] не создавать preprocessing-артефакты Stage 5.

После инкремента FakeDetector выполняет весь Stage 3 от входного потока до
accepted ownership handoff либо controlled `rejected`/`failed` outcome с
cleanup.

## Обязательные тесты

- [x] все форматы утверждённого image/audio/video MVP allowlist проходят при
  согласованной сигнатуре и safe read;
- [x] отсутствие declared Content-Type допустимо;
- [x] отсутствие необязательных metadata допустимо;
- [x] `file`, `file.` и `.mp4` отклоняются с `missing_extension`;
- [x] расширение нормализуется в lowercase;
- [x] архив отклоняется;
- [x] офисный документ отклоняется;
- [x] переименованный файл с неверной сигнатурой отклоняется;
- [x] declared MIME mismatch отклоняется, а отсутствующий declared MIME не
  мешает проверке;
- [x] превышение pre-detection hard limit прекращает intake;
- [x] превышение per-media limit после определения типа отклоняется;
- [x] недоверенный `Content-Length` не определяет фактический размер;
- [x] повреждённый файл отклоняется;
- [x] image проходит полный decode, audio/video — controlled probe и bounded
  decode с timeout;
- [x] SHA-256 стабилен;
- [x] разные `analysis_id` получают изолированные каталоги;
- [x] path traversal и `original_name` не влияют на путь или внутреннее имя
  input;
- [x] rejection и exception до handoff очищают input/workspace;
- [x] cleanup failure отражается фактически;
- [x] accepted handoff передаёт ownership и не удаляется Stage 3;
- [x] несостоявшийся handoff сохраняет ownership и запускает cleanup;
- [x] отклонение не создаёт analyzers, findings или риск `low`/`high`;
- [x] internal intake failure формирует `failed`, а validation failure —
  `rejected`.

## Критерий завершения

Stage 3 возвращает либо accepted handoff с `ValidatedFileDescriptor` и
контролируемым владением исходным временным файлом, либо terminal
`rejected`/`failed` с фактическим результатом cleanup; анализаторы не запускаются.

## Финальный аудит Stage 3

Статус финального независимого аудита: **PASS**.

- [x] `S3-AUD-001`: канонические relational invariants `ValidationResult`
  независимо перепроверены, включая четыре противоречивые комбинации;
- [x] `S3-AUD-002`: structural Matroska/WebM classification независимо
  перепроверена на реальных MKV/WebM и malformed/contaminated EBML;
- [x] `S3-AUD-003`: controlled `cwd`, `shell=False` и `stdin=DEVNULL` для всех
  FFmpeg/ffprobe runtime и validation вызовов независимо перепроверены;
- [x] `S3-RERUN-001`: разрешённые и запрещённые relational states
  `Stage3Terminal` независимо воспроизведены;
- [x] `S3-RERUN-002`: ffprobe output overflow и stdout infrastructure failure
  независимо разделены и проверены вместе с kill/reap/close/join и integrated
  terminal `failed` outcome.

Все completion criteria Stage 3 и полный quality barrier прошли. Stage 3 закрыт
со статусом `DONE`. Принятые Stage 4 contracts не меняют фактически завершённый
Stage 3 lifecycle.

---

# Этап 4. Жизненный цикл задачи, хранение и маршрутизация — DONE

## Цель

Принять ownership успешно проверенного controlled source и создать управляемую
задачу дальнейшего анализа с внутренней очередью, маршрутизацией, состояниями и
полной post-handoff очисткой.

## Обязательные задачи

### Documentation prerequisite — Lifecycle and cleanup contract — DONE

Ветка: `docs/stage4-lifecycle-cleanup-contract`.

- [x] зафиксировать receiver/handoff commit и rollback provisional state;
- [x] уточнить canonical `MediaType` routing и internal missing-binding failure;
- [x] определить in-process `TaskRegistry`, `AnalysisContext` и internal
  `AnalysisTask` boundary;
- [x] отделить Stage 4 task state от `AnalysisResult` и `ResultRepository` Stage 8;
- [x] принять Option A cleanup retry/TTL/quarantine policy и active-task exclusion;
- [x] определить deterministic sweep triggers и conservative entry handling;
- [x] декомпозировать Stage 4 на три functional increments и отдельный final audit.

Документальная prerequisite не является functional increment: production code,
tests, config, dependencies, external schema `1.0`, Stage 2 models/enums и Stage 3
contract shape/redesign не изменены.

### Stage 4 Increment 1 — Managed accepted task lifecycle — DONE

Ветка: `feat/stage4-managed-task-lifecycle`.

Functional vertical slice:

```text
Stage3Accepted
→ AnalysisContext / AnalysisTask
→ state machine
→ local registry
→ canonical router
→ deterministic FIFO queue/run_next
→ test executor
→ immediate post-handoff cleanup
→ terminal task snapshot
```

- [x] подтвердить identity и factual fields `Stage3Accepted`;
- [x] создать `AnalysisContext` и internal `AnalysisTask` без ownership capability;
- [x] реализовать допустимые state transitions и запрет terminal requeue/restart;
- [x] реализовать authoritative local typed in-process `TaskRegistry`;
- [x] реализовать canonical routes `IMAGE`, `AUDIO`, `VIDEO` и safe
  internal/infrastructure failure при отсутствующем binding;
- [x] реализовать deterministic FIFO enqueue и явный `run_next`;
- [x] фиксировать `queued_at` только после successful enqueue;
- [x] выполнить logical receiver commit только после registry reservation, route
  resolution и successful enqueue, откатывая provisional state при исключении;
- [x] выполнить test executor и immediate post-handoff cleanup;
- [x] вернуть factual terminal task snapshot без `AnalysisResult` и
  `ResultRepository.save()`.

Исключено из Increment 1: concurrency workers, queue pressure, retries, TTL,
quarantine, preprocessing, analyzers и persistence `AnalysisResult`.

### Stage 4 Increment 2 — Bounded local execution lifecycle — DONE

Ветка: `feat/stage4-bounded-local-execution`.

- [x] реализовать bounded per-media queues;
- [x] реализовать workers и настроенные per-media concurrency limits;
- [x] обеспечить exactly-once claim;
- [x] определить и проверить overflow behavior;
- [x] реализовать start/stop/drain и safe shutdown;
- [x] корректно обработать pending/running accepted tasks при shutdown;
- [x] изолировать caller/event loop от тяжёлого выполнения.

### Stage 4 Increment 3 — Cleanup recovery — DONE

Ветка: `feat/stage4-cleanup-recovery`.

- [x] реализовать initial cleanup и configured immediate retries;
- [x] фиксировать factual partial/failed cleanup без изменения primary status;
- [x] реализовать optional quarantine после retry exhaustion;
- [x] реализовать workspace TTL с обязательным исключением active/non-terminal
  `TaskRegistry` entries;
- [x] реализовать quarantine TTL и повторные cleanup attempts без durable metadata;
- [x] интегрировать sweep при scheduler startup, после terminal task cleanup и при
  graceful shutdown;
- [x] не оставлять abandoned ordinary workspace и не заявлять ложный cleanup
  success для symlink/suspicious/unknown entries.

### Stage 4 final audit remediation — DONE

- [x] `S4-AUD-001` independently verified closed: factual ownership state
  quarantined `AcceptedSource` синхронизирован с direct cleanup и janitor TTL
  recovery;
- [x] `S4-RERUN-001`: исключить stranded active task при сбое terminal
  `Clock.now()` после physical cleanup;
- [x] `S4-RERUN2-001`: сохранить strict UTC/chronology validation и pre-mutation
  defense-in-depth для authoritative lifecycle timestamps;
- [x] `S4-RERUN3-001`: реализовать shared `AuthoritativeLifecycleClock`, explicit
  internal `TerminalSettlement`, post-cleanup `finished_at` и recovery
  `FACT_READY` без повторного physical cleanup; локально проверено полным quality
  barrier: 989 passed, 2 skipped, coverage 91%;
- [x] `S4-RERUN4-001`: вынести janitor/filesystem callbacks из global
  `TaskRegistry` lock, сохранив atomic cleanup claim, same-analysis registration
  exclusion, exactly-one cleanup owner и exception-safe retry; локально проверено
  полным quality barrier: 994 passed, 2 skipped, coverage 91%;
- [x] independent final audit rerun5 завершён со статусом `PASS`: все historical
  findings независимо подтверждены как `CLOSED`, новых production defects и
  post-architecture findings не обнаружено; 994 passed, 2 skipped, coverage 91%,
  quality barrier полностью green, repository integrity confirmed.

## Обязательные тесты

- [x] валидные переходы статусов;
- [x] недопустимые переходы отклоняются;
- [x] ownership accepted input принимается ровно один раз;
- [x] enqueue failure откатывает provisional registry state и не подтверждает handoff;
- [x] missing canonical route binding приводит к receiver exception и Stage 3 cleanup, а не `rejected`;
- [x] `queued_at` отсутствует до successful enqueue;
- [x] cleanup accepted input и будущих артефактов выполняется после успеха;
- [x] post-handoff cleanup выполняется после исключения;
- [x] ошибка удаления отражается;
- [x] retry/quarantine/TTL policy применяется только при сбое cleanup;
- [x] active/non-terminal task исключается из TTL cleanup независимо от mtime;
- [x] sweep triggers и quarantine TTL/retry детерминированы;
- [x] ограничения параллельности соблюдаются;
- [x] Stage 4 не создаёт `AnalysisResult` и не вызывает `ResultRepository.save()`.

## Критерий завершения

Тестовая задача принимает ownership проверенного source, проходит регистрацию
дальнейшего lifecycle, очередь, маршрутизацию и post-handoff очистку, а её
живое состояние правдиво доступно через in-process `TaskRegistry`. Cleanup
recovery не очищает live tasks, не оставляет ordinary abandoned workspace и не
выдаёт quarantine за persistent repository. Durable restart recovery и
`AnalysisResult` persistence не входят в Stage 4.

## Финальный аудит Stage 4

Все три functional increments и completion criteria Stage 4 подтверждены
independent final audit rerun5 со статусом `PASS`. Findings `S4-AUD-001`,
`S4-RERUN-001`, `S4-RERUN2-001`, `S4-RERUN3-001` и `S4-RERUN4-001` независимо
подтверждены как `CLOSED`; новых production defects и post-architecture findings
не обнаружено. Финальный quality barrier полностью green: 994 passed, 2 skipped,
coverage 91%; repository integrity confirmed. Stage 4 имеет статус `DONE`.
Следующее действие — подготовка и начало Stage 5 согласно ROADMAP; Stage 5 ещё
не начат.

---

# Этап 5. Предварительная обработка и каркас анализаторов — DONE

## Цель

Создать расширяемый механизм подготовки image/audio/video и единый контракт выполнения анализаторов.

## Архитектурная prerequisite

```text
Stage 5 architecture PLAN: ACCEPTED WITH OWNER CLARIFICATIONS
Implementation status: DONE
```

Архитектурная prerequisite подготовлена и зафиксирована документацией.

Принятые owner clarifications нормативно закреплены в `PROJECT.md` и
`CONTRACTS.md`: generic analyzer timeout реализуется spawned child process per
invocation; opaque parent capabilities преобразуются в private picklable
`WorkerRequest`; normal `TIMEOUT` публикуется только после confirmed stop/reap,
а unreapable worker является fatal infrastructure failure; общий
`limits.processing_timeout_seconds` начинается как monotonic budget на входе
`Stage5ExecutionService.execute(task)` без добавления нового Stage 4 claim
timestamp.

## Implementation decomposition

Текущие статусы increments:

1. **Increment 1 — DONE:** internal models + source/artifact capability boundary.
2. **Increment 2 — DONE:** bounded subprocess primitive + Stage 3 parity migration.
3. **Increment 3 — DONE:** image/audio/video preprocessing.
4. **Increment 4 — DONE:** analyzer registry/orchestration + hard process timeout.
5. **Increment 5 — DONE:** integrated Stage 4 → Stage 5 lifecycle.
6. **Исправления по итогам финального аудита Stage 5 — DONE:** R1–R6 = DONE;
   focused closure audit = PASS.

Increment 2 выделил private shared process boundary с hard-bounded stdout,
discard-режимом, explicit cwd, `shell=False`, disabled stdin, timeout и
подтверждённым terminate/kill/reap. `FFmpegMediaInspector` мигрирован без
изменения Stage 3 argument construction и rejected/failed semantics.

Increment 3 добавил внутренний детерминированный dispatcher и реализации
предобработки для image/audio/video. Все создаваемые файлы резервируются в
`WorkspaceArtifactRegistry` до физического создания; `PreparedMedia` содержит
только непрозрачные ссылки и ограниченные неизменяемые метаданные. Для image
создаётся PNG первого отображаемого кадра с применённой EXIF orientation, для
audio — PCM s16le WAV, фактические фрагменты и спектрограмма по требованию, для
video — ограниченный набор периодических PNG-кадров и FLAC-аудиодорожка по
требованию.

Increment 4 добавил внутренний analyzer contract, закрытый worker-resolvable
registry с analyzer-specific typed settings validation и последовательный
orchestrator в точном порядке per-media `enabled`. Каждый фактически запущенный
analyzer выполняется в отдельном explicit-spawn worker; private bounded transport
не переносит parent capabilities или media bytes. Analyzer exception и
serialization failure дают безопасный canonical `ERROR`, а canonical `TIMEOUT`
возникает только после подтверждённого terminate/kill/reap; unreapable worker
остаётся fatal infrastructure failure. Framework подтверждён только internal fake
analyzers без score, findings и default-config activation.

Increment 5 добавил внутренний `Stage5ExecutionService`, совместимый с прежним
`TaskExecutor.execute(task)`, и связал production path Stage 3/4 с preprocessing,
авторитетным `Stage5TaskData`, переходом `PREPROCESSING → ANALYSIS` и
последовательным analyzer orchestration. Требования к demand-driven артефактам
вычисляются только по активному analyzer plan; единый monotonic deadline от входа
в executor ограничивает preprocessing и каждый analyzer. Отдельные
`ERROR`/`TIMEOUT` сохраняются как `AnalyzerResult`, фатальная инфраструктурная
ошибка и общий timeout завершают execution как `FAILED`, а terminal settlement,
cleanup и release остаются исключительной ответственностью Stage 4. Полный quality barrier: 1143
passed, 2 skipped, coverage 90%.

Функциональная реализация Stage 5 и исправления по результатам финального аудита
завершены. R1
закрывает `S5-AUD-001` и `S5-AUD-002`; R2 закрывает `S5-AUD-003`,
`S5-AUD-004`, `S5-AUD-005`, `S5-AUD-006` и `S5-AUD-011`; R3 закрывает
`S5-AUD-007`, `S5-AUD-008` и `S5-AUD-010`; R4 закрывает `S5-AUD-009` и
`S5-AUD-012`. R5 устраняет оставшийся путь прерывания `S5-AUD-001`,
воспроизведённый повторным аудитом. R6 закрыл замечания аудита изображений.
Полная проверка R4: 1236 passed,
2 skipped, coverage 90% (89,69% при точности до сотых); целевая проверка:
217 passed. Ruff, проверка форматирования затронутых Python-файлов, mypy,
`poe check`, pre-commit, CLI smoke и `git diff --check` прошли.

Целевая проверка R5: worker/process/lifecycle/R1/R2 — 337 passed, 1 skipped
(создание symlink недоступно в среде); дополнительные проверки preprocessing
по resource/budget/timeout/termination — 6 passed, 30 deselected. Добавлены
72 проверки прерываний с реальными дочерними процессами, включая ограниченный reap,
сохранение барьера и однократную очистку при восстановлении. Ruff, проверка
форматирования восьми затронутых Python-файлов, `mypy src` и `git diff --check` прошли.
Полный pytest/poe barrier в R5 не запускался; полный набор проверок остаётся после R6.

## Исправления по итогам финального аудита

- [x] R1 — безопасность процессов и владения: неподтверждённое завершение
  процесса блокирует физическую очистку и `FINISHED`; ошибки ввода-вывода
  контролируемого входа отделены от ошибок анализатора;
- [x] R2 — согласованные ограничения ресурсов и транспорта, а также единый
  идентификатор снимка конфигурации;
- [x] R3 — резервирование артефактов с учётом псевдонимов путей Windows, очистка исходных
  EXIF/XMP/ICC из нормализованного PNG и обязательность нормализации в конфигурации;
- [x] R4 — публикация оставшихся включённых анализаторов как `SKIPPED` по политике
  остановки и неизменяемое авторитетное хранение результатов с отделённым чтением
  через реестр; единый сериализатор и предел R2 сохранены;
- [x] R5 — прерывание после запуска рабочего или дочернего процесса проходит
  ограниченную последовательность stop/reap; исходное прерывание сохраняется, неподтверждённая безопасность
  передаётся через существующий R1 barrier и блокирует cleanup/release/FINISHED;
- [x] R6 — оставшиеся замечания аудита изображений (APNG и tRNS): отдельный
  default image не подменяет первый APNG animation frame, а RGB/grayscale/palette
  `tRNS` материализуется в alpha до очистки raw metadata;
- [x] повторный независимый финальный аудит (focused closure audit): `PASS`;
  `S5-AUD-001`, `S5-RERUN-001` и `S5-RERUN-002` — `CLOSED`, 146 targeted
  passed, новых findings нет.

## Финальное закрытие

- **Final verification:** `PASS` — 1313 passed, 2 skipped, coverage 89.76%,
  branch coverage enabled; Ruff, mypy, `poe check`, pre-commit и CLI — `PASS`.
- **Focused closure audit:** `PASS` — `S5-AUD-001`, `S5-RERUN-001` и
  `S5-RERUN-002` имеют статус `CLOSED`; 146 targeted passed; новых findings нет.
- **Architecture Truth Review:** `CLOSE_STAGE5_UNCHANGED`. Перед Stage 6 новых
  архитектурных решений не требуется.
- **Future/post-v1.0 candidates:** deprecate/remove
  `analyzers.defaults.continue_on_error`; deprecate/remove
  `image.normalize_for_analysis`; возможное переименование
  `keyframe_interval_seconds` при будущей schema revision; отдельный generated
  artifact budget, chunked result transport и restart recovery — только при
  измеренной потребности.

## Обязательные задачи

### Предварительная обработка изображения

- [x] переиспользовать проверенный source и безопасно открыть изображение для
  подготовки аналитических представлений;
- [x] переиспользовать либо дополнить подтверждённые технические параметры;
- [x] извлечь доступные метаданные;
- [x] создать нормализованную рабочую копию;
- [x] зарегистрировать промежуточный артефакт.

### Предварительная обработка аудио

- [x] декодировать проверенный source в объёме, необходимом для подготовки;
- [x] переиспользовать либо дополнить подтверждённые параметры;
- [x] создать canonical signed 16-bit PCM WAV fragments без resample/downmix;
- [x] разделить на фрагменты по конфигурации;
- [x] построить спектрограмму только при необходимости;
- [x] зарегистрировать артефакты.

### Предварительная обработка видео

- [x] переиспользовать проверенный source и при необходимости дополнить параметры
  через FFmpeg/ffprobe безопасным вызовом;
- [x] не загружать всё видео в память;
- [x] извлечь periodic sampled representative frames/сегменты;
- [x] извлечь аудиодорожку при наличии;
- [x] зарегистрировать артефакты;
- [x] ограничить время внешних процессов.

### Каркас анализаторов

- [x] реализовать протокол `Analyzer`;
- [x] реализовать registry;
- [x] включать анализаторы конфигурацией;
- [x] проверять применимость;
- [x] реализовать timeout;
- [x] изолировать ошибку отдельного анализатора;
- [x] реализовать тестовый анализатор для каждого маршрута или общий fake analyzer;
- [x] собирать `AnalyzerResult`.

## Обязательные тесты

- [x] подготовка валидного изображения;
- [x] подготовка валидного аудио;
- [x] подготовка валидного видео;
- [x] повреждённые данные дают контролируемую ошибку;
- [x] внешний процесс вызывается без shell-инъекции;
- [x] disabled analyzer не запускается;
- [x] not applicable отражается корректно;
- [x] error одного анализатора не останавливает остальные;
- [x] timeout отражается;
- [x] артефакты попадают в очистку.

## Критерий завершения

Система может подготовить каждый тип медиа, запустить набор тестовых анализаторов и получить массив контрактных `AnalyzerResult`.

## Решение до этапа 6

Необходимо выбрать минимальный набор **реальных** MVP analyzers, их версии,
applicability, fixtures и analyzer-specific semantics для `raw_metrics` /
`candidate_findings`.

---

# Этап 6. Базовые анализаторы и формирование признаков — DONE

## Цель

Подключить ограниченный, реально проверяемый набор анализаторов и преобразовать их результаты в нормализованные признаки.

## Ворота этапа

### Increment 0 — analyzer profile, provenance и documentation prerequisite — DONE

Owner утвердил Profile B и provenance policy. До production implementation
зафиксированы:

- четыре `analyzer_id` и их версии;
- Finding policy v1 и граница sibling Stage 6 task state;
- versioned deterministic MVP thresholds;
- dependency, hardware и fixture policies;
- обязательный канонический provenance registry `REFERENCES.md`.

Profile B:

| Analyzer | Version | Назначение |
|---|---|---|
| `image_metadata_consistency` | `1.0.0` | технический image analyzer |
| `audio_pcm_quality` | `1.0.0` | технический audio analyzer |
| `video_sampled_frame_quality` | `1.0.0` | технический video analyzer |
| `image_copy_move_correspondence` | `1.0.0` | content-oriented image analyzer |

Audio/video content analyzers сознательно не входят в MVP v1. ML analyzers,
model weights, PyTorch и CUDA не входят в Stage 6 MVP. Профиль остаётся CPU-only;
GPU не требуется.

### Finding policy v1

- все первоначальные findings имеют `severity=weak`;
- `score`, `score_name`, `source_score` и `score_impact` равны `null`;
- `critical_override_eligible=false`;
- AI probability и статистическая интерпретация heuristic thresholds запрещены;
- thresholds являются versioned deterministic MVP defaults;
- candidate findings преобразуются в `Finding` на Stage 6 с сохранением analyzer
  identity, version и связи с источником;
- нормализованные `Finding[]` хранятся в отдельном sibling Stage 6 task state;
  смысл `Stage5TaskData` не расширяется.

### Threshold policy

Для `audio_pcm_quality`:

```text
full_scale_sample_ratio threshold = 0.001
```

Для `image_copy_move_correspondence`:

```text
min_dimension_px = 128
max_pixels = 12_000_000
max_keypoints = 5_000
descriptor_ratio = 0.75
min_spatial_separation_px = max(32, 0.05 * min_dimension)
ransac_reprojection_threshold_px = 3
min_cluster_inliers = 12
min_cluster_inlier_ratio = 0.5
max_clusters = 4
```

Значения не являются статистически валидированными forensic thresholds. Это
воспроизводимые MVP defaults; их изменение в Stage 6 требует обоснования
deterministic positive/negative/challenge fixtures и отдельной фиксации.

### Dependency, hardware и fixture policies

- planned pins для `image_copy_move_correspondence`:
  `opencv-python-headless==4.14.0.94` и `numpy==2.5.2`;
- Increment 2 до основной реализации выполняет dependency smoke gate: package
  installation, `import numpy`, `import cv2`, создание ORB и минимальная
  descriptor operation;
- несовместимая пара wheels может быть скорректирована как dependency correction
  без пересмотра архитектуры Stage 6;
- остальные три analyzers не требуют новых runtime dependencies;
- текущий development/reference computer можно использовать для benchmark, но
  он не становится обязательным deployment requirement;
- предварительный ориентир reference environment: x86-64 CPU, 16 GiB RAM, без
  GPU; это не окончательная minimum specification;
- closure increment измеряет фактические resource requirements на benchmark и
  фиксирует результат;
- repository хранит deterministic generated positive, negative,
  false-positive/challenge и boundary/not-applicable fixtures;
- реальные datasets/media на этом этапе не добавляются, а fixtures не
  представляются статистической validation dataset.

### Provenance requirement

`REFERENCES.md` является каноническим реестром происхождения методов,
реализаций, библиотек, repositories, статей, моделей и weights. Правило Stage 6:
**NO PROVENANCE — NO ANALYZER**. Реальный analyzer нельзя считать завершённым,
пока применимая provenance information не заполнена и происхождение метода
отделено от происхождения реализации.

Framework test analyzers сохраняются только для проверки общей execution
архитектуры; production implementations подключаются отдельными trusted
registrations.

### Increment 1 — technical analyzers + Finding vertical slice — DONE

Реализованы три независимых production-path technical analyzers версии `1.0.0`:

- `image_metadata_consistency` использует controlled original source и не
  интерпретирует отсутствие metadata или software tag как finding;
- `audio_pcm_quality` потоково анализирует canonical signed 16-bit little-endian
  PCM WAV и локализует не более 16 strongest saturation observations по
  существующим fragments;
- `video_sampled_frame_quality` использует только подготовленные sampled frames,
  сравнивает decoded pixels и не требует video audio track.

Private typed candidate boundary повторно валидируется deterministic Stage 6
converter. Content-addressed `finding_id` следует §9.5 `CONTRACTS.md`; findings
сохраняются как canonical immutable bytes в отдельном sibling `Stage6TaskData`, а
detached reads не изменяют authoritative state. Новые runtime dependencies,
public API, persistence, risk/completeness logic и новый `ProcessingStage` не
добавлены. Generated fixtures и targeted Stage 5/6 regressions подтверждают
контракт и resource/transport bounds.

Ближайшее действие: Increment 2 — smoke gate planned OpenCV/NumPy pins и
реализация `image_copy_move_correspondence`.

### Increment 2 — ограниченное соответствие областей изображения — DONE

Запланированные версии `opencv-python-headless==4.14.0.94` и `numpy==2.5.2`
штатно установлены через uv и подтверждены на Windows / Python 3.12: импорт,
ORB-дескрипторы и оценка аффинной модели RANSAC прошли детерминированную
минимальную проверку. Реализован доверенный
`image_copy_move_correspondence` `1.0.0`, использующий только существующий
`normalized_image`, сопоставление ORB-признаков внутри изображения только на CPU,
пространственное разделение и не
более четырёх итераций OpenCV RANSAC.

Каждый принятый геометрический кластер создаёт ровно два bbox-кандидата с общим
адресуемым по содержимому `correlation_group`; симметричные самосопоставления и
близкие дублирующие пары областей детерминированно подавляются. Настройками и кодом
установлены пределы: 5 000 ключевых точек, 4 кластера и 8 кандидатов; дескрипторы,
ключевые точки, сопоставления и пиксели не публикуются через транспорт. Пройдены
генерируемые положительная, отрицательная, с альфа-каналом RGBA, проверка ложного
срабатывания, граничная, детерминированная и выполняемая в порождённом рабочем
процессе фикстуры. Наблюдение остаётся `weak` и не утверждает подделку переносом
области изображения.

### Increment 3 — production integration, benchmark и полный barrier — DONE

`Stage5ExecutionService`, не меняя `TaskExecutor` и ownership terminal lifecycle,
после orchestration сверяет возвращённый tuple с опубликованными данными, читает
detached canonical `AnalyzerResult[]` через authoritative `TaskRegistry`, передаёт
их `Stage6FindingService` и публикует отдельный `Stage6TaskData` в состоянии
`RUNNING / ANALYSIS`. Пустой `Finding[]` публикуется как корректное состояние;
ошибка candidate validation безопасно завершает задачу через существующий
`internal_error` analysis phase. Новый `ProcessingStage`, public executor,
schema, persistence или Stage 7 logic не добавлены.

Production composition root создаёт закрытый `AnalyzerRegistry` только из четырёх
real Profile B registrations и связывает intake, preprocessing, spawned analyzer
workers, Finding formation, registry и bounded scheduler. Канонический example
config включает планы в порядке:

```text
image: image_metadata_consistency → image_copy_move_correspondence
audio: audio_pcm_quality
video: video_sampled_frame_quality
```

Сквозные генерируемые image/audio/video tests подтвердили production composition,
авторитетное хранение results/findings, пустой результат, `NOT_APPLICABLE`,
изоляцию `ERROR`, безопасный malformed candidate, неизменный смысл
`Stage5TaskData`, lifecycle `ANALYSIS` до terminalization и detached reads.

Closure benchmark `uv run python scripts/benchmark_stage6_copy_move.py` выполнен
2026-09-08 на Windows 11 `10.0.26200`, AMD64, Intel(R) Core(TM) Ultra 7 270K Plus,
24 logical CPU, 130427.84 MiB total RAM, Python 3.12.10, OpenCV 4.14.0 и NumPy
2.5.2. В отдельном свежем child process анализировался генерируемый по seed 6003
feature-rich PNG 4000×3000 (12 000 000 pixels, 3 896 452 bytes) с одной
скопированной областью 700×700; один warm-up исключён, затем измерены три запуска.
RAM измерена Win32 `GetProcessMemoryInfo / PeakWorkingSetSize`, включая baseline
интерпретатора и импортов дочернего процесса.

| Run | Wall, s | CPU, s | Peak working set, MiB | Keypoints | Descriptors | Matches | Clusters | Candidates |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.613 | 0.578 | 161.78 | 5000 | 5000 | 104 | 1 | 2 |
| 2 | 0.615 | 0.562 | 161.65 | 5000 | 5000 | 104 | 1 | 2 |
| 3 | 0.622 | 0.578 | 161.66 | 5000 | 5000 | 104 | 1 | 2 |

Итог: median wall `0.615 s`, max wall `0.622 s`, max peak working set
`161.78 MiB`. Это наблюдение одной reference machine, а не универсальная
hardware guarantee. Предварительный conservative deployment baseline x86-64 CPU,
16 GiB RAM, без GPU подтверждён и не понижен по одному локальному замеру. Пределы
12 MP, 5000 ORB keypoints, 4 clusters и 8 candidates не расширялись; измерение
дало 1 cluster и 2 candidates, raw pixels/keypoints/descriptors в result не
публикуются, Stage 5 transport bound и deterministic OpenCV one-thread/OpenCL-off
policy не изменены.

Full Stage 6 quality barrier пройден после implementation и benchmark: `uv lock
--check`, Ruff, mypy, pre-commit, CLI/import smoke и `1389 passed, 2 skipped`;
combined coverage `89.55%`, statement coverage `92.03%`, branch coverage `79.52%`
при включённом `--cov-branch`. Исторические 19 formatter discrepancies остались
тем же не затронутым Stage 6 debt, все изменённые Python-файлы format-clean.
Эта проверка качества реализации предшествовала независимому финальному аудиту
и сохранена для прослеживаемости. Формальное закрытие зафиксировано ниже.

### Ремедиация замечаний независимого аудита и финальное закрытие — DONE

Независимый финальный аудит Stage 6 завершился `FAIL` с четырьмя блокирующими
замечаниями. `S6-AUD-001`, `S6-AUD-003` и `S6-AUD-004` закрыты. Повторный аудит
подтвердил устранение наблюдаемых разрывов владения потоками `S6-AUD-002`, но
обнаружил `S6-REAUD-001` уровня `MEDIUM`: вторичное исключение рабочего потока
при завершении `lifespan` могло заменить первичное исключение вызывающего кода.
Локальная ремедиация выполнена без изменения Profile B, публичной схемы,
`TaskExecutor`, `ProcessingStage` или архитектуры владения Stage 4:

- [x] `S6-AUD-001` — после обнаружения ORB связанные пары keypoint/descriptor
  канонически упорядочиваются и жёстко ограничиваются `max_keypoints` до
  самосопоставления; публикуемые счётчики описывают сохранённое подмножество;
- [x] `S6-AUD-002` — attempts запуска, публикация полного worker ownership,
  переход в `RUNNING` и startup notify находятся под одной failure-cleanup
  boundary без `try/except/else`; при сбое до commit планировщик публикует
  terminating state, запрещает новые передачи задач, явно ожидает через `join()`
  все наблюдаемо запущенные потоки и затем очищает ownership; обычное `Exception`
  сохраняет `SchedulerStateError`, а exact `KeyboardInterrupt`/`SystemExit`
  поднимается повторно; production lifespan включает `start()` в собственную
  cleanup boundary и после любого подтверждённого startup либо фактического
  non-stopped состояния вызывает штатный `shutdown()`, включая post-return
  interruption до локальной фиксации успешного startup;
- [x] `S6-AUD-003` — `PixelXDimension`/`PixelYDimension` ищутся во всех
  допустимых представлениях Pillow раньше `ImageWidth`/`ImageLength`;
  присутствующий некорректный основной тег не подменяется резервным и не создаёт
  необоснованного заключения о согласованности;
- [x] `S6-AUD-004` — подавление пар по IoU с прежним порогом `0.5` проверяет оба
  порядка неупорядоченной пары областей — прямой и перекрёстный; отдельные
  кластеры сохраняются.

- [x] `S6-REAUD-001: CLOSED` — `lifespan` различает завершение с первичным
  исключением и без него. После завершённого `shutdown()` сохраняется тот же
  объект первичного `BaseException`; без первичного исключения ошибка рабочего
  потока выходит наружу. Сбой незавершённого `shutdown()` не подавляется.
  Проверены разные объекты `KeyboardInterrupt`, `SystemExit` и `RuntimeError`,
  реальная задача рабочего потока, однократные `join()` и отсутствие живых
  `stage4-*`. Устранение подтверждено финальной независимой проверкой закрытия.

#### S6-LIM-001 — CPython `Thread.start()` pre-ack interruption ambiguity

Статус: `ACCEPTED_RUNTIME_LIMITATION`.

Влияние на закрытие: `DOES_NOT_BLOCK_STAGE6_CLOSURE`.

CPython 3.12 может создать нативный поток ОС раньше, чем `Thread.start()`
опубликует `_started` и `ident`. В этом узком окне `ident` может оставаться
`None`, `is_alive()` — возвращать `False`, а `join()` — быть недоступным, поэтому
публичный API `threading` не позволяет доказуемо отличить ещё не созданный поток
от созданного, но ещё не подтвердившего старт. Планировщик не заявляет явный
`join()` такого ненаблюдаемого потока.

Остаточное окно принято как эксплуатационное ограничение: после неудачного
старта состояние планировщика уже является `SHUTTING_DOWN` или `STOPPED`, новые
передачи задач отклоняются, а поздно подтвердивший старт рабочий поток при входе
в цикл видит завершающее состояние и заканчивает работу без исполнения задачи.
Устранение наблюдаемого разрыва владения после цикла запуска `S6-AUD-002`
подтверждено независимым аудитом. Глобальная для процесса
отсрочка сигналов, отдельный долгоживущий владелец старта, дополнительный поток
или процесс запуска, собственный нативный механизм запуска или расширение C,
приватные глобальные объекты CPython, daemon-потоки и тайм-ауты или опрос для
угадывания результата старта не вводятся.

Нагрузочная фикстура на зафиксированной версии OpenCV дала `5687` исходных
keypoints/descriptors и `5000` сохранённых и проанализированных; `BFMatcher`
получил не более `5000`, результат остался детерминированным и ограниченным.
Повторный контрольный замер 12 MP сохранил `5000` keypoints/descriptors, `104`
сопоставления, `1` кластер и `2` кандидата.

Финальная полная проверка качества на HEAD
`0377185889a703aee92df6c23458a28aef1630a1`: `1438 passed, 2 skipped`;
совокупное покрытие `89.78%`, покрытие операторов `92.27%` (`5595/6064`),
покрытие ветвей `79.73%` (`1196/1500`) при включённом `--cov-branch`.
`uv lock --check`, Ruff, mypy для 56 исходных файлов, pre-commit, базовая
проверка CLI, импорт пакета, импорт OpenCV 4.14.0, импорт NumPy 2.5.2 и
`git diff --check` имеют статус `PASS`. Исторический базовый набор расхождений
форматтера остался тем же: 19 файлов; рабочее дерево при аудите было чистым.

Финальная независимая проверка закрытия вынесла решение
`CLOSE_STAGE6_WITH_ACCEPTED_LIMITATION`. `S6-AUD-001`…`S6-AUD-004` и
`S6-REAUD-001` имеют статус `CLOSED`; `S6-AUD-005` — `INFO / NON_BLOCKING`.
Новых замечаний уровня `HIGH` или `MEDIUM`, блокирующих закрытие, нет.
`S6-LIM-001` сохранён как осознанное `ACCEPTED_RUNTIME_LIMITATION` /
`NON_BLOCKING`: он не распространяется на наблюдаемые рабочие потоки, для
которых все наблюдаемые разрывы владения при запуске устранены. Stage 6 завершён
и закрыт.

## Рекомендуемый минимальный принцип выбора

Для каждой модальности достаточно:

- одного технического/метадатного анализатора;
- одного простого содержательного анализатора, если он обоснован и тестируем;
- ML-анализатора только при подтверждённой необходимости и доступном оборудовании.

Количество анализаторов не является критерием качества.

## Обязательные задачи

- [x] утвердить профиль анализаторов image;
- [x] утвердить профиль анализаторов audio;
- [x] утвердить профиль анализаторов video;
- [x] реализовать выбранные анализаторы как независимые модули;
- [x] зафиксировать версии;
- [x] добавить тестовые fixtures;
- [x] реализовать преобразование candidate findings в `Finding`;
- [x] хранить `Finding[]` в отдельном sibling Stage 6 task state;
- [x] сохранять связь с анализатором и версией;
- [x] реализовать локализацию, где она доступна;
- [x] ввести correlation_group для связанных результатов;
- [x] не назначать critical автоматически по confidence.
- [x] создать `REFERENCES.md` и зафиксировать правило NO PROVENANCE — NO ANALYZER;
- [x] актуализировать provenance после каждой фактической реализации analyzer.

## Обязательные тесты

- [x] каждый анализатор проходит контрактный тест;
- [x] корректно сообщает not applicable;
- [x] не создаёт выдуманный score;
- [x] формирует стабильный finding type;
- [x] локализация валидна;
- [x] версия присутствует;
- [x] ошибка не ломает общий цикл;
- [x] коррелированные признаки маркируются.

## Критерий завершения

Сквозной контур работает с утверждённым Profile B; каждый analyzer имеет
проверенные deterministic fixtures и заполненную запись в `REFERENCES.md`, а
нормализованные findings сохраняют provenance в отдельном sibling Stage 6 state.

---

# Этап 7. Полнота, риск и рекомендации — DONE

## Цель

Преобразовать набор признаков в объяснимую оценку с учётом неполноты и корреляции.

## Декомпозиция реализации

- [x] Increment 1 — зафиксировать политику MVP и реализовать чистое
  детерминированное ядро полноты, риска и рекомендаций без интеграции с жизненным
  циклом;
- [x] Increment 2 — добавить минимальное внутреннее состояние задачи для
  результатов Stage 7 без нового оркестратора;
- [x] Increment 3 — подключить Stage 7 к рабочему выполнению в существующей
  модели владения жизненным циклом.

Increment 2 добавил отдельный предназначенный только для внутреннего использования
`Stage7TaskData` с каноническими неизменяемыми JSON-байтами для
`AnalysisCompleteness`, `RiskAssessment` и `Recommendation`, однократную атомарную
публикацию и независимое чтение через авторитетный `TaskRegistry`. Жизненный цикл
расширен переходами
`ANALYSIS → RISK_ASSESSMENT → COMPLETED | PARTIAL | FAILED / CLEANUP`;
Stage 8 Macro 1 позднее расширил общий терминальный участок через
`PERSISTENCE → FINISHED`. Пригодный `PARTIAL` поддерживается
`TaskExecutionOutcome.partial()` без искусственной ошибки и отдельного пути очистки.
Increment 3 подключил рабочую цепочку
`Stage 5 → AnalyzerResult[] → Stage 6 → Finding[] → RISK_ASSESSMENT → Stage 7`.
Исполнитель получает активный план анализаторов из того же неизменяемого снимка
конфигурации, публикует `Stage7TaskData` до возврата основного результата
выполнения и сопоставляет `complete` с `COMPLETED`, а `partial` и `insufficient` —
с `PARTIAL`. Внутренний сбой Stage 7 безопасно приводит к `FAILED`; существующее
владение очисткой и публикация `FINISHED` не изменены. Рабочий Profile B сохраняет
`probability=null`, пустой доверенный каталог правил `critical_override` и один
вклад weak для коррелированной пары `Finding` copy-move.

Все три функциональных инкремента Stage 7 реализованы, предаудитный полный барьер
качества реализации успешно пройден. Независимый финальный аудит завершён с verdict
`CLOSE_STAGE7_UNCHANGED`; Stage 7 формально закрыт. Stage 8 также формально закрыт:
Macro 1 и Macro 2 завершены, findings `S8-A01`–`S8-A03` исправлены, а
post-remediation closure audit завершён с `PASS` без новых findings.

## Обязательные задачи

### Полнота

- [x] реализовать подсчёт `planned`/`applicable`/`completed`/`error`/`timeout`/`skipped`;
- [x] реализовать статусы `complete`/`partial`/`insufficient`; сохранить
  `not_assessed` только для отклонения или сбоя до Stage 7;
- [x] включить алгоритм полноты v1 в единый пакет правил
  `score_model_v1@0.1.0` без нового публичного поля;
- [x] запретить `low` при `insufficient`;
- [x] формировать `missing_capabilities` в порядке активного плана.

### Риск

- [x] реализовать отдельный `RiskAssessmentService`;
- [x] загружать веса и пороги из типизированной конфигурации;
- [x] версионировать правила как `score_model_v1@0.1.0`;
- [x] реализовать балльную модель MVP как проектную, не статистическую;
- [x] реализовать ограничение двойного учёта `correlation_group`;
- [x] оставить `probability` и `probability_method` равными `null`;
- [x] реализовать детерминированные `explanation` и `limitations`.

### Critical override

- [x] оставить выключенным по умолчанию;
- [x] оставить доверенный рабочий каталог Profile B пустым;
- [x] проверить список разрешённых типов, точное доверенное правило, источник,
  версию и применимость;
- [x] сохранять вызвавшие `critical_override` идентификаторы `finding_id`
  детерминированно;
- [x] добавить отдельные тесты с тестовым доверенным правилом.

### Рекомендации

- [x] связать риск и полноту с безопасными действиями;
- [x] не выполнять автоматическое реагирование;
- [x] формировать детерминированный русскоязычный человекочитаемый текст;
- [x] учитывать `partial`/`insufficient`.

## Обязательные тесты

- [x] отсутствие признаков при полном анализе;
- [x] несколько `Finding` с `severity=weak`;
- [x] `Finding` с `severity=significant`;
- [x] коррелированные `Finding` не удваивают вклад;
- [x] анализ со статусом `partial`;
- [x] анализ со статусом `insufficient`;
- [x] `critical_override` выключен;
- [x] разрешённый `critical_override`;
- [x] запрещённый `critical_override`;
- [x] `probability` остаётся `null`;
- [x] объяснение соответствует основаниям.

## Критерий завершения

Для фиксированного набора входных `AnalyzerResult` система детерминированно выдаёт контрактные `Finding`, полноту, риск и рекомендацию, подтверждённые тестами.

## Финальный аудит Stage 7

Независимый read-only аудит завершён с verdict
`CLOSE_STAGE7_UNCHANGED`. Correctness findings уровней `BLOCKER`, `HIGH` и
`MEDIUM` отсутствуют.

- `S7-A01` (`LOW`) — `CLOSED` в documentation closure: устаревший комментарий
  примера конфигурации синхронизирован с фактическим production execution path;
- `S7-A02` (`LOW`) — `CLOSED` попутно во время Stage 8 Macro 1: регрессионные
  проверки подтверждают `processing_timeout / FAILED` при истечении срока до
  публикации и отсутствие нового окна тайм-аута или сбоя после успешной границы
  фиксации `publish_stage7_assessment()`.

Stage 7 имеет статус `DONE`. Stage 8 также завершён и закрыт после исправления
findings `S8-A01`–`S8-A03` и успешного post-remediation closure audit.

---

# Этап 8. JSON, API и WebUI — DONE / CLOSED

## Цель

Предоставить единый итоговый результат человеку и внешней системе без дублирования бизнес-логики.

## Декомпозиция реализации

- [x] Macro 1 — хранение результатов: правдивый терминальный `AnalysisResult`
  1.0, отделённые факты терминального состояния, единые сборщик и финализатор,
  атомарное сохранение JSON и рабочая интеграция с записью до `FINISHED`;
- [x] Macro 2 — утверждённые асинхронный HTTP API и WebUI с HTTP Basic;
  реализация и проверка владельцем завершены, независимый финальный аудит выполнен,
  findings `S8-A01`–`S8-A03` исправлены в remediation commit `7093922`, а
  post-remediation independent closure audit завершён с `PASS` без новых findings.

Macro 1 исправляет схему `AnalysisResult` 1.0 до первого внешнего использования:
до появления первого рабочего потребителя API/WebUI добавлена фактическая
нулевая допустимость терминальных путей без перехода на 2.0 и без миграции
совместимости. `ResultFinalizationService` собирает результат только из
авторитетных фактов, применяет `include_raw_metrics` к отделённой проекции и
сохраняет её до публикации `FINISHED`. Ошибка сохранения оставляет принятую задачу
в `PERSISTENCE` с `result_write_failed`, не повторяя анализ и очистку; ошибка
сохранения Stage 3 не создаёт фиктивный результат или гарантию восстановления.

## Ворота этапа

Решения владельца для Macro 2 подтверждены:

- [x] асинхронный API с задачами;
- [x] три маршрута и фактические временные метки статуса;
- [x] смешанная семантика HTTP-ответов при отклонении;
- [x] HTTP Basic для WebUI;
- [x] статический Bearer-токен API из окружения.

Реализация этих внешних границ относится только к Macro 2.

## Обязательные задачи

### Итоговый результат

- [x] собрать только терминальный `AnalysisResult` 1.0 для принятого пути и путей
  Stage 3;
- [x] добавить фактический статус очистки без подстановочных значений;
- [x] сохранить через существующий `JsonFileResultRepository`;
- [x] проверить детерминированный канонический JSON и атомарную запись;
- [x] не включать внутренние пути, права доступа и секреты;
- [x] обеспечить `FACT_READY → PERSISTENCE → save → FINISHED`;
- [x] сохранить авторитетные факты анализаторов и признаков для принятого
  `failed`;
- [x] применить `include_raw_metrics` без изменения состояния задачи;
- [x] отклонять `atomic_write=false` и `store_original_name=false`.

### API

- [x] реализовать выбранный профиль;
- [x] проверить Bearer-токен из окружения;
- [x] реализовать загрузку `multipart/form-data`;
- [x] валидировать SourceContext;
- [x] вернуть канонические ошибки;
- [x] не размещать бизнес-логику в маршрутах;
- [x] сформировать OpenAPI из моделей.

### WebUI

- [x] создать страницу загрузки;
- [x] показать ограничения;
- [x] создать статус/ожидание обработки;
- [x] создать страницу результата;
- [x] использовать тот же `AnalysisResult`;
- [x] показать полноту и ограничения;
- [x] показать предупреждение об отсутствии окончательной экспертизы;
- [x] реализовать утверждённый HTTP Basic;
- [x] создать каталоги `templates` и `static`;

## Обязательные тесты

### Хранение результатов Macro 1

- [x] все терминальные формы `COMPLETED`, `PARTIAL`, `REJECTED`, `FAILED`;
- [x] инварианты только терминального результата, фактическая нулевая
  допустимость, хронология и `NOT_ASSESSED` без подстановочных нулей;
- [x] отклонение и сбой Stage 3, неудачная передача владения и отсутствие
  результата для
  `PreRegistrationError`;
- [x] канонический круговой цикл сериализации, CRUD и перечисление в репозитории,
  атомарная замена и безопасность при повреждении данных, несовпадении
  идентификатора, небезопасном пути, символической ссылке и `OSError`;
- [x] обе политики `include_raw_metrics` без изменения авторитетных фактов;
- [x] срок выполнения до публикации Stage 7 и граница фиксации после публикации;
- [x] сохранение после `FACT_READY`, `FINISHED` только после сохранения и запрет
  повторной попытки при ошибке сохранения;
- [x] отделённые авторитетные факты терминального состояния и облегчённый рабочий
  путь изображения.

### HTTP/WebUI Macro 2

- [x] успешная загрузка WebUI;
- [x] успешная загрузка API;
- [x] оба канала используют один сервис;
- [x] 401 без токена;
- [x] 413 для большого файла;
- [x] 415 для неподдерживаемого типа;
- [x] статус и результат соответствуют контракту;
- [x] WebUI не пересчитывает риск;
- [x] ошибка не раскрывает трассировку;
- [x] OpenAPI соответствует Pydantic-моделям.

## Критерий завершения

Файл можно передать через WebUI и API, получить один и тот же доменный результат и безопасно обработать ошибки.

Macro 1 и Macro 2 реализованы и покрыты контрактными и межканальными тестами.
Общий критерий функциональной реализации достигнут. Stage 8 Macro 1 и Macro 2
завершены; независимый финальный аудит выполнен, findings `S8-A01`, `S8-A02` и
`S8-A03` исправлены в remediation commit `7093922`. Post-remediation independent
closure audit завершён с `PASS`, новых findings нет. Stage 8 имеет статус
`DONE / CLOSED`; Stage 9 также завершён и закрыт после independent
post-remediation audit с `PASS`: findings `S9-A01` и `S9-A02` закрыты, новых
findings нет. Актуальный статус Stage 10 приведён в разделе «Текущее состояние»
и подробном разделе Этапа 10.

Quality barrier closure audit Stage 8: `1687 passed, 3 skipped`, coverage `90%`;
`ruff`, `mypy`, `pre-commit`, lock, CLI/import и `git diff --check` — `PASS`.

---

# Этап 9. Надёжность, безопасность и сквозные тесты — DONE / CLOSED

## Цель

Доказать работоспособность полного цикла в штатных и аварийных сценариях.

## Декомпозиция Stage 9

- [x] Macro 1 — DONE / committed at `ad6050c`: lifecycle safety и JSONL diagnostics: cleanup safety barrier
  Stage 3, per-analysis pre-handoff coordination с janitor, безопасные
  диагностические события и `request_id` correlation; findings `S9-M1-R01` и
  `S9-M1-R02` устранены;
- [x] Macro 2 — DONE / committed at `4e4ba3c`: targeted filesystem
  TOCTOU/reparse и runtime-root hardening; sensitive roots/direct workspace проверяются
  на symlink/junction/detectable reparse, destructive recovery retained/reports
  suspicious objects, а private runtime ACL остаётся documented deployment
  prerequisite stdlib/Windows;
- [x] Macro 3 — DONE / committed at `bddcedb`: bounded actual HTTP multipart
  body, receive/parse deadline, strict multipart structure и FFmpeg/process
  security;
- [x] Macro 4 — DONE / committed at `2ef98a3`: Profile B full-path E2E,
  restart/failure/security/concurrency/shutdown proof и измеренный
  performance/resource envelope.
- [x] Final audit remediation — DONE / committed at `111a832`: `S9-A01` и
  `S9-A02` устранены; multipart completeness подтверждается closing-boundary
  callback и завершением ASGI stream; receive/parse deadline дополнен
  synchronous monotonic checkpoints и финальной проверкой до возврата формы.

Macro 1–4 и remediation committed. Independent final audit вернул `REMEDIATE`
по `S9-A01` и `S9-A02`. Independent post-remediation audit завершён с `PASS`:
`S9-A01` — `CLOSED`, `S9-A02` — `CLOSED`; новых findings нет.

Финальное состояние findings:

```text
BLOCKER 0
HIGH 0
MEDIUM 0
LOW 0
```

## Зафиксированные owner decisions

- `S9-D01`: runtime приватен для account приложения; защита от hostile process
  той же Windows account или Administrator не обещается; Macro 2 остаётся
  targeted, полный Win32 handle-based redesign не требуется.
- `S9-D02`: Macro 2 создаёт новые sensitive runtime roots максимально приватно
  средствами stdlib/Python 3.12, не переписывает существующие ACL, не добавляет
  pywin32/dependency, fail-safe обрабатывает reparse hazards; непроверяемые stdlib
  ACL являются deployment prerequisite.
- `S9-D03`: Macro 3 использует max per-media limit + 1 MiB envelope, actual-byte
  counting, `413` до регистрации и `server.request_timeout_seconds` как HTTP
  receive/parse deadline.
- `S9-D04`: JSONL использует только утверждённый safe allowlist; raw exception,
  credentials, secrets, `SourceContext`, headers, filename, paths и иной
  user-controlled payload запрещены без sanitization contract.
- `S9-D05`: durable recovery, persistence/analysis retry и startup cleanup
  `.result-*.tmp` не вводятся; pre-handoff cleanup barrier обязателен, residue
  получает diagnostic и ручную safe maintenance procedure.
- `S9-D06`: local MVP опирается на bounded algorithms, body guard и измеренный
  resource envelope; OS-level CPU/RAM hard quotas вне Stage 9.

## Обязательные задачи

### Ошибки

- [x] классифицировать ошибки;
- [x] обеспечить безопасные пользовательские сообщения;
- [x] сохранять утверждённую Macro 1 диагностику в JSONL;
- [x] проверить частичный сбой;
- [x] проверить системный сбой;
- [x] проверить timeout;
- [x] проверить сбой сохранения;
- [x] проверить сбой очистки.

### Безопасность

- [x] проверить path traversal в sensitive runtime ownership boundaries;
- [x] проверить и усилить runtime storage против concurrent symlink
  substitution / TOCTOU, включая descriptor-based/no-follow подход при
  необходимости;
- [x] проверить command/option injection и protocol abuse для FFmpeg/ffprobe;
- [x] ограничить subprocess time/output и HTTP body receive/parse;
- [x] проверить отсутствие секретов и private payload в JSONL Macro 1;
- [x] проверить отсутствие runtime в Git;
- [x] проверить MIME/signature mismatch;
- [x] ограничить доступ к новым runtime roots средствами stdlib и зафиксировать
  Windows ACL deployment prerequisite;
- [x] проверить токен API;
- [x] проверить CSRF при cookie-аутентификации WebUI, если она выбрана.

### Сквозные сценарии

- [x] валидное изображение;
- [x] валидное аудио;
- [x] валидное видео;
- [x] отклонённый файл;
- [x] один анализатор ошибся;
- [x] несколько анализаторов недоступны;
- [x] insufficient completeness;
- [x] ошибка очистки;
- [x] повторный запрос результата;
- [x] параллельные задачи в пределах лимита.

### Производительность

- [x] измерить время базовых сценариев;
- [x] измерить память для видео;
- [x] проверить отсутствие загрузки крупного видео целиком;
- [x] проверить очередь при нескольких задачах;
- [x] проверить необходимость корректировки EXAMPLE-лимитов по результатам:
  `DEFERRED_WITH_REASON` — informational baseline малых deterministic fixtures
  не обосновывает изменение deployment limits или введение SLA.

## Macro 4 — фактическая E2E-матрица

| Media | Fixture | Активные analyzers | Ожидаемый итог | Внешний путь | Persistence/restart |
|---|---|---|---|---|---|
| image | generated seeded copy-move PNG 512×512 | `image_metadata_consistency`, `image_copy_move_correspondence` | `completed`, findings, complete risk/recommendation | API и representative WebUI | persisted result; отдельный restart proof |
| audio | generated PCM WAV 8 kHz с bounded saturation observations | `audio_pcm_quality` | `completed`, finding, complete risk/recommendation | API | persisted result |
| video | generated MP4 64×64, 2 fps, repeated frames, 3.2 s | `video_sampled_frame_quality` | `completed`, finding, complete risk/recommendation | API | persisted result |

Full-path тесты используют настоящий `create_app`, production composition,
Stage 3 validation, scheduler/registry, Stages 5–7, финализатор,
`JsonFileResultRepository`, API/WebUI и временные каталоги pytest. Отдельно
проверены restart без старого `TaskRegistry`, Stage 3 mismatch, media-tool
infrastructure failure, persistence failure без retry/ложного `FINISHED`, cleanup
residue, auth/body guards assembled app, одновременные image-задачи и graceful
shutdown со startup/shutdown sweep.

## Macro 4 — классификация оставшегося checklist

| Область | Классификация | Основание |
|---|---|---|
| Error taxonomy, safe messages, partial/timeout/insufficient paths | VERIFIED | существующие Stage 5/7 targeted tests и новые full-path terminal tests |
| System, persistence и cleanup failures | IMPLEMENTED | representative deterministic E2E через production boundaries |
| Runtime not in Git | VERIFIED | `.gitignore`, `git ls-files` и итоговый status проверяются barrier |
| MIME/signature mismatch и API token | VERIFIED | assembled-app E2E плюс targeted transport/auth tests |
| WebUI CSRF | NOT_APPLICABLE | cookie/session architecture не выбрана; строгий same-origin guard проверен |
| Bounded deterministic behavior | VERIFIED | artifact/process/body limits, Profile B E2E и measurement sanity |
| OS CPU/RAM hard quotas | DEFERRED_WITH_REASON | `S9-D06`: вне local MVP и Stage 9 |
| Изменение EXAMPLE deployment limits | DEFERRED_WITH_REASON | получен informational reference baseline, но нет данных для нормативной коррекции |

## Macro 4 — reference measurement 2026-09-16

Команда воспроизведения:

```powershell
uv run python scripts/measure_stage9_profile_b.py --runs 3
```

Среда: Windows 11 `10.0.26200`, AMD64, Python 3.12.10,
Intel64 Family 6 Model 198 Stepping 2, 24 logical CPU. Каждый media run выполнен
в свежем process; wallclock охватывает scheduler start, полный application
workflow, persisted result retrieval и graceful shutdown.

| Media | Fixture bytes | Runs | Median wall, s | Max wall, s | Result bytes | Max runner peak RSS, MiB |
|---|---:|---:|---:|---:|---:|---:|
| image | 80 483 | 3 | 1.047 | 1.077 | 6 862 | 73.08 |
| audio | 16 044 | 3 | 0.633 | 0.666 | 4 621 | 67.70 |
| video | 1 101 | 3 | 0.644 | 0.654 | 4 775 | 67.52 |

Полный wallclock девяти изолированных запусков с созданием child process составил
`11.590 s`. RSS на этой Windows-среде измерен stdlib `ctypes` через Win32
`GetProcessMemoryInfo / PeakWorkingSetSize` для свежего workflow runner process.
Метрика включает baseline Python/import/runtime, но не суммирует RSS spawned
analyzer и FFmpeg/ffprobe processes; на POSIX harness использует `ru_maxrss`, а
при недоступности корректной метрики возвращает `null`. Числа являются reference
measurement этой среды, не SLA и не deployment guarantee.

## Критерий завершения

Все обязательные сквозные, негативные и безопасностные тесты проходят; известные ограничения зафиксированы; исходные и промежуточные данные удаляются фактически.

Stage 9 имеет статус `DONE / CLOSED`. Финальный quality barrier:

- full pytest: `1763 passed, 17 skipped`;
- coverage: `90%`;
- targeted remediation/post-remediation suite: `116 passed`;
- `uv lock --check`: `PASS`;
- Ruff: `PASS`;
- mypy: `PASS`, 64 source files;
- pre-commit: все 8 hooks `PASS`;
- CLI/import smoke: `PASS`;
- `git diff --check`: `PASS`.

Принятые ограничения Stage 9 не являются незакрытыми findings:

- Windows ACL остаётся deployment prerequisite;
- hostile same-account / Administrator находится вне гарантированной threat model;
- полный filesystem/process sandbox отсутствует;
- OS CPU/RAM hard quotas не вводились;
- durable unfinished-job recovery отсутствует;
- persistence retry отсутствует;
- автоматическое удаление `.result-*.tmp` crash residue не вводилось;
- resource measurements имеют informational характер и не являются SLA;
- 17 symlink-related skips на текущем Windows host связаны с отсутствием
  symlink privileges; native Windows junction coverage при этом выполнялась.

Актуальный статус Stage 10 приведён в разделе «Текущее состояние» и подробном
разделе Этапа 10.

---

# Этап 10. Сборка и демонстрация MVP — DONE / CLOSED

## Цель

Подготовить воспроизводимый прототип, который можно установить, запустить, продемонстрировать и передать.

## Обязательные задачи

- [x] зафиксировать версии runtime-зависимостей через механический export `uv.lock`;
- [x] проверить чистую установку exact wheel через uv во внешнем venv;
- [x] описать установку FFmpeg для Windows;
- [x] создать README запуска;
- [x] создать безопасный пример `.env.example`;
- [x] подготовить рабочую конфигурацию Profile B для handoff/demo;
- [x] подготовить deterministic generator небольшого набора легальных тестовых файлов;
- [x] описать ограничения анализаторов;
- [x] проверить запуск без IDE;
- [x] проверить очистку после демонстрации;
- [x] зафиксировать номер версии MVP `0.1.0`;
- [x] обновить `CHANGELOG.md` для Macro 1;
- [x] отметить все выполненные критерии MVP.

## Статус макрозадач

- Macro 1 — **DONE / owner accepted**, committed SHA
  `841213f299dd6eb5052cabff95d7bb34fa3f91ab`: package-version source,
  sdist→wheel build, runtime constraints из `uv.lock`, package resources и
  isolated installed-wheel verification.
- Macro 2 — **DONE / owner accepted**: user-facing README и единый
  handoff guide, Windows FFmpeg prerequisite, config/secrets workflow,
  deterministic demo-media generator и его Profile B regression coverage.
- Macro 3 — **DONE / owner accepted**: внешний release assembler и
  verifier создаёт manifest + SHA-256 + versioned ZIP, устанавливает exact wheel
  из проверенной распаковки в fresh venv, запускает kit-копию demo generator и
  два реальных процесса установленного CLI. Development gate подтвердил real
  loopback HTTP, Basic/Bearer, WebUI upload, API image/audio/video, каноническую
  JSON persistence, cleanup, restart retrieval и signal-aware graceful shutdown;
  strict clean-SHA certification после remediation commit завершилась с `PASS`.

## Аудит, исправления и закрытие

Первоначальная strict certification на baseline SHA
`273a62951efebb0d2f10f4456ff4ebe4dd377a1f` завершилась с `PASS`.
Первоначальный независимый аудит Stage 10 вернул `REMEDIATE` по findings
`S10-A01`–`S10-A04`. Все четыре finding исправлены и проверены владельцем;
remediation commit — `7ee5e27755f4bb8f18a0a3924f8b79a1eb8e5217`.

Strict clean-SHA certification на этом remediation SHA — **PASS**:

- `certification_mode = strict`;
- `certified = true`;
- `overall_status = passed`;
- source SHA start/end = `7ee5e27755f4bb8f18a0a3924f8b79a1eb8e5217`;
- source SHA stable = `true`;
- source tree clean = `true`.

Это сертифицированная база исправлений до текущего документационного закрытия,
а не SHA будущего коммита закрытия документации.

Независимый аудит после исправлений (independent post-remediation audit) —
**PASS**. Итоговые статусы: `S10-A01 CLOSED`, `S10-A02 CLOSED`,
`S10-A03 CLOSED`, `S10-A04 CLOSED`. Новых findings нет:
**BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0**.

Stage 10 — **DONE / CLOSED**; Macro 1, Macro 2 и Macro 3 —
**DONE / owner accepted**. Версия MVP остаётся `0.1.0`, поддерживаемая база —
Windows 11 x64 / Python 3.12 / CPU-only.

## Критерии готовности MVP

- [x] запускается на целевом компьютере;
- [x] принимает image/audio/video через предусмотренные каналы;
- [x] отклоняет неподдерживаемые файлы;
- [x] запускает утверждённые анализаторы;
- [x] формирует признаки;
- [x] формирует полноту, риск и рекомендацию;
- [x] сохраняет JSON;
- [x] показывает WebUI-результат;
- [x] удаляет временные данные;
- [x] проходит тесты, Ruff и mypy;
- [x] не требует необязательной инфраструктуры;
- [x] не выдаёт результат за окончательную экспертизу.

Macro 3 development evidence подтверждает запуск exact wheel без IDE,
image/audio/video через real HTTP, Profile B analyzers, полный result contract,
каноническую persistence, WebUI, cleanup и restart. Отклонение неподдерживаемых
входов и формирование findings/risk/recommendation уже покрыты закрытыми Stage
8–9 и общим regression barrier. Внешними prerequisites остаются только
утверждённые Python 3.12, uv и FFmpeg/ffprobe; предупреждение об отсутствии
окончательной экспертизы сохранено в WebUI и handoff.

## Критерий завершения

Прототип воспроизводимо устанавливается и демонстрирует полный цикл на подготовленных тестовых данных.

Критерий выполнен; Stage 10 закрыт. Следующим этапом стал Stage 11 — Post-MVP
Normalization & Hardening, описанный ниже.

---

# Stage 11 — Post-MVP Normalization & Hardening — DONE / CLOSED

## Цель и принцип

Преобразовать успешно завершённый staged MVP в целостную, долгоживущую
продуктовую кодовую базу, не потеряв гарантии, полученные на этапах 1–10.

На этом этапе не добавляются широкие новые продуктовые возможности. Stage 11
устраняет случайную сложность, остатки поэтапной разработки, подтверждённые
дефекты и угрозы масштабируемости при сохранении доказанного поведения.

Краткий принцип: **«Не добавлять возможности. Удалять случайность.»**

Post-MVP whole-codebase audit завершён с вердиктом
`READY_FOR_NORMALIZATION_PLANNING`: `BLOCKER 0`, `HIGH 0`, `MEDIUM 2`, `LOW 2`.
Отдельно классифицированы `ARCHITECTURE 4`, `TECH_DEBT 3`, `NORMALIZATION 1`,
`STYLE 1`, `DOCUMENTATION 2`, `TEST_QUALITY 2`, `DEFERRED 1`.

## Статус макрозадач

- Macro 0 — Roadmap Restructuring: **DONE / owner accepted**;
- Macro 1 — Confirmed Defect Remediation: **DONE / owner accepted**;
- Macro 2 — Runtime State Retention: **DONE / owner accepted**;
- Macro 3 — Analyzer Registration Normalization: **DONE / owner accepted**;
- Macro 4 — Product Naming & Architecture Normalization: **DONE / owner accepted**;
- Macro 5 — Technical Debt / Config / Test-Support Cleanup: **DONE / owner accepted**;
- Macro 6 — Tests / Comments / Documentation Normalization: **DONE / owner accepted**;
- Macro 7 — Release Tooling Normalization: **DONE / owner accepted**;
- Macro 8 — Final Whole-Project Audit / Certification / Graphify Review:
  **DONE / owner accepted**.

## Macro 0 — Roadmap Restructuring — DONE / owner accepted

Цель:

- [x] формально ввести Stage 11;
- [x] перенести существующие будущие работы Stage 11+ в Stage 12+;
- [x] зафиксировать scope Stage 11 и уже принятые owner decisions;
- [x] не изменять production-код и runtime-поведение.

Macro 0 завершён и принят владельцем. Реализация Macro 1–8 в него не входила.

## Macro 1 — Confirmed Defect Remediation — DONE / owner accepted

Четыре подтверждённых post-MVP аудитом дефекта исправлены и приняты владельцем.

- **D01 — MEDIUM — CLOSED.** `ffprobe` теперь корректно запрашивает disposition
  attached picture: реальный M4A с embedded cover art принимается как аудио, а
  поведение для настоящего видео остаётся защищённым.
- **D02 — MEDIUM — CLOSED.** WebUI HTTP Basic credentials намеренно ограничены
  ASCII; неподдерживаемые non-ASCII credentials безопасно отклоняются при
  startup.
- **D03 — LOW — CLOSED.** Патологическая вложенность `source_context` JSON
  отображается в существующий управляемый ответ
  `400 invalid_source_context_json`, а не выходит как text/plain 500.
- **D04 — LOW — CLOSED.** `AnalyzerConfigurationError` обрабатывается как
  управляемый CLI startup failure: Uvicorn не запускается, ожидаемые ошибки
  конфигурации не выходят как traceback.

Проверка закрытия: targeted regression suite — `219 passed`; полный pytest —
`1813 passed, 17 skipped`; coverage — `90%`; lock, Ruff, mypy, pre-commit,
smoke-проверки и diff-check — `PASS`; owner implementation review — `PASS`.

## Macro 2 — Runtime State Retention — DONE / owner accepted

Цель — устранить неограниченное удержание в RAM завершённых агрегатов
`AnalysisTask`.

Отдельное независимое исследование подтвердило:

- полное удержание `AnalysisTask` после `FINISHED` не требуется для штатного
  получения production-результата;
- удержание является историческим остатком staged lifecycle development/testing;
- завершённые задачи остаются под сильными ссылками `TaskRegistry`, поэтому его
  размер растёт с числом завершённых анализов;
- `gc.collect()` не может освободить задачи, пока ими владеет registry;
- это намеренное неограниченное логическое удержание, а не доказанная
  классическая потеря объектов Python GC.

**OWNER DECISION — после успешного `FINISHED` использовать только repository-only
semantics.** Предпочтительная архитектура:

```text
TaskRegistry = unfinished/live work
ResultRepository = completed history
```

После успешного persistence и terminal settlement необходимо согласованно
опубликовать `FINISHED`, сохранить только краткоживущие detached return data,
нужные текущему caller, и удалить полный завершённый агрегат из `TaskRegistry`.
Постоянный terminal cache, TTL, LRU/FIFO и конфигурация terminal-state retention
не вводятся.

Обязательные поведенческие условия:

- persistence по-прежнему предшествует `FINISHED`;
- persistence failure остаётся в `PERSISTENCE` и не вытесняется;
- unsafe/incomplete cleanup остаётся live и не вытесняется;
- успешно сохранённые completed/partial/failed outcomes следуют одному правилу
  вытеснения;
- fast submit поддерживает согласованный live-or-persisted status lookup;
- worker не удерживает предыдущую завершённую задачу неограниченно во время idle;
- получение после restart остаётся repository-backed.

**OWNER DECISION — missing result after eviction.** После `FINISHED` durable
source of truth — сохранённый repository:

```text
valid persisted result
→ normal terminal status/result

persisted result absent
→ 404 / not found

persisted result present but corrupt/unreadable/storage failure
→ controlled storage/internal error
```

Прежнее поведение, при котором RAM помнила о когда-то существовавшем удалённом
JSON, сохранять не требуется. Post-`FINISHED` registry inspection из Stage 5/6/7
больше не считается обязательным продуктовым контрактом.

Macro 2 завершён и принят владельцем. `TaskRegistry` теперь владеет только
незавершённой live/recoverable работой, а `ResultRepository` — завершённой
историей. Успешно сохранённые задачи после подготовленного commit `FINISHED`
точно удаляются из registry; terminal cache и политики TTL/LRU не добавлены.
Ошибка persistence оставляет задачу live в `PERSISTENCE`, а unsafe/deferred
cleanup — live/recoverable.

Terminal preparation завершается до persistence; после успешного `save()`
атомарно применяются подготовленный `FINISHED` и exact eviction. Repository-backed
чтения, включая fast-submit после быстрого eviction, сохраняют корректное
поведение, idle worker больше не удерживает завершённую задачу, а полная безопасная
проекция status errors сохранена. Owner review, независимый аудит и focused
remediation re-audits завершены; финальный независимый вердикт — **PASS**.

## Macro 3 — Analyzer Registration Normalization — DONE / owner accepted

Цель — сделать добавление собственных built-in анализаторов контролируемым и
локализованным.

**OWNER DECISION:** Stage 11 не вводит third-party plugin system, внешний plugin
loader, каталог `mods`, динамическую загрузку стороннего Python, plugin
marketplace/API или внешнюю расширяемость анализаторов. Все анализаторы остаются
first-party компонентами FakeDetector, которые разрабатываются, проверяются,
тестируются и поставляются вместе с продуктом.

Macro 3 завершён и принят владельцем. Один authoritative static internal catalog
теперь определяет production built-in анализаторы и остаётся закрытым доверенным
first-party каталогом. Plugin API, dynamic discovery и third-party loading не
введены.

В каталоге централизованы identity, version, media, factory, typed settings,
preprocessing requirements и trusted result-contract metadata. Runtime registry,
worker resolution, Stage 5 completeness и Stage 6 validation получают
соответствующие представления из нормализованного каталога. Порядок выполнения
по-прежнему определяется порядком конфигурации, а Stage 7 completeness использует
точный validated active analyzer plan.

Import-time construction production analyzer instances удалён. Согласованность
конкретной реализации с каталогом и worker-side validation созданного экземпляра
остаются обязательными. Алгоритмы анализаторов, публичные схемы,
API/config/CLI-контракты и семантика риска не изменены.

Implementation self-review, owner review, independent audit, remediation
`M3-AUD-001` и focused independent re-audit завершены; финальный независимый
вердикт — **PASS**.

## Macro 4 — Product Naming & Architecture Normalization — DONE / owner accepted

Macro 4 завершён, реализация закоммичена и принята владельцем. Текущие
production-модули реализации lifecycle переименованы из имён этапов разработки
в имена по ответственности; это внутренняя архитектурная нормализация, а не
ребрендинг продукта или изменение публичных контрактов.

Выполненные переименования:

```text
_stage5_resources.py → _generated_artifact_budget.py
lifecycle/_stage5.py → lifecycle/_analysis_execution.py
lifecycle/_stage6.py → lifecycle/_finding_formation.py
lifecycle/_stage7.py → lifecycle/_assessment.py
Stage5ExecutionService → AnalysisExecutionService
Stage6FindingService → FindingFormationService
Stage7AssessmentService → AnalysisAssessmentService
```

Связанные private transport/resource symbols также получили семантические
имена. A03 закрыт: общий mapping HTTP-статуса терминального исхода intake
перенесён в нейтральный внутренний `_http_status.py`. API и WebUI используют
одну HTTP-политику; WebUI больше не зависит от реализации API adapter.

Внешне наблюдаемые compatibility identifiers, включая `stage5_resource_limit`,
сохранены. Lifecycle state/data contracts `Stage5TaskData`, `Stage6TaskData` и
`Stage7TaskData` намеренно оставлены без переименования. Package name, CLI,
переменные окружения, analyzer IDs, схемы, API routes, формат сохранённого
результата, версия, auth, risk/completeness и lifecycle-поведение не изменены.
Compatibility shims, plugin architecture и новые зависимости не добавлены.
Исторические Stage-ссылки сохранены; `PROJECT.md` и `CONTRACTS.md` были точечно
синхронизированы в implementation commit.

Самопроверка реализации, полный просмотр diff владельцем и независимый
архитектурный/regression-аудит GPT-6 Astra Low завершены. Независимый аудит
подтвердил семантическую/AST-эквивалентность и импорты из установленного wheel;
финальный независимый вердикт — **PASS**. Итоговая валидация реализации:
`1848 passed, 17 skipped`, покрытие `90%`; lock, Ruff, mypy, pre-commit,
diff-check и CLI — `PASS`.

На момент закрытия Macro 4 Stage 11 оставался `IN_PROGRESS`; следующей задачей
был Macro 5, Technical Debt / Config / Test-Support Cleanup.

## Macro 5 — Technical Debt / Config / Test-Support Cleanup — DONE / owner accepted

Macro 5 реализован, закоммичен, принят владельцем и прошёл независимый аудит.
Точечная нормализация технического долга завершена:

- **TD01:** удалён подтверждённо мёртвый `_ALLOWED_MIME_TYPES`; поведение
  поддерживаемых MIME, форматов и сигнатур сохранено.
- **TD02:** поля и имена схемы `1.0` сохранены;
  `error_handling.hide_internal_error_details` допускает только `true`,
  `external_systems.enabled` — только `false`. Ранее неактивные противоположные
  значения отклоняются при валидации конфигурации. Defaults, `schema_version`,
  поддерживаемый канонический JSON и идентичность config snapshot не изменены.
  Раскрытие внутренних исключений и внешние интеграции не добавлены.
- **TD03:** framework fake-анализаторы и fake worker definitions вынесены из
  production-пакета и каталога в `tests/support`, отсутствующий в wheel.
  Production-каталог содержит только прежние четыре доверенных first-party
  built-in анализатора и не разрешает и не выполняет `framework_test.*`.
  Узкий private resolver с явной инъекцией сохраняет реальные Windows-spawn
  тесты. Plugin architecture, dynamic discovery, import-by-string, plugin entry
  points и управление resolver через конфигурацию не введены.

Сохранены analyzer IDs, версии, группы и production worker keys, закрытая
архитектура каталога Macro 3, имена по ответственности и HTTP-слои Macro 4,
поведение lifecycle/risk/completeness/persistence и публичные контракты
API/CLI/WebUI/result. Широкая очистка не выполнялась.

Целевая проверка реализации: `367 passed, 3 skipped`; независимый
целевой аудит: `295 passed`, без пропусков; полный набор тестов: `1864 passed,
17 skipped`, покрытие `90%`. Lock, Ruff, mypy, pre-commit, diff-check, CLI,
AST, canonical snapshot, pickle/spawn и installed-wheel checks — `PASS`.
Независимый аудит GPT-6 Astra Medium: финальный вердикт — **PASS**;
замечаний, требующих исправления, нет.

На момент закрытия Macro 5 Stage 11 оставался `IN_PROGRESS`; следующей задачей
был Macro 6, Tests / Comments / Documentation Normalization, тогда ещё не начатый.

## Macro 6 — Tests / Comments / Documentation Normalization — DONE / owner accepted

Macro 6 реализован, закоммичен, принят владельцем и прошёл независимый аудит.
Нормализация выполнена без изменения публичного поведения:

- Воспроизведён изолированный цикл `result_finalization → lifecycle →
  result_finalization`. Ненужный импорт `TerminalTaskFacts` во время выполнения
  перенесён под `TYPE_CHECKING`; оба порядка импорта проходят в свежих процессах
  Python. Документированный публичный Python-интерфейс не изменён; потребителей
  удалённого связывания во время выполнения или через рефлексию нет.
- Тестовые модули текущей реализации переименованы:
  `test_stage5_execution.py → test_analysis_execution.py`,
  `test_stage5_resources.py → test_generated_artifact_budget.py`,
  `test_stage7_assessment.py → test_analysis_assessment.py`.
  Восемь тестов владения артефактами, путей и очистки перенесены в
  `tests/test_workspace_artifacts.py` с сохранением 26 параметризованных случаев.
  Два AST-эквивалентных конфигурационных builder для intake объединены в
  `tests/support/intake.py`. Значимая логика, fixtures, assertions и параметризация
  сохранены; значимые тесты не удалены. Число собранных тестов выросло с 1881
  до 1883 только за счёт двух проверок порядка импортов в свежих процессах.
- Усилен реальный тест границы сохранения и живого реестра: в `PERSISTENCE`
  приоритет остаётся у `TaskRegistry`, получение результата ожидает завершения;
  после терминальной фиксации и удаления задачи авторитетным становится
  сохранённый результат `ResultRepository`.
- Текущие технические комментарии и docstrings production-кода нормализованы
  на английском по ответственности. Намеренные lifecycle Stage-контракты,
  совместимые имена, коды ошибок и исторические Stage/Increment-записи сохранены.
- Устаревшие текущие утверждения `PROJECT.md` и `CONTRACTS.md` сверены с
  production-архитектурой после Macros 1–5: закрытым каталогом четырёх анализаторов,
  исключительно тестовыми fake-анализаторами, обязанностями выполнения анализа,
  формирования признаков, оценки и финализации. Описания артефактов,
  предобработки и внешних систем синхронизированы; исторические записи сохранены.
- Финальный раздел `6. Команда агенту для продолжения разработки` удалён целиком,
  включая пояснение и блок инструкции. Definition of Done сохранён;
  связанного SVG не существовало.

Проверки реализации и аудита: изолированный `test_result_finalization.py` —
`15 passed`; целевой набор аудита — `286 passed, 1 skipped`; собрано `1883`
теста; полный набор — `1866 passed, 17 skipped`, покрытие `90%`.
`uv lock --check`, Ruff, mypy, pre-commit, `git diff --check`, CLI help и оба
порядка импортов в свежих процессах — `PASS`. Независимый аудит GPT-6 Astra Low:
финальный вердикт — **PASS**, замечаний, требующих исправления, нет.

На момент закрытия Macro 6 Stage 11 оставался `IN_PROGRESS`; следующей задачей
был Macro 7, Release Tooling Normalization (`NOT_STARTED / next action`).
Работы Macro 7 и Macro 8 тогда не были начаты.

## Macro 7 — Release Tooling Normalization — DONE / owner accepted

Нормализация release tooling завершена и принята владельцем. Полный diff
проверен владельцем — `PASS`; независимый аудит GPT-6 Astra Medium — `PASS`,
замечаний, требующих исправления, нет (`BLOCKER 0`, `HIGH 0`, `MEDIUM 0`, `LOW 0`).
Реализация зафиксирована в commit `abe8270e967470d12b4bed25e690f264e9b52849`.

В Macro 7 выполнены семантические переименования:

- `generate_stage10_demo_media.py` → `generate_release_demo_media.py`;
- `verify_stage10_package.py` → `verify_release_package.py`;
- `verify_stage10_release.py` → `verify_release.py`.

Текущие тесты release tooling также получили имена по ответственности.
Совместимые обёртки не оставлены: поддерживаемого внешнего контракта,
требующего старых имён файлов, не обнаружено. Прежний verifier размером около
2207 строк существенно декомпозирован: `scripts/verify_release.py` стал
высокоуровневым координатором, а реализация вынесена в закрытый пакет
`scripts/release_tooling/` с модулями `common`, `build`, `kit`, `environment`,
`demo`, `transport`, `server`, `probes`, `reporting`. Граф зависимостей ацикличен;
закрытые модули не импортируют координатор, инструменты остаются вне runtime
пакета продукта. Описание ответственности модулей — в `PROJECT.md`, §16.2.1.

Сохранены сертификационные гарантии:

- strict требует чистого дерева tracked и untracked файлов; development явно
  не сертифицирует; проверяются стабильность HEAD и source status, контракт
  хоста Windows 11 x64 workstation / Python 3.12;
- source → sdist → wheel из этого точного sdist; runtime constraints механически
  экспортируются из `uv.lock`; проверяются точный состав release kit,
  manifest schema `1.0`, SHA-256, безопасные ZIP validation и extraction;
- свежее внешнее venv, установка из точного проверенного извлечённого wheel,
  provenance установленного пакета, изоляция от checkout и равенство runtime
  dependencies;
- реальный установленный CLI, HTTP-проверки API/WebUI, анализ image/audio/video,
  persistence, получение прежних результатов после restart, cleanup,
  graceful shutdown и завершение принадлежащих проверке процессов;
- безопасное сокрытие секретов и итоговые проверки целостности исходного дерева
  и release kit.

Устранён узкий пробел владения процессом: если startup завершается исключением
после создания сервера, но до передачи владения координатору, обработка
`BaseException` завершает принадлежащий проверке процесс. Покрыты `RuntimeError`,
`KeyboardInterrupt`, `SystemExit`, `BaseException`, первоначальный и повторный
startup, эскалация terminate → bounded wait → kill. Двойного cleanup/reap не
обнаружено. Это усиление безопасности tooling, а не изменение поведения продукта.

Результаты проверок реализации: baseline — `1883 collected`,
`1866 passed, 17 skipped`, покрытие `90%`; итог — `1906 collected`,
`1889 passed, 17 skipped`, покрытие `90%`. Добавлены `23` граничных случая
release tooling. Целевые наборы: release demo handoff — `8 passed`, release
packaging — `4 passed`, release verification — `29 passed`, release tooling
boundaries — `23 passed`. Полный quality barrier: `uv lock --check`, Ruff,
mypy, pytest, pre-commit, `git diff --check`, product CLI help — `PASS`.

Строгая проверка после implementation commit командой
`uv run python scripts/verify_release.py` — `PASS`:
`overall_status=passed`, `certification_mode=strict`, `certified=true`,
`source_sha_stable=true`, `source_tree_clean=true`. SHA в начале и конце —
`abe8270e967470d12b4bed25e690f264e9b52849`; source status в начале и конце пуст.
Release gate не изменил состояние репозитория. Подтверждено:

- создан sdist, wheel собран из него, проверен точный wheel;
- release kit содержит ровно 8 файлов; manifest и ZIP проверены, имена членов
  безопасны, извлечение чистое, хэши совпали;
- создано свежее внешнее venv, установлен wheel из проверенного ZIP;
  editable install — `false`, checkout отсутствует в `sys.path`, сравнение
  зависимостей — `25/25`, установленных dev-only зависимостей нет;
- сгенерированы demo image/audio/video, запущен реальный установленный CLI
  server, проверены API/WebUI; анализ всех трёх типов завершён, canonical
  persistence подтверждён; после restart получены все четыре прежних результата,
  WebUI отобразил прежний результат;
- workspaces и остатки quarantine отсутствуют, demo media ограничены своим
  каталогом; два принадлежащих проверке серверных процесса завершены, listeners
  закрыты, широкая системная очистка не применялась;
- graceful shutdown через Windows `CTRL_BREAK_EVENT` подтверждён кодом возврата
  `3` и lifecycle shutdown markers.

Поведение runtime продукта не изменилось: API routes/schemas, WebUI behavior/auth,
config schema, persisted result schema, lifecycle, analyzers,
risk/completeness/recommendation, зависимости продукта и `uv.lock` сохранены.

На момент закрытия Macro 7 Stage 11 оставался `IN_PROGRESS`; Macro 8 имел статус
`NOT_STARTED / next action`. Строгая сертификация tooling Macro 7 не заменяла
финальную whole-project сертификацию Stage 11 / Macro 8; решение по Graphify
тогда было отложено.

## Macro 8 — Final Whole-Project Audit / Certification / Graphify Review — DONE / owner accepted

Macro 8 завершён и принят владельцем. Первоначальный whole-project audit дал
вердикт `REMEDIATE`: `M8-A01 MEDIUM`, `M8-A02 MEDIUM`, `M8-A03 LOW`, `M8-A04 LOW`.
Ограниченная ремедиация в commit
`0167f78e2ab18a7b297807e9cb3fa19f69b6a7ec` закрыла все четыре замечания:

| Finding | Статус | Исправление |
|---|---|---|
| M8-A01 — MEDIUM | CLOSED | Проверка provenance sdist отклоняет untracked, ignored и локально сгенерированное содержимое по принципу fail-closed; Graphify исключён из принимаемого sdist. |
| M8-A02 — MEDIUM | CLOSED | Владение сырым процессом release-server начинается сразу после `Popen`; при ошибках `BaseException` в создании wrapper/reader процесс завершается с обязательным ожиданием его выхода (reap). |
| M8-A03 — LOW | CLOSED | Глубокая рекурсия YAML преобразуется в безопасный `ConfigurationError`; CLI возвращает `2` без traceback и запуска сервера. |
| M8-A04 — LOW | CLOSED | Два неуместных текущих имени с хронологической Stage-терминологией заменены семантическими именами по ответственности. |

Проверка полного diff владельцем — `PASS`; независимый целевой повторный аудит
GPT-6 Astra High — `PASS`; strict clean-SHA certification — `PASS`; финальная
независимая проверка закрытия GPT-6 Astra High — `PASS`.
`STAGE_11_CLOSURE_RECOMMENDATION=YES`; все M8 findings — `CLOSED`.
Осталось замечаний, требующих исправления: `BLOCKER 0`, `HIGH 0`, `MEDIUM 0`,
`LOW 0`. `CURRENT_ARCHITECTURE_RESIDUE=0`; гарантии MVP A–R — `PASS`.

### Финальные результаты проверок

Итоговый набор: `1944 collected`, `1927 passed`, `17 skipped`, покрытие `90%`.
Полный quality barrier — `PASS`: `uv lock --check`, Ruff, mypy
(`65 source files`), pytest, pre-commit, `git diff --check`, product CLI help.
Целевые наборы: release packaging — `18 passed`, release verification —
`29 passed`, release tooling boundaries — `44 passed`, config / CLI / main —
`112 passed`.

Строгая сертификация командой `uv run python scripts/verify_release.py` на commit
`0167f78e2ab18a7b297807e9cb3fa19f69b6a7ec` завершилась с
`overall_status=passed`, `certification_mode=strict`, `certified=true`,
`source_sha_stable=true`, `source_tree_clean=true`. SHA в начале и конце совпал
с этим commit; source status в начале и конце пуст. Release gate не изменил
состояние репозитория. Подтверждены:

- состав sdist: `177` записей = `176` tracked файлов репозитория + корневой
  `PKG-INFO`; принятых Graphify entries — `0`; provenance и хэши исходников
  проверены, wheel собран из этого точного проверенного sdist;
- точный release kit из `8` файлов, manifest schema `1.0`, целостность SHA-256,
  безопасные проверка и извлечение ZIP;
- свежее внешнее venv, установка из точного извлечённого wheel;
  editable install — `false`, checkout отсутствует в `sys.path`, runtime
  dependencies — `25/25`, dev-only зависимости отсутствуют;
- реальный установленный CLI, реальные API и WebUI, анализ image/audio/video,
  canonical persistence и получение прежних результатов после restart — `4/4`;
- успешная очистка, завершение и reap двух собственных процессов, закрытые
  listeners; graceful Windows `CTRL_BREAK_EVENT`, ожидаемый return code `3`;
  широкая системная очистка не применялась.

Это предоставленные финальные технические результаты до документационного
закрытия. После commit документации владелец выполнит финальную строгую
сертификацию на новом чистом SHA.

### Graphify — принятая владельцем REBUILD_POLICY

Финальная рекомендация `GRAPHIFY_RECOMMENDATION=REBUILD_POLICY` была принята
владельцем при закрытии Stage 11. Нормативные правила перенесены в
`../AGENTS.md`, раздел «Graphify — REBUILD_POLICY». На момент закрытия Stage 11
локальный граф был `STALE`, пересборка в том проходе не выполнялась;
свидетельства последующей пересборки Macro 1 приведены в M1-H.

## Гарантии MVP, обязательные к сохранению

Финальная проверка Macro 8 подтвердила `PASS` для всех гарантий A–R
(ниже перечислены в том же порядке):

- единый `AnalysisApplicationService` для API и WebUI;
- immutable config snapshot;
- различие status/stage/completeness/risk;
- detached/canonical reads;
- exactly-once execution и terminal settlement;
- cleanup safety barriers;
- порядок `FACT_READY → PERSISTENCE → save → FINISHED`;
- live precedence, пока работа не завершена;
- canonical persisted result после завершения;
- atomic result write и identity validation;
- bounded worker protocol;
- trusted/closed analyzer catalog;
- subprocess/artifact/finding safety budgets;
- correlation handling без двойного учёта;
- запрет fake calibrated probability claims;
- safe diagnostics;
- installed-wheel release guarantees;
- negative failure-path tests.

Этот список фиксирует границы Stage 11 и не заменяет подробные контракты в
`CONTRACTS.md`.

## Критерий завершения

Критерий выполнен: Stage 11 — **DONE / CLOSED**, Macros 0–8 —
**DONE / owner accepted**; текущего Macro нет. Основания закрытия:
post-MVP whole-project audit, нормализация Macros 1–7, финальный аудит Macro 8,
ограниченная ремедиация и независимый целевой повторный аудит, полный quality
barrier и строгая сертификация установленного артефакта. Финальная проверка
GPT-6 Astra High — `PASS`, рекомендация закрыть Stage 11 — `YES`.
Замечаний, требующих исправления, осталось `0`;
`CURRENT_ARCHITECTURE_RESIDUE=0` (неуместных текущих архитектурных имён с историей
Stage нет); гарантии MVP A–R — `PASS`. Принята политика Graphify `REBUILD_POLICY`.

---

# Stage 12 — Analyzer Expansion, Licensing & Product Validation — IN_PROGRESS

## Цель и границы

Расширить набор анализаторов до разнообразного объяснимого набора
детерминированных/классических проверок изображений, аудио и видео. Центр этапа —
анализаторы; предобработка, лицензирование, WebUI, продуктовая проверка и поставка
служат этой цели. Принятые архитектурные ограничения находятся в `PROJECT.md`
§20.1–20.2; интерфейсы и точная семантика результата — в `CONTRACTS.md`.

Текущий подтверждённый production-каталог содержит ровно пять анализаторов
(`src/fakedetector/analyzers/_catalog.py`):

- `image_metadata_consistency@1.0.0`;
- `image_copy_move_correspondence@1.0.0`;
- `image_jpeg_double_quantization@1.0.0`;
- `audio_pcm_quality@1.0.0`;
- `video_sampled_frame_quality@1.0.0`.

Macro 0 не изменяет этот каталог, предобработку, WebUI или локализацию.
В Pass 2 разрешены только лицензионные metadata, включение LICENSE в поставку
и соответствующие release-тесты; публикация не выполняется.
Stage 12 не реализует ML и не добавляет ML runtime,
веса, GPU-требования или загрузки моделей; исследовательский каталог ML
допустим, реализация отложена в Stage 13+. Калибровка вероятности, новая
инфраструктура и интеграции не становятся частью этапа автоматически.

<a id="diploma-sprint1"></a>
## Дипломный analyzer expansion — Sprint 1, 2026-10-12

**OWNER ACCEPTED / MERGED**, PR #70, merge commit main `97b1f0b`, задание
`STAGE12-DIPLOMA-ANALYZER-EXPANSION-SPRINT1`, baseline
`fff73dd6415610b02bf36e6511c1a99094f98865`, рабочая ветка
`feat/stage12-diploma-analyzer-expansion-sprint1`.
Отдельным owner authorization разрешён experimental tier и этот implementation
sprint, без ожидания production/core promotion и без переоткрытия Macro 2/3.
Научные dispositions, VRC G5 DEFER, Stage A engineering fail и запрет Stage B
сохранены. Исторические ограничения runtime ниже относятся к прежним задачам;
нынешнее узкое исключение — [METHODS, experimental tier](METHODS.md#diploma-experimental).

Реализованы **9 новых runtime IDs**: ATD, ASC, ARC — `EXPERIMENTAL`;
ABN, image noise/resampling, video repeated content/visual discontinuity/timing —
`EXPERIMENTAL_WEAK`. Точные IDs и спецификации находятся в METHODS.
Пять CORE алгоритмов/версий не менялись. Runtime получает общий закрытый каталог;
новые методы включаются существующими списками ID и используют штатный worker.
Новых зависимостей, public/config schema fields, Findings, risk fusion и ML нет.
`config/config.diploma.yaml` включает все 14 методов и `include_raw_metrics=true`;
исторический config/Profile B сохранён. WebUI показывает результаты без Findings.

Triage: ATD/ASC/ABN/timing — EASY; noise/resampling/VRC/visual — MEDIUM;
ARC — HARD, реализован после остальных с переиспользованием frozen-v2 арифметики;
thumbnail — **DEFERRED_FROM_SPRINT**: нет bounded embedded-thumbnail producer,
descriptor/binding и безопасного nested decode в preprocessing. Псевдоминиатюры
не создавались. VCM-FRAME-1 не включён в этот sprint; прежний INACTIVE сохранён.

Инженерные свидетельства: focused unit/worker tests, synthetic positive/control,
применимость, nonfinite/malformed input, caps и сквозной diploma API/WebUI тест
с реальными preprocessing, persistence и cleanup. Полный итог проверок и
SHA-256 review seal — во внешнем bundle
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\DIPLOMA-analyzer-expansion-sprint1`.
Это development verification dirty tree, **не strict certification**.
Graphify не пересобран, его provenance `625b9e83…` — STALE.

Владелец подтвердил приёмку и merge PR #70 в задании следующего sprint.
Этот факт закрывает review реализации analyzer expansion, но не Stage 12
или Macro 4/5/10. Следующая весовая модель разрешена отдельным заданием ниже;
новая исследовательская кампания автоматически не начинается.

<a id="diploma-ensemble-sprint1"></a>
## Дипломный ансамбль — Sprint 1, 2026-10-13

**OWNER ACCEPTED / MERGED**, PR #71, main baseline `4459e79`, задание
`STAGE12-DIPLOMA-ENSEMBLE-SPRINT1`; baseline `97b1f0b156cfc2162c942ae5f221389dd6629609`,
ветка `feat/stage12-diploma-ensemble-sprint1`, исходное дерево чистое.
Owner gate закрыт для реализации эвристической нормализации, начальных весов,
семейств, ограниченной агрегации, переключения diploma config и небольших
изменений WebUI. Приёмка и merge подтверждены владельцем в задании
`STAGE12-DIPLOMA-DEMO-EVALUATION-SPRINT1`.

По вердикту `REMEDIATE` и явному разрешению владельца применено узкое исправление
`STAGE12-DIPLOMA-ENSEMBLE-SPRINT1-R1`: итоговая нормализация использует каноническую
ёмкость типа медиа. Baseline R1 — тот же HEAD и ожидаемые 11 unstaged tracked-файлов
реализации Sprint 1, без untracked. Нормализаторы, семейства, веса, коэффициенты
семейной агрегации и пороги сохранены. Обновлённый diff R1 принят в составе PR #71.

Реализован `diploma_ensemble_v1@0.1.0` в существующем assessment layer: все 14
анализаторов имеют определённую обработку, 12 семейств (четыре на media type),
фиксированная каноническая ёмкость типа медиа и объяснение вкладов. Спецификация —
[PROJECT](PROJECT.md#diploma-ensemble), таблица нормализации —
[METHODS](METHODS.md#diploma-ensemble-normalization). `score_model_v1` и default
config сохранены, экспериментальные методы остаются measurement-only.
Публичные/config схемы, зависимости, preprocessing и analyzer implementations
не менялись. Вероятность не рассчитывается; critical override не расширен.

Проверки охватывают арифметику, все 14 ID, ATD/ASC correlation control,
повреждённые/неопределённые метрики, полноту и регрессию исторической политики.
R1 дополнительно проверяет ёмкости, максимум 100/HIGH для всех типов медиа
и отсутствие усиления оставшихся откликов при недоступных свидетельствах.
Сквозные image/audio/video пути используют реальные preprocessing и workers,
сохраняют ensemble score, возвращают тот же JSON через API, показывают summary
и explanation в WebUI, завершают cleanup. Отдельные synthetic oracles
проверяют существующие outputs девяти experimental методов. Итоги focused
tests и `uv run poe check`, полный diff, inventory и SHA-256 seal находятся в
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\DIPLOMA-ensemble-sprint1`.
Проверки из dirty tree — development verification, **не strict certification**.
Graphify остаётся STALE (`625b9e83…`); пересборка в этом задании не выполнялась.

После приёмки PR #71 следующий отдельный инкремент — Diploma Finish ниже.
Stage 12 и Macro 4 остаются IN_PROGRESS;
закрытие Macro 6/7, научная приёмка методов, корпусная калибровка и Stage B
этим sprint не заявляются.

<a id="diploma-demo-evaluation-sprint1"></a>
## Diploma Finish — контролируемая демонстрационная оценка, Sprint 1, 2026-10-13

**OWNER ACCEPTED / MERGED**, PR #72, main baseline `bc30188`; задание
`STAGE12-DIPLOMA-DEMO-EVALUATION-SPRINT1`; чистый baseline
`4459e795b8d784a4e683487c0d5b3f8e155b8bce`, ветка
`feat/stage12-diploma-demo-evaluation-sprint1`.
PR #70 (14 runtime analyzers) и PR #71 (дипломный ансамбль с R1 capacity
normalization) — **OWNER ACCEPTED / MERGED**, согласно текущему заданию владельца.

Scope: детерминированный first-party корпус, внешний manifest и результаты,
FILE_LEVEL_E2E через штатный intake, парные сравнения, раздельные observation /
holdout отчёты, шесть демонстрационных случаев и русский исследовательский текст.
`calibration_observation` — название split, не разрешение настройки модели.
Ансамбль `diploma_ensemble_v1@0.1.0`, его веса, normalizers, семейства, ёмкости,
пороги и probability=null заморожены до оценки. Новых методов, зависимостей,
public/config schema fields и медиа в Git нет.

Подготовлен `scripts/diploma_demo_evaluation.py` с командами generate/evaluate/report
и [русский отчёт](research/2026-10-13-diploma-demo-evaluation.md).
Финальный корпус: 40 файлов (14 image / 14 audio / 12 video),
10 control / 16 manipulated / 14 confound_control;
28 calibration_observation / 12 holdout_demo. Две генерации побайтно совпали.
Все 40 FILE_LEVEL_E2E прошли штатные intake/preprocessing/workers/persistence/cleanup;
COMPONENT_LEVEL=0. Наблюдаются 14/14 анализаторов и 12/12 семейств.
Сохранены все результаты, парные дельты, девять elevated controls, четыре слабых
целевых преобразования и шесть holdout-сценариев live demo.
Рекомендация — **NEED_MORE_DATA**; модель после результатов не менялась.

Focused tests: **245 passed**. `uv run poe check` выполнен один раз:
pre-commit и mypy PASS, pytest **3068 passed / 17 skipped / 1 failed**.
Единственный fail — `test_sdist_wheel_metadata_entry_point_and_resources`:
sdist provenance отвергает intended untracked-файлы. Read-only сверка архива
подтвердила ровно три таких новых файла, без иных лишних/пропущенных членов,
дубликатов или расхождений байтов. **OWNER_VERIFY_REQUIRED**, guard не ослаблен,
staging не выполнялся. CLI smoke выполнен отдельно — PASS; Ruff новых файлов
и `git diff --check` — PASS. Это development verification, не strict certification.
Полный diff, новые файлы целиком, manifest, таблицы, логи и SHA-256 seal —
во внешнем review bundle `DIPLOMA-demo-evaluation-sprint1`.

История Macro 4, VRC G5 DEFER и запрет Stage B сохранены. Этот инкремент не
закрывает Stage 12, Macro 8, научную валидацию или production-калибровку.
Приёмка и merge PR #72 подтверждены владельцем в задании
`STAGE12-DIPLOMA-BENIGN-VALIDATION-SPRINT1`. Приведённые выше результаты
проверок отражают историю агентской реализации до staging владельцем,
не текущую сертификацию baseline. Следующий инкремент — benign-валидация ниже;
любые изменения калибровки требуют отдельного задания.

<a id="diploma-benign-validation-sprint1"></a>
## Diploma Finish — независимая benign-валидация, Sprint 1, 2026-10-13

**DONE / OWNER ACCEPTED / MERGED — PR #73**, подтверждено владельцем
в задании VRC targeted research от 2026-10-14. Исходное задание
`STAGE12-DIPLOMA-BENIGN-VALIDATION-SPRINT1`; чистый baseline
`bc301888281fdc6954b70c267c33354c12c1b39f`, ветка
`feat/stage12-diploma-benign-validation-sprint1`.
PR #70, #71 и #72 — **OWNER ACCEPTED / MERGED** по подтверждению владельца.

Отдельный `scripts/diploma_benign_validation.py`: объявление лицензированных
источников, ограниченная загрузка, детерминированная подготовка, E2E и отчёт.
Источник происхождения/лицензий —
[REFERENCES](REFERENCES.md#diploma-benign-validation-sources),
методика и результаты — [русский отчёт](research/2026-10-13-diploma-benign-validation.md).
Новых production методов, зависимостей, public/config schemas и медиа в Git нет.
`diploma_ensemble_v1@0.1.0` и полный source/config/lock fingerprint сохранены.

Корпус: 32 файла, 8 audio + 8 video source families (по 16 файлов/media),
16 BENIGN_REFERENCE / 12 BENIGN_PROCESSING / 4 BENIGN_CONFOUND.
Объём оригиналов 95 575 335 bytes; лицензии CC BY 3.0, CC BY-SA 3.0/4.0, CC0.
Source-family split закреплён до оценки: 20 observation / 12 holdout_benign.
Две подготовки дали побайтное совпадение всех 32 файлов.
FILE_LEVEL_E2E=32 / COMPONENT_LEVEL=0: все completed/complete/cleanup completed,
все 5 audio и 4 video анализатора наблюдались, один ABN insufficient_evidence.

Аудио: LOW/MEDIUM/HIGH=0/16/0, score>25 у 16/16 файлов и 8/8 семейств;
HIGH нет. Видео: 16/0/0, VRC≥0.75 у 16/16 файлов и 8/8 семейств,
median=0.997052, p75=0.998907. CORE video_quality=0 везде, поэтому
Pearson/Spearman undefined; совместных ненулевых responses 0/16.
Это не FPR/accuracy и не доказательство независимости семейств.
**PRIMARY_DECISION: TARGETED_RESEARCH_REQUIRED** — насыщение VRC на benign
материале требует отдельного исследования масштаба/выбора экстремума;
численная remediation не обоснована, настройка модели не выполнялась.

Исторические проверки до staging/приёмки PR #73: focused tests — **271 passed**,
2 targeted follow-up checks PASS. Единственный
`uv run poe check`: pre-commit/mypy PASS; pytest **3094 passed / 17 skipped / 1 failed**.
Fail только sdist provenance для трёх intended untracked-файлов, read-only
сверка архива не выявила иных нарушений. **OWNER_VERIFY_REQUIRED**; release
guard не менялся, staging не выполнялся. CLI smoke отдельно PASS, Ruff и
`git diff --check` PASS. Полные свидетельства, новые файлы целиком и SHA-256 seal —
review bundle `DIPLOMA-benign-validation-sprint1`. После review/staging владельцем
требуется повтор quality barrier.
Это development verification, не strict certification. Git mutations отсутствуют.
Stage 12 и Macro 4 остаются IN_PROGRESS; VRC G5 DEFER и запрет Stage B сохранены.
На завершение исполнения следующим gate был owner review полного diff,
manifests, таблиц и ограничений; принятие PR #73 подтверждено выше.
Последующее целевое исследование VRC отдельно разрешено владельцем 2026-10-14.

<a id="diploma-vrc-targeted-research-sprint1"></a>
## Diploma Finish — VRC targeted research, Sprint 1, 2026-10-14

**DONE / OWNER ACCEPTED / MERGED — PR #74**, подтверждено владельцем
в задании VRC redesign research. Исходное задание
`STAGE12-DIPLOMA-VRC-TARGETED-RESEARCH-SPRINT1`, чистый baseline
`c32de18326f020b3bc362dc5eff47042376616cb`, ветка
`feat/stage12-vrc-targeted-research-sprint1`. PR #70, #71, #72 и #73 —
**OWNER ACCEPTED / MERGED** по подтверждению владельца.

Разрешены только component-level исследования VRC на замороженных видео,
matched distant-repeat probes, focused tests и
[русский отчёт](research/2026-10-14-vrc-targeted-research.md).
Production `video_repeated_content_correspondence@1.0.0`, профиль
`VRC-DENSE-DIPLOMA-1` и `diploma_ensemble_v1@0.1.0` не меняются;
production-ready статус не присваивается. Stage 12 и Macro 4 — **IN_PROGRESS**.

Audio transition по наблюдениям PR #73 требует отдельного targeted sprint;
ATD/ASC и audio scoring не входят в текущую работу.

Исполнение research завершено: 16 frozen benign-video derivatives / 8 families,
8 matched reference + 8 distant-repeat probes, 12 старых diagnostic demo-видео.
Полное production `raw_metrics` воспроизведено для 28 исторических файлов;
максимальная ошибка current response — 0. Матрица из 5 gates × 10 pooling
diagnostics заморожена до outcomes; все 50 вариантов измеримы.
Расположение strongest T0: same-region 15/16, gap ≤0.5 s 15/16.
Benign median strongest: T0=0.997052, T4=0.993708; T4 ≥0.95 — 13/16.
Лучший описательный rank T3_GAP_2S__median даёт median=0.976271 и лишь
3/8 положительных paired deltas. **READY_FOR_PROTOTYPE: 0/50**;
исследовательская disposition — **VRC_REDESIGN_REQUIRED**.
Это не принятие production-изменения, не FPR/TPR и не новая FILE_LEVEL_E2E validation.

Focused tests — **103 passed**; независимый перерасчёт pair ledgers подтвердил
220 sample/gate rows, 400 paired deltas и 50 benign summaries.
Единственный полный `uv run poe check`: pre-commit/mypy PASS,
pytest **3118 passed / 17 skipped / 1 failed**, coverage 91%.
Fail только sdist provenance трёх intended untracked-файлов; read-only сверка
архива не выявила иных нарушений. **OWNER_VERIFY_REQUIRED**; guard сохранён,
staging запрещён заданием и не выполнялся. Ruff/focused mypy и CLI smoke PASS.
Это development verification, не strict certification; после review/staging
владельцу требуется повтор barrier.
Исторический owner review выполнялся по bundle `DIPLOMA-vrc-targeted-research-sprint1`;
приёмка PR #74 и `VRC_REDESIGN_REQUIRED` подтверждена владельцем в следующем задании.
Приведённые проверки относятся к агентской реализации до staging, не текущей
сертификации baseline. Следующий отдельно разрешённый redesign — ниже;
production implementation по-прежнему требует отдельного OWNER GATE.

<a id="diploma-vrc-redesign-research-sprint1"></a>
## Diploma Finish — VRC redesign research, Sprint 1, 2026-10-15

**IN_PROGRESS / IMPLEMENTED / OWNER REVIEW PENDING**, задание
`STAGE12-DIPLOMA-VRC-REDESIGN-RESEARCH-SPRINT1`, чистый baseline
`178434843521382fa905bb4d15b95ceb702fb693`, ветка
`feat/stage12-vrc-redesign-research-sprint1`. PR #70, #71, #72, #73 и #74 —
**OWNER ACCEPTED / MERGED** по подтверждению владельца.

Research-only harness `scripts/diploma_vrc_redesign_research.py` переиспользует
принятый dense producer и frozen inputs: 16 benign-видео / 8 source families,
8 matched reference + 8 distant-repeat derivatives и 12 demo-видео.
Новых загрузок, медиа в Git, dependencies и public/config schemas нет.
Полные production raw_metrics воспроизведены для 44/44 файлов; максимальная
ошибка response — 0; повторная pixel/PTS QA всех 8 copied episodes совпала.

Матрица 4 descriptors × 2 information policies × 3 run lengths × 2 relative
scores + 2 controls = 50 entries закреплена до outcomes. Selection использовал
только 5 observation families: 41/48 redesigned candidates прошли screen.
Выбран **D2__I25__K9__R10**, frozen до любых новых holdout outcomes.
На 3 holdout families вычислены только этот кандидат и production control;
переотбора и изменений формулы не было. Все 10 заданных prototype gates PASS:
combined benign median=0.037240, ≥0.75 — 0/16, repeat median=1,
paired positive=8/8, paired median Δ=0.966883.

Исследовательская disposition — **VRC2_METHOD_CANDIDATE_READY_FOR_PROTOTYPE**.
Это не production-ready метод и не принятие production-изменения.
Существенные ограничения сохранены: выбранный best run полностью внутри
известной копии только у 3/8 семейств (median допускает несовпадающие группы);
на demo 8/12 случаев имеют INSUFFICIENT_RUN_SUPPORT, включая distant repeat
и loop, ещё 1/12 static — INSUFFICIENT_LOW_INFORMATION. K9/I25 чувствителен
к cadence/доступной последовательной поддержке. Null не заменялся нулём.

Методика, полный observation ranking, holdout, family-level результаты,
demo и ограничения — [русский отчёт](research/2026-10-14-vrc-redesign-research.md).
Имя отчёта сохранено по заданию; фактическое выполнение — 2026-10-15.
Новые результаты — COMPONENT_LEVEL_RESEARCH, не FILE_LEVEL_E2E, FPR/TPR,
authenticity ground truth, probability или ensemble calibration.
1048 candidate/sample rows прошли точный численный replay; независимый
перерасчёт populations/scores и порядка фаз подтвердил результат.

Итоговые focused tests — 119 passed; Ruff, format и focused mypy PASS.
Единственный `uv run poe check`: pre-commit/mypy PASS; pytest — 3171 passed,
17 skipped, 1 failed, coverage 91%. Итог — OWNER_VERIFY_REQUIRED: единственный
fail связан с sdist provenance трёх intended untracked-файлов. Read-only проверка
фактического архива подтвердила полный набор 236 tracked файлов с точными bytes
и отсутствие иных лишних/пропущенных/изменённых members. Guard не ослаблен;
staging запрещён и не выполнялся. CLI smoke и `git diff --check` PASS.
Полные проверки и diff находятся во внешнем review bundle
`DIPLOMA-vrc-redesign-research-sprint1`; после review/staging владельцу нужен
повтор barrier. Это development verification, не strict certification;
owner acceptance ещё не получен.
Production VRC, VRC-DENSE-DIPLOMA-1, maturity EXPERIMENTAL_WEAK и
`diploma_ensemble_v1@0.1.0` остаются неизменными. VRC G5 DEFER и запрет исходного
Stage B сохранены; Stage 12 и Macro 4 — IN_PROGRESS.

Следующий gate — owner review, затем отдельное разрешение на прототип с явными
границами применимости, insufficiency и локализации. Пересмотр K/I25 требует
нового объявленного исследования, а не настройки по открытому holdout.
Audio transition остаётся отдельным targeted sprint; ATD/ASC/ARC/ABN и
audio ensemble behavior не меняются. Git mutations не выполнялись.

## Карта Macro и зависимости

| Macro | Название | Статус | Вход / результат и критерий перехода |
|---:|---|---|---|
| 0 | Stage Definition, Licensing & Third-Party Policy | DONE / merged | План и политика оформлены; Apache-2.0 выбрана; лицензионная поставка и provenance проверены |
| 1 | Forensic Preprocessing Foundations | DONE / CLOSED / owner accepted | M1-A–M1-G и targeted remediation DONE / owner accepted / committed; M1-H DONE / PASS; actionable findings 0 |
| 2 | Image Analyzer Expansion — Wave 1 | DONE / CLOSED | Один новый production-анализатор DQ; остальные кандидаты research-only/deferred; M2-HR6 PASS / OWNER ACCEPTED; M2H-D01 → Macro 6 |
| 3 | Audio Analyzer Expansion — Wave 1 | DONE / CLOSED / OWNER ACCEPTED | M3-R1/R2A/R2B/R3A приняты владельцем; M3-R3B disposition принят, broad validation отложена; M3-R3C, M3-R3D-P/E/F приняты владельцем; M3-R3D-F confirmation MIXED (5/8 rescues); ARC research measurement demonstrated, production promotion и дальнейшее ARC retention development текущего Macro 3 DEFERRED; M3H-A01 deferred; M3-ATD-D1 DONE / OWNER ACCEPTED DISPOSITION, ATD RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED, carry-forward RESOLVED; M3-ASC-D1 DONE / OWNER ACCEPTED DISPOSITION, ASC RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED, carry-forward RESOLVED; все required carry-forward разрешены; M3-HYG-1 DONE / OWNER ACCEPTED, hygiene gate CLOSED; M3-CR1 DONE / OWNER ACCEPTED CLOSURE (2026-10-01); STRICTLY CERTIFIED по подтверждению владельца в M4-R1 (см. Macro 4); production audio-метод не принят |
| 4 | Video Analyzer Expansion — Wave 1 | IN_PROGRESS | M4-R2 VRC-DENSE-1 Stage A COMPLETE / SYNTHETIC_ONLY / OWNER ACCEPTED / COMPLETE WITH ENGINEERING FAIL (2026-10-12); G1 PASS, G2 FAIL, G3 PARTIAL, G4 NOT_EVALUATED_STAGE_A, G5 DEFER; Stage B BLOCKED / NOT AUTHORIZED; полный Stage A rerun NOT PLANNED; VCM-FRAME-1 TARGETED_RESEARCH / INACTIVE; production UNCHANGED / NO VRC PROMOTION; [закрытие Stage A](#video-m4r2-closeout) |
| 5 | Analyzer Wave 2 / Experimental Promotion | NOT_STARTED | После 2–4: обоснованный отбор второй волны, проверка экспериментальных методов и допуск в доверенный каталог |
| 6 | Correlation, Completeness & Result Semantics Review | NOT_STARTED | После 2–5: проверка выросшего набора без двойного учёта и завышения полноты; изменения дизайна только отдельным решением |
| 7 | WebUI Product Layer / Localization / Human-readable Results | NOT_STARTED | После 6: согласованное представление результата, RU/EN и проверка неизменности API/domain semantics |
| 8 | Real Corpus & Hands-on Product Acceptance | NOT_STARTED | После 5–7: корпус с проверенными правами, воспроизводимые измерения и формальная ручная приёмка |
| 9 | GitHub Release / Distribution | NOT_STARTED | После 0 и 8: проверенная поставка, лицензии/уведомления и отдельный шаг публикации владельцем |
| 10 | Final Whole-Stage Audit & Certification | NOT_STARTED | После 0–9: независимый аудит, закрытие замечаний, quality barrier, сертификация установленного артефакта и решение о закрытии Stage 12 |

Общая предобработка обязательно предшествует массовой реализации анализаторов.
Macro 2 и 3 технически опираются на 1, последовательность выше — план выполнения;
зависимости общих ядер уточняются при отборе методов. Подготовка критериев корпуса
может сопровождать волны, но не заменяет формальную приёмку Macro 8. Macro 6
не разрешает откладывать известный двойной учёт до конца волн: каждый новый метод
должен заранее описать семейство свидетельств и связь с текущей корреляцией.
Macro 9 не разрешает публикацию в Macro 0; любые Git mutations выполняет владелец.

## Macro 0 — DONE / merged

- [x] формально открыть Stage 12 и определить Macro 0–10;
- [x] записать принятые направление и границы в `PROJECT.md`;
- [x] разделить текущий каталог, исследовательские кандидаты и будущую реализацию;
- [x] оформить политику provenance, текущий аудит и сравнение лицензий в `REFERENCES.md`;
- [x] сохранить наблюдения ручного знакомства с продуктом в будущем backlog;
- [x] получить явный выбор лицензии проекта владельцем: Apache-2.0;
- [x] отдельным проходом оформить лицензию, metadata, README и стратегию
  сторонних уведомлений; проверить состав/ожидания release kit и при необходимости
  согласованно обновить их;
- [x] проверить согласованность, diff и относящиеся к этому проходу проверки,
  затем закрыть Macro 0.

Первый проход ограничивался документацией/политикой. В Pass 2 владелец выбрал
Apache-2.0; добавлены канонический `LICENSE`, SPDX metadata и обязательная лицензия
в составе kit. Проверяются реальные sdist/wheel, точный состав kit, хэши,
соответствующие release-тесты, diff и согласованность документов.
Отдельный пустой NOTICE не требуется; стратегия — в `REFERENCES.md`.
Полный набор тестов и пересборка Graphify не запускаются. Строгая сертификация
требует чистого tracked source tree и выполняется после Git-действий владельца.

Результаты Pass 2 до Git-действий владельца:

- `LICENSE` побайтово совпадает с официальным текстом Apache — `PASS`;
- сборка sdist и wheel из sdist, SPDX metadata и содержимое лицензии — `PASS`;
- фактическая сборка kit/ZIP, точный inventory, manifest-хэши и извлечение — `PASS`
  в несертифицирующей проверке;
- Ruff для изменённых Python-файлов и `git diff --check` — `PASS`;
- профильные `test_release_packaging.py`, `test_release_verification.py`,
  `test_release_tooling_boundaries.py`, `test_release_demo_handoff.py`:
  **98 passed, 1 failed**. Единственная остановка — существующий
  `_verify_sdist_provenance` отклоняет новый untracked `LICENSE`;
  проверка и её требование tracked source сохранены.

Финальный проход закрытия: владелец добавил только новый корневой `LICENSE`
в Git. Команда `uv run pytest -q tests/test_release_packaging.py
tests/test_release_verification.py` прошла: **47 passed**, включая ранее
остановившуюся проверку provenance. Начальный и итоговый `git diff --check` —
`PASS`. Ограничение проверки устранено; блокеров владельца нет. Macro 0 —
`DONE`; на момент этого прохода Stage 12 был `IN_PROGRESS`, Macro 1 — `NOT_STARTED`.
В финальном проходе изменён только `ROADMAP.md`; Git mutations агент не выполнял.
Строгая release certification на грязном source tree не запускалась.

## Исследовательский вход и отбор волн

Владелец передал достаточную для планирования сводку отдельного read-only
исследования: 20 image-, 14 audio-, 14 video-кандидатов и 23 темы ML для Stage 13+.
Полный отчёт в этот проход не приложен; числа — сведения из задания, а не
результат нового исследования Macro 0. Кандидаты намеренно пересекаются по
семействам свидетельств. Лицензионные ограничения Noiseprint и PhotoHolmes
зафиксированы отдельно в `REFERENCES.md` как исследовательские сведения.

Предложенный вход первой волны, **не утверждённые analyzer IDs/контракты или
обязательные пакеты реализации**:

| Направление | Рабочие названия кандидатов |
|---|---|
| Image / Macro 2 | `image_jpeg_double_quantization`, `image_jpeg_grid_consistency`, `image_noise_residual_consistency`, `image_resampling_consistency`, `image_embedded_thumbnail_consistency` |
| Audio / Macro 3 | `audio_temporal_discontinuity`, `audio_spectral_consistency`, `audio_background_noise_consistency`, `audio_repeated_segment_correspondence`, `audio_metadata_container_consistency` |
| Video / Macro 4 | `video_encoding_structure_consistency`, `video_timestamp_consistency`, `video_motion_consistency`, `video_audio_timing_consistency` |
| Расширение текущего / Macro 4 | усиление анализа повторов/замирания в ответственности `video_sampled_frame_quality`, без дублирующего анализатора |

Принятые методы оформляются в `METHODS.md` по его gate; источники и лицензии —
в `REFERENCES.md`. Research-материалы сами по себе не разрешают реализацию.
Перед каждой волной согласуются конкретные методы и IDs, входные представления,
CPU/resource budgets, применимость и ограничения, семейства свидетельств,
права на код/данные и критерии проверки. Для каждого допускаемого метода нужны
положительные, отрицательные, ложноположительные/challenge, граничные и
`not_applicable` случаи; отсутствие пригодного сигнала не доказывает подлинность.
Macro 5 продвигает только прошедшие эти критерии методы; остальные остаются
исследовательскими кандидатами с записанной причиной отсрочки.

## Macro 1 — общая криминалистическая предобработка — DONE / CLOSED / owner accepted

Исходные представления до Macro 1 описаны в `CONTRACTS.md` §7: нормализованный PNG,
16-bit PCM, необязательная спектрограмма и разреженные кадры с целевыми
временными отметками. Они не дают автоматически все факты для новых методов.
Macro 1 реализовал необходимые расширения до зависимых волн:

- исходные/native JPEG-факты и действительно исходные квантованные JPEG
  коэффициенты для анализа DCT/квантования; DCT нормализованного PNG не подменяет их;
- достоверное соответствие координат исходного и нормализованного изображения,
  включая ориентацию, и общие остаточные/фильтрующие вычисления;
- числовые STFT/оконные представления, а не только изображение спектрограммы;
- аудио с точностью исходника там, где проверяется подлинность разрядности:
  преобразованный 16-bit PCM не является доказательством исходной bit depth;
- измеренные PTS/DTS/time-base/frame-duration, ограниченные плотные окна
  последовательных видеокадров и соответствие video/audio timelines;
- общие image/audio forensic kernels для повторного использования в видео.

Для каждого расширения определить производителя и потребителей, сохранность
исходных фактов, формат внутренних данных, применимость, точность координат/
времени, лимиты, контролируемый доступ и очистку. Контрактные изменения
оформляются в задаче Macro 1 по мере необходимости, не придумываются в Macro 0.
Парсинг, ffprobe, STFT и декодирование не размножаются внутри анализаторов.

### Pass 1 — аудит и план реализации

Baseline: `a66295ed8a7165d078f714fe4f212675ea8fffdc`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, исходное рабочее дерево
чистое. В Pass 1 были сформулированы **предложения и критерии будущих задач**;
принятые позднее внутренние контракты M1-A находятся в `CONTRACTS.md` §7.5.
Реализация анализаторов, новая публичная схема и повышение текущих
лимитов этим проходом не разрешаются. Проверенные сведения о JPEG-кандидатах
и отдельном installed-wheel smoke находятся в `REFERENCES.md`.

Предлагается сохранить владельца подготовки `PreprocessingDispatcher` и
существующий путь `PreparedMedia → private worker transport → AnalyzerRequest`.
Небольшие immutable facts проходят строгую типизированную проекцию в существующую
metadata-границу; большие числовые данные — зарегистрированные артефакты с
ограниченными manifest и readers. Новые артефакты создаются только по объединённым
требованиям активного закрытого каталога. Residual/STFT kernels могут вычислять
числовые порции внутри существующего analyzer worker из этих представлений;
постоянно сохранять каждую производную матрицу не требуется.

### Решения владельца перед реализацией — RESOLVED

| Gate | Утверждённый выбор | Статус |
|---|---|---|
| G1 — native JPEG | `pyjpegio==0.3.0` в M1-B, bounded private child и preflight | APPROVED; зависимость не добавляется в M1-A |
| G2 — численные зависимости | NumPy/OpenCV, без SciPy | APPROVED |
| G3 — точность аудио | Hybrid: source/decoder facts + precision-preserving windows; старый PCM16 сохраняется | APPROVED |
| G4 — timing owner | Preprocessing с существующей bounded process boundary | APPROVED |
| G5 — контракты | Только внутренние типы/requirements/readers; public API/domain/YAML без изменений | APPROVED |

Условия решений и реализованные внутренние контракты находятся в
`CONTRACTS.md` §7.5. Таблица закрывает owner gates и не означает готовность B–F.

Выбор G1 не разрешает прямой вызов native decoder в родительском процессе,
передачу raw markers анализаторам или приём коэффициентов после предупреждений
декодера. У проверенного wheel выявлены soft recovery отсутствующего EOI и
ограничение Unicode absolute path; M1-B должен проверять строгий отказ и запуск
из controlled source workspace с существующим фиксированным ASCII-именем
`source`, без копирования исходника или изменения cwd родителя.

### Последовательность M1-A–M1-H

M1-A–M1-G и targeted remediation — `DONE / owner accepted / committed`.
M1-H — `DONE / PASS`: независимый аудит закрытия завершён, M1H-F01 и M1H-F02 —
`CLOSED`, замечаний к исправлению — **0**. Macro 1 — `DONE / CLOSED / owner accepted`.

| Increment | Зависимости | Проверяемый результат |
|---|---|---|
| M1-A — contracts/models/limits — DONE | Решения G1–G5 | Типизированные immutable facts, manifests и контракты будущих readers, applicability/coverage, source identity, пределы чисел/размеров; общий demand plan и бюджет до записи; уточнение внутренних контрактов без public schema expansion |
| M1-B — original image/JPEG — DONE | A, G1/G4 | Ограниченные исходные факты, EXIF mapping всех 8 ориентаций, native quantized coefficients и таблицы с component/table IDs; изолированный decoder, общее bounded stderr для строгой обработки warnings, Unicode workspace и installed-wheel smoke |
| M1-C — residual kernels — DONE | A, mapping из B | Небольшие собственные детерминированные residual/filter kernels с явными dtype, границами, halo и областью покрытия; без Noiseprint и копирования чужих ограниченных реализаций |
| M1-D — audio precision/STFT — DONE | A, G2/G3 | Source/decoded sample-format facts, точные sample indices и дополнительные окна; общий framing/window/rFFT/magnitude/power API, без чтения spectrogram PNG и без принудительного downmix/resample |
| M1-E — bounded timing — DONE | A/B, G4 | Типизированные stream/packet/frame facts, signed PTS/DTS и rational time base; bounded ffprobe и переиспользование общей sideband-границы из B для timing; без raw JSON в analyzer inputs |
| M1-F — dense windows/AV mapping — DONE | B/C/D/E | Ограниченные последовательные RGB frames и timing из одного decode; exact региональные audio packet/video frame endpoints и offsets, явные coverage/unknown states без глобальной continuity и precision audio/STFT demand |
| M1-G — integration/hardening — DONE | B–F | Совместные count/byte/CPU budgets, безопасная сериализация, timeout/overflow/crash/reap/cleanup matrix, существующие consumers без изменения поведения; sdist → wheel → внешняя runtime-среда без checkout и dev packages |
| M1-H — independent closure audit — DONE / PASS | G | Первичный аудит REMEDIATE; targeted remediation принята и закоммичена; финальный независимый повторный аудит PASS, M1H-F01/F02 CLOSED, actionable findings 0 |

Документационное закрытие Macro 1 завершено и merged; итоговый статус Macro 2 указан в §2.2.
A задаёт общие contracts/limits для B–F;
точные реализованные ограничения принадлежат `CONTRACTS.md` §7.5. Предложения
Pass 1 ниже сохраняются как исходные критерии выполненной проверки A/G, не production
sampling defaults и не новые YAML-поля.

Приведённые ниже отчёты M1-A–M1-G — исторические снимки на момент каждого
инкремента; последующие результаты закрытия зафиксированы в разделе M1-H.

### M1-A — internal contracts, demand plan, resource policy — DONE

Baseline: `5c8bf5d909478268eb91112fb90f286f09f4e4eb`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, рабочее дерево
перед реализацией чистое. Расширены существующие requirements/registry,
добавлены строгие immutable facts и bounded numeric descriptors, source/artifact
binding в текущей metadata-границе, EXIF edge/bbox mapping и арифметический JPEG
preflight с MCU-padding. Новые producers не реализованы; текущий каталог их
не запрашивает. Dependencies, public contracts и YAML не менялись.

Проверено 2026-09-21: focused tests (`test_stage5_internal_models.py`,
`test_analyzer_registry.py`, `test_preprocessing.py`) — **219 passed**.
Окончательный `uv run poe check` — **PASS**: pre-commit, mypy (65 source files),
pytest **2068 collected / 2051 passed / 17 skipped**, покрытие **90%**, CLI smoke.
Проверены итоговый diff, scope, отсутствие ненужных compatibility paths и новых
public exports; `git diff --check` — PASS. Release certification и пересборка
Graphify не запускались. Git mutations не выполнялись. M1-A завершён;
На момент этого инкремента Stage 12 и Macro 1 оставались `IN_PROGRESS`, owner blockers отсутствуют.

### M1-B — original image/JPEG — DONE

Baseline: `50d2fb77624193a99c9ab821582e39546d54bc44`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, начальное дерево чистое.
Выполнен утверждённый объём M1-B: original facts/EXIF, структурный JPEG preflight,
native coefficients по явному demand, bounded child, raw artifacts и immutable
reader. Thumbnail extraction/comparison и forensic conclusions не входят в это
задание и не реализованы. Текущие четыре analyzers и public contracts сохранены.
Точный внутренний контракт — `CONTRACTS.md` §7.5; provenance и измерения памяти —
`REFERENCES.md`, интеграция M1-B.

Проверено 2026-09-21:

- focused preprocessing/models/process/registry — **348 passed**;
- дополнительные 12 interruption/recovery cases — **PASS**; Windows stdlib
  process probes запускают реальный interpreter, исключая venv redirector;
- `uv run poe check` — **PASS**: pre-commit, mypy (65 source files), pytest
  **2137 collected / 2120 passed / 17 skipped**, покрытие **90%**, CLI smoke;
- `uv run python scripts/verify_release_package.py` — **PASS**: проверенный
  inventory/hash sdist → wheel, внешний CPython 3.12.10 venv, 26 runtime
  distributions точно соответствуют lock-derived constraints, dev packages
  отсутствуют, imports из site-packages, checkout отсутствует в sys.path;
- установленный wheel: progressive RGB 17×17, malformed missing EOI,
  over-limit SOF, Unicode workspace и cleanup — **PASS**;
- preflight spy подтверждает отсутствие native вызова при structural/resource
  rejection; 2047/2048/2049×2048 grayscale проверяют границу policy;
- safe warning/error/crash/timeout/protocol/overflow, partial artifact cleanup,
  source/artifact binding и запрет writable numeric buffer — **PASS**.

Измеренный peak working set дочернего процесса для трёх fixtures — около 66–75 MiB; это не
hard RAM quota. В M1-G остаются общий RSS/concurrency и native allocation risks,
а также strict clean committed-tree certification: эта проверка честно выполнена
на изменённом working tree (`source_tree_clean=false`). Provenance guards не
ослаблены. Git mutations и пересборка Graphify не выполнялись. Owner blockers
отсутствуют; на момент этого инкремента Stage 12 и Macro 1 оставались `IN_PROGRESS`. Следующим increment был M1-C.

### M1-C — shared deterministic image residual kernels — DONE

Baseline: `23070b84dc322adf42d5cdbe56970fdcf538baa8`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, начальное дерево чистое.
Добавлен один private NumPy-слой для bounded tiles, BT.601 luminance, binomial
smoothing 3×3/5×5, high-pass residual, центральных конечных разностей и robust
local statistics. Tile boundary использует фиксированный `REFLECT_101`; kernel
outputs покрывают ровно core, RGBA alpha не участвует в сигнале. Все числовые
результаты — finite immutable little-endian float64 с `bytes` backing. Точный
numeric/resource contract находится в `CONTRACTS.md` §7.5.

Проверено 2026-09-21:

- focused kernel tests — **52 passed**;
- focused kernels + analyzer registry + все текущие production analyzers —
  **170 passed**;
- `uv run poe check` — **PASS**: pre-commit, mypy (65 source files), pytest
  **2189 collected / 2172 passed / 17 skipped**, покрытие **90%**, CLI smoke;
- максимальные raster/tile/count/halo limits проверены ниже, на границе и выше;
  workspace preflight, pathological dimensions, strided input, invalid dtype/
  shape, `NaN`/`Inf`, border, alpha и immutable buffers покрыты тестами;
- итоговый diff и `git diff --check` проверены; public API/schema/YAML,
  normalized image pipeline, четыре analyzer `1.0.0`, risk и completeness не
  изменены.

Новых зависимостей и provenance нет; `CHANGELOG.md` и `REFERENCES.md` не
изменялись. Release certification и пересборка Graphify не запускались. Git
mutations не выполнялись. Owner blockers отсутствуют; на момент этого инкремента Stage 12 и Macro 1
оставались `IN_PROGRESS`. Следующим increment был M1-D.

### M1-D — source-precision audio и numeric STFT foundations — DONE

Baseline: `51f3d24a40eb50893285c5b6ec1c1b0284ae12d7`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, начальное дерево чистое.
Реализованы source/decoder facts, дополнительные precision-preserving окна,
общие immutable framing/periodic Hann/rFFT/magnitude/power kernels и demand-driven
подготовка raw numeric artifacts. Контракт принадлежит `CONTRACTS.md` §7.5;
сведения об используемых интерфейсах — `REFERENCES.md`.

Проверены PCM8/16/24/32, float32/64 без clipping, lossy decode, mono/stereo/8
channels, 192 kHz, begin/middle/end и перекрытия, фактические короткие окна,
малформатный/truncated input, timeout/overflow и unresolved process barrier.
Проверены framing/tail, Hann coefficients, DC/single-bin sine, magnitude/power,
finite values, immutable backing, provenance identity и resource preflight.
Production demand не активирует новые producers; PCM16/fragments/PNG spectrum
совпадают с прежними байтами на regression fixture. Новые анализаторы, Findings,
public API/domain/config и runtime dependencies не добавлялись.

Итоговый `uv run poe check`: **2255 passed, 17 skipped, coverage 90%**;
pre-commit, Ruff, mypy (65 source files) и CLI smoke — PASS. Штатный packaging
regression (sdist → wheel → install/import) также прошёл; отдельная strict
release certification не запускалась. Реализация и тесты размещены в существующих
tracked файлах, release provenance policy не менялась. Git mutations и
перестройка Graphify не выполнялись.

Ограничения: выборочное покрытие, отказ для неизвестного/s64 decoder format и
неподтверждённой непрерывности PTS; короткое окно без полного FFT frame не создаёт
spectral artifact. Общий native RSS/concurrency остаётся предметом M1-G.
Owner blockers отсутствуют. На момент этого инкремента Stage 12 и Macro 1 оставались `IN_PROGRESS`.
Следующим increment был M1-E.

### M1-E — bounded media timing facts — DONE

Baseline: `c20183c58d525329229898bc436414db1624cea6`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, начальное дерево чистое.
Реализованы bounded stream/packet/video-frame timing facts, exact rational time,
типизированные numeric tables и проверка их чтения, requested/observed coverage
и связь будущих pixels/timestamps через идентичность decode operation.
Семантика и ограничения принадлежат `CONTRACTS.md` §7.5.

Timing подключён к существующему demand plan; исправлена чрезмерно широкая
активация M1-D: timing-only video demand не вызывает source-precision audio decode.
Существующие четыре анализатора не запрашивают новые capabilities; PCM16 и
sampled-video поведение сохранено. Новые анализаторы, Findings, public API,
AnalysisResult, YAML/config, зависимости и risk/completeness не менялись.

Проверены сгенерированные CFR, B-frame, VFR, short/non-zero-start video,
video с audio и без него, missing PTS/DTS, точность больших ticks, rational
validation, begin/middle/end, неточный seek, partial/empty coverage, count/byte
preflight, malformed/truncated media, malformed tables, timeout, реальные
stdout/stderr overflow с reap и передача unresolved-process cleanup barrier.
Первичная проверка с существующими contracts/runner/registry и packaging
regression: **584 passed**. После замечаний владельца выполнены две точечные
коррекции: частоты кадров получили отдельный тип `TimingRate`, перекрывающиеся
регионы объединяются без дополнительных probes/artifacts. Семантика закреплена
в `CONTRACTS.md` §7.5. Проверки типов, границ рациональных чисел, объединения
регионов и сохранения положительного/отрицательного start добавлены в тесты.
Focused suite после коррекций: **492 passed**. Итоговый `uv run poe check`:
**2374 passed, 17 skipped, coverage 90%**; pre-commit, Ruff, mypy (65 source files)
и CLI smoke — PASS.

Реализация и тесты находятся в существующих tracked файлах; provenance policy
пакета не ослаблялась. `git diff --check` — PASS. Git mutations, Graphify rebuild
и отдельная strict release certification не выполнялись. CHANGELOG и REFERENCES
не менялись: новые архитектурные решения и внешние зависимости не вводились.

Ограничения: выборочные области не доказывают full-file continuity; наблюдаемый
временной envelope не доказывает отсутствие внутренних пробелов. Причина
завершения probe сохраняет неоднозначность packet budget/EOF. Audio timing
ограничен packets; dense RGB и AV mapping не реализованы. Общий native
RSS/concurrency остаётся предметом M1-G. Owner blockers отсутствуют.
На момент этого инкремента Stage 12 и Macro 1 оставались `IN_PROGRESS`. Следующий increment — **M1-F**.

### M1-F — dense video windows и A/V timing mapping — DONE

Baseline: `0223ad8e38c40daa369d6a1e7bed80769e7bb995`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, начальное дерево чистое.
Dense producer и региональное A/V mapping подключены к существующему demand plan.
Семантика, same-decode гарантия, geometry, artifact/process bounds и ограничения
принадлежат `CONTRACTS.md` §7.5. Samples/STFT не активируются timing/mapping demand.
Текущие четыре анализатора и sampled-video путь, их версии, public API/config,
зависимости, Findings, risk/completeness не изменены.

Проверены generated CFR/VFR/B-frame video, H.264/RGB, small/odd/scaled geometry,
high-FPS/frame boundary, независимый temporal limit при low FPS, merged regions,
begin/middle/end и ненулевой start. Проверены pixel/timing identity/count/checksum,
malformed/partial output, timeout, реальные stdout/stderr overflow с reap,
artifact ownership/cleanup/barrier и preflight. A/V тесты покрывают независимые
time bases, большие signed ticks, offsets, resets, partial/empty/unknown regions,
missing streams и отсутствие ложной глобальной continuity.

После owner review generic M1-E timing и dense same-decode timing разделены
типизированной ролью. Восстановлены role-specific provenance checks; AV mapping
всегда использует generic observations. Добавлены проверки неизменности таблиц
при совместном demand и отказов при подмене provenance/role/artifact binding.
Существующие resource ceilings сохранены; oversized composition отклоняется
preflight, без молчаливого уменьшения generic timing coverage.

После targeted remediation focused suite: **664 passed**. `uv run poe check`:
**2436 passed, 17 skipped, coverage 90%**; pre-commit, Ruff, mypy (65 source files)
и CLI smoke — PASS. `git diff --check` — PASS.

CHANGELOG фиксирует смену внутреннего AV контракта; REFERENCES — интерфейсы
showinfo/trim без копирования внешнего кода. Реализация остаётся в существующих
tracked файлах. Git mutations, Graphify rebuild и strict release certification
не выполнялись. Native decoder RSS/concurrency и общий hardening остаются M1-G.
Owner blockers отсутствуют. На момент этого инкремента Stage 12 и Macro 1 оставались `IN_PROGRESS`.
Следующий increment — **M1-G**.

### M1-G — Integration, Resource, Failure & Concurrency Hardening — DONE

Baseline `f885a04f44044a3cf8148bc7b6c3c69336b4b375`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`; исходное дерево чистое.
M1-G принят владельцем и закоммичен; HEAD после M1-G — `5f869782592b34ffc437b37da9def91d79782042`.
Новых capabilities, representations, dependencies,
public API/config fields и analyzers нет. Нормативные гарантии принадлежат
`CONTRACTS.md` §7.5; ниже — результаты проверки, а не новые sampling defaults.

Матрица 14 сочетаний IMAGE/AUDIO/VIDEO выполняется дважды с обратным порядком и
дублированными declarations. Проверены closure, отсутствие дублированных artifacts,
одинаковые facts и SHA-256 numeric content без требования одинаковых decode UUID.
Для JPEG также выполнены residual kernels на декодированном raster; отдельный
`RESIDUAL_RASTER` producer не добавлен. Generic/AV semantics при добавлении dense
проверены существующей матрицей M1-F. Для долгого A/V composition spy запрещает
record/dense операции при 18 representations; молчаливого сокращения нет.

**Решение о 16 representations.** Лимит сохранён как самостоятельный предел
совместной работы, а не ограничение размера JSON. На generated 20s 64×48/25fps
MPEG-4 + AAC layout из 18 записей занимает 9 171 bytes; его транспортная проекция
с 120 длинными timestamps — 13 238 bytes. Измерение layout выполнено только в тесте,
без разрешения такого manifest потребителю. Валидный граничный граф из 16 записей
(удалена одна целая dense пара только для проверки границы) занимает 8 260 / 12 201
bytes соответственно. Producer автоматически такую пару не удаляет. Причин
расширять допуск по одному лишь размеру metadata нет; с precision/STFT полная
верхняя композиция потребовала бы уже 25 записей. Generic/dense tables различаются
семантически. Artifact count/bytes и временные пределы остаются независимыми.
Для допустимого итогового результата проверяется весь envelope до 32 768 bytes,
включая legacy strings; тесты покрывают 32 767 / 32 768 / 32 769 bytes.
Manifest 16 384, response 65 536 и canonical result 65 509 не смешиваются.

**Windows memory observations, 2026-09-22.** Python 3.12.10, Windows x64;
малые generated fixtures и временные файлы вне checkout. `GetProcessMemoryInfo`,
sampling working set каждые 10 ms, baseline после создания fixture и GC;
отдельно OS `PeakWorkingSetSize` каждого child. Parent включает Dispatcher,
legacy preprocessing и чтение artifacts для SHA-256. Поэтому child peak нельзя
приписывать исключительно новой dense функции. Значения ниже — bytes, не SLA.

| Профиль | Parent baseline | Parent sampled peak | Child sum sampled peak | Наибольший child OS peak | Parent после cleanup/GC |
|---|---:|---:|---:|---:|---:|
| JPEG RGB 2048×680, 4:4:4, 4 177 920 coefficients | 50 782 208 | 57 634 816 | 67 407 872 | 78 127 104 | 55 189 504 |
| PCM32 192kHz, 8 channels, 1s, precision windows | 50 053 120 | 58 241 024 | 27 938 816 | 29 110 272 | 53 989 376 |
| STFT 262144×4 samples, FFT4096/hop1024/batch32 | 49 573 888 | 74 067 968 | 0 | 0 | 53 583 872 |
| Dense 3840×2160/32fps, 1s MPEG-4 → 640×360 | 50 061 312 | 73 408 512 | 433 922 048 | 464 502 784 | 54 419 456 |
| Generic timing + dense, 640×360/25fps, 20s, без audio | 50 708 480 | 74 330 112 | 51 658 752 | 51 453 952 | 55 341 056 |
| Два параллельных dense dispatch указанного 4K профиля | 50 249 728 | 52 850 688 | 888 717 312 | 464 031 744 | 54 845 440 |

В serial profiles наблюдался максимум один live child, в concurrent — два.
Child sum и individual peak измерены разными способами и не обязаны совпадать.
Краткие parent пики sampling может пропускать; after-cleanup также может превышать
sampled peak. Allocator не обязан возвращать память ОС до исходного baseline.
Все наблюдавшиеся children завершились; cleanup проверен дважды.

Учтённые artifacts: JPEG 16 717 381 bytes/4 files; audio 12 288 204/4;
dense 23 278 748/3; combined 66 909 432/22; concurrent — по 23 278 748/3 на задачу.
STFT: samples 4 194 304 bytes, 16 588 704 bytes результатов прошли через 8 batches;
расчётный workspace bound 25 174 016 bytes. Это верхний допустимый batch/FFT при
четырёх channels; 8 channels/batch32 отвергаются workspace preflight.
Учтённые bytes не являются RSS. Hard OS quota отсутствует. Реализованный допуск
ограничивает два forensic dispatch на interpreter; несколько процессов или прямые
private tool calls не образуют общий лимит. Serial/concurrent dense artifact hashes
совпали; пути и decode UUID не сравнивались как обещанная детерминированность.

**Failure/resource audit.** Сохранены существующие границы JPEG/residual/audio/
STFT/timing/dense и spy preflight tests. Добавлены finite timeout prelaunch,
14 сочетаний execution/close failures, admission success/failure/timeout/
interruption и recoverable barrier. Существующая матрица покрывает реальные
read/write/overflow/timeout/crash/wait/terminate/kill/reap и прерывания cleanup.
Для numeric families проверены чужой ID, read-only backing, truncation и append;
существующие model/parser tests проверяют identity/provenance, role, dtype/endian,
shape, NaN/Inf, operation ID, geometry/count и generic/dense binding.
Добавлены partial-write/extent/descriptor-validation failures на audio samples,
spectra, generic packet/frame и dense timing; JPEG/RGB lifecycle проверяется
существующими тестами. Register-before-write и idempotent cleanup подтверждены.
Бюджет задачи монотонный; возврата extents для повторного расходования нет.

Targeted owner remediation закрывает отложенную M1-D классификацию audio
`ValueError`: только явные policy/count preflight дают resource failure,
ошибки внутренних descriptors/STFT/manifest дают controlled invariant failure.
Final AV manifest также отделяет representation count от нарушения связей.
Lifecycle tests требуют точные kind/phase, очищенный текст и idempotent cleanup;
прежние timing/dense classifications сохранены. Это часть того же M1-G,
без новой capability или изменения публичных результатов.
Проверки remediation: focused preprocessing/internal models — **604 passed**;
`uv run poe check` — **2505 passed, 17 skipped, coverage 90%**,
pre-commit/Ruff, mypy (65 source files) и CLI smoke — PASS.
`git diff --check` — PASS; Git mutations не выполнялись.

**Package verification.** Обычный sdist → wheel, свежая внешняя Python 3.12 venv,
26 locked runtime distributions, `uv pip check`, без editable/dev packages и
checkout в `sys.path`. Installed probe расширен на precision audio/STFT, generic
timing, same-decode dense RGB/timing и AV mapping; JPEG child/cleanup сохранены.
`source_tree_clean=false`: это development verification, не strict certification.
Позднее первичный аудит M1-H подтвердил strict clean-tree installed-wheel
certification — **PASS**. Это не меняет статус приведённой выше dirty-tree проверки.

Focused suite: **729 passed, 1 skipped**. `uv run poe check`: **2495 passed,
17 skipped, coverage 90%**; pre-commit/Ruff, mypy (65 source files) и CLI smoke — PASS.
`git diff --check` — PASS. Текущий каталог четырёх analyzers,
их IDs/versions, requirements, risk/completeness и прежняя активация не изменены.
Graphify rebuild, Git mutations и M1-H не выполнялись. Owner blockers отсутствуют.
На момент завершения M1-G следующим действием был отдельный M1-H.

### M1-H — независимый аудит закрытия — DONE / PASS

Macro 1 — **DONE / CLOSED / owner accepted**. M1-A–M1-G и targeted remediation —
**DONE / owner accepted / committed**. Финальный независимый повторный аудит —
**PASS**, замечаний к исправлению — **0**; public contract drift и регрессии
текущих анализаторов не обнаружены.

Первичный M1-H имел результат **REMEDIATE**; его замечания сохранены в истории:

- **M1H-F01 / HIGH — CLOSED:** вторичное прерывание при artifact close могло
  потерять cleanup barrier. Targeted remediation сохраняет исходный unresolved
  barrier через существующий `_CleanupSafetyInterruption` и семантику прерывания;
  admission удерживается до подтверждения безопасности/reap. Добавлены 18 regression
  cases, включая dense dispatch с живым child и однократное освобождение admission.
- **M1H-F02 / LOW — CLOSED:** ROADMAP содержал устаревшие противоречивые статусы
  M1-G/M1-H. Формулировки текущего состояния нормализованы.

Focused suite remediation: **620 passed, 2 skipped**. На момент remediation
повторный аудит и Graphify rebuild ещё не выполнялись; последующие результаты
закрытия ниже заменяют прежнее ожидание этих действий.

**Baseline закрытия:** `625b9e83f133fb0ae31a4b90e9e1288bff96f69c`.
Strict clean-tree certification на этом HEAD — **PASS**:
Python **3.12.10**, строгая проверка sdist/wheel в свежих внешних средах,
non-editable установка, **26/26** утверждённых runtime distributions,
без checkout/source fallback; installed-wheel probes **M1-B/D/E/F — PASS**.
Graphify исключён из package artifacts.

SHA-256 проверенных артефактов:

- sdist: `9f9ab76f423ddbee8f01088745abf9a62e4ddc4da1af08ade9fee37285d60ecf`;
- wheel: `529b52cb34494dabfb381a5666122f26cbebd362e469465986fd7915bf2af631`.

Финальный quality barrier: **2540 collected, 2523 passed, 17 skipped,
coverage 90%**; Ruff/pre-commit — **PASS**, mypy — **PASS / 65 source files**,
CLI smoke и `git diff --check` — **PASS**. Это принятые результаты технического
закрытия на указанном HEAD, не повторный запуск в документационном инкременте.

**Graphify:** требование первичного аудита `REQUIRED_BEFORE_MACRO1_CLOSURE`
выполнено — **SATISFIED**; статус — **CURRENT**, source SHA —
`625b9e83f133fb0ae31a4b90e9e1288bff96f69c`. Graphify остаётся ignored/untracked,
вспомогательным свидетельством для архитектурной навигации, не доказательством
runtime correctness и не источником полномочий для package/release.

**Принятые остаточные ограничения** (не открытые findings; нормативные границы —
`CONTRACTS.md` §7.5, сведения о native allocations — `REFERENCES.md`):

- hard OS RSS quota и глобального cross-process forensic semaphore нет;
  forensic admission действует только внутри процесса/interpreter;
- прямые private tools и legacy dispatch могут оставаться вне forensic admission;
  RSS native allocator может оставаться повышенным после освобождения данных;
- sampled timing не доказывает непрерывность, подлинность или lip-sync;
- предел **16 representations** намеренно отклоняет некоторые совместные demands;
- Graphify не доказывает runtime correctness;
- локальная целостность артефактов не защищает от произвольного привилегированного
  локального атакующего.

Публичные контракты сохранены. Бизнес-маршруты остаются ровно
`POST /api/v1/analyses`, `GET /api/v1/analyses/{analysis_id}` и
`GET /api/v1/analyses/{analysis_id}/result`; каталог остаётся ровно из четырёх
анализаторов с версиями, перечисленных в начале Stage 12. Новые анализаторы
Macro 2 не установлены и не активированы. Текущий статус Macro 2 и gate M2-A — в §2.2.

### Критерии ресурсов и достоверности для A/G

- Сохранить общий предел **256** generated artifacts и
  `B_m = limits.max_file_size_mb[m] * 1_048_576` на все созданные файлы задачи,
  включая текущие normalized/fragments/frames. Дополнительного независимого
  бюджета не вводить. Уменьшение precision ради помещения в бюджет запрещено;
  превышение сохраняет существующий `stage5_resource_limit`.
- Небольшие facts/manifests вместе с прежней metadata должны помещаться в
  **32 768 байт**; file facts — **16 384**, settings — **8 192**.
  Ответ analyzer worker — **65 536**, canonical result — **65 509 байт**.
  Большие arrays и таблицы событий не входят в ответ или `raw_metrics`.
- Каждый новый binary reader проверяет формат, shape, dtype/endian, длину,
  арифметическое переполнение и принадлежность artifact ID до выделения памяти;
  object arrays/pickle, произвольные пути и raw EXIF/XMP/ICC запрещены.
- JPEG: стартовый профиль — input не больше `min(32 MiB, input limit)`, до
  256 markers/scans и 1 MiB совокупных marker payload, до 4 компонентов/таблиц
  и `2^22` коэффициентов всех компонентов суммарно. Это до **16 MiB int32**
  перед расходом общего бюджета; учитывать также native buffers и полную копию
  сжатого JPEG. Thumbnail: до 512 KiB encoded и 512×512 decoded pixels.
  Предварительная оценка проверяется до native allocation; crop после decode
  не считается memory bound. Необычные coding modes и переопределение таблиц
  между scans требуют явной применимости, не приблизительных коэффициентов.
- Residual: стартовый tile ≤512×512 с halo ≤2 для kernels ≤5×5, до 16 tiles;
  вычисление float64 с оценкой временных массивов ≤32 MiB. Общий reader
  допускает ≤`2^22` decoded raster pixels для этого профиля и учитывает память
  целого RGB/RGBA raster отдельно: вырезание tile после полной загрузки
  изображения само по себе не ограничивает память. Производные residual arrays
  выдаются порциями, постоянная полная карта не создаётся автоматически.
- Audio: до 3 окон по ≤10 секунд, каждое ≤`2^20` samples суммарно по каналам,
  rate ≤192 kHz, channels ≤8. Float64 занимает до 8 MiB на окно; native integer
  precision хранится без потерь в int32. Это дополнительные представления,
  не новые условия Stage 3 admission. STFT: `n_fft ≤4096`, `hop ≥n_fft/4`,
  до 8192 time/channel frames, batch ≤32, без полной STFT в памяти.
  Учитывать complex128 workspace NumPy; границы окон и channel policy явные.
- Timing: до 3 областей, на выбранный stream/область до 256 packets и
  512 frame records; до 2 streams, общий предел 4608 records. Каждый ffprobe
  output ≤256 KiB, общий typed timing artifact ≤1 MiB. Сохранять фактически
  прочитанные границы: `read_intervals` seek не гарантирует запрошенный start.
  Переполнение не превращать в успешно разобранный обрезанный JSON.
- Dense video: до 3 окон, ≤32 последовательных кадров и ≤2 секунд на окно,
  максимум 96 кадров; дополнительный RGB24 raster внутри 640×360 с сохранением
  aspect ratio, без upscale. Максимум pixels output — **66 355 200 байт**
  плюс manifests, всё внутри `B_video`; обрабатывать rolling batches, не весь
  набор сразу. Native decode gate — до 3840×2160, включая изменение размеров
  потока; resize после decode не гарантирует низкий native RSS. Размеры,
  scaling/color conversion и фактическое покрытие всегда сохраняются.
- Потолки дают проверяемые объёмы данных: 16 MiB coefficients, 8 MiB sample
  window, примерно 63.3 MiB всех dense RGB frames. Их применимость и пиковый RSS
  нужно измерить вместе с существующими артефактами и configured concurrency;
  они не обещают hard OS RAM quota и не гарантируют покрытие всего входа.
- Все операции получают `min(operation timeout, remaining overall budget)`.
  Стартовые потолки для проверки: 15 s на probe, 30 s на native JPEG/window decode;
  residual/STFT выполняются внутри существующего bounded analyzer invocation.
  Seek/preroll, native allocation и задержка декодера учитываются отдельно от
  числа выходных кадров; короткий output не означает короткую работу.

### Критерии закрытия Macro 1

- [x] Решения G1–G5 рассмотрены и записаны в соответствующих источниках истины.
- [x] A–G выполнены; first-wave consumers имеют конкретные входные представления,
  но сами новые анализаторы в Macro 1 не реализованы.
- [x] EXIF 1–8, non-square image, component subsampling/padding и преобразование
  native bbox в normalized coordinates проверены; native JPEG DCT не вычисляется
  из PNG и не меняет координатную систему молча.
- [x] Residual kernels ограничены tiles/halo/workspace, имеют фиксированные
  dtype/range/border/coverage и immutable outputs; grayscale/RGB/RGBA, alpha,
  determinism, finite validation и resource boundaries проверены без Findings.
- [x] Проверены baseline/progressive/grayscale JPEG, non-contiguous quant table
  IDs, malformed/truncated/oversized input, native warnings/crash/timeout и
  Unicode workspace. Source markers не попадают в logs/results.
- [x] Проверены integer PCM 8/16/24/32, float samples, silence/impulse/tone,
  stereo/channels, последние неполные окна и отсутствие потери >16-bit evidence;
  ffprobe sample format не выдаётся за effective bit depth или историю монтажа.
- [x] Проверены CFR/VFR, B-frame reorder, missing/negative/duplicate timestamps,
  discontinuities, ненулевые разные stream starts, отсутствие audio, короткий
  EOF и long-GOP seek. Timing и dense frames связаны одним decode, не только
  совпадением порядковых номеров двух независимых запусков.
- [x] Derived duration/drift отличается от metadata/decoder facts; разрывы между
  отдельными окнами не выдаются за наблюдавшиеся discontinuities. Ни `avg_frame_rate`,
  ни совпадение длительностей не доказывают CFR/AV synchronization.
- [x] Все новые файлы зарегистрированы до записи и очищаются существующим lifecycle;
  одновременный stdout/stderr ограничен, overflow/timeout подтверждают reap,
  unresolved reader сохраняет cleanup safety barrier.
- [x] Требования активного каталога объединяются до подготовки, каждый общий
  артефакт создаётся один раз; текущие четыре analyzers и public semantics сохранены.
- [x] Проверены installed-wheel execution, import origin и lock-derived runtime
  constraints; лицензии точных native artifacts оформлены; нет checkout dependency,
  моделей, ML runtime, новых конфигурационных полей или параллельного storage.
- [x] M1-H завершён: финальный независимый повторный аудит PASS, actionable findings 0;
  Macro 1 — DONE / CLOSED / owner accepted.

В Pass 1 не запускались project test suite, release certification и пересборка
Graphify. Изменения реализации и Git mutations не выполнялись.

## Macro 2 — Image Analyzer Expansion — Wave 1 — DONE / CLOSED

Итог и хронология проверок — в §2.2. Ниже сохранена история принятых
инкрементов; промежуточные состояния не переоткрывают закрытый Macro 2.

### M2-A — DONE / OWNER ACCEPTED / PRODUCTION IMPLEMENTED

Приёмка реализации с packaging remediation подтверждена явным current-state
свидетельством владельца в задании M2-BR1 от 2026-09-24. Ниже сохранён ход
проверок M2-A; их прежние ограничения относятся к состоянию до этой приёмки.

Первоначальная попытка реализации корректно остановлена до изменений кода:
DQ/grid были только кандидатами без полных принятых спецификаций. В M2-R4
владелец 2026-09-24 принял полную запись DQ-HIST-1 / DQ-R3C-1 и закрыл
DQ-G1–G4. M2-A разблокирован только для реализации принятого DQ scope;
Grid и другие непринятые методы в это разрешение не входят.

- [x] M2-R1: подготовить целевое исследование DQ/grid и сравнение методов;
  [отчёт от 2026-09-23](research/2026-09-23-jpeg-dq-grid-method-selection.md)
  принят владельцем как research evidence согласно заданию M2-R2.
- [x] M2-R1: оформить research provenance/licensing записи в `REFERENCES.md`;
  это не допуск внешнего кода или production-реализации.
- [x] M2-R2: по явному measurement-only разрешению подготовить изолированный
  harness, арифметические тесты, controlled corpus вне Git и
  [отчёт](research/2026-09-23-jpeg-dq-grid-calibration.md). Работа представлена
  для owner review; вывод обоих методов — `CALIBRATION_NOT_READY`.
- [x] M2-R2: owner acceptance исследовательских результатов подтверждён
  владельцем в задании M2-R4; это не принятие production-метода.
- [x] M2-R3A: подготовить дизайн real corpus, сравнение прав, source-safe split,
  расчёт holdout и варианты operating point; M2-R3A принят владельцем в задании R3B.
- [x] M2-R3A owner decision remediation: выбран BALANCED TRIAGE ≤1%; расширенный
  вариант 3600 и 2000 собственных RAW не обязательны; 0,5% опционален,
  0,1% не требуется. Это не production thresholds и не принятие методов.
- [x] M2-R3B — OWNER_ACCEPTED: pilot evidence и research implementation приняты;
  RAW 120 acquisition-approved,
  107 developed, 97 measurable groups / 237 JPEG; VISION 50 selected,
  43 QA/measurable groups / 55 social JPEG. DQ — USEFUL_SIGNAL, Grid — WEAK_SIGNAL,
  DQ переходит к FINAL_CALIBRATION; Grid — DEFERRED_RESEARCH_ONLY. Результаты
  — в [отчёте R3B](research/2026-09-24-jpeg-real-corpus-pilot.md).
  109 focused tests PASS; полный barrier имеет один untracked-source provenance
  failure — OWNER_VERIFY_REQUIRED после Git-действий владельца; приёмка pilot evidence
  не подменяет эту проверку.
- [x] Владелец первоначально зафиксировал размеры 200/100/500/100 и optional
  challenges 50; в R3D до исходов заменил 500 на максимум после QA (320).
  Назначение пилотных групп и DQ-only statistical acceptance rule сохранены.
- [x] M2-R3C: выполнить calibration200/validation100 с outcome-blind split,
  source/scene/hash leakage checks, двумя предобъявленными семьями правил,
  freeze decision/support/abstention и однократной независимой validation.
  [Отчёт R3C](research/2026-09-24-jpeg-dq-final-calibration.md):
  `READY_FOR_FINAL_HOLDOUT`; 0/98 primary FP, upper 3,0106%, abstention 2%,
  aligned40to90 sensitivity 65/99 applicable / 65/100 unconditional.
  Другие quality histories и ограничения состава описаны отдельно.
- [x] M2-R3C: owner acceptance получен в задании M2-R3D.
- [x] M2-R3D: выполнить один frozen-rule DQ-only holdout с заранее записанными
  acquisition, source/scene/session QA, membership hash и endpoint.
  По отдельному pre-outcome owner decision включены все 320 пригодных групп:
  0/308 FP, upper 0,9679255009%, `FINAL_HOLDOUT_PASS`;
  [отчёт R3D](research/2026-09-24-jpeg-dq-final-holdout.md).
  Без tuning и адаптивного добора; VISION/challenges вне primary FPR, Grid исключён.
- [x] M2-R3D: owner acceptance исследовательского результата подтверждён
  заданием M2-R4. Coverage остаётся описательным свидетельством; новый
  post-hoc acceptance threshold не вводится.
- [x] R3D package/full barrier verification — DONE: владелец подтвердил
  успешный повтор после staging — 2686 passed, 17 skipped; CLI smoke PASS;
  git status clean. R3D committed SHA:
  `7216fdc037e7e85fee6557cdd71bb5902c4cf2fd`. Это свидетельство владельца,
  не новый запуск M2-R4 и не strict certification.
- [x] M2-R4: подготовить полную спецификацию
  [DQ-HIST-1](METHODS.md#dq-hist-1--гистограммное-измерение-dct):
  DQ-G1–G4 `CLOSED`, статус метода `ACCEPTED`. Frozen rule, threshold и final-holdout
  interpretation не изменены; Findings, полнота, correlation и ресурсный scope
  описаны в METHODS без изменения общих контрактов и production code.
- [x] M2-R4 — OWNER_ACCEPTED: явное решение владельца от 2026-09-24 принимает
  полную запись DQ в METHODS и разрешает её production implementation.
  M2-A — READY_FOR_IMPLEMENTATION в точном принятом scope;
  принятие не означает реализацию, activation, tests или release certification.
  Grid сохраняет `DEFERRED_RESEARCH_ONLY`: слабое различение локальных patches
  и benign crop/recompress в R3B; возврат требует отдельного плана.
- [x] Реализовать M2-A в принятом DQ scope; Grid не активировать.
- [x] Повторить package provenance после staging владельцем и исправить packaging regression.
- [x] Получить приёмку реализации владельцем — подтверждено заданием M2-BR1.

M2-A реализует `image_jpeg_double_quantization@1.0.0` через существующий
каталог, controlled numeric reader и Stage 6 candidate formation. Каталог
содержит пять анализаторов. DQ выбирается существующим списком
`analyzers.image.enabled`; конфигурационный пример Profile B не расширен.
Новых настроек, зависимостей или публичных полей нет. Принятые измерения,
правило решения и ограничения METHODS сохранены; Grid не реализован.

Проверки M2-A: focused/integration suite — 599 passed; дополнительные
first-SOF/payload boundary проверки — 4 passed. `uv run poe check`:
**2791 passed, 17 skipped, 1 failed** — только sdist provenance нового
untracked `_image_jpeg_dq.py`. Новые production/test файлы остаются unstaged;
повтор package verification после staging владельцем — `OWNER_VERIFY_REQUIRED`.
Pre-commit, mypy и отдельно выполненный CLI smoke — PASS; повтор проверок
каталога после уточнения assertions — 88 passed. Новые файлы отдельно проверены
pre-commit. При четырёх одновременных worker executions с максимальной plane
16 MiB и FFT до 65536 bins peak working set каждого — 75 272 192–75 583 488
байт; выборочный суммарный worker RSS — 300 916 736 байт (шаг 5 ms).
Это измерение workers, не совокупный peak с preprocessing; допустимый JPEG
2048² и ресурсные отказы проверены отдельно. Это development verification,
не strict certification; на момент этого прогона приёмка M2-A была открыта.
Macro 2 этим не закрывается.

Packaging remediation M2-A: после staging владельцем выявлено устаревшее
ожидание четырёх регистраций в installed-wheel probe. Проверка теперь сверяет
точные ID/версии пяти анализаторов, наличие DQ-модуля в wheel, его установленное
происхождение и worker factory; исключение `framework_test.image` сохранено.
Других устаревших ожиданий полного каталога в release tooling не найдено;
Profile B/default enabled и реализация DQ не изменены. Точный regression test —
1 passed; связанные release tests — 99 passed; `uv run poe check` — PASS:
**2792 passed, 17 skipped in 143.07s (0:02:23)**, pre-commit/mypy/CLI smoke PASS.
Прежний `OWNER_VERIFY_REQUIRED` по package provenance закрыт этим повтором.
Это development verification; последующая приёмка реализации подтверждена
заданием M2-BR1, без повторного открытия DQ.

Исследовательский код M2-R2 не регистрирует IDs и не влияет на риск/полноту.
Проверки M2-R2: focused suite — 89 passed; полный quality barrier —
2611 passed, 17 skipped, 1 failed на sdist provenance нового untracked отчёта.
Ruff, mypy и отдельно выполненный CLI smoke — PASS. Для повторной проверки
sdist после Git-действий владельца — `OWNER_VERIFY_REQUIRED`; требование
tracked provenance сохранено. Полные свидетельства находятся в отчёте M2-R2.
Пять image-кандидатов и их методологический допуск перечислены в `METHODS.md`;
исследовательские отчёты подчиняются `research/README.md`.

### M2-BR1 — DONE / OWNER_ACCEPTED_RESEARCH_CLOSURE

Владелец завершил review и явно принял **исследовательское закрытие M2-BR1**.
Это решение не является принятием ни одного production-метода.

- [x] Изучить реальные Macro 1 capabilities и первичные classical references
  для noise residual и resampling; сравнить distinct/correlated evidence с
  metadata, copy-move, DQ и deferred Grid.
- [x] Зафиксировать exploratory profiles до outcomes и выполнить bounded pilot:
  20 VISION crops + 4 synthetic controls, 360 measurements; repeat360 идентичен.
- [x] Подготовить [отчёт отбора](research/2026-09-24-image-noise-resampling-method-selection.md)
  и provenance; оба результата — рекомендация **RESEARCH_ONLY / WEAK_SIGNAL**.
  У noise matching подавляет added-noise signal; у resampling JPEG/texture
  overlap и abstention не позволяют перейти к production threshold calibration.
- [x] Получить owner acceptance исследовательского закрытия M2-BR1.

Методы сохраняют `CANDIDATE / METHOD NOT YET ACCEPTED`. Профили N-MAD-MATCH-1
и R-D2-MATCH-1 остаются `RESEARCH_ONLY / WEAK_SIGNAL`: production-методы не
приняты, production calibration и production implementation не разрешены;
thresholds/severity не выбраны. Дальнейшее targeted research требует отдельного решения.
Следующий возможный scope — отдельное исследование нерешённых confounds из
отчёта, не автоматическая калибровка/реализация. Новых runtime dependencies,
analyzers, config/API/scoring/completeness changes нет; каталог — пять.
M2-A не менялся; Grid — `DEFERRED_RESEARCH_ONLY`; на момент закрытия M2-BR1
Macro 2 / Stage 12 оставались `IN_PROGRESS`. Все внешние BR1 материалы находятся
только в заданных
`FakeDetector-Work/research|reviews|tmp/M2-BR1-noise-resampling/`.

### M2-CR1 — DONE / OWNER_ACCEPTED_RESEARCH_CLOSURE

Владелец завершил review и явно принял **исследовательское закрытие M2-CR1**.
Это решение не является принятием production-метода.

- [x] Проверить EXIF/TIFF, фактические preprocessing capabilities и границу
  ответственности `image_metadata_consistency`; сохранить
  [отчёт](research/2026-09-24-image-embedded-thumbnail-method-selection.md)
  и [provenance](REFERENCES.md#thumbnail-m2cr1).
- [x] До outcomes закрепить THUMB-NCC-GRAD-1; исследовать 30 VISION файлов
  и 360 controlled cases на 20 native сценах + 4 synthetic controls.
  Resize/compression/orientation устойчивы в пилоте; benign crop пересекается
  с transplanted-thumbnail measurements. Производственная применимость
  ограничена ещё и raster budget; пилот не является интеграционной проверкой.
- [x] Подготовить рекомендацию **RESEARCH_ONLY / WEAK_SIGNAL**, без production
  thresholds, severity, Finding types, analyzer или preprocessing implementation.
- [x] Получить owner acceptance исследовательского закрытия M2-CR1.

THUMB-NCC-GRAD-1 сохраняет `RESEARCH_ONLY / WEAK_SIGNAL`: production-метод
не принят, production calibration и production implementation не разрешены.
Поддержка standard EXIF IFD1 относится только к исследовательскому прототипу;
production thumbnail preprocessing capability не реализована и не принята.
Vendor previews остаются вне scope. Отдельные gates — bounded extraction/decode
и семантика optional representation failures, подтверждение geometry и benign-edit
challenge. Дальнейшее targeted research требует отдельного решения владельца;
принятие исследовательского закрытия не разрешает калибровку или реализацию.
Структурные checks не реализуются здесь.
Каталог остаётся пять, DQ не меняется, Grid — `DEFERRED_RESEARCH_ONLY`,
noise/resampling — `RESEARCH_ONLY`. На момент закрытия M2-CR1 Macro 2 и Stage 12
оставались `IN_PROGRESS`.
Внешние материалы — только `FakeDetector-Work/research|reviews|tmp/M2-CR1-thumbnail/`.

<a id="audio-m3r1"></a>

## Macro 3 — Audio Analyzer Expansion — Wave 1 — DONE / CLOSED / OWNER ACCEPTED

Датированные записи ниже сохраняют историю инкрементов: промежуточные
`IN_PROGRESS`, `OPEN / REQUIRED`, прежние «следующие шаги» и запросы review тогда подготовленных
diff относятся к моменту соответствующей записи, не переоткрывают принятые gates
и не назначают текущую работу. Текущие carry-forward и порядок завершения —
в [сводке обязательств](#audio-m3-required-carry-forward); итоговый ARC disposition —
в [M3-R3D-F](#audio-m3r3df). Принятые методические ограничения сохраняются.

### M3-R1 — DONE / OWNER ACCEPTED RESEARCH SELECTION

Дата: 2026-09-26. Baseline:
`1acaf4f9129d5b36c6c69a6ab6250e49e2da4d09`, ветка
`feat/stage12-macro3-audio-analyzer-expansion-wave1`, чистое committed дерево.
Выполнен research/method-selection increment для пяти рабочих audio-кандидатов.
Полные технические свидетельства и validation design находятся в
[отчёте M3-R1](research/2026-09-26-audio-method-selection.md);
candidate profiles — в [METHODS](METHODS.md#audio-m3r1), происхождение — в
[REFERENCES](REFERENCES.md#audio-m3r1).

**Явное OWNER ACCEPTANCE от 2026-09-26 (M3-R1A):** владелец принял исследовательский
отбор M3-R1 и закрыл G1–G6. Запись выполнена поверх ожидаемого dirty M3-R1 diff
на том же HEAD, с тремя изменёнными tracked документами и untracked отчётом.
ATD-LOCAL-1, ASC-TV-1 и ARC-NCC-1 — **OWNER_ACCEPTED_FOR_MEASUREMENT_PROTOTYPE**.
ABN-FLOOR-1 сохраняет `RESEARCH_ONLY / WEAK_SIGNAL`; AMC-RESP-1 —
`REJECT_DUPLICATE_RESPONSIBILITY / OWNER ACCEPTED NEGATIVE RESULT`.

**Новый production audio-метод не принят.** Нет analyzer implementation,
registration, thresholds или Findings. Каталог остаётся из пяти анализаторов;
`audio_pcm_quality@1.0.0`, risk/completeness/correlation и публичные контракты
сохранены. Macro 1/2 остаются закрыты; M2H-D01 остаётся **DEFERRED TO MACRO 6**.
Macro 3 и Stage 12 остаются **IN_PROGRESS**. Принятие M3-R1 не закрывает Macro 3
и не является production method acceptance.

Принятые владельцем gates исследовательского scope:

| Gate | Состояние | Принятое решение от 2026-09-26 |
|---|---|---|
| G1 | CLOSED / ACCEPTED | ATD-LOCAL-1, ASC-TV-1, ARC-NCC-1 допущены только к bounded research measurements; без production registration, Findings, severity, thresholds, scoring/risk/completeness/public contract changes |
| G2 | CLOSED / ACCEPTED | ATD/ASC измерять раздельно и сравнивать в одном transition track/family; без fusion, combined production score или двух независимых votes; ABN остаётся weak, не третий голос |
| G3 | CLOSED / ACCEPTED | ARC допущен отдельным correspondence track; статистическая независимость от transition evidence не заявляется, production correlation остаётся для последующей validation / Macro 6, где применимо |
| G4 | CLOSED / ACCEPTED | AMC отклонён как duplicate responsibility: intake, preprocessing/container validation, typed source/decoded facts, infrastructure/errors; production analyzer из этого scope не создавать, parser failure не Finding |
| G5 | CLOSED / ACCEPTED | Audio route, 8–48 kHz, mono/stereo, M1-D precision windows и существующие shared STFT/framing/typed timing/source facts; без новых capabilities, CONTRACTS changes или подразумеваемого full-duration coverage |
| G6 | CLOSED / ACCEPTED | Только существующий runtime stack, без SciPy и новых runtime dependencies; новые datasets автоматически не одобрены, реальные записи требуют проверки provenance/license и intended use |

Разрешённый следующий исследовательский scope — **два отдельных measurement-only
validation трека**: A — ATD/ASC (раздельные измерения без fusion, поведение и confounds
переходов); B — ARC (retrieval/correspondence/resources). Выполнение этих экспериментов
ещё не заявляется. Формулы и наблюдения M3-R1 не изменены; efficacy, false-positive
rate, sensitivity, runtime и RSS остаются неизмеренными.

Если необходимое измерение нельзя честно выполнить на existing representations —
**STOP / OWNER GATE**, без расширения preprocessing. Если необходимы корпус или
библиотека с неустановленными правами/scope — **OWNER GATE**. Условные gaps отчёта
не разрешают менять `CONTRACTS.md`. Production admission позже требует полного gate
`METHODS.md`; measurement-only допуск не означает calibrated detector, production
корреляцию или увеличение полноты анализа.

Проверки этого docs/research-only инкремента: baseline, `git diff --check`, полный
intended diff и итоговый status; полный quality barrier и strict certification
по заданию не требуются. Материалы owner review, включая новый untracked отчёт:
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-R1-audio-method-selection\`.
Принятие исследовательского scope дано владельцем явно; корректность этой записи
и обновлённый полный diff остаются предметом owner review. Новых исследований,
экспериментов и изменений production в M3-R1A нет.

### M3-R2A — DONE / OWNER ACCEPTED RESEARCH RESULT

Явное owner acceptance исследовательского результата: **2026-09-26**.

2026-09-26, baseline `9e386dc52e9c4ce59ac35bda35b992f0b65f286c`, ожидаемая
ветка и чистое начало; продолжение выполнено поверх разрешённого dirty diff.
Из 609 cases 608 завершены (573 controlled + 35 real/derived), один заранее
предусмотренный resource case штатно отклонён. Counts включают честные
insufficient/undefined; 512 short residue fixtures не дают ASC comparisons.
Одна generated lineage и пять real source groups, derivatives не независимые
trials. Полные counts/results/limitations и frozen hashes — в
[отчёте M3-R2A](research/2026-09-26-audio-transition-measurement-prototype.md).

**Исторический pre-measurement gate и owner resolution:** Vibe Ace потребовал
63 164 304 bytes при 52 428 800 budget и получил `audio_precision_artifacts`.
Владелец принял техническое свидетельство и разрешил REPLACE_SOURCE; запись
сохранена, Vibe Ace не считается completed measurement. Первый проверенный
replacement — реальная trumpet recording Mihai Sorohan / Freesound 77711,
публичный полный HQ MP3 preview, CC BY 4.0. Штатный M1 PASS: 11 172 400 bytes.
V1 сохранена, V2 зафиксирована до ATD/ASC outcomes. Бюджет, M1, формулы,
fixtures/support/aggregation/labels не менялись. Этот resource gate **RESOLVED**.

Принятый владельцем результат для каждого из ATD-LOCAL-1 и ASC-TV-1:
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**.
12 selected cases × 3 repeats — exact determinism PASS; 12 oracle/structural
групп PASS. Существующие M1 focused tests: 43 passed, 563 deselected.
ATD/ASC описывают разные аспекты перехода, но высокие benign responses и
неоднозначность global maxima не обосновывают forensic-селективность.
Production methods/thresholds не приняты, Findings/registration/fusion нет.

<a id="audio-m3-required-carry-forward"></a>

**Обязательный carry-forward Macro 3:**

| Профиль | Обязательство / disposition | Состояние |
|---|---|---|
| ATD-LOCAL-1 | RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED, M3-ATD-D1, 2026-09-29 | RESOLVED |
| ASC-TV-1 | RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED, M3-ASC-D1, 2026-09-30 | RESOLVED |

ATD-обязательство закрыто [принятым disposition](#audio-m3-atd-d1),
ASC-обязательство — [принятым M3-ASC-D1](#audio-m3-asc-d1).
**ASC REQUIRED CARRY-FORWARD: RESOLVED.**
**MACRO3_ALL_REQUIRED_CARRY_FORWARD_RESOLVED: YES.** Дальнейшей ATD/ASC promotion
work в текущем Macro 3 нет. **M3-HYG-1 — DONE / OWNER ACCEPTED**:
[documentation / instruction hygiene audit](#audio-m3-hyg-1) и ограниченные правки
приняты владельцем 2026-10-01, hygiene gate **CLOSED**.
[M3-CR1](#audio-m3-cr1) — **DONE / OWNER ACCEPTED CLOSURE**, принято 2026-10-01.
Macro 3 — **DONE / CLOSED / OWNER ACCEPTED**. Активных исследований и owner gates
Macro 3 нет. В задании M4-R1 владелец подтвердил завершённую strict certification;
основание актуализации записано в [Macro 4](#video-m4r1). Ниже сохранены
исторические основания прежнего целевого протокола и общее правило закрытия;
текущие dispositions указаны выше.

**История целевого протокола M3-R2A:** прежний протокол требовал реальных event
annotations, content-matched controls, source-level holdout и проверки ресурсной
применимости. Тогда владелец отложил исследование по очередности, не сняв
обязательства явного итогового решения по ATD/ASC; исследование не обязано было
предшествовать ARC.
Позднее принятые M3-ATD-D1 и M3-ASC-D1 разрешили оба обязательства как
RESEARCH_ONLY_NON_SPECIFIC без нового исследования. Прежний протокол не является
активным требованием закрытия Macro 3 и не объявляется выполненным.

**Условие закрытия Macro 3:** запрещено отмечать Macro 3 DONE/CLOSED, пока
владелец не зафиксирует явное последующее итоговое решение **для каждого** из
ATD-LOCAL-1 и ASC-TV-1. Допустимые решения:

1. Целевое исследование выполнено, профиль продвигается далее.
2. RESEARCH_ONLY / WEAK_SIGNAL.
3. DEFERRED в явно названный последующий scope/stage.
4. REJECT_NOT_USEFUL либо эквивалентное явное отклонение.

Молчание, нехватка времени и начало ARC не разрешают ни одно обязательство.
Откладывание только по очередности не является итоговым DEFERRED-решением.
Условие явного disposition для обоих профилей выполнено решениями выше.
Hygiene audit и закрытие Macro 3 по [M3-CR1](#audio-m3-cr1) приняты владельцем
2026-10-01; обязательных текущих gates Macro 3 не осталось.

**Исторический следующий трек после M3-R2A, разрешённый владельцем:** ARC-NCC-1 —
measurement-only prototype повторного сегментного соответствия. Это не
production acceptance ARC, не одобрение production-анализатора и не утверждение
статистической независимости от transition evidence. На тот момент carry-forward
ATD/ASC оставался неразрешённым. Production calibration, реализация ATD/ASC, thresholds,
Findings и fusion не разрешены; новый corpus и изменение измерений автоматически
не допускаются. Запись решения и полный intended diff проверены владельцем; staging/commit остаются владельцу.

M3-R1 остаётся DONE / OWNER ACCEPTED RESEARCH SELECTION, G1–G6 CLOSED / ACCEPTED;
Текущие статусы ATD/ASC и обязательства указаны выше; production acceptance отсутствует.
ARC здесь не исследовался, ABN/AMC не менялись. Macro 3 и Stage 12 — IN_PROGRESS.
Полный quality barrier и strict certification не запускались по docs/research
scope. Bundle включает весь diff и untracked отчёт:
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-R2A-transition\`.

### M3-R2B — DONE / OWNER ACCEPTED RESEARCH RESULT

Явное owner acceptance от **2026-09-26**: исследовательский результат принят;
production method acceptance отсутствует.

2026-09-26, baseline `fe092c43b86115c8ba69e14c940a737215ce5665`, ожидаемая
ветка, чистое committed начало. Выполнен measurement-only прототип ARC-NCC-1
по M3-R1 §§3,7; формулы, нормализация, search/support bounds и numeric guard
не изменены. 80 cases завершены: 45 controlled одной lineage, 35 real/derived
пяти ранее проверенных source groups. Слой controlled не объединён с real.
28/28 допустимых controlled truth cases и 30/30 real-derived truth cases прошли
retrieval и дали истинный offset; один overlapping controlled truth вне profile.
Это не population recall, forensic detection или production calibration.
Benign loops/повторные фразы/tones дают rho=1. Полные ограничения, exact/near,
localization, caps и ресурсы — в
[отчёте M3-R2B](research/2026-09-26-audio-repeated-segment-measurement-prototype.md).

Первая реализация остановилась на numeric failure ordinary prefix sums;
компенсированное суммирование исправило арифметическую реализацию без изменения
профиля. История не перезаписана, все 80 cases выполнены исправленной реализацией.
43 existing focused tests, семь групп arithmetic oracles, 12 × 3 exact repeats —
PASS. Максимальный ARC wall 2.365 s; process-lifetime peak 82 096 128 bytes,
без утверждения hard/concurrent bound или учёта child FFmpeg peak.

Принятый исследовательский outcome: **READY_FOR_LARGER_VALIDATION**.

<a id="audio-m3r2b-speech-validation"></a>

**Следующее разрешённое исследование:** speech-dominant / voice-message
source-level validation ARC-NCC-1 на frozen v2. Главный вопрос — различимость
распределений измерений **NATURAL RE-SPEECH VS COPIED WAVEFORM**: тот же человек
естественно повторяет слово/фразу в независимых takes, либо один физически
записанный речевой сегмент скопирован/повторно использован. Разрешённые ранее
контролируемые gain/codec/noise transformations остаются в исследовательском scope.
Текущий M3-R2B это различение не доказал; следующая validation ещё не выполнена.

Обязательные концептуальные классы:

1. Тот же speaker / та же phrase / независимые natural takes.
2. Тот же speaker / копия физического waveform segment.
3. Контроли с другой phrase.
4. Контроли с другим speaker, где полезно.
5. Копия с разрешёнными controlled transformations.
6. Естественные pauses/breaths/repeated short words.
7. Background music/TV/tone/ambience challenge cases.

Natural re-speech — действительно отдельные записи/takes, не копии и не
time-shifted derivatives. Производные одной записи не независимые source trials.
Обязательна speaker/source grouping; если позднее вводятся calibration/validation/
holdout splits, группы не должны пересекать их границы. Новый corpus допускается
только после проверки прав.

Music, tones, alarms, loops, ambience и прочие non-speech repeats остаются
документированными challenge/out-of-domain cases, **не основной calibration
population** следующей validation. Высокая rho не означает suspicious manipulation.
Это сужение следующего исследовательского вопроса, не всего product scope.

Владелец принял численно исправленную реализацию финального M3-R2B как **frozen
ARC v2** для следующей validation. Сохраняются формула, compensated float64
accumulation, normalization, numerical guard, descriptor, retrieval/search bounds,
candidate caps, overlap exclusions, support, ties и channel behavior. Настройка
после будущих outcomes запрещена; история численной коррекции сохраняется.

**Production calibration: NOT AUTHORIZED.** Допустимы сравнение распределений и
оценка разделимости; production rho/descriptor threshold, severity, Finding type,
suspicious/not-suspicious decision и risk contribution требуют отдельного
последующего явного owner gate. Наблюдаемый gap автоматически не становится порогом.
Production method acceptance, analyzer implementation/registration и новая
production correlation semantics не разрешены. Запись решения и полный intended diff проверены владельцем;
staging/commit остаются владельцу.

ATD/ASC carry-forward остаётся **OPEN / REQUIRED**, не разрешён этим исследованием;
ранее записанное [условие закрытия](#audio-m3-required-carry-forward) действует
без изменения. Macro 3 и Stage 12 — **IN_PROGRESS**. REFERENCES сохранён:
новых источников нет. Full quality barrier и strict certification не запускались.
Review bundle с полным diff, включая untracked отчёт:
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-R2B-arc\`.

### M3-R3A — DONE / OWNER ACCEPTED RESEARCH RESULT

2026-09-26 UTC / 2026-09-27 Asia/Krasnoyarsk, baseline
`4f122da5eef74ade8d886942f843ce44bc8f11fe`, ожидаемая ветка и чистое начало.
Выполнено ограниченное речевое исследование с разделением по источникам
на **неизменённом frozen ARC v2**:
LaMIT v2, четыре speakers ×25 phrases ×2 независимых takes, 200 originals;
exploratory/holdout по два speakers, без пересечения groups/derivatives.
Target20 speakers не достигнут; это controlled read speech, не реальные
voice messages. Полные результаты, corpus feasibility, freeze и ограничения —
в [отчёте M3-R3A](research/2026-09-26-audio-arc-speech-source-validation.md).

727 cases завершены: 700 речевых сравнений и27 отдельных challenges.
Natural cross max rho0.552478; minimum copy maximum0.905596. В каждом
copy-классе98/100 cases имеют допустимую geometry; все98 сохранили true offset.
Два short takes не исключены из знаменателя. 43 focused tests, семь frozen
oracle groups и восемь cases×3 exact repeats (семь предобъявленных плюс
highest global natural) — PASS; numeric failure нет.
История доэкспериментального уточнения codec tail mapping сохранена отдельно;
она не меняет ARC v2, corpus membership или split и не опирается на ARC outcomes.

Явное owner acceptance исследовательского результата: **2026-09-27**.
ARC-NCC-1 сохраняет **NEEDS_TARGETED_RESEARCH**. Владелец принял ограниченную
поддержку гипотезы о меньшем сходстве независимого same-speaker/same-phrase
re-speech по сравнению с copied physical waveform при frozen ARC v2.
Четыре speakers, controlled read speech и два natural takes на фразу
не представляют популяцию реальных voice messages.
Generated periodic background на независимых takes даёт cross rho до0.965409;
**PERIODIC / REPEATED BACKGROUND** — основной нерешённый confound:
tone/music-like фон может давать correspondence, перекрывающую copied waveform.
Observed gap не является production threshold, FPR/sensitivity claim или
calibration result; **production calibration NOT AUTHORIZED**.
Frozen ARC v2 и все его численные/поисковые правила сохранены; tuning не разрешён.

Следующее запланированное исследование — **M3-R3B: более широкая natural
voice-message / speech ARC validation с реалистичными background confounds**.
Приоритеты: больше независимых speakers и natural takes, менее лабораторная
речь и естественные voice-message условия; настоящий TV/music фон,
room/ambient noise, periodic tones/hum и повторяющийся фоновый контент.
Сохраняются source-level speaker grouping и holdout без speaker leakage;
выбор корпуса с установленными правами и отдельный frozen plan ещё предстоят.
Основной вопрос: сохраняет ли большой clean-speech gap между natural re-speech
и copied waveform полезность в реалистичных voice-message условиях?
Дополнительный вопрос: можно ли выявить доминирование periodic/repeated
background как low-applicability / confounded, не изменяя ARC v2?
Это план следующего исследования, не выполненная validation и не production rule.

Production method acceptance, analyzer implementation/registration, Findings,
risk/correlation и public contracts не изменены.
ATD/ASC **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD** остаются
OPEN / REQUIRED; правило закрытия Macro3 сохранено, Macro3 — **IN_PROGRESS**.
Review bundle: `FakeDetector-Work/reviews/M3-R3A-arc-speech/`;
complete.diff включает untracked report. Full barrier/strict certification
не запускались, Git mutations не выполнялись; staging/commit остаются владельцу.
Исследовательский результат принят; запись решения и полный intended diff
проверены владельцем; staging/commit остаются владельцу.

### M3-R3B — DONE / OWNER ACCEPTED BLOCKED FEASIBILITY RESULT

Явное owner disposition: **2026-09-27**. Feasibility result принят;
текущий owner gate **CLOSED** решением об отсрочке, corpus gate не пройден.

2026-09-27, baseline `c1a86d17fba5372b10990a53ac546488e22f68ea`,
ветка `feat/stage12-macro3-audio-analyzer-expansion-wave1`, чистое начало.
Проверка существующих корпусов и возможности их совместного использования
не установила пригодный primary natural voice-message корпус с проверенными
правами, ≥12 speakers и ≥3 независимыми natural takes на repeated prompt.
Измерительная часть **NOT_EVALUATED**; predeclaration не создана, corpus
membership и split не заморожены. Это остановка по acquisition/scope gate,
а не отрицательный экспериментальный outcome ARC.

BanglaSER имеет достаточные заявленные counts, но enacted/denoised материал
не принят молча за натуральную voice-message population. Другие ограничения
кандидатов, источники и пределы поиска — в
[отчёте M3-R3B](research/2026-09-27-audio-arc-voice-background-validation.md).
Широкая source-level validation (≥12 speakers / ≥3 natural takes):
**DEFERRED UNTIL CALIBRATION / PRODUCTION-READINESS RESEARCH**.
Она **не требуется для текущей дипломной proof-of-concept фазы**.
First-party acquisition сейчас **NOT AUTHORIZED / NOT REQUIRED**;
first-party корпус не является требованием текущей дипломной фазы.
Внешний recording plan (цель 20×5×3, натуральный фон отдельно) сохранён
как будущий calibration/acquisition design; он не разрешает сбор сейчас.

Первоначальный M3-R3B scope с independent / continuous / shared background
слоями сохранён как отложенная работа. При её будущем возобновлении нужны
проверка состава/прав/независимости, speaker/background grouping и хэшированная
predeclaration до ARC outcomes; малый pilot/derivatives не закрывают broad gate.
Frozen ARC v2 не изменён; ARC остаётся **NEEDS_TARGETED_RESEARCH**.
Production calibration, thresholds, analyzer implementation/registration,
Finding и automatic background gate не разрешены и не выполнены.
ATD/ASC **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD** остаются
OPEN / REQUIRED; Macro 3 — **IN_PROGRESS**, правило закрытия сохранено.

Review bundle: `FakeDetector-Work/reviews/M3-R3B-arc-voice/`, включая
полный diff с untracked отчётом, corpus-feasibility, provenance-summary
и first-party-recording-plan. Измерения, focused tests/oracles, full quality
barrier и strict certification не запускались. Feasibility result принят;
запись disposition и полный intended diff проверены владельцем;
Git mutations не выполнялись, staging/commit остаются владельцу.

<a id="audio-m3r3c"></a>

### M3-R3C — DONE / OWNER ACCEPTED RESEARCH RESULT

**2026-09-28**, baseline `7c8d334960c3975f836caaf01939281dd52f204f`, ожидаемая
ветка `feat/stage12-macro3-audio-analyzer-expansion-wave1`, чистое начало.
Выполнена **ARC Diploma Stress & Challenge Validation** на неизменённом frozen v2:
184 cases, 8 speech recordings /7 speakers, 3 music и11 background groups.
Явное owner acceptance: **2026-09-28** — приняты исследовательские свидетельства
и failure map. ARC-NCC-1 сохраняет **NEEDS_TARGETED_RESEARCH**;
production method acceptance, calibration и FPR/sensitivity validation отсутствуют.

- 96 ordinary controlled copies (exact/gain/MP3/noise, три lengths) сохранили
  истинный offset/error0; отсутствие известной копии в originals не означает
  forensic authenticity ground truth. Только4/8 speech originals дали rho:
  остальные слишком коротки для двух nonoverlap2L.
- Music excerpt достиг0.996936, shared background за независимой речью —0.945472,
  periodic signals —1. В cap stress21 eligible/20 nominated/0 retained true pairs;
  global rho1 относится только к тону. Все difficult cases сохранены.
- Три full-source resource rejections учтены отдельно; заранее выбранные внешние
  excerpt fixtures не означают нового preprocessing/full-duration acceptance.

[Отчёт и failure map](research/2026-09-27-audio-arc-diploma-stress-validation.md)
и `FakeDetector-Work/reviews/M3-R3C-arc-stress/` содержат полный intended diff,
predeclaration, source/provenance, copy/benign/music/background/resource summaries.
37 focused M1 tests,7 frozen oracle groups и8 групп ×3 exact repeats — **PASS**;
numeric guard violations и ARC timeouts отсутствуют. Full quality barrier и
strict certification не запускались, executable repo files не менялись.

**Gate принятия M3-R3C — CLOSED / OWNER ACCEPTED (2026-09-28).**
Владелец принял эффективность известных копий в проверенной geometry,
неспецифичность высокого rho и отдельную проблему потери номинированной
speech-copy при bounded candidate cap. Один порог не разрешает forensic
interpretation; ARC пока не готов к tuning/calibration study.
Разрешено планирование следующего M3-R3D, а не tuning или threshold selection.
Frozen v2 не меняется; ARC v3 и новый automatic background gate не разрешены.
Git mutations не выполнялись, staging/commit остаются владельцу.

M3-R3C **не population calibration** и не требует same-speaker/same-phrase/
three-take membership: этот вопрос ограниченно исследован в M3-R3A, а broad
population validation явно отложена. Результат M3-R3A остаётся действительным
только в его заявленном scope; stress cases не расширяют его автоматически.
Source identity/provenance обязательны; предпочтителен явно rights-established /
open материал. Controlled derivatives сохраняют точные parent/recipe hashes;
raw media остаются вне Git. Frozen ARC v2 не меняется.
Production calibration **NOT AUTHORIZED**, production threshold **NONE**;
FPR claims и production analyzer не разрешены. ATD/ASC carry-forward не закрыт,
Macro 3 остаётся **IN_PROGRESS**.

<a id="audio-m3r3d"></a>

### M3-R3D — ARC Applicability & Retrieval Competition Research

Решение владельца от **2026-09-28** разрешает **планирование** M3-R3D.
**M3-R3D-P — DONE / OWNER ACCEPTED DESIGN RESULT; owner acceptance: 2026-09-29.**
На baseline `c60c76dab32eeac1bf8ce0e9cd2be9cc829e1c12`,
в ожидаемой ветке и с чистым началом выполнен анализ сохранённых M3-R3C outputs.
Новый ARC experiment, acquisition или изменение frozen v2 не выполнялись.
[Design report](research/2026-09-29-audio-arc-applicability-retrieval-design.md)
и внешний bundle `FakeDetector-Work/reviews/M3-R3D-arc-applicability/`
содержат retrieval chain, concentration, сравнение вариантов и решение владельца.

1. Descriptive attribution известных fixtures доступна частично из outputs,
   а semantic truth foreground/background требует masks/recipe. Надёжная
   automatic attribution неизвестной записи не установлена.
2. В cap stress21 eligible →20 nominated →0 retained true pairs: ranks518–585
   вне cap64. Все64 возвращённые пары — background-only; 59/64 имеют один
   coarse offset, после refinement все относятся к известной tone family.
   Полная потеря truth происходит до NCC; post-attribution её не исправляет.
3. Принята рекомендация: **COMBINED_ATTRIBUTION_AND_DIVERSIFICATION_STUDY_REQUIRED**.
   Отдельный applicability method пока лишь возможный вариант; его necessity
   не доказана. Concentration сама по себе не правило исключения true copies.
4. **Gate принятия M3-R3D-P — CLOSED / OWNER ACCEPTED (2026-09-29).**
   Принят design/evidence analysis, не production method или FPR/sensitivity
   validation. ARC-NCC-1 остаётся **NEEDS_TARGETED_RESEARCH**.

**M3-R3D-E — ARC Attribution & Retention Diversification Experiment:**
разрешён владельцем **2026-09-29**, выполнен в scope ниже; результат и следующий
owner gate записаны в [текущем состоянии](#audio-m3r3de).
Владелец разрешил две связанные исследовательские части:

- **A — frozen-v2 attribution study:** существующие M3-R3C cases/outputs и
  существующие M1 representations в явно ограниченном scope. Fixture truth
  используется только для оценки; production classifier и tuning cutoffs запрещены.
- **B — retention diversification experiment:** разрешена внешняя research-only
  реализация экспериментальных retention alternatives под `FakeDetector-Work`.
  Меняется только выбор фиксированного retained budget из уже номинированного
  candidate union. Frozen v2 остаётся неизменённым каноническим research baseline;
  каждый experimental selector сравнивается с исходным frozen-v2 top64 behavior.
  Называть experimental selector ARC v3 запрещено.

Сохраняются descriptor, candidate generation, per-seed top4 nomination,
seed cap256, candidate/NCC cap64, NCC formula, numerical arithmetic/guard,
refinement delta ±4096, overlap/support/tie/channel behavior, текущие M1
precision windows и preprocessing capabilities. Запрещены рост caps, расширение
search bounds, full-duration scan вне текущих M1 representations, новый
preprocessing/dependency и изменения executable-кода репозитория.
Fixture/oracle speech/background masks разрешены **только для оценки**, не для
управления selection. Новое media acquisition не разрешено и не требуется:
используются только существующие M3-R3C evidence/corpus.

**До любых новых retention/NCC outcomes** M3-R3D-E обязан зафиксировать точные
experimental selectors, детерминированные grouping/selection procedure,
ordering/tie behavior, attribution feature set, evaluation metrics, baseline
comparison, включённые cases, resource protocol и falsification conditions.
SHA-256 преддекларации вычисляется и записывается **до outcomes**. Настройка
selector parameters после наблюдения outcomes запрещена. Преддекларация и
эксперимент в этой acceptance-задаче не создавались и не выполнялись.

**ARC v3 implementation — NOT AUTHORIZED.** Эксперимент может дать основания
за или против будущего ARC-v3 gate; предлагаемые изменения ARC baseline или
production/executable-кода репозитория требуют **STOP / OWNER GATE**.
Production tuning/calibration, threshold selection, analyzer и Finding не разрешены.

Все исходные M3-R3C evidence/review artifacts сохранены; новых источников нет.
Docs-only проверки: `git diff --check`, полный intended diff с untracked report
и итоговый status; tests/experiments/quality barrier/certification не запускались.
Принятие design result записано по явному решению владельца;
staging/commit остаются владельцу.

Descriptor, formula, compensated accumulation, normalization, NCC, guard,
search bounds, caps, overlap, support, ties и channels frozen v2 сохраняются.
Production calibration **NOT AUTHORIZED**, thresholds отсутствуют.
M3-R3B broad source-level validation остаётся **DEFERRED UNTIL CALIBRATION /
PRODUCTION-READINESS RESEARCH**, не обязательна для текущей дипломной фазы.
ATD-LOCAL-1 и ASC-TV-1 сохраняют **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**;
оба обязательства нерешённые, правило закрытия Macro 3 сохранено.
Macro 3 остаётся **IN_PROGRESS**.

<a id="audio-m3r3de"></a>

### M3-R3D-E — DONE / OWNER ACCEPTED RESEARCH RESULT

**Owner acceptance: 2026-09-29. Gate M3-R3D-E — CLOSED / OWNER ACCEPTED.**

**2026-09-29**, baseline `f70c9520842a48bb35ac836b2abc849a044609c0`, ожидаемая
ветка и clean start подтверждены. [Отчёт experiment](research/2026-09-29-audio-arc-attribution-retention-experiment.md)
содержит результаты всех184 cases для R0/R1/R2/R3. Frozen-v2 reproduction
**184/184 PASS**,7 numerical/oracle groups и8cases ×4policies ×3 exact executions
**PASS**. Union/order, seed cap256/NCC cap64, refinement bounds и baseline v2
сохранены; новых media/preprocessing или repo executable changes нет.

R1/R3 вернули по2 true nominations в cap stress, одна уникальная refined пара,
error311samples: within±4096 с structural support, **exact offset не восстановлен**.
R0/R2 retained truth=0. Все policies сохранили retained/localized/exact96/96
ordinary copy cases, но R1/R3 вернули673 truth pairs вместо1485. Benign high
correspondence и проблема semantic attribution сохраняются.

Принятый исследовательский outcome:
**DIVERSIFICATION_PROMISING_OWNER_GATE_FOR_FUTURE_ARC_CHANGE**;
best research policy **R1 / EXACT_OFFSET_ROUND_ROBIN**, не production behavior.
Attribution: **ATTRIBUTION_EXISTING_OUTPUTS_PARTIAL**. Simple automatic semantic
signature не установлена. Seed/union/caps/guard invariants и30s deadline соблюдены;
RSS не объявлен certified bound.

Остановка первого R1 до записи результата вызвана сравнением tuples/lists в
validation assertion. Исправлено только JSON-сравнение; исходный freeze,
traceback и исправленный seal сохранены. Selector-код, grouping/quotas и
параметры не менялись. Владелец явно принял experiment вместе с этой protocol
correction; история post-freeze исправления не удалена и не переописана как
неизменённый harness. Outcome-driven tuning не выполнялся.

Принят результат с его ограничениями: одна constructed flooding geometry,
неточная stress-localization, одна refined пара из двух nominations,
сокращение retained truth pairs и нерешённая semantic attribution. Это не
улучшение recall/sensitivity. Acceptance не разрешает ARC v3 implementation,
production tuning/calibration, thresholds,
analyzer или Finding. ARC-NCC-1 **NEEDS_TARGETED_RESEARCH**. ATD/ASC
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD** остаются нерешёнными;
M3-R3B broad validation остаётся deferred, Macro 3 **IN_PROGRESS**.

Review bundle: `FakeDetector-Work/reviews/M3-R3D-E-arc-attribution-retention/`.
Полный intended diff включает untracked report; `git diff --check` и итоговый
status проверены. Full quality barrier/strict certification не запускались;
Git mutations не выполнялись, staging/commit остаются владельцу.

В acceptance M3-R3D-E следующий ARC шаг **M3-R3D-F — R1 Flooding Confirmation
Study** был запланирован с незакрытым scope gate. Отдельное задание владельца
разрешило узкое confirmation study; его выполненный scope, принятый результат
и disposition записаны [ниже](#audio-m3r3df). Это не разрешение ARC v3.

**M3H-A01 — ARC Companion Applicability / Context Qualification:
DEFERRED RESEARCH HYPOTHESIS**, не активная задача. Смысл, допустимая
AMBIGUOUS / UNRESOLVED interpretation и отдельный source-separation/capability
gate сохранены в [METHODS](METHODS.md#audio-m3h-a01). Никакой experiment или
implementation гипотезы текущим решением не разрешён.

После явного disposition ATD/ASC, перед окончательным закрытием Macro 3,
запланирован **MACRO 3 DOCUMENTATION /
INSTRUCTION HYGIENE AUDIT**: проверить AGENTS.md и связанные governance/docs
на устаревшие временные правила, дубли инструкций, stale owner gates, историю,
которой место в research reports/changelog, и ненужные ветви процесса.
Это не произвольное сокращение AGENTS.md; **NO ACTION REQUIRED** допустим,
если всё активное содержимое необходимо. Аудит и cleanup сейчас не выполняются.
Macro 3 остаётся **IN_PROGRESS**, правило разрешения ATD/ASC carry-forward сохранено.

<a id="audio-m3r3df"></a>

### M3-R3D-F — DONE / OWNER ACCEPTED RESEARCH RESULT

**Owner acceptance: 2026-09-29. Gate M3-R3D-F — CLOSED / OWNER ACCEPTED.**

**2026-09-29**, baseline `4a528615e6a814aaa1476e92bfae509d5eeca5b5`, ожидаемая
ветка и clean start подтверждены. Owner scope разрешил только неизменённый R1
против R0,8 новых fixtures (2 speech recordings ×4 background families), старый
positive control и96 ordinary copy cases. Преддекларация и SHA-256 зафиксированы
до outcomes; новые selectors, attribution/M3H-A01 и production tuning не входили
в scope. [Отчёт](research/2026-09-29-audio-arc-r1-flooding-confirmation.md)
сохраняет recipes, identities, все результаты и ограничения.

Outcome — **R1_FLOODING_CONFIRMATION_MIXED**. Все8 новых cases имеют
**EFFECTIVE_FLOODING**, R0 retained truth0. R1 дал localized rescue в5/8 и
exact physical offset в2/8; rescue есть в каждом из4 background families,
но три synthetic cases второй source/geometry не восстановлены. Источники —
две записи одного speaker; causal effects source/placement не разделены.
No-effective-flooding и earlier-failure cases отсутствуют.
Старый cap stress точно воспроизведён (R1 две nominations →одна пара, error311,
не exact); ordinary R0/R1 сохраняют96/96 retained/localized/exact и1485/673
truth pairs. Семь oracle groups и заданные ×3 deterministic executions — PASS.
Прежние bounds/union/ARC v2/R1 сохранены; outcome-driven tuning отсутствует.

Владелец принял **MIXED** результат без усиления: R1 полезен за пределами прежнего
250Hz stress и во всех4 families, но не является универсальным flooding solution;
3/8 failures сохраняются, exact лишь2/8, pair multiplicity существенно сокращена.
Надёжное общее восстановление при flooding и semantic attribution не установлены.

**ARC disposition: RESEARCH MEASUREMENT DEMONSTRATED / PRODUCTION PROMOTION
DEFERRED**, с сохранением **NEEDS_TARGETED_RESEARCH**. Production promotion
отложено до последующих calibration / production-readiness research.
**Дальнейшее ARC retention development внутри текущего Macro 3 — DEFERRED**,
вне оставшегося пути его закрытия. ARC больше не активная исследовательская
ветвь этого Macro; новых ARC experiments, R1 tuning/variants, quotas/tolerances,
расширения search/caps или production implementation сейчас не разрешено.
Frozen v2 остаётся **FROZEN RESEARCH BASELINE**, R1 — **PROMISING FUTURE RESEARCH
DIRECTION**, не принятая реализация. ARC v3 и production tuning/calibration
**NOT AUTHORIZED**; production threshold отсутствует.

**Следующий активный topic — ATD-LOCAL-1 carry-forward disposition.**
Следующая отдельно поставленная задача должна определить явное решение по ATD.
ATD-LOCAL-1 и ASC-TV-1 сохраняют **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**;
оба обязательства нерешены. Новые ATD measurements в этой acceptance-задаче
не выполнялись и не разрешены. M3H-A01 — **DEFERRED RESEARCH HYPOTHESIS**,
source separation **NOT AUTHORIZED**, второй analyzer не реализован.
M3-R3B broad source-level / population validation остаётся **DEFERRED UNTIL
CALIBRATION / PRODUCTION-READINESS RESEARCH**, gate не переоткрывается.
Macro 3 **IN_PROGRESS**; прежнее closure rule сохранено. Hygiene audit остаётся
запланированным после ATD/ASC disposition, сейчас не выполняется;
**NO ACTION REQUIRED** остаётся допустимым будущим исходом.

Review: `FakeDetector-Work/reviews/M3-R3D-F-r1-confirmation/`; полный intended
diff включает untracked report. `git diff --check` и итоговый status проверены.
Новых media/dependencies/preprocessing/repo executables нет. Предыдущие evidence
trees не изменены. Full quality barrier/strict certification не запускались;
Git mutations не выполнялись, staging/commit остаются владельцу.

<a id="audio-m3-atd-d1"></a>

### M3-ATD-D1 — DONE / OWNER ACCEPTED DISPOSITION

**Owner acceptance: 2026-09-29. ATD carry-forward gate — CLOSED / RESOLVED.**

**2026-09-29**, baseline `136efa9741c226da616d76846a5e0755c5b70612`, ожидаемая
ветка и clean start подтверждены. Выполнен review существующих M3-R2A evidence,
без новых экспериментов и без изменения предшествующих материалов.
[Отчёт ATD](research/2026-09-29-audio-atd-disposition-review.md) разделяет
воспроизводимость физического измерения и недостаточную forensic-селективность.

**Принятый статус ATD-LOCAL-1: RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED.**
Владелец принял валидность описательного измерения и отсутствие установленной
forensic-селективности. Сильный benign
overlap и ограниченная локализация controlled splice не обосновывают promotion
текущего ATD. Одна малая дополнительная гипотеза, способная изменить disposition,
не выделена; TARGETED_NEXT_STUDY не предлагается. Production acceptance,
threshold/calibration, analyzer/Finding и fake probability не разрешаются.

**ATD REQUIRED CARRY-FORWARD — RESOLVED.** Дальнейшая ATD promotion work
в текущем Macro 3 отсутствует; новый ATD experiment не начинается. Прототип
остаётся research/descriptive evidence для будущей работы, не обязательством
нынешнего Macro 3. ASC-TV-1 сохраняет
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**, **OPEN / REQUIRED**.
Вывод ATD не зависит от ASC, fusion и statistical independence не утверждаются.

ARC остаётся неактивным/deferred согласно принятому M3-R3D-F; его scope не
переоткрывается. Macro 3 — **IN_PROGRESS**, прежнее правило явного disposition
для каждого carry-forward сохраняется. **Следующий активный topic — ASC-TV-1
carry-forward disposition.** После ASC disposition запланирован **Macro 3
documentation / instruction hygiene audit**, затем Macro 3 closure review.
ASC work и hygiene audit в этой acceptance-задаче не выполнялись. M3H-A01
остаётся deferred; ARC — RESEARCH MEASUREMENT DEMONSTRATED / PRODUCTION
PROMOTION DEFERRED, без активной работы.

Запись принятого решения и обновлённый полный diff требуют owner review;
staging/commit остаются владельцу.
Review bundle acceptance: `FakeDetector-Work/reviews/M3-ATD-D1-disposition/acceptance/`, включая полный
intended diff с untracked report. `git diff --check`, просмотр diff и итогового
status обязательны; тесты, эксперименты, full quality barrier и certification
не запускались. Git mutations не выполнялись, staging/commit остаются владельцу.

<a id="audio-m3-asc-d1"></a>

### M3-ASC-D1 — DONE / OWNER ACCEPTED DISPOSITION

**Owner acceptance: 2026-09-30. ASC carry-forward gate — CLOSED / RESOLVED.**

**2026-09-30**, baseline `a2169e566a4d1cebf15bbd715397a75312eacb0b`, ожидаемые
ветка/HEAD и clean start исходного review подтверждены. Запись принятия
M3-ASC-D1-A выполнена на том же HEAD поверх ожидаемого dirty diff M3-ASC-D1.
Выполнен review существующих ASC evidence
M3-R2A, без новых экспериментов и без изменения предшествующих материалов.
[Отчёт ASC](research/2026-09-30-audio-asc-disposition-review.md) отдельно
рассматривает TV и flux, physical measurement, benign overlap, controlled
manipulation и пределы локализации. Принятый disposition и ограничения
зафиксированы в [METHODS](METHODS.md#audio-m3-asc-d1).

**ASC-TV-1: RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED.**
**ASC REQUIRED CARRY-FORWARD: RESOLVED.** Владелец принял валидность TV/flux
как описательных измерений и отсутствие установленной forensic-селективности;
численные свидетельства сохранены. **FURTHER_ASC_PROMOTION_WORK_IN_CURRENT_MACRO3:
NONE**; новый ASC experiment не начинается, прототип остаётся research evidence.
ATD — **RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED**, carry-forward **RESOLVED**;
ATD не переоткрывается. ARC — **RESEARCH MEASUREMENT DEMONSTRATED / PRODUCTION
PROMOTION DEFERRED**, активной работы нет; M3H-A01 остаётся deferred.

**MACRO3_ALL_REQUIRED_CARRY_FORWARD_RESOLVED: YES.** Следующая активная задача —
**MACRO 3 DOCUMENTATION / INSTRUCTION HYGIENE AUDIT**, затем
**MACRO 3 CLOSURE REVIEW**. Macro 3 **IN_PROGRESS**, автоматического закрытия нет.
Hygiene audit позднее проверит AGENTS.md, governance/process docs, устаревшие
временные инструкции, дубли правил, obsolete owner gates, исторический материал
для research/changelog и возможную неоднозначность прежнего carry-forward
protocol text. **NO ACTION REQUIRED** остаётся допустимым исходом; необходимость
cleanup не предрешена. Hygiene и closure в M3-ASC-D1-A не выполняются.

Research/review bundles: `FakeDetector-Work/research/M3-ASC-D1-disposition/`
и `FakeDetector-Work/reviews/M3-ASC-D1-disposition/`; новый review bundle принятия —
`FakeDetector-Work/reviews/M3-ASC-D1-disposition/acceptance/`.
Полный intended diff включает
untracked отчёт. Проверки: `git diff --check`, просмотр полного diff и итогового
status; full quality barrier, тесты и certification не запускались по scope.
Production method/threshold/Finding не разрешены; Git mutations не выполнялись,
изменения остаются unstaged. Disposition принят; корректность записи принятия
и обновлённый полный diff требуют owner review, staging/commit остаются владельцу.

<a id="audio-m3-hyg-1"></a>

### M3-HYG-1 — DONE / OWNER ACCEPTED

**Owner acceptance: 2026-10-01. Hygiene owner-review gate — CLOSED.**
**HYGIENE_OUTCOME: BOUNDED_CLEANUP_PERFORMED / OWNER ACCEPTED.**
Ограниченные правки приняты; дальнейшей активной hygiene work нет.

**2026-10-01**, baseline `6ce26e40b8bf93104ab7b2c355ea2273491c9bfa`;
ожидаемые ветка/HEAD и clean start исходного M3-HYG-1 подтверждены. Запись
принятия M3-HYG-1-A выполнена на том же HEAD поверх ожидаемого dirty diff
завершённого cleanup. После инвентаризации выполнен
ограниченный documentation / instruction hygiene cleanup: прежние статусы и
следующие шаги отделены от текущих требований в METHODS/ROADMAP, устранены
устаревшее описание отсутствия forensic demand в CONTRACTS и пропуск принятого
`pyjpegio` в справочном списке PROJECT. AGENTS и исторические research records
сохранены. Принятые ATD/ASC/ARC dispositions и M3H-A01 не пересматриваются.

Материалы: `FakeDetector-Work/research/M3-HYG-1-doc-hygiene/` и
`FakeDetector-Work/reviews/M3-HYG-1-doc-hygiene/`. Проверки ограничены
`git diff --check`, полным intended diff и итоговым status; эксперименты,
тесты, quality barrier и certification не выполняются по scope задания.
Следующая активная задача — **MACRO 3 CLOSURE REVIEW**; она не выполняется
в M3-HYG-1-A. Macro 3 остаётся **IN_PROGRESS** до отдельного closure review
и решения владельца.

<a id="audio-m3-cr1"></a>

### M3-CR1 — DONE / OWNER ACCEPTED CLOSURE

**Owner acceptance: 2026-10-01. CLOSURE_RECOMMENDATION: MACRO3_CLOSE / OWNER ACCEPTED.**
**Macro 3 — DONE / CLOSED / OWNER ACCEPTED.** Владелец явно принял рекомендацию
закрытия; все разрешённые обязательства выполнены либо получили явное итоговое
решение или отсрочку. Результаты задокументированы и проверены.
Активных исследований и owner gates Macro 3 нет.
Baseline `53ffbed543a39d0674f1dcc0ea80035ce68455f7`, ветка
`feat/stage12-macro3-audio-analyzer-expansion-wave1`; ожидаемые ветка/HEAD
совпали, начальное дерево исходного M3-CR1 чистое. Review выполнен до правок
документации. Запись принятия M3-CR1-A выполнена на том же HEAD поверх ожидаемого
dirty diff завершённого M3-CR1; изменён только ROADMAP.

Проверены канонические документы, все принятые M3-R1, R2A/R2B, R3A/R3B/R3C,
R3D-P/E/F, ATD-D1 и ASC-D1 records, состояние M3-HYG-1 и diff Macro 3 от
baseline M3-R1. Все разрешённые исследовательские обязательства имеют явные
dispositions; [required carry-forward](#audio-m3-required-carry-forward)
ATD/ASC разрешены, hygiene gate закрыт. Текущих нерешённых обязательных gates
не обнаружено. Отложенные ARC promotion/retention, broad validation и M3H-A01
не требуют нового исследования для закрытия. Отсутствие нового production
audio-анализатора соответствует принятым исходам; методы не продвигаются.

Production-каталог проверен по исходнику и runtime registrations: прежние пять
анализаторов версии 1.0.0 по PROJECT §6.10. Исполняемые файлы, зависимости,
API/schema, preprocessing и семантика результатов не изменены за Macro 3.
Принятые исправления HYG не меняют контракты. Graphify **STALE** и не использован
как closure evidence; пересборка не требуется. Новых экспериментов нет.

Сохранён результат M3-CR1: полный `uv run poe check` на указанном baseline —
**PASS**: pre-commit,
mypy (66 source files), pytest **2792 passed / 17 skipped**, coverage **90%**,
CLI smoke. `git diff --check` — **PASS**; полный diff и итоговый status
проверены. В M3-CR1-A тесты, эксперименты и quality barrier не повторялись;
выполнены только документационные diff/status проверки по scope задания.
Strict certification **DEFERRED_UNTIL_CLEAN_COMMITTED_CLOSURE_SHA**.
Непосредственное следующее действие после commit записи закрытия владельцем —
**STRICT PACKAGE CERTIFICATION ON CLEAN COMMITTED CLOSURE SHA**, только после
подтверждения чистого репозитория. В этой задаче certification не запускается;
Macro 4 не начинается. Финальная сертификация Stage 12 остаётся в Macro 10.

Review bundle: `FakeDetector-Work/reviews/M3-CR1-closure/` — inventory,
проверки dispositions/carry-forward/catalog/contracts/scope/semantics,
closure recommendation, review-summary, complete.diff и git-status.txt.
Acceptance bundle: `FakeDetector-Work/reviews/M3-CR1-closure/acceptance/` —
acceptance-only.diff, complete.diff от HEAD, review-summary.md и git-status.txt.
Принятые ATD/ASC/ARC/ABN/AMC dispositions и M3H-A01 сохраняются: deferred work
не отменена, research-only методы не продвигаются, production thresholds не приняты.
Закрытие принято владельцем; корректность записи решения и полный intended diff
предоставлены для owner review. Изменения unstaged, Git mutations не выполнялись.

<a id="video-m4r1"></a>
## Macro 4 — Video Analyzer Expansion — Wave 1 — IN_PROGRESS

<a id="video-m4r2-closeout"></a>
### M4-R2 — закрытие VRC-DENSE-1 Stage A и G5 DEFER, 2026-10-12

**OWNER ACCEPTED / COMPLETE WITH ENGINEERING FAIL**: владелец явно принял
независимый OWNER review **PASS** в задании
`M4-R2-VRC-STAGE-A-CLOSEOUT-DEFER`. Закрыт только исследовательский трек
M4-R2 / VRC Stage A: **COMPLETE / SYNTHETIC_ONLY / COMPLETE_144_CELL_MATRIX**.
Macro 4 и Stage 12 остаются **IN_PROGRESS**.

| Показатель | Принятый результат |
|---|---|
| Composite matrix | 144 cells: 133 VALID, 11 LOCAL_FAIL, 0 GLOBAL_STOP, 0 NOT_EXECUTED |
| G1 | PASS |
| G2 | FAIL |
| G3 | PARTIAL |
| G4 | NOT_EVALUATED_STAGE_A |
| G5 disposition | DEFER |
| Formal determinism, 48 slots | 41 PASS, 0 FAIL, 7 NOT_FULLY_EVALUATED |
| Stage B | BLOCKED / NOT AUTHORIZED |
| Production | UNCHANGED / NO VRC PROMOTION; ровно пять анализаторов |
| Further full Stage A rerun | NOT PLANNED |

Composite объявлен отдельно: неизменный AJ-06 prefix, positions 1..132 до
**B02-r3**, плюс AJ-07 **B03..B06**, все три fresh repeats, 12 cells.
AJ-06 **B03-r1 и B03-r2 исключены** из composite. Это не переименование AJ-06
в завершённую серию и не выбор успешных повторов по outcomes.

Все 11 LOCAL_FAIL имеют причину **RESOURCE_MONITOR_SAMPLING_GAP**:
это engineering/resource failures, не scientific mismatches. В принятом
composite нет свидетельств numeric determinism mismatch, ошибки научной
арифметики VRC, binding failure, RSS >1 GiB, scientific output-cap failure
или lifecycle ownership failure. **NO OBSERVED NUMERIC MISMATCH** не означает
**FORMAL DETERMINISM PASS FOR ALL 48 SLOTS**; семь NOT_FULLY_EVALUATED не становятся
PASS на основании совпавших диагностических проекций.

Научная интерпретация, exact-copy support/coverage и основания **DEFER** —
в [METHODS](METHODS.md#video-m4r1). G2 FAIL и G3 PARTIAL сохранены; реальный
корпус не допущен, G4 невозможно оценить в Stage A, а P1 требует разрешения
engineering failures до Stage B. Допуска M4-R2-E real-source execution нет:
acquisition, R01–R12 evidence и Stage B manifests не создаются. Production
implementation, runtime/config/public schema, новый Finding type и независимый
forensic/risk vote не разрешены.

Матрица из 144 cells завершена. Дальнейший полный Stage A rerun **NOT PLANNED**;
G2 failure сохраняется, outcome-driven rerun и retry-until-pass не разрешены.

Исторические серии остаются неизменными свидетельствами:

| Серия | Сохранённый статус |
|---|---|
| AJ-01 | STOPPED / G2 FAIL / historical |
| AJ-02 | STOPPED / G2 FAIL / historical |
| AJ-03 | STOPPED / G2 FAIL / historical |
| AJ-04 | STOPPED / G2 FAIL / historical |
| AJ-05 | STOPPED PREFLIGHT / 0 FORMAL ATTEMPTS / historical |
| AJ-06 | STOPPED / G2 FAIL / historical |
| AJ-07 | COMPLETED 12/12 completion extension |

Исторический AJ-06 B03-r2 сохраняет **ROOT_CAUSE_NOT_ESTABLISHED**;
публикационная гонка не объявляется доказанной причиной того JSONDecodeError.
**HANDLE_COUNT_RESIDUAL: UNATTRIBUTED +3** сохраняется как
**RESIDUAL / NOT ESTABLISHED AS HARNESS HANDLE LEAK**. Он не объявлен ни
безвредным, ни доказанной утечкой. Исторические resource-monitor scheduling
outliers сохранены в исходных evidence; новой диагностики или перезапуска
ради этих findings в closeout нет.

Основания и неизменные ссылки (SHA-256):

- [Frozen P1](research/2026-10-01-video-vrc-protocol.md):
  `e78cec2d22914f8bff26b5a8c831975be3d00dbcc4cd0aad04b96653ba738a0f`;
- accepted AJ-07 harness manifest:
  `d6b740c37a73342c06826673b06fff823d01c91af0974c956a6e8bb01a4dea37`;
- accepted Stage A completion declaration:
  `9e02b2b986c09fc25a6615635bc42575963159aaf7fe3e80f79ae97eed18ee33`.

Принятый внешний bundle:
`FakeDetector-Work/reviews/M4-R2-VRC-stage-a/formal-aj07-stage-a-completion/`
(`07-aj07-manifest.json`, `08-stage-a-completion-declaration.json`,
`14-stage-a-composite-final-matrix.json`, `15-composite-source-map.json`);
AJ-06: `FakeDetector-Work/reviews/M4-R2-VRC-stage-a/formal-aj06-complete-matrix/`.
Именованный независимый review —
`FakeDetector_OWNER_REVIEW_STAGE_A_AJ07_2026-10-12.md`; локальная копия при
closeout не найдена. Основание принятия — явное OWNER DECISION текущего задания,
решение review не пересчитывалось. Closeout bundle с полным diff и source hashes:
`FakeDetector-Work/reviews/M4-R2-VRC-stage-a/stage-a-final-closeout/`.

**NEXT_UNRESOLVED_MACRO4_ITEM: VCM-FRAME-1** — существующий вторичный кандидат,
**TARGETED_RESEARCH / INACTIVE**. Это навигация для владельца, не разрешение
исследования и не назначение новой задачи. Остальные dispositions Macro 4
сохранены. Закрытие VRC Stage A само по себе не закрывает Macro 4;
следующая работа не начинается. **STOP / OWNER GATE** после review closeout.

### M4-R1 — выбор измерения и план исследования, 2026-10-01

Ниже историческая запись состояния M4-R1-A; прежний checklist и следующий шаг
не назначают текущую работу. Актуальный статус — в [закрытии Stage A](#video-m4r2-closeout).

Исторический baseline M4-R1: ветка `feat/stage12-macro3-audio-analyzer-expansion-wave1`,
HEAD `c4488109e56c90c3b715779ad7d11f900b51c5b8`, чистое рабочее дерево.
**Macro 3 — DONE / CLOSED / OWNER ACCEPTED / STRICTLY CERTIFIED** по явному
подтверждению владельца в задании M4-R1. Это обновляет прежнее ближайшее действие
о сертификации после closure commit; исторические записи M3-CR1 описывают
состояние на тот момент. Агент в M4-R1 сертификацию не повторял и новые
certification artifacts не заявляет. Dispositions и carry-forward Macro 3
не переоткрыты.

**M4-R1 — DONE / OWNER ACCEPTED METHOD SELECTION**: решение владельца
от 2026-10-01 записано в M4-R1-A. Рабочая ветка при M4-R1-A —
`feat/stage12-macro4-video-analyzer-expansion-wave1`, HEAD тот же;
начальное состояние M4-R1-A — ожидаемые незакоммиченные изменения M4-R1
в METHODS, ROADMAP и новом research report. Принято исследовательское
направление, а не production-метод или спецификация.

- [x] сверить production-каталог: ровно пять прежних анализаторов `@1.0.0`;
- [x] изучить validation, legacy sampling, on-demand timing/dense/AV,
  image reuse, tests и CLI/result semantics;
- [x] оформить ответственность текущего video analyzer, descriptive scorecard,
  ограничения sampling и один bounded next-study plan;
- [x] получить owner acceptance M4-R1: принято исследовательское направление;
- [ ] завершить owner review M4-R1-A и commit владельцем;
- [ ] выполнить следующую активную задачу M4-R2; production gate остаётся
  закрытым до необходимых свидетельств и явного принятия владельцем.

Подробные основания и proposed profile находятся в
[отчёте M4-R1](research/2026-10-01-video-method-selection.md);
методический статус — в [METHODS](METHODS.md#video-m4r1).
**На момент M4-R1-A: VRC-DENSE-1 — PROTOTYPE_NEXT / OWNER ACCEPTED RESEARCH DIRECTION**
как исследование расширения существующей
responsibility `video_sampled_frame_quality`, без дублирующего анализатора
и независимого risk vote. **VCM-FRAME-1 — TARGETED_RESEARCH / INACTIVE** —
вторичный кандидат. Discontinuity/regional timing остаются
research-only, GOP/codec и semantic A/V — deferred. Image metadata/JPEG DQ
не переносятся на decoded frames.

**Следующая задача на момент M4-R1-A: M4-R2 — VRC-DENSE-1 Bounded Measurement
Prototype**, после owner review M4-R1-A и commit владельцем. В M4-R1-A M4-R2,
media acquisition и измерения не выполнялись. Предложенные параметры нужно
зафиксировать до измерений; forensic specificity ещё не установлена,
повторяющееся содержание не доказывает манипуляцию. Принятие не разрешает
production method/thresholds, Findings, severity/risk, probability/verdict,
catalog registration, новое preprocessing, dependencies или runtime API/schema.
Production-каталог сохраняет ровно пять принятых анализаторов.

Изменения только в METHODS, ROADMAP и новом research report. Проверки —
`git diff --check`, полный intended diff включая untracked report и итоговый
status; tests, full quality barrier и certification исключены scope задания.
Graphify STALE, не использовался и не пересобирался; Git mutations нет.
Внешние материалы: `FakeDetector-Work/research/M4-R1-video-selection/` и
`FakeDetector-Work/reviews/M4-R1-video-selection/` (включая complete.diff).
Запись принятия M4-R1-A предоставлена для owner review в подкаталоге
`reviews/M4-R1-video-selection/acceptance/`: acceptance-only.diff, complete.diff
включая untracked report, review-summary.md и git-status.txt.
Macro 4 и Stage 12 остаются IN_PROGRESS.

### M4-R2-P — протокол и готовность корпуса, 2026-10-01

Ниже историческая запись подготовки и принятия P1, включая checklist на тот
момент. Текущее исполнение закрыто в [Stage A closeout](#video-m4r2-closeout).
Frozen P1 сохранён byte-identical, его исторические planning statements
не являются текущим статусом исполнения.

**DONE / OWNER ACCEPTED**: владелец принял весь рассмотренный протокол
2026-10-01 в M4-R2-P-A. **VRC-DENSE-1/P1 — FROZEN RESEARCH PROTOCOL**.
Исторический baseline M4-R2-P: ветка
`feat/stage12-macro4-video-analyzer-expansion-wave1`, HEAD
`bc767c2cc2f8ea0110c2208705ae36d787130251`, чистое committed дерево;
запись M4-R1-A уже присутствует в baseline. Это подготовка, не запуск M4-R2.
M4-R2-P-A начата на той же ветке/HEAD с ожидаемыми незакоммиченными изменениями
M4-R2-P: METHODS, ROADMAP и untracked protocol report; эти изменения сохранены.

[Протокол VRC-DENSE-1/P1](research/2026-10-01-video-vrc-protocol.md)
конкретизирует M4-R1 §7 без изменения формул и producer limits:
Stage A — 42 procedural + 6 boundary slots; Stage B — до 12 независимых
real groups × 4 variants. Реальные записи **NOT ADMITTED**, все 12 slots missing.
Stage A самостоятельно даёт только SYNTHETIC_ONLY; added-value gate требует
минимум двух независимых eligible real groups. Recipes и analytic/resource
oracles заданы до outcomes; encoder capabilities проверены read-only,
encoding/generation/measurements не выполнялись.

- [x] подготовить profile, manifest/transform recipes, права/provenance template,
  support/truth rules, resource и determinism plans для owner review;
- [x] получить owner acceptance конкретного frozen protocol: 2026-10-01;
- [ ] отдельно разрешить M4-R2-E и выполнить инженерную Stage A;
- [ ] допустить permitted real files/provenance/hashes перед Stage B;
- [ ] рассмотреть результаты без автоматического production promotion.

**На момент M4-R2-P-A: M4-R2-E — NEXT / SEPARATE EXECUTION AUTHORIZATION REQUIRED**.
Следующей задачей была **M4-R2-E / Stage A** (42 procedural + 6 boundary cases);
в M4-R2-P-A она не выполняется. Stage B — **BLOCKED / REAL_CORPUS_NOT_ADMITTED**;
R01–R12 не являются существующими/admitted research evidence.
Synthetic-only результат не удовлетворяет real-source added-value gate.
Engineering watchpoints Stage A сохранены в protocol report §8.4: возможные
превышения 20 MiB lossless derivatives и 4 MiB полного JSONL pair output.
Они не разрешают менять P1; материальное изменение требует новой версии
протокола и отдельного OWNER GATE.
Production method/thresholds, новый analyzer ID, Findings, preprocessing,
dependencies и public API/config/schema не разрешены. VCM-FRAME-1
TARGETED_RESEARCH / INACTIVE; Macro 3 CLOSED / STRICTLY CERTIFIED;
Macro 4 и Stage 12 IN_PROGRESS. Production-каталог сохраняет пять анализаторов.

Изменены только METHODS, ROADMAP и новый protocol report. Для этой docs-only
задачи предусмотрены `git diff --check`, полный intended diff с untracked report
и итоговый status; tests, full quality barrier и certification не запускаются.
Внешние snapshots: `FakeDetector-Work/research/M4-R2-VRC/`; owner review bundle:
`FakeDetector-Work/reviews/M4-R2-VRC-protocol/` (complete.diff с полным новым report).
Принятие основано на явном решении владельца; запись M4-R2-P-A требует owner review.
Acceptance bundle в подкаталоге `reviews/M4-R2-VRC-protocol/acceptance/`:
acceptance-only.diff, complete.diff, review-summary.md, git-status.txt,
protocol-sha256.txt. Hash финального report служит ссылкой для будущей M4-R2-E;
исполнение, media generation, encoding trials и новые измерения не выполнялись.

## Macro 6 — корреляция и смысл результата

Из закрытого Macro 2 перенесён **M2H-D01 — DEFERRED TO MACRO 6**.
Это отложенный вопрос, не блокер закрытия Macro 2; его решение требует
отдельно разрешённой работы Macro 6.

Размер портфеля не равен числу независимых свидетельств. ELA, double
quantization, JPEG grid и JPEG ghost могут отражать общую историю JPEG-обработки;
audio temporal/spectral/background transitions — одну границу монтажа.
Видеообёртки image/audio-ядер должны сохранять исходное семейство свидетельств,
а не добавлять независимый голос только из-за `media=video`.

До отдельно утверждённого изменения действуют точные правила
`CONTRACTS.md` §11.4. Семейство свидетельств здесь — понятие планирования,
не новое поле схемы и не автоматическая группировка по сходству названий.
Macro 6 проверяет взаимодействия методов, отсутствие повторных вкладов,
честную полноту активного профиля, ограничения и формулировки рекомендаций.
Macro 0 не изменяет веса, пороги, `correlation_group` или риск-движок.

## Macro 7–8 — наблюдения ручного знакомства с продуктом

2026-09-20 владелец собрал сертифицированный ZIP, распаковал его вне репозитория,
создал чистое venv, установил wheel с runtime constraints, выполнил
`uv pip check`, запустил установленный CLI, открыл WebUI и попробовал
image/audio/video. Это **неформальное знакомство с продуктом**, не формальная
приёмка Stage 12 и не новая выполненная проверка этого прохода.

Будущий backlog Macro 7, проверяемый в Macro 8:

- человекочитаемое представление `completed`, `complete`, `low`, `weak`,
  при необходимости — понятные значки статуса;
- RU/EN WebUI на стабильных смысловых ключах; авторская английская строка
  анализатора не должна быть единственным основанием перевода;
- читаемые локализованные временные метки;
- `coverage_ratio`, `error=[]`, `timeout=[]` и сходные технические сведения
  в подробностях, а не на первом плане обычного результата;
- визуализация локализованных в медиа признаков, где это разрешено контрактами;
- осторожные рекомендации при слабых признаках вместо чрезмерно категоричного
  «дополнительные действия не требуются»;
- неизменные канонические API/domain enums и смысл результата при смене языка.

Презентационный перевод сам по себе не требует изменения `CONTRACTS.md`.
Если понадобится изменение смысла рекомендации, его отдельно рассматривает
Macro 6; WebUI не пересчитывает риск или рекомендации.
Macro 8 должен заранее закрепить разрешённый корпус, ожидаемые ограничения,
метрики/критерии, версии профиля и воспроизводимые сценарии ручной приёмки,
включая неполный анализ и ложноположительные случаи. Генерируемые тестовые
примеры не подменяют реальный корпус и статистическую проверку.

## Критерии завершения Stage 12

- [ ] Macros 0–10 завершены по собственным критериям, результаты приняты владельцем;
- [ ] согласованные волны расширяют image/audio/video набор реальными методами;
  каждый имеет provenance, проверку прав, объяснимые признаки и пределы применимости;
- [ ] общие представления/ядра реализованы до зависимых анализаторов без
  дублирования парсинга и ослабления безопасности/cleanup;
- [ ] сохранены CPU-only, offline, bounded execution, закрытый каталог,
  структурированные результаты и отсутствие выдуманной вероятности;
- [ ] проверены корреляция, полнота, рекомендации и отсутствие завышенных выводов;
- [ ] выполнены согласованный WebUI/RU/EN объём и формальная приёмка на корпусе;
- [ ] проектная лицензия выбрана и оформлена; права и уведомления для фактической
  поставки проверены, ограничения сторонних бинарных компонентов учтены;
- [ ] Macro 9 подготовил и выпустил согласованную GitHub-поставку с сохранением
  гарантий установленного wheel; публикация и Git-действия выполнены владельцем;
- [ ] финальный аудит, относящиеся к реализации тесты/quality checks и строгая
  installed-wheel certification прошли, замечания закрыты;
- [ ] ML-реализация, веса и ML runtime не добавлены; Stage 13+ остаётся отдельно.

---

# Stage 13+ — Дальнейшие расширения — AFTER_MVP / NOT_STARTED

ML-реализация и остальные перечисленные ниже направления не начаты в Stage 12
и требуют отдельного решения владельца.

## Анализ и качество

- [ ] расширенные ML-модели;
- [ ] калибровка вероятности;
- [ ] экспериментальные датасеты сверх корпуса Stage 12;
- [ ] метрики качества будущих ML-моделей;
- [ ] сравнение моделей;
- [ ] обновление разрешённых critical-признаков.

## Хранение и пользователи

- [ ] SQLite;
- [ ] история анализов;
- [ ] поиск по SHA-256;
- [ ] очистка результатов по сроку;
- [ ] роли и права;
- [ ] развитая аутентификация.

## Интеграции

- [ ] почтовый коннектор;
- [ ] SIEM;
- [ ] DLP;
- [ ] SOAR;
- [ ] внешние форматы событий;
- [ ] автоматизированные сценарии реагирования вне ядра.

## Инфраструктура

- [ ] Docker;
- [ ] CI/CD;
- [ ] эксплуатационный мониторинг;
- [ ] внешний брокер задач;
- [ ] отдельные GPU-обработчики;
- [ ] распределённая обработка.

---

## 4. Блокеры и решения

BLOCKER Этапа 1: неподдерживаемый `logging.level` и ошибки открытия собственного
log handler приводили к необработанным исключениям до Uvicorn. Устранён:
уровень валидируется моделью, ошибки handler преобразуются в безопасную
`LoggingSetupError`, CLI завершается с кодом 4 без запуска Uvicorn.

Активные BLOCKER Этапа 1 отсутствуют.

Решение Stage 12 Macro 0 `PROJECT_LICENSE` — **CLOSED**: владелец выбрал
Apache-2.0 в Pass 2 от 2026-09-20; проектное решение — `PROJECT.md` §21.7,
лицензионный реестр — `REFERENCES.md`. Открытого вопроса о выборе лицензии нет.

Исторические точки принятия решений для завершённых этапов 6–10
(актуальные решения — в `PROJECT.md` и `CONTRACTS.md`):

| Когда | Вопрос | До решения можно продолжать? |
|---|---|---|
| Перед этапом 6 | Минимальный набор реальных анализаторов | Да, с тестовыми анализаторами |
| Перед этапом 6 | Характеристики компьютера и CUDA | Да, до ML |
| Перед этапом 7 | Веса, пороги и полнота | Да, можно реализовать версионируемый движок и тестовую конфигурацию |
| Перед этапом 7 | Critical override policy | Да, оставить выключенным |
| Перед этапом 8 | Синхронный/асинхронный API | Да, ядро не зависит от HTTP-профиля |
| Перед этапом 8 | Аутентификация WebUI | Да, до внешнего пользовательского доступа |
| Перед этапом 10 | Формат поставки | Да, локальный запуск остаётся базой |

---

## 5. Definition of Done для любой задачи

Задача считается выполненной, когда:

- [ ] поведение реализовано;
- [ ] код типизирован;
- [ ] добавлены тесты;
- [ ] тесты проходят;
- [ ] Ruff проходит;
- [ ] mypy проходит для затронутого кода;
- [ ] контракты не нарушены;
- [ ] временные данные очищаются;
- [ ] ошибки безопасны;
- [ ] секреты и runtime не попали в Git;
- [ ] чек-лист обновлён;
- [ ] изменение проекта отражено в `CHANGELOG.md`, если требуется.
