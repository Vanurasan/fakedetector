# M2-R2 — калибровочное исследование JPEG DQ/Grid

Дата: 2026-09-23. Baseline: `0fc37897aa67dbe08468d52ff9e9999b39301fad`,
ветка `feat/stage12-macro2-image-analyzer-expansion-wave1`; до работы дерево чистое.
Исследование выполнено по ограниченному measurement-only разрешению владельца,
записанному в `../METHODS.md`. M2-R1 принят как исследовательское свидетельство;
production-методы, findings и пороги не приняты.

## Вывод и границы

DQ-HIST-1 и GRID-PHASE-1: **CALIBRATION_NOT_READY**. Арифметика измерений
проверяется отдельно от криминалистической достоверности. Числовые production
пороги не предлагаются. Синтетические положительные примеры не закрывают
калибровку, а наблюдаемые challenge-ответы требуют проверки на реальном корпусе.
Недостаток доказательств пока не обосновывает окончательный `REJECT_METHOD`.

## Harness и воспроизводимость

Код расположен в `scripts/research/`: `jpeg_measurements.py` — чистая арифметика
и чтение DCT через `AnalyzerRequest.read_numeric`; `jpeg_corpus.py` — генератор;
`jpeg_calibration.py` — запуск, bounded diagnostics и агрегаты. Это отдельные
исследовательские dataclasses, а не production result models. Runtime package
не импортирует эти модули; wheel по существующему build profile содержит только
`src/fakedetector`. Исследовательские исходники входят в source distribution
по существующему правилу для `scripts/`, без runtime-активации.

Измерения используют `ImagePreprocessor` Macro 1, его manifest/provenance,
проверки selectors/геометрии, существующий native decoder, общий artifact budget,
реестр и cleanup. Входные descriptors создаются только для собственных
сгенерированных JPEG с проверенным SHA-256. Это не новый intake для произвольных
внешних файлов. Pillow decode/re-encode в генераторе служит построению известной
истории; measurement path JPEG повторно не декодирует и не разбирает.

Для Grid читается единственный normalized PNG через controlled access.
Обратная EXIF-перестановка восстанавливает native pixels без интерполяции.
Используются существующие `extract_image_tiles` / `to_luminance`, по одному
окну с halo=2; потенциально reflected край halo исключён из математической
опоры. Для исходного L берётся один равный RGB-канал. Межоконные значения
не суммируются как независимые свидетельства.

DQ: полные непаддированные блоки, девять AC modes лексикографически,
signed bins и ноль сохранены, Python integer min/max/range, dense allocation
только до R=65536, rFFT backward и меньший j при точном равенстве. R=1 даёт
null spectral diagnostics. q1 из измерений не оценивается; таблицы первого
сохранения в inventory — известные параметры генерации, не вывод детектора.

Grid: строгие максимумы без голосования при равенстве, неопределённая фаза при
tie, точные origins и Nt из METHODS. Полный binomial tail считается в log-space
через lgamma, recurrence и фиксированный `math.fsum`, без epsilon-cutoff.
`ell_x<0 AND ell_y<0` при уникальных фазах — только разрешённый research flag.
В JSON нет Inf/NaN, карт C или полных histogram/spectrum. Неприменимость малого
растра/неизвестного EXIF отделена от отсутствия голосов; resource rejection
не превращается в отрицательное наблюдение. Неожиданные ошибки останавливают
прогон; контролируемые resource-limit отказы записываются отдельно.

Команда из корня репозитория (каталог должен отсутствовать):

```powershell
uv run python -m scripts.research.jpeg_calibration --output C:\Users\Vanur\Desktop\m2-r2-calibration-final-2026-09-23
```

Корпус и машинные результаты находятся в этом внешнем каталоге:
`inventory.json`, `provenance.json`, `measurements.jsonl`, `dq.csv`,
`aggregate.json`, `rejections.json`, `output_sizes.json`, `corpus/`.
Provenance содержит версии Python/platform/NumPy/Pillow/pyjpegio и SHA-256
исследовательских модулей; inventory — параметры и SHA-256 каждого JPEG,
source-group, partition, фактические first/final DQT. Повторный запуск создаёт
новый каталог; runtime timings не являются детерминированными измерениями.
Первичный каталог `m2-r2-calibration-2026-09-23` — диагностический незавершённый
прогон; итоговые выводы и counts относятся только к `...-final-...`.

## Происхождение и дизайн корпуса

Все изображения созданы собственными NumPy/геометрическими генераторами.
Нет скачанных изображений, внешних fonts, реальных записей, моделей или новых
зависимостей. Текстоподобные glyphs рисуются линиями и прямоугольниками.
Методическое происхождение остаётся в `../REFERENCES.md`:
`JPEG-PF04`, `JPEG-LF03`, `JPEG-GRID20`, `JPEG-M2R1-PROPOSAL` и существующие
записи NumPy/Pillow/pyjpegio. Нового внешнего provenance нет; reference code
не копировался. Исследовательский код подчиняется корневому Apache-2.0.

Восемь исходных content groups: гладкие функции, PRNG noise, периодическая
шахматная текстура, текстоподобные glyphs, диагональные линии, saturation,
flat и sparse AC. Базовый размер 199×167; seeds 1200–1207. Все производные,
включая увеличенные коллажи и панорамы, сохраняют группу исходника. Размерные
noise-пробы seed 1300 имеют общую девятую группу; большой flat остаётся в
группе flat. Разбиение задано до измерений: lines/saturated — exploratory
holdout, остальные обычные группы — exploratory; размерные пробы отдельно.
Это проверка новых content families, не репрезентативный независимый real
holdout. Дублирующие JPEG/измерения при пересечении матриц допустимы и не
превращаются в независимые samples. Ни thresholds, ни classifier не обучаются.

Матрица генерации охватывает:

- single quality 20/40/75/90/95/100; lossless source crop (3,5) перед единственным
  quality-100 JPEG как отдельный отрицательный challenge;
- aligned 40→90, 90→40, 75→75, 74→75, 99→100; порядок quality не подменяет
  поэлементное сравнение DQT;
- custom constant tables 8→8, 8→9, 8→16; фактические таблицы сохраняются;
- все 64 `(dx,dy)` для smooth/periodic и обоих порядков 40→90 / 90→40;
- 4:4:4, 4:2:2, 4:2:0, baseline/progressive, исходный L и одинаковый L-as-RGB;
- три промежуточных сохранения, down/up resize, nearest/bicubic, sharpening;
- benign collage: правая половина из точно сдвинутого первого JPEG; одинаковая
  арифметика могла бы моделировать splice, намерение по пикселям не различается;
- малые patches внутри/на краю опоры; 1200×800 collage и 4096×256 panoramas
  для smooth/noise/periodic. Panorama patches: `[100,116)×[100,116)` внутри
  и `[600,616)×[100,116)` вне всех support окон, подтверждено тестом;
- EXIF 1–8 на некратных 8 размерах и invalid EXIF 9;
- 7×7, 8×8, 9×9, 66×67, 67×66, 67×67, 1024×67, 1536² и 2048².

Точные строки и DQT — в inventory. Trellis и альтернативные encoders не
воспроизводятся существующим Pillow-профилем; произвольный новый encoder
не подключался. CMYK/non-JPEG/malformed JPEG не являются калибровочной популяцией
этого генератора; существующие preprocessing tests остаются соответствующим
failure/applicability evidence, не статистикой качества нового метода.

## Арифметическая проверка

Focused suite `tests/test_jpeg_research.py` проверяет hand histogram
`[-2,-2,0,1]`, zero/empty bins, R=1, FFT ties, R=65536/65537, полный int32
диапазон, ideal signed requantization через независимый Fraction reference и
периодичность числа достижимых bins. Grid сравнивается с независимым scalar
loop и прямой Decimal-суммой binomial terms (60 decimal digits), включая
крайне малый tail; проверяется точная модельная NFA-граница ell=0.
Все 64 пары фаз, ties, постоянный C, minimum support, origins, EXIF 1–8,
исключение padded component blocks и реальный preprocessing/cleanup проверены.
Здесь не утверждается cross-platform certification: выполнена одна целевая
Windows/Python/NumPy среда.

## Результаты калибровочного прогона

Inventory: **541 JPEG, 9 source groups**; успешно измерены **540**
(492 уникальных JPEG SHA-256), отдельно зарегистрирован **1 resource rejection**.
Измеренные partitions: exploratory — 469 строк, holdout — 62, resource — 9.
Две holdout content groups слишком малы и специфичны для оценки generalization;
performance после подбора thresholds здесь вообще не вычисляется.

### DQ: наблюдаемость и перекрытие

14 274 component/mode записей: 6 890 с невырожденным спектром, 7 375 с R=1,
9 без полных блоков (7×7 grayscale). У 62 из 540 файлов все spectral diagnostics
null; это включает один файл без блоков. Histogram-limit отказов на корпусе нет;
максимальный R=1712. Геометрический N в базовом RGB 4:2:0 — 480 для первого
компонента и 120 для каждого меньшего компонента. Максимум N=65 536 на большом
flat не делает его AC-гистограмму информативной. Отсутствие спектра — не negative.

Ниже фиксирован **первый SOF component, mode (0,1), q2=2**, без выбора
«лучшего» mode. Обе версии каждого источника имеют N=480 и final quality=90.

| Источник | История | Доля пустых bins | FFT amplitude | cycles/bin |
|---|---|---:|---:|---:|
| smooth | single | 0 | 0.494426 | 0.015625 |
| smooth | aligned 40→90 | 0.701754 | 0.917979 | 0.140625 |
| noise | single | 0.288344 | 0.821794 | 0.00390625 |
| noise | aligned 40→90 | 0.521739 | 0.821540 | 0.00390625 |
| text | single | 0.979522 | 0.863359 | 0.44140625 |
| text | aligned 40→90 | 0.978417 | 0.957897 | 0.19140625 |
| sparse | single | 0.976744 | 0.999980 | 0.046875 |
| sparse | aligned 40→90 | 0.976303 | 0.999957 | 0.23828125 |

DQ в smooth aligned действительно наблюдает структуру, отличную от single.
Но noise почти не меняет максимум, text уже single имеет крайне разреженную
опору, sparse даёт amplitude почти 1 в обеих историях. Сдвиг smooth (3,5)
перед 40→90 снижает empty fraction до 0.056604, amplitude до 0.526821 и
возвращает peak к 0.015625; Grid при этом сохраняет только native (0,0).
Значит, исчезновение DQ-структуры не означает отсутствия повторного JPEG.

Для того же component/mode aggregate показывает пересечение диапазонов
single/recompressed amplitude при каждом совместно представленном q2:
q2=14 — `[0.482588,0.997559]`, q2=6 — `[0.477717,0.999503]`,
q2=2 — `[0.494426,0.999980]`, q2=1 — `[0.493667,0.999965]`.
Это описательное пересечение, не ROC, не specificity и не независимые samples.
Таблицы 75→75 совпадают; 99→100 эквивалентны на девяти выбранных modes.
Профиль сохраняет actual q2, поэтому подобные quality labels не объявляются
различимыми историями. Полные mode/component/q2/stratum distributions и counts
сохранены в `aggregate.json` и `dq.csv`; объединённого DQ-score нет.

### Grid: обычная сетка, конфликт и challenges

| Контролируемая группа | Файлов | Любой research flag | Ненулевая block-origin phase | Несколько разных flagged phases |
|---|---:|---:|---:|---:|
| Все single histories, включая support/invalid EXIF | 67 | 21 | 8 | 5 |
| Обычные single quality-варианты | 48 | 20 | 7 | 4 |
| Все recompressed histories | 473 | 334 | 144 | 21 |
| Aligned | 40 | 18 | 5 | 1 |
| Shift matrix | 256 | 217 | 103 | 12 |
| Large collage | 3 | 3 | 1 | 1 |
| Panorama patch внутри | 3 | 3 | 2 | 2 |
| Panorama patch вне опоры | 3 | 3 | 2 | 2 |

У 5 файлов нет минимального окна, у 2 unknown EXIF исключает применимость;
32 измеримых файла не имеют голосов ни в одном окне. Остальные 501 имеют
измерения с некоторой голосующей опорой; отсутствие двухосевого flag не означает
недостаток геометрической применимости и не подтверждает single history.

При smooth 40→90 все 64 shifts дали 50 файлов с каким-либо flag и только 2
с ненулевой phase; при 90→40 — 64 и 0. Для periodic соответствующие counts —
54/53 и 49/48. Это сильная content/final-compression зависимость; эти группы
содержат по одному исходнику, а не 64 независимых испытания чувствительности.
Subsampling также меняет diagnostics: у `format` групп 0/1/2 разные counts;
это не основание назначить им разные production thresholds.

В noise collage 1200×800 левые окна имеют (0,0), правые с x=686 — (3,5),
что согласуется с заданной перестановкой правой половины. Например,
centers `[686,1198)×[1,513)` дают ell_x≈−665.51, ell_y≈−298.10.
Эта локальная информация отличается от глобальной DQ-гистограммы, но сама
по себе не различает доброкачественный коллаж и злонамеренный splice.
На маленьких вставках эти результаты не дают гарантии обнаружения:
даже counts наборов phases у panorama inside/outside одинаковы.

**Контрпримеры для наивных positive rules.** Single text отмечается ненулевыми
фазами при всех шести quality; single lines — при quality=20. Lossless periodic
source, сначала cropped (3,5), затем единожды JPEG quality=100, имеет flagged
phases `(5,0)` и `(5,4)`; первый DQ-mode одновременно имеет amplitude=1 и
empty fraction≈0.994334. Предыдущего JPEG у него по конструкции нет.
Таким образом, совместный сильный ответ DQ/Grid также не устраняет content
false positives. 8 single-history ненулевых flags и 5 multi-phase случаев —
наблюдения на контролируемой матрице, **не population FPR**. Production false
positives/sensitivity пока не определены, поскольку production rule отсутствует.
Истинная recompression в benign repeated export не означает злой умысел.

### Корреляция

Smooth aligned 40→90 даёт структурированную DQ-гистограмму вместе с native Grid;
shift может ослабить DQ, сохранив текущую native grid. Periodic aligned имеет
R=1 в приведённом mode при наблюдаемой Grid; sparse имеет почти единичный FFT
peak без Grid flag. Large collage показывает дополнительную локальную фазу.
Single periodic challenge показывает совместный отклик вообще без prior JPEG.

`aggregate.json` хранит DQ-amplitude distributions условно по наличию shifted
Grid flag и описательную Pearson association отдельно по component/mode/q2.
Это не коэффициент независимости методов: производные и окна зависимы,
контент и размеры смешаны, DQ-детектор ещё не определён. Бинарный DQ flag для
таблицы co-occurrence не изобретался. Данных для разделения предлагаемой общей
группы `image_jpeg_compression_history` нет; **общая группа по-прежнему обоснована**.

## Ресурсные наблюдения

Среда: Windows, Python 3.12.10, NumPy 2.5.2, Pillow 12.3.0, pyjpegio 0.3.0.
Последовательный corpus run выполнен до запуска полного quality suite.
Сумма измеренных этапов для 540 успешных случаев — 176.90 s (без генерации,
сериализации, cleanup и rejected case). Медианы / максимумы:

| Этап | Медиана, s | Максимум, s |
|---|---:|---:|
| Macro 1 preprocessing | 0.29524 | 0.43665 |
| DQ | 0.01389 | 0.09423 |
| Grid, включая подготовку raster | 0.01009 | 0.97365 |

На 1536² grayscale noise: 36 864 полных блока, 9 437 184 numeric bytes,
preprocessing 0.43665 s, DQ 0.04394 s, Grid 0.97365 s. На 2048² flat:
65 536 блоков, 16 777 216 numeric bytes (Macro 1 ceiling), preprocessing
0.34808 s, DQ 0.01661 s, Grid 0.09758 s. Максимальный raster — `2^22` pixels;
16 окон до 512², последовательная обработка. Для 4096×256 windows остаются
пробелы покрытия; их наличие проверено patch-тестом.

`tracemalloc` включён для inputs ≥`2^20` pixels, после preprocessing; peak
включает Python/NumPy allocations чтения numeric и Grid/raster. Максимум —
25 204 076 bytes (24.04 MiB) на 2048² flat; на 1536² noise — 14 183 829 bytes.
Это **не native process RSS**: native decoder child, preprocessing allocations,
пиковая память генерации корпуса и concurrency не сертифицированы. Временные
массивы bounded: histogram максимум 65 536 bins, corpus максимум R=1712;
полный предел FFT проверен golden fixture. Grid хранит одно окно/halo/C/masks,
а не full-frame float64 maps. Признаков неограниченного роста этих intermediates нет.

Дополнительно выполнены отдельные fresh-process Windows RSS probes, включая
parent preprocessing. Проверяемый скрипт и JSON находятся рядом с результатами:
`windows_rss_probe.py`, `windows_rss_results.json`. Из корня проекта:

```powershell
uv run python C:\Users\Vanur\Desktop\m2-r2-calibration-final-2026-09-23\windows_rss_probe.py support-1536x1536-noise
uv run python C:\Users\Vanur\Desktop\m2-r2-calibration-final-2026-09-23\windows_rss_probe.py support-2048x2048-flat
uv run python C:\Users\Vanur\Desktop\m2-r2-calibration-final-2026-09-23\windows_rss_probe.py support-2048x2048-noise
```

`GetProcessMemoryInfo` показал parent peak working set 86 585 344 bytes для
1536² noise, 96 886 784 bytes для 2048² flat и 86 593 536 bytes для rejected
2048² noise; initial working set около 52 MB. Это общий parent process с
Python/imports/preprocessing, не 32 MiB numeric workspace. Decoder child и
совместный RSS при configured concurrency по-прежнему не охвачены. Повторные
resource probes не добавляются к corpus counts и не становятся новыми samples.

2048² noise отклонён с `resource_limit / jpeg_artifact_preflight`: normalized
RGB PNG плюс 16 MiB coefficients не помещаются в существующий общий 20 MiB
artifact budget. Это ожидаемое действие safety boundary, не benign verdict и
не defect production. Budget не увеличен. Для research case установлен более
узкий 60 s deadline; существующий native operation timeout сохраняется.

Максимум сериализованных DQ/Grid diagnostics одного файла — 22 079 bytes,
полной research case строки с inventory/timings — 23 823 bytes; это меньше
65 536-byte worker response ceiling, хотя harness не отправляет worker result.
Размеры внешних файлов: measurements.jsonl — 10 000 034 bytes, dq.csv —
1 713 489, aggregate.json — 6 096 049, inventory.json — 2 053 597,
provenance.json — 969, rejections.json — 1 731. Общий размер этих шести файлов —
19 865 869 bytes; общий корпусный aggregate не является production artifact.
Такая сумма повторяет bounded строки/strata по числу cases и не означает
раздувания одного аналитического ответа. Resource rejection и непроверенный
native RSS/concurrency сохраняются в production-resource gate.

## Решения по порогам класса C

| Нерешённый порог METHODS | Решение | Почему |
|---|---|---|
| DQ minimum blocks | INSUFFICIENT_EVIDENCE | N=1 измерим, но empirical reliability по content/component/q2 не установлена |
| DQ minimum nonzero observations | INSUFFICIENT_EVIDENCE | Flat/sparse и сильное квантование дают вырожденную или нестабильную опору |
| DQ periodicity | INSUFFICIENT_EVIDENCE | Спектральный максимум есть и у single; нет калиброванной null population |
| DQ empty-bin density | INSUFFICIENT_EVIDENCE | Sparse/структурный контент даёт gaps без предыдущего JPEG |
| DQ agreement across modes | INSUFFICIENT_EVIDENCE | Modes и компоненты зависимы; pooling/голосование не откалиброваны |
| Grid число несовместимых фаз | INSUFFICIENT_EVIDENCE | Несколько фаз наблюдаются и у single structured content |
| Grid число окон | INSUFFICIENT_EVIDENCE | Перекрывающиеся окна не являются независимыми наблюдениями |
| Grid spatial persistence | INSUFFICIENT_EVIDENCE | Покрытие и размер patch меняют наблюдаемость; нет real validation |
| Grid practical NFA boundary | INSUFFICIENT_EVIDENCE | Plug-in p и зависимые texture votes не дают population FPR |
| Grid minimum statistical support | INSUFFICIENT_EVIDENCE | 64×64 — геометрический минимум, не доказанный минимум достоверности |

Near-boundary численная устойчивость — отдельная проверка вычислений, а не
новый forensic threshold. Severity/confidence/semantics также не назначаются.
Ни одна строка не получает `PROPOSE_THRESHOLD`; окончательный `REJECT_SIGNAL`
для самих измерений не обоснован. Наивные правила «FFT peak означает историю»
и «несколько фаз сами по себе означают неоднородную JPEG-историю» не поддержаны.

## Реальный корпус и owner gates

Подходящий независимый реальный корпус с подтверждёнными правами и known
processing history в проектном реестре не установлен. Этот прогон его не
создаёт. Нужны фотографии нескольких devices/encoders, документы/графика,
periodic structures, benign workflows, source-group-separated calibration и
нетронутый holdout; покрытие DQT/order/subsampling/размеров/контента и provenance
каждой записи. Неизвестная история снимка не может считаться ground truth single.

Владелец задаёт целевую область применения и допустимый operating FPR до
подбора порога. При нуле ошибок на независимых negative source groups и уровне
доверия `1-alpha` односторонняя граница равна `1-alpha^(1/n)`; необходимый n
для заданного FPR f — `ceil(log(alpha)/log(1-f))`. Здесь f не выбирается.
Ненулевые ошибки требуют соответствующего binomial interval; counts блоков,
окон и производных JPEG не заменяют число независимых источников.

Открыты DQ-G1–G4 / GRID-G1–G4 в их production-смысле. Owner review должен
рассмотреть исходники harness, полные новые файлы и машинные результаты,
согласовать реальный корпус/operating target, затем отдельно принять полные
методы, semantic/severity rules и production scope. M2-A остаётся **BLOCKED**.
Общая предлагаемая группа `image_jpeg_compression_history` сохраняется;
изменений assessment engine нет. Self-report не является owner acceptance.

## Quality checks и owner review

- `uv run pytest --no-cov -q tests/test_jpeg_research.py` — **89 passed**.
- `uv run ruff check .` — **PASS**, включая новые untracked Python-файлы.
- `uv run mypy src scripts/research` — **PASS**, 69 source files.
- `uv run poe check`: pre-commit (включая uv-lock) и `mypy src` — PASS;
  полный pytest — **2611 passed, 17 skipped, 1 failed**, 117.93 s.
- Единственный failure:
  `test_sdist_wheel_metadata_entry_point_and_resources` отклоняет
  `docs/research/2026-09-23-jpeg-dq-grid-calibration.md` как untracked sdist
  member. Остальные новые исходники также требуют tracked provenance.
  Проверка и build policy сохранены. Это **OWNER_VERIFY_REQUIRED** после
  review/Git-действий владельца; агент не выполняет staging/commit и не может
  объявить полный quality barrier зелёным. Это не `BLOCKED` исследования.
- Sequence не дошла до smoke из-за failure; `uv run poe smoke` отдельно — PASS.
- `git diff --check`, просмотр фактического diff и итогового status выполнены.
  Production-код, каталог, публичные контракты, dependencies/config/schema,
  Graphify, REFERENCES и CHANGELOG не менялись. Strict certification не проводилась.

Изменены `docs/METHODS.md`, `docs/ROADMAP.md`; новые файлы — этот отчёт,
`scripts/research/__init__.py`, `jpeg_measurements.py`, `jpeg_corpus.py`,
`jpeg_calibration.py`, `tests/test_jpeg_research.py`. Все изменения unstaged;
Git mutations отсутствуют. Полный review bundle с фактическим diff, полными
копиями всех восьми файлов и SHA-256 manifest сохранён вне репозитория:
`C:\Users\Vanur\Desktop\m2-r2-owner-review-2026-09-23`.
Он включает все шесть intended untracked entries, которые обычный `git diff`
не показывает. Корпус и машинные результаты остаются в отдельном внешнем
каталоге, указанном выше.
