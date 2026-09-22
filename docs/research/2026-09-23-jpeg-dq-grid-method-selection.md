# M2-R1 — выбор методов JPEG DQ и grid

Дата: 2026-09-23. Режим: исследование и документационное предложение.
**Не production-контракт, не owner acceptance и не реализация анализаторов.**

## Результат и baseline

| Кандидат | Результат отбора | Предложение | Что мешает production |
|---|---|---|---|
| `image_jpeg_double_quantization` | **RESEARCH_ONLY_NOT_READY** | Гистограммный DQ-HIST-1 как точно заданное измерение; likelihood-модель BP12 как следующая альтернатива для калибровки | Нет проверенного null/decision rule, support minimum и переносимого порога |
| `image_jpeg_grid_consistency` | **RESEARCH_ONLY_NOT_READY** | Локальные фазы blocking artifacts GRID-PHASE-1 на основе GRID20 | Bounded адаптация не наследует автоматически NFA-гарантию; нет калиброванного правила phase conflict |

Оба предложения — **PROPOSED / PENDING OWNER ACCEPTANCE**, readiness
**NOT_READY**. Нельзя принять их как готовые finding-producing методы только
по наличию этой записи. Возможный отдельный следующий scope — измерительный
прототип без findings и corpus calibration; владелец ещё его не разрешал.
Таким образом, исследование закончено, но method gate M2-A остаётся открытым.

Проверенный baseline:

- ветка `feat/stage12-macro2-image-analyzer-expansion-wave1`;
- HEAD `895f30ef634ef628c7efee889f69e7afe481c877`;
- начальный `git status --short --untracked-files=all` пуст;
- никаких Git mutations, реализации, запуска анализаторов или корпусных
  экспериментов в M2-R1 не выполнялось.

Изучены `AGENTS.md`, `PROJECT.md`, актуальный Stage 12/Macro 2 в `ROADMAP.md`,
`CONTRACTS.md` §§7.5, 8.4, 9, 11.4, `METHODS.md`, provenance policy и
`research/README.md`. Сопоставлены `preprocessing/_models.py`, image producer
в `_service.py`, существующий normalized-PNG consumer `_image_copy_move.py`,
JPEG/native/EXIF tests в `test_preprocessing.py` и residual/numeric-reader
tests в `test_stage5_internal_models.py`. Тесты прочитаны, не запускались.

Graphify query использован только для поиска связанных типов. Его root
provenance содержит source SHA `625b9e83f133fb0ae31a4b90e9e1288bff96f69c`,
отличный от baseline: граф **STALE**, не архитектурное доказательство.
Пересборка не проводилась; выводы о доступных данных проверены по текущим
контрактам и исходникам.

## Источники и качество свидетельств

Авторы, venue/year, стабильные ссылки, точная использованная часть и
license/implementation relevance находятся в каноническом реестре:

| Reference ID | Прочитанное свидетельство | Использование в выборе |
|---|---|---|
| [JPEG-T81](../REFERENCES.md#jpeg-t81) | Стандарт JPEG, DCT/quantization/components и coding modes | Отличать факты текущего кодирования от предполагаемой истории |
| [JPEG-PF04](../REFERENCES.md#jpeg-pf04) | Авторский полный текст, §3 | Гистограммные/спектральные следы DQ и пределы идеальной модели |
| [JPEG-LF03](../REFERENCES.md#jpeg-lf03) | Авторский полный текст, §§2–4 | Отношения q1/q2, missing bins, rounding и неоднозначность первичной таблицы |
| [JPEG-PF08](../REFERENCES.md#jpeg-pf08) | Авторский текст, histogram/SVM pipeline | Сравнение с обучаемым классическим решением |
| [JPEG-BP12](../REFERENCES.md#jpeg-bp12) | Авторский текст, §§III–V, Algorithms 2/3 | Модели aligned/non-aligned double JPEG и likelihood localization |
| [JPEG-NIU19](../REFERENCES.md#jpeg-niu19) | Издательские abstract/introduction/preview, не закрытый полный текст | Same-table семейство как отдельный алгоритмический путь |
| [JPEG-GRID20](../REFERENCES.md#jpeg-grid20) | Полный текст, Algorithm 1, §§2–5 | Cross-difference, local phase voting, NFA, вычислительные/содержательные ограничения |
| [JPEG-ZERO21](../REFERENCES.md#jpeg-zero21) | Издательское описание и полный текст, §3 | Альтернатива через число DCT zeros на разных origins |

Поиск выполнен 2026-09-23; это целевое сравнение классических методов, а не
заявление об исчерпывающем обзоре литературы или мировом state of the art.
Даты crawled/published у поисковой выдачи не использовались как год статьи.
Вторичные выдачи служили навигацией; технические основания выше — первичные
источники. PDF GRID20 прочитан через локальное извлечение вне репозитория после
таймаутов web-reader. Чужие изображения, datasets и code в проект не внесены.

## Что реально предоставляет Macro 1

| Представление | Подтверждённый контракт | Следствие для метода |
|---|---|---|
| `OriginalImageFacts`/`JpegHeader`/DQT | Native размеры, source mode, EXIF mapping, SOF0/SOF2, sampling и selectors, natural-order tables | Не угадывать качество по имени файла, table ID или номеру component |
| `JpegCoefficientsDescriptor` | Clean, immutable int32 planes в native SOF order, `(by,bx,8,8)` | DQ получает исходные quantized coefficients без нового JPEG decode |
| `normalized_image` PNG | Lossless storage подготовленных RGB/RGBA pixels, без resize, с EXIF orientation | Grid может читать уже подготовленный raster; обратная EXIF permutation требует точного mapping |
| `ImageCoordinates` | Native/oriented pixel-edge mapping, normalized bbox | Нельзя сравнивать фазу до/после EXIF без преобразования |
| Residual kernels | Bounded tiles/luminance и числовые операции; **producer `residual_raster` отсутствует** | Тип descriptor не считать готовым producer; новый raster pipeline не нужен при использовании PNG |

Hard envelope: JPEG input <=32 MiB, суммарно <=`2^22` MCU-padded coefficients;
raster <=`2^22` pixels, до 16 tiles по 512×512 и 32 MiB numerical workspace.
Это D/safety limits, не evidence sufficiency. Coefficient plane включает
краевые неполные блоки; их исключение определено в спецификации.

JPEG facts не гарантируют историю, primary DQT или цветовую роль компонента.
Новый декодер/парсер, direct source access, SciPy и дополнительные runtime
dependencies не требуются для предложенных измерений. Same-table perturbation
и некоторые полные likelihood/shift методы потребовали бы отдельного
согласования общего числового/recompression pipeline.

## DQ: сравнение кандидатов

| Подход | Научная опора и полезность | Ограничения и решение |
|---|---|---|
| Signed DCT histograms; periodicity/FFT, missing bins, peak/valley | PF04/LF03 объясняют наблюдаемые искажения при последовательном квантовании; текущие native planes пригодны | Нет универсальной гладкости исходного распределения или transferable cutoff. Выбран как измерительная основа, без классификации |
| Восстановление q1 по missing-bin/периодической структуре | LF03 связывает наблюдаемые формы с первичным шагом | Часть q1 неидентифицируема; близкие/кратные шаги, rounding и мало данных мешают. Не выдавать точный q1 из одного FFT peak |
| A-DJPG likelihood/mixture model, BP12 | Позволяет учитывать single/double hypotheses и строить blockwise map | Нужно зафиксировать estimation/noise/mixture profile, численное решение и working point; likelihood >1 не является заданной FPR. Сильная следующая альтернатива, но не готовая спецификация FakeDetector |
| SVM на low-frequency histograms, PF08 | Обучаемая граница может использовать больше информации, чем один пик | Training corpus/model provenance, domain shift; ML inference против текущего Stage 12 scope. Не выбран |
| Same-table repeated recompression/perturbation, NIU19 | Отдельный сигнал от округления/сходимости; отсутствие DQ modulation не делает задачу всегда невозможной | Новое повторное кодирование, perturbation и codec-dependent калибровка. Не выбран для M2-A; полного текста для переноса алгоритма нет |
| NA-DJPG/shift search, BP12 | Исследует другой DCT grid и compression-history artifact | Нужны retransform/shift hypotheses и иной noise model; не лечится тем же histogram threshold. Не добавлять как неявный fallback |

Выбор DQ-HIST-1 обусловлен прямым соответствием observable существующим
coefficients и возможностью честно наблюдать эффект, сохранив ограничения.
Простота не доказывает качество detector. **Production метод не выбран до
уровня готового decision rule**: точный профиль в `METHODS.md` позволяет
воспроизводимо собирать измерения, но не обходить calibration gate.

Отношения квантов важнее чисел quality: обычно более грубый первый шаг и
более мелкий второй позволяют видеть gaps, обратный порядок может давать
peak/valley, а same/equivalent отношения скрывают modulation. Формула
`n(k)` в спецификации выводится для идеального rounding; она не переносит
cutoff на encoder с clipping/IDCT error. q1 не наблюдается в файле, и нельзя
обещать, что найден точный порядок сохранений.

Grayscale даёт самостоятельную опору. В цветном JPEG subsampled chroma имеет
меньше блоков и другие распределения; применять единый support threshold
к pooled компонентам нельзя. В предложении компоненты измеряются отдельно,
без угадывания Y. Малое изображение может иметь вычислимый histogram и
одновременно недостаточно данных для forensic inference. Baseline и progressive
с одинаковыми окончательными coefficients должны дать одинаковые измерения;
это проверяемая инварианта, а не требование равной статистики всех encoders.

## Grid: что именно проверять

Научно полезный вопрос — согласуется ли **пространственная фаза** наблюдаемых
блоковых границ в разных частях изображения с простой общей историей сетки.
Наличие сильных границ через восемь пикселей ожидаемо у обычного JPEG;
их сила сама по себе не является аномалией. Содержимое может имитировать фазу.

| Семейство | Distinct signal и ограничения | Решение |
|---|---|---|
| Глобальная periodic blocking/phase по первым или вторым разностям | Дешёвый показатель границ, но реагирует на текст/edges; single low-quality JPEG закономерно силён | Не использовать общую blocking strength как positive finding |
| Локальная BAG extraction и сравнение фаз | Пространственное расположение содержит информацию, потерянную в глобальной DQ-гистограмме | Выбран класс задачи; локальность не доказывает независимость от recompression |
| GRID20: cross-difference + local maxima votes + a contrario | Явная модель, объяснимые phase/support и опубликованный критерий grid detection | Выбрана bounded исследовательская адаптация; модель noise и покрытие требуют проверки |
| ZERO21: число близких к нулю DCT coefficients на разных origins | Проверяет grid origins другим observable; local/global и a contrario | Не выбран в первой волне: дополнительные phase-wise DCT, zero tolerance и вычислительный профиль; current-grid coefficients недостаточны. Кандидат не объявляется научно отвергнутым |
| NA-DJPG grid-shift model BP12 | Обнаруживает recompression с несовпадающей сеткой | По смыслу это второй double-JPEG detector, с сильным перекрытием DQ; не выбран как отдельный «независимый» grid proof |

GRID-PHASE-1 сохраняет phase voting, но ограничивает исследуемые окна и явно
переопределяет множитель тестирования. Это **адаптация**, не воспроизведение
авторского software v2.0. Её сравнение с исходным методом, численная
устойчивость и corpus false-positive behavior ещё не проверены.

Нельзя интерпретировать NFA как posterior probability подделки или как
измеренную частоту ошибок на реальных JPEG. Обычный JPEG уже
не является «изображением без решётки» из null model. Нужна калибровка
именно **конфликта фаз**, включая structured benign content, а не только
демонстрация low NFA на JPEG. Следовательно, независимый production grid
метод сейчас не готов. Пространственный сигнал отличается от глобального DQ
и полезен для дальнейшего исследования, но его независимость не доказана;
оснований для выхода из общей correlation group нет.

## Production suitability

| Критерий | DQ-HIST-1 | GRID-PHASE-1 |
|---|---|---|
| Детерминизм | Integer histograms и фиксированные FFT/порядок/ties; floating repeatability проверить | Fixed windows, strict votes, полные log-tail sums; возле decision boundary проверить platforms |
| CPU/RAM | O(9B + 36 L log L), L<=65536; planes/FFT последовательно | До 2^22 обработанных центров и bounded binomial sums; raster/copies отдельно |
| Пространственная опора | Полные native component blocks; forensic минимум C ещё неизвестен | До 16 окон; 64×64 — исходная support рекомендация, не гарантия |
| Объяснимость | Какие распределения измерены; без утверждения q1 | Какая фаза, в каком support, сколько votes; без точной splice mask |
| Качество JPEG | Слабая/неидентифицируемая DQ modulation и sparse AC при сильном сжатии | Высокое качество может не оставлять заметной grid; низкое даёт сильную нормальную grid |
| Grayscale/chroma | Один или несколько раздельных компонентов; subsampling меняет N | Grayscale/RGB luminance; chroma не используется, RGB decode effects проверяются |
| Progressive | Final coefficients, clean decode; не отдельный признак | Final pixels, clean decode; порядок scans не признак |
| Локальность | Глобальная; mixing областей может скрыть сигнал | Статистика окон; малые/непокрытые области могут быть пропущены |
| False positives | Content sparsity/periodicity, clipping, нестандартные tables/encoder | Текстуры, edges, upsampling, phase ties, sampling bias |
| Корреляция | JPEG history; не считать modes независимыми | JPEG history; не считать windows или conflict независимыми от DQ |
| Новые dependencies | Нет | Нет; reference AGPL code не включается |
| Дополнительный preprocessing | Не нужен для измерения; никакого local JPEG decode | Подготовленный PNG + facts достаточны; `residual_raster` producer не требуется |

Все оценки ресурсов аналитические. Ни throughput, ни RSS, ни sensitivity/FPR
в этом исследовании не измерены. Не объявлять dirty-tree development verification
strict certification; package verification вообще не проводилась.

## Пороги и правила вывода

Полный реестр условий и точные формулы принадлежат
[DQ-HIST-1](../METHODS.md#dq-hist-1--гистограммное-измерение-dct) и
[GRID-PHASE-1](../METHODS.md#grid-phase-1--локальные-фазы-blocking-artifacts).

| Класс | Что имеется | Что из этого не следует |
|---|---|---|
| A | GRID20 epsilon=1/NFA<1, рекомендация окна >=64 | Ни project FPR, ни порог подозрения, ни независимость JPEG evidence |
| B | Идеальная DQ lattice periodicity; NFA/multiplicity при выполнении null assumptions | Не доказана применимость noise model к реальным текстурам или bounded адаптации |
| C | Forensic minimum N/nonzero support, DQ periodicity threshold, GRID conflict/persistence threshold, operating FPR и severity calibration | Числа отсутствуют; разработчик не вправе назначить их во время coding |
| D | Полные 8×8 блоки, пустая/вырожденная опора, bounded histogram/raster/windows, valid coordinates | Safe computation не означает достаточную статистическую опору |

Собственные profile constants — девять AC modes, FFT layout, окно/сетка
выборки — полностью определены для измерения и требуют валидации полезности;
это не якобы литературные forensic cutoffs. У numerical QC своя роль:
finite values, log-space без tail truncation, детерминированные ties. Нельзя
заменить calibration epsilon машинным epsilon или бытовым «достаточно блоков».

Выбранное действие при отсутствии C-порогов: **BLOCK production activation**.
Измерительный режим без findings может быть отдельно принят, но не активируется
этим отчётом. Текущий результат `PRODUCTION_THRESHOLDS_JUSTIFIED=NO` относится
к production suspicion/finding thresholds, несмотря на наличие A/B/D оснований.

## Корреляция и benign причины

Предложено единое семейство JPEG compression history и одна существующая
`correlation_group` для обоих методов. Точное предлагаемое значение и поведение
агрегации определены в `METHODS.md`; глобальный risk engine не меняется.
Глобальная DQ modulation и локальный phase conflict дают разные наблюдения,
но могли возникнуть одним benign crop/export. Отдельная группа для локального
случая сейчас не оправдана; проверка взаимного вклада остаётся Macro 6.

Обычные причины обоих сигналов: повторное сохранение, экспорт из редактора,
создание thumbnails, изменение размера/кадрирование сервисом доставки,
поворот с повторным кодированием, подготовка иллюстраций и разрешённый коллаж.
Истинное обнаружение такой истории не является false positive относительно
recompression, но становится ошибочным обвинением при формулировке «подделка».

Отдельные технические ложные срабатывания: единичное JPEG-кодирование
периодической текстуры, sparse DCT на графике/тексте, saturation/clipping,
нестандартные таблицы, scene edges и upsampling. False negatives ожидаемы при
same/equivalent quantization, слабом signal, сильном последнем сжатии,
anti-forensic обработке, смешении областей и недостаточном покрытии. Эта
работа не задаёт adversarial robustness guarantee.

<a id="validation"></a>

## Будущая validation matrix

Это **план**, не результаты тестирования. Все производные одного исходного
изображения должны оставаться в одном train/calibration/holdout split.
Для каждого generated case фиксировать исходник/generator provenance,
encoder/version, реальные DQT, subsampling, mode, pixel transforms и порядок
операций. Quality numbers — лишь параметры конкретного encoder.

### DQ

| ID | Контролируемый случай | Ожидаемое измерение/ограничение |
|---|---|---|
| DQ-01 | Single JPEG из собственного lossless source, несколько DQT | Histogram/FFT baseline; наличие пика само по себе допустимо, recompression label не выводится |
| DQ-02 | Aligned double, по исследуемой частоте q1>q2 | В подходящем содержимом сравнить gaps/периодическую массу с идеальным lattice; rounding может заполнить gaps |
| DQ-03 | Aligned double, q1<q2, включая некратные шаги | Измерить peak/valley и ослабление следа; не требовать обнаружения каждого quality-order case |
| DQ-04 | Same DQT и разные quality labels с одинаковыми q на modes | Возможная неразличимость от single; не проверять обязательный positive |
| DQ-05 | Near-same/custom DQT и кратные q2/q1 | Поэлементно измерить disappearing/aliased modulation; не объявлять q1 из FFT period |
| DQ-06 | Shift `(dx,dy)` по всем 0..7 перед повторным JPEG | Сопоставить с aligned baseline; degradation не превращать в «single JPEG» |
| DQ-07 | Grayscale и одинаковый контент в RGB | Проверить independent component counts/normalization, отсутствие смешивания planes |
| DQ-08 | 4:4:4 / 4:2:2 / 4:2:0 | Проверить geometry и меньший chroma support, разные selectors, отсутствие pooled histogram |
| DQ-09 | Baseline/progressive с идентичными final DCT/DQT | Измерения совпадают; если encoder изменил coefficients, сравнивать фактические данные, не только quality label |
| DQ-10 | Размеры <8, 8, 9, некратные MCU; N=1; flat/all-zero AC | Нет padded evidence, R=1 без спектра, честные counts/insufficient support |
| DQ-11 | Benign repeated save/export, resizing/rotation, 3+ сохранения | Наблюдать историю без утверждения точного save count, злого умысла или chronology |
| DQ-12 | Текст/линии/шахматная сетка, noise/texture, saturation, trellis/custom encoder | Оценить overlap diagnostics single/double; не требовать идеально гладких single histograms |

### Grid

| ID | Контролируемый случай | Ожидаемое измерение/ограничение |
|---|---|---|
| GRID-01 | Обычный aligned single JPEG | Если grid наблюдается — native block-origin `(0,0)`; отсутствие grid допустимо |
| GRID-02 | Low-quality single JPEG с сильным blocking | Высокая концентрация votes на обычной фазе; сила blocking не должна создавать inconsistency finding |
| GRID-03 | Crop/shift на 0..7 px, затем recompression с разными DQT order | Возможны старая shifted phase, новая phase или подавление первой; известный shift — проверка координат, не гарантия detection |
| GRID-04 | Aligned recompression | Phase может оставаться `(0,0)` при выраженной DQ modulation; это важное различие сигналов |
| GRID-05 | Доброкачественные brick/fabric/fences/периодические textures | Измерить spurious phases и NFA; нарушение null model проверять на реальном корпусе |
| GRID-06 | Текст, screenshot, диагонали, резкие edges | Количество votes/ties, axis-only responses; одна значимая ось не даёт двухмерную grid |
| GRID-07 | Размеры 66/67 по каждой оси, flat image, узкие панорамы | Проверить minimum 64 centers, дубли окон, отсутствие голосов и gaps покрытия |
| GRID-08 | Grayscale и chroma-heavy 4:4:4/4:2:2/4:2:0 | Измерить влияние RGB reconstruction; не приписывать chroma grid luminance-процедуре |
| GRID-09 | Все EXIF 1–8, размеры некратны 8, invalid EXIF | После обратной перестановки native phase одинакова; unknown mapping не даёт выдуманную localization |
| GRID-10 | Controlled splice с разными phases; benign collage; маленькие patches в/вне окон | Измерить detectability и coverage; bbox означает окно, не точную маску splice; intent не различается |
| GRID-11 | Upsampling разными kernels, sharpening и повторный export | Проверить non-JPEG periodic patterns и ложные conflicts, даже если NFA мало |
| GRID-12 | Baseline/progressive, high-quality final save и очень сильный final save | При одинаковых pixels одинаковое измерение; отдельно оценить исчезновение prior-grid signal |

### Общие и corpus проверки

- Golden arithmetic fixtures: заданный histogram и точный ideal requantizer
  отдельно от реального codec; отсутствие путаницы signed rounding/floor.
  Для grid — искусственная граница перед x=8/y=8, все фазовые сдвиги,
  equality/ties, log-tail против высокоточного независимого расчёта.
- Determinism: повторные запуски, EXIF permutations, thread scheduling;
  finite/near-zero NFA values на целевых версиях NumPy/Python/platform.
- Failure/resource: malformed identity/shape/byte length, absent required
  artifact, limits ниже/на/выше потолков, serialization ceiling и timeout;
  никакого fallback к source decode и никаких findings из ошибок.
- Корреляция: совместные single, aligned double, shifted double и benign
  exports; при одинаковом group итоговый вклад равен максимуму severity,
  а не сумме. Не менять движок ради удачного benchmark.
- Real corpus обязателен для practical FPR, support minima, domain/encoder
  shift, scene-dependent periodicity, отношения DQ/grid и полезности
  localization. Synthetic fixtures проверяют арифметику, не population FPR.
- Корпус включает фотографии нескольких devices/encoders, документы/графику,
  известные benign delivery workflows, независимый holdout и отдельные
  strata по DQT/order, subsampling, размеру, контенту. Исходники и права
  должны быть известны; реальные media не помещаются в Git.
- Измерять image-level false alarm rate и sensitivity с доверительными
  интервалами, abstention/coverage и stratum counts; для grid дополнительно
  overlap окон с известной областью без обещания pixel segmentation.
  Для DQ отделить «single vs recompressed» от «benign vs malicious».
- До подбора threshold владелец задаёт допустимый operating FPR и область
  применения. Требуемый размер negative holdout выводится из этой цели:
  при независимых изображениях и нуле ошибок односторонняя верхняя граница
  FPR равна `1-alpha^(1/n)` на уровне `1-alpha`. Это B для оценки uncertainty,
  не выбранный здесь production threshold; blocks одного фото не считать n
  независимыми наблюдениями. Ненулевые ошибки требуют соответствующего
  binomial interval. Подгонка threshold и итоговый holdout не совмещаются.

## Owner gates и документационные решения

Конкретные DQ-G1–G4 и GRID-G1–G4 перечислены только в спецификациях
`METHODS.md`. Чтобы реализовывать findings без изобретения правил при coding,
нужно сначала закрыть calibration/profile/semantics gaps, затем получить
принятие владельцем точной версии. Альтернатива — отдельно согласовать
ограниченный measurement-only scope, его честную полноту и дальнейшие
эксперименты. Оба пути оставляют текущий M2-A **BLOCKED**.

`REFERENCES.md` дополнен research provenance, а не разрешением копировать code.
`ROADMAP.md` фиксирует только завершение исследовательского предложения и
следующие gates. `CHANGELOG.md` не меняется: его §§1–2 требуют записи принятых
изменений и исключают ещё не принятые идеи. Канонические контракты, Python,
tests, каталог, dependencies, config/schema, runtime activation не меняются.

Owner review должен включать полный новый файл этого отчёта: до staging
владельцем он остаётся intended untracked и не входит в обычный `git diff`.
Полный review bundle сохраняется вне репозитория по `AGENTS.md`.
