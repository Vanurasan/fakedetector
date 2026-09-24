# M2-BR1 — отбор noise residual и resampling методов

Дата: 2026-09-24. Baseline: `96184067ca91220a708203d88068f5a2387a83c1`.
Ветка: `feat/stage12-macro2-image-analyzer-expansion-wave1`; начальное дерево чистое.
Это исследовательское свидетельство, **не production-контракт и не приёмка
владельца**. Правила допуска — [METHODS](../METHODS.md#gate-принятия-метода),
происхождение — [REFERENCES](../REFERENCES.md#m2-br1--классические-residualresampling-методы-2026-09-24),
статус работ — [ROADMAP](../ROADMAP.md).

## 1. Результат отбора

| Кандидат | Исследованный профиль | Рекомендация | Полезный сигнал |
|---|---|---|---|
| `image_noise_residual_consistency` | `N-MAD-MATCH-1` | **RESEARCH_ONLY** | **WEAK**: локальная фильтрация видна, но matching существенно подавляет сигнал добавленного шума |
| `image_resampling_consistency` | `R-D2-MATCH-1` | **RESEARCH_ONLY** | **WEAK**: локальное увеличение bilinear заметно на части данных; JPEG, texture и support ограничивают различение |

Идентификаторы означают воспроизводимые exploratory measurements, не выбранные
production-методы. Ни один кандидат сейчас не рекомендуется для подбора
production threshold. Числа ниже — параметры исследовательского измерения и
его применимости, **не пороги подозрения, severity или вероятность подделки**.
Ни у одного рассмотренного метода не найдено буквальной универсальной границы,
которая заменяла бы эмпирическую калибровку на целевом распределении.

Наблюдаемая локальная обработка может быть доброкачественной. По одним пикселям
нельзя отличить намеренно скрывающий монтаж local denoise от той же операции
редактора при обычной ретуши. Поэтому задача метода — узкое измерение локального
различия, а не определение намерения или подлинности. Отсутствие измерения и
отсутствие отклонения не означают authentic/clean.

Production-каталог проверен: пять анализаторов `@1.0.0`, включая принятый DQ.
DQ не изменён и не перекалиброван; Grid остаётся `DEFERRED_RESEARCH_ONLY`.
Новых analyzers, registration, API, scoring, completeness, dependencies,
config/schema, ML, SciPy и runtime network нет.

## 2. Что действительно доступно в Macro 1

Основания: `CONTRACTS.md` §7.4–7.5; `preprocessing/_media_tools.py`,
`_requirements.py`, `_service.py`; `tests/test_stage5_internal_models.py`.
Graphify использован только для навигации: provenance SHA `625b9e83…` не совпадает
с baseline, поэтому **STALE**. Ограниченный query был усечён и не используется
как доказательство полноты. Пересборки нет; выводы ниже сверены с текущим кодом.

| Возможность | Факт и следствие для кандидатов |
|---|---|
| `normalized_image` | Lossless PNG, RGB/RGBA, EXIF transpose, без resize. Это display-referred RGB8, не RAW/linear radiance. Первый animation frame не представляет весь файл во времени |
| `extract_image_tiles` / `TileRegion` | Immutable uint8 tiles, half-open oriented coordinates, halo 0–2, `REFLECT_101`; не новый decode/resize pipeline |
| `to_luminance` | `Y'=0.299R+0.587G+0.114B`, float64; **alpha игнорируется**, следовательно explicit support mask обязателен |
| `smooth_luminance` / `high_pass_residual` | Binomial 3×3/5×5; residual = Y' − smoothing. Это остаток фильтра, не выделенный sensor noise |
| `finite_differences` | Только centered first differences `[-0.5,0,0.5]` x/y. Second difference, spatial autocorrelation и image periodicity API отсутствуют |
| `robust_local_statistics` | Median, unscaled MAD, Q25/Q75 с linear interpolation на целой core-plane. Masked summary и matching отсутствуют; пилот применяет NumPy к выбранным samples, не меняя общий helper |
| `residual_raster` | Тип/capability не означает наличие producer. Готового residual artifact нет; пилот вызывает private kernels на tiles |
| Ресурсы | Raster ≤2^22 pixels; ≤16 tiles, side≤512, halo≤2; residual workspace≤32 MiB. Это safety envelope, не обещание OS RSS quota |
| Provenance | Существующие controlled artifacts, source identity, immutable buffers и общий generated-artifact budget должны сохраняться при любом будущем подключении |

Пробелы: brightness/texture support selection; alpha/saturation/edge masks;
действительно независимая texture measure; bounded image second differences,
autocorrelation/spectra; local comparison и calibrated image-level aggregation.
Это вычисления кандидата, не основание добавлять публичные representations или
поля. CPU deadline и совокупный live workspace будущего consumer нужно проверять
дополнительно: каждый kernel preflight не учитывает все удерживаемые им arrays.

Пилот использует сохранённые внешние вырезки с заведомо известными pixels.
Он **не является integration test** controlled artifact reader/worker lifecycle.
В production нельзя копировать его прямой файловый доступ или автоматически
уменьшать неподходящее изображение для обхода raster limit.

## 3. Первичные источники и альтернативы

Полные названия, авторы, годы, URL/DOI и права каждого источника — в стабильных
записях `NR-MS09`, `NR-CB13`, `RS-PF05`, `RS-MS08`, `RS-K08`, `RS-KG09`
[реестра](../REFERENCES.md#m2-br1--классические-residualresampling-методы-2026-09-24).
Внешний исходный код не изучался и не копировался; preferred path —
**FIRSTPARTY_CODE**. Наличие кода IPOL не даёт ему автоматически лицензию статьи.

| Источник / семейство | Что действительно исследовано авторами и что ограничивает перенос |
|---|---|
| `NR-MS09`, локальные уровни шума | Abstract заявляет AWGN-сегментацию и оценку noise estimator при разных sigma, размерах регионов и JPEG quality. Это не доказательство одинакового noise level в современных фотографиях. Полный PDF недоступен; детали wavelet/segmentation и количественные показатели здесь не воспроизводятся |
| `NR-CB13`, noise curve / DCT | Оценка высокочастотной энергии по отобранным малотекстурным блокам и зависимость оценки от яркости. Статья прямо разбирает contamination текстурой. Это noise estimation, не проверка локального forensic detector/FPR. Заимствована необходимость matching, не опубликованные параметры или полный алгоритм |
| `RS-PF05`, EM/p-map | На 50 изображениях исследованы bicubic scaling/rotation, gamma, добавленный шум и compression. Сильная зависимость от JPEG; настройки авторов нельзя переносить как наш operating point. EM и поиск по transform templates добавляют стоимость и nuisance-параметры, поэтому не выбраны для первого bounded профиля |
| `RS-MS08`, производные / covariance | В доступном abstract аналитически обоснована периодичность интерполяции и производных. Полный текст не получен; complete Radon procedure и численные результаты не подтверждены. Не заявляется реализация статьи или равноценность двух осевых проекций Radon sweep |
| `RS-K08`, фиксированный предсказатель | Авторы используют 200 grayscale camera images, 100 для transformed tests, предварительную decimation×2 nearest и crops 256²; linear scaling/rotation. Это узкая камера/обработка, не smartphone validation. Фиксированный predictor и periodogram мотивируют bounded альтернативу EM |
| `RS-KG09`, JPEG-aware detector | Две камеры, по 100 RAW, контролируемые pre/post JPEG и linear transforms. Показаны как подавление сигнала, так и его усиление преобразованными JPEG-следами. Использование последнего как самостоятельного нового evidence дублирует часть compression/grid responsibility, поэтому не выбрано |

Выводы о применимости к FakeDetector далее — **инженерные выводы этого
исследования**, не утверждения, что все эти ограничения экспериментально
измерены в каждой статье. Порогов и заявленного FPR публикаций не переносим.

### Сравнение noise measurements

| Вариант | Польза | Причина выбора / ограничения |
|---|---|---|
| Fixed binomial residual + MAD | Простое, объяснимое, уже доступен kernel | Выбран для скрининга; MAD устойчивее к редким большим остаткам, но не отделяет fine texture от шума |
| Local variance / high-frequency energy | Реагирует на local noise, blur, sharpen | Записаны как diagnostics. Энергия residual включает контент; это не независимое от MAD доказательство |
| Lag autocorrelation | Может показать filtering/colored residual | Записаны x/y lag1. Сам high-pass создаёт корреляцию даже у белого шума; абсолютное значение не есть camera fingerprint |
| Bounded local spectrum | Может описывать направленность и периодические помехи | FFT на 128² технически bounded; в noise-пилоте не вычислялась. Не добавлена как ещё один post-hoc поиск максимума; тесно связана с resampling/JPEG |
| DCT noise curve | Отделяет часть яркостного и низкочастотного контента | Сильный research reference, но требует достаточного low-texture support в каждом brightness stratum; не выбран второй профиль после исходов |
| Unmatched neighborhood scale | Высокая coverage и заметный controlled noise | Контрольная абляция, не кандидат production: сравнивает разные brightness/texture regions и легко получает content signal |

Brightness matching предпочтён делению на Y': физическая noise curve в
gamma-coded/computational RGB неизвестна; normalizing by brightness не выводится
из модели RAW shot noise. Matching по noisy gradient тоже не нейтрален:
добавленный шум меняет eligibility и подбираемые референсы. Это проверяемый
failure mode, а не причина задним числом ослабить matching.

### Сравнение resampling measurements

Second difference/prediction error, его autocorrelation и Fourier periodicity
описывают связанные зависимости соседних pixels. Проекции mean(abs(d2))
дают bounded вариант без learned model и EM. FFT выбран вместо отдельного
автокорреляционного detector; autocorrelation не добавляет независимого evidence.
Два направления ограничивают cost, но могут терять наклонные traces: resize
чаще оставляет осевой сигнал, rotate/affine не гарантируют его сохранения.
Local phase agreement между двумя половинами tile записывается как diagnostic,
а не как доказательство общей interpolation grid: fence и fabric тоже coherent.

Nearest создаёт repetition/discontinuities, bilinear — линейные зависимости,
bicubic — более широкий сглаживающий/звонящий отклик. Integer decimation,
antialiasing перед downscale, repeated resampling, sharpening и JPEG могут
подавить либо заменить исходную периодичность. Здесь нет обещания определить
kernel, scale, угол или число операций по одному пику.

## 4. Точный exploratory профиль N-MAD-MATCH-1

Параметры зафиксированы до outcomes в external `provenance/predeclaration.md`.
Единицы Y'/residual — значения шкалы RGB8; profile score — log2 ratio,
не uncertainty/probability. Для пилота source crop равен 768×768 RGB8.

1. Вход: oriented RGB/RGBA uint8 raster, обе стороны ≥512, pixels≤2^22.
   Для i,j=0..3 core starts: `x_i=2+floor(i*(W-132)/3)`, аналогично y;
   16 cores 128×128 в row-major порядке, halo2, без resize. Полные cores
   покрывают 262144 pixels; для 768² это 44,44%, gaps не исследованы.
2. Existing BT.601 luminance, `B5=b⊗b`, `b=[1,4,6,4,1]/16`;
   `r=Y'−B5*Y'`. Kernels сохраняют immutable outputs. Внутренние halo pixels
   реальны; в этом профиле центры отстоят от края, extrapolation не требуется.
3. Pixel support: все RGB channels строго `4<c<251`; alpha ровно 255 для
   RGBA. Маску erode квадратом 5×5 до core. Затем оставлять только
   `g=max(|dx|,|dy|)≤8`, где dx/dy — existing centered finite differences.
   Непрозрачный RGB под alpha<255 не становится свидетельством. Нельзя
   compositing на белый/чёрный фон использовать как forensic input.
4. Tile eligible при ≥8192 mask pixels, median(g)≤12 и
   `16≤median(Y')≤239`. Медианы яркости/текстуры берутся по целому core;
   residual metrics — только по mask. High texture/сильные edges исключаются;
   низкая текстура без сопоставимых neighbors всё равно недостаточна.
5. `s_i=median(|r−median(r)|)`: **unscaled MAD**, без коэффициента Gaussian
   sigma. Дополнительно variance с ddof0, mean(r²), x/y lag1 normalized
   covariance по парам, где обе маски true. При <2 парах или знаменателе≤1e-12
   autocorrelation отсутствует; это не ноль. Эти diagnostics не участвуют в score.
6. Для tile i подобрать другие eligible cores: разница median Y'≤16 и
   `|log2((g_i+0.25)/(g_j+0.25))|≤0.5`. Выбрать до пяти ближайших по
   squared Euclidean distance центров; равные расстояния — row-major index.
   Требуются ≥3 референсов. Self-match запрещён. Это пространственный
   приоритет среди сопоставимых областей, не сравнение с любыми соседями.
7. `d_i=|log2((s_i+0.25)/(median_j(s_j)+0.25))|`; image descriptor =
   max d_i. Константа 0.25 предотвращает нестабильность near-zero residual,
   является произвольным исследовательским regularizer, не noise floor камеры.
   При равных maxima выбирать меньший row-major index. Публиковать число
   eligible tiles, сравнений, mask support и максимум с координатами.
8. Нет ни одного допустимого сравнения — abstention (`None` во внешнем
   harness), не score0. Нулевой MAD разрешён как измерение при наличии
   support. Unmatched ablation использует все остальные eligible tiles,
   минимум3, без brightness/texture matching, с той же формулой ratio.

Допуски включают равенство, кроме строгих saturation bounds. NumPy medians
и quantiles используют обычную linear interpolation; NaN/Inf не допускаются.
Нет adaptive tile search, learned denoiser, RNG в measurement или новых
preprocessing artifacts. Seed нужен только для controlled noise generation.

**False positives / альтернативные объяснения:** разные материалы одинаковой
средней яркости; мелкая текстура; неоднородная резкость/глубина резкости;
локальный tone mapping, denoise/sharpen, HDR/multi-frame fusion; chroma/luma
compression; JPEG block/ringing, экранная решётка; imperfect texture proxy.
5×5 alpha mask не защищает от удалённого content confounding.

**False negatives:** donor с близкими residual statistics; малая patch/gap;
постобработка всего изображения; мало сопоставимых tiles; шум увеличивает g
и исключает target/reference; blur меняет matching; gamma/clipping подавляют
различия. Нельзя называть r sensor noise, PRNU или Noiseprint и нельзя
идентифицировать source camera. Вариант без matching эти проблемы не решает.

## 5. Точный exploratory профиль R-D2-MATCH-1

Вход, grid, bounded tiles, яркость, texture proxy и deterministic peer ordering
те же, что в §4. Это собственный screening descriptor по мотивам periodicity
литературы, не faithful reproduction EM/Radon/Kirchner detector.

1. Для x/y по существующему halo вычислить `Dxx=Y(x−1)−2Y(x)+Y(x+1)`
   и Dyy. Нужен шаг 1: повторное применение centered first-difference даёт
   другое ядро/шаг и не объявляется second difference этого профиля.
2. `v_x[x]=mean_y(|Dxx[y,x]|)`, `v_y[y]=mean_x(|Dyy[y,x]|)`.
   Вычесть mean(v), умножить на periodic Hann
   `w[n]=0.5−0.5cos(2πn/128)`, вычислить rFFT128.
3. `P[k]=|F[k]|² / sum_{k=1..64}|F[k]|²`. При знаменателе≤1e-12
   направление без опоры. DC не учитывается. Исключить k≤3 и все bins
   на расстоянии≤2 от `16m`, m=1..4, то есть окрестности m/8 cycles/pixel.
   Из оставшихся bins выбрать максимум; tie — меньший k. Это notch guard,
   не гарантия удаления JPEG после поворота/ресайза или иной истории.
4. Eligibility направления: весь tile с halo opaque, все RGB channels
   строго (4,251), median Y' в [16,239]. Фиксируется raw dominant bin до notch.
   Texture veto: аналогичный спектр mean(Y') projection имеет суммарную
   normalized power≥0.1 в k−1..k+1. Такое направление не является target.
   Эта heuristic может отклонить настоящий resampling на текстуре и пропустить
   текстуру без выраженного mean projection; она не валидирована как classifier.
5. Для phase diagnostic split |d2| пополам по ортогональной оси,
   получить два length128 spectra и записать
   `arg(F_half1[k]*conj(F_half2[k]))`. Нулевая амплитуда не подтверждает
   coherence; phase не участвует в score, отдельный порог не выбирался.
6. ≥3 brightness/texture-matched peers в том же направлении; usable spectrum
   и opaque/unsaturated support обязательны. Peer может иметь texture veto:
   его не объявляют anomalous target, но common periodic texture должна
   оставаться в reference spectrum. Из допустимых peers берутся первые 5.
7. `q_i,d=max(0,log2((P_i,d[k_i]+1e-12)/(median_j(P_j,d[k_i])+1e-12)))`.
   Сравнение идёт **на одной частоте target**, а не между несвязанными peaks.
   Image descriptor — максимум по target/direction; tie row-major, затем x/y.
   ≥1 сравнение достаточно для exploratory measurement; его support/coverage
   сохраняются. Ни одного сравнения — abstention. Нет production decision.

**Локальный / глобальный смысл:** общий peak во всех сравнимых tiles должен
уменьшать ratio, поэтому global resize не является целевым положительным
сценарием. Но неоднородный контент может менять P даже после единой global
операции. Сам local/global ratio не доказывает локальную editing history.

**Multiple testing:** максимум выбирается из ≤32 target/direction comparisons
и заранее ограниченных bins; это всё ещё selection bias. Здесь нет p-value,
Bonferroni-claim или calibrated false-alarm boundary. Любой будущий threshold
должен калиброваться по image-level maximum с неизменным количеством окон,
veto/notches/support и независимым source-group split. Нельзя калибровать один
tile, затем применять порог к 16 tiles без учёта множественного поиска.

**False positives:** регулярная архитектура, fences, текст, fabrics, повторная
плитка, экраны/display capture, moiré, CFA/computational processing и
преобразованные JPEG block frequencies. Phase coherence не исключает их.
**False negatives:** angle вне осевых проекций, antialiased downscale,
integer decimation, weak/неподходящий interpolation kernel, повторная
interpolation, сильный JPEG, sharpen, small patch, clipping и отсутствие peers.
Notch подавляет также реальные interpolation peaks рядом с m/8.
Определение JPEG-фазы и grid mismatch не является задачей профиля.

## 6. Предрегистрация, данные и воспроизводимость

Все новые внешние файлы находятся под:

```text
C:\Users\Vanur\Desktop\FakeDetector-Work\research\M2-BR1-noise-resampling\
  corpus\          20 исходных VISION JPEG + 24 PNG базы
  provenance\      predeclaration.md, freeze.json, sources.json, vision-readme.txt,
                   contact-sheet.jpg, ATTRIBUTION.md
  scripts\         acquire.py, pilot.py, summarize.py, test_pilot.py, verify_repeat.py
  results\         measurements.json, resources.json, summary.json, repeat.json
```

20 native VISION records выбраны до outcomes: первые по sorted SHA-256 из
reviewed M2-R3B `pilot_external_stress` manifest, только `_I_nat_`. Нет
выбора по DQ результатам; calibration/validation/holdout manifests не читались.
Условия VISION сверены с официальным README, сохранённый snapshot/hash проверен.
Исходники прочитаны из уже существующего `Stage12-Macro2-DQ/corpus/originals.zip`,
только выбранные файлы скопированы в новый root с повторной проверкой SHA.
Старые manifests могут содержать прежние пути; это provenance, а не новые
записи по этим путям. Существующий корпус не изменён.

После EXIF transpose получена центральная crop 768² **без resize**; original
в таблицах означает эту базу, не нетронутый full-resolution native файл.
Большие native VISION inputs не стали production-applicable из-за crop.
Старые CC0 PNG masters в доступном архиве не сохранились; новая RAW-проявка,
установка rawpy/venv и большой acquisition не выполнялись.

По contact sheet присутствуют foliage, natural surfaces/gravel, street
architecture, tiled floors, окно/решётка, indoor furniture/objects, wall/sky,
fabric. Это 20 отдельных файлов/source groups, **не доказательство 20
независимых сцен**: возможны близкие места/серии; нет кластерной QA нового корпуса.
Современные phone HDR/night/portrait pipelines не представлены доказательно.
Крупный текст и moiré добавлены только как четыре собственных procedural bases:
smooth ramp, fence, text-like rectangles, moiré. Настоящие документы/экраны
не проверены; synthetic text не заменяет их. Маски alpha проверены отдельно
арифметическим тестом, не real translucent corpus.

Для каждой базы 15 вариантов, всего **360**: original; global blur 3×3 sigma 0.8;
global sharpen `I+0.7*(I−blur)`; global bilinear×1.25 и center crop;
JPEG75/subsampling2; local blur 5×5 sigma 1.2; local median3; local sharpen;
local iid RGB Gaussian sigma 6; local×1.25 nearest/bilinear/bicubic;
local rotate7° bilinear; affine shear0.12 bilinear; local bilinear+JPEG75.
Local patch `[192:576,192:576]`, transform выполнен в parent 512² с центром 384,
вставляется central 384²; RNG seed 240924+индекс source только для added noise.
Измеряемые cores с halo не пересекают шов patch. Added noise и sharpen
округляются `rint`, clip[0,255], uint8; остальные transforms используют
зафиксированную uint8 арифметику OpenCV/Pillow. Глобальные операции — benign controls;
локальные blur/denoise/sharpen тоже **могут быть доброкачественными**.
Composited donor patch не проверялась; результаты added noise не заменяют её.

Заморожено до measurement:

| Артефакт | SHA-256 |
|---|---|
| `predeclaration.md` | `cbcdc9d6d2d4cb6b0a52b28c0cdbe6b856626dbfa88077d1eb0dc83b1fbaf83d` |
| `sources.json` | `ba988a2d6ebf0e9a3748387cd1d5339d0767701a1ed61a4550f96d07516fcc80` |
| `pilot.py` | `08fa7150611db34845763370832c6dac267edbc76263372d13d49d95d01b8e03` |

Python 3.12.10, NumPy 2.5.2, OpenCV 4.14.0 — environment facts в freeze;
Pillow 12.3.0 отдельно сверена в том же окружении после run.
До первого outcome исправлены только lint/format замечания, арифметические
тесты прошли. После outcomes measurement code/параметры не менялись.
Summary script отформатирован и helper вынесен без изменения формул.
`verify_repeat.py` повторил pixels и все measurement fields: **360 идентичных
records**. Это воспроизводимость в одном окружении, не bitwise guarantee
между версиями NumPy/OpenCV, ОС или процессорами.

Из корня проекта воспроизведение использует `uv run python <external-script>`:
`acquire.py` → `pilot.py` → `summarize.py`; `verify_repeat.py` проверяет
сохранённый run без изменения freeze. Скрипты предназначены для этого
небольшого корпуса, не общего пользовательского входа. Повтор acquisition/run
перезаписывает соответствующие внешние outputs; исходный review bundle сохраняет
их hashes. Dependencies/repository Python не изменены.

## 7. Результаты micro-pilot

Ниже только **20 реальных баз**; четыре synthetic базы не увеличивают этот
denominator. `n` — число файлов хотя бы с одним сравнением, не покрытие всех
tiles. Abstention =20−n. Все scores без forensic threshold. Внешний summary
содержит min/Q25/median/Q75/max, paired counts, overlap и ranking для каждого
варианта; округление в таблице до трёх знаков.

| Вариант | Noise n/20 | Noise median | Resampling n/20 | Resampling median |
|---|---:|---:|---:|---:|
| original | 19 | 0.200 | 12 | 4.062 |
| global blur | 18 | 0.194 | 14 | 4.240 |
| global sharpen | 18 | 0.209 | 11 | 3.944 |
| global resize | 20 | 0.160 | 13 | 1.042 |
| JPEG75 | 19 | 0.204 | 12 | 3.680 |
| local blur | 18 | 0.478 | 10 | 3.842 |
| local median | 17 | 0.333 | 11 | 3.621 |
| local sharpen | 18 | 0.338 | 11 | 3.748 |
| local added noise | 17 | 0.179 | 10 | 3.782 |
| local nearest×1.25 | 19 | 0.228 | 12 | 5.417 |
| local bilinear×1.25 | 19 | 0.357 | 11 | 6.901 |
| local bicubic×1.25 | 19 | 0.246 | 13 | 5.098 |
| local rotate7° | 19 | 0.222 | 12 | 4.432 |
| local affine | 20 | 0.188 | 12 | 4.135 |
| local bilinear + JPEG75 | 18 | 0.247 | 11 | 4.058 |

### Noise: частичный signal и потеря при matching

Original matched range 0.075–0.323, IQR 0.148–0.214. Local blur median 0.478,
IQR 0.181–0.648, но 7/18 значений внутри original range; global sharpen
достигает 0.530. Это перекрытие, не zero-FP operating point.
Local noise без matching: median 1.329 против original 0.355,
19/20 paired increases, all-pairs rank относительно benign mixture 0.929.
После matching: median 0.179 против 0.200, лишь 9/17 paired increases,
rank 0.535, 3/20 abstentions. Нельзя выдавать красивое unmatched различение
за устойчивое измерение после brightness/texture control.

Rank — доля всех пар variant/control с большим score (+0.5 при tie),
только descriptive statistic. Benign mixture содержит original, global blur,
sharpen, resize и JPEG75: 94 noise и 62 resampling applicable records,
зависимых внутри source. Это **не independent AUC estimate, FPR или TPR**.
Изменение cohort eligibility означает, что сравнение одних medians недостаточно;
paired denominators сохранены отдельно.

### Resampling: resize различим частично, общий gate не пройден

Original range 1.416–7.153, IQR 3.726–4.829. Local bilinear median 6.901,
IQR 4.517–7.647: 9/10 paired increases, rank vs benign0.828, но 5/11
applicable значений внутри original range и9/20 abstentions. Global resize
median 1.042: на этой смеси local comparison полезнее самого факта peak.
После JPEG75 local bilinear median 4.058, rank 0.592, **11/11** applicable
значений внутри original range. Rotate/affine сильно перекрываются с контролем.

На original D01_I_nat_0179 (ткань/интерьер) score 7.153, D19_I_nat_0085
(каменная кладка) 5.731, D31_I_nat_0072 (освещённая стена/объект) 5.435,
D11_I_nat_0036 (окно/решётка) 4.627. Это **контрольные большие отклики**, не
ложные Findings: classifier отсутствует, внутренняя история камеры неизвестна.
Они показывают, почему suppression одного очевидного raw texture peak
не обеспечивает достоверного различения. Уже существующая JPEG/CFA обработка
и контент здесь не разделены экспериментально.

Synthetic original noise: fence/text — 0; smooth/moire — abstention.
Synthetic original resampling: fence 1.183, text-like 0.005, moiré 0.094,
smooth — abstention. Эти простые controls не доказывают robustness на
реальных экранах/fabric/moiré. Phase diagnostic не был превращён после исходов
в дополнительный фильтр. Локализация максимумов сохранена, но правильность
segmentation/bbox не валидирована; максимум может относиться к reference
изменённой области, а не к самой вставке.

## 8. CPU, память, artifacts и границы

- Совместное N/R измерение одной 768² базы: median 37.4 ms, p95 42.4 ms,
  max 53.6 ms; timing включает tracemalloc и shared descriptor extraction,
  не acquisition/decode/transforms. Раздельное время N и R не измерялось.
- Все 360 measurements с transform/decode и записью результатов:16.135s.
  Repeat проверяет численные значения, не стабильность времени.
- Максимум tracemalloc во время measurement:3128943 bytes (~2.98MiB).
  Peak working set процесса с acquisition-independent loading/transforms/results:
  124854272 bytes (~119.07MiB). RSS не равен workspace и не сравнивается
  напрямую с 32 MiB. Tracemalloc не гарантирует учёт всех native allocations.
- Media:63882798 bytes (~60.9MiB); measurement JSON5056728 bytes;
  resource JSON154 bytes. Derivatives не сохраняются, только hashes/metrics;
  PNG bases и originals внешние. Production artifact count/bytes не изменились.
- Numeric core cost:16×128²; mask/filter/reductions линейны по core samples;
  ≤32 rFFT128 плюс raw/half diagnostics, ≤16² сравнений и до 5 peers.
  Sequential tile processing; полный float64 raster не создаётся.
  Это вписывается в существующий envelope конструктивно, без SciPy.
- Проверка over-limit raster и 52 existing kernel tests подтверждает guards,
  но native full-resolution decode peak, timeout/concurrent worker behavior,
  shared artifact budget и hostile-input integration этого профиля ещё не
  проверены. OS hard memory quota не заявляется. Production readiness из
  маленького пилота не следует.

## 9. Разделение ответственности и корреляция

| Существующее / отложенное evidence | Отличие N/R | Корреляция, overlap и решение |
|---|---|---|
| `image_jpeg_double_quantization` | DQ изучает native quantized DCT histograms; N — spatial residual scale, R — derivative periodicity | JPEG может менять оба spatial descriptors. Наличие двух метрик не даёт двух независимых аргументов; JPEG-only periodicity нового вклада не оправдывает |
| `image_copy_move_correspondence` | ORB/RANSAC correspondence двух регионов; N/R не находят donor/duplicate correspondence | Transformed copy-move может вызвать все три; periodic structures дают связанные ложные отклики. Нельзя считать N/R подтверждением copy-move без отдельной validation |
| `image_metadata_consistency` | Сопоставление declared dimensions/EXIF с actual facts | Иное представление, но одна операция export может изменить metadata и pixels. Metadata presence/absence не определяет residual eligibility или подозрение |
| `image_jpeg_grid_consistency` (deferred) | Grid ищет blocking phase/consistency; R должен исследовать interpolation statistics вне JPEG-only peaks | Detector transformed JPEG grids под новым именем — overlapping/duplicate responsibility. Такой вариант не выбран; Grid не активируется |
| N против R | Scale/moments против periodic covariance | Blur, interpolation и sharpening меняют оба. Это коррелированные local processing descriptors, а не независимые votes |

**Предварительные группы, только предложение:** для N и R одна общая
`image_local_processing_consistency`, не отдельная группа по analyzer/tile/bin.
Название отражает общий локальный processing evidence и намеренно объединяет
оба кандидата. Для DQ/Grid сохраняется существующая
`image_jpeg_compression_history`; metadata — `image_metadata_consistency`;
copy-move — существующая `image_region_correspondence_<hash>` для пары.
Это не расширение runtime enum или изменение risk engine.

Предложение новой общей N/R группы **не разрешает суммировать её с DQ и
co-located copy-move**: текущая модель max-вклада внутри группы сама по себе
не решает cross-group correlation. До production требуется отдельное решение
Macro6 о коррелированном вкладе/подавлении и validation JPEG/texture confounds.
Если полезный R-сигнал окажется только transformed JPEG grid, самостоятельный
R-метод не имеет доказанной дополнительной ценности: вернуть его на research
gate, не обходить dedup новым именем группы. Сейчас никаких Findings/вкладов нет.

## 10. Abstention и возможная узкая семантика

Предложение для будущей спецификации, не новый контракт: известный выход за
область метода — `not_applicable`; корректно прочитанный вход, но недостаточно
support — `completed` без findings/score с явным `insufficient_evidence` и
coverage. Ошибка/повреждение required artifact, identity mismatch, preprocess
failure и timeout остаются ошибками соответствующего слоя, **не Finding и
не отрицательный forensic результат**. Точное отображение требует общего
METHODS gate, существующие API/status не меняются.

Возможная N-семантика: «В обследованных сопоставимых областях различаются
статистики высокочастотного остатка; возможна неоднородная локальная обработка».
Возможная R-семантика: «В части обследованных сопоставимых областей отличаются
периодические зависимости, совместимые с интерполяцией; текстура и обработка
могут давать похожий результат». Такие формулировки остаются предложением:
нынешний pilot не устанавливает надёжный decision rule даже для них.
Severity, finding type, production score и threshold не задаются.

## 11. Ответы на decision questions

| Вопрос | Ответ |
|---|---|
| N1: конкретный deterministic profile? | Да, N-MAD-MATCH-1 точен и bounded; продолжать можно только targeted research, не threshold calibration |
| N2: переживает brightness/texture matching? | Для local blur/sharpen частично; для added noise устойчивость не подтверждена: rank 0.929 без matching падает до0.535 после него. Это главный отрицательный результат |
| N3: может ли benign content доминировать? | Да. Unmatched residual зависит от структуры; matched global controls перекрывают local variants; local denoise/sharpen сами могут быть benign |
| N4: именно residual consistency, а не JPEG/edges? | Формально измеряется residual, strong edges маскированы; независимость от fine texture/JPEG не доказана. Generic residual не объявляется noise source |
| N5: bounded в текущей policy? | Да для предложенного числового профиля; production lifecycle/RSS/concurrency ещё не проверены |
| N6: узкие честные Findings возможны? | Сформулировать можно (§10), но без calibrated support/decision они ещё не обоснованы |
| N7: статус? | **RESEARCH_ONLY**, полезный сигнал **WEAK** |
| R1: конкретный deterministic profile? | Да, R-D2-MATCH-1, без EM/Radon/ML; ограничение двумя осями явно задано |
| R2: local против global resize? | В пилоте частично: medians 6.901 против 1.042 для bilinear. Не универсально и не доказанная classifier performance |
| R3: periodic texture FP? | Серьёзный unresolved confound: original maxima до 7.153 при local bilinear median 6.901; true FPR неизвестен, поскольку threshold не задан |
| R4: JPEG contamination? | Да по литературе и pilot collapse после JPEG75; notch не устраняет rotated/rescaled JPEG remnants |
| R5: multiple testing/localization? | Поиск bounded; статистически контролировать можно только future image-level calibration. Сейчас нет false-alarm control и валидированной localization |
| R6: ресурсы? | Числовой профиль bounded в текущем envelope; интеграционная сертификация не выполнена |
| R7: статус? | **RESEARCH_ONLY**, полезный сигнал **WEAK** |

## 12. Следующий ограниченный gate и проверка работы

Автоматического перехода к реализации/калибровке нет. Если владелец продолжает
исследование, сначала нужен outcome-blind targeted pilot, закрывающий именно
неопределённости метода: для N — независимый от добавленного residual texture
proxy и реальная matched-support coverage; для R — JPEG/periodic-texture
challenge с native-scale, non-JPEG и современными phone workflows. Требуются
source grouping, donor composites, real screens/text/fabrics, локальная и
глобальная обработка и явный отказ при отсутствии support. Новый профиль
должен иметь новый ID/freeze; нынешний нельзя подгонять под эти 360 outcomes.
Только после устранения method-level confounds имеет смысл отдельное решение
о calibration split, operating target, aggregation, correlation и Finding gate.

Проверки: 52 existing residual kernel tests и 7 внешних арифметических/support
tests — PASS; repeat 360 — PASS; Ruff check/format для пяти внешних scripts — PASS.
Repository changes — только четыре Markdown-файла: этот отчёт, METHODS,
ROADMAP, REFERENCES. Mypy production-кода и полный `uv run poe check` для этого
docs-only repository diff не запускались по разрешению задания §21;
динамический одноразовый внешний harness не выдаётся за typed production code.
Итоговые `git diff --check`, documentation consistency, diff review и точный
status фиксируются в review summary после завершения редактирования.
Git mutations и loose Desktop files отсутствуют. Owner review bundle, включая
полный untracked отчёт, находится только в
`FakeDetector-Work/reviews/M2-BR1-noise-resampling/`.
