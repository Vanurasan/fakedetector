# M2-R3B — ограниченный пилот реального корпуса

Дата: 2026-09-24. Baseline: `d3a64be2ae6a0b4e77202266e23ecdedd7b0ac5d`,
ветка `feat/stage12-macro2-image-analyzer-expansion-wave1`.
**M2-R3B: OWNER_ACCEPTED — pilot evidence и research implementation приняты владельцем.**
Продолжение использует явное разрешение владельца на внешний binary rawpy.
M2-R3A принят владельцем. Operating profile — `BALANCED_TRIAGE`, target
image-level FPR ≤1% — цель будущей калибровки, не production threshold.
DQ-HIST-1: сигнал достаточен для FINAL_CALIBRATION, production acceptance и порога нет.
GRID-PHASE-1: WEAK_SIGNAL, `RESEARCH_ONLY_NOT_READY / DEFERRED`, вне текущего
Stage 12 primary holdout; исследовательское направление не отвергнуто навсегда.
Приёмка владельцем пилота не закрывает Macro 2 / Stage 12; M2-A — BLOCKED.
Основания: [R3A](2026-09-24-jpeg-real-corpus-operating-point-design.md),
[METHODS](../METHODS.md), [datasets](../REFERENCES.md#m2-r3a-datasets),
[RAW tool](../REFERENCES.md#research-rawpy-m2r3b), [политика исследований](README.md).

## Acquisition и точные counts

Внешний workspace `fakedetector-m2-r3b-pilot-2026-09-24` содержит все медиа,
снимки условий, manifests с локальными путями, contact sheets, инструменты
воспроизведения и machine results. В Git — только код, тесты и документация.
`selection.json` и `acquisition.jsonl` сохраняют record/URL, дату получения,
license URL, формат, source identity, metadata и SHA-256. Seed `12032026`,
четыре загрузчика, download ceiling 60 MiB/file. Пределы 200 RAW / 100 VISION
source groups соблюдены; после продолжения новых исходников не скачивали.

| Стадия raw.pixls | Групп/файлов | Значение |
|---|---:|---|
| Выбрано и скачано | 120 | По одной записи на make/model |
| Per-record CC0 и download/hash QA пройдены | 120 | Acquisition admission |
| Успешно проявлено | 107 | Фиксированный профиль AHD |
| Отказ проявки | 13 | `unsupported_fixed_AHD_CFA` |
| Исключено после visual/content QA | 10 | 9 цветовых мишеней, 1 репродукция картины |
| Допущено bounded lossless masters | 97 | Measurement admission |
| Группы с созданными и измеренными JPEG | 97 | 237 JPEG, 0 preprocessing refusals |

120 rights-approved означает подтверждённую CC0-лицензию самой записи;
не означает автоматического разрешения прав на все изображённые объекты.
Одна фотография доминирующей репродукции исключена из-за неясных прав на
произведение. Девять кадров мишеней исключены из primary content scope.
Терминология исправляет прежнее смешение acquisition admission с ожидавшей
проявки measurement admission. Yield: 107/120 = 89,17% developed;
97/120 = 80,83% admitted; после успешной проявки 97/107 = 90,65%.

| Стадия VISION | Групп | Файлов |
|---|---:|---:|
| Выбрано/скачано, dataset rights подтверждены | 50 | 150 |
| Visual QA исключения | 7 | 21 |
| После QA, safe intake пройден | 43 | 129 |
| Native: после QA / измерено | 43 / 0 | 43 / 0 |
| Social: после QA / измерено | 43 / 43 | 86 / 55 |
| Есть хотя бы один preprocessing resource refusal | 43 | 74 |
| Есть social resource refusal | 31 | 31 |
| Полностью потеряно из-за resource refusal | 0 | — |
| Есть хотя бы один измеримый JPEG | 43 | 55 |

Таким образом, **140 измеримых source groups = 97 RAW + 43 VISION**;
**292 измеренных JPEG = 237 controlled + 55 social**. 170 выбранных families
не являются знаменателем измерений. VISION не входит в primary FPR denominator.

Downloaded bytes: RAW 2 687 533 529, VISION 161 115 457; общий download wall
285,93 s. Ошибок загрузки, RAW publisher-hash mismatch и exact-byte дублей — 0.
Для VISION publisher hashes отсутствуют: сохранены собственные SHA-256.
Снимок raw.pixls catalog SHA-256:
`8dc5f5c74e20cc3a38f4548d53bba4bb516835e2a859e80bf86e7ac6283b3aa3`;
VISION README: `22896dffbc6448e96102c4bb5d15b061efd10c9aa776766d1b48ac9fec515c45`.

Из 2016 RAW catalog records последовательные фильтры исключили 146 non-CC0,
780 вне выбранных форматов, 201 неоднозначных/потенциально lossy modes,
102 по плановому размеру >50 MB. 787 оставшихся записей представляют только
444 уникальные casefold make/model пары. Выбор 120 использовал перемешивание
и обход производителей; остаётся 324 таких пары, а не 667 независимых моделей.
Форматы: CR2, MRW, NEF, ORF, PEF, RAF, RW2, RWL, SRW. Среди 97 masters:
Canon 13, Nikon 12, Pentax 12, Samsung 12, Olympus 11, Panasonic 11,
Leica 10, Minolta 7, OM System 6, Fujifilm 3. Make/model не доказывает
разные физические устройства, независимость сцен или pristine history.

VISION attribution: CSP Lab, University of Florence, 2017; Shullani, Fontani,
Iuliani, Al Shaya, Piva, *VISION: a video and image dataset for source
identification*, DOI `10.1186/s13635-017-0067-2`. Фотографии — CC BY-SA 4.0;
условия статьи отдельные. Native/FBH/WA одного original остаются одной family.
Выбрано по пять originals для D01 Samsung Galaxy S3 Mini, D04 LG D290,
D08 Samsung Galaxy Tab 3, D11 Samsung Galaxy S3, D15 Apple iPhone 6,
D19 Apple iPhone 6 Plus, D23 Asus Zenfone 2 Laser, D27 Samsung Galaxy S5,
D31 Samsung Galaxy S4 Mini, D35 Samsung Galaxy Tab A — 10 устройств, 4 бренда.

## QA, группировка и ограничения покрытия

Для RAW проверены SHA исходников и PNG masters; exact duplicates — 0.
Bounded near-duplicate QA: dHash64 distance ≤8 либо корреляция grayscale32×32
≥0,97, затем ручной просмотр всех 107 проявленных кадров на четырёх contact
sheets. Единственная dHash-пара (луна/стена, distance 5, correlation 0,014)
оказалась ложным совпадением и сохранена. Десять content/rights исключений
зафиксированы до measurement в `raw-visual-review.json`.
Для VISION dHash ≤8 дал 0 пар; ручной просмотр нашёл семь сходных сцен с
разными ракурсами. Они исключены со всеми версиями; ledger —
`vision-visual-review.json`. Это демонстрирует ограниченность dHash,
а не доказывает исчерпывающую дедупликацию остальных сцен.

Содержание: природа/растения, город/интерьеры, поверхности и предметы;
RAW также включает ночные сцены и текстиль. Квоты содержания не задавались,
репрезентативность современной популяции камер и low-light не доказана.
Все derivatives source family имеют одну partition; весь пилот навсегда
exploration/external stress. Предварительные прогоны не суммируются с итоговыми.

| VISION workflow | Назначено | QA исключено | После QA | Resource refusal | Измерено |
|---|---:|---:|---:|---:|---:|
| Native | 50 | 7 | 43 | 43 | 0 |
| Facebook high-quality | 50 | 7 | 43 | 31 | 12 |
| WhatsApp | 50 | 7 | 43 | 0 | 43 |
| Всего | 150 | 21 | 129 | 74 | 55 |

Все 74 отказа — `preprocessing/resource_limit/jpeg_preflight` существующего
preflight, включая суммарные padded coefficients. Native не уменьшались
для обхода лимита. Coverage 55/129 = 42,64% после QA, 55/150 = 36,67% всех
назначенных файлов. Это существенное ограничение native workflow support.

## Детерминированная RAW-проявка

Изолированные venv, wheel/cache находятся вне репозитория. Установлен только
официальный binary wheel `rawpy-0.27.1-cp312-cp312-win_amd64.whl`, 921 403 bytes,
SHA-256 `e9d9c83cd0422e84b2052a02eb9d612839ac68dfae4d6d3751740e08024599b1`,
сверенный с PyPI JSON. rawpy 0.27.1 (MIT), LibRaw 0.22.1 (поставляемая
LICENSE.LibRaw — LGPL 2.1); GPL2/GPL3 demosaic packs отключены.
Python 3.12.10, MSC v.1943 AMD64, Windows-11-10.0.26200-SP0;
NumPy 2.5.2, Pillow 12.3.0. Снимки PyPI/лицензий и wheel license hashes
сохранены; [REFERENCES](../REFERENCES.md#research-rawpy-m2r3b) владеет provenance.
Исходники конвертера не собирались. rawpy не установлен в project environment
и не добавлен в зависимости/metadata/release продукта.

`develop_raw.py` запускает отдельный worker на файл: 120 s timeout,
60 000 000 sensor pixels ceiling, `OMP_NUM_THREADS=1`. Только Flat RAW с
2×2 Bayer CFA; другой CFA отклоняется без смены алгоритма/подстановки preview.
Полный фиксированный rawpy postprocess профиль:

```text
demosaic_algorithm=AHD; half_size=False; four_color_rgb=False
dcb_iterations=0; dcb_enhance=False; fbdd_noise_reduction=Off
noise_thr=0.0; median_filter_passes=0
use_camera_wb=False; use_auto_wb=False; user_wb=None
output_color=sRGB; output_bps=8; user_flip=0
user_black=None; user_cblack=None; user_sat=None
no_auto_bright=True; auto_bright_thr=0.01; adjust_maximum_thr=0.75; bright=1.0
highlight_mode=Clip; exp_shift=1.0; exp_preserve_highlights=0.0
no_auto_scale=False; gamma=(2.222,4.5)
chromatic_aberration=(1.0,1.0); bad_pixels_path=None
```

Daylight WB, встроенные camera matrices/black-white metadata LibRaw; custom
ICC/profile, sharpening, embedded JPEG и дополнительный denoise не используются.
Цветовые primaries — sRGB, gamma curve — BT.709, не sRGB transfer function.
Профиль не меняется под отдельную камеру. Full RGB8 buffer dimensions/hash
сохраняются в ledger. Затем `scale=min(1,1280/max_side,sqrt(1000000/area))`,
размеры округляются вниз; Lanczos, без upscale. Bounded RGB8 PNG с
`compress_level=6,optimize=False`, без исходных metadata, становится master.
PNG lossless относительно этого RGB8 raster; 8-bit development/resampling
не объявляются lossless относительно sensor data. Полноразмерные TIFF/PNG
копии не сохраняются. Master SHA, полный профиль и script hash записаны в
`raw-development.jsonl` / `raw-development-provenance.json`.

При первоначальной настройке gamma был передан списком вместо требуемого tuple;
скрипт исправлен и весь development повторён. Этот служебный сбой не включён
в dataset rejections. Итоговые 13 отказов — только неподходящий CFA.
Повторная проявка пяти исходников дала **5/5 совпадений full RGB и PNG hashes**.
Cross-platform bit identity этим не установлена.

## Controlled derivatives и harness

97 masters дали 237 JPEG: по одному single каждому; первые 20 QA-admitted
в заранее заданном acquisition order получили ещё семь вариантов. Single
quality `(40,75,95)[ordinal%3]`, subsampling `(ordinal//3)%3` (4:4:4, 4:2:2,
4:2:0), progressive при `ordinal%5==0`; 48 progressive, 189 baseline.

| История | JPEG | Transform |
|---|---:|---|
| single | 97 | master → q40/75/95 |
| single90 | 20 | master → q90, парный baseline |
| aligned | 20 | q40 → q90 |
| same_dqt | 20 | q75 → q75 |
| repeat | 20 | q40 → q60 → q80 → q90 |
| shift | 20 | q40 → crop(3,5) → q90 |
| resize | 20 | q40 → bicubic scale0,75 → q90 |
| phase_patch | 20 | q40 → offset(3,5) с wrap, правая половина patch → q90 |

phase_patch — известная локальная неоднородность для проверки Grid; wrap seam
и граница patch — confounders, не модель реальной malicious manipulation.
Generator сохраняет ordered chain, parent/output hashes, geometry, JPEG
settings и DQT. Все 237 derivatives уникальны по bytes и прошли measurement.

`jpeg_calibration.measure` теперь использует существующие controlled ingestion,
`FileValidator`, затем Macro 1 preprocessing/numeric access и прежние Grid
kernels. Проверяются bytes/hash, реальный JPEG, размеры/mode; cleanup включает
intake failures. Формулы R2 не изменялись. Неизвестные native quality/sampling
остаются `None`. `jpeg_pilot` проверяет bounded external manifest, права,
source/master/terms hashes, partitions/group identity и явные QA rejections.
Обработка по одному файлу, SQLite transaction на record, resume связан с
manifest/config/code/package fingerprints и повторной проверкой input hashes.
Дубли не увеличивают counts; коллекции всех raster/Measurement не накапливаются.
Потоковые count/min/max/mean/variance и 20 фиксированных amplitude bins
сохраняются по component/mode/q2 и workflow/device/quality; это не thresholds.
Лимиты manifest: 200 RAW / 100 VISION групп, 500 sources, 1000 records, 16 MiB.

CLI: `uv run python -m scripts.research.jpeg_pilot --manifest <external-json>
--output <external-directory>`. RAW development выполняется отдельно внешним
Python; production RAW intake, Findings, API/config/result schema, каталог,
risk/completeness и resource ceilings не изменены.

## Exploratory DQ и Grid

RAW: 6399 component/mode histograms = 6290 measured + 109 constant.
VISION: 1485 = 1482 measured + 3 constant. Constant не считается нулевым
сигналом. Далее иллюстрация component ID 1, mode (0,1), без утверждения
семантики канала. Значения округлены; полные записи находятся в SQLite.

| RAW история | n | Amplitude min / median / max | Empty fraction median |
|---|---:|---|---:|
| single | 97 | 0,86937 / 0,97268 / 0,99836 | 0,23926 |
| single90 | 20 | 0,93406 / 0,96729 / 0,99897 | 0,34969 |
| aligned | 20 | 0,94388 / 0,98703 / 0,99899 | 0,72402 |
| same_dqt | 20 | 0,90860 / 0,98049 / 0,99836 | 0,20692 |
| repeat | 20 | 0,94455 / 0,98045 / 0,99901 | 0,66148 |
| shift | 20 | 0,93433 / 0,96004 / 0,99894 | 0,27968 |
| resize | 20 | 0,92898 / 0,96125 / 0,99840 | 0,37702 |
| phase_patch | 20 | 0,94154 / 0,96477 / 0,99899 | 0,40003 |

Парный aligned минус single90: empty fraction выросла в 19/20 групп,
median delta 0,32240, range −0,00452…0,49275. Amplitude выросла в 13/20,
median delta всего 0,000272, range −0,000240…0,049341. Для семи same-DQT
пар с исходным single75 median amplitude delta 0,00000386, empty delta 0.
Повторный benign export тоже даёт высокий empty fraction; same-DQT слаб.
**DQ_PILOT_RESULT: USEFUL_SIGNAL** — узкий вывод о полезном контролируемом
отклике histogram, не о готовом классификаторе. Распределения перекрываются;
amplitude сама по себе не определяет двойное сжатие, q1 или манипуляцию.

| RAW история | n | Любой Grid flag | Shifted flag | Multiple phases |
|---|---:|---:|---:|---:|
| single | 97 | 95 | 0 | 0 |
| single90 / aligned / same_dqt / repeat (каждая) | 20 | 20 | 0 | 0 |
| shift | 20 | 19 | 9 | 8 |
| resize | 20 | 19 | 0 | 0 |
| phase_patch | 20 | 20 | 9 | 9 |

**GRID_PILOT_RESULT: WEAK_SIGNAL.** Multiple phases есть у 9/20 локальных
patches и у 8/20 benign global crop/recompress; восемь source groups совпадают.
Обычная единая JPEG-решётка не является finding. Post-hoc content разбиение
20 пар: natural10 (shift/patch multiple 6/6), built9 (2/3), textile1 (0/0).
Это малые описательные страты, не причинная оценка содержания.
Для 17 RAW файлов с multiple phases amplitude указанного mode:
0,94410 / 0,95317 / 0,98823; для остальных 220: 0,86937 / 0,97489 / 0,99901.
Перекрытие не позволяет считать методы независимыми или усиливать уверенность
простым объединением flags. Single quality×sampling имеет 9 сочетаний по
10–11 групп; q2 для q40/75/95 равно 14/6/1. Median amplitude по этим стратам
около 0,96663–0,98376 при широком перекрытии. Один source на model и неодинаковый
контент не позволяют отделить camera effect от quality/content.

VISION WA43: amplitude 0,90056 / 0,97690 / 0,99324, q2=2;
FBH12: 0,94958 / 0,98020 / 0,99560, q2=6–10; 9216–19200 полных blocks.
Any Grid flag 41/43 WA и 12/12 FBH; shifted/multiple — 0.
Content/device/workflow/q2 смешаны; native measurements отсутствуют.
VISION labels не доказывают malicious manipulation. Ни sensitivity, ни
population FPR по этому пилоту не оцениваются; decision rules не созданы.

## Ресурсы и воспроизводимость

| Измерение | RAW | VISION |
|---|---:|---:|
| Development wall | 209,41 s | неприменимо |
| Derivative generation wall | 7,46 s | готовые dataset versions |
| Итоговый measurement wall | 155,19 s | 77,94 s |
| Сумма preprocessing / DQ / Grid | 101,52 / 5,28 / 39,07 s | 26,79 / 1,38 / 43,86 s |
| Peak parent RSS measurement | 124 489 728 bytes | 126 963 712 bytes |
| Maximum measured pixels | 1 000 000 | 2 359 296 (2048×1152) |
| Maximum numeric bytes | 12 138 240 | 14 155 776 |
| Итоговые SQLite + summary + provenance | 7 954 915 bytes | 1 942 607 bytes |

Parent RSS включает run/resume/пять повторов, исключает child processes;
Windows GetProcessMemoryInfo. Отдельно development single-worker peak RSS
686 022 656 bytes, максимальное elapsed 4,72 s/file. Это наблюдения этой
сессии, не гарантии памяти/производительности других камер и платформ.
107 masters: 166 764 563 bytes; 97 admitted masters: 154 037 404 bytes;
237 generated JPEG: 46 240 070 bytes. Внешний workspace при замере занимал
3 208 501 644 bytes, включая env/cache, snapshots и предварительные артефакты;
поздние логи могут увеличить размер. Ненужные full-size raster копии отсутствуют.

Resume сохранил summary без double-count: RAW 237 terminal records,
VISION 150 (21 QA + 74 resource + 55 measured). Пять повторов измерений
в каждом наборе: 5/5 точных совпадений DQ/Grid; RAW development отдельно 5/5.
Первоначальный VISION comparator tuples-vs-JSON-lists исправлен вне проекта.
Итоговый VISION прогон сохранён из первой части работы с его исходным
fingerprint; последующая смена generator для phase_patch/sampling не меняла
measurement kernels/intake. Его fingerprint не объявляется текущим полным
code fingerprint. RAW прогон связан с итоговым research code.

Основные свидетельства: `raw-development-provenance.json`,
`raw-development.jsonl`, `raw-development-repeat.json`, `raw-admission-ledger.json`,
`raw-manifest.json`, `raw-results/`, `raw-resource.json`,
`vision-reviewed-manifest.json`, `vision-final-results/`, `vision-final-resource.json`,
`pilot-descriptive-analysis.json`. External scripts и snapshots сохраняются
для локального воспроизведения; материалы с paths/metadata не входят в Git.

## Зафиксированные владельцем размеры корпуса и DQ-only holdout

Владелец зафиксировал целевые размеры следующей фазы и **PRIMARY_HOLDOUT_METHOD: DQ**,
**PRIMARY_HOLDOUT_SIZE: 500**. Канонический статус решения — в [ROADMAP](../ROADMAP.md).
Acquisition ещё не выполнен; его состав и source/device/content quotas требуют
execution planning до final holdout. Freeze counts не означает freeze этих квот.

| Часть | Eligible source groups | Использование пилота |
|---|---:|---|
| Exploration/calibration | 200 | 97 RAW пилота + 103 новых |
| Validation | 100 | Только новые группы |
| Untouched primary holdout | 500 | Только новые, никогда не исследованные группы |
| VISION external stress | 100 | 43 пилотных exploration + 57 новых stress |
| Необязательные challenges | 50 | Отдельные группы, вне primary denominator |

Core — 800 групп, не 3000/3600. Для holdout один заранее назначенный применимый
negative JPEG на независимую source family и один фиксированный image-level
endpoint: **DQ ONLY**. Односторонняя 95% exact binomial оценка
(Clopper–Pearson upper bound) для n=500:
0 errors → 0,5974%; 1 → 0,9452%; 2 → 1,2538%. Следовательно, для единой
заранее зафиксированной проверки ≤1% допускается максимум одна ошибка;
0 или 1 false positive могут удовлетворять FPR-критерию, 2 и более — нет.
Это **принятое statistical acceptance rule**, не DQ measurement threshold.
Grid исключён из текущего Stage 12 primary statistical holdout и не может
использовать те же 500 изображений для второй независимой ≤1% claim без отдельного
multiplicity/statistical плана. 500 не обеспечивают ≤1% для каждого device/content bin.
Точное DQ decision rule, sensitivity/coverage requirement и abstention semantics
должны быть зафиксированы до открытия holdout; тривиальное «всегда negative»
не является utility. DQ и Grid не получили production acceptance.

Observed yield 97/120 даёт около 619 кандидатов на 500 eligible. Следующая
оценка acquisition остаётся предложением для execution planning, а не owner freeze:
заранее ограниченная очередь 700 holdout candidates с outcome-blind eligibility
и frozen order: первые 500 eligible до запуска decision rules, остальные —
неиспользованный резерв. Если eligible меньше 500 либо результат не проходит,
это недостигнутый план/FAIL, а не повод добирать до PASS. Новое исследование
потребует отдельного решения. Holdout скрыт от calibration, все families,
near-duplicates и связанные derivatives остаются вместе; split manifest/hash,
квоты source/device/content/quality и preprocessing support фиксируются заранее.
При device-domain validation необходимо отдельно закрепить разделение устройств;
source-disjoint само по себе не означает device-disjoint.

Ограничение доступности: под нынешними фильтрами остаётся 324 archive make/model
пары. При пилотном yield это ориентировочно 262 дополнительных eligible masters;
с 97 пилотными — около 359, на 441 меньше core800. Нельзя обещать заполнить план
этим архивом при прежнем one/model ограничении. Нужны дополнительные разрешённые
CC0 форматы/источники или собственные съёмки с независимыми сценами и подтверждёнными
правами; состав и квоты требуют owner freeze. **2000 собственных RAW не требуются.**
Экстраполяция yield не гарантирует независимость или будущую пригодность.

Средний скачанный RAW — 22,40 MB. Порядок 900–1100 новых candidates означал бы
20–25 GB RAW, дополнительно masters/derivatives и результаты; резерв 35–40 GB
разумен как планирование, не обещание размера. Матрицу derivatives следует
ограничить заранее. VISION100 означает 100 QA/measurable social families,
не 100 native-supported: **0/43 native pilot images измеримы** при текущих ceilings.
Production resource limits не ослабляются; скрытое уменьшение native samples
для изменения этого факта запрещено. 43 уже просмотренные VISION families остаются
exploratory external stress, не новые validation/holdout evidence; новые57 оцениваются отдельно.
Optional challenges50 не входят в FPR denominator.

## Проверки пилота и owner acceptance closure

Focused research tests: **109 passed** (89 R2 + 20 pilot), включая rights,
hashes, duplicate/source grouping, partitions, rejections, interruption/resume,
cleanup, transform provenance, same-DQT/phase_patch и streaming moments.
Ruff research-кода и теста — PASS. Полный `uv run poe check`: pre-commit — PASS,
mypy — PASS (65 source files), pytest — **2631 passed, 17 skipped, 1 failed**.
Единственный failure: `test_sdist_wheel_metadata_entry_point_and_resources` —
защита sdist provenance отклоняет intended untracked source (первым новый отчёт).
**OWNER_VERIFY_REQUIRED**: повторить после Git-действий владельца; staging
агентом и ослабление проверки запрещены. Последующий CLI smoke отдельно — PASS.
Это development verification; strict certification не выполнялась.

До owner acceptance итоговый diff и все intended untracked проверены вместе;
`git diff --check` и итоговый status вошли в полный внешний bundle
`m2-r3b-complete-owner-review-2026-09-24`. Он охватывает R3B delta до этой docs-only closure:
REFERENCES, ROADMAP, два изменённых R2 модуля, новый отчёт, два новых pilot
модуля и тест. Полные тексты восьми файлов, hashes, tracked/untracked diff,
status, логи и внешние reproduction scripts предоставлены без staging.
Graphify stale, не пересобирался. Git mutations отсутствуют.

Владелец принял pilot evidence и research implementation; counts и DQ-only
statistical endpoint зафиксированы. Эта docs-only closure меняет только ROADMAP
и данный отчёт; проверки — `git diff --check`, согласованность документации
и итоговый Git status. Прежние результаты тестов выше относятся к реализации
пилота; новый полный test run для docs-only closure не требуется.

Следующий шаг DQ — FINAL_CALIBRATION; остаются planning acquisition/квот,
freeze decision rule/sensitivity/coverage/abstention и DQ METHODS gates.
Grid — DEFERRED_RESEARCH_ONLY без окончательного отказа от направления.
Методы не приняты в production, production thresholds/анализаторы не созданы,
M2-A остаётся BLOCKED. Пилот никогда не используется как final untouched holdout;
адаптивный добор после просмотра outcomes запрещён.
