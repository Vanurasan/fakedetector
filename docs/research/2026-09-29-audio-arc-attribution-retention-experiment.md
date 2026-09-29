# M3-R3D-E — ARC attribution и retention diversification

Дата: **2026-09-29**. **DONE / OWNER ACCEPTED RESEARCH RESULT**.
Owner acceptance: **2026-09-29**, включая documented protocol correction (§8).
Baseline: `f70c9520842a48bb35ac836b2abc849a044609c0`, ветка
`feat/stage12-macro3-audio-analyzer-expansion-wave1`; начало clean.
Основание: [принятый design result M3-R3D-P](2026-09-29-audio-arc-applicability-retrieval-design.md#9-owner-acceptance--2026-09-29).
ARC-NCC-1 сохраняет **NEEDS_TARGETED_RESEARCH**, Macro 3 — **IN_PROGRESS**.

## 1. Результат и границы вывода

**DIVERSIFICATION_PROMISING_OWNER_GATE_FOR_FUTURE_ARC_CHANGE**.
Лучшая исследовательская policy по предобъявленному порядку выбора — **R1**.
R1 и R3 вернули по две потерянные nominations известной speech-copy, тогда как
R0 и R2 не вернули ни одной. Однако две nominations сходятся к **одной** паре
интервалов; refined offset отличается от физической truth на **311 samples**.
Это полезное свидетельство восстановления truth-associated correspondence
в существующем refinement bound, **не** восстановление exact physical offset.
Ни одна policy не решила semantic attribution или не стала production-методом.

Во всех четырёх policies сохранены retained/localized/exact cases **96/96**
обычных controlled copies. При этом R1/R3 оставляют **673** truth pairs вместо
**1485** у R0/R2: отсутствие case-level regression не означает сохранения всех
перекрывающихся измерений или доказанной population sensitivity.
Результат attribution: **ATTRIBUTION_EXISTING_OUTPUTS_PARTIAL**.
Простая проверенная signature для automatic foreground/background semantics
не установлена. Высокие music/background/periodic maxima остаются.

ARC v2 не изменён. R1–R3 — внешние **EXPERIMENTAL_RETENTION_POLICY**, не ARC v3.
ARC v3, production tuning/calibration, thresholds, analyzer, Finding,
risk/correlation и public contract changes не разрешены и не выполнены.

## 2. Преддекларация, воспроизведение и история исполнения

Все scripts, inputs и outputs находятся во внешнем
`FakeDetector-Work/research/M3-R3D-E-arc-attribution-retention/`.
Исходные evidence trees M3-R3C и M3-R3D-arc-applicability не изменялись.
Новых media, preprocessing, dependency или repository executable changes нет.

| Идентичность | SHA-256 |
|---|---|
| Frozen ARC v2 | `04a2d54f0e5bc51c3eacf376cd797b16c178dd6a9740accb626cc77e92bfa625` |
| Исходная преддекларация до любого selector outcome | `9fc6c331140db6683d99b26385f298ba2b88612c3e50da337327d9732fb178f8` |
| Преддекларация с записью исправления validation guard, до полного повторного R1–R3 | `dacc06f254f981a275a6f4e61ae3a552717af21d36760d63908b3135ab710310` |
| Неизменённый selector implementation | `158994c004fcd37de7b9cd854e195c5b8dbc8788fe4d0c06e35e083b231d2da0` |
| Исходный M3-R3C raw.jsonl | `f6239fb234c0d36fb3bcaf41bce4c28ce52c83d982a85de592eb7c362b9febf4` |
| Исходный M3-R3C cases.json | `702a8ff79185bc9fa8d919a2f081b65a613d48f9fe44915a70922b334145ae29` |

`seal.json` содержит также hashes harness, frozen helper/oracle copies,
evaluation code, selector-spec и полного corpus-membership. Исходный seal и
код сохранены в `freeze-history/initial/`; обе версии преддекларации доступны.

**Baseline reproduction — PASS, 184/184 exact canonical numerical hashes.**
Совпали states, seed locations, весь nominated union/order, baseline retained
pairs/order, refined coordinates, NCC/support/channels и остальные sealed
numerical fields. Исключены только timings и memory observations, как в
исходной `arc_v2.numerical`. Допуск для сравнения не применялся.
Использованы sealed **prepared M1 artifacts**; новый FFmpeg decode не запускался.
Три исходных technical resource rejections сохранены как inputs, а не повторно
измерены. Их отсутствие numeric results не подменено нулями.

**Остановка и исправление harness.** После успешного baseline и oracle checks
первый запуск R1 вычислил первый case, но до записи результата остановился:
validation assertion сравнивала `list[tuple]` в памяти с `list[list]` из JSON.
Это ошибка сравнения представлений, не изменение candidate union. Исправлена
ровно эта assertion: обе стороны сравниваются через `json.dumps`. Selector,
grouping, quotas, ordering, features, metrics, corpus и numerics не менялись.
Первый незаписанный case не использован для настройки и не добавлен в counts.
Сохранены traceback `results/stop-experiment.json`, пустой stopped R1 output
и исходный harness. Перед полным R1–R3 записан новый seal.
Это явное отклонение от первоначального запрета менять harness после freeze,
ограниченное serialization validation; владелец явно принял его вместе с
результатом эксперимента **2026-09-29** (§8).
Исходный pre-outcome freeze не заменён утверждением, что исправления не было.

## 3. Corpus, policies и неизменяемые границы

Полный M3-R3C fixed challenge set: **184 fixtures** на policy, **181 processable**
и **3 technical resource rejections**, всего **736 case/policy rows** без repeats.
Изначальная база — 22 real recordings: 8 speech recordings / 7 speakers,
3 music и 11 background groups; generated cases имеют отдельную synthetic
lineage. Производные и pairs зависимы от parent/source; это не 736 независимых
наблюдений и не новый same-speaker natural re-speech корпус. M3-R3B broad
validation остаётся отложенной до calibration / production-readiness research.

| Policy | Точное правило retained selection |
|---|---|
| R0 — BASELINE_RANK64 | Первые min(64,N) исходного ranked union |
| R1 — EXACT_OFFSET_ROUND_ROBIN | Groups по exact integer `absolute_B - absolute_A` |
| R2 — WINDOW_PAIR_ROUND_ROBIN | Groups по exact ordered `(window_A, window_B)` |
| R3 — WINDOW_OFFSET_ROUND_ROBIN | Groups по exact `(window_A, window_B, coarse_offset)` |

Для R1–R3 порядок groups — original global rank первого элемента; внутри
groups исходный rank order. Последовательные passes берут по одному элементу
из каждой непустой group до64 или исчерпания. Нет offset tolerance, merging,
дополнительных quotas, oracle masks или distance cutoffs. Политики не менялись
после outcomes, пятой policy нет. Selector получает только candidates/seeds.

Экспериментальный harness заменяет ровно точку `candidates[:64]` в копии
frozen source на selection hook. Candidate generation, descriptor/distance,
per-seed/per-channel top4 и union/ranking не меняются; полный ordered union
и seeds проверены против R0 для каждого case/policy. Downstream refinement/NCC
исполняет неизменённый код. Original global ranks записаны отдельно от
`pair.rank`, отражающего порядок выполнения NCC выбранных пар.

Сохранены seed cap256, candidate/NCC cap64, δ±4096, compensated float64,
guard, overlap/support/ties/channels, M1 precision windows, native rate/channels,
30 s deadline и FFT Q≤131072. Нет full-duration fallback, нового preprocessing
или дополнительных кандидатов вне union. Artifact coverage не расширена.

## 4. Truth retention и localization

Eligible geometry повторяет M3-R3C: полный source2L в truth mask, destination
при truth offset внутри destination mask/M1 window, δ в ±4096, nonoverlap.
Truth consulted только **после selection**. Обе метрики публикуются отдельно:

- **EXACT_PHYSICAL_OFFSET:** refined offset равен physical truth offset.
- **WITHIN_EXISTING_REFINEMENT_BOUND:** absolute error ≤4096, без нового tolerance.

Дополнительная предобъявленная `localized` требует eligible measured pair,
ошибку≤4096, полные refined a/b intervals внутри truth masks и structural
support. Structural support означает defined values, не similarity threshold.

| Policy | Retained truth cases /96 | Localized /96 | Exact physical offset /96 | Within ±4096 /96 | Retained truth pairs |
|---|---:|---:|---:|---:|---:|
| R0 | 96 | 96 | 96 | 96 | 1485 |
| R1 | 96 | 96 | 96 | 96 | 673 |
| R2 | 96 | 96 | 96 | 96 | 1485 |
| R3 | 96 | 96 | 96 | 96 | 673 |

Case-level regression lists для R1/R2/R3 пусты по всем четырём метрикам.
R1/R3 сократили число retained truth pairs на **812**, сохранив хотя бы одну
exact supported пару каждого case; потеря части возвращаемых correspondences
не подменяется утверждением об улучшении recall. Для обычных
fixtures grouping по windows не меняет результат R2, тогда как offsets
перераспределяют budget. Полные per-case ranks, truth counts, errors/support
находятся в `results/evaluated-cases.json` и `known-copy-regression.md`.

### Cap stress: truth offset=2510832 samples

У каждой policy 21 eligible и 20 nominated truth pairs, тот же union из677.

| Policy | Retained true nominations | Localized | Exact offset | Within ±4096 | Полностью background-only selected pairs /64 |
|---|---:|---:|---:|---:|---:|
| R0 | 0 | 0 | 0 | 0 | 64 |
| R1 | 2 | 2 | 0 | 2 | 10 |
| R2 | 0 | 0 | 0 | 0 | 62 |
| R3 | 2 | 2 | 0 | 2 | 17 |

R1/R3 сохраняют **original ranks518 и524**, seed pairs **(6,252)** и **(6,251)**,
coarse offsets2512200 и2508104. Обе сходятся к a=[24576,114688),
b=[2535097,2625209), refined offset=**2510521**, error=**311 samples**.
Это **одна** уникальная refined пара, не два независимых совпадения.
Rho: **0.8954785150443949 / 0.8954785150443947**; support в обеих парах
**[0.677881347437162, 0.8405035433182501]**, structural support=true,
exact_decoded=false. NCC для этих nominations теперь действительно выполнен.

Сам факт связи с truth установлен по fixture construction; смешанная waveform
содержит общий tone, поэтому полученная correspondence не доказывает чистый
foreground вклад. При 44100 Hz ошибка311 — около7.05 ms. Не выбирался новый
допуск и не заявляется exact-copy localization для этого stress case.

| Policy | Unique coarse offsets | Top coarse share | Unique refined offsets | Top refined share | Unique window pairs | Seed endpoints |
|---|---:|---:|---:|---:|---:|---:|
| R0 | 2 | 59/64 | 7 | 41/64 | 3 | 113 |
| R1 | 64 | 1/64 | 58 | 2/64 | 6 | 54 |
| R2 | 3 | 31/64 | 8 | 28/64 | 6 | 96 |
| R3 | 57 | 3/64 | 55 | 3/64 | 6 | 57 |

R2 показывает отрицательный результат: охват всех шести window-pair groups
и меньший overlap не спасают truth, когда внутри groups лидирует periodic
structure. R1/R3 представляют редкие exact offsets и тем самым пропускают
две truth nominations ниже прежнего cap. **Global max rho=1 у всех policies**;
retention diversity не устраняет benign periodic correspondence.

## 5. Attribution: ровно17 features, результат PARTIAL

Features сгенерированы без case/source/truth labels, затем labels присоединены
для evaluation. Определения зафиксированы в преддекларации: retained count,
cap flag, unique/top-share coarse offsets, unique/top-share refined offsets,
unique/top-share window pairs, pair overlap, unique seed endpoints,
defined structural support fraction, exact_decoded fraction, channel-offset
disagreement fraction, max/median retained rho, max/median support-min.
Это описательная панель, без classifier, score, learned combination или cutoff.

Rho агрегируется сначала максимумом информативных channels внутри pair.
Support-min — минимум first rho и двух support rhos одного defined channel,
затем максимум channels для pair; case max/median берутся по таким pair values.
Case max_rho и max_support_min могут относиться к **разным** парам/каналам.
Overlap — положительное пересечение одновременно a и b full2L intervals среди
unordered measured pair-of-pairs. Undefined shares/continuous values остаются
undefined; counts=0 допустимы для выполненного пустого retrieval, но недоступные
features resource-rejection cases не подменяются нулём.

Evaluation strata: A copies96; B shared background18; C distinct background18;
D generated periodic4; E real mechanical/periodic5; F music11; G speech8;
H mixed/ambiguous24. Они не production labels. В D нет real source IDs,
но есть одна synthetic lineage; это не четыре независимых источника.
Для F rho определён в9/11, G —4/8, H —21/24. Все cases сохранены.
Полные min/median/max/defined counts **всех17 features для каждой группы и
policy** находятся в `attribution-summary.md`; полные panels — во внешнем JSON.

Некоторые baseline R0 пересечения диапазонов:

| Feature | Known copies | Generated periodic | Music | Shared background |
|---|---|---|---|---|
| max_rho min…max | 0.994111699…1 | 1…1 | 0.144703262…0.996936217 | 0.162894255…0.945471763 |
| top coarse share min…max | 0.140625…0.666667 | 0.28125…0.625 | 0.109375…0.34375 | 0.285714…0.285714 |
| pair overlap min…max | 0.674603…1 | 0.681548…0.816468 | 0.638889…1 | 1…1 |
| structural support fraction | 1 | 0.3125…1 | 1 | 1 |
| exact_decoded fraction | 0…0.703125 | 0 | 0 | 0 |
| max support-min min…max | 0.972428470…1 | 1…1 | 0.027636965…0.991262391 | 0.001191222…0.893562332 |

Таким образом, high rho/support, concentration и overlap не дают надёжного
одиночного forensic объяснения. Exact decoded equality полезна как физический
факт, но её отсутствие не исключает gain/codec/noise copy; её наличие само по
себе не определяет foreground роль. Channel agreement также не semantic truth.
Из этих пересечений не следует математическая невозможность любой будущей
совместной signature; **проверенная простая signature здесь не установлена**.

### Обязательные контрпримеры и secondary challenges

| Case / max_rho | R0 | R1 | R2 | R3 |
|---|---:|---:|---:|---:|
| Vibe Ace excerpt2 | 0.996936217 | 0.994345849 | 0.996936217 | 0.994345849 |
| Washing machine | 0.906703482 | 0.906703482 | 0.906703482 | 0.906703482 |
| Shared speech background, -10 dB | 0.945471763 | 0.945471763 | 0.945471763 | 0.945471763 |
| Shared trumpet music, -10 dB | 0.940959458 | 0.940959458 | 0.940959458 | 0.940959458 |
| Distinct speech-background segments counterpart | 0.054256856 | 0.054256856 | 0.054256856 | 0.054256856 |
| Distinct trumpet segments counterpart | 0.056211030 | 0.056211030 | 0.056211030 | 0.056211030 |
| Tone / hum / beep / rhythm, каждый | 1 | 1 | 1 | 1 |
| Original Libri5639 | 0.350497998 | 0.209768187 | 0.244144374 | 0.244144374 |

Vibe Ace продолжает совпадать с support: max_support_min=0.991262391 у R0/R2
и0.990968015 у R1/R3. Это легитимная музыка без нашей copy-insertion, но без
доказанной истории студийного производства. Washing machine также сохраняет
max_support_min=0.893054786. Diversification часто заменяет одни benign pairs
другими, не решая interpretation. Shared/distinct overlays при union≤64
сохраняют все пары, меняя лишь порядок; показатели закономерно не изменились.

Для beep max rho и max_support_min равны1 у всех, но доля defined structural
support **0.3125 у R0/R2 и0.28125 у R1/R3**: больше выбранных пар имеют undefined
support. Это отдельная secondary потеря поддержки, не скрытая за неизменным max.
Silence и short-copy остаются abstentions; full Vibe Ace, room и Sweet Waltz
сохраняют resource rejection. Их undefined не означают доказательство отсутствия
копирования. Original speech включает только четыре cases с defined rho.

## 6. Ресурсы, numerics и determinism

| Policy | Total median / max, s | Grouping median / max, µs | Selector Python peak, bytes | Max current WS / lifetime peak WS, bytes |
|---|---|---|---:|---|
| R0 | 0.514737 / 2.797568 | не инструментирован отдельно | 512 | 91709440 / 105054208 |
| R1 | 0.512572 / 2.741952 | 11.900 / 113.700 | 36536 | 91860992 / 105267200 |
| R2 | 0.533135 / 2.921704 | 13.300 / 214.100 | 7664 | 94212096 / 107880448 |
| R3 | 0.493057 / 2.713505 | 13.600 / 217.800 | 38824 | 98017280 / 110653440 |

Grouping time включён в coarse/total. Allocation peak — отдельный tracemalloc
replay тех же selectors без NCC; target≤32MiB соблюдён. Native RSS не равен
Python allocations. Working set измерен одним Windows API; R0 выполнен отдельным
process, R1–R3 последовательно, поэтому allocator/history мешают причинному
сравнению policy RSS. Lifetime peaks не per-case peaks; speedup не заявляется.
Historical preprocessing time не представлен новым measurement. Полные
per-case coarse/NCC time, evaluations, artifacts bytes, current/peak WS,
selected ranks, diversity и cap activity сохранены во внешних results.

Deadline30s не превышен, seed≤256, retained/NCC≤64, union/order неизменны.
**Numerical stability — PASS**, guard failures отсутствуют; историческая
roundoff handling frozen v2 не менялась. **7 oracle groups PASS**, независимый
scalar/FFT comparison на10lags: max error3.9898639947466563e-17.
**Determinism — PASS:** 8 заданных cases ×4policies ×3executions; selected
identities/order и canonical numerical hashes идентичны. Первый полный run
входит в тройку, выполнено64 дополнительных repeats; они не увеличивают corpus.

## 7. Следующий owner gate и review

R1 выбран по predeclared правилу: useful bounded localization, отсутствие
ordinary case losses; при равных результатах с R3 — меньший policy index.
Это не оптимизация selector после outcomes. R2 гипотезу rescue не подтвердил.
R1/R3 дают ограниченное основание изучать будущую замену только retained-budget
selection среди неизменного union. Рекомендация **PROMISING** относится именно
к этому bounded исследовательскому свидетельству, а не к exact offset в stress,
общей forensic применимости или готовности к production implementation.

Результат, включая protocol correction и неточную cap-stress localization,
принят владельцем **2026-09-29** (§8); gate принятия M3-R3D-E закрыт.
Следующий owner gate — зафиксировать scope **M3-R3D-F — R1 Flooding Confirmation
Study**, пока **PLANNED / OWNER SCOPE NOT YET FROZEN**. Минимальная conceptual
delta возможного будущего изменения retention — exact-offset
round-robin на уже nominated union при прежнем budget. Никакой ARC v3 version,
schema или реализации не назначено. Automatic applicability method остаётся
отдельным нерешённым вопросом; tuning/calibration не разрешены.

ATD-LOCAL-1 и ASC-TV-1 сохраняют **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**,
оба обязательства нерешены. Macro 3 **IN_PROGRESS**; принятие исследовательского
результата записано по явному решению владельца. Production метод/анализатор/
Finding не принят и не реализован.

Review: `FakeDetector-Work/reviews/M3-R3D-E-arc-attribution-retention/`.
Предоставлены predeclaration/hash, selector-spec, baseline reproduction,
attribution/retention, known-copy regression, cap stress, challenge, determinism,
resource, measurement summaries, review-summary, complete.diff и git-status.
Full intended diff включает новый untracked report. `git diff --check` и итоговый
status проверены; source evidence hashes и freeze проверены повторно.
Full quality barrier и strict certification не запускались. Git mutations
не выполнялись, staging/commit остаются владельцу.

## 8. OWNER ACCEPTANCE — 2026-09-29

Владелец явно принял **M3-R3D-E: DONE / OWNER ACCEPTED RESEARCH RESULT**.
Приняты outcome **DIVERSIFICATION_PROMISING_OWNER_GATE_FOR_FUTURE_ARC_CHANGE**,
лучшая исследовательская policy **R1 / EXACT_OFFSET_ROUND_ROBIN** и attribution
outcome **ATTRIBUTION_EXISTING_OUTPUTS_PARTIAL**. Gate принятия результата закрыт.

**Protocol correction принята явно, история сохранена.** Исходный pre-outcome
freeze сохранён; baseline reproduction успешно завершился. Первый R1 execution
остановился до записи экспериментального результата из-за сравнения in-memory
`list[tuple]` с JSON `list[list]`. Исправлена только serialization/comparison
validation. Selector implementation, grouping, quotas, ordering, corpus,
features и metrics не менялись; outcome-driven tuning не выполнялся.
Original failure, traceback и freeze history остаются сохранёнными. Acceptance
не означает, что post-freeze harness correction не было; описание §2 сохраняется.

**Количественные результаты приняты без усиления выводов.** Frozen-v2 baseline
reproduction — **PASS**. Каждая R0/R1/R2/R3 имеет **96/96 retained, 96/96 localized,
96/96 exact physical offset** ordinary controlled copies. Retained truth pairs:
**1485 у R0/R2**, **673 у R1/R3**; это не improved recall или sensitivity.
В cap stress R0/R2 retained truth=0, R1/R3 сохраняют по2 truth-associated
nominations, сходящиеся к **одной** refined паре: offset=2510521 samples при
physical truth=2510832, error=311 samples. Ошибка внутри существующего ±4096,
structural support определён, но **exact physical offset не восстановлен**.
Две nominations не являются двумя независимыми detections.

R1 даёт promising bounded evidence, что exact-offset diversity прежнего budget
может вернуть truth-associated correspondence, потерянную global rank64 при
periodic flooding. Поддержка ограничена одной constructed cap-stress geometry;
retained truth pair multiplicity сильно уменьшилась. Benign periodic/music/
background high correspondence сохраняется; automatic semantic attribution
не решена. **R1 — исследовательское направление, не принятая ARC implementation
или production behavior.** Все измерения и limitations §§3–6 сохранены.

Следующий ARC шаг — **M3-R3D-F — R1 Flooding Confirmation Study**,
**PLANNED / OWNER SCOPE NOT YET FROZEN**: подтвердить R1 на нескольких заранее
объявленных periodic/background flooding geometries до любого решения о
будущей retention implementation. В этой задаче он не выполняется, подробные
fixtures/selectors не определены; следующий gate — owner scope freeze.

Новое решение сохраняет **M3H-A01 — ARC Companion Applicability / Context
Qualification** только как **DEFERRED RESEARCH HYPOTHESIS**. Возможный companion
квалифицировал бы контекст ARC-matched windows без самостоятельного verdict о
манипуляции, с допустимым **AMBIGUOUS / UNRESOLVED**. Source separation не
предполагается; новые capabilities требуют **STOP / SEPARATE OWNER GATE**.
Полное описание и границы — в [METHODS](../METHODS.md#audio-m3h-a01), статус и
будущий hygiene audit — в [ROADMAP](../ROADMAP.md#audio-m3r3de). Гипотеза не
является активной задачей, принятым методом или новым public result schema.

ARC-NCC-1 — **NEEDS_TARGETED_RESEARCH**, ARC v2 **FROZEN**; ARC v3 implementation
и production tuning/calibration **NOT AUTHORIZED**, threshold **NONE**.
Production method не принят, analyzer не реализован, Finding не добавлен.
Source separation, второй analyzer, speech/music detector, новые features,
classifier/score/thresholds, schemas/correlation changes, dependencies и media
acquisition не разрешены. ATD/ASC остаются **NEEDS_TARGETED_RESEARCH / REQUIRED
CARRY-FORWARD**, оба обязательства нерешены; Macro 3 **IN_PROGRESS**.

Эта acceptance-задача изменила только документацию. Новые tests/experiments,
quality barrier, certification и hygiene audit не выполнялись. Staging/commit
остаются владельцу; Git mutations не выполнялись.
