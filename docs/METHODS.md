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
| `image_noise_residual_consistency` | Конкретный метод ещё не принят; требуется общий gate выше |
| `image_resampling_consistency` | Конкретный метод ещё не принят; требуется общий gate выше |
| `image_embedded_thumbnail_consistency` | Конкретный метод ещё не принят; требуется общий gate выше |

Исследование M2-R1 сохранено в
[отчёте от 2026-09-23](research/2026-09-23-jpeg-dq-grid-method-selection.md).
Запись DQ ниже включает принятое правило и semantics production findings.
Принятие разрешает реализацию, но не означает готовность, включение в каталог,
прохождение тестов или release certification. Grid остаётся предложением.

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

- Принятый Analyzer ID: `image_jpeg_double_quantization`, начальная версия
  будущего анализатора `1.0.0`; регистрация ещё не выполнена.
- **ACCEPTED**: явное решение владельца M2-R4 от **2026-09-24** принимает
  полную спецификацию ниже без изменения frozen rule и ограничений.
  Разрешена только реализация; анализатор не реализован, не активен в каталоге,
  не прошёл production tests или release certification.
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
Это привязки принятых свидетельств, не fingerprint будущей реализации.

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
Их фактический общий RSS проверяется в будущей реализации. Не использовать
32 MiB residual workspace как дополнительный JPEG artifact budget.

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
приемлемого bounded research execution, не сертификация будущего worker.

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
не доказывают размер будущего production-конверта: boundary tests обязательны.
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

Будущая задача реализации должна проверить следующую матрицу без tuning:

| Область | Обязательная проверка |
|---|---|
| Measurement equivalence | Signed/zero histogram, DQT natural order, native full-block crop, SOF order при нестандартных IDs; совпадение diagnostics/median/decision с frozen research oracle |
| Support/boundary | N 1023/1024, nonzero 255/256, occupied 7/8, span 15/16 и 65536/65537, 4/5 valid modes, constant/no-full-blocks, odd/even median, equality/соседние binary64 значения около threshold |
| Scope и determinism | L/RGB, три sampling layouts, SOF0/SOF2 после всех scans, EXIF 1–8/unknown без изменения native score; non-JPEG/CMYK/unsupported layout; повтор на тех же coefficients |
| Finding / полнота / корреляция | Один weak positive; null public scores; no_signal отдельно от insufficient_evidence; предупреждения и штатные completed counts; одна family без повторного вклада |
| Negatives / positives / benign | R3C/R3D evidence сохраняется; aligned40to90, reverse/same/close, repeated benign export; synthetic textures, flat, clipping, custom/trellis как challenges, не новое независимое n |
| Failure / ресурсы | Missing/corrupt source-bound artifacts, identity/length/shape mismatch, preflight и общий artifact budget, histogram ceiling, worker response boundary, remaining budget, reap/cleanup и peak RSS при допустимой concurrency |

Research tests и measurements уже свидетельствуют об арифметике и frozen rule;
они не объявляют пройденными production integration/resource tests. Новая
реализация потребует focused tests и полного quality barrier; strict installed
certification возможна только по правилам clean committed SHA.

| Gate | Owner gate M2-R4 от 2026-09-24 | Принятое решение |
|---|---|---|
| DQ-G1 | `CLOSED` | Измерение DQ-HIST-1 и точное support/median правило DQ-R3C-1 без изменений |
| DQ-G2 | `CLOSED` | Frozen threshold, независимые свидетельства и явные population/portability limits |
| DQ-G3 | `CLOSED` | Один weak Finding, null public scores, отдельные no_signal/insufficient semantics в существующих контрактах |
| DQ-G4 | `CLOSED` | Только image JPEG L/RGB на Macro 1, bounded workspace, прежние budgets/failures, без новых dependencies |

Обязательный owner gate полной записи закрыт решением от 2026-09-24:
метод `ACCEPTED`, M2-A — `READY_FOR_IMPLEMENTATION` только в принятом DQ scope.
Production analyzer не реализован; тестирование, activation и release
certification этим решением не подтверждены. Grid не включён в разрешение.
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
