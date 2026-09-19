# FakeDetector

FakeDetector 0.1.0 — локальный CPU-only MVP для предварительного анализа
изображений, аудио и видео на технические признаки искусственного создания или
модификации. Он формирует findings, полноту, объяснимый risk и рекомендацию, но
не доказывает подделку или подлинность и не заменяет экспертную проверку.

FakeDetector MVP 0.1.0 существует; Stages 1–10 — `DONE / CLOSED`. Текущий этап
разработки — Stage 11, «Post-MVP Normalization & Hardening» (`IN_PROGRESS`).
Macro 0, «Roadmap Restructuring», Macro 1, «Confirmed Defect Remediation»,
Macro 2, «Runtime State Retention», Macro 3, «Analyzer Registration
Normalization», Macro 4, «Product Naming & Architecture Normalization», и
Macro 5, «Technical Debt / Config / Test-Support Cleanup», —
`DONE / owner accepted`; следующая задача — Macro 6, «Tests / Comments /
Documentation Normalization» (`NOT_STARTED / next action`). После Macro 2 `TaskRegistry`
владеет только незавершённой live/recoverable работой, а завершённая история
читается из `ResultRepository`; успешные сохранённые задачи вытесняются без
terminal cache, TTL или LRU.
Macro 3 свёл регистрацию production built-in анализаторов к одному закрытому
first-party каталогу. Из него выводятся согласованные представления для runtime,
worker resolution, полноты и валидации; динамическая загрузка и plugin API не
добавлены, а алгоритмы, публичные схемы и внешние контракты не изменились.
Macro 4 нормализовал внутренние имена production-модулей и сервисов по их
ответственности и закрыл A03: API и WebUI используют общую нейтральную
HTTP-политику, WebUI больше не зависит от реализации API adapter. Внешние
контракты и поведение сохранены; финальный независимый аудит — `PASS`.
Macro 5 устранил подтверждённый технический долг: удалена мёртвая MIME-константа,
неподдерживаемые значения двух полей конфигурации теперь отклоняются при
валидации, а framework fake-анализаторы перенесены в `tests/support` и исключены
из production-каталога и wheel. Схема `1.0`, defaults, поддерживаемые config
snapshots и публичные контракты сохранены; реальные Windows-spawn тесты
продолжают выполняться. Независимый аудит GPT-6 Astra Medium — `PASS`,
замечаний, требующих исправления, нет.
Stage 11 не расширяет продукт широкими новыми возможностями: он нормализует и
укрепляет доказанное MVP-поведение. Подробный план и статусы — в
[ROADMAP](docs/ROADMAP.md).

## Поддерживаемая среда

- Windows 11 x64;
- Python 3.12;
- CPU-only;
- wheel как основной install artifact;
- внешние `ffmpeg` и `ffprobe` в `PATH`.

Standalone executable, installer, Docker, PyPI и GitHub Release не входят в
MVP. Проверенный Stage 10 media-tool baseline — Gyan Windows x64 full build
`9.0.1-full_build-www.gyan.dev`; это tested build, не заявленная минимальная
версия.

## Быстрый старт из release kit

Release producer передаёт exact wheel и механически созданный из `uv.lock`
`runtime-constraints.txt`. Получателю не нужны checkout, IDE, editable install
или dev-зависимости.

Release producer собирает и проверяет весь handoff одной командой. До commit она
даёт честное non-certifying evidence:

```powershell
uv run python scripts/verify_stage10_release.py --development
```

После review и commit строгий запуск без флага требует чистое source tree и
создаёт сертифицирующий отчёт:

```powershell
uv run python scripts/verify_stage10_release.py
```

В versioned ZIP находятся wheel, runtime constraints, canonical config,
`.env.example`, demo generator, `MVP_HANDOFF.md`, canonical `CHANGELOG.md` и
`release-manifest.json`. SHA-256 самого manifest и ZIP записываются во внешнем
verification report, поэтому circular self-hash не используется.

```powershell
uv venv --python 3.12 --no-project .venv
uv pip install --python .\.venv\Scripts\python.exe `
  --constraint .\runtime-constraints.txt `
  .\fakedetector-0.1.0-py3-none-any.whl
uv pip check --python .\.venv\Scripts\python.exe

New-Item -ItemType Directory -Path .\work
Copy-Item .\config.example.yaml .\work\config.yaml
Set-Location .\work

$apiBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($apiBytes)
$env:MEDIA_ANALYZER_API_TOKEN = ([BitConverter]::ToString($apiBytes)).Replace("-", "")
$passwordBytes = New-Object byte[] 24
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($passwordBytes)
$webPassword = ([BitConverter]::ToString($passwordBytes)).Replace("-", "")
$env:MEDIA_ANALYZER_WEBUI_CREDENTIALS = "analyst:$webPassword"
$webPassword

..\.venv\Scripts\python.exe ..\generate_stage10_demo_media.py `
  --output-dir .\demo-media
..\.venv\Scripts\fakedetector.exe --config .\config.yaml
```

Откройте `http://127.0.0.1:8080/` и используйте HTTP Basic credentials из
environment. API использует `Authorization: Bearer <token>` и маршруты:

```text
POST /api/v1/analyses
GET  /api/v1/analyses/{analysis_id}
GET  /api/v1/analyses/{analysis_id}/result
```

`.env.example` — только reference/template: FakeDetector не загружает `.env`
автоматически. Секреты должны быть установлены в environment процесса.

Относительные config/runtime/result/log paths разрешаются от текущего working
directory. Запускайте приложение с явным `--config` из стабильного каталога.
Остановка — `Ctrl+C`. При повторном запуске с тем же working directory и result
storage сохранённые terminal results доступны по прежнему `analysis_id`;
незавершённые задачи не восстанавливаются.

Полный пошаговый Windows/FFmpeg/install/demo/API/restart/troubleshooting guide:
[MVP_HANDOFF](docs/MVP_HANDOFF.md).

## Что проверяет Profile B

| Media | Analyzer |
|---|---|
| image | `image_metadata_consistency@1.0.0` |
| image | `image_copy_move_correspondence@1.0.0` |
| audio | `audio_pcm_quality@1.0.0` |
| video | `video_sampled_frame_quality@1.0.0` |

`completeness=complete` означает завершение настроенного набора, а не
универсальную forensic completeness. Low risk не доказывает подлинность;
`probability=null` ожидаем; audio/video Profile B — технические quality и
sampled-frame checks, не универсальные deepfake classifiers.

## Security boundaries

Локальный demo по умолчанию слушает только loopback. WebUI Basic вне loopback
допустим только за HTTPS/reverse proxy; public bind без deployment review не
рекомендуется. Runtime directories должны принадлежать доверенной Windows
account и иметь подходящие ACL. Hostile same-account/Administrator actor,
OS sandbox, hard CPU/RAM quotas, rate limiting и TLS не входят в гарантии MVP.

## Разработка и проверки

Из source checkout:

```powershell
uv lock --check
uv run ruff check .
uv run mypy src
uv run pytest
uv run pre-commit run --all-files
uv run fakedetector --help
```

Источники истины: [PROJECT](docs/PROJECT.md), [CONTRACTS](docs/CONTRACTS.md),
[ROADMAP](docs/ROADMAP.md), [REFERENCES](docs/REFERENCES.md) и
[CHANGELOG](docs/CHANGELOG.md).

## Лицензия

Лицензия пока не выбрана. Все права сохранены.
