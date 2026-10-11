# M3-R3A — ARC: independent re-speech и copied waveform

Дата исследования: **2026-09-26 UTC / 2026-09-27 Asia/Krasnoyarsk**.
Baseline `4f122da5eef74ade8d886942f843ce44bc8f11fe`, ветка
`feat/stage12-macro3-audio-analyzer-expansion-wave1`, чистое начало.
**DONE / OWNER ACCEPTED RESEARCH RESULT; owner acceptance: 2026-09-27.**
ARC-NCC-1 сохраняет **NEEDS_TARGETED_RESEARCH**.
Это результат ограниченного речевого исследования, не production acceptance,
не разрешение calibration и не закрытие Macro 3.

## 1. Корпус, независимые единицы и scope

Права и attribution: [M3-SP-01 / LaMIT v2](../REFERENCES.md#audio-m3r3a-lamit).
Внешний корпус удовлетворяет same human speaker + same phrase + separate takes:
поставщик описывает две разные recording sessions. Проверены source SHA-256,
200 различных decoded sample payloads, идентификаторы speakers/phrases/takes.
Одни лишь разные hashes не доказывают независимое произнесение: основание —
документированный протокол сбора. Это не forensic-сертификация исходных сессий.

Выбраны все четыре speakers и 25 равномерно распределённых phrase IDs
(1,5,…,97), по два takes: **200 natural utterances, 100 speaker/phrase groups,
четыре независимые speaker groups**. Provider содержит 800 уникальных takes;
byte-identical копии в Audio/Audio_and_labels не удваивают population.
Никакой outcome-dependent выбор или удаление источников не выполнялись.
Два original takes короче 2L; они сохранены и не padded ради валидного NCC.

Target 20×5×3 не достигнут: здесь 4×25×2. Это ограниченный описательный pilot
для четырёх speakers, но не подтверждённая широкая source-level validation.
Итальянская controlled read speech не заменяет реальные voice messages,
разнообразные устройства/помещения, языки или независимый first-party корпус.
Увеличение pair count не увеличивает число speakers.

S01/S02 — exploratory; S03/S04 — holdout, по 100 takes на split.
Группы выбраны по outcome-blind SHA ordering до измерений. Все derivatives
остаются в родительском split; cross-speaker controls только внутри split.
При четырёх speakers отдельный validation split не создавался. Common prompts
между splits допустимы, но результаты нельзя считать независимыми phrase trials.
Holdout не использован для настройки ARC или thresholds.

## 2. Freeze, fixtures и история подготовки

Frozen ARC v2 SHA-256:
`04a2d54f0e5bc51c3eacf376cd797b16c178dd6a9740accb626cc77e92bfa625`.
Скопирован без изменения из [принятого M3-R2B](2026-09-26-audio-repeated-segment-measurement-prototype.md#10-owner-acceptance--2026-09-26).
Формула, compensated float64, descriptor/normalization, guard, search bounds,
caps, overlap, support, ties, channels и ресурсы сохранены.
Новых preprocessing capabilities, runtime dependencies и SciPy нет.
Точный профиль остаётся [M3-R1 §§3,7](2026-09-26-audio-method-selection.md).

Рабочая преддекларация SHA-256: `432d29ac6192fa32972e2c37031648b9b82bd7ae40505a5c20a23d00d5b3450e`.
Состав, split, transformations, scripts, метрики и exclusions зафиксированы
до corpus outcomes; cases SHA — в logs/premeasurement.json.
Первоначальная V1 `98e4e71920b6eaf0c0f076cf5d1aa3886adbfd10fa8059e61a60b9f1a89219e5` сохранена с исходными scripts в
archive/pre-outcome-v1. V1 preparation остановилась до ARC на первой MP3-копии:
148648 исходных против148655 decoded samples. Packet accounting
131×1152−1105−1152=148655, first_sample_pts1105 — encoder priming.
Это ограничение нового constructor, не numeric failure ARC.

До outcomes уточнён только tail mapping: весь decoded материал остаётся в
fixture, но source/truth ограничен min(parent count, decoded count).
Packet durations, skip/discard и typed first PTS проверяются; неподтверждённый
хвост не выдаётся за исходный take. Нет alignment по NCC, подбора кодека,
resample, downmix, trimming или padding для искусственной поддержки.
История остановки и диагностики сохранена; frozen ARC v2 не менялся.

Все originals целиком прочитаны первым штатным bounded M1 window; fixtures
повторно проходят тот же M1 producer. STFT только существующая4096/1024.
Fixture — лабораторная композиция двух отдельных записей с явным gap,
не натуральная запись двух voice messages. Сохраняются parent SHA,
speaker/phrase/take IDs, source/destination intervals, recipe и derivative SHA.
Для каждого speaker/phrase: T1↔T2; exact/gain0.4/noise sd0.005/MP3 96k
копии T1; контроль следующей phrase. RNG2026092604. Destination phase0 или137
выбрана по phrase ID до outcomes. Никакие derivatives не новые natural takes.
Cross-speaker controls сопоставляют только speakers одного split.

## 3. Речевые распределения и speaker-level результаты

**727 completed fixtures: 700 primary speech comparisons и27 challenges.**
Каждый класс копии имеет100 constructed cases, всего400 copy derivatives.
Единица summary — source-level comparison; independent group — speaker.
Cross rho — максимум retained first-part rho, когда оба полных2L support
лежат внутри разных исходных takes/копий. Gap-crossing и внутриодного-take
пары не входят в этот описательный контраст. Они не удаляются из raw outputs;
global max по всем возвращённым парам показан отдельно. Это известная
лабораторная разметка, недоступная production detector, не изменение ARC.
Пустой cross-set — abstention, не rho0. Неопределённый NCC не suspicious result.
Медиана стандартная, p95 nearest rank; никакого threshold sweep.

Per-speaker maxima; двух-speaker comparison показано обоим speakers,
но в общем числе comparisons учитывается один раз:

| Speaker / split | COPIED_CODEC | COPIED_EXACT | COPIED_GAIN | COPIED_NOISE | DIFFERENT_PHRASE_SAME_SPEAKER | DIFFERENT_SPEAKER_DIFFERENT_PHRASE | NATURAL_RE_SPEECH | SAME_PHRASE_DIFFERENT_SPEAKER |
|---|---|---|---|---|---|---|---|---|
| S01 / exploratory | 0.999875 | 1 | 1 | 0.996542 | 0.236222 | 0.157149 | 0.309817 | 0.181164 |
| S02 / exploratory | 0.999891 | 1 | 1 | 0.974811 | 0.2656 | 0.157149 | 0.488186 | 0.181164 |
| S03 / holdout | 0.999832 | 1 | 1 | 0.995656 | 0.254903 | 0.250347 | 0.436541 | 0.370398 |
| S04 / holdout | 0.999921 | 1 | 1 | 0.998676 | 0.414925 | 0.250347 | 0.552478 | 0.370398 |

Сводки классов с теми же четырьмя speaker groups:

| Класс | Speakers | Comparisons | Cross rho median / p95 / max | Global rho median / p95 / max | Cross abstention | Cap hit |
|---|---|---|---|---|---|---|
| COPIED_CODEC | 4 | 100 | 0.999621 / 0.999893 / 0.999921 | 0.999619 / 0.999893 / 0.999921 | 2 | 92 |
| COPIED_EXACT | 4 | 100 | 1 / 1 / 1 | 1 / 1 / 1 | 2 | 92 |
| COPIED_GAIN | 4 | 100 | 1 / 1 / 1 | 1 / 1 / 1 | 2 | 92 |
| COPIED_NOISE | 4 | 100 | 0.991494 / 0.997745 / 0.998676 | 0.991491 / 0.997745 / 0.998676 | 2 | 92 |
| DIFFERENT_PHRASE_SAME_SPEAKER | 4 | 100 | 0.153452 / 0.314938 / 0.414925 | 0.178644 / 0.314938 / 0.414925 | 4 | 95 |
| DIFFERENT_SPEAKER_DIFFERENT_PHRASE | 4 | 50 | 0.107506 / 0.183893 / 0.250347 | 0.125063 / 0.230246 / 0.388814 | 2 | 48 |
| NATURAL_RE_SPEECH | 4 | 100 | 0.265816 / 0.488186 / 0.552478 | 0.273324 / 0.488186 / 0.614381 | 2 | 99 |
| SAME_PHRASE_DIFFERENT_SPEAKER | 4 | 50 | 0.128552 / 0.214542 / 0.370398 | 0.149088 / 0.237898 / 0.370398 | 2 | 49 |

| Класс | Exploratory rho median / p95 / max | Holdout rho median / p95 / max |
|---|---|---|
| COPIED_CODEC | 0.999567 / 0.999851 / 0.999891 | 0.999668 / 0.999897 / 0.999921 |
| COPIED_EXACT | 1 / 1 / 1 | 1 / 1 / 1 |
| COPIED_GAIN | 1 / 1 / 1 | 1 / 1 / 1 |
| COPIED_NOISE | 0.972187 / 0.996163 / 0.996542 | 0.992919 / 0.99789 / 0.998676 |
| DIFFERENT_PHRASE_SAME_SPEAKER | 0.147073 / 0.236222 / 0.2656 | 0.165505 / 0.325911 / 0.414925 |
| DIFFERENT_SPEAKER_DIFFERENT_PHRASE | 0.103214 / 0.147694 / 0.157149 | 0.113737 / 0.208286 / 0.250347 |
| NATURAL_RE_SPEECH | 0.248984 / 0.435674 / 0.488186 | 0.285841 / 0.524136 / 0.552478 |
| SAME_PHRASE_DIFFERENT_SPEAKER | 0.114381 / 0.170852 / 0.181164 | 0.148621 / 0.237898 / 0.370398 |

Наблюдаемые диапазоны natural и всех transformed/exact copies:

| Speaker | Natural min / max | Copy min / max | Пересечение диапазонов |
|---|---|---|---|
| S01 | 0.0973845 / 0.309817 | 0.986536 / 1 | False |
| S02 | 0.118622 / 0.488186 | 0.905596 / 1 | False |
| S03 | 0.131847 / 0.436541 | 0.968598 / 1 | False |
| S04 | 0.128502 / 0.552478 | 0.986385 / 1 | False |

На определённых cross-сравнениях pooled natural max=0.552478, minimum
максимума среди всех четырёх copy-классов=0.905596; в каждом из четырёх speakers
наблюдаемые диапазоны не пересеклись, в том числе у обоих holdout speakers.
Это ограниченное свидетельство различимости waveform correspondence на данной
матрице. Global natural max по всем retained pairs=0.614381; global и размеченный
cross-контраст не взаимозаменяемы, а число определённых cases может различаться.

Это descriptive overlap/gap, не cutoff, FPR, sensitivity, accuracy или F1.
Highest observed natural case: `NATURAL_RE_SPEECH__S04_P077_T1__S04_P077_T2`,
cross max rho=0.552478.
Support NCC той же пары: [0.0035290083389948003, -0.004131866915823835];
exact decoded equality: False.
Все first/support NCC и exact decoded flags сохранены в raw JSON;
высокая first-part rho не означает высокие оба support blocks.
Ограниченный диапазон четырёх speakers не подтверждает отсутствие перекрытия
в будущей популяции; полезность для forensic intent этим не установлена.

## 4. Retrieval, localization и caps

Truth означает происхождение constructed copy, не факт malicious edit.
Eligible pair допускает истинный offset в frozen delta/support geometry.
Coarse seed-overlap exclusions, descriptor nominations и cap64 могут
не сохранить такую геометрически достижимую пару; пропуск не маскируется.
Case-level existence и pair-level counts сообщаются отдельно. Минимальный
offset error среди retained eligible pairs — точность соответствия,
не точность границ редактирования; undefined localization не считается0.

| Класс | Truth cases | Eligible cases | Nominated cases | Retained cases | True offset cases | Eligible / nominated / retained pairs | Min offset error median / p95 / max samples |
|---|---|---|---|---|---|---|---|
| CHALLENGE_CAP | 4 | 4 | 4 | 4 | 4 | 12 / 4 / 4 | 0 / 0 / 0 |
| COPIED_CODEC | 100 | 98 | 98 | 98 | 98 | 4227 / 3713 / 3091 | 0 / 0 / 0 |
| COPIED_EXACT | 100 | 98 | 98 | 98 | 98 | 4227 / 3714 / 3089 | 0 / 0 / 0 |
| COPIED_GAIN | 100 | 98 | 98 | 98 | 98 | 4227 / 3711 / 3087 | 0 / 0 / 0 |
| COPIED_NOISE | 100 | 98 | 98 | 98 | 98 | 4227 / 3510 / 2609 | 0 / 0 / 0 |

В каждом copy-классе 98/100 cases имеют допустимую truth geometry; все98
номинированы, retained и имеют хотя бы один true-offset pair. Два остальных
используют S01/P061/T1 (78899 samples) и S01/P085/T1 (88594), короче2L=90112.
Они сохранены в полном знаменателе, а не удалены как неудобные observations.
В exact class cap сократил число известных nominated pairs с3714 до3089,
но ни один из98 допустимых copy cases не потерял все истинные пары.
Это не гарантия recall при другом положении, окружении или количестве копий.

Нет принудительного NCC для неноминированных или capped pairs. Seed phase0/137
и короткие takes остаются в матрице. Corpus/wrapper не менялся после outcomes.
Для codec truth относится к constructed destination после priming removal;
encoded PTS и неподтверждённый хвост не приравниваются к parent coordinates.
Детальные eligible/nominated/retained counts и cap-hit flags каждого source
сохранены в results/case-summary.json; все позиции seeds/pairs — в raw JSONL.

## 5. Challenges и оставшиеся пробелы

| Класс | Cases | Global rho median / p95 / max | Undefined pairs | Candidate cap / seed cap |
|---|---|---|---|---|
| CHALLENGE_BACKGROUND_AMBIENCE_PROXY | 4 | 0.28536 / 0.367031 / 0.367031 | 0 | 4 / 0 |
| CHALLENGE_BACKGROUND_MUSIC_PROXY | 4 | 0.828014 / 0.969701 / 0.969701 | 0 | 4 / 0 |
| CHALLENGE_BACKGROUND_TONE | 4 | 0.855961 / 0.977846 / 0.977846 | 0 | 4 / 0 |
| CHALLENGE_CAP | 4 | 1 / 1 / 1 | 0 | 4 / 4 |
| CHALLENGE_CONSTANT | 1 | — / — / — | 64 | 1 / 0 |
| CHALLENGE_PERIODIC_TONE | 1 | 1 / 1 / 1 | 0 | 1 / 0 |
| CHALLENGE_SHORT | 4 | — / — / — | 0 | 0 / 0 |
| CHALLENGE_SILENCE | 1 | — / — / — | 0 | 0 / 0 |
| CHALLENGE_WORD_LOOP_PROXY | 4 | 1 / 1 / 1 | 0 | 4 / 0 |

Общий generated tone на независимых takes даёт cross max rho=0.965409
(global max=0.977846); chord/music proxy — cross max=0.952054
(global max=0.969701). Таким образом, benign периодический фон создаёт высокую
correspondence и перекрывает часть наблюдаемого диапазона noisy copies.
Разделение clean read speech не переносится автоматически на такие условия.
Это существенный confound, даже без выбора какого-либо decision threshold.

Word-loop, background chord/music и ambience — явно generated proxies из
source fragments или сигналов. Они не названы натуральными repeated words,
дыханием, TV/music recordings или room recordings. Silence/constant и tone
проверяют undefined/periodic cases, а 60s tiled speech — cap competition.
Не представлены размеченные natural fillers/«да»/«нет», breath, cough/laugh,
deliberate imitation, настоящий background TV/music и разнообразные codec
histories. Они требуют targeted research; ограничение не устраняется
переименованием synthetic proxy. Benign periodic correspondence не Finding.

## 6. Проверки и ресурсы

Existing focused tests: **43 passed,563 deselected in5.08s**, exit0.
Frozen external oracles: **7 groups PASS**. Selected exact repeats:
**8 cases ×3 PASS**: семь предобъявленных (high copy, low/highest
cross natural, codec, gain, cap-hit, silence) и дополнительная replication
проверка highest global natural `NATURAL_RE_SPEECH__S04_P073_T1__S04_P073_T2` при финальном review.
Дополнительная проверка не меняла исходные measurements, corpus или ARC;
её план и raw repeats сохранены отдельно. Hashes numerical outputs совпали,
timing/RSS исключены.
Это повторяемость одного Python/NumPy/FFmpeg/CPU environment, не всех платформ.
Полные команды, hashes и runtime/platform metadata сохранены во внешних logs.

| Speaker | Preprocessing median / max s | Coarse median / max s | NCC median / max s | ARC median / max s | Observed working set max bytes | Lifetime peak max bytes | Artifacts max bytes |
|---|---|---|---|---|---|---|---|
| S01 | 0.535235 / 2.12515 | 0.0113893 / 0.118853 | 1.4202 / 1.59498 | 1.43197 / 1.62463 | 98242560 | 119291904 | 31582152 |
| S02 | 0.635514 / 2.15059 | 0.0157928 / 0.122529 | 1.48295 / 1.58883 | 1.4969 / 1.62315 | 98336768 | 119291904 | 31582152 |
| S03 | 0.635863 / 2.12727 | 0.0158651 / 0.122681 | 1.48131 / 1.83551 | 1.49886 / 1.86099 | 98451456 | 119681024 | 31582152 |
| S04 | 0.616757 / 2.11045 | 0.0151999 / 0.110149 | 1.51449 / 1.6894 | 1.52959 / 1.71454 | 98537472 | 119681024 | 31582152 |

ARC max wall=1.86099s; observed process-lifetime peak=
119681024 bytes. Working set — наблюдение
процесса до/после case; lifetime peak не является изолированным per-source peak.
Reader/hash I/O входит в timings. Original и codec preparation сохранены
отдельно; таблица отражает подготовку конечного fixture и ARC phase.
FFmpeg child RSS не измерен; hard/native/concurrent production bounds не заявлены.
Всего unique descriptor/channel comparisons: 743032;
дополнительные ranking evaluations: 125393;
NCC verifications: 44823; lag/channel evaluations:
353150887. Все измерения mono; канал не считается
дополнительной независимой единицей. Artifact bytes описывают numeric outputs,
не disk budget всего corpus/review workspace.

## 7. Outcome, owner gate и review

Рекомендация **NEEDS_TARGETED_RESEARCH**: получена ограниченная descriptive
проверка, но четыре speakers, read-speech domain, два takes и неполные реальные
challenges недостаточны для заявленной широкой voice-message validation.
Высокая correspondence при общем periodic background дополнительно требует
целевого исследования applicability и confounds, без подбора ARC на этих данных.
Gate принятия результатов/ограничений закрыт решением владельца в §8.
Выбор расширения rights-established естественного корпуса (исследовательский
ориентир20 speakers×5 phrases×3 независимых takes), реальных voice messages/
challenges и отдельный frozen plan остаются будущей работой.
Calibration автоматически не разрешена даже при observed gap.

ATD-LOCAL-1 и ASC-TV-1: **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**,
оба обязательства сохранены. Macro3 **IN_PROGRESS**; его closure rule не меняется.
Production thresholds, method acceptance, analyzer implementation/registration,
Findings, severity, risk/correlation и public contract changes отсутствуют.

Research root: `C:\Users\Vanur\Desktop\FakeDetector-Work\research\M3-R3A-arc-speech\`.
Predeclaration/V1 archive, corpus/speaker manifests, provider/license snapshots,
frozen script hashes, originals/fixtures, raw measurements/repeats, summaries,
oracles и logs остаются вне Git. Голоса в репозиторий не добавлены.
Review root: `C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-R3A-arc-speech\`.
complete.diff включает intended untracked report. Остальные материалы:
review-summary, git-status, measurement-summary, speaker-summary,
resource-summary, provenance-summary и split-summary.
Проверяются diff --check, фактический complete diff и итоговый status.
Full quality barrier, strict certification и Git mutations не выполняются.
Agent self-report не owner acceptance; staging/commit остаются владельцу.

## 8. OWNER ACCEPTANCE — 2026-09-27

Владелец явно принял M3-R3A: **DONE / OWNER ACCEPTED RESEARCH RESULT**.
ARC-NCC-1 остаётся **NEEDS_TARGETED_RESEARCH**. Это принятие исследовательского
результата и его ограничений, не production method acceptance.

Принята следующая интерпретация:

1. Ограниченный clean-speech pilot поддерживает рабочую гипотезу, что
   независимо повторно произнесённая тем же человеком та же фраза существенно
   менее похожа, чем скопированные физические waveform segments при frozen ARC v2.
2. Поддержка ограничена четырьмя speakers, controlled read speech и только
   двумя natural takes на фразу. Корпус не представляет популяцию реальных
   voice messages; большая выборка производных fixtures этого не меняет.
3. Наблюдаемое clean-speech разделение не является production threshold,
   FPR claim, sensitivity claim или calibration result.
4. Основной нерешённый confound — **PERIODIC / REPEATED BACKGROUND**.
   Generated tone/music-like фон может давать очень высокую correspondence,
   включая значения, перекрывающие наблюдения copied waveform (§5).
5. Следующий исследовательский приоритет — более широкая natural voice-message /
   speech validation с реалистичным покрытием background confounds. План M3-R3B,
   включая вопросы полезности clean-speech gap и low-applicability при
   доминирующем фоне без изменения ARC v2, зафиксирован в
   [ROADMAP](../ROADMAP.md#m3-r3a--done--owner-accepted-research-result).
   Следующее исследование ещё не выполнено; production rule не проектируется.

Frozen ARC v2 неизменён: formula, compensated accumulation, normalization,
descriptor, NCC, guard, search bounds, caps, support, ties и channel behavior.
Tuning не разрешён. Все измерения, история подготовки и ограничения §§1–6
сохранены без изменений; новых экспериментов при записи acceptance нет.

**Production calibration NOT AUTHORIZED**; production threshold отсутствует.
Production method acceptance, analyzer implementation/registration и Finding
отсутствуют; risk/correlation и public contracts не изменены.
ATD-LOCAL-1 и ASC-TV-1 сохраняют
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**; оба обязательства
не разрешены. Macro 3 остаётся **IN_PROGRESS**.

Исследовательский результат принят владельцем; запись решения и обновлённый
полный intended diff проверены владельцем; staging/commit остаются владельцу.
Тесты, эксперименты, full quality barrier и certification в этой acceptance-задаче
не запускались. Git mutations не выполнялись; staging/commit остаются владельцу.
