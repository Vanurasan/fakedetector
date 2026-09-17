# FakeDetector

FakeDetector 0.1.0 — локальный CPU-only MVP для предварительного анализа
изображений, аудио и видео на технические признаки искусственного создания или
модификации. Он формирует findings, полноту, объяснимый risk и рекомендацию, но
не доказывает подделку или подлинность и не заменяет экспертную проверку.

Stage 10 имеет статус `IN_PROGRESS`: Macro 1 (wheel и воспроизводимая установка)
принят владельцем; Macro 2 (handoff, документация и demo generator) реализован и
ожидает review; финальный release kit и installed-artifact gate принадлежат
Macro 3.

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
