# Контролируемая демонстрационная оценка дипломного ансамбля

Дата эксперимента: **2026-10-13**. Задание:
`STAGE12-DIPLOMA-DEMO-EVALUATION-SPRINT1`. Baseline:
`4459e795b8d784a4e683487c0d5b3f8e155b8bce` (main после принятого PR #71).
Это исследовательский черновик практической главы диплома и свидетельства
инженерного прогона. **AGENT SELF-REPORT IS NOT OWNER ACCEPTANCE.**
Текущий статус приёмки — [ROADMAP](../ROADMAP.md#diploma-demo-evaluation-sprint1).

## 1. Цель эксперимента

Проверить поведение существующего `diploma_ensemble_v1@0.1.0` на фиксированном
корпусе файлов, созданных собственным детерминированным генератором. Задачи:
показать путь от входного файла до объяснимой оценки, сравнить одну основу до
и после известного преобразования, выявить повышенные отклики контролей и
слабые ответы на целевые воздействия, подготовить воспроизводимую демонстрацию.

Это **контролируемый воспроизводимый инженерный эксперимент**. Он не является
репрезентативным deepfake benchmark, внешней валидацией, production-калибровкой,
доказательством общей точности или чувствительности/специфичности в реальном мире.
Оценка обозначает технические аномалии, а не вероятность подделки.

Роли зафиксированы до основного прогона:

- `control`: генератор не вносил намеренную целевую манипуляцию;
- `manipulated`: генератор внёс указанное детерминированное преобразование;
- `confound_control`: доброкачественное содержание или обработка, способные
  вызывать похожий отклик.

Ground truth означает исключительно действие генератора. Синтетические контроли
не называются «реальными», «подлинными» или доказанно немодифицированными файлами.
Роль `manipulated` не утверждает, что аналогичная обработка в практике злонамеренна:
повторный JPEG-экспорт, например, может быть обычной операцией.

## 2. Состав тестового корпуса

Всего **40 файлов**, **10 базовых групп**: 14 image, 14 audio, 12 video;
10 `control`, 16 `manipulated`, 14 `confound_control`.
Все 40 относятся к **FILE_LEVEL_E2E**. COMPONENT_LEVEL случаев — **0**.
Дубликаты для достижения численности не добавлялись; media SHA-256 уникальны.
Полный размер исходных файлов — 24 575 484 байта.

| Media | control | manipulated | confound_control | observation | holdout |
| --- | --- | --- | --- | --- | --- |
| image | 4 | 5 | 5 | 10 | 4 |
| audio | 3 | 6 | 5 | 10 | 4 |
| video | 3 | 5 | 4 | 8 | 4 |

Разделение задано функцией от стабильного `pair_id`: числовой суффикс, кратный
трём, означает `holdout_demo`, остальные — `calibration_observation`.
Все варианты одной основы остаются в одном split. Observation содержит
28 файлов и 7 основ; holdout — 12 файлов и 3 основы (`image-03`, `audio-03`,
`video-03`). Membership, роли, seeds, имена и параметры после основного прогона
не менялись. Название `calibration_observation` **не разрешало настройку модели**.

Holdout здесь демонстрационный, а не слепая внешняя проверка: шестифайловый
development smoke до основного прогона включал `audio-03-control` и
`audio-03-clip`. Этот факт ограничивает интерпретацию независимости holdout;
веса, пороги и нормализаторы после smoke или основного прогона не менялись.

Количество по каждому преобразованию приведено в таблицах файлов ниже
(одна строка — один файл); отдельная сводка `transformation → count` находится
в `summary.json` и разделе A внешнего `tables/report.md` для обоих splits.

## 3. Методика генерации и происхождение

Инструмент — [scripts/diploma_demo_evaluation.py](../../scripts/diploma_demo_evaluation.py),
версия генератора `diploma-demo-1.0.0`. Все исходные изображения, звуки и кадры
созданы first-party кодом; внешних датасетов, личных медиа, моделей, шрифтов,
веб-загрузок и сторонних генеративных сервисов нет. Происхождение библиотек
описано в [REFERENCES, общие инструменты](../REFERENCES.md#общие-библиотеки-и-инструменты),
происхождение применяемой видеопредобработки — в
[M1-F](../REFERENCES.md#dense-video-foundations-m1-f--2026-09-21).
Новых зависимостей или заимствованных реализаций не добавлено.

Среда: Windows 11 build 26200, Python 3.12.10, NumPy 2.5.2, Pillow 12.3.0,
opencv-python-headless 4.14.0.94, pyjpegio 0.3.0, FFmpeg/ffprobe
9.0.1-full_build-www.gyan.dev. Это фактическая среда эксперимента, не новая
требуемая версия или изменение лицензирования проекта.

Изображения: процедурная геометрия с градиентом; псевдоестественная цветная
текстура; низкоамплитудный шум. Обычный размер 768×768; resize JPEG — 640×640.
Seeds — 12001…12004. Варианты включают несовпадение EXIF-размеров, копирование
области 176×176, локальный bilinear resize 264→176→264, локальное усиление
остатка, повторяющийся узор, усиленную текстуру, PNG-resize и JPEG-экспорты
Q90, Q40→Q90, Q90→Q90. Resampling — фактическая интерполяция пикселей, а не
подстановка ожидаемой метрики анализатора.

Аудио: WAV PCM s16le, mono, 8 kHz, 65 536 samples (8.192 s), seeds
22001…22003. Основы — chirp/тональная смесь, broadband-шум и гармоническая
смесь с речеподобной амплитудной/спектральной огибающей. Последняя не является
записью речи или моделью синтеза речи. Внесены разрыв, локальная смена спектра,
повтор 16 384 samples, изменение низкоэнергетического уровня и clipping.
Контроли-confounds — transient, loop, gain change, silence и near-silence.

Видео: 80 кадров 320×180, исходные 8 fps, seeds 32001…32003; перемещение
объекта, панорамирование текстурного поля, орбитальное движение. Кодирование
MPEG-4 intra, q=2, yuv420p, `threads=1`, `bitexact`, без metadata, с
`fps_mode=passthrough`, track time scale 8000. Варианты: freeze, дальний повтор,
повтор блока, визуальная вставка, PTS gap; confounds — scene cut, VFR,
периодическое движение и статичная сцена.

В development smoke разрыв PTS первоначально стоял на кадре 12: следующий
кадр пары оказался за штатной двухсекундной границей dense-окна. До финальной
генерации он перенесён на кадр 8; величина gap и runtime не менялись. Также
до основного прогона устранена мутация списка координат библиотекой Pillow:
в `paste` передаётся tuple. Первая генерация сохранена отдельно как
диагностический артефакт; evaluator отверг её manifest до анализа файлов.
Это исправления генератора, не калибровка и не исключение неудобных результатов.

Финальная генерация выполнена дважды. **Все 40 media-файлов и manifest
побайтно совпали**, включая 12 MP4. `load_manifest` проверил обе копии.
Гарантия относится к зафиксированной среде; переносимость байтов между
другими версиями кодеков/библиотек не заявляется.

Manifest SHA-256:
`ea2561a66a94665c3be76287131ff36695e3e042975545003e238976b4205b4a`.
Fingerprint дизайна samples:
`03633647f20bf30d81645fc6ce5592bee7824cb8106e412802178525a291726f`.
Каждая строка manifest содержит sample/pair ID, media, role, split, generator
version, seed, base, transformation и параметры, target families, expected
confound, формат, относительное имя, SHA-256, размер и evidence level.

## 4. Методика прогона и воспроизведение

Команды из checkout, PowerShell; `$DemoRoot` должен указывать на **новый или
пустой абсолютный каталог вне репозитория**:

```powershell
$DemoRoot = Join-Path $env:USERPROFILE 'Desktop\FakeDetector-Work\diploma-demo-evaluation'
uv run python scripts/diploma_demo_evaluation.py generate --output $DemoRoot
uv run python scripts/diploma_demo_evaluation.py evaluate --corpus $DemoRoot
uv run python scripts/diploma_demo_evaluation.py report --corpus $DemoRoot
```

Для второй генерации используется другой пустой внешний каталог. Нельзя
повторно генерировать поверх уже замороженного корпуса. `report` разрешает
обновлять только производные таблицы; source media, freeze, manifest и
сохранённые результаты не перезаписываются. Относительные пути, каталог
репозитория и его предки, symlinks/junctions и выход за workspace отвергаются.

Каждый файл проходит `AnalysisApplicationService.submit`, штатные intake,
security/file validation, очередь, preprocessing, отдельные analyzer workers,
assessment, persistence и cleanup. Ожидание завершается через публичный
`get_result` только после публикации терминального результата. Это локальная
adapter-neutral граница приложения: HTTP transport и браузер в эксперименте
не измерялись. Анализаторы напрямую не вызываются; тестовые структуры PTS
не подставляются. Auth-настройки остаются включёнными, сетевой listener не
запускается. Из diploma config изменены только три пути хранения.

Перед генерацией сохранён `freeze.json`: вся production Python-реализация,
diploma config, lockfile, версии инструментов и fingerprint assessment.
Перед оценкой проверяются freeze, manifest, membership и все file hashes;
после оценки проверка повторяется. Fingerprint `_assessment.py` с LF:
`0b022e995316fecde23b7afbbeb2f32bb836e7bc973fdd3d0ed86c6fc06a2a1b`.

Все 40 файлов завершились со статусом `completed`, полнотой `complete` и
успешной очисткой. Сумма измеренных интервалов submission→result составила
**160.781 s**; это один запуск, не SLA или статистический benchmark.
ERROR, TIMEOUT, PARTIAL, `insufficient` completeness и пропущенных файлов — 0.
При этом зафиксированы **10 NOT_APPLICABLE** результатов DQ на PNG и
**8 insufficient_evidence** откликов завершённых анализаторов. Выполнение
метода не тождественно достаточности его измерения.

Внешние артефакты: `corpus/`, `freeze.json`, `manifest.json`,
`manifest.sha256`, `reproducibility.json`, `results/*.json`,
`results/index.jsonl`, `results/run.json`, `results/complete.json`,
`tables/score-by-sample.csv`, `family-responses.csv`, `analyzer-responses.csv`,
`pair-deltas.csv`, `samples.json`, `summary.json`, `report.md`.
CSV записаны UTF-8 с BOM для Excel. Runtime JSON и медиа в Git не входят.

## 5. Система оценки

Используется неизменённая политика
[PROJECT §10.8](../PROJECT.md#diploma-ensemble) и
[METHODS, нормализаторы](../METHODS.md#diploma-ensemble-normalization).
Замороженные условия: CORE 1.00, EXPERIMENTAL 0.65, EXPERIMENTAL_WEAK 0.35;
family factors 1/0.25/0.10/0; capacities image=3.4375, audio=2.8125,
video=2.05; LOW ≤25, MEDIUM 25<score≤55, HIGH >55; probability=null.
Это фиксация условий данного опыта, не новая нормативная спецификация.

Таблицы берут нормализованные отклики из фактических `AnalyzerResult` и Findings
через существующие функции ансамбля. Отдельно сохранены weight, effective
response, family factor, вклад после уменьшения и вклад в score. Сумма
семейств сверена с сохранённым runtime score без разбора округлённого текста.
ATD/ASC остаются одним `audio_transition`, noise/resampling — одним
`image_local_processing`. Семейства не считаются независимыми.

Неопределённый отклик анализатора хранится как null. Семейство без пригодного
измерения даёт арифметический ноль без уменьшения канонической ёмкости.
Такие нули входят в распределения семейных вкладов; пригодность указана отдельно.
Распределения анализаторов содержат только определённые отклики. Внешний отчёт
сохраняет каждый sample ID даже при сбое; неоценённый файл не превращается в LOW.

## 6. Результаты

Все числа ниже — **только на этом контролируемом демонстрационном корпусе**.
Это demo detection / elevated-control rates, не production TPR/FPR,
общая accuracy или оценка естественной частоты атак.

| Показатель | Весь корпус | calibration_observation | holdout_demo |
| --- | --- | --- | --- |
| Demo manipulated >25 | 12/16 (75.00%) | 9/12 (75.00%) | 3/4 (75.00%) |
| Demo manipulated >55 | 2/16 (12.50%) | 1/12 (8.33%) | 1/4 (25.00%) |
| Demo elevated controls >25 | 9/24 (37.50%) | 5/16 (31.25%) | 4/8 (50.00%) |
| Demo elevated controls >55 | 2/24 (8.33%) | 0/16 (0.00%) | 2/8 (25.00%) |
| Pairwise score increase | 14/16 (87.50%) | 11/12 (91.67%) | 3/4 (75.00%) |
| Median pair delta | 10.370852 | 10.370852 | 21.567579 |

Доли elevated-control объединяют `control` и `confound_control` (24 файла);
матрица порогов разделяет эти роли. Доли используют все файлы соответствующих
ролей; отсутствующие оценки учитывались бы отдельно. Pairwise rate использует
16 control→manipulated сравнений с двумя определёнными score, а не все 30
вариантов, среди которых 14 confounds. Наблюдения внутри пар зависимы.

### Матрица текущих порогов

| Split | Role | LOW | MEDIUM | HIGH | Unassessed |
| --- | --- | --- | --- | --- | --- |
| all | confound_control | 7 | 5 | 2 | 0 |
| all | control | 8 | 2 | 0 | 0 |
| all | manipulated | 4 | 10 | 2 | 0 |
| calibration_observation | confound_control | 5 | 4 | 0 | 0 |
| calibration_observation | control | 6 | 1 | 0 | 0 |
| calibration_observation | manipulated | 3 | 8 | 1 | 0 |
| holdout_demo | confound_control | 2 | 1 | 2 | 0 |
| holdout_demo | control | 2 | 1 | 0 | 0 |
| holdout_demo | manipulated | 1 | 2 | 1 | 0 |

### Все файлы: calibration_observation

| sample_id | role | transformation | score | level | strongest family | Два наибольших отклика |
| --- | --- | --- | --- | --- | --- | --- |
| audio-01-control | control | none | 36.249065 | MEDIUM | audio_transition | ASC=0.929762, ABN=0.828768 |
| audio-01-loop | confound_control | periodic_loop | 49.180351 | MEDIUM | audio_transition | ARC=1.000000, ATD=0.903635 |
| audio-01-spectral | manipulated | local_spectral_change | 40.748509 | MEDIUM | audio_transition | ABN=1.000000, ASC=0.999917 |
| audio-01-splice | manipulated | hard_splice | 37.102728 | MEDIUM | audio_transition | ASC=0.936573, ATD=0.863383 |
| audio-01-transient | confound_control | sharp_transient | 37.925707 | MEDIUM | audio_transition | ATD=0.954147, ASC=0.935059 |
| audio-02-control | control | none | 20.818521 | LOW | audio_transition | ATD=0.786494, ASC=0.311187 |
| audio-02-floor | manipulated | background_floor_change | 39.420705 | MEDIUM | audio_transition | ABN=0.994876, ATD=0.930717 |
| audio-02-level | confound_control | level_change | 32.462421 | MEDIUM | audio_transition | ABN=0.885294, ATD=0.836685 |
| audio-02-repeat | manipulated | copied_segment | 43.708445 | MEDIUM | audio_repetition | ARC=1.000000, ATD=0.786494 |
| audio-02-silence | confound_control | silence | 0.000000 | LOW | нет | нет положительных |
| image-01-control | control | none | 0.028184 | LOW | image_local_processing | R=0.002635, N=0.000531 |
| image-01-metadata | manipulated | exif_dimension_mismatch | 29.119093 | MEDIUM | image_metadata | MD=1.000000, R=0.002635 |
| image-01-resize | confound_control | benign_resize | 0.879922 | LOW | image_local_processing | R=0.084877, N=0.006174 |
| image-02-control | control | none | 8.733259 | LOW | image_local_processing | R=0.849292, N=0.033753 |
| image-02-copy | manipulated | copy_move | 37.820542 | MEDIUM | image_region_correspondence | CM=1.000000, R=0.849292 |
| image-02-resample | manipulated | local_resampling | 9.471850 | LOW | image_local_processing | R=0.845780, N=0.337965 |
| image-02-tiles | confound_control | repetitive_texture | 37.985342 | MEDIUM | image_region_correspondence | CM=1.000000, R=0.873560 |
| image-04-control | control | none | 8.505885 | LOW | image_local_processing | R=0.828094, N=0.029222 |
| image-04-local_noise | manipulated | local_residual_mismatch | 8.505885 | LOW | image_local_processing | R=0.828094, N=0.029222 |
| image-04-strong_noise | confound_control | strong_texture | 8.431501 | LOW | image_local_processing | R=0.828094 |
| video-01-control | control | none | 17.011913 | LOW | video_repetition | VRC=0.995096, VIS=0.001316 |
| video-01-cut | confound_control | ordinary_scene_cut | 20.295701 | LOW | video_repetition | VRC=0.995148, VIS=0.193600 |
| video-01-distant | manipulated | distant_repeated_content | 17.095644 | LOW | video_repetition | VRC=1.000000, VIS=0.001316 |
| video-01-freeze | manipulated | frozen_run | 65.876131 | HIGH | video_quality | VRC=1.000000, VQ=1.000000 |
| video-02-control | control | none | 16.815895 | LOW | video_repetition | VRC=0.979548, VIS=0.005383 |
| video-02-timing | manipulated | pts_gap | 29.008305 | MEDIUM | video_repetition | VRC=0.979389, PTS=0.714286 |
| video-02-transition | manipulated | strong_visual_transition | 25.365189 | MEDIUM | video_repetition | VRC=0.979548, VIS=0.506127 |
| video-02-vfr | confound_control | benign_variable_rate | 22.506952 | LOW | video_repetition | VRC=0.979548, PTS=0.333333 |

### Все файлы: holdout_demo

| sample_id | role | transformation | score | level | strongest family | Два наибольших отклика |
| --- | --- | --- | --- | --- | --- | --- |
| audio-03-clip | manipulated | full_scale_clipping | 87.796100 | HIGH | audio_quality | PCM=1.000000, ATD=1.000000 |
| audio-03-control | control | none | 48.228299 | MEDIUM | audio_transition | ATD=0.871658, ARC=0.729334 |
| audio-03-quiet | confound_control | near_silence | 41.935387 | MEDIUM | audio_transition | ABN=1.000000, ASC=1.000000 |
| audio-03-repeat | manipulated | copied_segment | 53.840002 | MEDIUM | audio_transition | ARC=1.000000, ATD=0.960556 |
| image-03-control | control | single_jpeg_export | 0.398084 | LOW | image_local_processing | N=0.039098 |
| image-03-recompress | manipulated | aligned_recompression | 37.921539 | MEDIUM | image_recompression | DQ=1.000000, R=0.848613 |
| image-03-reexport | confound_control | benign_jpeg_reexport | 0.398139 | LOW | image_local_processing | N=0.039103 |
| image-03-resize | confound_control | benign_jpeg_resize | 0.373346 | LOW | image_local_processing | N=0.036668 |
| video-03-control | control | none | 17.124316 | LOW | video_repetition | VRC=0.999610, VIS=0.003386 |
| video-03-loop | confound_control | periodic_motion | 66.036076 | HIGH | video_quality | VRC=1.000000, VQ=1.000000 |
| video-03-repeat | manipulated | repeated_block | 17.124316 | LOW | video_repetition | VRC=0.999610, VIS=0.003386 |
| video-03-static | confound_control | static_scene | 65.853659 | HIGH | video_quality | VRC=1.000000, VQ=1.000000 |

Сокращения анализаторов расшифрованы в таблице всех 14 анализаторов ниже.
Полные пер-анализаторные отклики каждого файла, включая null и причины,
даны во внешних CSV/JSON и `tables/report.md` (разделы B/G).
Ранжирование strongest family выбирает только положительный отклик.

### Парные изменения control→manipulated

| Split | variant (основа: тот же pair_id-control) | control score | variant score | delta | Изменения семейств |
| --- | --- | --- | --- | --- | --- |
| calibration_observation | audio-01-spectral | 36.249065 | 40.748509 | 4.499445 | audio_background=+0.059931, audio_repetition=+0.000688, audio_transition=+0.065928 |
| calibration_observation | audio-01-splice | 36.249065 | 37.102728 | 0.853664 | audio_repetition=-0.000154, audio_transition=+0.024163 |
| calibration_observation | audio-02-floor | 20.818521 | 39.420705 | 18.602185 | audio_background=+0.330769, audio_repetition=+0.002733, audio_transition=+0.189684 |
| calibration_observation | audio-02-repeat | 20.818521 | 43.708445 | 22.889925 | audio_background=+0.000074, audio_repetition=+0.643706 |
| holdout_demo | audio-03-clip | 48.228299 | 87.796100 | 39.567801 | audio_background=-0.012101, audio_quality=+1.000000, audio_repetition=+0.033961, audio_transition=+0.090984 |
| holdout_demo | audio-03-repeat | 48.228299 | 53.840002 | 5.611703 | audio_background=-0.078654, audio_repetition=+0.175933, audio_transition=+0.060550 |
| calibration_observation | image-01-metadata | 0.028184 | 29.119093 | 29.090909 | image_metadata=+1.000000 |
| calibration_observation | image-02-copy | 8.733259 | 37.820542 | 29.087283 | image_local_processing=-0.000125, image_region_correspondence=+1.000000 |
| calibration_observation | image-02-resample | 8.733259 | 9.471850 | 0.738591 | image_local_processing=+0.025389 |
| holdout_demo | image-03-recompress | 0.398084 | 37.921539 | 37.523456 | image_local_processing=+0.289869, image_recompression=+1.000000 |
| calibration_observation | image-04-local_noise | 8.505885 | 8.505885 | 0.000000 | нет |
| calibration_observation | video-01-distant | 17.011913 | 17.095644 | 0.083731 | video_repetition=+0.001716 |
| calibration_observation | video-01-freeze | 17.011913 | 65.876131 | 48.864219 | video_quality=+1.000000, video_repetition=+0.001716 |
| calibration_observation | video-02-timing | 16.815895 | 29.008305 | 12.192410 | video_repetition=-0.000056, video_timing=+0.250000 |
| calibration_observation | video-02-transition | 16.815895 | 25.365189 | 8.549294 | video_visual_transition=+0.175261 |
| holdout_demo | video-03-repeat | 17.124316 | 17.124316 | 0.000000 | нет |

Все 30 сравнений, включая доброкачественные варианты, содержатся в
`pair-deltas.csv`; изменившиеся семейства с точными дельтами — там же.

### Повышенные отклики контролей

**Elevated control responses**, все девять случаев:

| sample_id | split | role | score | level |
| --- | --- | --- | --- | --- |
| audio-01-control | calibration_observation | control | 36.249065 | MEDIUM |
| audio-01-loop | calibration_observation | confound_control | 49.180351 | MEDIUM |
| audio-01-transient | calibration_observation | confound_control | 37.925707 | MEDIUM |
| audio-02-level | calibration_observation | confound_control | 32.462421 | MEDIUM |
| audio-03-control | holdout_demo | control | 48.228299 | MEDIUM |
| audio-03-quiet | holdout_demo | confound_control | 41.935387 | MEDIUM |
| image-02-tiles | calibration_observation | confound_control | 37.985342 | MEDIUM |
| video-03-loop | holdout_demo | confound_control | 66.036076 | HIGH |
| video-03-static | holdout_demo | confound_control | 65.853659 | HIGH |

Сильный отклик на обычную текстуру, loop или статичную сцену сам по себе
не доказывает algorithmic false positive: методы измеряют соответствующие
аномалии/сходства, а роль корпуса не является экспертной меткой подделки.

### Слабые ответы на контролируемые преобразования

**Missed/weak controlled transformations**, все четыре случая LOW:

| sample_id | split | role | score | level |
| --- | --- | --- | --- | --- |
| image-02-resample | calibration_observation | manipulated | 9.471850 | LOW |
| image-04-local_noise | calibration_observation | manipulated | 8.505885 | LOW |
| video-01-distant | calibration_observation | manipulated | 17.095644 | LOW |
| video-03-repeat | holdout_demo | manipulated | 17.124316 | LOW |

### Поведение всех 12 семейств

| Family | count | usable | nonzero | mean | median | max | Роли |
| --- | --- | --- | --- | --- | --- | --- | --- |
| image_metadata | 14 | 14 | 1 | 0.071429 | 0.000000 | 1.000000 | M |
| image_recompression | 14 | 4 | 1 | 0.071429 | 0.000000 | 1.000000 | M |
| image_region_correspondence | 14 | 14 | 2 | 0.142857 | 0.000000 | 1.000000 | CC,M |
| image_local_processing | 14 | 14 | 14 | 0.177299 | 0.291111 | 0.325595 | CC,C,M |
| audio_quality | 14 | 14 | 1 | 0.071429 | 0.000000 | 1.000000 | M |
| audio_transition | 14 | 13 | 13 | 0.653303 | 0.729053 | 0.812500 | CC,C,M |
| audio_repetition | 14 | 13 | 13 | 0.213690 | 0.008884 | 0.650000 | CC,C,M |
| audio_background | 14 | 13 | 12 | 0.205495 | 0.262446 | 0.350000 | CC,C,M |
| video_quality | 12 | 12 | 3 | 0.250000 | 0.000000 | 1.000000 | CC,M |
| video_repetition | 12 | 12 | 12 | 0.347302 | 0.349083 | 0.350000 | CC,C,M |
| video_visual_transition | 12 | 12 | 11 | 0.021504 | 0.001535 | 0.177145 | CC,C,M |
| video_timing | 12 | 12 | 2 | 0.030556 | 0.000000 | 0.250000 | CC,M |

Обозначения ролей: C=`control`, M=`manipulated`, CC=`confound_control`.
Count — число файлов соответствующего media, usable — число файлов хотя бы
с одним пригодным членом семейства. Ненулевой отклик не равен доказанному
обнаружению целевого вмешательства. Раздельные распределения по splits
находятся в разделах F внешнего отчёта и в `summary.json.splits`.

### Поведение всех 14 анализаторов

| ID (сокращение) | maturity | usable | signal | no-signal | insufficient | N/A | mean | median | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_metadata_consistency (MD) | CORE | 14 | 1 | 13 | 0 | 0 | 0.071429 | 0.000000 | 1.000000 |
| image_jpeg_double_quantization (DQ) | CORE | 4 | 1 | 3 | 0 | 10 | 0.250000 | 0.000000 | 1.000000 |
| image_copy_move_correspondence (CM) | CORE | 14 | 2 | 12 | 0 | 0 | 0.142857 | 0.000000 | 1.000000 |
| image_noise_residual_consistency (N) | EXPERIMENTAL_WEAK | 13 | 12 | 1 | 1 | 0 | 0.050717 | 0.032329 | 0.337965 |
| image_resampling_consistency (R) | EXPERIMENTAL_WEAK | 11 | 11 | 0 | 3 | 0 | 0.621906 | 0.828094 | 0.873560 |
| audio_pcm_quality (PCM) | CORE | 14 | 1 | 13 | 0 | 0 | 0.071429 | 0.000000 | 1.000000 |
| audio_temporal_discontinuity (ATD) | EXPERIMENTAL | 13 | 13 | 0 | 1 | 0 | 0.884825 | 0.871658 | 1.000000 |
| audio_spectral_consistency (ASC) | EXPERIMENTAL | 13 | 13 | 0 | 1 | 0 | 0.699381 | 0.897443 | 1.000000 |
| audio_repeated_segment_correspondence (ARC) | EXPERIMENTAL | 13 | 13 | 0 | 1 | 0 | 0.354042 | 0.013889 | 1.000000 |
| audio_background_noise_consistency (ABN) | EXPERIMENTAL_WEAK | 13 | 12 | 1 | 1 | 0 | 0.632293 | 0.828768 | 1.000000 |
| video_sampled_frame_quality (VQ) | CORE | 12 | 3 | 9 | 0 | 0 | 0.250000 | 0.000000 | 1.000000 |
| video_repeated_content_correspondence (VRC) | EXPERIMENTAL_WEAK | 12 | 12 | 0 | 0 | 0 | 0.992291 | 0.997379 | 1.000000 |
| video_visual_discontinuity (VIS) | EXPERIMENTAL_WEAK | 12 | 11 | 1 | 0 | 0 | 0.061440 | 0.004385 | 0.506127 |
| video_timing_anomaly (PTS) | EXPERIMENTAL_WEAK | 12 | 2 | 10 | 0 | 0 | 0.087302 | 0.000000 | 0.714286 |

Для каждого из 14 анализаторов ERROR/TIMEOUT/SKIPPED/not observed/extraction
error = **0**. Среднее/медиана/максимум рассчитаны по пригодным откликам;
`usable = signal + no-signal`. Пригодные результаты представлены у всех
14/14 анализаторов; все 12/12 семейств имеют ненулевые наблюдения.
Раздельные таблицы по splits находятся в разделе G внешнего отчёта.

## 7. Анализ по изображениям

EXIF mismatch (`image-01-metadata`, observation) повысил score
0.028184→29.119093; семейство `image_metadata` изменилось 0→1.
Copy-move (`image-02-copy`, observation) дал 8.733259→37.820542, но
доброкачественный повторяющийся узор `image-02-tiles` также получил
`image_region_correspondence=1` и score 37.985342. Этот контроль показывает
необходимость предметной интерпретации совпадений областей.

На holdout JPEG Q40→Q90 (`image-03-recompress`) score вырос
0.398084→37.921539; `image_recompression=1`. Обычный Q90→Q90
(`image-03-reexport`) остался LOW 0.398139, resize JPEG — LOW 0.373346.
Это свидетельство данных конкретных операций/текстуры, не общая специфичность DQ.

Реальный локальный resize `image-02-resample` остался LOW 9.471850
(дельта 0.738591). Для `image-04-local_noise` score точно совпал с контролем:
8.505885. В raw metrics tile 0 residual MAD вырос 1.064453→4.257813,
но texture вырос примерно 1→4, и для изменённого tile отсутствуют matching
comparisons. Максимум сохранился на других tiles. Это установленная по raw
metrics граница matching; повышение веса не восстановило бы ненаблюдаемую
сравнительную метрику. У resampling этой основы уже был высокий baseline
max log2 ratio 4.817126, иллюстрирующий отклик на стохастическую текстуру.

## 8. Анализ по аудио

У chirp-контроля `audio-01-control` (observation) score 36.249065:
`audio_transition=0.724909`, `audio_background=0.290069`,
`audio_repetition=0.004527`. Hard splice увеличил score лишь до 37.102728,
тогда как обычный loop дал 49.180351, transient — 37.925707 и доброкачественное
изменение уровня broadband — 32.462421. Это содержательные confounds
нескольких семейств, а не независимые подтверждения монтажа.

Broadband repeat `audio-02-repeat` (observation) повысил score
20.818521→43.708445, delta=22.889925. Holdout `audio-03-repeat` повысил его
48.228299→53.840002, delta=5.611703: естественные периодические компоненты
основы уже дают сильный ARC baseline. Clipping `audio-03-clip` (holdout)
получил HIGH 87.796100, включая `audio_quality=1`.

Digital silence `audio-02-silence` имеет score 0 и completeness=complete,
при этом ATD/ASC/ARC/ABN — `insufficient_evidence`. Это не положительное
свидетельство подлинности. Near-silence `audio-03-quiet` (holdout)
получила MEDIUM 41.935387; важны относительные меры и квантование PCM.
Эксперимент не проверяет детекцию синтетической речи.

## 9. Анализ по видео

Freeze `video-01-freeze` (observation) повысил score
17.011913→65.876131. Однако статичная сцена `video-03-static` (holdout)
тоже получила HIGH 65.853659: `video_quality=1`, `video_repetition=0.35`,
остальные семейства — 0. Оба семейства реагируют на повторение; это наглядный
пример межсемейной корреляции. Периодическое движение `video-03-loop`
получило HIGH 66.036076 без намеренной целевой манипуляции.

Во всех 12 видео VRC дал ненулевой отклик. Дальний повтор
`video-01-distant` действительно наблюдён: сохранённая минимальная пара
связывает PTS 0…3000 и 64000…67000, оба distance numerator равны 0.
Нормализованный VRC response=1, семейный вклад=0.35; итог остаётся LOW
17.095644. Это не отсутствие измерения повтора: одиночного слабого семейства
недостаточно для перехода текущего порога. Исходный контроль уже имел высокий
VRC baseline, поэтому delta score всего 0.083731.

`video-03-repeat` (holdout) повторяет кадры 16…23, то есть участок [2,3) s.
Штатные dense-окна данного файла покрывают [0,2), [4,6), [8,10) s:
целевой блок в них не попадает. Legacy sampled quality также не сформировал
Finding. Все семейные вклады и score 17.124316 совпали с контролем.
Это ограничение покрытия FILE_LEVEL_E2E, сохранённое в отчёте.

PTS gap `video-02-timing` подтверждён в реальном MP4 и первом dense-окне:
gap 6000 ticks при медиане 1000 и time base 1/8000,
timing response=5/7, `video_timing=0.25`, score 29.008305.
Доброкачественный VFR `video-02-vfr` дал timing response=1/3,
score 22.506952. Gap — наблюдаемая временная нерегулярность, не доказательство
монтажа. COMPONENT_LEVEL подмены не использовались.

## 10. Анализ ограничений и набор live demo

Малый процедурный корпус содержит 10 зависимых базовых групп. Media и роли
распределены не как в реальной эксплуатации. Split отделяет также типы
содержимого, поэтому различия observation/holdout не позволяют измерить
обобщение или статистически сравнить модели. Не строились доверительные
интервалы, ROC-кривые, оптимальные thresholds или оценки population FPR/FNR.
Видео короткие и без аудиодорожки; изображения не являются фотографиями;
аудио не является человеческой речью. Длинные файлы и внешние данные не
исследованы. Применимость ограничена штатными окнами, matching и retrieval.

У выбранных шести сценариев split=`holdout_demo`. Выбор сделан **после**
прогона для учебной наглядности; он не используется для расчёта метрик.
Все 40 результатов выше и внешние полные таблицы остаются доступными.

| sample_id | Роль | Score / level | Учебный смысл |
| --- | --- | --- | --- |
| image-03-control | control | 0.398084 / LOW | Обычный JPEG-экспорт; отсутствие DQ Finding не означает подлинность |
| image-03-recompress | manipulated | 37.921539 / MEDIUM | Та же текстура после Q40→Q90; виден прирост recompression-family |
| audio-03-control | control | 48.228299 / MEDIUM | Речеподобная огибающая сама вызывает elevated control response |
| audio-03-clip | manipulated | 87.796100 / HIGH | Насыщение той же основы, CORE Finding и объяснимый прирост score |
| video-03-control | control | 17.124316 / LOW | Обычное движение; уже заметен высокий VRC baseline |
| video-03-static | confound_control | 65.853659 / HIGH | Доброкачественная статичная сцена показывает межсемейную корреляцию и предел интерпретации HIGH |

Видео-пара демонстрирует ограничение на доброкачественном варианте.
Показ `video-03-repeat` с неизменной оценкой в полной таблице обязателен при
обсуждении покрытия; он не скрывается отбором шести сцен. Для live demo файлы
из внешнего `corpus/` можно загрузить в уже существующий WebUI diploma profile.
Скриншоты и новый UI в этот sprint не создавались.

### Potential calibration actions for OWNER review

**CALIBRATION_RECOMMENDATION: NEED_MORE_DATA.** Текущие эмпирические ограничения
достаточны для демонстрации и формулировки гипотез, но не для выбора численных
весов/порогов. Ни одно действие ниже не реализовано.

| Категория | Точные свидетельства | Ожидаемый эффект / следующий gate |
| --- | --- | --- |
| NEED MORE DATA | Observation: audio-01-control=36.249065, image-02-tiles=37.985342; holdout: audio-03-control=48.228299, video-03-static=65.853659 | Расширить независимые основы и доброкачественные сценарии перед выбором operating point; внешние данные требуют отдельной задачи с provenance |
| ADD FAMILY CAP / CROSS-FAMILY CONTROL | Holdout video-03-static: quality=1 и repetition=0.35 от одной статичности; observation video-01-freeze=65.876131 использует те же семейства | Ограничение совместного голоса может уменьшить elevated responses статичных сцен, но также ослабить freeze; проверить обе группы до назначения cap |
| CHANGE NORMALIZER — гипотеза | Observation video-01-control=17.011913 и video-01-distant=17.095644, несмотря на observed zero-distance pair; holdout video-03-control=17.124316 | Изучить информативность высокого VRC baseline и роли minimum/max pooling; конкретная функция не выбрана и не внедрена |
| CHANGE WEIGHTS / CHANGE THRESHOLDS — отложено | Observation audio-01-control=36.249065 и splice=37.102728; holdout audio-03-control=48.228299 и repeat=53.840002 | Простое повышение порога может одновременно убрать control responses и скрыть целевые преобразования; корпус не обосновывает новое число |
| KEEP AS IS для воспроизведения | Observation image-01-metadata: delta=29.090909; holdout image-03-recompress: delta=37.523456; audio-03-clip: delta=39.567801 | Сохранить version 0.1.0 как зафиксированную контрольную точку; сравнение будущего варианта требует отдельного OWNER GATE |

Для `image-04-local_noise` (observation, delta=0) и `video-03-repeat`
(holdout, delta=0) сначала следует исследовать поддержку/matching и покрытие.
Переоценка коэффициентов не создаёт отсутствующие наблюдения. Изменение методов,
окон или retrieval также выходит за scope этого sprint.

## 11. Выводы

Получены воспроизводимые file-level свидетельства работы всех 14 анализаторов
и 12 семейств. На данном корпусе 14/16 целевых преобразований увеличили score,
12/16 превысили 25, 2/16 превысили 55. Среди 24 контролей с confounds
9/24 превысили 25 и 2/24 превысили 55. Медиана парного прироста — 10.370852.
Наряду с наглядными случаями сохранены четыре слабых ответа и все девять
elevated controls. Эти числа описывают корпус и не валидируют продукт в мире.

Ансамбль, public/config schemas и зависимости не изменены. Результаты дают
материал для практической главы и демонстрации с ограничениями; Stage 12,
научная/production-приёмка методов и калибровка этим экспериментом не закрыты.
Focused tests: **245 passed**. Единственный полный `uv run poe check` дал
pre-commit PASS, mypy PASS и pytest **3068 passed / 17 skipped / 1 failed**.
Fail — только sdist provenance для intended untracked-файлов, начиная с этого
отчёта; guard не менялся, staging запрещён заданием. Сверка архива подтвердила
ровно три новых untracked-члена без иных нарушений inventory/байтов на момент
сборки. Поэтому итог barrier — **OWNER_VERIFY_REQUIRED**, а не PASS.
CLI smoke выполнен отдельно — PASS. Полные логи и diff — во внешнем bundle.
Development verification dirty tree не называется strict certification;
после owner review и staging требуется повтор проверки владельцем.
