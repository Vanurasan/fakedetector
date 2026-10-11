# M4-R1 — выбор видеоизмерения и план исследования

Дата: 2026-10-01. **METHOD SELECTION / RESEARCH PLAN ONLY**.
**M4-R1 — DONE / OWNER ACCEPTED METHOD SELECTION**: владелец явно принял
исследовательское направление 2026-10-01 в M4-R1-A. Production-метод не принят;
forensic specificity ещё не установлена.
Эксперименты, новые измерения и прототипы в M4-R1 не выполнялись.

Принято основное направление **VRC-DENSE-1 — PROTOTYPE_NEXT /
OWNER ACCEPTED RESEARCH DIRECTION**:
соответствие разнесённых меняющихся четырёхкадровых последовательностей внутри доступных
dense-окон. Это исследование расширения ответственности
`video_sampled_frame_quality`, а не предложение нового analyzer ID.
Вторичный кандидат **VCM-FRAME-1 — TARGETED_RESEARCH / INACTIVE**: сохранность
пространственного copy-move correspondence после video decode.
Production method, thresholds, Findings, severity/risk и catalog registration
этой записью не разрешены.

## 1. Основания и границы свидетельств

| Тип свидетельства | Что использовано |
|---|---|
| REPOSITORY FACT | Read-only проверка ветки `feat/stage12-macro3-audio-analyzer-expansion-wave1`, HEAD `c4488109e56c90c3b715779ad7d11f900b51c5b8`, чистого начального status; чтение перечисленных ниже исходников и тестов |
| ACCEPTED PROJECT EVIDENCE | Нормативные PROJECT §6.8/§6.10/§16, CONTRACTS §7.4–7.5, gate METHODS, закрытые M1-E/F/G и dispositions Macro 2/3 в ROADMAP. По явному заданию владельца Macro 3 уже DONE / CLOSED / OWNER ACCEPTED / STRICTLY CERTIFIED; повторная сертификация и переоткрытие не выполняются |
| EXTERNAL LITERATURE | Только официальные определения FFmpeg/ffprobe из уже используемых проектом источников; §8. Это интерфейсная документация, не доказательство forensic specificity |
| INFERENCE | Оценки полезности, сложности, потери сигнала и риска confounds выведены из доступных представлений. Это не измеренная точность и не population FPR |
| PROPOSED HYPOTHESIS | VRC-DENSE-1 и будущая матрица §7 — собственное предложение измерения; работоспособность и добавочная ценность ещё не продемонстрированы |

Полностью прочитаны AGENTS, PROJECT, CONTRACTS, METHODS, ROADMAP, REFERENCES,
README; дополнительно `docs/research/README.md`.
Graphify **STALE**: provenance source SHA
`625b9e83f133fb0ae31a4b90e9e1288bff96f69c` не равен baseline.
Граф не использовался как свидетельство и не пересобирался.

Основные проверяемые указатели: полные пути — от корня репозитория;
сокращённые source-пути — от `src/fakedetector/`, имена preprocessing
`_media_tools.py`/`_models.py` — внутри `preprocessing/`. Тестовые символы
без пути находятся в указанном рядом test-файле.

| Область | Файлы и символы / проверяемые тесты |
|---|---|
| Intake и validation | `src/fakedetector/intake/validation.py`: `_safe_read`, распознавание контейнера; `intake/media_tools.py`: `probe`, `decode_video`, `video_parameters`; `tests/test_file_validator.py`, `tests/test_media_tools.py` |
| Legacy video | `preprocessing/_service.py`: `VideoPreprocessor.prepare`, `_video_timestamps`; `preprocessing/_media_tools.py`: `sampled_frame`; `test_video_periodic_sampling_is_deterministic_bounded_png_without_resize`, `test_video_timestamp_plan_applies_internal_resource_cap` |
| Forensic demand и данные | `preprocessing/_requirements.py`, `_models.py`, `_service.py::_prepare_timing_forensic`; `analyzers/_models.py`, `_transport.py`; CONTRACTS §7.5 |
| Timing и dense | `_media_tools.py`: `probe_timing_stream`, `select_timing_regions`, `probe_timing_records`, `decode_dense_window`, `_dense_records`; `tests/test_preprocessing.py`: same-decode, B-frame/VFR/offset, geometry, corruption, resource/cleanup, combined-demand tests |
| A/V | `_models.py::AVTimelineDescriptor.from_timing`; `tests/test_stage5_internal_models.py`: `test_av_regional_mapping_exact_independent_time_bases_and_resets`, missing/unknown tests |
| Каталог и video responsibility | `analyzers/_catalog.py`, `_registry.py`, `_video_frames.py`, `_candidates.py`; `tests/test_stage6_real_analyzers.py`: one/two/three samples, decoded pixels, dimension variants, spawned worker; `tests/test_analyzer_registry.py` |
| Image reuse | `analyzers/_image_metadata.py`, `_image_copy_move.py`, `_image_jpeg_dq.py`; image normalization в `preprocessing/_service.py`; `tests/test_image_copy_move_correspondence.py`, `tests/test_image_jpeg_dq.py`; METHODS DQ и REFERENCES analyzer records |
| CLI и результат | `main.py`, `result_finalization.py`, `templates/result.html`; `tests/test_cli.py`, `tests/test_stage9_e2e.py`; README Profile B |
| Предыдущие исследования | Image DQ, noise/resampling и thumbnail records; `2026-09-26-audio-method-selection.md` и закрывающие Macro 3 dispositions. Они не являются video validation; допуска VISION JPEG нельзя автоматически переносить на видео |

Названия тестов здесь — свидетельство существующих assertions после чтения,
не результаты нового запуска. Фактический каталог содержит ровно пять
`@1.0.0`: `image_metadata_consistency`,
`image_copy_move_correspondence`, `image_jpeg_double_quantization`,
`audio_pcm_quality`, `video_sampled_frame_quality`. Отличий от задания нет.

## 2. Карта текущих video-возможностей

Все факты этого раздела — **REPOSITORY FACT**, контракты сверены с кодом.
«Есть в инфраструктуре» и «запрашивается текущим production-анализатором» различаются.

| Вопрос A–K | Доступно и ограничения |
|---|---|
| A. Input/container | MP4/MOV/AVI/MKV после signature/MIME/extension/size checks; controlled source и SHA-256. Intake исключает attached cover из video-классификации. Проверка декодирования ограничена первой секундой / максимум тремя video frames, не всем потоком |
| B. Video metadata | `VideoTechnicalParameters`: duration_seconds, container, video_codec, optional audio_codec/bitrate_bps, width, height, fps, has_audio. Произвольные tags, edit history, encoder history, rotation/SAR/color/HDR provenance не публикуются этим контрактом |
| C. Duration/streams | Intake берёт duration первого video stream, иначе format duration; fps = валидный avg_frame_rate, иначе r_frame_rate. Исходная пара stream/format duration после этого отдельно не экспонируется. Stream timing по demand хранит собственные declared duration/start, ticks/time base и rates, но не восстанавливает утраченный container-duration fact |
| D. Sampling | `n=min(120,max(1,ceil(duration/interval)))`, targets `i*interval`, начиная с нуля. Default config model interval=2 s, example YAML=1 s; допустим integer ≥1. При cap сохраняется начало, не равномерное покрытие всего ролика; есть warning об отсутствующем хвосте. Название `keyframe_interval_seconds` не означает I-frame extraction |
| E. Representations | Legacy: отдельные PNG `sampled_frame`, без явного resize; first video stream, один кадр на target. Поля artifact: sample ordinal `frame_index`, target start_time. Optional FLAC только при наличии audio, разрешении config и demand. Dense: отдельные source-bound RGB24 numeric windows и timing того же decode — по demand |
| F. Exact timestamps | У legacy только `timestamp_semantics=deterministic_target`; фактический PTS и native frame number не сохранены. У dense есть измеренный PTS в rational stream time base, связанный с конкретными пикселями. Это точность времени наблюдаемого кадра, не доказательство точного момента редактирования |
| G. Adjacent comparison | Да, соседние **samples** можно сравнивать по mode/geometry/decoded bytes. Между ними могут быть десятки исходных кадров. Dense сохраняет последовательные output frames только внутри отдельного окна; через разрыв окон «соседства» нет |
| H. Identity/hash | Есть source SHA-256, artifact IDs и same-decode binding. У legacy нет сохранённого frame hash. Dense сверяет Adler-32 showinfo с raw bytes, но checksum не сохраняется в descriptor и не служит API хэшей повторов. decode_operation_id — идентификатор операции, не хэш содержания |
| I. Image analyzers | Все три зарегистрированы только для IMAGE, video request неприменим. Sampled PNG не является `normalized_image` image route; RGB24 numeric array не PNG. Часть pixel kernels технически переиспользуема отдельным исследованием, но прямой analyzer wrapper нарушит предпосылки (§4) |
| J. Потери | Пропущенные кадры/короткие вставки/точные границы; у legacy — PTS и cadence. Decode не сохраняет native JPEG coefficients/DQT, codec residuals/QP/motion vectors/packet structure. Dense дополнительно уменьшает пространственную детализацию и оставляет большие временные разрывы |
| K. Нет full-stream forensic API | Нет полного frame census, полного packet/GOP scan, QP/bitstream parser, optical flow, track/face/ASR/lip-sync pipeline или доказанной полной A/V синхронизации. Source capability не является разрешением обходить общего preprocessing producer |

### 2.1. Доступные on-demand foundations M1

Текущий `video_sampled_frame_quality` не запрашивает forensic capabilities.
Однако существующий `PreprocessingRequirements` уже поддерживает на video route
`stream_timing`, `timing_records`, `dense_video`, `av_timeline`,
а также audio precision/samples/spectral. Image capabilities на video route запрещены.

- **Stream timing:** первый video и первый audio stream, если есть;
  точный rational seconds/tick, signed start/PTS/DTS, nonnegative duration,
  отдельные declared decimals, avg/r rates. Отсутствующее значение остаётся
  unknown, rates не доказывают CFR.
- **Generic records:** до трёх номинальных двухсекундных регионов начало/середина/
  конец, overlapping regions объединяются; unknown duration → только начало.
  Packet rows: PTS/DTS/duration; video frame rows дополнительно best-effort,
  pkt_duration, key_frame, pict_type. Девять `<i8` columns с validity mask;
  отсутствующий ноль отличим от наблюдаемого нуля. Порядок packet — demux,
  frame — output decoder. B-frame reorder, повторы/немонотонность PTS сохраняются.
- `-read_intervals start%+#N` ограничивает **input packets**, не точную длину
  региона: 256 для packet probe / 512 для frame probe; frame output также ≤512.
  Preroll/выход за nominal stop могут оставаться. Coverage
  empty/unknown/partial/envelope, envelope не означает непрерывность;
  `packet_budget_or_eof` не различает причины остановки. Все rows суммарно ≤4608,
  numeric timing artifacts ≤1 MiB; probe stdout/stderr ≤256 KiB, timeout ≤15 s.
- **Dense:** `ffmpeg_dense/1 : rgb24_bilinear/1`, native ≤3840×2160,
  output ≤640×360, bilinear/no-upscale, без autorotation и display/SAR correction.
  Не более трёх окон, первых 32 последовательных output frames каждого и первых
  двух секунд каждого merged requested region: максимум 96 кадров.
  При 25 fps 32 кадра не покрывают две секунды. Merged region длиной три секунды
  тоже не становится полным dense-окном.
- Dense pixels и `purpose=dense` timing имеют один decode_operation_id,
  artifact reference и producer provenance. PTS измерен в том же filtergraph;
  packet DTS/best-effort/pkt_duration не выдумываются. Generic frame table
  другого decode нельзя привязать ни к dense pixels, ни к legacy PNG.
  Размеры/число/Adler-32 проверены producer; malformed/empty output — ошибка.
- **A/V:** `av_timing/1 : regional_endpoints/1` связывает generic audio packet
  и video frame endpoints регионов. Fraction(audio_time−video_time) — разность
  выбранных endpoint observations, не lip-sync offset, не непрерывный drift.
  missing audio — штатная неприменимость, не подозрение. Для timing/AV demand
  не требуется precision audio/STFT.

Все numeric arrays проходят immutable typed reader, source identity и exact
byte-length проверки; артефакты контролирует workspace lifecycle.
Raw media в result/worker response не помещается. Лимиты суммируются с legacy:
до 256 artifacts, общий generated-byte budget видео по умолчанию 200 MiB,
до 16 manifest representations. Dense RGB worst case —
66 355 200 bytes суммарно, 22 118 400 bytes на окно; это не предел process RSS.
Комбинация dense+generic timing+AV на трёх регионах двух потоков даёт
18 representations и отклоняется preflight, без тихого урезания.
Поэтому primary просит **только DENSE_VIDEO** с существующим dependency closure,
а не все доступные возможности. Legacy PNG при этом всё равно создаются.

Dense decoder/filter/output работают с одним thread, timeout ≤30 s на окно
и оставшимся общим бюджетом. Два forensic calls на interpreter допускаются
без очереди; это не глобальная OS memory quota. Наличие bounded artifacts
само по себе не доказывает bounded peak native RSS.

### 2.2. CLI и результат

`main.py` запускает локальное приложение через uvicorn; отдельной batch CLI
для video measurement нет. HTTP/API и WebUI используют сохранённый результат.
Profile B ожидает только `video_sampled_frame_quality` на video route;
image/audio analyzers к кадрам/дорожке автоматически не подключаются.
`include_raw_metrics=false` удаляет raw_metrics при finalization.
`completeness=complete` означает исполнение сконфигурированного analyzer plan,
а не просмотр всех кадров. Probability остаётся null, preprocessing errors
не преобразуются в Findings. Новый research report не меняет эти правила.

## 3. Ответственность и перекрытия

**REPOSITORY FACT:** `VideoSampledFrameQualityAnalyzer.analyze` сортирует
samples по frame_index, target time, artifact ID. Сравнивает соседние
декодированные кадры целиком: width, height, mode, pixel bytes. Разная PNG
компрессия/metadata не создаёт различия при одинаковых decoded pixels.

| Сейчас измеряется / публикуется | Точная граница |
|---|---|
| Число samples и adjacent pairs, dimension variants | Без анализа blur/noise/семантического содержания или полного codec stream |
| exact_duplicate_pair_count; longest run/count/target span | Два одинаковых samples дают метрику, но не repetition candidate |
| `repeated_sampled_video_frames` | Run минимум из трёх равных соседних samples; interval между их **target** endpoints, не доказанная непрерывная freeze duration; `video_temporal_repetition` |
| `video_sample_resolution_change` | Более одного размера; refs представителей первых двух dimension variants, interval first/last targets; `video_stream_consistency` |
| Ограничение кандидатов | Общий cap 16; dimension candidate занимает место; repeat runs отбираются по длине/target span, затем детерминированно упорядочиваются |

Нет поиска разнесённых групп, near-correspondence, motion compensation,
визуальных cut descriptors или точной локализации вставки.

**ACCEPTED PROJECT EVIDENCE:** ROADMAP «Исследовательский вход и отбор волн»
уже относит усиление повторов/замирания к существующей ответственности,
без дублирующего анализатора. **INFERENCE:** VRC добавляет область измерения
(разнесённые меняющиеся группы), но его DISTINCT_RESPONSIBILITY=PARTIAL.
Исследование можно чисто отделить от текущего adjacent exact-run алгоритма;
отдельную forensic responsibility/независимость от него оно не создаёт.

| Предложение | Владелец / решение |
|---|---|
| Ещё один exact freeze detector с теми же sampled frames | Дублирует текущий video analyzer → REJECT_DUPLICATE_RESPONSIBILITY |
| Decoder error, invalid container, unsupported codec, отсутствие обязательных facts | Intake/preprocessing error/applicability, не Finding → REJECT_DUPLICATE_RESPONSIBILITY |
| VRC-DENSE-1 | Исследование расширения текущей temporal repetition responsibility; production изменение требует нового gate |
| Abrupt transition и timing differences | Иные описательные факты; одна сцена/перекодирование способны породить несколько откликов. Независимые risk votes не разрешены |
| Frame copy-move | Пространственное соответствие внутри кадра; несколько соседних кадров одного события не независимые подтверждения |
| A/V endpoints | Timing observation; не отдельное подтверждение семантической рассинхронизации |

Во всех вариантах: no-signal != authentic; provenance != verdict;
repeated content, cut, codec anomaly и descriptive measurement != manipulation.
Неприменимость, unknown и failure не становятся положительным свидетельством.

## 4. Проверка image reuse

| Анализатор / классификация | Технический вызов | Сохранность предпосылок и pseudo-evidence |
|---|---|---|
| `image_metadata_consistency` — **NOT_APPLICABLE** | Video request отклоняется по media type. Код читает original image source через Pillow, не список sampled PNG | Проверяет EXIF pixel dimensions относительно decoded **source image**, учитывает валидность Orientation; отсутствие EXIF/software tag не Finding. Созданный FFmpeg PNG не хранит доказанную source-image EXIF историю. Проверка его собственных tags описывала бы наш export. Container dimensions/tags — другой контракт; подстановка video facts недопустима |
| `image_copy_move_correspondence` — **NEEDS_TARGETED_RESEARCH** | Direct video request неприменим; нужен IMAGE + один normalized_image PNG RGB/RGBA. ORB/RANSAC pixel primitives технически пригодны для отдельного внешнего исследования | Пространственно разделённые соответствия могут сохраниться, но decode/chroma subsampling/resize/компрессия меняют keypoints и геометрию. Исходные image thresholds нельзя объявить video-валидированными. Повторяющиеся окна/плитка/текст/UI/логотипы — обычные положительные соответствия. Bbox относится к sampled raster; устойчивость по времени не доказывает монтаж |
| `image_jpeg_double_quantization` — **INVALID_AFTER_VIDEO_DECODE** | Нужны IMAGE original JPEG identity, clean native quantized coefficients и исходные DQT; JPEG_COEFFICIENTS недопустим на video route | PNG/RGB24 не сохраняют эти входы. DCT decoded RGB или JPEG, повторно созданный из кадра, измеряет новый pipeline, а не исходный DQ. Даже MJPEG в контейнере не предоставляет автоматически source JPEG manifest/coefficients через текущий путь. Codec QP — не JPEG DQT |

**ACCEPTED PROJECT EVIDENCE:** DQ-HIST-1/DQ-R3C-1 принят для ограниченного
image JPEG recompression-history сценария; это не допуск video DQ.
Copy-move использует bounded ORB ≤5000 keypoints, минимум 128 px по каждой
оси, максимум 12 MP, до четырёх clusters/восьми bbox candidates, один OpenCV
thread и отключённый OpenCL. Эти bounds не делают анализ 120 кадров бесплатным.
Нормализованный image PNG, original raster/coordinates/JPEG/residual capabilities
имеют image route semantics; ими нельзя «переименовать» video frame.

**PROPOSED HYPOTHESIS:** вторичный VCM-FRAME-1 сначала сопоставляет
известный spatial copy и benign repeated texture до/после encode/decode.
Достаточно отдельного целевого изучения ≤12 заранее выбранных кадров,
последовательно, с текущими pixel/resource bounds; codec/scale controls и
native-to-raster mapping обязательны. Это не вторая задача реализации
параллельно VRC и не разрешение wrapper/config/catalog изменений.

## 5. Кандидаты и descriptive scorecard

ID ниже — research labels, не analyzer IDs. Для каждого FORENSIC_QUESTION
дан в первой таблице; остальные поля во второй имеют ровно требуемые значения.
Числового общего score или рейтинга нет.
Все confounds — **INFERENCE**, подлежащие проверке, а не измеренная частота.

| ID / семейство / FORENSIC_QUESTION | Представление и физический сигнал | Confounds, ресурсы и реалистичная validation path |
|---|---|---|
| VQ-ADJ-1 / A: есть ли run точных равенств соседних samples? | Legacy PNG, decoded equality и target span | Static/low-motion, slides, surveillance, loops, screen recordings; O(n·pixels), n≤120, по два кадра. Уже покрыт production tests; отдельный метод не нужен |
| **VRC-DENSE-1 / A: насколько близки пространственный вид и порядок изменений двух разнесённых четырёхкадровых групп?** | Dense RGB + same-decode timing; L1 block-color и temporal-difference distances (§7) | Static/periodic motion, animation loops, screens/slides, повторный показ одной сцены, повторное кодирование; ≤96 frames, ≤3741 group pairs. Controlled copies + untouched real clips; измеряет correspondence, не намерение |
| VTD-DIFF-1 / B: насколько различаются соседние наблюдаемые кадры? | Legacy/dense pixels; нормированная абсолютная RGB-разность, для dense отдельный PTS gap | Обычные cuts, pan/zoom, flash, lighting, scene changes, animation/effects. O(n·pixels), ≤119 legacy / ≤93 dense adjacent pairs, без сравнения через gaps. Генерируемые cuts и обычные съёмки доступны, но специфичность монтажа не следует |
| VIM-META-1 / C: согласуются ли image metadata и raster кадра с происхождением видео? | Нужной source-image EXIF связи нет; generated PNG tags не заменяют её | Нормальный export/metadata stripping; вычисления малы, но нужное измерение неопределимо. Проверка отсутствия input возможна, validation forensic-гипотезы на этом input — нет |
| **VCM-FRAME-1 / C: сохраняется ли геометрически согласованное внутрикадровое correspondence после video decode?** | Pixel ORB/RANSAC primitives, sampled raster и его размеры | Repeated texture/UI, camera motion/compression; до 12 кадров в целевом исследовании, ≤5000 features/кадр. Controlled spatial copy + benign repetition, с encode/resize controls |
| VIJ-DQ-1 / C: сохраняется ли native JPEG DQ measurement на decoded video frame? | Требуемых source JPEG coefficients/DQT нет | Новое JPEG-сохранение создаёт собственный след; RGB DCT не замена. На текущем input честной validation нет; стоимость/порог от image DQ не переносится |
| VTS-REGION-1 / D: какие различия declared timing и наблюдаемых PTS/durations есть в регионах? | Stream facts + generic masked rows; rational gaps, order/counts, endpoint-vs-declared observations | VFR, B-frames, seek/preroll, edit lists/start offsets, mux/encoder delay, missing fields, ограниченный probe. ≤4608 rows; generated CFR/VFR/offset/reset fixtures доступны. Полный declared-vs-decoded duration и container-vs-stream comparison не обеспечены |
| VVAL-1 / D: прочитан ли контейнер и соблюдены ли обязательные параметры? | Существующие validation/preprocessing outcomes | Corrupt/unsupported/unknown input — отказ, не forensic evidence. Повторный decode увеличивает расходы без новой ответственности; текущие validation tests уже владеют задачей |
| VGOP-STRUCT-1 / E: можно ли связать нарушение codec/GOP структуры с повторным монтажом? | Частичные key_frame/pict_type есть; полного GOP, QP, motion vectors, residual/bitstream syntax нет | Scene-adaptive GOP, rate control, normal transcode, packet loss. Нужны отдельный bounded source parser/codec profile и validation corpus; стоимость сейчас не определена. Не считать наличие FFmpeg разрешением codec internals |
| VAV-ENDPOINT-1 / F: различаются ли времена выбранных audio/video endpoints региона? | Существующий AVTimelineDescriptor, точные rational offsets | Independently sampled endpoints, audio encoder delay, preroll, разная coverage. Generic timing cost + скаляры; synthetic offset/missing-stream controls доступны. Не измеряет смысловую синхронность |
| VAV-SEMANTIC-1 / F: совпадает ли речевое/видимое событие во времени? | Нет speech/face/event correspondences; timing+FLAC не создают их | Dubbing, off-screen sound, music/effects. Нет выбранного bounded deterministic метода; типичный face/ASR/model путь требует новых dependencies/rights и OWNER GATE. Концептуально DEFER, без optical-flow/ML stack |

| ID | CURRENT_INPUT_SUPPORT | DISTINCT_RESPONSIBILITY | CPU_OFFLINE_FEASIBLE | NEEDS_NEW_DEPENDENCY | BENIGN_CONFOUND_RISK | MEASUREMENT_CAN_BE_PREDECLARED | VALIDATION_DATA_REALISTIC_FOR_DIPLOMA | RECOMMENDED_DISPOSITION |
|---|---|---|---|---|---|---|---|---|
| VQ-ADJ-1 | READY | NO | YES | NO | HIGH | YES | YES | REJECT_DUPLICATE_RESPONSIBILITY |
| VRC-DENSE-1 | READY | PARTIAL | YES | NO | HIGH | YES | YES | PROTOTYPE_NEXT |
| VTD-DIFF-1 | READY | PARTIAL | YES | NO | HIGH | YES | YES | RESEARCH_ONLY |
| VIM-META-1 | MISSING | NO | YES | NO | HIGH | NO | NO | RESEARCH_ONLY |
| VCM-FRAME-1 | PARTIAL | PARTIAL | YES | NO | HIGH | PARTIAL | YES | TARGETED_RESEARCH |
| VIJ-DQ-1 | MISSING | NO | PARTIAL | NO | HIGH | NO | NO | DEFER |
| VTS-REGION-1 | PARTIAL | PARTIAL | YES | NO | HIGH | PARTIAL | YES | RESEARCH_ONLY |
| VVAL-1 | READY | NO | YES | NO | HIGH | YES | YES | REJECT_DUPLICATE_RESPONSIBILITY |
| VGOP-STRUCT-1 | PARTIAL | PARTIAL | PARTIAL | NO | HIGH | PARTIAL | PARTIAL | DEFER |
| VAV-ENDPOINT-1 | READY | PARTIAL | YES | NO | HIGH | YES | YES | RESEARCH_ONLY |
| VAV-SEMANTIC-1 | MISSING | YES | PARTIAL | YES | HIGH | NO | PARTIAL | DEFER |

NO в NEEDS_NEW_DEPENDENCY не обещает готовность: для VGOP собственный parser
тоже новая инфраструктура и требует gate; зависимость ещё не выбрана.
YES у semantic A/V относится к рассмотренному model/face/ASR пути, не утверждает
невозможность всех мыслимых простых сигналов. VIM/VIJ отклонены именно как
image reuse; их research-only/defer записи не разрешают псевдоизмерение.
READY у VRC означает наличие approved producer, а не готовую production activation.

Причина выбора VRC — проверяемая добавочная область наблюдения: разнесённые
меняющиеся группы вместо уже реализованных adjacent exact runs. Она имеет
доступный source-bound input, небольшой полный перебор и простую truth-map
проверку. Discontinuity дешевле, но обычный cut уже создаёт искомую разность;
timing прежде всего описывает mux/decode workflow; GOP и semantic A/V требуют
неподготовленных входов. Это основание приоритета малого эксперимента,
не доказательство большей forensic точности VRC. Copy-move имеет подходящие
pixel primitives, но ещё требует проверки сохранности image assumptions.

## 6. Ограничения sampling по кандидатам

**INFERENCE из §2.** Ниже «локализация» относится к наблюдению, не к границе
манипуляции. Рост частоты требует новых resource calculations и не разрешён
в M4-R1; current caps автоматически не повышаются.

| Temporal кандидат | Короткое событие между samples | Сохранность повторов | Точная локализация | Допустимый охват | Цена более частого наблюдения |
|---|---|---|---|---|---|
| VQ-ADJ-1 | Может быть полностью пропущено | Несколько repeated native frames могут не дать трёх равных samples; одинаковые samples не доказывают freeze между ними | Только targets, не measured PTS | Первые ≤120 targets, хвост после cap отсутствует | Больше PNG/decode/I/O до cap; при меньшем interval cap достигается раньше |
| VRC-DENSE-1 | Вне трёх окон, после 32-го кадра и на границе окна событие пропускается | Нужно обе группы целиком; пропуск/сдвиг cadence/resize может уничтожить соответствие. Периодическое содержание может дать его без вставки | Точные PTS четырёх наблюдений; не начало/конец вставки | Только допустимые пары внутри/между retained windows, без соединения gaps | Больше frames/windows означает рост RGB bytes и числа pair comparisons квадратично по числу групп; дополнительные лимиты не разрешены |
| VTD-DIFF-1 | Краткий cut/flash и обратный переход между samples невидимы | Сам не detector повторов; sampling может сделать соседние samples равными или несходными | Legacy targets / dense measured pair endpoints, не transition boundary | Только sampled adjacent pair; через dense gaps сравнение не интерпретируется | O(n·pixels) плюс decode/storage; более высокая fps сама меняет величину adjacent difference |
| VTS-REGION-1 | Anomaly вне probes/после packet cap пропускается | Packet/frame counts не доказывают visual duplicate, missing rows маскируют cadence | Наблюдаемые ticks, не полный timeline и не attachment к legacy pixels | Региональные packet/frame observations; envelope не full coverage | Больше probes/rows/native decode, новые output/time budgets; более частые PNG не добавляют packet facts |
| VGOP-STRUCT-1 | GOP boundary вне probe невидима | Pixel sampling не сохраняет codec history; key/pict_type недостаточны | Только имеющиеся frame ticks, не вся GOP структура | Частичные observations; полного анализа нет | Нужен отдельный source parser/bounded scan; увеличение PNG sampling не возвращает QP/residuals |
| VAV-ENDPOINT-1 | Короткая рассинхронизация между регионами невидима | Не visual repetition measurement; sparse endpoints не описывают повтор | Exact endpoint offsets не есть offset одного общего события | Независимые audio/video regional observations | Больше generic probes и coverage, representation cap; увеличение только PNG sampling не помогает |
| VAV-SEMANTIC-1 | Sparse support пропускает событие; content correspondence отсутствует | Повторное содержание не обеспечивает парность звука и изображения | Сейчас неприменима | Семантического утверждения сделать нельзя | Потребовались бы content pipeline и отдельный бюджет/owner gate |
| VCM-FRAME-1, если расширять вывод во времени | Пространственная вставка между samples не наблюдается | Повтор внутри одного кадра может пережить decode, временная persistence неизвестна | Bbox в sampled raster + target; dense потребовал бы согласованный geometry mapping | Только отдельно измеренный кадр; нет track | ORB/matching на каждом новом кадре, bounded native memory и суммарное время растут |

Ни отсутствие измерения, ни доля покрытых кадров не превращаются в вероятность
подделки/подлинности. Долю времени нельзя считать как «3×2 s / duration», когда
32-frame cap, gaps, duration metadata или merged regions уменьшают поддержку.

## 7. Следующая активная задача

**M4-R2 — VRC-DENSE-1 Bounded Measurement Prototype**, после owner review
M4-R1-A и commit владельцем. Сейчас M4-R2, media acquisition и измерения
не выполняются. Всё далее — **PROPOSED HYPOTHESIS**: исследовательский протокол,
который нужно зафиксировать до измерений, а не production-спецификация или
уже выполненный эксперимент. Никакой threshold optimization.

### 7.1. Измерение и детерминированный алгоритм

Вопрос: может ли очень малое представление передать соответствие **меняющейся**
четырёхкадровой группы в другом месте retained video, которое не описывается
нынешним exact adjacent-run счётчиком? Измерение — цветовые различия и различия
последовательных изменений в decoded coded-grid RGB. Это не optical flow,
не motion reconstruction и не вероятностная мера редактирования.

Вход: video source из controlled workspace; существующий dispatcher с demand
`DENSE_VIDEO` (dependency `STREAM_TIMING`), manifest и numeric reader.
Не вызывать image analyzers на поддельном IMAGE request.
Не менять producers, legacy sampling, public models, catalog, config или quotas.
Generic timing/AV/audio capabilities для этого профиля не запрашивать.

1. Проверить source identity, producer/profile, frame count, shape,
   same-decode timing binding; читать по одному окну, освобождать RGB после
   извлечения descriptors. Порядок — stream, region, output ordinal.
2. Для каждого RGB кадра шириной W≥16 и высотой H≥9 разделить coded grid на
   16×9 непустых прямоугольников: границы x[j]=floor(j·W/16),
   y[k]=floor(k·H/9). Для каждого из 144 blocks и трёх каналов вычислить
   integer sum S и area A, затем q=floor((S+floor(A/2))/A).
   Это округлённый средний decoded code value, 432 значения 0…255;
   не линейная физическая яркость. Нового resize/цветового преобразования нет.
3. Внутри каждого окна сформировать все группы из четырёх последовательных
   output frames, шаг один кадр, без crossing window boundary.
   Требуются строго возрастающие measured PTS. VFR допустим: полный вектор
   трёх rational PTS gaps сохраняется отдельно; выравнивание — только по
   frame ordinal, без time warp, interpolation или предположения равного fps.
4. Сравнить каждую неупорядоченную пару групп одного source/stream,
   одинаковой native/output geometry и profile. В одном окне между группами
   оставить минимум один неиспользованный кадр: start_b≥start_a+5.
   В разных окнах потребовать a_last_PTS<b_first_PTS (или обратный порядок).
   Самосравнение и overlapping temporal supports исключить, порядок не менять.
5. Для q-последовательностей a,b вычислить целочисленные числители:
   N_color = sum по 4×432 |a−b|;
   N_delta = sum по 3×432 |(a[t+1]−a[t])−(b[t+1]−b[t])|.
   Опубликовать fractions D_color=N_color/(4×432×255),
   D_delta=N_delta/(3×432×510). Отдельно T_a,T_b =
   sum по 3×432 |q[t+1]−q[t]|/(3×432×255).
   T=0 означает лишь отсутствие изменений **descriptor**, не неподвижность
   всех pixels. Никакого cutoff для near match, dynamic или manipulation нет.
6. Сохранить **все** допустимые pair rows в каноническом порядке, без top-k
   retention, score/risk или threshold. ≤3×29=87 групп, ≤3741 пар до exclusions.
   Различия между round-mean descriptors не доказывают различие всех сцен;
   D_color=0 не означает byte-equal pixels. Реестр полных frame hashes не нужен.
7. Для отдельно фиксированных truth pairs и matched controls вывести distances,
   tie counts и положение относительно всех eligible pairs как исследовательскую
   диагностику, без объявления detection. Нынешние legacy exact-adjacent metrics
   оставить baseline comparator, без новой Finding policy.

### 7.2. Данные, controls и поддержка

До измерений зафиксировать manifest, transform recipes, truth mapping и hashes.
Предлагаемый предел — **96 cases**: шесть собственных процедурных источников
× семь заранее заданных вариантов (42), двенадцать собственных реальных
коротких записей × четыре варианта (48), шесть boundary cases.
Один source group, а не каждый derivative, является единицей независимости.
Реальные записи ещё не получены и не считаются admitted corpus.

| Часть | Заранее заданное содержание |
|---|---|
| Procedural sources | Движущийся уникальный текстурный объект; pan по текстуре; static; periodic animation; slide/screen; cut/flash/lighting sequence. Все seeds и траектории фиксируются до outcomes |
| Семь вариантов каждого | Без вставки; копия четырёх динамических frames внутри retained window; та же копия через два retained windows; copy, целиком вне retained support; lossless-reference copy; тот же copy после одного фиксированного lossy export; matched export без copy. Для static/periodic источников это confound controls, не доказательство злонамеренности |
| Real sources | 12 независимых собственных clips: по два static/low-motion, pan/handheld, natural periodic motion, screen/slides, обычный cut/flash/lighting, dynamic nonperiodic. Без чужих защищённых экранных материалов. ≤20 s, ≤1280×720, source ≤20 MiB; фактический fps/rotation/history записать |
| Четыре real варианта | Original; заранее локализованный nonadjacent four-frame copy; fixed lossy export original; тот же export copy. Matched untouched pairs той же длины и temporal separation назначить до distance outcomes |
| Boundary cases | <4 frames; merged three-second request с фактически укороченным dense support; high-fps 32-frame cap; VFR; duplicate/nonmonotone PTS representation; geometry <16×9. Последние непригодные representations проверяются как input/undefined cases, без объявления валидного media producer output |
| Дополнительные confound assertions | Same descriptor при разных microtextures; много равных static/loop групп; декодирование/resize и RGB rounding. Нулевая distance не равна identity и не равна монтажу |

Для positive construction сохранить frame-ordinal map до/после трансформации,
encode command/version и observed same-decode PTS после неё. Копия длиной
четыре frames не обязана пережить lossy export как byte equality.
Placement фиксируется по declared плану, но принадлежность к support оценивается
только по **наблюдаемым** кадрам, без перемещения неудачного случая после outcomes.
Source и target должны присутствовать полностью; вне support — coverage miss,
а не «успешный no-signal». Короткую копию между legacy targets использовать,
чтобы проверить добавочную область измерения.

Lossless reference и один lossy recipe фиксируются в будущей preregistration
по доступному уже установленному FFmpeg encoder/build; никаких установок.
Если нужного encoder нет, отметить непроверенную клетку, не заменить профиль
скрыто. До запуска должны быть записаны точные codec/pixel-format/quality/GOP
arguments и hash recipe: M4-R1 не выдаёт неподтверждённую команду за эксперимент.
Это параметры construction, не поиск operating threshold.

Данные: собственные/переданные владельцем разрешённые clips с автором,
датой, recording device/workflow, правами внутреннего использования и
распространения, source SHA-256; derivatives наследуют provenance и условия.
Не считать прошлый допуск VISION **JPEG** разрешением VISION videos.
Внешняя dataset acquisition не нужна для этого малого пилота; если собственных
реальных sources нет, результат честно synthetic-only и недостаточен для
вывода о реальной применимости. Медиа и производные остаются вне Git.

### 7.3. Localization, undefined и ресурсы

Каждая pair row содержит source hash, profile, stream, region/operation binding,
четыре output ordinals и четыре exact PTS/time-base для обеих групп, native/output
geometry, requested region, observed coverage и обе последовательности PTS gaps.
Опорный интервал [first_PTS,last_PTS] — envelope четырёх наблюдений, не длительность
вставки, не frame exposure duration. Нельзя соединять две группы общим
«подозрительным интервалом» или экстраполировать на пропуски.

Undefined/not applicable: <4 frames, W<16/H<9, разные geometry/profiles,
отсутствующий/немонотонный PTS, нет допустимой пары, несогласованный binding.
Последнее — input failure, а не forensic positive. Static/loops не исключать
задним числом: сохранять distances и T=0/ties как ограничения специфичности.
Malformed numeric length, decoder failure, budget/timeout — отдельные failures,
не нулевые метрики и не признаки манипуляции.

Пределы будущего пилота:

- Один case за раз; существующие native/dense/time/artifact caps не повышаются.
  Сохранить текущий generated-byte budget и оставшийся deadline; legacy PNG
  также учитываются. DENSE_VIDEO-only даёт максимум два stream facts и
  шесть dense pixel/timing representations, то есть ≤8, а не 18.
- ≤96 dense frames / 87 групп / 3741 pair rows; descriptor storage
  96×432 bytes = 41 472 bytes, pair arithmetic менее 12 млн component
  differences. RGB reader — одно окно ≤22 118 400 bytes; не держать три окна
  и не создавать pair×frame×pixel tensor.
- Рабочий numeric budget прототипа — ≤64 MiB одновременно для чтения окна,
  descriptors и временных массивов, отдельно от Python/FFmpeg runtime.
  Wall deadline ≤600 s на case с preparation, measurement ≤30 s;
  при превышении прекращать case без изменения профиля.
- Наблюдать parent+child memory; при наблюдаемом суммарном RSS >1 GiB
  прекращать исследовательский case и записывать resource failure.
  Это operational stop по наблюдениям, **не OS-enforced hard memory quota**.
  Зафиксировать peak observations и sampling interval; не назвать их
  certification или гарантированным worst-case.
- Внешний workspace пилота ≤4 GiB: исходники/derivatives ≤96×20 MiB,
  artifacts одного case удаляются штатным lifecycle после сохранения
  hashes/descriptors/результата. Pair output ≤4 MiB/case; это внешний research
  output, не предложение увеличить production worker response.

### 7.4. Детерминизм, численная устойчивость и decision gate

Профиль не использует RNG/ML/BLAS reductions. S и distance numerators считать
в signed int64 после расширения uint8; delta в signed type до abs.
S≤255×640×360=58 752 000; N_color≤440 640, N_delta≤660 960.
Это аналитические bounds, не результат запуска.
Canonical evidence хранит integers/fractions; float presentation не участвует
в сортировке/решениях. PTS subtraction/multiplication — Python int/Fraction.

Проверить на маленьких аналитических arrays: identical→0, symmetry,
min/max range, one-cell change, rounding на half-area, разные размеры cell,
black/white, reversed sequence, static descriptor collision, большие signed
timestamps и разные rational bases. Результат ≤1 по обеим distances;
undefined не сериализуется NaN/inf. Сравнить независимый простой scalar oracle
и vectorized implementation, не ослаблять assertions при расхождении.

Три fresh-process повторения всего frozen корпуса:
точное равенство descriptor bytes, rational measurements, eligible pair sets,
truth/support classification и порядка rows. decode_operation_id случайный
и меняется между запусками: сравнивать корректность binding внутри запуска
и source/stream/region/frame identity, не буквальное равенство UUID.
Elapsed/RSS также исключаются из equality, но записываются отдельно.
Повторить extraction хотя бы для lossless/lossy/VFR/high-fps представителей;
различие decoder pixels при фиксированном build — ограничение воспроизводимости,
не повод вводить tolerance после просмотра результатов.

Решение о дальнейшем исследовании:

1. **Инженерная пригодность:** все analytic/determinism/resource assertions
   пройдены; ни одной false full-coverage/localization claim.
   Failure → исправить прототип в его scope или явно остановить профиль;
   не объявлять production evidence.
2. **Добавочная измеримость:** на заранее назначенных eligible dynamic truth pairs
   показать нулевую descriptor distance для exact construction и меньшую
   D_color, чем у назначенного untouched control, после фиксированного lossy
   export минимум на двух независимых real source groups.
   Это заранее заданный gate полезности малого пилота, не forensic threshold
   или статистическая оценка FPR. Ties/нарушения/coverage misses показывать все.
3. **Ограничения:** static/periodic/normal-edit controls обязательно могут
   иметь малые distances; нельзя выдавать их за ошибки измерения или удалить
   ради красивого разделения. Если остаётся лишь их измерение либо эффект
   не добавляет ничего к adjacent exact baseline, disposition → RESEARCH_ONLY
   или DEFER с причиной. Не расширять search/window/profile в этом же пилоте.
4. Даже при успехе — только предложение отдельной validation задачи.
   Production promotion, near-match cutoff, severity, correlation/risk и новые
   Findings остаются неразрешёнными. Успех измерения не доказывает manipulation.

## 8. Источники, provenance и лицензии

**EXTERNAL LITERATURE**, просмотр 2026-10-01, официальная online documentation
FFmpeg contributors (живые страницы без привязки к конкретной локальной сборке):

| Источник | Использованное определение и предел |
|---|---|
| [ffprobe, Main options / read_intervals](https://ffmpeg.org/ffprobe.html#Main-options) | `#` задаёт число input packets; seek может не совпасть с requested start. Это подтверждает различие запроса и наблюдения, не forensic rule |
| [FFmpeg Filters, showinfo](https://ffmpeg.org/ffmpeg-filters.html#showinfo) | PTS в time-base units, key/picture type, Adler-32 описывают кадр на конкретной точке filtergraph; не исходную историю монтажа |
| [FFmpeg, -ss / seek_timestamp](https://ffmpeg.org/ffmpeg.html#Main-options) | Input/output seek имеют разную семантику. Фактические аргументы проекта проверены в исходниках, full-video coverage из наличия seek не выводится |

Это повторное обращение к уже используемым интерфейсным источникам:
[REFERENCES](../REFERENCES.md), записи FFmpeg/ffprobe и
«Dense video foundations M1-F». Не добавлены внешний forensic algorithm,
reference implementation, models, weights или dataset.
Документация цитируется ссылками; тексты, изображения и чужой код не копируются
в продукт. Лицензионный допуск FFmpeg зависит от конкретной сборки и прежней
политики поставки; ссылка на API не меняет его.

Method source VRC-DENSE-1 — **project-specific proposed heuristic**,
implementation source пока отсутствует; предполагается собственный внешний
research code поверх существующих Python/NumPy/FFmpeg.
ORB/RANSAC и JPEG DQ рассматриваются только в рамках уже записанных
[analyzer references](../REFERENCES.md#analyzer-references) и METHODS.
Новые внешние зависимости и лицензионные решения не требуются в M4-R1;
REFERENCES не изменяется. Никакой blanket-лицензии будущего корпуса не заявлено.

## 9. Dispositions и review

| Решение | Итог M4-R1, принятый владельцем 2026-10-01 |
|---|---|
| Primary | VRC-DENSE-1 — PROTOTYPE_NEXT / OWNER ACCEPTED RESEARCH DIRECTION; extension research существующей video responsibility |
| Secondary | VCM-FRAME-1 — TARGETED_RESEARCH / INACTIVE |
| Visual discontinuity | RESEARCH_ONLY: измеримо, но cut/flash/pan не специфичны |
| Container/timing | RESEARCH_ONLY; input validity duplicate — REJECT_DUPLICATE_RESPONSIBILITY |
| GOP/codec | DEFER; частичные frame types не заменяют source structure |
| Cross-modal A/V | DEFER для semantic synchronization; имеющиеся endpoint offsets — RESEARCH_ONLY |
| Image metadata / JPEG DQ | NOT_APPLICABLE / INVALID_AFTER_VIDEO_DECODE; никакого frame wrapper |
| Новые зависимости / preprocessing для primary | NO / NO; существующий demand нужен лишь внешнему будущему прототипу |
| Production method/threshold/catalog changes | NO / NO / NO |

Сохранены только docs/research изменения: METHODS — принятие исследовательского
направления без production promotion, ROADMAP — статус и следующая активная
задача, этот отчёт — основания и proposed study. Исторические branch/baseline
M4-R1 в §1 и численные параметры протокола сохранены. PROJECT/CONTRACTS/REFERENCES
и executable files не изменяются. Macro 3 не переоткрывается;
Macro 4 остаётся IN_PROGRESS.

Проверки M4-R1: `git diff --check`, полный intended diff включая новый untracked
отчёт, итоговый `git status --short --untracked-files=all`.
Тесты, quality barrier, certification и experiment runs не выполняются по scope.
Self-report готовности материалов не является owner acceptance.
Принятие направления в M4-R1-A основано на явном решении владельца; запись
решения ещё подлежит owner review. Она не разрешает новые analyzer IDs,
Findings, severity/risk, probability/verdict, preprocessing, dependencies
или runtime API/schema; production-каталог остаётся из пяти анализаторов.

Внешний research root:
`C:\Users\Vanur\Desktop\FakeDetector-Work\research\M4-R1-video-selection\`.
Внешний review root:
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M4-R1-video-selection\`.
Тематические Markdown artifacts — срезы этого отчёта для review, без отдельной
нормативной силы; complete.diff включает весь новый отчёт. Git mutations нет.
Материалы проверки записи M4-R1-A находятся в подкаталоге `acceptance/`
review root; там complete.diff включает весь intended diff относительно HEAD,
а acceptance-only.diff — только изменения записи принятия относительно M4-R1.
