# Независимая benign-валидация дипломного ансамбля: аудио и видео

Дата: **2026-10-13** (Asia/Krasnoyarsk). Задание:
`STAGE12-DIPLOMA-BENIGN-VALIDATION-SPRINT1`. Baseline:
`bc301888281fdc6954b70c267c33354c12c1b39f` после принятого PR #72.
Это исследовательский материал практической главы диплома.
**AGENT SELF-REPORT IS NOT OWNER ACCEPTANCE.** Статус приёмки —
[ROADMAP](../ROADMAP.md#diploma-benign-validation-sprint1).

## 1. Цель проверки

Проверены три заранее сформулированных вопроса: H-AUDIO-1 — отклики четырёх
аудиосемейств на обычный внешний контент; H-VRC-1 — высокий benign baseline
VRC; H-VIDEO-CORR-1 — совместная активация `video_quality` и
`video_repetition`. Сохраняется `diploma_ensemble_v1@0.1.0` без изменений
алгоритмов, нормализаторов, весов, семейств, capacity и порогов.
Score — описательный эвристический сигнал технических аномалий 0…100;
`probability=null`, LOW ≤25, MEDIUM ≤55, HIGH >55. Новая численная
калибровка не проводилась ни на observation, ни на holdout.

## 2. Отличие от синтетического демонстрационного корпуса

В [предыдущем эксперименте](2026-10-13-diploma-demo-evaluation.md) использовались
40 собственных процедурных файлов. Здесь — новые внешние публичные записи:
8 аудио- и 8 видеосемейств, 32 ограниченных производных файла. Синтетические
fixtures применены только в pytest и не входят в метрики этого отчёта.

`BENIGN_REFERENCE` означает обычный опубликованный контент без целевой
манипуляции со стороны эксперимента. Это не «authentic ground truth»:
история записи, публикации и предшествующей обработки неизвестна полностью.
`BENIGN_PROCESSING` — обычная повторная обработка. `BENIGN_CONFOUND` —
заранее отмеченный вариант естественного периодического/малоподвижного
содержания, которое уже присутствует в источнике; эксперимент не создавал
вставки, повторы, freeze attack или повреждения PTS.

## 3. Источники и лицензии

Каноническая provenance/licensing-запись с названиями, ссылками и SHA-256:
[REFERENCES](../REFERENCES.md#diploma-benign-validation-sources).
Commons API JSON, HTML исходных страниц и revision IDs сохранены до загрузки
внешних медиа. Original SHA-256, размеры, direct URLs и время получения UTC
записаны в `source-manifest.json` / `source-provenance.csv`.
Все 16 оригинальных SHA-256 различны; общий объём — **95 575 335 bytes**.
Фактическое получение 12 октября UTC соответствует 13 октября местного времени.
На страницах явно указаны CC BY 3.0, CC BY-SA 3.0/4.0 либо CC0.

Attribution и названия сохраняются в manifests; изменения — извлечение первых
12 секунд, преобразование параметров и кодирование, описанные ниже. Производные
сохраняют лицензионное происхождение источника. Медиа не добавляются в Git и
не перераспространяются этим заданием; авторы не объявляются сторонниками проекта.


| Source ID | Содержание / категория | Автор / attribution | Лицензия |
| --- | --- | --- | --- |
| audio-01 | speech | OrbiliusMagister | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| audio-02 | music | Jason M. C., Han | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| audio-03 | ambient_rain | Effib | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| audio-04 | birds | Robert EA Harvey | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| audio-05 | transient_thunder | Subhashish Panigrahi | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| audio-06 | periodic_clock | Jud McCranie | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| audio-07 | periodic_bells | Glaneur de sons | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |
| audio-08 | night_ambient | DrTrumpet | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| video-01 | continuous_motion | Petar Milošević | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| video-02 | natural_outdoor | https://www.youtube.com/user/Editor | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |
| video-03 | person_camera_motion | Sage Ross | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| video-04 | periodic_motion | Maoileann | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| video-05 | camera_pan | Elekes Andor | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| video-06 | talking_person | Rahulkepapa | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| video-07 | static_noise | Glarph | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) |
| video-08 | animation_cuts | (c) copyright 2008, Blender Foundation / www.bigbuckbunny.org | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |


Для каждой записи заявлен свой автор; source family означает различную
линейку происхождения, а не доказанную статистическую независимость.
`audio-07` опубликован через Freesound, `video-02` — лицензированная YouTube-копия,
`video-08` — Blender Foundation, Big Buck Bunny Trailer (2008). Остальные
источники отмечены Commons как own work. Выбор не использовал оценки FakeDetector.
Ограничение размера — 40 MB на оригинал / 128 MB суммарно. HTTPS redirects
ограничены доменами Wikimedia; архивы не распаковываются. При HTTP 429 полученные
файлы сохранялись, повторный `acquire` проверял SHA-256 receipts; источник не заменялся.

## 4. Состав benign-корпуса

**32 файла, 16 независимых source families: 16 audio / 8 семейств и
16 video / 8 семейств.** По две производные на одну запись. Роли:
16 BENIGN_REFERENCE, 12 BENIGN_PROCESSING, 4 BENIGN_CONFOUND.
Последние — `audio-06-processed`, `audio-07-processed`, `video-04-processed`,
`video-07-processed`: часы, колокола, вращение мельницы, VHS-шум.
Периодический/шумовой контент присутствует и в их reference-паре; роль C
обозначает цель стресс-проверки, не отдельную операцию добавления аномалии.

Split закреплён по source family до скачивания и оценки: суффиксы 03/06/08
для каждого media → `holdout_benign`, остальные → `observation`.
Все производные одного источника остаются вместе. Observation — 20 файлов,
5+5 семейств; holdout — 12 файлов, 3+3 семейства. Основной внешний корпус
оценён один раз; holdout не использовался в development smoke.
Тесты используют только собственные маленькие локальные fixtures.

Таксономия задана до оценки по описанию источника. Контактный лист выбранных
интервалов подтвердил движение паровоза/собаки, воду, мельницу, выступление,
VHS-шум, анимацию и титры. У `video-05` категория исходника `camera_pan`,
но первые 12 s преимущественно малоподвижны. `video-08` — анимация с обычным
монтажом, `video-07` — шум конца VHS; они не называются натуральной камерной сценой.
Речь представлена одним коротким чтением, музыка — одним фортепианным источником.
Ночной фон представлен сверчками, а не специально записанным тихим помещением.

## 5. Методика подготовки и воспроизводимость

Инструмент: [diploma_benign_validation.py](../../scripts/diploma_benign_validation.py),
версия `diploma-benign-1.0.0`. Использованы stdlib и существующее окружение
проекта; новых зависимостей нет. Для каждой записи взят интервал [0,12) s.
Временные интервалы после просмотра оценок не менялись.

Аудио reference: PCM s16le WAV, mono 16 kHz. Processed: тот же reference
переведён в mono 8 kHz; gain, splice, copy/paste и искусственная тишина
не вводились. Это исследование двух стандартных параметров подготовки,
а не проверка untouched оригиналов с родной частотой.
Видео reference: MPEG-4, fit до 480×270 с сохранением aspect ratio,
24 fps, q=2, GOP=1, yuv420p. Processed: fit до 320×180, 15 fps,
q=5, GOP=12, из reference. Audio stream удалён. Metadata удалены,
один encoder thread, bitexact flags, time base 1/24000.
Смена fps и кодека — обычная обработка, не атака с PTS.

Две подготовки дали **32/32 побайтно одинаковых файла**; все derivative
SHA-256 различны. ffprobe подтвердил 12 s для каждого. Размер корпуса —
66 745 803 bytes. Exact FFmpeg argv с относительными путями сохранён для
каждого sample. JSON-seals связывают source-plan → source-manifest → freeze
→ manifest → run → journal → result JSON. Frozen source/runtime/config/lock
fingerprints проверены до и после прогона; фактически импортирован checkout.


Manifest SHA-256: `5cac6a0b0c347ce41abd7f1e759cf08148e7d3ef0760a5e8b291c106a58803d2`.

Среда: Python 3.12.10; Windows-11-10.0.26200-SP0; NumPy 2.5.2; Pillow 12.3.0; opencv 4.14.0.94; FFmpeg `ffmpeg version 9.0.1-full_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers`.


Последовательность воспроизведения из checkout (переменная `$workspace` должна
содержать новый абсолютный каталог вне репозитория):

```powershell
uv run python -m scripts.diploma_benign_validation declare --workspace $workspace
uv run python -m scripts.diploma_benign_validation acquire --workspace $workspace
uv run python -m scripts.diploma_benign_validation prepare --workspace $workspace
uv run python -m scripts.diploma_benign_validation evaluate --workspace $workspace
uv run python -m scripts.diploma_benign_validation report --workspace $workspace
```

Для проверки именно этого эксперимента используются сохранённые seals и
source SHA-256: повторная декларация веб-источников позднее сама по себе не
гарантирует прежних bytes. `acquire` проверяет уже записанные оригиналы;
`prepare/evaluate` не перезаписывают frozen evidence. Таблицы можно восстановить
командой `report`. Внешний workspace: `FakeDetector-Work/diploma-benign-validation`;
review bundle: `FakeDetector-Work/reviews/DIPLOMA-benign-validation-sprint1`.

## 6. Методика анализа

**FILE_LEVEL_E2E=32, COMPONENT_LEVEL=0.** Файл проходит
`AnalysisApplicationService.submit` → intake/validation → preprocessing →
spawned analyzer workers → Findings → assessment → сохранённый `get_result`
→ cleanup. Создание `AnalyzerResult` вместо измерений корпуса не используется.
Изменены лишь три runtime storage paths. Штатные budgets, настройки безопасности,
аутентификация адаптеров и набор анализаторов сохранены. HTTP listener не нужен.

Все 32 результата: `completed`, completeness `complete`, cleanup `completed`.
Суммарное время submission→result — 197.640 s; это инженерный замер данной
машины, не performance benchmark. Временные файлы штатного runtime удалены.
Наблюдались все 5 audio и все 4 video analyzers; 144 исполнения `completed`.
Состояния response: 95 signal, 48 completed_no_signal, 1 insufficient_evidence;
not_applicable/error/timeout/skipped — 0. Недостаток измерения не заменён нулём.

Отклики вычислены теми же production normalizers по сохранённым raw_metrics,
не извлечены из prose. Отдельно сохранены normalized response, maturity,
effective response, family factor, contribution и score contribution.
Суммы вкладов воспроизводят все 32 persisted score. Канонический знаменатель
остаётся audio=2.8125, video=2.05; пробел измерения его не уменьшает.
ATD и ASC считаются одним `audio_transition`, не независимыми доказательствами.

Квантили: линейная интерполяция в позиции (n−1)p. Spearman: Pearson по рангам
со средним рангом для совпадений, без SciPy. Constant vector или N<2 → null,
не 0. Корреляция семейств сравнивает именно family responses; ненаблюдаемые
семейства исключаются из пар с отдельным счётчиком. Source-family корреляция
также рассчитана по среднему двух derivatives, а не по 16 якобы независимым точкам.
Пороговые rates считаются по неокруглённому score; ниже значения округлены
для чтения. Полная точность и raw metrics сохранены в CSV/JSON.

## 7. Результаты по аудио — H-AUDIO-1

Все **16/16 файлов, 8/8 семейств** превысили 25; HIGH — **0/16, 0/8 семейств**.
LOW/MEDIUM/HIGH = **0/16/0**. Медиана score 41.205910, диапазон
25.513373…50.868035. Доминирующее семейство во всех 16 случаях — `audio_transition`.
Это MEDIUM triage/manual-review response, а не автоматически «false positive»:
корпус не имеет forensic authenticity ground truth.

Обозначения далее: O=observation, H=holdout_benign;
R=BENIGN_REFERENCE, P=BENIGN_PROCESSING, C=BENIGN_CONFOUND.
Q/T/Rp/B — audio_quality / audio_transition / audio_repetition / audio_background.


| sample_id | Split/роль | Score | Q | T | Rp | B | ATD | ASC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| audio-01-reference | O/R | 35.133833 | 0.000000 | 0.750194 | 0.025153 | 0.212791 | 0.955515 | 0.794522 |
| audio-01-processed | O/P | 39.555476 | 0.000000 | 0.754108 | 0.030397 | 0.327993 | 0.962165 | 0.792001 |
| audio-02-reference | O/R | 44.145522 | 0.000000 | 0.807177 | 0.084438 | 0.349977 | 1.000000 | 0.967245 |
| audio-02-processed | O/P | 42.567188 | 0.000000 | 0.791945 | 0.055269 | 0.349989 | 0.963513 | 0.977498 |
| audio-03-reference | H/R | 41.823946 | 0.000000 | 0.812500 | 0.013798 | 0.350000 | 1.000000 | 1.000000 |
| audio-03-processed | H/P | 41.413912 | 0.000000 | 0.801437 | 0.013910 | 0.349419 | 0.931920 | 1.000000 |
| audio-04-reference | O/R | 41.353461 | 0.000000 | 0.803639 | 0.009427 | 0.350000 | 0.945471 | 1.000000 |
| audio-04-processed | O/P | 41.058358 | 0.000000 | 0.796712 | 0.008055 | 0.350000 | 0.902841 | 1.000000 |
| audio-05-reference | O/R | 39.305086 | 0.000000 | 0.702850 | 0.072514 | 0.330092 | 0.901026 | 0.721124 |
| audio-05-processed | O/P | 40.651441 | 0.000000 | 0.693099 | 0.106464 | 0.343758 | 0.917146 | 0.596641 |
| audio-06-reference | H/R | 50.868035 | 0.000000 | 0.812500 | 0.618163 | undefined | 1.000000 | 1.000000 |
| audio-06-processed | H/C | 44.163365 | 0.000000 | 0.812500 | 0.079595 | 0.350000 | 1.000000 | 1.000000 |
| audio-07-reference | O/R | 46.019027 | 0.000000 | 0.811714 | 0.132574 | 0.349997 | 1.000000 | 0.995165 |
| audio-07-processed | O/C | 38.904515 | 0.000000 | 0.811684 | 0.118373 | 0.164132 | 1.000000 | 0.994981 |
| audio-08-reference | H/R | 38.022154 | 0.000000 | 0.763727 | 0.012015 | 0.293631 | 0.951429 | 0.894147 |
| audio-08-processed | H/P | 25.513373 | 0.000000 | 0.665053 | 0.022977 | 0.029534 | 0.939655 | 0.334012 |


Распределения normalized responses пяти анализаторов; n означает пригодные измерения:

| Analyzer | n | min | median | max |
| --- | --- | --- | --- | --- |
| audio_pcm_quality | 16 | 0.000000 | 0.000000 | 0.000000 |
| audio_temporal_discontinuity | 16 | 0.901026 | 0.958840 | 1.000000 |
| audio_spectral_consistency | 16 | 0.334012 | 0.986240 | 1.000000 |
| audio_repeated_segment_correspondence | 16 | 0.012392 | 0.065897 | 0.951021 |
| audio_background_noise_consistency | 15 | 0.084383 | 0.998341 | 1.000000 |


ATD везде ≥0.901026; ASC медиана 0.986240. Большой максимум локального
изменения встречается в речи, музыке, шуме и паузах. Для
`audio-01-reference` максимум ATD J=0.955515 около sample 105056 (6.566 s
при 16 kHz), ASC F4=0.794522 на support [61440,69632); это внутренние
участки обычной речи, не только граница начала файла.
У `audio-02-reference` J=1 на sample 1132, у `audio-07-reference` J=1
на sample 893: начало записи может влиять на max pooling.
У `audio-03-reference` ASC F1=1 и J=1 соседствуют с нулевыми/тихими участками;
факт не приписывается злонамеренному splice. Во всех случаях сохранены
исходные count/undefined/median/p95/max и support positions.

Внутри T больший effective response получает factor=1, второй — 0.25.
При ties порядок по analyzer ID даёт ASC первым. Например,
`audio-03-reference`: 0.65×1 + 0.25×0.65×1 = 0.8125,
а не 1.3. Это коррелированные измерения одной семьи; веса не переоценивались.

Единственный `insufficient_evidence` — ABN у `audio-06-reference`:
пригодной низкоэнергетической нормированной пары нет, а не «background=0».
Его семейный арифметический вклад равен 0, но raw response остаётся null.
Ритмичные часы дают ARC=0.951021; 77.62% цифровой тишины в штатном normalized
PCM согласуется с изолированными тиками. Max score 50.868035 не достигает HIGH.
После обычного 16→8 kHz ARC=0.122454, ABN=1, score=44.163365.
Падение/рост одного raw response не изолирует причинный эффект частоты:
вместе меняются полоса, дискретизация и длительность fixed-sample windows.

`audio-08-reference` → processed: score 38.022154 → 25.513373;
штатный normalized PCM RMS 0.009567 → 0.000344,
ASC 0.894147 → 0.334012, ABN 0.838945 → 0.084383.
Снижение высокочастотной полосы сверчков при обычном resampling —
правдоподобное объяснение, не доказанная причинная модель и не внесённый gain attack.

Распределения по source family и категории (каждая категория имеет лишь один
независимый источник; оба variants повышены):


| Source family / категория | Split | Reference | Processed | Δ score | >25 файлы / семьи | >55 файлы / семьи |
| --- | --- | --- | --- | --- | --- | --- |
| audio-01 / speech | O | 35.133833 | 39.555476 | 4.421643 | 2/2; 1/1 | 0/2; 0/1 |
| audio-02 / music | O | 44.145522 | 42.567188 | -1.578333 | 2/2; 1/1 | 0/2; 0/1 |
| audio-03 / ambient_rain | H | 41.823946 | 41.413912 | -0.410034 | 2/2; 1/1 | 0/2; 0/1 |
| audio-04 / birds | O | 41.353461 | 41.058358 | -0.295104 | 2/2; 1/1 | 0/2; 0/1 |
| audio-05 / transient_thunder | O | 39.305086 | 40.651441 | 1.346355 | 2/2; 1/1 | 0/2; 0/1 |
| audio-06 / periodic_clock | H | 50.868035 | 44.163365 | -6.704669 | 2/2; 1/1 | 0/2; 0/1 |
| audio-07 / periodic_bells | O | 46.019027 | 38.904515 | -7.114511 | 2/2; 1/1 | 0/2; 0/1 |
| audio-08 / night_ambient | H | 38.022154 | 25.513373 | -12.508780 | 2/2; 1/1 | 0/2; 0/1 |


Rates по split и роли, с source-family denominators:

| Split | Media | N | Families | >25 samples | >25 family any | >55 samples | >55 family any |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | audio | 16 | 8 | 16/16 (100.00%) | 8/8 (100.00%) | 0/16 (0.00%) | 0/8 (0.00%) |
| all | video | 16 | 8 | 0/16 (0.00%) | 0/8 (0.00%) | 0/16 (0.00%) | 0/8 (0.00%) |
| holdout_benign | audio | 6 | 3 | 6/6 (100.00%) | 3/3 (100.00%) | 0/6 (0.00%) | 0/3 (0.00%) |
| holdout_benign | video | 6 | 3 | 0/6 (0.00%) | 0/3 (0.00%) | 0/6 (0.00%) | 0/3 (0.00%) |
| observation | audio | 10 | 5 | 10/10 (100.00%) | 5/5 (100.00%) | 0/10 (0.00%) | 0/5 (0.00%) |
| observation | video | 10 | 5 | 0/10 (0.00%) | 0/5 (0.00%) | 0/10 (0.00%) | 0/5 (0.00%) |

| Media | Роль | N | Families | min | median | max | >25 samples | >25 family any |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| audio | BENIGN_CONFOUND | 2 | 2 | 38.904515 | 41.533940 | 44.163365 | 2/2 (100.00%) | 2/2 (100.00%) |
| audio | BENIGN_PROCESSING | 6 | 6 | 25.513373 | 40.854899 | 42.567188 | 6/6 (100.00%) | 6/6 (100.00%) |
| audio | BENIGN_REFERENCE | 8 | 8 | 35.133833 | 41.588704 | 50.868035 | 8/8 (100.00%) | 8/8 (100.00%) |
| video | BENIGN_CONFOUND | 2 | 2 | 17.233658 | 17.240264 | 17.246870 | 0/2 (0.00%) | 0/2 (0.00%) |
| video | BENIGN_PROCESSING | 6 | 6 | 17.096341 | 17.127377 | 22.894338 | 0/6 (0.00%) | 0/6 (0.00%) |
| video | BENIGN_REFERENCE | 8 | 8 | 17.090955 | 17.135959 | 22.900343 | 0/8 (0.00%) | 0/8 (0.00%) |


Во всех role-группах HIGH=0 (и на уровне файлов, и source families).
Суммировать число семейств между R и P/C нельзя: это одни и те же источники.

## 8. VRC baseline — H-VRC-1

**VRC близок к насыщению во всех 16/16 видео из 8/8 семейств.** Это наблюдается
в каждой из восьми категорий данного корпуса, а не только в static/periodic.
Observation: 10/10, 5/5; holdout: 6/6, 3/3. Категориальная выборка N=1 family
не позволяет заключить, что категория не влияет на величину в популяции.


| Split | n | min | p25 | median | p75 | max |
| --- | --- | --- | --- | --- | --- | --- |
| all | 16 | 0.984178 | 0.996175 | 0.997052 | 0.998907 | 0.999930 |
| holdout_benign | 6 | 0.984178 | 0.992451 | 0.997483 | 0.999275 | 0.999930 |
| observation | 10 | 0.993634 | 0.996588 | 0.997052 | 0.998608 | 0.999862 |


Buckets заданы до оценки: ==0: **0**, 0<r<0.25: **0**, 0.25≤r<0.5: **0**,
0.5≤r<0.75: **0**, r≥0.75: **16**. Null/insufficient VRC: 0.
После maturity 0.35 это 0.344462…0.349975 family response, или примерно
16.80…17.07 score points при video capacity=2.05. При этом общий video
score остаётся LOW во всех 16 случаях: 17.090955…22.900343.
VRC saturation и HIGH overall не отождествляются.


| Source family / категория | Split | Reference r | Processed r | Средний r | ≥0.75 файлы / семьи |
| --- | --- | --- | --- | --- | --- |
| video-01 / continuous_motion | O | 0.995221 | 0.993634 | 0.994427 | 2/2; 1/1 |
| video-02 / natural_outdoor | O | 0.998436 | 0.998666 | 0.998551 | 2/2; 1/1 |
| video-03 / person_camera_motion | H | 0.991013 | 0.984178 | 0.987595 | 2/2; 1/1 |
| video-04 / periodic_motion | O | 0.997122 | 0.996494 | 0.996808 | 2/2; 1/1 |
| video-05 / camera_pan | O | 0.999793 | 0.999862 | 0.999828 | 2/2; 1/1 |
| video-06 / talking_person | H | 0.998203 | 0.996764 | 0.997483 | 2/2; 1/1 |
| video-07 / static_noise | O | 0.996982 | 0.996873 | 0.996927 | 2/2; 1/1 |
| video-08 / animation_cuts | H | 0.999930 | 0.999632 | 0.999781 | 2/2; 1/1 |


Для каждого reference eligible_pairs=3423, processed=2946; различие связано
с плотностью кадров в фиксированных dense-окнах, а не с label. Raw
`minimum_color_pair` и `minimum_delta_pair` сохранены отдельно с обеими
дистанциями, temporal activity и PTS, без склеивания разных пар.

Точные примеры normalizer `1−max(color/440640,delta/660960)`:

- `video-03-processed` (H, движение человека/собаки): minimum_color pair
  color=6972, delta=2426, r=0.9841775599. Начала групп PTS=17600 и 25600,
  то есть 0.7333 и 1.0667 s при time base 1/24000. Похожие соседние группы
  обычного движения уже дают сильный отклик.
- `video-05-reference` (O, малоподвижная панорама): color=91, delta=57,
  r=0.9997934822; начала 248000 и 258000 ticks.
- `video-08-reference` (H, титры трейлера): color=31, delta=23,
  r=0.9999296478; начала 254000 и 259000 ticks. Это маленькая, но ненулевая
  дистанция. В каждом видео exact pixel duplicates на legacy sample path отсутствуют.

Это воспроизводимое свидетельство неспецифичности текущего масштаба/выбора
экстремума VRC на данном benign-корпусе. Интерпретация механизма: теоретически
ограниченные descriptor distances малы для близких кадров, а минимум ищется
среди тысяч пар. Установить вклад масштаба отдельно от выбора кандидатов и
содержания по этому эксперименту нельзя. Нормализатор не изменён.

## 9. Связь video_quality и video_repetition — H-VIDEO-CORR-1

Во всех 16 файлах `video_quality=0`; `video_repetition>0` во всех 16.
Совместных ненулевых откликов **0/16 файлов, 0/8 семейств**; quality-only=0,
repetition-only=16, both-zero=0, unavailable=0. Pearson и Spearman
**undefined**, поскольку quality — constant vector. Для observation
(N=10), holdout (N=6) и средних по source families (N=8) также undefined.
Это не нулевая корреляция, не доказательство независимости и не доказательство
отсутствия возможного двойного учёта на другом содержимом.

CORE raw measurements одинаковы по структуре: 12 sampled frames, 11 comparisons,
dimension_variant_count=1, exact_duplicate_pair_count=0,
longest_exact_duplicate_run_samples=1, span=0 s, timestamps 0…11 s.
Даже визуально статичные титры и дальний вид не оказались побайтно одинаковыми
после декодирования. В этом корпусе механизм совместного голоса, показанный
ранее на процедурной статике, **не воспроизведён**. Подменять внешнюю сцену
искусственным freeze для получения желаемого результата запрещено и не делалось.

Таблица отсортирована по `video_quality + video_repetition` убывающе;
Q всегда 0, exact_duplicate_pair_count всегда 0:


| sample_id | Split/роль | Q | Rp | Q+Rp | VRC r | Score / level |
| --- | --- | --- | --- | --- | --- | --- |
| video-08-reference | H/R | 0.000000 | 0.349975 | 0.349975 | 0.999930 | 22.900343 / LOW |
| video-05-processed | O/P | 0.000000 | 0.349952 | 0.349952 | 0.999862 | 17.122417 / LOW |
| video-05-reference | O/R | 0.000000 | 0.349928 | 0.349928 | 0.999793 | 17.135824 / LOW |
| video-08-processed | H/P | 0.000000 | 0.349871 | 0.349871 | 0.999632 | 22.894338 / LOW |
| video-02-processed | O/P | 0.000000 | 0.349533 | 0.349533 | 0.998666 | 17.111452 / LOW |
| video-02-reference | O/R | 0.000000 | 0.349453 | 0.349453 | 0.998436 | 17.090955 / LOW |
| video-06-reference | H/R | 0.000000 | 0.349371 | 0.349371 | 0.998203 | 17.106183 / LOW |
| video-04-reference | O/R | 0.000000 | 0.348993 | 0.348993 | 0.997122 | 17.136095 / LOW |
| video-07-reference | O/R | 0.000000 | 0.348944 | 0.348944 | 0.996982 | 17.182513 / LOW |
| video-07-processed | O/C | 0.000000 | 0.348905 | 0.348905 | 0.996873 | 17.233658 / LOW |
| video-06-processed | H/P | 0.000000 | 0.348867 | 0.348867 | 0.996764 | 17.096341 / LOW |
| video-04-processed | O/C | 0.000000 | 0.348773 | 0.348773 | 0.996494 | 17.246870 / LOW |
| video-01-reference | O/R | 0.000000 | 0.348327 | 0.348327 | 0.995221 | 17.104090 / LOW |
| video-01-processed | O/P | 0.000000 | 0.347772 | 0.347772 | 0.993634 | 17.132336 / LOW |
| video-03-reference | H/R | 0.000000 | 0.346855 | 0.346855 | 0.991013 | 17.593146 / LOW |
| video-03-processed | H/P | 0.000000 | 0.344462 | 0.344462 | 0.984178 | 18.016721 / LOW |


Source-family view (оба derivatives, без удвоения независимого N):

| Family | N | Средняя Q | Средняя Rp | Совместно >0 | Pearson / Spearman |
| --- | --- | --- | --- | --- | --- |
| video-01 | 2 | 0 | 0.348050 | 0/2 | undefined / undefined |
| video-02 | 2 | 0 | 0.349493 | 0/2 | undefined / undefined |
| video-03 | 2 | 0 | 0.345658 | 0/2 | undefined / undefined |
| video-04 | 2 | 0 | 0.348883 | 0/2 | undefined / undefined |
| video-05 | 2 | 0 | 0.349940 | 0/2 | undefined / undefined |
| video-06 | 2 | 0 | 0.349119 | 0/2 | undefined / undefined |
| video-07 | 2 | 0 | 0.348925 | 0/2 | undefined / undefined |
| video-08 | 2 | 0 | 0.349923 | 0/2 | undefined / undefined |


## 10. Elevated benign cases

Полный elevated список — все 16 аудиострок раздела 7 и `audio-elevated.csv`;
исключённых повышенных результатов нет. Доминирует T, audio_quality=0 везде.
Особенно показательны обычная речь `audio-01-reference` (O, 35.133833),
дождь `audio-03-reference` (H, 41.823946), часы `audio-06-reference`
(H, 50.868035), сверчки `audio-08-processed` (H, 25.513373).
Они показывают content-dependent переходы/периодичность/полосу, не подтверждают подделку.

Видео с score>25 нет. Самые высокие `video-08-reference`=22.900343 и
processed=22.894338 (H) имеют visual transition response≈0.3414,
согласующийся с обычными титрами/монтажом. Timing response=0 во всех видео
после стандартизации в CFR; этот результат не валидирует нативный VFR.

## 11. Ограничения

- **Pseudo-replication:** 32 samples — только 16 source families. Две обработки
  не дают два независимых свидетельства. Headline rates показаны и как sample,
  и как family-any; для корреляции дополнительно использованы family means.
- Convenience selection Commons, 8 семейств на media, одна запись на категорию;
  нет случайной выборки эксплуатации, доказанной подлинности, FPR/FNR или accuracy.
  Один внешний поставщик и общая подготовка создают дополнительные зависимости.
- Только первые 12 s: начало файла и обычные паузы могут завышать extrema.
  Выбор первых интервалов был заранее одинаковым, но не репрезентативен всей записи.
  Многие видео имеют неподвижный фон. Нативные rate/resolution/codecs не оценивались.
- Mono/downsample audio и CFR/resize/re-encode video влияют на сигналы.
  Пара video меняет сразу несколько параметров; причинную attribution не даёт.
  Сверхтихого room tone и длительной речи мало; нулевая тишина не создавалась.
- Входной файл E2E не означает full-media evidence coverage: сохраняются
  штатные precision/dense/sample windows, fixed-frame размеры, caps и null states.
  CORE exact equality и VRC descriptor similarity имеют разные критерии.
- Нет вариации video_quality, поэтому H-VIDEO-CORR-1 остаётся неопределённой.
  Добавление искусственной статики после просмотра оценок не выполнялось.
- Holdout действительно отделён по источникам и не использован в smoke,
  но всего 3 семейства на media. Нет заявлений об inferential significance,
  доверительных интервалах или causal proof. Model tuning не было.

## 12. Выводы

H-AUDIO-1: обычное содержание даёт MEDIUM во всех восьми независимых
аудиосемействах обоих splits. ATD/ASC и ABN часто сильны, CORE saturation нет.
Это наблюдение о нагрузке на triage; MEDIUM само по себе не доказывает дефект.

H-VRC-1: normalized VRC **0.984178…0.999930 во всех восьми видеосемействах**,
включая обычное движение и речь. Насыщение широко внутри этого корпуса,
а не редкое исключение. Вес 0.35 ограничивает overall score, но не делает
сам отклик специфичным. HIGH на ordinary independent sources не наблюдался.

H-VIDEO-CORR-1: совместная активация не наблюдалась; zero-variance CORE не
позволяет оценить корреляцию. Результат не снимает известного ограничения
межсемейной зависимости и не обосновывает внедрение cross-family cap.

## 13. Рекомендация владельцу

**PRIMARY_DECISION: TARGETED_RESEARCH_REQUIRED.**

Основание — воспроизводимое близкое к насыщению слабое VRC-измерение на
8/8 независимых benign source families, подтверждённое observation и holdout,
при отсутствии exact repeated-frame Findings. Численный новый normalizer,
вес или threshold по этому корпусу не обоснован: нет независимого набора
целевых повторов с оценкой потери чувствительности.

Для отдельного следующего OWNER GATE предлагается outcome-blind исследование
VRC scale/minimum pooling на независимых benign и целевых повторных эпизодах,
с распределениями pair distances, temporal separation и активностью сцены.
Сначала отделить влияние descriptor scale от отбора минимума и стандартной
подготовки; затем сравнивать заранее объявленные варианты. Это предложение
исследования, не выбранная формула и не реализованная калибровка.
Для аудио — отдельно проверить влияние max pooling, начала/пауз и native rate;
для корреляции — получить обычные реальные источники с вариативным CORE response.
Число HIGH, потерю response на известных трансформациях и независимый family N
нужно рассматривать вместе до изменения модели.

Веса, thresholds, normalizers, family mapping, ensemble version, public/config
schemas и зависимости не изменены. Stage 12 и scientific/production dispositions
не закрываются. CHANGELOG не обновлён: нет принятого изменения поведения,
контракта, архитектуры или постоянного workflow; текущий статус ведёт ROADMAP.

Проверки и приёмка фиксируются в review bundle; development verification из
dirty tree не является strict certification. Staging/commit выполняет владелец.

Focused tests: **271 passed**; после уточнения проверки набора ролей и имени
path-safety теста — ещё 2 targeted checks PASS. `uv run poe check` выполнен
**один раз**: pre-commit PASS, mypy PASS (71 source files), pytest
**3094 passed / 17 skipped / 1 failed**, coverage 91%.
Единственный fail — `test_sdist_wheel_metadata_entry_point_and_resources`:
sdist provenance отклоняет intended untracked-файлы. Read-only сверка архива
подтвердила ровно три таких файла, без иных лишних/пропущенных членов,
дубликатов, unsafe paths или расхождений байтов на момент сверки.
**FULL_QUALITY_BARRIER: OWNER_VERIFY_REQUIRED**; release guard не менялся,
staging не выполнялся. CLI smoke отдельно PASS, Ruff новых файлов и
`git diff --check` PASS. Полные логи, final diff, копии всех intended untracked
файлов, manifests, raw result JSON, таблицы и SHA-256 seal — во внешнем bundle.
После owner review и staging требуется повтор barrier владельцем.
