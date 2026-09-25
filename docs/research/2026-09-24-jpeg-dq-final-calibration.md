# M2-R3C — финальная исследовательская калибровка DQ

Дата: 2026-09-24. Baseline: `f9802e14a3024d00a05bd6610a925e7e8982bcb0`,
ветка `feat/stage12-macro2-image-analyzer-expansion-wave1`.
Работа опирается на принятый владельцем
[R3B](2026-09-24-jpeg-real-corpus-pilot.md),
[DQ-HIST-1](../METHODS.md#dq-hist-1--гистограммное-измерение-dct),
[DATASET-PIXLS-CC0](../REFERENCES.md#dataset-pixls-cc0) и
[разрешённый внешний rawpy](../REFERENCES.md#research-rawpy-m2r3b).
Новых внешних источников, инструментов или production dependencies нет.
Это research evidence, не принятие метода или production threshold.
Grid остаётся `DEFERRED_RESEARCH_ONLY`, M2-A — BLOCKED.

## Корпус и outcome-blind допуск

Внешний workspace `fakedetector-m2-r3c-2026-09-24` содержит медиа,
acquisition/development ledgers, QA, split, machine results и reproduction scripts.
В Git медиа и локальные corpus paths не включаются.

| Стадия | Число |
|---|---:|
| Новые кандидаты, заранее назначенные calibration / validation | 150 / 150 |
| Скачано файлов | 300 |
| Совпадение SHA-256 с publisher catalog | 299 |
| Publisher hash mismatch, исключён до проявки | 1 |
| Успешно проявлено | 262 |
| Неподдерживаемый фиксированным AHD профиль CFA | 36 |
| LibRaw I/O rejection | 1 |
| Visual/content/duplicate QA исключения среди проявленных | 27 |
| Пригодный, не использованный резерв | 32 |
| Новые допущенные calibration / validation | 103 / 100 |
| Пилотные группы, только calibration | 97 |
| Итоговые calibration / validation source groups | **200 / 100** |

Downloaded bytes: **6 685 716 340**. Record 5084 исключён из-за несовпадения
publisher SHA; собственный hash не подставлен вместо ожидаемого. Отказы не
зависят от DQ. Сохраняются исходные record IDs, URLs, CC0 URL каждой записи,
device metadata, исходные/master SHA, время загрузки и partition.

Использован прежний catalog snapshot R3B и те же RAW format/mode/size filters.
Seed `24092026`; случайный порядок записей, одна новая casefold make/model
пара, все пилотные модели исключены. Кандидаты поочерёдно назначены calibration
и validation **до скачивания и DQ**. После development/QA берутся первые
пригодные 103/100 в своих очередях; переход между очередями запрещён.
Не потребовались дополнительные источники или адаптивный добор.

План acquisition/правил SHA-256:
`5bc59aa10ef15f65dc5ceae51aaff1ed47935c4be4bb217dad376d299eef0bcb`.
Полный фиксированный AHD/LibRaw профиль, bounded RGB8 PNG, Lanczos без upscale,
потолки 1280 по стороне / 1 000 000 pixels, timeout 120 s и один поток —
как в R3B. RAW проявлены прежним внешним Python/rawpy environment;
project environment и runtime dependencies не менялись.

Просмотрены все 262 новых masters на семи contact sheets и пилотные sheets.
Bounded near-duplicate screening сравнил новые masters с 107 проявленными
пилотными: dHash64 distance ≤8 либо grayscale32×32 correlation ≥0,97;
девять flagged pairs проверены визуально. Из них 1792 повторяет pilot1791;
1430/1432 — мишени. Остальные flagged pairs показывают разные сцены.
Визуально дополнительно исключены 1480/1476, 2564/2570, 4258/4257, 1202/1201.
Всего исключены 18 мишеней, 5 повторов сцен, 3 доминирующие репродукции
с неясными правами и 1 master с аномальным пурпурным результатом проявки.
Exact original/master duplicates и повтор scene/source identity запрещены
split validator, в том числе внутри одной partition: они не увеличивают n.

| Содержание | Calibration | Validation |
|---|---:|---:|
| Природа | 57 | 49 |
| Застройка/интерьеры | 22 | 31 |
| Предметы | 22 | 18 |
| Периодические текстуры | 2 | 2 |
| Пилот, без новой содержательной разметки | 97 | 0 |

В validation: Panasonic 35, Canon 27, Olympus 15, Fujifilm 12, Nikon 8,
Pentax 2, Samsung 1. Calibration: Panasonic 49, Canon 41, Nikon 26,
Olympus 21, Samsung 17, Pentax 15, Leica 10, Fujifilm 8, Minolta 7,
OM System 6. Это реализованный состав очередей, не репрезентативные
популяционные квоты. Идентичность физической камеры по make/model не доказана;
visual/dHash screening не доказывает исчерпывающую независимость всех сцен.
Device-domain transfer и per-device ≤1% claim из этого корпуса не следуют.

Все приобретённые кандидаты и просмотренный резерв остаются development/QA
данными и не назначаются будущему untouched holdout. Финальные 500 источников
не выбирались, не скачивались, не обрабатывались; VISION не запускался.

## Контролируемые истории и endpoint

Для каждой группы создаются семь детерминированных JPEG; исходные и выходные
hashes, ordered transforms и фактические DQT записаны в derivative ledger.
Здесь числа 40/75/90/95 — **encoder quality settings**, не элементы DQT q2.

| Workflow | История | Статистическая роль |
|---|---|---|
| single | master → quality 40/75/95 по `ordinal % 3` | Единственный primary negative каждой группы |
| single90 | master → 90 | Дополнительный парный negative, отдельный знаменатель |
| aligned40to90 | 40 → 90 | Заранее выбранный utility endpoint |
| aligned90to40 | 90 → 40 | Обратное соотношение качеств |
| same75 | 75 → 75 | Поэлементно одинаковые DQT |
| close85to90 | 85 → 90 | Близкие качества |
| repeat | 40 → 60 → 80 → 90 | Доброкачественный повторный экспорт |

Ordinal начинается с нуля отдельно в каждой partition. Subsampling
`(ordinal // 3) % 3` задаёт 4:4:4 / 4:2:2 / 4:2:0 для RGB;
каждый десятый master преобразуется Pillow RGB→L перед всеми JPEG-проходами.
Каждый пятый имеет progressive final encode, остальные baseline;
предыдущие проходы baseline. Для L sampling setting не создаёт chroma.
Grayscale здесь связан с progressive, поэтому их отдельные причинные эффекты
не оцениваются. Shift/crop не входят в основной aligned endpoint.

На workflow приходится один результат на source group. Нельзя сложить семь
производных или single/single90 в независимый binomial n. Отказы и abstentions
не являются negatives и не заменяются резервом после просмотра outcomes.
Benign repeated save считается положительной известной JPEG-историей;
malicious intent не является ground truth этого опыта.

## Предобъявленный выбор и точное правило

До новых измерений записаны ровно две серьёзно рассматриваемые семьи:
медиана `empty_fraction` и медиана `amplitude` по одинаковой опоре.
Перебора сотен combinations, настройки support по outcomes, подбора q2 bins
или выбора наиболее подозрительного канала нет.

1. Вход — успешные DQ-HIST-1 measurements из существующего controlled intake,
   Macro 1 clean JPEG decode и numeric access. Здесь исследованы RGB/L,
   SOF0/SOF2, 8-bit. Формулы signed histogram, FFT и крайние полные блоки
   не изменены. q1 не оценивается.
2. Берётся **первый компонент в SOF order**, а не component ID 1 и не
   предполагаемый Y. Остальные компоненты не голосуют. Девять AC modes:
   `(0,1),(0,2),(0,3),(1,0),(1,1),(1,2),(2,0),(2,1),(3,0)`.
3. Mode применим при `state=measured`, `N>=1024`,
   `N-round(N*zero_fraction)>=256`, `occupied>=8`, `span>=16`.
   Восстановление integer nonzero count из count/N diagnostic использует
   Python `round`; исходный histogram хранит точное целочисленное отношение.
   Flat/constant, нулевая/недостаточная опора и histogram-limit modes исключаются.
4. Требуется минимум пять применимых modes одного первого компонента.
   Иначе `insufficient_evidence` (в research Python — `None`), никогда `false`.
   Для каждого valid mode берётся выбранная метрика: empty fraction равна
   `(span-occupied)/span`; amplitude — максимум ненулевых FFT frequencies
   полного signed `H/N` с zero padding до ближайшей степени двух.
   Центральный bin не удаляется; q2 не заменяется quality label.
5. Image score — обычная медиана valid modes; при чётном количестве —
   арифметическое среднее двух центральных значений. Метрика конечна в `[0,1]`.
6. Для каждой семьи threshold — **максимум score применимых calibration
   primary negatives**. Positive строго при `score > threshold`;
   точное равенство — `dq_recompression_signal=false`.
7. Выбирается семья с большей unconditional detection долей
   `aligned40to90` из 200 групп, включая abstention в знаменатель utility.
   При равенстве выбирается empty fraction. После выбора порог не меняется.

Это намеренно простые исследовательские support gates, не доказанные
универсальные границы информативности. Отсутствие сигнала не доказывает
подлинность. Positive означает только согласованность распределения с
предшествующей requantization, не редактор, число сохранений или злой умысел.

Протокол `R3C-source-endpoint-1` заранее требует для рекомендации holdout:
наблюдаемый primary FPR ≤1%, primary applicability ≥90% и unconditional
aligned40to90 sensitivity ≥20%. Utility gate отсеивает почти всегда negative
правило; это ограниченный research gate, не production acceptance.
Односторонний 95% Clopper–Pearson upper считается отдельно по применимым
primary source endpoints: корень `P_p[X<=FP]=0,05`;
при FP=0 — `1-0,05^(1/n)`. При n=0 FPR/upper отсутствуют.
Даже 0/100 дают upper ≈2,9513%, поэтому validation100 не сертифицирует ≤1%.

## Calibration и freeze

| Семья | Threshold | Применимые primary negatives | FP | aligned40to90 / все 200 |
|---|---:|---:|---:|---:|
| Медиана empty fraction — **выбрана** | **0,6005747126436781** | 191 | 0 | **136/200 = 68%** |
| Медиана amplitude | 0,9964767057846488 | 191 | 0 | 2/200 = 1% |

Calibration: 1400/1400 JPEG измерены, preprocessing refusals 0.
Primary FPR — 0/191 = 0%, abstention 9/200 = 4,5%.
Формальный one-sided upper — 1,5562%, но после выбора threshold на этих же
данных он не является независимой гарантией FPR. Парный `single90`:
1/199 FP = 0,5025%, abstention 1/200. Дополнительный FP сохранён;
под него threshold не перенастраивался.

| История | Applicable | Positive | Sensitivity среди applicable | Positive / все 200 |
|---|---:|---:|---:|---:|
| aligned40to90 | 195 | 136 | 69,7436% | 68% |
| aligned90to40 | 175 | 0 | 0% | 0% |
| same75 | 197 | 0 | 0% | 0% |
| close85to90 | 198 | 0 | 0% | 0% |
| repeat | 196 | 121 | 61,7347% | 60,5% |

Нулевая чувствительность в обратной/same/close стратах — существенное
ограничение уже calibration evidence. Оно не скрыто общей средней по histories.

Финальный файл `frozen-rule.json`, version `DQ-R3C-1`, содержит exact float
threshold, modes, support gates, aggregation, boundary/abstention semantics,
metric definitions, calibration manifest hash, implementation fingerprint,
baseline repo SHA, UTC timestamp и validation protocol version.
JSON канонический: sorted keys, compact separators, UTF-8, один завершающий LF;
создание exclusive, чтение с проверкой SHA-256 и canonical bytes.

**Финальный SHA-256 правила:**
`2b958bf4fb94926c7f7de0a9a7b74f3897667a22cb802fb85592bab4dd5fd5be`.

Freeze: `2026-09-23T21:28:36.762193+00:00` (24 сентября в рабочей timezone).
Split SHA-256:
`906c29dfd2b305eaab3fd38352fc74c13cf645b8b8575c71f37dbff746d98af8`.
Проверка split запрещает пилот в validation, совпадение source/scene/URL/hash
и превышение размеров. Никакая holdout partition этой моделью не принимается.

Первичный execution artifact с hash
`b39374c4bc6294ea06f63048f969dc5c813906f70046aee077f243633375933f`
сохранён отдельно в `calibration-execution-rule.json`. До validation финальная
сериализация обновила **только timestamp и implementation fingerprint**:
исправлены аннотации типов генератора, вычисления не менялись. Все остальные
поля сравнены на точное равенство; исходные байты execution generator
восстановлены и сверены с его исходным fingerprint, сохранены отдельно.
Пять повторов дали точное совпадение derivative bytes и всех DQ diagnostics.
`calibration-summary.json` ссылается на этот прежний execution hash;
validation привязана к финальному hash выше. Это не переобучение на validation.

Fingerprint включает все Python-файлы `src/`, research tooling, `uv.lock`,
example config и внешний execution script; source lists/hashes сохранены.
Полный media-free evidence bundle содержит обе привязки, manifests,
candidate selection, freeze evidence, validation-start marker и rerun results.

Calibration manifest SHA-256:
`e589f837ea7d929dae1c7f2f50e4e286f86e4756ebb3f14e69341e81d68daeee`.
Финальный implementation fingerprint:
`f71d85640aa1624ad116a0da6e66401e329220231df642b0b25ca49ea43a21cf`.

## Однократная независимая validation

Validation начата `2026-09-23T21:28:37.057709+00:00`, после финального freeze.
Все 700/700 JPEG измерены, preprocessing refusals 0. Порог, семья и support
не менялись после просмотра validation; все связанные code/config/lock hashes
повторно сверены с финальным fingerprint.

| Negative endpoint | Assigned groups | Applicable | FP | FPR | One-sided 95% upper | Abstention |
|---|---:|---:|---:|---:|---:|---:|
| **Primary single** | **100** | **98** | **0** | **0%** | **3,0106198695%** | **2/100 = 2%** |
| Парный single90 | 100 | 99 | 0 | 0% | 2,9806673773% | 1/100 = 1% |

Это два зависимых набора endpoints одних источников, не n=197 независимых
negatives. Primary quality 40: 32/34 applicable, quality 75: 33/33,
quality 95: 33/33; FP во всех трёх стратах 0. Два primary abstentions
принадлежат quality40 и сохранены в coverage denominator.

| Положительная история | Applicable / 100 | Detected | Sensitivity среди applicable | Detected / все 100 | Abstention |
|---|---:|---:|---:|---:|---:|
| **aligned40to90** | **99** | **65** | **65,6566%** | **65%** | **1%** |
| aligned90to40 | 95 | 0 | 0% | 0% | 5% |
| same75 | 99 | 0 | 0% | 0% | 1% |
| close85to90 | 99 | 0 | 0% | 0% | 1% |
| benign repeat | 99 | 58 | 58,5859% | 58% | 1% |

Чувствительность сообщается **STRATIFIED_ONLY**: общая доля по смеси пяти
историй зависела бы от произвольных весов этой смеси. Same-DQT/equivalent-DQT
контроль не обнаруживается; отсутствие сигнала при 90→40 и близких качествах
не означает отсутствие реального повторного JPEG encoding.

Ниже descriptive validation strata: `TP/app` относится только к aligned40to90,
`primary app` — к single; primary FP в каждой строке 0. Строки разных
измерений пересекаются, их нельзя суммировать. Полные per-model/per-workflow
таблицы и отдельные abstention counts сохранены в machine summaries.

| Страта | Source groups | Primary app | aligned40to90 TP/app |
|---|---:|---:|---:|
| Природа | 49 | 48 | 29/48 |
| Застройка/интерьеры | 31 | 31 | 21/31 |
| Предметы | 18 | 17 | 14/18 |
| Периодические текстуры | 2 | 2 | 1/2 |
| RGB 4:4:4 | 30 | 29 | 20/30 |
| RGB 4:2:2 | 30 | 30 | 20/30 |
| RGB 4:2:0 | 30 | 29 | 16/29 |
| Grayscale | 10 | 10 | 9/10 |
| Canon | 27 | 26 | 19/26 |
| Fujifilm | 12 | 11 | 9/12 |
| Nikon | 8 | 8 | 4/8 |
| Olympus | 15 | 15 | 10/15 |
| Panasonic | 35 | 35 | 21/35 |
| Pentax | 2 | 2 | 1/2 |
| Samsung | 1 | 1 | 1/1 |

В корпусе визуально присутствуют гладкие/тёмные сцены, мелкая растительность,
городские текстуры, ткань и повторяющиеся структуры. Это не отдельные
репрезентативные noise/detail/ISO strata: количественная разметка шума отсутствует,
RAW development и уменьшение разрешения могут сглаживать шум/тонкую текстуру.
Малые device/content bins не подтверждают собственный FPR ≤1%.
Применимость к camera-native JPEG, другим encoders, custom/trellis DQT,
неизвестной сложной обработке и исходным большим размерам этим опытом не доказана.

## Ресурсы, воспроизводимость и проверки

Среда измерений: Windows 11 x64, CPython 3.12.10, NumPy 2.5.2,
Pillow 12.3.0, pyjpegio 0.3.0, Pydantic 2.13.4. Network использовался только
для acquisition; сами measurements выполнялись локально.

| Наблюдение | Calibration | Validation |
|---|---:|---:|
| Source groups / JPEG | 200 / 1400 | 100 / 700 |
| Generation + measurement + reporting wall, s | 578,04 | 289,51 |
| Сумма preprocessing, s | 502,40 | 251,65 |
| Сумма DQ, s | 26,24 | 13,21 |
| Максимум numeric artifact bytes | 12 138 240 | 12 138 240 |
| Отказы preprocessing | 0 | 0 |
| Наблюдавшийся parent peak RSS до промежуточного snapshot, bytes | 112 705 536 | 102 428 672 |

RSS — промежуточные Windows process snapshots, не полный peak всей сессии
и не совокупность parent/child. Native child limits, controlled intake,
deadline и cleanup остаются прежними. Потоковый JPEG execution читает один
raster за раз; внешний runner хранит ограниченные 1400/700 scalar measurement
records, не набор декодированных изображений. Grid в новых прогонах не вычислялся.

Acquisition wall 410,71 s; development wall 445,32 s с перекрытием загрузки.
Максимальный зарегистрированный peak отдельного внешнего RAW worker —
714 625 024 bytes; это offline corpus preparation, не production JPEG budget.
Пять полных повторов calibration derivatives и DQ — 5/5 exact matches.
Cross-platform bit identity не заявляется.

Проверки реализации:

- focused R2/R3B/R3C tests — **134 passed**;
- `uv run poe check`: pre-commit PASS, mypy `src` PASS (65 files),
  pytest **2656 passed, 17 skipped, 1 failed**;
- единственный failure — `test_sdist_wheel_metadata_entry_point_and_resources`:
  sdist provenance отвергает intended untracked `scripts/research/jpeg_dq_corpus.py`;
- **OWNER_VERIFY_REQUIRED**: повторить полный barrier после Git-действий
  владельца. Staging и ослабление provenance check агент не выполнял;
- CLI smoke отдельно — PASS, targeted Ruff/format — PASS;
- targeted mypy двух новых research modules с `--follow-imports=silent` — PASS;
- проверены точная арифметика, equality boundary, support/abstention,
  component/mode aggregation, source counting без derivative n, split leakage,
  calibration-only selection, freeze/hash/tampering, exact binomial, deterministic
  histories и DQ-only regression с запретом вызова Grid.

Это development verification, **не strict certification**. Graphify stale,
не пересобирался и не использовался как актуальное архитектурное доказательство.
Финальные diff/check/status и полный owner bundle охватывают все восемь
изменённых/новых файлов, включая четыре intended untracked; Git mutations нет.
Новых public API/config/result полей, production dependencies, Findings,
catalog entries, risk/completeness изменений и compatibility paths нет.

## Решение и оставшиеся gates

**DQ_CALIBRATION_RESULT: READY_FOR_FINAL_HOLDOUT.** Предобъявленные условия
выполнены: primary FPR 0% ≤1%, primary applicability 98% ≥90%,
aligned40to90 unconditional sensitivity 65% ≥20%; support и abstention
полностью определены, вычисления проверены, измеренные ресурсы приемлемы
для этого bounded research execution. Дополнительная настройка этого правила
не планируется. Ограниченная чувствительность других историй остаётся явной.

Готовность относится к **однократной будущей проверке фиксированного правила**,
не к production acceptance и не к уже доказанному FPR ≤1%: validation upper
3,0106% превышает цель. Future holdout сохраняет 500 новых source groups,
DQ-only endpoint и target ≤1%; он **не открыт**. Abstention не превращается
в negative и не заменяется новым источником после outcomes; при применимом
n меньше 500 требуется считать exact upper по фактическому n, а не подставлять 500.

Остаются owner review/acceptance R3C, повтор package provenance verification
после действий владельца, отдельное исполнение outcome-blind holdout protocol
и DQ METHODS gates. Источники текущего исследования исключаются из future
untouched pool. Любая будущая настройка по validation делает эти 100 групп
development data и требует новой независимой validation; повторный выбор
порога на текущих validation/holdout запрещён.

**DQ_METHOD_ACCEPTED: NO; PRODUCTION_THRESHOLD_CREATED: NO;
PRODUCTION_ANALYZER_IMPLEMENTED: NO; GRID_STATUS: DEFERRED_RESEARCH_ONLY;
M2_A_STATUS: BLOCKED; OWNER_ACCEPTANCE_REQUIRED: YES.**
