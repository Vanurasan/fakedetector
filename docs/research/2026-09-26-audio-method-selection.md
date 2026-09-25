# M3-R1 — отбор классических аудиометодов и семейств свидетельств

Дата исследования: 2026-09-26. Baseline: `1acaf4f9129d5b36c6c69a6ab6250e49e2da4d09`,
ветка `feat/stage12-macro3-audio-analyzer-expansion-wave1`; начальное дерево чистое.
Текущий статус: **DONE / OWNER ACCEPTED RESEARCH SELECTION**; явное решение
владельца от 2026-09-26 и границы допуска измерений записаны в §12.
Разделы 1–10 сохраняют исходные исследовательские наблюдения и рекомендации M3-R1;
их readiness не является экспериментальным результатом или production acceptance.
Это исследовательское
свидетельство по политике [README](README.md), не production-спецификация.
Имена кандидатов и профилей ниже не являются analyzer IDs. Числа в профилях —
предложения фиксированного измерительного протокола и ограничений, не пороги подозрения.

## 1. Вывод и пределы исследования

Рекомендуются **два** будущих measurement-only трека: сравнение локальных переходов
и соответствие повторяющихся фрагментов. В первом temporal и spectral измерения
сохраняются раздельно для анализа, но относятся к одному предложенному семейству.
Наличие пригодной формулы означает готовность проверить измерение, а не доказанную
forensic-селективность. Production-метод, thresholds, severity и Finding types не выбраны.

| Рабочий кандидат | Предлагаемый профиль | Readiness | Существующих inputs достаточно | Предложенное семейство |
|---|---|---|---|---|
| `audio_temporal_discontinuity` | ATD-LOCAL-1 | READY_FOR_MEASUREMENT_PROTOTYPE | YES, в узком покрытии §3 | локальные переходы |
| `audio_spectral_consistency` | ASC-TV-1 | READY_FOR_MEASUREMENT_PROTOTYPE | YES, в узком покрытии §3 | локальные переходы |
| `audio_background_noise_consistency` | ABN-FLOOR-1 | RESEARCH_ONLY / WEAK_SIGNAL | YES для описательной статистики; NO для доказанного выделения фона | локальные переходы, не отдельное свидетельство |
| `audio_repeated_segment_correspondence` | ARC-NCC-1 | READY_FOR_MEASUREMENT_PROTOTYPE | YES, только выбранные окна | повторное соответствие |
| `audio_metadata_container_consistency` | AMC-RESP-1 | REJECT_DUPLICATE_RESPONSIBILITY | YES для проверки пересечения обязанностей; NO для новых структурных утверждений | отдельное forensic-семейство не обосновано |

Внешнее исследование выполнено по оригинальным статьям и официальной документации.
Provenance и границы лицензий: [REFERENCES, M3-R1](../REFERENCES.md#audio-m3r1).
Микроэксперименты, загрузка корпусов и калибровка не выполнялись. Ни один численный
результат эффективности/FPR здесь не получен. Аналитические контрпримеры отделены
от будущих экспериментальных проверок. Windows 11 x64 / Python 3.12, CPU, offline
совместимы с предлагаемой арифметикой NumPy; скорость и RSS ещё предстоит измерить.

## 2. Проверенные возможности и границы обязанностей

Прочитаны `AGENTS.md`, релевантные архитектура/инварианты/качество `PROJECT.md`,
текущее состояние Stage 12 и M1-D/E/F `ROADMAP.md`, §§6–8, 11.4 `CONTRACTS.md`,
gate и шаблон `METHODS.md`, политика `REFERENCES.md`, `research/README.md`.
Graphify использован только для навигации: graph provenance SHA
`625b9e83f133fb0ae31a4b90e9e1288bff96f69c` не совпадает с baseline, значит **STALE**.
Пересборки не было; утверждения ниже проверены непосредственно по исходникам.

| Факт | Проверенное свидетельство на baseline | Следствие для M3 |
|---|---|---|
| Закрытый каталог содержит ровно пять анализаторов | `src/fakedetector/analyzers/_catalog.py`, `_BUILT_IN_ANALYZER_DEFINITIONS`; `tests/test_analyzer_registry.py` | Три image: metadata, copy-move, JPEG DQ; один audio PCM quality; один video sampled-frame quality; все `1.0.0` |
| `AudioPrecisionFacts`, `AudioWindowDescriptor`, `SpectralWindowDescriptor` | `preprocessing/_models.py`, соответствующие классы; `tests/test_stage5_internal_models.py` | Source declarations отделены от decoder observations; факт разрядности не равен effective bit depth |
| Отбор и декодирование bounded окон | `preprocessing/_media_tools.py::select_audio_windows`, `decode_audio_window`; `_service.py::_prepare_audio_forensic` | Начало/середина/конец по declared duration, максимум 3 окна, каждое до 10 s и `2^20` sample-channel значений |
| Фактическое покрытие и точность | `test_window_values_and_coverage_match_source`, `test_audio_producer_retains_incomplete_requested_coverage`, `test_u8_centering_and_high_rate`, `test_truncated_source_is_not_padded` в `tests/test_preprocessing.py` | Использовать `samples` и observed PTS, а не requested seek; нет padding, forced resample/downmix; `<i4` right-aligned / `<f8` |
| Общие framing/STFT kernels | `_media_tools.py::frame_audio`, `periodic_hann`, `stft_batches`; `test_frames`, `test_fft_dc_sine_multichannel_deterministic`, `test_spectral_resource_and_finite_output` | Фреймы без centering/padding; periodic Hann; независимые каналы; finite checks |
| Demand `audio_spectral` | `_service.py::_prepare_audio_forensic`; `test_dispatcher_numeric_audio_demand` | `hann4096_hop1024/1`, magnitude, batch 16; FFT ≤4096, hop ≥FFT/4, всего ≤8192 time/channel frames |
| M1-E timing | `_media_tools.py` timing producer; `test_timing_only_dispatch_never_decodes_precision_audio_and_legacy_unchanged` | Signed PTS/DTS, rational time base, bounded packet rows; audio decoded-frame rows этим producer **не создаются** |
| M1-F A/V | `CONTRACTS.md` §7.5; `_models.py::AVTimelineDescriptor`, `tests/test_stage5_internal_models.py::test_av_mapping_missing_streams_are_explicit` | Региональные endpoints и unknown/coverage; не sample-to-packet mapping и не доказательство непрерывности |
| Intake validation | `intake/validation.py::FileValidator.validate`, `_safe_read`, `_resolve_detected_format`; `intake/media_tools.py::FFmpegMediaInspector`, `audio_parameters` | Allowlist, extension/MIME/signature/container, обязательные duration/rate/channels/codec, bounded decode; rejection/error не Finding |
| M4A с обложкой | `tests/test_file_validator.py::test_m4a_with_attached_cover_is_accepted_as_audio` | Attached picture не превращает аудио в подозрительный video container |
| Metadata-анализатор | `analyzers/_image_metadata.py::ImageMetadataConsistencyAnalyzer` | Только image, сравнение EXIF размеров с decoded dimensions; универсального audio metadata-анализатора нет |

Пути `preprocessing/`, `intake/`, `analyzers/` в таблице относительны
`src/fakedetector/`. Перечисленные тесты **прочитаны**, заново не запускались.

### 2.1. Точное пересечение с `audio_pcm_quality@1.0.0`

`analyzers/_audio_pcm.py::_read_pcm_stats` читает legacy signed-16 WAV блоками
4096 frames; считает по всем scalar samples каналов peak, RMS, абсолютный DC,
digital silence ratio и full-scale ratio. `analyze` проверяет saturation каждого
fragment, выбирает до 16 по ratio/time/ID и создаёт `audio_full_scale_saturation`
в `audio_signal_quality`. Действующая настройка threshold `0.001` здесь только
описана как baseline, не предложена заново. Тесты в
`tests/test_stage6_real_analyzers.py` проверяют silence, крайние PCM16 значения,
stereo scalar semantics, точную границу threshold, top-16 и bounded чтение.

Новые предложения используют RMS лишь как локальный контекст сравнения двух сторон.
Повторно сообщать saturation/clipping/peak/DC/silence как новую forensic-улику нельзя.
Clipping способен вызвать одновременно текущую quality observation и ATD/ASC response:
это зависимость причин, которую нужно проверить, а не объявить независимым голосом.
Текущие analyzer, настройки, Findings и группы не изменяются.

## 3. Общие условия измерительных профилей

ATD/ASC/ARC предлагаются сначала для audio route, WAV/FLAC/MP3/M4A после intake,
первого выбранного audio stream, `8000 ≤ fs ≤ 48000`, 1 или 2 канала.
Это намеренно уже M1 envelope 192 kHz / 8 channels; видео и остальные rate/channel
профили — `not_applicable` исследовательскому протоколу. Расширение не выполняется
через resample или downmix. Lossy codec входит в challenge-страты, не исключается
молча; одинаковый результат между разными декодерами заранее не гарантируется.

Inputs — source-bound manifest, precision facts, фактические sample windows через
controlled numeric reader; ASC/ARC также готовые magnitude spectra 4096/1024.
Нет чтения исходного файла анализатором, собственного probe, второго decode или
самодельного STFT. Другой spectral descriptor не угадывается: профиль неприменим.
ATD переиспользует `frame_audio` на существующих samples. ARC использует готовую
STFT для отбора и waveform NCC для проверки; FFT свёртки NCC не является новым
STFT-представлением и не меняет профиль producer.

Покрытие — объединение фактических `[samples.start, samples.stop)`; разрывы между
артефактами не сшиваются. У каждого измерения сохраняются stream/channel, оба
интервала поддержки и исключённые края. Доля покрытия относительно declared duration
имеет пометку «знаменатель заявлен», не подменяет полную наблюдаемую длительность.
Локальное время `n/fs` относится к sample timeline; исходное PTS-время внутри окна
вычисляется как `(first_sample_pts + local_index)/fs`, отдельно. Отрицательный PTS
не обрезается до нуля; исследовательские координаты не изменяют public Localization.

Вычисления float64, без округления входных integer codes до PCM16. До квадратов,
разностей и NCC каждый используемый блок делится на его `max(abs(x))`; для сравнения
уровней слева/справа масштаб общий на обе стороны. Это арифметическая стабилизация,
а не изменение артефакта и не dBFS-калибровка. Нулевой блок отмечается отдельно.
Значения `<f8` вне `[-1,1]` допустимы; finite input, finite output и отсутствие
overflow обязательны. Нулевой знаменатель → неопределённое измерение с причиной,
не бесконечная подозрительность. Для численно вырожденных NCC см. §7.

Медиана чётного набора — среднее двух центральных значений после стабильной сортировки;
квантили отчётности — nearest rank `x[ceil(p*m)-1]` для `m>0`. Порядок обхода:
stream, start sample, channel, index; ties разрешаются меньшим sample index.
Никаких случайных seeds, обучаемых параметров или адаптивного threshold tuning.
Повторяемость ожидается на фиксированных Python/NumPy/FFmpeg build и CPU;
межплатформенная побитовая идентичность FFT не заявляется.

`not_applicable` означает выход за измерительный профиль; `insufficient_evidence`
означает допустимые inputs, но недостаточное покрытие/поддержку/контраст.
Это исследовательские причины, не новые AnalyzerStatus enum. Повреждение артефакта,
ошибка manifest/decoder, timeout и budget failure остаются техническими ошибками;
их нельзя переименовать в отсутствие forensic-сигнала. При исчерпании времени
результат маркируется незавершённым с фактическим покрытием.

## 4. ATD-LOCAL-1 — локальная временная неоднородность

**Рабочий кандидат:** `audio_temporal_discontinuity`.
**Принятие:** CANDIDATE / METHOD NOT YET ACCEPTED.
**Readiness:** READY_FOR_MEASUREMENT_PROTOTYPE. **Вопрос:** где внутри наблюдавшихся
окон waveform имеет локально резкий переход относительно соседних samples?

### Точное предлагаемое измерение

1. На каждом канале `frame_audio(frame_length=2048, hop=512)`, только полные
   фреймы. Размер контекста 256 ms при 8 kHz, 42.67 ms при 48 kHz; hop 64/10.67 ms.
2. В фрейме с началом `a` рассматриваются границы `b=a+768,...,a+1279`.
   Выбирается `b*`, максимизирующая `abs(x[b]-x[b-1])`; при равенстве — первая.
   Это отбор позиции измерения, не правило обнаружения монтажа.
3. Стороны `L=x[b*-512:b*]`, `R=x[b*:b*+512]`. Их общий масштаб — §3.
   Пусть `j=abs(R[0]-L[-1])`, `d` — медиана абсолютных первых разностей внутри
   L и R, **без** соединяющей разности. Записать `J=j/(j+d)`.
4. `rL=sqrt(mean(L²))`, `rR=sqrt(mean(R²))`; записать
   `E=abs(rR-rL)/(rR+rL)` и signed `Es=(rR-rL)/(rR+rL)`.
5. `mL=median(L)`, `mR=median(R)`, `sL=median(abs(L-mL))`, аналогично `sR`;
   `A=abs(mR-mL)/(abs(mR-mL)+sL+sR)`. MAD здесь не называется шумом.
6. Zero-crossing count можно сохранять только как контекст:
   доля `x[i]*x[i-1]<0` внутри каждой стороны (считать по знакам, без произведения);
   zeros не являются crossings. Он не входит в J/E/A и не определяет readiness.

J/E/A находятся в `[0,1]`, Es в `[-1,1]` для определённых значений. Нет суммы,
весов или общего forensic-score. Нулевые знаменатели и число таких случаев
сохраняются явно. Постоянный ненулевой блок: E=0, J/A неопределённы; цифровая тишина:
все три неопределённы. Silence-to-sound даёт E=1 и может быть полностью доброкачественна.

**Агрегация:** отдельно по окну/каналу/метрике count, median, p95, max; до 16
позиций на метрику в исследовательском отчёте по убыванию значения, ties по времени.
Ни top-16, ни максимум не называются обнаруженными edits. Каналы не усредняются.
**Покрытие/локализация:** каждый b* — sample-position математической разности,
с поддержкой `[b*-512,b*+512)`, не доказанная граница монтажа. Первые 768 и конечные
непокрытые samples не проверены как центры; все интервалы кандидатов выводятся точно.
Короткое окно без полного 2048 frame → insufficient evidence; один frame даёт
одну локальную оценку и не даёт распределения по записи.

**Положительная интерпретация:** локальный переход уровня/амплитуды/первой разности.
**Не доказывает:** splice, синтез, злой умысел, подлинность при отсутствии response,
инструмент, автора, время и количество сохранений.
**Benign/challenge:** естественные transients, перкуссия, plosives, silence boundaries,
clipping, fades, mastering/dynamic compression, packet-loss concealment, codec/frame
effects, gain changes. Аналитический контрпример: одинаковая последовательность
samples может быть намеренно синтезированным click или соединением двух записей;
любая детерминированная функция samples даст одинаковые J/E/A.

**Ресурсы:** `O(C*N + B*C*512*log(512))` при сортировке для медиан, B число фреймов;
до 3×934×2=5604 frame-channel измерений при 48 kHz/10 s. Последовательные фреймы,
≤32 MiB дополнительной рабочей памяти, без копии всей framed матрицы.
**Validation:** §9, ATD-колонка. **References:** M3-AUD-01, M3-AUD-02, M3-AUD-03.
Комбинация J/E/A и параметры — собственное исследовательское предложение FakeDetector,
не воспроизведение опубликованного forensic detector. **Gates:** G1, G2, G5, G6 (§10).

## 5. ASC-TV-1 — изменение спектрального распределения

**Рабочий кандидат:** `audio_spectral_consistency`.
**Принятие:** CANDIDATE / METHOD NOT YET ACCEPTED.
**Readiness:** READY_FOR_MEASUREMENT_PROTOTYPE. **Вопрос:** насколько различается
форма спектра и положительный прирост magnitude в соседнем локальном контексте?

Для готового `M[j,c,k] ≥ 0`, `k=0..2048`, сохраняется семантика Macro 1:
periodic Hann 4096, hop 1024, backward rFFT без amplitude/PSD correction.
Размер frame — 512/85.33 ms, hop — 128/21.33 ms при 8/48 kHz соответственно.
Низкий fs означает грубую локализацию; это обязательная страта будущей проверки.

Для пар `(j,j+h)`, отдельно `h=1` (перекрывающиеся) и `h=4` (неперекрывающиеся),
оба frames должны принадлежать одному sample artifact и одному каналу.
Для каждой пары разделить обе magnitude строки на их общий максимум до суммирования.
Пусть `s_j=sum_k M[j,k]`, `p_j[k]=M[j,k]/s_j`. При любом `s=0` TV неопределена.
Измерение формы — total variation:

`D_h(j) = 0.5 * sum_k abs(p_(j+h)[k] - p_j[k])`.

Второе, отдельное измерение положительного magnitude change:

`F_h(j) = sum_k max(M[j+h,k]-M[j,k], 0) / (s_(j+h)+s_j)`.

Обе величины в `[0,1]`; denominator=0 означает неопределённость. F допускает один
нулевой frame с явным silence marker. D не равна вероятности и не является PSD.
Нормализация D инвариантна к положительному gain каждого frame, но не к изменению
смеси источников, EQ или denoising. F сохраняет чувствительность к уровню.
L1 half-wave spectral flux имеет опубликованное основание (M3-AUD-02, §2.1);
TV-нормализация, второй лаг и bounded отчётность — собственный профиль.

Raw flux не выбран единственным измерением из-за зависимости от уровня.
Log-spectrum distance потребовала бы произвольного floor и сильнее зависела бы от
тихих bins; здесь она не добавляется. Полосные медианы рассматриваются в ABN.
Phase/complex novelty не используется: demand выдаёт magnitude, не phase; наличие
общего kernel с complex output не означает наличие готового complex artifact.

**Агрегация:** отдельно D1/D4/F1/F4 и каждый канал/окно: count, median, p95, max,
до 16 максимальных позиций на метрику; ни weighted fusion, ни решение о Finding.
**Локализация:** объединённая поддержка `[j*1024,(j+h)*1024+4096)` плюс sample start;
не single-sample cut. При h=1 общие samples делают measurements зависимыми.
При менее 2 frames нет adjacent comparison, менее 5 нет h=4; обе причины явные.

**Положительная интерпретация:** спектральное распределение/уровень меняется.
**Не доказывает:** редактирование или тип генерации; постоянный спектр не удостоверяет
непрерывную историю. **Benign/challenge:** фонемы, смена нот/инструмента, перкуссия,
EQ, compression, denoising, lossy codec, silence, bandwidth changes, sample-rate
conversion в истории файла и легитимная смена сцены. Прежний resample не выводится
из одного D. ATD и ASC могут отвечать на один click; большой D при неизменном RMS
даёт дополнительное описание, но не доказывает независимость причины.

**Ресурсы:** `O(F*C*2049)`, две фиксированные величины h; input artifacts ≤64 MiB
каждый по M1 и общий generated budget; ≤32 MiB дополнительного workspace при
обработке строками. Нет второго STFT. **Validation:** §9, ASC-колонка.
**References:** M3-AUD-01/02/03, M3-AUD-09. **Gates:** G1, G2, G5, G6.

## 6. ABN-FLOOR-1 — описательный нижний спектральный уровень

**Рабочий кандидат:** `audio_background_noise_consistency`.
**Принятие:** CANDIDATE / METHOD NOT YET ACCEPTED.
**Readiness:** RESEARCH_ONLY / WEAK_SIGNAL. **Вопрос:** сохраняется ли различие
низкоэнергетических spectral descriptors при сопоставимом содержании и фоне?

Изучены локальная оценка уровня шума Pan et al. (M3-AUD-04; доступен индексированный
abstract, полный текст через основной URL вернул 403), minimum statistics Martin
(M3-AUD-05) и environmental signature Zhao et al. (M3-AUD-06). Последняя работа
использует обучаемую модель clean speech/GMM: это не разрешённый non-ML pipeline.
Удаление обучаемой части не сохраняет валидность исходного метода. Minimum statistics
требует smoothing/bias assumptions; произвольный квантиль спектра не становится
несмещённой оценкой noise PSD. Опубликованные accuracy здесь не переносятся.

### Ограниченный диагностический профиль, не рекомендованный трек

Inputs и применимость §3, готовый M1 magnitude. Для каждой пары неперекрывающихся
контекстов длительностью `T=2*fs` samples, границы `b=T,T+fs,...,N-T` в каждом
окне/канале: слева `[b-T,b)`, справа `[b,b+T)`. Включать только STFT frames,
**целиком** попавшие в соответствующую сторону. Не менее 8 frames на сторону.
Масштаб M общий максимум двух сторон; `P=M²` после масштабирования.

Ранжировать frames по `sum(P)` с tie по ordinal; взять ровно
`r=max(4,ceil(n/5))` самых тихих на каждой стороне. Это low-energy selection,
не VAD и не доказательство отсутствия речи/музыки. Разбить bins 1..2048 на 16
равных полос по 128 bins (DC отдельно исключён). В каждом выбранном frame считать
среднее P в полосе, затем медиану выбранных frames: вектор `v_side[16]`.
Сохранять `level_side=sum(v_side)` и TV между `v_side/level_side`, если оба уровня
положительны; отдельно signed normalized level change, как E в §4 без sqrt.
Числа описывают низкоэнергетический спектр, не sensor noise и не microphone ID.

**Matching обязателен до forensic-интерпретации.** Для будущего исследования нужны
независимые от измеряемого v метки «тот же background-only материал / сравнимое
содержание», из controlled mixture ground truth или ручной аннотации с проверкой.
Нельзя выбирать matched пары по близости самого v и затем выдавать исчезновение
различия за доказанную устойчивость. Сравнить unmatched/matched strata, отдельно
одинаковый foreground с разным background и наоборот. Если matching устраняет
различие, фиксируется отрицательный результат. В продукте таких меток сейчас нет;
low-energy selection эту недостающую информацию не восстанавливает.

**Покрытие:** только обе 2 s стороны; localization — эти интервалы, не найденный
cut. Мало frames, нулевой уровень, masking или отсутствие независимого matching →
insufficient evidence для вывода о фоне. **Агрегация:** отдельные описательные
векторы/TV/уровни, count и matched/unmatched strata; без score и выводов о подлинности.
**Benign/challenge:** речь/музыка маскируют фон; смена комнаты и движущийся микрофон,
AGC, suppression, denoising, compression, codec, нестационарная улица и легитимные
cuts между помещениями меняют v. Стационарность — проверяемое условие, не default.
**Что не доказано:** content-invariant noise measurement и уникальность источника.

**Ресурсы:** ≤7 контекстных пар на 10 s окно; обработка по одному каналу и паре,
`O(F*C*2049 + B*C*F*log F)` с фиксированным B, workspace ≤32 MiB.
**Validation:** если владелец отдельно возобновит исследование — матрица §9 плюс
factorial foreground/background и matching ablation; сейчас этот трек не рекомендован.
Positive controlled: тот же foreground с известным переключением добавленного фона;
negative: неизменные foreground и фон. Boundary: ровно 8 frames/сторону, 4 s ±1 sample;
not-applicable: общий scope §3; insufficient: masking, нули, нет matching labels.
Determinism: повторный отбор тихих frames при ties; resource/failure: максимальное
покрытие, nonfinite/budget/timeout, как для ASC. Это не проведённый noise benchmark.
**References:** M3-AUD-04/05/06; формула floor — собственная exploratory эвристика.
**Gates:** G1/G2 и G5 (если нужен продуктовый typed mask), G6 для реальных аннотаций.

## 7. ARC-NCC-1 — ограниченное соответствие повторяющихся сегментов

**Рабочий кандидат:** `audio_repeated_segment_correspondence`.
**Принятие:** CANDIDATE / METHOD NOT YET ACCEPTED.
**Readiness:** READY_FOR_MEASUREMENT_PROTOTYPE. **Вопрос:** есть ли две разнесённые
области с близкой waveform-структурой при одном временном смещении?

NCC (M3-AUD-07) даёт проверяемую математическую меру; fingerprint retrieval
(M3-AUD-08) объясняет отбор кандидатов/согласование offsets, но не forensic intent.
Ни код Shazam, ни его полный алгоритм не предлагаются. Autocorrelation всего файла
и full-duration all-pairs отвергнуты из-за ресурса и господства периодических сигналов.

### Предлагаемый фиксированный протокол

1. `H=1024`, `L=H*ceil(fs/H)` samples (примерно 1 s), шаг seeds `4H=4096`.
   В каждом M1 sample window seed a — кратный 4096 локальный индекс, для которого
   `[a,a+2L)` целиком доступен. Ширина 2L оставляет вторую секунду для support check.
   Все seeds упорядочены по абсолютному sample index; если их U>256, оставить
   индексы `floor(i*(U-1)/255)`, i=0..255. Это явное сокращение recall, без
   content-dependent пересэмплирования и без повторного decode. K≤256 на файл,
   общие seed positions для каналов.
2. Descriptor первой части `[a,a+L)`: готовые STFT frames, целиком внутри неё;
   ≥4 frames обязательно. M делится на максимум внутри сегмента/канала; затем
   сумма magnitude в каждой из 16 полос bins 1..2048 (128 bins/полосу), DC исключён.
   Разбить упорядоченные frames на четыре последовательные группы с границами
   `floor(t*F/4)`, t=0..4; взять среднее полосных сумм в каждой. Получить 64 числа,
   разделить на их L2 norm. Нулевой norm → seed неинформативен в этом канале.
3. Для пары seeds одного канала с непересекающимися `[a,a+2L)` и `[b,b+2L)`
   считать squared Euclidean distance descriptor. На seed/канал оставить 4
   ближайших, ties по b; объединить неориентированные пары. Затем оставить 64
   пары на файл по минимуму distance среди доступных каналов, ties по a,b.
   Для stereo каналы не перемешивать. Это bounded `K*(K-1)/2 ≤32640` пар на канал,
   **не** `O(N²)` сравнение полной записи. Ни одной dense N×N waveform матрицы.
4. Ориентировать пару a<b. Сдвигать второй seed на целые `δ∈[-4096,4096]`;
   допустимы только δ, при которых `[b+δ,b+δ+2L)` целиком в его M1 окне и не
   пересекает `[a,a+2L)`. Если δ нет — insufficient support для этой пары.
5. Для каждого канала и допустимого δ на первой части длины L измерить ZNCC:
   `rho_c(δ)=sum((x-mean(x))*(yδ-mean(yδ)))/sqrt(sum((x-mean(x))²)*sum((yδ-mean(yδ))²))`.
   Нормировать x и весь доступный search buffer y на их отдельные maxabs до
   центровки; это сохраняет математическую NCC. Если variance sum ≤`64*eps*L`
   после масштабирования, считать lag численно неинформативным (`eps=2^-52`).
   Это floor численной устойчивости, не similarity/forensic threshold.
6. Для bounded вычисления числителя допустима NumPy FFT-свёртка **развёрнутого**
   центрированного x с y (linear correlation), с zero extension **только рабочих
   массивов свёртки**; знаменатели из
   prefix sums y/y². Исходное аудио не дополняется нулями. FFT length — наименьшая
   степень 2 не меньше `2L+8192-1`, максимум 131072. Никакой circular correlation.
   Для отрицательной variance в пределах того же roundoff floor — undefined;
   существенно отрицательная/nonfinite — numeric failure. NCC вне `[-1,1]` более
   чем на `64*eps` → numeric failure, в пределах — clamp только roundoff.
7. Выбрать общий δ*, максимизирующий среднее signed rho по информативным каналам
   (не abs rho), ties: меньший abs δ, затем меньший δ. Silent channel не голосует;
   его отсутствие поддержки явно записывается. Сохранить rho отдельно по каналам.
   Stereo с разными лучшими offsets не объявляется единым подтверждённым повтором.
   Если нет ни одного определённого rho ни на одном lag, δ* не назначается:
   пара имеет insufficient evidence, проверки на произвольном offset не выполняются.
8. На **том же** δ* измерить rho независимо в первой и второй половинах
   следующей части `[a+L,a+2L)`, то есть два неперекрывающихся support блока
   длины `L/2` (L кратно 1024). Нужны оба определённых значения хотя бы одного
   и того же канала: minimum structural support — 2L samples и общий offset.
   Не выбирать новый δ по support и не подстраивать длину. Порог rho для
   «достаточного сходства» **не выбран**; выдаются все три значения и причины gaps.
   Для support применяется та же centered NCC, со своим maxabs для каждого блока
   и variance floor `64*eps*m`, где `m=L/2`; нулевой maxabs означает undefined.
9. На допустимом δ* отдельно проверить числовое равенство исходных samples
   на полном 2L и каждому каналу, без gain/centering. Равные decoded samples
   означают exact decoded correspondence, не одинаковый encoded bitstream;
   float +0/-0 численно равны. Высокая NCC без exact equality — near-correspondence
   measurement, не классификация copy. Отрицательная rho (polarity reversal)
   записывается, но данный positive-NCC поиск не гарантирует её обнаружение.

**Агрегация:** до 64 пар со всеми channel/support measurements; без суммирования
как независимых свидетельств. Перекрывающиеся пары с общим offset могут описывать
один повтор; в прототипе сохранять их связь по координатам, не создавать новые votes.
До 64 кандидатов — лимит вычисления, не minimum forensic similarity. Полная
локализация — два `[a,a+2L)` / `[b+δ*,b+δ*+2L)` интервала и offset, точность одного
decoded sample; это точность соответствия, не установленное место copy/paste.

**Exact/near:** протокол не гарантирует recall всех exact copies: coarse descriptor,
seed cap, смещение STFT phase, короткая вставка или copy вне M1 окон могут скрыть
даже точный повтор. Не поддерживаются time stretch/pitch shift, channel permutation,
изменение sample rate между копиями; EQ/codec/recompression ухудшают NCC.
В M3-R2 нужен отдельный отчёт потерь на каждом этапе, а не только точность NCC
на заранее известных парах. Structural support не доказывает энтропию сигнала.

**Benign/challenge:** музыкальные loops/choruses, повторная речь, tones, silence,
alarms, ambience, repeated codec frames, намеренно зацикленные записи. Константа
даёт undefined NCC; тон может давать rho≈1 при многих δ и остаётся неоднозначным.
Копия сложного шумового фрагмента может поддерживать гипотезу общего материала,
но легитимный loop даст тот же результат. Рекомендованная будущая формулировка:
«В проверенных областях наблюдается повторное соответствие аудиоструктуры;
оно может возникать при копировании или обычном повторении материала».
Ни malicious editing, ни авторство/направление копирования из этого не следуют.

**Ресурсы:** `O(F*C*2049 + K²*C*64 + 64*C*Q*log Q)`, K≤256, C≤2, Q≤131072.
Дескрипторы ≤256×2×64×8=256 KiB; без dense distance matrix, отбор streaming top-k.
Одна пара/канал и его FFT workspace за раз, план ≤32 MiB дополнительной памяти;
не держать сразу все spectra/windows: максимум два sample artifacts и один spectrum
при соответствующей фазе, освобождение между фазами. Это не измеренная RSS гарантия.
Будущий harness проверяет время до каждой пары и не превышает remaining budget
и 30 s измерительной фазы; незавершение явно отражается. Лимиты producer не расширяются.
**Validation:** §9, ARC-колонка. **References:** M3-AUD-07/08, существующий NumPy stack.
Descriptor/search/support protocol — собственное предложение, implementation отсутствует.
**Gates:** G1, G3, G5, G6; никаких новых библиотек не требуется.

## 8. AMC-RESP-1 — проверка дублирования ответственности

**Рабочий кандидат:** `audio_metadata_container_consistency`.
**Принятие:** CANDIDATE / METHOD NOT YET ACCEPTED.
**Readiness:** REJECT_DUPLICATE_RESPONSIBILITY. Это профиль анализа обязанностей,
не исполнимая forensic-методика. Отдельное production-worthy свидетельство в
проверенных текущих facts не установлено; нет основания добавлять шестой analyzer.

| Предлагаемое сравнение | Вход/точное наблюдение | Почему не отдельный forensic Finding |
|---|---|---|
| Extension/declared MIME/signature/container | Равенство разрешённой строки format matrix | Уже Stage 3; отсутствие declared MIME не ошибка |
| Parse/decode успех, duration/rate/channels/codec | Обязательные параметры и bounded safe read | Уже intake/preprocessing; повреждённый файл или timeout не подозрительная улика |
| Declared rate/channels против decoded | Equality в AudioPrecisionFacts и producer observations | Контракт инварианта M1-D; mismatch является техническим отказом |
| Source bits против decoder width | Разные семантические величины, простое `!=` невалидно | PCM24 в s32, float decoder после lossy codec — нормальны; M3-AUD-10 |
| Declared duration против packet endpoints | Разность рациональных значений можно измерить лишь на известном покрытии | M1-E ограничен, timestamps могут быть неизвестны; seek, rounding, priming/padding и edits контейнера не равны подделке; M3-AUD-09/11 |
| PTS/DTS discontinuity | Разность соседних известных packet ticks с отдельно известной duration | Не waveform edit и не гарантия sample gap; M1-D discontinuous decode не создаёт пригодное окно |
| Software/time tags, отсутствие metadata | Текущая audio projection не содержит произвольных tags | Provenance не verdict; отсутствие optional metadata не улика |

**Узкая допустимая часть:** техническая диагностика объявленных и наблюдаемых
фактов там, где они семантически сравнимы и уже валидируются; не новый analyzer.
Для valid-but-unusual RIFF/BWF chunks, conflicting edit lists или битстримной истории
понадобились бы новые typed facts и самостоятельный метод. Они не извлечены и
не рекомендуются в этом инкременте. Image metadata-анализатор не выполняет audio
проверку, но наличие аналогии с EXIF dimensions само по себе не обосновывает её.

**Применимость/покрытие:** только факты текущих validation/M1 окон и packet regions;
полное сканирование контейнера отсутствует. **Insufficient:** unknown поля и
неполное покрытие не дают contradiction. **Positive interpretation:** техническое
расхождение требует диагностики, а не вывода об edit intent. **Локализация:**
новая forensic-localization неприменима. **Агрегация/thresholds:** отсутствуют.
**Ресурсы:** bounded сравнение существующих скалярных фактов/≤4608 timing rows,
не повторное чтение всего контейнера. **Validation:** будущая проверка решения G4
на valid PCM24/s32, неизвестных bits, AAC priming, M4A cover, signed/unknown PTS,
truncated input, probe timeout; ожидание — факты/ошибки, никогда новые Findings.
Positive для аудита обязанностей — заведомый extension/MIME mismatch и нарушение
decoded invariant, negative — согласованные поля; benign — перечисленные valid
форматы. Boundary — отсутствующее поле/нулевое значение/граница record budget;
not-applicable — чужой media route; insufficient — unknown ticks/неполное coverage.
Determinism — повтор сравнения одинаковых typed facts; resource/failure — capped
probe и timeout с прежней семантикой ошибки. Forensic-positive класса здесь нет.
**References:** M3-AUD-09/10/11 и локальные свидетельства §2. **Gate:** G4, при
возврате к структурным методам G5/G6; сейчас прототип не рекомендуется.

## 9. Evidence families и будущая validation matrix

### 9.1. Модель для планирования

Предлагаются два семейства, имена **EXAMPLE**, не значения production correlation:
`audio_edit_boundary_consistency` (ATD/ASC, условно ABN) и
`audio_repetition_correspondence` (ARC). `audio_container_consistency` рассмотрено,
но не предлагается третьим семейством на текущих свидетельствах.

| Одна физическая причина | Waveform/energy | Spectrum/shape | Noise floor/ambience | Codec/timing | Вывод о независимости |
|---|---|---|---|---|---|
| Резкая склейка/локальный переход | Jump, RMS/MAD | Broadband change/leakage | Может смениться | Не обязательно меняется после re-encode | ATD/ASC/ABN могут описывать один boundary |
| Plosive/удар инструмента | Резкий onset | Изменение широких полос | Foreground загрязняет floor | Обычно без отдельного timing события | Те же responses без монтажа |
| Смена источника/помещения/микрофона | Возможен gain/level shift | Меняются смесь, EQ, bandwidth | Меняется ambience | Может сохраниться валидный codec | Recording condition change не означает злой умысел |
| AGC/denoise/compression | Меняется envelope | Меняется динамика полос | Меняется floor | Контейнер может быть тем же | Processing history связывает все три |
| Codec frame/PLC/recompression | Click/ringing/repeated waveform | Spectral artifacts | Noise modulation | Packet факт может совпасть по времени | Совпадение не делает четыре независимых голоса |
| Повторный сегмент | Могут быть две границы | Совпадение вдали по времени | Совпадает фон копии | Повтор codec packets возможен | Correspondence — иное отношение, но причинно связано с boundary |

Энергия связана с квадратами спектра (Parseval с соответствующими window/scaling),
поэтому простая численная корреляция — лишь часть пересечения. Даже gain-invariant
TV и waveform jump могут иметь общий источник. Bandwise floor вычисляется из тех же
STFT samples. Нельзя делить семейство по каналам, частотам, метрикам или локализациям
и этим создавать независимые votes. Также нельзя объявлять ARC статистически
независимым от ATD/ASC: копирование создаёт и соответствие, и границы.

В measurement-only фазе нет votes вообще. В validation нужны совместные response
таблицы ATD/ASC/ABN, conditional overlap внутри event/recording, matched strata,
абляция отдельных измерений на одних и тех же benign/edit событиях. Один input
recording и его производные составляют одну группу. До Findings требуется решение
по отношениям с `audio_signal_quality` и между двумя предложенными семействами.
`CONTRACTS.md` §11.4 (максимум severity внутри равной непустой группы) сохранён;
изменение risk/correlation не разрешено. **M2H-D01 — DEFERRED TO MACRO 6** сохранён.

### 9.2. План measurement-only проверки для READY профилей

Все ячейки — **будущий план**, не выполненные тесты. Начать с замороженного протокола
и manifest исходников/преобразований/версий/coverage; параметры менять только новым
профилем, не подбирать по желаемому разделению. Measurement outputs, никак не Findings.

| Категория | ATD-LOCAL-1 | ASC-TV-1 | ARC-NCC-1 |
|---|---|---|---|
| Positive controlled | Cut с фазовым/амплитудным скачком; gain/DC step, тот же контент с известным b | Стык разных спектров при равном RMS, bandwidth/EQ step; фазовый cut с leakage | Вставка копии сложного 2L материала с известным offset; exact и положительный gain/DC near-copy |
| Negative | Непрерывный гладкий сигнал, неизменный speech take | Стационарный тон/стационарная смесь, неизменённый take | Разные независимые фрагменты; сходный спектр с другой фазовой реализацией |
| Benign/challenge | Speech phonemes/plosives, percussion, silence, fades, clipping, mastering, PLC, codec/recompression, gain/EQ/compression | Те же recordings и события; инструмент/нота/сцена, denoise, AGC, bandwidth/SRC history | Легитимные loops, choruses, repeated speech, tones, silence, alarm, ambience, repeated codec frames; time stretch, pitch, polarity, channel swap как failure challenges |
| Boundary | b на всех остатках mod 512, на краях окна, gap между M1 окнами; 2047/2048/2049 samples | 4095/4096/4097; 2 и 5 frames, dropped tails, DC/Nyquist, silent/active channel | Длина 2L−1/2L/2L+1, касающиеся/пересекающиеся intervals; lag −4097/−4096/0/4096/4097, seed-grid phase и U=255/256/257, cap=63/64/65 |
| Not applicable | Image/video route, fs вне 8–48 kHz, >2 channels, неподходящая representation | То же; spectral profile не 4096/1024 magnitude | То же; различный stream/channel pairing не допускается |
| Insufficient evidence | Короткое покрытие, zero denominator, тишина/константа | Нет 2/5 полных frames, обе стороны zero; различать h=1/h=4 | Нет двух непересекающихся 2L областей; менее 4 spectral frames; constant/near-constant variance; нет двух support blocks |
| Determinism/repeat | 3 повтора тех же decoded samples, ties, int24/float64, independent channel order | 3 повтора, один и тот же descriptor/FFT build; прямой small-vector reference | 3 повтора, равные descriptors/NCC peaks; direct dot-product oracle против FFT NCC на коротких массивах |
| Resource/failure | Максимум окон/каналов, finite huge floats, timeout, bad identity/length | Aggregate frame/artifact limits, nonfinite spectra, producer budget failure | K/64-pair/Q limits, many identical seeds, исключение dense N² allocation, timeout посередине, missing support, numerical cancellation |

Синтетика проверяет арифметику, coverage, инвариантности и предсказуемые контрпримеры.
Она не устанавливает population FPR. Дополнительно требуются независимые реальные
speech/music/environment recordings с правами и provenance; без них production
calibration gate не закрывается. Собирать исходные takes и отдельно контролируемые
копии/изменения; все производные одного take остаются в одном split. Легитимные
edited masters должны присутствовать отдельно от untouched recordings.

Для ATD/ASC записывать response на размеченных событиях, их поддержки/ошибку
локализации, распределения по challenge-стратам и совместное пересечение, не только
общий максимум. Проверить, исчезает ли разница edited/benign после matching по
содержанию/уровню; отрицательный результат допустим. Для ARC отдельно считать
покрытые ground-truth пары, прохождение seed/descriptor/cap этапов, correctness offset,
support и ambiguity на легитимных повторах. Успех на заранее поданной паре не
подменяет end-to-end candidate retrieval. FPR/decision accuracy до правила решения
не вычислять; corpus statistics описывать только для реально заданной выборки.

Performance протокол: Windows 11 x64 / Python 3.12, точные NumPy/FFmpeg build,
CPU/RAM, cold/warm runs, peak RSS, wall time, bytes/artifact count. Для ATD/ASC,
как и ARC, measurement deadline `min(remaining,30 s)`; проверять между bounded
блоками и сохранять причину незавершения. Это будущий предел harness, не новый
runtime config. Проверить общий artifact budget с legacy outputs: наличие M1
capability не гарантирует, что всё поместится для каждого принятого файла.

Для ABN, если он будет отдельно разрешён, добавить stationary/nonstationary
background, смену среды без монтажа, движение микрофона, foreground masking,
AGC/denoise/codec и независимые matching labels. Без этого нет перехода в READY.

## 10. Пробелы, owner gates и рекомендуемый следующий scope

Для **двух рекомендованных** треков существующих M1 inputs достаточно в §3.
Новая runtime dependency не предлагается: NumPy достаточен; SciPy не установлен
в runtime и не требуется. OpenCV не нужен этим аудиоизмерениям. Физическое время
измерения не подтверждено и должно быть частью будущего prototype admission.

Следующие точные недостающие данные описываются только как условные gaps,
**не запрос их реализации в M3-R2**:

| Если владелец захочет расширить вопрос | Недостающее внутреннее представление | Предшествующий gate |
|---|---|---|
| Исследовать noise независимо от содержания в продукте | Source/stream/sample-bound маска сопоставимых background-only intervals, метод/версия получения и явные unknown/coverage; валидный non-ML способ её получения пока не установлен | Сначала метод matching, затем отдельный contract increment G5 |
| Связать decoded boundary с codec frame/PLC/priming | Typed аудио decoded-frame sample spans ↔ packet identity/PTS, skip/discard/priming/padding и provenance одного decode; M1-E packet rows и M1-F endpoints этого не содержат | Отдельный bounded preprocessing contract G5, до зависимой реализации |
| Изучать valid container edit-history | Allowlisted типизированные chunk/box факты с byte extents, field semantics и coverage (например edit lists), а не raw tags/ffprobe JSON | Новый метод и G4/G5; сейчас отклонено как неподготовленное направление |
| Full-duration repetition или phase novelty | Новый согласованный bounded sampling demand либо complex spectral artifact producer profile | Отдельное согласование G5, не скрытый full decode/второй STFT |

Флаг «новая capability предложена» в итоговом отчёте означает **NO** для
рекомендуемого scope; перечисленные gaps не считаются принятой или рекомендованной
к реализации capability. Контракты можно специфицировать как будущую потребность,
не меняя `CONTRACTS.md` в этом инкременте.

| Gate | Решение владельца до зависимого продолжения | Рекомендация исследования |
|---|---|---|
| G1 | Какие профили допускаются к measurement-only prototype | ATD-LOCAL-1, ASC-TV-1, ARC-NCC-1, без Findings и production registration |
| G2 | Temporal/spectral/background: отдельные измерения общего семейства, один combined analyzer или один метод | ATD/ASC как раздельные измерения одного трека; без fusion; ABN оставить weak |
| G3 | Отдельный repetition track/family | Да для ARC; причинную независимость от boundary не объявлять |
| G4 | Retain/narrow/reject metadata/container | Принять отрицательный результат AMC-RESP-1, REJECT_DUPLICATE_RESPONSIBILITY |
| G5 | Достаточен ли узкий существующий input scope; нужен ли contract increment | Сохранить §3 и существующие producer profiles; новые capabilities не нужны выбранным трекам |
| G6 | Dependencies, datasets и условия измерительного корпуса | Без новых libraries/downloads; реальные записи только после проверки прав и явного допуска владельца |

На момент исходного исследования все шесть gates были **OPEN**; таблица выше
сохраняет предложения, вынесенные владельцу. Они закрыты явным решением в §12:
разрешён ограниченный measurement-only scope, не принятие production-метода.
Production acceptance позже потребует полного правила,
валидации, семантики/корреляции, ресурсов и provenance каждого компонента.

Tentative wording для трека переходов: «В проверенном интервале наблюдается
локальное изменение waveform/спектральной структуры; подобное изменение возможно
и при естественном событии или обычной обработке». Для ARC — формулировка §7.
Это текст для последующего исследования интерпретации, не созданные Findings.
Во всех случаях: no signal != authentic; signal != malicious manipulation;
preprocessing/container/parser failure != Finding; provenance != verdict.
Вероятность подделки, намерение, точный editor/tool/time/save count не выводятся.

## 11. Проверки и материалы review

Изменения ограничены этим отчётом, candidate-записью `METHODS.md`, provenance
`REFERENCES.md` и статусом/gates `ROADMAP.md`. Src/tests/config/scripts, зависимости,
публичные API/schema/YAML/CLI, scoring/completeness/correlation не меняются.
Macro 2 и M2H-D01 сохранены, Macro 3 не закрывается.

Обязательные проверки M3-R1: совпадение branch/HEAD, чистый baseline;
`git diff --check`, проверка полного фактического diff, scope и итогового status.
Новый untracked отчёт должен целиком входить в `complete.diff`; staging не применяется.
Полный `uv run poe check` и strict certification по заданию не запускаются.
Фактические результаты и полный status — во внешнем `review-summary.md`.
Owner review: `C:\Users\Vanur\Desktop\FakeDetector-Work\reviews\M3-R1-audio-method-selection\`.
Исследовательские заметки: `C:\Users\Vanur\Desktop\FakeDetector-Work\research\M3-R1-audio-method-selection\`.

## 12. Явное принятие владельцем исследовательских gates — 2026-09-26

Владелец рассмотрел M3-R1 и в задании M3-R1A явно принял G1–G6.
**M3-R1: DONE / OWNER ACCEPTED RESEARCH SELECTION.** Macro 3 остаётся
**IN_PROGRESS**. Это **OWNER ACCEPTANCE исследовательского scope**, а не
принятие production-метода. Авторитетная запись допуска профилей —
[METHODS, Macro 3](../METHODS.md#audio-m3r1); состояние работ —
[ROADMAP, Macro 3](../ROADMAP.md#audio-m3r1).

| Gate | Принятый исход |
|---|---|
| G1 — ACCEPTED | ATD-LOCAL-1, ASC-TV-1 и ARC-NCC-1: OWNER_ACCEPTED_FOR_MEASUREMENT_PROTOTYPE. Разрешены только bounded research measurements и measurement-only validation; ABN остаётся RESEARCH_ONLY / WEAK_SIGNAL, AMC не продвигается в прототип |
| G2 — ACCEPTED | ATD/ASC измеряются раздельно и сравниваются внутри одного общего transition track/evidence family; без fusion, combined score или двух независимых forensic votes. ABN не является третьим голосом |
| G3 — ACCEPTED | ARC — отдельный repeated-segment/correspondence measurement track; его поведение можно исследовать отдельно. Статистическая независимость от transition evidence не заявляется; production correlation отложена до последующей validation / Macro 6, где применимо |
| G4 — ACCEPTED | AMC-RESP-1: REJECT_DUPLICATE_RESPONSIBILITY / OWNER ACCEPTED NEGATIVE RESULT. Исследованный scope не отделён от intake, preprocessing/container validation, typed source/decoded facts и infrastructure/errors; `audio_metadata_container_consistency` из этой ответственности не создавать |
| G5 — ACCEPTED | Использовать audio route, 8–48 kHz, mono/stereo, существующие M1-D precision windows, shared STFT/framing APIs и typed timing/source facts при необходимости. Новые capabilities и изменение CONTRACTS.md не разрешены; full-duration coverage не подразумевается |
| G6 — ACCEPTED | Использовать существующий runtime stack; новые runtime dependencies не разрешены, SciPy не добавляется. Новая dataset dependency автоматически не одобрена; реальные записи/корпуса требуют проверки provenance/license и intended use |

Разрешены **два** отдельных будущих исследовательских трека:

- **A — локальные переходы:** ATD-LOCAL-1 и ASC-TV-1, отдельные измерения без
  fusion; сравнение поведения и доброкачественных confounds.
- **B — повторное соответствие:** ARC-NCC-1; проверка retrieval, correspondence
  и ресурсов отдельно от transition track.

G1–G6 закрыты только в этих границах. Если требуемое измерение нельзя честно
выполнить в существующих representations — **STOP / OWNER GATE**, без молчаливого
расширения preprocessing. Если необходимый корпус или библиотека не имеют
установленных прав/разрешённого scope — **OWNER GATE** до зависимой работы.

Допуск не разрешает production analyzer registration, Findings, severity,
production Decision Rules/thresholds, risk contribution, scoring, completeness,
public contracts или изменение `correlation_group`/risk aggregation.
Parser/container/validation failure не становится suspicious Finding.
Production method acceptance отсутствует; ABN остаётся weak, отрицательный
результат AMC принят. Macro 3 не закрывается.

**M3-R1 не выполнял измерительных экспериментов:** efficacy, false-positive rate,
sensitivity, runtime и RSS остаются неизмеренными. M3-R1A не выполняет новых
исследований/экспериментов и не меняет формулы, наблюдения или происхождение методов.
Разрешение будущих измерений не означает, что они уже выполнены.
