# M3-R2A — измерительный прототип общего трека переходов

Дата: 2026-09-26. **DONE / OWNER ACCEPTED RESEARCH RESULT**.
Baseline `9e386dc52e9c4ce59ac35bda35b992f0b65f286c`, ветка
`feat/stage12-macro3-audio-analyzer-expansion-wave1`. Начало исходной задачи —
чистое committed дерево; продолжение после owner resolution — ожидаемые dirty
REFERENCES/ROADMAP и untracked этот отчёт. Git mutations не выполнялись.

ATD-LOCAL-1: **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**.
ASC-TV-1: **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**.
Владелец принял исследовательский результат 2026-09-26 (§11); production-метод не принят.
Обе процедуры численно воспроизводимы в проверенной матрице и дают разное
описание переходов; ни одна пока не показала forensic-селективности на benign
контенте. Сильные ordinary responses сохранены. Нет fusion, score, порогов,
Findings, реализации/регистрации анализаторов или изменений correlation/risk.
ARC не исследовался, статусы ABN/AMC сохранены. Macro 3 остаётся IN_PROGRESS.

## 1. Исторический ресурсный gate и решение владельца до измерений

Vibe Ace / Kevin MacLeod, SHA-256
`14634cc7c6f825db857c1594ac8c609bf49321336f625bd6559a039644bfc9f6`,
44.1 kHz stereo, 61.44 s, отклонён неизменённым `_prepare_audio_forensic`:
`PreprocessingError(resource_limit, audio_precision_artifacts)`.
Три штатных окна требуют 21 168 000 bytes worst-case samples и 41 996 304 bytes
spectra, всего **63 164 304** при бюджете **52 428 800**; превышение 10 735 504.
Окна `[0,441000)`, `[1134252,1575252)`, `[2268504,2709504)`.
Это useful technical boundary evidence, не forensic Finding. Vibe Ace не имеет
completed ATD/ASC measurements. Он не обрезался, бюджет не увеличивался.

Владелец явно разрешил **REPLACE_SOURCE**, сохранив rejection и V1.
Первый и единственный фактически проверенный replacement-кандидат: запись
«solo trumpet -06in F - 90bpm.wav», Mihai Sorohan / sorohanro, Freesound 77711.
Использован неизменённый полный provider HQ MP3 preview, другая реальная запись,
не cropped Vibe Ace и не synthetic music. Исходный uploaded WAV требует login
и не скачивался; эти данные не называются lossless original recording.
Выбор: первый источник в записанном порядке, с правами/допустимым scope и
PASS штатного M1 producer. Только права/формат/preflight; ATD/ASC ещё не запускались.

Replacement preflight **PASS**: 44 100 Hz, stereo, 5.333356 s;
**11 172 400 required/actual artifact bytes**, **52 428 800 budget bytes**,
два артефакта. Штатное окно `[0,235201)`. SHA-256 download:
`1aa175783edddd4db6aa0fdc26c1a0fa01dab19028c7b58eeb575eb66b1b06bf`.
Current canonical page явно разрешает CC BY 4.0; права и historical BY 3.0
metadata описаны в [REFERENCES M3-TR-04](../REFERENCES.md#audio-m3r2a).
Selection rule, все attempted candidates и фактический manifest сохранены во
внешних `provenance/replacement-selection-rule.md`, `replacement-selection.json`.

**PREDECLARATION_V1**, неизменённая историческая версия:
`fbac82a38984856edc5206bae1cb5b621be4cda5e406a1b3058c0a4743321fce`.
**PREDECLARATION_V2**, действующий frozen protocol:
`db515484f4716d828e1fc3532369a2b148df4691894c99f7ed4e732b42025452`.
V2 freeze UTC: `2026-09-25T19:50:08.739573+00:00` (2026-09-26 Asia/Krasnoyarsk).
V2 изменяет только source membership/identity, manifest/hash, закрытый resource
gate и соответствующие ссылки. Source groups остаются 1 generated + 5 measured
real; Vibe Ace отдельно historical rejection. V1 scripts сохранены, V2 entrypoints
отличаются только ссылками на corpus/source/freeze. ATD/ASC formulas, fixtures,
labels, normalization, support, metrics, aggregation и threshold policy неизменны.
**До replacement selection и V2 freeze численных ATD/ASC outcomes не существовало.**
Gate разрешён; задача сейчас не BLOCKED.

## 2. Процедура, coverage и границы evidence

Формулы — [M3-R1 §§3–5](2026-09-26-audio-method-selection.md), без изменений.
ATD использует shared `frame_audio(2048,512)`, b=a+768…a+1279, earliest max-diff,
L/R по 512, common-max scale, раздельные J/E/Es/A. ASC читает штатные
source-bound magnitude spectra periodic Hann 4096/1024/backward rFFT, h=1/4,
common-max и раздельные D1/D4/F1/F4. Нет второго STFT, resample/downmix или
собственного decoder. Harness вызывает существующие typed probe, M1 producer,
registry/budget и `AnalyzerRequest.read_numeric`. Весь application/intake pipeline
этим прямым private-path вызовом не сертифицируется.

В JSON каждый stream/window/channel/metric имеет count/undefined_count,
median, nearest-rank p95, max, top-16 с tie по sample index, строки измерений,
две поддержки и union, source PTS отдельно от sample coordinate. Raw waveforms
и spectra в отчётных JSON не помещены. Zero denominator → null с причиной;
короткая поддержка → insufficient; identity/nonfinite/budget/timeout — technical.
Межоконных сравнений и сшивания gaps нет. Все координаты — наблюдаемые M1 facts.
Например, у NPS первый sample PTS=1105, sample index=0; последующие окна начинаются
с sample 449740/899481, source PTS 450845/900586. Эти шкалы не подменяются.
Declared-denominator coverage для trumpet ≈1.0000000017 из-за округления declared
duration; оно сохранено без ложного clamp. Это не доказательство full-duration
coverage вообще. У 60 s / 8 kHz resource input наблюдено 30 s (50%).

## 3. Состав матрицы и provenance

Запрошено **609 cases**, завершено **608**: **573 controlled + 35 real/derived**.
Один `resource_48000` — ожидаемый technical rejection до numeric artifacts;
нулевое покрытие сохранено. Historical Vibe Ace в эти 609 не включён.
Завершение case включает честные insufficient/undefined: только **85 cases**
имеют хотя бы одну ASC adjacent comparison; 512 residue fixtures по 2048 samples
не пригодны для ASC. Эти boundary fixtures не раздувают efficacy sample size.
Числа являются количеством исследовательских обработок, не detected edits.

| Source group | Cases |
|---|---:|
| generated-master-20260926 | 574 |
| nps-humpback-20010925 | 7 |
| libri-speaker-6930 | 7 |
| libri-speaker-1320 | 7 |
| libri-speaker-5639 | 7 |
| sorohanro-freesound-77711 | 7 |

Одна generator lineage `generated-master-20260926`, seed **20260926**;
все 574 synthetic cases зависимы по происхождению. Пять real groups — три
разных LibriSpeech speakers, NPS и замена music; по одному source + шесть
derivatives первого M1 окна. Все derivatives остаются в родительской группе.
Нет независимого train/test split, population sample или p-values.
Реальные recordings могут иметь обычную encoding/editing history; benign здесь
не означает экспертно установленную подлинность. Все hashes/rights —
[REFERENCES](../REFERENCES.md#audio-m3r2a), `provenance/corpus-v2.json`.

Точные counts по каждому case class (включая requested resource rejection):

| Case class | Запрошено |
|---|---:|
| sine | 1 |
| multitone | 1 |
| noise | 1 |
| smooth_envelope | 1 |
| smooth_frequency | 1 |
| speechlike | 1 |
| continuous | 1 |
| phase_jump | 1 |
| amplitude_step | 1 |
| gain_step | 1 |
| dc_step | 1 |
| waveform_splice | 1 |
| similar_content_boundary | 1 |
| equal_rms_spectral | 1 |
| bandwidth_step | 1 |
| eq_step | 1 |
| stationary_spectra | 1 |
| leakage_jump | 1 |
| phoneme_transition | 1 |
| plosive | 1 |
| percussion | 1 |
| silence_to_speech | 1 |
| speech_to_silence | 1 |
| fade | 1 |
| clipping | 1 |
| gain_change | 1 |
| eq_change | 1 |
| dynamic_compression | 1 |
| noise_suppression | 1 |
| legitimate_scene_change | 1 |
| bandwidth_history | 1 |
| integer_precision | 4 |
| gain_invariance | 2 |
| channel_order | 2 |
| length | 9 |
| silence | 1 |
| constant | 1 |
| nyquist | 1 |
| active_silent_stereo | 1 |
| candidate_residue | 512 |
| search_edge | 5 |
| three_windows_gap | 2 |
| one_max_window | 1 |
| codec_recompression | 2 |
| environment | 1 |
| real_gain | 5 |
| real_dc | 5 |
| real_mute | 5 |
| real_fade | 5 |
| real_clip | 5 |
| real_splice | 5 |
| speech | 3 |
| music | 1 |

В synthetic основной матрице 7 negative, 11 controlled-positive, 15 benign
cases; они дают 33 window/channel строки для сравнений. Benign матрица покрывает
14 заданных семантических классов, codec представлен MP3 и AAC. Phoneme/plosive,
percussion и noise suppression — явно generated proxies; suppression — простой
noise gate, не полноценный denoiser. Bandwidth history — moving average;
SRC не выполнялся и не объявляется проверенным. У real speech нет ручной
фонемной разметки, поэтому конкретный peak не приписывается plosive.

## 4. Контролируемые и benign результаты

Ниже maxima каждой отдельной метрики первого окна/channel 0; полные distributions,
включая median/p95, undefined и все поддержки, находятся в `measurements/final.jsonl`.
Es — signed maximum, не abs и не signed значение в позиции max E. Таблица не
объединяет synthetic с real и не вводит decision threshold.

| Case (первое окно, channel 0) | J | E | Es | A | D1 | D4 | F1 | F4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| sine | 0.597954 | 1.78205e-14 | 1.78205e-14 | 2.64035e-13 | 1.20246e-12 | 1.98851e-12 | 6.01627e-13 | 9.94518e-13 |
| multitone | 0.673693 | 3.54057e-14 | 3.21071e-14 | 1.71472e-12 | 4.79851e-12 | 8.10797e-12 | 2.40552e-12 | 4.06053e-12 |
| noise | 0.860903 | 0.0532171 | 0.0532171 | 0.141243 | 0.235508 | 0.301973 | 0.120258 | 0.163672 |
| smooth_envelope | 0.597954 | 0.0357185 | 0.0357185 | 2.64559e-13 | 0.00382513 | 0.00794642 | 0.0708892 | 0.272389 |
| smooth_frequency | 0.589304 | 0.00450032 | 0.00450032 | 0.0723986 | 0.458383 | 0.986575 | 0.229192 | 0.493295 |
| speechlike | 0.765251 | 0.285736 | 0.285736 | 0.0920813 | 0.164616 | 0.197137 | 0.385402 | 0.722119 |
| continuous | 0.597576 | 2.06611e-05 | 2.06611e-05 | 0.00309704 | 2.85893e-05 | 1.39925e-05 | 1.44354e-05 | 7.10948e-06 |
| phase_jump | 0.940626 | 0.00097466 | 0.00097466 | 0.0662226 | 0.585014 | 0.764586 | 0.372962 | 0.63012 |
| amplitude_step | 1 | 0.75 | 0.75 | 1 | 0.726108 | 0.726108 | 0.612959 | 0.858624 |
| gain_step | 0.597954 | 0.206567 | 0.206567 | 2.64035e-13 | 0.318723 | 0.50573 | 0.325983 | 0.493726 |
| dc_step | 0.927889 | 0.186244 | 0.186244 | 0.346546 | 0.37454 | 0.693404 | 0.343981 | 0.532331 |
| waveform_splice | 0.707107 | 2.84187e-14 | 2.84187e-14 | 1.84211e-12 | 0.631744 | 0.99785 | 0.411862 | 0.727023 |
| similar_content_boundary | 0.765251 | 0.285736 | 0.285736 | 0.0920813 | 0.250977 | 0.351672 | 0.390374 | 0.725391 |
| equal_rms_spectral | 0.707107 | 2.84187e-14 | 2.84187e-14 | 1.84211e-12 | 0.631744 | 0.99785 | 0.411862 | 0.727023 |
| bandwidth_step | 0.828025 | 2.33106e-14 | 1.78205e-14 | 1.56298e-12 | 0.535747 | 0.741594 | 0.261752 | 0.411468 |
| eq_step | 0.69942 | 2.90053e-14 | 2.87291e-14 | 1.62198e-12 | 0.382525 | 0.524978 | 0.215441 | 0.326974 |
| stationary_spectra | 0.673693 | 0.00116989 | 9.43113e-14 | 1.92563e-12 | 0.616881 | 0.997812 | 0.400165 | 0.702552 |
| leakage_jump | 0.953389 | 0.340154 | 0.340154 | 0.469182 | 0.499463 | 0.789822 | 0.4115 | 0.654829 |
| phoneme_transition | 0.803749 | 0.446399 | 0.446399 | 0.0920813 | 0.601427 | 0.988361 | 0.595579 | 0.841525 |
| plosive | 0.943713 | 0.285736 | 0.285736 | 0.100699 | 0.690913 | 0.82373 | 0.65064 | 0.810803 |
| percussion | 0.998306 | 0.973237 | 0.973237 | 0.278158 | 0.283585 | 0.653325 | 1 | 1 |
| silence_to_speech | 0.765251 | 0.284046 | 0.271172 | 0.0920813 | 0.310834 | 0.781671 | 1 | 1 |
| speech_to_silence | 0.999468 | 1 | 0.285736 | 0.0920813 | 0.361162 | 0.847492 | 0.394092 | 0.713236 |
| fade | 0.77137 | 0.365204 | 0.286854 | 0.0943942 | 0.165097 | 0.197139 | 0.448001 | 0.800916 |
| clipping | 1 | 0.213323 | 0.213323 | 0.290606 | 0.288954 | 0.501183 | 0.352141 | 0.565155 |
| gain_change | 0.597954 | 0.206567 | 0.206567 | 2.64035e-13 | 0.318723 | 0.50573 | 0.325983 | 0.493726 |
| eq_change | 0.69942 | 2.90053e-14 | 2.87291e-14 | 1.62198e-12 | 0.382525 | 0.524978 | 0.215441 | 0.326974 |
| dynamic_compression | 0.869988 | 0.285736 | 0.285736 | 0.0920813 | 0.3127 | 0.462911 | 0.474237 | 0.765919 |
| noise_suppression | 0.861032 | 0.123162 | 0.123162 | 0 | 0.239888 | 0.324666 | 0.137909 | 0.213957 |
| legitimate_scene_change | 0.859707 | 0.285736 | 0.285736 | 0.128649 | 0.729123 | 0.977464 | 0.712975 | 0.970352 |
| bandwidth_history | 0.764704 | 0.28581 | 0.285714 | 0.0779013 | 0.163952 | 0.196442 | 0.385347 | 0.722096 |
| codec_mp3 | 0.765374 | 0.285762 | 0.285743 | 0.0921311 | 0.164619 | 0.19707 | 0.385442 | 0.722139 |
| codec_aac | 0.766321 | 0.285627 | 0.285627 | 0.0939423 | 0.16481 | 0.196732 | 0.386067 | 0.72238 |

Математические contrasts: equal-RMS spectral transition даёт E≈2.84e−14 и
D1=0.631744/D4=0.997850; ASC описывает смену формы при почти неизменном уровне.
Фазовый jump даёт J=0.940626 с точным b, а E≈0.000975; waveform jump не обязан
сопровождаться energy step. Gain-only transition имеет E=0.206567 и D1=0.318723:
в смешанных frames возникает leakage, поэтому frame-wise gain invariance D
не обещает нулевую D на crossing frame. Tiny pure-gain oracle даёт D=0,
F=1/3 для ×2. Значение E не обязано равняться идеальным 1/3: b выбран по diff,
а не по известной gain boundary; для gain_step max E смещён на −287 samples.

Ограничения выражены уже в controls: stationary sine даёт J≈0.598, stationary
noise J≈0.861; max-diff selector не делает J близким к нулю на каждом benign
сигнале. Smooth frequency transition даёт D4≈0.987 без вставленной границы.
Benign clipping даёт J=1, percussion proxy E≈0.973 и F1/F4=1, plosive proxy
D1≈0.691; legitimate scene change D1≈0.729. Эти значения не скрыты и не
называются FPR. Амплитудный controlled step с J/A=1 и E=0.75 остаётся только
проверкой ожидаемой арифметики, не discriminator монтажа.

## 5. Реальный слой и производные

| Case (первое окно, channel 0) | J | E | Es | A | D1 | D4 | F1 | F4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| nps-humpback | 0.935499 | 0.553933 | 0.553933 | 0.488399 | 0.263574 | 0.388079 | 0.158849 | 0.275974 |
| libri-6930 | 0.981672 | 0.906032 | 0.906032 | 0.57931 | 0.55365 | 0.757096 | 0.617927 | 0.918253 |
| libri-1320 | 0.981965 | 0.831203 | 0.831203 | 0.692607 | 0.57106 | 0.794907 | 0.758274 | 0.919406 |
| libri-5639 | 0.988636 | 0.949167 | 0.949167 | 0.353589 | 0.617944 | 0.876915 | 0.815652 | 0.985676 |
| sorohanro-trumpet | 0.962965 | 0.819895 | 0.819895 | 0.392144 | 0.635307 | 0.841142 | 0.815197 | 0.95286 |

Это пять originals, первое окно и channel 0; остальные окна/каналы и 30
derivatives полностью сохранены отдельно в JSON. У одного последующего окна
неизменённого LibriSpeech 5639 J=1; насыщение bounded метрики не доказывает
edit. Real music D1≈0.635 сопоставима с controlled equal-RMS spectral case.
Высокие benign responses встречаются в речи, музыке и environment, а не только
в искусственном generator. Real clipped derivatives также достигают J=1.
Размер/разнообразие real слоя недостаточны для production calibration:
**REAL_CORPUS_INSUFFICIENT** для такой цели. Эти наблюдения не population FPR,
не sensitivity и не лицензия на продвижение к production.

## 6. ATD↔ASC без fusion

Descriptive Spearman для отдельных maxima: controlled n=33 window/channel
строки из одной lineage; real n=45 из пяти source groups с зависимыми derivatives
и каналами. Это не 33/45 независимых forensic trials. Correlation не доказывает
ни independence, ни causal distinction, ни production correlation_group.

| Слой | ATD metric | D1 | D4 | F1 | F4 |
|---|---|---:|---:|---:|---:|
| controlled | J | 0.303846 | 0.241472 | 0.50924 | 0.456225 |
| controlled | E | 0.00586167 | 0.0343327 | 0.635123 | 0.648188 |
| controlled | Es | 0.0228074 | 0.0204596 | 0.654091 | 0.672707 |
| controlled | A | 0.16275 | 0.139667 | 0.580545 | 0.570341 |
| real | J | 0.230909 | 0.294793 | 0.266722 | 0.392373 |
| real | E | 0.34977 | 0.443776 | 0.325442 | 0.511047 |
| real | Es | 0.490063 | 0.585805 | 0.469437 | 0.730935 |
| real | A | -0.294679 | -0.431765 | -0.402543 | -0.379203 |

Предварительно заданные paired increases относительно control, tolerance 1e−12
только для numerical equality, не detector threshold. Generated tone-related
cases сравниваются с sine, speech-related — speechlike; real derivatives — с
первым parent окном. Некоторые broad challenge comparisons не content-matched,
поэтому эти четыре категории описывают конкретную пару maxima, не весь метод.

| Слой / сравнение maxima | Both increase | ATD-only | ASC-only | Neither |
|---|---:|---:|---:|---:|
| controlled / E/D1 | 12 | 1 | 13 | 0 |
| controlled / J/D1 | 23 | 0 | 2 | 1 |
| real / E/D1 | 1 | 6 | 3 | 26 |
| real / J/D1 | 3 | 12 | 1 | 20 |

В real benign derivatives E/D1: neither 15, ATD-only 6, ASC-only 3, both 0;
J/D1: neither 11, ATD-only 10, ASC-only 1, both 2. В real controlled derivatives
E/D1 neither 11/both 1: изменение часто не поднимает source maximum, потому что
исходный benign максимум уже высок. Это важное ограничение max-based reporting,
а не доказательство отсутствия локального изменения. Исходные delta сохранены.

Top-1 E/D1 поддержки пересекаются в **11/33** controlled и **7/45** real строках.
Низкое пересечение maxima разных метрик не означает независимости причин:
maxima могут приходиться на разные обычные события одной записи.
ASC полезна для spectral change при стабильном RMS; ATD даёт sample-position
выбранной разности и отдельно уровень/DC-контекст. Новые независимые votes из
этого не следуют. Продуктовой fusion или нового score нет.

## 7. Локализация, края, численная проверка и determinism

Все **512** step residues локализованы выбранным b точно и дали J/E/Es/A=1.
Этот факт относится к специально построенному одношаговому сигналу.
Для 11 основных positive cases truth входит в поддержку max J в 8/11,
max E в 6/11, max D1/D4 в 11/11. Медианная abs-разница координаты top J и truth
481 samples, top E — 287. ASC координата — начало union support, не cut:
median 1280/5376 samples для D1/D4 нельзя называть ошибкой point detector.
Поддержка D1 занимает 5120 samples, D4 — 8192, ATD — 1024. Истинная граница
similar-content splice не совпала с глобальным ATD maximum. Неизмеренные края,
gaps и отсутствующий h=4 явно сохранены; full-file localization не заявляется.

**PASS**: 12 oracle/structural groups. Independent scalar formulas проверены
на phase/gain/spectral/int24/huge-float/stereo случаях (atol=rtol=1e−12), отдельно
analytic gain/disjoint-spectrum/active-silent endpoints, exact 512 residues,
zero denominators, ties, channel ordering, complete frames/lags/tails,
nonfinite и deadline technical rejection. `results/oracles.json` — полный список.
Длины 2047/2048/2049, 4095/4096/4097, 5120, 8192/8193 дают ровно штатные counts.
PCM8/16/24/32 и float64 paths измерены, но bit-identical equivalence между разными
quantization/codec histories не предполагается. Global ×2 сохраняет все ATD/ASC
значения точно; ×1e150 дал max abs delta 3.42e−14 / 4.24e−16, finite output.

**Determinism PASS:** 12 заранее выбранных cases × **3** повтора, hashes полного
numerical результата windows совпадают точно; timing/RSS исключены. Три fresh
process cases также совпали с основным numerical результатом. Межплатформенная
побитовая FFT identity не заявляется. Формулы после результатов не менялись.

## 8. Фактические ресурсы и ограничения замеров

Windows 11 x64 build 26200; Python 3.12.10; NumPy 2.5.2; FFmpeg/ffprobe
9.0.1-full_build-www.gyan.dev, gcc 16.1.0. CPU Intel Core Ultra 7 270K Plus,
24 physical / 24 logical cores. Точные version outputs — logs/measurement-start.json.
Всего 27 252 ATD frame/channel, 13 168 ASC frame/channel, 13 062 h=1 и 12 752 h=4
сравнений (каждое даёт две раздельные величины). Timeouts нет; предусмотренный
min(remaining,30 s) проверяется между bounded blocks. В resource rejection
coverage=0; technical refusal не превращён в insufficient forensic signal.

| Case | ATD s | ASC s | Harness s | Preprocessing s | Artifacts / bytes |
|---|---:|---:|---:|---:|---|
| phase_jump | 0.011954 | 0.0018924 | 0.0163747 | 0.456791 | 2 / 1479128 |
| resource_8000 | 0.0949376 | 0.0155313 | 0.12628 | 2.79265 | 6 / 11216400 |
| resource_48000_short | 0.155049 | 0.0380596 | 0.216608 | 1.52711 | 2 / 22924560 |
| nps-humpback | 0.35588 | 0.0529492 | 0.440533 | 6.48029 | 6 / 31582144 |
| sorohanro-trumpet | 0.152667 | 0.0193816 | 0.184217 | 1.27894 | 2 / 11172400 |

Основной процесс, 35 real/derived cases: median/max ATD **0.037856/0.355880 s**,
ASC **0.006110/0.052949 s**, combined harness **0.050019/0.440533 s**.
Median CPU=0.046875 s, max=0.390625 s; Windows process_time имеет грубую дискретность,
нулевые CPU у коротких cases не означают отсутствие работы. Preprocessing отдельно:
real median 0.744075 s, max 6.480292 s. Reader/hash I/O входит в harness, отдельно
учтено. Не складывать elapsed разных фаз как hard realtime guarantee.
Median ASC=0 во всей controlled матрице обусловлена 512 короткими residue cases;
это не representative throughput. Max controlled ATD/ASC=0.155049/0.038060 s.

Fresh-process observations (кэш ОС не сбрасывался, не storage-cold):

| Свежий процесс | ATD s | ASC s | Harness s | Process peak bytes |
|---|---:|---:|---:|---:|
| phase_jump | 0.0117755 | 0.0022547 | 0.0171301 | 54476800 |
| resource_48000_short | 0.148875 | 0.0382494 | 0.211005 | 77369344 |
| sorohanro-trumpet | 0.109236 | 0.0265451 | 0.148709 | 65085440 |

Общий измерительный процесс: max process-lifetime working-set peak
**117 542 912 bytes (112.098 MiB)** через Windows GetProcessMemoryInfo.
Fresh process peaks 54 476 800 / 77 369 344 / 65 085 440 bytes. Это whole-process
RSS/working set с imports/allocator, не hard memory bound, не tracemalloc и не
per-case peak в общей последовательности. FFmpeg child RSS этим счётчиком не
покрывается; полная native preprocessing RSS certification не выполнена.
Во время numeric measurement загружается один sample ИЛИ spectral artifact,
ATD по одному frame, ASC по одной паре; нет full-duration decode или N².
Numeric scratch существенно меньше 32 MiB по фиксированному layout. Отдельная
диагностика deep size повторно прочитанного JSON bookkeeping максимум 13 382 120
bytes (NPS), не in-flight RSS и не доказательство hard bound. Максимум успешно
использованных artifacts — 6 / 31 582 144 bytes, в пределах текущего бюджета.
Три максимальных stereo окна 48 kHz и historical Vibe Ace штатно не допускаются:
изолированная допустимость отдельных representations не гарантирует композицию.

## 9. Q1–Q10 и следующий gate

| Вопрос | Ответ |
|---|---|
| Q1: ATD соответствует математическому намерению? | Да на проверенной матрице/oracle; max-diff selector может смещать energy estimate и даёт высокую J на обычных сигналах |
| Q2: ASC соответствует математическому намерению? | Да; D описывает shape, F positive magnitude change, zero support честно undefined; crossing gain frames создают leakage |
| Q3: benign high ATD? | Noise, plosive/percussion proxies, clipping, silence boundaries, real speech/music; встречается J=1 без forensic verdict |
| Q4: benign high ASC? | Smooth frequency, фонемные/scene proxies, natural music/speech, silence onset, обработка gain/EQ/compression |
| Q5: ASC добавляет описание? | Да: equal-RMS spectral/EQ cases при E≈0; это не доказанная forensic independence |
| Q6: ATD добавляет описание? | Да: sample-position jump и отдельный RMS/DC context; phase jump J высок при малой E, scalar support уже ASC |
| Q7: насколько responses пересекаются? | Paired deltas/support/correlations выше; source maxima часто уже велики, одну причину нельзя считать двумя votes |
| Q8: честна ли localization? | Да как mathematical support; нет оснований называть global maxima найденными cut или считать union start точной границей |
| Q9: совместимы ли ресурсы? | Обработанные cases укладываются в budgets/deadline; default preflight отклоняет отдельные композиции, child RSS и hard bounds не доказаны |
| Q10: готовы ли к большему corpus/calibration? | Оба NEEDS_TARGETED_RESEARCH; сначала annotated content-matched benign/controlled transitions, source-level holdout, проверка ограничения maxima; production calibration не разрешена |

Исходная рекомендация исследователя до owner acceptance (§11) — определить
целевой протокол с реальными event annotations, matched controls,
достаточным source diversity и честной ресурсной применимостью. Здесь это
рекомендация, не автоматически разрешённое расширение корпуса, preprocessing
или изменение формул. Исходный допуск ATD/ASC — OWNER_ACCEPTED_FOR_MEASUREMENT_PROTOTYPE;
production acceptance отсутствует, thresholds/FPR/severity не созданы.

## 10. Проверки и артефакты owner review

Существующие focused tests выполнены на том же baseline и не повторялись без
новых изменений M1; **43 passed, 563 deselected in 4.95s**, exit 0:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_preprocessing.py tests/test_stage5_internal_models.py -k 'window_values_and_coverage_match_source or incomplete_window_no_padding or window_selection or window_policy_limits or window_policy_rejection or test_frames or fft_dc_sine_multichannel_deterministic or spectral_resource_and_finite_output or fft_aggregate_frames_and_tightened_policy or numeric_reader_binds_identity_extent_and_immutable_backing or numeric_reader_rejects_nonfinite_audio or audio_sample_provenance_identity or audio_precision_budget_preflight_precedes_decode or dispatcher_numeric_audio_demand or audio_producer_retains_incomplete_requested_coverage or u8_centering_and_high_rate or test_invalid_numeric_input' --basetemp='C:\Users\Vanur\Desktop\FakeDetector-Work\research\M3-R2A-transition\focused-test-temp' -p no:cacheprovider
```

External execution: project `.venv/Scripts/python.exe` + `scripts/prepare_v2.py`,
`measure_v2.py`, `oracles.py`, `analyze_results.py`; fresh-process calls
`measure_v2.py phase_jump`, `resource_48000_short`, `sorohanro-trumpet`.
Repository code/tests/config/dependencies не изменены. `git diff --check`,
полный intended diff с untracked report и status проверяются при сборке bundle;
full quality barrier и strict certification не запускались по scope задания.

Research root: `C:\Users\Vanur\Desktop\FakeDetector-Work\research\M3-R2A-transition\`.
`predeclaration.md`/`predeclaration-v2.md` и SHA JSON сохраняют обе версии;
`fixtures/cases.json` содержит source/derivative hashes, recipes и manifests;
`measurements/final.jsonl`, `determinism.json`, `cold-*.json` — machine-readable
outcomes; `results/event-maxima.json`, `paired-comparisons.json`, `analysis.json`,
`oracles.json` — анализ; `provenance/` — rights snapshots и history gate.
`scripts/` хранит воспроизводимый harness и hashes. Никаких loose Desktop files.
Review bundle: `C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-R2A-transition\`:
complete.diff, review-summary.md, git-status.txt, measurement-summary.md,
resource-summary.md, provenance-summary.md. Owner acceptance этого результата
не подменяется успешным self-report; staging/commit остаются владельцу.

## 11. OWNER ACCEPTANCE — 2026-09-26

Владелец явно принял M3-R2A: **DONE / OWNER ACCEPTED RESEARCH RESULT**.
Принятый статус **каждого** из ATD-LOCAL-1 и ASC-TV-1:
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**. Арифметика/oracles и
детерминизм подтверждены в проверенной матрице; селективность на benign content
остаётся неразрешённой. Измеренные результаты и ограничения выше сохранены.

Целевое продолжение ATD/ASC отложено в последовательности работ, **не отменено**.
Оба обязательства остаются **OPEN / REQUIRED**. Их не требуется выполнять
непосредственно перед ARC, однако каждое требует явного последующего решения
владельца до закрытия Macro 3 по [правилу ROADMAP](../ROADMAP.md#audio-m3-required-carry-forward).
Начало ARC, молчание или нехватка времени не разрешают carry-forward.

Владелец разрешил следующий активный трек: **ARC-NCC-1 — measurement-only
prototype повторного сегментного соответствия**. ARC в M3-R2A не исследовался;
это разрешение не означает production method acceptance, одобрение production
анализатора, статистическую независимость от transition evidence или закрытие
обязательств ATD/ASC. Macro 3 остаётся **IN_PROGRESS**.

Production calibration, реализация ATD/ASC, выбор thresholds, Findings и fusion
не разрешены. Risk/correlation и публичные контракты не изменены. Эта запись
приёмки не добавляет экспериментов или экспериментальных свидетельств;
запись решения и обновлённый полный intended diff проверены владельцем; staging/commit остаются владельцу.
