# METHODS.md

> Канонический владелец конкретной принятой криминалистической методологии анализаторов.

## Назначение и границы

Здесь фиксируются принятые владельцем методы: применимость, входные
представления, точное детерминированное измерение, нормализация, правила решения
и обоснование порогов, смысл findings, ограничения, корреляция, ресурсы и
валидация. Формулы и пороги не выводятся из одного названия кандидата.

- `PROJECT.md` задаёт архитектуру, продуктовые политики и инварианты.
- `CONTRACTS.md` задаёт общие analyzer/preprocessing/result/finding интерфейсы,
  модели, validation/serialization и failure semantics. Они остаются там.
- `REFERENCES.md` владеет происхождением и лицензиями внешних источников;
  метод ссылается на стабильные записи реестра, не дублирует лицензионный аудит.
- `ROADMAP.md` владеет очередностью, статусом реализации и owner gates.
- `../AGENTS.md` задаёт процесс работы и приёмки; `CHANGELOG.md` хранит историю.
- `research/` сохраняет входные свидетельства, сравнения и экспериментальные
  наблюдения; исследовательский отчёт не является production authority.

Полномочия разграничены по областям. Междоменное противоречие требует owner gate;
код и тесты — свидетельства реализации, не способ молча изменить спецификацию.
Создание документа не переопределяет поведение существующих анализаторов и
не объявляет их методологию заново принятой или перенесённой сюда.

## Gate принятия метода

Этот gate сохраняется для production/core promotion. Отдельный дипломный
допуск описан в [experimental tier](#diploma-experimental); он не превращает
исследовательские отрицательные результаты в `ACCEPTED` production-методы.

`CANDIDATE / METHOD NOT YET ACCEPTED` означает направление исследования.
Даже наличие статьи, `RESEARCH_REFERENCE`, preprocessing capability или
положительного экспериментального результата не разрешает production-реализацию.

Перед началом реализации нового метода необходимо:

1. Провести целевое исследование: сравнить варианты, применимость, ограничения,
   измерения и обоснование порогов; сохранить проверяемые свидетельства и ссылки.
2. Оформить применимые provenance/licensing записи в `REFERENCES.md`.
3. Подготовить полную спецификацию по шаблону ниже; незаполненный обязательный
   пункт не заменять предположением. Для неприменимого пункта записать причину.
4. Получить явное принятие владельцем конкретной спецификации и закрыть
   необходимые owner gates; записать решение, дату и принятый объём в этой записи
   со статусом `ACCEPTED`. Self-report агента не является принятием.
5. Отразить снятие блокера и разрешённый scope реализации в `ROADMAP.md`.

Только после этого начинается реализация. `ACCEPTED` относится к методологии,
не означает DONE, production-active, прохождение тестов или включение в каталог.
Изменение принятого измерения, порогов или семантики требует явного решения
владельца и обновления этой спецификации в том же принимаемом изменении.

## Шаблон спецификации метода

Шаблон — структура документа, не новые runtime-поля или конфигурация.

| Раздел | Обязательное содержание |
|---|---|
| Analyzer ID | Точный согласованный идентификатор; рабочее имя кандидата явно обозначается |
| Принятие | Статус метода, решение/дата принятия владельцем и принятый объём |
| Evidence family | Семейство свидетельств и граница независимости сигнала |
| Цель / наблюдаемый сигнал | Что измеряется и какой ограниченный вывод поддерживается |
| Применимость | Допустимые форматы, свойства входа, качество и покрытие |
| Not-applicable / insufficient-evidence | Точные условия неприменимости и недостатка данных в рамках CONTRACTS |
| Требуемые preprocessing representations | Конкретные существующие представления/capabilities, точность и координатные системы |
| Точная детерминированная процедура | Входы, последовательность вычислений, формулы/параметры, обработка границ и вырожденных случаев |
| Нормализация / агрегация | Масштабы, единицы, правила объединения локальных измерений и покрытия |
| Decision rules и обоснование порогов | Точные условия решений и свидетельства, обосновывающие каждый production-порог |
| Finding semantics | Значение выдаваемых признаков и измерений в существующей модели результата |
| Что метод не доказывает | Пределы выводов; отсутствие сигнала не доказывает подлинность |
| Локализация, если применима | Покрытие, координаты, точность, преобразования; иначе причина неприменимости |
| Correlation group / related evidence | Связь с другими свидетельствами и существующими правилами корреляции без двойного учёта |
| Доброкачественные причины / false positives | Обычная обработка и challenge-сценарии, способные дать похожий сигнал |
| Ресурсы | Ожидания CPU/RAM/time/artifacts, алгоритмические границы и соответствие действующим бюджетам |
| Validation matrix | Positive, negative, benign/challenge, boundary, not-applicable, insufficient-evidence, determinism и resource/failure случаи; пределы синтетических fixtures и требуемые корпусные свидетельства |
| Provenance / reference IDs | Стабильные IDs/якоря REFERENCES, происхождение собственного вклада и ссылки на research-свидетельства |
| Открытые owner gates | Нерешённые вопросы и условия принятия; при ACCEPTED не остаётся блокирующих вопросов |

<a id="diploma-experimental"></a>
## Дипломный experimental tier — Sprint 1, 2026-10-12

**OWNER AUTHORIZED** заданием `STAGE12-DIPLOMA-ANALYZER-EXPANSION-SPRINT1`:
«Diploma experimental analyzer tier authorized». Разрешена экспериментальная
runtime-реализация для дипломного прототипа; научный и production disposition
сохранён: **experimental runtime implementation authorized for diploma prototype;
scientific/production disposition unchanged**. Это отдельный допуск реализации,
не ретроактивная приёмка метода, корпуса или результатов настоящего sprint.

Исторические записи ниже и `research/` читаются в контексте своих задач:
их запрет runtime implementation снят только для описанного experimental tier.
Production/core promotion, изменение пяти CORE методов и переоткрытие Macro 2/3
не разрешены. VRC остаётся G5 DEFER; P1 не меняется, Stage B не начинается.

Все новые методы имеют версию `1.0.0`, фиксированный профиль без настроек,
CPU-only выполнение на существующих NumPy/Pillow и внутренних ядрах. В Sprint 1
они публикуют **измерения без Findings и без собственного score**. Порогов подозрения,
confidence, accuracy/FPR, probability или critical override у анализаторов нет.
Отдельная последующая политика дипломного fusion описана
[ниже](#diploma-ensemble-normalization); она не меняет runtime-измерения.
Численные границы support/устойчивости ниже не являются forensic thresholds.
Отсутствие/неопределённость измерения не означает подлинность. Сильный response
не отделяет монтаж от обычного содержания или обработки.

| Analyzer ID | Runtime maturity | Сохранённое научное положение / профиль |
|---|---|---|
| `audio_temporal_discontinuity` | EXPERIMENTAL | RESEARCH_ONLY_NON_SPECIFIC; ATD-LOCAL-1 |
| `audio_spectral_consistency` | EXPERIMENTAL | RESEARCH_ONLY_NON_SPECIFIC; ASC-TV-1 |
| `audio_repeated_segment_correspondence` | EXPERIMENTAL | RESEARCH MEASUREMENT DEMONSTRATED / PRODUCTION PROMOTION DEFERRED; ARC-NCC-1 |
| `audio_background_noise_consistency` | EXPERIMENTAL_WEAK | RESEARCH_ONLY / WEAK_SIGNAL; ABN-FLOOR-1 |
| `image_noise_residual_consistency` | EXPERIMENTAL_WEAK | RESEARCH_ONLY / WEAK_SIGNAL; N-MAD-MATCH-1 |
| `image_resampling_consistency` | EXPERIMENTAL_WEAK | RESEARCH_ONLY / WEAK_SIGNAL; R-D2-MATCH-1 |
| `video_repeated_content_correspondence` | EXPERIMENTAL_WEAK | G5 DEFER; VRC-DENSE-DIPLOMA-1 на основе P1 |
| `video_visual_discontinuity` | EXPERIMENTAL_WEAK | RESEARCH_ONLY; VISUAL-DENSE-DIPLOMA-1 |
| `video_timing_anomaly` | EXPERIMENTAL_WEAK | RESEARCH_ONLY; TIMING-DENSE-DIPLOMA-1 |

### Audio: применимость, процедуры и границы

Точные формулы ATD/ASC/ABN/ARC из
[M3-R1 §§3–7](research/2026-09-26-audio-method-selection.md) приняты этим
дипломным допуском **только как описательные измерения**. Их значения и
исследовательские результаты не перекалибровываются. Audio route, 8–48 kHz,
mono/stereo; без resample/downmix, не более трёх observed precision windows
по 10 s. Читаются только source-bound numeric artifacts; не source bytes.
ATD требует `AUDIO_SAMPLES`, остальные — `AUDIO_SPECTRAL` с его dependency closure.
Precision provenance — `ffmpeg_audio/1 : precision_windows/1`; спектр —
`numpy_stft/1 : hann4096_hop1024/1`, magnitude, Hann4096/hop1024.
Неподдерживаемый rate/channel или spectral layout неприменим; отсутствующий
обязательный manifest/артефакт, отрицательная magnitude, nonfinite/повреждённые
bytes — техническая ошибка. Короткое окно без полного STFT frame — недостаток
поддержки, а не ошибка. Границы разных окон не сшиваются.

- **ATD:** shared `frame_audio(2048,512)`, earliest максимальная разность
  среди границ a+768…a+1279; стороны по 512 samples. После common-max
  стабилизации раздельно `J=j/(j+d)`, `E=|rR-rL|/(rR+rL)`, signed `Es`,
  `A=|medianR-medianL|/(|medianR-medianL|+MAD_L+MAD_R)`. d — медиана внутренних
  абсолютных первых разностей, без соединяющего jump; RMS и MAD по M3-R1.
  Zero denominator → null. Фрейм короче 2048 не дополняется. Нет вывода о splice.
- **ASC:** пары готовых спектров одного окна/канала при h=1 и h=4.
  Common-max до суммирования; `D=0.5*sum(abs(pR-pL))`,
  `F=sum(max(MR-ML,0))/(sum(MR)+sum(ML))`. Нулевой спектр делает D
  неопределённой; F определена при одном ненулевом спектре. Нет нового STFT.
- **ABN:** в каждом окне границы b=2fs,3fs,…,N−2fs, стороны по 2fs;
  только полностью входящие STFT frames, минимум 8 на сторону. После общего
  масштабирования M вычисляется P=M². Стабильный отбор `max(4,ceil(n/5))`
  самых тихих frames по sum(P), tie по ordinal. Bins1…2048 делятся на 16×128;
  median средних полосных мощностей даёт v. Сохраняются v, sum(v), TV
  нормированных v и signed level change. Уровни безразмерны, нормированы
  на максимум именно этой пары; это не dBFS или оценка sensor noise PSD.
  До 7 пар/окно/канал, до 42 строк. Независимого matching содержания нет:
  `background_attribution=insufficient_evidence_no_independent_matching` всегда.
  Низкая энергия не означает выделенный фон или identity микрофона.
- **ARC:** сохранены L=1024·ceil(fs/1024), seeds через 4096 с полным 2L,
  равномерное сокращение до 256; ≥4 готовых frames на descriptor, 16 полос без DC,
  4 временные группы/L2; top4/seed/channel, непересекающийся 2L, union/cap64.
  Поиск signed ZNCC δ=−4096…4096 при полном 2L в исходном окне; общий lag по
  среднему информативных каналов, tie по |δ|, затем δ. Два support L/2 измеряются
  на том же lag; exact decoded equality 2L хранится отдельно по каналам.
  Сохранена numeric correction frozen v2 из M3-R2B: compensated prefix sums,
  floor 64eps·m, guard 64eps вне [-1,1], linear FFT≤131072. Неинформативный lag
  не выбирается; канал тишины может иметь exact equality, но не NCC/support.
  Channel-best offsets и disagreement сохраняются. R1 diversification не
  переносится: остаются known flooding/retention misses, unresolved attribution,
  естественные loops/tones и высокая NCC фона. Это не новый ARC v3.

Runtime-отчёт ATD/ASC компактен: по окну/каналу/метрике count, undefined_count,
median, nearest-rank p95 и первое max с sample-support и source PTS при наличии.
Вместо исследовательских всех строк/top16 сохраняется один максимум каждой
метрики. Null остаётся null. ARC сохраняет до 64 пар, три NCC по каналам,
sample-интервалы и PTS отдельно, seed/union/cap counts; полный research ledger
не переносится. Эти координаты описывают поддержку измерения, не место монтажа.
ATD/ASC/ABN причинно пересекаются; ARC не объявляется статистически независимым.
Нового `Finding.correlation_group` нет; дипломное объединение откликов задаётся
отдельной политикой assessment, а не анализаторами.

Происхождение: [REFERENCES M3-R1](REFERENCES.md#audio-m3r1), M3-AUD-01–09;
собственные измерительные комбинации и first-party код, без копирования
сторонних реализаций. Для ARC переиспользована численная часть собственного
frozen `arc_v2.py` (`04a2d54f…`, M3-R3C), без его файлового доступа, monitor,
corpus harness и runtime-данных. Исторические evidence trees не изменены.

### Image: применимость, процедуры и границы

Точные N-MAD-MATCH-1 и R-D2-MATCH-1 из
[M2-BR1 §§4–5](research/2026-09-24-image-noise-resampling-method-selection.md)
приняты как experimental измерения без порога. Вход — обязательный legacy
`normalized_image` PNG RGB/RGBA; дополнительный demand отсутствует, готовый
residual artifact не предполагается. Обе стороны ≥512, pixels≤2^22,
без resize для обхода лимита. Сетка 4×4: starts `2+floor(i*(size−132)/3)`,
cores 128², halo 2. Общие `extract_image_tiles`, BT.601 luminance,
`finite_differences`, binomial5 residual; только bounded tile arithmetic.

N-MAD: строгий RGB support (4,251), alpha 255, erosion 5×5 и g≤8;
≥8192 support pixels, median(g)≤12, median(Y)∈[16,239]. Unscaled residual MAD,
variance/energy/lag1 — раздельные diagnostics. До 5 пространственно ближайших
peers с |Δbrightness|≤16 и |log2((g_i+.25)/(g_j+.25))|≤.5, tie row-major,
минимум 3; `d=abs(log2((MAD_i+.25)/(median_peer_MAD+.25)))`.
Это остаток фильтра, не sensor noise, PRNU или camera fingerprint.

R-D2: шаговые Dxx/Dyy, mean(abs(d2)) по ортогональной оси; центрирование,
periodic Hann/rFFT128, normalized power без DC (denominator>1e−12).
Исключаются k≤3 и расстояние≤2 от 16m. Все halo/core opaque/unsaturated,
brightness∈[16,239]. Target с texture power≥.1 около своего пика (k±1)
отклоняется; peer с veto остаётся reference, если spectrum пригоден.
С тем же matching/minimum3 сравниваются мощности **на частоте target**:
`q=max(0,log2((P_i[k]+1e−12)/(median_peer_P[k]+1e−12)))`.
Phase половин — diagnostic без решения. Спектральная периодичность не
устанавливает interpolation history; JPEG/texture/notch и отсутствие peers
могут скрыть сигнал или создать ложное различие.

Оба результата сохраняют поддержку/eligibility tiles, peers, сравнения и
максимум (null при отсутствии сравнений), координаты oriented pixels.
`core_pixels` — число обработанных core samples, не union coverage:
у малых допустимых размеров cores могут перекрываться. Канонический
half-open grid и максимум не являются вероятностью или p-value.
Не более 16 tiles и 32 направлений; raster освобождается после извлечения tiles.
Общий шум/текстура/сжатие связывают эти методы с image quality и JPEG evidence;
статистически независимый голос не заявляется. Provenance —
[NR-RS-BR1-FIRSTPARTY](REFERENCES.md#nr-rs-br1-firstparty--собственные-исследовательские-профили).

### Video: отдельные runtime-профили и границы P1

Все три метода требуют только `DENSE_VIDEO` + dependency `STREAM_TIMING`:
существующие RGB24/PTS одного decode, до 3 окон×32 кадра, ≤640×360,
native≤3840×2160. Generic timing/AV не запрашиваются: совместный спрос
всех представлений превысил бы manifest cap. Timing analyzer наблюдает
**только dense frame PTS**, не packet/GOP/DTS и не semantic A/V sync.
Frames не сортируются, gaps между окнами не сшиваются, target times legacy PNG
не подставляются вместо PTS. Сохраняются requested/observed bounds,
coverage/stop reason, rational time base. Missing/bad input — ошибка reader;
неизвестные PTS — явно неопределённые сравнения, не suspicious Finding.

- **VRC-DENSE-DIPLOMA-1:** неизменённые block mean432, integer half-up,
  four-output-frame groups, geometry/stream compatibility, строгие PTS,
  temporal nonoverlap и один spare frame внутри окна из
  [P1 §2](research/2026-10-01-video-vrc-protocol.md). Все ≤3741 unordered
  пары проверяются, static/periodic не удаляются. Сохраняются отдельные
  D_color=N_color/440640, D_delta=N_delta/660960 и T numerator/330480.
  Runtime выводит counts/распределения и первую пару минимума отдельно по
  каждой distance с числителями и поддержкой; полный P1 JSONL/4MiB report
  в envelope 64 KiB не переносится. Zero descriptor не означает pixel equality.
  Этот профиль — разрешённая runtime-адаптация, **не правка frozen P1**,
  не повтор Stage A и не свидетельство прохождения G2/G3/G4/G5.
- **VISUAL-DENSE-DIPLOMA-1:** те же 16×9 RGB means; для соседних кадров
  одного окна при known строго возрастающих PTS
  `sum(abs(q_next−q_prev))/(432*255)`. До 93 пар; count/undefined,
  median/p95/max и support первого максимума. Motion, cuts, flash и lighting
  не различаются; threshold отсутствует.
- **TIMING-DENSE-DIPLOMA-1:** gap соседних observed PTS вычисляется Python int,
  отсутствующий PTS разрывает сравнение. Сохраняются gaps, duplicate/decrease
  counts; reference — median положительных gaps данного окна. Описательная
  deviation=`abs(gap−reference)/(abs(gap)+reference)` при наличии reference,
  иначе null-summary. VFR и decoder timing — доброкачественные объяснения.

Для VRC/visual размер ниже 16×9 неприменим, недостаток кадров/пар —
`insufficient_evidence`. Timing не требует этой spatial geometry.
Читается одно pixel-окно за раз; далее удерживаются только descriptors/timing.
Происхождение: собственные методы из [M4-R1](research/2026-10-01-video-method-selection.md)
и P1, NumPy и [M1-F foundations](REFERENCES.md#dense-video-foundations-m1-f--2026-09-21).
Связь с `video_sampled_frame_quality` и между тремя методами сохраняется как
ограничение интерпретации; статистическая независимость не заявляется.

### Проверки и оставшиеся границы

Focused tests включают математические positive/control oracles, silence/flat,
support boundaries, alpha/saturation, matching/notches, exact/near NCC и
periodic confounds, PTS duplicate/decrease/missing/negative/large ticks,
determinism, malformed/nonfinite inputs и реальные spawned workers.
Проверяются максимальные планы, seed/pair caps и envelope; сквозной тест
исполняет diploma config через реальный preprocessing/API/persistence/WebUI/cleanup.
Это инженерные проверки собственных синтетических fixtures, не корпусная
forensic validation и не новые accuracy/FPR. Текущий итог — в ROADMAP.
Worker timeout и existing artifact budgets действуют без послабления;
длинный stereo audio может быть отклонён штатным общим бюджетом ещё до анализа.
Нет гарантии full-media coverage или hard RSS quota.

`image_embedded_thumbnail_consistency` не реализован: отсутствует bounded
preprocessing producer/descriptor для настоящего embedded IFD1 JPEG. Нужны
отдельные extraction/binding/resource изменения; самодельная миниатюра не evidence.

<a id="diploma-ensemble-normalization"></a>
## Нормализация дипломного ансамбля — 2026-10-13

**OWNER AUTHORIZED**, `STAGE12-DIPLOMA-ENSEMBLE-SPRINT1`. Это инженерная
нормализация уже существующих результатов версии `1.0.0`, не принятие новых
forensic decision rules, не изменение scientific disposition и не новая
корпусная валидация. Общая модель, начальные коэффициенты и пороги принадлежат
[PROJECT §10.8](PROJECT.md#diploma-ensemble); публичное представление и отказ —
[CONTRACTS §11.7](CONTRACTS.md#117-diploma_ensemble_v1-в-существующей-схеме).

Исправление владельца `STAGE12-DIPLOMA-ENSEMBLE-SPRINT1-R1` меняет только итоговую
нормализацию по канонической ёмкости в PROJECT §10.8. Все 14 преобразований
ниже, членство в семействах и коэффициенты влияния сохранены.

В таблице `max_defined` берёт максимум определённых значений, без замены null
нулём; если таких значений нет, response=null (`insufficient_evidence`).
Общая входная граница: только `completed && applicable` даёт измеряемый отклик.
`error`/`timeout`/`skipped`/`not_applicable` и отсутствующий в активном плане ID
дают response=null с отдельной причиной. Явное `state=insufficient_evidence`
у experimental также даёт null. Завершение исполнения и достаточность измерения
не отождествляются. Все response конечны и принадлежат `[0,1]`.

`B` — **DIPLOMA_HEURISTIC_NORMALIZATION** бинарного CORE-свидетельства:
`1`, если есть хотя бы один принятый `Finding` этого источника, иначе `0`.
Severity, source_score и повторные локализации не суммируются. Это не новая
серьёзность Finding: существующие CORE Findings остаются `weak`, а `1` означает
срабатывание принятого правила источника, не силу доказательства подделки.

| Analyzer ID | Семейство | Maturity / влияние | Источник и точное преобразование | Направление, отсутствие данных, confounds |
|---|---|---|---|---|
| `image_metadata_consistency` | `image_metadata` | CORE / 1.00 | `B` по принятым Findings о несогласованных размерах | Появление Finding: 0→1; отсутствие/удаление EXIF само по себе не сигнал; переэкспорт и устаревшие теги |
| `image_copy_move_correspondence` | `image_region_correspondence` | CORE / 1.00 | `B` по принятым Findings соответствующих регионов | Появление Finding: 0→1; обе локализации и несколько кластеров не умножают отклик; естественные повторы/текстуры |
| `image_jpeg_double_quantization` | `image_recompression` | CORE / 1.00 | `B` по `jpeg_recompression_pattern`; `raw_metrics.decision=insufficient_evidence` → null | Появление Finding: 0→1; insufficient вместе с Finding — противоречие; обычное повторное JPEG-сжатие |
| `audio_pcm_quality` | `audio_quality` | CORE / 1.00 | `B` по принятому saturation Finding | Появление Finding: 0→1; число фрагментов не увеличивает response; перегрузка записи/мастеринг |
| `video_sampled_frame_quality` | `video_quality` | CORE / 1.00 | `B` по принятым resolution-change/repeated-frame Findings | Появление Finding: 0→1; оба типа учитываются один раз; статичные сцены, обычный монтаж |
| `audio_temporal_discontinuity` | `audio_transition` | EXPERIMENTAL / 0.65 | `max_defined(windows[*].{J,E,A}.max)` | Не убывает по каждой unsigned метрике; Es уже представлен через E и повторно не используется; речь, музыка, transients |
| `audio_spectral_consistency` | `audio_transition` | EXPERIMENTAL / 0.65 | `max_defined(windows[*].{D1,D4,F1,F4}.max)` | Не убывает по TV/flux; `no_full_stft_frame` пропускается; смены тембра, музыкальные переходы, усиление |
| `audio_repeated_segment_correspondence` | `audio_repetition` | EXPERIMENTAL / 0.65 | По measured pairs/channels с `structural_support=true`: `max_defined(max(0,min(rho,support_rhos[0],support_rhos[1])))` | Не убывает по каждому signed NCC; все три значения обязаны быть определены; exact_decoded без NCC не голосует; loops, tones, фон, retrieval misses |
| `audio_background_noise_consistency` | `audio_background` | EXPERIMENTAL_WEAK / 0.35 | `max_defined(contexts[*].tv, abs(contexts[*].signed_level_change))` | Не убывает по TV и модулю изменения уровня; attribution остаётся insufficient независимо от response; тихая речь/музыка и общий звук вместо выделенного фона |
| `image_noise_residual_consistency` | `image_local_processing` | EXPERIMENTAL_WEAK / 0.35 | `x=max_log2_ratio`, `response=x/(1+x)` | Не убывает по x≥0; null→null; текстура, фильтрация, JPEG, ограниченное matching; не PRNU |
| `image_resampling_consistency` | `image_local_processing` | EXPERIMENTAL_WEAK / 0.35 | `x=max_log2_ratio`, `response=x/(1+x)` | Не убывает по x≥0; null→null; периодическая текстура, JPEG/notches, нехватка peers; не доказательство resampling |
| `video_repeated_content_correspondence` | `video_repetition` | EXPERIMENTAL_WEAK / 0.35 | Для каждого ненулевого `minimum_color_pair` и `minimum_delta_pair`: `r=1-max(color_numerator/440640,delta_numerator/660960)`; response=max_defined(r) | Не возрастает по дистанциям одной пары; две разные минимальные дистанции не склеиваются; null pairs→null; статические сцены, периодические движения, грубые descriptors |
| `video_visual_discontinuity` | `video_visual_transition` | EXPERIMENTAL_WEAK / 0.35 | `max_defined(windows[*].transition.max)` | Не убывает по переходу; `unsupported_geometry` пропускается; движение, flash, lighting, обычные cuts |
| `video_timing_anomaly` | `video_timing` | EXPERIMENTAL_WEAK / 0.35 | По окну: максимум `gap_deviation.max` и `(duplicate_pts_pairs+decreasing_pts_pairs)/observed_pairs`; response=max_defined по окнам | Не убывает по deviation и доле нарушений; observed_pairs=0→null; доля определена и без positive-gap reference; VFR/decoder timing |

Для обоих image log-ratio масштаб `1` —
**DIPLOMA_HEURISTIC_NORMALIZATION**: одна log2 единица означает удвоение исходного
стабилизированного отношения и даёт response `0.5`; `x→∞` даёт `1`.
Это не порог forensic решения. Масштаб выбран из единиц самой метрики, а не
подогнан по accuracy. Синтетические fixtures предыдущего sprint подтверждают
измеримость log-ratio, но не валидируют этот коэффициент для реальных файлов.
У остальных experimental преобразований используются естественные границы
TV, относительных изменений, signed NCC и нормированных descriptor distances;
новых эмпирических anchors нет. Max по окнам — чувствительный к экстремумам
эвристический выбор, не статистическая оценка и не независимое голосование окон.

Численная безопасность: используемые числа проверяются на конечность, тип
(bool и string не числа) и исходный домен. NCC допускает `[-1,1]`, signed
level change — `[-1,1]`, unsigned ответы — `[0,1]`, log-ratio — конечный `x≥0`.
Для естественно ограниченных float-измерений допускается только численная
погрешность `64*ulp(1.0)` за границей с последующим clamp в исходный домен:
существующая TV reduction может вернуть `1.0000000000000002`. Это не forensic
threshold и не normalization anchor. Существенный выход за домен отклоняется;
для целых счётчиков, log-ratio, весов и арифметики семейств допуск не применяется.
Делитель `1+x` положителен и не переполняется для конечного float64 x;
остальные делители — положительные фиксированные константы или проверенный
ненулевой count. Метрики max требуют целый `count>0`, null — `count=0`.
Сумма duplicate/decrease не превышает observed_pairs. В VRC принимаются
целые числители в их естественных границах; минимум вычисляется для сохранённых
пар, полный pair ledger не восстанавливается. Любая ошибка используемого
значения отклоняет оценку, а не становится чистым откликом. Неиспользуемые
диагностические поля не интерпретируются повторно.

Обход ограничен текущими runtime-профилями: ATD/ASC ≤6 строк окон/каналов
(каждый distribution count ≤1000), ABN ≤42 контекстов, ARC ≤64 пар ×2 канала,
video ≤3 окон и ≤31 наблюдаемых пар/окно. Порядок окон, пар, каналов и Findings
не влияет на ответ. Пустые/неинформативные выборки остаются null. Естественная
тишина у ATD/ASC/ABN может давать неопределённое измерение, а не нулевой отклик.

Карта семейств сохраняет предложенную владельцем. Уменьшение ATD/ASC и
noise/resampling подавляет очевидное внутрисемейное повторение; корреляции
между семействами не устранены и не объявлены отсутствующими. В частности,
CORE video repetition и VRC могут реагировать на одну статичную сцену;
image local processing и JPEG — на обычное сжатие. Это явное ограничение
интерпретации начального дипломного ансамбля. Новых Findings, corpus campaign,
accuracy/FPR/FNR или изменения frozen P1/ARC-v2 нет.

<a id="video-m4r1"></a>
## Кандидаты Stage 12 / Macro 4 — M4-R1 / M4-R2

**M4-R1 — DONE / OWNER ACCEPTED METHOD SELECTION**: владелец явно принял
выбор исследовательского направления 2026-10-01 в M4-R1-A.
**Production-метод не принят**; в M4-R1 эксперименты и реализация не выполнялись.
Основания, descriptive scorecard, проверка image reuse, sampling limitations
и единственный proposed experiment находятся в
[отчёте M4-R1](research/2026-10-01-video-method-selection.md).

- **VRC-DENSE-1 — DEFER / OWNER ACCEPTED DISPOSITION (2026-10-12):**
  принято направление измерения соответствия разнесённых меняющихся
  четырёхкадровых последовательностей на существующих dense RGB
  и same-decode timing. Это исследование расширения ответственности
  `video_sampled_frame_quality`, указанной в ROADMAP, без нового analyzer ID
  или независимого вклада в риск. Повтор/малая distance не доказывают монтаж.
- **VCM-FRAME-1 — TARGETED_RESEARCH / INACTIVE:** вторичное изучение сохранности
  пространственного copy-move correspondence после video decode; прямой
  перенос image analyzer/thresholds не разрешён.
- Visual discontinuity и regional timing остаются **RESEARCH_ONLY**;
  codec/GOP structure и semantic A/V synchronization — **DEFER**.
  Adjacent exact-repeat и input-validation duplicates отклонены.
  Image metadata reuse — **NOT_APPLICABLE**, JPEG DQ после decode —
  **INVALID_AFTER_VIDEO_DECODE**.

Конкретизация M4-R1 §7 принята владельцем 2026-10-01 в M4-R2-P-A и зафиксирована в
[протоколе M4-R2-P](research/2026-10-01-video-vrc-protocol.md):
`VRC-DENSE-1/P1`, точные формулы, corpus/transform plan, oracles и execution gates.
**M4-R2-P — DONE / OWNER ACCEPTED**.
**VRC-DENSE-1/P1 — FROZEN RESEARCH PROTOCOL**: принят весь рассмотренный протокол,
включая formulas, corpus manifest, transform recipes, truth/control mappings,
oracles, resource limits и gates. Это не production-спецификация или thresholds.
Материальное изменение требует новой документированной версии протокола
и отдельного OWNER GATE; молчаливая правка P1 не разрешена.

Владелец принял независимый review завершённой composite Stage A 2026-10-12:
**COMPLETE / SYNTHETIC_ONLY / COMPLETE WITH ENGINEERING FAIL**.
Состав матрицы, G1–G4, формальный determinism и неизменные исторические серии —
в [закрытии M4-R2](ROADMAP.md#video-m4r2-closeout).

**G3 — PARTIAL:** в формально пригодных свидетельствах 65 exact-copy observations:
49 **SUPPORTED_ELIGIBLE** и 16 **COVERAGE_MISS**. Все 49 supported eligible
наблюдений удовлетворяют `D_color = 0`, `D_delta = 0`. Coverage misses остаются
отсутствием поддержки, а не успешными zero-distance detections.

VRC показывает контролируемую синтетическую измеримость. В динамических
конструкциях P01/P02 заранее заданная V02 copy pair даёт нулевую VRC distance,
соответствующий untouched control — ненулевую; существующий adjacent exact-run
baseline не описывает то же структурное соответствие. При этом сохранены
неспецифичные нули, ties или близкие наблюдения в static, periodic, slides и
обычных edit/cut/flash/lighting constructions. Эти результаты не устанавливают
forensic specificity, manipulation classifier, универсальный порог,
real-world added value, population accuracy/FPR или production readiness.

**G5 — DEFER:** VRC остаётся исследовательским кандидатом с продемонстрированным
синтетическим сигналом. Переход к real-source validation по frozen P1 отложен:
G2 **FAIL**, G3 **PARTIAL**, G4 **NOT_EVALUATED_STAGE_A**, реальный корпус не допущен;
P1 требует разрешить engineering failures Stage A до Stage B.
Stage B — **BLOCKED / NOT AUTHORIZED**. Полный повтор Stage A **NOT PLANNED**;
retry-until-pass и подбор повторов по outcomes не разрешены.

Production-каталог сохраняет ровно пять анализаторов; VRC promotion отсутствует.
Нет допуска нового Finding type, независимого forensic/risk vote, severity/risk,
probability/verdict, catalog registration, нового preprocessing, dependencies,
runtime/config/public schema или изменения принятого video analyzer. Все
production steps сохраняют gate принятия метода выше. Очередность — в
[ROADMAP](ROADMAP.md#video-m4r1); VCM-FRAME-1 остаётся TARGETED_RESEARCH / INACTIVE.
Macro 3 не переоткрывается.

<a id="audio-m3r1"></a>

## Кандидаты Stage 12 / Macro 3 — M3-R1

Дата предложения и явного owner acceptance исследовательских gates G1–G6:
**2026-09-26** (M3-R1A). ATD-LOCAL-1, ASC-TV-1 и ARC-NCC-1 получили статус
**OWNER_ACCEPTED_FOR_MEASUREMENT_PROTOTYPE**: разрешены только ограниченные
исследовательские измерения и measurement-only validation. **Production-метод
не принят**; gate production acceptance выше остаётся обязательным.
Рабочие имена не являются analyzer IDs.
Полная структура gate, точные exploratory процедуры, применимость, покрытия,
численные/ресурсные границы и validation matrix сохранены в
[исследовании M3-R1](research/2026-09-26-audio-method-selection.md).
Эти процедуры не становятся нормативной production-методологией этой ссылкой.

| Рабочий кандидат / профиль | Статус исследовательского профиля | Вопрос и inputs | Семейство и основной предел |
|---|---|---|---|
| `audio_temporal_discontinuity` / ATD-LOCAL-1 | RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED | Локальные waveform/energy переходы; существующие precision samples и framing | Общее исследовательское семейство переходов; plosive/перкуссия/quality artifacts дают сходный response |
| `audio_spectral_consistency` / ASC-TV-1 | RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED | TV нормированных magnitude spectra и отдельный flux; готовый M1 STFT | То же семейство, без независимого голоса; фонемы/ноты/EQ/codec меняют спектр |
| `audio_background_noise_consistency` / ABN-FLOOR-1 | RESEARCH_ONLY / WEAK_SIGNAL | Описательные low-energy spectral floors; M1 STFT достаточен для измерений, но не для выделения фона | То же семейство условно; content/background matching не установлен, sensor noise/microphone identity не выводятся |
| `audio_repeated_segment_correspondence` / ARC-NCC-1 | NEEDS_TARGETED_RESEARCH; RESEARCH MEASUREMENT DEMONSTRATED / PRODUCTION PROMOTION DEFERRED | Bounded descriptor retrieval и waveform NCC/support; M1 samples/STFT | Отдельный исследовательский трек повторов; легитимный loop неотличим по одному соответствию |
| `audio_metadata_container_consistency` / AMC-RESP-1 | REJECT_DUPLICATE_RESPONSIBILITY / OWNER ACCEPTED NEGATIVE RESULT | Проверка пересечения validation, precision и timing обязанностей | Новое forensic-семейство не обосновано; invalid/unknown input не Finding |

Владелец разрешил два отдельных measurement tracks: ATD/ASC измеряются раздельно
и сравниваются внутри одного общего трека переходов, **без fusion**; ARC — отдельный
трек повторного соответствия. Статистическая независимость ARC от transition evidence
не утверждается; production correlation остаётся вопросом последующей validation /
Macro 6, где применимо. ABN не является третьим независимым голосом и остаётся weak.
Отрицательный результат AMC принят: создавать `audio_metadata_container_consistency`
из исследованной ответственности не разрешено, поскольку она не отделена от intake,
preprocessing/container validation, typed source/decoded facts и infrastructure/errors.
Parser/container/validation failure не становится suspicious Finding.

Принятый узкий scope: audio route, 8–48 kHz, mono/stereo, существующие M1-D precision
windows, shared STFT/framing APIs и typed timing/source facts при необходимости,
без downmix/resample и без подразумеваемого full-duration покрытия.
Достаточность preprocessing относится только к этому scope, не всем аудиофайлам.
No-data, недостаток поддержки и технический отказ различаются в исследовании.

Production decision rules/thresholds/severity, Finding types и analyzer IDs
**не выбраны**. Допуск не разрешает production registration, Findings, scoring,
risk contribution, completeness или public contract changes. Семейства относятся
только к исследовательским трекам; production
`correlation_group`, риск и `CONTRACTS.md` §11.4 не изменяются. ATD/ASC/ABN могут
реагировать на один переход, ARC может быть причинно связан с его границами.
Текущий `audio_pcm_quality@1.0.0` и его saturation/quality semantics сохранены;
новое измерение не должно повторно выдавать quality observation как forensic-улику.

Provenance: [M3-R1 в REFERENCES](REFERENCES.md#audio-m3r1), M3-AUD-01–12.
Параметры и комбинации exploratory профилей — собственные предложения проекта;
чужая реализация не скопирована, новые dependencies/datasets не допущены.
G1–G6 закрыты решением владельца; их состояние и принятый следующий scope принадлежат
[ROADMAP, Macro 3](ROADMAP.md#audio-m3r1).
Новые preprocessing capabilities и изменения `CONTRACTS.md` не разрешены.
Если необходимое измерение невозможно честно выполнить на существующих inputs —
**STOP / OWNER GATE**, без скрытого расширения. Новые runtime dependencies запрещены,
SciPy не добавляется. Dataset dependency автоматически не одобрена: реальные записи
допускаются только после проверки provenance/license и предполагаемого использования;
неустановленные права/scope необходимого корпуса или библиотеки требуют owner gate.
Production по-прежнему требует полного gate принятия метода выше. Измерительные
эксперименты одним лишь решением M3-R1A не объявляются выполненными.

**Как читать историю Macro 3 ниже:** промежуточные статусы `OPEN / REQUIRED`,
разрешения на следующее исследование и прежний порядок работ относятся к моменту
соответствующего инкремента. Текущие статусы приведены в таблице выше, итоговые
dispositions — в M3-ATD-D1, M3-ASC-D1 и записи ARC disposition после M3-R3D-F.
Исторические next steps не назначают новую работу; актуальная последовательность
принадлежит [ROADMAP](ROADMAP.md#audio-m3-required-carry-forward).
Принятые ограничения измерений и gate production acceptance сохраняются.

**M3-R2A — DONE / OWNER ACCEPTED RESEARCH RESULT; owner acceptance: 2026-09-26.**
Результаты и frozen V1/V2 protocol hashes — в
[отчёте transition prototype](research/2026-09-26-audio-transition-measurement-prototype.md).
Принятый владельцем исследовательский статус ATD-LOCAL-1 и ASC-TV-1:
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD** для каждого.
Проверенные арифметика/oracles и детерминизм прошли; при почти постоянном RMS
ASC описывает spectral transitions, ATD сохраняет sample-position jump и
level/DC-контекст. Высокие ответы на benign speech/music/transients и неоднозначность
global maxima не дают forensic-селективности. Следующее исследование требует
annotated content-matched events и проверки на независимых source groups.
Целевое продолжение отложено в последовательности работ до последующего решения;
следующий активный трек — measurement research ARC-NCC-1. Обязательства ATD/ASC
не отменены и остаются OPEN / REQUIRED; правило их явного разрешения перед
закрытием Macro 3 закреплено в [ROADMAP](ROADMAP.md#audio-m3-required-carry-forward).
Переход к production calibration не разрешён. Общий transition family сохранён,
fusion и независимые forensic votes не создаются. Формулы не изменены.
Owner-accepted prototype scope остаётся в силе; **production method acceptance
не произошло**, thresholds/Decision Rules не добавлены, реализация анализаторов
и Findings не разрешены и не добавлены. Resource rejection
Vibe Ace сохранён; владелец разрешил outcome-blind замену источника до измерений,
без увеличения бюджета или изменения preprocessing.

**M3-ATD-D1 — DONE / OWNER ACCEPTED DISPOSITION; owner acceptance: 2026-09-29.**
По [review ATD](research/2026-09-29-audio-atd-disposition-review.md) владелец принял
**RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED**, без новой measurement study. Сохранённые M3-R2A
свидетельства подтверждают воспроизводимое описание локальных waveform/energy
переходов и ответ на отдельные controlled step/DC/phase constructions, но не
forensic-селективность. Generated benign attacks/percussion, clipping и level
changes дают сильные ответы; gain/EQ пары разных экспериментальных ролей имеют
одинаковые waveform и ATD outputs. На реальных originals нет event annotations,
поэтому причины отдельных peaks не приписываются plosives или codec artifacts.
Global maxima не обеспечивают общую splice localization. Принятый disposition относится
к нынешнему измерительному профилю, не доказывает невозможность любого будущего
метода и не выбирает production threshold.

**ATD carry-forward — RESOLVED** явным решением владельца. Измерение остаётся
валидным описанием переходов; сильный ответ сам по себе не является достаточным
свидетельством монтажа. Benign и manipulated response ranges существенно
перекрываются. Это не production method acceptance: порог отсутствует, production
анализатор не реализован, Finding не добавлен, severity/risk mapping и
fake/authentic verdict не разрешены. Дальнейших ATD promotion work и экспериментов
в текущем Macro 3 нет; прототип сохраняется как research/descriptive evidence.
Формулы и прототип не изменены. Вывод не зависит от ASC: измерения раздельны,
fusion и статистическая независимость не утверждаются. ASC сохраняет
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD** и становится следующим
активным topic. Датированные записи прежних исследований сохраняют историю
состояния до этого disposition.
Текущее состояние gate — в [ROADMAP](ROADMAP.md#audio-m3-atd-d1).

<a id="audio-m3-asc-d1"></a>

**M3-ASC-D1 — DONE / OWNER ACCEPTED DISPOSITION; owner acceptance: 2026-09-30.**
По [review ASC](research/2026-09-30-audio-asc-disposition-review.md) владелец
явно принял **RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED** на основании
существующих M3-R2A evidence. Запись принятия M3-ASC-D1-A не добавляет экспериментов.

Normalized magnitude spectral TV (D1/D4) воспроизводимо описывает смену формы
спектра, spectral flux (F1/F4) — отдельный положительный magnitude change.
Контролируемые переходы поддерживают физический response обоих измерений;
benign фонемные/перкуссионные/scene proxies, плавная смена частоты, gain/EQ
и высокие ответы реальных speech/music не обосновывают forensic specificity
ни одного из них. Причины отдельных real peaks без event annotations не
устанавливаются. Диапазоны manipulated и benign responses существенно
перекрываются; max-based localization ненадёжна в нескольких real-derived
splice cases. Global maximum и union support не являются найденным cut;
ни одна feature не получила доказанного преимущества в forensic-селективности.

ASC даёт описание spectral change при почти постоянном RMS, отличное от ATD,
но не новый независимый forensic vote. TV/flux и ASC/ATD не сливаются.
Принятый ATD disposition не переоткрывается. Одна малая дополнительная study,
способная изменить disposition текущего ASC профиля, не выделена.
Формулы, M1 STFT и прежние evidence сохранены; post-hoc выбор feature/lag
не выполнялся. Production method не разрешён, production threshold отсутствует,
production analyzer не реализован, Finding не добавлен; severity/risk mapping
и fake/authentic verdict не разрешены. ASC остаётся валидным описательным
измерением; принятый предел forensic-интерпретации не означает его неисправность,
бесполезность или математическую невозможность будущей ценности.

**ASC carry-forward — RESOLVED** явным решением владельца.
**FURTHER_ASC_PROMOTION_WORK_IN_CURRENT_MACRO3: NONE.** Новый ASC experiment
в текущем Macro 3 не начинается. Прототип сохраняется как research/descriptive
evidence для будущей работы, а не как нерешённое обязательство Macro 3.
Состояние carry-forward и следующая работа — в
[ROADMAP](ROADMAP.md#audio-m3-asc-d1).

**M3-R2B — DONE / OWNER ACCEPTED RESEARCH RESULT; owner acceptance: 2026-09-26.**
ARC-NCC-1: **READY_FOR_LARGER_VALIDATION**, только исследовательская готовность.
В [отчёте ARC](research/2026-09-26-audio-repeated-segment-measurement-prototype.md)
разделены 45 controlled cases одной lineage и 35 real/derived cases пяти source
groups. Из 29 controlled truth cases один имеет запрещённое перекрытие; остальные
28/28 прошли bounded retrieval и дали истинный offset. Это проверка correspondence
на заданной матрице, не population recall и не обнаружение монтажа. Легитимные
повторы и tones достигают rho=1; silence/constant не дают определённого NCC.
Формулы, нормализация, support, caps и numeric guard M3-R1 сохранены. Ошибка
накопления обычных prefix sums в первой реализации исправлена компенсированным
суммированием; обе версии, остановленный запуск и независимая диагностика сохранены.
Семь групп arithmetic oracles и 12 cases × 3 exact repeats прошли проверку.
Владелец разрешил следующее source-level исследование в **speech-dominant /
voice-message** domain. Главный контраст на уровне распределений измерений:
**NATURAL RE-SPEECH VS COPIED WAVEFORM** — независимые естественные произнесения
одним человеком того же слова/фразы против повторного использования одного
физически записанного речевого сегмента. M3-R2B это различение ещё не доказал.
Music/tones/alarms/loops/ambience сохраняются как challenge/out-of-domain cases,
не основная calibration population следующего исследования; высокая rho сама
по себе не означает suspicious manipulation. Область всего продукта не сужается.
Для следующей validation принят frozen ARC v2 с compensated float64 accumulation;
точная формула, нормализация, numeric guard, descriptor, search bounds/caps,
overlap exclusions, support, ties и channel behavior сохраняются без настройки
после будущих outcomes. Идентичность v2 и история исправления — в отчёте ARC;
speaker/source grouping и план — в [ROADMAP](ROADMAP.md#audio-m3r2b-speech-validation).
**Production calibration NOT AUTHORIZED.** Разрыв распределений не становится
production threshold без отдельного последующего owner gate.
Production method acceptance, thresholds, Finding,
analyzer implementation/registration и статистическая независимость не заявляются.
Обязательства ATD/ASC не разрешены; их статусы и правило закрытия Macro 3 сохранены.

**M3-R3A — DONE / OWNER ACCEPTED RESEARCH RESULT; owner acceptance: 2026-09-27.**
ARC-NCC-1 сохраняет **NEEDS_TARGETED_RESEARCH**; принят исследовательский
результат, а не production-метод.
[Речевой pilot](research/2026-09-26-audio-arc-speech-source-validation.md)
использовал неизменённый frozen v2, четыре speakers LaMIT, 25 фраз и два
независимых takes (200 originals), speaker-disjoint exploratory/holdout 2/2.
На определённых размеченных cross-сравнениях natural max rho=0.552478 против
minimum copy maximum=0.905596; 98 из100 cases каждого copy-класса имели
допустимую geometry и сохранили истинный offset; два коротких source takes
остались abstentions.
Это 727 лабораторных fixtures, а не 727 независимых speakers или реальные
voice messages. Четырёх speaker groups и неполных natural challenges
недостаточно для широкой validation; global outputs и support описаны отдельно.
Generated tone на независимых takes повышает cross rho до0.965409:
периодический / повторяющийся фон — основной нерешённый confound, без
forensic-вердикта; generated tone/music-like фон может давать correspondence,
перекрывающую наблюдения copied waveform.
Владелец принял ограниченную поддержку рабочей гипотезы: независимое повторное
произнесение той же фразы тем же человеком существенно менее похоже, чем копия
физического waveform, при frozen ARC v2. Четыре speakers, controlled read speech
и только два natural takes на фразу не представляют популяцию реальных
voice messages. Observed separation не является production threshold,
FPR/sensitivity claim или результатом calibration.
Frozen ARC v2 сохранён без изменений: формула, compensated accumulation,
normalization, descriptor, NCC, guard, search bounds, caps, support, ties
и channel behavior. Tuning и production calibration не разрешены;
production Decision Rules / thresholds не созданы, production acceptance нет.
ATD/ASC carry-forward сохранён без разрешения обязательств.

**M3-R3B — DONE / OWNER ACCEPTED BLOCKED FEASIBILITY RESULT;
owner disposition: 2026-09-27.** Текущий owner gate **CLOSED** решением
об отсрочке; corpus gate не объявлен пройденным, новых измерений нет.
[Проверка доступности корпуса](research/2026-09-27-audio-arc-voice-background-validation.md)
не установила primary natural voice-message корпус с подтверждёнными правами,
не менее 12 speakers и тремя независимыми natural takes на repeated prompt.
Статус ARC-NCC-1 остаётся **NEEDS_TARGETED_RESEARCH**, результат измерительной
части M3-R3B — **NOT_EVALUATED**. Это не новое свидетельство за или против ARC.
Принятая ограниченная clean-speech гипотеза M3-R3A и основной нерешённый
confound **PERIODIC / REPEATED BACKGROUND** сохранены. Frozen ARC v2,
production-calibration prohibition и обязательства ATD/ASC не изменены;
автоматический background/applicability gate не создан.
Широкая source-level validation с ≥12 speakers / ≥3 natural takes имеет статус
**DEFERRED UNTIL CALIBRATION / PRODUCTION-READINESS RESEARCH** и не требуется
для текущей дипломной proof-of-concept фазы. First-party acquisition сейчас
не разрешён и не обязателен; внешний recording plan сохранён на будущее.
Разрешённый после disposition scope — M3-R3C stress/challenge validation;
его текущее состояние зафиксировано в [ROADMAP](ROADMAP.md#audio-m3r3c).
Это не population calibration и не выполнение отложенной broad validation;
production threshold/FPR claim не допускаются.

**M3-R3C — DONE / OWNER ACCEPTED RESEARCH RESULT; owner acceptance: 2026-09-28.**
ARC-NCC-1 остаётся **NEEDS_TARGETED_RESEARCH**.
[Дипломная stress/challenge validation](research/2026-09-27-audio-arc-diploma-stress-validation.md)
с неизменённым frozen v2 включает184 cases, 8 speech recordings /7 speakers,
3 music и11 background source groups. Все96 обычных exact/gain/codec/noise
copy-cases сохранили истинный offset с ошибкой0 samples и полным structural
support; это не exhaustive recall или production sensitivity.
Легитимный Vibe Ace excerpt достиг rho0.996936 с последующим support,
перекрывая noise-copy maxima. Shared physical background за независимой речью
дал до0.945472; periodic signals —1. В отдельном cap stress20 true nominations
вытеснены из cap64; все возвращённые пары относятся к background-only тону.
Таким образом, высокий global rho не устанавливает копирование foreground речи.
Владелец принял эти свидетельства и failure map: frozen v2 эффективно находит
известные физические копии в проверенных controlled cases, но высокий rho
не специфичен для manipulated speech. Легитимная музыка, механическая
периодичность, общий физический фон и generated tone/hum/beep/rhythm могут
давать copy-like correspondence. Один rho threshold сам по себе не решает
наблюдаемую проблему forensic interpretation. Applicability/background attribution
и bounded retrieval competition остаются нерешёнными методологическими вопросами;
ARC **не готов к tuning/calibration study**. Новый автоматический gate не создан.
Принят исследовательский результат, не production-метод или FPR/sensitivity
validation. Frozen v2 сохраняется и для следующего исследования; ARC v3
не разрешён. Планирование M3-R3D и будущий gate перед любым изменением
candidate/search поведения зафиксированы в [ROADMAP](ROADMAP.md#audio-m3r3d).
Original speech определена только в4/8 cases из-за geometry; controlled read
speech и generated overlays не являются natural voice-message validation.
Три full-source resource rejections сохранены отдельно от заранее созданных
native-rate/channel excerpt fixtures; runtime preprocessing не расширен.
Formula/search/caps/guard/support/channels не менялись. Production calibration,
thresholds, method acceptance, analyzer/registration, Finding и risk/correlation
изменения отсутствуют. ATD/ASC **REQUIRED CARRY-FORWARD** не разрешён.

**M3-R3D-P — DONE / OWNER ACCEPTED DESIGN RESULT; owner acceptance: 2026-09-29.**
[Анализ существующих M3-R3C outputs](research/2026-09-29-audio-arc-applicability-retrieval-design.md)
разделяет waveform correspondence и attribution foreground/background.
Attribution из существующих outputs — **PARTIAL**: информация позволяет
описывать известные fixtures, но для неизвестной записи support, channels и lag
concentration сами по себе не доказывают манипулированную речь.
В cap stress20 true nominations имеют ranks518–585 и теряются на global
distance ranking → cap64 до NCC;
все64 retained pairs относятся к одной известной periodic tone family.
Post-attribution не возвращает отброшенные пары, а concentration встречается
и у настоящих копий. Владелец принял рекомендацию исследования:
**COMBINED_ATTRIBUTION_AND_DIVERSIFICATION_STUDY_REQUIRED**; efficacy нового
retention не проверена, но retention diversification research обосновано.
Необходимость отдельного automatic applicability method — **UNCERTAIN**.
Принят design result, не production method, labels/Decision Rule или
FPR/sensitivity validation; analyzer/Finding не разрешены.
ARC-NCC-1 сохраняет **NEEDS_TARGETED_RESEARCH**, frozen v2 неизменён;
ARC v3 implementation и tuning/calibration не разрешены. Разрешённый владельцем
исследовательский M3-R3D-E и его точные границы находятся
в [ROADMAP](ROADMAP.md#audio-m3r3d).

**M3-R3D-E — DONE / OWNER ACCEPTED RESEARCH RESULT; owner acceptance: 2026-09-29.**
[Attribution/retention experiment](research/2026-09-29-audio-arc-attribution-retention-experiment.md)
на всех184 M3-R3C cases воспроизвёл frozen-v2 baseline точно и сравнил R0–R3
без изменения union, caps, descriptor или NCC. R1/R3 сохранили в cap stress
по2 true nominations, сходящиеся к одной refined паре с ошибкой311samples:
within±4096 и structural support, но **не exact physical offset**. R0/R2 truth
не сохранили. Все policies имеют retained/localized/exact96/96 ordinary copies;
R1/R3 уменьшили число retained truth pairs с1485 до673. Высокая benign
correspondence сохранилась; automatic attribution не решена.
Принятый outcome: **DIVERSIFICATION_PROMISING_OWNER_GATE_FOR_FUTURE_ARC_CHANGE**,
лучшая research policy **R1 / EXACT_OFFSET_ROUND_ROBIN**;
attribution **ATTRIBUTION_EXISTING_OUTPUTS_PARTIAL**.
R1 принят только как исследовательское направление, не как ARC implementation
или production behavior. Свидетельство rescue ограничено одной constructed
cap-stress geometry; сокращение truth pairs не означает улучшения recall/sensitivity.
Владелец принял результат вместе с исправлением serialization validation guard
harness; исходный freeze, остановка и traceback сохранены в истории отчёта;
selectors и параметры не менялись. Frozen v2 неизменён, ARC v3 и production
tuning/calibration не разрешены; ARC-NCC-1 **NEEDS_TARGETED_RESEARCH**.
ATD/ASC carry-forward остаются нерешёнными.

**M3-R3D-F — DONE / OWNER ACCEPTED RESEARCH RESULT; owner acceptance: 2026-09-29.**
[Предобъявленное сравнение](research/2026-09-29-audio-arc-r1-flooding-confirmation.md)
неизменённых R0/R1 на8 новых fixtures дало **R1_FLOODING_CONFIRMATION_MIXED**:
все8 имеют nominated truth, потерянную R0 на cap64; R1 восстановил localized
correspondence в5/8, exact physical offset в2/8. Rescue встречается во всех4
background families, но три source/geometry2 synthetic cases не восстановлены.
Две записи принадлежат одному speaker; source и placement меняются совместно,
поэтому их причинные эффекты не разделены. Offset diversity сама по себе
не гарантирует rescue. Старый control и96/96 retained/localized/exact ordinary
copies точно воспроизведены; truth pairs R0/R1=1485/673, case regression нет.
Вывод ограничен bounded challenge, не population sensitivity или automatic
semantic attribution. Frozen ARC v2 и R1 неизменны; production tuning/calibration,
thresholds и ARC v3 не разрешены. ARC-NCC-1 **NEEDS_TARGETED_RESEARCH**;
ATD/ASC carry-forward нерешён. Текущая очередность — в
[ROADMAP](ROADMAP.md#audio-m3r3df).

**ARC disposition владельца от 2026-09-29: RESEARCH MEASUREMENT DEMONSTRATED /
PRODUCTION PROMOTION DEFERRED.** Сохраняется **NEEDS_TARGETED_RESEARCH**:
frozen v2 остаётся действующим исследовательским measurement prototype;
controlled copy correspondence и bounded retrieval flooding продемонстрированы,
R1 даёт частичное mitigation evidence. R1 **не является универсальным решением**
flooding, но полезный результат не ограничен прежним250Hz fixture. Сохраняются
3/8 нерешённых failures, лишь2/8 exact localizations и сокращение retained
truth-pair multiplicity1485→673. Надёжное production-safe retention поведение
не установлено; automatic semantic applicability/foreground-background attribution
не решена. R1 — **PROMISING FUTURE RESEARCH DIRECTION**, не принятая ARC implementation.
ARC v2 — **FROZEN RESEARCH BASELINE**; ARC v3 — **NOT AUTHORIZED**.
Production promotion отложено до последующих calibration / production-readiness
research; дальнейшее ARC retention development выведено из оставшегося пути
закрытия текущего Macro 3. Это не разрешает tuning R1, новые quotas/tolerances,
thresholds, expansion search/caps или production analyzer. Новых ARC экспериментов
в текущем Macro 3 не назначено; следующий активный topic определён ROADMAP.

<a id="audio-m3h-a01"></a>

**M3H-A01 — ARC Companion Applicability / Context Qualification:
DEFERRED RESEARCH HYPOTHESIS (owner decision: 2026-09-29).**
Это сохранённая исследовательская гипотеза, не принятый метод или активная задача.
ARC может отвечать только за repeated waveform correspondence; отдельный будущий
companion method **может** квалифицировать контекст именно ARC-matched windows:
speech-dominant, stationary/background-like, tonal/periodic, mixed либо ambiguous.
Такие описания квалифицируют свидетельство, но сами по себе не дают verdict
о манипуляции и не создают независимый forensic голос.

Гипотеза не предполагает, что произвольная смешанная запись надёжно разделяется
на speech/music/noise. Если исследование будет отдельно разрешено, первоначально
рассматривается существующий mixed signal и bounded representations: локальная
waveform structure matched windows, существующий STFT, stationarity,
tonal/periodic structure, temporal variation, speech-like activity лишь при
доступности без новой capability. Это **иллюстративные направления**, не
утверждённые features, detector, classifier, score или thresholds.

**AMBIGUOUS / UNRESOLVED — допустимый исход** будущей context qualification.
Например, речь поверх повторяющейся музыки или устойчивого фона может давать
сильную correspondence, не позволяя установить источник совпадения по mixed
signal. Нельзя принуждать fake/authentic или foreground/background conclusion
без достаточного свидетельства. Это исследовательский/архитектурный принцип,
не новый public result schema или изменение correlation policy.

Если qualification требует source separation, speech/background separated
streams, новой ML model, preprocessing capability, dependency или representation
вне принятой предобработки: **STOP / SEPARATE OWNER GATE**. Source separation
не входит в текущий implementation scope Macro 3. M3H-A01 не разрешает сейчас
эксперимент, второй analyzer, speech/music detector, новые STFT features,
schema/correlation changes, dependency или acquisition media. Статус и следующий
ARC scope зафиксированы в [ROADMAP](ROADMAP.md#audio-m3r3de).

## Кандидаты Stage 12 / Macro 2

DQ-HIST-1 / DQ-R3C-1 для `image_jpeg_double_quantization@1.0.0` принят
владельцем 2026-09-24: **ACCEPTED** в точном scope записи ниже. Остальные
имена остаются рабочими кандидатами; Grid сохраняет
**DEFERRED_RESEARCH_ONLY**, readiness — **NOT_READY**.
Остальные сохраняют **CANDIDATE / METHOD NOT YET ACCEPTED**.
Текущий статус работ и очередность хранятся только в `ROADMAP.md`.

| Рабочее имя | Методологический gate |
|---|---|
| `image_jpeg_double_quantization` | DQ-HIST-1 / DQ-R3C-1 ACCEPTED; DQ-G1–G4 CLOSED; разрешена реализация точного принятого scope |
| `image_jpeg_grid_consistency` | DEFERRED_RESEARCH_ONLY; реализация Grid не разрешена, требуется отдельное принятие метода |
| `image_noise_residual_consistency` | M2-BR1: N-MAD-MATCH-1, рекомендация RESEARCH_ONLY / WEAK_SIGNAL; production-метод не принят |
| `image_resampling_consistency` | M2-BR1: R-D2-MATCH-1, рекомендация RESEARCH_ONLY / WEAK_SIGNAL; production-метод не принят |
| `image_embedded_thumbnail_consistency` | M2-CR1: THUMB-NCC-GRAD-1, рекомендация RESEARCH_ONLY / WEAK_SIGNAL; production-метод не принят |

Исследование M2-R1 сохранено в
[отчёте от 2026-09-23](research/2026-09-23-jpeg-dq-grid-method-selection.md).
Запись DQ ниже включает принятое правило и semantics production findings.
Принятие разрешает реализацию, но не означает готовность, включение в каталог,
прохождение тестов или release certification. Grid остаётся предложением.

Исследовательский gate M2-BR1 сохранён в
[отчёте от 2026-09-24](research/2026-09-24-image-noise-resampling-method-selection.md).
Точные exploratory profiles и micro-pilot не являются нормативными методами:
у N не подтверждена устойчивость после brightness/texture matching, у R —
различение при JPEG и periodic texture. Production thresholds, severity и
Finding types не выбраны; общий gate принятия остаётся открытым для обоих.
Предложенная общая N/R correlation group и её отношения с существующими
группами требуют отдельного решения, не меняют scoring. Provenance —
[M2-BR1 в REFERENCES](REFERENCES.md#m2-br1--классические-residualresampling-методы-2026-09-24).

Исследовательский gate M2-CR1 сохранён в
[отчёте thumbnail](research/2026-09-24-image-embedded-thumbnail-method-selection.md).
Узкий исследованный scope — стандартный EXIF IFD1 JPEG thumbnail внутри JPEG;
MakerNote и другие previews не включены. Content comparison отличается от
проверки metadata, но benign crop и неустановленная geometry не позволяют
рекомендовать production-калибровку. Нужны отдельный допуск bounded preprocessing
capability и согласование отсутствия/ошибок вложенного изображения; существующие
metadata checks этим не расширяются. THUMB-NCC-GRAD-1 — только exploratory
профиль, без production threshold, severity, Finding type и принятой correlation
group. Общий gate остаётся открытым; provenance —
[M2-CR1 в REFERENCES](REFERENCES.md#thumbnail-m2cr1).

## M2-R1–M2-R4: основания и границы предложений

Абзацы M2-R1–M2-R3D ниже описывают состояние соответствующего инкремента.
Текущая принятая спецификация DQ дана в записи DQ-HIST-1; DQ-G1–G4 закрыты
явным решением владельца M2-R4 от 2026-09-24.

Дата предложения: 2026-09-23. M2-R1 принят владельцем как исследовательское
свидетельство согласно заданию M2-R2; принятие production-методов отсутствует.
Оба результата отбора — **RESEARCH_ONLY_NOT_READY**. Это завершённое целевое
исследование с открытыми gates, а не разрешение реализации M2-A.

Обозначения порогов: **A** — опубликованный; **B** — математически выведенный
в явно указанной модели; **C** — требует проектной эмпирической калибровки;
**D** — структурная применимость/безопасность, не порог подозрения.
Числовой параметр измерительного профиля не становится forensic-порогом.

Предлагаемое evidence family — **JPEG compression history**. Если после
калибровки оба анализатора получат findings, все их file/region findings в
одном анализе должны использовать одно непустое значение
`correlation_group="image_jpeg_compression_history"`. Это предложение значения
существующего поля, не новое поле/enum и не изменение движка. По
`CONTRACTS.md` §11.4 учитывается максимальный вклад severity в группе;
остальные findings остаются в объяснении. Нельзя давать разные группы по
analyzer ID, частоте DCT, компоненту, окну или фазе. Исключения из группировки
в M2-R1 не предлагаются; более широкий пересмотр остаётся Macro 6.

До принятия и калибровки production activation запрещена. Допустимый отдельный
вариант решения владельца — принять только измерительный scope без findings:
`score=null`, `score_name=null`, `candidate_findings=[]`, ограниченные скалярные
`raw_metrics` и явное предупреждение, что детектор истории сжатия не откалиброван.
Такое решение о включении в активный профиль ещё не получено. Оно не разрешает
называть отсутствие findings
успешной проверкой подлинности или засчитывать измерение как валидированный
детектор: смысл покрытия активного профиля должен быть согласован до включения.

**Ограниченное разрешение M2-R2 от 2026-09-23.** Владелец явно разрешил
изолированный research-only measurement/calibration harness для точных
предложенных процедур DQ-HIST-1 и GRID-PHASE-1 ниже. Это разрешение реализовать
измерения в `scripts/research/`, арифметические тесты и контролируемые эксперименты
с медиа и таблицами вне репозитория. Оно не разрешает production-анализаторы,
регистрацию IDs, findings, вклад в риск/полноту, активацию каталога, публичные
API/config/schema, production-пороги или новые runtime-зависимости.
Используются существующие Macro 1 preprocessing и controlled numeric/PNG access;
для Grid — обратная EXIF-перестановка и bounded tile/luminance kernels.
Это не закрытие production gates DQ-G1–G4 / GRID-G1–G4 и не вариант активного
измерительного анализатора из предыдущего абзаца. Результаты и ограничения
эксперимента сохраняются в
[отчёте M2-R2](research/2026-09-23-jpeg-dq-grid-calibration.md).
По результатам M2-R2 оба профиля остаются `RESEARCH_ONLY_NOT_READY`,
калибровочный вывод — `CALIBRATION_NOT_READY`: измерения воспроизведены,
но controlled corpus показывает content/challenge overlap и не устанавливает
population FPR. Для всех нерешённых порогов класса C — `INSUFFICIENT_EVIDENCE`;
числовые production thresholds не предлагаются. Требуются независимый реальный
корпус с provenance/правами и заданный владельцем operating target.
Предлагаемая общая correlation group сохраняется; принятие методов отсутствует.

**Исследовательское продолжение M2-R3C от 2026-09-24.** По явному разрешению
задания подготовлено полное research-only правило `DQ-R3C-1`: выбор семьи
на 200 calibration groups, фиксированные support/aggregation/abstention semantics,
канонический freeze artifact и отдельная validation на 100 группах. Точная процедура,
hashes и результаты находятся в
[отчёте R3C](research/2026-09-24-jpeg-dq-final-calibration.md).
Это proposed complete research rule, не production threshold или `ACCEPTED`.
Измерительные формулы DQ-HIST-1 ниже не изменены; агрегация используется только
в отдельном исследовательском правиле. DQ-G1–G4 не закрыты; на момент R3C
untouched holdout и принятие владельцем оставались отдельными шагами.
Grid не перекалибровывался.

**Исследовательское продолжение M2-R3D от 2026-09-24.** M2-R3C принят
владельцем; `DQ-R3C-1` однократно применён без изменений к final holdout,
замороженному до исходов. По pre-outcome owner decision вместо 500 включён
максимум после QA — 320 независимых source groups. Результат:
0 FP / 308 applicable, 12 abstentions, 0 admission failures;
one-sided exact 95% upper 0,9679255008705269% ≤1%, `FINAL_HOLDOUT_PASS`.
Hashes, состав, границы независимости и strata — в
[отчёте R3D](research/2026-09-24-jpeg-dq-final-holdout.md).
Это свидетельство для исследованной single-history смеси, не универсальная
гарантия для JPEG. Coverage 96,25% против 98% в validation описывается без
нового acceptance threshold; интерпретация остаётся владельцу. Ограниченная
чувствительность reverse/same-DQT/close-quality из R3C не устранена.
На завершение R3D method acceptance, DQ-G1–G4 и production promotion
оставались открыты; M2-A не был разблокирован.

**Owner acceptance M2-R4 от 2026-09-24.** Владелец явно принял полную
спецификацию DQ-HIST-1 / `DQ-R3C-1` для production implementation в точном
документированном scope, включая все support gates, boundary behavior,
Finding semantics, insufficient_evidence, полноту, ресурсы и ограничения
переносимости. Статус метода — `ACCEPTED`, DQ-G1–G4 — `CLOSED`.
Принятие исследовательской цепочки M2-R1–M2-R3D сохранено.
Новых измерений, tuning или переинтерпретации final holdout нет. Grid остаётся
`DEFERRED_RESEARCH_ONLY`: в R3B multiple phases наблюдались у 9/20 локальных
patches и 8/20 benign crop/recompress, что не даёт достаточного различения.

`insufficient-evidence` ниже — смысл результата, не новый `AnalyzerStatus`.
Предлагается: известное несоответствие входа области метода — `not_applicable`;
пустая/вырожденная статистическая опора после корректного измерения —
`completed`, пустые findings, `score=null`, явное ограничение и счётчики опоры.
Повреждённый required artifact, нарушение identity/shape/length — ошибка,
не отсутствие сигнала. Timeout/resource failures сохраняют действующие
границы orchestration/preprocessing, не превращаются в benign verdict.

## DQ-HIST-1 — гистограммное измерение DCT

### Идентичность, принятие и цель

- Принятый Analyzer ID: `image_jpeg_double_quantization`, версия
  анализатора `1.0.0`.
- **ACCEPTED**: явное решение владельца M2-R4 от **2026-09-24** принимает
  полную спецификацию ниже без изменения frozen rule и ограничений.
  Текущий статус реализации M2-A, её проверок и приёмки — в [ROADMAP](ROADMAP.md).
  Принятие метода не означает приёмку реализации или release certification.
- Evidence family / correlation group: `image_jpeg_compression_history`.
- Наблюдение: заполненность, нулевые значения и спектральная структура
  гистограмм квантованных AC-коэффициентов по отдельным компонентам/частотам.
- Методическая основа: [JPEG-PF04](REFERENCES.md#jpeg-pf04),
  [JPEG-LF03](REFERENCES.md#jpeg-lf03). Конкретный bounded профиль ниже —
  **project-specific heuristic**, а не воспроизведение опубликованного
  классификатора. [JPEG-BP12](REFERENCES.md#jpeg-bp12) остаётся альтернативой
  для последующего выбора калиброванного likelihood-детектора.

### Применимость и входы

Только `image`, JPEG с уже успешной Macro 1 предобработкой: 8-bit SOF0/SOF2,
`OriginalImageFacts`, `JpegHeader`, выбранные по component selectors DQT и
`JpegCoefficientsDescriptor(decode_quality="clean")`.
Demand — существующий `jpeg_coefficients` с его зависимостями; чтение только
через `AnalyzerRequest.read_numeric`. Нет локального JPEG parser/decode,
реконструкции DCT из PNG или повторного кодирования.

Planes — `<i4`, `(block_y, block_x, 8, 8)`, native SOF order; DQT — natural
row-major, не zigzag. Компоненты не называются Y/Cb/Cr по одному индексу:
manifest не гарантирует такую семантическую маркировку. Каждая plane измеряется
отдельно; никаких объединённых chroma/luma histogram и голосования каналов.
Production scope предложения — source mode `L` с одним компонентом или `RGB`
с тремя компонентами. Для RGB sampling в SOF order: `(1,1),(1,1),(1,1)`;
`(2,1),(1,1),(1,1)`; `(2,2),(1,1),(1,1)` — соответственно 4:4:4/4:2:2/4:2:0.
Для L — `(1,1)`. Это исследованные component layouts, не утверждение одинаковой
чувствительности. Иные/неизвестные source modes и layouts вне production scope
дают `not_applicable`, если предобработка уже успешно предоставила факты.
Прежний измерительный протокол может описывать до четырёх компонентов;
это не расширяет область применения предлагаемого decision rule.

Non-JPEG — `not_applicable`. Unsupported coding/precision и превышение
preflight limits обрабатываются действующим preprocessing; анализатор их не
обходит. Progressive допустим только после завершённого clean decode всех
scans. Последовательность scans сама по себе не является recompression.
Неизвестная EXIF orientation не мешает глобальной native-гистограмме;
локализация в ориентированном изображении в этом профиле не выполняется.

### Детерминированная процедура измерения

1. Проверить согласованность facts/descriptor/table selectors и provenance.
   Для компонента c с sampling `(h_c,v_c)` использовать только блоки
   `0 <= bx < floor(W*h_c/(8*max_h))`,
   `0 <= by < floor(H*v_c/(8*max_v))`. Это консервативное исключение краевых
   блоков с неполной исходной опорой, включая возможное дополнение MCU.
   Зафиксировать число использованных и исключённых блоков. `N_c=0` —
   недостаточная опора, без подстановки padded blocks.
2. Взять множество AC modes `F={(u,v): 1 <= u+v <= 3, u,v >= 0}` — девять
   частот, обход по `(u,v)` лексикографически. DC исключён, чтобы смещение
   яркости не доминировало. Это собственный симметричный low-frequency
   измерительный профиль; его forensic оптимальность не установлена.
3. Для каждой пары `(c,u,v)` построить signed histogram
   `H(k)=sum_b 1[C_b(u,v)=k]`. Не брать абсолютные значения, не удалять ноль,
   не winsorize, не подменять кванты JPEG quality factor.
   `a=min C`, `b=max C`, `R=b-a+1` вычислять без int32 overflow.
   При `R>65536` не выделять dense histogram: записать число блоков, границы
   диапазона и ограничение измерения. Сначала собрать min/max, затем выделять
   bounded dense histogram. Предел — D, ограничение workspace;
   выход за него не признак редактирования и не утверждение о валидности JPEG.
4. При `N_c>0` и допустимом R нормировать `h(k)=H(k)/N_c`.
   Записать `q2=Q_c[u,v]`, `N_c`, `R`, число занятых bins, `H(0)/N_c`
   (ноль вне диапазона даёт 0) и долю пустых bins внутри `[a,b]`:
   `(R-count(H>0))/R`. Это плотность опоры, не частота ложных тревог.
5. `L=2^ceil(log2 R)` (при R=1 положить L=1). Заполнить первые R значений
   вектора `z[r]=h(a+r)`, остальные — нулями. Вычислить NumPy rFFT с
   `norm="backward"`; `A_j=abs(sum_{r=0}^{L-1} z[r] exp(-2*pi*i*j*r/L))`.
   Для `j=1..floor(L/2)` выбрать максимум, при точном равенстве — меньший j.
   Скалярные выходы: `j/L` cycles/bin и `A_j` (математический диапазон `[0,1]`,
   floating roundoff не является forensic сигналом). Не округлять j/L
   до предполагаемого q1. R=1 — спектральные показатели `null`, а не 0.
   FFT zero padding интерполирует спектр, но не создаёт новых наблюдений.
6. Обход SOF components и F фиксирован. Не агрегировать пики в общую оценку
   риска, не выбирать «самый подозрительный» канал. До 36 записей скалярных
   диагностик; полные histograms/spectra остаются внутренними и не передаются
   в `raw_metrics`, metadata или ответ worker. В production scope максимум
   27 записей; правило ниже использует только девять modes первого компонента.

Эти измерения, включая диагностическую FFT, сохраняются без изменения.
FFT amplitude/frequency и остальные компоненты не участвуют в решении.
Привязка индексов: `u` — первая частотная ось 8×8, `v` — вторая;
`q2=table.values[8*u+v]`. Нельзя менять порядок SOF по component ID.

Нулевой/однозначный histogram и один блок измеримы, но не дают статистической
доказательности. Преобладание нулей, sparse tails, гладкая огибающая и обрезание
опоры сами создают спектральные максимумы. Профиль намеренно сохраняет эти
ограничения; произвольный high-pass, удаление центральных bins или threshold
не добавляются для получения желаемого результата.

### Модель DQ и предел восстановления q1

Для объяснения, отдельно от измерительного алгоритма, положим
`R+(t)=floor(t+1/2)`, `q1,q2` — положительные целые:

```text
k = R+(q1 * R+(t/q1) / q2)
n(k;q1,q2) = ceil((k+1/2)*q2/q1) - ceil((k-1/2)*q2/q1)
T = q1 / gcd(q1,q2)
```

Здесь n — число значений первого квантованного индекса, попадающих во второй
bin. Из `n(k+T)=n(k)` следует возможная периодичность; `n=0` означает
недостижимый bin только в этой идеальной модели. При `q1=q2` n постоянно;
при некоторых кратных отношениях модуляция также исчезает. Вывод B относится
к заданному rounding, не ко всем JPEG encoders. Реальные IDCT, округление,
clipping и повторный DCT размывают этот рисунок; правило floor из PF04 нельзя
молча переносить на signed rounding реального encoder.

Фактически известен только q2 из файла. Даже точный период T не определяет q1
однозначно; округлённый FFT peak тем более не восстанавливает таблицу или
quality setting. q1 estimation в DQ-HIST-1 **не выполняется**. Near-same
таблицы проверять поэлементно: близкие quality labels могут дать одинаковые
q на выбранных modes. Shifted-grid recompression не соответствует этой модели;
отсутствие DQ-пиков ничего не исключает. Проверить прошлую aligned-сетку по
нынешнему header нельзя, поэтому это ограничение inference, не проверяемый
флаг применимости.

### DQ-G1 — фиксированный профиль решения

Правило `DQ-R3C-1` применяется к измерениям выше. Только первый компонент
**в SOF order**, независимо от его числового ID, даёт голоса. F содержит ровно
`(0,1),(0,2),(0,3),(1,0),(1,1),(1,2),(2,0),(2,1),(3,0)`.
Не выбирать компонент, mode или metric по величине сигнала.

Valid mode одновременно удовлетворяет всем условиям:

- состояние histogram — `measured`: `N>0`, `2<=R<=65536`;
- полных native blocks `N>=1024`;
- nonzero observations `N-round(N*zero_fraction)>=256`, где
  `zero_fraction=H(0)/N`; используется Python `round` (ties-to-even), как в R3C;
- `occupied=count(H>0)>=8`;
- `span=R>=16`.

Счётчики исходного histogram целочисленные; восстановление nonzero из
`H(0)/N` сохраняет точное число в данном bounded диапазоне. Округление
диагностик до проверки опоры запрещено. `no_full_blocks`, `constant`,
`histogram_limit` и modes ниже любой границы исключаются, а не получают score=0.
Отсутствующая/повторная mode, несогласованный manifest, NaN/Infinity либо
некорректная измеренная метрика — ошибка, не статистическое воздержание.

Для каждого valid mode `empty_fraction=(span-occupied)/span` на **полном signed
диапазоне от min до max включительно**, с пустыми bins и без удаления нулевого
bin, если он входит в диапазон; при нуле вне диапазона `H(0)=0`.
Никакого tail trimming, удаления нуля, объединения знаков или подбора q2 нет.
Требуется минимум **5 valid modes из 9** первого компонента. При меньшем числе
image score отсутствует и решение — `insufficient_evidence`, никогда negative.
При достаточной опоре image score — `statistics.median` их `empty_fraction`:
для чётного числа — арифметическое среднее двух центральных значений.

Числа — Python float / binary64, без предварительного округления, epsilon,
clamp и адаптации к размеру/quality. Positive строго при
`score > 0.6005747126436781`; равенство и меньший score — отсутствие сигнала.
Здесь `score` — внутреннее измерение, не поле `AnalyzerResult.score`.
Пять modes и все support boundaries включаются по `>=`; R=65536 допустим,
R=65537 исключает mode до dense allocation. Повтор на тех же коэффициентах
должен давать те же support, score и decision. Cross-platform bit identity
всего native decoding/FFT принятой цепочкой не установлена.

### DQ-G2 — происхождение порога и переносимость

| Условие/параметр | Класс и основание | Разрешённый смысл |
|---|---|---|
| 8-bit SOF0/SOF2, clean artifacts, полный 8×8 support | D; существующий Macro 1 контракт | Можно читать измерения |
| N=0, R=1 | D; пустая/вырожденная выборка | Нет статистической опоры/спектра |
| R<=65536, девять AC modes | D для памяти; modes — параметр собственного профиля | Ограничение вычисления, не качество детектора |
| n=0, период T | B; идеальная модель выше | Объяснение механизма, не positive rule |
| N>=1024, nonzero>=256, occupied>=8, span>=16; минимум 5 modes | Предобъявленные support gates R3C, не универсальная граница информативности | Ниже опоры — `insufficient_evidence` |
| Медиана empty_fraction > 0.6005747126436781 | C; calibration R3C, затем untouched R3D | Только узкий recompression-history signal |

R3C сравнил ровно две предобъявленные семьи: медианы `empty_fraction` и
`amplitude` на одинаковой опоре. Порог каждой — максимум применимых primary
negative scores calibration200 (97 pilot + 103 новых RAW source groups).
Выбрана empty fraction по большей unconditional aligned40to90 sensitivity:
136/200 против 2/200; tie rule отдавал предпочтение empty fraction.
Порог не подбирался по validation/holdout. Calibration 0/191 primary FP не
является независимой проверкой после выбора; дополнительный парный single90
дал 1/199 FP, и этот результат не был устранён настройкой.

Независимая validation100: 0/98 primary FP, abstentions 2,
one-sided exact 95% upper 3,0106198695%. Final untouched holdout:
assigned/admitted 320/320, applicable 308, FP 0, abstentions 12,
admission failures 0; observed FPR 0%, one-sided exact 95% Clopper–Pearson
upper **0,9679255009% <=1%**, `FINAL_HOLDOUT_PASS`.
Граница при нуле ошибок — `1-0.05^(1/308)`; знаменатель не 320 и не число
производных. Это эмпирическое свидетельство для применимой части оценённой
целевой популяции, не универсальная гарантия ≤1% на всех JPEG и не вероятность
ложности отдельного Finding. Принятое в R4 свидетельство coverage — 96,25%
против 98% validation; отдельный coverage PASS/FAIL задним числом не вводится.

Финальный canonical rule SHA-256:
`2b958bf4fb94926c7f7de0a9a7b74f3897667a22cb802fb85592bab4dd5fd5be`.
Measurement implementation fingerprint R3C:
`f71d85640aa1624ad116a0da6e66401e329220231df642b0b25ca49ea43a21cf`.
Holdout membership SHA-256:
`99e52cc1f785bcaaaa8ca423e1c0c5487cb882d56b5e01bcf5f0027e8687a189`.
Это привязки принятых свидетельств, не fingerprint production-реализации.

Population — отобранные PIXLS CC0 RAW, фиксированная AHD/LibRaw проявка в RGB8,
Lanczos без upscale до 1280 по стороне / 1 000 000 pixels, Pillow JPEG.
Primary negative — один single-history endpoint/source group: quality
40/75/95, RGB sampling 4:4:4/4:2:2/4:2:0, каждый десятый grayscale,
каждый пятый progressive. Grayscale и progressive связаны дизайном.
Quality labels — настройки encoder, не q2 из DQT. Source/scene/hash/session
QA и outcome-blind freeze описаны в R3C/R3D; holdout включает все 320
пригодных групп по pre-outcome owner decision без post-outcome добора.

Пределы переноса обязательны в интерпретации результата:

- compatibility corpus не является репрезентативной случайной выборкой всех
  камер, контента или пользовательских workflows; у 118/320 holdout sources
  неизвестна дата сессии, make/model не доказывает физическое устройство;
- visual/hash QA не доказывает исчерпывающую независимость сцен; малые
  device/content strata не имеют собственного подтверждения ≤1%; периодических
  текстур в validation и holdout только по две группы, noise/ISO strata не заданы;
- RAW development/resize могут сглаживать шум и текстуру. Camera-native JPEG,
  другие encoders, custom/trellis DQT, большие размеры и неизвестные сложные
  workflows не получают подтверждённого FPR из этого опыта, даже если
  технически допускаются Macro 1 и профилем. Resize для обхода лимитов запрещён;
- VISION pilot — отдельное exploratory свидетельство, не validation frozen
  rule и не добавка к primary n; новый VISION stress/holdout здесь не выполнен;
- sensitivity validation остаётся стратифицированной: aligned40to90 —
  **65/99 applicable (65/100 unconditional)**; reverse90to40 — **0/95**,
  same75 — **0/99**, close85to90 — **0/99**; benign repeat — **58/99**.
  Holdout проверял negatives и не улучшает эти sensitivity estimates.

DQ-HIST-1 не является универсальным double-JPEG detector. Новых thresholds,
подстройки по q2/device/content и fallback на amplitude/BP12/Grid нет.
Изменение frozen procedure/support/rule требует отдельного owner gate,
нового исследования и независимой проверки; R4 их не разрешает.

### DQ-G3 — Finding, отсутствие сигнала и полнота

При достаточной опоре и positive выдаётся ровно один candidate Finding на файл,
нормализуемый существующим `FindingFormationService` (`CONTRACTS.md` §9):

| Существующее поле | Предлагаемое значение / смысл |
|---|---|
| `group` | `image` |
| `type` | `jpeg_recompression_pattern`; строковый type, не новый enum/schema field |
| `severity` | `weak`: косвенный технический признак, возможный при обычном экспорте/пересылке |
| `source_analyzer_id`, `source_analyzer_version` | `image_jpeg_double_quantization`, `1.0.0` после реализации и принятия |
| `description` | «Статистика коэффициентов JPEG содержит рисунок, согласующийся с поддержанным сценарием повторного JPEG-сжатия с совпадающей блочной сеткой. Признак возможен при обычном повторном сохранении и не устанавливает подделку или злой умысел». |
| `localization` | `{"type":"file"}`; глобальное измерение, без карты изменённых областей |
| `correlation_group` | `image_jpeg_compression_history` |
| `source_score`, `score_impact` | `null`, `null` |
| `critical_override_eligible` | `false` |
| `evidence_refs` | `[]`: публичные artifacts не создаются |

`finding_id` формируется штатно по §9.5. `AnalyzerResult.score=null`,
`score_name=null` при всех исходах, в соответствии с §9.4. Полей `confidence`
или `evidence_strength` в текущем Finding нет: их не добавлять. Ни величина
empty_fraction, ни upper FPR не являются confidence или вероятностью подделки.
Severity не повышается с ростом score или числом valid modes.

Технические сведения помещаются только в существующий `raw_metrics`:
идентификаторы DQ-HIST-1 / DQ-R3C-1, метрика `empty_fraction`, точный threshold,
image-level median (либо null), трёхзначное решение (positive / no_signal /
insufficient_evidence), первый component ID и valid-mode count. Для каждой
component/mode — ограниченные скаляры: ID, u/v, q2, N, excluded blocks,
state, min/max/span, occupied, zero_fraction, empty_fraction, frequency,
amplitude; для modes первого компонента также valid/support outcome.
Новые top-level поля не вводятся; пути, коэффициентные массивы, histograms,
spectra и corpus records не публикуются. Название внутреннего score всегда
сопровождается пояснением «медиана доли пустых bins», не «вероятность».

| Исход | Статус и данные | `summary` / ограничение |
|---|---|---|
| Positive | `completed`, `applicable=true`, один candidate | «Обнаружен статистический рисунок, согласующийся с поддержанным сценарием повторного JPEG-сжатия с совпадающей сеткой». |
| Достаточная опора, score<=threshold | `completed`, `applicable=true`, findings=[]; измеренная median сохранена | «Поддержанный статистический рисунок повторного JPEG-сжатия не обнаружен. Это не подтверждает подлинность и не исключает повторное сжатие». |
| Меньше 5 valid modes | `completed`, `applicable=true`, findings=[], median=null; счётчики и явное предупреждение | «Недостаточно статистической опоры для вывода об этом рисунке повторного JPEG-сжатия» (`insufficient_evidence`). |
| Non-JPEG или source mode/layout вне scope | `not_applicable`, `applicable=false`, findings=[], score/score_name=null | Указать конкретную известную причину неприменимости; не выводить negative. |
| Повреждение required representation / identity / shape / length | Действующая ошибка execution/infrastructure | Не Finding, не no_signal и не insufficient_evidence. |

Всегда явно сообщать узкую sensitivity/portability область. В частности,
`insufficient_evidence` — смысл измерения, **не новый AnalyzerStatus** и не
`AnalysisCompleteness.status=insufficient`. По неизменному §10 CONTRACTS
такой `completed` учитывается в completed/applicable counts и не добавляется
в `missing_capabilities`. Поэтому итог может быть `complete`, хотя DQ
воздержался: это полнота выполнения активного плана, не полнота forensic
свидетельств. Предупреждение и null median обязательны; отсутствие сигнала
или опоры нельзя называть успешной проверкой подлинности. Research coverage
308/320 — доля поддержанных решений, не runtime `coverage_ratio`.

Рекомендательное пояснение при positive: «Сопоставьте признак с известной
историей экспорта и передачи файла; если происхождение важно для решения,
проверьте источник по независимому каналу». Это пояснение в `summary`, не
новый объект Recommendation и не автоматическое действие. Итоговая
`Recommendation` остаётся по `CONTRACTS.md` §12.3: один weak Finding при
complete даёт 5 баллов/low и `no_additional_action`. Метод не переопределяет
эту политику и не обещает обязательной ручной проверки. При недостатке опоры
пояснить ограничение исходного JPEG; повтор на тех же bytes не создаёт опору.

Запрещены категорические утверждения manipulated/forged/fake/tampered,
«точно повторно сжат», вероятность манипуляции, злой умысел, точное предыдущее
качество/q1, число сохранений/правок, редактор/application identity и подлинность
при отсутствии сигнала. Экспорт, пересылка, обычная коррекция, поворот или
кадрирование могут сопровождаться benign recompression. Обнаружение такой
истории не равно false positive на single JPEG и не доказывает malicious intent.

### DQ-G4 — локализация, ресурсы и scope

Локализация — только файл/фактически учтённые полные блоки; карта изменённых
областей не выводится из глобального histogram. Края исключены и учитываются
в coverage. Correlation — `image_jpeg_compression_history`, включая будущие
JPEG history analyzers и локальные расширения этого семейства. Компонент,
mode, регион или другой analyzer ID не создают независимое доказательство.
По `CONTRACTS.md` §11.4 в группе учитывается максимальный вклад severity,
остальные findings остаются объяснением без повторного вклада. Grid не активируется.

Demand — только существующий `jpeg_coefficients`; зависимости
`jpeg_structure`, `image_coordinates`, `original_image` раскрываются штатно.
Нормализованный PNG остаётся обязательным продуктом preprocessing, но DQ его
не читает, не вычисляет DCT из pixels и не запрашивает residual/grid pipeline.
Границы `CONTRACTS.md` §7.5 / `ForensicResourcePolicy` сохраняются: JPEG input
32 MiB (и более строгий configured intake limit), 256 markers/scans, 1 MiB
marker payload, суммарно `2^22` native **MCU-padded** coefficients, raster
`2^22` pixels. Это hard envelope, не доказательство переносимости порога.

Пусть B — сумма полных блоков: `B<=2^22/64=65536`. Histogram passes — O(9B),
в предлагаемом L/RGB scope FFT — до 27 преобразований длины не более 65536,
O(27 L log L). Компоненты и modes обрабатываются последовательно, не
накапливаются planes/histograms/spectra всех modes. Совокупные int32 planes
Macro 1 — до 16 MiB, native 16-bit coefficients — до 8 MiB в decoder child;
это не сумма полного RSS процессов.

Bounded workspace одного mode (максимум 65536 observations/bins): contiguous
int32 values до 256 KiB, перевод/смещение int64 — до двух буферов по 512 KiB,
int64 histogram до 512 KiB, normalized/padded float64 vectors — до двух
буферов по 512 KiB, complex128 rFFT — до 524 304 bytes и amplitude float64
до 262 152 bytes. Явные числовые temporaries вместе <4 MiB на mode;
профиль выделяет им максимум 8 MiB с запасом, без нового config/policy поля.
Одна читаемая immutable plane до 16 MiB; transient копии controlled reader,
FFT/native allocator и Python overhead не выдаются за включённые в эти 8 MiB.
Эти числовые границы не определяют фактический общий RSS. Статус измерений
worker RSS и ограничения оценки совокупного пика preprocessing и workers —
в [ROADMAP](ROADMAP.md); измеренный worker RSS не подтверждает такой общий пик.
Не использовать 32 MiB residual workspace как дополнительный JPEG artifact budget.

Новых видов artifacts нет: существующие numeric component files и PNG
учитываются вместе с прочими файлами в `_GeneratedArtifactBudget` и лимите
256 artifacts, регистрируются до записи и удаляются общим lifecycle.
64 MiB на numeric artifact не отменяют более строгий JPEG ceiling и общий
configured budget. В R2 2048² noise был корректно отклонён, потому что PNG
плюс 16 MiB coefficients превышали общий 20 MiB budget; лимит не увеличивается,
downsampling и fallback для получения решения запрещены.

Принятые измерения, не новый benchmark: в R3C validation700 сумма DQ 13,21 s,
preprocessing 251,65 s; в R3D на 320 endpoints DQ 6,622 s, preprocessing
129,429 s, весь measurement/reporting wall 140,655 s. Максимальный numeric
artifact 12 138 240 bytes. Средний DQ R3D около 20,7 ms на endpoint не является
worst-case timeout. R3C parent peak snapshots 112 705 536 / 102 428 672 bytes
для calibration/validation не измеряют совокупный parent+child peak. Offline
RAW worker RSS не относится к production JPEG budget. Среда — Windows 11 x64,
Python 3.12.10, NumPy 2.5.2, Pillow 12.3.0, pyjpegio 0.3.0. Это свидетельства
приемлемого bounded research execution, не сертификация production worker.

Preprocessing остаётся владельцем decode/preflight/resource failures:
unsupported coding/precision, native warning/error/timeout, превышение
artifact/input/coefficient budget не превращаются в Finding, `not_applicable`
или no_signal. Применимость проверяется только после успешной предобработки.
Native child использует `min(30 s, remaining budget)`; analyzer worker —
существующий analyzer timeout и remaining overall budget (§8.5–8.6).
Обычный analyzer `timeout` возможен только после подтверждённого reap;
неостановленный reader сохраняет infrastructure failure/cleanup barrier.
Resource exhaustion во время измерения — контролируемый сбой, не abstention;
исключение mode при R>65536 — заранее определённое ограничение опоры,
а не перехват ошибки выделения памяти.

Сохраняются manifest <=16 384 bytes, metadata request <=32 768 bytes,
worker response <=65 536 bytes (AnalyzerResult <=65 509 bytes). Только
ограниченные скалярные diagnostics и максимум один Finding; размер проверяется
штатно после нормализации, overflow — error. R2 diagnostics <=22 079 bytes
не доказывают размер production-конверта: boundary tests обязательны.
Новые runtime dependencies не нужны: NumPy/stdlib считают histogram, FFT и
median, уже принятый pyjpegio предоставляет coefficients через Macro 1.
SciPy, rawpy/LibRaw research environment, модели и сетевой доступ в runtime
не добавляются. Новых YAML/API/schema полей и fallback реализаций нет.

Validation matrix — [DQ-01–DQ-12 и общие проверки](research/2026-09-23-jpeg-dq-grid-method-selection.md#validation).
Особые challenge cases: плоское изображение, синтетические текстуры, мелкий
текст, малое N, сильное квантование, trellis/custom tables, clipping.
Provenance и собственный вклад — [JPEG-M2R1-PROPOSAL](REFERENCES.md#jpeg-m2r1-proposal).

### Свидетельства, приёмочная матрица и owner decision

Принятая исследовательская цепочка:

| Инкремент | Основание для предложения |
|---|---|
| [M2-R1](research/2026-09-23-jpeg-dq-grid-method-selection.md) | Выбор DQ-HIST-1 и собственный bounded профиль, сравнение альтернатив и provenance |
| [M2-R2](research/2026-09-23-jpeg-dq-grid-calibration.md) | Арифметика/synthetic challenges; CALIBRATION_NOT_READY не заменял population evidence |
| [M2-R3A](research/2026-09-24-jpeg-real-corpus-operating-point-design.md) | Права, source-safe split и operating target BALANCED TRIAGE ≤1% |
| [M2-R3B](research/2026-09-24-jpeg-real-corpus-pilot.md) | DQ USEFUL_SIGNAL; Grid WEAK_SIGNAL и DEFERRED_RESEARCH_ONLY |
| [M2-R3C](research/2026-09-24-jpeg-dq-final-calibration.md) | Calibration200, freeze DQ-R3C-1, независимая validation100 и narrow sensitivity |
| [M2-R3D](research/2026-09-24-jpeg-dq-final-holdout.md) | Untouched DQ-only holdout, FINAL_HOLDOUT_PASS без изменения rule/endpoint |

Corpus provenance — [DATASET-PIXLS-CC0](REFERENCES.md#dataset-pixls-cc0),
pilot stress — [DATASET-VISION](REFERENCES.md#dataset-vision), offline development —
[RESEARCH-RAWPY-M2R3B](REFERENCES.md#research-rawpy-m2r3b).
Исследовательская реализация измерения/правила —
`scripts/research/jpeg_measurements.py`, `scripts/research/jpeg_dq_rule.py`;
они служат проверяемым oracle, не production import/dependency.
Новых внешних источников или недостающих provenance linkages не выявлено.

В M2-R4 от 2026-09-24, до реализации M2-A, была зафиксирована следующая
обязательная приёмочная матрица без tuning:

| Область | Обязательная проверка |
|---|---|
| Measurement equivalence | Signed/zero histogram, DQT natural order, native full-block crop, SOF order при нестандартных IDs; совпадение diagnostics/median/decision с frozen research oracle |
| Support/boundary | N 1023/1024, nonzero 255/256, occupied 7/8, span 15/16 и 65536/65537, 4/5 valid modes, constant/no-full-blocks, odd/even median, equality/соседние binary64 значения около threshold |
| Scope и determinism | L/RGB, три sampling layouts, SOF0/SOF2 после всех scans, EXIF 1–8/unknown без изменения native score; non-JPEG/CMYK/unsupported layout; повтор на тех же coefficients |
| Finding / полнота / корреляция | Один weak positive; null public scores; no_signal отдельно от insufficient_evidence; предупреждения и штатные completed counts; одна family без повторного вклада |
| Negatives / positives / benign | R3C/R3D evidence сохраняется; aligned40to90, reverse/same/close, repeated benign export; synthetic textures, flat, clipping, custom/trellis как challenges, не новое независимое n |
| Failure / ресурсы | Missing/corrupt source-bound artifacts, identity/length/shape mismatch, preflight и общий artifact budget, histogram ceiling, worker response boundary, remaining budget, reap/cleanup и peak RSS при допустимой concurrency |

На момент M2-R4 research tests и measurements свидетельствовали об арифметике
и frozen rule, но не подтверждали production integration/resource tests.
Для реализации M2-A требовались focused tests и полный quality barrier;
strict installed certification возможна только по правилам clean committed SHA.
Текущий статус выполнения проверок и приёмки реализации — в [ROADMAP](ROADMAP.md).

| Gate | Owner gate M2-R4 от 2026-09-24 | Принятое решение |
|---|---|---|
| DQ-G1 | `CLOSED` | Измерение DQ-HIST-1 и точное support/median правило DQ-R3C-1 без изменений |
| DQ-G2 | `CLOSED` | Frozen threshold, независимые свидетельства и явные population/portability limits |
| DQ-G3 | `CLOSED` | Один weak Finding, null public scores, отдельные no_signal/insufficient semantics в существующих контрактах |
| DQ-G4 | `CLOSED` | Только image JPEG L/RGB на Macro 1, bounded workspace, прежние budgets/failures, без новых dependencies |

Обязательный owner gate полной записи закрыт решением M2-R4 от 2026-09-24:
метод `ACCEPTED`; на момент этого решения, до реализации, M2-A получил
`READY_FOR_IMPLEMENTATION` только в принятом DQ scope.
Решение M2-R4 само по себе не подтверждает тестирование, включение в активный
план или release certification. Текущий статус реализации M2-A — в ROADMAP.
Grid не включён в разрешение.
Если реализация потребует отклонения от DQ-R3C-1 или ослабления лимитов —
STOP / OWNER GATE, а не скрытая адаптация.

## GRID-PHASE-1 — локальные фазы blocking artifacts

### Идентичность, принятие и цель

- Рабочий Analyzer ID: `image_jpeg_grid_consistency`.
- **PROPOSED / PENDING OWNER ACCEPTANCE; NOT_READY**.
- Текущий допуск: **DEFERRED_RESEARCH_ONLY**; R4 не меняет измерение,
  калибровку или activation Grid.
- Семейство: JPEG compression history; наблюдение — локально доминирующие
  фазы периодических границ, а не общая сила обычного JPEG blocking.
- Основа: [JPEG-GRID20](REFERENCES.md#jpeg-grid20), Algorithm 1, §§2.1–2.5.
  Предлагаемое ограничение окон и точный множитель тестов ниже — собственная
  адаптация; переносимость опубликованной статистической гарантии не доказана.
  Поэтому выбран исследовательский протокол, не production detector.

### Применимость и представления

Только JPEG image, source mode L/RGB, baseline/progressive после корректной
предобработки; `original_image`/`image_coordinates`/`jpeg_structure` и один
существующий `normalized_image` PNG без resize. Pixel count <=`2^22`, известное
EXIF-преобразование 1–8. Анализатор читает подготовленный PNG через controlled
artifact access; исходный JPEG не декодирует. Восстановить native расположение
пикселей обратной точной перестановкой EXIF (без интерполяции), затем измерять.
Так текущая native grid соответствует границам перед x/y=8,16,... независимо
от EXIF и размеров, некратных 8. Нельзя сравнивать oriented phase с native нулём.

`residual_raster` не запрашивать: Macro 1 предоставляет тип и числовые kernels,
но не producer этой capability. Существующие bounded tile/luminance kernels
могут обслуживать чтение подготовленного raster. Требуется только новый
числовой метод, не новый parser, decoder или representation. Выбор этого пути
должен войти в owner acceptance; расширять preprocessing ради удобства нельзя.

Non-JPEG, CMYK/неустановленный source mode, неизвестная orientation,
несогласованная геометрия без доказанного mapping и превышение raster-потолка
входят в ограничения применимости; contract corruption — ошибка.
Нет гарантии, что derived RGB luminance точно равна native JPEG Y.
Grayscale поддерживается; chroma не анализируется. Subsampling может влиять
через RGB-реконструкцию, и это подлежит отдельной проверке. Progressive —
способ передачи окончательных coefficients, не самостоятельная grid anomaly.

### Точный исследовательский протокол

1. Работать в native pixel indices `0<=x<W`, `0<=y<H`. Luminance
   `I=0.299R+0.587G+0.114B`, float64; для исходного grayscale с равными RGB
   каналами взять один канал как float64. Без gamma/ICC-коррекции, resize и
   квантования I. Cross-difference:
   `C(x,y)=abs(I(x,y)+I(x+1,y+1)-I(x+1,y)-I(x,y+1))`.
2. Голосующие центры ограничить `1<=x<=W-3`, `1<=y<=H-3`, чтобы оба соседа
   C были определены без padding. Положить `U=W-3`, `V=H-3`,
   `w=8*floor(min(512,U)/8)`, `h=8*floor(min(512,V)/8)`.
   Если w<64 или h<64 — `not_applicable` по опоре этого профиля, не negative.
3. Множество origins по x: `1+floor(i*(U-w)/3)`, i=0,1,2,3;
   по y аналогично. Удалить точные дубли, взять декартово произведение,
   сортировка `(y,x)`: до 16 окон w×h. Это фиксированное геометрическое
   покрытие, без выбора по содержимому. Окна могут перекрываться; между ними
   нет наблюдений. Работать по одному окну с halo=2;
   reflected border из kernels не должен попадать в измерение.
4. В каждом окне horizontal vote возникает при строгих
   `C(x,y)>C(x-1,y)` и `C(x,y)>C(x+1,y)`; он добавляется в `vx[x mod 8]`.
   Vertical аналогично по y. Равенства не голосуют. Для каждой оси получить
   восемь counts, n=sum counts, m=max counts. Если максимум не единственный,
   phase считается неопределённой; не выбирать меньший индекс как detection.
5. Нормировать counts на n при n>0. При n=0 — неопределённая phase,
   статистический показатель не вычисляется. Boundary phase g означает
   границу **после** пикселя с индексом g mod 8; block-origin phase равна
   `(g+1) mod 8`. Текущему native JPEG соответствует boundary `(7,7)` и
   block-origin `(0,0)`. Этот сдвиг необходимо проверить отдельной фикстурой.
6. Для окна площади A=w*h определить `eta=A/16`, `kappa=ceil(m/2)`, `p=n/A`.
   Число всех прямоугольников с длинами сторон, кратными 8, внутри U×V:
   `Rx=sum_{j=1}^{floor(U/8)} (U-8*j+1)`, Ry аналогично.
   Предлагаемый множитель для каждой оси `Nt=16*Rx*Ry` учитывает восемь фаз
   и две parity-группы и охватывает выбранные окна, включая origins,
   некратные 8. Это собственная замена приближённого множителя GRID20,
   а не утверждение эквивалентности результатов опубликованному коду.
7. Диагностический показатель:
   `ell=log10(Nt)+log10(sum_{j=kappa}^{eta} binom(eta,j)*p^j*(1-p)^(eta-j))`.
   Считать binomial tail полностью в log-space: первый log-term через
   `lgamma`, последующие через отношение
   `t[j+1]/t[j]=(eta-j)/(j+1)*p/(1-p)`; суммирование log-sum-exp с
   `math.fsum` и фиксированным порядком. Никакого обрезания «малого хвоста»
   на выбранном epsilon. При p=0/kappa=0 tail=1; невозможный положительный
   kappa при p=0 — ошибка инварианта. p=1 даёт tail=1. Не сериализовать Inf/NaN.
8. Сохранить на окно native bbox, площадь, n/m и долю максимума по осям,
   уникальную phase или null, ell по осям или null. Полные массивы C/votes
   в ответ не включать. Для сравнения только измерительных flags допускается
   `ell_x<0 AND ell_y<0` при двух уникальных фазах — опубликованное epsilon=1,
   **без production finding и без слова «подделка»**.
   Зафиксировать набор разных block-origin phases таких окон и наличие phase,
   отличной от `(0,0)`. Не суммировать их значимость и не превращать число окон
   в число независимых свидетельств.

Показатель ell использует plug-in p и модель голосов, не реальную вероятность
ошибки на фотографиях. Nt учитывает перебор фаз, включая выбор максимума;
для union bound независимость разных окон не требуется. Однако этот множитель
не обосновывает отдельный binomial tail при зависимых голосах текстуры и
оценке p по тому же окну. Перекрывающиеся окна не дают независимых наблюдений.
Обоснование исходной статьи не является доказательством family-wise FPR для
этой адаптации. Пограничные ell около 0 требуют cross-platform numerical
проверки; production rule на них сейчас отсутствует.

### Пороги, семантика и ограничения

| Условие/параметр | Класс и основание | Ограничение |
|---|---|---|
| 8 px, область определённости C, конечные числа | D; структура измерения | Не forensic suspicion |
| Минимальное окно 64×64 | A: рекомендация GRID20 §2.5; роль D | Восемь периодов на сторону не гарантируют достоверности |
| До 16 окон 512×512, <=2^22 pixels | D; существующие потолки и собственный sampling profile | Не гарантируют обнаружение малых областей |
| Строгий local maximum, отсутствие ties | Определение измерения; D для однозначности | Не отсекать слабые амплитуды произвольным порогом |
| ell<0 / NFA<1 | A: GRID20; B только в согласованной null-модели | Здесь лишь исследовательский flag, не production error guarantee |
| Число несовместимых фаз/окон, spatial persistence, практическая NFA граница | C; **не заданы** | Positive finding не определён |
| Минимальная статистическая опора и near-boundary численная устойчивость | C для support; численная проверка отдельно | Не подменять их числом 64 или epsilon=1 |

Предлагаемый будущий positive finding: «локальные периодические границы
согласуются с неоднородной историей JPEG-сетки». Одна обычная решётка, даже
сильная, не является finding; единый shifted grid может отражать benign crop.
Разные локальные фазы могут быть полезны сверх глобальной DQ-гистограммы, но
не доказывают монтаж: периодические текстуры и upsampling дают альтернативные
объяснения. Слабая/отсутствующая решётка и отсутствие phase conflict не
доказывают подлинность, single save или единое происхождение.

Локализация — только окно статистической опоры, не маска редактирования и не
точная граница splice. Для окна голосующих центров с origin `(x0,y0)` полный
bounding support исходных пикселей равен
`[x0-1,x0+w+2) × [y0-1,y0+h+2)`. Для будущего bbox применять существующее
`ImageCoordinates.normalized_bbox` к этим native pixel edges; не выдавать
coverage вне источника. Из-за окон/halo разные support могут перекрываться. Correlation
остаётся общей с DQ даже для локального конфликта; отделение не доказано.

### Ресурсы, валидация и gates

PNG raster до `2^22` pixels; native RGB buffer до 12 MiB, временная перестановка
EXIF может потребовать ещё такой buffer. Численная обработка последовательно
по окнам; float64 luminance/C, masks и histogram counts должны укладываться
в 32 MiB workspace. Верхняя оценка посещений центров `16*512*512=2^22`,
binomial sums — до `2*16*(512*512/16+1)` членов. В отличие от перебора всех
rectangles, Nt вычисляется формулой без создания этих окон.
Ожидается bounded CPU без новой runtime dependency: NumPy/Pillow и stdlib;
SciPy, AGPL binary, RNG, model weights не требуются. Это не измеренные сроки
или RSS; decode/copies/serialization и remaining timeout требуют будущего
ресурсного теста. До 16 scalar window summaries; новых artifacts нет.

Validation matrix — [GRID-01–GRID-12 и общие проверки](research/2026-09-23-jpeg-dq-grid-method-selection.md#validation).
Особые challenge cases: сильное обычное blocking, кирпич/ткань/решётки,
текст/screenshots, nearest-neighbor upsampling, sharpening, chroma edges,
малые вставки вне/на границах выбранных окон, JPEG quality около максимума.
Provenance — [JPEG-GRID20](REFERENCES.md#jpeg-grid20),
[JPEG-M2R1-PROPOSAL](REFERENCES.md#jpeg-m2r1-proposal);
отклонённая для этой волны альтернатива — [JPEG-ZERO21](REFERENCES.md#jpeg-zero21).

Открытые gates: **GRID-G1** — принять bounded window/Nt/native-coordinate
адаптацию либо выбрать полный опубликованный профиль с доказанным budget;
**GRID-G2** — проверить null-model и practical FPR на benign corpus,
калибровать conflict/support rule; **GRID-G3** — подтвердить координаты,
численную устойчивость, ресурсы и чувствительность покрытия; **GRID-G4** —
принять точные finding semantics/severity и scope владельцем. Без GRID-G1–G4
спецификация production detector неполна; разработчик не должен додумывать её.
