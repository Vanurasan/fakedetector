# M2-R3A — реальный корпус и варианты operating point

Дата исследования: 2026-09-24. Baseline: `2e91d560d633b4948ffccf1769db10367e0aedfb`,
ветка `feat/stage12-macro2-image-analyzer-expansion-wave1`; исходное дерево чистое.
Статус: дизайн подготовлен для owner review, не приёмка методов или Stage 12.
Основание — [M2-R2](2026-09-23-jpeg-dq-grid-calibration.md),
[METHODS](../METHODS.md), [политика исследований](README.md).

## Рекомендация

**RECOMMEND_CORPUS: C — контролируемые JPEG из CC0/собственных RAW + VISION.**
Основная калибровка использует реальные сцены с известной историей до первого
JPEG; VISION проверяет переносимость на камерные JPEG и доброкачественную
пересылку. Это две отдельно учитываемые части, не одна смешанная population.
**Решение владельца в remediation M2-R3A: BALANCED TRIAGE, target image-level
FPR ≤1%.** Это цель калибровки Stage 12, не production threshold и не вероятность
манипуляции. 0,5% остаётся необязательной более строгой будущей целью проверки;
0,1% для Stage 12 не требуется. Числовые decision thresholds ещё не выбраны.

**Размер корпуса не зафиксирован.** 3600 независимых source groups (3000 core +
600 VISION) сохраняются как расширенный/full-corpus вариант, не обязательное
требование acquisition и не предпосылка R3B или M2-A. Корпус ещё не собран,
файлы изображений не скачивались. Требования 2000 собственных RAW нет: их число
зависит от пригодного дедуплицированного CC0 yield, пробелов device/content,
ресурсных отказов и результатов пилота.

Следующий шаг R3B — ограниченный пилот: ориентировочно 100–200 одобренных CC0 RAW
source groups, ограниченная VISION-подвыборка и немного собственных источников
только для явных пробелов содержания/устройств. Эти диапазоны планируют пилот,
а не задают статистический размер production-выборки. После пилота R3B предлагает,
а владелец утверждает финальные размеры calibration, validation, untouched primary
holdout, VISION external stress и source/device/content quotas. Их фиксируют
до просмотра final holdout outcomes. Нельзя адаптивно добавлять negatives до PASS.
DQ-HIST-1 и GRID-PHASE-1 не приняты; все нерешённые пороги класса C сохраняют
`INSUFFICIENT_EVIDENCE`, M2-A остаётся **BLOCKED**.

## Корпуса и права

Канонические записи provenance/условий — [REFERENCES, M2-R3A](../REFERENCES.md#m2-r3a-datasets).
Ни лицензия статьи, ни доступность URL не заменяют лицензию изображений.
Ниже — сравнение для выбора, не дополнительный источник разрешений.
Числа относятся к опубликованным коллекциям, а не к независимому n эксперимента.

| Кандидат, владелец и источник | Размер, формат, разнообразие | Пригодность и затраты |
|---|---|---|
| RAISE; MMLab / University of Trento; [сайт](https://loki.disi.unitn.it/RAISE/), [guide](https://loki.disi.unitn.it/RAISE/guide.html) | 8156 исходных фото; NEF и TIFF; Nikon D40/D90/D7000, несколько фотографов, реальные сцены | Сильная основа B по истории, слабее по устройствам. [Полный набор ~350 GB](https://loki.disi.unitn.it/RAISE/download.html), есть поднаборы; RAW и TIFF одной сцены — один источник. Сейчас не допущен по правам |
| raw.pixls.us; PIXLS.US и авторы вкладов; [каталог](https://raw.pixls.us/), [метаданные](https://raw.pixls.us/json/getrepository.php?set=all) | На дату проверки 2016 записей, 1870 CC0 и 146 прочих; у CC0 925 точных пар make/model, 922 без учёта регистра. CR2/CR3, NEF, ARW, DNG, RAF и другие RAW; повторные режимы камеры могут изображать одну сцену | Рекомендуется CC0-подмножество для B. На все CC0 планировать ~60 GB по округлённым размерам каталога, не измеренный download. Для примера 1000 выбранных RAW: оценка 20–50 GB; не зеркалировать всё |
| VISION; CSP Lab, University of Florence; [README](https://lesc.dinfo.unifi.it/VISION/README.txt), [статья](https://link.springer.com/article/10.1186/s13635-017-0067-2) | 11 732 native изображения, 34 427 с социальными версиями; 35 устройств, 11 брендов. JPEG, Nat/Flat, Facebook/WhatsApp; видео в scope не входят | Рекомендуется отдельная часть A; 600 source groups — расширенный вариант. Для него native + доступные социальные версии: 2–10 GB, оценка, не размер архива. Старые устройства/сервисы ограничивают переносимость |
| Open Images V7; Google LLC / авторы фотографий, CVDF для доставки; [описание](https://storage.googleapis.com/openimages/web/factsfigures_v7.html), [загрузка](https://storage.googleapis.com/openimages/web/download_v7.html) | Около 9 млн изображений, разнообразные сцены, в поставке JPEG; камера и предыдущие экспорты обычно не установлены | Не основа single-JPEG null. Возможен последующий внешний challenge после проверки каждой лицензии. Выборка 1000 оригиналов: план 1–10 GB, размер уточняется по `OriginalSize`; весь архив не нужен |

Метаданные raw.pixls.us прочитаны без загрузки RAW; подсчёт CC0 основан на URL
`publicdomain/zero/1.0` в поле лицензии, make/model — на строковых метках, не
на подтверждённых физических устройствах. Показанные kB/MB дают ~55,740 GB
при десятичном прочтении и ~58,448 GB при двоичном; точные bytes проверять при
acquisition. В это не входят проявленные растры и производные. Снимок каталога
сохранён вне Git, SHA-256:
`8dc5f5c74e20cc3a38f4548d53bba4bb516835e2a859e80bf86e7ac6283b3aa3`.
Количество независимых сцен устанавливается только
при acquisition audit, не по количеству моделей или файлов.

| Кандидат | Лицензия/ограничение | Внутренняя калибровка FakeDetector | Распространение файлов и результатов |
|---|---|---|---|
| RAISE | Non-commercial research/education; требуется цитирование | **Не допущено до письменного уточнения прав** на калибровку коммерчески применимого продукта; слово «internal» не снимает NC | Разрешение на перепубликацию файлов/производных не установлено; публикация исследовательских результатов предусмотрена с цитированием только в разрешённом режиме. Коммерческое использование результатов не считать автоматически разрешённым |
| raw.pixls.us, только CC0 | CC0 1.0 по каждой записи; прочие лицензии исключить | Да для подтверждённых CC0 записей и допустимого содержания | Copyright-разрешение охватывает копирование/изменение/коммерцию; права третьих лиц не исчезают. Файлы не включать в Git/поставку; агрегированные собственные результаты можно публиковать с provenance |
| VISION | Dataset CC BY-SA 4.0; статья имеет отдельную лицензию | Да, включая коммерчески ориентированное исследование, при соблюдении условий | Изображения и адаптации — attribution, указание изменений, применимый ShareAlike, без дополнительных ограничений; не перелицензировать их Apache-2.0. Собственные агрегированные числа без изображений публиковать с цитированием; переиздание существенной части базы отдельно проверить |
| Open Images | Изображения заявлены CC BY 2.0, аннотации CC BY 4.0; издатель требует проверять лицензию каждого фото | Только после проверки конкретной записи; неясные права — **unusable pending clarification** | Подтверждённые фото/адаптации — с применимым attribution и указанием изменений; агрегаты без воспроизведения фото отдельно от набора. Аннотации не дают прав на фото |

Собственные съёмки — проектируемый источник, не существующий внешний dataset.
Нужны автор/правообладатель, письменное право на внутреннюю коммерчески
ориентированную калибровку и создание производных, отдельно право публикации
образцов. Пока это не оформлено, соответствующий файл не допускается. Для
текстовых challenges использовать собственный несекретный текст и материалы
с подтверждёнными правами; не снимать чужие документы/интерфейсы без основания.

### Почему C

- **A отдельно:** удобны реальные device/encoder и известные цепочки доставки,
  но native JPEG не доказывает единственный DCT/quantization pass внутри камеры;
  качество первого прохода может быть неизвестно. Нельзя получать «lossless
  original» декодированием JPEG и переименованием в PNG.
- **B отдельно:** точно известны наши JPEG-проходы, DQT и геометрия; остаются
  смещение выборки RAW, проявка и ограниченное разнообразие encoder.
- **C:** B обеспечивает контролируемые negatives/positives, A проверяет внешнюю
  переносимость и nuisance на benign workflows. Цифры обеих частей публикуются
  раздельно; VISION не увеличивает n основной single-history оценки.

RAISE технически привлекателен, но не включён в рекомендуемый acquisition.
Open Images не закрывает unknown-history проблему. Синтетические patterns M2-R2
остаются арифметическими/challenge fixtures и не увеличивают real-source n.

## Что именно считать ошибкой

До калибровки определить и заморозить исследовательские image-level правила:
DQ — вывод о предшествующей JPEG-квантизации; Grid — вывод о неоднородной
истории сетки. Сильная текущая решётка сама по себе не ошибка и не finding.
В R3A правил, thresholds, severity или новых production scores не назначается.

Основной negative endpoint: на источнике без предшествующего JPEG после одного
контролируемого JPEG-прохода любой ложный положительный вывод замороженной пары
правил DQ/Grid. Оба измерения исполняются на одном изображении; считаем событие
`DQ false positive OR Grid false positive` один раз. Так основной FPR относится
к паре правил на уровне изображения, а не к mode/window. Отдельные method-FPR
также показываются. Числа ниже не гарантируют каждый из нескольких endpoints
одновременно: если вместо одного primary endpoint нужны совместные заявления,
заранее распределить alpha (например, 0,025 на каждый из двух) и пересчитать n.

Для первичной оценки каждый независимый source group даёт **один** заранее
назначенный negative JPEG. Предлагаемая исследовательская смесь: равновероятные
quality 40/75/95, sampling 4:2:0/4:2:2/4:4:4 с вероятностями 0,6/0,2/0,2,
baseline/progressive 0,8/0,2; назначение seeded до измерений. Это дизайн смеси,
не оценка частот файлов в электронной почте. Владелец утверждает или меняет
целевую смесь до freeze. Quality=20/100 и дополнительные варианты — challenges.

Заведомо доброкачественное повторное сохранение — положительный пример истории
сжатия для DQ, но не пример злонамеренности. Для Grid глобально aligned/shifted
пересохранение без локально разных историй — отдельный negative stratum именно
для утверждения о неоднородности. Локальная контролируемая замена фаз — positive
для Grid независимо от намерения автора. Не смешивать эти labels с DQ labels.

Отдельно показывать долю benign workflows, вызвавших будущий пользовательский
сигнал внимания: это nuisance rate, а не FPR обнаружения recompression. Никакой
полученный здесь результат не устанавливает malicious-manipulation FPR.
Sensitivity оценивается по подтверждённым контролируемым положительным историям,
с доверительными интервалами и source-group clustering; численных обещаний
чувствительности до R3B нет.

Для каждого метода и stratum выводить total / admitted / measured / insufficient
support / rejected / positive. Неприменимость, нехватку опоры, timeout и resource
failure не записывать как истинный negative. FPR сообщать с явным знаменателем
применимых независимых negatives и coverage относительно всех назначенных
источников. Для joint endpoint основной n включает источники, на которых
оба правила применимы и имеют требуемую опору; отдельные method denominators
могут отличаться. Дополнительно показывать долю сигналов на всех входах; низкая
coverage не должна улучшать видимость качества детектора.

## Объём holdout и односторонняя уверенность 95%

Пусть n — число независимых применимых negative source groups, k — число
ложных сигналов фиксированного image-level endpoint, p — его частота в
оговорённой популяции. Используется точная односторонняя верхняя биномиальная
граница Clopper–Pearson, alpha=0,05; [NIST](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm).
Для k<n верхняя граница U решает:

```text
sum(j=0..k) C(n,j) U^j (1-U)^(n-j) = 0.05
k=0: U = 1 - 0.05^(1/n)
n_min(k=0, target=f) = ceil(log(0.05) / log(1-f)) ≈ ceil(2.996/f)
k=n: U=1
```

Для ненулевого k минимальный n найден целочисленным поиском условия
`P[Binomial(n,f) <= k] <= 0.05`; на предыдущем n условие ещё не выполнено.
Расчёт воспроизводится через начальный член `(1-f)^n` и рекурсию
`t[j+1]=t[j]*(n-j)/(j+1)*f/(1-f)`. Это проектный расчёт, а не измерение корпуса.

| Цель f | n минимум при k=0 | n минимум при k=1 | n минимум при k=3 | Грубый план для погрешности около ±50% от f при p≈f |
|---|---:|---:|---:|---:|
| 5% | 59 | 93 | 153 | 206 |
| 2% | 149 | 236 | 386 | 531 |
| 1% | 299 | 473 | 773 | 1072 |
| 0,5% | 598 | 947 | 1549 | 2154 |
| 0,1% | 2995 | 4742 | 7752 | 10812 |

Последний столбец — лишь нормальное приближение для одной стороны:
`ceil(1.64485²*f*(1-f)/(0.5*f)²)`, не точный критерий допуска; для редких ошибок
финально применять exact interval. ± здесь описывает масштаб погрешности,
а не двустороннее покрытие 95%. Минимумы первых столбцов условны на указанный k;
это не power calculation и не гарантия, что корпус данного объёма пройдёт цель.
Если истинное p равно целевой границе, убедительно доказать U<=f маловероятно;
рабочее p должно быть ниже цели с запасом. При k>0 нулевая формула неприменима.

При n=1000 и k=0 U≈0,2991%: это позволяет проверять 0,5%, но не 0,1%.
При k=1 для 0,5% хватает 947, при k=3 нужны 1549; поэтому 1000 не обещает
прохождение conservative. При alpha=0,025 и k=0 для 0,5% нужны 736, для 0,1%
— 3688 независимых negatives (если нужны два одновременных method-заявления).

Все эти границы предполагают независимые испытания из определённой population.
Серии, один сюжет с нескольких камер, derivatives, блоки, windows и DCT modes
не добавляют независимых samples. Если остаются session/device correlations,
показать cluster-sensitive анализ и эффективное ограничение доказательств;
не выдавать биномиальную формулу за доказательство независимости. Отбор удобных
сцен/камер не даёт population FPR всех почтовых вложений. Per-stratum заявления
нуждаются в собственном n и поправке на множественность, а не в общем n (например, 1000 в расширенном варианте).

## Выбранный профиль и сравнение альтернатив

Владелец выбрал **BALANCED TRIAGE, ≤1%**. Таблица сохраняет сравнение вариантов;
exploratory не выбран, conservative — только необязательная будущая проверка.

| Профиль | Image-level target FPR и минимум holdout при k=0 / k=1 | Поведение и цена |
|---|---|---|
| Exploratory / высокая чувствительность | ≤5%; 59 / 93 | Исследовательский список для ручного просмотра; допускает больше ложных сигналов. Потенциально шире sensitivity/coverage, но выгода не измерена. Для риск-поддержки только с ясным ограничением, без автоматических обвинений |
| Balanced triage | ≤1%; 299 / 473 | Умеренная очередь ручной проверки; ожидаемо потеря слабых сигналов относительно exploratory. Проверять sensitivity по quality/history и долю недостаточной опоры, не только общий FPR |
| Conservative / низкая ложная тревога | ≤0,5%; 598 / 947 | Меньше необоснованных сигналов внимания, вероятно больше пропусков и abstentions. Отсутствие сигнала не означает подлинность; полезен как один фактор риск-поддержки |

Финальный primary holdout должен быть достаточен для проверки **≤1%** по
заранее согласованному acceptance rule при односторонней уверенности 95%:
например, минимум 299 применимых независимых negatives при допустимых k=0,
473 при k≤1 или 773 при k≤3. Это условные минимумы, не выбранный размер и
не гарантия прохождения. После пилота учесть coverage/rejections и утвердить
полный назначенный n, допустимый k и правило U≤1%; прогнать весь замороженный
holdout без досрочной остановки или добора до PASS. Primary holdout 1000 —
только пример расширенного дизайна ниже. Расчёты 2% и 0,1% оставлены для
сравнения, они не меняют выбранную цель; 0,1% для Stage 12 не требуется.

## Разбиение без утечки

Ниже **расширенный вариант**, а не обязательные размеры/проценты Stage 12.
Окончательные размеры всех четырёх частей (calibration, validation, untouched
primary holdout, VISION external stress) и source/device/content quotas R3B
предлагает по итогам bounded pilot; до final corpus freeze их утверждает владелец.

| Часть | Exploration/calibration | Validation | Untouched holdout | Всего |
|---|---:|---:|---:|---:|
| Контролируемые RAW/собственные lossless источники | 1500 (50%) | 500 (16,7%) | 1000 (33,3%) | 3000 |
| Внешняя VISION, отдельный domain/device stress | 300 (50%) | 100 (16,7%) | 200 (33,3%) | 600 |
| Сумма, без статистического pooling | 1800 | 600 | 1200 | 3600 |

Числа примера — после rights/dedup/format eligibility, до method support rejections.
В расширенном варианте можно предусмотреть 10–20% резерв; он не включён в 3600
и не даёт права добирать «до PASS» после просмотра ошибок. Если фактический
применимый n ниже требуемого — результат `INSUFFICIENT_EVIDENCE` либо новый
заранее спланированный независимый эксперимент, а не подмена rejected файлов.

1. До генерации проверить точные hashes, визуальные near-duplicates и
   provenance. Объединить burst, один сюжет/сессию и варианты RAW+JPEG в
   source family. Для основного endpoint выбирать один исходник из зависимого
   семейства; все прочие версии оставить в той же partition как paired data.
2. Сначала заморозить список источников и связанных семей, затем seeded split
   с balancing по происхождению, сценам и доступным camera model. У неизвестного
   physical device явно оставить unknown, не считать model ID device ID.
3. Для основной оценки распределять независимые сцены известных устройств
   между partitions с учётом session grouping; отдельно показывать срезы по
   устройствам. Такая оценка условна на представленные устройства. Для внешнего
   VISION stress разделить целые physical device IDs между тремя partitions;
   утверждённые после пилота квоты подбирать из непересекающихся групп устройств;
   все версии выбранного оригинала сохранять вместе. Если квоты недостижимы — сообщить
   фактические counts до freeze, не нарушать device/source separation.
4. Exploration служит выбору support/aggregation/decision rules; validation —
   проверке ограниченного заранее записанного набора вариантов и окончательному
   выбору. Если validation использован повторно для tuning, считать его частью
   development и явно учитывать это; untouched holdout остаётся закрытым.
5. До holdout зафиксировать source manifest hash, seed, версии генератора,
   правила/пороги, primary endpoint, целевую смесь, alpha, exclusions, метрики,
   план отказа и размер. Содержимое и результаты holdout не просматривать при
   tuning; acquisition-проверку проводит отдельный от подбора правил куратор.
6. Один финальный прогон. После неуспеха нельзя выбирать удачный профиль,
   encoder или stratum по этому holdout и повторно называть его untouched.
   Пересмотр требует нового holdout либо честного exploratory статуса.

Разбиение издателя не заменяет проектное: родительская фотография и её
социальные версии могут иметь разные имена, но один source-group ID. Все
дополнительные crops, grayscale, размеры и quality наследуют split родителя.

## Реальные strata и контролируемые производные

Для расширенного варианта 3000 core пример квот **доминирующего** содержания:
1200 обычных смешанных природных/городских сцен, 450 low-detail, 450 high-detail
непериодических, 450 foliage/fabric/brick/fences/periodic textures, 150
high-contrast edges и 300 low-light/noisy. Сумма 3000; дополнительные теги
могут пересекаться. Квоты наследуются split пропорционально, допустимые
округления фиксируются до измерений. Это не утверждённые квоты: окончательные
числа определяются после пилота и принимаются владельцем до final corpus freeze.
Не отбирать сцены по отклику методов.

Текст/screenshots/document-like: пример отдельной дополнительной challenge-части
100 собственных/разрешённых источников (50/20/30), вне 3600 фотографий и
primary population FPR. Реальные фото вывесок/бумаги могут входить в основной
корпус с дополнительным тегом, screenshots не выдаются за natural photograph.
M2-R2 synthetic patterns также остаются отдельно и не входят в эти 100.

Для расширенного варианта ориентир — не менее 10 физических устройств, несколько
производителей и съёмочных сессий; это не обязательная квота пилота или обещание
репрезентативности рынка. Показывать вклад каждого устройства/автора и долю
unknown device. CC0-архив ориентирован на светлые низко-ISO сцены; собственными
съёмками восполнить low-light, шум, текстуры и современные телефоны.

RAW проявляется **вне production** в фиксированный lossless TIFF/PNG:
версии converter/profile, demosaic, colour space, white balance, tone curve,
sharpening/denoise и bit-depth conversion записать. Не использовать embedded
JPEG preview. RAW с потерями, sRAW/mRAW и неясной внутренней историей — отдельный
challenge или исключение; не считать любой `.dng` доказанным sensor original.
Lossless container после JPEG тоже не даёт pristine negative.

Для bounded основного прогона до первого JPEG привести master к RGB8, длинной
стороне не более 1280 и площади не более 1 000 000 pixels без upscale. Сохранить
оригинал, точный resampling и master hash. Это калибровка на таких производных,
не подтверждение full-native-resolution качества. Выделить отдельные native
и boundary probes; отказ по действующим лимитам считать отказом, не обходить.

| Workflow | Запланированное действие | Ground truth / отдельный смысл |
|---|---|---|
| Single JPEG | Lossless master → JPEG; quality 40/75/95 в primary, 20/100 в challenge | DQ-negative; Grid-negative для неоднородной истории |
| Benign repeated export | JPEG → decode → ещё 1–3 сохранения; равные и разные DQT | Recompression-positive, benign; nuisance отдельно |
| Aligned double | 40→90, 90→40, 75→75, 74→75, 99→100, origin неизменен | DQ-positive по истории, detectability не гарантируется; отсутствие локального grid conflict |
| Shifted crop/recompress | Crop после первого JPEG; фазы (0,0), (1,0), (0,1), (3,5), (7,7), crop без shift как контроль | Известный глобальный shift, не доказательство локального монтажа; полная 8×8 матрица только на exploration challenge |
| Resize/recompress | Масштабы 0,5/0,75; bicubic/Lanczos, nearest как challenge; exact dimensions | История есть, старая решётка может исчезнуть; не считать отказ DQ ошибкой арифметики |
| Rotation/recompress | Поворот пикселей 90° и 2° с записью interpolation/crop; EXIF-only отдельно | EXIF-перестановка не JPEG-проход; lossless coefficient rotation и decode/re-encode различать |
| Thumbnail/social-like | Контролируемые resize до 320/640 и JPEG 60/80 | Приближение workflow, не воспроизведение нынешнего Facebook/WhatsApp; реальные версии VISION отдельно |
| Same/equivalent DQT | Полное совпадение таблиц и совпадение только выбранных modes, разные labels quality | Проверять фактические tables/selectors; не приписывать отсутствующую различимость |
| Локально разные grid histories | Контролируемые patches из того же master с разными JPEG-phase histories; маска внутри/на краю/вне sampled windows | Grid-positive с известной support geometry; это исследовательская обработка, не malicious intent |

Не выполнять полный декартов продукт. На exploration — расширенная матрица
по подвыборке; на всех core sources — ориентировочно 12–20 заранее назначенных
производных для paired diagnostics. Primary negative один на источник.
Final quality, subsampling 4:4:4/4:2:2/4:2:0, RGB/L, baseline/progressive и
EXIF 1–8 распределять по сбалансированному плану; native grayscale и RGB→L
различать. Grayscale-производные — paired challenge, не дополнительные n.
Для encoder diversity основа использует существующий Pillow/native codec с
точной версией; VISION добавляет камерные encoders. Второй контролируемый encoder
требует отдельного выбора/проверки provenance в R3B; установка здесь не разрешена.

## Harness: что переиспользуется и что потребуется в R3B

Просмотрены [Case/generate](../../scripts/research/jpeg_corpus.py),
[measure/main/aggregate](../../scripts/research/jpeg_calibration.py),
[измерения](../../scripts/research/jpeg_measurements.py) и
[тесты](../../tests/test_jpeg_research.py).
Graphify имеет provenance SHA `625b9e83f133fb0ae31a4b90e9e1288bff96f69c`,
generator graphifyy 0.9.53; **STALE** относительно baseline R3A. Узлов этих
research-модулей нет; граф не использован как доказательство, не пересобирался.

**Production architecture менять не требуется для допустимых JPEG-производных;
существующий CLI без изменений реальный корпус не принимает.** `main()` всегда
вызывает synthetic `generate()`, provenance содержит прежний baseline и
собственные geometric/PRNG rights. `measure()` ищет `corpus/{case_id}.jpg`,
проверяет hash, но создаёт trusted `ValidatedFileDescriptor` из `Case`, что
приемлемо для собственного генератора, а не произвольных внешних загрузок.
Нельзя подставить скачанный файл под synthetic inventory и сохранить старые
утверждения о правах, quality и validation.

Малые research-only изменения будущего execution pass:

- Загрузка утверждённого внешнего manifest, проверка source/derivative hashes,
  прав и partition invariants; генерация controlled JPEG из проверенных masters.
  RAW development — отдельная offline операция, не новый production intake.
- Для внешних VISION JPEG получить действительную валидацию существующим
  intake/validation путём, сохранить факты вместо доверия расширению и Case.
  Не угадывать исходную quality по DQT; разрешить unknown только в research
  inventory. Нового production schema/config поля не требуется.
- Сохранить `ImagePreprocessor`, clean numeric access, обратную EXIF-перестановку,
  общий artifact budget/cleanup, 60 s research deadline и все safety ceilings.
  Многие native фотографии превышают лимит raster или **суммарных** padded
  coefficients `2^22`; даже допустимые отдельно артефакты могут не войти в
  общий budget. VISION native не уменьшать/пересохранять незаметно ради допуска:
  rejected native остаётся rejected, resized версия — другая известная история.
  Поэтому даже пример external holdout из 200 назначенных groups не гарантирует 200
  измеримых native JPEG; доли отказов native/social показывать отдельно.
- Добавить source-level endpoints и интервалы после отдельного разрешения на
  исследовательские decision rules; нынешние quantiles/range overlap и Grid
  research flags ещё не классификатор. Сохранять отдельные method и joint counts.
- Потоковые агрегаты/обработка чанками: нынешний `results` и списки `aggregate`
  растут со всем corpus; при 36–60 тыс. derivatives это потребует ограничить
  память исследовательского runner. Перезапуск по manifest/hash не должен
  удваивать n. Это локальная доработка harness, не новая production архитектура.

Предлагаемые **research manifest**, не публичные поля:

| Уровень | Сохранить/добавить |
|---|---|
| Источник | `dataset_id/version`, original URL/ID, retrieval date, SHA-256, author/rights holder, license URL и snapshot hash, internal/redistribution permission, rights-review status |
| Группа/разбиение | Уже есть `source_group`, `partition`; добавить scene/burst/session family, device ID отдельно от make/model, duplicate cluster, split seed/version/hash, роль primary/challenge/external |
| Master | Original format/geometry/bit depth, известность prior history, converter/version/settings и master hash; содержание, low-light/detail/periodic tags |
| Производная | Уже есть quality/tables/sampling/shift/orientation/hash/geometry; дополнить ordered transform chain, encoder/build, resize filter, rotation/crop coordinates, parent hash, маску локальных изменений, отдельные DQ/Grid/benign labels |
| Прогон | Реальный source SHA и diff fingerprint для dirty development, package/tool versions, frozen rule hash, endpoint/alpha, admission/support/rejection reason, n sources/derivatives, coverage и timings |

Камера/автор/сессия могут быть unknown, это явное ограничение. Внешние пути и
служебные EXIF остаются в локальном manifest вне Git; публикуемые агрегаты не
должны раскрывать GPS, серийные номера, имена владельцев или закрытые документы.

## Ресурсы и execution plan M2-R3B

Бюджет расширенного варианта, не предпосылка пилота и не benchmark:
3000 RAW по 20–50 MB — 60–150 GB;
lossless masters по 2–5 MB — 6–15 GB; 36–60 тыс. bounded JPEG по 0,2–1 MB —
7–60 GB; VISION 2–10 GB, scalar diagnostics и provenance ещё несколько GB.
Для этого варианта резервировать **250–300 GB** при хранении RAW и bounded masters;
архив полноразмерных TIFF и резервная копия потребуют больше. Собственные съёмки
требуют времени автора/куратора; готовый открытый набор не покрывает автоматически
весь core. Лицензионной платы для рекомендованных CC-частей не заявлено;
стоимость трафика/накопителя/съёмок зависит от владельца.

1. Начать R3B с bounded pilot acquisition под выбранную цель ≤1%: примерно
   100–200 одобренных CC0 RAW source groups, ограниченная VISION-подвыборка,
   собственные источники лишь для явных device/content gaps. Согласовать лимиты
   пилота, population/смесь, primary endpoint, условия публикации и provenance
   offline RAW converter. В текущей docs-only remediation acquisition не выполняется.
2. Получить metadata/terms snapshots и per-record allowlist, проверить права,
   provenance, контейнеры, hashes и дедупликацию. Измерить фактический usable
   independent-source yield; не принимать ND/NC/unknown как CC0.
3. В exploration-пилоте проверить RAW development, VISION admission и необходимые
   research-only адаптации harness, bounded generation, runtime, peak RSS, disk,
   coverage/rejections. Для доработок выполнить meaningful tests
   split/hash/unknown-history/validation/rejection/aggregation и quality barrier
   согласно AGENTS. Measurement profile без отдельного gate не менять.
4. По результатам пилота предложить владельцу финальные calibration size,
   validation size, untouched primary holdout size, VISION external-stress size
   и source/device/content quotas. Обосновать статистическую достаточность для
   ≤1% и planned acceptance rule, acquisition/storage budget и необходимость
   собственных снимков. **Владелец утверждает финальные размеры и квоты**;
   3000+600 и 2000 собственных RAW не являются обязательными требованиями.
5. По утверждённому плану дособрать и независимо проверить корпус; до просмотра
   final holdout outcomes заморозить размеры, source/device/content quotas и
   split manifest вне репозитория. Пилот и все его derivatives остаются только
   в exploration, включая отдельный VISION exploration stress. Final holdout
   изолирован от tuning. Добор negatives по результатам holdout до PASS запрещён.
6. Exploration и validation: оценить возможность калибровки, overlap, support,
   sensitivity/coverage, benign nuisance и совместные ответы. Если рабочее
   правило с полезной чувствительностью не найдено, остановить калибровочную
   гипотезу до holdout; сохранить отрицательный результат без выдуманного порога.
7. До final holdout outcomes заморозить правила и протокол проверки выбранного
   BALANCED TRIAGE ≤1%; единожды оценить holdout,
   отдельно external device stress и challenges. Опубликовать k/n/U, coverage,
   чувствительность по историям, ограничения sampling и все исключения.
8. Предоставить owner review исходники, полный diff и intended untracked,
   fingerprints, машинные агрегаты и права. Даже успешный R3B не принимает
   production-методы: DQ-G1–G4 / GRID-G1–G4 и M2-A scope закрываются отдельно.

## Оставшиеся решения и проверка R3A

Operating profile/target закрыт решением владельца: BALANCED TRIAGE, ≤1%.
Открыты: финальные размеры и квоты после пилота; допустимый nuisance для benign экспорта;
целевая population/смесь и минимально полезная sensitivity/coverage; бюджет и
права собственных съёмок; converter/encoder provenance; точные research decision
rules и стратегия holdout; затем полные production gates из METHODS.
Решение о выборе корпуса не означает автоматическое разрешение этих шагов.
METHODS не изменяется: существующие owner gates уже отражают эти ограничения.

Проверки R3A: точная арифметика таблицы, согласованность counts/split/ссылок и
статусов, `git diff --check`, просмотр полного diff и нового отчёта, итоговый
`git status --short --untracked-files=all`. Для этой docs-only задачи заданием
разрешены эти узкие проверки; pytest/`uv run poe check` и strict certification
не выполняются. Не заявляется устранение исторического failure M2-R2.
Review bundle remediation
`C:\Users\Vanur\Desktop\m2-r3a-owner-decision-remediation-2026-09-24` вне Git
включает полный новый отчёт, оба изменённых tracked
документа, diff и SHA-256 manifest. Данные, код, зависимости и runtime schema
не изменены; Git mutations отсутствуют. В remediation изменены только этот
отчёт и ROADMAP; REFERENCES сохранён из предыдущего review без изменений.
Выбор профиля принят владельцем; это не принятие методов или полного корпуса.
