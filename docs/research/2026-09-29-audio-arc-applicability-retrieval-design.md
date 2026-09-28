# M3-R3D-P — applicability и конкуренция bounded retrieval ARC

Дата: **2026-09-29**. **DONE / OWNER ACCEPTED DESIGN RESULT**.
Owner acceptance: **2026-09-29**, явное решение записано в §9.
ARC-NCC-1: **NEEDS_TARGETED_RESEARCH**. Это анализ сохранённых свидетельств,
не новый ARC experiment или production acceptance. Разрешён только будущий
внешний research-only experiment в границах §9.

## 1. Вывод и границы свидетельств

Рекомендация: **COMBINED_ATTRIBUTION_AND_DIVERSIFICATION_STUDY_REQUIRED**.
Две проблемы требуют раздельной проверки: семантика уже возвращённого
соответствия и потеря номинированной speech-copy до NCC. Post-attribution может
ограничить интерпретацию retained background pairs, но не восстановить
отброшенные пары. Исследование минимального изменения retention обосновано;
его эффективность ещё не показана. Владелец разрешил внешний bounded research
experiment (§9); изменение ARC v2 или реализация ARC v3 не разрешены.

Использованы только существующие [M3-R3C](2026-09-27-audio-arc-diploma-stress-validation.md)
outputs и fixture truth: 184 cases, из них 181 complete_selected_windows и
3 technical resource rejections. Независимая популяция не расширена:
22 real recordings, включая 8 speech recordings / 7 speaker groups, 3 music
и 11 background groups; generated fixtures имеют отдельную synthetic lineage.
Сотни пар внутри case не являются независимыми источниками.

Принятые M3-R2B numerical corrections, M3-R3A limited clean-speech interpretation,
M3-R3B disposition и M3-R3C результаты не пересмотрены. Broad source-level
validation остаётся отложенной; нового media, preprocessing, dependency или
public result schema нет. Файл REFERENCES не изменён.

Внешняя база: `FakeDetector-Work/research/M3-R3C-arc-stress/`, включая
`results/raw.jsonl`, `fixtures/cases.json`, source manifest, sealed predeclaration,
prepared artifacts и scripts; просмотрен и исходный review bundle. Перед анализом
проверены sealed hashes, совпадение 184 fixture/raw IDs, final-media и prepared
numeric hashes. Зафиксирован fingerprint 1088 файлов исходных research/review
деревьев; после работы проверена их неизменность.

| Идентичность | SHA-256 |
|---|---|
| Frozen `scripts/arc_v2.py` M3-R3C | `04a2d54f0e5bc51c3eacf376cd797b16c178dd6a9740accb626cc77e92bfa625` |
| M3-R3C predeclaration | `7afb533a9b388664362f584472fbf49ece94b1b43c4387e338dd71797461001d` |
| M3-R3C cases.json | `702a8ff79185bc9fa8d919a2f081b65a613d48f9fe44915a70922b334145ae29` |
| Анализируемый raw.jsonl | `f6239fb234c0d36fb3bcaf41bce4c28ce52c83d982a85de592eb7c362b9febf4` |

Воспроизводимый metadata-only анализ сохранён отдельно:
`FakeDetector-Work/research/M3-R3D-arc-applicability/scripts/analyze_stored.py`
и `results/analysis.json` (включает input/script hashes и все 184 case summaries).
Он считает ранги, геометрию и распределения сохранённых пар; не исполняет ARC,
не вычисляет новые descriptors/NCC и не читает waveform для нового измерения.

## 2. Что означает сильное соответствие

Метки ниже — описательные research labels с указанием основания, не
автоматическая классификация, Finding или production applicability rule.
Максимум rho указан по каналу; global maximum и cross-fixture соответствие
нельзя взаимозаменять. Structural support означает определённость rho в первом
L и двух следующих L/2 на одном канале, а не силу поддержки выше порога.

| Описательная категория | Существующее свидетельство | Основание и граница вывода |
|---|---|---|
| FOREGROUND_COPY_SUPPORT | Все 96 обычных exact/gain/codec/noise copy-cases имеют retained truth, minimum localization error 0 samples и structural support | Parent/recipe hashes и source/destination masks устанавливают физическую копию; raw offset/support подтверждают совпадение. Одни rho/offset не доказывают foreground-семантику неизвестной записи |
| BACKGROUND_DOMINATED_SUPPORT | `mix-lamit-S03_P001_T1-shared--10`: cross/global rho 0.945471763; shared trumpet 0.940959458; shared rain 0.907473885 | Из recipe известны разные foreground speakers и один физический background. Контраст уровней и shared/distinct-segment construction поддерживает attribution; численная доля каждого компонента не измерена, смесь не становится чистым background |
| PERIODIC_STRUCTURE_SUPPORT | Все 64 retained cap-stress pairs: rho 1; washing machine maximum 0.906703482 с support 0.898888399 / 0.887722437 | Для stress fixture masks доказывают background-only tone; у washing machine source annotation и повторяемость лишь поддерживают механическую интерпретацию, без изолированного ground truth компонентов |
| MIXED_OR_AMBIGUOUS_SUPPORT | `mix-generated-tone--10`: global 0.939373700, cross-foreground 0.920067424; mixtures при менее доминирующем фоне | Global и cross maxima могут относиться к разным участкам. Из scalar rho нельзя безопасно разделить речь/фон; attribution смешанной пары требует recipe/annotations, а для неизвестного media может оставаться неопределённой |
| NATURAL_CONTENT_REPETITION | `excerpt-vibe-ace-2`: channel 1 rho 0.996936217, support 0.996238813 / 0.973365162; channel 0 rho 0.988577311 | Легитимная исходная музыка без нашей copy-insertion, совпадение продолжается и согласовано по channels. Это не доказательство независимо сыгранного повтора: source production history, включая возможный музыкальный loop, не установлена |

Vibe Ace: a=[20480,110592), b=[183311,273423), offset=162831 samples при
44100 Hz, delta=-1009 на обоих каналах, exact_decoded=false. Поддержка двух
каналов и двух последующих блоков не делает correspondence специфичной для
манипулированной речи. Generated tone/hum/rhythm дают rho 1 с продолжением;
у одного из максимальных beep matches support=[undefined,1] из-за silent block.
Первый rho 1 сам по себе не означает даже полный structural support.

В real-overlay challenge background использован как один shared waveform либо
два участка того же source file. Distinct segments не равны независимым
записям среды; foreground — разные speakers, не same-speaker natural re-speech.
Эта challenge layer не доказывает распространённость confound в voice messages.

**Доступность attribution — PARTIAL.** Frozen outputs описывают, где и как
совпадает waveform. Fixture masks/recipe позволяют атрибутировать известные
случаи, но outputs не содержат ground truth «речь изменена». Даже exact_decoded
доказывает только равенство decoded samples; near-1 без exact равенства бывает
у periodic signals. Descriptive attribution на известных fixtures выполнима;
надёжная автоматическая attribution неизвестной записи ещё не установлена.

## 3. Инвентаризация информации

У ARC нет принятого production result: A ниже означает сохранённый research
output, а не публичный контракт. B не подразумевает право экспортировать новые
поля. Новое представление из C потребует OWNER GATE до реализации.

| Категория | Информация | Доступность / ограничения |
|---|---|---|
| A — сохранённые outputs | Seed locations, window/sample/PTS coordinates; pair seed positions, refined intervals/offset/delta | `raw.jsonl`: seeds, windows, pairs; доступны точные sample coordinates внутри выбранных M1 windows, без обещания full-duration coverage |
| A | Per-channel rho, два support_rhos, structural_support, exact_decoded, channel_best_deltas, channel_offset_disagreement | Для retained measured pairs; undefined сохранён, не заменён нулём; support continuation не speech attribution |
| A | Seed/candidate counts и cap flags, exclusions, coarse_comparisons; все coarse_nominations | Union сохранён в global rank order, можно восстановить ранг каждой nominated пары. Ранжирующие distances сохранены только для retained pairs |
| A — производные сводки | Exact lag counts, window-pair distribution, interval overlaps, concentration, temporal coverage | Вычисляются без изменения ARC. Точные bins/метрики здесь описательные, не production thresholds или добавленные API fields |
| A — диагностика | equal_best_lag_count, NCC evaluations, timings и memory observations | Ties относятся к NCC после retention; не объясняют автоматически coarse ranking. Исторические timings/RSS не новый certified bound |
| B — research truth | Parent/recipe hashes, fixture source/destination masks, mix alignment/levels, source/background identity | Сохранены в case/raw manifests для проверки эксперимента; для произвольного пользовательского media таких semantic masks нет. Это oracle-аннотации, не выход preprocessing |
| B — execution internals | Descriptor vectors, directed top4 lists, все pair/channel distances до cap | Вычислялись внутри frozen research execution, но полный trace не сохранён. Не реконструированы новым ARC запуском; distances потерянных true pairs неизвестны, ранги известны |
| B — существующие M1 representations | Native sample windows, shared STFT 4096/1024, typed timing/source facts | Prepared artifacts существуют с hashes; могут поддержать отдельно разрешённую bounded diagnostic study без нового preprocessing. В этой задаче новые waveform/STFT diagnostics не запускались |
| C — отсутствующая capability | Foreground/background separated streams; semantic speech masks; полный duration вне текущих windows | Не являются текущими representations. Их необходимость для будущего метода означает STOP / OWNER GATE; здесь они не нужны и не добавлены |

Повторные offsets видимы без oracle. Объединение разных offsets в **одну
физическую periodic family** ниже опирается на известную 250 Hz construction,
а не на уже существующий автоматический family detector. Такое различие
критично при оценке вариантов B/C.

## 4. Retrieval chain: где потеряна известная речь

Case `cap-competition-tone-speech`: 60 s, fs=44100, mono, L=45056,
250 Hz tone на всей длительности. Speech waveform длины 135168 samples
скопирован из [0,135168) в [2510832,2646000), truth offset=2510832.
Из-за фазы фонового тона суммарная смесь не является exact waveform copy;
ground truth относится к скопированному foreground.

Точный порядок frozen реализации: seeds → допустимые coarse сравнения →
per-seed/per-channel top4 nominations → undirected union → global distance
ranking → retained64 → bounded NCC. Union уже состоит из nominations;
`coarse_nominations` содержит весь **отсортированный** union, не только top64.

| Шаг | Счёт и наблюдение |
|---|---|
| M1 windows | [0,441000), [1102500,1543500), [2205000,2646000); анализируются выбранные windows, не все 60 s |
| Seed geometry | 258 seeds до cap → 256; удалены absolute 1274532 и 2549064 по неизменённой evenly spaced index selection |
| Truth geometry | 23 потенциальные пары до seed cap → 21 после; это геометрическая возможность проверить truth offset с полным 2L, не уже измеренные NCC |
| Coarse stage | 27979 допустимых mono descriptor comparisons; top4 lists объединены в 677 уникальных undirected pairs |
| Nomination | 20 из 21 truth-eligible pairs номинированы; пара seed indices (11,255) не вошла в union |
| Ranking | True ranks: 518, 523, 524, 525, 526, 527, 528, 529, 539, 540, 541, 542, 543, 544, 545, 548, 550, 559, 560, 585 |
| Retention | Все 20 nominated true pairs за пределами первых 64; retained truth=0, NCC для этих пар не выполнялся |
| Returned evidence | 64/64 refined full-2L pairs целиком в background-only области; все first-L rho=1, support в [0.9999999999999999,1], exact_decoded=false |

Truth eligibility восстановлена из сохранённых seed/window/truth coordinates:
source full2L внутри speech mask, destination at truth offset внутри destination
mask/window, delta в ±4096 и coarse nonoverlap. Это metadata-only проверка,
не новая signal evaluation; она совпадает с прежними 21/20/0 counts.

Основная полная потеря происходит **на global distance ranking → cap64**, до
refinement/NCC; две возможности теряются на seed cap и одна на top4 nomination,
но после них true candidates ещё существуют. Увеличение rho или post-filter
retained pairs не может вернуть отсутствующее измерение truth. Сам факт
номинации также не доказывает, что будущий иной retention даст верную NCC
локализацию на фоне: это отдельный проверяемый вопрос будущего исследования.

Все 64 stored coarse distances различны: от 3.178429992542962e-28 до
4.142687184565965e-27. Полного distance trace вне retained64 нет: нельзя
утверждать наличие/отсутствие ties на границе 64/65 или точный distance margin
до truth. Установлен bounded-selection failure при большом числе практически
одинаковых тональных descriptors; exact pair duplication отсутствует (union
уже deduplicated). NCC equal-best ties встречаются позже, у retained pairs
от 3 до 9 равных maxima, и влияют на delta, но не являются причиной удаления
true candidates до NCC. Контрфактическое изменение coarse ties не проверялось.

## 5. Candidate concentration без production cutoffs

Offset ниже — `b_interval.start - a_interval.start`, delta — локальная поправка
к b seed. Их смешение скрыло бы концентрацию coarse retrieval. Exact lag family
здесь определяется равенством integer offset; broader periodic family отдельно
определена известной fixture construction, без обученного clustering radius.

| Уровень | Концентрация |
|---|---|
| Полный union | 677 unique pairs, 91 exact coarse offsets; top offset 102400: 121/677 (17.87%), 1102500: 115, 1000100: 109, 1204900: 65 |
| Union и fixture masks | 450/677 nominal full2L pairs целиком background-only; остальные 227 не следует целиком приписывать чистому тону |
| Union window pairs | (0,0)=32, (0,1)=147, (0,2)=219, (1,1)=63, (1,2)=172, (2,2)=44 |
| Retained coarse offsets | 1102500: 59/64 (92.1875%); 2205000: 5/64; два coarse offset families |
| Refined offsets | 1102500:41, 1101618:12, 1103382:4, 2205000:4, 1104264:1, 1100736:1, 2204118:1; семь exact offsets, top share 41/64=64.0625% |
| Fixture periodic family | Все 64 offsets кратны 882 samples, т.е. пяти периодам известного 250 Hz тона при 44100 Hz: одна физическая periodic family занимает 100% cap |
| Local refinement delta | 0:45, -882:13, +882:4, +1764:1, -1764:1; это пять deltas, не пять независимых источников |
| Retained temporal regions | (window0,window1)=52/64 (81.25%), (1,2)=7, (0,2)=5; 113 unique seed indices, все refined pairs background-only |
| Pair overlap | 877 из 2016 unordered pair-of-pairs (43.502%) имеют положительное пересечение одновременно a-intervals и b-intervals; full2L, полуоткрытые интервалы, без IoU cutoff |

Таким образом, нет единственного универсального «числа семей»: 91 coarse
offset в union, два в retained seeds, семь после refinement и одна известная
физическая tone family. Наличие единственного тона в ground truth не доказывает
автоматическую идентифицируемость этой семьи на неизвестном media.

Для проверки неспецифичности концентрации рассмотрены существующие контрасты
(все measured retained pairs case; доли не являются порогами):

| Case | Pairs | Unique refined offsets | Top exact-offset share | Overlap pairs / все pair-of-pairs |
|---|---:|---:|---:|---:|
| cap-competition-tone-speech | 64 | 7 | 41/64 | 877/2016 |
| generated-tone | 64 | 13 | 38/64 | 1374/2016 |
| original-esc-washing_machine | 43 | 18 | 7/43 | 903/903 |
| excerpt-vibe-ace-2 | 64 | 41 | 18/64 | 1937/2016 |
| mix-lamit-S03_P001_T1-shared--10 | 21 | 7 | 10/21 | 210/210 |
| copy-lamit-S01_P001_T1-long-exact | 64 | 23 | 32/64 | 2016/2016 |
| original-libri-5639 | 64 | 56 | 3/64 | 308/2016 |

Copy-контроль тоже имеет сильную концентрацию и полный pair overlap: нельзя
просто отбрасывать повторяющийся lag, overlapping candidates или concentration.
Short-window geometry сама увеличивает overlap; comparisons зависимы.
Original Libri maximum 0.350497998 с support -0.018097537 / 0.053676545 показывает,
что structural_support=true не означает продолжение сильной correspondence.

## 6. Сравнение четырёх направлений

| Вариант | Что способен проверить | Ограничение / стоимость / решение |
|---|---|---|
| A — POST-ARC ATTRIBUTION, frozen v2 | Координаты/support/channels/concentration и известные annotations позволяют объяснить retained correspondence и явно оставить ambiguous | Минимальная работа с существующими outputs; ground truth недоступен в deployment. Не возвращает 20 потерянных truth nominations. Обоснована отдельная study интерпретации, без automatic decision rule |
| B — RETRIEVAL DIVERSIFICATION | Гипотеза: bounded retention может представить разные lag/time structures вместо расходования всех 64 мест на один repeated background | Внешний research-only experiment разрешён решением §9, ARC baseline не меняется. Простая diversity не гарантирует rescue rank518 и может вытеснить хорошие speech copies. Не требует изменения descriptor/NCC/caps; текущая задача не реализует или проверяет новый selector |
| C — SEPARATE APPLICABILITY / BACKGROUND METHOD | Отделяет waveform correspondence от вопроса, к какому компоненту она относится; существующие samples/STFT могут дать bounded exploratory diagnostics | Надёжный automatic detector пока не обоснован: TV/speech background семантически похож на foreground, legitimate music и true copy разделяются не одной concentration. Дополнительные CPU/RSS и право на метод надо исследовать отдельно; necessity отдельного production method — UNCERTAIN |
| D — KEEP ARC RESEARCH-ONLY | Сохраняет корректное measurement interpretation без необоснованного production advancement | Допустимый конечный outcome, если attribution требует недоступных semantic masks либо diversification не помогает при прежнем budget. Пока остаются проверяемые узкие гипотезы; прекращать всё исследование преждевременно |

Разделение «измерена repeated waveform correspondence» и «речь могла быть
смонтирована» концептуально чище, чем попытка вложить foreground/background
семантику в NCC. Это оценка будущего дизайна, не принятие новой архитектуры,
анализатора, risk/correlation policy или public schema. Где semantic attribution
не доказана, описание должно оставаться waveform-only / ambiguous.

## 7. Минимальное следующее исследование и OWNER GATE

Две связанные части **будущего, ещё не выполненного** исследования разрешены
решением владельца §9. Точный bounded scope принадлежит
[ROADMAP](../ROADMAP.md#audio-m3r3d); repo executable changes не разрешены.

**Часть A — frozen-v2 attribution study.** Использовать прежние cases и outputs,
сначала описывать признаки без fixture labels, затем проверять объяснения по
заранее сохранённым masks/recipes. Обязательные контрпримеры: обычные speech
copies всех четырёх transformations, Vibe Ace, washing machine, real shared
background (включая speech background), distinct segments, generated signals,
cap stress, undefined/resource-rejection cases. Для близкого рассмотрения
samples/STFT используется явно ограниченный diagnostic protocol на существующих
M1 representations, зафиксированный до outcomes. Не создавать classifier/cutoff.
Считать согласованные, ошибочные и ambiguous attribution на уровне case/source;
не выдавать эти описательные counts за FPR или независимую population validation.

**Часть B — разрешённая проверка retention hypothesis, ещё не выполнена.**
Наблюдаемый failure — 20 nominated truth pairs rank518–585 не доходят до NCC,
при том что 64 места заняты одной известной tone family. Наименьшая conceptual
перемена для исследования — только распределение неизменного бюджета retained
позиций среди уже номинированных lag/time structures. Не изменять nomination,
descriptor, NCC, численную арифметику или их thresholds; не увеличивать cap и
не сканировать полный файл. Никаких quotas, bin widths, similarity tolerances,
fallbacks, version/schema сейчас не выбрано. Ground-truth speech/background
masks могут оценивать результат, но **не управлять selector**.

До будущих outcomes необходимо зафиксировать конкретную проверяемую hypothesis,
детерминированную grouping/selection procedure и resource protocol; любое
отклонение требует нового gate, не настройки по результату. Сравнить с frozen-v2
baseline весь прежний набор, сохранив все difficult cases. В первую очередь
отдельно учитывать eligible/nominated/retained truth, correct offsets и support,
а не только global rho или рост diversity. Не смешивать улучшение представленности
truth в retained set с доказанной локализацией по NCC и forensic usefulness.

**Что опровергнет гипотезу:** truth по-прежнему теряется; дополнительные retained
truth pairs не локализуются; ухудшается сохранение обычных known copies;
selector расходует budget на случайные dissimilar pairs; выигрывает только
при доступе к oracle masks; требует нового preprocessing/полного duration либо
не укладывается в прежние bounds. Для attribution отрицательным результатом
будет невозможность различить legitimate repetition, shared speech background
и foreground copies без недоступной semantic truth. Такой результат ведёт к
явному research-only outcome или отдельному method gate, а не forced promotion.

**Resource invariants будущего сравнения:** прежние M1 precision windows,
native rate/channels, L/full2L, seed cap256, per-seed top4, candidate cap64,
delta ±4096, overlap/support/tie/channel rules и frozen numerical guard.
Нельзя получать rescue ростом числа NCC, расширением search, hidden fallback
или нового preprocessing. Grouping overhead входит в total time/RSS; прежние
30 s deadline и FFT Q≤131072 сохраняются; прежний memory plan≤32 MiB
дополнительных buffers не превращается в enforced native RSS quota или
certified production bound. Resource/undefined cases
остаются в сравнении. Production tuning/calibration/thresholds запрещены.

Следовательно, post-processing frozen outputs недостаточен для retrieval
failure, но это обоснование **исследования**, не доказательство необходимости
конкретной новой версии ARC. Отдельный automatic applicability method может
понадобиться; его необходимость и реализуемость пока UNCERTAIN. Если он требует
category C representations, работа останавливается на новом OWNER GATE.

## 8. Статус и проверка

M3-R3D-P — **DONE / OWNER ACCEPTED DESIGN RESULT**; дальнейшая экспериментальная
работа разрешена явным решением владельца §9, но ещё не выполнена. Frozen v2
не менялся, новых measurements/media нет. Tests, oracle rerun, quality barrier
и certification не запускались; выполнены `git diff --check`, review полного
intended diff с новым untracked report и итоговый Git status.

Review bundle: `FakeDetector-Work/reviews/M3-R3D-arc-applicability/` —
analysis-summary, retrieval-chain, candidate-concentration, design-options,
recommended-next-experiment, review-summary, complete.diff и git-status.txt.
Original M3-R3C evidence/review bundle сохранены неизменными.
Staging/commit остаются владельцу, Git mutations не выполнялись.

Методологический статус ARC остаётся **NEEDS_TARGETED_RESEARCH**, production
tuning/calibration не разрешены. ATD-LOCAL-1 и ASC-TV-1 остаются
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**; оба carry-forward нерешены.
Macro 3 — **IN_PROGRESS**. Принятие design report и разрешение следующего
experiment scope записаны по явному решению владельца, не agent self-report.

## 9. OWNER ACCEPTANCE — 2026-09-29

Владелец явно принял **M3-R3D-P: DONE / OWNER ACCEPTED DESIGN RESULT**.
Gate принятия design/evidence analysis закрыт. Принята рекомендация
**COMBINED_ATTRIBUTION_AND_DIVERSIFICATION_STUDY_REQUIRED**.

Приняты результаты и ограничения §2–6 без изменения численных свидетельств:

- Attribution из frozen-v2 outputs — **PARTIAL**: geometry, support, channels
  и concentration описывают correspondence, но не устанавливают надёжную
  automatic foreground/background semantic truth неизвестного media.
  Fixture masks/recipes дают основание для attribution controlled cases.
- Главная полная потеря truth — **GLOBAL DISTANCE RANKING → CAP64** до NCC:
  21 eligible →20 nominated, ranks518–585 →0 retained; NCC для этих true
  speech pairs не выполнялся.
- 59/64 разделяют coarse offset, 41/64 — refined offset; все64 относятся
  к одной physical tone family **по известной fixture construction**.
  Это не universal detector или production rule.
- Post-attribution не восстанавливает отброшенный candidate. Concentration
  нельзя использовать как rejection rule: настоящие copies тоже могут иметь
  выраженную concentration/overlap. Retention diversification research
  обосновано, отдельный automatic applicability method остаётся **UNCERTAIN**.

Владелец разрешил **M3-R3D-E — ARC Attribution & Retention Diversification
Experiment: AUTHORIZED / NOT YET EXECUTED**. Часть A исследует описательную
attribution существующих cases/outputs с bounded M1 representations. Часть B
допускает research-only retention alternatives **внешне под FakeDetector-Work**,
меняющие только выбор прежнего fixed budget из уже nominated union.
Fixture/oracle masks используются только для оценки, не для selection.
Сравнение обязательно с неизменённым frozen-v2 top64 baseline.
Точные invariants, запреты и требования до outcomes зафиксированы в
[ROADMAP](../ROADMAP.md#audio-m3r3d). До новых retention/NCC outcomes обязательны
полная преддекларация selectors/procedure/features/metrics/cases/resources/
falsification и её SHA-256; tuning после outcomes запрещён.

В этой задаче experiment не выполнялся, selectors не реализованы.
ARC-NCC-1 остаётся **NEEDS_TARGETED_RESEARCH**; frozen v2 неизменён,
experimental selector не именуется ARC v3. **ARC v3 implementation — NOT
AUTHORIZED**; вывод о необходимости ARC baseline/production executable change
означает следующий **STOP / OWNER GATE**.
Production method acceptance, tuning/calibration, threshold selection,
FPR/sensitivity validation, analyzer implementation и Finding не разрешены.
Новые media/dependencies/preprocessing не разрешены. M3-R3B broad validation
остаётся **DEFERRED UNTIL CALIBRATION / PRODUCTION-READINESS RESEARCH**.
ATD/ASC **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD** остаются нерешёнными;
Macro 3 — **IN_PROGRESS**. Staging/commit остаются владельцу.
