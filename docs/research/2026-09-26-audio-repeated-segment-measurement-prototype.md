# M3-R2B — ARC-NCC-1: измерительный прототип повторного соответствия

Дата: **2026-09-26**. **DONE / OWNER ACCEPTED RESEARCH RESULT**.
Baseline `fe092c43b86115c8ba69e14c940a737215ce5665`, ветка
`feat/stage12-macro3-audio-analyzer-expansion-wave1`; начальное дерево чистое.
Исследовательский outcome: **READY_FOR_LARGER_VALIDATION**.
Это готовность к большему source-level исследованию, не production acceptance.
Явное решение владельца и следующий speech/voice-message scope записаны в §10.
Нет порога, classifier, Finding, production analyzer или correlation изменения.
ATD/ASC не запускались; обязательные carry-forward и Macro 3 IN_PROGRESS сохранены.

## 1. Замороженный профиль и проверяемая история

Точный источник: [M3-R1 §§3,7](2026-09-26-audio-method-selection.md).
Общие условия и весь ARC-профиль дословно извлечены в external predeclaration.
SHA-256 **predeclaration.md**: `68a7dc51c850fe4daf18e54409d9911b32d770dcc72c21d1256e69469fdfe3ff`.
SHA-256 M3-R1: `d8a453c17956f5435f5227fa6b1a1500af68e9aba8b13caed4e670f3cb5e7368`.
Freeze UTC: `2026-09-26T15:01:41.957576+00:00`.

Фиксированные inputs: audio route, 8–48 kHz, mono/stereo, M1-D precision windows
и готовая magnitude STFT 4096/1024, periodic Hann; source identity через typed
manifest/numeric reader. Без второго STFT, собственного decoder, resample/downmix.
H=1024; L=H ceil(fs/H); seeds через4096, только полный2L; K≤256 равномерным
индексным сокращением. Descriptor: ≥4 полных STFT frames первой L, 16 полос
по128 bins безDC, четыре temporal группы, 64 числа/L2. Top4 соседей на seed/channel,
nonoverlap2L, union и cap64 на файл; squared distance, ties по source time.
δ целочисленный ±4096 с полным2L support в исходном окне, без overlap.
Signed centered NCC первой L; общий lag по mean информативных каналов,
tie меньший absδ, затем меньший δ. Два независимых support L/2 на том же offset;
три значения по каждому каналу, без similarity threshold. Numeric floor64eps*m,
guard64eps за[-1,1]; отдельные maxabs, float64. Exact decoded equality на2L
проверяется отдельно от NCC, без gain/centering. FFT linear Q≤131072,
streaming top4, memory plan≤32MiB дополнительных buffers, deadline30s.
Каналы не перемешиваются; разные channel-best offsets явно отмечены.

Fixtures, seed2026092602, source selection/grouping, recipes, метрики,
абстенции, exact repeat subset и ограничения были зафиксированы до corpus outcomes.
80 recipes/hashes/manifests сохранены в fixtures/cases.json; его hash и время
записаны в logs/premeasurement.json до measurements. Ни одной процедуры или
параметра ARC после результатов не подбирали; эксперименты ATD/ASC не повторяли.

### Исправление численной реализации, без изменения профиля

Первый frozen harness остановился на multitone после 14 completed cases:
ordinary float64 prefix cumsum дал rho=1.0000000000000189 (85eps сверх1),
поэтому guard64eps корректно выдал numeric failure. Independent math.fsum scalar
дал1.0; тот же FFT numerator с точнее просуммированным denominator дал
1.0000000000000002. Это ошибка накопления в реализации prefix sums, не основание
менять guard, normalization, similarity или метод. Диагностика:
results/numeric-diagnostic.json, первоначальная остановка results/stop.json.

В arc_v2.py prefix sums вычисляются компенсированным float64 суммированием.
Формула ZNCC, variance floor, clamp, search/candidate/support правила и fixtures
не изменены. Первоначальные arc.py/run.py/oracles.py, их hashes и частичные
measurements/final.jsonl не перезаписаны. Исправление и SHA новых скриптов
записаны в implementation-correction.json до полного повторного запуска.
Преддекларация не изменена. Ниже только final-v2.jsonl: все80 cases выполнены
заново; старые14 не добавляются к sample size. Результаты разных реализаций
не смешиваются. История исправления является частью owner review.

## 2. Матрица, источники и права

**45 controlled cases**, одна conservative generator lineage; **35 real/derived
cases**, пять source groups (пять originals + по шесть derivatives).
Synthetic и real статистика раздельны; derivatives, каналы и пары не независимые
источники. Generated speech/music/percussion — явно proxies. Положительная метка
означает созданное соответствие, не forged/manipulated detection.

Реальные источники повторно используются из [REFERENCES M3-TR-01/02/04](../REFERENCES.md#audio-m3r2a).
Локальные hashes проверены до использования. Новых provenance фактов/источников
нет; REFERENCES не изменён. LibriSpeech и Sorohan — CC BY4.0 с существующими
attribution/license/change notices; NPS — записанная ранее US Government provenance.
Originals и derivatives остаются с attribution во внешнем workspace, не в Git.
История лицензии Sorohan BY3/BY4 и provider MP3 сохранена без переинтерпретации.
Vibe Ace не использован. Source SHA и точные recipes/derivative SHA в manifest.

| Source group | Cases | Original SHA-256 |
|---|---:|---|
| nps-humpback-20010925 | 7 | `b2d1086dbba2fe72f6f9456d905f29a7e5db2b6087e86295fc9c897bf3cce79d` |
| libri-speaker-6930 | 7 | `9ce35224156f071ab58eb7feb8a5ceae600f6f9f353da2a6cbf797b6b1ac8a23` |
| libri-speaker-1320 | 7 | `bbe9ef85bbe228c73a414f064c9bd992c94135d73f9900b33104ad93c07d0594` |
| libri-speaker-5639 | 7 | `ecba1c65406f3d2fdfe383a22385dfe19cc117b71b126817f5e20df791f22a50` |
| sorohanro-freesound-77711 | 7 | `1aa175783edddd4db6aa0fdc26c1a0fa01dab19028c7b58eeb575eb66b1b06bf` |

В каждом real derivative использованы первые2L первого штатного M1 окна;
полный source не декодируется специально. Block нормирован для создания fixture,
а не при изменении M1. Второй block — exact, gain0.4, noise sd0.005,
MP3 round-trip96k, legitimate phrase либо word loop первыхL/4. Каждый такой
файл получен явно как derivative и заново прошёл штатный M1 producer. Source
interval, parent window, amplitude scale и derivative truth сохранены. Original
recordings могут иметь обычную editing/codec history и не сертифицированы как
подлинные. Эти пять sources недостаточны для production calibration.

## 3. Controlled results

29 cases имеют truth; overlapping truth с offset32767 при2L32768 находится
вне допустимой геометрии. Остальные **28/28** имеют representable seed/candidate,
попали в top4 union и retained64; у каждого есть выбранная пара с истинным offset.
Это case-level existence, не утверждение, что все возвращённые пары верны.
Нет population recall/sensitivity; здесь одна generated lineage и удобные
позиции truth, хотя включены +1, +137, a4096/b90112 и legal separation boundary.

Max rho ниже — максимум первой части среди candidate/channel outputs, не score.
Exact пары — хотя бы один канал имеет численно равные все2L decoded samples.
Этот счётчик не требует информативного NCC у равного канала: у stereo_silent
все64 пары имеют одинаковый нулевой канал, но это не64 подтверждённых повтора
активного канала. Exact equality и structural support читаются отдельно по каналам.
Пустое значение означает отсутствие определённого rho, не нулевой match.
Truth counts у negative равны0 и не означают measured miss rate.

| Case | Seeds | Пары | Max rho | Exact пары | Truth eligible / retained / true offset |
|---|---:|---:|---:|---:|---|
| exact | 25 | 64 | 1 | 2 | 3 / 2 / 2 |
| gain | 25 | 64 | 1 | 0 | 3 / 2 / 2 |
| noise | 25 | 64 | 0.998758 | 0 | 3 / 2 / 2 |
| speech | 25 | 64 | 1 | 2 | 3 / 2 / 2 |
| music | 25 | 64 | 1 | 1 | 3 / 1 / 1 |
| ambience | 25 | 64 | 1 | 2 | 3 / 2 / 2 |
| minimum_separation | 25 | 64 | 1 | 2 | 2 / 2 / 2 |
| just_beyond | 25 | 64 | 1 | 2 | 2 / 2 / 2 |
| shift_137 | 25 | 64 | 1 | 2 | 2 / 2 / 2 |
| late | 25 | 64 | 1 | 3 | 3 / 3 / 3 |
| overlap_truth | 25 | 64 | 0.0344397 | 0 | 0 / 0 / 0 |
| unrelated_noise | 25 | 64 | 0.03899 | 0 | 0 / 0 / 0 |
| similar_energy | 25 | 64 | 0.0356649 | 0 | 0 / 0 / 0 |
| tone | 25 | 62 | 1 | 0 | 0 / 0 / 0 |
| multitone | 25 | 62 | 1 | 0 | 0 / 0 / 0 |
| nonrepeating_speech | 25 | 58 | 0.230113 | 0 | 0 / 0 / 0 |
| nonrepeating_music | 25 | 58 | 0.478709 | 0 | 0 / 0 / 0 |
| coarse_collision | 25 | 64 | 0.0359165 | 0 | 0 / 0 / 0 |
| length_2048 | 0 | 0 | — | 0 | 0 / 0 / 0 |
| length_8192 | 0 | 0 | — | 0 | 0 / 0 / 0 |
| length_32767 | 0 | 0 | — | 0 | 0 / 0 / 0 |
| length_32768 | 1 | 0 | — | 0 | 0 / 0 / 0 |
| length_65535 | 8 | 0 | — | 0 | 0 / 0 / 0 |
| length_65536 | 9 | 1 | 0.00730047 | 0 | 0 / 0 / 0 |
| silence | 25 | 0 | — | 0 | 0 / 0 / 0 |
| constant | 25 | 64 | — | 0 | 0 / 0 / 0 |
| near_silence | 25 | 64 | 0.03899 | 0 | 0 / 0 / 0 |
| musical_loop | 25 | 64 | 1 | 39 | 2 / 1 / 1 |
| chorus_riff | 25 | 57 | 1 | 53 | 2 / 2 / 2 |
| spoken_phrase | 25 | 64 | 1 | 35 | 2 / 2 / 2 |
| syllable_word | 25 | 64 | 1 | 64 | 2 / 2 / 1 |
| alarm_beep | 25 | 64 | 1 | 64 | 2 / 1 / 1 |
| periodic_tone | 25 | 57 | 1 | 29 | 2 / 2 / 1 |
| footsteps_percussion | 25 | 64 | 1 | 64 | 2 / 2 / 1 |
| room_background | 25 | 63 | 1 | 50 | 2 / 2 / 2 |
| legitimate_production_duplicate | 25 | 63 | 1 | 50 | 2 / 2 / 2 |
| calibration_tone | 25 | 57 | 1 | 35 | 2 / 2 / 1 |
| frame_repeat_proxy | 25 | 64 | 1 | 64 | 2 / 2 / 1 |
| stereo_both | 25 | 64 | 1 | 2 | 3 / 2 / 2 |
| stereo_one | 25 | 64 | 1 | 2 | 3 / 2 / 2 |
| stereo_silent | 25 | 64 | 1 | 64 | 3 / 2 / 2 |
| stereo_order_swap | 25 | 64 | 1 | 2 | 3 / 2 / 2 |
| resource_8000 | 48 | 64 | 1 | 1 | 3 / 1 / 1 |
| resource_48000 | 256 | 64 | 1 | 3 | 3 / 3 / 3 |
| exact_codec | 25 | 64 | 0.999069 | 0 | 3 / 2 / 2 |

Exact/gain дают rho до1; noisy copy до0.998758, codec до0.999069.
Coarse collision сохраняет64 кандидата, но max rho≈0.035917; unrelated noise
≈0.038990. Support для этих false coarse matches имеет малые signed значения,
включая отрицательные. Порог отсутствует: алгоритм описывает слабое waveform
соответствие, не выдаёт бинарное reject/accept forensic решение.
В overlap fixture истинная пара запрещена; низкие scores оставшихся допустимых
пар не являются дефектом retrieval. L-boundaries дают от0 до1 admissible pair;
complete_selected_windows означает завершённую обработку, не достаточную улику.

## 4. Real / real-source-derived results

**30/30** сконструированных real-derived truth cases: representable, nominated,
retained и хотя бы одна пара на истинном offset. По одной допустимой паре в
коротких derivatives — очень лёгкий retrieval сценарий, не доказательство
поиска на больших real recordings. Пять originals не имеют экспертной разметки
повторов, поэтому их scores не превращаются в recall или false positives.

| Case | Seeds | Пары | Max rho | Exact пары | Truth eligible / retained / true offset |
|---|---:|---:|---:|---:|---|
| nps-humpback | 256 | 64 | 0.128276 | 0 | 0 / 0 / 0 |
| nps-humpback__exact | 23 | 1 | 1 | 1 | 1 / 1 / 1 |
| nps-humpback__codec | 23 | 1 | 0.99268 | 0 | 1 / 1 / 1 |
| nps-humpback__gain | 23 | 1 | 1 | 0 | 1 / 1 / 1 |
| nps-humpback__noise | 23 | 1 | 0.999465 | 0 | 1 / 1 / 1 |
| nps-humpback__legitimate_phrase | 23 | 1 | 1 | 1 | 1 / 1 / 1 |
| nps-humpback__word_loop | 23 | 1 | 1 | 1 | 1 / 1 / 1 |
| libri-6930 | 6 | 0 | — | 0 | 0 / 0 / 0 |
| libri-6930__exact | 9 | 1 | 1 | 1 | 1 / 1 / 1 |
| libri-6930__codec | 9 | 1 | 0.999854 | 0 | 1 / 1 / 1 |
| libri-6930__gain | 9 | 1 | 1 | 0 | 1 / 1 / 1 |
| libri-6930__noise | 9 | 1 | 0.99882 | 0 | 1 / 1 / 1 |
| libri-6930__legitimate_phrase | 9 | 1 | 1 | 1 | 1 / 1 / 1 |
| libri-6930__word_loop | 9 | 1 | 1 | 1 | 1 / 1 / 1 |
| libri-1320 | 17 | 42 | 0.219558 | 0 | 0 / 0 / 0 |
| libri-1320__exact | 9 | 1 | 1 | 1 | 1 / 1 / 1 |
| libri-1320__codec | 9 | 1 | 0.999406 | 0 | 1 / 1 / 1 |
| libri-1320__gain | 9 | 1 | 1 | 0 | 1 / 1 / 1 |
| libri-1320__noise | 9 | 1 | 0.99972 | 0 | 1 / 1 / 1 |
| libri-1320__legitimate_phrase | 9 | 1 | 1 | 1 | 1 / 1 / 1 |
| libri-1320__word_loop | 9 | 1 | 1 | 1 | 1 / 1 / 1 |
| libri-5639 | 54 | 64 | 0.350498 | 0 | 0 / 0 / 0 |
| libri-5639__exact | 9 | 1 | 1 | 1 | 1 / 1 / 1 |
| libri-5639__codec | 9 | 1 | 0.999351 | 0 | 1 / 1 / 1 |
| libri-5639__gain | 9 | 1 | 1 | 0 | 1 / 1 / 1 |
| libri-5639__noise | 9 | 1 | 0.998857 | 0 | 1 / 1 / 1 |
| libri-5639__legitimate_phrase | 9 | 1 | 1 | 1 | 1 / 1 / 1 |
| libri-5639__word_loop | 9 | 1 | 1 | 1 | 1 / 1 / 1 |
| sorohanro-trumpet | 36 | 64 | 0.144703 | 0 | 0 / 0 / 0 |
| sorohanro-trumpet__exact | 23 | 1 | 1 | 1 | 1 / 1 / 1 |
| sorohanro-trumpet__codec | 23 | 1 | 0.997262 | 0 | 1 / 1 / 1 |
| sorohanro-trumpet__gain | 23 | 1 | 1 | 0 | 1 / 1 / 1 |
| sorohanro-trumpet__noise | 23 | 1 | 0.999633 | 0 | 1 / 1 / 1 |
| sorohanro-trumpet__legitimate_phrase | 23 | 1 | 1 | 1 | 1 / 1 / 1 |
| sorohanro-trumpet__word_loop | 23 | 1 | 1 | 1 | 1 / 1 / 1 |

Gain0.4 сохраняет rho=1. Noise first-part rho0.998820–0.999720 (с учётом обоих
каналов); MP3 first-part rho0.992680–0.999854. Support сохранён отдельно в JSON;
для codec minimum support≈0.993998, а для noisy≈0.998087. Это наблюдения конкретной
recipe, не гарантии robust correspondence для всех codecs/noise/SNR.
В неизменённом LibriSpeech6930 окно слишком коротко для двух nonoverlap2L
seeds: нет пары, хотя созданные повторные derivatives становятся длиннее.

## 5. Легитимные повторы, abstention и неоднозначность

Проверены все13 запрошенных challenge категорий: musical loop, chorus/riff,
spoken phrase, syllable/word, alarm/beep, periodic tone, footsteps/percussion,
stationary ambience, repeated room/background, silence/near-silence,
codec-like repetition proxy, legitimate production duplicate, calibration tone.
Proxy из повторяемых1024 samples не выдаётся за подтверждённый codec defect.
Stationary ambience представлен random-noise baseline, отдельно repeated texture.
Есть14 явно benign-labelled controlled cases; taxonomy classes и cases не равны.

Loops, phrases, syllable, beep, footsteps, room texture, production duplicate и
calibration tone дают rho/support до1, в том числе exact equality. Real-derived
legitimate_phrase и word_loop также дают1. Это **benign high correspondence**,
не false-positive rate: frozen forensic decision rule отсутствует.
Полное совпадение не устанавливает монтаж, злой умысел, направление donor/copy,
личность редактора или save history. Отсутствие correspondence не аутентифицирует.

Silence исключается как неинформативный descriptor. Constant может пройти
coarse stage (periodic Hann оставляет non-DC magnitude), но64 пары получают
undefined NCC: произвольный offset/support не назначается. Near-silence с
scale1e-12 после maxabs сохраняет структуру исходного noise; numeric floor
относительный и не доказывает акустически значимую амплитуду или entropy.
Tone/multitone без inserted copy дают rho≈1 и support≈1. Всего363 пары имеют
несколько численно равных лучших lag; periodic ambiguity не устранена ties.

## 6. Localization и bounded retrieval

На допустимой truth минимум abs offset error по retained парам каждого case=0
samples:28 controlled и30 real-derived. Остальные pairs могут соответствовать
другим периодам или случайному похожему участку. Координаты истинных копий
заданы fixture recipes, а не вручную переустановлены после результата.
У real originals donor/edit truth отсутствует. Support interval2L и sample
точность offset не равны точной границе редактирования.

Каждая пара хранит source SHA, stream, sample-artifact window, channel, seed IDs,
rank, squared descriptor distances, два итоговых intervals, δ/offset, separation,
overlap=False, source PTS отдельно, три NCC и exact equality. Окна не сшиваются;
coverage описывает только observed M1 windows. Detailed truth сопоставление —
results/case-summary.json; все пары — measurements/final-v2.jsonl.
В Sorohan original50/64 пар имеют разные channel-best offsets; общий signed-mean
offset сохраняется описательно и не объявляется единым подтверждённым повтором.

| Слой | Seeds до/после cap | Уникальные descriptor/channel comparisons | Повторные distance evaluations при ranking union | NCC пары | Lag/channel evaluations | Overlap pair exclusions |
|---|---:|---:|---:|---:|---:|---:|
| controlled | 1273 / 1247 | 34955 | 3872 | 2394 | 19345626 | 10283 |
| real | 809 / 807 | 29379 | 1127 | 264 | 2175681 | 9268 |

coarse_comparisons в raw JSON считает уникальные допустимые пары/каналы;
ranking повторно вычисляет distance по доступным каналам nominated union,
поэтому фактических distance evaluations **38827 / 30506**, а не только
34955 / 29379. Ни одна dense distance matrix не создаётся; top4 streaming,
candidate bookkeeping O(K*C*4), union максимум848 в этом запуске.
Cap64 активен в28/45 controlled и3/35 real cases. Seed cap: resource48000
282→256, NPS258→256. После него потерянных **допустимых размеченных** repeats
в этой матрице нет; это не гарантия полного recall. Обрезаны другие candidates;
они не получили NCC и не называются отрицательными. Cross-window или короткий
repeat вне support, seed phase и новые dense repetitions требуют дальнейшей проверки.
50 descriptor/channel exclusions controlled;64 constant pairs с insufficient
NCC; structural support имеется у2330 controlled и264 real pairs.

## 7. Детерминизм и ресурсы

Existing focused tests: **43 passed, 563 deselected in6.09s**, exit0.
Точная команда в logs/focused-tests.json; тесты source precision/window reading,
framing/STFT/channel order, artifact identity/length/finite/bounds. Тесты не менялись.
External arithmetic: **7 oracle groups PASS**, независимый scalar math.fsum,
FFT at10lags, gain/polarity/scales, zero variance, descriptor analytic values,
top4/cap/ties/overlap. Первые oracles не покрыли cumulative multitone error;
после correction та же группа PASS, полный corpus также без numeric failure.

**12 cases ×3 exact repeats PASS**: exact,gain,noise,musical_loop,unrelated_noise,
periodic_tone,stereo_both,stereo_one,stereo_silent,stereo_order_swap,silence,
resource48000. Совпали hashes всех numerical JSON полей; wall/RSS исключены.
Это один фиксированный Python/NumPy/FFmpeg/CPU build, не cross-platform guarantee.

| Слой | Preprocessing median/max s | Coarse median/max s | NCC median/max s | Total ARC median/max s |
|---|---|---|---|---|
| controlled | 0.827012 / 2.283637 | 0.004251 / 0.104839 | 0.679728 / 1.494600 | 0.684718 / 1.600167 |
| real | 0.465637 / 6.524370 | 0.002719 / 0.100159 | 0.006779 / 2.348605 | 0.009753 / 2.364621 |

Windows11 x64, Python3.12.10, NumPy2.5.2; точный FFmpeg/platform output в
logs/measurement-start-v2.json. Таймаутов/producer resource rejection в final80
нет; previous multitone numeric failure сохранён отдельно. Общий process-lifetime
peak working set **82 096 128 bytes (78.293MiB)**, max artifacts **34 386 840 bytes**,
максимум6 artifacts. Это whole-process measurement с imports/allocator, не
per-case RSS, hard bound или certified concurrent production peak. FFmpeg child
RSS не измерен; preprocessing wall измерен отдельно. Tracemalloc не используется.
Reader/hash I/O входят в соответствующие coarse/NCC timings; это не чистые kernel
benchmarks. Последовательный process cache не сбрасывался, cold-start не заявляется.

Q≤131072, descriptors≤256KiB; одна spectrum в descriptor phase, максимум два
sample artifacts в NCC phase, остальные windows освобождаются. Компенсированные
prefix buffers bounded длинойL+8192, не full-source arrays. Аналитический план
workspace≤32MiB не превращён в измеренную hard native memory quota.

## 8. Q1–Q10, outcome и следующий owner gate

| Вопрос | Вывод |
|---|---|
| Q1: coarse retrieval восстанавливает repeats? | Да на28 допустимых controlled и30 constructed real-derived cases; source-level generalization не проверена |
| Q2: NCC/support отвергает coarse false matches? | Разделяет численно: noise collision max≈0.036 против near1 для копий; binary rejection без threshold отсутствует; constant честно undefined |
| Q3: gain/noise/codec? | Gain invariant; заданные noise/MP3 сохраняют высокую first/support NCC; robustness ограничена одной recipe на source |
| Q4: legitimate repetitions? | Loops, speech/word, beeps, percussion/background и production copies дают те же1/exact; intent не устанавливается |
| Q5: silence/tones? | Silence/constant дают abstention; periodic tone даёт1 и ambiguous lag; near-silence не абсолютный energy gate |
| Q6: localization? | Есть true-offset pair для каждой допустимой размеченной копии; periodic alternative pairs остаются, donor/edit boundary неизвестны |
| Q7: bounded misses? | В размеченном допустимом наборе не наблюдались; overlap truth исключён, crop/caps/phase/full-file recall не гарантируются |
| Q8: cap? | 28/45 controlled и3/35 real cases; seed cap у2 файлов, union до848→64 |
| Q9: архитектурные ресурсы? | Штатные inputs достаточны, final ARC wall до2.365s и measured process peak78.293MiB; native/concurrent hard bounds не сертифицированы |
| Q10: larger validation? | READY_FOR_LARGER_VALIDATION как research outcome; не production calibration и не method acceptance |

Более крупное source-level исследование оправдано арифметической проверяемостью,
bounded ресурсами и восстановлением заданных copies; forensic-селективность
этим не установлена. Нужны разнообразные naturally repeated events и matched
annotations, независимые source groups/holdout, разные seed/STFT phases,
complex cap competition, timing/codec histories и численная устойчивость.
Исходный owner gate приёмки результата и выбора следующего validation scope
закрыт решением владельца в §10. Новый threshold не разрешается self-report;
права и допустимое использование будущего corpus должны быть проверены.
Production acceptance, analyzer implementation/registration, Finding, severity,
risk/correlation и public contracts отсутствуют. Статистическая независимость ARC не установлена:
созданные copy boundaries могут причинно совпадать с transition events.
ATD/ASC NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD не изменены и не разрешены;
[Macro3 closure rule](../ROADMAP.md#audio-m3-required-carry-forward) сохраняется.

## 9. Артефакты и ограничения проверки

Research root: `C:\Users\Vanur\Desktop\FakeDetector-Work\research\M3-R2B-arc\`.
predeclaration.md + SHA JSON; implementation-correction.json; scripts и hashes;
fixtures/cases.json; provenance/reused-sources.json; logs/commands.json;
final-v2.jsonl, determinism-v2.json; results/summary.json, case-summary.json,
search-counts.json, oracles-v2.json. Исторические partial outputs/diagnostics сохранены.
Review root: `C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-R2B-arc\`:
complete.diff, review-summary.md, git-status.txt, measurement-summary.md,
resource-summary.md, provenance-summary.md. Полный intended diff включает этот
untracked report; staging не использован. Raw media/harness остаются вне Git.
Изменены только report, METHODS и ROADMAP. REFERENCES/ATD/ASC report сохранены.
git diff --check, полный diff и status проверяются при сборке bundle.
Full quality barrier и strict certification не запускались; Git mutations нет.

## 10. OWNER ACCEPTANCE — 2026-09-26

Владелец явно принял **M3-R2B: DONE / OWNER ACCEPTED RESEARCH RESULT**.
ARC-NCC-1 сохраняет **READY_FOR_LARGER_VALIDATION** исключительно как research
readiness. Это не production method acceptance, calibration, разрешение
реализации/регистрации анализатора, Finding или threshold. Измеренные результаты,
ограничения и история численного исправления выше сохранены.

Следующий разрешённый domain — **speech-dominant / voice-message audio**.
Основной вопрос на уровне распределений frozen ARC-NCC-1:
**NATURAL RE-SPEECH VS COPIED WAVEFORM**. В первом классе один человек естественно
произносит то же слово/фразу несколько раз в действительно отдельных записях/takes;
во втором повторно используется один физически записанный речевой сегмент,
в том числе с gain/codec/noise transformations в ранее разрешённом scope.
M3-R2B **не доказал** различимость этих классов. Следующий эксперимент ещё не выполнен.

Music, tones, alarms, loops, ambience и другие non-speech repeats не являются
основной calibration population следующего исследования. Они остаются важными
challenge/out-of-domain cases и документируются: высокая correspondence сама
по себе не означает suspicious manipulation. Решение сужает следующий research
question, не определяет заново весь product scope FakeDetector.

**Frozen ARC v2 принят для следующей validation:** численно исправленная
реализация, использованная для completed final run M3-R2B, `scripts/arc_v2.py`.
SHA-256: `04a2d54f0e5bc51c3eacf376cd797b16c178dd6a9740accb626cc77e92bfa625`.
Идентичности execution/oracle scripts сохранены в implementation-correction.json;
преддекларация и обе версии истории остаются доступны. Сохраняются точная формула,
compensated float64 accumulation, normalization, numerical guard, descriptor,
retrieval/search bounds, candidate caps, overlap exclusions, support rules,
tie behavior и channel behavior. После будущих outcomes их нельзя подстраивать.

Следующая validation — source-level, с speaker/source grouping. Концептуальные
классы: same speaker/same phrase/independent natural takes; same speaker/copied
physical waveform; different phrase controls; different speaker controls, где
полезно; copied segment с разрешёнными transformations; natural pauses/breaths/
repeated short words; background music/TV/tone/ambience challenges. Копии и
time-shifted derivatives не являются natural re-speech takes. Производные одной
записи не независимые source trials. Если позднее появятся calibration/validation/
holdout splits, speaker/source groups не должны попадать в разные splits.

**Production calibration NOT AUTHORIZED.** Следующий эксперимент может сравнить
распределения и их разделимость, но observed gap не становится production rho
или descriptor threshold без отдельного последующего явного owner gate. Severity,
Finding type, suspicious/not-suspicious decision и risk contribution не разрешены.
Production analyzer implementation/registration не разрешены. Новые источники
по-прежнему требуют проверки прав и intended use до использования.

ATD-LOCAL-1 и ASC-TV-1 сохраняют **NEEDS_TARGETED_RESEARCH / REQUIRED CARRY-FORWARD**;
оба обязательства не разрешены. ARC progress не закрывает Macro 3:
**IN_PROGRESS**, [условие закрытия](../ROADMAP.md#audio-m3-required-carry-forward)
сохранено. В этой записи приёмки нет новых экспериментов или тестов.
Запись решения и обновлённый полный intended diff проверены владельцем;
staging/commit остаются владельцу.
