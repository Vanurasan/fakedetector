# M3-ATD-D1 — review обязательства ATD-LOCAL-1

Дата: **2026-09-29**. Baseline: `136efa9741c226da616d76846a5e0755c5b70612`,
ветка `feat/stage12-macro3-audio-analyzer-expansion-wave1`, начало чистое.
Тип работы: review существующих свидетельств, без новых измерений и экспериментов.

## 1. Рекомендация review и её принятие

**Disposition review: RESEARCH_ONLY_NON_SPECIFIC; принят владельцем 2026-09-29.** ATD воспроизводимо
описывает локальные waveform/energy переходы, но сильный ответ не устанавливает
монтажную причину. Сохранить измерительный прототип как исследовательское
свидетельство, без дальнейшего promotion текущего профиля в рамках дипломного
scope. Одна малая нерешённая гипотеза, способная изменить этот вывод, в имеющихся
свидетельствах не найдена; `TARGETED_NEXT_STUDY` не предлагается.

Рекомендация принята явно: **M3-ATD-D1 — DONE / OWNER ACCEPTED DISPOSITION**.
ATD — **RESEARCH_ONLY_NON_SPECIFIC / OWNER ACCEPTED**, carry-forward **RESOLVED**;
ASC-обязательство не разрешено. Решение записано в разделе owner acceptance ниже.
Правило закрытия принадлежит
[ROADMAP](../ROADMAP.md#audio-m3-required-carry-forward).

## 2. Свидетельства и проверяемость

Исходные основания — [M3-R1, ATD-LOCAL-1](2026-09-26-audio-method-selection.md)
и принятый владельцем [M3-R2A](2026-09-26-audio-transition-measurement-prototype.md).
Происхождение и лицензии остаются в [REFERENCES, M3-R2A](../REFERENCES.md#audio-m3r2a);
новых источников или изменений provenance в этом review нет.
Последующие repository research-записи сохраняют carry-forward, но не добавляют
новых ATD измерений. Внешние исходные материалы:

- `FakeDetector-Work/research/M3-R2A-transition/`: `predeclaration-v2.md`,
  `fixtures/cases.json`, сохранённые media/M1 artifacts,
  `measurements/final.jsonl`, `measurements/determinism.json`, три `cold-*.json`,
  `results/event-maxima.json`, `results/analysis.json`, `results/oracles.json`;
- там же `scripts/protocol.py`, `prepare_v2.py`, `measure_v2.py` и
  `analyze_results.py` прочитаны как описание прежней процедуры, не запускались;
- `FakeDetector-Work/reviews/M3-R2A-transition/`: прежние measurement/provenance
  summaries и review-summary; provenance и отрицательные результаты сохранены.

Read-only сверка подтвердила hashes V1/V2, восьми sealed scripts, corpus manifest
и replacement selection. Все 609 case/raw identities совпали, проверены media
hashes и 705 ссылок на prepared artifacts. Все 627 сохранённых window/channel
строк `event-maxima.json` сверены с ATD max/top в `final.jsonl`.
Сохранённые 12 групп ×3 повторов и три fresh-process результата согласуются
с raw windows. Это проверка существующих файлов, **не повторный запуск** тестов,
oracles или измерений.

Идентичности исходных свидетельств:

| Материал | SHA-256 |
|---|---|
| Frozen predeclaration V2 | `db515484f4716d828e1fc3532369a2b148df4691894c99f7ed4e732b42025452` |
| `scripts/protocol.py` | `27742945543e894f20785549f862ae9c8236732ba7122f49e7b6321ff2b96d3b` |
| `fixtures/cases.json` | `bc861e90d0ba8bdcd074af2d6a189d83cf6bd4f0182e8f75c94f6b0b61b92c73` |
| `measurements/final.jsonl` | `5b97eb395234b5eae9697c9453ebcf2ab69691bdbc2caa3d64320ad4e8ce029a` |

M3-R2A завершил 608 из 609 cases: 573 controlled и 35 real/derived;
`resource_48000` — технический отказ, не отрицательный ATD ответ. Исторический
Vibe Ace также не completed measurement. В основной synthetic matrix 33 строки
(7 negative, 11 controlled-positive, 15 benign), одна generated lineage.
512 residue fixtures проверяют позиционную арифметику, не 512 независимых
случаев монтажа. Пять real source groups: три LibriSpeech speakers, NPS humpback
и sorohanro trumpet; 5 originals +30 derivatives дают 45 window/channel строк,
не 45 независимых источников. Это не population validation и не holdout study.

## 3. Что физически измерено

Сохранённая процедура выбирает наибольшую соседнюю sample difference в центральном
диапазоне каждого полного 2048-sample frame при hop 512, с earliest tie.
На сторонах по 512 samples отдельно вычисляются J, E, Es и A: относительный
sample jump, RMS contrast и его знак, median/DC contrast. Точная процедура
остаётся в M3-R1 и frozen M3-R2A; формулы, нормализация, tie/undefined/channel
behavior не менялись. Метрики не суммируются в forensic score.

Сохранённый oracle PASS включает scalar references, zero denominators/ties,
channel order, framing и все 512 residue positions; общий прежний набор содержит
также ASC-проверки и не объявляется ATD-only набором. В специальном step fixture
все 512 смещений дали точный b и J/E/Es/A=1. Это поддерживает воспроизводимую
физическую интерпретацию, а не обнаружение произвольной склейки.

Ни позиция b, ни max/top-16 сами по себе не являются найденным монтажом.
Support ATD — 1024 samples; покрытие ограничено существующими M1 windows.
Далее max J/E/A — **отдельные** максимумы, часто в разных позициях.
Es — signed measurement, а его сохранённый максимум не равен max |Es|.
Числа округлены только для представления; cutoff не вводится.

## 4. Controlled manipulation и локализация

Основные synthetic constructions, все с truth b=32000 при 16 kHz:

| Case | Конструкция | max J | max E | Δ позиции max J / max E, samples |
|---|---|---:|---:|---:|
| `phase_jump` | Скачок фазы синусоиды на π/2 | 0.940626 | 0.000975 | 0 / −287 |
| `amplitude_step` | Постоянный уровень 0.1 → 0.7 | 1 | 0.75 | 0 / 0 |
| `gain_step` | Вторая половина tone ×2 | 0.597954 | 0.206567 | +481 / −287 |
| `dc_step` | DC +0.3 на второй половине tone | 0.927889 | 0.186244 | 0 / 0 |
| `waveform_splice` | Tone 250 → 2000 Hz | 0.707107 | ≈2.84e−14 | +481 / +25289 |
| `similar_content_boundary` | Speechlike splice со сдвигом 137 samples | 0.765251 | 0.285736 | −21793 / −9246 |
| `equal_rms_spectral` | Та же waveform, что `waveform_splice` | 0.707107 | ≈2.84e−14 | +481 / +25289 |
| `bandwidth_step` | Смесь tone/high → tone | 0.828025 | ≈2.33e−14 | 0 / −6528 |
| `eq_step` | Изменение соотношения компонент смеси | 0.699420 | ≈2.90e−14 | +5953 / +14081 |
| `stationary_spectra` | Смена пары частот смеси | 0.673693 | 0.001170 | −12159 / +14 |
| `leakage_jump` | Tone с добавленным step +0.5 | 0.953389 | 0.340154 | 0 / 0 |

В этих 11 строках truth находится внутри support max J в 8/11, max E в 6/11;
медианы абсолютного смещения — 481 и 287 samples соответственно. Это прежние
описательные результаты, **не sensitivity** и не доля точных локализаций.
Например, `waveform_splice` имеет truth внутри J support, но не точный max b;
`similar_content_boundary` не локализован глобальным максимумом J или E.
Почти нулевой E при equal-RMS splice ожидаем для level contrast и не опровергает
сам факт искусственного splice. Теоретический gain contrast 1/3 не обязан
появиться при выбранном sample-difference b: фактический max E равен 0.206567.

На каждом из пяти реальных источников прежний протокол создавал DC +0.2 и
splice со сдвигом второй половины на 137 samples из нормированного первого M1
window. Это 10 controlled-positive derivatives, не 10 новых источников.
Сохранённые max J/E локализации splice:

| Источник | Канал | Δ max J | Δ max E | Truth в support max J / E |
|---|---:|---:|---:|---|
| `nps-humpback__splice` | 0 | −163996 | +151649 | нет / нет |
| `libri-6930__splice` | 0 | −1467 | −6436 | нет / нет |
| `libri-1320__splice` | 0 | +43776 | +30817 | нет / нет |
| `libri-5639__splice` | 0 | −62652 | +50434 | нет / нет |
| `sorohanro-trumpet__splice` | 0 и 1 | −91767 | −28837 | нет / нет |

Все значения — sample offsets в соответствующем исходном rate; каналы одной
записи не независимые случаи. Для DC derivative `libri-5639` max J и E точно
совпали с truth; у trumpet оба канала имеют точный max J, но не max E.
У остальных трёх sources max J/E truth не поддерживают. Это ограниченная
демонстрация ответа на DC, не надёжная general splice localization.
Отсутствие truth в global-max support не доказывает отсутствия любого локального
ответа или truth среди остальных кандидатов; такой retrieval claim здесь не делается.

## 5. Benign overlap и границы attribution

| Поддержанный challenge | Сохранённые max J / E | Что можно заключить |
|---|---|---|
| `plosive` | 0.943713 / 0.285736 | Generated speechlike + затухающий noise attack; не размеченный реальный plosive |
| `percussion` | 0.998306 / 0.973237 | Generated tonal/noise transient даёт почти предельный ответ |
| `phoneme_transition` | 0.803749 / 0.446399 | Generated смена компонент; не естественная фонемная разметка |
| `speech_to_silence` | 0.999468 / 1 | Benign-labelled переход к тишине перекрывает сильные controlled ответы |
| `clipping` | 1 / 0.213323 | Quality distortion может давать предельный J; причина не становится монтажной |
| `gain_change` | 0.597954 / 0.206567 | Те же waveform и полный ATD output, что `gain_step` |
| `eq_change` | 0.699420 / ≈2.90e−14 | Те же waveform и полный ATD output, что `eq_step` |
| `fade` | 0.771370 / 0.365204 | Обычная обработка уровня также меняет ответ |
| `legitimate_scene_change` | 0.859707 / 0.285736 | Generated speechlike → noise; не запись размеченного природного события |
| `codec_mp3` / `codec_aac` | 0.765374 / 0.285762; 0.766321 / 0.285627 | Реальный 64 kbps codec round-trip generated speechlike, не доказательство codec click |

У codec source `speechlike` уже J=0.765251, E=0.285736; близкие максимумы после
кодирования не устанавливают codec как причину сильного отдельного события.
`noise_suppression` — noise-gate proxy, `bandwidth_history` — moving-average proxy,
не исследование настоящего denoiser, SRC или packet-loss concealment.
Высокий ответ на recording glitch как отдельную причинную категорию не установлен.

Пять реальных originals без внесённого проектом splice имеют следующие
max J/E в window 0, channel 0:

| Source | max J | max E |
|---|---:|---:|
| NPS humpback | 0.935499 | 0.553933 |
| LibriSpeech 6930 | 0.981672 | 0.906032 |
| LibriSpeech 1320 | 0.981965 | 0.831203 |
| LibriSpeech 5639 | 0.988636 | 0.949167 |
| sorohanro trumpet | 0.962965 | 0.819895 |

В последующем window оригинала LibriSpeech 5639 наблюдался также J=1.
Это подтверждает сильный ответ на обычном исходном материале, но не связывает
конкретный максимум с реальным plosive, ударом или природным событием:
event annotations отсутствуют. «Original» означает отсутствие преобразования
проектом, не сертифицированную подлинность и не отсутствие прежней обработки.
NPS — environmental source, не доказательство причины каждого peak.
Benign high response надёжно показан controlled challenges; реальные записи
дополняют ограниченность forensic interpretation, но не дают FPR.

Тождество media hashes и **полных** сохранённых ATD outputs для gain/EQ пар
проверено непосредственно. Две экспериментальные роли одной waveform не дают
двух независимых observations; они показывают, что label/намерение обработки
не восстанавливаются из этих измерений. Наблюдаемое перекрытие максимумов
не является доказательством математической невозможности любого будущего
многомерного метода, но не обосновывает promotion нынешнего ATD профиля.

## 6. Сравнение dispositions

| Вариант | Оценка существующих оснований |
|---|---|
| TARGETED_NEXT_STUDY | Не выбран: малый дополнительный content-matched тест уточнил бы отдельный confound, но пока нет конкретного неизменённого ATD признака с показанной специфичностью, ради которого он мог бы изменить disposition. Новые признаки или semantics означали бы другую задачу |
| **RESEARCH_ONLY_NON_SPECIFIC** | **Выбран:** физическое измерение полезно как описание; benign overlap, совпадающие gain/EQ inputs и слабая splice localization не поддерживают самостоятельный forensic вывод |
| DEFER_TO_PRODUCTION_READINESS_RESEARCH | Не выбран: широкий корпус нужен для будущих population claims, но его отсутствие не мешает уже сейчас ограничить интерпретацию нынешнего профиля; review не превращается в обязательную calibration программу |
| REJECT_FORENSIC_PROMOTION | Не выбран как итоговая метка: forensic promotion сейчас не обоснован, однако воспроизводимое descriptive measurement и отрицательные свидетельства заслуживают сохранения в research-only статусе |

Новой пороговой гипотезы, ROC/F1, production cutoff, severity, Finding, fake
probability или fake/authentic verdict нет. Apparent gap, который потребовал бы
post-hoc threshold, здесь не заявляется. Формулы, preprocessing, зависимости,
production contracts и runtime не изменяются.

ATD disposition **не зависит от ASC**: для рекомендации использованы только
ATD measurements и ground-truth recipes. ATD/ASC остаются раздельными измерениями
общего transition track, без fusion и без утверждения статистической независимости.
ASC сохраняет **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**. ARC не активен;
его принятый deferred scope не переоткрывается. Macro 3 — **IN_PROGRESS**.

## 7. OWNER ACCEPTANCE — 2026-09-29

Владелец явно принял **RESEARCH_ONLY_NON_SPECIFIC** для ATD-LOCAL-1:

- валидность воспроизводимого описательного измерения локальных waveform/energy
  переходов и наличие ответа на controlled manipulation;
- сильные benign responses и существенное перекрытие benign/manipulated ranges;
- forensic specificity **NOT ESTABLISHED**: сильный ATD response сам по себе
  недостаточен для вывода о монтаже или склейке;
- **M3-ATD-D1 — DONE / OWNER ACCEPTED DISPOSITION**;
- **ATD carry-forward — RESOLVED**;
- **FURTHER_ATD_PROMOTION_WORK_IN_CURRENT_MACRO3 — NONE**: новые ATD эксперименты
  не начинаются, прототип сохраняется для будущих research/descriptive целей.

Это не отрицание физической валидности ATD. Production method не разрешён,
production threshold отсутствует, production analyzer не реализован, Finding
не добавлен, severity/risk mapping не разрешён. Fake/authentic verdict нет.
Численные результаты, формулы, evidence и ограничения review не изменены.

ATD disposition не зависит от ASC. Измерения остаются раздельными, без fusion
и утверждения статистической независимости. ASC-TV-1 сохраняет
**NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**, **OPEN / REQUIRED**.
Следующий активный topic — **ASC-TV-1 carry-forward disposition**; после него
запланированы documentation/instruction hygiene audit и Macro 3 closure review.
ASC work и hygiene audit в этой задаче не выполняются.

ARC сохраняет **RESEARCH MEASUREMENT DEMONSTRATED / PRODUCTION PROMOTION
DEFERRED**, активной ARC work нет; M3H-A01 остаётся deferred.
Macro 3 — **IN_PROGRESS**.

## 8. Передача записи решения владельцу

Owner disposition принят; корректность его записи и обновлённый полный intended
diff требуют owner review. Staging/commit остаются владельцу.

Новые review-материалы находятся в
`C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-ATD-D1-disposition\acceptance\`;
сверка и ATD-only выписка из сохранённых результатов — в соответствующей
`research\M3-ATD-D1-disposition\`. Предыдущие evidence trees не изменены.
Review bundle включает весь intended diff, в том числе этот untracked report.
Проверки: `git diff --check`, полный diff и итоговый status; новых тестов,
экспериментов, full quality barrier и strict certification нет. Git mutations
не выполнялись; staging/commit остаются владельцу.
