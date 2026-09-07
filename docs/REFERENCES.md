# REFERENCES

> Канонический реестр происхождения методов, реализаций, библиотек, статей,
> моделей, весов и значимых исходных данных анализаторов FakeDetector.

## Назначение и правила

Правило проекта: **NO PROVENANCE — NO ANALYZER**.

Реальный анализатор не считается завершённым, пока для всех применимых внешних
методов и реализаций не зафиксированы их происхождение, точная версия и лицензия.
Происхождение метода и происхождение реализации указываются раздельно:

- **Method source** отвечает на вопрос, откуда взят метод или концепция;
- **Implementation source** отвечает на вопрос, чей код фактически используется
  или на основе какого кода создана реализация.

Если анализатор использует собственную эвристику проекта, применяется точная
формулировка:

```text
Method source: project-specific heuristic
Implementation source: original FakeDetector implementation
```

Внешние библиотеки при этом перечисляются как building blocks. Наличие статьи,
похожего repository или общей идеи не позволяет приписывать им полный pipeline
FakeDetector. Для каждого анализатора, где применимо, реестр фиксирует:

- `analyzer_id` и `analyzer_version`;
- метод и источник метода или концепции;
- название статьи, авторов, publication/year, DOI или официальный URL;
- источник реализации, library/package, exact version, repository и официальную
  документацию;
- лицензию кода, модели и весов;
- источник модели/весов и значимый dataset оригинальных авторов;
- адаптацию FakeDetector и части, реализованные самим проектом;
- известные ограничения.

Stage 6 MVP является CPU-only. ML-анализаторы, model weights, PyTorch и CUDA в
него не входят; GPU не требуется. Реальные datasets/media на этом этапе в
repository не добавляются. Deterministic generated positive, negative,
false-positive/challenge и boundary/not-applicable fixtures не являются
статистической validation dataset и не должны так описываться.

## Общие библиотеки и инструменты

### Python standard library

- Назначение: базовые операции, hashing и техническая обработка без внешней
  runtime dependency для `audio_pcm_quality`.
- Версия runtime: Python 3.12.
- Документация: <https://docs.python.org/3.12/>.
- Source: <https://github.com/python/cpython>.
- License: PSF License; <https://docs.python.org/3.12/license.html>.

Конкретные используемые модули должны быть уточнены после фактической реализации
анализатора.

### Pillow

- Назначение: доступ к image metadata и sampled frames как implementation
  building block.
- Текущая dependency: `pillow>=12.3.0`; текущая разрешённая lock-версия —
  `12.3.0`.
- Repository: <https://github.com/python-pillow/Pillow>.
- Документация: <https://pillow.readthedocs.io/>.
- License: MIT-CMU; <https://github.com/python-pillow/Pillow/blob/12.3.0/LICENSE>.

### OpenCV

- Назначение: planned implementation building block для ORB descriptors и
  RANSAC-based model fitting в `image_copy_move_correspondence`.
- Planned package pin: `opencv-python-headless==4.14.0.94`.
- Upstream repository: <https://github.com/opencv/opencv>.
- Python packaging repository: <https://github.com/opencv/opencv-python>.
- Package: <https://pypi.org/project/opencv-python-headless/4.14.0.94/>.
- Официальная документация: <https://docs.opencv.org/4.x/>.
- License: Apache License 2.0;
  <https://github.com/opencv/opencv/blob/4.x/LICENSE>.

Pin является planned dependency decision до Increment 2. До основной реализации
обязателен smoke gate: установка пакетов, `import numpy`, `import cv2`, создание
ORB и минимальная descriptor operation. Несовместимая пара wheels может быть
скорректирована как dependency correction без пересмотра архитектуры Stage 6.

### NumPy

- Назначение: planned array/numerical building block для
  `image_copy_move_correspondence`.
- Planned package pin: `numpy==2.5.2`.
- Project: <https://numpy.org/>.
- Repository: <https://github.com/numpy/numpy>.
- Package: <https://pypi.org/project/numpy/2.5.2/>.
- Официальная документация: <https://numpy.org/doc/stable/>.
- License: основной код NumPy — BSD-3-Clause; поставка также содержит компоненты
  с лицензиями, перечисленными в versioned license file:
  <https://github.com/numpy/numpy/blob/v2.5.2/LICENSE.txt>.

Pin имеет тот же статус planned dependency decision и проходит общий smoke gate
Increment 2 до реализации copy-move analyzer.

## Analyzer references

### image_metadata_consistency

- `analyzer_id`: `image_metadata_consistency`.
- `analyzer_version`: `1.0.0`.
- Method: deterministic consistency checks доступных image metadata и
  подтверждённых технических параметров.
- Method source: project-specific heuristic.
- Implementation source: original FakeDetector implementation.
- Implementation building block: Pillow; сведения о версии, source и license
  приведены в разделе «Общие библиотеки и инструменты».
- Model/weights source: не применяется.
- Dataset/source: не применяется; используются deterministic generated fixtures.
- FakeDetector-specific adaptation: правила consistency, applicability,
  bounded metadata handling, candidate findings и их преобразование в `Finding`.
- Реализуется самим FakeDetector: вся логика consistency и threshold/policy
  interpretation.
- Known limitations: отсутствие EXIF или иных естественно необязательных metadata
  само по себе не является finding; metadata могут быть удалены обычным export,
  пересылкой или повторным сохранением. Анализатор не заявляется научно
  валидированным forensic detector.

### audio_pcm_quality

- `analyzer_id`: `audio_pcm_quality`.
- `analyzer_version`: `1.0.0`.
- Method: peak, RMS, DC offset, silence и full-scale sample ratio как стандартные
  signal metrics, объединённые в bounded техническую эвристику.
- Method source: project-specific heuristic на основе стандартных signal metrics.
- Implementation source: original FakeDetector implementation.
- Implementation building block: Python standard library.
- Model/weights source: не применяется.
- Dataset/source: не применяется; используются deterministic generated fixtures.
- FakeDetector-specific adaptation: bounded PCM processing, applicability,
  candidate findings и их преобразование в `Finding`.
- Реализуется самим FakeDetector: расчёт метрик, interpretation и threshold
  policy.
- Versioned deterministic MVP default: `full_scale_sample_ratio` threshold =
  `0.001`.
- Known limitations: threshold не является статистически валидированным forensic
  threshold; метрики качества PCM не обнаруживают синтетическую речь и не
  доказывают искусственное происхождение аудио.

### video_sampled_frame_quality

- `analyzer_id`: `video_sampled_frame_quality`.
- `analyzer_version`: `1.0.0`.
- Method: bounded deterministic comparison подготовленных sampled frames.
- Method source: project-specific heuristic.
- Implementation source: original FakeDetector implementation.
- Implementation building blocks: Pillow и Python `hashlib`.
- Model/weights source: не применяется.
- Dataset/source: не применяется; используются deterministic generated fixtures.
- FakeDetector-specific adaptation: sampling-scope interpretation, bounded frame
  comparison, applicability, candidate findings и их преобразование в `Finding`.
- Реализуется самим FakeDetector: вся comparison и finding policy.
- Known limitations: анализируется только ограниченная выборка подготовленных
  кадров; finding не является доказательством video forgery и не заменяет
  temporal или content detector.

### image_copy_move_correspondence

- `analyzer_id`: `image_copy_move_correspondence`.
- `analyzer_version`: `1.0.0`.
- Method: поиск пространственно разделённых соответствий локальных признаков с
  bounded filtering и RANSAC-based geometric consistency.
- Method source: project-specific heuristic, использующая ORB и RANSAC только как
  method building blocks.
- Implementation source: original FakeDetector implementation поверх OpenCV и
  NumPy.
- Model/weights source: не применяется.
- Dataset/source: не применяется; используются deterministic generated fixtures.

Method building blocks:

1. **ORB.** Ethan Rublee, Vincent Rabaud, Kurt Konolige, Gary Bradski. “ORB: An
   efficient alternative to SIFT or SURF.” Proceedings of the IEEE International
   Conference on Computer Vision (ICCV), 2011. DOI:
   <https://doi.org/10.1109/ICCV.2011.6126544>.
2. **RANSAC.** Martin A. Fischler, Robert C. Bolles. “Random Sample Consensus: A
   Paradigm for Model Fitting with Applications to Image Analysis and Automated
   Cartography.” Communications of the ACM, 1981. DOI:
   <https://doi.org/10.1145/358669.358692>.

Implementation building blocks:

- OpenCV / `opencv-python-headless==4.14.0.94` — ORB descriptors и
  RANSAC-enabled geometric operations;
- `numpy==2.5.2` — bounded numerical/array operations.

FakeDetector-specific adaptation и original implementation:

- spatial separation;
- bounded match filtering;
- cluster acceptance policy;
- threshold/cap policy;
- преобразование candidate findings в `Finding`;
- `correlation_group` policy.

Versioned deterministic MVP defaults:

| Параметр | Значение |
|---|---:|
| `min_dimension_px` | `128` |
| `max_pixels` | `12_000_000` |
| `max_keypoints` | `5_000` |
| `descriptor_ratio` | `0.75` |
| `min_spatial_separation_px` | `max(32, 0.05 * min_dimension)` |
| `ransac_reprojection_threshold_px` | `3` |
| `min_cluster_inliers` | `12` |
| `min_cluster_inlier_ratio` | `0.5` |
| `max_clusters` | `4` |

Эти значения не являются статистически валидированными forensic thresholds.
Они являются воспроизводимыми MVP defaults и могут изменяться в Stage 6 только
после обоснования deterministic positive/negative/challenge fixtures и фиксации
изменения.

Known limitations: повторяющиеся текстуры, симметрия, сжатие и малые изображения
могут приводить к ложным или пропущенным соответствиям. Полный copy-move pipeline
FakeDetector не заявляется реализацией одной из перечисленных статей: ORB и
RANSAC используются только как building blocks собственной bounded heuristic.
