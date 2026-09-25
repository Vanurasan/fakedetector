# M2-R3D — однократный финальный holdout замороженного DQ

Дата: 2026-09-24. Baseline: `36ccaf8aef8ad2a90d5d82f0c799185f18751691`,
ветка `feat/stage12-macro2-image-analyzer-expansion-wave1`.
M2-R3C принят владельцем в задании R3D. Это исследовательское свидетельство,
не production acceptance, не закрытие M2-A и не strict certification.

**FINAL_HOLDOUT_PASS:** 0 FP / 308 применимых независимых source endpoints;
односторонняя точная 95% верхняя граница FPR —
**0,009679255008705269 = 0,9679255008705269% ≤1%**.
Назначены и допущены 320 групп, abstentions — 12, отказы допуска — 0.
Результат относится к заданному контролируемому single-history JPEG endpoint
и исследованному составу источников, с ограничениями независимости ниже.

## Решения владельца до открытия исходов

Первоначальная цель — 500 групп. После исключения всех кандидатов R3B/R3C
старые RAW-фильтры оставляли только 367 записей ещё до проверки сцен и проявки.
Владелец разрешил расширить acquisition PIXLS CC0, сохранив DQ и RAW-профиль.
Подготовлены две очереди: 763 кандидата и дополнительно 120; они сформированы
по metadata без DQ. До завершения QA оптимистическая верхняя оценка была
446 групп, не число допущенных независимых источников.

Владелец затем явно заменил цель 500 на **максимум пригодных независимых
PIXLS CC0 source groups после полной outcome-blind QA**, без произвольного
уменьшения выборки. Это решение принято до freeze и первого DQ-измерения.
Критерий `upper_95 <= 0.01` по фактическому applicable n не менялся.
Итоговые 320 — все пригодные группы объявленного acquisition-пула после QA,
а не выбранное по результатам или удобству число.

## Замороженное правило и последовательность freeze

Использован исходный canonical artifact `DQ-R3C-1` из
[R3C](2026-09-24-jpeg-dq-final-calibration.md), без пересериализации или настройки.

| Параметр | Зафиксированное значение |
|---|---|
| Метрика | `empty_fraction` |
| Threshold | `0.6005747126436781` |
| Решение | Строго `score > threshold`; равенство — negative |
| Компонент | Первый в SOF order |
| AC modes | `(0,1),(0,2),(0,3),(1,0),(1,1),(1,2),(2,0),(2,1),(3,0)` |
| Опора mode | `state=measured`, `N>=1024`, nonzero `>=256`, occupied `>=8`, span `>=16` |
| Агрегация | Медиана; для чётного количества среднее двух центральных значений |
| Опора изображения | Минимум пять valid modes; иначе `insufficient_evidence` |
| Статистический критерий | Односторонняя 95% exact Clopper–Pearson upper `<=0.01` |
| Замены | После membership freeze отсутствуют; после открытия нет добора или исключений |

SHA-256 исходного правила:
`2b958bf4fb94926c7f7de0a9a7b74f3897667a22cb802fb85592bab4dd5fd5be`.
Исходный implementation fingerprint R3C:
`f71d85640aa1624ad116a0da6e66401e329220231df642b0b25ca49ea43a21cf`.
Все перечисленные им файлы, включая baseline external runner, совпали побайтно.
Новый research-only orchestration имеет отдельный execution fingerprint;
он проверен перед прогоном, после него и при проверке воспроизводимости.

Финальный протокол `R3D-final-source-endpoint-1`, SHA-256:
`fa0d7fd86ac1279e2e33e675c2a79e278bfa619b62eff914f3005a6e37ee28ea`.

**Frozen membership manifest SHA-256:**
`99e52cc1f785bcaaaa8ca423e1c0c5487cb882d56b5e01bcf5f0027e8687a189`.

Membership freeze: `2026-09-24T05:15:27.692621+00:00`.
Exclusive opening marker: `2026-09-24T05:15:55.393590+00:00`.
До marker проверены rule hash, canonical manifest, связанные evidence assets,
все original/master/endpoint/terms hashes. Затем выполнен один полный прогон.
Повторное открытие того же manifest блокируется. До freeze DQ-исходы этих
групп не вычислялись; после открытия правило, corpus, preprocessing,
decision/abstention semantics и acceptance criterion не менялись.

## Источники, acquisition и права

Использованы только записи
[DATASET-PIXLS-CC0](../REFERENCES.md#dataset-pixls-cc0) с per-record CC0 URL
из прежнего publisher catalog snapshot. Его SHA-256:
`8dc5f5c74e20cc3a38f4548d53bba4bb516835e2a859e80bf86e7ac6283b3aa3`.
Сохранены record ID, source URL, publisher SHA-256, actual SHA-256, RAW format,
metadata, доступный EXIF, master hash, права, source/scene identity и
`split=final_holdout`. На странице поставщика повторно проверены декларации
прав и происхождения camera-native RAW; per-record условия сохранены в catalog.

Основная расширенная очередь использовала seed `2409202604`, shuffled order,
сначала одну casefold make/model пару, затем остальные записи. Дополнительная
очередь с seed `2409202605` добавлена до DQ после выявления дефицита независимых
групп. Итоговый порядок — первая очередь, затем дополнительная; представитель
каждой допустимой связной source/scene/session группы — первый пригодный в очереди.
Content quotas не подгонялись: содержание описано после outcome-blind QA.

Расширены только acquisition-форматы и потолок размера дополнительных RAW
с 50 до 150 MB; сохранены исключения известных lossy/неясных режимов,
small/medium RAW, pixel-shift, converter/linear/ProRAW/HDR и high-resolution
композитов по metadata. Для NEF/ARW требовались uncompressed/lossless сведения;
IIQ/TIF допускались только в обозначенных native RAW вариантах.
Это ограниченный admissible pool, не весь архив PIXLS.

Проявка осталась byte-identical R3C: прежний внешний
[rawpy environment](../REFERENCES.md#research-rawpy-m2r3b), Bayer 2×2 Flat/AHD,
фиксированный профиль, 60 MP input ceiling, timeout 120 s, один поток;
RGB8 PNG, Lanczos без upscale, максимум 1280 по стороне / 1 000 000 pixels.
Embedded previews не использовались. Runtime dependencies проекта не менялись.

| Acquisition / development | Число |
|---|---:|
| Новые metadata-кандидаты | 883 = 763 + 120 |
| Загруженные RAW | 883 |
| Совпали с publisher SHA-256 | 882 |
| Hash mismatch, исключён до проявки | 1 |
| Успешно проявлены | 802 |
| Отказы до финального назначения, включая hash mismatch | 81 |
| Загруженные bytes | 25 125 183 578 |

65 отказов связаны с неподдерживаемым фиксированным CFA-профилем;
4 — LibRaw data errors, 10 — unsupported/not RAW, 1 — LibRaw I/O,
1 — acquisition hash mismatch. Эти отказы произошли **до membership freeze**
и не являются holdout abstentions или holdout admission failures.

Корпус, изображения, EXIF, derivatives, journals, manifests и machine results
хранятся во внешнем workspace `fakedetector-m2-r3d-2026-09-24`.
Медиа и локальные corpus paths в Git не включены.

## Независимость и outcome-blind QA

Из пула исключены все 120 RAW-кандидатов R3B и все 300 кандидатов R3C,
включая резервы и отказы, вместе с известными производными/сценами/сессиями.
Manifest guards проверяют source group, scene group, URL, original/master hashes
и уникальность endpoint bytes; derivatives не увеличивают независимый n.
В exclusion evidence также сохранены hashes и identities приобретённых
пилотных VISION-файлов.

EXIF запрошен для 1303 RAW-записей (420 прежних + 883 новых): получено 1143,
84 запроса не дали metadata, у 76 отсутствовала ссылка. Одинаковая casefold
make/model и дата съёмки консервативно объединены в одну возможную сессию.
Дата съёмки доступна у 202 из финальных 320 представителей; у остальных
session metadata остаётся unknown. Make/model не доказывает физическое устройство.
Группы со связью к прежней partition исключены целиком; среди новых групп
непригодный представитель не лишает допуска другой пригодный member до freeze.

Bounded screening сравнил 1171 RAW master (369 прежних + 802 новых):
dHash64 distance `<=8` или grayscale 32×32 correlation `>=0.97`.
Получены 558 flagged pairs; связи уже известных групп учтены автоматически.
Дополнительно визуально разобраны 80 пар: 14 same-scene links и 66 разных сцен.
К завершению QA не осталось неразобранных пар, затрагивающих допускаемые группы.
Визуальный ledger содержит 595 masters; уже отвергнутые прежние сессии не
нуждались в повторном визуальном допуске. Исключены мишени, доминирующие
репродукции/люди с неясными правами и явные RAW development anomalies.

Для leakage QA отдельно сравнены 50 уже приобретённых native VISION pilot
источников с кандидатами: единственная flagged pair визуально различна.
Это проверка пересечений, **не новый VISION stress experiment** и не DQ evidence.
Неизвестные связи не объявляются доказанно отсутствующими: visual/hash screening
не является исчерпывающим доказательством независимости сцен или физических камер.

| Взаимоисключающий итог candidate ledger | Число |
|---|---:|
| Связь с прежними source/scene/session groups | 357 |
| Отказ acquisition/development среди остальных | 50 |
| Visual/rights/development QA среди остальных | 53 |
| Дополнительные представители той же новой группы | 103 |
| Все пригодные независимые группы, назначенные holdout | **320** |
| Всего | **883** |

Это другой разрез, чем таблица development: 31 из 81 отказа также относится
к прежним группам и классифицирован в первой строке. Суммировать разрезы нельзя.

## Endpoint и первичный результат

Каждая группа дала один benign single-history JPEG: quality 40/75/95 по
`ordinal % 3`, sampling `(ordinal // 3) % 3`, каждый десятый RGB→L,
каждый пятый progressive. Это прежний R3C primary endpoint; ordinal начинается
с нуля по окончательному manifest. Совпадение генерации с R3C проверено
побайтными тестами. Дополнительных positives/challenges на holdout не создавали.

| Показатель | Результат |
|---|---:|
| Assigned | 320 |
| Admitted | 320 |
| Applicable negatives — binomial n | **308** |
| Insufficient evidence | 12 |
| Admission/resource failures | 0 |
| Protocol-invalid endpoints | 0 |
| False positives | **0** |
| Наблюдаемый image-level FPR | **0 / 308 = 0%** |
| One-sided exact 95% upper | **0,009679255008705269** |
| Applicability | **96,25%** |
| Abstention | **3,75%** |
| Resource rejection | **0%** |
| Итог | **FINAL_HOLDOUT_PASS** |

При 0 FP граница равна `1 - 0.05^(1/308)`; она независимо сверена
60-digit Decimal расчётом. В знаменатель не подставлялись ни 320, ни прежние
500, ни derivatives. Все 320 outcomes обработаны, без ранней остановки.
Никакие источники после открытия не удалялись, не заменялись и не добавлялись.

Coverage относительно R3C validation: 96,25% против 98%, разность −1,75 п.п.;
abstention 3,75% против 2%. Резкого падения по этим описательным долям не видно.
Отдельный final-holdout coverage acceptance threshold заранее не назначался;
coverage не получает выдуманного PASS/FAIL и требует интерпретации владельца.

## Описательные strata

FP и admission failures во всех строках — 0. Разные измерения таблиц
пересекаются; их нельзя складывать в новый n. Малые strata не сертифицируют
собственный FPR ≤1%.

| Страта | Assigned | Applicable | Abstention |
|---|---:|---:|---:|
| Природа | 140 | 133 | 7 |
| Застройка/интерьеры | 102 | 102 | 0 |
| Предметы | 76 | 71 | 5 |
| Периодические текстуры | 2 | 2 | 0 |
| Quality 40 | 107 | 97 | 10 |
| Quality 75 | 107 | 105 | 2 |
| Quality 95 | 106 | 106 | 0 |
| RGB | 288 | 277 | 11 |
| Grayscale | 32 | 31 | 1 |

| Основные make strata | Assigned | Applicable | Abstention |
|---|---:|---:|---:|
| Canon | 85 | 81 | 4 |
| Panasonic | 22 | 22 | 0 |
| Sony | 21 | 21 | 0 |
| HUAWEI | 16 | 15 | 1 |
| Pentax | 16 | 15 | 1 |
| Nikon | 15 | 15 | 0 |
| Samsung | 14 | 14 | 0 |
| Leica | 13 | 12 | 1 |
| Hasselblad | 11 | 11 | 0 |
| Остальные | 107 | 102 | 5 |

DNG составили 154/320 original RAW, 147 applicable; CR3 — 26/25,
ARW — 19/19, CRW — 19/19, RW2 — 18/18; прочие форматы — 84/80.
Это форматы источников, все измеренные endpoints — JPEG.
Полные per-device, format, quality, sampling, mode и progressive strata
сохранены в `holdout-result.json`. Новое распределение устройств отличается
от R3C; это compatibility corpus, не репрезентативная популяционная выборка.

## Проверки и воспроизводимость

Среда JPEG: Windows 11 x64, Python 3.12.10, NumPy 2.5.2,
Pillow 12.3.0, pyjpegio 0.3.0, Pydantic 2.13.4.
Полный measurement/reporting wall — 140,655 s; сумма preprocessing —
129,429 s, DQ — 6,622 s; maximum numeric artifact — 12 138 240 bytes.
Максимальный зарегистрированный peak отдельного offline RAW worker —
715 603 968 bytes; это не RSS production JPEG pipeline или всей сессии.

Заранее предусмотренная verification после открытия: ordinal 0/160/319,
группы `rawpixls-1983`, `rawpixls-1677`, `rawpixls-7039`.
Во всех трёх случаях совпали endpoint bytes, полные DQ diagnostics и decision.
Повторная агрегация исходных rows в обратном порядке совпала точно.
Это проверка детерминизма, не второй независимый holdout и не новый statistical n.
Rule, implementation, manifest и endpoints сохранили исходные hashes.

- Focused research suite — **163 passed**, включая 29 R3D tests.
- `uv run poe check`: pre-commit PASS, mypy `src` PASS (65 files),
  pytest **2685 passed, 17 skipped, 1 failed**.
- Единственный failure:
  `test_sdist_wheel_metadata_entry_point_and_resources`,
  `Untracked or duplicate sdist source member: 'scripts/research/jpeg_dq_holdout.py'`.
- **OWNER_VERIFY_REQUIRED:** повторить package/full barrier после Git-действий
  владельца. Staging и ослабление provenance checks не выполнялись.
- CLI smoke отдельно — PASS; targeted Ruff/format и research mypy — PASS.
- Проверены split, prior/within-group leakage, manifest/rule tampering,
  exclusive freeze/open, полный состав без replacement, abstention/failure
  exclusion, actual n, границы 0/1/2 FP и 298/299, 472/473 applicable,
  меньший owner-approved N, детерминированная агрегация и R3C byte equivalence.

Это development verification. Итоговый diff просмотрен на scope/API expansion,
дублирование, ненужные зависимости/config/schema и временные хвосты;
полный owner-review bundle включает новые untracked файлы целиком.
Graphify остаётся STALE, не пересобирался. Git mutations отсутствуют.

## Ограничения, отклонения и рекомендация

Расширение acquisition и замена 500 на максимум после QA были явно разрешены
владельцем до исходов; это записанные изменения плана, не post-outcome tuning.
Материальных нарушений frozen protocol и известных оставшихся пересечений
не обнаружено. UNKNOWN device/session metadata и bounded QA остаются
ограничениями интерпретации; биномиальная формула не доказывает независимость.

Полученный upper относится к применимым single-history endpoints этой смеси
RAW-проявки, размеров и Pillow JPEG encoding. Он не сертифицирует все native
camera JPEG, другие encoders/DQT, большие разрешения, произвольные workflows
или каждую device/content страту. Отсутствие сигнала не доказывает подлинность.

Известный sensitivity context остаётся R3C: aligned 40→90 — 65/99 applicable
(65/100 unconditional), полезная, но неполная чувствительность; reverse,
same-DQT и close-quality — 0 detections. Holdout не меняет этот вывод.
`DQ-R3C-1` не универсальный double-JPEG detector. Смысл сигнала узкий:
свидетельство, согласующееся с поддержанной aligned JPEG recompression history;
не malicious manipulation, вероятность подделки, точное предыдущее quality,
число правок или идентичность редактора.

Рекомендуется owner acceptance полученного **статистического свидетельства**
и отдельное решение по полной методологической спецификации. Непосредственная
production promotion пока **не рекомендуется**: DQ-G1–G4 не закрыты,
semantics/severity/completeness и границы переносимости требуют решения владельца.
DQ остаётся research-only до явного принятия; production threshold/analyzer,
Findings, catalog и risk/completeness integration не добавлены.
Grid — `DEFERRED_RESEARCH_ONLY`; новых Grid/VISION stress measurements нет.

**DQ_METHOD_ACCEPTED: NO; DQ_PRODUCTION_PROMOTION_RECOMMENDED: NO;
PRODUCTION_ANALYZER_IMPLEMENTED: NO; M2_A_STATUS: BLOCKED;
OWNER_ACCEPTANCE_REQUIRED: YES; GIT_MUTATIONS_PERFORMED: NO.**
