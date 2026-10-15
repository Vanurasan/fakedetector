# Исследование redesign VRC — Sprint 1

Дата выполнения: **2026-10-15**, Asia/Krasnoyarsk. Имя файла с датой 2026-10-14
сохранено по заданию `STAGE12-DIPLOMA-VRC-REDESIGN-RESEARCH-SPRINT1`.
Baseline: `178434843521382fa905bb4d15b95ceb702fb693`; исходная ветка
`feat/stage12-vrc-redesign-research-sprint1`, рабочее дерево было чистым.
Это **RESEARCH_ONLY / COMPONENT_LEVEL_RESEARCH**. Production VRC
`video_repeated_content_correspondence@1.0.0`, `VRC-DENSE-DIPLOMA-1` и
`diploma_ensemble_v1@0.1.0` сохранены. **AGENT SELF-REPORT IS NOT OWNER ACCEPTANCE.**
Статус приёмки принадлежит [ROADMAP](../ROADMAP.md#diploma-vrc-redesign-research-sprint1).

## 1. Причина redesign

Абсолютная похожесть `1 − distance / theoretical_maximum` даёт почти единицу
для обычного внешнего видеоконтента. Цель — проверить, отделяет ли необычно
сильное поддержанное дальнее соответствие известную копию эпизода от обычной
визуальной близости. Исследуются представление (RQ1), временная поддержка (RQ2),
относительная исключительность (RQ3), малоинформативные сцены (RQ4) и перенос
выбора на прежние holdout-семейства (RQ5). ML, semantic inference, настройки
ансамбля и пороги для отдельных файлов не применялись.

## 2. Что установлено предыдущими исследованиями

[Benign validation PR #73](2026-10-13-diploma-benign-validation.md) дала
VRC ≥0.75 у 16/16 видео, median≈0.997052. В
[targeted research PR #74](2026-10-14-vrc-targeted-research.md) ограничение
gap≥2 s и разные регионы оставили median≈0.993708. Extreme-value selection
усиливала насыщение, но не создавала его: обычная дальняя joint distance имела
median≈0.02373 на теоретической шкале 0…1. На всём benign T0 delta distance
не превышала color distance. Раздельное сохранение color/delta minima не
объяснило результат. Median pooling снизил benign median лишь до≈0.976271,
при этом полезное paired различение ухудшилось; готовы были 0/50 вариантов.
Владелец принял `VRC_REDESIGN_REQUIRED` и отдельно разрешил эту матрицу.

Перед новыми измерениями **44/44 полных production raw_metrics воспроизведены
точно**, включая 16 benign, 12 demo и 16 paired входов. Для первых 28 сверены
также прежние FILE_LEVEL_E2E результаты. **MAX_BASELINE_REPRO_ERROR=0**.
Production retention и normalizer дополнительно сверены независимой реализацией
предыдущего принятого harness. Это контроль воспроизведения, не новые E2E-прогоны.

## 3. Новый принцип: distinctiveness вместо абсолютной похожести

Для полного множества допустимых runs одного файла сравниваются лучший run
и собственное распределение конкурирующих correspondences. Score означает
относительное выделение лучшего совпадения. Он **не является probability,
confidence, FPR/TPR, authenticity ground truth или откалиброванным production
response**. Единица возможна для точной копии и обычного повторного содержания;
отсутствие измерения не означает подлинности.

Harness [diploma_vrc_redesign_research.py](../../scripts/diploma_vrc_redesign_research.py)
переиспользует принятые `probe_timing_stream`, `select_timing_regions`,
`decode_dense_window`, typed readers, group extraction и `_block_descriptor`.
Нет отдельного декодера, image-codec round trip, новых зависимостей или runtime API.
Production preprocessing сохраняет максимум 3×32 кадров, RGB24, реальные PTS,
геометрию и границы регионов. Полноразмерная матрица N×N×descriptor не создаётся:
расстояния считаются по одной строке. Все grids/populations остаются вне Git.

## 4. Корпус и split discipline

Новых интернет-источников и новых медиа нет. Повторно использованы принятые
корпуса `diploma-benign-validation`, `vrc-targeted-research-sprint1` и
`diploma-demo-evaluation` во внешнем `FakeDetector-Work`.
Происхождение и лицензии — [реестр PR #73](../REFERENCES.md#diploma-benign-validation-sources);
происхождение demo — [отчёт PR #72](2026-10-13-diploma-demo-evaluation.md).

Основной benign denominator — **16 файлов / 8 source families**:
8 BENIGN_REFERENCE, 6 BENIGN_PROCESSING, 2 BENIGN_CONFOUND. Все sample IDs,
роли, source_family, split и SHA-256 сохранены. Отдельно — 8 matched references
и 8 distant-repeat derivatives PR #74. Reference пары не добавляется к benign
denominator; две обычные обработки тоже не считаются двумя независимыми семьями.

| Split | Source families | Benign | Matched reference | Matched repeat |
| --- | --- | --- | --- | --- |
| observation | video-01/02/04/05/07 | 10 | 5 | 5 |
| holdout_benign | video-03/06/08 | 6 | 3 | 3 |

Повтор PR #74 сохраняет точную копию кадров 6…23 в 246…263:
`[0.25,1.00) s → [10.25,11.00) s`, 24 fps. Нового encoding не было.
Повторная pixel/PTS QA подтвердила все 18 различных исходных кадров, exact копию
и неизменённые наблюдения вне destination во всех 8 семействах; SHA-256
и старые QA/seals совпали. Это известное действие генератора, не реальные deepfakes.

Порядок фаз: input/matrix freeze → production reproduction всех входов →
50 вариантов только на observation → ranking → `selected-candidate.json` →
ровно выбранный кандидат + production control на holdout → freeze disposition →
demo только для этих двух вариантов. Raw dense grids holdout сохранены при
обязательном baseline reproduction; новые descriptor/energy/score outcomes до
выбора не вычислялись. **Holdout не использован для выбора формулы.** При этом
его контент и production/PR74 outcomes известны из прошлых работ: это восстановленная
граница выбора данного sprint, а не новый полностью слепой внешний датасет.

## 5. D1–D4 descriptors

База — те же 9×16 RGB block means с production integer half-up rounding,
включающие все пиксели. Группа состоит из четырёх последовательных retained frames
с известными строго возрастающими PTS. Missing timing не интерполируется.
Последующие операции выполняются в signed float64.

| ID | Представление группы | Компонент |
| --- | --- | --- |
| D1_CENTERED_GRID | Для каждого кадра/канала вычитается среднее по 144 блокам | 1728 |
| D2_SPATIAL_GRADIENT | Signed разности соседних блоков по горизонтали и вертикали, все 4 кадра | 3156 |
| D3_TEMPORAL_RESIDUAL | Три последовательные временные разности centered grids D1 | 1296 |
| D4_HYBRID_STRUCTURE_MOTION | Concatenate D2+D3, без вручную выбранных весов | 4452 |

Расстояние — `mean(abs(descriptor_A − descriptor_B))`. Теоретического деления
на 255 для D1–D4 нет. В D4 вес задаётся только числом компонентов; пространственная
часть занимает 3156/4452, temporal — 1296/4452. Signed differences не заменены
модулями до сравнения. D1 удаляет общий покадровый RGB offset, сохраняя структуру.

## 6. Informativeness gate

`temporal_energy = mean(abs(D3))`. Энергии рассчитываются для **всех valid groups**
файла, до исключения по парам/runs. I0 допускает все группы; I25 допускает
только `energy > p25`, со строгим сравнением и линейным квантилем.
Если не осталось групп, результат — `INSUFFICIENT_LOW_INFORMATION`, score=null.

Это **относительный** фильтр. Он не задаёт абсолютного motion floor: почти
статичные, но неодинаковые энергии всё ещё могут оставить примерно 75% групп.
При одинаковой положительной энергии строгий gate также не оставит групп.
Centered energy не видит чистый глобальный RGB offset. Эти свойства не исправлялись
после outcomes; дополнительных порогов или fallback нет.

## 7. Consistent-lag run support

Каждая constituent pair должна иметь совместимые stream/geometry и
`B.first_pts×base_B − A.last_pts×base_A ≥ 2 s`, вычисленные точно через Fraction.
End означает PTS последнего наблюдённого кадра, без выдуманной длительности кадра.
Runs K3/K5/K9 состоят из последовательных **стартов групп** на каждой стороне
в пределах одного dense sequence. Пропущенный start или информационный отказ
разрывает run; регионы не сшиваются. Допуск проверяется для каждой constituent pair.

Совмещение задаёт постоянный ordinal lag; реальные PTS offsets каждой пары
сохранены. Дополнительный неуказанный tolerance по секундам не вводился.
K соседних четырёхкадровых групп покрывают K+3 кадров и перекрываются;
это не K независимых эпизодов. При K9 поддержка занимает 12 кадров — 0.5 s
при 24 fps, но 1.5 s при 8 fps. В вычислении gap fps не используется.

Run distance — **median всех K distances**, не minimum. Поэтому K9 допускает
до четырёх несовпадающих constituent pairs при нулевой медиане. Это существенно
для локализации и показано в разделе 13. Сохраняется полное множество eligible
runs, включая перекрытия; при нехватке поддержки — `INSUFFICIENT_RUN_SUPPORT`.

## 8. R10/R50 relative scores

Пусть `d_best=min(all eligible run distances)`. Квантили линейно интерполируются
в позиции `(n−1)×p`, как в предыдущем research harness:

- R10: `clip(1 − d_best / p10_distance, 0, 1)`;
- R50: `clip(1 − d_best / median_distance, 0, 1)`.

Если denominator≤`1e-12`, результат — `INSUFFICIENT_NONSELECTIVE_DISTRIBUTION`,
score=null. Epsilon закреплён до outcomes как численный, не forensic threshold.
Один положительный run даст score=0 против самого себя. Лучший из равных runs
выбирается первым в стабильном group/combinations traversal. Все значения конечны.

## 9. Frozen matrix

4 descriptors × 2 information policies × 3 K × 2 relative rules = **48**,
плюс два controls, всего **50 entries**. CONTROL_CURRENT_PRODUCTION сохраняет
исходные minima и normalizer. CONTROL_RAW_RELATIVE_R10 использует прежнюю
joint distance `max(color/440640,delta/660960)`, gap≥2 s, K1, I0 и R10:
это проверка вклада относительной шкалы без замены raw representation.
Controls не участвовали в выборе кандидата.


Матрица SHA-256: `465f8ce7555b7169e3b8357b7eece35a3f6902c9daa9edd5c75b2743c04e1fc1`.

Freeze до outcomes: `2026-10-15T10:07:12.150520+00:00` UTC. Точные правила, null semantics, ranking и gates находятся во внешнем
`research-matrix.json`; 50 entries не добавлялись и не исключались.


## 10. Observation results

Получены **1000 candidate/sample rows = 20 файлов × 50 entries**; пропусков и
insufficient нет. Для каждого из 50 entries paired positive=5/5 и repeat median=1.
Из redesigned candidates **41/48 OBS_READY_FOR_HOLDOUT**. Семь отказов относятся
к R50 и превышению доли benign≥0.75: D1/I0/K3,K5,K9; D1/I25/K3,K5;
D2/I25/K3; D4/I25/K3. Остальные gates у этих вариантов пройдены.

Все результаты ниже относятся только к observation. Колонка ≥0.75 имеет
denominator 10, paired positive — 5. Полные min/p25/median/p75/max, роли,
insufficient counts и source-family таблица сохранены в CSV/JSON.


| Candidate | Benign median | Benign ≥0.75 | Repeat median | Paired + | Median Δ | Obs ready |
| --- | --- | --- | --- | --- | --- | --- |
| D1__I0__K3__R10 | 0.134144 | 0 | 1.000000 | 5 | 0.880269 | YES |
| D1__I0__K3__R50 | 0.488697 | 3 | 1.000000 | 5 | 0.545007 | NO |
| D1__I0__K5__R10 | 0.125883 | 0 | 1.000000 | 5 | 0.893588 | YES |
| D1__I0__K5__R50 | 0.475967 | 3 | 1.000000 | 5 | 0.555053 | NO |
| D1__I0__K9__R10 | 0.097497 | 0 | 1.000000 | 5 | 0.905364 | YES |
| D1__I0__K9__R50 | 0.449026 | 3 | 1.000000 | 5 | 0.559574 | NO |
| D1__I25__K3__R10 | 0.157460 | 0 | 1.000000 | 5 | 0.902584 | YES |
| D1__I25__K3__R50 | 0.493016 | 3 | 1.000000 | 5 | 0.552542 | NO |
| D1__I25__K5__R10 | 0.128792 | 1 | 1.000000 | 5 | 0.854404 | YES |
| D1__I25__K5__R50 | 0.421608 | 3 | 1.000000 | 5 | 0.635631 | NO |
| D1__I25__K9__R10 | 0.044562 | 0 | 1.000000 | 5 | 0.958741 | YES |
| D1__I25__K9__R50 | 0.176481 | 1 | 1.000000 | 5 | 0.851668 | YES |
| D2__I0__K3__R10 | 0.092469 | 0 | 1.000000 | 5 | 0.908539 | YES |
| D2__I0__K3__R50 | 0.558816 | 2 | 1.000000 | 5 | 0.465637 | YES |
| D2__I0__K5__R10 | 0.080192 | 0 | 1.000000 | 5 | 0.916505 | YES |
| D2__I0__K5__R50 | 0.555199 | 2 | 1.000000 | 5 | 0.464924 | YES |
| D2__I0__K9__R10 | 0.060328 | 0 | 1.000000 | 5 | 0.937714 | YES |
| D2__I0__K9__R50 | 0.549955 | 2 | 1.000000 | 5 | 0.463456 | YES |
| D2__I25__K3__R10 | 0.110233 | 0 | 1.000000 | 5 | 0.921882 | YES |
| D2__I25__K3__R50 | 0.534560 | 3 | 1.000000 | 5 | 0.499409 | NO |
| D2__I25__K5__R10 | 0.089036 | 1 | 1.000000 | 5 | 0.898749 | YES |
| D2__I25__K5__R50 | 0.519751 | 2 | 1.000000 | 5 | 0.514068 | YES |
| D2__I25__K9__R10 | 0.037179 | 0 | 1.000000 | 5 | 0.971192 | YES |
| D2__I25__K9__R50 | 0.143591 | 1 | 1.000000 | 5 | 0.857278 | YES |
| D3__I0__K3__R10 | 0.211189 | 0 | 1.000000 | 5 | 0.804204 | YES |
| D3__I0__K3__R50 | 0.385483 | 1 | 1.000000 | 5 | 0.663561 | YES |
| D3__I0__K5__R10 | 0.180997 | 0 | 1.000000 | 5 | 0.824017 | YES |
| D3__I0__K5__R50 | 0.349455 | 1 | 1.000000 | 5 | 0.685403 | YES |
| D3__I0__K9__R10 | 0.160840 | 0 | 1.000000 | 5 | 0.837745 | YES |
| D3__I0__K9__R50 | 0.290413 | 1 | 1.000000 | 5 | 0.710580 | YES |
| D3__I25__K3__R10 | 0.186740 | 0 | 1.000000 | 5 | 0.812122 | YES |
| D3__I25__K3__R50 | 0.338512 | 0 | 1.000000 | 5 | 0.682243 | YES |
| D3__I25__K5__R10 | 0.136644 | 0 | 1.000000 | 5 | 0.872144 | YES |
| D3__I25__K5__R50 | 0.292723 | 0 | 1.000000 | 5 | 0.719757 | YES |
| D3__I25__K9__R10 | 0.058471 | 0 | 1.000000 | 5 | 0.960602 | YES |
| D3__I25__K9__R50 | 0.143466 | 0 | 1.000000 | 5 | 0.898673 | YES |
| D4__I0__K3__R10 | 0.100813 | 0 | 1.000000 | 5 | 0.907310 | YES |
| D4__I0__K3__R50 | 0.528758 | 2 | 1.000000 | 5 | 0.493524 | YES |
| D4__I0__K5__R10 | 0.084068 | 0 | 1.000000 | 5 | 0.918444 | YES |
| D4__I0__K5__R50 | 0.527445 | 2 | 1.000000 | 5 | 0.496918 | YES |
| D4__I0__K9__R10 | 0.068511 | 0 | 1.000000 | 5 | 0.925476 | YES |
| D4__I0__K9__R50 | 0.513157 | 2 | 1.000000 | 5 | 0.498831 | YES |
| D4__I25__K3__R10 | 0.098061 | 0 | 1.000000 | 5 | 0.916013 | YES |
| D4__I25__K3__R50 | 0.501617 | 3 | 1.000000 | 5 | 0.534467 | NO |
| D4__I25__K5__R10 | 0.113404 | 1 | 1.000000 | 5 | 0.875400 | YES |
| D4__I25__K5__R50 | 0.489948 | 2 | 1.000000 | 5 | 0.546936 | YES |
| D4__I25__K9__R10 | 0.040112 | 0 | 1.000000 | 5 | 0.960254 | YES |
| D4__I25__K9__R50 | 0.138429 | 1 | 1.000000 | 5 | 0.861968 | YES |
| CONTROL_CURRENT_PRODUCTION | 0.997052 | 10 | 1.000000 | 5 | 0.002894 | NO |
| CONTROL_RAW_RELATIVE_R10 | 0.181146 | 0 | 1.000000 | 5 | 0.824650 | YES |


CONTROL_RAW_RELATIVE_R10 уже снижает benign median до 0.181146 при paired
median Δ=0.824650; production даёт 0.997052 и 0.002894 соответственно.
Следовательно, относительная шкала сама вносит крупное улучшение на observation.
Этот control не открывался на holdout, поэтому его перенос и превосходство
отдельных компонентов redesign за пределами observation не доказаны.

Далее диапазоны **медиан по вариантам**, не объединённые независимые выборки.
Repeat median=1 и paired positive=5/5 для всех строк; insufficient rate=0/20
в каждом варианте. Разные variants используют те же пять семейств.


| Ось | Вариантов | Ready | Benign median: min…max | Paired median Δ: min…max |
| --- | --- | --- | --- | --- |
| descriptor=D1 | 12 | 7 | 0.044562…0.493016 | 0.545007…0.958741 |
| descriptor=D2 | 12 | 11 | 0.037179…0.558816 | 0.463456…0.971192 |
| descriptor=D3 | 12 | 12 | 0.058471…0.385483 | 0.663561…0.960602 |
| descriptor=D4 | 12 | 11 | 0.040112…0.528758 | 0.493524…0.960254 |
| information=I0 | 24 | 21 | 0.060328…0.558816 | 0.463456…0.937714 |
| information=I25 | 24 | 20 | 0.037179…0.534560 | 0.499409…0.971192 |
| k=3 | 16 | 12 | 0.092469…0.558816 | 0.465637…0.921882 |
| k=5 | 16 | 14 | 0.080192…0.555199 | 0.464924…0.918444 |
| k=9 | 16 | 15 | 0.037179…0.549955 | 0.463456…0.971192 |
| relative=R10 | 24 | 24 | 0.037179…0.211189 | 0.804204…0.971192 |
| relative=R50 | 24 | 17 | 0.138429…0.558816 | 0.463456…0.898673 |


Для контроля остальных координат — однофакторные сопоставления с выбранной
комбинацией. Это описательные сравнения, без статистической значимости.


| Candidate | Benign median | Paired median Δ | Benign ≥0.75 |
| --- | --- | --- | --- |
| D1__I25__K9__R10 | 0.044562 | 0.958741 | 0 |
| D2__I25__K9__R10 | 0.037179 | 0.971192 | 0 |
| D3__I25__K9__R10 | 0.058471 | 0.960602 | 0 |
| D4__I25__K9__R10 | 0.040112 | 0.960254 | 0 |
| D2__I0__K9__R10 | 0.060328 | 0.937714 | 0 |
| D2__I25__K3__R10 | 0.110233 | 0.921882 | 0 |
| D2__I25__K5__R10 | 0.089036 | 0.898749 | 1 |
| D2__I25__K9__R50 | 0.143591 | 0.857278 | 1 |


## 11. Candidate freeze

Ranking закреплён заранее: ready, число positive families, median Δ,
меньшая benign median, меньше benign≥0.75, больше repeat median,
простота D1→D4, более короткий K, lexical ID. При null median вариант идёт
после определённых значений. Measurable family здесь требует всех её benign
samples **и** обоих matched файлов; null не исключается ради readiness.
Положительный вклад как минимум двух семейств проверяется явно; при требовании
4/5 positive этот gate избыточен, но не заменён субъективным judgement.

Выбран **D2__I25__K9__R10**, observation_ready=true. Следующие ranks:
D3__I25__K9__R10, D4__I25__K9__R10, D1__I25__K9__R10, D2__I0__K9__R10.
Первые различаются по paired median Δ, а не по редакторскому выбору после holdout.
Независимый stdlib-перерасчёт подтвердил метрики и полный порядок всех 48 вариантов.


Freeze UTC: `2026-10-15T10:13:21.507812+00:00`.

`selected-candidate.json` SHA-256: `9f40e13656fbbb12122829c12b8eea37d341695210022cd22180d3409d1f7795`.

Holdout run начат `2026-10-15T10:14:29.641613+00:00` UTC; до этого
папка holdout была пуста. Файл выбора содержит полную формулу, параметры,
observation metrics, matrix/code/freeze fingerprints и больше не менялся.


## 12. Holdout results и readiness gates

После freeze оценены только выбранный кандидат и production control:
12 holdout-файлов × 2 = 24 rows. Все 3/3 семейства и 12/12 файлов измеримы;
paired positive=3/3. Нет re-ranking, изменения формулы или порогов после holdout.


| Split | Benign N | Min | p25 | Median | p75 | Max | ≥0.50 | ≥0.75 | Repeat median | Paired + | Median Δ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| observation | 10 | 0.007445 | 0.018063 | 0.037179 | 0.087839 | 0.686627 | 1 | 0 | 1.000000 | 5/5 | 0.971192 |
| holdout | 6 | 0.008368 | 0.022510 | 0.038587 | 0.051598 | 0.106914 | 0 | 0 | 1.000000 | 3/3 | 0.959875 |
| combined | 16 | 0.007445 | 0.016685 | 0.037240 | 0.067510 | 0.686627 | 1 | 0 | 1.000000 | 8/8 | 0.966883 |


Combined distributions не подменяют исходную границу выбора. Gate F/G использует
ровно 16 benign derivatives; gate D/E/H — восемь matched source-family пар.
Все 32 основных файла измеримы; source-family denominator остаётся 8.


| Gate | Требование | Факт | Итог |
| --- | --- | --- | --- |
| A | observation_ready=true | true | PASS |
| B | все holdout families measurable | 3/3 | PASS |
| C | все holdout repeat>reference | 3/3 | PASS |
| D | combined positive ≥7/8 | 8/8 | PASS |
| E | combined median Δ≥0.15 | 0.966883 | PASS |
| F | combined benign median≤0.50 | 0.037240 | PASS |
| G | benign≥0.75 ≤4/16 | 0/16 | PASS |
| H | repeat median≥0.70 | 1.000000 | PASS |
| I | finite + deterministic replay | все 1048 rows; replay совпал | PASS |
| J | production unchanged | source/config/lock fingerprints совпали | PASS |


Пороги gate — заданные владельцем engineering research criteria. Они не
переходят в production risk thresholds и не являются calibration. Disposition
зафиксирована до demo; его outcomes не использовались для повторного выбора.

Для выбранного кандидата роли показаны отдельно. В holdout BENIGN_CONFOUND нет.


| Split | Роль | Measurable / total | Families | Min | p25 | Median | p75 | Max | ≥0.50 | ≥0.75 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| O | BENIGN_CONFOUND | 2/2 | 2 | 0.036998 | 0.070281 | 0.103563 | 0.136846 | 0.170128 | 0 | 0 |
| O | BENIGN_PROCESSING | 3/3 | 3 | 0.013821 | 0.058762 | 0.103702 | 0.395165 | 0.686627 | 1 | 0 |
| O | BENIGN_REFERENCE | 5/5 | 5 | 0.007445 | 0.011350 | 0.030791 | 0.037359 | 0.040250 | 0 | 0 |
| O | reference | 5/5 | 5 | 0.009327 | 0.011350 | 0.028808 | 0.037426 | 0.039931 | 0 | 0 |
| O | repeat | 5/5 | 5 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 5 | 5 |
| H | BENIGN_PROCESSING | 3/3 | 3 | 0.017640 | 0.027380 | 0.037120 | 0.072017 | 0.106914 | 0 | 0 |
| H | BENIGN_REFERENCE | 3/3 | 3 | 0.008368 | 0.024211 | 0.040054 | 0.047750 | 0.055446 | 0 | 0 |
| H | reference | 3/3 | 3 | 0.008089 | 0.024107 | 0.040125 | 0.076251 | 0.112377 | 0 | 0 |
| H | repeat | 3/3 | 3 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 3 | 3 |
| Combined | BENIGN_CONFOUND | 2/2 | 2 | 0.036998 | 0.070281 | 0.103563 | 0.136846 | 0.170128 | 0 | 0 |
| Combined | BENIGN_PROCESSING | 6/6 | 6 | 0.013821 | 0.022510 | 0.070411 | 0.106111 | 0.686627 | 1 | 0 |
| Combined | BENIGN_REFERENCE | 8/8 | 8 | 0.007445 | 0.010605 | 0.034075 | 0.040103 | 0.055446 | 0 | 0 |
| Combined | reference | 8/8 | 8 | 0.008089 | 0.010845 | 0.033117 | 0.039980 | 0.112377 | 0 | 0 |
| Combined | repeat | 8/8 | 8 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 8 | 8 |


## 13. Matched distant-repeat results и локализация

В таблице по одной строке на lineage family. Benign R/P — обычные accepted
reference/processed; paired ref — дополнительное matched encoding PR #74.
Каждая paired delta считается только относительно собственного matched reference.


| Family | Split | Benign R | Benign P/C | Paired ref | Paired repeat | Δ |
| --- | --- | --- | --- | --- | --- | --- |
| video-01 | O | 0.011350 | 0.013821 | 0.011350 | 1.000000 | 0.988650 |
| video-02 | O | 0.030791 | 0.103702 | 0.028808 | 1.000000 | 0.971192 |
| video-03 | H | 0.040054 | 0.037120 | 0.040125 | 1.000000 | 0.959875 |
| video-04 | O | 0.037359 | 0.170128 | 0.037426 | 1.000000 | 0.962574 |
| video-05 | O | 0.040250 | 0.686627 | 0.039931 | 1.000000 | 0.960069 |
| video-06 | H | 0.055446 | 0.017640 | 0.112377 | 1.000000 | 0.887623 |
| video-07 | O | 0.007445 | 0.036998 | 0.009327 | 1.000000 | 0.990673 |
| video-08 | H | 0.008368 | 0.106914 | 0.008089 | 1.000000 | 0.991911 |


Combined paired Δ: min=0.887623, median=0.966883, max=0.991911; positive/zero/negative=8/0/0.


| Family | Best start A→B | Zero pairs /9 | d_best | p10 | Median distance | Runs | Весь run внутри копии |
| --- | --- | --- | --- | --- | --- | --- | --- |
| video-01 | 0:2 → 2:2 | 5 | 0.000000 | 1.210076 | 4.936312 | 441 | NO |
| video-02 | 0:12 → 2:12 | 9 | 0.000000 | 1.212928 | 2.871673 | 99 | YES |
| video-03 | 0:5 → 2:5 | 8 | 0.000000 | 36.472307 | 38.010139 | 153 | NO |
| video-04 | 0:3 → 2:3 | 6 | 0.000000 | 0.924271 | 2.498416 | 72 | NO |
| video-05 | 0:2 → 2:2 | 5 | 0.000000 | 0.282636 | 0.893695 | 336 | NO |
| video-06 | 0:5 → 2:5 | 8 | 0.000000 | 1.107098 | 4.267110 | 95 | NO |
| video-07 | 0:11 → 2:11 | 9 | 0.000000 | 1.259189 | 1.376426 | 48 | YES |
| video-08 | 0:7 → 2:7 | 9 | 0.000000 | 0.261090 | 16.539290 | 115 | YES |


Все best runs имеют истинный offset 10 s и пересекают известную копию, но
**только 3/8 полностью находятся внутри неё** (02/07/08). У остальных первый
stable minimum начинается раньше destination: у 01/05 лишь 5/9 constituent
distances нулевые, у 04 — 6/9, у 03/06 — 8/9. Например, у 01 расстояния
`[27.265209,20.472433,13.663498,6.837452,0,0,0,0,0]` дают median=0.
Поэтому score=1 не означает девять идеально совпадающих групп или точную
локализацию границ эпизода. Frozen median и tie-break соблюдены; новая
подгонка best-run selection не выполнялась. Все PTS, gap, энергии обеих
сторон и constituent distances сохранены в `selected-run-details.csv`.

## 14. Low-information/static behavior

На observation нет insufficient у любого из 50 entries. У выбранного кандидата
основные 32 файла также измеримы; в benign остаются 65/87 групп у reference
и 60/81 у processed. Это не свидетельство высокой абсолютной информативности.
У почти статичного `video-05-reference` p25 energy≈0.059676, у processed≈0.051719.
Тем не менее I25 оставляет группы и соответственно 105/79 runs.
Processed — наибольший benign score=0.686627 против reference=0.040250;
обычная обработка и собственное tail distribution заметно меняют результат.

Точный demo static даёт energy=0 у всех 39 valid groups, eligible_groups=0,
`INSUFFICIENT_LOW_INFORMATION`, score=null. Это ожидаемая граница применимости,
**не** доказательство подлинности. Превращение static в нулевой response не выполнялось.
Простого абсолютного near-static rejection данный gate не обеспечивает.

## 15. Demo diagnostics

После заморозки основной disposition выполнены 12 demo × 2 entries = 24 rows.
Только 3/12 redesigned scores измеримы; 8/12 `INSUFFICIENT_RUN_SUPPORT`,
1/12 `INSUFFICIENT_LOW_INFORMATION`. В таблице K=9/D2/I25/R10 для всех строк;
production score остаётся прежним. Пустая метрика обозначена null.


| sample_id | Production | Research score | State | Groups | Runs | d_best | p10 | Median distance | Energy p25 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| video-01-control | 0.995096 | null | INSUFFICIENT_RUN_SUPPORT | 29 | 0 | null | null | null | 0.283431 |
| video-01-cut | 0.995148 | null | INSUFFICIENT_RUN_SUPPORT | 29 | 0 | null | null | null | 0.285435 |
| video-01-distant | 1.000000 | null | INSUFFICIENT_RUN_SUPPORT | 29 | 0 | null | null | null | 0.287123 |
| video-01-freeze | 1.000000 | 0.010140 | MEASURED | 26 | 25 | 3.903359 | 3.943346 | 3.998733 | 0.000000 |
| video-02-control | 0.979548 | null | INSUFFICIENT_RUN_SUPPORT | 29 | 0 | null | null | null | 1.206576 |
| video-02-timing | 0.979389 | null | INSUFFICIENT_RUN_SUPPORT | 25 | 0 | null | null | null | 1.206506 |
| video-02-transition | 0.979548 | null | INSUFFICIENT_RUN_SUPPORT | 29 | 0 | null | null | null | 1.206576 |
| video-02-vfr | 0.979548 | null | INSUFFICIENT_RUN_SUPPORT | 27 | 0 | null | null | null | 1.204165 |
| video-03-control | 0.999610 | 0.004049 | MEASURED | 29 | 10 | 4.068441 | 4.084981 | 4.118821 | 0.526320 |
| video-03-loop | 1.000000 | null | INSUFFICIENT_RUN_SUPPORT | 27 | 0 | null | null | null | 0.514318 |
| video-03-repeat | 0.999610 | 0.004049 | MEASURED | 29 | 10 | 4.068441 | 4.084981 | 4.118821 | 0.526320 |
| video-03-static | 1.000000 | null | INSUFFICIENT_LOW_INFORMATION | 0 | 0 | null | null | null | 0.000000 |


Важное ограничение: **наблюдаемый `video-01-distant` и loop не получили
измерение**, хотя production видит соответствие. В обычных 8 fps окнах всего
16 кадров/13 стартов; I25 разрывает последовательности, нужные для K9.
Отсутствие runs здесь не равно отсутствию повторов и не улучшает recall.
Freeze остаётся измеримым со слабым research score≈0.010140, а не сильным
дальним повтором. `video-03-control` и ранее пропущенный `video-03-repeat`
совпадают: ≈0.004049. Исходный копируемый эпизод `[2,3) s` не наблюдается
в retained окнах `[0,2),[4,6),[8,10)`; redesigned policy не создаёт отсутствующие кадры.
Demo не используется для настройки K/I25, изменения ranking или обхода null.

## 16. Ограничения и ответы на RQ

- RQ1: D1–D4 дают полезное paired различение в observation. D2 выиграл frozen
  ranking, но control с прежним raw descriptor и R10 тоже существенно улучшился.
  Нельзя приписать весь выигрыш spatial representation или доказать необходимость
  каждого компонента. Raw-relative control не проверялся на holdout по заданию.
- RQ2: последовательные runs усилили выбранное сочетание в observation,
  но кадры групп перекрываются; median допускает несовпадающее меньшинство.
  K в кадрах зависит от cadence, а строгий I25 существенно снижает применимость
  на 8 fps demo. Нужны отдельные applicability/localization проверки прототипа.
- RQ3: относительная шкала убрала широкое saturation на данном benign наборе
  и сохранила exact-copy responses. Она зависит от tail population, длины файла,
  числа/перекрытия runs и других эпизодов. Низкий score не означает слабой
  абсолютной похожести; высокий не доказывает злонамеренный монтаж.
- RQ4: all-static стал явно insufficient. Почти статичный материал с вариативной
  малой энергией остаётся допустимым; p25 не является абсолютным motion threshold.
- RQ5: выбранный только на пяти observation-семействах кандидат прошёл три
  holdout-семейства без reselection. Эти данные ранее исследовались; нового
  полностью слепого корпуса нет. По ним не оцениваются FPR/TPR или significance.
- Всего восемь lineage families, удобная выборка, короткие стандартизованные
  derivatives одного источника поставки. Семьи не гарантируют статистическую
  независимость; benign R/P и matched ref/repeat зависимы.
- Positive probes — точная копия 18 кадров, заранее полностью наблюдаемая dense
  окнами. Не проверены частичные геометрические изменения, speed changes,
  near-copy, более короткие эпизоды и семантически похожий иной контент.
- 48-way selection на пяти семействах ограничивает переносимость; высокая
  paired разность не заменяет большую независимую проверку. Controls и похожие
  variants не дают дополнительные независимые sample counts.
- Cache replay проверяет детерминированную математику в зафиксированной среде;
  production reproduction отдельно проверяет decoder. Новая application-level
  E2E integration, hard RSS quota и cross-version codec portability не заявляются.

## 17. Final disposition

**VRC2_METHOD_CANDIDATE_READY_FOR_PROTOTYPE.** Все заранее заданные observation
и holdout prototype-readiness gates выполнены. Выбранный research candidate —
**D2__I25__K9__R10**. Combined benign median≈0.037240, benign≥0.75 — 0/16,
repeat median=1, positive paired deltas=8/8, median Δ≈0.966883.

Это готовность **к отдельному исследовательскому production prototype sprint**,
а не production-ready VRC, принятие нового forensic метода или расширение
scientific disposition. Существующий VRC остаётся EXPERIMENTAL_WEAK; ни weight,
normalizer, profile/version, family/capacity, threshold, schema, dependency или
ансамбль не менялись. Провалы применимости demo и неточная граница best run
сохранены как обязательные ограничения, а не исключены из отчёта.

## 18. Воспроизведение, проверки и следующий шаг

Внешний workspace — `FakeDetector-Work/vrc-redesign-research-sprint1`.
Команды выполняются из checkout с явными абсолютными внешними путями:

```powershell
uv run python -m scripts.diploma_vrc_redesign_research prepare --workspace $workspace --benign $benignWorkspace --demo $demoWorkspace --paired $pairedWorkspace
uv run python -m scripts.diploma_vrc_redesign_research observation --workspace $workspace
uv run python -m scripts.diploma_vrc_redesign_research holdout --workspace $workspace
uv run python -m scripts.diploma_vrc_redesign_research demo --workspace $workspace
```

Повтор полного эксперимента требует нового output workspace: frozen artifacts
создаются exclusive. Phase guards проверяют code/matrix/source/config/lock/env
fingerprints; изменение формулы после выбора отвергается. Все input hashes,
manifest bindings, baseline, QA, candidate freeze и phase artifacts сохранены.
Генерации новых media нет, grids/populations и временные decode artifacts находятся
вне репозитория; временные decode directories очищены.

1048 candidate/sample rows прошли точный повтор численного расчёта. Независимый
перерасчёт без project imports подтвердил populations, квантильные distances,
scores, support и phase order с допуском `1e-12` (1 068 952 run-distance checks,
с повторным использованием популяций R10/R50). Ranking всех 48 вариантов
независимо подтверждён до holdout. Никакой post-hoc remediation формулы не было.

Focused до внешнего прогона: **77 passed** (53 новых cases + 24 предыдущих).
Итоговый focused прогон четырёх research suites: **119 passed** за 59.76 s;
Ruff, format check и focused mypy PASS. Единственный `uv run poe check`:
pre-commit PASS, mypy src PASS; pytest — **3171 passed, 17 skipped, 1 failed**
за 249.64 s, coverage 91%. Единственный fail —
`test_sdist_wheel_metadata_entry_point_and_resources`: provenance guard отверг
intended untracked report. Read-only проверка всего фактического sdist подтвердила
236 tracked members с точными working-tree bytes, root PKG-INFO и ровно три
intended untracked-файла этого sprint; иных extra/missing/invalid/mismatched
members нет. Итог barrier — **OWNER_VERIFY_REQUIRED**. Guard не ослаблялся,
staging не выполнялся; после owner review/staging нужен повтор barrier владельцем.
CLI `uv run fakedetector --help` отдельно PASS; `git diff --check` PASS.
После barrier изменены только записи результатов проверок в отчёте и ROADMAP.
Это development verification, не strict certification из dirty tree.
Git mutations не выполнялись.

Review bundle: `DIPLOMA-vrc-redesign-research-sprint1`, с полным diff,
копиями четырёх изменённых файлов, обязательными CSV/JSON, freeze, raw research
rows, логами и SHA-256/size seal; крупные медиа не включены. Полный input inventory
позволяет восстановить путь к каждому accepted source. Graphify STALE,
source SHA `625b9e83…`, использован только для навигации, без пересборки.

Следующий шаг — owner review `PASS / REMEDIATE`. После приёмки отдельное задание
может разрешить прототип выбранной формулы с явными applicability/insufficiency
semantics и проверкой потери поддержки на низком fps. Изменение K/I25, selection
или локализации требует нового объявленного исследования; текущий holdout нельзя
использовать для такого повторного выбора. Ensemble calibration остаётся отдельным
gate. Audio transition сохраняется в ROADMAP для отдельного targeted sprint.
Stage 12 остаётся IN_PROGRESS; исходный VRC Stage B не разрешён этим отчётом.
