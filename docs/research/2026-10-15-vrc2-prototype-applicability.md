# VRC2: прототип и границы применимости — Sprint 1

Фактическое выполнение: **2026-10-18**, Asia/Krasnoyarsk. Имя файла сохранено по заданию
`STAGE12-DIPLOMA-VRC2-PROTOTYPE-APPLICABILITY-SPRINT1`. Baseline
`4e564dc8d0fa20df196f7cb1a1e63224ac4fcf83`, ветка
`feat/stage12-vrc2-prototype-applicability-sprint1`; в начале реализации дерево было чистым. После
остановки владельцем продолжены те же unstaged-изменения; восстановленные внешние данные проверены
по исходным hashes, без повторного получения из интернета. **AGENT SELF-REPORT IS NOT OWNER
ACCEPTANCE.** Статус приёмки принадлежит
[ROADMAP](../ROADMAP.md#diploma-vrc2-prototype-applicability-sprint1).

## 1. Цель и происхождение данных

Перенести единственный принятый research-кандидат PR #75 в настоящий Analyzer-compatible worker-only
прототип, доказать точность реализации и измерить применимость на заранее объявленных контролируемых
воздействиях. Это **прототип, не production-ready метод**. Нового поиска методов, настройки по
результатам, обучения и ансамблевой калибровки нет.

Использованы существующие 16 benign-видео восьми семейств, 8 matched references, 8 exact-copy
derivatives и 12 demo-видео. SHA-256/size всех 44 входов, привязки accepted caches, 166 артефактов
завершённого PR #75, manifests, selection и исходный исследовательский код проверены. Полный входной
inventory лежит во внешнем workspace. Пять прежних observation families и три прежних holdout
families не переименованы; этот sprint использует все восемь для диагностики, не создаёт новый
слепой holdout.

Происхождение и лицензии внешних источников — [реестр PR
#73](../REFERENCES.md#diploma-benign-validation-sources); demo — [отчёт PR
#72](2026-10-13-diploma-demo-evaluation.md), accepted paired episodes — [PR
#74](2026-10-14-vrc-targeted-research.md), выбор метода — [PR
#75](2026-10-14-vrc-redesign-research.md). Исходные и производные медиа, numeric artifacts и большие
результаты не входят в Git.

## 2. Замороженный метод и матрица

Единственная формула — **D2__I25__K9__R10**; точная исходная спецификация — [PR #75,
§§5–8](2026-10-14-vrc-redesign-research.md#5-d1d4-descriptors). Сохранены 9×16 RGB block means с
integer half-up rounding, группы по четыре кадра, signed spatial gradients, энергия centered
temporal residual, строгий `energy > p25`, точный реальный gap≥2 s через Fraction, девять
последовательных aligned correspondences, median девяти distances, линейный p10, epsilon `1e-12`,
`clip(1-d_best/p10,0,1)` и первый минимум в исходном порядке обхода. K3/K5, I0, абсолютного motion
floor и fallback нет.

До стресс-измерений запечатана матрица **128 paired cells / 256 файлов**: 5 cadence × 8 семей, 5
repeat lengths × 8, 6 transformations × 8. SHA-256 канонического `applicability-matrix.json`:
`48422e3ab09c211379c985b1b5a85c2007616648aa529c172df63b842ad5b727`. Принятый
`selected-candidate.json` PR #75:
`9f40e13656fbbb12122829c12b8eea37d341695210022cd22180d3409d1f7795`.

Все команды, пути, source hashes и интервалы объявлены в матрице до outcomes. Длительность каждого
файла — 12 s; source начинается в 0.25 s, destination — в 10.25 s. Общий encoding: MPEG-4 intra,
`q:v=2`, `g=1`, один поток, yuv420p, bitexact, timescale 24000. Cadence преобразуется общим
`fps=24/12/8/6/4:start_time=0` после вставки. При low fps номинальные границы известной вставки и
дискретные PTS наблюдаемых кадров могут не совпадать.

| Near-copy case | Воздействие только на вставляемый destination episode |
| --- | --- |
| N0_EXACT | Точная копия исходного эпизода |
| N1_BRIGHTNESS | `eq=brightness=0.04`, затем общий encoding |
| N2_REENCODE | Дополнительный MPEG-4 intra проход `q:v=8`, затем общий `q:v=2` |
| N3_SCALE_ROUNDTRIP | Bilinear downscale до `trunc(iw/4)*2 × trunc(ih/4)*2`, upscale в исходную геометрию |
| N4_CENTER_CROP | Центрированный crop `trunc(iw*0.96/2)*2 × trunc(ih*0.96/2)*2`, bilinear resize и `setsar=1` |
| N5_SPEED_1_05 | Исходный участок длиной 0.7875 s, `setpts=PTS/1.05`, fps=24, destination 0.75 s |

Параметры не менялись после outcomes. В каждом pair reference проходит тот же общий encoding без
destination transformation. Повторная генерация в отдельном временном каталоге проверяет равенство
SHA-256 и размера каждого конечного файла. ffprobe проверяет точную полную последовательность PTS и
число кадров `12×fps`. Новых библиотек или интернет-загрузок нет.

После matrix freeze в harness уточнялись import/type declarations, executable runtime-isolation gate
и журналирование фаз. Это инженерные изменения harness; команды, состав матрицы и runtime-реализация
формулы не менялись. На каждой фазе проверяется полное равенство матрицы заново построенной
спецификации, hashes прототипа/каталога и среды. Исходный script receipt сохранён в
freeze/design.json, receipt исполненной версии — в logs/executions.jsonl, окончательный — в review
seal.

## 3. Архитектура прототипа

[`_video_vrc2_prototype.py`](../../src/fakedetector/analyzers/_video_vrc2_prototype.py) содержит
`VideoRepeatedContentCorrespondenceV2PrototypeAnalyzer`:
`video_repeated_content_correspondence_v2_prototype@0.1.0`, группа video, профиль
`VRC2-D2-I25-K9-R10-PROTOTYPE-1`. Используются реальные AnalyzerRequest, AnalyzerResult, forensic
manifest, dense descriptors, numeric readers и timing facts. Runtime-код не импортирует research
scripts и не зависит от внешнего workspace.

Результат измерительный: `score=null`, `score_name=null`, candidate findings пусты.
`relative_distinctiveness` лежит только в raw_metrics; это не вероятность, confidence, authenticity
score или доказательство подделки. Диагностика хранит coverage, энергии/квантили, counts, лучший run
с каждой из девяти constituent pairs, реальными PTS, gap/lag и энергиями. Состояния: MEASURED,
INSUFFICIENT_LOW_INFORMATION, INSUFFICIENT_RUN_SUPPORT, INSUFFICIENT_NONSELECTIVE_DISTRIBUTION.
Нулевое измерение не подменяет null. Ноль valid groups относится к RUN_SUPPORT; дополнительный
research-only state PR #75 для отсутствующих групп не расширяет заданные четыре состояния прототипа.
На обязательных accepted входах такого расхождения нет.

## 4. Изоляция normal runtime и ансамбля

Единственная дополнительная запись `_WORKER_DEFINITIONS`:
`prototype.video_repeated_content_correspondence_v2.v0`. Она отсутствует в CORE,
experimental/runtime definitions, runtime ID resolver и обычных регистрациях. Сохраняются 5 CORE + 9
experimental = 14 runtime IDs. Попытка выбрать VRC2 через обычную конфигурацию отвергается
существующим registry.

VRC1 `video_repeated_content_correspondence@1.0.0`, `VRC-DENSE-DIPLOMA-1`,
`diploma_ensemble_v1@0.1.0`, `_ENSEMBLE_FAMILIES`, веса, capacity, нормализатор, пороги, configs,
public/config schemas и зависимости не менялись. VRC2 не вносит вклад в ансамбль. Изменение
worker-only допуска отражено в документах владельцев архитектуры и transport-контракта; это не
публичное расширение API.

## 5. Exact parity с PR #75

**32/32 primary inputs**, state parity **32/32**, максимальное расхождение всех численных метрик и
score — **0**, при допустимом `1e-12`. Сначала принятую исследовательскую реализацию повторно
вычислили на hash-checked cached grids и точно сравнили с принятыми outcomes. Затем каждый исходный
файл повторно декодировали штатным dense producer и вызвали прототип как компонент. Сверены states,
valid/eligible groups, eligible runs, p25, d_best, p10, median, relative score, полная выбранная
последовательность PTS/identity и constituent distances/energies. Полные VRC1 raw_metrics также
точно совпали для 32/32. Стресс-интерпретация началась только после запечатанного успешного parity
gate.

## 6. Реальное worker execution

Пять обязательных случаев: benign reference, benign processing, accepted exact repeat, demo
all-static и demo insufficient-run-support. Каждый вызван дважды через штатный
`_SpawnedWorkerRunner` с prototype worker key. Replay совпал с предыдущим worker result и
компонентным result. Все результаты валидированы как AnalyzerResult, без Findings/score. Ошибочный
settings request даёт `worker_error`; timeout 0.001 s проверяет штатный terminate/join/reap.
Дополнительно focused tests проверяют corrupt artifact → analyzer_error. PID-kill эвристик нет.

Пять реальных случаев дали соответственно MEASURED, MEASURED, MEASURED, INSUFFICIENT_LOW_INFORMATION
и INSUFFICIENT_RUN_SUPPORT; cleanup подтверждён. Стресс-матрица и demo recheck также используют
реальные процессы worker. Это **COMPONENT/WORKER_LEVEL validation**, не новая FILE_LEVEL_E2E
интеграция с application intake, orchestration и итоговым HTTP risk result.

## 7. Ресурсы и boundedness

Существующий dense cap — не более трёх регионов по 32 retained frames, не более 2 s на окно и
640×360 RGB; одно полное окно занимает максимум 22 118 400 bytes пикселей. Получается не более 87
четырёхкадровых групп. D2 имеет 3156 float64-компонентов. Descriptor matrix ≤87×3156 (2 196 576
bytes), scalar distance matrix ≤87² (60 552 bytes). Вычитание/модуль выполняются по строкам, без
N×N×3156 tensor. Дополнительно живут исходный список descriptors, одна строковая временная матрица и
временный результат abs: порядок менее 9 MB этих численных буферов, без Python/interpreter, decoded
pixels и системных библиотек. Это аналитическая оценка структуры, не измеренный peak RSS.

Грубая верхняя граница unordered pairs/run starts — C(87,2)=3741. Для трёх разнесённых sequences по
29 групп tighter upper bound — 2523 pairs и 1323 K9 runs до I25; каждый start просматривает максимум
29 aligned offsets, в scoring берутся только первые 9. Хранятся scalar population и один best run.
Поиск более длинной поддержки используется исключительно для объяснения insufficiency и не меняет
K9. Retained RGB читается по одному окну.

Использован действующий analyzer timeout **120 s**, bounded IPC и штатный cleanup; лимиты не
увеличены. **Hard RSS quota отсутствует в существующем analyzer worker**, peak RSS здесь не
измеряется, новой monitoring dependency нет. Поэтому результат не является сертификацией hard RSS
или production ресурсов. Worker wall time включает spawn/IPC/вычисление, но не preprocessing и
генерацию. Нагрузка рабочей машины не является контролируемым benchmark.

Наблюдения всех **256 стресс-workers**: median wall=1.024 s, max=1.149 s; максимальный IPC
response=6018 bytes при cap 65536. Timeout, invalid response и cleanup failures в этих вызовах — 0;
в пяти gate cases (два повтора каждого) и 12 demo failures также нет. Специальный timeout/error
probe отдельно успешно проверяет негативный путь.

## 8. Cadence applicability

| Case | Ref measurable | Repeat measurable | + | 0 | − | null | Median repeat | Median Δ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C24 | 8/8 | 8/8 | 8 | 0 | 0 | 0 | 1.000000 | 0.966883 |
| C12 | 6/8 | 6/8 | 5 | 0 | 0 | 3 | 1.000000 | 0.935096 |
| C8 | 3/8 | 3/8 | 1 | 0 | 1 | 6 | 0.012123 | 0.060844 |
| C6 | 2/8 | 2/8 | 0 | 1 | 0 | 7 | 0.000000 | 0.000000 |
| C4 | 0/8 | 0/8 | 0 | 0 | 0 | 8 | null | null |

Каждый denominator — восемь семейств; нули и insufficiency показаны отдельно. Median исключает
только null, количество таких случаев явно сохранено. Потеря K9/I25 support при снижении fps —
результат frozen метода, а не повод для fallback.

При C12 у video-04 недостаточна reference-side run support, у video-06 — repeat-side; у video-07
reference имеет RUN_SUPPORT, а repeat — NONSELECTIVE_DISTRIBUTION (20 runs, p10≤epsilon). Поэтому
6/8 measurable repeats не равны 6/8 измеримым парам: полностью измеримых положительных пар только
5/8.

## 9. Repeat-length applicability

 | Case | Ref measurable | Repeat measurable | + | 0 | − | null | Median repeat | Median Δ | | --- |
--- | --- | --- | --- | --- | --- | --- | --- | | L025 | 8/8 | 8/8 | 7 | 0 | 1 | 0 | 0.163650 |
0.138009 | | L050 | 8/8 | 8/8 | 6 | 1 | 1 | 0 | 1.000000 | 0.923846 | | L075 | 8/8 | 8/8 | 8 | 0 | 0
| 0 | 1.000000 | 0.966883 | | L100 | 8/8 | 8/8 | 8 | 0 | 0 | 0 | 1.000000 | 0.966883 | | L150 | 8/8
| 8/8 | 8 | 0 | 0 | 0 | 1.000000 | 0.966883 |

Exact-copy эпизоды имеют длину 0.25/0.50/0.75/1.00/1.50 s при 24 fps. Это зависимые варианты тех же
восьми источников. Положительная delta у короткого повтора сама по себе не означает, что выбранный
run попал в известный эпизод. Полные семейные counts, scores и delta — repeat-length-results.csv;
пересечения привязаны по source_family/cell в localization-results.csv.

## 10. Near-copy robustness

| Case | Ref measurable | Repeat measurable | + | 0 | − | null | Median repeat | Median Δ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| N0_EXACT | 8/8 | 8/8 | 8 | 0 | 0 | 0 | 1.000000 | 0.966883 |
| N1_BRIGHTNESS | 8/8 | 8/8 | 8 | 0 | 0 | 0 | 0.730444 | 0.681802 |
| N2_REENCODE | 8/8 | 8/8 | 7 | 0 | 1 | 0 | 0.483955 | 0.410898 |
| N3_SCALE_ROUNDTRIP | 8/8 | 8/8 | 8 | 0 | 0 | 0 | 0.643055 | 0.595224 |
| N4_CENTER_CROP | 8/8 | 8/8 | 5 | 0 | 3 | 0 | 0.107538 | 0.087458 |
| N5_SPEED_1_05 | 8/8 | 8/8 | 8 | 0 | 0 | 0 | 1.000000 | 0.961322 |

Positive/zero/negative/insufficient — описательные знаки paired delta, не TPR/FNR. Порогов
production acceptance из этих response не выводили. Для каждой пары near-copy-results.csv содержит
reference/repeat scores, states, delta и counts; JSON соответствующей ячейки хранит полный best_run,
а localization-results.csv — known-episode overlap. N5 — объявленный challenge case, не обязательный
gate.

## 11. Localization diagnostics

| Case | Best run 9 pairs | ANY | MAJORITY | FULLY |
| --- | --- | --- | --- | --- |
| C24 | 8 | 8/8 | 8/8 | 3/8 |
| C12 | 7 | 6/8 | 6/8 | 0/8 |
| C8 | 3 | 2/8 | 2/8 | 0/8 |
| C6 | 2 | 2/8 | 2/8 | 0/8 |
| C4 | 0 | 0/8 | 0/8 | 0/8 |
| L025 | 8 | 6/8 | 6/8 | 0/8 |
| L050 | 8 | 6/8 | 6/8 | 0/8 |
| L075 | 8 | 8/8 | 8/8 | 3/8 |
| L100 | 8 | 8/8 | 8/8 | 2/8 |
| L150 | 8 | 8/8 | 8/8 | 2/8 |
| N0_EXACT | 8 | 8/8 | 8/8 | 3/8 |
| N1_BRIGHTNESS | 8 | 8/8 | 8/8 | 5/8 |
| N2_REENCODE | 8 | 7/8 | 7/8 | 5/8 |
| N3_SCALE_ROUNDTRIP | 8 | 8/8 | 8/8 | 5/8 |
| N4_CENTER_CROP | 8 | 6/8 | 6/8 | 2/8 |
| N5_SPEED_1_05 | 8 | 8/8 | 8/8 | 2/8 |

По всей объявленной матрице: ANY_OVERLAP **99/128**, MAJORITY_OVERLAP **99/128**, FULLY_CONTAINED
**32/128**. Denominator включает и null: отсутствие выбранного run не исключается из отчёта. ANY
требует хотя бы одну constituent pair с пересечением на обеих сторонах; MAJORITY — не менее пяти из
девяти; FULLY — все девять пар полностью внутри соответствующих известных интервалов. Это не
localization accuracy по популяции.

Span — замкнутый диапазон реально наблюдённых PTS; известный episode — полуоткрытый интервал. End
error сравнивает последний наблюдённый PTS с exclusive концом episode, не добавляя выдуманную
длительность кадра. Сохранены обе границы обеих сторон, counts overlap/full containment и отклонение
первого temporal lag от известных 10 s. Все constituent PTS/lag и distances доступны в исходных
JSON. Selection не изменялся.

## 12. Low-information и почти статичный материал

All-static demo даёт **INSUFFICIENT_LOW_INFORMATION**, p25=0, eligible groups=0,
relative_distinctiveness=null; ноль не возвращается. Два дополнительных first-party unit fixtures
иллюстрируют относительность I25 и не расширяют stress matrix: изменение одной ячейки на один RGB
level даёт eligible groups=63, runs=507, p25≈0.003065 и INSUFFICIENT_NONSELECTIVE_DISTRIBUTION;
слабый случайный паттерн 100/101 после десяти статичных кадров, повторённый в трёх окнах, остаётся
MEASURED с response=1, p25≈0.164748, eligible groups=63, runs=507. Абсолютного motion floor нет;
малое изменение само по себе не запрещает измерение. Эти fixtures проверяют математику компонента,
не application E2E.

## 13. Объяснение run-support insufficiency

Для всех 256 стресс-входов сохранены valid groups, I25-eligible groups, длины непрерывных eligible
starts по stream/region, maximum aligned run support, temporal-gap eligible pair count и informative
temporal-gap pair count. Основная таблица — run-support-diagnostics.csv; для 12 demo дополнительно
demo-run-support.csv и полные raw_metrics. Восемь demo RUN_SUPPORT случаев имеют максимум 5–6
aligned groups, то есть меньше K9; наличие многих отдельных подходящих пар не создаёт непрерывного
run. Ни K, ни информационная маска не ослаблялись.

## 14. Demo comparison

| Sample | State | Score | Valid | I25 | Runs | Max aligned |
| --- | --- | --- | --- | --- | --- | --- |
| video-01-control | INSUFFICIENT_RUN_SUPPORT | null | 39 | 29 | 0 | 5 |
| video-01-cut | INSUFFICIENT_RUN_SUPPORT | null | 39 | 29 | 0 | 5 |
| video-01-distant | INSUFFICIENT_RUN_SUPPORT | null | 39 | 29 | 0 | 5 |
| video-01-freeze | MEASURED | 0.010140 | 39 | 26 | 25 | 13 |
| video-02-control | INSUFFICIENT_RUN_SUPPORT | null | 39 | 29 | 0 | 5 |
| video-02-timing | INSUFFICIENT_RUN_SUPPORT | null | 34 | 25 | 0 | 5 |
| video-02-transition | INSUFFICIENT_RUN_SUPPORT | null | 39 | 29 | 0 | 5 |
| video-02-vfr | INSUFFICIENT_RUN_SUPPORT | null | 36 | 27 | 0 | 6 |
| video-03-control | MEASURED | 0.004049 | 39 | 29 | 10 | 10 |
| video-03-loop | INSUFFICIENT_RUN_SUPPORT | null | 39 | 27 | 0 | 5 |
| video-03-repeat | MEASURED | 0.004049 | 39 | 29 | 10 | 10 |
| video-03-static | INSUFFICIENT_LOW_INFORMATION | null | 39 | 0 | 0 | 0 |

**12/12 exact parity** с принятыми research states/scores и best runs. MEASURED 3/12, RUN_SUPPORT
8/12, LOW_INFORMATION 1/12. `video-03-repeat` сохраняет visibility limitation: изменённый блок [2,3)
s не попадает в retained windows [0,2), [4,6), [8,10). Низкий измеренный response этого файла не
является реакцией на невидимую вставку; он совпадает с контролем. Demo не использовано для настройки
формулы.

## 15. Ограничения интерпретации

Восемь уже известных lineage families, один корпус поставки, короткие стандартизованные видео и
зависимые derivatives не дают population-level FPR/TPR, significance, real-deepfake detection или
authenticity claims. 256 сгенерированных файлов не превращаются в 256 независимых источников. Это
exact-copy и transformed controlled probes, а не реальные атаки.

Relative score зависит от собственного распределения run distances. Даже положительная paired delta
не доказывает локализацию вставки. K9 в кадрах, перекрывающиеся группы, I25 и finite retained
windows ограничивают cadence, длину и наблюдаемость. Median допускает несовпадающее меньшинство, а
best-run selection не является сегментацией границ. Null не означает отсутствия повтора.

Рецепты детерминированы для зафиксированной версии FFmpeg и среды; переносимость побайтового
результата между версиями не заявляется. Resource PASS относится к наблюдаемым timeout/IPC/cleanup,
без hard RSS certification. Production readiness, публичная конфигурируемость и ensemble
contribution этим sprint не разрешаются. Формула по outcomes не настраивалась.

## 16. Prototype readiness gates

| Gate | Требование | Результат |
| --- | --- | --- |
| P1 | 32/32 parity | PASS |
| P2 | Worker replay и cleanup | PASS |
| P3 | Runtime/default/ensemble isolation | PASS |
| P4 | C24: 8/8 обе стороны measurable | PASS |
| P5 | C12: ≥7/8 measurable positive pairs | FAIL |
| P6 | N0: 8/8 positive | PASS |
| P7 | N1+N2: ≥14/16 positive | PASS |
| P8 | Finite valid AnalyzerResult | PASS |
| P9 | Без наблюдаемого timeout/IPC/cleanup regression | PASS |
| P10 | Frozen D2/I25/K9/R10 | PASS |

P8 следует из валидации каждого worker response и strict JSON сериализации; P10 — из точного primary
parity, component tests и сохранённого runtime fingerprint. P9 ограничен наблюдаемыми лимитами
существующего worker, не доказывает hard RSS safety.

## 17. Final disposition

**VRC2_PROTOTYPE_APPLICABILITY_LIMITED**.

Не пройдены gates: P5. Формула и выбор метода не менялись. Это решение о следующем исследовательском
шаге; production VRC1, ensemble и обычная конфигурация остаются прежними. Интеграция и изменение
метода требуют нового owner gate.

## 18. Воспроизведение и следующий шаг

Focused suite: **163 passed** за 24.59 s, включая 47 новых cases. Ruff и format
для всех пяти Python-файлов PASS; focused mypy для prototype/catalog и harness
PASS (harness: `MYPYPATH=src`, `--follow-imports=silent`, без изменения конфигурации
проекта). Независимая проверка 256 результатов и 128 paired cells подтвердила
формулу, constituent medians/I25/gap, localization, signs/gates, hashes всех
264 конечных и промежуточных media и пустой temporary artifacts directory.

Единственный финальный `uv run poe check`: pre-commit PASS; mypy src — PASS,
72 source files; pytest — **3218 passed, 17 skipped, 1 failed** за 293.44 s,
coverage **91%** (новый prototype module — 95%). Единственный fail:
`test_sdist_wheel_metadata_entry_point_and_resources`; sdist provenance guard
отверг intended untracked отчёт. До изменения итоговых validation-записей
независимо проверены все members фактического sdist: 239 tracked файлов с точными
working-tree bytes, root PKG-INFO и ровно пять intended untracked-файлов этого
sprint. Unexpected/missing/duplicate/byte mismatches — 0. Это inventory review,
не обход guard и не strict certification. Installed-wheel часть этого теста
после provenance failure не выполнялась.

Итог barrier — **OWNER_VERIFY_REQUIRED**, не зелёный PASS. Guard не ослаблялся,
staging запрещён и не выполнялся. После owner review/staging владельцу нужен
повтор полного barrier. CLI `uv run fakedetector --help` отдельно PASS, поскольку
последовательность poe остановилась на pytest. После barrier изменены только
validation-записи в этом отчёте и ROADMAP; runtime и tests сохранены.
`git diff --check` PASS. Полный diff дополнен содержимым всех intended untracked
файлов; отдельно проверены scope, отсутствие случайного API expansion,
dependencies/config/schema changes, дублирующих или временных механизмов.
Graphify STALE, source SHA `625b9e83…`; использован только для навигации,
без пересборки и без роли архитектурного доказательства.

Review bundle:
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\DIPLOMA-vrc2-prototype-applicability-sprint1`.
Он содержит 00–20 review artifacts, полные копии всех 10 изменённых/новых файлов,
все CSV/JSON evidence, логи и SHA-256/size seal. Крупные media не включены;
их пути, размеры и hashes доступны в generated-media-inventory.csv.

Harness —
[`diploma_vrc2_prototype_applicability.py`](../../scripts/diploma_vrc2_prototype_applicability.py).
Внешний workspace — `C:\Users\Vanur\Desktop\FakeDetector-Work\vrc2-prototype-applicability-sprint1`.
Фазы: `prepare`, `parity`, `worker`, `stress`, `demo`, `finish`. Все вызываются как `uv run python
-m scripts.diploma_vrc2_prototype_applicability <phase> --workspace <absolute-path>`; для prepare
также нужен `--accepted <absolute-PR75-workspace>`. Новый полный прогон требует нового пустого
output workspace; stress может продолжать только запечатанные завершённые ячейки неизменной матрицы.
При прерывании исходные результаты сохранены, завершённые ячейки проверены по seals и не пересчитаны
для отбора.

Следующий шаг — owner review полного diff и evidence bundle с вердиктом PASS / REMEDIATE.
Последующее расширение валидации, изменение применимости, новый метод, runtime selection и
ансамблевая интеграция требуют отдельного решения владельца. Stage 12 остаётся IN_PROGRESS; исходные
VRC G5 DEFER и запрет Stage B не пересматриваются. Git mutations не выполнялись.
