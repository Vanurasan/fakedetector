# ROADMAP.md

> Живая дорожная карта разработки и единственный источник истины о текущем состоянии реализации.
>
> Версия документа: **1.0**  
> Дата фиксации: **2026-07-24**  
> Статус документа: **ACTIVE**

---

## 0. Назначение документа

`ROADMAP.md` одновременно отвечает на два вопроса:

1. что уже выполнено;
2. что необходимо делать дальше.

Отдельный `CURRENT_STATE.md` не используется, чтобы не дублировать статусы.

Документ содержит:

- текущий этап;
- ближайшее действие;
- блокеры и открытые решения;
- этапы разработки;
- чек-листы;
- критерии завершения;
- обязательные проверки;
- границу MVP и работ после MVP.

Документ не повторяет архитектуру и контракты. При необходимости он ссылается на `PROJECT.md` и `CONTRACTS.md`.

---

## 1. Правила ведения дорожной карты

### 1.1. Статусы

Используются только следующие статусы:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
DONE
```

Дополнительный статус для группы работ:

```text
AFTER_MVP
```

Смысл:

| Статус | Смысл |
|---|---|
| `NOT_STARTED` | Работа ещё не начата |
| `IN_PROGRESS` | Работа ведётся сейчас |
| `BLOCKED` | Продолжение невозможно без решения или внешнего условия |
| `DONE` | Все критерии завершения выполнены и проверены |
| `AFTER_MVP` | Работа сознательно отложена за границу MVP |

### 1.2. Правило единственного текущего этапа

В нормальном режиме только один этап имеет статус `IN_PROGRESS`.

Параллельная работа разрешается только когда:

- задачи не меняют одни и те же контракты;
- зависимости между ними явно отсутствуют;
- это не мешает получить проверяемый результат этапа.

### 1.3. Когда этап считается завершённым

Этап переводится в `DONE` только если:

- выполнены все обязательные задачи;
- выполнены критерии завершения;
- проходят связанные тесты;
- код соответствует `PROJECT.md` и `CONTRACTS.md`;
- обновлены чек-листы;
- принятое проектное изменение внесено в `CHANGELOG.md`, если оно было;
- отсутствуют скрытые заглушки, выданные за готовую функцию.

### 1.4. Как обновлять файл

После каждой законченной задачи агент обязан:

1. отметить выполненный пункт `[x]`;
2. обновить поле «Ближайшее действие»;
3. при завершении этапа обновить статус;
4. указать новые блокеры;
5. не переписывать описание уже выполненного этапа без причины;
6. не переносить историю изменений из `CHANGELOG.md` в дорожную карту.

### 1.5. Открытые решения

Если задача упирается в `OPEN`-решение:

- `BLOCKED` применяется только при невозможности продолжить без решения
  владельца, меняющего архитектуру, контракт или объём задачи; наличие открытого
  решения само по себе не останавливает независимую разрешённую работу;
- в разделе «Блокеры и решения» фиксируется конкретный вопрос;
- агент предлагает варианты и последствия;
- после выбора обновляется владелец области (`PROJECT.md` или `CONTRACTS.md`);
- изменение вносится в `CHANGELOG.md`;
- работа продолжается.

---

## 2. Текущее состояние

```text
Общий статус: Stages 1–11 — DONE / CLOSED
Последний закрытый этап: Stage 11 — Post-MVP Normalization & Hardening
Статус Stage 10: DONE / CLOSED
Текущий этап: Stage 12 — Analyzer Expansion, Licensing & Product Validation
Статус Stage 11: DONE / CLOSED
Статус Macros 0–8 Stage 11: DONE / owner accepted
Последний завершённый Macro: Stage 12 Macro 0 — Stage Definition, Licensing & Third-Party Policy (DONE)
Статус Stage 12: IN_PROGRESS
Текущий Macro: Macro 1 — Forensic Preprocessing Foundations (IN_PROGRESS; M1-A–M1-D DONE)
Статус Macro 0: DONE
Решение владельца PROJECT_LICENSE: CLOSED — Apache-2.0
Последний завершённый increment: M1-D — Source-Precision Audio & Numeric STFT Foundations (DONE)
Следующее действие: M1-E — bounded timing
Следующий Macro: Macro 2 — Image Analyzer Expansion — Wave 1 (NOT_STARTED; после закрытия Macro 1)
Будущие работы: Stage 12 Macros 2–10 — NOT_STARTED; Stage 13+ ML — AFTER_MVP / NOT_STARTED
Критические блокеры: отсутствуют
Реализация программы: Этапы 1–11 завершены; MVP 0.1.0 DONE / CLOSED; финальная проверка Stage 11 — PASS
Документационная база: сформирована
```

### 2.1. Выполненная подготовка

- [x] подготовлен единый `PROJECT.md`;
- [x] подготовлен `CONTRACTS.md`;
- [x] подготовлена компактная живая дорожная карта;
- [x] подготовлены правила ведения `CHANGELOG.md`;
- [x] исключено отдельное дублирующее описание current state;
- [x] технологический стек первой версии зафиксирован;
- [x] архитектурные инварианты зафиксированы;
- [x] разделены серьёзность признака, риск и полнота анализа;
- [x] итоговая псевдовероятность запрещена без валидированного метода.

### 2.2. Ближайшая задача

Stage 12 явно разрешён владельцем 2026-09-20. Решение о лицензии закрыто:
в Pass 2 выбран Apache-2.0 (`PROJECT.md` §21.7); сведения о происхождении
и уведомлениях находятся в `REFERENCES.md`. Оформление лицензии и изменения
поставки проверены. После добавления `LICENSE` в Git владельцем повторные
release-package/release-verification тесты прошли: **47 passed**.
Macro 0 — `DONE`. Macro 1 — Forensic Preprocessing Foundations — `IN_PROGRESS`.
M1-A (contracts/limits), M1-B (original image/JPEG), M1-C (deterministic image
residual kernels) и M1-D (audio precision/STFT) завершены. Следующий отдельный
implementation increment — **M1-E: bounded timing**. Решения G1–G5 закрыты; в M1-D новые
runtime dependencies, публичные схемы и конфигурационные поля не вводились.

---

## 3. Карта этапов

| № | Этап | Статус | Главный результат |
|---:|---|---|---|
| 0 | Документационная база | DONE | Синхронизированные источники истины |
| 1 | Каркас проекта и конфигурация | DONE | Запускаемое приложение |
| 2 | Доменные модели и репозитории | DONE | Типизированные модели контрактов |
| 3 | Приём и первичная проверка файлов | DONE | Безопасно принятый или отклонённый файл |
| 4 | Жизненный цикл задачи, хранение и маршрутизация | DONE | Управляемая задача с очисткой |
| 5 | Предварительная обработка и каркас анализаторов | DONE | Единый запуск анализаторов |
| 6 | Базовые анализаторы и формирование признаков | DONE | Реальные нормализованные признаки |
| 7 | Полнота, риск и рекомендации | DONE | Объяснимый итог без псевдовероятности |
| 8 | JSON, API и WebUI | DONE | Реализация и независимые аудиты завершены; этап закрыт |
| 9 | Надёжность, безопасность и сквозные тесты | DONE | Macro 1–4 и remediation committed; independent post-remediation audit — PASS, findings закрыты |
| 10 | Сборка и демонстрация MVP | DONE / CLOSED | Macro 1–3 DONE / owner accepted; independent post-remediation audit — PASS; S10-A01–S10-A04 CLOSED |
| 11 | Post-MVP Normalization & Hardening | DONE / CLOSED | Macros 0–8 DONE / owner accepted; финальная проверка и strict certification — PASS; actionable findings 0 |
| 12 | Analyzer Expansion, Licensing & Product Validation | IN_PROGRESS | Macro 0 DONE; Macro 1 IN_PROGRESS, M1-A–M1-D DONE; лицензия проекта Apache-2.0 |
| 13+ | Дальнейшие расширения | AFTER_MVP / NOT_STARTED | ML, интеграции, история, масштабирование; отдельное решение владельца |

---

# Этап 0. Документационная база — DONE

## Цель

Создать минимальный согласованный комплект проектной памяти без повторного пересказа одной информации в нескольких файлах.

## Выполнено

- [x] `PROJECT.md` назначен владельцем архитектуры, границ и стека;
- [x] `CONTRACTS.md` назначен владельцем интерфейсов и моделей данных;
- [x] `ROADMAP.md` назначен владельцем плана и текущего состояния;
- [x] `CHANGELOG.md` назначен владельцем истории изменений;
- [x] старые MD-файлы признаны архивными;
- [x] определён приоритет источников истины;
- [x] сформированы правила работы ИИ-агента.

## Критерий завершения

Комплект можно передать новому агенту без загрузки старой курсовой и архивных файлов.

---

# Этап 1. Каркас проекта и конфигурация — DONE

Дата завершения: **2026-08-01**.

## Цель

Создать минимальное Python-приложение, которое воспроизводимо устанавливается, запускается и проверяет конфигурацию.

## Обязательные задачи

### Структура проекта

- [x] создать Git-репозиторий;
- [x] добавить `.gitignore` для `.venv`, `.env`, `runtime`, моделей и кэшей;
- [x] зафиксировать Python 3.12 в `.python-version`;
- [x] инициализировать проект через `uv`;
- [x] создать `pyproject.toml` и `uv.lock`;
- [x] создать пакет приложения;
- [x] создать каталоги `src`, `tests`;
- [x] создать каталог `config` для примера конфигурации;
- [x] обеспечить автоматическое создание необходимых каталогов `runtime` при запуске приложения;
- [x] не хранить содержимое `runtime` в Git.

### Инструменты качества

- [x] подключить Ruff;
- [x] подключить mypy;
- [x] подключить pytest;
- [x] подключить pytest-cov;
- [x] подключить pre-commit после появления базовых команд;
- [x] добавить единые команды запуска проверок.

### Конфигурация

- [x] реализовать Pydantic-модели корневой конфигурации;
- [x] запретить неизвестные поля;
- [x] загрузить YAML;
- [x] объединить YAML с переменными окружения;
- [x] проверить обязательные секции;
- [x] реализовать безопасную ошибку некорректной конфигурации;
- [x] создать канонический `config.example.yaml` текущей схемы; настройки будущих модулей явно обозначить как неактивные или `EXAMPLE`;
- [x] не включать секреты в пример;
- [x] подключить загрузку и валидацию конфигурации к точке запуска приложения.

### Запуск

- [x] создать фабрику приложения FastAPI;
- [x] создать Uvicorn-команду запуска;
- [x] добавить служебный health endpoint без бизнес-логики;
- [x] добавить стартовое журналирование без секретов;
- [x] устранить BLOCKER небезопасной инициализации логирования: валидировать
  стандартные уровни до runtime и безопасно завершать CLI при ошибке открытия
  собственного log handler;
- [x] реализовать ротацию JSONL-логов.

## Обязательные тесты

- [x] корректная конфигурация загружается;
- [x] неизвестное поле отклоняется;
- [x] отсутствующий обязательный параметр отклоняется;
- [x] настройка может быть переопределена переменной окружения;
- [x] пример конфигурации не содержит буквальных значений секретов; используются только имена переменных окружения, а локальные secret/config-файлы исключены из Git.
- [x] приложение создаётся в тесте;
- [x] health endpoint возвращает успешный ответ;
- [x] Ruff и mypy проходят на каркасе.

## Findings финального аудита

Статус финального аудита: **COMPLETED**. Все первоначальные findings закрыты.

- [x] устранить несоответствие по `pydantic-settings`: владелец явно утвердил
  PyYAML + Pydantic v2 `BaseModel` + собственный env-overlay для MVP,
  документация синхронизирована с фактической реализацией;
- [x] исправить критерий запуска через официальный console script
  `uv run fakedetector --config config/config.example.yaml` и добавить целевую
  проверку `uv run poe server-smoke` с ограниченным запуском настоящего сервера;
- [x] синхронизировать naming startup events: `application_starting` является
  официальным событием непосредственно перед `uvicorn.run()` и не означает
  HTTP readiness, которая проверяется отдельно через `/health`;
- [x] добавить недостающие regression-тесты findings аудита: pytest запускает
  установленный `fakedetector --help` без runtime pipeline и параметризованно
  проверяет отсутствие каждого обязательного top-level поля `AppConfig`;
- [x] добавить validation для `token_env_var` как ASCII environment identifier
  по шаблону `^[A-Z_][A-Z0-9_]*$`.

### Повторный финальный аудит

Первоначальный результат повторного аудита: **BLOCKER: 0; MAJOR: 1; MINOR: 0**.
Все предыдущие findings были закрыты. Единственный новый finding: публичный
`README.md` был рассинхронизирован с реализацией и ошибочно описывал проект как
находящийся только на стадии проектирования, несмотря на готовый минимальный
запускаемый каркас.

- [x] устранить finding синхронизацией `README.md` с фактическим состоянием
  минимального запускаемого каркаса Этапа 1.

Статус повторного финального аудита: **COMPLETED / PASS**.

Итоговый результат: **BLOCKER: 0; MAJOR: 0; MINOR: 0**. Все первоначальные
findings и новый finding по `README.md` закрыты. Контрольная проверка после
синхронизации README прошла: полный quality pipeline и real-server smoke
завершились успешно, официальный CLI подтверждён, 106 тестов прошли, итоговое
branch coverage — 97%. Рабочее дерево Git после проверки осталось чистым.

## Критерий завершения

```text
uv sync
uv run pytest
uv run ruff check .
uv run mypy src
uv run fakedetector --config config/config.example.yaml
uv run poe server-smoke
```

выполняются без критических ошибок, приложение запускается и валидирует конфигурацию.

Критерий завершения выполнен и подтверждён 2026-08-01.

## Не делать на этом этапе

- анализ файлов;
- ML-модели;
- базу данных;
- внешний брокер задач;
- полноценную аутентификацию;
- сложный WebUI.

---

# Этап 2. Доменные модели и репозитории — DONE

Дата завершения: **2026-08-12**.

## Цель

Перенести канонические контракты в типизированный код до реализации потоков обработки.

## Обязательные задачи

### Доменные модели

- [x] реализовать enum из `CONTRACTS.md`;
- [x] реализовать `SourceContext`;
- [x] реализовать файловые дескрипторы;
  - [x] реализовать `InputFileDescriptor`;
  - [x] реализовать `ValidatedFileDescriptor` с техническими параметрами;
- [x] реализовать `ValidationResult`;
- [x] реализовать `AnalyzerResult`;
- [x] реализовать `Finding` и виды локализации;
- [x] реализовать `AnalysisCompleteness`;
- [x] реализовать `RiskAssessment`;
- [x] реализовать `Recommendation`;
- [x] реализовать `CleanupResult`;
- [x] реализовать итоговый `AnalysisResult`;
- [x] реализовать `AnalysisResultSummary`;
- [x] зафиксировать `schema_version`.

### Репозитории

- [x] определить протокол `ResultRepository`;
  - [x] определить типизированные операции `save`, `get`, `exists`;
  - [x] определить `list_recent` после фиксации полей `AnalysisResultSummary` и
    контрактного признака сортировки;
- [x] реализовать `JsonFileResultRepository`;
  - [x] реализовать файловый core для `save`, `get`, `exists`;
  - [x] реализовать `list_recent` после устранения контрактной неоднозначности;
- [x] реализовать атомарную запись;
- [x] реализовать безопасное чтение;
- [x] обработать повреждённый JSON;
- [x] в текущем production-коде сохранение `AnalysisResult` выполняется только
  через `ResultRepository`; обходные механизмы прямой записи отсутствуют.
  Соблюдение границы будущими модулями контролируется архитектурными тестами и
  code review на последующих этапах.

### Идентификаторы и время

- [x] реализовать генератор непрозрачного `analysis_id`;
- [x] реализовать единый UTC clock provider для тестируемости;
- [x] исключить персональные данные из идентификатора.

## Обязательные тесты

- [x] сериализация/десериализация каждой модели;
- [x] неверные enum отклоняются;
- [x] некорректная локализация отклоняется;
- [x] probability без метода отклоняется;
- [x] critical override без finding IDs отклоняется;
- [x] правила терминальных статусов проверяются;
- [x] результат записывается атомарно;
- [x] путь строится только по `analysis_id`.

## Findings финального аудита

- первоначальный аудит: **FAIL**;
- [x] `S2-AUD-001` — закрыт;
- [x] `S2-AUD-002` — закрыт;
- [x] `S2-AUD-003` — закрыт;
- [x] `S2-AUD-004` — закрыт;
- [x] `S2-AUD-005` — закрыт;
- repeat audit после первого remediation: **FAIL**;
- [x] `S2-AUD-001-R1` — закрыт;
- [x] `S2-AUD-003-R1` — закрыт;
- контрольный финальный аудит: **PASS**;
- итог: **BLOCKER: 0; MAJOR: 0; MINOR: 0**.

Real-symlink integration test остаётся platform-dependent skip; deterministic
tests для `get`, `exists` и `list_recent` проходят. Hardening против concurrent
symlink substitution / TOCTOU и no-follow остаётся задачей безопасности Этапа 9.

## Критерий завершения

Все доменные модели и репозиторий существуют в коде, имеют контрактные тесты и не зависят от FastAPI.

Критерий завершения выполнен и подтверждён контрольным финальным аудитом
2026-08-12.

## Не делать на этом этапе

- реальные анализаторы;
- расчёт риска;
- HTTP-маршруты анализа;
- история и SQLite.

---

# Этап 3. Безопасный приём, временное владение и первичная проверка файлов — DONE

## Цель

Реализовать законченный safe intake use case: принять недоверенный поток в
изолированный workspace, подтвердить поддерживаемый тип и безопасную читаемость,
а затем передать accepted input следующему lifecycle вместе с контролируемым
ownership либо завершить `rejected`/`failed` с фактическим cleanup.

## Обязательные задачи

### Increment 1 — Controlled intake and temporary ownership — DONE

- [x] определить прикладной сервис приёма файла;
- [x] определить adapter-neutral потоковый вход, общий для будущих WebUI и API;
- [x] создать `analysis_id` и `SourceContext`;
- [x] зафиксировать registration/received time;
- [x] создать изолированный `runtime/temp/<analysis_id>` для исходного input;
- [x] применить минимальную безопасную политику создания/доступа к каталогу без
  преждевременного Stage 9 TOCTOU/no-follow hardening;
- [x] использовать в системном пути и workspace только проверенный системный
  `analysis_id`;
- [x] создать внутреннее имя input без `original_name`, extension, MIME и
  external identifiers;
- [x] потоково читать и записывать input порциями без полной загрузки в память;
- [x] до определения `MediaType` применять hard limit, равный максимальному из
  настроенных per-media limits;
- [x] измерять фактический размер независимо от `Content-Length`;
- [x] рассчитывать SHA-256 в том же intake pass;
- [x] предоставить validator непрозрачный controlled-source handle;
- [x] определить минимальную ownership-семантику без универсального storage
  framework и без полного `AnalysisContext`;
- [x] очищать принадлежащий Stage 3 input/workspace при системном исключении до
  handoff.

После инкремента FakeDetector принимает недоверенный поток, ограничивает его
объём, безопасно размещает в isolated workspace, измеряет размер, рассчитывает
SHA-256 и удаляет данные при системном сбое до handoff.

### Increment 2 — Primary validation — DONE

- [x] проверка пустого файла;
- [x] обязательное наличие расширения с семантикой `file`/`file.`/`.mp4` →
  `missing_extension`;
- [x] нормализация обычного расширения без ведущей точки в lowercase;
- [x] проверка extension по утверждённому MVP allowlist;
- [x] принять отсутствие declared MIME без rejection;
- [x] определить фактический MIME независимо от declared MIME;
- [x] проверить обнаруженный MIME по MVP allowlist;
- [x] проверка фактической сигнатуры;
- [x] проверка согласованности extension, detected MIME, сигнатуры/контейнера и
  `MediaType` по нормативной матрице;
- [x] проверка согласованности declared и detected MIME только при наличии
  declared MIME;
- [x] после определения `MediaType` применить соответствующий per-media limit к
  фактически измеренному размеру;
- [x] полностью безопасно декодировать image;
- [x] controlled probe/open и bounded decode audio/video выполнять с timeout;
- [x] получить обязательные технические параметры без вымышленных значений;
- [x] не отклонять файл только из-за отсутствия естественно необязательных
  metadata или nullable технических параметров;
- [x] определение `MediaType`;
- [x] формирование `ValidationResult`.

После инкремента FakeDetector определяет, является ли вход поддерживаемым и
безопасно читаемым image/audio/video, и формирует `ValidatedFileDescriptor` либо
нормативный validation rejection.

### Increment 3 — Integrated Stage 3 lifecycle — DONE

- [x] WebUI/API adapters передают transport data одному intake service и не
  владеют validation business logic;
- [x] при accepted логически передавать `ValidatedFileDescriptor` вместе с
  opaque owned-source/lease/controlled handle;
- [x] после успешного handoff передавать ownership Stage 4 и не удалять accepted
  input в Stage 3;
- [x] если handoff не состоялся, сохранять ownership в Stage 3 и выполнять
  cleanup;
- [x] ожидаемые validation failures завершать как `rejected` со стабильным
  машинным кодом;
- [x] ошибки workspace, записи и неожиданные системные исключения завершать как
  `failed`, не маскируя их как invalid input;
- [x] при `rejected` не запускать анализаторы, не создавать findings и
  `RiskLevel`, сохранять completeness=`not_assessed`;
- [x] при `rejected` и `failed` до handoff выполнять cleanup и отражать его
  фактический outcome;
- [x] возвращать безопасные сообщения без внутренних путей;
- [x] не создавать preprocessing-артефакты Stage 5.

После инкремента FakeDetector выполняет весь Stage 3 от входного потока до
accepted ownership handoff либо controlled `rejected`/`failed` outcome с
cleanup.

## Обязательные тесты

- [x] все форматы утверждённого image/audio/video MVP allowlist проходят при
  согласованной сигнатуре и safe read;
- [x] отсутствие declared Content-Type допустимо;
- [x] отсутствие необязательных metadata допустимо;
- [x] `file`, `file.` и `.mp4` отклоняются с `missing_extension`;
- [x] расширение нормализуется в lowercase;
- [x] архив отклоняется;
- [x] офисный документ отклоняется;
- [x] переименованный файл с неверной сигнатурой отклоняется;
- [x] declared MIME mismatch отклоняется, а отсутствующий declared MIME не
  мешает проверке;
- [x] превышение pre-detection hard limit прекращает intake;
- [x] превышение per-media limit после определения типа отклоняется;
- [x] недоверенный `Content-Length` не определяет фактический размер;
- [x] повреждённый файл отклоняется;
- [x] image проходит полный decode, audio/video — controlled probe и bounded
  decode с timeout;
- [x] SHA-256 стабилен;
- [x] разные `analysis_id` получают изолированные каталоги;
- [x] path traversal и `original_name` не влияют на путь или внутреннее имя
  input;
- [x] rejection и exception до handoff очищают input/workspace;
- [x] cleanup failure отражается фактически;
- [x] accepted handoff передаёт ownership и не удаляется Stage 3;
- [x] несостоявшийся handoff сохраняет ownership и запускает cleanup;
- [x] отклонение не создаёт analyzers, findings или риск `low`/`high`;
- [x] internal intake failure формирует `failed`, а validation failure —
  `rejected`.

## Критерий завершения

Stage 3 возвращает либо accepted handoff с `ValidatedFileDescriptor` и
контролируемым владением исходным временным файлом, либо terminal
`rejected`/`failed` с фактическим результатом cleanup; анализаторы не запускаются.

## Финальный аудит Stage 3

Статус финального независимого аудита: **PASS**.

- [x] `S3-AUD-001`: канонические relational invariants `ValidationResult`
  независимо перепроверены, включая четыре противоречивые комбинации;
- [x] `S3-AUD-002`: structural Matroska/WebM classification независимо
  перепроверена на реальных MKV/WebM и malformed/contaminated EBML;
- [x] `S3-AUD-003`: controlled `cwd`, `shell=False` и `stdin=DEVNULL` для всех
  FFmpeg/ffprobe runtime и validation вызовов независимо перепроверены;
- [x] `S3-RERUN-001`: разрешённые и запрещённые relational states
  `Stage3Terminal` независимо воспроизведены;
- [x] `S3-RERUN-002`: ffprobe output overflow и stdout infrastructure failure
  независимо разделены и проверены вместе с kill/reap/close/join и integrated
  terminal `failed` outcome.

Все completion criteria Stage 3 и полный quality barrier прошли. Stage 3 закрыт
со статусом `DONE`. Принятые Stage 4 contracts не меняют фактически завершённый
Stage 3 lifecycle.

---

# Этап 4. Жизненный цикл задачи, хранение и маршрутизация — DONE

## Цель

Принять ownership успешно проверенного controlled source и создать управляемую
задачу дальнейшего анализа с внутренней очередью, маршрутизацией, состояниями и
полной post-handoff очисткой.

## Обязательные задачи

### Documentation prerequisite — Lifecycle and cleanup contract — DONE

Ветка: `docs/stage4-lifecycle-cleanup-contract`.

- [x] зафиксировать receiver/handoff commit и rollback provisional state;
- [x] уточнить canonical `MediaType` routing и internal missing-binding failure;
- [x] определить in-process `TaskRegistry`, `AnalysisContext` и internal
  `AnalysisTask` boundary;
- [x] отделить Stage 4 task state от `AnalysisResult` и `ResultRepository` Stage 8;
- [x] принять Option A cleanup retry/TTL/quarantine policy и active-task exclusion;
- [x] определить deterministic sweep triggers и conservative entry handling;
- [x] декомпозировать Stage 4 на три functional increments и отдельный final audit.

Документальная prerequisite не является functional increment: production code,
tests, config, dependencies, external schema `1.0`, Stage 2 models/enums и Stage 3
contract shape/redesign не изменены.

### Stage 4 Increment 1 — Managed accepted task lifecycle — DONE

Ветка: `feat/stage4-managed-task-lifecycle`.

Functional vertical slice:

```text
Stage3Accepted
→ AnalysisContext / AnalysisTask
→ state machine
→ local registry
→ canonical router
→ deterministic FIFO queue/run_next
→ test executor
→ immediate post-handoff cleanup
→ terminal task snapshot
```

- [x] подтвердить identity и factual fields `Stage3Accepted`;
- [x] создать `AnalysisContext` и internal `AnalysisTask` без ownership capability;
- [x] реализовать допустимые state transitions и запрет terminal requeue/restart;
- [x] реализовать authoritative local typed in-process `TaskRegistry`;
- [x] реализовать canonical routes `IMAGE`, `AUDIO`, `VIDEO` и safe
  internal/infrastructure failure при отсутствующем binding;
- [x] реализовать deterministic FIFO enqueue и явный `run_next`;
- [x] фиксировать `queued_at` только после successful enqueue;
- [x] выполнить logical receiver commit только после registry reservation, route
  resolution и successful enqueue, откатывая provisional state при исключении;
- [x] выполнить test executor и immediate post-handoff cleanup;
- [x] вернуть factual terminal task snapshot без `AnalysisResult` и
  `ResultRepository.save()`.

Исключено из Increment 1: concurrency workers, queue pressure, retries, TTL,
quarantine, preprocessing, analyzers и persistence `AnalysisResult`.

### Stage 4 Increment 2 — Bounded local execution lifecycle — DONE

Ветка: `feat/stage4-bounded-local-execution`.

- [x] реализовать bounded per-media queues;
- [x] реализовать workers и настроенные per-media concurrency limits;
- [x] обеспечить exactly-once claim;
- [x] определить и проверить overflow behavior;
- [x] реализовать start/stop/drain и safe shutdown;
- [x] корректно обработать pending/running accepted tasks при shutdown;
- [x] изолировать caller/event loop от тяжёлого выполнения.

### Stage 4 Increment 3 — Cleanup recovery — DONE

Ветка: `feat/stage4-cleanup-recovery`.

- [x] реализовать initial cleanup и configured immediate retries;
- [x] фиксировать factual partial/failed cleanup без изменения primary status;
- [x] реализовать optional quarantine после retry exhaustion;
- [x] реализовать workspace TTL с обязательным исключением active/non-terminal
  `TaskRegistry` entries;
- [x] реализовать quarantine TTL и повторные cleanup attempts без durable metadata;
- [x] интегрировать sweep при scheduler startup, после terminal task cleanup и при
  graceful shutdown;
- [x] не оставлять abandoned ordinary workspace и не заявлять ложный cleanup
  success для symlink/suspicious/unknown entries.

### Stage 4 final audit remediation — DONE

- [x] `S4-AUD-001` independently verified closed: factual ownership state
  quarantined `AcceptedSource` синхронизирован с direct cleanup и janitor TTL
  recovery;
- [x] `S4-RERUN-001`: исключить stranded active task при сбое terminal
  `Clock.now()` после physical cleanup;
- [x] `S4-RERUN2-001`: сохранить strict UTC/chronology validation и pre-mutation
  defense-in-depth для authoritative lifecycle timestamps;
- [x] `S4-RERUN3-001`: реализовать shared `AuthoritativeLifecycleClock`, explicit
  internal `TerminalSettlement`, post-cleanup `finished_at` и recovery
  `FACT_READY` без повторного physical cleanup; локально проверено полным quality
  barrier: 989 passed, 2 skipped, coverage 91%;
- [x] `S4-RERUN4-001`: вынести janitor/filesystem callbacks из global
  `TaskRegistry` lock, сохранив atomic cleanup claim, same-analysis registration
  exclusion, exactly-one cleanup owner и exception-safe retry; локально проверено
  полным quality barrier: 994 passed, 2 skipped, coverage 91%;
- [x] independent final audit rerun5 завершён со статусом `PASS`: все historical
  findings независимо подтверждены как `CLOSED`, новых production defects и
  post-architecture findings не обнаружено; 994 passed, 2 skipped, coverage 91%,
  quality barrier полностью green, repository integrity confirmed.

## Обязательные тесты

- [x] валидные переходы статусов;
- [x] недопустимые переходы отклоняются;
- [x] ownership accepted input принимается ровно один раз;
- [x] enqueue failure откатывает provisional registry state и не подтверждает handoff;
- [x] missing canonical route binding приводит к receiver exception и Stage 3 cleanup, а не `rejected`;
- [x] `queued_at` отсутствует до successful enqueue;
- [x] cleanup accepted input и будущих артефактов выполняется после успеха;
- [x] post-handoff cleanup выполняется после исключения;
- [x] ошибка удаления отражается;
- [x] retry/quarantine/TTL policy применяется только при сбое cleanup;
- [x] active/non-terminal task исключается из TTL cleanup независимо от mtime;
- [x] sweep triggers и quarantine TTL/retry детерминированы;
- [x] ограничения параллельности соблюдаются;
- [x] Stage 4 не создаёт `AnalysisResult` и не вызывает `ResultRepository.save()`.

## Критерий завершения

Тестовая задача принимает ownership проверенного source, проходит регистрацию
дальнейшего lifecycle, очередь, маршрутизацию и post-handoff очистку, а её
живое состояние правдиво доступно через in-process `TaskRegistry`. Cleanup
recovery не очищает live tasks, не оставляет ordinary abandoned workspace и не
выдаёт quarantine за persistent repository. Durable restart recovery и
`AnalysisResult` persistence не входят в Stage 4.

## Финальный аудит Stage 4

Все три functional increments и completion criteria Stage 4 подтверждены
independent final audit rerun5 со статусом `PASS`. Findings `S4-AUD-001`,
`S4-RERUN-001`, `S4-RERUN2-001`, `S4-RERUN3-001` и `S4-RERUN4-001` независимо
подтверждены как `CLOSED`; новых production defects и post-architecture findings
не обнаружено. Финальный quality barrier полностью green: 994 passed, 2 skipped,
coverage 91%; repository integrity confirmed. Stage 4 имеет статус `DONE`.
Следующее действие — подготовка и начало Stage 5 согласно ROADMAP; Stage 5 ещё
не начат.

---

# Этап 5. Предварительная обработка и каркас анализаторов — DONE

## Цель

Создать расширяемый механизм подготовки image/audio/video и единый контракт выполнения анализаторов.

## Архитектурная prerequisite

```text
Stage 5 architecture PLAN: ACCEPTED WITH OWNER CLARIFICATIONS
Implementation status: DONE
```

Архитектурная prerequisite подготовлена и зафиксирована документацией.

Принятые owner clarifications нормативно закреплены в `PROJECT.md` и
`CONTRACTS.md`: generic analyzer timeout реализуется spawned child process per
invocation; opaque parent capabilities преобразуются в private picklable
`WorkerRequest`; normal `TIMEOUT` публикуется только после confirmed stop/reap,
а unreapable worker является fatal infrastructure failure; общий
`limits.processing_timeout_seconds` начинается как monotonic budget на входе
`Stage5ExecutionService.execute(task)` без добавления нового Stage 4 claim
timestamp.

## Implementation decomposition

Текущие статусы increments:

1. **Increment 1 — DONE:** internal models + source/artifact capability boundary.
2. **Increment 2 — DONE:** bounded subprocess primitive + Stage 3 parity migration.
3. **Increment 3 — DONE:** image/audio/video preprocessing.
4. **Increment 4 — DONE:** analyzer registry/orchestration + hard process timeout.
5. **Increment 5 — DONE:** integrated Stage 4 → Stage 5 lifecycle.
6. **Исправления по итогам финального аудита Stage 5 — DONE:** R1–R6 = DONE;
   focused closure audit = PASS.

Increment 2 выделил private shared process boundary с hard-bounded stdout,
discard-режимом, explicit cwd, `shell=False`, disabled stdin, timeout и
подтверждённым terminate/kill/reap. `FFmpegMediaInspector` мигрирован без
изменения Stage 3 argument construction и rejected/failed semantics.

Increment 3 добавил внутренний детерминированный dispatcher и реализации
предобработки для image/audio/video. Все создаваемые файлы резервируются в
`WorkspaceArtifactRegistry` до физического создания; `PreparedMedia` содержит
только непрозрачные ссылки и ограниченные неизменяемые метаданные. Для image
создаётся PNG первого отображаемого кадра с применённой EXIF orientation, для
audio — PCM s16le WAV, фактические фрагменты и спектрограмма по требованию, для
video — ограниченный набор периодических PNG-кадров и FLAC-аудиодорожка по
требованию.

Increment 4 добавил внутренний analyzer contract, закрытый worker-resolvable
registry с analyzer-specific typed settings validation и последовательный
orchestrator в точном порядке per-media `enabled`. Каждый фактически запущенный
analyzer выполняется в отдельном explicit-spawn worker; private bounded transport
не переносит parent capabilities или media bytes. Analyzer exception и
serialization failure дают безопасный canonical `ERROR`, а canonical `TIMEOUT`
возникает только после подтверждённого terminate/kill/reap; unreapable worker
остаётся fatal infrastructure failure. Framework подтверждён только internal fake
analyzers без score, findings и default-config activation.

Increment 5 добавил внутренний `Stage5ExecutionService`, совместимый с прежним
`TaskExecutor.execute(task)`, и связал production path Stage 3/4 с preprocessing,
авторитетным `Stage5TaskData`, переходом `PREPROCESSING → ANALYSIS` и
последовательным analyzer orchestration. Требования к demand-driven артефактам
вычисляются только по активному analyzer plan; единый monotonic deadline от входа
в executor ограничивает preprocessing и каждый analyzer. Отдельные
`ERROR`/`TIMEOUT` сохраняются как `AnalyzerResult`, фатальная инфраструктурная
ошибка и общий timeout завершают execution как `FAILED`, а terminal settlement,
cleanup и release остаются исключительной ответственностью Stage 4. Полный quality barrier: 1143
passed, 2 skipped, coverage 90%.

Функциональная реализация Stage 5 и исправления по результатам финального аудита
завершены. R1
закрывает `S5-AUD-001` и `S5-AUD-002`; R2 закрывает `S5-AUD-003`,
`S5-AUD-004`, `S5-AUD-005`, `S5-AUD-006` и `S5-AUD-011`; R3 закрывает
`S5-AUD-007`, `S5-AUD-008` и `S5-AUD-010`; R4 закрывает `S5-AUD-009` и
`S5-AUD-012`. R5 устраняет оставшийся путь прерывания `S5-AUD-001`,
воспроизведённый повторным аудитом. R6 закрыл замечания аудита изображений.
Полная проверка R4: 1236 passed,
2 skipped, coverage 90% (89,69% при точности до сотых); целевая проверка:
217 passed. Ruff, проверка форматирования затронутых Python-файлов, mypy,
`poe check`, pre-commit, CLI smoke и `git diff --check` прошли.

Целевая проверка R5: worker/process/lifecycle/R1/R2 — 337 passed, 1 skipped
(создание symlink недоступно в среде); дополнительные проверки preprocessing
по resource/budget/timeout/termination — 6 passed, 30 deselected. Добавлены
72 проверки прерываний с реальными дочерними процессами, включая ограниченный reap,
сохранение барьера и однократную очистку при восстановлении. Ruff, проверка
форматирования восьми затронутых Python-файлов, `mypy src` и `git diff --check` прошли.
Полный pytest/poe barrier в R5 не запускался; полный набор проверок остаётся после R6.

## Исправления по итогам финального аудита

- [x] R1 — безопасность процессов и владения: неподтверждённое завершение
  процесса блокирует физическую очистку и `FINISHED`; ошибки ввода-вывода
  контролируемого входа отделены от ошибок анализатора;
- [x] R2 — согласованные ограничения ресурсов и транспорта, а также единый
  идентификатор снимка конфигурации;
- [x] R3 — резервирование артефактов с учётом псевдонимов путей Windows, очистка исходных
  EXIF/XMP/ICC из нормализованного PNG и обязательность нормализации в конфигурации;
- [x] R4 — публикация оставшихся включённых анализаторов как `SKIPPED` по политике
  остановки и неизменяемое авторитетное хранение результатов с отделённым чтением
  через реестр; единый сериализатор и предел R2 сохранены;
- [x] R5 — прерывание после запуска рабочего или дочернего процесса проходит
  ограниченную последовательность stop/reap; исходное прерывание сохраняется, неподтверждённая безопасность
  передаётся через существующий R1 barrier и блокирует cleanup/release/FINISHED;
- [x] R6 — оставшиеся замечания аудита изображений (APNG и tRNS): отдельный
  default image не подменяет первый APNG animation frame, а RGB/grayscale/palette
  `tRNS` материализуется в alpha до очистки raw metadata;
- [x] повторный независимый финальный аудит (focused closure audit): `PASS`;
  `S5-AUD-001`, `S5-RERUN-001` и `S5-RERUN-002` — `CLOSED`, 146 targeted
  passed, новых findings нет.

## Финальное закрытие

- **Final verification:** `PASS` — 1313 passed, 2 skipped, coverage 89.76%,
  branch coverage enabled; Ruff, mypy, `poe check`, pre-commit и CLI — `PASS`.
- **Focused closure audit:** `PASS` — `S5-AUD-001`, `S5-RERUN-001` и
  `S5-RERUN-002` имеют статус `CLOSED`; 146 targeted passed; новых findings нет.
- **Architecture Truth Review:** `CLOSE_STAGE5_UNCHANGED`. Перед Stage 6 новых
  архитектурных решений не требуется.
- **Future/post-v1.0 candidates:** deprecate/remove
  `analyzers.defaults.continue_on_error`; deprecate/remove
  `image.normalize_for_analysis`; возможное переименование
  `keyframe_interval_seconds` при будущей schema revision; отдельный generated
  artifact budget, chunked result transport и restart recovery — только при
  измеренной потребности.

## Обязательные задачи

### Предварительная обработка изображения

- [x] переиспользовать проверенный source и безопасно открыть изображение для
  подготовки аналитических представлений;
- [x] переиспользовать либо дополнить подтверждённые технические параметры;
- [x] извлечь доступные метаданные;
- [x] создать нормализованную рабочую копию;
- [x] зарегистрировать промежуточный артефакт.

### Предварительная обработка аудио

- [x] декодировать проверенный source в объёме, необходимом для подготовки;
- [x] переиспользовать либо дополнить подтверждённые параметры;
- [x] создать canonical signed 16-bit PCM WAV fragments без resample/downmix;
- [x] разделить на фрагменты по конфигурации;
- [x] построить спектрограмму только при необходимости;
- [x] зарегистрировать артефакты.

### Предварительная обработка видео

- [x] переиспользовать проверенный source и при необходимости дополнить параметры
  через FFmpeg/ffprobe безопасным вызовом;
- [x] не загружать всё видео в память;
- [x] извлечь periodic sampled representative frames/сегменты;
- [x] извлечь аудиодорожку при наличии;
- [x] зарегистрировать артефакты;
- [x] ограничить время внешних процессов.

### Каркас анализаторов

- [x] реализовать протокол `Analyzer`;
- [x] реализовать registry;
- [x] включать анализаторы конфигурацией;
- [x] проверять применимость;
- [x] реализовать timeout;
- [x] изолировать ошибку отдельного анализатора;
- [x] реализовать тестовый анализатор для каждого маршрута или общий fake analyzer;
- [x] собирать `AnalyzerResult`.

## Обязательные тесты

- [x] подготовка валидного изображения;
- [x] подготовка валидного аудио;
- [x] подготовка валидного видео;
- [x] повреждённые данные дают контролируемую ошибку;
- [x] внешний процесс вызывается без shell-инъекции;
- [x] disabled analyzer не запускается;
- [x] not applicable отражается корректно;
- [x] error одного анализатора не останавливает остальные;
- [x] timeout отражается;
- [x] артефакты попадают в очистку.

## Критерий завершения

Система может подготовить каждый тип медиа, запустить набор тестовых анализаторов и получить массив контрактных `AnalyzerResult`.

## Решение до этапа 6

Необходимо выбрать минимальный набор **реальных** MVP analyzers, их версии,
applicability, fixtures и analyzer-specific semantics для `raw_metrics` /
`candidate_findings`.

---

# Этап 6. Базовые анализаторы и формирование признаков — DONE

## Цель

Подключить ограниченный, реально проверяемый набор анализаторов и преобразовать их результаты в нормализованные признаки.

## Ворота этапа

### Increment 0 — analyzer profile, provenance и documentation prerequisite — DONE

Owner утвердил Profile B и provenance policy. До production implementation
зафиксированы:

- четыре `analyzer_id` и их версии;
- Finding policy v1 и граница sibling Stage 6 task state;
- versioned deterministic MVP thresholds;
- dependency, hardware и fixture policies;
- обязательный канонический provenance registry `REFERENCES.md`.

Profile B:

| Analyzer | Version | Назначение |
|---|---|---|
| `image_metadata_consistency` | `1.0.0` | технический image analyzer |
| `audio_pcm_quality` | `1.0.0` | технический audio analyzer |
| `video_sampled_frame_quality` | `1.0.0` | технический video analyzer |
| `image_copy_move_correspondence` | `1.0.0` | content-oriented image analyzer |

Audio/video content analyzers сознательно не входят в MVP v1. ML analyzers,
model weights, PyTorch и CUDA не входят в Stage 6 MVP. Профиль остаётся CPU-only;
GPU не требуется.

### Finding policy v1

- все первоначальные findings имеют `severity=weak`;
- `score`, `score_name`, `source_score` и `score_impact` равны `null`;
- `critical_override_eligible=false`;
- AI probability и статистическая интерпретация heuristic thresholds запрещены;
- thresholds являются versioned deterministic MVP defaults;
- candidate findings преобразуются в `Finding` на Stage 6 с сохранением analyzer
  identity, version и связи с источником;
- нормализованные `Finding[]` хранятся в отдельном sibling Stage 6 task state;
  смысл `Stage5TaskData` не расширяется.

### Threshold policy

Для `audio_pcm_quality`:

```text
full_scale_sample_ratio threshold = 0.001
```

Для `image_copy_move_correspondence`:

```text
min_dimension_px = 128
max_pixels = 12_000_000
max_keypoints = 5_000
descriptor_ratio = 0.75
min_spatial_separation_px = max(32, 0.05 * min_dimension)
ransac_reprojection_threshold_px = 3
min_cluster_inliers = 12
min_cluster_inlier_ratio = 0.5
max_clusters = 4
```

Значения не являются статистически валидированными forensic thresholds. Это
воспроизводимые MVP defaults; их изменение в Stage 6 требует обоснования
deterministic positive/negative/challenge fixtures и отдельной фиксации.

### Dependency, hardware и fixture policies

- planned pins для `image_copy_move_correspondence`:
  `opencv-python-headless==4.14.0.94` и `numpy==2.5.2`;
- Increment 2 до основной реализации выполняет dependency smoke gate: package
  installation, `import numpy`, `import cv2`, создание ORB и минимальная
  descriptor operation;
- несовместимая пара wheels может быть скорректирована как dependency correction
  без пересмотра архитектуры Stage 6;
- остальные три analyzers не требуют новых runtime dependencies;
- текущий development/reference computer можно использовать для benchmark, но
  он не становится обязательным deployment requirement;
- предварительный ориентир reference environment: x86-64 CPU, 16 GiB RAM, без
  GPU; это не окончательная minimum specification;
- closure increment измеряет фактические resource requirements на benchmark и
  фиксирует результат;
- repository хранит deterministic generated positive, negative,
  false-positive/challenge и boundary/not-applicable fixtures;
- реальные datasets/media на этом этапе не добавляются, а fixtures не
  представляются статистической validation dataset.

### Provenance requirement

`REFERENCES.md` является каноническим реестром происхождения методов,
реализаций, библиотек, repositories, статей, моделей и weights. Правило Stage 6:
**NO PROVENANCE — NO ANALYZER**. Реальный analyzer нельзя считать завершённым,
пока применимая provenance information не заполнена и происхождение метода
отделено от происхождения реализации.

Framework test analyzers сохраняются только для проверки общей execution
архитектуры; production implementations подключаются отдельными trusted
registrations.

### Increment 1 — technical analyzers + Finding vertical slice — DONE

Реализованы три независимых production-path technical analyzers версии `1.0.0`:

- `image_metadata_consistency` использует controlled original source и не
  интерпретирует отсутствие metadata или software tag как finding;
- `audio_pcm_quality` потоково анализирует canonical signed 16-bit little-endian
  PCM WAV и локализует не более 16 strongest saturation observations по
  существующим fragments;
- `video_sampled_frame_quality` использует только подготовленные sampled frames,
  сравнивает decoded pixels и не требует video audio track.

Private typed candidate boundary повторно валидируется deterministic Stage 6
converter. Content-addressed `finding_id` следует §9.5 `CONTRACTS.md`; findings
сохраняются как canonical immutable bytes в отдельном sibling `Stage6TaskData`, а
detached reads не изменяют authoritative state. Новые runtime dependencies,
public API, persistence, risk/completeness logic и новый `ProcessingStage` не
добавлены. Generated fixtures и targeted Stage 5/6 regressions подтверждают
контракт и resource/transport bounds.

Ближайшее действие: Increment 2 — smoke gate planned OpenCV/NumPy pins и
реализация `image_copy_move_correspondence`.

### Increment 2 — ограниченное соответствие областей изображения — DONE

Запланированные версии `opencv-python-headless==4.14.0.94` и `numpy==2.5.2`
штатно установлены через uv и подтверждены на Windows / Python 3.12: импорт,
ORB-дескрипторы и оценка аффинной модели RANSAC прошли детерминированную
минимальную проверку. Реализован доверенный
`image_copy_move_correspondence` `1.0.0`, использующий только существующий
`normalized_image`, сопоставление ORB-признаков внутри изображения только на CPU,
пространственное разделение и не
более четырёх итераций OpenCV RANSAC.

Каждый принятый геометрический кластер создаёт ровно два bbox-кандидата с общим
адресуемым по содержимому `correlation_group`; симметричные самосопоставления и
близкие дублирующие пары областей детерминированно подавляются. Настройками и кодом
установлены пределы: 5 000 ключевых точек, 4 кластера и 8 кандидатов; дескрипторы,
ключевые точки, сопоставления и пиксели не публикуются через транспорт. Пройдены
генерируемые положительная, отрицательная, с альфа-каналом RGBA, проверка ложного
срабатывания, граничная, детерминированная и выполняемая в порождённом рабочем
процессе фикстуры. Наблюдение остаётся `weak` и не утверждает подделку переносом
области изображения.

### Increment 3 — production integration, benchmark и полный barrier — DONE

`Stage5ExecutionService`, не меняя `TaskExecutor` и ownership terminal lifecycle,
после orchestration сверяет возвращённый tuple с опубликованными данными, читает
detached canonical `AnalyzerResult[]` через authoritative `TaskRegistry`, передаёт
их `Stage6FindingService` и публикует отдельный `Stage6TaskData` в состоянии
`RUNNING / ANALYSIS`. Пустой `Finding[]` публикуется как корректное состояние;
ошибка candidate validation безопасно завершает задачу через существующий
`internal_error` analysis phase. Новый `ProcessingStage`, public executor,
schema, persistence или Stage 7 logic не добавлены.

Production composition root создаёт закрытый `AnalyzerRegistry` только из четырёх
real Profile B registrations и связывает intake, preprocessing, spawned analyzer
workers, Finding formation, registry и bounded scheduler. Канонический example
config включает планы в порядке:

```text
image: image_metadata_consistency → image_copy_move_correspondence
audio: audio_pcm_quality
video: video_sampled_frame_quality
```

Сквозные генерируемые image/audio/video tests подтвердили production composition,
авторитетное хранение results/findings, пустой результат, `NOT_APPLICABLE`,
изоляцию `ERROR`, безопасный malformed candidate, неизменный смысл
`Stage5TaskData`, lifecycle `ANALYSIS` до terminalization и detached reads.

Closure benchmark `uv run python scripts/benchmark_stage6_copy_move.py` выполнен
2026-09-08 на Windows 11 `10.0.26200`, AMD64, Intel(R) Core(TM) Ultra 7 270K Plus,
24 logical CPU, 130427.84 MiB total RAM, Python 3.12.10, OpenCV 4.14.0 и NumPy
2.5.2. В отдельном свежем child process анализировался генерируемый по seed 6003
feature-rich PNG 4000×3000 (12 000 000 pixels, 3 896 452 bytes) с одной
скопированной областью 700×700; один warm-up исключён, затем измерены три запуска.
RAM измерена Win32 `GetProcessMemoryInfo / PeakWorkingSetSize`, включая baseline
интерпретатора и импортов дочернего процесса.

| Run | Wall, s | CPU, s | Peak working set, MiB | Keypoints | Descriptors | Matches | Clusters | Candidates |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.613 | 0.578 | 161.78 | 5000 | 5000 | 104 | 1 | 2 |
| 2 | 0.615 | 0.562 | 161.65 | 5000 | 5000 | 104 | 1 | 2 |
| 3 | 0.622 | 0.578 | 161.66 | 5000 | 5000 | 104 | 1 | 2 |

Итог: median wall `0.615 s`, max wall `0.622 s`, max peak working set
`161.78 MiB`. Это наблюдение одной reference machine, а не универсальная
hardware guarantee. Предварительный conservative deployment baseline x86-64 CPU,
16 GiB RAM, без GPU подтверждён и не понижен по одному локальному замеру. Пределы
12 MP, 5000 ORB keypoints, 4 clusters и 8 candidates не расширялись; измерение
дало 1 cluster и 2 candidates, raw pixels/keypoints/descriptors в result не
публикуются, Stage 5 transport bound и deterministic OpenCV one-thread/OpenCL-off
policy не изменены.

Full Stage 6 quality barrier пройден после implementation и benchmark: `uv lock
--check`, Ruff, mypy, pre-commit, CLI/import smoke и `1389 passed, 2 skipped`;
combined coverage `89.55%`, statement coverage `92.03%`, branch coverage `79.52%`
при включённом `--cov-branch`. Исторические 19 formatter discrepancies остались
тем же не затронутым Stage 6 debt, все изменённые Python-файлы format-clean.
Эта проверка качества реализации предшествовала независимому финальному аудиту
и сохранена для прослеживаемости. Формальное закрытие зафиксировано ниже.

### Ремедиация замечаний независимого аудита и финальное закрытие — DONE

Независимый финальный аудит Stage 6 завершился `FAIL` с четырьмя блокирующими
замечаниями. `S6-AUD-001`, `S6-AUD-003` и `S6-AUD-004` закрыты. Повторный аудит
подтвердил устранение наблюдаемых разрывов владения потоками `S6-AUD-002`, но
обнаружил `S6-REAUD-001` уровня `MEDIUM`: вторичное исключение рабочего потока
при завершении `lifespan` могло заменить первичное исключение вызывающего кода.
Локальная ремедиация выполнена без изменения Profile B, публичной схемы,
`TaskExecutor`, `ProcessingStage` или архитектуры владения Stage 4:

- [x] `S6-AUD-001` — после обнаружения ORB связанные пары keypoint/descriptor
  канонически упорядочиваются и жёстко ограничиваются `max_keypoints` до
  самосопоставления; публикуемые счётчики описывают сохранённое подмножество;
- [x] `S6-AUD-002` — attempts запуска, публикация полного worker ownership,
  переход в `RUNNING` и startup notify находятся под одной failure-cleanup
  boundary без `try/except/else`; при сбое до commit планировщик публикует
  terminating state, запрещает новые передачи задач, явно ожидает через `join()`
  все наблюдаемо запущенные потоки и затем очищает ownership; обычное `Exception`
  сохраняет `SchedulerStateError`, а exact `KeyboardInterrupt`/`SystemExit`
  поднимается повторно; production lifespan включает `start()` в собственную
  cleanup boundary и после любого подтверждённого startup либо фактического
  non-stopped состояния вызывает штатный `shutdown()`, включая post-return
  interruption до локальной фиксации успешного startup;
- [x] `S6-AUD-003` — `PixelXDimension`/`PixelYDimension` ищутся во всех
  допустимых представлениях Pillow раньше `ImageWidth`/`ImageLength`;
  присутствующий некорректный основной тег не подменяется резервным и не создаёт
  необоснованного заключения о согласованности;
- [x] `S6-AUD-004` — подавление пар по IoU с прежним порогом `0.5` проверяет оба
  порядка неупорядоченной пары областей — прямой и перекрёстный; отдельные
  кластеры сохраняются.

- [x] `S6-REAUD-001: CLOSED` — `lifespan` различает завершение с первичным
  исключением и без него. После завершённого `shutdown()` сохраняется тот же
  объект первичного `BaseException`; без первичного исключения ошибка рабочего
  потока выходит наружу. Сбой незавершённого `shutdown()` не подавляется.
  Проверены разные объекты `KeyboardInterrupt`, `SystemExit` и `RuntimeError`,
  реальная задача рабочего потока, однократные `join()` и отсутствие живых
  `stage4-*`. Устранение подтверждено финальной независимой проверкой закрытия.

#### S6-LIM-001 — CPython `Thread.start()` pre-ack interruption ambiguity

Статус: `ACCEPTED_RUNTIME_LIMITATION`.

Влияние на закрытие: `DOES_NOT_BLOCK_STAGE6_CLOSURE`.

CPython 3.12 может создать нативный поток ОС раньше, чем `Thread.start()`
опубликует `_started` и `ident`. В этом узком окне `ident` может оставаться
`None`, `is_alive()` — возвращать `False`, а `join()` — быть недоступным, поэтому
публичный API `threading` не позволяет доказуемо отличить ещё не созданный поток
от созданного, но ещё не подтвердившего старт. Планировщик не заявляет явный
`join()` такого ненаблюдаемого потока.

Остаточное окно принято как эксплуатационное ограничение: после неудачного
старта состояние планировщика уже является `SHUTTING_DOWN` или `STOPPED`, новые
передачи задач отклоняются, а поздно подтвердивший старт рабочий поток при входе
в цикл видит завершающее состояние и заканчивает работу без исполнения задачи.
Устранение наблюдаемого разрыва владения после цикла запуска `S6-AUD-002`
подтверждено независимым аудитом. Глобальная для процесса
отсрочка сигналов, отдельный долгоживущий владелец старта, дополнительный поток
или процесс запуска, собственный нативный механизм запуска или расширение C,
приватные глобальные объекты CPython, daemon-потоки и тайм-ауты или опрос для
угадывания результата старта не вводятся.

Нагрузочная фикстура на зафиксированной версии OpenCV дала `5687` исходных
keypoints/descriptors и `5000` сохранённых и проанализированных; `BFMatcher`
получил не более `5000`, результат остался детерминированным и ограниченным.
Повторный контрольный замер 12 MP сохранил `5000` keypoints/descriptors, `104`
сопоставления, `1` кластер и `2` кандидата.

Финальная полная проверка качества на HEAD
`0377185889a703aee92df6c23458a28aef1630a1`: `1438 passed, 2 skipped`;
совокупное покрытие `89.78%`, покрытие операторов `92.27%` (`5595/6064`),
покрытие ветвей `79.73%` (`1196/1500`) при включённом `--cov-branch`.
`uv lock --check`, Ruff, mypy для 56 исходных файлов, pre-commit, базовая
проверка CLI, импорт пакета, импорт OpenCV 4.14.0, импорт NumPy 2.5.2 и
`git diff --check` имеют статус `PASS`. Исторический базовый набор расхождений
форматтера остался тем же: 19 файлов; рабочее дерево при аудите было чистым.

Финальная независимая проверка закрытия вынесла решение
`CLOSE_STAGE6_WITH_ACCEPTED_LIMITATION`. `S6-AUD-001`…`S6-AUD-004` и
`S6-REAUD-001` имеют статус `CLOSED`; `S6-AUD-005` — `INFO / NON_BLOCKING`.
Новых замечаний уровня `HIGH` или `MEDIUM`, блокирующих закрытие, нет.
`S6-LIM-001` сохранён как осознанное `ACCEPTED_RUNTIME_LIMITATION` /
`NON_BLOCKING`: он не распространяется на наблюдаемые рабочие потоки, для
которых все наблюдаемые разрывы владения при запуске устранены. Stage 6 завершён
и закрыт.

## Рекомендуемый минимальный принцип выбора

Для каждой модальности достаточно:

- одного технического/метадатного анализатора;
- одного простого содержательного анализатора, если он обоснован и тестируем;
- ML-анализатора только при подтверждённой необходимости и доступном оборудовании.

Количество анализаторов не является критерием качества.

## Обязательные задачи

- [x] утвердить профиль анализаторов image;
- [x] утвердить профиль анализаторов audio;
- [x] утвердить профиль анализаторов video;
- [x] реализовать выбранные анализаторы как независимые модули;
- [x] зафиксировать версии;
- [x] добавить тестовые fixtures;
- [x] реализовать преобразование candidate findings в `Finding`;
- [x] хранить `Finding[]` в отдельном sibling Stage 6 task state;
- [x] сохранять связь с анализатором и версией;
- [x] реализовать локализацию, где она доступна;
- [x] ввести correlation_group для связанных результатов;
- [x] не назначать critical автоматически по confidence.
- [x] создать `REFERENCES.md` и зафиксировать правило NO PROVENANCE — NO ANALYZER;
- [x] актуализировать provenance после каждой фактической реализации analyzer.

## Обязательные тесты

- [x] каждый анализатор проходит контрактный тест;
- [x] корректно сообщает not applicable;
- [x] не создаёт выдуманный score;
- [x] формирует стабильный finding type;
- [x] локализация валидна;
- [x] версия присутствует;
- [x] ошибка не ломает общий цикл;
- [x] коррелированные признаки маркируются.

## Критерий завершения

Сквозной контур работает с утверждённым Profile B; каждый analyzer имеет
проверенные deterministic fixtures и заполненную запись в `REFERENCES.md`, а
нормализованные findings сохраняют provenance в отдельном sibling Stage 6 state.

---

# Этап 7. Полнота, риск и рекомендации — DONE

## Цель

Преобразовать набор признаков в объяснимую оценку с учётом неполноты и корреляции.

## Декомпозиция реализации

- [x] Increment 1 — зафиксировать политику MVP и реализовать чистое
  детерминированное ядро полноты, риска и рекомендаций без интеграции с жизненным
  циклом;
- [x] Increment 2 — добавить минимальное внутреннее состояние задачи для
  результатов Stage 7 без нового оркестратора;
- [x] Increment 3 — подключить Stage 7 к рабочему выполнению в существующей
  модели владения жизненным циклом.

Increment 2 добавил отдельный предназначенный только для внутреннего использования
`Stage7TaskData` с каноническими неизменяемыми JSON-байтами для
`AnalysisCompleteness`, `RiskAssessment` и `Recommendation`, однократную атомарную
публикацию и независимое чтение через авторитетный `TaskRegistry`. Жизненный цикл
расширен переходами
`ANALYSIS → RISK_ASSESSMENT → COMPLETED | PARTIAL | FAILED / CLEANUP`;
Stage 8 Macro 1 позднее расширил общий терминальный участок через
`PERSISTENCE → FINISHED`. Пригодный `PARTIAL` поддерживается
`TaskExecutionOutcome.partial()` без искусственной ошибки и отдельного пути очистки.
Increment 3 подключил рабочую цепочку
`Stage 5 → AnalyzerResult[] → Stage 6 → Finding[] → RISK_ASSESSMENT → Stage 7`.
Исполнитель получает активный план анализаторов из того же неизменяемого снимка
конфигурации, публикует `Stage7TaskData` до возврата основного результата
выполнения и сопоставляет `complete` с `COMPLETED`, а `partial` и `insufficient` —
с `PARTIAL`. Внутренний сбой Stage 7 безопасно приводит к `FAILED`; существующее
владение очисткой и публикация `FINISHED` не изменены. Рабочий Profile B сохраняет
`probability=null`, пустой доверенный каталог правил `critical_override` и один
вклад weak для коррелированной пары `Finding` copy-move.

Все три функциональных инкремента Stage 7 реализованы, предаудитный полный барьер
качества реализации успешно пройден. Независимый финальный аудит завершён с verdict
`CLOSE_STAGE7_UNCHANGED`; Stage 7 формально закрыт. Stage 8 также формально закрыт:
Macro 1 и Macro 2 завершены, findings `S8-A01`–`S8-A03` исправлены, а
post-remediation closure audit завершён с `PASS` без новых findings.

## Обязательные задачи

### Полнота

- [x] реализовать подсчёт `planned`/`applicable`/`completed`/`error`/`timeout`/`skipped`;
- [x] реализовать статусы `complete`/`partial`/`insufficient`; сохранить
  `not_assessed` только для отклонения или сбоя до Stage 7;
- [x] включить алгоритм полноты v1 в единый пакет правил
  `score_model_v1@0.1.0` без нового публичного поля;
- [x] запретить `low` при `insufficient`;
- [x] формировать `missing_capabilities` в порядке активного плана.

### Риск

- [x] реализовать отдельный `RiskAssessmentService`;
- [x] загружать веса и пороги из типизированной конфигурации;
- [x] версионировать правила как `score_model_v1@0.1.0`;
- [x] реализовать балльную модель MVP как проектную, не статистическую;
- [x] реализовать ограничение двойного учёта `correlation_group`;
- [x] оставить `probability` и `probability_method` равными `null`;
- [x] реализовать детерминированные `explanation` и `limitations`.

### Critical override

- [x] оставить выключенным по умолчанию;
- [x] оставить доверенный рабочий каталог Profile B пустым;
- [x] проверить список разрешённых типов, точное доверенное правило, источник,
  версию и применимость;
- [x] сохранять вызвавшие `critical_override` идентификаторы `finding_id`
  детерминированно;
- [x] добавить отдельные тесты с тестовым доверенным правилом.

### Рекомендации

- [x] связать риск и полноту с безопасными действиями;
- [x] не выполнять автоматическое реагирование;
- [x] формировать детерминированный русскоязычный человекочитаемый текст;
- [x] учитывать `partial`/`insufficient`.

## Обязательные тесты

- [x] отсутствие признаков при полном анализе;
- [x] несколько `Finding` с `severity=weak`;
- [x] `Finding` с `severity=significant`;
- [x] коррелированные `Finding` не удваивают вклад;
- [x] анализ со статусом `partial`;
- [x] анализ со статусом `insufficient`;
- [x] `critical_override` выключен;
- [x] разрешённый `critical_override`;
- [x] запрещённый `critical_override`;
- [x] `probability` остаётся `null`;
- [x] объяснение соответствует основаниям.

## Критерий завершения

Для фиксированного набора входных `AnalyzerResult` система детерминированно выдаёт контрактные `Finding`, полноту, риск и рекомендацию, подтверждённые тестами.

## Финальный аудит Stage 7

Независимый read-only аудит завершён с verdict
`CLOSE_STAGE7_UNCHANGED`. Correctness findings уровней `BLOCKER`, `HIGH` и
`MEDIUM` отсутствуют.

- `S7-A01` (`LOW`) — `CLOSED` в documentation closure: устаревший комментарий
  примера конфигурации синхронизирован с фактическим production execution path;
- `S7-A02` (`LOW`) — `CLOSED` попутно во время Stage 8 Macro 1: регрессионные
  проверки подтверждают `processing_timeout / FAILED` при истечении срока до
  публикации и отсутствие нового окна тайм-аута или сбоя после успешной границы
  фиксации `publish_stage7_assessment()`.

Stage 7 имеет статус `DONE`. Stage 8 также завершён и закрыт после исправления
findings `S8-A01`–`S8-A03` и успешного post-remediation closure audit.

---

# Этап 8. JSON, API и WebUI — DONE / CLOSED

## Цель

Предоставить единый итоговый результат человеку и внешней системе без дублирования бизнес-логики.

## Декомпозиция реализации

- [x] Macro 1 — хранение результатов: правдивый терминальный `AnalysisResult`
  1.0, отделённые факты терминального состояния, единые сборщик и финализатор,
  атомарное сохранение JSON и рабочая интеграция с записью до `FINISHED`;
- [x] Macro 2 — утверждённые асинхронный HTTP API и WebUI с HTTP Basic;
  реализация и проверка владельцем завершены, независимый финальный аудит выполнен,
  findings `S8-A01`–`S8-A03` исправлены в remediation commit `7093922`, а
  post-remediation independent closure audit завершён с `PASS` без новых findings.

Macro 1 исправляет схему `AnalysisResult` 1.0 до первого внешнего использования:
до появления первого рабочего потребителя API/WebUI добавлена фактическая
нулевая допустимость терминальных путей без перехода на 2.0 и без миграции
совместимости. `ResultFinalizationService` собирает результат только из
авторитетных фактов, применяет `include_raw_metrics` к отделённой проекции и
сохраняет её до публикации `FINISHED`. Ошибка сохранения оставляет принятую задачу
в `PERSISTENCE` с `result_write_failed`, не повторяя анализ и очистку; ошибка
сохранения Stage 3 не создаёт фиктивный результат или гарантию восстановления.

## Ворота этапа

Решения владельца для Macro 2 подтверждены:

- [x] асинхронный API с задачами;
- [x] три маршрута и фактические временные метки статуса;
- [x] смешанная семантика HTTP-ответов при отклонении;
- [x] HTTP Basic для WebUI;
- [x] статический Bearer-токен API из окружения.

Реализация этих внешних границ относится только к Macro 2.

## Обязательные задачи

### Итоговый результат

- [x] собрать только терминальный `AnalysisResult` 1.0 для принятого пути и путей
  Stage 3;
- [x] добавить фактический статус очистки без подстановочных значений;
- [x] сохранить через существующий `JsonFileResultRepository`;
- [x] проверить детерминированный канонический JSON и атомарную запись;
- [x] не включать внутренние пути, права доступа и секреты;
- [x] обеспечить `FACT_READY → PERSISTENCE → save → FINISHED`;
- [x] сохранить авторитетные факты анализаторов и признаков для принятого
  `failed`;
- [x] применить `include_raw_metrics` без изменения состояния задачи;
- [x] отклонять `atomic_write=false` и `store_original_name=false`.

### API

- [x] реализовать выбранный профиль;
- [x] проверить Bearer-токен из окружения;
- [x] реализовать загрузку `multipart/form-data`;
- [x] валидировать SourceContext;
- [x] вернуть канонические ошибки;
- [x] не размещать бизнес-логику в маршрутах;
- [x] сформировать OpenAPI из моделей.

### WebUI

- [x] создать страницу загрузки;
- [x] показать ограничения;
- [x] создать статус/ожидание обработки;
- [x] создать страницу результата;
- [x] использовать тот же `AnalysisResult`;
- [x] показать полноту и ограничения;
- [x] показать предупреждение об отсутствии окончательной экспертизы;
- [x] реализовать утверждённый HTTP Basic;
- [x] создать каталоги `templates` и `static`;

## Обязательные тесты

### Хранение результатов Macro 1

- [x] все терминальные формы `COMPLETED`, `PARTIAL`, `REJECTED`, `FAILED`;
- [x] инварианты только терминального результата, фактическая нулевая
  допустимость, хронология и `NOT_ASSESSED` без подстановочных нулей;
- [x] отклонение и сбой Stage 3, неудачная передача владения и отсутствие
  результата для
  `PreRegistrationError`;
- [x] канонический круговой цикл сериализации, CRUD и перечисление в репозитории,
  атомарная замена и безопасность при повреждении данных, несовпадении
  идентификатора, небезопасном пути, символической ссылке и `OSError`;
- [x] обе политики `include_raw_metrics` без изменения авторитетных фактов;
- [x] срок выполнения до публикации Stage 7 и граница фиксации после публикации;
- [x] сохранение после `FACT_READY`, `FINISHED` только после сохранения и запрет
  повторной попытки при ошибке сохранения;
- [x] отделённые авторитетные факты терминального состояния и облегчённый рабочий
  путь изображения.

### HTTP/WebUI Macro 2

- [x] успешная загрузка WebUI;
- [x] успешная загрузка API;
- [x] оба канала используют один сервис;
- [x] 401 без токена;
- [x] 413 для большого файла;
- [x] 415 для неподдерживаемого типа;
- [x] статус и результат соответствуют контракту;
- [x] WebUI не пересчитывает риск;
- [x] ошибка не раскрывает трассировку;
- [x] OpenAPI соответствует Pydantic-моделям.

## Критерий завершения

Файл можно передать через WebUI и API, получить один и тот же доменный результат и безопасно обработать ошибки.

Macro 1 и Macro 2 реализованы и покрыты контрактными и межканальными тестами.
Общий критерий функциональной реализации достигнут. Stage 8 Macro 1 и Macro 2
завершены; независимый финальный аудит выполнен, findings `S8-A01`, `S8-A02` и
`S8-A03` исправлены в remediation commit `7093922`. Post-remediation independent
closure audit завершён с `PASS`, новых findings нет. Stage 8 имеет статус
`DONE / CLOSED`; Stage 9 также завершён и закрыт после independent
post-remediation audit с `PASS`: findings `S9-A01` и `S9-A02` закрыты, новых
findings нет. Актуальный статус Stage 10 приведён в разделе «Текущее состояние»
и подробном разделе Этапа 10.

Quality barrier closure audit Stage 8: `1687 passed, 3 skipped`, coverage `90%`;
`ruff`, `mypy`, `pre-commit`, lock, CLI/import и `git diff --check` — `PASS`.

---

# Этап 9. Надёжность, безопасность и сквозные тесты — DONE / CLOSED

## Цель

Доказать работоспособность полного цикла в штатных и аварийных сценариях.

## Декомпозиция Stage 9

- [x] Macro 1 — DONE / committed at `ad6050c`: lifecycle safety и JSONL diagnostics: cleanup safety barrier
  Stage 3, per-analysis pre-handoff coordination с janitor, безопасные
  диагностические события и `request_id` correlation; findings `S9-M1-R01` и
  `S9-M1-R02` устранены;
- [x] Macro 2 — DONE / committed at `4e4ba3c`: targeted filesystem
  TOCTOU/reparse и runtime-root hardening; sensitive roots/direct workspace проверяются
  на symlink/junction/detectable reparse, destructive recovery retained/reports
  suspicious objects, а private runtime ACL остаётся documented deployment
  prerequisite stdlib/Windows;
- [x] Macro 3 — DONE / committed at `bddcedb`: bounded actual HTTP multipart
  body, receive/parse deadline, strict multipart structure и FFmpeg/process
  security;
- [x] Macro 4 — DONE / committed at `2ef98a3`: Profile B full-path E2E,
  restart/failure/security/concurrency/shutdown proof и измеренный
  performance/resource envelope.
- [x] Final audit remediation — DONE / committed at `111a832`: `S9-A01` и
  `S9-A02` устранены; multipart completeness подтверждается closing-boundary
  callback и завершением ASGI stream; receive/parse deadline дополнен
  synchronous monotonic checkpoints и финальной проверкой до возврата формы.

Macro 1–4 и remediation committed. Independent final audit вернул `REMEDIATE`
по `S9-A01` и `S9-A02`. Independent post-remediation audit завершён с `PASS`:
`S9-A01` — `CLOSED`, `S9-A02` — `CLOSED`; новых findings нет.

Финальное состояние findings:

```text
BLOCKER 0
HIGH 0
MEDIUM 0
LOW 0
```

## Зафиксированные owner decisions

- `S9-D01`: runtime приватен для account приложения; защита от hostile process
  той же Windows account или Administrator не обещается; Macro 2 остаётся
  targeted, полный Win32 handle-based redesign не требуется.
- `S9-D02`: Macro 2 создаёт новые sensitive runtime roots максимально приватно
  средствами stdlib/Python 3.12, не переписывает существующие ACL, не добавляет
  pywin32/dependency, fail-safe обрабатывает reparse hazards; непроверяемые stdlib
  ACL являются deployment prerequisite.
- `S9-D03`: Macro 3 использует max per-media limit + 1 MiB envelope, actual-byte
  counting, `413` до регистрации и `server.request_timeout_seconds` как HTTP
  receive/parse deadline.
- `S9-D04`: JSONL использует только утверждённый safe allowlist; raw exception,
  credentials, secrets, `SourceContext`, headers, filename, paths и иной
  user-controlled payload запрещены без sanitization contract.
- `S9-D05`: durable recovery, persistence/analysis retry и startup cleanup
  `.result-*.tmp` не вводятся; pre-handoff cleanup barrier обязателен, residue
  получает diagnostic и ручную safe maintenance procedure.
- `S9-D06`: local MVP опирается на bounded algorithms, body guard и измеренный
  resource envelope; OS-level CPU/RAM hard quotas вне Stage 9.

## Обязательные задачи

### Ошибки

- [x] классифицировать ошибки;
- [x] обеспечить безопасные пользовательские сообщения;
- [x] сохранять утверждённую Macro 1 диагностику в JSONL;
- [x] проверить частичный сбой;
- [x] проверить системный сбой;
- [x] проверить timeout;
- [x] проверить сбой сохранения;
- [x] проверить сбой очистки.

### Безопасность

- [x] проверить path traversal в sensitive runtime ownership boundaries;
- [x] проверить и усилить runtime storage против concurrent symlink
  substitution / TOCTOU, включая descriptor-based/no-follow подход при
  необходимости;
- [x] проверить command/option injection и protocol abuse для FFmpeg/ffprobe;
- [x] ограничить subprocess time/output и HTTP body receive/parse;
- [x] проверить отсутствие секретов и private payload в JSONL Macro 1;
- [x] проверить отсутствие runtime в Git;
- [x] проверить MIME/signature mismatch;
- [x] ограничить доступ к новым runtime roots средствами stdlib и зафиксировать
  Windows ACL deployment prerequisite;
- [x] проверить токен API;
- [x] проверить CSRF при cookie-аутентификации WebUI, если она выбрана.

### Сквозные сценарии

- [x] валидное изображение;
- [x] валидное аудио;
- [x] валидное видео;
- [x] отклонённый файл;
- [x] один анализатор ошибся;
- [x] несколько анализаторов недоступны;
- [x] insufficient completeness;
- [x] ошибка очистки;
- [x] повторный запрос результата;
- [x] параллельные задачи в пределах лимита.

### Производительность

- [x] измерить время базовых сценариев;
- [x] измерить память для видео;
- [x] проверить отсутствие загрузки крупного видео целиком;
- [x] проверить очередь при нескольких задачах;
- [x] проверить необходимость корректировки EXAMPLE-лимитов по результатам:
  `DEFERRED_WITH_REASON` — informational baseline малых deterministic fixtures
  не обосновывает изменение deployment limits или введение SLA.

## Macro 4 — фактическая E2E-матрица

| Media | Fixture | Активные analyzers | Ожидаемый итог | Внешний путь | Persistence/restart |
|---|---|---|---|---|---|
| image | generated seeded copy-move PNG 512×512 | `image_metadata_consistency`, `image_copy_move_correspondence` | `completed`, findings, complete risk/recommendation | API и representative WebUI | persisted result; отдельный restart proof |
| audio | generated PCM WAV 8 kHz с bounded saturation observations | `audio_pcm_quality` | `completed`, finding, complete risk/recommendation | API | persisted result |
| video | generated MP4 64×64, 2 fps, repeated frames, 3.2 s | `video_sampled_frame_quality` | `completed`, finding, complete risk/recommendation | API | persisted result |

Full-path тесты используют настоящий `create_app`, production composition,
Stage 3 validation, scheduler/registry, Stages 5–7, финализатор,
`JsonFileResultRepository`, API/WebUI и временные каталоги pytest. Отдельно
проверены restart без старого `TaskRegistry`, Stage 3 mismatch, media-tool
infrastructure failure, persistence failure без retry/ложного `FINISHED`, cleanup
residue, auth/body guards assembled app, одновременные image-задачи и graceful
shutdown со startup/shutdown sweep.

## Macro 4 — классификация оставшегося checklist

| Область | Классификация | Основание |
|---|---|---|
| Error taxonomy, safe messages, partial/timeout/insufficient paths | VERIFIED | существующие Stage 5/7 targeted tests и новые full-path terminal tests |
| System, persistence и cleanup failures | IMPLEMENTED | representative deterministic E2E через production boundaries |
| Runtime not in Git | VERIFIED | `.gitignore`, `git ls-files` и итоговый status проверяются barrier |
| MIME/signature mismatch и API token | VERIFIED | assembled-app E2E плюс targeted transport/auth tests |
| WebUI CSRF | NOT_APPLICABLE | cookie/session architecture не выбрана; строгий same-origin guard проверен |
| Bounded deterministic behavior | VERIFIED | artifact/process/body limits, Profile B E2E и measurement sanity |
| OS CPU/RAM hard quotas | DEFERRED_WITH_REASON | `S9-D06`: вне local MVP и Stage 9 |
| Изменение EXAMPLE deployment limits | DEFERRED_WITH_REASON | получен informational reference baseline, но нет данных для нормативной коррекции |

## Macro 4 — reference measurement 2026-09-16

Команда воспроизведения:

```powershell
uv run python scripts/measure_stage9_profile_b.py --runs 3
```

Среда: Windows 11 `10.0.26200`, AMD64, Python 3.12.10,
Intel64 Family 6 Model 198 Stepping 2, 24 logical CPU. Каждый media run выполнен
в свежем process; wallclock охватывает scheduler start, полный application
workflow, persisted result retrieval и graceful shutdown.

| Media | Fixture bytes | Runs | Median wall, s | Max wall, s | Result bytes | Max runner peak RSS, MiB |
|---|---:|---:|---:|---:|---:|---:|
| image | 80 483 | 3 | 1.047 | 1.077 | 6 862 | 73.08 |
| audio | 16 044 | 3 | 0.633 | 0.666 | 4 621 | 67.70 |
| video | 1 101 | 3 | 0.644 | 0.654 | 4 775 | 67.52 |

Полный wallclock девяти изолированных запусков с созданием child process составил
`11.590 s`. RSS на этой Windows-среде измерен stdlib `ctypes` через Win32
`GetProcessMemoryInfo / PeakWorkingSetSize` для свежего workflow runner process.
Метрика включает baseline Python/import/runtime, но не суммирует RSS spawned
analyzer и FFmpeg/ffprobe processes; на POSIX harness использует `ru_maxrss`, а
при недоступности корректной метрики возвращает `null`. Числа являются reference
measurement этой среды, не SLA и не deployment guarantee.

## Критерий завершения

Все обязательные сквозные, негативные и безопасностные тесты проходят; известные ограничения зафиксированы; исходные и промежуточные данные удаляются фактически.

Stage 9 имеет статус `DONE / CLOSED`. Финальный quality barrier:

- full pytest: `1763 passed, 17 skipped`;
- coverage: `90%`;
- targeted remediation/post-remediation suite: `116 passed`;
- `uv lock --check`: `PASS`;
- Ruff: `PASS`;
- mypy: `PASS`, 64 source files;
- pre-commit: все 8 hooks `PASS`;
- CLI/import smoke: `PASS`;
- `git diff --check`: `PASS`.

Принятые ограничения Stage 9 не являются незакрытыми findings:

- Windows ACL остаётся deployment prerequisite;
- hostile same-account / Administrator находится вне гарантированной threat model;
- полный filesystem/process sandbox отсутствует;
- OS CPU/RAM hard quotas не вводились;
- durable unfinished-job recovery отсутствует;
- persistence retry отсутствует;
- автоматическое удаление `.result-*.tmp` crash residue не вводилось;
- resource measurements имеют informational характер и не являются SLA;
- 17 symlink-related skips на текущем Windows host связаны с отсутствием
  symlink privileges; native Windows junction coverage при этом выполнялась.

Актуальный статус Stage 10 приведён в разделе «Текущее состояние» и подробном
разделе Этапа 10.

---

# Этап 10. Сборка и демонстрация MVP — DONE / CLOSED

## Цель

Подготовить воспроизводимый прототип, который можно установить, запустить, продемонстрировать и передать.

## Обязательные задачи

- [x] зафиксировать версии runtime-зависимостей через механический export `uv.lock`;
- [x] проверить чистую установку exact wheel через uv во внешнем venv;
- [x] описать установку FFmpeg для Windows;
- [x] создать README запуска;
- [x] создать безопасный пример `.env.example`;
- [x] подготовить рабочую конфигурацию Profile B для handoff/demo;
- [x] подготовить deterministic generator небольшого набора легальных тестовых файлов;
- [x] описать ограничения анализаторов;
- [x] проверить запуск без IDE;
- [x] проверить очистку после демонстрации;
- [x] зафиксировать номер версии MVP `0.1.0`;
- [x] обновить `CHANGELOG.md` для Macro 1;
- [x] отметить все выполненные критерии MVP.

## Статус макрозадач

- Macro 1 — **DONE / owner accepted**, committed SHA
  `841213f299dd6eb5052cabff95d7bb34fa3f91ab`: package-version source,
  sdist→wheel build, runtime constraints из `uv.lock`, package resources и
  isolated installed-wheel verification.
- Macro 2 — **DONE / owner accepted**: user-facing README и единый
  handoff guide, Windows FFmpeg prerequisite, config/secrets workflow,
  deterministic demo-media generator и его Profile B regression coverage.
- Macro 3 — **DONE / owner accepted**: внешний release assembler и
  verifier создаёт manifest + SHA-256 + versioned ZIP, устанавливает exact wheel
  из проверенной распаковки в fresh venv, запускает kit-копию demo generator и
  два реальных процесса установленного CLI. Development gate подтвердил real
  loopback HTTP, Basic/Bearer, WebUI upload, API image/audio/video, каноническую
  JSON persistence, cleanup, restart retrieval и signal-aware graceful shutdown;
  strict clean-SHA certification после remediation commit завершилась с `PASS`.

## Аудит, исправления и закрытие

Первоначальная strict certification на baseline SHA
`273a62951efebb0d2f10f4456ff4ebe4dd377a1f` завершилась с `PASS`.
Первоначальный независимый аудит Stage 10 вернул `REMEDIATE` по findings
`S10-A01`–`S10-A04`. Все четыре finding исправлены и проверены владельцем;
remediation commit — `7ee5e27755f4bb8f18a0a3924f8b79a1eb8e5217`.

Strict clean-SHA certification на этом remediation SHA — **PASS**:

- `certification_mode = strict`;
- `certified = true`;
- `overall_status = passed`;
- source SHA start/end = `7ee5e27755f4bb8f18a0a3924f8b79a1eb8e5217`;
- source SHA stable = `true`;
- source tree clean = `true`.

Это сертифицированная база исправлений до текущего документационного закрытия,
а не SHA будущего коммита закрытия документации.

Независимый аудит после исправлений (independent post-remediation audit) —
**PASS**. Итоговые статусы: `S10-A01 CLOSED`, `S10-A02 CLOSED`,
`S10-A03 CLOSED`, `S10-A04 CLOSED`. Новых findings нет:
**BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0**.

Stage 10 — **DONE / CLOSED**; Macro 1, Macro 2 и Macro 3 —
**DONE / owner accepted**. Версия MVP остаётся `0.1.0`, поддерживаемая база —
Windows 11 x64 / Python 3.12 / CPU-only.

## Критерии готовности MVP

- [x] запускается на целевом компьютере;
- [x] принимает image/audio/video через предусмотренные каналы;
- [x] отклоняет неподдерживаемые файлы;
- [x] запускает утверждённые анализаторы;
- [x] формирует признаки;
- [x] формирует полноту, риск и рекомендацию;
- [x] сохраняет JSON;
- [x] показывает WebUI-результат;
- [x] удаляет временные данные;
- [x] проходит тесты, Ruff и mypy;
- [x] не требует необязательной инфраструктуры;
- [x] не выдаёт результат за окончательную экспертизу.

Macro 3 development evidence подтверждает запуск exact wheel без IDE,
image/audio/video через real HTTP, Profile B analyzers, полный result contract,
каноническую persistence, WebUI, cleanup и restart. Отклонение неподдерживаемых
входов и формирование findings/risk/recommendation уже покрыты закрытыми Stage
8–9 и общим regression barrier. Внешними prerequisites остаются только
утверждённые Python 3.12, uv и FFmpeg/ffprobe; предупреждение об отсутствии
окончательной экспертизы сохранено в WebUI и handoff.

## Критерий завершения

Прототип воспроизводимо устанавливается и демонстрирует полный цикл на подготовленных тестовых данных.

Критерий выполнен; Stage 10 закрыт. Следующим этапом стал Stage 11 — Post-MVP
Normalization & Hardening, описанный ниже.

---

# Stage 11 — Post-MVP Normalization & Hardening — DONE / CLOSED

## Цель и принцип

Преобразовать успешно завершённый staged MVP в целостную, долгоживущую
продуктовую кодовую базу, не потеряв гарантии, полученные на этапах 1–10.

На этом этапе не добавляются широкие новые продуктовые возможности. Stage 11
устраняет случайную сложность, остатки поэтапной разработки, подтверждённые
дефекты и угрозы масштабируемости при сохранении доказанного поведения.

Краткий принцип: **«Не добавлять возможности. Удалять случайность.»**

Post-MVP whole-codebase audit завершён с вердиктом
`READY_FOR_NORMALIZATION_PLANNING`: `BLOCKER 0`, `HIGH 0`, `MEDIUM 2`, `LOW 2`.
Отдельно классифицированы `ARCHITECTURE 4`, `TECH_DEBT 3`, `NORMALIZATION 1`,
`STYLE 1`, `DOCUMENTATION 2`, `TEST_QUALITY 2`, `DEFERRED 1`.

## Статус макрозадач

- Macro 0 — Roadmap Restructuring: **DONE / owner accepted**;
- Macro 1 — Confirmed Defect Remediation: **DONE / owner accepted**;
- Macro 2 — Runtime State Retention: **DONE / owner accepted**;
- Macro 3 — Analyzer Registration Normalization: **DONE / owner accepted**;
- Macro 4 — Product Naming & Architecture Normalization: **DONE / owner accepted**;
- Macro 5 — Technical Debt / Config / Test-Support Cleanup: **DONE / owner accepted**;
- Macro 6 — Tests / Comments / Documentation Normalization: **DONE / owner accepted**;
- Macro 7 — Release Tooling Normalization: **DONE / owner accepted**;
- Macro 8 — Final Whole-Project Audit / Certification / Graphify Review:
  **DONE / owner accepted**.

## Macro 0 — Roadmap Restructuring — DONE / owner accepted

Цель:

- [x] формально ввести Stage 11;
- [x] перенести существующие будущие работы Stage 11+ в Stage 12+;
- [x] зафиксировать scope Stage 11 и уже принятые owner decisions;
- [x] не изменять production-код и runtime-поведение.

Macro 0 завершён и принят владельцем. Реализация Macro 1–8 в него не входила.

## Macro 1 — Confirmed Defect Remediation — DONE / owner accepted

Четыре подтверждённых post-MVP аудитом дефекта исправлены и приняты владельцем.

- **D01 — MEDIUM — CLOSED.** `ffprobe` теперь корректно запрашивает disposition
  attached picture: реальный M4A с embedded cover art принимается как аудио, а
  поведение для настоящего видео остаётся защищённым.
- **D02 — MEDIUM — CLOSED.** WebUI HTTP Basic credentials намеренно ограничены
  ASCII; неподдерживаемые non-ASCII credentials безопасно отклоняются при
  startup.
- **D03 — LOW — CLOSED.** Патологическая вложенность `source_context` JSON
  отображается в существующий управляемый ответ
  `400 invalid_source_context_json`, а не выходит как text/plain 500.
- **D04 — LOW — CLOSED.** `AnalyzerConfigurationError` обрабатывается как
  управляемый CLI startup failure: Uvicorn не запускается, ожидаемые ошибки
  конфигурации не выходят как traceback.

Проверка закрытия: targeted regression suite — `219 passed`; полный pytest —
`1813 passed, 17 skipped`; coverage — `90%`; lock, Ruff, mypy, pre-commit,
smoke-проверки и diff-check — `PASS`; owner implementation review — `PASS`.

## Macro 2 — Runtime State Retention — DONE / owner accepted

Цель — устранить неограниченное удержание в RAM завершённых агрегатов
`AnalysisTask`.

Отдельное независимое исследование подтвердило:

- полное удержание `AnalysisTask` после `FINISHED` не требуется для штатного
  получения production-результата;
- удержание является историческим остатком staged lifecycle development/testing;
- завершённые задачи остаются под сильными ссылками `TaskRegistry`, поэтому его
  размер растёт с числом завершённых анализов;
- `gc.collect()` не может освободить задачи, пока ими владеет registry;
- это намеренное неограниченное логическое удержание, а не доказанная
  классическая потеря объектов Python GC.

**OWNER DECISION — после успешного `FINISHED` использовать только repository-only
semantics.** Предпочтительная архитектура:

```text
TaskRegistry = unfinished/live work
ResultRepository = completed history
```

После успешного persistence и terminal settlement необходимо согласованно
опубликовать `FINISHED`, сохранить только краткоживущие detached return data,
нужные текущему caller, и удалить полный завершённый агрегат из `TaskRegistry`.
Постоянный terminal cache, TTL, LRU/FIFO и конфигурация terminal-state retention
не вводятся.

Обязательные поведенческие условия:

- persistence по-прежнему предшествует `FINISHED`;
- persistence failure остаётся в `PERSISTENCE` и не вытесняется;
- unsafe/incomplete cleanup остаётся live и не вытесняется;
- успешно сохранённые completed/partial/failed outcomes следуют одному правилу
  вытеснения;
- fast submit поддерживает согласованный live-or-persisted status lookup;
- worker не удерживает предыдущую завершённую задачу неограниченно во время idle;
- получение после restart остаётся repository-backed.

**OWNER DECISION — missing result after eviction.** После `FINISHED` durable
source of truth — сохранённый repository:

```text
valid persisted result
→ normal terminal status/result

persisted result absent
→ 404 / not found

persisted result present but corrupt/unreadable/storage failure
→ controlled storage/internal error
```

Прежнее поведение, при котором RAM помнила о когда-то существовавшем удалённом
JSON, сохранять не требуется. Post-`FINISHED` registry inspection из Stage 5/6/7
больше не считается обязательным продуктовым контрактом.

Macro 2 завершён и принят владельцем. `TaskRegistry` теперь владеет только
незавершённой live/recoverable работой, а `ResultRepository` — завершённой
историей. Успешно сохранённые задачи после подготовленного commit `FINISHED`
точно удаляются из registry; terminal cache и политики TTL/LRU не добавлены.
Ошибка persistence оставляет задачу live в `PERSISTENCE`, а unsafe/deferred
cleanup — live/recoverable.

Terminal preparation завершается до persistence; после успешного `save()`
атомарно применяются подготовленный `FINISHED` и exact eviction. Repository-backed
чтения, включая fast-submit после быстрого eviction, сохраняют корректное
поведение, idle worker больше не удерживает завершённую задачу, а полная безопасная
проекция status errors сохранена. Owner review, независимый аудит и focused
remediation re-audits завершены; финальный независимый вердикт — **PASS**.

## Macro 3 — Analyzer Registration Normalization — DONE / owner accepted

Цель — сделать добавление собственных built-in анализаторов контролируемым и
локализованным.

**OWNER DECISION:** Stage 11 не вводит third-party plugin system, внешний plugin
loader, каталог `mods`, динамическую загрузку стороннего Python, plugin
marketplace/API или внешнюю расширяемость анализаторов. Все анализаторы остаются
first-party компонентами FakeDetector, которые разрабатываются, проверяются,
тестируются и поставляются вместе с продуктом.

Macro 3 завершён и принят владельцем. Один authoritative static internal catalog
теперь определяет production built-in анализаторы и остаётся закрытым доверенным
first-party каталогом. Plugin API, dynamic discovery и third-party loading не
введены.

В каталоге централизованы identity, version, media, factory, typed settings,
preprocessing requirements и trusted result-contract metadata. Runtime registry,
worker resolution, Stage 5 completeness и Stage 6 validation получают
соответствующие представления из нормализованного каталога. Порядок выполнения
по-прежнему определяется порядком конфигурации, а Stage 7 completeness использует
точный validated active analyzer plan.

Import-time construction production analyzer instances удалён. Согласованность
конкретной реализации с каталогом и worker-side validation созданного экземпляра
остаются обязательными. Алгоритмы анализаторов, публичные схемы,
API/config/CLI-контракты и семантика риска не изменены.

Implementation self-review, owner review, independent audit, remediation
`M3-AUD-001` и focused independent re-audit завершены; финальный независимый
вердикт — **PASS**.

## Macro 4 — Product Naming & Architecture Normalization — DONE / owner accepted

Macro 4 завершён, реализация закоммичена и принята владельцем. Текущие
production-модули реализации lifecycle переименованы из имён этапов разработки
в имена по ответственности; это внутренняя архитектурная нормализация, а не
ребрендинг продукта или изменение публичных контрактов.

Выполненные переименования:

```text
_stage5_resources.py → _generated_artifact_budget.py
lifecycle/_stage5.py → lifecycle/_analysis_execution.py
lifecycle/_stage6.py → lifecycle/_finding_formation.py
lifecycle/_stage7.py → lifecycle/_assessment.py
Stage5ExecutionService → AnalysisExecutionService
Stage6FindingService → FindingFormationService
Stage7AssessmentService → AnalysisAssessmentService
```

Связанные private transport/resource symbols также получили семантические
имена. A03 закрыт: общий mapping HTTP-статуса терминального исхода intake
перенесён в нейтральный внутренний `_http_status.py`. API и WebUI используют
одну HTTP-политику; WebUI больше не зависит от реализации API adapter.

Внешне наблюдаемые compatibility identifiers, включая `stage5_resource_limit`,
сохранены. Lifecycle state/data contracts `Stage5TaskData`, `Stage6TaskData` и
`Stage7TaskData` намеренно оставлены без переименования. Package name, CLI,
переменные окружения, analyzer IDs, схемы, API routes, формат сохранённого
результата, версия, auth, risk/completeness и lifecycle-поведение не изменены.
Compatibility shims, plugin architecture и новые зависимости не добавлены.
Исторические Stage-ссылки сохранены; `PROJECT.md` и `CONTRACTS.md` были точечно
синхронизированы в implementation commit.

Самопроверка реализации, полный просмотр diff владельцем и независимый
архитектурный/regression-аудит GPT-6 Astra Low завершены. Независимый аудит
подтвердил семантическую/AST-эквивалентность и импорты из установленного wheel;
финальный независимый вердикт — **PASS**. Итоговая валидация реализации:
`1848 passed, 17 skipped`, покрытие `90%`; lock, Ruff, mypy, pre-commit,
diff-check и CLI — `PASS`.

На момент закрытия Macro 4 Stage 11 оставался `IN_PROGRESS`; следующей задачей
был Macro 5, Technical Debt / Config / Test-Support Cleanup.

## Macro 5 — Technical Debt / Config / Test-Support Cleanup — DONE / owner accepted

Macro 5 реализован, закоммичен, принят владельцем и прошёл независимый аудит.
Точечная нормализация технического долга завершена:

- **TD01:** удалён подтверждённо мёртвый `_ALLOWED_MIME_TYPES`; поведение
  поддерживаемых MIME, форматов и сигнатур сохранено.
- **TD02:** поля и имена схемы `1.0` сохранены;
  `error_handling.hide_internal_error_details` допускает только `true`,
  `external_systems.enabled` — только `false`. Ранее неактивные противоположные
  значения отклоняются при валидации конфигурации. Defaults, `schema_version`,
  поддерживаемый канонический JSON и идентичность config snapshot не изменены.
  Раскрытие внутренних исключений и внешние интеграции не добавлены.
- **TD03:** framework fake-анализаторы и fake worker definitions вынесены из
  production-пакета и каталога в `tests/support`, отсутствующий в wheel.
  Production-каталог содержит только прежние четыре доверенных first-party
  built-in анализатора и не разрешает и не выполняет `framework_test.*`.
  Узкий private resolver с явной инъекцией сохраняет реальные Windows-spawn
  тесты. Plugin architecture, dynamic discovery, import-by-string, plugin entry
  points и управление resolver через конфигурацию не введены.

Сохранены analyzer IDs, версии, группы и production worker keys, закрытая
архитектура каталога Macro 3, имена по ответственности и HTTP-слои Macro 4,
поведение lifecycle/risk/completeness/persistence и публичные контракты
API/CLI/WebUI/result. Широкая очистка не выполнялась.

Целевая проверка реализации: `367 passed, 3 skipped`; независимый
целевой аудит: `295 passed`, без пропусков; полный набор тестов: `1864 passed,
17 skipped`, покрытие `90%`. Lock, Ruff, mypy, pre-commit, diff-check, CLI,
AST, canonical snapshot, pickle/spawn и installed-wheel checks — `PASS`.
Независимый аудит GPT-6 Astra Medium: финальный вердикт — **PASS**;
замечаний, требующих исправления, нет.

На момент закрытия Macro 5 Stage 11 оставался `IN_PROGRESS`; следующей задачей
был Macro 6, Tests / Comments / Documentation Normalization, тогда ещё не начатый.

## Macro 6 — Tests / Comments / Documentation Normalization — DONE / owner accepted

Macro 6 реализован, закоммичен, принят владельцем и прошёл независимый аудит.
Нормализация выполнена без изменения публичного поведения:

- Воспроизведён изолированный цикл `result_finalization → lifecycle →
  result_finalization`. Ненужный импорт `TerminalTaskFacts` во время выполнения
  перенесён под `TYPE_CHECKING`; оба порядка импорта проходят в свежих процессах
  Python. Документированный публичный Python-интерфейс не изменён; потребителей
  удалённого связывания во время выполнения или через рефлексию нет.
- Тестовые модули текущей реализации переименованы:
  `test_stage5_execution.py → test_analysis_execution.py`,
  `test_stage5_resources.py → test_generated_artifact_budget.py`,
  `test_stage7_assessment.py → test_analysis_assessment.py`.
  Восемь тестов владения артефактами, путей и очистки перенесены в
  `tests/test_workspace_artifacts.py` с сохранением 26 параметризованных случаев.
  Два AST-эквивалентных конфигурационных builder для intake объединены в
  `tests/support/intake.py`. Значимая логика, fixtures, assertions и параметризация
  сохранены; значимые тесты не удалены. Число собранных тестов выросло с 1881
  до 1883 только за счёт двух проверок порядка импортов в свежих процессах.
- Усилен реальный тест границы сохранения и живого реестра: в `PERSISTENCE`
  приоритет остаётся у `TaskRegistry`, получение результата ожидает завершения;
  после терминальной фиксации и удаления задачи авторитетным становится
  сохранённый результат `ResultRepository`.
- Текущие технические комментарии и docstrings production-кода нормализованы
  на английском по ответственности. Намеренные lifecycle Stage-контракты,
  совместимые имена, коды ошибок и исторические Stage/Increment-записи сохранены.
- Устаревшие текущие утверждения `PROJECT.md` и `CONTRACTS.md` сверены с
  production-архитектурой после Macros 1–5: закрытым каталогом четырёх анализаторов,
  исключительно тестовыми fake-анализаторами, обязанностями выполнения анализа,
  формирования признаков, оценки и финализации. Описания артефактов,
  предобработки и внешних систем синхронизированы; исторические записи сохранены.
- Финальный раздел `6. Команда агенту для продолжения разработки` удалён целиком,
  включая пояснение и блок инструкции. Definition of Done сохранён;
  связанного SVG не существовало.

Проверки реализации и аудита: изолированный `test_result_finalization.py` —
`15 passed`; целевой набор аудита — `286 passed, 1 skipped`; собрано `1883`
теста; полный набор — `1866 passed, 17 skipped`, покрытие `90%`.
`uv lock --check`, Ruff, mypy, pre-commit, `git diff --check`, CLI help и оба
порядка импортов в свежих процессах — `PASS`. Независимый аудит GPT-6 Astra Low:
финальный вердикт — **PASS**, замечаний, требующих исправления, нет.

На момент закрытия Macro 6 Stage 11 оставался `IN_PROGRESS`; следующей задачей
был Macro 7, Release Tooling Normalization (`NOT_STARTED / next action`).
Работы Macro 7 и Macro 8 тогда не были начаты.

## Macro 7 — Release Tooling Normalization — DONE / owner accepted

Нормализация release tooling завершена и принята владельцем. Полный diff
проверен владельцем — `PASS`; независимый аудит GPT-6 Astra Medium — `PASS`,
замечаний, требующих исправления, нет (`BLOCKER 0`, `HIGH 0`, `MEDIUM 0`, `LOW 0`).
Реализация зафиксирована в commit `abe8270e967470d12b4bed25e690f264e9b52849`.

В Macro 7 выполнены семантические переименования:

- `generate_stage10_demo_media.py` → `generate_release_demo_media.py`;
- `verify_stage10_package.py` → `verify_release_package.py`;
- `verify_stage10_release.py` → `verify_release.py`.

Текущие тесты release tooling также получили имена по ответственности.
Совместимые обёртки не оставлены: поддерживаемого внешнего контракта,
требующего старых имён файлов, не обнаружено. Прежний verifier размером около
2207 строк существенно декомпозирован: `scripts/verify_release.py` стал
высокоуровневым координатором, а реализация вынесена в закрытый пакет
`scripts/release_tooling/` с модулями `common`, `build`, `kit`, `environment`,
`demo`, `transport`, `server`, `probes`, `reporting`. Граф зависимостей ацикличен;
закрытые модули не импортируют координатор, инструменты остаются вне runtime
пакета продукта. Описание ответственности модулей — в `PROJECT.md`, §16.2.1.

Сохранены сертификационные гарантии:

- strict требует чистого дерева tracked и untracked файлов; development явно
  не сертифицирует; проверяются стабильность HEAD и source status, контракт
  хоста Windows 11 x64 workstation / Python 3.12;
- source → sdist → wheel из этого точного sdist; runtime constraints механически
  экспортируются из `uv.lock`; проверяются точный состав release kit,
  manifest schema `1.0`, SHA-256, безопасные ZIP validation и extraction;
- свежее внешнее venv, установка из точного проверенного извлечённого wheel,
  provenance установленного пакета, изоляция от checkout и равенство runtime
  dependencies;
- реальный установленный CLI, HTTP-проверки API/WebUI, анализ image/audio/video,
  persistence, получение прежних результатов после restart, cleanup,
  graceful shutdown и завершение принадлежащих проверке процессов;
- безопасное сокрытие секретов и итоговые проверки целостности исходного дерева
  и release kit.

Устранён узкий пробел владения процессом: если startup завершается исключением
после создания сервера, но до передачи владения координатору, обработка
`BaseException` завершает принадлежащий проверке процесс. Покрыты `RuntimeError`,
`KeyboardInterrupt`, `SystemExit`, `BaseException`, первоначальный и повторный
startup, эскалация terminate → bounded wait → kill. Двойного cleanup/reap не
обнаружено. Это усиление безопасности tooling, а не изменение поведения продукта.

Результаты проверок реализации: baseline — `1883 collected`,
`1866 passed, 17 skipped`, покрытие `90%`; итог — `1906 collected`,
`1889 passed, 17 skipped`, покрытие `90%`. Добавлены `23` граничных случая
release tooling. Целевые наборы: release demo handoff — `8 passed`, release
packaging — `4 passed`, release verification — `29 passed`, release tooling
boundaries — `23 passed`. Полный quality barrier: `uv lock --check`, Ruff,
mypy, pytest, pre-commit, `git diff --check`, product CLI help — `PASS`.

Строгая проверка после implementation commit командой
`uv run python scripts/verify_release.py` — `PASS`:
`overall_status=passed`, `certification_mode=strict`, `certified=true`,
`source_sha_stable=true`, `source_tree_clean=true`. SHA в начале и конце —
`abe8270e967470d12b4bed25e690f264e9b52849`; source status в начале и конце пуст.
Release gate не изменил состояние репозитория. Подтверждено:

- создан sdist, wheel собран из него, проверен точный wheel;
- release kit содержит ровно 8 файлов; manifest и ZIP проверены, имена членов
  безопасны, извлечение чистое, хэши совпали;
- создано свежее внешнее venv, установлен wheel из проверенного ZIP;
  editable install — `false`, checkout отсутствует в `sys.path`, сравнение
  зависимостей — `25/25`, установленных dev-only зависимостей нет;
- сгенерированы demo image/audio/video, запущен реальный установленный CLI
  server, проверены API/WebUI; анализ всех трёх типов завершён, canonical
  persistence подтверждён; после restart получены все четыре прежних результата,
  WebUI отобразил прежний результат;
- workspaces и остатки quarantine отсутствуют, demo media ограничены своим
  каталогом; два принадлежащих проверке серверных процесса завершены, listeners
  закрыты, широкая системная очистка не применялась;
- graceful shutdown через Windows `CTRL_BREAK_EVENT` подтверждён кодом возврата
  `3` и lifecycle shutdown markers.

Поведение runtime продукта не изменилось: API routes/schemas, WebUI behavior/auth,
config schema, persisted result schema, lifecycle, analyzers,
risk/completeness/recommendation, зависимости продукта и `uv.lock` сохранены.

На момент закрытия Macro 7 Stage 11 оставался `IN_PROGRESS`; Macro 8 имел статус
`NOT_STARTED / next action`. Строгая сертификация tooling Macro 7 не заменяла
финальную whole-project сертификацию Stage 11 / Macro 8; решение по Graphify
тогда было отложено.

## Macro 8 — Final Whole-Project Audit / Certification / Graphify Review — DONE / owner accepted

Macro 8 завершён и принят владельцем. Первоначальный whole-project audit дал
вердикт `REMEDIATE`: `M8-A01 MEDIUM`, `M8-A02 MEDIUM`, `M8-A03 LOW`, `M8-A04 LOW`.
Ограниченная ремедиация в commit
`0167f78e2ab18a7b297807e9cb3fa19f69b6a7ec` закрыла все четыре замечания:

| Finding | Статус | Исправление |
|---|---|---|
| M8-A01 — MEDIUM | CLOSED | Проверка provenance sdist отклоняет untracked, ignored и локально сгенерированное содержимое по принципу fail-closed; Graphify исключён из принимаемого sdist. |
| M8-A02 — MEDIUM | CLOSED | Владение сырым процессом release-server начинается сразу после `Popen`; при ошибках `BaseException` в создании wrapper/reader процесс завершается с обязательным ожиданием его выхода (reap). |
| M8-A03 — LOW | CLOSED | Глубокая рекурсия YAML преобразуется в безопасный `ConfigurationError`; CLI возвращает `2` без traceback и запуска сервера. |
| M8-A04 — LOW | CLOSED | Два неуместных текущих имени с хронологической Stage-терминологией заменены семантическими именами по ответственности. |

Проверка полного diff владельцем — `PASS`; независимый целевой повторный аудит
GPT-6 Astra High — `PASS`; strict clean-SHA certification — `PASS`; финальная
независимая проверка закрытия GPT-6 Astra High — `PASS`.
`STAGE_11_CLOSURE_RECOMMENDATION=YES`; все M8 findings — `CLOSED`.
Осталось замечаний, требующих исправления: `BLOCKER 0`, `HIGH 0`, `MEDIUM 0`,
`LOW 0`. `CURRENT_ARCHITECTURE_RESIDUE=0`; гарантии MVP A–R — `PASS`.

### Финальные результаты проверок

Итоговый набор: `1944 collected`, `1927 passed`, `17 skipped`, покрытие `90%`.
Полный quality barrier — `PASS`: `uv lock --check`, Ruff, mypy
(`65 source files`), pytest, pre-commit, `git diff --check`, product CLI help.
Целевые наборы: release packaging — `18 passed`, release verification —
`29 passed`, release tooling boundaries — `44 passed`, config / CLI / main —
`112 passed`.

Строгая сертификация командой `uv run python scripts/verify_release.py` на commit
`0167f78e2ab18a7b297807e9cb3fa19f69b6a7ec` завершилась с
`overall_status=passed`, `certification_mode=strict`, `certified=true`,
`source_sha_stable=true`, `source_tree_clean=true`. SHA в начале и конце совпал
с этим commit; source status в начале и конце пуст. Release gate не изменил
состояние репозитория. Подтверждены:

- состав sdist: `177` записей = `176` tracked файлов репозитория + корневой
  `PKG-INFO`; принятых Graphify entries — `0`; provenance и хэши исходников
  проверены, wheel собран из этого точного проверенного sdist;
- точный release kit из `8` файлов, manifest schema `1.0`, целостность SHA-256,
  безопасные проверка и извлечение ZIP;
- свежее внешнее venv, установка из точного извлечённого wheel;
  editable install — `false`, checkout отсутствует в `sys.path`, runtime
  dependencies — `25/25`, dev-only зависимости отсутствуют;
- реальный установленный CLI, реальные API и WebUI, анализ image/audio/video,
  canonical persistence и получение прежних результатов после restart — `4/4`;
- успешная очистка, завершение и reap двух собственных процессов, закрытые
  listeners; graceful Windows `CTRL_BREAK_EVENT`, ожидаемый return code `3`;
  широкая системная очистка не применялась.

Это предоставленные финальные технические результаты до документационного
закрытия. После commit документации владелец выполнит финальную строгую
сертификацию на новом чистом SHA.

### Graphify — принятая владельцем REBUILD_POLICY

Финальная рекомендация `GRAPHIFY_RECOMMENDATION=REBUILD_POLICY` принята владельцем.
Текущий локальный граф — `STALE`: он не является достоверным доказательством
архитектуры. Graphify остаётся вспомогательным инструментом, не production
dependency. `graphify-out/` остаётся ignored; сгенерированные данные должны
оставаться ignored/untracked и не попадать в source distributions. Это включает
`graph.json`, `graph.html`, cache, memory, reflections, generated learning data
и локальные маркеры interpreter/root.

Генерация выполняется только вручную и явно после существенных изменений
структуры модулей, composition, импортов, lifecycle, каталога анализаторов,
release tooling или нормативных архитектурных контрактов. При генерации
фиксируются source/build SHA либо эквивалентный fingerprint исходников.
Статус `CURRENT` допустим только при соответствии provenance текущим исходникам;
иначе граф считается `STALE` и не используется как архитектурное доказательство.
Валидация должна проверять охват исходников/модулей, существование путей и
символов, provenance генератора и его версии, а также репрезентативные связи.
В рамках этого закрытия Graphify не пересобирался; команда генерации не задаётся.

## Гарантии MVP, обязательные к сохранению

Финальная проверка Macro 8 подтвердила `PASS` для всех гарантий A–R
(ниже перечислены в том же порядке):

- единый `AnalysisApplicationService` для API и WebUI;
- immutable config snapshot;
- различие status/stage/completeness/risk;
- detached/canonical reads;
- exactly-once execution и terminal settlement;
- cleanup safety barriers;
- порядок `FACT_READY → PERSISTENCE → save → FINISHED`;
- live precedence, пока работа не завершена;
- canonical persisted result после завершения;
- atomic result write и identity validation;
- bounded worker protocol;
- trusted/closed analyzer catalog;
- subprocess/artifact/finding safety budgets;
- correlation handling без двойного учёта;
- запрет fake calibrated probability claims;
- safe diagnostics;
- installed-wheel release guarantees;
- negative failure-path tests.

Этот список фиксирует границы Stage 11 и не заменяет подробные контракты в
`CONTRACTS.md`.

## Критерий завершения

Критерий выполнен: Stage 11 — **DONE / CLOSED**, Macros 0–8 —
**DONE / owner accepted**; текущего Macro нет. Основания закрытия:
post-MVP whole-project audit, нормализация Macros 1–7, финальный аудит Macro 8,
ограниченная ремедиация и независимый целевой повторный аудит, полный quality
barrier и строгая сертификация установленного артефакта. Финальная проверка
GPT-6 Astra High — `PASS`, рекомендация закрыть Stage 11 — `YES`.
Замечаний, требующих исправления, осталось `0`;
`CURRENT_ARCHITECTURE_RESIDUE=0` (неуместных текущих архитектурных имён с историей
Stage нет); гарантии MVP A–R — `PASS`. Принята политика Graphify `REBUILD_POLICY`.

---

# Stage 12 — Analyzer Expansion, Licensing & Product Validation — IN_PROGRESS

## Цель и границы

Расширить текущие четыре анализатора до разнообразного объяснимого набора
детерминированных/классических проверок изображений, аудио и видео. Центр этапа —
анализаторы; предобработка, лицензирование, WebUI, продуктовая проверка и поставка
служат этой цели. Принятые архитектурные ограничения находятся в `PROJECT.md`
§20.1–20.2; интерфейсы и точная семантика результата — в `CONTRACTS.md`.

Текущий подтверждённый каталог (`src/fakedetector/analyzers/_catalog.py`):

- `image_metadata_consistency@1.0.0`;
- `image_copy_move_correspondence@1.0.0`;
- `audio_pcm_quality@1.0.0`;
- `video_sampled_frame_quality@1.0.0`.

Macro 0 не изменяет этот каталог, предобработку, WebUI или локализацию.
В Pass 2 разрешены только лицензионные metadata, включение LICENSE в поставку
и соответствующие release-тесты; публикация не выполняется.
Stage 12 не реализует ML и не добавляет ML runtime,
веса, GPU-требования или загрузки моделей; исследовательский каталог ML
допустим, реализация отложена в Stage 13+. Калибровка вероятности, новая
инфраструктура и интеграции не становятся частью этапа автоматически.

## Карта Macro и зависимости

| Macro | Название | Статус | Вход / результат и критерий перехода |
|---:|---|---|---|
| 0 | Stage Definition, Licensing & Third-Party Policy | DONE | План и политика оформлены; Apache-2.0 выбрана; лицензионная поставка и provenance проверены |
| 1 | Forensic Preprocessing Foundations | IN_PROGRESS | M1-A–M1-D DONE; следующий increment M1-E, owner blockers отсутствуют |
| 2 | Image Analyzer Expansion — Wave 1 | NOT_STARTED | После 1: согласованный набор image-методов, provenance, применимость, признаки и тесты |
| 3 | Audio Analyzer Expansion — Wave 1 | NOT_STARTED | После 1 и планового закрытия 2: согласованный audio-набор на общих представлениях |
| 4 | Video Analyzer Expansion — Wave 1 | NOT_STARTED | После 1–3: временные/контейнерные проверки и переиспользование image/audio-ядер |
| 5 | Analyzer Wave 2 / Experimental Promotion | NOT_STARTED | После 2–4: обоснованный отбор второй волны, проверка экспериментальных методов и допуск в доверенный каталог |
| 6 | Correlation, Completeness & Result Semantics Review | NOT_STARTED | После 2–5: проверка выросшего набора без двойного учёта и завышения полноты; изменения дизайна только отдельным решением |
| 7 | WebUI Product Layer / Localization / Human-readable Results | NOT_STARTED | После 6: согласованное представление результата, RU/EN и проверка неизменности API/domain semantics |
| 8 | Real Corpus & Hands-on Product Acceptance | NOT_STARTED | После 5–7: корпус с проверенными правами, воспроизводимые измерения и формальная ручная приёмка |
| 9 | GitHub Release / Distribution | NOT_STARTED | После 0 и 8: проверенная поставка, лицензии/уведомления и отдельный шаг публикации владельцем |
| 10 | Final Whole-Stage Audit & Certification | NOT_STARTED | После 0–9: независимый аудит, закрытие замечаний, quality barrier, сертификация установленного артефакта и решение о закрытии Stage 12 |

Общая предобработка обязательно предшествует массовой реализации анализаторов.
Macro 2 и 3 технически опираются на 1, последовательность выше — план выполнения;
зависимости общих ядер уточняются при отборе методов. Подготовка критериев корпуса
может сопровождать волны, но не заменяет формальную приёмку Macro 8. Macro 6
не разрешает откладывать известный двойной учёт до конца волн: каждый новый метод
должен заранее описать семейство свидетельств и связь с текущей корреляцией.
Macro 9 не разрешает публикацию в Macro 0; любые Git mutations выполняет владелец.

## Macro 0 — DONE

- [x] формально открыть Stage 12 и определить Macro 0–10;
- [x] записать принятые направление и границы в `PROJECT.md`;
- [x] разделить текущий каталог, исследовательские кандидаты и будущую реализацию;
- [x] оформить политику provenance, текущий аудит и сравнение лицензий в `REFERENCES.md`;
- [x] сохранить наблюдения ручного знакомства с продуктом в будущем backlog;
- [x] получить явный выбор лицензии проекта владельцем: Apache-2.0;
- [x] отдельным проходом оформить лицензию, metadata, README и стратегию
  сторонних уведомлений; проверить состав/ожидания release kit и при необходимости
  согласованно обновить их;
- [x] проверить согласованность, diff и относящиеся к этому проходу проверки,
  затем закрыть Macro 0.

Первый проход ограничивался документацией/политикой. В Pass 2 владелец выбрал
Apache-2.0; добавлены канонический `LICENSE`, SPDX metadata и обязательная лицензия
в составе kit. Проверяются реальные sdist/wheel, точный состав kit, хэши,
соответствующие release-тесты, diff и согласованность документов.
Отдельный пустой NOTICE не требуется; стратегия — в `REFERENCES.md`.
Полный набор тестов и пересборка Graphify не запускаются. Строгая сертификация
требует чистого tracked source tree и выполняется после Git-действий владельца.

Результаты Pass 2 до Git-действий владельца:

- `LICENSE` побайтово совпадает с официальным текстом Apache — `PASS`;
- сборка sdist и wheel из sdist, SPDX metadata и содержимое лицензии — `PASS`;
- фактическая сборка kit/ZIP, точный inventory, manifest-хэши и извлечение — `PASS`
  в несертифицирующей проверке;
- Ruff для изменённых Python-файлов и `git diff --check` — `PASS`;
- профильные `test_release_packaging.py`, `test_release_verification.py`,
  `test_release_tooling_boundaries.py`, `test_release_demo_handoff.py`:
  **98 passed, 1 failed**. Единственная остановка — существующий
  `_verify_sdist_provenance` отклоняет новый untracked `LICENSE`;
  проверка и её требование tracked source сохранены.

Финальный проход закрытия: владелец добавил только новый корневой `LICENSE`
в Git. Команда `uv run pytest -q tests/test_release_packaging.py
tests/test_release_verification.py` прошла: **47 passed**, включая ранее
остановившуюся проверку provenance. Начальный и итоговый `git diff --check` —
`PASS`. Ограничение проверки устранено; блокеров владельца нет. Macro 0 —
`DONE`, Stage 12 — `IN_PROGRESS`, следующий Macro 1 — `NOT_STARTED`.
В финальном проходе изменён только `ROADMAP.md`; Git mutations агент не выполнял.
Строгая release certification на грязном source tree не запускалась.

## Исследовательский вход и отбор волн

Владелец передал достаточную для планирования сводку отдельного read-only
исследования: 20 image-, 14 audio-, 14 video-кандидатов и 23 темы ML для Stage 13+.
Полный отчёт в этот проход не приложен; числа — сведения из задания, а не
результат нового исследования Macro 0. Кандидаты намеренно пересекаются по
семействам свидетельств. Лицензионные ограничения Noiseprint и PhotoHolmes
зафиксированы отдельно в `REFERENCES.md` как исследовательские сведения.

Предложенный вход первой волны, **не утверждённые analyzer IDs/контракты или
обязательные пакеты реализации**:

| Направление | Рабочие названия кандидатов |
|---|---|
| Image / Macro 2 | `image_jpeg_double_quantization`, `image_jpeg_grid_consistency`, `image_noise_residual_consistency`, `image_resampling_consistency`, `image_embedded_thumbnail_consistency` |
| Audio / Macro 3 | `audio_temporal_discontinuity`, `audio_spectral_consistency`, `audio_background_noise_consistency`, `audio_repeated_segment_correspondence`, `audio_metadata_container_consistency` |
| Video / Macro 4 | `video_encoding_structure_consistency`, `video_timestamp_consistency`, `video_motion_consistency`, `video_audio_timing_consistency` |
| Расширение текущего / Macro 4 | усиление анализа повторов/замирания в ответственности `video_sampled_frame_quality`, без дублирующего анализатора |

Перед каждой волной согласуются конкретные методы и IDs, входные представления,
CPU/resource budgets, применимость и ограничения, семейства свидетельств,
права на код/данные и критерии проверки. Для каждого допускаемого метода нужны
положительные, отрицательные, ложноположительные/challenge, граничные и
`not_applicable` случаи; отсутствие пригодного сигнала не доказывает подлинность.
Macro 5 продвигает только прошедшие эти критерии методы; остальные остаются
исследовательскими кандидатами с записанной причиной отсрочки.

## Macro 1 — общая криминалистическая предобработка — IN_PROGRESS

Текущие представления описаны в `CONTRACTS.md` §7: нормализованный PNG,
16-bit PCM, необязательная спектрограмма и разреженные кадры с целевыми
временными отметками. Они не дают автоматически все факты для новых методов.
Macro 1 должен определить необходимые расширения до зависимых волн:

- исходные/native JPEG-факты и действительно исходные квантованные JPEG
  коэффициенты для анализа DCT/квантования; DCT нормализованного PNG не подменяет их;
- достоверное соответствие координат исходного и нормализованного изображения,
  включая ориентацию, и общие остаточные/фильтрующие вычисления;
- числовые STFT/оконные представления, а не только изображение спектрограммы;
- аудио с точностью исходника там, где проверяется подлинность разрядности:
  преобразованный 16-bit PCM не является доказательством исходной bit depth;
- измеренные PTS/DTS/time-base/frame-duration, ограниченные плотные окна
  последовательных видеокадров и соответствие video/audio timelines;
- общие image/audio forensic kernels для повторного использования в видео.

Для каждого расширения определить производителя и потребителей, сохранность
исходных фактов, формат внутренних данных, применимость, точность координат/
времени, лимиты, контролируемый доступ и очистку. Контрактные изменения
оформляются в задаче Macro 1 по мере необходимости, не придумываются в Macro 0.
Парсинг, ffprobe, STFT и декодирование не размножаются внутри анализаторов.

### Pass 1 — аудит и план реализации

Baseline: `a66295ed8a7165d078f714fe4f212675ea8fffdc`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, исходное рабочее дерево
чистое. В Pass 1 были сформулированы **предложения и критерии будущих задач**;
принятые позднее внутренние контракты M1-A находятся в `CONTRACTS.md` §7.5.
Реализация анализаторов, новая публичная схема и повышение текущих
лимитов этим проходом не разрешаются. Проверенные сведения о JPEG-кандидатах
и отдельном installed-wheel smoke находятся в `REFERENCES.md`.

Предлагается сохранить владельца подготовки `PreprocessingDispatcher` и
существующий путь `PreparedMedia → private worker transport → AnalyzerRequest`.
Небольшие immutable facts проходят строгую типизированную проекцию в существующую
metadata-границу; большие числовые данные — зарегистрированные артефакты с
ограниченными manifest и readers. Новые артефакты создаются только по объединённым
требованиям активного закрытого каталога. Residual/STFT kernels могут вычислять
числовые порции внутри существующего analyzer worker из этих представлений;
постоянно сохранять каждую производную матрицу не требуется.

### Решения владельца перед реализацией — RESOLVED

| Gate | Утверждённый выбор | Статус |
|---|---|---|
| G1 — native JPEG | `pyjpegio==0.3.0` в M1-B, bounded private child и preflight | APPROVED; зависимость не добавляется в M1-A |
| G2 — численные зависимости | NumPy/OpenCV, без SciPy | APPROVED |
| G3 — точность аудио | Hybrid: source/decoder facts + precision-preserving windows; старый PCM16 сохраняется | APPROVED |
| G4 — timing owner | Preprocessing с существующей bounded process boundary | APPROVED |
| G5 — контракты | Только внутренние типы/requirements/readers; public API/domain/YAML без изменений | APPROVED |

Условия решений и реализованные внутренние контракты находятся в
`CONTRACTS.md` §7.5. Таблица закрывает owner gates и не означает готовность B–F.

Выбор G1 не разрешает прямой вызов native decoder в родительском процессе,
передачу raw markers анализаторам или приём коэффициентов после предупреждений
декодера. У проверенного wheel выявлены soft recovery отсутствующего EOI и
ограничение Unicode absolute path; M1-B должен проверять строгий отказ и запуск
из controlled source workspace с существующим фиксированным ASCII-именем
`source`, без копирования исходника или изменения cwd родителя.

### Последовательность M1-A–M1-H

M1-A, M1-B, M1-C и M1-D — `DONE`; E–H остаются `NOT_STARTED`.
Macro 1 — `IN_PROGRESS`.

| Increment | Зависимости | Проверяемый результат |
|---|---|---|
| M1-A — contracts/models/limits — DONE | Решения G1–G5 | Типизированные immutable facts, manifests и контракты будущих readers, applicability/coverage, source identity, пределы чисел/размеров; общий demand plan и бюджет до записи; уточнение внутренних контрактов без public schema expansion |
| M1-B — original image/JPEG — DONE | A, G1/G4 | Ограниченные исходные факты, EXIF mapping всех 8 ориентаций, native quantized coefficients и таблицы с component/table IDs; изолированный decoder, общее bounded stderr для строгой обработки warnings, Unicode workspace и installed-wheel smoke |
| M1-C — residual kernels — DONE | A, mapping из B | Небольшие собственные детерминированные residual/filter kernels с явными dtype, границами, halo и областью покрытия; без Noiseprint и копирования чужих ограниченных реализаций |
| M1-D — audio precision/STFT — DONE | A, G2/G3 | Source/decoded sample-format facts, точные sample indices и дополнительные окна; общий framing/window/rFFT/magnitude/power API, без чтения spectrogram PNG и без принудительного downmix/resample |
| M1-E — bounded timing | A/B, G4 | Типизированные stream/packet/frame facts, signed PTS/DTS и rational time base; bounded ffprobe и переиспользование общей sideband-границы из B для timing; без raw JSON в analyzer inputs |
| M1-F — dense windows/AV mapping | B/C/D/E | Ограниченные последовательные кадры из одного decode на окно с подтверждённой связью pixels/timestamps; mapping audio sample indices и video timeline, обработка offsets/discontinuities и неизвестных значений |
| M1-G — integration/hardening | B–F | Совместные count/byte/CPU budgets, безопасная сериализация, timeout/overflow/crash/reap/cleanup matrix, существующие consumers без изменения поведения; sdist → wheel → внешняя runtime-среда без checkout и dev packages |
| M1-H — independent closure audit | G | Отдельный независимый read-only аудит, отсутствие незакрытых findings, проверка критериев Macro 1 и решение о закрытии |

Точный следующий implementation increment — отдельная задача
**M1-E: bounded timing**. A задаёт общие contracts/limits для B–F;
точные реализованные ограничения принадлежат `CONTRACTS.md` §7.5. Предложения
Pass 1 ниже сохраняются как критерии дальнейшей проверки A/G, не production
sampling defaults и не новые YAML-поля.

### M1-A — internal contracts, demand plan, resource policy — DONE

Baseline: `5c8bf5d909478268eb91112fb90f286f09f4e4eb`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, рабочее дерево
перед реализацией чистое. Расширены существующие requirements/registry,
добавлены строгие immutable facts и bounded numeric descriptors, source/artifact
binding в текущей metadata-границе, EXIF edge/bbox mapping и арифметический JPEG
preflight с MCU-padding. Новые producers не реализованы; текущий каталог их
не запрашивает. Dependencies, public contracts и YAML не менялись.

Проверено 2026-09-21: focused tests (`test_stage5_internal_models.py`,
`test_analyzer_registry.py`, `test_preprocessing.py`) — **219 passed**.
Окончательный `uv run poe check` — **PASS**: pre-commit, mypy (65 source files),
pytest **2068 collected / 2051 passed / 17 skipped**, покрытие **90%**, CLI smoke.
Проверены итоговый diff, scope, отсутствие ненужных compatibility paths и новых
public exports; `git diff --check` — PASS. Release certification и пересборка
Graphify не запускались. Git mutations не выполнялись. M1-A завершён;
Stage 12 и Macro 1 остаются `IN_PROGRESS`, owner blockers отсутствуют.

### M1-B — original image/JPEG — DONE

Baseline: `50d2fb77624193a99c9ab821582e39546d54bc44`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, начальное дерево чистое.
Выполнен утверждённый объём M1-B: original facts/EXIF, структурный JPEG preflight,
native coefficients по явному demand, bounded child, raw artifacts и immutable
reader. Thumbnail extraction/comparison и forensic conclusions не входят в это
задание и не реализованы. Текущие четыре analyzers и public contracts сохранены.
Точный внутренний контракт — `CONTRACTS.md` §7.5; provenance и измерения памяти —
`REFERENCES.md`, интеграция M1-B.

Проверено 2026-09-21:

- focused preprocessing/models/process/registry — **348 passed**;
- дополнительные 12 interruption/recovery cases — **PASS**; Windows stdlib
  process probes запускают реальный interpreter, исключая venv redirector;
- `uv run poe check` — **PASS**: pre-commit, mypy (65 source files), pytest
  **2137 collected / 2120 passed / 17 skipped**, покрытие **90%**, CLI smoke;
- `uv run python scripts/verify_release_package.py` — **PASS**: проверенный
  inventory/hash sdist → wheel, внешний CPython 3.12.10 venv, 26 runtime
  distributions точно соответствуют lock-derived constraints, dev packages
  отсутствуют, imports из site-packages, checkout отсутствует в sys.path;
- установленный wheel: progressive RGB 17×17, malformed missing EOI,
  over-limit SOF, Unicode workspace и cleanup — **PASS**;
- preflight spy подтверждает отсутствие native вызова при structural/resource
  rejection; 2047/2048/2049×2048 grayscale проверяют границу policy;
- safe warning/error/crash/timeout/protocol/overflow, partial artifact cleanup,
  source/artifact binding и запрет writable numeric buffer — **PASS**.

Измеренный peak working set дочернего процесса для трёх fixtures — около 66–75 MiB; это не
hard RAM quota. В M1-G остаются общий RSS/concurrency и native allocation risks,
а также strict clean committed-tree certification: эта проверка честно выполнена
на изменённом working tree (`source_tree_clean=false`). Provenance guards не
ослаблены. Git mutations и пересборка Graphify не выполнялись. Owner blockers
отсутствуют; Stage 12 и Macro 1 остаются `IN_PROGRESS`. Следующим increment был M1-C.

### M1-C — shared deterministic image residual kernels — DONE

Baseline: `23070b84dc322adf42d5cdbe56970fdcf538baa8`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, начальное дерево чистое.
Добавлен один private NumPy-слой для bounded tiles, BT.601 luminance, binomial
smoothing 3×3/5×5, high-pass residual, центральных конечных разностей и robust
local statistics. Tile boundary использует фиксированный `REFLECT_101`; kernel
outputs покрывают ровно core, RGBA alpha не участвует в сигнале. Все числовые
результаты — finite immutable little-endian float64 с `bytes` backing. Точный
numeric/resource contract находится в `CONTRACTS.md` §7.5.

Проверено 2026-09-21:

- focused kernel tests — **52 passed**;
- focused kernels + analyzer registry + все текущие production analyzers —
  **170 passed**;
- `uv run poe check` — **PASS**: pre-commit, mypy (65 source files), pytest
  **2189 collected / 2172 passed / 17 skipped**, покрытие **90%**, CLI smoke;
- максимальные raster/tile/count/halo limits проверены ниже, на границе и выше;
  workspace preflight, pathological dimensions, strided input, invalid dtype/
  shape, `NaN`/`Inf`, border, alpha и immutable buffers покрыты тестами;
- итоговый diff и `git diff --check` проверены; public API/schema/YAML,
  normalized image pipeline, четыре analyzer `1.0.0`, risk и completeness не
  изменены.

Новых зависимостей и provenance нет; `CHANGELOG.md` и `REFERENCES.md` не
изменялись. Release certification и пересборка Graphify не запускались. Git
mutations не выполнялись. Owner blockers отсутствуют; Stage 12 и Macro 1
остаются `IN_PROGRESS`. Следующим increment был M1-D.

### M1-D — source-precision audio и numeric STFT foundations — DONE

Baseline: `51f3d24a40eb50893285c5b6ec1c1b0284ae12d7`, ветка
`feat/stage12-macro1-forensic-preprocessing-foundations`, начальное дерево чистое.
Реализованы source/decoder facts, дополнительные precision-preserving окна,
общие immutable framing/periodic Hann/rFFT/magnitude/power kernels и demand-driven
подготовка raw numeric artifacts. Контракт принадлежит `CONTRACTS.md` §7.5;
сведения об используемых интерфейсах — `REFERENCES.md`.

Проверены PCM8/16/24/32, float32/64 без clipping, lossy decode, mono/stereo/8
channels, 192 kHz, begin/middle/end и перекрытия, фактические короткие окна,
малформатный/truncated input, timeout/overflow и unresolved process barrier.
Проверены framing/tail, Hann coefficients, DC/single-bin sine, magnitude/power,
finite values, immutable backing, provenance identity и resource preflight.
Production demand не активирует новые producers; PCM16/fragments/PNG spectrum
совпадают с прежними байтами на regression fixture. Новые анализаторы, Findings,
public API/domain/config и runtime dependencies не добавлялись.

Итоговый `uv run poe check`: **2255 passed, 17 skipped, coverage 90%**;
pre-commit, Ruff, mypy (65 source files) и CLI smoke — PASS. Штатный packaging
regression (sdist → wheel → install/import) также прошёл; отдельная strict
release certification не запускалась. Реализация и тесты размещены в существующих
tracked файлах, release provenance policy не менялась. Git mutations и
перестройка Graphify не выполнялись.

Ограничения: выборочное покрытие, отказ для неизвестного/s64 decoder format и
неподтверждённой непрерывности PTS; короткое окно без полного FFT frame не создаёт
spectral artifact. Общий native RSS/concurrency остаётся предметом M1-G.
Owner blockers отсутствуют. Stage 12 и Macro 1 остаются `IN_PROGRESS`.
Следующий increment — **M1-E: bounded timing**.

### Критерии ресурсов и достоверности для A/G

- Сохранить общий предел **256** generated artifacts и
  `B_m = limits.max_file_size_mb[m] * 1_048_576` на все созданные файлы задачи,
  включая текущие normalized/fragments/frames. Дополнительного независимого
  бюджета не вводить. Уменьшение precision ради помещения в бюджет запрещено;
  превышение сохраняет существующий `stage5_resource_limit`.
- Небольшие facts/manifests вместе с прежней metadata должны помещаться в
  **32 768 байт**; file facts — **16 384**, settings — **8 192**.
  Ответ analyzer worker — **65 536**, canonical result — **65 509 байт**.
  Большие arrays и таблицы событий не входят в ответ или `raw_metrics`.
- Каждый новый binary reader проверяет формат, shape, dtype/endian, длину,
  арифметическое переполнение и принадлежность artifact ID до выделения памяти;
  object arrays/pickle, произвольные пути и raw EXIF/XMP/ICC запрещены.
- JPEG: стартовый профиль — input не больше `min(32 MiB, input limit)`, до
  256 markers/scans и 1 MiB совокупных marker payload, до 4 компонентов/таблиц
  и `2^22` коэффициентов всех компонентов суммарно. Это до **16 MiB int32**
  перед расходом общего бюджета; учитывать также native buffers и полную копию
  сжатого JPEG. Thumbnail: до 512 KiB encoded и 512×512 decoded pixels.
  Предварительная оценка проверяется до native allocation; crop после decode
  не считается memory bound. Необычные coding modes и переопределение таблиц
  между scans требуют явной применимости, не приблизительных коэффициентов.
- Residual: стартовый tile ≤512×512 с halo ≤2 для kernels ≤5×5, до 16 tiles;
  вычисление float64 с оценкой временных массивов ≤32 MiB. Общий reader
  допускает ≤`2^22` decoded raster pixels для этого профиля и учитывает память
  целого RGB/RGBA raster отдельно: вырезание tile после полной загрузки
  изображения само по себе не ограничивает память. Производные residual arrays
  выдаются порциями, постоянная полная карта не создаётся автоматически.
- Audio: до 3 окон по ≤10 секунд, каждое ≤`2^20` samples суммарно по каналам,
  rate ≤192 kHz, channels ≤8. Float64 занимает до 8 MiB на окно; native integer
  precision хранится без потерь в int32. Это дополнительные представления,
  не новые условия Stage 3 admission. STFT: `n_fft ≤4096`, `hop ≥n_fft/4`,
  до 8192 time/channel frames, batch ≤32, без полной STFT в памяти.
  Учитывать complex128 workspace NumPy; границы окон и channel policy явные.
- Timing: до 3 областей, на выбранный stream/область до 256 packets и
  512 frame records; до 2 streams, общий предел 4608 records. Каждый ffprobe
  output ≤256 KiB, общий typed timing artifact ≤1 MiB. Сохранять фактически
  прочитанные границы: `read_intervals` seek не гарантирует запрошенный start.
  Переполнение не превращать в успешно разобранный обрезанный JSON.
- Dense video: до 3 окон, ≤32 последовательных кадров и ≤2 секунд на окно,
  максимум 96 кадров; дополнительный RGB24 raster внутри 640×360 с сохранением
  aspect ratio, без upscale. Максимум pixels output — **66 355 200 байт**
  плюс manifests, всё внутри `B_video`; обрабатывать rolling batches, не весь
  набор сразу. Native decode gate — до 3840×2160, включая изменение размеров
  потока; resize после decode не гарантирует низкий native RSS. Размеры,
  scaling/color conversion и фактическое покрытие всегда сохраняются.
- Потолки дают проверяемые объёмы данных: 16 MiB coefficients, 8 MiB sample
  window, примерно 63.3 MiB всех dense RGB frames. Их применимость и пиковый RSS
  нужно измерить вместе с существующими артефактами и configured concurrency;
  они не обещают hard OS RAM quota и не гарантируют покрытие всего входа.
- Все операции получают `min(operation timeout, remaining overall budget)`.
  Стартовые потолки для проверки: 15 s на probe, 30 s на native JPEG/window decode;
  residual/STFT выполняются внутри существующего bounded analyzer invocation.
  Seek/preroll, native allocation и задержка декодера учитываются отдельно от
  числа выходных кадров; короткий output не означает короткую работу.

### Критерии закрытия Macro 1

- [x] Решения G1–G5 рассмотрены и записаны в соответствующих источниках истины.
- [ ] A–G выполнены; first-wave consumers имеют конкретные входные представления,
  но сами новые анализаторы в Macro 1 не реализованы.
- [x] EXIF 1–8, non-square image, component subsampling/padding и преобразование
  native bbox в normalized coordinates проверены; native JPEG DCT не вычисляется
  из PNG и не меняет координатную систему молча.
- [x] Residual kernels ограничены tiles/halo/workspace, имеют фиксированные
  dtype/range/border/coverage и immutable outputs; grayscale/RGB/RGBA, alpha,
  determinism, finite validation и resource boundaries проверены без Findings.
- [x] Проверены baseline/progressive/grayscale JPEG, non-contiguous quant table
  IDs, malformed/truncated/oversized input, native warnings/crash/timeout и
  Unicode workspace. Source markers не попадают в logs/results.
- [ ] Проверены integer PCM 8/16/24/32, float samples, silence/impulse/tone,
  stereo/channels, последние неполные окна и отсутствие потери >16-bit evidence;
  ffprobe sample format не выдаётся за effective bit depth или историю монтажа.
- [ ] Проверены CFR/VFR, B-frame reorder, missing/negative/duplicate timestamps,
  discontinuities, ненулевые разные stream starts, отсутствие audio, короткий
  EOF и long-GOP seek. Timing и dense frames связаны одним decode, не только
  совпадением порядковых номеров двух независимых запусков.
- [ ] Derived duration/drift отличается от metadata/decoder facts; разрывы между
  отдельными окнами не выдаются за наблюдавшиеся discontinuities. Ни `avg_frame_rate`,
  ни совпадение длительностей не доказывают CFR/AV synchronization.
- [ ] Все новые файлы зарегистрированы до записи и очищаются существующим lifecycle;
  одновременный stdout/stderr ограничен, overflow/timeout подтверждают reap,
  unresolved reader сохраняет cleanup safety barrier.
- [ ] Требования активного каталога объединяются до подготовки, каждый общий
  артефакт создаётся один раз; текущие четыре analyzers и public semantics сохранены.
- [ ] Проверены installed-wheel execution, import origin и lock-derived runtime
  constraints; лицензии точных native artifacts оформлены; нет checkout dependency,
  моделей, ML runtime, новых конфигурационных полей или параллельного storage.
- [ ] M1-H завершён без незакрытых findings; Macro 1 закрывается отдельным решением.

В Pass 1 не запускались project test suite, release certification и пересборка
Graphify. Изменения реализации и Git mutations не выполнялись.

## Macro 6 — корреляция и смысл результата

Размер портфеля не равен числу независимых свидетельств. ELA, double
quantization, JPEG grid и JPEG ghost могут отражать общую историю JPEG-обработки;
audio temporal/spectral/background transitions — одну границу монтажа.
Видеообёртки image/audio-ядер должны сохранять исходное семейство свидетельств,
а не добавлять независимый голос только из-за `media=video`.

До отдельно утверждённого изменения действуют точные правила
`CONTRACTS.md` §11.4. Семейство свидетельств здесь — понятие планирования,
не новое поле схемы и не автоматическая группировка по сходству названий.
Macro 6 проверяет взаимодействия методов, отсутствие повторных вкладов,
честную полноту активного профиля, ограничения и формулировки рекомендаций.
Macro 0 не изменяет веса, пороги, `correlation_group` или риск-движок.

## Macro 7–8 — наблюдения ручного знакомства с продуктом

2026-09-20 владелец собрал сертифицированный ZIP, распаковал его вне репозитория,
создал чистое venv, установил wheel с runtime constraints, выполнил
`uv pip check`, запустил установленный CLI, открыл WebUI и попробовал
image/audio/video. Это **неформальное знакомство с продуктом**, не формальная
приёмка Stage 12 и не новая выполненная проверка этого прохода.

Будущий backlog Macro 7, проверяемый в Macro 8:

- человекочитаемое представление `completed`, `complete`, `low`, `weak`,
  при необходимости — понятные значки статуса;
- RU/EN WebUI на стабильных смысловых ключах; авторская английская строка
  анализатора не должна быть единственным основанием перевода;
- читаемые локализованные временные метки;
- `coverage_ratio`, `error=[]`, `timeout=[]` и сходные технические сведения
  в подробностях, а не на первом плане обычного результата;
- визуализация локализованных в медиа признаков, где это разрешено контрактами;
- осторожные рекомендации при слабых признаках вместо чрезмерно категоричного
  «дополнительные действия не требуются»;
- неизменные канонические API/domain enums и смысл результата при смене языка.

Презентационный перевод сам по себе не требует изменения `CONTRACTS.md`.
Если понадобится изменение смысла рекомендации, его отдельно рассматривает
Macro 6; WebUI не пересчитывает риск или рекомендации.
Macro 8 должен заранее закрепить разрешённый корпус, ожидаемые ограничения,
метрики/критерии, версии профиля и воспроизводимые сценарии ручной приёмки,
включая неполный анализ и ложноположительные случаи. Генерируемые тестовые
примеры не подменяют реальный корпус и статистическую проверку.

## Критерии завершения Stage 12

- [ ] Macros 0–10 завершены по собственным критериям, результаты приняты владельцем;
- [ ] согласованные волны расширяют image/audio/video набор реальными методами;
  каждый имеет provenance, проверку прав, объяснимые признаки и пределы применимости;
- [ ] общие представления/ядра реализованы до зависимых анализаторов без
  дублирования парсинга и ослабления безопасности/cleanup;
- [ ] сохранены CPU-only, offline, bounded execution, закрытый каталог,
  структурированные результаты и отсутствие выдуманной вероятности;
- [ ] проверены корреляция, полнота, рекомендации и отсутствие завышенных выводов;
- [ ] выполнены согласованный WebUI/RU/EN объём и формальная приёмка на корпусе;
- [ ] проектная лицензия выбрана и оформлена; права и уведомления для фактической
  поставки проверены, ограничения сторонних бинарных компонентов учтены;
- [ ] Macro 9 подготовил и выпустил согласованную GitHub-поставку с сохранением
  гарантий установленного wheel; публикация и Git-действия выполнены владельцем;
- [ ] финальный аудит, относящиеся к реализации тесты/quality checks и строгая
  installed-wheel certification прошли, замечания закрыты;
- [ ] ML-реализация, веса и ML runtime не добавлены; Stage 13+ остаётся отдельно.

---

# Stage 13+ — Дальнейшие расширения — AFTER_MVP / NOT_STARTED

ML-реализация и остальные перечисленные ниже направления не начаты в Stage 12
и требуют отдельного решения владельца.

## Анализ и качество

- [ ] расширенные ML-модели;
- [ ] калибровка вероятности;
- [ ] экспериментальные датасеты сверх корпуса Stage 12;
- [ ] метрики качества будущих ML-моделей;
- [ ] сравнение моделей;
- [ ] обновление разрешённых critical-признаков.

## Хранение и пользователи

- [ ] SQLite;
- [ ] история анализов;
- [ ] поиск по SHA-256;
- [ ] очистка результатов по сроку;
- [ ] роли и права;
- [ ] развитая аутентификация.

## Интеграции

- [ ] почтовый коннектор;
- [ ] SIEM;
- [ ] DLP;
- [ ] SOAR;
- [ ] внешние форматы событий;
- [ ] автоматизированные сценарии реагирования вне ядра.

## Инфраструктура

- [ ] Docker;
- [ ] CI/CD;
- [ ] эксплуатационный мониторинг;
- [ ] внешний брокер задач;
- [ ] отдельные GPU-обработчики;
- [ ] распределённая обработка.

---

## 4. Блокеры и решения

BLOCKER Этапа 1: неподдерживаемый `logging.level` и ошибки открытия собственного
log handler приводили к необработанным исключениям до Uvicorn. Устранён:
уровень валидируется моделью, ошибки handler преобразуются в безопасную
`LoggingSetupError`, CLI завершается с кодом 4 без запуска Uvicorn.

Активные BLOCKER Этапа 1 отсутствуют.

Решение Stage 12 Macro 0 `PROJECT_LICENSE` — **CLOSED**: владелец выбрал
Apache-2.0 в Pass 2 от 2026-09-20; проектное решение — `PROJECT.md` §21.7,
лицензионный реестр — `REFERENCES.md`. Открытого вопроса о выборе лицензии нет.

Исторические точки принятия решений для завершённых этапов 6–10
(актуальные решения — в `PROJECT.md` и `CONTRACTS.md`):

| Когда | Вопрос | До решения можно продолжать? |
|---|---|---|
| Перед этапом 6 | Минимальный набор реальных анализаторов | Да, с тестовыми анализаторами |
| Перед этапом 6 | Характеристики компьютера и CUDA | Да, до ML |
| Перед этапом 7 | Веса, пороги и полнота | Да, можно реализовать версионируемый движок и тестовую конфигурацию |
| Перед этапом 7 | Critical override policy | Да, оставить выключенным |
| Перед этапом 8 | Синхронный/асинхронный API | Да, ядро не зависит от HTTP-профиля |
| Перед этапом 8 | Аутентификация WebUI | Да, до внешнего пользовательского доступа |
| Перед этапом 10 | Формат поставки | Да, локальный запуск остаётся базой |

---

## 5. Definition of Done для любой задачи

Задача считается выполненной, когда:

- [ ] поведение реализовано;
- [ ] код типизирован;
- [ ] добавлены тесты;
- [ ] тесты проходят;
- [ ] Ruff проходит;
- [ ] mypy проходит для затронутого кода;
- [ ] контракты не нарушены;
- [ ] временные данные очищаются;
- [ ] ошибки безопасны;
- [ ] секреты и runtime не попали в Git;
- [ ] чек-лист обновлён;
- [ ] изменение проекта отражено в `CHANGELOG.md`, если требуется.
