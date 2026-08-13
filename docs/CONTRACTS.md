# CONTRACTS.md

> Канонические контракты данных, внутренних интерфейсов и внешнего взаимодействия проекта.
>
> Версия документа: **1.0**  
> Дата фиксации: **2026-07-24**  
> Статус: **источник истины по интерфейсам и структурам данных**

---

## 0. Назначение документа

`CONTRACTS.md` фиксирует, **какими данными обмениваются компоненты системы**, какие значения считаются допустимыми и как меняются контракты.

Документ определяет:

- общие правила сериализации и именования;
- жизненный цикл задачи анализа;
- внутренние доменные модели;
- контракт анализатора;
- контракт нормализованного признака;
- контракт риск-оценки и полноты анализа;
- итоговый JSON-результат;
- контракт конфигурации;
- логические операции WebUI и API;
- модель ошибок;
- интерфейс репозитория результатов;
- правила версионирования контрактов.

Документ **не описывает повторно**:

- назначение, архитектуру, стек и неизменяемые инварианты — это область `PROJECT.md`;
- порядок разработки и текущий статус — это область `ROADMAP.md`;
- историю принятых изменений — это область `CHANGELOG.md`.

### 0.1. Статусы решений

Используются статусы:

- **FIXED** — контракт принят и обязателен;
- **CONDITIONAL** — контракт применяется при выполнении явно указанных условий;
- **OPEN** — решение не принято, реализация не должна его выдумывать;
- **EXAMPLE** — пример допустимой структуры или значения, не являющийся утверждённой настройкой.

### 0.2. Приоритет документов

При конфликте:

1. назначение и архитектурные границы определяет `PROJECT.md`;
2. поля, типы, статусы, ошибки и интерфейсы определяет `CONTRACTS.md`;
3. реализованный статус и очередность определяет `ROADMAP.md`;
4. причины изменений восстанавливаются по `CHANGELOG.md`.

Архивные файлы не переопределяют настоящий документ.

---

## 1. Общие правила контрактов

### 1.1. Форматы

- Машиночитаемый обмен первой версии: **JSON UTF-8**.
- Конфигурация: **YAML UTF-8**, валидируемый Pydantic-моделями.
- Технические события: **JSON Lines**.
- Имена полей: `snake_case`.
- Имена перечислений: строчные значения `snake_case`.
- Денежные и локализованные числовые форматы не используются.
- Дробные числа сериализуются JSON-числами, а не строками.
- Все JSON-числа должны быть конечными: `NaN`, `Infinity` и `-Infinity`
  отклоняются как в прямых числовых полях, так и внутри вложенных JSON-структур;
  скрытая замена таких значений на `null` запрещена, включая стандартную JSON-
  сериализацию mutable-модели после прямого или вложенного изменения её
  первоначально провалидированного состояния.
- Размер файла указывается в байтах.
- Длительность указывается в секундах.
- Временные отметки указываются в UTC по ISO 8601 с суффиксом `Z`.

Пример времени:

```text
2026-07-24T14:35:22.314Z
```

### 1.2. Идентификаторы

`analysis_id`:

- является непрозрачной строкой;
- уникален в пределах хранилища результатов;
- создаётся системой, а не клиентом;
- не содержит оригинального имени файла, адреса пользователя или других персональных данных;
- может быть реализован на основе UUID/ULID, но клиент не должен зависеть от внутреннего формата.

Идентификаторы анализаторов и признаков:

- стабильны между запусками для одной логической сущности;
- не содержат пробелов;
- используют `snake_case` или стабильный префиксный формат.

### 1.3. Обязательные, необязательные и пустые поля

- Обязательное поле присутствует всегда, даже если значение равно `null`, только когда `null` имеет отдельный контрактный смысл.
- Необязательное неизвестное поле рекомендуется **не включать**, а не заполнять пустой строкой.
- Коллекции верхнего уровня итогового результата присутствуют всегда и используют пустой список `[]`, если элементов нет.
- Строка `"unknown"` не используется вместо отсутствующего значения без отдельного перечисления.
- `0` не используется как замена неизвестного значения.

### 1.4. Версионирование схем

Каждый итоговый результат содержит:

```json
"schema_version": "1.0"
```

Правила:

- изменение документации без изменения структуры данных не меняет `schema_version`;
- добавление необязательного обратно совместимого поля повышает минорную версию;
- удаление поля, переименование, изменение типа или смысла повышает мажорную версию;
- потребитель должен игнорировать неизвестные необязательные поля;
- производитель не должен менять смысл существующего поля без новой версии схемы.

**Статус: FIXED.**

### 1.5. Безопасность содержимого

В пользовательские ответы и результаты не включаются:

- токены и секреты;
- внутренние трассировки;
- произвольные полные пути файловой системы;
- содержимое исходного файла;
- бинарные данные;
- необработанный вывод внешних процессов;
- персональные сведения, не необходимые для сценария.

---

## 2. Перечисления доменной модели

### 2.1. Тип медиа `MediaType`

```text
image
audio
video
```

Иные значения в базовой версии не допускаются.

### 2.2. Канал поступления `SourceChannel`

```text
webui
api
```

Значения `mail_connector`, `siem`, `dlp`, `soar` не являются каналами ядра. Они указываются в поле `connector` или `external_system`, если файл пришёл через API.

### 2.3. Статус задачи `AnalysisStatus`

```text
queued
running
completed
partial
rejected
failed
```

Смысл:

| Значение | Смысл |
|---|---|
| `queued` | Задача зарегистрирована и ожидает обработки |
| `running` | Выполняется один из этапов обработки |
| `completed` | Анализ завершён, обязательная полнота достигнута |
| `partial` | Получен пригодный результат, но часть применимых проверок не выполнена |
| `rejected` | Файл отклонён до специализированного анализа |
| `failed` | Системная ошибка не позволила получить пригодный результат |

`low`, `medium`, `high` не являются статусами задачи.

### 2.4. Текущий этап `ProcessingStage`

```text
registered
validation
routing
queued
preprocessing
analysis
finding_formation
risk_assessment
result_formation
cleanup
persistence
finished
```

Поле этапа предназначено для диагностики и статуса долгой задачи. Оно не заменяет `AnalysisStatus`.

### 2.5. Статус анализатора `AnalyzerStatus`

```text
completed
skipped
not_applicable
error
timeout
```

| Значение | Смысл |
|---|---|
| `completed` | Анализатор выполнился и сформировал корректный результат |
| `skipped` | Анализатор применим, но отключён или пропущен политикой |
| `not_applicable` | Входные данные не удовлетворяют условиям применимости |
| `error` | Анализатор завершился ошибкой |
| `timeout` | Превышено разрешённое время выполнения |

### 2.6. Серьёзность признака `FindingSeverity`

```text
weak
significant
critical
```

### 2.7. Уровень риска `RiskLevel`

```text
low
medium
high
```

Уровень риска отсутствует (`null`) для `rejected`, `failed` и результата с недостаточной полнотой, если политика не разрешает корректную оценку.

### 2.8. Статус полноты `CompletenessStatus`

```text
complete
partial
insufficient
not_assessed
```

### 2.9. Статус очистки `CleanupStatus`

```text
not_started
completed
partial
failed
```

---

## 3. Жизненный цикл задачи

### 3.1. Канонические переходы

```text
queued
  → running
      → completed
      → partial
      → rejected
      → failed
```

Уточнение:

- `rejected` обычно возникает на этапах `validation` или `routing`;
- `partial` возникает, когда результат пригоден, но покрытие снижено;
- `failed` возникает при системной ошибке, не позволяющей сформировать пригодную оценку;
- терминальный статус не возвращается в `queued` или `running` без создания новой задачи повторного анализа.

### 3.2. Внутренний контекст задачи `AnalysisContext`

Минимальные поля:

| Поле | Тип | Обязательность | Назначение |
|---|---|---:|---|
| `analysis_id` | string | да | Идентификатор анализа |
| `created_at` | datetime | да | Время регистрации |
| `status` | `AnalysisStatus` | да | Текущий статус |
| `stage` | `ProcessingStage` | да | Текущий этап |
| `source` | `SourceContext` | да | Источник поступления |
| `workspace_path` | internal path | внутреннее | Изолированная рабочая область |
| `media_type` | `MediaType|null` | да | Определённый тип или `null` до маршрутизации |
| `config_snapshot_id` | string | да | Идентификатор использованной конфигурации |
| `started_at` | datetime|null | да | Начало обработки |
| `finished_at` | datetime|null | да | Окончание обработки |

`workspace_path` не сериализуется во внешний результат.

---

## 4. Источник поступления `SourceContext`

### 4.1. Модель

```json
{
  "channel": "api",
  "connector": "mail_connector",
  "external_system": "corporate_mail_gateway",
  "external_reference": "mail-784512"
}
```

### 4.2. Поля

| Поле | Тип | Обязательность | Ограничение |
|---|---|---:|---|
| `channel` | `SourceChannel` | да | `webui` или `api` |
| `connector` | string|null | нет | Идентификатор внешнего коннектора |
| `external_system` | string|null | нет | Логическое имя внешней системы |
| `external_reference` | string|null | нет | Внешний идентификатор сообщения/объекта |

Адрес отправителя электронной почты не является обязательным полем базового контракта. Если он нужен интеграции, его передача требует отдельной политики персональных данных.

---

## 5. Сведения о файле

### 5.1. Входной дескриптор `InputFileDescriptor`

| Поле | Тип | Обязательность |
|---|---|---:|
| `original_name` | string | да |
| `declared_content_type` | string|null | да |
| `size_bytes` | integer | да |
| `received_at` | datetime | да |

Правила:

- `original_name` используется только для отображения и диагностики;
- имя не используется для формирования системного пути;
- для MVP `original_name` обязан содержать расширение;
- `file.mp4` и `archive.tar.mp4` дают нормализованное расширение `mp4`;
- `file`, `file.` и `.mp4` считаются именами без расширения и отклоняются с
  кодом `missing_extension`;
- ведущая точка не входит в значение расширения, обычное расширение приводится
  к lowercase;
- расширение извлекается безопасно, но не используется в системном пути или
  внутреннем имени временного input;
- `declared_content_type=null` является допустимым входом и само по себе не
  приводит к отклонению;
- `size_bytes` равен фактически измеренному при потоковом intake размеру, а не
  недоверенному `Content-Length`;
- содержимое файла передаётся отдельно от дескриптора.

Внешний адаптер передаёт поток и доступные исходные сведения, но не определяет
`size_bytes`. Intake service формирует `InputFileDescriptor` после фактического
измерения controlled input.

### 5.2. Проверенный дескриптор `ValidatedFileDescriptor`

```json
{
  "original_name": "video_message.mp4",
  "extension": "mp4",
  "declared_mime_type": "video/mp4",
  "detected_mime_type": "video/mp4",
  "media_type": "video",
  "size_bytes": 48231520,
  "sha256": "...",
  "signature_match": true,
  "safe_read": true,
  "technical_parameters": {}
}
```

Обязательные смысловые поля:

- оригинальное имя;
- нормализованное расширение;
- заявленный MIME, если был передан;
- обнаруженный MIME;
- тип медиа;
- размер;
- SHA-256;
- результат проверки сигнатуры;
- результат безопасного чтения;
- технические параметры.

### 5.3. Технические параметры

Параметры зависят от типа медиа и хранятся как типизированная вложенная модель.

Изображение:

- ширина;
- высота;
- формат;
- цветовой режим;
- число кадров, если применимо;
- наличие метаданных.

Аудио:

- длительность;
- частота дискретизации;
- число каналов;
- формат/кодек;
- битрейт, если доступен.

Видео:

- длительность;
- контейнер;
- видеокодек;
- аудиокодек, если есть;
- ширина и высота;
- частота кадров;
- битрейт, если доступен;
- наличие аудиодорожки.

Неизвестные параметры не заполняются вымышленными значениями.

Естественно необязательные metadata и технические параметры могут отсутствовать
только там, где соответствующее поле допускает `null`. Отсутствие EXIF или иных
необязательных metadata само по себе не является validation failure, finding или
основанием для изменения риска. Если обязательный параметр невозможно получить
при безопасном probe/decode, `ValidatedFileDescriptor` сформировать нельзя.

---

## 6. Контракт первичной проверки

### 6.1. `ValidationResult`

```json
{
  "accepted": true,
  "checks": [
    {
      "code": "file_size_allowed",
      "passed": true,
      "message": "Размер файла соответствует ограничению."
    }
  ],
  "errors": [],
  "validated_file": {}
}
```

Поля:

| Поле | Тип | Обязательность |
|---|---|---:|
| `accepted` | boolean | да |
| `checks` | array of `ValidationCheck` | да |
| `errors` | array of `ErrorDetail` | да |
| `validated_file` | `ValidatedFileDescriptor|null` | да |

### 6.2. Обязательные проверки

- непустой файл;
- наличие расширения;
- допустимое расширение;
- допустимый обнаруженный MIME;
- фактическая сигнатура;
- соответствие заявленного и фактического типа, только если заявленный MIME
  присутствует;
- безопасное чтение/декодирование;
- обязательные технические параметры;
- поддерживаемый тип медиа;
- максимальный размер для определённого типа медиа;
- SHA-256 для принятого файла.

Специализированный анализ не запускается при `accepted=false`.

`declared_content_type=null` и `declared_mime_type=null` не являются причиной
отклонения. В этом случае consistency check между заявленным и обнаруженным MIME
логически неприменим, а остальные проверки выполняются. Allowed MIME проверяется
по обнаруженному фактическому типу, а не по недоверенному declared MIME.

### 6.3. MVP allowlist и нормативная матрица форматов

MVP принимает только следующие согласованные сочетания. Дополнительные
расширения или MIME-алиасы не входят в allowlist без отдельного изменения
контракта.

| MediaType | Extension | Detected MIME | Фактическая сигнатура/контейнер | Safe reader/decode |
|---|---|---|---|---|
| image | `jpg`, `jpeg` | `image/jpeg` | JPEG markers | полный image decode |
| image | `png` | `image/png` | PNG signature | полный image decode |
| image | `webp` | `image/webp` | RIFF/WEBP | полный image decode |
| audio | `wav` | `audio/wav` | RIFF/WAVE | controlled audio probe и bounded decode |
| audio | `mp3` | `audio/mpeg` | ID3 или MPEG audio frames | controlled audio probe и bounded decode |
| audio | `flac` | `audio/flac` | FLAC marker | controlled audio probe и bounded decode |
| audio | `m4a` | `audio/mp4` | совместимый ISO BMFF/M4A container | controlled audio probe и bounded decode |
| video | `mp4` | `video/mp4` | совместимый ISO BMFF/MP4 container | controlled video probe и bounded decode |
| video | `mov` | `video/quicktime` | совместимый QuickTime container | controlled video probe и bounded decode |
| video | `avi` | `video/x-msvideo` | RIFF/AVI | controlled video probe и bounded decode |
| video | `mkv` | `video/x-matroska` | Matroska/EBML | controlled video probe и bounded decode |

Принимаются только сочетания extension, detected MIME, сигнатуры/контейнера и
`MediaType`, согласованные одной строкой матрицы. Declared MIME не заменяет
detected MIME и, если передан, отдельно проверяется на согласованность.

### 6.4. Ограничение размера и SHA-256

До определения фактического `MediaType` hard limit равен максимальному из
настроенных `max_file_size_mb.image`, `audio` и `video`. После определения типа
к фактически измеренному размеру применяется соответствующий per-media limit.
Превышение любого применимого лимита является controlled rejection с
`file_too_large`.

Extension, declared MIME, `original_name` и `Content-Length` не выбирают
первоначальный лимит и не задают фактический `size_bytes`. Вход читается порциями;
фактический размер и SHA-256 рассчитываются в том же intake pass. Конкретные
числовые лимиты остаются конфигурацией.

### 6.5. Семантика безопасного чтения

Для image `safe_read=true` означает полное безопасное декодирование и получение
всех обязательных технических параметров.

Для audio и video полный decode всего файла на первичной проверке не требуется.
`safe_read=true` означает controlled safe open/probe, получение обязательных
технических параметров и ограниченное декодирование, достаточное для
подтверждения читаемости. Внешние процессы имеют timeout. Для video это не
означает, что каждый кадр файла уже декодирован.

Конкретные пределы bounded decode являются конфигурацией или implementation
detail. Первичная проверка не создаёт нормализованные копии, key frames,
аудиофрагменты, спектрограммы, извлечённые аудиодорожки или иные preprocessing-
артефакты.

### 6.6. Внутренний контракт временного владения

Логическая цепочка безопасного intake:

```text
external adapter
→ intake application service
→ temporary input owner
→ file validator
→ accepted ownership handoff
  или rejected / failed + cleanup
```

Temporary input owner создаёт `runtime/temp/<analysis_id>`, формирует внутреннее
имя input без пользовательских строк, потоково записывает controlled source,
предоставляет validator непрозрачную внутреннюю ссылку и удаляет принадлежащий
ему ресурс по команде intake service. Validator не владеет workspace и не
выполняет cleanup.

Каталог создаётся с минимально необходимой для текущего локального runtime
политикой доступа и изолируется от workspace других `analysis_id`. Hardening
против concurrent path substitution, TOCTOU и полный no-follow redesign
относятся к Stage 9 и не являются частью этого контракта Stage 3.

Успешный внутренний handoff логически содержит:

```text
ValidatedFileDescriptor
+ opaque owned-source / lease / controlled handle
```

Точная Python-форма handle является implementation detail. Handle и внутренний
путь не входят в `ValidatedFileDescriptor`, `ValidationResult` или внешний JSON.
Полный `AnalysisContext` для Stage 3 не требуется. До handoff достаточно
`analysis_id`, `SourceContext`, времени регистрации/приёма и temporary ownership
handle.

До успешного handoff owner отвечает за cleanup при rejection и exception. После
handoff Stage 4 принимает ownership и отвечает за дальнейший lifecycle и
последующую очистку accepted input. Если handoff не состоялся, ownership остаётся
у Stage 3.

### 6.7. Прикладной результат Stage 3

Единый integrated intake service возвращает внутренний прикладной результат:

```text
Stage3Outcome = Stage3Accepted | Stage3Terminal
```

Это application-level boundary между Stage 3 и downstream lifecycle, а не
внешний API/JSON contract и не публичная доменная модель Этапа 2. Он не изменяет
`schema_version` итогового JSON.

Stage 3 не формирует `AnalysisResult`. В частности, запрещено заполнять его
вымышленными queue timestamps, `config_snapshot_id`, processing values, risk,
recommendation или файловым дескриптором с неизвестным фактическим размером.
`AnalysisResult` формируется последующим lifecycle только после появления
требуемых им фактических данных.

#### `Stage3Accepted`

Успешный результат по смыслу содержит:

- фактический `analysis_id`;
- время успешной регистрации;
- `SourceContext`;
- успешный `ValidationResult`;
- тот же `ValidatedFileDescriptor`, который присутствует в validation result;
- непрозрачную controlled source capability, переданную downstream lifecycle.

Обязательные инварианты:

```text
validation.accepted == true
validation.validated_file != null
```

`Stage3Accepted` не является `AnalysisResult`, не получает искусственные
`AnalysisStatus` или `ProcessingStage` и не содержит findings, risk,
recommendation, `CleanupResult` или filesystem path. После подтверждённого
handoff обязанность cleanup больше не принадлежит Stage 3.

#### `Stage3Terminal`

`Stage3Terminal` используется только после успешной регистрации анализа, поэтому
`analysis_id`, registration timestamp и `SourceContext` обязательны. Результат
содержит только фактически доступные Stage 3 данные:

- `InputFileDescriptor | null`;
- `ValidationResult | null`;
- `ValidatedFileDescriptor | null`;
- terminal `AnalysisStatus`: только `rejected` или `failed`;
- terminal `ProcessingStage`: `finished`;
- `analyzers=[]`;
- `findings=[]`;
- completeness=`not_assessed`;
- final risk level=`null`;
- recommendation=`null`;
- `CleanupResult | null` согласно разделу 6.9;
- массив безопасных `ErrorDetail` с primary reason.

Отсутствующие значения не заменяются placeholders. `ValidationResult` равен
`null`, если primary validation не запускалась или не завершилась нормативным
результатом. `ValidatedFileDescriptor` присутствует только если validation была
успешно завершена до последующего системного сбоя, например failed handoff.

### 6.8. Сбой до регистрации

Если системный `analysis_id` не удалось получить либо успешная Stage 3
регистрация не была установлена, сервис не создаёт `Stage3Terminal` и не
фабрикует идентификатор. Такой сбой покидает application boundary как безопасное
типизированное pre-registration exception.

Pre-registration exception не является validation rejection или
`AnalysisResult` и не раскрывает исходное сообщение внутреннего исключения,
filesystem path, traceback или другие implementation details. После успешной
регистрации обычные системные сбои Stage 3 преобразуются integrated service в
фактический `Stage3Terminal` со статусом `failed`.

### 6.9. Cleanup terminal outcome

Если `OwnedSource` никогда не был создан, cleanup не требовался и
`Stage3Terminal.cleanup=null`. `CleanupStatus.NOT_STARTED` не используется как
неявный синоним «cleanup not required».

Если Stage 3 получил ownership и завершает `rejected` или `failed` до успешного
handoff, выполняется ровно одна immediate cleanup attempt. Её фактический
результат записывается в обязательный для этого случая `CleanupResult`.
Cleanup retry, TTL и quarantine остаются ответственностью Stage 4 и не
применяются Stage 3.

Cleanup failure не меняет и не маскирует primary outcome:

- validation rejection остаётся `rejected`, validation errors сохраняются, а
  cleanup failure отражается отдельно в `CleanupResult`;
- system failure остаётся `failed`, primary safe system error сохраняется, а
  cleanup error отражается отдельно;
- handoff failure является `failed`; primary handoff/system cause и cleanup
  failure сохраняются раздельно.

Результат не должен заявлять успешное удаление, если фактическая cleanup attempt
завершилась частично или неуспешно.

### 6.10. Pre-detection hard limit

`FileTooLargeError`, возникший во время bounded intake до primary validation,
является нормативным input rejection:

```text
status = rejected
error.code = file_too_large
validation_result = null
```

Synthetic `ValidationResult` не создаётся. `observed_size_bytes` означает только
число байтов, достаточное для подтверждения превышения hard limit, и не выдаётся
за полный фактический размер внешнего файла.

### 6.11. Accepted ownership handoff

До успешного подтверждения узким downstream receiver port обязанность cleanup
остаётся у Stage 3. После успешного подтверждения она переходит downstream
lifecycle. Минимальное внутреннее направление ownership state:

```text
owned
→ handed_off
→ released
```

Это implementation-private state, а не domain enum или сериализуемый контракт.
Pre-handoff cleanup terminal outcome переводит `owned` непосредственно в
`released`, не создавая ложного handoff.
Handoff имеет move-style semantics: исходная Stage 3 capability после transfer
недействительна; double transfer, transfer released source и transfer foreign
ownership запрещены. Успешный handoff запрещает последующий cleanup со стороны
Stage 3. Если receiver не подтвердил handoff, ownership и cleanup obligation
остаются у Stage 3 и выполняется одна immediate cleanup attempt.

Узкий receiver port не является универсальным lease/capability framework и не
реализует Stage 4. Stage 3 заканчивается либо accepted validated descriptor и
подтверждённым controlled ownership handoff, либо terminal `rejected`/`failed` с
фактическим pre-handoff cleanup outcome. Concrete downstream lifecycle,
`AnalysisContext`, state machine, queue, routing, concurrency, executor/process
lifecycle, artifact registry, eventual accepted-source cleanup, retries, TTL и
quarantine принадлежат Stage 4.

### 6.12. Adapter-neutral boundary

Integrated Stage 3 service принимает по смыслу:

```text
binary stream
original_name
declared_content_type | null
SourceContext
```

Application contract не зависит от FastAPI `UploadFile`. HTTP/WebUI analysis
wiring реализуется на соответствующей последующей стадии.

---

## 7. Контракт предварительной обработки

### 7.1. Общая модель `PreparedMedia`

Предварительная обработка возвращает ссылки на контролируемые рабочие артефакты и типизированные параметры, но не встраивает бинарные данные в JSON.

Общие поля:

| Поле | Тип | Назначение |
|---|---|---|
| `analysis_id` | string | Связь с задачей |
| `media_type` | `MediaType` | Маршрут обработки |
| `source_file_ref` | internal ref | Ссылка на исходный временный файл |
| `artifacts` | array of `PreparedArtifact` | Созданные промежуточные данные |
| `metadata` | object | Извлечённые метаданные |
| `warnings` | array | Предупреждения подготовки |

### 7.2. `PreparedArtifact`

Минимальные поля:

- `artifact_id`;
- `artifact_type`;
- внутренняя ссылка;
- формат;
- временной интервал или номер кадра, если применимо;
- признак необходимости удаления.

Допустимые типы включают:

```text
normalized_image
key_frame
audio_fragment
spectrogram
extracted_audio_track
metadata_snapshot
```

Внутренние файловые ссылки не включаются во внешний итоговый результат.

---

## 8. Контракт анализатора

### 8.1. Требования к анализатору

Каждый анализатор обязан иметь:

- стабильный `analyzer_id`;
- `analyzer_version`;
- поддерживаемый тип медиа;
- объявленные условия применимости;
- типизированные настройки;
- ограничение времени;
- детерминированную обработку ошибок;
- метод формирования структурированного результата;
- тесты контракта.

Анализатор не должен:

- самостоятельно формировать итоговый риск;
- записывать итоговый JSON напрямую;
- управлять HTTP-ответом;
- хранить исходный файл долговременно;
- создавать признак без указания источника и версии.

### 8.2. Логический интерфейс

```python
class Analyzer(Protocol):
    analyzer_id: str
    analyzer_version: str
    media_type: MediaType

    def check_applicability(
        self,
        request: AnalyzerRequest,
    ) -> ApplicabilityResult: ...

    def analyze(
        self,
        request: AnalyzerRequest,
    ) -> AnalyzerResult: ...
```

Синхронность интерфейса является логической. Оркестратор может выполнять анализатор в потоке или отдельном процессе.

### 8.3. `AnalyzerRequest`

Содержит:

- `analysis_id`;
- тип медиа;
- проверенный дескриптор файла;
- подготовленные данные;
- безопасный снимок настроек анализатора;
- лимит времени;
- сведения о качестве входа, необходимые методу.

Не содержит API-токенов, пользовательских паролей и несвязанных данных источника.

### 8.4. `AnalyzerResult`

```json
{
  "analyzer_id": "audio_video_sync_analyzer",
  "analyzer_version": "1.0.0",
  "media_type": "video",
  "group": "multimodal",
  "status": "completed",
  "applicable": true,
  "started_at": "2026-07-24T14:35:25Z",
  "finished_at": "2026-07-24T14:35:42Z",
  "duration_ms": 17000,
  "score": 0.94,
  "score_name": "model_confidence",
  "summary": "Выявлено устойчивое несоответствие аудио и движения губ.",
  "raw_metrics": {},
  "candidate_findings": [],
  "warnings": [],
  "errors": []
}
```

Обязательные поля:

| Поле | Тип |
|---|---|
| `analyzer_id` | string |
| `analyzer_version` | string |
| `media_type` | `MediaType` |
| `group` | string |
| `status` | `AnalyzerStatus` |
| `applicable` | boolean |
| `started_at` | datetime|null |
| `finished_at` | datetime|null |
| `duration_ms` | integer|null |
| `score` | number|null |
| `score_name` | string|null |
| `summary` | string |
| `raw_metrics` | object |
| `candidate_findings` | array |
| `warnings` | array |
| `errors` | array of `ErrorDetail` |

Правила:

- `score` имеет смысл только вместе с `score_name`;
- `score` отдельного анализатора не является итоговой вероятностью подделки;
- при `status=not_applicable` поле `applicable=false`;
- при `error` и `timeout` ошибка обязательна;
- при `skipped` должна быть указана безопасная причина.

---

## 9. Контракт признака `Finding`

### 9.1. Модель

```json
{
  "finding_id": "finding_0004",
  "group": "multimodal",
  "type": "audio_video_desynchronization",
  "severity": "critical",
  "source_analyzer_id": "audio_video_sync_analyzer",
  "source_analyzer_version": "1.0.0",
  "description": "Выявлено устойчивое несоответствие аудиодорожки и движения губ.",
  "localization": {
    "type": "time_interval",
    "start_seconds": 12.1,
    "end_seconds": 19.5
  },
  "source_score": 0.94,
  "score_impact": null,
  "critical_override_eligible": false,
  "correlation_group": "face_sync_segment_1",
  "evidence_refs": []
}
```

### 9.2. Поля

| Поле | Тип | Обязательность |
|---|---|---:|
| `finding_id` | string | да |
| `group` | string | да |
| `type` | string | да |
| `severity` | `FindingSeverity` | да |
| `source_analyzer_id` | string | да |
| `source_analyzer_version` | string | да |
| `description` | string | да |
| `localization` | `Localization|null` | да |
| `source_score` | number|null | да |
| `score_impact` | number|null | да |
| `critical_override_eligible` | boolean | да |
| `correlation_group` | string|null | да |
| `evidence_refs` | array of string | да |

`critical_override_eligible=true` разрешается только утверждённой политикой. Высокий `source_score` сам по себе не делает признак критическим.

### 9.3. Локализация `Localization`

Допустимые варианты:

#### Файл целиком

```json
{ "type": "file" }
```

#### Область изображения

```json
{
  "type": "bounding_box",
  "x": 0.21,
  "y": 0.15,
  "width": 0.34,
  "height": 0.42,
  "coordinate_space": "normalized"
}
```

Координаты нормализованы в диапазоне `0..1`.

#### Временной интервал

```json
{
  "type": "time_interval",
  "start_seconds": 12.1,
  "end_seconds": 19.5
}
```

#### Интервал кадров

```json
{
  "type": "frame_interval",
  "start_frame": 302,
  "end_frame": 487
}
```

Дополнительные виды локализации требуют повышения минорной версии схемы.

---

## 10. Контракт полноты анализа

### 10.1. `AnalysisCompleteness`

```json
{
  "status": "partial",
  "planned_analyzers": 5,
  "applicable_analyzers": 4,
  "completed_analyzers": 3,
  "failed_analyzers": 1,
  "timed_out_analyzers": 0,
  "skipped_analyzers": 1,
  "not_applicable_analyzers": 0,
  "coverage_ratio": 0.75,
  "missing_capabilities": ["synthetic_speech_detection"],
  "explanation": "Один применимый аудиоанализатор завершился ошибкой."
}
```

### 10.2. Правила

- `coverage_ratio` рассчитывается только по утверждённому алгоритму;
- до утверждения взвешенной модели допускается простое отношение успешно завершённых применимых анализаторов к числу применимых анализаторов;
- простой коэффициент имеет статус **CONDITIONAL** и должен сопровождаться версией алгоритма;
- `complete` означает выполнение всех обязательных применимых проверок активного профиля;
- `partial` означает, что оценка возможна, но покрытие снижено;
- `insufficient` означает, что надёжная риск-оценка не формируется;
- `not_assessed` используется для отклонённого файла или системного сбоя до анализа.

При `insufficient` поле `risk_assessment.final_level` должно быть `null`, если иное не утверждено отдельной политикой.

---

## 11. Контракт риск-оценки

### 11.1. `RiskAssessment`

```json
{
  "model_id": "score_model_v1",
  "model_version": "0.1.0",
  "score": 60,
  "score_based_level": "medium",
  "critical_override_applied": false,
  "critical_finding_ids": [],
  "final_level": "medium",
  "probability": null,
  "probability_method": null,
  "summary": "Выявлены значимые признаки возможной модификации.",
  "explanation": "Итог сформирован по совокупности двух независимых признаков.",
  "limitations": ["Анализ синтетической речи не выполнен."]
}
```

### 11.2. Поля

| Поле | Тип | Правило |
|---|---|---|
| `model_id` | string | Идентификатор алгоритма агрегации |
| `model_version` | string | Версия правил и весов |
| `score` | number|null | Только если активна балльная модель |
| `score_based_level` | `RiskLevel|null` | Уровень до critical override |
| `critical_override_applied` | boolean | Факт применения правила |
| `critical_finding_ids` | array | Основания override |
| `final_level` | `RiskLevel|null` | Итоговый уровень |
| `probability` | number|null | Только при валидированном методе |
| `probability_method` | string|null | Обязателен вместе с probability |
| `summary` | string | Краткое резюме |
| `explanation` | string | Объяснение результата |
| `limitations` | array of string | Ограничения оценки |

### 11.3. Обязательные ограничения

- `probability` по умолчанию равна `null`;
- запрещено копировать максимальный `AnalyzerResult.score` в `probability`;
- при `critical_override_applied=true` массив `critical_finding_ids` не пуст;
- при недостаточной полноте `final_level` не должен ложно принимать `low`;
- коррелирующие признаки не суммируются повторно без заданного правила;
- веса и пороги имеют отдельную версию.

Конкретные веса, пороги, корреляция и разрешённые critical-признаки имеют статус **OPEN** до отдельного решения.

---

## 12. Контракт рекомендации

### 12.1. `Recommendation`

```json
{
  "primary_action": "manual_review",
  "additional_actions": [
    "verify_source_via_independent_channel"
  ],
  "text": "Рекомендуется выполнить ручную проверку и подтвердить источник по независимому каналу.",
  "requires_manual_review": true
}
```

### 12.2. Действия

```text
no_additional_action
manual_review
verify_source
verify_source_via_independent_channel
request_better_quality_source
retry_analysis
escalate_to_security
send_to_incident_response
```

Автоматическое удаление письма, блокировка пользователя и автоматическое подтверждение бизнес-операции не входят в контракт ядра MVP.

---

## 13. Ошибки и предупреждения

### 13.1. `ErrorDetail`

```json
{
  "code": "file_signature_mismatch",
  "category": "validation",
  "message": "Фактический тип файла не соответствует заявленному.",
  "retryable": false,
  "field": "file",
  "analyzer_id": null,
  "safe_details": {}
}
```

Поля:

- `code` — стабильный машинный код;
- `category` — категория;
- `message` — безопасное человекочитаемое сообщение;
- `retryable` — можно ли повторить операцию без изменения входа;
- `field` — связанное поле, если применимо;
- `analyzer_id` — источник ошибки анализатора;
- `safe_details` — только безопасные структурированные детали.

### 13.2. Категории

```text
authentication
authorization
validation
unsupported_media
resource_limit
processing
analyzer
storage
cleanup
configuration
internal
```

### 13.3. Канонические коды MVP

| Код | Категория | Смысл |
|---|---|---|
| `authentication_required` | authentication | Не предоставлен токен/сессия |
| `authentication_failed` | authentication | Недействительные данные доступа |
| `file_missing` | validation | Файл не передан |
| `file_empty` | validation | Пустой файл |
| `file_too_large` | resource_limit | Превышен лимит |
| `missing_extension` | unsupported_media | В `original_name` отсутствует обязательное расширение |
| `unsupported_extension` | unsupported_media | Расширение не поддерживается |
| `unsupported_mime_type` | unsupported_media | MIME не поддерживается |
| `file_signature_mismatch` | validation | Несоответствие сигнатуры |
| `unsafe_or_unreadable_file` | validation | Файл не удалось безопасно прочитать |
| `unsupported_media_type` | unsupported_media | Тип не image/audio/video |
| `processing_timeout` | processing | Общий тайм-аут задачи |
| `analyzer_error` | analyzer | Ошибка конкретного анализатора |
| `analyzer_timeout` | analyzer | Тайм-аут анализатора |
| `result_not_found` | storage | Результат не найден |
| `result_write_failed` | storage | Не удалось атомарно сохранить результат |
| `cleanup_failed` | cleanup | Не удалось очистить данные |
| `invalid_configuration` | configuration | Конфигурация не прошла проверку |
| `internal_error` | internal | Непредвиденная системная ошибка |

Новые коды добавляются без переиспользования смысла существующих.

---

## 14. Контракт итогового результата `AnalysisResult`

### 14.1. Верхнеуровневая структура

```json
{
  "schema_version": "1.0",
  "analysis_id": "01J3...",
  "created_at": "2026-07-24T14:35:22Z",
  "updated_at": "2026-07-24T14:36:18Z",
  "status": "partial",
  "stage": "finished",
  "source": {},
  "file": {},
  "processing": {},
  "analyzers": [],
  "findings": [],
  "completeness": {},
  "risk_assessment": {},
  "recommendation": {},
  "cleanup": {},
  "warnings": [],
  "errors": []
}
```

### 14.2. Блок `processing`

```json
{
  "queued_at": "2026-07-24T14:35:22Z",
  "started_at": "2026-07-24T14:35:23Z",
  "finished_at": "2026-07-24T14:36:18Z",
  "duration_ms": 55000,
  "config_snapshot_id": "config_sha256_prefix",
  "application_version": "0.1.0"
}
```

### 14.3. Блок `cleanup`

```json
{
  "status": "completed",
  "original_file_deleted": true,
  "intermediate_files_deleted": true,
  "quarantine_used": false,
  "finished_at": "2026-07-24T14:36:17Z",
  "errors": []
}
```

### 14.4. Правила терминальных результатов

#### `completed`

- файл принят;
- `file` является `ValidatedFileDescriptor`;
- анализ выполнен с требуемой полнотой;
- `completeness.status=complete`;
- `risk_assessment.final_level` не равен `null`;
- риск и рекомендация сформированы;
- результат сохранён;
- статус очистки отражает фактическое состояние.

#### `partial`

- файл принят;
- `file` является `ValidatedFileDescriptor`;
- получена пригодная, но ограниченная оценка;
- полнота равна `partial`;
- `risk_assessment.final_level` не равен `null`;
- ограниченность результата явно отражена на верхнем уровне итогового
  `AnalysisResult`: top-level `warnings` достаточно только если хотя бы один
  warning содержит непустой после `.strip()` текст; также достаточно непустого
  `errors`, непустого после `.strip()` `completeness.explanation` или хотя бы
  одного непустого после `.strip()` элемента `risk_assessment.limitations`;
- предупреждения и ошибки только внутри отдельных `AnalyzerResult` сами по себе
  не удовлетворяют этому правилу.

#### `rejected`

- ожидаемое нарушение требований к входу обнаружено на validation/routing;
- анализаторы не запускались;
- `findings=[]`;
- `risk_assessment.final_level=null`;
- `completeness.status=not_assessed`;
- причина отклонения присутствует в `errors` стабильным машинным кодом;
- cleanup временного input до ownership handoff выполняется и его фактический
  результат отражается существующим блоком `cleanup`.

#### `failed`

- внутренняя системная ошибка FakeDetector, а не нормативное свойство входа, не
  позволила продолжить обработку;
- пригодная риск-оценка отсутствует;
- `risk_assessment.final_level=null`;
- причина сбоя отражена безопасно;
- очистка всё равно выполняется и фиксируется.

К `rejected` относятся, в частности, отсутствие или неподдерживаемость
расширения, неподдерживаемый фактический MIME/тип, несоответствие сигнатуры или
типов, пустой или слишком большой файл и повреждённый/безопасно недекодируемый
input. Невозможность создать workspace, внутренняя ошибка записи и неожиданный
системный exception относятся к `failed` и не маскируются как invalid input.

Cleanup не добавляется в `ValidationResult`: Stage 3 отражает фактическое удаление
в `Stage3Terminal.cleanup` согласно разделу 6.9. Последующий lifecycle переносит
эти фактические данные в `CleanupResult` terminal `AnalysisResult` только когда
может сформировать весь итоговый результат без placeholders. Если промежуточные
артефакты не создавались, `intermediate_files_deleted=true` означает, что после
cleanup промежуточных файлов не осталось; это не утверждение об их создании.

### 14.5. Полный пример

Полный пример является **EXAMPLE** и не утверждает конкретные анализаторы, веса и пороги.

```json
{
  "schema_version": "1.0",
  "analysis_id": "01J3EXAMPLE0001",
  "created_at": "2026-07-24T14:35:22Z",
  "updated_at": "2026-07-24T14:36:18Z",
  "status": "partial",
  "stage": "finished",
  "source": {
    "channel": "api",
    "connector": "mail_connector",
    "external_system": "corporate_mail_gateway",
    "external_reference": "mail-784512"
  },
  "file": {
    "original_name": "video_message.mp4",
    "extension": "mp4",
    "declared_mime_type": "video/mp4",
    "detected_mime_type": "video/mp4",
    "media_type": "video",
    "size_bytes": 48231520,
    "sha256": "b9f4c7a8e0f8b2c1a7d6e3f9120d6a8e2f3b6c1d44f8e8a91d6f9e41a5b2c773",
    "signature_match": true,
    "safe_read": true,
    "technical_parameters": {
      "container": "mp4",
      "duration_seconds": 42.6,
      "video_codec": "h264",
      "audio_codec": "aac",
      "width": 1280,
      "height": 720,
      "fps": 25.0,
      "has_audio": true
    }
  },
  "processing": {
    "queued_at": "2026-07-24T14:35:22Z",
    "started_at": "2026-07-24T14:35:23Z",
    "finished_at": "2026-07-24T14:36:18Z",
    "duration_ms": 55000,
    "config_snapshot_id": "config_example",
    "application_version": "0.1.0"
  },
  "analyzers": [
    {
      "analyzer_id": "audio_video_sync_analyzer",
      "analyzer_version": "1.0.0",
      "media_type": "video",
      "group": "multimodal",
      "status": "completed",
      "applicable": true,
      "started_at": "2026-07-24T14:35:25Z",
      "finished_at": "2026-07-24T14:35:42Z",
      "duration_ms": 17000,
      "score": 0.94,
      "score_name": "model_confidence",
      "summary": "Выявлена аудиовизуальная несогласованность.",
      "raw_metrics": {},
      "candidate_findings": [],
      "warnings": [],
      "errors": []
    },
    {
      "analyzer_id": "synthetic_speech_analyzer",
      "analyzer_version": "0.1.0",
      "media_type": "video",
      "group": "audio_ml",
      "status": "error",
      "applicable": true,
      "started_at": "2026-07-24T14:35:25Z",
      "finished_at": "2026-07-24T14:35:27Z",
      "duration_ms": 2000,
      "score": null,
      "score_name": null,
      "summary": "Анализатор завершился ошибкой.",
      "raw_metrics": {},
      "candidate_findings": [],
      "warnings": [],
      "errors": [
        {
          "code": "analyzer_error",
          "category": "analyzer",
          "message": "Аудиоанализатор не выполнил проверку.",
          "retryable": true,
          "field": null,
          "analyzer_id": "synthetic_speech_analyzer",
          "safe_details": {}
        }
      ]
    }
  ],
  "findings": [
    {
      "finding_id": "finding_0001",
      "group": "multimodal",
      "type": "audio_video_desynchronization",
      "severity": "significant",
      "source_analyzer_id": "audio_video_sync_analyzer",
      "source_analyzer_version": "1.0.0",
      "description": "Выявлено устойчивое несоответствие аудиодорожки и движения губ.",
      "localization": {
        "type": "time_interval",
        "start_seconds": 12.1,
        "end_seconds": 19.5
      },
      "source_score": 0.94,
      "score_impact": 25,
      "critical_override_eligible": false,
      "correlation_group": "face_sync_segment_1",
      "evidence_refs": []
    }
  ],
  "completeness": {
    "status": "partial",
    "planned_analyzers": 2,
    "applicable_analyzers": 2,
    "completed_analyzers": 1,
    "failed_analyzers": 1,
    "timed_out_analyzers": 0,
    "skipped_analyzers": 0,
    "not_applicable_analyzers": 0,
    "coverage_ratio": 0.5,
    "missing_capabilities": ["synthetic_speech_detection"],
    "explanation": "Один применимый анализатор завершился ошибкой."
  },
  "risk_assessment": {
    "model_id": "score_model_v1",
    "model_version": "0.1.0",
    "score": 25,
    "score_based_level": "medium",
    "critical_override_applied": false,
    "critical_finding_ids": [],
    "final_level": "medium",
    "probability": null,
    "probability_method": null,
    "summary": "Выявлен значимый мультимодальный признак.",
    "explanation": "Оценка ограничена из-за сбоя аудиоанализатора.",
    "limitations": ["Анализ синтетической речи не выполнен."]
  },
  "recommendation": {
    "primary_action": "manual_review",
    "additional_actions": ["verify_source_via_independent_channel"],
    "text": "Рекомендуется ручная проверка и подтверждение источника по независимому каналу.",
    "requires_manual_review": true
  },
  "cleanup": {
    "status": "completed",
    "original_file_deleted": true,
    "intermediate_files_deleted": true,
    "quarantine_used": false,
    "finished_at": "2026-07-24T14:36:17Z",
    "errors": []
  },
  "warnings": ["Анализ выполнен частично."],
  "errors": []
}
```

---

## 15. Репозиторий результатов

### 15.1. Логический интерфейс

```python
class ResultRepository(Protocol):
    def save(self, result: AnalysisResult) -> None: ...
    def get(self, analysis_id: str) -> AnalysisResult | None: ...
    def exists(self, analysis_id: str) -> bool: ...
    def list_recent(self, limit: int) -> list[AnalysisResultSummary]: ...
```

Первая реализация:

```text
JsonFileResultRepository
```

### 15.2. Краткое представление результата `AnalysisResultSummary`

`list_recent` возвращает минимальную содержательную проекцию валидного
`AnalysisResult`:

```python
class AnalysisResultSummary(BaseModel):
    analysis_id: str
    created_at: datetime
    updated_at: datetime
    status: AnalysisStatus
    media_type: MediaType | None
    final_risk_level: RiskLevel | None
    completeness_status: CompletenessStatus
```

Все семь полей обязательны. `media_type` и `final_risk_level` допускают `null`,
но не имеют значения по умолчанию. Неизвестные поля запрещены. Временные
отметки принимаются только как timezone-aware UTC и сериализуются с суффиксом
`Z`.

Правила формирования:

- `analysis_id = result.analysis_id`;
- `created_at = result.created_at`;
- `updated_at = result.updated_at`;
- `status = result.status`;
- для `ValidatedFileDescriptor` используется `media_type = result.file.media_type`;
- для `InputFileDescriptor` используется `media_type = null`;
- `final_risk_level = result.risk_assessment.final_level`;
- `completeness_status = result.completeness.status`.

Тип медиа нельзя угадывать по имени, расширению или MIME. Риск и полнота не
рассчитываются повторно. Отсутствующий риск не заменяется на `low`, а `null` не
заменяется строкой `"unknown"`.

В summary не входят `schema_version`, `stage`, исходное имя файла, source и
external references, ошибки, findings, результаты и метрики анализаторов,
рекомендация, cleanup и другие поля полного результата.

### 15.3. Семантика `list_recent`

- `limit <= 0` отклоняется с `ValueError` до обращения к файловой системе;
- отсутствующий каталог результатов означает пустой список и не создаётся;
- рассматриваются только непосредственные дочерние обычные файлы без перехода
  по symlink;
- имя кандидата имеет точный lowercase-вид `<analysis_id>.json`, а
  `analysis_id` проходит те же проверки безопасного компонента пути, что и
  остальные операции repository;
- Windows reserved device names `CON`, `PRN`, `AUX`, `NUL`, `COM1..COM9` и
  `LPT1..LPT9` отклоняются регистронезависимо для итогового имени
  `<analysis_id>.json` на любой платформе;
- каталоги, symlink, временные файлы, `.JSON`, `.json.tmp`, неканонические JSON
  и вложенные файлы игнорируются;
- каждый кандидат читается как UTF-8 и полностью валидируется как
  `AnalysisResult` поддерживаемой версии;
- имя файла обязано быть равно `f"{payload.analysis_id}.json"`;
- invalid UTF-8/JSON, schema-invalid или domain-invalid payload,
  неподдерживаемая версия схемы и несовпадение ID пропускаются без placeholder,
  не расходуют limit и не мешают чтению остальных записей;
- повреждённые записи не удаляются, не исправляются и не раскрываются
  потребителю;
- невозможность перечислить существующий каталог или прочитать существующий
  обычный кандидат из-за `OSError` приводит к безопасному
  `ResultRepositoryError` без пути, имени записи, payload и исходного сообщения
  операционной системы;
- после фильтрации summary сортируются по `created_at` по убыванию, а при равном
  времени — по `analysis_id` лексикографически по возрастанию;
- `updated_at`, filesystem timestamps, processing timestamps и порядок обхода
  каталога не влияют на сортировку;
- limit применяется после полной фильтрации и сортировки;
- операция является read-only и не создаёт каталог, индекс или cache.

Адресное чтение также проверяет identity-инвариант:
`result.analysis_id == requested analysis_id`. Несовпадение считается
повреждённой записью, приводит к безопасному `CorruptedResultError` и не
изменяет файл.

### 15.4. Требования

- атомарная запись;
- полная повторная проверка схемы непосредственно на границе `save` до
  построения target path, сериализации сохраняемого payload и любых операций с
  файловой системой; сохраняется именно повторно провалидированный результат;
- отсутствие прямой записи из анализаторов;
- безопасное формирование пути;
- отсутствие исходного мультимедиа в результате;
- корректная обработка повреждённого JSON;
- возможность позднее заменить реализацию без изменения ядра.

`list_recent` может не выставляться во внешний API MVP, но интерфейс допускается для WebUI и будущей истории.

---

## 16. Контракт конфигурации

### 16.1. Общие правила

Корневая модель содержит:

```text
schema_version
server
access_channels
limits
allowed_formats
validation
temporary_storage
preprocessing
analyzers
risk_assessment
result
error_handling
logging
external_systems
```

Неизвестные поля должны вызывать ошибку или предупреждение согласно строгой политике Pydantic. Для MVP рекомендуется запрет неизвестных полей, чтобы опечатки не игнорировались.

`schema_version` и все перечисленные корневые секции обязательны. Вложенное
поле обязательно только при отсутствии у него `default` или `default_factory`.
Если для вложенного поля определено документированное безопасное значение по
умолчанию, его отсутствие означает применение этого значения.

### 16.2. Поля секций текущей схемы

Перечисленные ниже поля входят в текущую схему. Их обязательность определяется
правилом `default` / `default_factory` из раздела 16.1.

#### `server`

- `host`;
- `port`;
- `request_timeout_seconds`;
- `application_version`.

#### `access_channels.webui`

- `enabled`;
- `require_authentication`.

#### `access_channels.api`

- `enabled`;
- `require_token`;
- `token_env_var`.

`token_env_var` содержит имя переменной окружения и соответствует ASCII-шаблону
`^[A-Z_][A-Z0-9_]*$`. Поле не содержит сам секрет. Наличие указанной переменной
окружения и получение её значения являются отдельной runtime-задачей.

#### `limits`

- `max_file_size_mb.image`;
- `max_file_size_mb.audio`;
- `max_file_size_mb.video`;
- `max_parallel_tasks.image`;
- `max_parallel_tasks.audio`;
- `max_parallel_tasks.video`;
- `processing_timeout_seconds`.

#### `allowed_formats`

Для каждого типа:

- `extensions`;
- `mime_types`.

Для MVP значения этой секции должны соответствовать нормативному allowlist из
раздела 6.3: image — `jpg`, `jpeg`, `png`, `webp`; audio — `wav`, `mp3`, `flac`,
`m4a`; video — `mp4`, `mov`, `avi`, `mkv`. MIME-набор должен оставаться
согласованным с той же матрицей. Это не делает конкретные числовые лимиты или
настройки будущих модулей архитектурными константами.

#### `validation`

- `check_extension`;
- `check_mime_type`;
- `check_file_signature`;
- `reject_if_type_mismatch`;
- `calculate_sha256`;
- `safe_decode`.

#### `temporary_storage`

- `root_path`;
- `ttl_minutes`;
- `cleanup_retries`;
- `quarantine_enabled`;
- `quarantine_ttl_hours`.

#### `preprocessing`

Типизированные секции `image`, `audio`, `video` с параметрами, используемыми реально реализованными модулями.

#### `analyzers`

- `defaults.timeout_seconds`;
- `defaults.continue_on_error`;
- `image.enabled`;
- `audio.enabled`;
- `video.enabled`;
- `settings` — словарь настроек по `analyzer_id`.

#### `risk_assessment`

- `model_id`;
- `model_version`;
- `thresholds`;
- `severity_scores`;
- `critical_override.enabled`;
- `critical_override.allowed_finding_types`;
- `completeness.minimum_for_assessment`.

Пороговые значения и веса в примере не являются валидированными.

#### `result`

- `directory`;
- `atomic_write`;
- `include_raw_metrics`;
- `store_original_name`.

#### `error_handling`

- `continue_if_analyzer_fails`;
- `mark_partial_on_analyzer_failure`;
- `hide_internal_error_details`.

#### `logging`

- `level`;
- `jsonl_path`;
- `rotation_max_bytes`;
- `rotation_backup_count`.

#### `external_systems`

В MVP интеграции отключены. Секция может содержать только явно реализованные адаптеры.

### 16.3. Пример минимальной конфигурации

Значения являются **EXAMPLE**, кроме `allowed_formats`, который для MVP обязан
соответствовать нормативному allowlist раздела 6.3.

```yaml
schema_version: "1.0"

server:
  host: "127.0.0.1"
  port: 8080
  request_timeout_seconds: 600
  application_version: "0.1.0"

access_channels:
  webui:
    enabled: true
    require_authentication: true
  api:
    enabled: true
    require_token: true
    token_env_var: "MEDIA_ANALYZER_API_TOKEN"

limits:
  max_file_size_mb:
    image: 20
    audio: 50
    video: 200
  max_parallel_tasks:
    image: 4
    audio: 2
    video: 1
  processing_timeout_seconds: 600

allowed_formats:
  image:
    extensions: ["jpg", "jpeg", "png", "webp"]
    mime_types: ["image/jpeg", "image/png", "image/webp"]
  audio:
    extensions: ["wav", "mp3", "flac", "m4a"]
    mime_types: ["audio/wav", "audio/mpeg", "audio/flac", "audio/mp4"]
  video:
    extensions: ["mp4", "mov", "avi", "mkv"]
    mime_types: ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"]

validation:
  check_extension: true
  check_mime_type: true
  check_file_signature: true
  reject_if_type_mismatch: true
  calculate_sha256: true
  safe_decode: true

temporary_storage:
  root_path: "runtime/temp"
  ttl_minutes: 60
  cleanup_retries: 3
  quarantine_enabled: true
  quarantine_ttl_hours: 24

preprocessing:
  image:
    extract_metadata: true
    normalize_for_analysis: true
  audio:
    extract_metadata: true
    fragment_duration_seconds: 10
    build_spectrogram: true
  video:
    extract_metadata: true
    keyframe_interval_seconds: 2
    extract_audio_track: true

analyzers:
  defaults:
    timeout_seconds: 120
    continue_on_error: true
  image:
    enabled: []
  audio:
    enabled: []
  video:
    enabled: []
  settings: {}

risk_assessment:
  model_id: "score_model_v1"
  model_version: "0.1.0"
  thresholds:
    low_max: 29
    medium_max: 60
  severity_scores:
    weak: 5
    significant: 25
  critical_override:
    enabled: false
    allowed_finding_types: []
  completeness:
    minimum_for_assessment: 0.5

result:
  directory: "runtime/results"
  atomic_write: true
  include_raw_metrics: false
  store_original_name: true

error_handling:
  continue_if_analyzer_fails: true
  mark_partial_on_analyzer_failure: true
  hide_internal_error_details: true

logging:
  level: "INFO"
  jsonl_path: "runtime/logs/application.jsonl"
  rotation_max_bytes: 10485760
  rotation_backup_count: 5

external_systems:
  enabled: false
```

---

## 17. Логические операции внешнего API

### 17.1. Независимые от HTTP операции

API должен обеспечивать логические операции:

1. передать файл на анализ;
2. получить идентификатор задачи;
3. получить статус задачи;
4. получить итоговый результат;
5. получить безопасную ошибку.

Операции отмены, удаления результата, повторного анализа и истории не входят в обязательный MVP.

### 17.2. Модель выполнения API

Окончательный выбор между синхронным и асинхронным профилем имеет статус **OPEN**.

#### Профиль A — синхронный

- один запрос загрузки;
- соединение ожидает завершения;
- ответ содержит итоговый `AnalysisResult`;
- проще реализовать;
- плохо подходит для долгого видео и тайм-аутов.

#### Профиль B — асинхронный job-style

- загрузка возвращает `analysis_id` и `queued`;
- клиент получает статус отдельным запросом;
- итоговый результат запрашивается после завершения;
- лучше соответствует очереди, аудио и видео;
- требует хранения промежуточного состояния и дополнительных маршрутов.

**Рекомендация для универсального image/audio/video API: профиль B.**  
**Решение должно быть подтверждено владельцем проекта до реализации HTTP-маршрутов.**

### 17.3. Рекомендуемый асинхронный HTTP-профиль

Этот раздел имеет статус **CONDITIONAL** до подтверждения профиля B.

#### Создать анализ

```http
POST /api/v1/analyses
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

Поля multipart:

- `file` — обязательный файл;
- `source_context` — необязательная JSON-строка, валидируемая как `SourceContext`.

Успешный ответ:

```http
202 Accepted
```

```json
{
  "analysis_id": "01J3...",
  "status": "queued",
  "status_url": "/api/v1/analyses/01J3...",
  "result_url": "/api/v1/analyses/01J3.../result"
}
```

#### Получить статус

```http
GET /api/v1/analyses/{analysis_id}
Authorization: Bearer <token>
```

```json
{
  "analysis_id": "01J3...",
  "status": "running",
  "stage": "analysis",
  "created_at": "2026-07-24T14:35:22Z",
  "updated_at": "2026-07-24T14:35:42Z"
}
```

#### Получить результат

```http
GET /api/v1/analyses/{analysis_id}/result
Authorization: Bearer <token>
```

- `200 OK` — терминальный результат существует;
- `202 Accepted` — анализ ещё выполняется;
- `404 Not Found` — неизвестный идентификатор.

### 17.4. Синхронный HTTP-профиль

Статус **CONDITIONAL** до выбора профиля A.

```http
POST /api/v1/analyze
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

- `200 OK` — полный итоговый результат;
- `4xx` — отклонение запроса/файла;
- `5xx` — системный сбой.

### 17.5. Общие HTTP-коды

| Код | Применение |
|---:|---|
| `200` | Результат или статус успешно получен |
| `202` | Задача принята или ещё выполняется |
| `400` | Некорректный запрос |
| `401` | Требуется аутентификация |
| `403` | Доступ запрещён |
| `404` | Анализ не найден |
| `413` | Файл превышает лимит |
| `415` | Формат/тип не поддерживается |
| `422` | Структура параметров не прошла валидацию |
| `429` | Превышено ограничение запросов, если оно включено |
| `500` | Внутренняя ошибка |
| `503` | Сервис временно не способен принять задачу |

### 17.6. HTTP-ошибка

```json
{
  "error": {
    "code": "file_too_large",
    "category": "resource_limit",
    "message": "Размер файла превышает допустимый предел.",
    "retryable": false,
    "field": "file",
    "analyzer_id": null,
    "safe_details": {
      "max_size_bytes": 20971520
    }
  },
  "request_id": "req_..."
}
```

---

## 18. Контракт WebUI

### 18.1. Минимальный пользовательский поток

1. Пользователь проходит предусмотренную аутентификацию.
2. Открывает форму загрузки.
3. Выбирает один поддерживаемый файл.
4. Видит ограничения до отправки.
5. Отправляет файл.
6. Получает статус обработки.
7. Видит итоговый результат или безопасную ошибку.

### 18.2. Минимальная форма

- одно поле файла;
- кнопка запуска;
- сведения о допустимых типах и размерах;
- защита от повторной отправки во время загрузки;
- CSRF-защита, если используется cookie-сессия;
- отсутствие пути локального файла в логах.

### 18.3. Страница результата

Отображает ту же модель `AnalysisResult`, не вычисляя риск повторно:

- статус;
- тип и безопасное имя файла;
- уровень риска или отсутствие оценки;
- полноту;
- основные признаки;
- ограничения и ошибки;
- рекомендацию;
- предупреждение об отсутствии окончательной экспертизы;
- фактический статус очистки без раскрытия внутренних путей.

Точный дизайн экранов имеет статус **OPEN**.

---

## 19. Контракт технического журнала

### 19.1. Базовое событие

```json
{
  "timestamp": "2026-07-24T14:35:42Z",
  "level": "INFO",
  "event": "analyzer_finished",
  "analysis_id": "01J3...",
  "module": "analyzer_manager",
  "analyzer_id": "metadata_analyzer",
  "duration_ms": 81,
  "status": "completed",
  "error_type": null,
  "message": "Analyzer completed."
}
```

### 19.2. Канонические события MVP

```text
application_starting
configuration_loaded
analysis_registered
validation_started
validation_rejected
validation_completed
preprocessing_started
preprocessing_completed
analyzer_started
analyzer_finished
analyzer_failed
risk_assessment_completed
cleanup_started
cleanup_completed
cleanup_failed
result_saved
analysis_completed
analysis_partial
analysis_failed
```

Официальное имя стартового события — `application_starting`. Оно записывается
после успешных загрузки конфигурации, подготовки runtime, настройки
журналирования и создания FastAPI-приложения, непосредственно перед передачей
управления `uvicorn.run()`. Событие означает начало серверного запуска, но не
подтверждает привязку Uvicorn к порту или готовность приложения принимать
HTTP-запросы. HTTP readiness проверяется отдельно через `GET /health`.

JSONL whitelist и обязательные поля события остаются без изменений.

События не являются пользовательским аудитом действий и не заменяют отдельную модель аудита, если она понадобится позднее.

---

## 20. Контрактные тесты

Обязательные группы:

1. сериализация и десериализация каждой модели;
2. запрет неизвестных значений enum;
3. проверка обязательных полей;
4. отклонение отрицательных размеров и длительностей;
5. проверка временных интервалов `start <= end`;
6. проверка нормализованных координат `0..1`;
7. запрет probability без probability_method;
8. запрет critical override без finding IDs;
9. запрет `low` при `completeness=insufficient`;
10. терминальные правила `completed/partial/rejected/failed`;
11. атомарность репозитория;
12. безопасная структура ошибок;
13. конфигурация с неизвестным полем;
14. отсутствие секретов в сериализованном результате;
15. совместимость результатов текущей минорной версии.

---

## 21. Управление изменениями контракта

Перед изменением поля или интерфейса необходимо:

1. определить владельца области;
2. проверить влияние на `PROJECT.md` и `ROADMAP.md`;
3. определить обратную совместимость;
4. изменить модели и тесты;
5. обновить примеры;
6. при необходимости повысить `schema_version`;
7. записать принятое изменение в `CHANGELOG.md`.

Запрещено:

- менять смысл поля без версии;
- использовать одно поле для двух разных понятий;
- переименовывать перечисления только ради косметики после появления потребителей;
- оставлять код и документацию с разными enum;
- добавлять обязательное поле без миграционного решения.

---

## 22. Открытые контрактные решения

До соответствующих этапов разработки требуют подтверждения:

1. синхронный или асинхронный HTTP-профиль;
2. окончательные HTTP-маршруты;
3. механизм аутентификации WebUI;
4. срок жизни и управление API-токенами после MVP;
5. точный набор обязательных анализаторов профиля;
6. алгоритм полноты и минимальное покрытие;
7. веса, пороги и корреляция признаков;
8. разрешённые critical-признаки;
9. итоговая JSON Schema как отдельный машинный файл;
10. срок хранения результатов;
11. операции отмены, удаления и повторного анализа;
12. история анализов и пагинация;
13. интеграционные события SIEM/DLP/SOAR;
14. политика передачи персональных данных источника.

ИИ-агент обязан остановиться на границе открытого решения, предложить варианты и не выдавать предположение за утверждённый контракт.

---

## 23. Краткая карта контрактов

```text
WebUI / API
→ InputFileDescriptor + SourceContext
→ temporary owned source
→ ValidationResult
→ Stage3Outcome
  | accepted: Stage3Accepted + opaque owned-source handoff
  | rejected / failed: Stage3Terminal + factual pre-handoff cleanup outcome
→ AnalysisContext
→ PreparedMedia
→ AnalyzerRequest
→ AnalyzerResult[]
→ Finding[]
→ AnalysisCompleteness
→ RiskAssessment
→ Recommendation
→ CleanupResult
→ AnalysisResult
→ ResultRepository
```

Ключевые запреты:

- `AnalyzerResult.score` не равен общей вероятности;
- `FindingSeverity` не равна `RiskLevel`;
- отклонённый файл не получает риск;
- неполный анализ не маскируется как полноценный;
- внутренний путь не выходит наружу;
- результат и журнал являются разными контрактами.
