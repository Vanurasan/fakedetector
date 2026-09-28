# M3-R3C — ARC: дипломная stress/challenge validation

Дата выполнения: **2026-09-28**. Имя отчёта с 2026-09-27 сохранено по заданию.
Baseline `7c8d334960c3975f836caaf01939281dd52f204f`, ветка
`feat/stage12-macro3-audio-analyzer-expansion-wave1`, чистое начало.
**DONE / OWNER ACCEPTED RESEARCH RESULT; owner acceptance: 2026-09-28.**
ARC-NCC-1: **NEEDS_TARGETED_RESEARCH**. Приняты исследовательские свидетельства
и failure map; это не production method acceptance, calibration, threshold
selection, FPR/sensitivity validation или analyzer implementation.

## 1. Ответ на основной вопрос

Frozen ARC v2 полезен как bounded measurement: все **96** обычных controlled
copy-cases (8 sources ×3 lengths ×4 transformations) сохранили хотя бы одну
истинную пару с полным структурным support и точным offset. Но переход к
`READY_FOR_TUNING_STUDY` пока не обоснован. Легитимная музыкальная запись дала
rho **0.996936**, а периодический фон вытеснил известную speech-copy из cap64:
21 геометрически допустимая true pair, 20 nominated, **0 retained**, при global
rho=1. Этот максимум описывает тон, а не найденную речь.

Владелец принял failure map **2026-09-28** и разрешил планирование M3-R3D —
ARC Applicability & Retrieval Competition Research; решение записано в §10.
Возможная смена search/formula или автоматический gate требует отдельного
решения; здесь они не проектировались и не реализованы. Frozen v2 сохранён,
tuning не выполнялся; ARC v3 не разрешён.
Отложенная broad source-level validation M3-R3B не возвращается как обязательное
условие текущей дипломной фазы. Ограниченный вывод M3-R3A не расширяется этим опытом.

## 2. Состав, происхождение и freeze

**22 реальные source recordings:** 8 speech recordings / **7 speaker groups**,
3 music groups и11 background groups. Пять LaMIT T1 recordings представляют
четырёх speakers; три LibriSpeech FLAC — трёх других speakers. Исходный выбор
не использовал M3-R3C outcomes: P001/T1 у каждого LaMIT speaker и P005/T1 у S01,
плюс три уже принятых LibriSpeech recordings. Это controlled/read narration,
а не подтверждённая voice-message population. Derivatives не увеличивают counts.

Реальные фоны: ESC-50 vacuum cleaner, washing machine, garbage-truck engine,
alarm clock, clock tick, rain, wind, train, breathing; NPS humpback; RoomTone01
с room/air-conditioning/server-fan noise. Music: Sorohan trumpet, Vibe Ace,
Sweet Waltz. LaMIT speech в смеси — TV-like content proxy, не запись телевизора.
Синтетические tone/hum/beep/rhythm и silence — **одна generator lineage**,
не дополнительные независимые source recordings.
Provenance, права, attribution и actual roles —
[REFERENCES M3-R3C](../REFERENCES.md#audio-m3r3c-sources).
Все source URLs, SHA-256 и даты доступа — во внешнем `sources/manifest.json`;
полный список предоставлен в `source-summary.md` и `provenance-summary.md`.

Predeclaration SHA-256: `7afb533a9b388664362f584472fbf49ece94b1b43c4387e338dd71797461001d`.
Frozen ARC v2 SHA-256:
`04a2d54f0e5bc51c3eacf376cd797b16c178dd6a9740accb626cc77e92bfa625`.
Файл скопирован без изменения из M3-R3A; математическая/численная история
[M3-R2B](2026-09-26-audio-repeated-segment-measurement-prototype.md) сохранена.
Compensated float64, descriptor, normalization, NCC, guard, search, caps,
overlap, support, ties и channels не менялись. Нового clamp нет; унаследованная
roundoff-обработка является частью frozen identity, guard не ослаблялся.

Все 184 final artifact hashes, parent/recipe hashes, sample intervals, codec
packet/priming facts, M1 manifests и numeric hashes заморожены до outcomes в
`fixtures/cases.json`; SHA `702a8ff79185bc9fa8d919a2f081b65a613d48f9fe44915a70922b334145ae29`.
Freeze timestamp и script hashes — `predeclaration.sha256.json`, начало исполнения —
`logs/measurement-start.json`. Нет удаления неудобных/high-rho cases после outcomes.
Holdout/calibration split не создавался: это фиксированный challenge set, без
обучения настроек. Background reuse сохраняет одну родительскую группу.

## 3. Конструкция и область измерений

Copy lengths: near=2L, medium=3L, long=min(4L, доступные samples первого M1 window),
L=1024 ceil(fs/1024). Измерены все 24 source/length сочетания в каждом copy-классе.
Source prefix [0,n) повторён в том же laboratory artifact; destination кратен4096
после gap≥fs/4, у нечётных source indices добавлено137 samples. Gap — fixture
construction, не padding предобработки. Gain0.4; Gaussian noise σ=0.1RMS(parent),
PCG64 seeds2026092800+source index; MP3 libmp3lame96k всего составленного artifact.
Sample rates/channels сохранены. MP3 skip/discard/first PTS проверены;
дополнительные0/38 decoded tail samples не расширяют truth interval.

Originals измерены без изменений. Полные Vibe Ace, Sweet Waltz и RoomTone01
получили штатный **technical_resource_rejection** до numeric artifacts.
Эти три результата сохранены. Отдельно, до outcomes, подготовлены native-rate /
channel 8s excerpts: начало0, midpoint−4s, duration−9s. Их FFmpeg atrim/float64
WAV construction полностью записана; это внешние research fixtures, **не новый
preprocessing capability, не runtime fallback и не full-duration acceptance**.
Исторический Vibe Ace rejection M3-R2A не переписан. Для двух длинных musical
sources также составлена пара разных3s sections первого/среднего excerpt.
Это разные source intervals, не утверждение независимого исполнения chorus.

36 real-source overlays: шесть background sources × shared/distinct segments
× +15/0/−10dB speech/background. Две speech portions — независимые LaMIT S01 и S02
P001/T1, каждая2L+4096. RMS uncentered, pooled по двум blocks и каналам;
один multiplier `RMS(speech)/RMS(background)/10^(dB/20)`; clipping/peak normalization
не выполнялись. Stereo background сохранён; mono foreground явно продублирован
на два канала fixture. Distinct segments одного файла **не независимые записи**;
у короткого LaMIT background их boundaries перекрываются на2394 samples.
12 generated overlays — те же levels и speech portions с общим tone/hum/beep/rhythm.
Все mixtures — искусственные stress cases, не частоты встречаемости в voice messages.

ARC использует только штатные bounded M1 samples/STFT4096/1024. Global rho —
максимум retained first-L channel rho после общего channel-mean lag selection.
Cross rho — отдельно, только полные2L в двух размеченных разных blocks.
Best-channel максимум не подменяет другие channels/support. Structural support
означает определённость двух последующих L/2, **не** превышение similarity rule.
Median обычная, p95 nearest-rank. Undefined не заменяется нулём.

## 4. Известные копии: измерение, retrieval, localization

| Класс | Cases | Min | Median | p95 | Max | Eligible | Nominated | Retained | Error=0 |
|---|---|---|---|---|---|---|---|---|---|
| COPY_EXACT | 24 | 1 | 1 | 1 | 1 | 24 | 24 | 24 | 24 |
| COPY_GAIN | 24 | 1 | 1 | 1 | 1 | 24 | 24 | 24 | 24 |
| COPY_CODEC | 24 | 0.997372885 | 0.999544465 | 0.999993341 | 0.999999875 | 24 | 24 | 24 | 24 |
| COPY_NOISE | 24 | 0.994111699 | 0.996783583 | 0.997826301 | 0.998312922 | 24 | 24 | 24 | 24 |


Global и размеченный cross maxima совпали для этих96 cases. Все96 имели
геометрически допустимую truth, nomination, retention и точный offset; минимум
ошибки **0 decoded samples** в каждом случае. Это локализация соответствующего
offset/2L support, не восстановление полных границ splice и не production sensitivity.
Число seed-pairs отличается от числа cases: на класс490 eligible;
exact/gain/codec/noise nominated409/407/409/407, retained372/372/372/369.
Таким образом, сохранение хотя бы одной истинной пары не означает exhaustive recall.
В каждом copy-классе12 cases достигли candidate cap, но сохранили truth.

## 5. Обычная речь, music и реальные backgrounds

| Original | Speaker | Global rho | Поддержка следующей L |
|---|---|---|---|
| original-lamit-S01_P001_T1 | lamit-S01 | — | нет двух nonoverlap2L |
| original-lamit-S01_P005_T1 | lamit-S01 | — | нет двух nonoverlap2L |
| original-lamit-S02_P001_T1 | lamit-S02 | 0.140995001 | [0.003697748156747477, 0.014075015755785803] |
| original-lamit-S03_P001_T1 | lamit-S03 | 0.0466990606 | [0.005563483062060735, -0.010149129858349057] |
| original-lamit-S04_P001_T1 | lamit-S04 | — | нет двух nonoverlap2L |
| original-libri-6930 | libri-speaker-6930 | — | нет двух nonoverlap2L |
| original-libri-1320 | libri-speaker-1320 | 0.219557906 | [-0.00018147155271704715, 0.017597916530475825] |
| original-libri-5639 | libri-speaker-5639 | 0.350497998 | [-0.01809753709732313, 0.05367654548696786] |


У четырёх из восьми коротких originals нет двух непересекающихся полных2L;
это ограничение geometry, не доказательство отсутствия повторов. Defined speech
range0.0466991–0.350498 относится только к четырём источникам. Highest LibriSpeech
5639: [118784,151552) ↔ [204940,237708), offset86156 при16kHz;
последующая поддержка −0.0180975/0.0536765 не повторяет высокий first-L максимум.
Здесь нет разметки слов/дыхания/vowel spans; они не выдаются за ground truth
повторов. Breathing отдельно представлен ESC-50. Изменение словесного содержания,
реальные бытовые voice messages и natural repeated chorus требуют иной разметки.

| Case | Global rho | Cross rho | Support best-channel |
|---|---|---|---|
| original-sorohanro-trumpet | 0.144703262 | — | [0.007713943598412159, 0.0014294516717871714] |
| original-vibe-ace | — | — | resource rejection |
| excerpt-vibe-ace-0 | 0.980550348 | — | [0.9492676233269999, 0.8964661759162034] |
| excerpt-vibe-ace-1 | 0.978024196 | — | [0.9595941439308061, 0.4120812656088967] |
| excerpt-vibe-ace-2 | 0.996936217 | — | [0.996238813485296, 0.9733651621294231] |
| natural-sections-vibe-ace | 0.556513535 | 0.180524971 | [0.017848140869810302, -0.0437906964889524] |
| original-sweetwaltz | — | — | resource rejection |
| excerpt-sweetwaltz-0 | 0.533068031 | — | [0.005137150617296528, 0.0006990987466698759] |
| excerpt-sweetwaltz-1 | 0.397006136 | — | [0.19133053778140374, 0.4799357198626652] |
| excerpt-sweetwaltz-2 | 0.448284648 | — | [-0.05332677726839536, -0.1906259739831055] |
| natural-sections-sweetwaltz | 0.171352206 | 0.171352206 | [0.044404778715884934, 0.0335788882534348] |


Vibe Ace final excerpt: [20480,110592) ↔ [183311,273423), offset162831
(≈3.69231s при44.1kHz). Channel1 rho0.996936, support0.996239/0.973365;
channel0 rho0.988577, support0.994242/0.941584. Оба выбрали δ=−1009,
channel disagreement отсутствует; exact decoded equality **false**.
Это повторяющаяся near-waveform структура легитимного музыкального accompaniment,
перекрывающая диапазон noise-copy maxima. Измерение не устанавливает, была ли
музыка независимо переисполнена, использовала production loop или sampling;
оно не означает suspicious copied speech. В трёх Vibe excerpts offset≈162830
повторяется. У заданной пары разных музыкальных sections cross maxima лишь
0.180525 (Vibe) /0.171352 (Sweet Waltz); более высокий Vibe global0.556514
не следует выдавать за cross-section result. Natural independently re-performed
chorus/riff этим набором не доказан.

| Case | Global rho | Support best-channel |
|---|---|---|
| original-esc-vacuum_cleaner | 0.0734947024 | [-0.0010033656557624831, 0.004016536273280185] |
| original-esc-washing_machine | 0.906703482 | [0.8988883985426566, 0.8877224371781335] |
| original-esc-engine | 0.148566013 | [-0.298641672198967, -0.011251222204669852] |
| original-esc-clock_alarm | 0.112384345 | [-0.02466303463202909, -0.05228432198620491] |
| original-esc-clock_tick | 0.172876976 | [0.26908716702081265, -0.14860398391462373] |
| original-esc-rain | 0.0495972066 | [0.018287897561504673, 0.00840801336005028] |
| original-esc-wind | 0.259293778 | [0.07135061897476866, -0.060182745784775324] |
| original-esc-train | 0.167116161 | [-0.033175564365100385, -0.08152149512566903] |
| original-esc-breathing | 0.225139708 | [0.015152254235111894, -0.06489799022305412] |
| original-nps-humpback | 0.128275513 | [-0.0026351630022333375, 0.015211063485210116] |
| original-room | — | resource rejection |
| excerpt-room-0 | 0.391684462 | [0.26554977520645145, 0.21454758369520158] |
| excerpt-room-1 | 0.367735008 | [0.3893835185392541, 0.1809674768785598] |
| excerpt-room-2 | 0.386915589 | [0.38300229951040454, 0.3773002207256796] |


Washing-machine source: rho0.906703, support0.898888/0.887722,
offset105535 samples (≈2.39308s); физически подобна повторяющаяся механическая
звуковая структура, exact samples не равны. Это source-label и waveform observation,
не утверждение forensic authenticity или установленной причины каждой вибрации.
Room/HVAC/fan excerpts достигли0.391684; их hashes/intervals сохранены отдельно.

## 6. Общий фон и периодичность

| Фон | Отношение | +15dB global/cross | 0dB global/cross | −10dB global/cross |
|---|---|---|---|---|
| esc-rain | shared | 0.163148019 / 0.0976607742 | 0.522390203 / 0.522390203 | 0.907473885 / 0.907473885 |
| esc-rain | distinct_segments | 0.162256075 / 0.0976283412 | 0.076730751 / 0.0537215102 | 0.0474781823 / 0.0474781823 |
| esc-vacuum_cleaner | shared | 0.167514755 / 0.0957185319 | 0.482263339 / 0.482263339 | 0.893562332 / 0.893562332 |
| esc-vacuum_cleaner | distinct_segments | 0.164173117 / 0.0920879106 | 0.0753714557 / 0.0545075596 | 0.0446175341 / 0.0446175341 |
| esc-engine | shared | 0.172235596 / 0.104265643 | 0.439174497 / 0.439174497 | 0.874102555 / 0.874102555 |
| esc-engine | distinct_segments | 0.164111372 / 0.0935096655 | 0.111114571 / 0.066843513 | 0.134480597 / 0.107588979 |
| esc-clock_alarm | shared | 0.167115029 / 0.0978145544 | 0.52891806 / 0.52891806 | 0.909476911 / 0.909476911 |
| esc-clock_alarm | distinct_segments | 0.163764703 / 0.0956035908 | 0.0957232406 / 0.0605084557 | 0.0929498842 / 0.0608811293 |
| sorohanro-trumpet | shared | 0.162894255 / 0.0959284781 | 0.634958995 / 0.634958995 | 0.940959458 / 0.940959458 |
| sorohanro-trumpet | distinct_segments | 0.169043279 / 0.100445036 | 0.111119399 / 0.0726935572 | 0.0562110298 / 0.0469062202 |
| lamit-S03_P001_T1 | shared | 0.168966968 / 0.0992589907 | 0.651595475 / 0.651595475 | 0.945471763 / 0.945471763 |
| lamit-S03_P001_T1 | distinct_segments | 0.166501539 / 0.10178527 | 0.0749780444 / 0.0542242566 | 0.0542568556 / 0.041326261 |


В shared cases повторялся **один и тот же физический background segment**:
rain, vacuum, garbage truck, alarm, trumpet либо третья speech recording.
Foreground recordings независимы, поэтому высокий cross максимум нельзя
приписывать копированию foreground речи. При−10dB shared rho0.874103–0.945472;
два следующих support blocks явно сохранены, не отфильтрованы.
При distinct-source-segments cross max≤0.107589 в этом малом set, но это не
универсальное свойство независимого фона и не правило классификации.

| Сигнал | Standalone rho | Standalone support | Mix +15 global/cross | Mix0 global/cross | Mix−10 global/cross |
|---|---|---|---|---|---|
| tone | 1 | [1.0, 1.0] | 0.193551841 / 0.128922473 | 0.622362412 / 0.573011035 | 0.9393737 / 0.920067424 |
| hum | 1 | [1.0, 1.0] | 0.18133959 / 0.117218483 | 0.617784816 / 0.574035199 | 0.938190018 / 0.920204342 |
| beep | 1 | [None, 1.0] | 0.174269772 / 0.107863104 | 0.513493134 / 0.513493134 | 0.904080559 / 0.904080559 |
| rhythm | 1 | [1.0, 1.0] | 0.163307657 / 0.0990909761 | 0.569819117 / 0.569819117 | 0.924101032 / 0.924101032 |


Standalone tone/hum/rhythm повторяют аналитические cycles и имеют rho/support=1;
beep повторяет pulse train, но у global-best pair одна support half undefined
из-за silence. Один first-L rho=1 не устанавливает достаточную поддержку.
Generated overlays в−10dB дали global до0.939374 и cross до0.924101;
различие global/cross сохранено, включая gap-crossing candidates.

## 7. Failure map и cap competition

| Область | Наблюдение / предел вывода |
|---|---|
| A — явно работает | 96 ordinary controlled copy-cases; retained true offset/error0 и full structural support, при фиксированных lengths/gain/codec/noise |
| B — benign high correspondence | Music near-repetition0.996936, mechanical source0.906703, shared physical background до0.945472, periodic cycles1; известна конструкция shared/synthetic, но не production history music |
| C — abstention / support | 4 коротких speech originals, silence, short0.5s copy; 3 full-source technical resource rejections отдельно; beep best pair имеет undefined half |
| D — retrieval competition | В60s tone+speech-copy 20 true nominations потеряны при cap64, все64 returned pairs лежат вне speech spans |
| E — numerical / implementation issue | Guard violations отсутствуют; frozen oracles и exact repeats PASS; numerical correction не потребовалась |

Cap stress: seeds258→256, candidate union677→64. Truth21 eligible→20 nominated→0 retained.
Best pair [163840,253952) ↔ [1266340,1356452), offset1102500,
rho/support1/1/1 целиком в background-only областях. Source speech была добавлена
в [0,135168) и [2510832,2646000); общий непрерывный250Hz фон не является копией
всего mixed waveform. High global output не доказывает retrieval target speech.
Это один заранее созданный worst case, не оценка частоты потерь в population.
Не требуется объявлять poor result numerical failure; изменять bounds здесь нельзя.

## 8. Повторяемость и ресурсы

37 focused M1 tests PASS (14 и23); неизменённый frozen suite **7 oracle groups PASS**.
Для exact/codec/noise, highest benign speech, highest music, highest periodic/
background, cap-hit и silence выполнены **исходный запуск +2 repeats**:
восемь групп, canonical numerical SHA совпали. Повторный cap-hit — выбранный
по predeclaration highest-rho ordinary copy с cap, не дополнительный новый
тест60s stress. Clock/memory поля исключены из numerical fingerprint;
остальные поля, пары и порядок сохранены. Guard violations/ARC timeouts: **0**.

| Ресурс | N | Median | p95 | Max |
|---|---|---|---|---|
| preprocessing_s | 184 | 0.5012793 | 1.4574326 | 6.5827416 |
| coarse_s | 181 | 0.0055128 | 0.0238576 | 0.0944683 |
| ncc_s | 181 | 0.4374851 | 2.2084261 | 2.437962 |
| wall_s | 184 | 0.43465255 | 2.232161 | 2.4649786 |
| working_set_bytes | 184 | 66879488 | 78217216 | 80355328 |
| process_lifetime_peak_bytes | 184 | 73658368 | 97882112 | 97882112 |
| artifact_bytes | 184 | 4770384 | 16824144 | 31582152 |


Время — seconds, память/artifacts — bytes. Total ARC wall не включает отдельно
измеренные preprocessing wall, acquisition и offline construction. Windows working
set относится к основному ARC-процессу, без суммирования FFmpeg child memory;
process-lifetime peak нельзя приписывать конкретному case. Наибольший observed
working set80,355,328 bytes, process peak97,882,112 bytes; **не certified hard bounds**.
Totals:108477 coarse comparisons,14747 nominations,6789 NCC verifications,
55,490,613 lag-channel evaluations; numeric artifacts1,094,961,656 bytes
(сумма case accounting, не размер всех workspace/media/repeat files).
Candidate-cap cases67, seed-cap cases2. 181 prepared/processed cases,
3 technical rejections;175 cases с defined global rho,6 measured abstentions.

## 9. Ограничения, outcome и review

Outcome **NEEDS_TARGETED_RESEARCH** сохраняется вследствие background ambiguity
и конкретной потери target speech на bounded retrieval, а не из-за отсутствия
отложенного большого корпуса. Общий порог не разрешит attribution известного
повторяющегося фона; будущий automatic applicability/background method — OWNER GATE,
не созданная здесь rule. Calibration, thresholds, analyzer implementation/
registration, Finding, risk/correlation и public contracts не менялись.
ATD-LOCAL-1 и ASC-TV-1: **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**,
OPEN/REQUIRED; Macro3 **IN_PROGRESS**, closure rule сохранено.

Raw media и скрипты: `FakeDetector-Work/research/M3-R3C-arc-stress/`.
Review: `FakeDetector-Work/reviews/M3-R3C-arc-stress/`; complete.diff включает
новый отчёт, все184 case summaries и provenance предоставлены отдельными файлами.
Full quality barrier и strict certification не запускались; executable repo files
не изменялись. Исследовательские свидетельства и failure map приняты владельцем
2026-09-28; планирование следующего scope разрешено в границах §10.
Git mutations не выполнялись; staging/commit остаются владельцу.

## 10. OWNER ACCEPTANCE — 2026-09-28

**M3-R3C: DONE / OWNER ACCEPTED RESEARCH RESULT.**
**ARC-NCC-1: NEEDS_TARGETED_RESEARCH.**
Владелец явно принял исследовательские свидетельства и failure map:

1. Frozen ARC v2 эффективно локализует известные физические waveform copies
   в проверенных обычных controlled cases. Все 96 exact/gain/codec/noise cases
   сохранили истинную пару и ожидаемый offset с ошибкой 0 samples в определённой
   экспериментом geometry; это не утверждение о production sensitivity.
2. Высокий rho не специфичен для manipulated speech: легитимная/повторяющаяся
   музыка, механическая периодичность, shared physical background и generated
   tone/hum/beep/rhythm дают copy-like correspondence. Один rho threshold
   сам по себе не разрешает наблюдаемую проблему forensic interpretation.
3. Отдельная проблема — bounded retrieval competition: повторяющийся или
   периодический фон может создать достаточно конкурирующих кандидатов,
   чтобы номинированная известная speech-copy исчезла после retained cap.
4. ARC **не готов к tuning/calibration study**. Нерешённые вопросы
   методологические: applicability/background attribution и bounded retrieval
   competition. Их принятие как failure map не означает их разрешения.

Разрешено **планирование M3-R3D — ARC Applicability & Retrieval Competition
Research**, ещё не выполненного исследования. Его вопросы и последовательность
принадлежат [ROADMAP](../ROADMAP.md#audio-m3r3d): начать с анализа текущих frozen
outputs и существующих M1 representations; оценить speech/background/periodic/
ambiguous mixed support и необходимость отдельного applicability метода.
Если без изменения candidate/search поведения retrieval failure не разрешается,
определить минимальное обоснованное будущее изменение ARC v3 и остановиться
на **OWNER GATE до реализации**. ARC v3 сейчас не разрешён.

Frozen ARC v2 сохраняется неизменным и для следующего research task:
descriptor, formula, compensated accumulation, normalization, NCC, numerical
guard, search bounds, candidate caps, overlap, support, ties и channel behavior.
Tuning, threshold selection и production calibration не разрешены; production
method acceptance, FPR/sensitivity validation, analyzer implementation и Finding
не выполнены. Все измерения, ограничения и failure-map результаты §§2–8 сохранены.
В этой acceptance-задаче tests/experiments/quality barrier/certification не запускались.

M3-R3B broad source-level validation: **DEFERRED UNTIL CALIBRATION /
PRODUCTION-READINESS RESEARCH**, без возврата в обязательства дипломной фазы.
ATD-LOCAL-1 и ASC-TV-1: **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**;
оба обязательства нерешённые. Macro 3 — **IN_PROGRESS**.
Staging/commit остаются владельцу; Git mutations не выполнялись.
