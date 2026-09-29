# M3-R3D-F — R1 flooding confirmation

Дата: **2026-09-29**. **DONE / OWNER ACCEPTED RESEARCH RESULT**.
Owner acceptance: **2026-09-29**, решение и disposition записаны в §8.
Baseline `4a528615e6a814aaa1476e92bfae509d5eeca5b5`, ветка
`feat/stage12-macro3-audio-analyzer-expansion-wave1`; clean start подтверждён.
Основание — принятое [M3-R3D-E](2026-09-29-audio-arc-attribution-retention-experiment.md)
и отдельное разрешение владельца на этот узкий confirmation scope.
ARC-NCC-1 — **NEEDS_TARGETED_RESEARCH**, Macro 3 — **IN_PROGRESS**.

## 1. Вывод

**R1_FLOODING_CONFIRMATION_MIXED**.
Все **8/8** новых fixtures дали **EFFECTIVE_FLOODING**: геометрически допустимая
speech-copy была номинирована, но полностью потеряна R0 при global rank → cap64.
Неизменённый R1 восстановил localized truth-associated correspondence в **5/8**,
с rescue хотя бы одного case в каждом из четырёх background families.
Для первого сочетания source/geometry rescue получен во всех A/B/C/D, для второго —
только D. В трёх оставшихся случаях R1 также не сохранил ни одной true nomination.
Таким образом, эффект не ограничен прежним 250 Hz контролем, но устойчивое
восстановление во всех проверенных placements/backgrounds **не подтверждено**.

R0: exact **0/8**, within existing ±4096 **0/8**. R1: exact **2/8**, within bound
и localized **5/8**. Обычные controlled copies сохранили **96/96 retained,
96/96 localized, 96/96 exact** у обеих policies; truth pairs — **1485 / 673**.
Сокращение pair multiplicity не скрыто за сохранением case counts и не означает
доказанную population sensitivity. Production acceptance или ARC v3 не разрешены.

## 2. Freeze, identities и воспроизведение

До любых новых R0/R1 outcomes созданы восемь fixtures, штатные M1 artifacts,
проверены source hashes, syntax и допустимая geometry; ARC тогда не запускался.
Преддекларация фиксирует recipes, coordinates, amplitudes, sources, implementations,
metrics, интерпретацию, порядок контролей/repeats и resource protocol.

| Объект | SHA-256 |
|---|---|
| Преддекларация | `62f6c280cb2c8eeab4f2e42dd518720560cc9dbd70c493806ab2dd132995424e` |
| Frozen ARC v2 | `04a2d54f0e5bc51c3eacf376cd797b16c178dd6a9740accb626cc77e92bfa625` |
| Неизменённый R0/R1 selector module из E | `158994c004fcd37de7b9cd854e195c5b8dbc8788fe4d0c06e35e083b231d2da0` |
| Confirmation harness | `bec84ae7d2981ef09f04a382f59d899eccf14dc24cb4e3dfe785de15ddba7269` |

Freeze UTC: `2026-09-29T14:34:02.345832+00:00`; start timestamp и hash записаны
до oracle/measurement execution. `seal.json` включает 446 identities:
444 implementation/input/source/artifact identities, их manifest и преддекларацию.
Fixtures, amplitudes, implementation и criteria после freeze не менялись.
Post-outcome summary code только читает результаты, не входит в измеритель.

R0 — canonical ranked top64. R1 — прежний **EXACT_OFFSET_ROUND_ROBIN**:
exact integer coarse-offset groups, порядок groups по первому global rank,
внутри исходный rank order, по одному элементу за проход до64.
Byte-identical selector module содержит исторические R2/R3 branches, но они
**не исполнялись**. Новых selectors/R1a/R1b нет. Прежний единственный selection
hook переиспользован без изменения. Seeds и полный ordered nominated union
совпали для R0/R1 каждого case. Truth/masks не поступают в selector.

Descriptor, distances, seed generation/cap256, top4, union, cap64, compensated
float64, normalization, NCC, numerical guard, δ±4096, overlap/support/ties/channels,
M1 precision windows и preprocessing сохранены. Унаследованная roundoff handling
frozen v2 не переписана; нового clamping или расширения bounds нет.

## 3. Источники, восемь fixtures и две геометрии

Повторно использованы только M3-R3C media; acquisition не выполнялся.
Provenance и ограничения прав наследуются из
[REFERENCES / M3-R3C](../REFERENCES.md#audio-m3r3c-sources): LaMIT и ESC-50,
включая individual Sampling+ notice washing-machine source. Это внешнее локальное
дипломное исследование; distribution media и production dataset не утверждаются.
REFERENCES не менялся, новых источников/библиотек нет.

По lexical order выбраны первые две speech recordings с native mono44100 и
первым M1 window не короче135168 samples. Это **две записи одного speaker S01**,
не два независимых speakers. Выбор не использовал новые ARC outcomes.

| Source | SHA-256 | Роль |
|---|---|---|
| lamit-S01_P001_T1 | `a92614218f608b8e80a050fe639a902e74d44322f3ab248758d2302721cc92d4` | Foreground geometry1 |
| lamit-S01_P005_T1 | `37d02fc38ddf77b78b1fa86767255da621d4e558667d9cda08580e643e18636c` | Foreground geometry2 |
| esc-washing_machine | `1b4210c50a01cabab07065a112463fad4f82de60385ef9aaf6316afe7d4b976c` | Real mechanical loop D |

Все новые fixtures — mono44100, 60s, N=2646000; L=45056. Foreground — первые
3L=135168 samples source, gain1; integer PCM представлен float64 /32768.
Фон непрерывен, foreground добавлен в source и destination masks, без clipping,
peak normalization, fades или resampling. Truth относится к copied foreground,
не к равенству всей смеси. Background не зависит от selector.

Существующая валидная M1 geometry: [0,441000), [1102500,1543500),
[2205000,2646000); фактические windows новых artifacts совпали с ней.

| Geometry | Правило placement | Source mask | Destination mask | Physical offset | Eligible seed pairs |
|---|---|---|---|---:|---:|
| 1 | first.start+4096 → last.stop−3L−4096 | [4096,139264) | [2506736,2641904) | 2502640 | 22 |
| 2 | middle.start+8192 → last.start+16384 | [1110692,1245860) | [2221384,2356552) | 1110692 | 36 |

Полные foreground masks помещаются в соответствующих precision windows и не
перекрываются. Placement зависит только от window coordinates до outcomes.

| Family | Зафиксированный фон, phase0 при sample0 |
|---|---|
| A — PURE TONE | 0.1 sin(2π·137t), новый137Hz, не прежний250Hz |
| B — HARMONIC HUM | 0.07 sin(2π·60t)+0.03 sin(2π·120t)+0.02 sin(2π·180t) |
| C — PERIODIC BEEP | 800Hz carrier, amplitude0.1; mask(k mod33075 <6615), pulse0.15s / interval0.75s |
| D — REAL MECHANICAL | Все220500 source samples циклически k mod220500, без crossfade; multiplier0.6760737502785742 =0.1/RMS(source), RMS0.1479128570792688 |

Две source/geometry ×четыре backgrounds = ровно8 новых cases. D — constructed
physical loop реального media, не восемь независимых записей среды и не оценка
частоты flooding в population. A/B/C — одна synthetic construction lineage.
Parent/recipe/final-media/prepared-artifact hashes предоставлены в sealed manifest.

## 4. Retrieval и localization новых fixtures

Eligible/nominated truth определяется прежней `evaluate.truth`: full2L в source
mask, truth destination в destination mask/M1 window, coarse nonoverlap и
доступность refinement в±4096. Evaluation выполняется после selection/NCC.
Localized требует error≤4096, обе refined2L intervals внутри truth masks и
defined structural support. Это определённость rho/support, не similarity cutoff.

**EXACT_PHYSICAL_OFFSET** — error0; **WITHIN_EXISTING_REFINEMENT_BOUND** —
error≤4096. Unique refined pairs считаются по двум intervals, не по nominations.
Background-only требует, чтобы оба полных refined intervals не пересекали ни
одну speech mask; частично смешанные пары не названы background-only.

Все cases ниже — **EFFECTIVE_FLOODING**. **NO_EFFECTIVE_FLOODING =0**,
**EARLIER_FAILURE =0**. Случай без эффективного flooding не считался бы rescue;
потеря до nominated union не объявлялась бы retention failure.
В каждой строке R0 retained/localized/exact truth=0; cap hit у обеих policies,
retained/NCC=64. В таблице R1 counts относятся к nominations, не к cases.

| Case | Union | Eligible/nominated | R1 retained/localized/exact | R1 unique refined truth pairs | R1 original ranks | R1 errors, samples |
|---|---:|---|---|---:|---|---|
| 1-A | 632 | 22/22 | 2/2/0 | 1 | 471,480 | 1174,1174 |
| 1-B | 669 | 22/22 | 2/2/2 | 2 | 513,517 | 0,0 |
| 1-C | 666 | 22/18 | 1/1/1 | 1 | 505 | 0 |
| 1-D | 635 | 22/21 | 2/1/0 | 2 | 475,481 | 3246,6797 |
| 2-A | 608 | 36/26 | 0/0/0 | 0 | — | — |
| 2-B | 705 | 36/26 | 0/0/0 | 0 | — | — |
| 2-C | 658 | 36/20 | 0/0/0 | 0 | — | — |
| 2-D | 638 | 36/25 | 1/1/0 | 1 | 260 | 3174 |

| Case / rank | Refined offset | Rho | Два support rhos | Localized |
|---|---:|---:|---|---|
| 1-A /471 и480 | 2501466 | 0.872490258 | 0.671708571,0.836078552 | Да; одна refined пара |
| 1-B /513 | 2502640 | 0.932788194 | 0.953561748,0.934713909 | Да, exact offset |
| 1-B /517 | 2502640 | 0.944182165 | 0.925234420,0.932924959 | Да, exact offset |
| 1-C /505 | 2502640 | 0.581672466 | 0.358252759,0.545901782 | Да, exact offset |
| 1-D /475 | 2505886 | 0.765659279 | 0.816357548,0.814949584 | Да, within bound |
| 1-D /481 | 2495843 | 0.774073690 | 0.791483534,0.801445054 | Нет: error6797 |
| 2-D /260 | 1107518 | 0.716598448 | 0.818702178,0.827006388 | Да, within bound |

Во всех этих retained truth-associated pairs structural support=true,
exact_decoded=false. Exact offset в смеси **не** означает identical decoded
waveform или доказанную speech-only attribution. В1-D более высокий rho дал
неверную локализацию; он не подменяет lower-rho localized pair. Ошибка6797 не
нарушает frozen δ bound: refinement ограничен относительно coarse seed, а
error сравнивается с physical truth offset. Новый tolerance не вводился.

| Case | Background-only pairs R0/R1 | Unique coarse offsets R0/R1 | Top coarse share R0/R1 |
|---|---|---|---|
| 1-A | 61/11 | 2/64 | 60/64,1/64 |
| 1-B | 64/33 | 2/64 | 56/64,1/64 |
| 1-C | 60/17 | 13/64 | 36/64,1/64 |
| 1-D | 53/30 | 2/64 | 35/64,1/64 |
| 2-A | 64/21 | 2/57 | 58/64,2/64 |
| 2-B | 64/41 | 2/64 | 57/64,1/64 |
| 2-C | 63/24 | 13/64 | 27/64,1/64 |
| 2-D | 64/33 | 2/64 | 33/64,1/64 |

Большая offset diversity сама по себе не гарантирует rescue:2-B и2-C имеют
64 разных coarse offsets, но ни одной retained true nomination. Это не новый
selector или автоматическая attribution rule. Source и geometry менялись
вместе, поэтому их причинные эффекты этим дизайном не разделены; установлена
зависимость результата от проверенного сочетания source/placement/background.
Полные per-pair intervals/channels, ranks, timings и undefined counts —
`new-fixture-results.md` и `results/evaluated.json` внешнего bundle.

## 5. Контроли, numerics и determinism

**Original cap-stress reproduction — PASS**: точные canonical hashes R0/R1
совпали с принятыми E outputs. R0 retained truth0; R1 nominations2 →одна refined
пара, offset2510521 при truth2510832, error311, localized2, exact0.
Этот контроль выполнен до новых outcomes, в счёт восьми fixtures не входит.

**96-case no-regression — PASS**, все194 control/policy canonical fingerprints
(97 cases ×2 policies) воспроизведены точно, исключены лишь прежние timing/memory
поля. Использованы sealed M1 artifacts; повторного decode controls не было.

| Policy | Retained /96 | Localized /96 | Exact /96 | Retained truth pairs |
|---|---:|---:|---:|---:|
| R0 | 96 | 96 | 96 | 1485 |
| R1 | 96 | 96 | 96 | 673 |

**Numerical stability — PASS**, guard violations и timeouts отсутствуют.
Неизменённый oracle suite: **7 groups PASS**, включая независимый scalar/FFT
на10lags, max error3.9898639947466563e-17. **Determinism — PASS**:
старый cap stress и geometry1 каждого A/B/C/D ×R0/R1 ×3 executions;
identities/order и canonical numerical hashes одинаковы. Основной run входит
в тройку;20 дополнительных repeats не увеличивают corpus. Всего105 cases,
210 основных case/policy rows и20 repeat rows, без oracle fixtures в этих counts.

## 6. Ресурсы и сохранение evidence

| Новые8 fixtures | R0 median/max | R1 median/max |
|---|---|---|
| Coarse, s | 0.097405 /0.100652 | 0.099570 /0.120462 |
| NCC, s | 1.591872 /1.629855 | 1.557150 /1.603530 |
| ARC total, s | 1.690388 /1.725793 | 1.656466 /1.724672 |
| Selector, µs | 1.600 /2.300 | 69.700 /81.100 |

Каждая новая fixture сохранила прежние seed cap256 и64 NCC verifications.
Предобработка новых fixtures:2.101669–2.726189s; каждый numeric artifact set31,582,152bytes,
восемь sets252,657,216bytes. Grouping time входит в coarse/ARC total.
Максимальный R1 selector overhead по всем основным cases194.500µs (старый control).
Отдельный tracemalloc replay: R0 peak512bytes, R1 peak18,544bytes, ниже32MiB.
Максимальный observed current working set154,812,416bytes, lifetime peak166,346,752bytes
по основным runs. Один последовательный process; allocator/history и harness
storage входят в WS, FFmpeg child memory — нет. Это не per-case hard bound,
не certified production RSS и не доказательство speedup.
30s deadline, FFT Q≤131072, search/caps/preprocessing не расширены.

Исходные evidence trees M3-R3C и M3-R3D-E сохранены без записи. Все consumed
source/artifact/implementation hashes повторно проверены; полный inventory
путей/размеров/mtime обоих деревьев сопоставлен до/после. Новые scripts, WAV,
numeric artifacts и raw outputs находятся только во внешнем research workspace.

## 7. Owner gate и материалы review

Исследование завершено без корректировок после outcomes. Владелец принял
**MIXED** результат **2026-09-29** (§8); gate принятия M3-R3D-F закрыт.
Дальнейшее ARC retention development в текущем Macro 3 отложено; следующий
активный topic — ATD-LOCAL-1 carry-forward disposition согласно ROADMAP.
Автоматического перехода к ARC v3, production tuning/calibration или thresholds
нет. ARC-NCC-1 остаётся **NEEDS_TARGETED_RESEARCH**. Ни production method,
ни analyzer/Finding/public contracts/risk/correlation не изменены.

M3H-A01 остаётся **DEFERRED RESEARCH HYPOTHESIS**, не исследовалась;
semantic attribution/source separation не выполнялись. ATD-LOCAL-1 и ASC-TV-1
сохраняют **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**, оба нерешены.
Macro 3 — **IN_PROGRESS**; broad validation M3-R3B остаётся deferred.

Research: `FakeDetector-Work/research/M3-R3D-F-r1-confirmation/`.
Review: `FakeDetector-Work/reviews/M3-R3D-F-r1-confirmation/`.
Предоставлены predeclaration/hash, fixture-manifest, positive-control,
new-fixture-results, known-copy-regression, determinism/resource/measurement
summaries, review-summary, complete.diff и git-status.txt. Полный intended diff
включает этот новый untracked report. `git diff --check` и итоговый status
проверены. Full quality barrier и strict certification не запускались;
executable repo files не менялись, Git mutations не выполнялись.
**AGENT SELF-REPORT IS NOT OWNER ACCEPTANCE**; staging/commit остаются владельцу.

## 8. OWNER ACCEPTANCE — 2026-09-29

Владелец явно принял **M3-R3D-F: DONE / OWNER ACCEPTED RESEARCH RESULT**,
outcome **R1_FLOODING_CONFIRMATION_MIXED**. Gate принятия результата закрыт.
Все экспериментальные measurements, recipes, hashes и limitations §§1–6
сохранены без изменения.

Приняты8 новых fixtures, **8/8 EFFECTIVE_FLOODING**, **5/8 R1 rescues** и
rescue хотя бы одного case в **4/4 families**: pure tone, harmonic hum,
periodic beep и real mechanical background. R0 exact/within±4096 — **0/8 /0/8**;
R1 exact — **2/8**, within existing±4096 — **5/8**. В96 ordinary known-copy cases
у обеих policies сохранены **96/96 retained, 96/96 localized, 96/96 exact**.
Retained truth-pair multiplicity уменьшается **1485 у R0 →673 у R1**;
case-level regression отсутствует, сохранение всех pairs или population
sensitivity не заявляется.

**R1 не является универсальным решением flooding.** Положительное свидетельство
не ограничено прежним250Hz control: полезное truth-associated rescue показано
на нескольких новых fixtures во всех четырёх families. Одновременно **3/8
failures не устранены**, лишь2/8 имеют exact physical localization, pair
multiplicity существенно сокращена. Source/geometry effects не разделены
для широкого обобщения; semantic foreground/background attribution не решена.
R1 остаётся **PROMISING FUTURE RESEARCH DIRECTION**, не принятой ARC implementation.

Принятая disposition ARC-NCC-1: **RESEARCH MEASUREMENT DEMONSTRATED /
PRODUCTION PROMOTION DEFERRED**. Статус **NEEDS_TARGETED_RESEARCH** сохраняется.
Frozen ARC v2 — действующий **FROZEN RESEARCH BASELINE**: demonstrated controlled
copy correspondence, bounded retrieval flooding и partial R1 mitigation не
устанавливают production-safe retention или automatic semantic applicability.
Production promotion отложено до последующих calibration / production-readiness
research. **Дальнейшее ARC retention development в текущем Macro 3 — DEFERRED**,
вне оставшегося пути закрытия Macro; новый ARC experiment не начинается.
ARC v3 **NOT AUTHORIZED**. Tuning R1, R1.1/R1.2, quotas/tolerances, новые flooding
fixtures, расширение search/caps, thresholds и production analyzer не разрешены.

M3H-A01 остаётся **DEFERRED RESEARCH HYPOTHESIS** без работы сейчас;
source separation **NOT AUTHORIZED**, второй analyzer не реализован.
Broad source-level / population validation M3-R3B сохраняет **DEFERRED UNTIL
CALIBRATION / PRODUCTION-READINESS RESEARCH** и не переоткрывается.
Следующий активный topic — **ATD-LOCAL-1 carry-forward disposition**;
ATD и ASC сохраняют **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**,
оба обязательства нерешены. Новых ATD measurements здесь нет.
Macro 3 остаётся **IN_PROGRESS**. Запланированный documentation/instruction
hygiene audit выполняется только будущей closure-stage задачей после ATD/ASC
disposition; **NO ACTION REQUIRED** допустим, сейчас аудит не проводился.

Acceptance-задача меняет только документацию. Tests, новые experiments,
quality barrier и certification не запускались. Запись решения и полный
обновлённый intended diff предоставлены для owner review; это проверка записи
уже принятого результата, не повторное открытие gate его принятия.
Git mutations не выполнялись, staging/commit остаются владельцу.
