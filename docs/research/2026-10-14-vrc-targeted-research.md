# Целевое исследование VRC — Sprint 1

Дата: **2026-10-14**, Asia/Krasnoyarsk. Задание
`STAGE12-DIPLOMA-VRC-TARGETED-RESEARCH-SPRINT1`, baseline
`c32de18326f020b3bc362dc5eff47042376616cb`, ветка
`feat/stage12-vrc-targeted-research-sprint1`; исходное дерево чистое.
Исследование **research-only**, без production change и без post-hoc ensemble tuning.
`diploma_ensemble_v1@0.1.0`, вес VRC 0.35, video capacity 2.05, семейства,
нормализаторы, пороги и public/config schemas сохранены.
**AGENT SELF-REPORT IS NOT OWNER ACCEPTANCE.** Статус приёмки принадлежит
[ROADMAP](../ROADMAP.md#diploma-vrc-targeted-research-sprint1).

## 1. Причина исследования

[PR #73: benign validation](2026-10-13-diploma-benign-validation.md) обнаружил
высокий отклик VRC у 16/16 обычных видео из восьми source families.
Владелец независимо подтвердил расчёт по raw retained pairs; ошибка экспорта
не объясняет насыщение. Проверяются четыре вопроса: вклад временной близости
(RQ1), выбора экстремума из множества пар (RQ2), масштаба нормированных
distances (RQ3) и возможность простой ограниченной remediation (RQ4).
Ансамбль и аудио в этом эксперименте не настраиваются.

## 2. Зафиксированное production-поведение и воспроизведение

`video_repeated_content_correspondence@1.0.0`, профиль
`VRC-DENSE-DIPLOMA-1`: четыре последовательных dense frames на группу;
16×9 RGB block means, 432 целых значения на кадр, integer half-up rounding.
Группы должны иметь совместимые stream/geometry, строго возрастающие известные
PTS и не пересекаться во времени. В одном регионе `abs(start_a-start_b)<5`
исключается; разность 5 допускается. При равных минимумах сохраняется первая
пара в порядке window/start/combinations.

`color_distance=sum(abs(A-B))/440640`,
`delta_distance=sum(abs(diff(A)-diff(B)))/660960`,
`joint_distance=max(color_distance,delta_distance)`,
`joint_similarity=1-joint_distance`.
Production независимо сохраняет `minimum_color_pair` и `minimum_delta_pair`,
затем берёт максимальную joint similarity этих двух пар. Это может отличаться
от максимума joint similarity по всем допустимым парам.

Harness [diploma_vrc_targeted_research.py](../../scripts/diploma_vrc_targeted_research.py)
переиспользует `probe_timing_stream`, `select_timing_regions`,
`decode_dense_window`, typed manifests/readers и `_block_descriptor`.
Допуск пар, целочисленные расстояния и retention воспроизведены независимо.
Для **16 benign + 12 demo** повторно полученные полные production `raw_metrics`
совпали с сохранёнными FILE_LEVEL_E2E результатами, включая окна, counts,
distributions и обе retained pairs. Максимальная ошибка response — **0**.
Эта проверка завершена до вычисления альтернативных outcomes.

Новые измерения — **COMPONENT_LEVEL_RESEARCH**: они проходят существующий
bounded dense producer и VRC component, но не submit/API/persistence/cleanup
полного приложения. FILE_LEVEL_E2E остаётся историческим свидетельством PR #72/#73;
новая application-level E2E validation не заявляется.

## 3. Корпуса, paired construction и provenance

Использованы ровно 16 замороженных benign-video derivatives: семейства
`video-01`…`video-08`, по `-reference` и `-processed`. Labels и split сохранены:
03/06/08 — `holdout_benign`, остальные — `observation`.
Эти уже открытые данные в данном sprint не являются новым слепым holdout.
Две производные не удваивают число независимых источников; восемь lineage
families не доказывают статистическую независимость.
Происхождение, авторы и лицензии —
[существующий реестр](../REFERENCES.md#diploma-benign-validation-sources).
Новых интернет-источников и зависимостей нет.

Из одного `BENIGN_REFERENCE` каждого семейства созданы
`paired-video-NN-reference` и `paired-video-NN-repeat`: **8+8 файлов**.
Оба кодируются одинаково: MPEG-4, q=2, GOP=1, yuv420p, один thread,
bitexact, без аудио/metadata, time base 1/24000, 288 кадров, 24 fps, 12 s.
У repeat кадры 246…263 заменены копией кадров 6…23 исходника;
у reference сохраняется исходный сегмент назначения. Обе ветви используют
одинаковые split/trim/setpts/concat, отличаются только выбором среднего сегмента.
Это копия **0.75 s**: `[0.25,1.00)` → `[10.25,11.00)`, разнос стартов **10 s**.
PTS возрастают по 1000 ticks; повреждений PTS и freeze-only конструкции нет.

Фактически retained окна этих 24 fps файлов: `[0,31/24]`, `[5,5+31/24]`,
`[10,10+31/24]` по PTS первых/последних наблюдений, по 32 кадра.
Источник и назначение вставки полностью внутри регионов 0 и 2.
Все 16 выходов сгенерированы дважды и побайтно совпали.
Все восемь source segments содержат **18 различных decoded frames**;
их копии побайтно равны в destination. Наблюдаемые кадры вне destination
совпадают с matched reference. Общая повторная компрессия есть в обеих ветвях.
Commands записаны в `paired-design.json` до encoding, SHA-256 — в manifest
до запуска variants. Это controlled method probes, **не реальные deepfakes**
и **не accuracy ground truth**.

Дополнительно применена та же матрица ко всем 12 существующим demo-видео
без изменения дизайна. Они остаются отдельным diagnostic dataset и не входят
в benign headline denominator.

Внешний workspace:
`C:\Users\Vanur\Desktop\FakeDetector-Work\vrc-targeted-research-sprint1`.
Исходные manifests и media hashes проверены существующими валидаторами.
`freeze.json`, `prepared.json`, `run.json` и `complete.json` связывают
матрицу, входы, код, окружение и результаты. Между prepare и evaluate исправлены
аннотации типов и имена локальных переменных; матрица и численные правила
не менялись. Исходная версия prepare сохранена в `input/preparation-harness.py`.
Медиа и временные RGB artifacts не помещались в Git.

## 4. Замороженная матрица

SHA-256 `research-matrix.json`:
`daed5cbaf10f15c658be8161df406d99ded7b2aa2b433d2ca2415f13ffb8d443`.
Файл создан до альтернативных outcomes; ни один gate не исключался.

| Gate | Условие поверх production admissibility |
|---|---|
| T0_CURRENT | Текущий допуск |
| T1_GAP_0_5S | `B.first_pts - A.last_pts >= 0.5 s` |
| T2_GAP_1S | Тот же gap ≥1 s |
| T3_GAP_2S | Тот же gap ≥2 s |
| T4_CROSS_REGION | Разные dense regions |

Gap вычисляется точно через `Fraction(PTS × time_base)`; fps не подставляется.
Конец группы означает PTS последнего наблюдаемого кадра, без выдуманной
длительности его отображения. Start-to-start separation сохранена отдельно.

Каждый gate имеет десять pooling variants: strongest, second, third, fifth,
top3 mean, top5 mean, p99, p95, median, GREEDY_DISJOINT_TOP3 mean — **50 variants**.
Квантили — linear interpolation `(n-1)*p`; top-k требует не менее k пар.
Greedy выбирает до трёх пар без повторного использования той же четырёхкадровой
группы. Это **не запрет пересечения кадров** соседних групп и не три независимых
эпизода. Число поддерживающих пар выводится отдельно; readiness требует трёх.
Пустые/неподдержанные значения — `null`, не ноль. Все summary statistics
вычисляются по полному eligible set; полный ограниченный pair ledger сохранён
в `artifacts/pairs/`, а top-5 с PTS/gap — в отдельной temporal table.

До outcomes дополнительно закреплён описательный readiness screen:
8/8 measurable families, 16/16 supported benign samples, ≥7/8 положительных
paired deltas, снижение benign median минимум на 0.05 против current response,
median <0.95 и снижение среднего benign response в каждом из восьми семейств.
Числа 0.05/0.95 — операционализация исследовательского критерия, **не production
thresholds**. Ranking сначала учитывает coverage/support, затем benign median
и ≥0.95 count, paired positives, семейную устойчивость и простоту.
Переопределение шкалы similarity и exploratory normalizer не вводились.

## 5. Гипотеза локальной временной близости — RQ1

Наблюдение владельца воспроизведено: **15/16** лучших T0-пар из одного региона,
**1/16** — cross-region; **15/16** имеют gap ≤0.5 s, **0** — (0.5,1),
**0** — [1,2), **1** — ≥2 s. Для тех же 15 файлов start-to-start separation
также ≤0.5 s; у **13/16** файлов разность стартовых ordinals равна 5.
Исключения внутри региона: `video-05-reference` — 10, `video-07-processed` — 7.
Cross-region исключение — `video-07-reference`, gap 4.916667 s.
Разность ordinals разных регионов не интерпретируется как временное расстояние.

Однако удаление локальных пар **недостаточно**: T4 median остаётся 0.993708,
≥0.95 — 13/16, ≥0.75 — 16/16. Изменение median относительно T0 всего
0.003344. Локальная непрерывность объясняет расположение большинства максимумов,
но не объясняет всё насыщение после её исключения.
Все gates сохраняют 16/16 файлов и восемь семейств. T3 и T4 на этих корпусах
выбирают одинаковые наборы пар: внутри каждого retained окна нет gap ≥2 s.
Это свойство наблюдаемого покрытия, не общая эквивалентность правил.

В следующей таблице — strongest similarity, N=16 для каждой строки.
Уровни ≥0.95/0.90/0.75 описательные, не operating thresholds.

| Gate | min | p25 | median | p75 | max | ≥.95 | ≥.90 | ≥.75 | <.75 |
|---|---|---|---|---|---|---|---|---|---|
| T0_CURRENT | 0.984178 | 0.996175 | 0.997052 | 0.998907 | 0.999930 | 16 | 16 | 16 | 0 |
| T1_GAP_0_5S | 0.960861 | 0.990894 | 0.996650 | 0.998021 | 0.999739 | 16 | 16 | 16 | 0 |
| T2_GAP_1S | 0.927587 | 0.985466 | 0.994339 | 0.996479 | 0.998620 | 14 | 16 | 16 | 0 |
| T3_GAP_2S | 0.837160 | 0.955940 | 0.993708 | 0.995779 | 0.996982 | 13 | 14 | 16 | 0 |
| T4_CROSS_REGION | 0.837160 | 0.955940 | 0.993708 | 0.995779 | 0.996982 | 13 | 14 | 16 | 0 |


| sample_id | Split | Current = T0 strongest | T4 strongest | region:ordinal A → B | Gap s | Start separation s |
|---|---|---|---|---|---|---|
| video-01-reference | O | 0.995221 | 0.952315 | 1:2 → 1:7 | 0.083333 | 0.208333 |
| video-01-processed | O | 0.993634 | 0.957149 | 1:0 → 1:5 | 0.133333 | 0.333333 |
| video-02-reference | O | 0.998436 | 0.994365 | 1:23 → 1:28 | 0.083333 | 0.208333 |
| video-02-processed | O | 0.998666 | 0.994987 | 1:21 → 1:26 | 0.133333 | 0.333333 |
| video-03-reference | H | 0.991013 | 0.837334 | 0:20 → 0:25 | 0.083333 | 0.208333 |
| video-03-processed | H | 0.984178 | 0.837160 | 0:11 → 0:16 | 0.133333 | 0.333333 |
| video-04-reference | O | 0.997122 | 0.993051 | 2:7 → 2:12 | 0.083333 | 0.208333 |
| video-04-processed | O | 0.996494 | 0.992511 | 1:21 → 1:26 | 0.133333 | 0.333333 |
| video-05-reference | O | 0.999793 | 0.996235 | 2:8 → 2:18 | 0.291667 | 0.416667 |
| video-05-processed | O | 0.999862 | 0.995584 | 2:7 → 2:12 | 0.133333 | 0.333333 |
| video-06-reference | H | 0.998203 | 0.996496 | 2:2 → 2:7 | 0.083333 | 0.208333 |
| video-06-processed | H | 0.996764 | 0.995627 | 0:12 → 0:17 | 0.133333 | 0.333333 |
| video-07-reference | O | 0.996982 | 0.996982 | 1:0 → 2:1 | 4.916667 | 5.041667 |
| video-07-processed | O | 0.996873 | 0.996414 | 2:4 → 2:11 | 0.266667 | 0.466667 |
| video-08-reference | H | 0.999930 | 0.900402 | 2:14 → 2:19 | 0.083333 | 0.208333 |
| video-08-processed | H | 0.999632 | 0.976071 | 2:9 → 2:14 | 0.133333 | 0.333333 |

Отдельный retention diagnostic дал **absolute difference=0 для всех 44 файлов**
между current retained-minima response и true strongest joint similarity.
Следовательно, потеря совместного максимума при раздельном retention не является
причиной этого результата. Возможность такой потери математически существует
и покрыта отдельным тестом с несовпадающими color/delta minima.

## 6. Extreme-value/minimum pooling — RQ2

У T0 по 3423 пары для reference и 2946 для processed. Межфайловые Pearson и
Spearman между `log(eligible_pairs)` и strongest приведены ниже. Два производных
файла семейства зависимы; количество пар связано с fps/обработкой. Эти описательные
корреляции не устанавливают причинность; p-values и доверительные интервалы
не рассчитывались.

| Gate | Pairs/file | Pearson | Spearman | median(max−p99) | median(max−p95) |
|---|---|---|---|---|---|
| T0_CURRENT | 2946…3423 | 0.168384 | 0.162698 | 0.000741 | 0.002065 |
| T1_GAP_0_5S | 2595…2838 | -0.017236 | 0.108465 | 0.000680 | 0.001853 |
| T2_GAP_1S | 2322…2532 | -0.075469 | 0.054233 | 0.001775 | 0.002650 |
| T3_GAP_2S | 2187…2523 | -0.091029 | 0.054233 | 0.000393 | 0.001168 |
| T4_CROSS_REGION | 2187…2523 | -0.091029 | 0.054233 | 0.000393 | 0.001168 |

До outcomes закреплены 16 PCG64-перестановок полного candidate set на sample/gate
с SHA-256 seed и вложенные размеры 1/4/16/64/256/1024/full. Это диагностика
извлечения экстремума из уже наблюдённого распределения, не новые независимые
видеонаблюдения. В каждом вложенном ряду максимум не убывает по определению.
Таблица показывает median по 16 файлам от среднего strongest по 16 перестановкам.
Полные per-sample/per-replicate ряды сохранены в `extreme-value-pooling.csv`.

| Число кандидатов | T0 | T4 |
|---|---|---|
| 1 | 0.977934 | 0.976221 |
| 4 | 0.990783 | 0.987992 |
| 16 | 0.995334 | 0.992329 |
| 64 | 0.996511 | 0.993313 |
| 256 | 0.996668 | 0.993588 |
| 1024 | 0.996932 | 0.993675 |
| Полный set | 0.997052 | 0.993708 |

Рост числа кандидатов усиливает высокий отклик в пределах этих наблюдений,
но даже случайная одиночная distant pair имеет высокий типичный отклик.
Малый разрыв strongest−p99 и сохранение насыщения p95 показывают, что проблема
не ограничена одной исключительно удачной парой. Результат поддерживает механизм
extreme-value усиления, но не количественно отделяет его причинный вклад от
масштаба дескриптора и содержания.

## 7. Масштаб descriptor distances — RQ3

Ниже для каждой distance приведены **медианы соответствующих per-file статистик**
16 benign-файлов, а не распределение смешанного корпуса с весом по числу пар.
Полные семь статистик для каждого sample/gate/distance — в
`distance-distributions.csv`; ни одна eligible pair не отбрасывается при расчёте.

| Gate | Distance | min | p01 | p05 | p25 | median | p75 | max |
|---|---|---|---|---|---|---|---|---|
| T0_CURRENT | color | 0.002948 | 0.003495 | 0.004298 | 0.009355 | 0.017493 | 0.034490 | 0.052720 |
| T0_CURRENT | delta | 0.000770 | 0.000861 | 0.000938 | 0.001159 | 0.001365 | 0.001961 | 0.004071 |
| T0_CURRENT | joint | 0.002948 | 0.003495 | 0.004298 | 0.009355 | 0.017493 | 0.034490 | 0.052720 |
| T1_GAP_0_5S | color | 0.003350 | 0.003871 | 0.007024 | 0.010937 | 0.022646 | 0.036652 | 0.052720 |
| T1_GAP_0_5S | delta | 0.000784 | 0.000889 | 0.000960 | 0.001174 | 0.001379 | 0.001999 | 0.004071 |
| T1_GAP_0_5S | joint | 0.003350 | 0.003871 | 0.007024 | 0.010937 | 0.022646 | 0.036652 | 0.052720 |
| T2_GAP_1S | color | 0.005661 | 0.006568 | 0.007427 | 0.011788 | 0.023563 | 0.037236 | 0.052720 |
| T2_GAP_1S | delta | 0.000786 | 0.000893 | 0.000963 | 0.001179 | 0.001387 | 0.002007 | 0.004071 |
| T2_GAP_1S | joint | 0.005661 | 0.006568 | 0.007427 | 0.011788 | 0.023563 | 0.037236 | 0.052720 |
| T3_GAP_2S | color | 0.006292 | 0.006583 | 0.007439 | 0.012001 | 0.023729 | 0.037068 | 0.052720 |
| T3_GAP_2S | delta | 0.000786 | 0.000893 | 0.000962 | 0.001182 | 0.001389 | 0.002004 | 0.004071 |
| T3_GAP_2S | joint | 0.006292 | 0.006583 | 0.007439 | 0.012001 | 0.023729 | 0.037068 | 0.052720 |
| T4_CROSS_REGION | color | 0.006292 | 0.006583 | 0.007439 | 0.012001 | 0.023729 | 0.037068 | 0.052720 |
| T4_CROSS_REGION | delta | 0.000786 | 0.000893 | 0.000962 | 0.001182 | 0.001389 | 0.002004 | 0.004071 |
| T4_CROSS_REGION | joint | 0.006292 | 0.006583 | 0.007439 | 0.012001 | 0.023729 | 0.037068 | 0.052720 |

После исключения близких пар типичная медиана color/joint distance — лишь
**0.023729**, delta — **0.001389**. Даже median pooling поэтому даёт 0.976271.
Теоретические denominators соответствуют предельным изменениям всех компонент;
обычное содержание занимает существенно более узкую часть этой шкалы.
Это согласуется с гипотезой RQ3: `1−distance` численно близок к 1 и для
доброкачественных дальних групп. Однако experiment не варьировал spatial grid,
дескриптор или нормализатор отдельно; их причинные вклады не разделены.
Новая функция нормализации не предложена как production решение.

## 8. Robust pooling diagnostics

Все 50 variants измеримы на 16 benign-файлах и восьми matched families;
greedy support равен трём. Ни top-3/top-5, ни p99/p95, ни запрет повторного
использования идентичной группы не устранили высокий benign baseline.
Таблица сопоставляет median response при T0 и T4; все остальные gate/pool
числа, counts ≥0.95/0.90/0.75 и <0.75 находятся в `benign-variant-summary.csv`.

| Pooling | T0 benign median | T4 benign median | T4 ≥.95 /16 | T4 paired Δ>0 /8 | T4 paired median Δ |
|---|---|---|---|---|---|
| strongest | 0.997052 | 0.993708 | 13 | 8 | 0.006289 |
| second | 0.996917 | 0.993683 | 13 | 8 | 0.006321 |
| third | 0.996911 | 0.993654 | 13 | 8 | 0.006340 |
| fifth | 0.996805 | 0.993635 | 13 | 8 | 0.006376 |
| top3_mean | 0.996960 | 0.993682 | 13 | 8 | 0.006317 |
| top5_mean | 0.996907 | 0.993666 | 13 | 8 | 0.006336 |
| p99 | 0.996505 | 0.993417 | 13 | 8 | 0.004936 |
| p95 | 0.995702 | 0.992561 | 13 | 7 | 0.003131 |
| median | 0.982507 | 0.976271 | 10 | 3 | -0.000243 |
| greedy_disjoint_top3_mean | 0.996960 | 0.993610 | 13 | 8 | 0.006388 |

Greedy disjoint группы могут разделять три кадра из четырёх с соседними
группами. Поэтому его три supports нельзя называть тремя независимыми повторами.
Усиление до независимых эпизодов в текущую матрицу не добавлялось post hoc.

## 9. Matched distant-repeat experiment — controlled paired separation result

Разности — `repeat_metric−reference_metric`. Это **controlled paired separation
result**, не sensitivity, TPR или оценка реальных deepfakes. Exact sample IDs
для каждой пары указаны ниже. Все 18 скопированных кадров сохранились в dense
наблюдениях. Все repeat strongest при T4 равны 1, но reference уже близки к 1.

| Reference sample_id | Repeat sample_id | T4 ref max | T4 repeat max | Δ max | Δ median |
|---|---|---|---|---|---|
| paired-video-01-reference | paired-video-01-repeat | 0.952315 | 1.000000 | 0.047685 | 0.024421 |
| paired-video-02-reference | paired-video-02-repeat | 0.994360 | 1.000000 | 0.005640 | 0.000876 |
| paired-video-03-reference | paired-video-03-repeat | 0.837341 | 1.000000 | 0.162659 | -0.001266 |
| paired-video-04-reference | paired-video-04-repeat | 0.993062 | 1.000000 | 0.006938 | -0.002610 |
| paired-video-05-reference | paired-video-05-repeat | 0.996208 | 1.000000 | 0.003792 | -0.000334 |
| paired-video-06-reference | paired-video-06-repeat | 0.996505 | 1.000000 | 0.003495 | -0.000152 |
| paired-video-07-reference | paired-video-07-repeat | 0.996991 | 1.000000 | 0.003009 | 0.001334 |
| paired-video-08-reference | paired-video-08-repeat | 0.900408 | 1.000000 | 0.099592 | -0.303847 |

Для каждой из 50 комбинаций ниже приведены знаки и диапазон paired deltas; denominator всегда 8.

| Gate | Pooling | + / 0 / − | median Δ | min Δ | max Δ |
|---|---|---|---|---|---|
| T0_CURRENT | strongest | 8 / 0 / 0 | 0.002351 | 0.000068 | 0.008973 |
| T0_CURRENT | second | 8 / 0 / 0 | 0.002493 | 0.000068 | 0.009234 |
| T0_CURRENT | third | 8 / 0 / 0 | 0.002534 | 0.000082 | 0.009702 |
| T0_CURRENT | fifth | 8 / 0 / 0 | 0.002588 | 0.000089 | 0.010705 |
| T0_CURRENT | top3_mean | 8 / 0 / 0 | 0.002479 | 0.000073 | 0.009303 |
| T0_CURRENT | top5_mean | 8 / 0 / 0 | 0.002521 | 0.000078 | 0.009859 |
| T0_CURRENT | p99 | 6 / 0 / 2 | 0.000893 | -0.000415 | 0.014993 |
| T0_CURRENT | p95 | 4 / 0 / 4 | 0.000139 | -0.002196 | 0.029547 |
| T0_CURRENT | median | 4 / 0 / 4 | -0.000108 | -0.011515 | 0.003391 |
| T0_CURRENT | greedy_disjoint_top3_mean | 8 / 0 / 0 | 0.002479 | 0.000073 | 0.009303 |
| T1_GAP_0_5S | strongest | 8 / 0 / 0 | 0.003252 | 0.000254 | 0.039120 |
| T1_GAP_0_5S | second | 8 / 0 / 0 | 0.003284 | 0.000275 | 0.041789 |
| T1_GAP_0_5S | third | 8 / 0 / 0 | 0.003361 | 0.000286 | 0.044227 |
| T1_GAP_0_5S | fifth | 8 / 0 / 0 | 0.003388 | 0.000340 | 0.048491 |
| T1_GAP_0_5S | top3_mean | 8 / 0 / 0 | 0.003299 | 0.000272 | 0.041712 |
| T1_GAP_0_5S | top5_mean | 8 / 0 / 0 | 0.003333 | 0.000296 | 0.044051 |
| T1_GAP_0_5S | p99 | 7 / 0 / 1 | 0.002411 | -0.000093 | 0.051179 |
| T1_GAP_0_5S | p95 | 5 / 0 / 3 | 0.001786 | -0.000522 | 0.088342 |
| T1_GAP_0_5S | median | 3 / 0 / 5 | -0.000133 | -0.156578 | 0.023700 |
| T1_GAP_0_5S | greedy_disjoint_top3_mean | 8 / 0 / 0 | 0.003314 | 0.000285 | 0.042513 |
| T2_GAP_1S | strongest | 8 / 0 / 0 | 0.005339 | 0.001403 | 0.072397 |
| T2_GAP_1S | second | 8 / 0 / 0 | 0.005372 | 0.001534 | 0.072467 |
| T2_GAP_1S | third | 8 / 0 / 0 | 0.005432 | 0.001589 | 0.074551 |
| T2_GAP_1S | fifth | 8 / 0 / 0 | 0.005992 | 0.002596 | 0.122383 |
| T2_GAP_1S | top3_mean | 8 / 0 / 0 | 0.005381 | 0.001508 | 0.073138 |
| T2_GAP_1S | top5_mean | 8 / 0 / 0 | 0.005596 | 0.001877 | 0.092826 |
| T2_GAP_1S | p99 | 8 / 0 / 0 | 0.004920 | 0.000171 | 0.158448 |
| T2_GAP_1S | p95 | 7 / 0 / 1 | 0.003154 | -0.000488 | 0.325750 |
| T2_GAP_1S | median | 3 / 0 / 5 | -0.000246 | -0.301523 | 0.024401 |
| T2_GAP_1S | greedy_disjoint_top3_mean | 8 / 0 / 0 | 0.005523 | 0.001752 | 0.089066 |
| T3_GAP_2S | strongest | 8 / 0 / 0 | 0.006289 | 0.003009 | 0.162659 |
| T3_GAP_2S | second | 8 / 0 / 0 | 0.006321 | 0.003057 | 0.162747 |
| T3_GAP_2S | third | 8 / 0 / 0 | 0.006340 | 0.003177 | 0.162897 |
| T3_GAP_2S | fifth | 8 / 0 / 0 | 0.006376 | 0.003216 | 0.162970 |
| T3_GAP_2S | top3_mean | 8 / 0 / 0 | 0.006317 | 0.003081 | 0.162768 |
| T3_GAP_2S | top5_mean | 8 / 0 / 0 | 0.006336 | 0.003135 | 0.162846 |
| T3_GAP_2S | p99 | 8 / 0 / 0 | 0.004936 | 0.000171 | 0.158709 |
| T3_GAP_2S | p95 | 7 / 0 / 1 | 0.003131 | -0.000484 | 0.325758 |
| T3_GAP_2S | median | 3 / 0 / 5 | -0.000243 | -0.303847 | 0.024421 |
| T3_GAP_2S | greedy_disjoint_top3_mean | 8 / 0 / 0 | 0.006388 | 0.003094 | 0.175933 |
| T4_CROSS_REGION | strongest | 8 / 0 / 0 | 0.006289 | 0.003009 | 0.162659 |
| T4_CROSS_REGION | second | 8 / 0 / 0 | 0.006321 | 0.003057 | 0.162747 |
| T4_CROSS_REGION | third | 8 / 0 / 0 | 0.006340 | 0.003177 | 0.162897 |
| T4_CROSS_REGION | fifth | 8 / 0 / 0 | 0.006376 | 0.003216 | 0.162970 |
| T4_CROSS_REGION | top3_mean | 8 / 0 / 0 | 0.006317 | 0.003081 | 0.162768 |
| T4_CROSS_REGION | top5_mean | 8 / 0 / 0 | 0.006336 | 0.003135 | 0.162846 |
| T4_CROSS_REGION | p99 | 8 / 0 / 0 | 0.004936 | 0.000171 | 0.158709 |
| T4_CROSS_REGION | p95 | 7 / 0 / 1 | 0.003131 | -0.000484 | 0.325758 |
| T4_CROSS_REGION | median | 3 / 0 / 5 | -0.000243 | -0.303847 | 0.024421 |
| T4_CROSS_REGION | greedy_disjoint_top3_mean | 8 / 0 / 0 | 0.006388 | 0.003094 | 0.175933 |

Положительные max/top-k разности во всех восьми семействах показывают
сохранение ответа на наблюдаемый вставленный повтор, но не решают насыщение.
Переход к медиане всего множества пар уменьшает селективность к короткому эпизоду:
у T3/T4 пять отрицательных paired deltas из восьми, minimum −0.303847.
Снижение benign median и полезное paired различение должны оцениваться совместно.

## 10. Проверка старого demo corpus

Применены все gates/pools ко всем 12 файлам, без regeneration или изменения
дизайна. Здесь компактное сопоставление T0/T4; полная таблица —
`demo-diagnostic-summary.csv`. Demo не включён в benign denominator.

| sample_id | T0 max | T4 max | T4 p99 | T4 median | T4 greedy |
|---|---|---|---|---|---|
| video-01-control | 0.995096 | 0.987947 | 0.987906 | 0.987598 | 0.987906 |
| video-01-cut | 0.995148 | 0.987981 | 0.987949 | 0.809357 | 0.987955 |
| video-01-distant | 1.000000 | 1.000000 | 1.000000 | 0.987455 | 1.000000 |
| video-01-freeze | 1.000000 | 0.993332 | 0.993332 | 0.987741 | 0.992267 |
| video-02-control | 0.979548 | 0.937611 | 0.935252 | 0.912729 | 0.936299 |
| video-02-timing | 0.979389 | 0.933762 | 0.930435 | 0.912436 | 0.931158 |
| video-02-transition | 0.979548 | 0.937611 | 0.933943 | 0.912064 | 0.935746 |
| video-02-vfr | 0.979548 | 0.935755 | 0.932333 | 0.912569 | 0.933976 |
| video-03-control | 0.999610 | 0.999610 | 0.999511 | 0.987759 | 0.999596 |
| video-03-loop | 1.000000 | 1.000000 | 1.000000 | 0.995733 | 1.000000 |
| video-03-repeat | 0.999610 | 0.999610 | 0.999511 | 0.987759 | 0.999596 |
| video-03-static | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |

`video-03-static` остаётся 1 при всех вариантах. `video-03-loop` также остаётся
1 для max/top-k/p99/p95/greedy; T4 median=0.995733. Подавления benign static/loop
не получено. `video-01-freeze` теряет локальный perfect match, но T4 max=0.993332.
Наблюдаемый `video-01-distant` сохраняет T4 max/top3/top5/p99/greedy=1.
При T4 median его response=0.987455, чуть ниже control=0.987598:
такая агрегация ослабляет именно короткий целевой повтор.

Ранее пропущенный `video-03-repeat` остаётся равен `video-03-control` по всем
вариантам: копируемый участок [2,3) s не входит в retained dense окна
[0,2), [4,6), [8,10). Изменение candidate policy не создаёт отсутствующее
наблюдение. Здесь не исправлялись покрытие или дизайн этого случая.

## 11. Ranking и проверка готовности

У всех 50 вариантов coverage 8/8 families и 16/16 benign samples, поэтому
первое различие ranking — benign saturation reduction. Лучший описательный
rank — **T3_GAP_2S__median**; численно равный T4_CROSS_REGION__median идёт
следом по замороженному simplicity tie-break. Это **не выбранный production
кандидат**. Его benign median=0.976271, снижение=0.020781; ≥0.95 у 10/16,
paired positives=3/8, paired median delta=−0.000243. Средний benign response
уменьшается во всех восьми семействах, однако основные критерии не выполнены.

**READY_FOR_PROTOTYPE: 0/50.** Даже наименьшая median всех вариантов выше 0.95,
а максимальное median reduction меньше предзаданного 0.05. Вывод не зависит
от одного привлекательного sample и не достигается исключением static/loop.
Полный порядок, все coverage и paired criteria — `variant-ranking.csv`.

## 12. Ограничения

- Малый convenience corpus: 16 derivatives, восемь lineage families; нет
  случайной эксплуатационной выборки и нового независимого validation set.
- Источники уже были преобразованы в короткие CFR MP4 без аудио. Исследуется
  этот frozen preprocessing profile, не native VFR, длинные файлы или все codecs.
- Dense producer наблюдает только до 3×32 кадров. Совпадение descriptors не
  означает pixel equality; equality в контролируемой вставке проверена отдельно.
- Paired construction заменяет короткий поздний эпизод ранним с теми же settings;
  это ограниченная проба точной копии, не все виды монтажа или генерации.
- Greedy support не обеспечивает неперекрывающиеся кадры/эпизоды. Квантили могут
  размывать редкий целевой повтор; max чувствителен к размеру candidate set.
- Межфайловые correlations описательны; nested subsampling демонстрирует свойство
  pooling на фиксированных данных, а не причинный эксперимент с независимыми файлами.
- RQ3 не отделяет влияние grid, visual homogeneity и denominator в отдельных
  вмешательствах. Никакой другой нормализатор или ML inference не исследовался.
- Высокий response — **не authenticity/deepfake probability** и не доказательство
  манипуляции. Числа здесь **не FPR/TPR**, accuracy или production calibration.
  Ансамбль после outcomes не настраивался.

## 13. Итоговая disposition и ответы на RQ

**VRC_REDESIGN_REQUIRED.** В границах замороженной матрицы temporal gate и
robust pooling недостаточны: сильное similarity насыщение сохраняется, а более
агрессивное усреднение одновременно ослабляет ответ на внесённый distant repeat.
Это вывод о данном ограниченном семействе правил, не доказательство невозможности
любого объяснимого метода.

RQ1: локальная близость определяет 15/16 текущих лучших locations, но её
исключение почти не устраняет benign saturation. RQ2: extrema усиливаются с числом
кандидатов; p99/p95 остаются близки к максимуму, межфайловая связь слабая и не
причинная. RQ3: дальние обычные descriptors численно близки под текущей шкалой;
одной temporal policy недостаточно. RQ4: готового bounded policy candidate нет.
Отдельный retention defect на этих 44 файлах не обнаружен.

## 14. Воспроизведение, проверки и следующий шаг

Команды из checkout, с новым абсолютным workspace вне репозитория:

```powershell
uv run python -m scripts.diploma_vrc_targeted_research prepare --workspace $workspace --benign $benignWorkspace --demo $demoWorkspace
uv run python -m scripts.diploma_vrc_targeted_research evaluate --workspace $workspace
```

`prepare` проверяет исходные seals/media, фиксирует матрицу, воспроизводит старые
результаты, создаёт и проверяет matched probes. `evaluate` проверяет bindings и
production/environment fingerprints до и после измерений. Выходы exclusive:
старые результаты не перезаписываются. Индивидуальные exact FFmpeg argv и SHA-256
находятся во внешнем manifest, окружение — в freeze. Медиа не входят в review bundle.

Focused tests: **103 passed**, включая 24 новых tests/cases. Ruff и focused mypy
проверяют новый harness; независимый перерасчёт без project imports подтвердил
**220 sample/gate rows, 400 paired deltas, 50 benign summaries** и SHA-256 seals.
Новые tests используют только маленькие собственные fixtures, не внешний corpus.

Единственный `uv run poe check`: pre-commit PASS, mypy по 71 source files PASS,
pytest **3118 passed / 17 skipped / 1 failed**, coverage **91%**.
Единственный fail — `test_sdist_wheel_metadata_entry_point_and_resources`:
существующий provenance guard отклоняет intended untracked report.
Независимая read-only проверка всех 237 members фактически построенного sdist
подтвердила ровно три intended untracked-файла (report, harness, tests), без
пропусков tracked files, duplicate/invalid members и расхождений байтов на момент
сборки. Итог barrier — **OWNER_VERIFY_REQUIRED**, не PASS; guard не ослаблялся.
CLI smoke, который последовательность не достигла после fail, выполнен отдельно — PASS.
Полный barrier повторно не запускался. Последующие правки документов только
фиксируют эти результаты; это development verification, **не strict certification**.
После owner review/staging проверку повторяет владелец. Git mutations не выполнялись.

Review bundle:
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\DIPLOMA-vrc-targeted-research-sprint1`.
Включены все таблицы, полный pair ledger, manifests/freeze, логи, полный diff
с тремя untracked-файлами и копии всех четырёх изменённых файлов.
SHA-256 и размеры артефактов записаны в seal; медиа в bundle отсутствуют.
Graphify STALE (provenance SHA `625b9e83…`), не пересобирался и не использовался
как архитектурное доказательство. Проверка diff не выявила production изменений,
новых dependencies/config/schema, дублирующего runtime или временных helpers.

Следующий шаг — owner review отчёта, таблиц и полного diff. Отдельный sprint
может исследовать более селективное представление/контекст повторяемого эпизода
и поддержку независимыми эпизодами; конкретный метод, normalizer или threshold
здесь не выбран. Production modification требует отдельной авторизации и method
gate. VRC не объявляется production-ready, Stage 12 остаётся IN_PROGRESS.
