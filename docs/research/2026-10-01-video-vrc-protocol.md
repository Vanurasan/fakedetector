# M4-R2-P — протокол VRC-DENSE-1 и готовность корпуса

Дата: 2026-10-01. **PREDECLARATION / CORPUS READINESS ONLY**.
**M4-R2-P — DONE / OWNER ACCEPTED** (решение владельца 2026-10-01, M4-R2-P-A).
**VRC-DENSE-1/P1 — FROZEN RESEARCH PROTOCOL**.
**M4-R2-E — NEXT / SEPARATE EXECUTION AUTHORIZATION REQUIRED**.

## 1. Предрегистрация и основания

Владелец принял и заморозил исследовательский профиль `VRC-DENSE-1/P1` до получения
измерительных outcomes. Это конкретизация [M4-R1 §7](2026-10-01-video-method-selection.md),
а не изменение его формул, лимитов или принятие production-метода.
Вопрос: дают ли разнесённые меняющиеся четырёхкадровые группы наблюдение,
которое не описывают adjacent exact-run metrics `video_sampled_frame_quality`?
Цвет и последовательные изменения измеряются раздельно. Fusion, top-k,
manipulation/near-match thresholds, новые Findings и независимый risk vote отсутствуют.
VCM-FRAME-1 остаётся INACTIVE; Macro 3 не переоткрывается.

Baseline проверен отдельными read-only командами: ветка
`feat/stage12-macro4-video-analyzer-expansion-wave1`, HEAD
`bc767c2cc2f8ea0110c2208705ae36d787130251`, начальный status пуст.
Прочитаны правила AGENTS, относящиеся к задаче разделы PROJECT, CONTRACTS,
METHODS, REFERENCES, текущий Macro 4 и M1-E/F/G ROADMAP, research README,
M4-R1 и внешний `reviews/M4-R1-video-selection/acceptance/review-summary.md`.
M4-R1-A фиксирует принятие направления владельцем 2026-10-01, без принятия
production-метода. Текущий committed baseline содержит эту запись.

| Свидетельство | Проверенный источник; предел утверждения |
|---|---|
| Demand и квоты | `src/fakedetector/preprocessing/_requirements.py`: `PreprocessingRequirements`, `_DEPENDENCIES`, `ForensicResourcePolicy`; CONTRACTS §7.5 |
| План и выпуск dense | `preprocessing/_service.py::_prepare_timing_forensic`, `_media_tools.py::probe_timing_stream`, `select_timing_regions`, `dense_geometry`, `decode_dense_window`, `_dense_records` (пути здесь от `src/fakedetector/`) |
| Binding и чтение | `preprocessing/_models.py::ForensicManifest`, `DenseVideoWindowDescriptor`; `analyzers/_models.py::AnalyzerRequest.read_numeric`; source, role, provenance, byte length и immutable backing проверяются существующим кодом |
| Lifecycle | `_generated_artifact_budget.py`, `lifecycle/cleanup.py::WorkspaceCleanup`; регистрация перед записью, общий budget, запрет cleanup до подтверждённого reap |
| M1-E/F tests | `tests/test_preprocessing.py`: `test_regions_bound_short_overlap_and_long_unsampled_gaps`, `test_nonzero_and_negative_starts_are_preserved`, `test_dense_real_same_decode_rgb_and_timing`, `test_dense_observed_timing`, `test_dense_geometry_windows_and_limits`, `test_dense_pixel_reference_requires_same_decode_operation` |
| M1-G и reader tests | Там же: `test_dense_failed_artifact_lifecycle_and_barrier`, `test_dense_close_interruption_retains_admission_until_child_reaped`, `test_dense_resource_rejection_precedes_process`, `test_generic_timing_and_av_are_stable_when_dense_is_corequested`, `test_dense_dependency_requires_streams_but_not_generic_records`, `test_combined_generic_dense_mapping_preflight_preserves_existing_limits`; `tests/test_stage5_internal_models.py::test_numeric_reader_binds_identity_extent_and_immutable_backing` |
| Baseline comparator | `analyzers/_video_frames.py::VideoSampledFrameQualityAnalyzer`; `tests/test_stage6_real_analyzers.py`: one/distinct samples, three identical samples/target times и decoded pixels, а не PNG bytes |

Это source inspection, не новый запуск тестов или эксперимент. Graphify
`0.9.53`, source SHA `625b9e83f133fb0ae31a4b90e9e1288bff96f69c` — **STALE**;
read-only query использован только для навигации. Граф не пересобирался и
не служит доказательством текущих контрактов.

Численные результаты ниже — аналитические bounds/oracles, не measurements.
Все IDs, таблицы и файлы этого протокола относятся только к внешнему research
harness; новых runtime/config/public schema fields в репозитории нет.

## 2. Спецификация профиля

### 2.1. Вход и same-decode binding

Controlled video source проходит существующий intake/validation и dispatcher.
Единственный demand — `DENSE_VIDEO`, closure ровно `{DENSE_VIDEO, STREAM_TIMING}`;
`audio_spectrogram=false`, `video_audio_track=false`. Generic `TIMING_RECORDS`,
AV и audio precision не запрашиваются. Legacy sampled PNG всё равно создаются.
Используется неизменённый снимок `config/config.example.yaml` baseline
(legacy interval 1 s, video generated budget 200 MiB, общий deadline 600 s).
В будущем сохранить SHA-256 этого снимка; иной снимок не подставлять молча.

Manifest SHA-256 должен совпасть с SHA-256 **измеряемого файла case**, а не с
hash его предка. Отдельно сохраняется `source_group` и hash оригинала.
Первый video stream выбирает существующий producer; возможный первый audio
stream даёт только stream facts. Dense-only имеет максимум 2 stream facts +
3 пары pixel/timing representations = 8, ниже потолка 16.

Обязательны producer `ffmpeg_dense/1`, profile `rgb24_bilinear/1`,
`pixel_format=rgb24`, `geometry_profile=coded_grid_bilinear_no_upscale`.
Pixels: `|u1`, C-order `(n,H,W,3)`; timing: `<i8`, `(n,9)`,
`record_kind=frame`, `purpose=dense`, `stop_reason=dense_limits_or_eof`.
Pixel descriptor ссылается на конкретный timing artifact; совпадают
`decode_operation_id`, число кадров и representation provenance.
Stream/time base и region берутся через эту ссылку, не угадываются по имени файла.
Ordinal timing column 3 равен позиции `0..n-1`; validity bit 0 подтверждает PTS.
Чтение — только `AnalyzerRequest.read_numeric` через source-bound manifest:
точная длина до/после read, закрытый dtype/shape, immutable bytes backing.

Текущий producer проверяет native/output showinfo одного filtergraph,
time base, ordinals, PTS, geometry, frame count и Adler-32 каждого RGB frame
(начальное значение 0). Это binding bytes/timing, не forensic content hash.
Generic records другого decode и target times legacy PNG использовать вместо
этих PTS запрещено. UUID проверяется внутри запуска, не между запусками.

Существующий план: до трёх nominal 2 s regions, перекрывающиеся regions
объединяются; unknown duration даёт только начало. У каждого merged request
dense сохраняет первые не более 2 s и 32 output frames. Native до 3840×2160,
output до 640×360, bilinear/no-upscale, без autorotation/SAR/display correction.
Requested interval не превращается в фактически полное покрытие.

### 2.2. Дескриптор и группы

Для каждого валидного кадра W≥16, H≥9:

```text
x[j] = floor(j*W/16), j=0..16
y[k] = floor(k*H/9),  k=0..9
A = (x[j+1]-x[j]) * (y[k+1]-y[k])
S = sum RGB channel code values in [y[k],y[k+1]) × [x[j],x[j+1])
q[k,j,c] = floor((S + floor(A/2))/A), c = R,G,B
```

Каждый block непустой; остаточные строки/столбцы не отбрасываются. Это half-up
integer rounding, не banker rounding. Вектор 432 `uint8` значений идёт по
`k`, затем `j`, затем RGB. Нового resize/цветового преобразования нет;
среднее относится к decoded code values, не линейной яркости.
Суммирование выполняется в signed int64 без промежуточного uint8 overflow.

Окна читаются по одному, в порядке `(stream_index, region)`. Все RGB views
освобождаются до чтения следующего окна; остаются descriptors и timing.
Группа `g=(region,start_ordinal)` содержит четыре **последовательных output**
кадра `s..s+3`, для каждого `s=0..n-4`, шаг 1, без перехода между окнами.
Отсутствующий PTS или нестрого возрастающие PTS внутри группы делают эту группу
undefined. Нельзя сортировать кадры по PTS или исправлять их значения.
Другие валидные группы того же окна сохраняются; журнал перечисляет все
исключённые starts и причины, а case получает отметку о частичной пригодности.

PTS seconds = `Fraction(int(tick)*int(base_num), int(base_den))`.
Три gaps считаются вычитанием этих Fraction с Python int, не NumPy int64
multiply и не float/fps. VFR допустим, gaps сохраняются у каждой группы.
Сравнение только по позиции кадра `t=0..3`; без time warp, interpolation,
cadence normalization или требования одинаковых gap vectors.
Локализация группы — `[first_PTS,last_PTS]`, envelope четырёх наблюдений;
это не длительность вставки или exposure.

### 2.3. Все допустимые пары

Перечислить каждую неупорядоченную пару разных валидных групп ровно один раз.
Разные cases/исходные hashes/streams не сравниваются. У групп должны совпасть
native width/height, output W/H, pixel/geometry profile и producer/profile versions.
В одном окне ориентировать пару по ordinal и требовать `start_b ≥ start_a+5`:
после четырёх кадров A остаётся хотя бы один неиспользованный кадр перед B.
В разных окнах требовать `a.last_PTS < b.first_PTS` либо обратное и
ориентировать A раньше B по точному времени. Равенство endpoints, overlap
или interleaving envelopes исключаются. Внутри одного окна также требуется
строго разнесённый временной envelope: ordinal gap не разрешает temporal overlap
при немонотонности вне самих групп. Это реализует уже заданное M4-R1 исключение
overlapping temporal supports, не новую distance-фильтрацию.

Все пары проверяются независимо от truth, цвета и T; static/periodic группы
не удаляются. Причины несовместимости и итоговые counts сохраняются.
Максимум групп `3*(32-3)=87`, unordered pairs `87*86/2=3741` до exclusions.
При трёх полностью разделённых монотонных 32-frame окнах: 300 пар внутри каждого
и `3*29*29=2523` между окнами, итого 3423 eligible pairs — oracle enumeration,
не обещанное число строк реального case.

### 2.4. Раздельные измерения и канонический вывод

```text
C = 432; t = 0..3; component c = 0..431
N_color = sum(t,c) abs(a[t,c] - b[t,c])
delta_a[t,c] = a[t+1,c] - a[t,c], t=0..2
delta_b[t,c] = b[t+1,c] - b[t,c]
N_delta = sum(t=0..2,c) abs(delta_a[t,c] - delta_b[t,c])
N_Ta = sum(t=0..2,c) abs(delta_a[t,c])
N_Tb = sum(t=0..2,c) abs(delta_b[t,c])
D_color = N_color / 440640
D_delta = N_delta / 660960
T_a = N_Ta / 330480; T_b = N_Tb / 330480
```

Перед subtraction/abs uint8 расширяется до signed int64. Хранятся исходные
числители и фиксированные denominators, а также сокращённые fractions
`[numerator,denominator]`, denominator>0, gcd=1, ноль `[0,1]`.
Все четыре меры лежат в `[0,1]`; `N_color≤440640`, `N_delta≤660960`,
`N_T≤330480`, консервативно `S≤255*640*360=58752000`.
T=0 означает только неизменность descriptor. D_color=0 не означает byte equality.
Совместного score и cutoff нет; float допустим лишь как неканоническая подпись.

Каждая строка пары содержит case/source-group и case SHA-256, profile P1,
stream index и для A/B: region, pixel/timing artifact IDs, operation UUID,
четыре output ordinals и четыре measured ticks с time base, native/output
geometry, requested ticks, observed coverage/stop reason, три rational gaps,
отдельный envelope. Далее идут четыре numerators/denominators и fractions.
Нельзя объединять A и B в один «подозрительный» интервал.

Порядок rows — лексикографически `(case_id, stream_index, region_a, start_a,
region_b, start_b)` **после** ориентации пары. Regions/ordinals — числа.
Порядок корпуса: P01..P06, V01..V07; B01..B06; R01..R12, V01..V04.
UUID, distances, elapsed и RSS не участвуют в сортировке. UTF-8 без BOM,
LF, compact JSONL, фиксированный набор ключей с сортировкой ключей;
integers не конвертируются в float (reader обязан сохранять большие integers).
Descriptors сохраняются C-order bytes и SHA-256, порядок frame IDs фиксирован.
Полный pair output ≤4 MiB/case/run; превышение — resource failure всего case,
без top-k/усечения. Незавершённый output помечается incomplete и не используется
для utility gate. Metadata/descriptors/failure ledger хранятся отдельно.

Для каждой заранее назначенной truth/control пары отдельно по D_color и
D_delta вывести `less_count`, `equal_count` среди **всех** eligible pairs,
`rank=1+less_count`; equal_count включает саму строку. Нет выбора более выгодной
distance, оптимизации ranks, ранжирования по fusion или отсечения ties.

### 2.5. Undefined, abstention и failure

| Условие | Обязательный результат |
|---|---|
| n<4 либо W<16/H<9 | Окно NOT_APPLICABLE, без фиктивных групп/нулевых distances |
| PTS отсутствует/нестрого возрастает в группе | Группа UNDEFINED_PTS; все starts и причины в ledger, никакой замены PTS |
| Profiles/geometry различаются; overlap; gap меньше одного spare frame | Пара INELIGIBLE с причиной; валидные остальные пары остаются |
| Ни одной eligible пары | Case NO_ELIGIBLE_PAIRS; пустой pair output и явный status |
| Source/role/provenance/UUID/reference mismatch, malformed numeric length | INPUT_FAILURE, остановка case; не forensic positive |
| Producer reject/decoder error/empty decode/timeout/resource cap | Отдельный failure с исходным phase; не «distance=0» и не отсутствие сигнала |
| Truth отсутствует целиком/частично в observed support | COVERAGE_MISS с 8 membership bits; не успешный no-signal |
| Все 8 кадров найдены, но timing/geometry/pair eligibility не выполнены | SUPPORTED_INELIGIBLE с причиной; не подмена coverage miss |
| Static, periodic, slides, обычный cut/flash | Валидные confound measurements, включая нули и ties; не исключение |

Undefined хранится как status и `null`, никогда NaN/inf. Binding failure
не позволяет публиковать ранее посчитанные строки как успешный case.

## 3. Процедурный manifest и truth

### 3.1. Шесть исходных конструкций

Все P sources: 320×180, RGB24, 500 frames, CFR 25/1, PTS `i/25`, i=0..499,
без audio; длительность 20 s. Генератор — будущий собственный внешний код,
без RNG, fonts, скачанных текстур/картинок. Целочисленные формулы ниже полностью
определяют pixels. `//` — floor; `%` — неотрицательный остаток; channels c=0,1,2.

Базовая текстура:
`U(s,x,y,c)=32+((13*(x//8)+17*(y//8)+29*c+31*s+((x//8)*(y//8))%19)%160)`.
Она вычисляется для любых неотрицательных x,y, не требует texture bitmap.

| ID / seed | Конструкция кадра F(i,y,x,c) |
|---|---|
| P01 / 101 | Background `U(101,x,y,c)//2`. Объект 64×48 с left=`(3*i)%257`, top=`(2*i)%133`; внутри его прямоугольника заменить на `U(111,x-left,y-top,c)+32`. Движущаяся текстурная область |
| P02 / 202 | `U(202,x+i,y+(i//3),c)` — pan по непериодизированной конечной области текстурной формулы |
| P03 / 303 | `U(303,x,y,c)` — static, неизменные pixels |
| P04 / 404 | Background `U(404,x,y,c)//2`; объект 64×48: left=`8*(i%25)`, top=60, fill=`U(414,x-left,y-top,c)+32`. Точный период 25 frames |
| P05 / 505 | Slide index `h=i//50`; `U(505+h,x,y,c)`, но при `20≤x<300` и `40≤y<60` значение `(40*h+60*c)%256`. Собственные screen/slides, без чужих материалов |
| P06 / 606 | При i<12: `U(606,x,y,c)`; 12≤i<238: `U(616,x,y,c)` (обычный cut); 238≤i<240: 255 (flash); 240≤i<450: `U(616,x,y,c)`; i≥450: `min(255,U(616,x,y,c)+((i-450)//2))` (lighting ramp). События заранее размещены в трёх planned retained windows |

Dynamic construction label заранее P01/P02; P03/P04/P05/P06 — benign/confound.
Label не гарантирует T>0 в каждой группе: нули/ties сохраняются. Pan/object
тоже могут давать descriptor collisions; название «уникальный объект» не является
обещанием уникальности descriptor. Здесь задаётся один собственный объект,
а не доказанный injective coding каждой сцены.

### 3.2. Семь вариантов каждого source group

Операция `Copy(F,s,d)` заменяет **ровно** output frames `d..d+3` на исходные
`F[s..s+3]`, сохраняя destination ordinals/PTS и общее число кадров. Это replacement,
не вставка с увеличением duration. Карта `origin[i]=s+i-d` для destination,
иначе `origin[i]=i`; `role=source_copy|destination_copy|untouched` хранится отдельно.
Все координаты 0-based; интервал ordinal half-open `[s,s+4)`.

`L` и `Y` — единственные рецепты §5. Decode/transcode никогда не даёт новую
независимую группу. В каждом source group создаются именно семь case slots:

| Variant | Рецепт и parent | Заранее заданная truth pair / untouched control |
|---|---|---|
| V01 | `L(F)`, оригинал процедурной конструкции | Copy отсутствует; диагностическая пара (4,16), control (8,20) |
| V02 | Decode V01 → Copy(4,16) → L | Within-window truth (4,16), control (8,20) |
| V03 | Decode V01 → Copy(4,229) → L | Cross-window truth (4,229), control (8,233) |
| V04 | Decode V01 → Copy(104,116) → L | Truth (104,116), control (108,120), обе группы запланированы вне retained support |
| V05 | Decode V02 → L, без новой Copy | Lossless-reference повторный export той же within-window copy; truth/control как V02 |
| V06 | Decode V05 → Y | Один фиксированный lossy export этой copy; truth/control как V02 |
| V07 | Decode V01 → Y, без Copy | Matched export без copy; диагностическая пара (4,16), control (8,20) |

V05 конкретизирует предложенную M4-R1 lossless-reference cell: ожидаемая
эквивалентность её pixels V02 проверяет сохранность при lossless re-export.
Она не новая source observation и не дополнительный успех utility gate.
Это явная техническая зависимость, включая возможное совпадение файловых hashes.
Каждый P01..P06 × V01..V07 заранее имеет ID `Pss-Vvv`: 42 case slots,
включая static/periodic copy operations как confound constructions.

При заявленных 20 s/25 fps producer должен запросить [0,2), [9,11), [18,20)
и удержать ordinal sets 0..31, 225..256, 450..481. Это **предсказание плана**,
которое будущий run обязан сравнить с observations. Placement не перемещается,
если mux/decode дал другое support. Truth (4,16) лежит между legacy targets 0 и 1 s.
Control имеет те же четыре кадра на группу и ту же separation (12 frames);
cross control separation 225 frames. Контрольные ordinals не перезаписываются.

### 3.3. Шесть boundary slots

| ID | Точная конструкция / ожидаемый тип проверки |
|---|---|
| B01 | Первые 3 frames P01, L, 320×180, 25 fps: n<4, NO_ELIGIBLE_PAIRS/NOT_APPLICABLE, без zero padding |
| B02 | P01 formula i=0..74, L, 25 fps: 3 s, один merged request [0,3), dense первые ≤32 frames и ≤2 s; partial support обязателен |
| B03 | P01 formula i=0..239 на native 1280×720: каждый исходный pixel размножен в block 4×4; L, 120 fps, 2 s. Проверить 32-frame cap и output 640×360; не 240 retained frames |
| B04 | P01 formula i=0..99, L с VFR clock `PTS[i]=7200*(i//2)+1800*(i%2)` в базе 1/90000. Gaps чередуются 1/50 и 3/50 s; никакого CFR conversion |
| B05 | Только typed representation fixture, не media producer output: 16×9 RGB q=i для i=0..11, base 1/1000; две фиксированные subcases PTS `[0,40,80,80,160,200,240,280,320,360,400,440]` и `[0,40,80,60,160,200,240,280,320,360,400,440]`. Endpoints/coverage согласованы; группы через duplicate/decrease UNDEFINED, кадры не пересортировать. Обе subcases считаются одним boundary slot |
| B06 | Только representation fixture: RGB24 `(12,8,15,3)`, значение i, PTS 40*i, base 1/1000; W<16/H<9. NOT_APPLICABLE, без upscale |

B05/B06 используют валидную структуру manifest/numeric reader с явно помеченным
`INPUT_FIXTURE`; они не выдают поддельное binding свидетельство за работу producer.
Их source identity — SHA-256 canonical fixture specification и raw payloads,
не hash якобы записанного видео; native geometry равна output, stream=0, region=0,
requested=[0,480) ticks, duration каждой строки 40 ticks, ordinals 0..11,
validity mask PTS+duration=5, прочие optional columns равны 0 и отсутствуют.
Coverage=envelope, endpoints 0/440; искусственный operation token связывает
pixels/timing только внутри fixture. UUID не является свидетельством decode.
Дополнительные analytic arrays §6 — unit oracles, не дополнительные corpus cases.
Все 48 Stage A slots сейчас **PLANNED / NOT GENERATED**, hashes не выдумываются.

### 3.4. Support mapping до distances

До чтения distances сохраняются source/derivative ordinal maps, case SHA-256,
recipe/генератор hash, frame count/clock и заранее заданные truth/control ordinals.
Construction ordinal относится ко всему сконструированному файлу; dense ordinal
локален окну. Их связывает только measured same-decode PTS и проверенный clock:
для CFR `i=PTS_seconds*F` должен быть точным integer, для B04 — точное совпадение
с clock table. Нельзя округлять до ближайшего кадра или связывать по похожести.
У admitted originals Stage B clock проверяется до construction; неоднозначность
даёт SUPPORT_UNRESOLVED, а не подтверждение truth. Повторное попадание одной
PTS в разные windows сохраняет оба observation IDs, но не удваивает source evidence.

Membership source и destination проверяется для всех восьми frames и их
последовательности в одной группе. Заранее сохраняются отдельно truth kind,
support status, eligibility и точное `T=0`/`T≠0`; truth не выводится из distances.
Две группы должны присутствовать полностью. Отрицательный support или
неоднозначность никогда не превращаются в positive/negative detection result.

## 4. Готовность реального корпуса

**REAL_CORPUS_ADMITTED: NO.** Ни один реальный video source не передан в задании
и не верифицирован для этого корпуса. Назначенный `research/M4-R2-VRC/` до задачи
отсутствовал; M4-R1 прямо записывает отсутствие admitted recordings. Иные медиа
на компьютере не рассматриваются как разрешённые sources. Acquisition/download
в M4-R2-P не выполняется. Нужны до 12 originals с provenance и hashes:

| Slots | Категория; независимые recording sessions |
|---|---|
| R01, R02 | Static / low-motion |
| R03, R04 | Pan / handheld |
| R05, R06 | Natural periodic motion |
| R07, R08 | Собственные screen/slides |
| R09, R10 | Обычный cut/flash/lighting; история нормального монтажа раскрыта |
| R11, R12 | Dynamic nonperiodic |

Все slots **MISSING / NOT ADMITTED**. Source group — независимая recording
session/событие. Обрезки одной записи, разные encodes, соседние takes одного
непрерывного события, повторное использование кадров и несколько ракурсов
одного события не дают независимых groups. Один device может использоваться
снова, но разнообразие устройств не заявляется без фактов. Для edited control
R09/R10 все исходные sessions образуют один connected source group; ни один
из его ancestors не используется в другом R group. Это сохраняет benign edit
control, не выдавая его за single-history untouched camera original.

Предлагаемая узкая collection eligibility P1: 12–20 s, файл ≤20 MiB,
16≤W≤1280, 10≤H≤720, чётные W/H, один основной video stream, SDR 8-bit,
без rotation (0) и с SAR 1:1; CFR **25/1 или 30/1**, first PTS 0 и
последующие PTS точно i/F. Такой collection profile позволяет однозначные
ordinal maps без нового VFR-transform механизма; VFR остаётся в B04 и
разрешён измерению §2. Это ограничение переноса результатов нужно показывать.
Не конвертировать неподходящий original ради admission. Audio допустимо,
но в derivatives удаляется явно, семантическая A/V оценка не проводится.
Natural scene category/history определяются до descriptor extraction.
Не требовать «хорошей» distance или динамичности descriptor для admission.

Для каждого admitted R group четыре slots:

| Variant | Construction и truth |
|---|---|
| V01 | Original bytes без изменений; pair (4,16) — untouched diagnostic, control (8,20) |
| V02 | Decode original → Copy(4,16) → L; truth (4,16), control (8,20) |
| V03 | Decode original → Y без Copy; matched export, pair/control как V01 |
| V04 | Decode V02 → Y; та же truth/control, что V02 |

Все четыре сохраняют связь с original SHA, ancestor list и rights. Placement
одинаков и назначен до outcomes, между legacy targets 0 и 1 s при обоих fps.
Исходная compression history original остаётся частью provenance; L не
«восстанавливает» утраченную информацию. Full decoded video в RAM не хранится:
construction идёт потоково с buffer четырёх source frames.

Template admission record (все обязательные неизвестные поля остаются `MISSING`):

```text
source_group; slot; original_filename; original_sha256; original_bytes
creator/rightsholder; capture_date; device/software/workflow; recording_session
ancestors_and_sha256; edits/transcodes_before_receipt; category_and_reason
permission_evidence_location; internal_research_allowed; derivative_creation_allowed
redistribution_original_allowed; redistribution_derivatives_allowed; attribution
people/screens/third_party_material_permissions; restrictions; retention_terms
reviewer; admission_date; admitted_or_excluded; exclusion_reason
container/codec/pixel_format; W/H/SAR/rotation; fps; time_base; PTS_origin
frame_count/duration; audio_present; clock_validation; technical_size_validation
derivatives: case_id, parent_sha256, recipe_sha256, argv, executable_sha256,
            frame_ordinal_map_sha256, derivative_sha256, bytes, construction_status
```

Права внутреннего использования и создания derivatives должны быть подтверждены;
публикация/распространение разрешается только при отдельном положительном поле,
unknown не означает permission. Нет blanket dataset license или переноса допуска
VISION JPEG на видео. Originals, карты и производные вне Git.

Admission/exclusion ledger freeze происходит **до всех Stage B measurements**:
hash списка slots, originals, recipes, maps, derivatives и прав. Пока данных нет,
реальные SHA-256 не заполнены, и Stage B закрыта. Предпочтительно заполнить и
запечатать B manifest до Stage A outcomes; если это невозможно, будущая collection
следует тем же slots/правилам без использования результатов A для отбора.
Недостающий slot остаётся missing; после просмотра измерений заменять source,
выбирать другой take, сдвигать copy/control или менять category нельзя.
До outcomes объективно неподходящие кандидаты фиксируются с причинами; замену
допускает только документированный premeasurement admission, не молчаливое стирание.

Если derivative >20 MiB, неправильный clock/frame count, unsupported media или
недостаточные права — записать NOT EXECUTABLE/NOT ADMITTED с причиной. Не менять
CRF, spatial size, duration или input cap для спасения cell. Полный максимум
остаётся 42+6+48=96, пропуски и зависимости публикуются. Derivatives, pairs,
три repeats и V05 не считаются независимыми наблюдениями.

## 5. Encoding и transform recipes

### 5.1. Проверенная среда, без encoding runs

Read-only проверки 2026-10-01: `ffmpeg -version`, `ffprobe -version`,
`ffmpeg -hide_banner -h encoder=libx264rgb`, `encoder=libx264`, `encoder=ffv1`,
`-h muxer=mp4`, `muxer=matroska`, `muxer=nut`, `-h filter=scale`.
Оба executable: `9.0.1-full_build-www.gyan.dev`, gcc `16.1.0`, сборка
`--enable-gpl --enable-version3 --enable-static --enable-libx264`.
Python существующего `.venv`: 3.12.10 AMD64; NumPy 2.5.2. Установок не было.

Executable directory:
`C:\Users\Vanur\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\`.

| Executable | Проверенный SHA-256 |
|---|---|
| ffmpeg.exe | `57c56e369d5b4873b4d93fc1a1d833cb7cd8bc9325c14b05c34ce60b22842d8a` |
| ffprobe.exe | `afe05347caaabe479b3c4eae71992b6ec1e11c57266a1d665deb0f9fe9847208` |

Local help подтверждает RGB24 у libx264rgb, YUV420P у libx264, MP4 muxer
и `video_track_timescale`. Выбор **L=libx264rgb/MP4** позволяет сохранить RGB
и явно задать clock в контейнере, используемом существующими dense tests.
FFV1/bgr0 также присутствует, но не выбран и не является fallback: для MKV
нельзя из одной container duration обещать producer три stream-timing windows.
Качество Y заранее CRF 23, без перебора. Эти решения не основаны на outcomes.

Статус L/Y: **AVAILABLE_BY_BUILD / ENCODE_NOT_RUN**. Полные command paths,
версии, defaults точной сборки и hashes включаются в transform provenance.
Первый будущий construction gate проверяет реальные encoder exit/frame count,
PTS и RGB roundtrip L. Если рецепт не исполняется или не выполняет postconditions,
соответствующая cell **NOT EXECUTABLE**, а не другой codec/quality.
Наличие help не выдаётся за end-to-end successful encoding.

### 5.2. Точные argv templates

Команды ниже — спецификация argv для будущего harness, **не выполненные команды**.
Переносы строк не являются PowerShell-синтаксисом. Запуск без shell,
`<FFMPEG>` — абсолютный executable выше; `<OUT>` — новый external case file,
никогда original; `-n` запрещает overwrite. `<W>`, `<H>`, `<F>`, `<N>`
подставляются только из manifest (§3/§4). Фактический argv сохраняется массивом
строк вместе с hashes; незаданные codec parameters — defaults ровно указанной
hash-pinned сборки. Нет hardware encoding, auto recipe selection или audio output.

**L / lossless reference:** stdin содержит ровно N RGB24 frames, C-order.

```text
<FFMPEG> -hide_banner -nostdin -v error -xerror -n
  -f rawvideo -pixel_format rgb24 -video_size <W>x<H> -framerate <F>
  -i pipe:0 -map 0:v:0 -an -sn -dn -map_metadata -1 -map_chapters -1
  -filter_threads 1 -vf format=rgb24 -frames:v <N> -fps_mode passthrough
  -c:v libx264rgb -preset medium -crf 0 -pix_fmt rgb24 -threads:v 1
  -g 1 -keyint_min 1 -sc_threshold 0 -bf 0
  -x264-params keyint=1:min-keyint=1:scenecut=0:bframes=0:open-gop=0:threads=1
  -enc_time_base:v 1:90000 -video_track_timescale 90000
  -color_range pc -f mp4 <OUT>
```

Для B04 и **только B04** заменить `-vf format=rgb24` на единый argv value:
`settb=expr=1/90000,setpts=7200*floor(N/2)+1800*mod(N\,2),format=rgb24`.
Здесь N в filter expression — input frame ordinal, а `<N>=100` — frame limit.
Raw input F=25; output `-fps_mode passthrough`, без `-r`, drop/duplicate frames
и без восстановления CFR. Наблюдаемая последняя duration записывается как факт,
продолжительность 4 s не предполагается из числа кадров.

**Y / единственный lossy export:** stdin — decoded RGB24 ровно той parent
последовательности, которая указана в manifest; для real original pixel
conversion в RGB является явно записанным construction step, не измерением VRC.

```text
<FFMPEG> -hide_banner -nostdin -v error -xerror -n
  -f rawvideo -pixel_format rgb24 -video_size <W>x<H> -framerate <F>
  -i pipe:0 -map 0:v:0 -an -sn -dn -map_metadata -1 -map_chapters -1
  -filter_threads 1
  -vf scale=iw:ih:flags=bilinear:in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p
  -frames:v <N> -fps_mode passthrough
  -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -threads:v 1
  -g 50 -keyint_min 50 -sc_threshold 0 -bf 2
  -x264-params keyint=50:min-keyint=50:scenecut=0:bframes=2:b-adapt=0:open-gop=0:threads=1
  -enc_time_base:v 1:90000 -video_track_timescale 90000
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709
  -f mp4 <OUT>
```

Это один RGB→YUV420/BT.709 export с lossy quantization, fixed GOP и B-frames;
дополнительного resize нет. Никаких bitrate/CRF trials. Y применяется только
к чётным размерам и CFR cases, B04 использует L. L/Y не доказывают исходную
физическую colorimetry сцены; Y tags описывают выбранную construction conversion.

Parent decode для CFR transforms (sequential stream, без seek):

```text
<FFMPEG> -hide_banner -nostdin -v error -xerror -err_detect explode
  -protocol_whitelist file -threads 1 -filter_threads 1 -noautorotate
  -i <PARENT> -map 0:v:0 -an -sn -dn -vf format=rgb24
  -fps_mode passthrough -c:v rawvideo -threads:v 1 -pix_fmt rgb24
  -f rawvideo pipe:1
```

Чтение ровно W*H*3 байт на frame; partial frame/extra/missing frame — failure.
Не ограничивать decode `-frames:v N`, чтобы лишний output не скрывался.
Source quartet кешируется; destination quartet заменяется по ordinal map;
тайминг исходника предварительно проверен как zero-origin CFR i/F.
Re-encoding назначает тот же clock, а output MP4 time base 1/90000.
Для VFR media B04 real-source transform не предлагается; генератор задаёт clock.

Construction verification до measurement: bounded ffprobe с allowlist
`stream=index,codec_type,width,height,pix_fmt,time_base,start_pts,duration_ts,
avg_frame_rate,r_frame_rate:frame=pts,duration,width,height` и
`-select_streams v:0 -show_streams -show_frames -of json`.
Сохранить argv/выбранные поля; не tags/raw diagnostics в repository.
Максимум 600 frames для real CFR и 500 для P, B overrides §3;
stdout ≤1 MiB, stderr ≤256 KiB, timeout ≤30 s и remaining deadline.
L roundtrip сравнить с входными RGB потоково byte-for-byte до VRC; Y —
только frame count, geometry, clock и успешный decode, без требования pixel equality.
Это generation truth check; **measurement** всё равно идёт исключительно через
существующий dense producer, не через этот full construction decode/probe.

Recipes имеют IDs `L`, `L-B04`, `Y`, `DECODE-RGB`, `COPY4`.
До generation hash UTF-8/LF текста §5 и canonical expanded argv templates;
до outcomes также generator/harness files, environment snapshot, ordinal maps,
source и каждого derivative. Файловые hashes не подменяются descriptor hashes.
При обновлении executable/source/recipe требуется новый freeze record до run;
текущий протокол не допускает молчаливого fallback.

Источники интерфейсов: [FFmpeg libx264/libx264rgb](https://ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb)
(RGB input, codec options) и [FFmpeg advanced options](https://ffmpeg.org/ffmpeg.html#Advanced-options)
(encoder time base, passthrough), просмотрены 2026-10-01. Возможности конкретной
сборки подтверждены local help и SHA выше, не живой web-страницей.
Метод/генератор — first-party proposal; правовая граница внешних executables
и прежних NumPy/FFmpeg определена в [REFERENCES](../REFERENCES.md), разделах
«Внешние FFmpeg / ffprobe» и «Dense video foundations M1-F». Их поставка и
лицензионный допуск не меняются; сторонние код, weights и dataset не добавлены.

## 6. Аналитические oracles и детерминизм

### 6.1. Независимый scalar oracle

Будущий prototype сравнить с простым scalar reference на Python int/Fraction,
не использующим vectorized descriptor/distance helpers. Следующие expected values
выведены аналитически, **не результаты выполнения M4-R2-P**. Ровно те же
формулы/ordering/eligibility должны выполняться без tolerance.

| Oracle | Вход и ожидаемый результат |
|---|---|
| Identical | a=b для любой четырёхкадровой группы: N_color=N_delta=0, T_a=T_b; T не обязан быть нулём |
| Symmetry | Swap a/b сохраняет D_color/D_delta, меняет местами T/gaps/identity; unordered enumeration всё равно одна строка |
| Rounding | A=2,S=1→q=1; A=3,S=1→0; A=3,S=2→1; A=4,S=2→1; A=1,S=255→255. W=17,H=10 проверяет все неравные cells без потери edges |
| Constant black/white | a=[0,0,0,0], b=[255,255,255,255] во всех C: D_color=1, D_delta=0, T_a=T_b=0 |
| Joint maxima | a=[0,255,0,255], b=[255,0,255,0] во всех C: N_color=440640, N_delta=660960, T_a=T_b=1 |
| One-cell change | a=0, у b ровно q[t=1,cell=0,R]=1, прочие 0: N_color=1, N_delta=2, N_Ta=0, N_Tb=2 |
| Reversed sequence | a=[0,1,2,3], b=[3,2,1,0] во всех C: N_color=3456, N_delta=2592, D_color=2/255, D_delta=1/255, T_a=T_b=1/255 |
| Static descriptor collision | W=32,H=18, каждый 2×2 block/channel `[0,2;2,0]` либо `[2,0;0,2]`: оба q=1. Даже при чередовании microtextures pixels меняются, D_color=D_delta=T=0 |
| Rational PTS | ticks 0,1,3,6 при base 1/3: gaps 1/3,2/3,1. Та же шкала с ticks 0,2,6,12 при 1/6 равна точно; это scalar arithmetic oracle, не два stream bases в одном manifest |
| Large signed PTS | ticks `-2^62+[0,3,7,12]`, base 1001/30000: gaps 1001/10000,1001/7500,1001/6000; subtraction/multiply не переполняют Python int |
| Pair boundary | same window starts 0/4 исключить, 0/5 включить; same group исключить; cross windows с равными endpoints или overlap исключить, с strict separation включить |
| Enumeration | n=3→0 групп; n=4→1 группа, 0 пар; n=9→6 групп, 1 same-window пара; n=32→29 групп, 300 same-window пар; 3 полных разнесённых окна→87/3423 |
| Undefined | missing validity bit PTS, duplicate/nonmonotone PTS, n<4, small geometry, incompatible geometry/profile, no pairs; точные statuses §2.5, не NaN/нулевой forensic signal |
| Binding failure | Другой UUID/source SHA/timing role/provenance/reference, неверная numeric length: rejection существующим boundary или INPUT_FAILURE, без successful rows |

Malformed binding/length checks — negative test inputs, не выпуск файлов,
выдаваемых за валидный producer output. Descriptor collision/normal cut/static
являются необходимыми контрпримерами forensic specificity, а не поводом
добавлять threshold или удалять источник.

### 6.2. Три независимых fresh-process runs

После protocol acceptance и freeze файлов выполнить три повтора каждого
admitted case: новый Python process, новый controlled workspace, новый intake,
полный dispatcher/decode, numeric read, descriptors и все pair rows.
Один case за раз; не reuse artifacts, descriptors или inherited process state.
Frozen input files не перекодируются между repeats; regeneration recipes
проверяется отдельно как construction, не смешивается с extraction determinism.
Таким образом lossless/lossy/B04 VFR/B03 high-fps обязательно проходят новый
extraction трижды, а не только повторение arithmetic над одним массивом.

Equality projection сохраняет source/case hashes, stream/region/profile,
geometry, requested/observed timing, validity masks, ordinals, PTS/gaps,
artifact logical IDs, descriptor bytes/hash, eligible set, integer numerators,
fractions, row order, truth/support/classification и baseline metrics.
Transient `decode_operation_id`, analysis/workspace IDs/paths, elapsed/RSS
исключаются из межзапускового equality **после** проверки связей внутри run.
Operation UUID проецируется в стабильный token `(case_id,stream,region,dense)`;
проверить, что pixel/timing references действительно соответствуют ему,
а разные decode operations не были случайно склеены. Ошибки binding не маскируются
удалением UUID. Failure phase и support reasons также сравниваются.

Dense raw RGB SHA-256 вычисляется потоково как determinism diagnostic, не
per-frame forensic registry; его различие отмечается даже при равных descriptors.
Побитовое равенство input, output arrays и exact fractions — единственный pass.
Float presentation/UUID/RSS/wall time не участвуют. При расхождении сохранить
все repeats и причину, без majority vote, tolerance или выбора лучшего run.
Неудача ресурса не доказывает numeric nondeterminism, но инженерный gate не пройден.
После исправления harness все три repeats затронутого frozen stage повторяются,
исходный failure остаётся в ledger; изменение профиля требует owner gate.

## 7. Ресурсный план и lifecycle

| Ограничение | План/аналитический расчёт |
|---|---|
| Producer | Без изменений: ≤3 windows, ≤32 frames/window, ≤96 total; ≤2 s/window; native/output caps §2 |
| Descriptor storage | `96*432=41472` bytes uint8; если нужен отдельный signed view всех descriptors, ещё 331776 bytes |
| RGB reader | Одно окно `32*640*360*3=22118400` bytes; никаких трёх RGB windows одновременно |
| Working numeric RAM | Budget 64 MiB: допускаем консервативно два window buffers при read (`44236800`), один signed int64 frame (`5529600`), descriptors/signed copy (`373248`), timing (`6912`), scratch ≤4 MiB: всего 54340864 bytes <67108864. Предпочтительно sum cell view с dtype=int64 без полного cast кадра |
| Pair arithmetic | `3741*(4*432+3*432)=11312784` component differences; deltas/T вычислять по группам или одной паре, не pair×frame×pixel tensor |
| Existing storage quotas | ≤256 generated artifacts, manifest≤16 KiB, metadata≤32 KiB, ≤16 representations, timing≤1 MiB. Video generated budget baseline 200 MiB включает legacy PNG и dense, source учитывается отдельно |
| Existing process limits | Dense timeout min(30 s, remaining), probe min(15 s, remaining), stdout bounded frame bytes, stderr≤256 KiB; существующий admission ceiling два forensic calls/interpreter, исследование всё равно последовательно |
| Case wall deadline | ≤600 s с construction/preparation/intake/measurement; использовать монотонное время и remaining budget, вложенный dispatcher не начинает новый 600 s после preparation |
| Measurement | Цель и stop ≤30 s для numeric read/descriptors/pairs/output; при превышении TIME_RESOURCE_FAILURE, без меньшего search space |
| RSS | Parent + все активные children; наблюдение каждые 100 ms, также на start/exit/phase boundaries. При наблюдаемой сумме >1073741824 bytes остановить case, записать RSS_RESOURCE_FAILURE |
| Pair output | ≤4 MiB/case/run, все eligible rows или incomplete failure; никаких top-k |

RSS — operational observation, **не OS-enforced hard quota** и не доказанный
worst-case. Записываются peak observed, реальный максимальный sampling gap,
PID/parent chain и пропуски наблюдения. Будущий Windows harness может читать
working set через standard-library ctypes/Win32 и отслеживаемые child handles;
новая dependency не нужна. Недоступное наблюдение помечается
RESOURCE_MONITOR_UNAVAILABLE: инженерный gate не пройден, повтор не идёт молча
без monitor. Нельзя складывать независимые individual peaks как одновременный
RSS; суммируются observations одного sampling sweep, его длительность сохраняется.
Короткие пропущенные пики остаются ограничением sampling.

Один case и его children завершаются до следующего. SIG/terminate/kill/reap
и unresolved-process barrier сохраняют существующие правила: нельзя удалять
workspace, пока reader/process safety не подтверждена. Dense artifacts создаются
через `WorkspaceArtifactRegistry` до записи и `_GeneratedArtifactBudget.open_output`;
в конце `WorkspaceCleanup` освобождает controlled source copy и generated data.
Research harness не обходит producer direct FFmpeg measurement, quota или registry.
Если подтверждение reap/cleanup вывело фактический wall time за 600 s, case
не проходит resource gate; время не скрывается и barrier не снимается ради deadline.
Construction originals/derivatives — отдельный внешний корпус с собственными
правами retention; контролируемая intake copy не является archival original.

Global external research workspace **≤4 GiB (4096 MiB)**, включая временные
файлы и все три repeats. Preflight allocations:

| Категория | Максимум MiB |
|---|---:|
| Все frozen originals, ancestors и derivatives вместе | 1920 |
| Pair outputs: 96 cases × 3 runs × 4 MiB | 1152 |
| Descriptors, maps, manifests, telemetry, protocol/review | 128 |
| Generated artifacts одного active case | 200 |
| Construction scratch, bounded streaming files | 256 |
| Controlled source copy и intake overhead | 32 |
| Резерв до общего cap | 408 |
| Всего | 4096 |

Cap media 20 MiB/case применяется и к derivatives; лимит 1920 MiB охватывает
также ancestors R09/R10, а не только case files. Нет сохранения full rawvideo
500-frame/600-frame dumps: generator/decode/encode соединяются bounded stream,
buffer Copy4 ≤4*1280*720*3=11059200 bytes, плюс один текущий frame.
Construction scratch очищается после подтверждённого завершения процессов.
На каждую будущую запись проверяется оставшийся global budget; превышение
останавливает generation/run, не вызывает удаления чужих файлов, сокращения
корпуса по outcomes или увеличения quota. После каждого run сохранить evidence
и очистить его dense/legacy artifacts штатным lifecycle. 64 MiB — budget
descriptor working memory, не суммарный RSS Python/FFmpeg.

## 8. Два этапа и execution gates

### 8.1. Stage A — engineering/procedural

Ровно запланированные 42 procedural + 6 boundary slots, сначала construction
postconditions и analytic oracles, затем три fresh-process repeats frozen
inputs. Проверяются descriptor arithmetic, pair enumeration, truth/support,
coverage misses, resize/rounding, deterministic extraction, ресурсы, static,
periodic, slides/cut/flash confounds. Пропуски/NOT EXECUTABLE cells остаются
в полной матрице, даже если 48 successful cases получить нельзя.
Результат Stage A обязательно **SYNTHETIC_ONLY**. Он не устанавливает
real-world forensic usefulness и не проходит real-source added-value gate.

### 8.2. Stage B — real-source challenge

**BLOCKED / REAL_CORPUS_NOT_ADMITTED**. R01–R12 — запланированные slots,
а не существующие/admitted research evidence.

До 12 admitted independent source groups × 4 variants. Stage B разрешается
только после protocol acceptance, отдельного разрешения M4-R2-E и admission
файлов/прав/provenance/hash manifest. Stage A engineering failures сначала
разрешаются; источник для «улучшения результатов» не подбирается. При менее
12 admitted groups показать незаполненные slots и ограниченное покрытие категорий.
При менее двух eligible independent real groups added-value gate заведомо
NOT DEMONSTRATED; synthetic groups его не заменяют.

### 8.3. Baseline и decision rules до outcomes

Baseline — существующий `video_sampled_frame_quality@1.0.0` на legacy PNG
того же case и frozen config. Сохраняются `sampled_frame_count`,
`compared_adjacent_pair_count`, `dimension_variant_count`,
`exact_duplicate_pair_count`, `longest_exact_duplicate_run_samples`,
`longest_exact_duplicate_span_seconds`, first/last target timestamps и interval.
Comparison основан на width/height/mode/decoded bytes, а не PNG encoding.
Внешний harness может вызвать существующий analyzer для получения raw metrics;
не запускать FindingFormation/risk pipeline и не публиковать candidate Findings
как VRC результат. Target timestamps baseline не приписываются dense frames
как measured PTS. Новый analyzer или независимый forensic vote не создаётся.

| Gate | Заранее заданное правило |
|---|---|
| G0: разрешение | Владелец принимает конкретные P1 formulas, manifest/recipes/oracles/limits и их SHA-256, затем отдельно разрешает M4-R2-E. Протокол принят 2026-10-01; отдельное разрешение M4-R2-E ещё требуется |
| G1: construction/admission | Все исполняемые cells имеют проверенные files, rights, source/derivative hashes, clock/maps и recipes; непригодные/недостающие явно в ledger до measurements. B без реальных файлов закрыта |
| G2: engineering | Все analytic/determinism/resource assertions пройдены; ни одной false coverage/localization claim. Любой непроверенный обязательный assertion — NOT PASSED; failure устраняется в scope prototype либо профиль останавливается |
| G3: controlled measurability | Для eligible exact copy constructions D_color=D_delta=0; отсутствие поддержки — coverage miss, не pass. Для confounds также сохраняются нули/ties; baseline metrics выводятся рядом |
| G4: added measurability M4-R1 | Минимум **две независимые реальные source groups**: у заранее заданной eligible меняющейся truth pair в V02 нулевые D_color/D_delta; в V04 после fixed Y `D_color(truth)<D_color(control)` для назначенного (8,20). T/gaps и D_delta публикуются отдельно. Для каждой засчитанной группы показать, какое соответствие (4,16) не описывает adjacent exact-run baseline |
| G5: disposition | Если полезного добавочного наблюдения нет, либо остаются только неспецифичные static/periodic/normal-edit эффекты — RESEARCH_ONLY или DEFER с причиной. Даже успех G4 допускает лишь предложение отдельной validation, не production promotion |

Для G4 «меняющаяся» означает наблюдаемый **ненулевой** N_T у обеих exact
групп V02, а не fitted cutoff. Это проверка отсутствия полного descriptor
constancy, не новый dynamic threshold; все T=0 pairs остаются в output.
G4 считается по заранее назначенным real pairs, не по лучшему рангу среди
тысяч пар. Control берётся из того же V04, untouched ordinals (8,20);
V01/V03 показывают те же позиции без вмешательства. Если Y дал T=0, tie,
reversal of ordering, ineligibility или missing support, это явно сообщается;
нельзя заменить control, выбрать D_delta вместо D_color или скрыть failure.
Один group засчитывается максимум один раз, независимо от variants/repeats.
Все group outcomes, counts eligible/ineligible/missing и ties публикуются,
без заявления population accuracy/FPR. Наличие G4 у двух групп — только
малый pilot gate, не достаточное доказательство forensic specificity.

G4 сохраняет правило M4-R1 «ниже назначенного control после lossy export»;
ничего не говорит об универсальном пороге или идентификации манипуляции.
Если baseline уже описывает всё полезное наблюдение, G5 требует отрицательного
disposition даже при малых distances. Benign controls не удаляются и не
объявляются ошибками измерения из-за малого D_color/D_delta.

### 8.4. Что предоставляется владельцу

Владелец явно принял весь рассмотренный P1 2026-10-01 в M4-R2-P-A:
formulas, corpus manifest, transform recipes, truth/control mappings, oracles,
resource limits и G0–G5. Техническое содержание P1 сохранено без изменений.
Любое материальное изменение после freeze требует документированной новой
версии протокола и отдельного OWNER GATE с сохранением предыдущего протокола
и ledger. Молчаливая правка P1 и outcomes-driven tuning запрещены.

Для Stage A сохранены два engineering watchpoints: lossless libx264rgb
derivatives могут превысить 20 MiB; полный JSONL всех eligible pairs может
превысить 4 MiB/case/run. Это риски будущей feasibility verification, не outcomes.
При превышении записать engineering failure и остановить затронутый case
по P1. Нельзя менять limits, recipes, output semantics или pair selection;
оптимизация по forensic measurement outcomes не разрешена.

В репозитории только этот report и узкие status/gate ссылки METHODS/ROADMAP.
Внешний research root:
`C:\Users\Vanur\Desktop\FakeDetector-Work\research\M4-R2-VRC\`.
Тематические snapshots: `protocol-predeclaration.md` (§1),
`profile-specification.md` (§2), `fixture-manifest.md` (§3),
`corpus-readiness.md` (§4), `transform-recipes.md` (§5),
`oracle-and-determinism-plan.md` (§6), `resource-plan.md` (§7),
`execution-gates.md` (§8). Каждый ссылается на SHA-256 полного report;
snapshots не имеют отдельной нормативной силы и сохраняют историческое
состояние M4-R2-P до записи принятия; финальный hash указан в acceptance bundle.

Review root:
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M4-R2-VRC-protocol\`:
`review-summary.md`, `complete.diff`, `git-status.txt`.
Complete diff обязан включать полностью новый untracked report, без staging.
Проверки этой protocol-only задачи: `git diff --check`, review полного intended
diff и итоговый status; дополнительно согласованность формул/счётов/ссылок и
полноты review bundle. Tests, full quality barrier, certification, corpus
generation, measurements и real acquisition не выполняются.

Запись M4-R2-P-A предоставляется для owner review в подкаталоге `acceptance/`
review root: acceptance-only.diff, complete.diff (включая полный untracked report),
review-summary.md, git-status.txt и protocol-sha256.txt. SHA-256 финального report
после acceptance edits хранится только снаружи и служит reference для M4-R2-E.
Hashes ещё не созданных generator/harness/media не заявляются: их фиксируют
до соответствующих экспериментальных measurements по P1.

Следующая задача — **M4-R2-E / Stage A**, с отдельным разрешением исполнения.
Stage A (42 procedural + 6 boundary cases) в M4-R2-P-A не выполняется;
Stage B остаётся **BLOCKED / REAL_CORPUS_NOT_ADMITTED**. Synthetic-only результаты
не удовлетворяют real-source added-value gate. Принятие протокола основано
на явном решении владельца, не self-report агента. Macro 4 и Stage 12 остаются
IN_PROGRESS; Macro 3 закрыт и strictly certified; VCM-FRAME-1
TARGETED_RESEARCH / INACTIVE; production-каталог из пяти анализаторов сохранён.
