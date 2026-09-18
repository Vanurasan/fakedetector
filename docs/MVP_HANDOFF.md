# Установка и демонстрация FakeDetector MVP 0.1.0

Это руководство описывает передачу и локальную демонстрацию установленного
wheel на гарантируемой платформе: **Windows 11 x64, Python 3.12, CPU-only**.
Исходный checkout, IDE, editable install и dev/pytest-зависимости получателю не
нужны.

FakeDetector формирует технические признаки и объяснимую риск-оценку. Он не
подтверждает подлинность, не доказывает подделку и не заменяет экспертную
криминалистику, антивирус или антифишинговую систему.

## Состав release kit и роли

Macro 3 собирает и проверяет versioned release kit со следующим точным
recipient-facing inventory:

```text
fakedetector-0.1.0-py3-none-any.whl
runtime-constraints.txt
config.example.yaml
.env.example
generate_stage10_demo_media.py
MVP_HANDOFF.md
CHANGELOG.md
release-manifest.json
```

`CHANGELOG.md` является копией канонического repository
`docs/CHANGELOG.md`. Manifest связывает её и остальные recipient-facing файлы с
HEAD SHA и состоянием working tree на момент начала сборки, а также с SHA-256
каждого файла. Только успешный strict report при clean source подтверждает точную
привязку к commit SHA. Сам manifest не хэширует себя:
его SHA-256 и SHA-256 versioned ZIP находятся во внешнем
`verification-report.json`.

Release producer собирает wheel и механически создаёт constraints из
`uv.lock`; получатель использует готовые файлы и не регенерирует constraints:

```powershell
uv build --sdist --out-dir <artifacts>
uv build --wheel --out-dir <artifacts> <sdist-path>
uv export --locked --no-dev --no-emit-project --format requirements.txt `
  --no-annotate --no-header --no-hashes `
  --output-file <kit>\runtime-constraints.txt
```

`runtime-constraints.txt` — производный release-файл, а не второй вручную
поддерживаемый lock. Producer запускает полный gate до commit в честном
non-certifying режиме:

```powershell
uv run python scripts/verify_stage10_release.py --development
```

После review и commit строгий запуск требует чистое source tree и связывает
release с новым commit SHA:

```powershell
uv run python scripts/verify_stage10_release.py
```

По умолчанию output создаётся во внешнем OS temp directory. Для явного внешнего
пустого каталога используется `--output-dir <path>`; непустой каталог gate не
перезаписывает.

## 1. Предварительные требования

Установите:

- Python 3.12 x64 (`python --version` должен показывать `3.12.x`);
- `uv`;
- внешние `ffmpeg.exe` и `ffprobe.exe`, доступные через `PATH` тому же процессу,
  который запускает FakeDetector.

Один воспроизводимый ручной workflow установки FFmpeg для Windows:

1. Скачайте Windows x64 full build со страницы
   [Gyan FFmpeg builds](https://www.gyan.dev/ffmpeg/builds/).
2. Распакуйте архив в стабильный каталог, например `C:\Tools\ffmpeg`, так чтобы
   исполняемые файлы находились по путям `C:\Tools\ffmpeg\bin\ffmpeg.exe` и
   `C:\Tools\ffmpeg\bin\ffprobe.exe`.
3. Откройте `System Properties` → `Advanced` → `Environment Variables`, выберите
   пользовательскую переменную `Path`, нажмите `Edit` → `New` и добавьте
   `C:\Tools\ffmpeg\bin`. Не заменяйте существующее содержимое `Path`.
4. После изменения `Path` закройте текущий терминал и откройте новый PowerShell.
5. Выполните приведённые ниже команды `ffmpeg -version` и `ffprobe -version`.
6. После установки wheel выполните generator из раздела 5 как практическую
   проверку media capabilities, необходимых демонстрации FakeDetector.

Проверка в новом PowerShell:

```powershell
python --version
uv --version
Get-Command ffmpeg
Get-Command ffprobe
ffmpeg -version
ffprobe -version
```

Runtime при старте фактически запускает обе команды с `-version` и прекращает
запуск, если хотя бы одна недоступна или завершается с ошибкой. Для production
media input разрешён только локальный протокол `file`; сетевые media protocols
не требуются.

Stage 10 проверен с **Gyan Windows x64 full build
`9.0.1-full_build-www.gyan.dev`** для FFmpeg и ffprobe. Это tested build, а не
заявленная минимальная поддерживаемая версия. Бинарники не входят в репозиторий,
wheel или release kit. После установки дополнительно запустите generator из
раздела 5: он практически проверит наличие `lavfi`, encoder `mpeg4` и работу
ffprobe на создаваемом MP4.

## 2. Установка exact wheel

Откройте PowerShell в каталоге распакованного release kit:

```powershell
uv venv --python 3.12 --no-project .venv
uv pip install --python .\.venv\Scripts\python.exe `
  --constraint .\runtime-constraints.txt `
  .\fakedetector-0.1.0-py3-none-any.whl
uv pip check --python .\.venv\Scripts\python.exe
.\.venv\Scripts\fakedetector.exe --help
```

Эта схема устанавливает exact wheel с утверждённым runtime dependency set. Не
используйте `-e`, `PYTHONPATH`, импорт из checkout или dev dependency group.

## 3. Рабочий каталог и конфигурация

Создайте стабильный working directory и скопируйте канонический пример:

```powershell
New-Item -ItemType Directory -Path .\work
Copy-Item .\config.example.yaml .\work\config.yaml
Set-Location .\work
```

Запуск всегда использует явный `--config`. Путь к YAML разрешается относительно
текущего каталога процесса. Относительные пути внутри YAML (`runtime/temp`,
`runtime/results`, `runtime/logs/application.jsonl`) также зависят от текущего
working directory, а не от расположения YAML. Поэтому для запуска и повторного
запуска оставайтесь в одном каталоге `work` или задайте в YAML стабильные
абсолютные пути.

Пример уже включает Profile B и интервал видео-сэмплирования 1 секунду:

| Media | Analyzer |
|---|---|
| image | `image_metadata_consistency@1.0.0` |
| image | `image_copy_move_correspondence@1.0.0` |
| audio | `audio_pcm_quality@1.0.0` |
| video | `video_sampled_frame_quality@1.0.0` |

Не добавляйте секреты в YAML.

## 4. Секреты окружения

`.env.example` содержит только два пустых имени-подсказки:

```text
MEDIA_ANALYZER_API_TOKEN=
MEDIA_ANALYZER_WEBUI_CREDENTIALS=
```

FakeDetector **не загружает `.env` автоматически**. Значения должны находиться
в environment процесса до запуска. Пример создаёт случайные значения для
текущей PowerShell-сессии:

```powershell
$apiBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($apiBytes)
$apiToken = ([BitConverter]::ToString($apiBytes)).Replace("-", "")
$env:MEDIA_ANALYZER_API_TOKEN = $apiToken
$passwordBytes = New-Object byte[] 24
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($passwordBytes)
$webPassword = ([BitConverter]::ToString($passwordBytes)).Replace("-", "")
$env:MEDIA_ANALYZER_WEBUI_CREDENTIALS = "analyst:$webPassword"
$apiToken
$webPassword
```

Сохраните показанные API token и WebUI password в разрешённом защищённом
хранилище. Формат Basic credentials — одна непустая пара `username:password`;
API token также должен быть непустым. При отсутствующих/некорректных secrets
запуск завершается без обслуживания HTTP-запросов.

## 5. Генерация demo media

Из каталога `work`:

```powershell
..\.venv\Scripts\python.exe ..\generate_stage10_demo_media.py `
  --output-dir .\demo-media
```

Output directory должен отсутствовать или быть пустым; generator никогда не
перезаписывает существующие или посторонние файлы. Он печатает абсолютные пути
трёх созданных файлов:

- seeded PNG 512×512 с двумя одинаковыми областями 112×112;
- mono PCM WAV, 16-bit, 8 kHz, 1 s, с детерминированными bounded saturation
  observations;
- MP4 64×64, 2 fps, около 3.2 s, с повторяющимися кадрами.

PNG и WAV детерминированы по байтам в гарантируемой среде. Для MP4 обещаются
стабильные смысловые свойства, а не одинаковые байты между разными FFmpeg builds.
Generator использует только Python stdlib, runtime-зависимости wheel и внешние
FFmpeg/ffprobe; он не импортирует tests или measurement harness.

## 6. Запуск и WebUI walkthrough

Оставаясь в `work`, запустите установленный console script:

```powershell
..\.venv\Scripts\fakedetector.exe --config .\config.yaml
```

По умолчанию сервер слушает только `127.0.0.1:8080`. Откройте
`http://127.0.0.1:8080/`, введите пользователя `analyst` и сгенерированный
password, затем по очереди загрузите:

1. `demo-media\fakedetector-demo-copy-move.png`;
2. `demo-media\fakedetector-demo-audio.wav`;
3. `demo-media\fakedetector-demo-video.mp4`.

После каждой загрузки дождитесь перенаправления со status page на result page.
Зафиксируйте `analysis_id`, status, completeness, findings, risk, recommendation
и cleanup status. WebUI использует HTTP Basic; cookie-session нет.

## 7. Эквивалент через API

В другом PowerShell перейдите в тот же release-kit working directory `work`,
установите сохранённый API token в `$env:MEDIA_ANALYZER_API_TOKEN`, затем
выполните:

```powershell
Set-Location 'C:\path\to\fakedetector-0.1.0\work'
$env:MEDIA_ANALYZER_API_TOKEN = '<saved API token>'
$headers = @{ Authorization = "Bearer $env:MEDIA_ANALYZER_API_TOKEN" }
$submission = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8080/api/v1/analyses `
  -Headers $headers `
  -Form @{ file = Get-Item .\demo-media\fakedetector-demo-copy-move.png }
$analysisId = $submission.analysis_id
$analysisId

do {
  Start-Sleep -Milliseconds 500
  $status = Invoke-RestMethod -Method Get `
    -Uri "http://127.0.0.1:8080/api/v1/analyses/$analysisId" `
    -Headers $headers
} until ($status.result_available)

$result = Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8080/api/v1/analyses/$analysisId/result" `
  -Headers $headers
$result | ConvertTo-Json -Depth 20
```

Если используемая Windows PowerShell не поддерживает `Invoke-RestMethod -Form`,
используйте `curl.exe`:

```powershell
curl.exe -sS -H "Authorization: Bearer $env:MEDIA_ANALYZER_API_TOKEN" `
  -F "file=@demo-media/fakedetector-demo-copy-move.png;type=image/png" `
  http://127.0.0.1:8080/api/v1/analyses
```

API имеет ровно три маршрута: создать analysis, получить status, получить
result. Результат может временно возвращать `202`, пока анализ выполняется.

## 8. Как интерпретировать результат

- Findings — технические сигналы доступных методов, не экспертный вердикт.
- `completeness.status=complete` означает, что завершился весь настроенный для
  этого media набор анализаторов. Это не универсальная криминалистическая
  полнота.
- Низкий risk не доказывает подлинность; отсутствие findings означает только,
  что текущие методы не нашли сигналов.
- Weak findings не обязаны давать высокий risk: v1 использует
  детерминированную внутреннюю эвристику и корреляцию вкладов.
- `probability=null` и `probability_method=null` ожидаемы: статистически
  валидированная вероятность в MVP не вычисляется.
- `audio_pcm_quality` проверяет свойства PCM/качества, а
  `video_sampled_frame_quality` — выборочные кадры. Это не универсальные
  deepfake classifiers.

## 9. Остановка, persistence и restart

Остановите сервер `Ctrl+C`. Завершённый результат находится в:

```text
work\runtime\results\<analysis_id>.json
```

Исходный media и промежуточные artifacts после штатного анализа удаляются;
результат JSON и JSONL log сохраняются. Запустите ту же команду из того же
working directory и повторите API GET для сохранённого `analysis_id`: terminal
result читается из result repository после restart.

Незавершённые задачи не восстанавливаются после restart; их ID без сохранённого
JSON станет неизвестным (`404`). Автоматического persistence retry, истории,
retention cleanup и crash-residue recovery в MVP нет. После проверки
восстановленного результата снова остановите сервер `Ctrl+C`.

## 10. Безопасность и deployment boundaries

- Для локальной демонстрации сохраняйте loopback host `127.0.0.1`.
- Не меняйте host на public interface без отдельного deployment review.
- WebUI Basic за пределами loopback допустим только за HTTPS/reverse proxy;
  TLS не входит в приложение.
- API всегда используйте с Bearer token; auth bypass не является demo mode.
- Runtime parent и все каталоги должны принадлежать доверенной Windows account
  и иметь подходящие ACL. Python `mode=0o700/0o600` на Windows — best effort.
- Защита от hostile process той же account или Administrator, OS sandbox и
  hard CPU/RAM quotas не входят в гарантии MVP.
- Не публикуйте config с secrets, `.env`, media, results или logs.

## 11. Troubleshooting

| Симптом | Причина и действие |
|---|---|
| Python не 3.12 или venv не создаётся | Проверьте `python --version`; создайте venv через `uv venv --python 3.12 --no-project`. Wheel поддерживает `>=3.12,<3.13`. |
| `Runtime initialization failed.` и exit code 3 | Частые причины: `ffmpeg`/`ffprobe` не видны этому процессу или runtime paths небезопасны/недоступны. Проверьте обе `-version` команды в той же shell и права каталогов. |
| FFmpeg есть в одной shell, но не в другой | После изменения `PATH` откройте новый PowerShell и сравните `Get-Command ffmpeg`/`ffprobe`. |
| Generator сообщает missing capability | Tested build поддерживает `lavfi` и encoder `mpeg4`; установите совместимый full build и повторите generator. Runtime startup проверяет только `-version`, generator проверяет фактическую capability. |
| `Configuration error...` и exit code 2 | Неверный путь `--config`, UTF-8/YAML, неизвестное поле, недопустимое значение или ошибочный `FAKEDETECTOR_*` override. Сверьте с неизменённым example. |
| `Access configuration failed.` и exit code 5 | Нет непустого API token либо Basic credentials не имеют формы `username:password`. Переменные должны быть в environment запускаемого процесса; `.env` не загружается. |
| `Logging initialization failed.` и exit code 4 | Log directory/file недоступен или нарушает filesystem safety. Проверьте working directory и ACL. |
| Uvicorn сообщает bind/address in use | Порт 8080 занят. Остановите другой процесс или измените существующее поле `server.port` в рабочем config. |
| Upload возвращает `413`, `415` или `422` | Превышен лимит, media type/extension/signature не поддерживается либо request fields не прошли validation. Rejection не является risk verdict. |
| Analysis завершается internal/media error | FFmpeg build может не иметь нужного demuxer/decoder/encoder. Проверьте файл generator, `ffprobe <file>` и tested build; не добавляйте network protocol input. |
| После restart старый ID даёт `404` | Запуск выполнен из другого cwd/с другим `result.directory`, либо результат не был сохранён до остановки. Вернитесь к тому же `work` и config. |
| Runtime/result/log directory недоступен | Остановите приложение, исправьте ownership/ACL доверенного parent и повторите запуск; не заменяйте roots symlink/junction. |
