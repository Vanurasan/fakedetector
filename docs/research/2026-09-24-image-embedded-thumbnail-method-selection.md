# M2-CR1 — отбор метода согласованности embedded thumbnail

Дата: 2026-09-24. Baseline: `f16d98f955231f002506545e2e95a5bf82016531`.
Ветка: `feat/stage12-macro2-image-analyzer-expansion-wave1`; исходное дерево чистое.
Исследовательское свидетельство, **не production-контракт и не owner acceptance**.
Допуск — [METHODS](../METHODS.md#gate-принятия-метода), происхождение/права —
[REFERENCES](../REFERENCES.md#thumbnail-m2cr1), статус — [ROADMAP](../ROADMAP.md).

## 1. Решение и граница вывода

Рекомендация: **RESEARCH_ONLY**. Выбранный **исследовательский**, а не production
профиль — `THUMB-NCC-GRAD-1`; полезный сигнал — **WEAK** для будущей forensic
ответственности. Standard EXIF IFD1 JPEG извлекается без vendor parser, а
похожие изображения устойчиво сопоставляются в простых условиях. Однако
неуспех сопоставления не отличает замену содержимого от обычного crop,
padding, неизвестного thumbnail processing или устаревшей миниатюры.

Наблюдать различие между двумя изображениями полезно, но само различие не
доказывает подделку, намерение, manipulated status или нарушение подлинности.
Обновлённая после монтажа миниатюра может полностью совпадать с основным кадром;
совпадение также не доказывает подлинность. Производственная калибровка сейчас
не рекомендуется: сначала нужно определить проверяемую geometry/abstention
ответственность и контракт optional preprocessing representation.

Production analyzer, capability, threshold, severity, risk contribution,
Finding type и correlation group **не добавлены и не приняты**. Каталог остаётся
пять анализаторов `@1.0.0`: metadata, copy-move, JPEG DQ, audio PCM quality,
video sampled frame quality. DQ не пересматривается; Grid остаётся
`DEFERRED_RESEARCH_ONLY`, noise и resampling — `RESEARCH_ONLY`.

## 2. Раздельный scope

| Область | Результат исследования / предлагаемый первый scope |
|---|---|
| A. Стандартный EXIF IFD1 JPEG внутри JPEG APP1 | Единственный выбранный scope: один Exif APP1, TIFF IFD0 → IFD1, Compression=6, непрерывный baseline JPEG. Поддержан внешним исследовательским прототипом; в production такой capability **нет** |
| B. Другие стандартные EXIF/TIFF thumbnails | Несжатые RGB/YCbCr strips имеют другую схему расположения и размеров. TIFF с несколькими IFD/SubIFD не считать эквивалентом JPEG APP1. Известны из стандарта, исключены из v1; unsupported, не подозрение |
| C. MakerNote / proprietary previews | Не обходятся, не декодируются и не используются как fallback. Привязка offset к vendor layout и разные semantics требуют самостоятельного источника/допуска; увеличение coverage не оправдывает этот scope |
| D. Не-EXIF previews | JFIF APP0/JFXX, MPF/другие container previews и внешние sidecar thumbnails не смешиваются с A. При встрече — вне профиля, без inference «миниатюры нет вообще». Контейнеры PNG/WebP/HEIF и RAW здесь не исследовались |

`absent` в отчёте означает отсутствие **поддерживаемого EXIF IFD1 JPEG**, а не
полный отрицательный поиск всех preview representations. В корпусе не было
отдельных DSLR/mirrorless camera-native JPEG: реальные native файлы — смартфоны
и планшеты. Это ограничение, не замена таких камер RAW embedded previews.

## 3. Что установлено по первичным источникам

Полные название/организация/версия/URL и конкретные использованные факты каждого
источника находятся в реестре `TH-EXIF31`, `TH-TIFF6`, `TH-KF10`, `TH-PIL123`,
`TH-CV-NCC`, `TH-JFIF`. CIPA 3.1 получен официально и прочитан локально;
это актуальная редакция 2026, а не предположение, что Exif 3.0 всё ещё последняя.

- IFD0 относится к primary image; его next-IFD указывает на IFD1 thumbnail.
  TIFF header задаёт `II`/`MM`, magic 42 и относительные offsets. IFD содержит
  2-byte count, entries по 12 bytes и 4-byte next offset. Count — число значений,
  не байтов; короткое значение хранится inline. Tags записываются по возрастанию.
- Compression=6 в IFD1 обозначает JPEG. `JPEGInterchangeFormat` (513/0x0201)
  и `JPEGInterchangeFormatLength` (514/0x0202) — LONG/count1: начало SOI
  относительно TIFF header и длина непрерывного SOI–EOI stream. Размеры JPEG
  берутся из SOF; IFD0/Exif PixelXDimension не являются размерами thumbnail.
- Table 21 разрешает собственный IFD1 Orientation; его tag type — SHORT/count1,
  значения 1–8, default 1. Отсутствие tag не является нормативным указанием
  наследовать IFD0. Для primary нормализация уже применяется отдельно.
- Thumbnail необязателен. EXIF не устанавливает универсальные pixel dimensions
  thumbnail; общий APP1 ограничивает bytes. Несжатые TIFF thumbnails и JPEG
  используют разные representations. Частота отсутствия не следует из стандарта.

Это пересказ структуры, не полный валидатор EXIF. Политики при duplicate tags,
alias/overlap, invalid lengths, неизвестной геометрии и превышении лимитов ниже —
**собственные консервативные предложения**, а не forensic правила CIPA.

`TH-KF10` моделирует формирование thumbnail через crop/padding, фильтрацию,
масштабирование, контраст/яркость и JPEG. Цель статьи — различать processing
signatures камер/редакторов. Здесь не воспроизведены её optimizer, signature
classifier или заявленные авторские характеристики. Из неё используется
обоснование benign generation differences, а не готовый detector «fake».
Никакой код статьи не изучался и не копировался.

## 4. Capability audit текущего baseline

Graphify query использовал словарь `[image, metadata, preprocessing, artifact,
resource]`; граф имеет provenance `625b9e83…`, поэтому **STALE**. Результат
усечён, применяется только для навигации, без rebuild. Доказательства ниже —
текущие исходники, тесты и CONTRACTS §7.3–7.5, PROJECT §6.8, §15, §20.1.

| Возможность | Фактическое состояние / необходимая граница |
|---|---|
| Original bytes | `AcceptedSource` / `PreparedSourceRef.open_for_read()` дают controlled stream. Trusted local-path callback не является свободным путём в AnalyzerRequest |
| JPEG markers | `preprocessing/_media_tools.py::_JpegParser` проверяет размер/структуру marker segments, SOF/DQT/DHT/scans; APP1 пропускается как payload, TIFF/IFD1 не интерпретируется |
| Source identity | `_service.py::_original_image_facts` сверяет SHA-256 с validated source, даёт mode, frame, native dimensions, orientation и JPEG facts. Ни thumbnail extent, ни decoded preview в `OriginalImageFacts` нет |
| Normalized raster | `_decode_normalized_image`: первый image frame, `ImageOps.exif_transpose`, RGB/RGBA PNG без resize и исходного EXIF/XMP/ICC. `convert('RGB')` не является полноценным ICC color-managed rendering |
| Safe metadata | `_image_source_metadata` даёт bounded technical facts, не EXIF blob. Восстановить IFD1 bytes из normalized PNG нельзя |
| Pillow API | В установленном 12.3.0 `Exif.get_ifd(IFD1)` возвращает dictionary, `ImageFile.get_child_images()` ищет также SubIFDs, делает seek/read(length)/Image.open/load. API существует, но сам не проверяет project provenance, 512-side ceiling, overlap, общий artifact budget или remaining deadline |
| Nested decode | Специального bounded nested-thumbnail producer/descriptor/reader нет. Прямой вызов Pillow helper из analyzer не закрывает эту потребность |
| Image geometry | `ImageCoordinates` хранит native/oriented размеры и EXIF 1–8; `normalized_bbox` переводит углы в существующую координатную модель. Сопоставление thumbnail↔primary crop/affine отсутствует |
| Numeric kernels | NumPy/OpenCV/Pillow уже доступны; luminance и finite differences есть в private preprocessing kernels. Пилот независим от production и не создаёт параллельное production API |
| Demand | `ForensicCapability` закрыт: image original/coordinates/JPEG/residual; thumbnail отсутствует. `_catalog.py` запрашивает JPEG_COEFFICIENTS только для DQ; остальные четыре не запрашивают forensic capabilities |
| Artifacts | Общие 256 artifacts, byte budget по media limit, регистрация до записи, cleanup ownership; 16 forensic representations, 16 KiB manifest, 32 KiB metadata envelope, 64 MiB/numeric artifact |
| Resource/process protections | JPEG input 32 MiB, 256 markers/scans, 1 MiB payload; raster≤2^22 pixels. Bounded subprocess runner, remaining deadline, terminate/reap и cleanup barrier доступны; OS hard RSS quota нет. Новый nested Pillow decode автоматически изолированным не становится |

Изучены `tests/test_preprocessing.py`, `tests/test_stage6_real_analyzers.py`
и контракты forensic transport/ресурсов. Отдельные tests metadata уже проверяют
coded dimensions при Orientation 1/6/8 и отсутствие вывода при invalid orientation.
Тестов гарантированного EXIF-thumbnail extraction в текущем production нет.

### Разделение с metadata analyzer

`analyzers/_image_metadata.py::analyze` открывает controlled source через Pillow,
декодирует native raster и сравнивает positive EXIF dimensions с decoded dimensions
при допустимой orientation. `_exif_value` проверяет primary EXIF/dimension tags
с fallback на ImageWidth/ImageLength; IFD1 не читает. Единственный candidate —
`image_metadata_dimension_mismatch`. Presence EXIF/XMP/ICC/Software даёт факты,
а не самостоятельные findings. **Проверка повреждённой структуры thumbnail также не реализована**.

Структурные отношения tags, dimensions, duplicates и offsets логически относятся
к metadata responsibility. Если владелец когда-либо разрешит их расширение,
проверенные факты должен поставлять общий parser; не следует создавать отдельный
анализатор только ради malformed thumbnail tags. Никакой такой перенос/расширение
в M2-CR1 не сделан. Сравнение **decoded content двух изображений** — отдельная
ответственность, которую нынешний metadata analyzer не выполняет.

## 5. Предлагаемое безопасное извлечение — ещё не реализация

Следующие числа — верхние resource/support bounds исследовательского предложения,
**не production threshold** и не новые config fields. Это ужесточение существующего
envelope, а не разрешение обойти его. Полный parser acceptance потребует отдельной
реализации, adversarial tests и owner gate.

| Объект | Предлагаемая проверка до чтения/выделения памяти |
|---|---|
| Source / JPEG scan | ≤32 MiB и действующий per-media limit; ≤256 markers/scans, суммарный marker payload≤1 MiB. SOI и lengths проверены; Exif APP1 только до первого SOS. Повторный Exif APP1/неоднозначное размещение — abstention, не first/last wins |
| APP1 | 16-bit length включает два байта length: payload≤65533; после `Exif\0\0` TIFF extent≤65527 bytes. Все offsets принадлежат именно этому сегменту, не всему файлу |
| TIFF traversal | Только фиксированные пути IFD0/IFD1 и их standard Exif/GPS/Interop IFD для extent validation: ≤8 IFD, ≤3 уровня, ≤128 entries/IFD, ≤1024 всего. Никакой рекурсии через arbitrary SubIFDs/MakerNotes; все visited offsets учитываются |
| Entry arithmetic | Type/count allowlist, checked count×width и table size до allocation. Offset≤extent−length; native narrowing только после проверки, без wraparound. II/MM и magic42 обязательны; BigTIFF не принимается |
| Duplicates/conflicts | Повтор tag даже с равным значением, repeated/cyclic IFD, неоднозначный offset/length, конфликт со SOF — structural/unsupported diagnostic. Unsorted tags не сортировать молча в «валидный» профиль |
| Overlap | Интервалы header, IFD tables, out-of-line values и thumbnail сравниваются. Перекрытие thumbnail с любой metadata extent или пересечение структур — безопасный отказ; opaque MakerNote value проверяется как span, содержимое не разбирается. Неизвестный field type не позволяет безопасно вычислить span — unsupported |
| Thumbnail bytes | Одна пара LONG/count1, 1≤length≤65527 и фактический остаток APP1; непрерывный JPEG SOI–EOI. Нельзя seek вне segment, искать «похожий SOI» вместо неверного pointer или склеивать fragments |
| Nested JPEG | Только baseline 8-bit, grayscale/3-component; SOF до allocation: стороны 1…512, pixels≤262144. Не использовать IFD dimensions вместо SOF. APPn/COM/restart внутри стандартного thumbnail исключены; nested EXIF не обходится |
| Truncation/corruption | Полный bounded marker/entropy preflight и decode; отсутствующий/ранний EOI, trailing data, warnings и неполный decode не превращаются в content mismatch. `LOAD_TRUNCATED_IMAGES` не включается |
| Decode resources | RGB payload≤786432 bytes; не более одной декодированной миниатюры, immutable artifact; temporary image comparison buffers планировать≤32 MiB. Строгая size preflight не заменяет контроль native decoder RSS |
| Execution/artifacts | До decode reserve artifact, проверить оставшийся общий count/bytes и manifest budget. Trusted child через существующий runner, timeout≤min(5s, remaining), bounded stdout/stderr, terminate/reap и cleanup barrier. Эти 5s — предлагаемый потолок, не измеренный production SLA |

JPEG APP1 byte ceiling не ограничивает decoded pixels: маленький compressed
payload может объявить огромные dimensions. Limit должен проверяться **до**
`load()`. Metadata нельзя передавать downstream как arbitrary JSON/blob.
Миниатюра должна сохранять связь с source SHA-256, parser/profile version,
IFD origin, byte range/hash и native/display geometry, через внутренние immutable
facts и opaque artifact ref. Записывать весь raw EXIF для этого не нужно.

Потребуется отдельное расширение demand/закрытых representation types, producer,
transport validation и controlled reader. Рабочее описание — «embedded IFD1 JPEG
representation», **не утверждённое имя enum/API**. Producer живёт в общей trusted
preprocessing infrastructure; analyzer получает prepared raster и факты, не
MakerNote parser, arbitrary paths или самостоятельный extraction subprocess.

### Что реально проверяет внешний прототип

`scripts/pilot.py` снаружи репозитория реализует только два IFD, проверки их
entries/value spans, duplicate tags/APP1, cycle/tail, offsets/lengths и nested
dimensions. Exif/GPS/Interop pointers не обходятся; неизвестный type129 EXIF3
не поддержан, sorted-tag validation и полный nested marker/entropy preflight
не реализованы. Nested `Image.open/load` выполняется в процессе research runner,
без production subprocess/lifecycle integration. Он **не является готовым
безопасным production parser**, даже при зелёных 48 boundary tests.

Эти различия перечислены явно, чтобы feasibility результата не выдавалась за
certification. Чтение и декодирование выполнено только на provenance-checked
corpus и собственных fixtures. Новая capability в текущем проекте отсутствует.

## 6. Отсутствие, повреждение и ошибки

| Случай | Требуемая forensic граница / предлагаемый будущий путь |
|---|---|
| Нет поддерживаемого thumbnail | `NOT_APPLICABLE`, без Finding/подозрения; обычное отсутствие metadata |
| Thumbnail валиден и согласован | Никакого Finding; completed измерение, не authenticity claim |
| Некорректная структура tags/offsets | Отказ от content comparison; safe structural fact. Возможное расширение metadata analyzer — отдельное решение, не новый content analyzer и не автоматический Finding |
| Bytes есть, вложенный JPEG не декодируется | Decode/preprocessing diagnostic; нельзя считать ни отсутствием thumbnail, ни content mismatch, ни успешным отрицательным результатом |
| Геометрия вне профиля, недостаточно texture/support | Abstention с причиной и без Finding. Unsupported/неприменимость отличается от operational error; «не нашлось соответствия» не равно «контент чужой» |
| Валидный materially different content | Только потенциальное свидетельство различия representations, после принятой geometry/decision policy; stale benign edit остаётся объяснением |
| Ресурсный отказ, timeout, source/artifact failure | Сохранить ошибки и cleanup guarantees; не маскировать в completed/no Finding или в подозрение |

Важный architectural gap: сейчас `lifecycle/_analysis_execution.py` преобразует
`PreprocessingError` в **failed task**, а не изолированный analyzer error;
для `resource_limit` сохраняет соответствующую безопасную причину.
Доступного универсального «optional capability failed, остальные продолжили»
контракта здесь нет. Поэтому нельзя обещать, что будущий malformed thumbnail
автоматически даст только `AnalyzerStatus.ERROR` без влияния на task.

Предложение для отдельного owner gate: bounded typed availability result
отличает normal absence/unsupported от present-but-failed, а optional consumer
применяет существующие analyzer statuses (`not_applicable`, `error`, `timeout`)
без изменения scoring/completeness алгоритмов. Нужны явное согласование с
CONTRACTS и integration tests; внутреннее отсутствие artifact не должно
превратиться в скрытое successful no-signal. Infrastructure/identity failures
сохраняют fail-closed поведение. M2-CR1 эти semantics **не меняет**.

## 7. Сравнение classical вариантов

Это инженерная оценка применимости, а не заявление, что все варианты
экспериментально реализованы в данном пилоте.

| Вариант | Польза | Решение / ограничения |
|---|---|---|
| Orientation-normalized aspect | Дешёвый geometry gate | Используется; aspect не является content score. Native SOF и IFD0/IFD1 orientation учитывать раздельно |
| Raw RGB equality / MAE | Легко объяснить | Не выбран: filter/quality/color pipeline меняют pixels без изменения сцены |
| Scale-normalized luminance + NCC | Устойчив к положительному affine brightness/contrast, downscale подавляет compression detail | Основная exploratory метрика. Не устойчив к неизвестному crop, clipping, local tone mapping; теряет chroma-only различия |
| Low-frequency structure | Снижает чувствительность к resize/sharpen | Реализована blur+64² representation перед NCC; не независимый второй голос, small local changes могут исчезнуть |
| Edge-map similarity | Меньше зависимости от абсолютной яркости | NCC gradient magnitudes сохранён как diagnostic; blur/sharpen/texture меняют границы |
| Gradient orientation | Полезна при изменении контраста | Weighted unsigned cos(2Δ) diagnostic. Параллельные полосы и градиенты дают высокое agreement без одной сцены |
| Perceptual hash | Дешёвый retrieval diagnostic | Не выбран: collisions/малый support, geometry и отсутствие spatial explanation; не заменяет alignment или calibrated forensic rule |
| Feature correspondence | Может подтвердить crop соответствие и область покрытия | ORB/internal copy-move primitives потенциально доступны, но 160×120 часто мало keypoints. Выбор совпадений/отсутствие совпадений не доказывает несовместимость |
| Bounded affine/homography | Компенсирует более общую геометрию | В пилоте не реализовано. До допуска задать max keypoints/matches/iterations, seed+tie rules, nondegenerate inliers, coverage и запрет extreme warp. Homography может переобучиться на repetitive texture |
| Crop-tolerant search | Проверяет ограниченные benign crops | Фиксированная сетка, без threshold sweep; offset crops вне сетки демонстрируют остаточную чувствительность |
| Letterbox/padding detection | Может вернуть правильный content rectangle | Автоматически не удаляется: чёрное небо/рамка сцены не всегда padding. Нужен отдельный validated detector; пока aspect mismatch → abstention |
| Thumbnail-to-primary localization | Полезна для доказанного crop correspondence | Возможная геометрическая область покрытия, не область подделки. Пилот сохраняет выбранную гипотезу, не публикует forensic bbox |

### Orientation и геометрия

Primary нормализуется один раз по IFD0; не следует повторно применять эту
ориентацию к уже нормализованному PNG. Thumbnail pixels могут остаться в
native положении или уже быть повёрнуты. IFD1 Orientation сохраняется отдельно;
реальное поведение при его отсутствии нельзя угадать по стандартному default.
Пилот проверяет все восемь dihedral hypotheses и фиксирует выбранную, не объявляя
наследование IFD0 установленным правилом.

Center crop, fit, digital zoom, editorial crop и border добавляют разные
геометрические отношения. EXIF DigitalZoomRatio сам по себе не восстанавливает
crop rectangle. Относительно разные aspect без принятой crop/padding модели
не допускают mismatch inference. Совпадение после перебора orientations/crops
имеет selection bias; дальнейшая калибровка обязана учитывать весь поиск, а не
распределение одной заранее известной геометрии.

## 8. Точный exploratory профиль THUMB-NCC-GRAD-1

Предрегистрация: external `provenance/predeclaration.md`, записана до extraction
coverage и outcomes. Числа далее — параметры измерения/support, **не подозрение**.
Ни score cutoff, ни majority vote, ни severity/вероятность не определены.

1. Вход: primary JPEG и извлечённый IFD1 JPEG. Primary EXIF transpose → RGB8;
   nested RGB8 из Pillow без самостоятельного nested EXIF. Для real native
   comparison исследовательский primary уменьшается до long side≤768 Lanczos.
   Это offline representation, не изменение production normalized PNG.
2. Условный будущий production путь ограничен текущими `2^22` primary pixels.
   Пилот допускал provenance-checked originals≤24 MP до offline resize: **не
   доказательство обхода существующего ceiling**. Только 2 из 20 native inputs
   удовлетворяют этому ceiling; из 30 файлов — 12 вместе с social exports.
3. Для thumbnail orientations 1…8 в этом порядке создаются geometry hypotheses:
   full/full; затем crop primary с fraction 0.9, 0.8 одновременно по ширине/высоте,
   anchors x/y ∈ {0,0.5,1}, y-major/x-minor; затем аналогичные crops thumbnail.
   Width/height и offsets округляются вниз через int. Crop только одной стороны
   за раз: `8 × (1+18+18) = 296` hypotheses максимум, без recursive search.
4. Пропустить hypothesis, если `abs((Wa/Ha)/(Wb/Hb)−1)>0.03`. После этого обе
   области преобразуются в Y'=0.299R+0.587G+0.114B на шкале 0…1, INTER_AREA
   resize 64×64, GaussianBlur 5×5/sigma1/BORDER_REFLECT_101. Одинаковая сетка
   используется для сравнения; небольшой aspect residual внутри 3% допуска
   остаётся ограничением. Tiny thumbnails могут upscale: их отдельный minimum
   information support ещё не валидирован, production пригодность не заявляется.
5. NCC = `sum((A−mean A)(B−mean B))/sqrt(sum((A−mean A)^2)sum((B−mean B)^2))`.
   Перед ним std каждой plane≥3/255. `np.gradient` даёт centered interior и
   одностороннюю разность на границе; magnitude M и direction θ. Joint support:
   `MA≥0.01 & MB≥0.01`, доля≥0.10. Иначе hypothesis не измеряется.
6. Diagnostics: NCC всех magnitudes; на joint support
   `sum(min(MA,MB) cos(2(θA−θB)))/sum(min(MA,MB))`. Это unsigned orientation,
   не корреляция направления signed edge. Вырожденный denominator≤1e−12
   возвращает отсутствующую correlation, не числовое подтверждение совпадения.
7. Выбрать max luminance NCC среди supported hypotheses; точное равенство
   разрешает первый в указанном порядке. Gradient/edge score берутся **для той
   же** geometry, не как три независимых максимума. Агрегация image-level —
   только выбранный measurement tuple. При отсутствии supported hypothesis —
   abstention; при низком NCC без доказанной geometry — indeterminate.
8. Сохранить source/fixture/thumbnail hashes, extraction state, dimensions,
   orientations, selected geometry, число geometry/supported hypotheses,
   direct orientation1/full NCC, best NCC/edge/gradient, support, elapsed time.
   Это external raw measurements, не новый public raw_metrics contract.

Порядок детерминирован, RNG synthetic=20260924, OpenCV threads=1. Не выполняются
обучение, weights, threshold sweep или адаптация сетки после outcomes.
Не задаётся обработка «по максимальному mismatch»: оптимизация ищет объясняющее
совпадение, а не наиболее отличающийся crop. Color transform, local edits,
strong crops и unsupported geometry сохраняют альтернативные объяснения.

## 9. Пилот: происхождение, контролируемые случаи и результаты

### Выбор и права

30 JPEG отобраны до outcomes из reviewed VISION manifest M2-R3B: для каждого
из десяти device IDs первые два native source_id лексикографически и natFBH
версия первого. 20 native файлов + 10 социальных экспортов — **20 scene groups,
не 30 независимых сцен**. Источники извлечены по SHA-256 из существующего
`Stage12-Macro2-DQ/corpus/originals.zip`, без новых загрузок медиа. Условия и
attribution сохранены по `DATASET-VISION`; DQ/BR1 алгоритмы не запускались.

Четыре собственных synthetic families: constant, linear gradient, repetitive
stripes, textured colored shapes. На каждом из 24 working rasters построено
15 cases: consistent, global resize, JPEG recompression primary, recompression
thumbnail, thumbnail resize, sharpen, color/contrast, physical rotation, EXIF
rotation, center crop80%, off-grid crop80%, center crop50%, stale pre-edit
thumbnail (crop80%+contrast), letterbox и cyclic transplant. Всего **360**.
Все controlled thumbnail bytes реально помещены в synthetic IFD1, извлечены и
декодированы перед сравнением. Это не независимые samples для FPR.

Thumbnail base long side160/quality85, variant side96/quality30;
primary fixture quality90, recompression control quality40; exact transforms
и порядок — predeclaration/script. JFIF APP0, автоматически создаваемый Pillow,
удаляется при генерации, чтобы fixtures не назывались стандартным Exif thumbnail
при наличии запрещённого APPn. Первичный технический прогон с APP0 сохранён
отдельно как `initial-fixture-run.json`, не используется для fingerprint или
acceptance. Финальные прогоны выполняются на неизменном script, без ретюнинга
метрик; корректировка контейнера не изменила измеренные pixels/scores.

### Extraction и native camera processing

| Наблюдение | Результат и знаменатель |
|---|---|
| IFD1 JPEG найден и extent извлечён | 20/30; все 20 native. Во всех 10 natFBH отсутствует EXIF |
| Прошёл строгую extent/decode проверку прототипа | 19/20 extracted; 19/30 общей выборки |
| Исключение | `D11_I_nat_0036`: объявлено 11686 bytes, EOI на offset11683, после него `00`. Strict `jpeg_extent` отказ **до decode**; отдельная диагностика Pillow успешно декодирует 160×120. Это не «1 недекодируемая миниатюра» и не Finding |
| Native geometry/support | 19/19 допущенных comparisons имеют support, выбрана full geometry; 17 orientation1, 2 orientation3 |
| Native likeness NCC | min 0.997797, median 0.999626, max 0.999989 |
| Orientation в реальных файлах | IFD0=1 у 16 native, =3 у 2, отсутствует у 2; IFD1=1 у 14, отсутствует у 6. Два iPhone6Plus с IFD0=3/IFD1 absent требуют hypothesis3. Это наблюдение поведения, не универсальное наследование |
| Pixel sizes thumbnails | 160×120, 320×240, 256×144, 512×288, 512×384; нельзя жёстко приравнять EXIF thumbnail к 160×120 |

В исходном JSON общий label `decode_failure` включает preflight failure;
`reason=jpeg_extent` и `results/diagnostics.json` уточняют классификацию. Это
важно для корректного счёта decodability. Compatibility padding policy после
результата не ослаблена. Строгость может снижать benign coverage; её следует
согласовать отдельно, не использовать отказ как подозрение.

Отсутствие наблюдается у 10/30 здесь, но условно — 0/20 native и 10/10 natFBH.
Это **не оценка распространённости** в интернете, современных смартфонах или
пользовательском потоке. Не отбирали corpus по наличию thumbnail, однако сам
набор старых устройств и заданных workflow уже сильно ограничивает переносимость.

### Controlled comparisons на 20 реальных сценах

В таблице только measurements с support; max NCC высокий означает похожесть.
Никакой границы «сработало / false positive» не выбиралось.

| Case | Supported / 20 | NCC min / median / max |
|---|---:|---|
| Consistent | 20 | 0.999848 / 0.999955 / 0.999991 |
| Global resize | 20 | 0.999853 / 0.999960 / 0.999991 |
| Primary JPEG recompression | 20 | 0.999836 / 0.999950 / 0.999987 |
| Thumbnail recompression | 20 | 0.998717 / 0.999752 / 0.999908 |
| Thumbnail resize | 20 | 0.999520 / 0.999849 / 0.999975 |
| Sharpen | 20 | 0.996578 / 0.999679 / 0.999969 |
| Color/contrast | 20 | 0.995239 / 0.999382 / 0.999933 |
| Physical rotation90 | 20 | 0.999848 / 0.999955 / 0.999991 |
| IFD0 orientation6 | 20 | 0.999848 / 0.999955 / 0.999991 |
| Center crop80% | 20 | 0.999576 / 0.999872 / 0.999982 |
| Offset crop80%, anchor(.23,.67) | 20 | 0.773024 / 0.882615 / 0.979122 |
| Center crop50% | 20 | 0.253444 / 0.641134 / 0.952171 |
| Stale benign crop80%+contrast | 20 | 0.995018 / 0.999357 / 0.999929 |
| Letterbox 10% top/bottom | 0 | Все abstain по aspect, не mismatch |
| Cyclic transplant | 17 | 0.252421 / 0.477716 / 0.871480 |

Transplant строился по списку 20 real +4 synthetic: первые 19 real targets
ссылаются на следующий другой real файл, последний real — на constant synthetic.
Два real-real comparisons не прошли aspect, последний real-synthetic не имеет
support. Поэтому 17 supported — реальные different-file pairs; это не 20
доказанно unrelated реальных сцен. Same-device снимки могут быть визуально
сходны, identity файлов не гарантирует независимости содержимого.

На этой небольшой выборке same-image resize/compression/orientation далеко от
different-file measurements. Но **диапазоны crop и transplant перекрываются**;
их нельзя разделить обещанием robust threshold. Offset crop, отсутствующий в
сетке, существенно ухудшает score даже при 80% retained width/height.
Gradient/edge diagnostics не получили post-hoc combined decision rule.

Synthetic checks выявляют отдельную неоднозначность: linear gradient vs stripes
даёт gradient orientation≈1 при luminance NCC≈0.146. Направление границ само
по себе не подтверждает общую сцену. Constant case abstains; periodic content,
smooth backgrounds и локальные детали ниже thumbnail resolution остаются
challenge families. Не измерены scene-semantic FPR, compositing sensitivity,
доказанная localization accuracy, HDR/local tone maps, camera digital zoom,
цветовые профили и все варианты vendor sharpening. Результаты не подменяют их.

## 10. Ресурсы и воспроизведение

Внешний исследовательский каталог:
`C:\Users\Vanur\Desktop\FakeDetector-Work\research\M2-CR1-thumbnail\`.
Каталог review — `...\reviews\M2-CR1-thumbnail\`, временные файлы —
`...\tmp\M2-CR1-thumbnail\`. Новых loose Desktop paths нет.

| Артефакт | Назначение |
|---|---|
| `provenance/predeclaration.md` | Выбор source/metrics/controls до outcomes |
| `provenance/sources.json`, `vision-readme.txt` | Per-file source URL, hash, device/group, исходные attribution/terms и local path |
| `provenance/cipa-exif-2026.pdf` и `.txt` | Официальный стандарт и извлечённый текст, вне Git |
| `scripts/pilot.py`, `scripts/test_pilot.py`, `scripts/summarize.py` | Собственные скрипты воспроизведения, граничные тесты, проверка repeat/сохранённых hashes; вне production |
| `results/pilot.json`, `repeat.json`, `diagnostics.json` | Все исходные measurement tuples, repeat comparison и уточнение extent exception |
| `corpus/`, `fixtures/` | 30 исходных JPEG и 360 производных, только внешние файлы |

Среда: Windows, Python3.12.10, NumPy2.5.2, OpenCV4.14.0
(`opencv-python-headless==4.14.0.94`), Pillow12.3.0. Скрипты не импортируют
production FakeDetector. Команды из repository root:

```powershell
$r = 'C:\Users\Vanur\Desktop\FakeDetector-Work\research\M2-CR1-thumbnail'
.venv\Scripts\python.exe -B "$r\scripts\pilot.py" pilot
.venv\Scripts\python.exe -B "$r\scripts\pilot.py" repeat
.venv\Scripts\python.exe -B "$r\scripts\summarize.py"
uv run pytest --no-cov -q -p no:cacheprovider "$r\scripts\test_pilot.py"
uv run ruff check "$r\scripts"
uv run ruff format --check "$r\scripts"
```

Для полного regenerate нужны сохранённые `Stage12-Macro2-DQ` manifest/ZIP;
local `sources.json` сохраняет также upstream URLs/hash при недоступности архива.
Скрипт восстанавливает files по проверенному hash, не доверяет старым абсолютным
путям поля `original.path` в историческом manifest. Network при анализе не нужен.
Созданные VISION derivatives остаются CC BY-SA 4.0 с указанными изменениями.

Script SHA-256:
`1fb16439d558d0939867316e7cb1c53884dc515eb14888dc89ae5e9003dd29a2`.
Predeclaration SHA-256:
`52815ec4ad45b264312632060029edbf37d936dbcd7bf85d75bf69ce2218903c`.
Ссылки/полные hashes остальных артефактов — diagnostics и review manifest.

Repeat360 проверяет measurement tuples, fixture/thumbnail hashes и все 30 native
наблюдений, исключая elapsed time; timing/RSS не должны быть побитово равны.
Время отдельных controlled comparisons: median 0.133/0.142s, max 0.220/0.217s
в двух финальных прогонах; полный проход 56.58/57.69s. Windows PeakWorkingSetSize
276 877 312 / 275 623 936 bytes (около 264 MiB) у whole research process,
включая декодированные реальные inputs и удерживаемые рабочие растры. Это **не** bound одного future worker и не совместный peak
четырёх production executions. Точное время и пик памяти каждого запуска записаны в JSON.

30 originals занимают 56 139 567 bytes; 360 final fixtures — 31 312 301 bytes.
Два final measurement JSON — около 0.46 MiB; raw media не входят в Git/review diff.
Для будущего результата планируется один RGB thumbnail≤0.75 MiB плюс bounded facts,
без опубликованной difference-map. PIL/native allocation overhead и concurrent
envelope ещё требуют измерения. Действующие лимиты нельзя подменить измеренным RSS.

48 focused tests покрывают II/MM, точный byte extent, Orientation1…8 primary и
independent thumbnail, duplicate tag/APP1, неверный TIFF magic,
entry/count/offset/length limits, cycle/overlap, truncation, corrupt/oversized/
progressive nested JPEG, absence, unsupported compression, aspect/support
abstention и повторяемость. Они не доказывают safety отсутствующих функций
production parser. Ruff и format проверяются для внешних research scripts;
для docs-only repository scope используются разрешённые узкие проверки,
`git diff --check`, review фактического diff/нового отчёта и итоговый status.
Полный `uv run poe check` и strict certification не выполняются.

## 11. Корреляция и локализация

Предварительное evidence family: **согласованность изображений внутри одного
файла**. Это название для обсуждения, не принятая `correlation_group` или новая
schema. Идентификатор группы не предлагается до принятия метода и семантики.

- Metadata: обе проверки реагируют на export, stale fields или metadata
  transplant; content mismatch может сопровождать dimension mismatch. Они
  различаются измеряемыми фактами, но не гарантированно независимы.
- Copy-move: ищет соответствующие области внутри primary raster. Thumbnail
  comparison сравнивает два representations; локальный clone может сохраниться
  в thumbnail или исчезнуть при downsample. Отдельный независимый risk vote
  из этого не следует.
- JPEG DQ: оба сигнала могут возникнуть при benign resave. DQ измеряет историю
  quantization, thumbnail — relation content; один не подтверждает другой и
  не доказывает malicious edit. Повторное кодирование может удалить thumbnail.

Первый возможный content signal следует локализовать на файл целиком, пока нет
подтверждённого spatial residual method. Crop correspondence показывает область
покрытия основного изображения, не место монтажа. Для будущего spatial output
нужно mapping через `ImageCoordinates` с oriented bbox и явной thumbnail
resolution uncertainty. Здесь bbox, heatmap, severity и Finding не создаются.

## 12. Ответы T1–T9 и оставшиеся gates

| Вопрос | Ответ |
|---|---|
| T1. Feasible и safe extraction в архитектуре? | **Условно да** для standard IFD1 JPEG: segment/IFD traversal конечны, trusted producer/runner можно использовать. Готовая безопасная capability отсутствует; прототип не certification |
| T2. Уже достаточно preprocessing? | **Нет**: исходные bytes доступны контролируемо, но prepared thumbnail bytes/raster/provenance/state отсутствуют |
| T3. Нужна новая capability? | **Да**, внутренняя demand/representation/producer/reader плюс owner-approved failure semantics; реализация запрещена текущим scope |
| T4. Отличается от metadata analyzer? | **Да для content**, structural validation остаётся metadata responsibility. Существующий analyzer не сравнивает IFD1 pixels |
| T5. Robust same vs unrelated? | **Частично**: resize/compression/orientation separation в пилоте есть; different-file sample мал и ограничен, crop cases перекрываются. Универсальная robust separation не подтверждена |
| T6. Вред benign crop/edit/stale? | **Существенный**: off-grid/moderate и heavy crop снижают NCC, stale edit остаётся законным объяснением реального mismatch. Post-edit обновление thumbnail убирает сигнал |
| T7. Safe abstention при geometry failure? | **Да как консервативная политика**, без mismatch вывода; aspect/low-support refusal продемонстрирован. Но support не доказывает правильность geometry, поэтому низкий supported score тоже indeterminate; useful production coverage не установлена |
| T8. Вписываются ли bounds? | **Инженерно возможно, ещё не подтверждено integration измерениями**. Thumbnail мал, поиск конечен; 18/20 native originals вне текущего raster ceiling. Resource/error gates обязательны, лимиты не повышены |
| T9. Оправдана дальнейшая калибровка? | **Не production calibration сейчас**. Есть основание только для targeted research geometry/coverage и безопасной обработки optional preview после отдельного решения владельца |

До изменения рекомендации нужны: rights-cleared camera/modern-phone corpus с
benign histories; held-out off-grid/aspect crop, letterbox, digital zoom,
same-scene/repetitive/low-texture и chroma/local-edit controls; подтверждение
geometry или проверяемая abstention с coverage; точная политика strict extent
vs benign padding; immutable availability/provenance contract; isolated nested
decoder и resource/failure integration tests. После этого владелец решает,
существует ли достаточная отдельная content responsibility, имеет ли смысл
calibration или лучше закрыть кандидата/рассмотреть только metadata checks.

Самостоятельно расширять geometry search, включать MakerNotes, выбирать
threshold или увеличивать production raster limit ради добавления анализатора
не следует. Owner review остаётся открыт; Macro 2 / Stage 12 не закрываются.
