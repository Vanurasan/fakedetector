# M3-ASC-D1 — review обязательства ASC-TV-1

Дата: **2026-09-30**. Baseline: `a2169e566a4d1cebf15bbd715397a75312eacb0b`,
ветка `feat/stage12-macro3-audio-analyzer-expansion-wave1`; начало исходного
review чистое, ветка и HEAD совпали с заданием. Запись принятия M3-ASC-D1-A
выполнена на том же HEAD поверх ожидаемого dirty diff завершённого review.
Review существующих свидетельств; новые
измерения, эксперименты, загрузки данных и запуск прежнего harness не выполнялись.

## 1. Рекомендация и её принятие

**Disposition: RESEARCH_ONLY_NON_SPECIFIC; принят владельцем 2026-09-30.** ASC воспроизводимо
описывает спектральные переходы, но сильный ответ нынешнего профиля не позволяет
обоснованно отличить монтаж / несогласованность источника от обычной эволюции
содержания. Это относится отдельно к normalized magnitude spectral TV и flux.
Ни одна из них не показала существенно лучшую forensic-селективность.

Сохранить прототип и отрицательные свидетельства как research/descriptive
материал. Одна малая дополнительная гипотеза, способная изменить disposition
неизменённого профиля, по этим свидетельствам не выделена;
`IF_TARGETED_NEXT_STUDY: NONE`. Вывод не означает математической невозможности
любого будущего контекстного или многомерного метода.

**M3-ASC-D1: DONE / OWNER ACCEPTED DISPOSITION**.
ASC — **RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED**;
**ASC carry-forward: RESOLVED**. Явное решение владельца записано в §8.
Принятие профиля и его пределы принадлежат [METHODS](../METHODS.md#audio-m3-asc-d1),
состояние carry-forward — [ROADMAP](../ROADMAP.md#audio-m3-required-carry-forward).

## 2. Свидетельства и их проверяемость

Основания: [M3-R1 §§3, 5](2026-09-26-audio-method-selection.md), принятый
[M3-R2A §§2–7, 9, 11](2026-09-26-audio-transition-measurement-prototype.md),
существующие внешние файлы `FakeDetector-Work/research/M3-R2A-transition/`:

- `predeclaration.md`, `predeclaration-v2.md` и frozen SHA manifest;
- `scripts/protocol.py::asc`, `prepare_v2.py::generate`, `measure_v2.py`,
  `analyze_results.py`: прочитаны как описание проведённой процедуры;
- `fixtures/cases.json`, сохранённые source media и M1 artifacts;
- `measurements/final.jsonl`, `determinism.json`, три `cold-*.json`;
- `results/event-maxima.json`, `analysis.json`, `paired-comparisons.json`,
  `oracles.json`; provenance corpus/replacement manifests;
- прежние review/measurement/provenance/resource summaries в
  `FakeDetector-Work/reviews/M3-R2A-transition/`.

Поиск по repository research охватил также последующие ARC-записи и
[принятый ATD review](2026-09-29-audio-atd-disposition-review.md).
Они сохраняют историю ASC carry-forward, но не добавляют ASC measurements.
ATD disposition не переоткрывается. Происхождение и права ранее использованных
источников остаются в [REFERENCES, M3-R2A](../REFERENCES.md#audio-m3r2a);
новых источников, лицензий или внешних научных утверждений этот review не вводит.

Read-only сверка существующих файлов: hashes V1/V2, восьми frozen scripts,
corpus/replacement manifests совпали; 609 case/raw identities и media hashes,
705 ссылок на prepared artifacts проверены. Все 627 сохранённых window/channel
строк maxima сверены с ASC max/top исходных JSON; 424 доступные ASC metric
summaries сверены с сохранёнными строками, включая count/undefined, median/p95,
top ordering и support. Записи 12 cases ×3 повторов и трёх fresh processes
согласуются с исходными numerical windows. Это **проверка сохранённых результатов**,
не повторные измерения, новые oracle tests или certification.

| Идентичность | SHA-256 |
|---|---|
| Frozen V2 | `db515484f4716d828e1fc3532369a2b148df4691894c99f7ed4e732b42025452` |
| `scripts/protocol.py` | `27742945543e894f20785549f862ae9c8236732ba7122f49e7b6321ff2b96d3b` |
| `fixtures/cases.json` | `bc861e90d0ba8bdcd074af2d6a189d83cf6bd4f0182e8f75c94f6b0b61b92c73` |
| `measurements/final.jsonl` | `5b97eb395234b5eae9697c9453ebcf2ab69691bdbc2caa3d64320ad4e8ce029a` |

M3-R2A: 608/609 completed cases, 573 controlled +35 real/derived. Только
**85 cases** имеют adjacent ASC support; 512 коротких residue fixtures ASC не
проверяют. Одна generated lineage; пять real groups (три LibriSpeech speakers,
NPS humpback, sorohanro trumpet). Производные, каналы, лаги и перекрывающиеся
frames не являются независимыми trials. Нет source-level holdout/population
validation. `resource_48000` и исторический Vibe Ace — technical rejections,
не отрицательные ASC measurements. Разрешённая outcome-blind замена Vibe Ace
сохранена, её результат не усилен.

Graphify provenance относится к SHA `625b9e83f133fb0ae31a4b90e9e1288bff96f69c`:
граф **STALE**, совпадающих ASC/M3-R2A узлов не найдено. Граф не пересобирался
и не использовался как доказательство. Выводы проверены по прямым источникам.

## 3. Два измерения и физическая воспроизводимость

Точная процедура остаётся в M3-R1 §5 и frozen M3-R2A. ASC читает принятый M1
`numpy_stft/1`, `hann4096_hop1024/1`: magnitude periodic Hann 4096, hop 1024,
backward rFFT, без padding/centering, второго STFT, resample или downmix.
Пары принадлежат одному окну и каналу; лаги h=1 и h=4 сохраняются отдельно.

| Свойство | Normalized magnitude spectral TV, D1/D4 | Spectral flux, F1/F4 |
|---|---|---|
| Измеряемая величина | Половина L1-разности отдельно нормированных magnitude distributions | Сумма положительных приростов magnitude / сумма magnitudes обеих сторон |
| Физический смысл | Изменение формы спектрального распределения | Направленный положительный magnitude change, чувствительный к уровню |
| Gain | Инвариантность к positive gain каждого готового frame | Чувствительность к относительному gain между frames |
| Silent support | Любая нулевая спектральная сумма делает D undefined | Одна silent сторона допустима; обе нулевые — undefined |
| Tiny pure-gain oracle ×2 | D=0 | F=1/3 |
| Различие на сохранённых controls | `smooth_envelope`: D1=0.00382513, D4=0.00794642 | Тот же case: F1=0.0708892, F4=0.272389 |
| Forensic specificity | Не установлена | Не установлена; отказ от D в пользу F не обоснован |

Сохранённый oracle PASS включает scalar references на spectral/gain/precision/
stereo/huge-float cases, gain/disjoint/silence endpoints, complete frames/lags,
zero denominators и channel ordering. Сохранённый determinism PASS относится
к проверенной матрице и фиксированной среде; межплатформенная bitwise FFT
identity не заявляется. Это поддерживает физическую воспроизводимость ASC.

Frame-wise invariance D не гарантирует D=0 у STFT frame, пересекающего gain
boundary: смешанная поддержка и leakage уже дали D1=0.318723/D4=0.505730.
D и F не взаимозаменяемы, не сливаются и не создают два forensic votes.
Выбор более благоприятной метрики или лага после исходов не выполняется.

## 4. Controlled manipulation и локализация

Все числа ниже — отдельные максимумы первого окна/channel 0, округлённые
только для представления. Максимумы разных метрик могут иметь разные позиции.
Это извлечение из прежних `event-maxima.json` / `final.jsonl`, не новый эксперимент.
Основные generated constructions имеют b=32000 при 16 kHz.

| Case / конструкция | D1 | D4 | F1 | F4 |
|---|---:|---:|---:|---:|
| `phase_jump`, фаза tone +π/2 | 0.585014 | 0.764586 | 0.372962 | 0.630120 |
| `amplitude_step`, постоянный уровень 0.1→0.7 | 0.726108 | 0.726108 | 0.612959 | 0.858624 |
| `gain_step`, tone справа ×2 | 0.318723 | 0.505730 | 0.325983 | 0.493726 |
| `dc_step`, tone справа +0.3 | 0.374540 | 0.693404 | 0.343981 | 0.532331 |
| `waveform_splice`, tone 250→2000 Hz | 0.631744 | 0.997850 | 0.411862 | 0.727023 |
| `similar_content_boundary`, speechlike shift −137 samples | 0.250977 | 0.351672 | 0.390374 | 0.725391 |
| `equal_rms_spectral`, та же waveform, что `waveform_splice` | 0.631744 | 0.997850 | 0.411862 | 0.727023 |
| `bandwidth_step`, смесь tone/high→tone | 0.535747 | 0.741594 | 0.261752 | 0.411468 |
| `eq_step`, изменение соотношения tone/high | 0.382525 | 0.524978 | 0.215441 | 0.326974 |
| `stationary_spectra`, смена двух стационарных смесей | 0.616881 | 0.997812 | 0.400165 | 0.702552 |
| `leakage_jump`, tone справа +0.5 | 0.499463 | 0.789822 | 0.411500 | 0.654829 |

TV и flux отвечают на controlled changes. У sine/multitone они близки к нулю
(около 1e−12), что подтверждает физический контраст с выбранными стационарными
controls. Но `waveform_splice` и `equal_rms_spectral` имеют одинаковые media
hashes и полные ASC outputs: это одна конструкция в двух ролях, не два независимых
подтверждения. Эти tone/speechlike constructions не являются content-matched
реальной сменой источника с независимо размеченными benign phonemes.

Truth входит в top-1 support D1/D4/F1 в 11/11 основных positive строках,
F4 — в 10/11; исключение F4 — `similar_content_boundary`. Support h=1 занимает
5120 samples, h=4 — 8192 (320/512 ms при 16 kHz). Начало union support не cut;
попадание truth внутрь такого интервала не означает точную локализацию монтажа.

На каждом из пяти real parents были созданы DC +0.2 и splice −137 samples
в правой половине первого M1 окна (controlled-positive), а также benign gain,
mute, fade и clipping derivatives. Для **шести** window/channel строк real splice
(trumpet stereo) truth входит в top support D1: **0/6**, D4: **1/6**,
F1: **1/6**, F4: **1/6**. Для шести real DC строк: **3/6, 0/6, 2/6, 1/6**
соответственно. Это сохранённые support indicators, не detection rate или recall.

Например, `libri-1320__splice` имеет D1=0.556704/D4=0.835370,
F1=0.693976/F4=0.909961; только D4 top support включает truth.
У `sorohanro-trumpet__splice`, channel 0, все четыре максимума равны parent
(0.635307/0.841142/0.815197/0.952860), все top supports вне truth.
Глобальный максимум может оставаться обычным событием даже после внесённого
изменения. Это не доказательство отсутствия локального response, но ограничение
его forensic-интерпретации и max-based localization. Gaps и непокрытые края
не превращаются в проверенное full-file покрытие.

## 5. Benign confounds: что действительно показано

| Причина / свидетельство | D1 / D4 | F1 / F4 | Предел причинного вывода |
|---|---:|---:|---|
| Плавная смена частоты, `smooth_frequency` | 0.458383 / 0.986575 | 0.229192 / 0.493295 | Нет вставленной abrupt boundary; высокий D4 не доказывает даже резкую склейку |
| Фонемный переход, generated `phoneme_transition` | 0.601427 / 0.988361 | 0.595579 / 0.841525 | Proxy, не размеченная реальная фонема |
| Артикуляционный transient, generated `plosive` | 0.690913 / 0.823730 | 0.650640 / 0.810803 | Proxy, не подтверждённая причина real peak |
| Перкуссия/атака, generated `percussion` | 0.283585 / 0.653325 | 1 / 1 | F насыщается на benign onset |
| `silence_to_speech` | 0.310834 / 0.781671 | 1 / 1 | D undefined на парах с полностью silent frame; максимум взят по определённым парам |
| Обычная смена содержимого, `legitimate_scene_change` | 0.729123 / 0.977464 | 0.712975 / 0.970352 | Generated speechlike→noise, не сертификат естественной сцены |
| Изменение уровня, `gain_change` | 0.318723 / 0.505730 | 0.325983 / 0.493726 | Та же waveform и полные ASC outputs, что positive `gain_step` |
| EQ, `eq_change` | 0.382525 / 0.524978 | 0.215441 / 0.326974 | Та же waveform и outputs, что positive `eq_step` |
| `dynamic_compression` | 0.312700 / 0.462911 | 0.474237 / 0.765919 | Заданный static compressor |
| Codec MP3 / AAC 64 kbps | 0.164619 / 0.197070; 0.164810 / 0.196732 | 0.385442 / 0.722139; 0.386067 / 0.722380 | Source `speechlike` уже имеет 0.164616/0.197137 и 0.385402/0.722119; codec не установлен как причина сильного отдельного peak |

`speech_to_silence`, fade и clipping также измерены: D1/D4 соответственно
0.361162/0.847492, 0.165097/0.197139, 0.288954/0.501183;
F1/F4 — 0.394092/0.713236, 0.448001/0.800916, 0.352141/0.565155.
Noise suppression проверен только простым noise-gate proxy, bandwidth history —
moving-average proxy. Настоящий denoiser, SRC, packet-loss concealment или
recording glitch как отдельная причинная категория здесь не подтверждены.

| Реальный original, первое окно/channel 0 | D1 | D4 | F1 | F4 |
|---|---:|---:|---:|---:|
| NPS humpback | 0.263574 | 0.388079 | 0.158849 | 0.275974 |
| LibriSpeech 6930 | 0.553650 | 0.757096 | 0.617927 | 0.918253 |
| LibriSpeech 1320 | 0.571060 | 0.794907 | 0.758274 | 0.919406 |
| LibriSpeech 5639 | 0.617944 | 0.876915 | 0.815652 | 0.985676 |
| sorohanro trumpet | 0.635307 | 0.841142 | 0.815197 | 0.952860 |

Реальная музыка даёт D1, сопоставимую с controlled equal-RMS switch; реальная
речь — высокие TV/flux без внесённого проектом splice. «Original» не означает
экспертно подтверждённую подлинность или отсутствие encoding/editing history.
Смена нот/инструментов предусмотрена как confound M3-R1, но у trumpet нет
event annotations: нельзя приписать отдельный peak определённой ноте или атаке.
То же ограничение относится к фонемам и артикуляции real speech.

Benign high response непосредственно подтверждён generated challenges;
real originals дополняют картину overlap. Для TV benign plosive/scene response
не ниже ряда controlled boundaries; D4 плавной частотной эволюции близка к 1.
Для flux benign onset достигает верхней границы 1, speech/music maxima также
перекрывают controlled responses. Полное тождество gain/EQ пар проверено по
media hashes и ASC outputs: разные экспериментальные labels не восстановимы
из одинаковых измерений. Пары не считаются независимыми observations.
Нет воспроизводимой forensic separation ни для D, ни для F. Это не population
FPR, не статистический тест и не доказательство невозможности будущего метода.

## 6. Отношение к ATD

ASC даёт **материально отличное описательное измерение**: в equal-RMS spectral
construction ATD E≈2.84e−14, ASC D1=0.631744/D4=0.997850; TV отражает смену формы
при почти постоянном уровне. ATD отдельно сохраняет sample-position jump и
RMS/DC-контекст. Flux дополнительно чувствителен к magnitude/level evolution.
Эта описательная полезность не равна доказанной дополнительной forensic utility.

ASC disposition обоснован собственными D/F, controls и recipes выше, не принятым
отрицательным результатом ATD. Сохранённые descriptive correlations и различия
позиций maxima не доказывают statistical independence. ASC/ATD остаются раздельными
измерениями общего transition track; fusion и независимые votes не создаются.
**ATD: RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED; carry-forward RESOLVED.**

## 7. Сравнение dispositions и следующий шаг

| Вариант | Оценка |
|---|---|
| TARGETED_NEXT_STUDY | Не выбран. Один content-matched source-switch/phoneme тест уточнил бы частный контраст, но текущие данные не выделяют неизменённый D/F признак с обещающей специфичностью. Даже благоприятный малый результат не устраняет уже показанные smooth-frequency, onset, gain/EQ и scene confounds; новый контекст/правило выбора означал бы другой scope |
| **RESEARCH_ONLY_NON_SPECIFIC** | **Выбран.** Физическое измерение воспроизводимо и описательно полезно; benign overlap и ограничения локализации не позволяют forensic promotion нынешнего профиля |
| DEFER_TO_PRODUCTION_READINESS_RESEARCH | Не выбран как disposition. Broad annotated corpus, независимые source groups и calibration нужны для будущих population claims, но уже имеющиеся данные достаточны, чтобы ограничить нынешнюю интерпретацию research-only. Такой campaign не становится новым обязательством |
| REJECT_FORENSIC_PROMOTION | Не выбран: достаточно зафиксировать установленный предел специфичности и сохранить описательный профиль. Оснований категорично исключить любую дальнейшую promotion-работу именно с этим профилем недостаточно; конкретная дальнейшая работа здесь не назначается, promotion сейчас не разрешается |

ROC/F1 optimization, threshold search/selection, severity mapping, Finding,
fake/authentic verdict и post-hoc выбор feature/lag не выполнялись.
Видимый зазор на выбранных примерах, который потребовал бы cutoff после
просмотра исходов, недостаточен для specificity; здесь такой cutoff не предлагается.
Production analyzer/threshold отсутствуют; production method не разрешён.

Владелец принял disposition (§8): ATD и ASC carry-forward **RESOLVED**,
**MACRO3_ALL_REQUIRED_CARRY_FORWARD_RESOLVED: YES**.
Следующая активная задача — **MACRO 3 DOCUMENTATION / INSTRUCTION HYGIENE AUDIT**,
затем **MACRO 3 CLOSURE REVIEW**. Macro 3 **IN_PROGRESS**;
автоматического закрытия нет. Hygiene/closure в этой задаче не выполняются.
ARC active work **NO**; принятый deferred scope и M3H-A01 не переоткрываются.

## 8. OWNER ACCEPTANCE — 2026-09-30

Владелец явно принял **RESEARCH_ONLY_NON_SPECIFIC** для ASC-TV-1:

- физическую валидность воспроизводимого измерения спектральных переходов;
- валидность normalized magnitude spectral TV и spectral flux как двух
  различных описательных измерений;
- наличие controlled manipulation response и сильных benign responses,
  существенное перекрытие их диапазонов;
- ненадёжность max-based localization в нескольких real-derived splice cases;
- forensic specificity **NOT ESTABLISHED**: сильный ASC response недостаточен
  для различения editing / source inconsistency и правдоподобной benign
  spectral evolution; ни TV, ни flux не установили существенно лучшую специфичность;
- описательное отличие от ATD: сильная смена спектральной формы возможна при
  слабом ATD energy transition; независимый forensic vote не установлен;
- **M3-ASC-D1: DONE / OWNER ACCEPTED DISPOSITION**;
- **ASC carry-forward: RESOLVED**;
- **FURTHER_ASC_PROMOTION_WORK_IN_CURRENT_MACRO3: NONE**.

Это не признание ASC неисправным, бесполезным или невалидным и не утверждение
математической невозможности будущей ценности. Прототип сохраняется как
research/descriptive evidence для будущей работы. Новые ASC эксперименты
и дальнейшая promotion work в текущем Macro 3 не начинаются.

Production method **NOT AUTHORIZED**, production threshold **NONE**,
production analyzer **NOT IMPLEMENTED**, Finding **NOT ADDED**;
severity/risk mapping и fake/authentic verdict **NOT AUTHORIZED**.
Post-hoc feature/lag selection не выполняется. TV и flux не становятся
двумя forensic votes; ASC и ATD не сливаются, статистическая независимость
и независимый forensic vote ASC относительно ATD не утверждаются.

ATD остаётся **RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED**, carry-forward
**RESOLVED**, его работа не переоткрывается. ARC сохраняет **RESEARCH MEASUREMENT
DEMONSTRATED / PRODUCTION PROMOTION DEFERRED**, активной ARC work нет;
M3H-A01 остаётся deferred. Все required carry-forward Macro 3 разрешены,
но Macro 3 остаётся **IN_PROGRESS**.

Следующая активная задача — **MACRO 3 DOCUMENTATION / INSTRUCTION HYGIENE AUDIT**,
затем **MACRO 3 CLOSURE REVIEW**. Планируемый audit проверит AGENTS.md,
governance/process docs, устаревшие временные инструкции, дубли правил,
obsolete owner gates, историю для research/changelog и возможную неоднозначность
старого carry-forward protocol text. **NO ACTION REQUIRED** — допустимый исход;
необходимость cleanup не предрешена. Эти работы здесь не выполнялись.
Свидетельства, формулы, таблицы и численные результаты review не изменены.

## 9. Артефакты и проверки

Research: `C:\Users\Vanur\Desktop\FakeDetector-Work\research\M3-ASC-D1-disposition\`:
`evidence-summary.md`, `feature-comparison.md`, `benign-confounds.md`,
`manipulation-evidence.md`, `disposition-analysis.md`, `recommended-next-step.md`,
`evidence-integrity.json`, `asc-evidence-extract.json`.
Review: `C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-ASC-D1-disposition\`:
`review-summary.md`, `complete.diff`, `git-status.txt`.
Исходные bundles сохранены. Запись принятия имеет отдельный review bundle
в подкаталоге `acceptance/`: `acceptance-baseline.json`, `acceptance-only.diff`,
`complete.diff`, `review-summary.md`, `git-status.txt`.

Полный intended diff включает новый untracked отчёт. Проверки этой docs-only
задачи: `git diff --check`, просмотр полного diff и итогового status;
проверка scope/API/dependencies/config/schema/дублирования и временных хвостов.
Предыдущие evidence не изменены. Исполняемые repository files, tests,
preprocessing, зависимости и production contracts не менялись. Новые тесты,
full quality barrier и certification не запускались по явному scope задания.
Git mutations не выполнялись; изменения unstaged. Disposition принят владельцем;
корректность записи принятия и обновлённый полный intended diff требуют owner
review. Staging/commit остаются владельцу. Agent self-report не заменяет приёмку.
