# FakeDetector

FakeDetector 0.1.0 — локальный CPU-only MVP для предварительного анализа
изображений, аудио и видео на технические признаки искусственного создания или
модификации. Он формирует findings, полноту, объяснимый risk и рекомендацию, но
не доказывает подделку или подлинность и не заменяет экспертную проверку.

FakeDetector MVP 0.1.0 существует; Stages 1–11 — `DONE / CLOSED`.
Stage 11 — Post-MVP Normalization & Hardening — `DONE / CLOSED`;
Macros 0–8 Stage 11 — `DONE / owner accepted`.
Финальная независимая проверка GPT-6 Astra High и строгая сертификация
установленного артефакта — `PASS`; замечаний, требующих исправления, нет,
гарантии MVP A–R сохранены. Владелец открыл Stage 12 — Analyzer Expansion,
Licensing & Product Validation: `IN_PROGRESS`.
Указанный `PASS` относится к закрытию Stage 11 и не сертифицирует последующие
Stage 12 SHA. По решению владельца от 2026-10-19 новая функциональная разработка
приостановлена до сверки документации и независимого архитектурного review;
Stage 12 остаётся `IN_PROGRESS`. Принятый baseline включает PR #75 и #76;
Задание `STAGE13-ML-AASIST-L-IMPLEMENTATION-01` от 2026-10-22 отдельно разрешило
один experimental measurement-only AASIST-L; остальные направления этой паузой
не открываются. PR #78 принят владельцем и слит как
`35ae4d3ca11bfe0bfcfb98954bc43c911e524800`. Runtime-каталог содержит 15 анализаторов:
5 CORE, 9 исходных experimental и 1 AASIST-L experimental measurement-only.
Стандартный профиль включает 4 анализатора, дипломный — 14;
AASIST-L необязателен, по умолчанию выключен и не участвует в scoring.
Незавершённые исследования Macro 4 отложены с сохранением исторических результатов;
Macro 5 не начат и отложен ради завершения ВКР. Независимый инженерный аудит
Macro 6 — PASS; четыре находки рассмотрены, адресная семантическая ремедиация
реализована; по дополнительному разрешению владельца исторический guard
принимает только точную обратную проекцию текста F01 с прежним полным SHA.
Повторные focused tests и полный quality barrier прошли; Macro 6 —
DONE / OWNER ACCEPTED / MERGED (PR #79, baseline
`3d1ef2c0a050fdfa54e782f9c2493160a6d4f7cf`). Дизайн M7-R1 принят владельцем;
отдельно разрешённый M7-R2 реализует WebUI/RU/EN: IMPLEMENTATION IN PROGRESS,
независимые review и merge ожидаются. Macro 7 не закрыт; Macros 8–10 не завершены.
Текущий статус разработки, подробные основания закрытия предыдущих этапов
и принятая политика Graphify `REBUILD_POLICY` —
в [ROADMAP](docs/ROADMAP.md).

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
uv run python scripts/verify_release.py --development
```

После review и commit строгий запуск без флага требует чистое source tree и
создаёт сертифицирующий отчёт:

```powershell
uv run python scripts/verify_release.py
```

В versioned ZIP находятся wheel, runtime constraints, `LICENSE`, canonical config,
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

..\.venv\Scripts\python.exe ..\generate_release_demo_media.py `
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

WebUI по умолчанию русскоязычный; переключатель English использует `?lang=en`.
Язык сохраняется в форме, переходах и ссылках результата без cookie или сессии.
Сохранённые аналитические пояснения и сообщения показываются на исходном языке:
перевод интерфейса не означает полного перевода отчёта. На странице обработки
можно остановить автообновление (`refresh=off`); сам анализ продолжается.
Временные метки отображаются в UTC, размеры — в МиБ/MiB с точным числом байт.
Семантика оценки и технической полноты остаётся прежней; детали представления —
[PROJECT §6.1](docs/PROJECT.md#61-webui) и [CONTRACTS §18](docs/CONTRACTS.md#18-контракт-webui).

`.env.example` — только reference/template: FakeDetector не загружает `.env`
автоматически. Секреты должны быть установлены в environment процесса.

Относительные config/runtime/result/log paths разрешаются от текущего working
directory. Запускайте приложение с явным `--config` из стабильного каталога.
Остановка — `Ctrl+C`. При повторном запуске с тем же working directory и result
storage сохранённые terminal results доступны по прежнему `analysis_id`;
незавершённые задачи не восстанавливаются.

Полный пошаговый Windows/FFmpeg/install/demo/API/restart/troubleshooting guide:
[MVP_HANDOFF](docs/MVP_HANDOFF.md).

## Opt-in AASIST-L: только необработанное измерение

`audio_aasist_l_measurement@1.0.0` — 15-й конфигурируемый анализатор,
`EXPERIMENTAL`. Стандартный и дипломный enabled lists не меняются.
Для checkout: `uv sync --locked --extra aasist-l`. Для установленного wheel
release producer экспортирует отдельные constraints из того же lock:

```powershell
uv export --locked --no-dev --extra aasist-l --no-emit-project --no-hashes `
  --output-file runtime-aasist-l.txt
uv pip install --python .\.venv\Scripts\python.exe --constraint .\runtime-aasist-l.txt `
  ".\fakedetector-0.1.0-py3-none-any.whl[aasist-l]"
```

Передайте отдельно `model-asset/aasist-l.onnx`, `model-manifest.json`, MIT
`LICENSE`, `UPSTREAM_NOTICE`, ORT `LICENSE/ThirdPartyNotices` и экспортированные
constraints. Точный [pin и происхождение](docs/REFERENCES.md#aasist-l),
[профиль и ограничения](docs/METHODS.md#aasist-l-measurement).
Artifact: HF revision `357e022c44a1aa926097e18c1457bde3873ed8bf`, 766114 bytes,
SHA-256 `f43f0a638b52846f5d0e630c0a738d10e9306325945127c6f8662d559585f218`.
Модель можно взять из принятого feasibility ZIP; при отдельном приобретении
используется только pinned artifact URL из REFERENCES. В runtime загрузки из сети нет.

Администратор размещает файл в отдельном локальном каталоге с доступом на запись
только доверенным операторам, вне checkout, package и task/runtime storage.
Абсолютный `model_path` задаётся в существующей карте analyzer settings:

```yaml
analyzers:
  audio:
    enabled: [audio_pcm_quality, audio_aasist_l_measurement]
  settings:
    audio_aasist_l_measurement:
      model_path: 'C:\FakeDetector-Models\AASIST-L\aasist-l.onnx'
result:
  include_raw_metrics: true
```

Это фрагмент для слияния с полной конфигурацией, не замена всего YAML.
Реализация проверяет ordinary regular file, все parents без reparse/symlink,
одиночный hardlink, размер, полный SHA и descriptor identity; native loader
получает те же проверенные bytes. Политика ACL каталога остаётся обязанностью
администратора. Missing/corrupt model и optional-runtime/load/inference failure
дают безопасный ERROR. Disabled метод не требует ORT или model asset.

Принимаются только исходные mono/16000 Hz и штатный PCM16 WAV. Измеряется первый
префикс до 64600 отсчётов; короткий допустимый префикс повторяется, что не добавляет
наблюдений. Пустой, технически слишком короткий или цифрово беззвучный префикс
даёт `insufficient_evidence` без logits. Speech presence всегда `unverified`.
Отклик out-of-domain/uncalibrated: forensic validity и вероятность подделки
не установлены. Нет Findings, score, probability или влияния logits на ансамбль.
Выполнение учитывается только в фактической полноте активного плана.

ORT CPU имеет intra/inter threads=1; лимита RAM средствами ОС нет. Для
ограничения BLAS resources задайте `$env:OPENBLAS_NUM_THREADS = '1'` **до запуска
Python**; один ORT thread сам по себе не ограничивает другие native библиотеки.
Стандартный release kit модель/ML wheelhouse автоматически не включает.
Для полностью offline установки заранее подготовьте совместимые wheels всей
locked closure и используйте `uv pip install --no-index --find-links <wheelhouse>`
с теми же constraints; перенос только ONNX-файла недостаточен.

## Что проверяет Profile B

Стандартный [config.example.yaml](config/config.example.yaml) включает следующие
четыре анализатора. CORE-каталог содержит пять: дополнительный
`image_jpeg_double_quantization@1.0.0` доступен для явного включения и уже включён
в дипломный профиль.

| Media | Analyzer |
|---|---|
| image | `image_metadata_consistency@1.0.0` |
| image | `image_copy_move_correspondence@1.0.0` |
| audio | `audio_pcm_quality@1.0.0` |
| video | `video_sampled_frame_quality@1.0.0` |

`completeness=complete` означает завершение настроенного набора, а не
универсальную forensic completeness или достаточность криминалистических
свидетельств. Low risk и score=0 не доказывают подлинность или безопасность;
`no_additional_action` относится только к выполненным проверкам.
`probability=null` ожидаем; audio/video Profile B — технические quality и
sampled-frame checks, не универсальные deepfake classifiers.

## Дипломный experimental профиль

В source checkout доступен отдельный [config/config.diploma.yaml](config/config.diploma.yaml):
пять CORE и девять experimental анализаторов. После установки зависимостей,
FFmpeg и переменных аутентификации, описанных выше, запуск из корня checkout:

```powershell
uv run fakedetector --config config/config.diploma.yaml
```

Профиль сохраняет `raw_metrics`; они доступны в API JSON и разделе «Результаты
анализаторов» WebUI. Experimental методы публикуют описательные измерения без
Findings и собственного score. Профиль использует `diploma_ensemble_v1@0.1.0`:
assessment объединяет доступные отклики в **сводный эвристический сигнал 0–100**,
не вероятность подделки. В WebUI видны краткое резюме и объяснение семейств,
весов, уменьшенных вкладов, канонической ёмкости и пробелов покрытия. Значение
100 означает теоретический максимум текущей политики для данного типа медиа;
недоступные свидетельства не уменьшают ёмкость. Начальные коэффициенты не
откалиброваны, эмпирической сопоставимости разных типов медиа нет;
`probability` остаётся null. Сильный response возможен на обычном
содержании; отсутствие response не доказывает подлинность. Уменьшение вкладов
внутри семейства не устраняет возможную зависимость между семействами;
статистическая независимость не установлена. Точная принятая граница —
[METHODS, нормализация ансамбля](docs/METHODS.md#diploma-ensemble-normalization).
Политика ансамбля —
[PROJECT §10.8](docs/PROJECT.md#diploma-ensemble). Применимость,
ограниченное покрытие и известные confounds — в
[METHODS](docs/METHODS.md#diploma-experimental).
Отдельный VRC2 `video_repeated_content_correspondence_v2_prototype@0.1.0`
не входит в конфигурируемый runtime-каталог: он доступен только исследовательскому worker,
не выбирается обычной конфигурацией и не участвует в ансамбле. Принятый результат
PR #76 — `VRC2_PROTOTYPE_APPLICABILITY_LIMITED`, не production promotion;
результаты и ограничения — в
[ROADMAP](docs/ROADMAP.md#diploma-vrc2-prototype-applicability-sprint1).
Стандартный config и исторический Profile B не изменены. Штатные ресурсные
лимиты сохраняются: например, длинный stereo audio может превысить общий
бюджет precision/STFT artifacts и завершиться preprocessing error.

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
uv run poe check
```

`poe check` последовательно выполняет pre-commit, mypy, pytest и CLI smoke.
Отдельные диагностические команды:

```powershell
uv run ruff check .
uv run mypy src
uv run pytest
uv run pre-commit run --all-files
uv run fakedetector --help
```

Источники истины по областям: [AGENTS](AGENTS.md) — процесс работы агента,
[PROJECT](docs/PROJECT.md) — архитектура и продуктовые политики,
[CONTRACTS](docs/CONTRACTS.md) — интерфейсы и данные,
[METHODS](docs/METHODS.md) — принятая методология,
[REFERENCES](docs/REFERENCES.md) — provenance/licensing,
[ROADMAP](docs/ROADMAP.md) — план и статус.
[CHANGELOG](docs/CHANGELOG.md) хранит историю;
[research](docs/research/README.md) — исследовательские свидетельства.
Начало чтения кода: [PROJECT §6.19 — карта реализации](docs/PROJECT.md#implementation-map),
затем [жизненный цикл §7](docs/PROJECT.md#7-канонический-жизненный-цикл-анализа).
Планы и непройденные gates остаются в ROADMAP; наличие прототипа или capability
предобработки само по себе не означает наличие принятого метода.

## Лицензия

Собственный код FakeDetector распространяется по
[Apache License 2.0](LICENSE). SPDX: `Apache-2.0`.

Сторонние зависимости, внешние `ffmpeg`/`ffprobe`, а также будущие модели,
веса и наборы данных сохраняют собственные лицензии и условия. Лицензия
FakeDetector не перелицензирует их или реализации, цитируемые как
исследовательские источники. Правила и результаты проверки — в
[REFERENCES](docs/REFERENCES.md).
