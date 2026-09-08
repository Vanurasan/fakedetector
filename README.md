# FakeDetector

FakeDetector — прототип системы предварительного анализа изображений, аудио и
видео на признаки искусственного создания или модификации.

Проект строится как вспомогательный инструмент оценки риска: он должен собирать
результаты нескольких анализаторов и в следующих этапах формировать объяснимое
заключение. Такая оценка не устанавливает подлинность материала окончательно и
не заменяет экспертную проверку.

## Состояние проекта

**Stage 6 — IN_PROGRESS.** Реализация Profile B, production integration и полный
quality barrier завершены. До формального закрытия остаётся отдельный независимый
финальный аудит Stage 6.

| Stage | Status | Что реализовано или запланировано |
|---:|---|---|
| 1 | DONE | Каркас приложения, конфигурация, CLI, logging и FastAPI health |
| 2 | DONE | Доменные контракты, типизированные модели и нормативные правила |
| 3 | DONE | Intake, validation и контролируемое владение source |
| 4 | DONE | Lifecycle задачи, routing, scheduler, workspace и cleanup/recovery |
| 5 | DONE | Preprocessing image/audio/video и analyzer framework |
| 6 | IN_PROGRESS | Profile B и Finding production path реализованы; final audit pending |
| 7 | PLANNED | Полнота анализа, риск и рекомендации |
| 8 | PLANNED | Итоговый JSON, API и WebUI |
| 9 | PLANNED | Надёжность, безопасность и сквозные тесты |

## Что уже умеет система

- Запускаться через CLI, загружать YAML-конфигурацию с env overrides,
  валидировать её через Pydantic и вести ротационные JSONL-логи.
- Потоково принимать и проверять image/audio/video: контролировать размер,
  расширение, MIME, сигнатуру, безопасное чтение и SHA-256, а также управлять
  владением временным source.
- Создавать и маршрутизировать задачи, выполнять их с ограниченной
  параллельностью, учитывать workspace artifacts и проводить детерминированный
  cleanup/recovery.
- Подготавливать изображения, аудио и видео для анализа, включая bounded-вызовы
  внешних процессов и ограничения количества и общего размера артефактов.
- Регистрировать и включать анализаторы по конфигурации, проверять их
  применимость, изолировать timeout и ошибки, а затем собирать упорядоченные
  `AnalyzerResult`.
- Применять детерминированную политику выполнения и хранить внутреннее состояние
  Stage 5 в неизменяемом виде.
- Выполнять четыре CPU-only анализатора Profile B для image/audio/video и
  преобразовывать authoritative `AnalyzerResult` в нормализованные weak `Finding`
  с отдельным immutable Stage 6 task state.

## Что пока не реализовано

- Расчёт полноты и риска, а также рекомендации.
- Сборка и persistence итогового результата, публичный upload API и Web UI.
- Production deployment и эксплуатационный hardening.

## Общая схема pipeline

```text
РЕАЛИЗОВАНО — STAGES 1–6
Input → Validation → Task lifecycle → Preprocessing
→ Profile B analyzers → Finding formation

ДАЛЕЕ
Risk / completeness / recommendation (Stage 7)
→ Result / persistence / API / Web UI (Stage 8)
→ Hardening и end-to-end verification (Stage 9)
```

## Запуск и проверки

Запуск приложения с примером конфигурации:

```text
uv run fakedetector --config config/config.example.yaml
```

Проверка запуска реального сервера и endpoint `GET /health`:

```text
uv run poe server-smoke
```

Полный quality pipeline:

```text
uv run poe check
```

## Quality status

Stage 6 implementation barrier: **1389 passed, 2 skipped, combined coverage
89.55%**; statement coverage 92.03%, branch coverage 79.52% и `--cov-branch`
включён. Независимый final audit Stage 6 ещё не выполнялся.

Это зафиксированный результат закрытия этапа, а не гарантированное текущее число
тестов после будущих изменений.

## Документация

- [PROJECT](docs/PROJECT.md) — назначение, архитектура, границы и основной стек.
- [CONTRACTS](docs/CONTRACTS.md) — модели данных, интерфейсы и нормативное
  поведение.
- [ROADMAP](docs/ROADMAP.md) — этапы разработки и текущий статус.
- [REFERENCES](docs/REFERENCES.md) — происхождение методов и реализаций анализаторов.
- [CHANGELOG](docs/CHANGELOG.md) — история существенных изменений и принятых
  решений.

## Технологический стек

- Python 3.12 и uv;
- FastAPI и Uvicorn;
- Pydantic v2, PyYAML;
- Pillow;
- FFmpeg/ffprobe как системная зависимость;
- локальная файловая система и стандартные механизмы Python для очередей,
  потоков и процессов;
- pytest, pytest-cov, Ruff, mypy и pre-commit для контроля качества.

## Лицензия

Лицензия пока не выбрана. Все права сохранены.
