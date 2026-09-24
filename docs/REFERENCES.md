# REFERENCES

> Канонический реестр происхождения методов, реализаций, библиотек, статей,
> моделей, весов и значимых исходных данных анализаторов FakeDetector.

## Назначение и правила

Правило проекта: **NO PROVENANCE — NO ANALYZER**.

Этот реестр владеет provenance/licensing и фактами о внешних источниках:
публикациях, реализациях, библиотеках, моделях/весах, datasets, executables и
других компонентах. Конкретные принятые forensic-методы принадлежат `METHODS.md`,
общие интерфейсы — `CONTRACTS.md`, план и статус — `ROADMAP.md`.

`RESEARCH_REFERENCE` не означает принятие production-метода. Научная ссылка
может обосновывать метод, но сама по себе не утверждает пороги, применимость
или finding semantics FakeDetector. Принятые записи `METHODS.md` ссылаются на
стабильные IDs записей REFERENCES (или существующие постоянные якоря разделов),
где это применимо. Исследовательские сравнения хранятся по политике
`research/README.md`; ни отчёт, ни provenance-запись сами не разрешают реализацию.
Описания существующих методов ниже служат контекстом происхождения, не заменяют
методологическую спецификацию. Лицензионные выводы этим разграничением не меняются.

Реальный анализатор не считается завершённым, пока для всех применимых внешних
методов и реализаций не зафиксированы их происхождение, точная версия и лицензия.
Происхождение метода и происхождение реализации указываются раздельно:

- **Method source** отвечает на вопрос, откуда взят метод или концепция;
- **Implementation source** отвечает на вопрос, чей код фактически используется
  или на основе какого кода создана реализация.

Если анализатор использует собственную эвристику проекта, применяется точная
формулировка:

```text
Method source: project-specific heuristic
Implementation source: original FakeDetector implementation
```

Внешние библиотеки при этом перечисляются как building blocks. Наличие статьи,
похожего repository или общей идеи не позволяет приписывать им полный pipeline
FakeDetector. Для каждого анализатора, где применимо, реестр фиксирует:

- `analyzer_id` и `analyzer_version`;
- метод и источник метода или концепции;
- название статьи, авторов, publication/year, DOI или официальный URL;
- источник реализации, library/package, exact version, repository и официальную
  документацию;
- лицензию кода, модели и весов;
- источник модели/весов и значимый dataset оригинальных авторов;
- адаптацию FakeDetector и части, реализованные самим проектом;
- известные ограничения.

Stage 6 MVP является CPU-only. ML-анализаторы, model weights, PyTorch и CUDA в
него не входят; GPU не требуется. Реальные datasets/media на этом этапе в
repository не добавляются. Deterministic generated positive, negative,
false-positive/challenge и boundary/not-applicable fixtures не являются
статистической validation dataset и не должны так описываться.

## Политика сторонних материалов Stage 12

Принятое направление — `PROJECT.md` §20; план допуска методов — `ROADMAP.md`.
Здесь находятся правила реестра и результаты инженерной проверки лицензий,
**не юридическое заключение**. Лицензия собственного кода FakeDetector —
`Apache-2.0` (`PROJECT.md` §21.7). Лицензия библиотеки не становится лицензией всего
продукта, а выбор лицензии продукта не отменяет прав сторонних авторов.

### Категории происхождения

Это категории документационного реестра, не новые enum/поля runtime-контрактов.
Один анализатор может ссылаться на несколько записей разных категорий.

| Категория | Что фиксируется и проверяется отдельно |
|---|---|
| `FIRST_PARTY_CODE` | Собственная реализация, авторство и метод; Apache-2.0, корневой `LICENSE`; внешние building blocks указываются отдельно |
| `RUNTIME_LIBRARY` | Точная версия, источник/артефакт, платформа, транзитивные и встроенные компоненты, их лицензии и уведомления |
| `ADAPTED_EXTERNAL_CODE` | Исходный repository/commit/файлы, авторы, объём копирования/адаптации, лицензия и сохранённые уведомления об изменениях |
| `EXTERNAL_EXECUTABLE` | Поставщик, версия и сборка бинарника, флаги, связанные библиотеки, условия запуска/распространения; bundled или внешняя предпосылка |
| `RESEARCH_REFERENCE` | Статья/стандарт/метод и официальная ссылка; это не разрешение копировать код, иллюстрации или данные |
| `MODEL_ARCHITECTURE` | Источник описания архитектуры и отдельно источник её реализации; в Stage 12 только исследование |
| `MODEL_WEIGHTS` | Правообладатель, версия/hash/URL весов, отдельные условия использования и распространения, происхождение обучения; вне реализации Stage 12 |
| `DATASET` | Версия/источник, лицензия набора и права на исходные записи/лица/голоса, допустимые цели и публикация производных данных |
| `BENCHMARK` | Происхождение протокола, кода оценки, метрик, разделений и данных; ограничения доступа/публикации результатов |
| `GENERATED / TEST MEDIA` | Генератор, параметры и исходные материалы, права на них и на результат, воспроизводимость; синтетическая фикстура не является валидирующим корпусом |

### Обязательная запись перед допуском

**NO PROVENANCE — NO ANALYZER** распространяется на каждый реально используемый
компонент метода. Запись должна отвечать на следующие вопросы:

1. Каков научный/методический источник (авторы, статья/стандарт, год, DOI/URL)
   либо какая часть является собственной эвристикой?
2. Чей код используется, копируется или адаптируется; каковы точная версия/commit,
   источник, затронутые файлы и собственные изменения?
3. Какие лицензии относятся к коду и библиотекам, включая транзитивные/native
   части точного бинарного артефакта; где проверены тексты и уведомления?
4. Есть ли модель/веса; каковы отдельные источники, hash и условия весов?
   Если их нет — явно «не применяется».
5. Какие datasets, benchmark и исходные записи использованы; разрешены ли
   обучение, оценка, публикация примеров и производных данных в предполагаемом режиме?
6. Разрешено ли коммерческое использование и отдельно повторное распространение
   каждого материала? При условиях перечислить их; неизвестное не означает разрешённое.
7. Какие attribution/NOTICE, сведения об изменениях, исходники, условия
   перелинковки/замены библиотеки или иные обязанности требуются?
8. Что действительно включено в wheel/ZIP/другой артефакт, что устанавливается
   отдельно и что лишь цитируется? Зафиксировать целевую платформу и способ поставки.
9. Какие patent/IP вопросы остаются открытыми, кто и когда проверял запись,
   каков итог допуска именно для этого сценария?

Результат проверки фиксируется словами: допущено для указанного сценария,
только исследование, требуется выяснение или отклонено для ядра. Это не
runtime-механизм и не новый конфигурационный флаг. Неполная запись не допускает
реализацию к выпуску; обновление версии/платформы/способа поставки требует
повторной проверки. Ссылки на `main`/`master` — навигация; для допуска нужны
versioned тексты либо идентифицируемый артефакт и сохранённое свидетельство проверки.

### Критерии отбора и недопустимые упрощения

Предпочтительны собственные реализации и зависимости с разрешительными лицензиями
при выполнении их условий. Будущие численные/STFT-библиотеки, JPEG-парсеры,
декодеры, фильтрующие ядра и средства benchmark проходят один и тот же допуск;
Macro 0 не утверждает конкретный новый пакет. Copyleft требует разбора реального
способа интеграции и распространения, а не автоматического запрета коммерции.
Research-only, academic-only и noncommercial материалы не допускаются в Stage 12
CORE, если их условия ограничивают предполагаемый коммерчески применимый продукт.
Они могут остаться `RESEARCH_REFERENCE` только в пределах разрешённого использования.

Не применять следующие подмены:

- публичный GitHub repository сам по себе не даёт разрешительной лицензии;
- GPL/AGPL не означают запрет коммерческого использования; обязанности copyleft
  и право брать оплату — разные вопросы (для AGPL отдельно учитывать сетевой сценарий);
- запуск отдельного executable не является автоматическим освобождением от
  лицензионных условий: существенны связь компонентов и фактическая поставка;
- опубликованная статья не разрешает копирование чужой реализации;
- лицензия кода модели не покрывает веса автоматически;
- лицензия dataset не гарантирует прав на каждую исходную запись;
- лицензия framework не заменяет лицензии включённых методов;
- разрешительная copyright-лицензия не доказывает отсутствие сторонних патентов.

## Текущая проверка лицензий — 2026-09-20

### Область и доказательства

Проверен baseline `8d6c3c35c8c50f0b0e2fa916d892fa5612c36b2d`:
`pyproject.toml`, `uv.lock`, каталог анализаторов, `scripts/release_tooling/kit.py`,
`build.py`, README и `MVP_HANDOFF.md`. Версии ниже сопоставлены с локальными
distribution metadata и текстами лицензий в `.venv/Lib/site-packages` на
Windows x64 / CPython 3.12.10. Это проверка имеющихся зависимостей и способа
поставки, не новая сертификация ZIP и не проверка всех платформенных wheels.

Текущий kit содержит wheel FakeDetector, runtime constraints, `LICENSE`, config,
`.env.example`, генератор demo, `MVP_HANDOFF.md`, `CHANGELOG.md` и manifest.
Зависимости устанавливаются отдельно по constraints; Python, uv и внешние
ffmpeg/ffprobe в kit не включены. Wheel FakeDetector содержит пакет приложения,
а не wheelhouse зависимостей. На указанном baseline project `LICENSE` и
`[project].license` отсутствовали. В Pass 2 Macro 0 добавлены официальный
`LICENSE`, `license = "Apache-2.0"`, `license-files = ["LICENSE"]` и обязательная
копия лицензии в kit. Это изменение собственного кода, не лицензий зависимостей.

### Прямые runtime-зависимости

Версия — из lock и установленной среды, лицензия — из текста поставки;
официальная ссылка позволяет проверить upstream. Общие обязанности описаны
после таблицы, особенности бинарных компонентов — отдельно ниже.

| Пакет | Версия | Лицензия основного кода / источник | Существенное для поставки |
|---|---|---|---|
| fastapi | 0.139.2 | [MIT](https://github.com/fastapi/fastapi/blob/master/LICENSE) | Сохранение copyright и текста разрешения |
| jinja2 | 3.1.6 | [BSD-3-Clause](https://github.com/pallets/jinja/blob/3.1.6/LICENSE.txt) | Уведомления, disclaimer, запрет приписывать поддержку авторам |
| numpy | 2.5.2 | BSD-3-Clause; [upstream](https://github.com/numpy/numpy/blob/v2.5.2/LICENSE.txt) | Лицензия основного кода не исчерпывает Windows wheel; см. native-компоненты |
| opencv-python-headless | 4.14.0.94 / OpenCV 4.14.0 | OpenCV Apache-2.0, Python packaging MIT; ссылки в разделе OpenCV ниже | Полный `LICENSE-3RD-PARTY.txt`, в том числе FFmpeg LGPL; не считать весь wheel Apache-only |
| pillow | 12.3.0 | [MIT-CMU](https://github.com/python-pillow/Pillow/blob/12.3.0/LICENSE) | Сохранить условия MIT-CMU и отдельные bundled notices; это не просто MIT |
| pydantic | 2.13.4 | [MIT](https://github.com/pydantic/pydantic/blob/main/LICENSE) | Учитывать отдельный нативный `pydantic-core` |
| python-multipart | 0.0.32 | [Apache-2.0](https://github.com/Kludex/python-multipart/blob/master/LICENSE.txt) | Копия лицензии, сохранение применимых уведомлений; условия изменений/NOTICE при применимости |
| pyyaml | 6.0.3 | [MIT](https://github.com/yaml/pyyaml/blob/main/LICENSE) | В Windows есть `yaml/_yaml.cp312-win_amd64.pyd`; также проверять используемый LibYAML |
| uvicorn[standard] | 0.51.0 | [BSD-3-Clause](https://github.com/Kludex/uvicorn/blob/main/LICENSE.md) | `standard` расширяет транзитивный/native состав; нельзя учитывать только uvicorn |

MIT требует сохранить copyright и текст разрешения в копиях/существенных частях.
BSD-3-Clause дополнительно задаёт правила уведомлений для бинарной поставки,
disclaimer и запрет endorsement без разрешения. MIT-CMU содержит собственные
условия уведомлений и использования имён; текст не заменяется обычным MIT.
Apache-2.0 требует передать лицензию, отметить изменения и сохранить применимые
уведомления; если upstream поставляет NOTICE, перенести требуемую атрибуцию.
Выбор MIT для FakeDetector не снимает Apache-условия его зависимостей.

### Транзитивные и нативные компоненты

Значимые группы по `uv.lock` и локальным license files (не полный dump dev-среды):

- HTTP/шаблоны: `starlette==1.3.1`, `MarkupSafe==3.0.3` — BSD-3-Clause;
  `anyio==4.14.2`, `h11==0.16.0`, `annotated-doc==0.0.4` — MIT;
  `idna==3.18` — BSD-3-Clause.
- Валидация: `pydantic-core==2.46.4`, `annotated-types==0.8.0`,
  `typing-inspection==0.4.2` — MIT; `typing-extensions==4.16.0` — PSF-2.0.
- Uvicorn standard: `click==8.4.2`, `python-dotenv==1.2.2`,
  `websockets==16.1.1` — BSD-3-Clause; `colorama==0.4.6`,
  `httptools==0.8.0`, `watchfiles==1.2.0` — MIT. У httptools отдельно присутствуют
  `licenses/vendor/http-parser/LICENSE-MIT` и `licenses/vendor/llhttp/LICENSE`.
  `uvloop==0.22.1` есть в универсальном lock, но не в проверенной Windows-среде;
  перенос на другую платформу требует аудита её выбранных артефактов.
- NumPy Windows: `numpy-2.5.2.dist-info/licenses/LICENSE.txt` фиксирует OpenBLAS
  (BSD-3-Clause), LAPACK (BSD-3-Clause-Open-MPI) и GCC runtime
  (`GPL-3.0-or-later WITH GCC-exception-3.1`) внутри `numpy.libs/libscipy_openblas*.dll`.
  Само metadata expression `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`
  не заменяет этот текст. Проверяются условия runtime exception, сохраняются
  лицензии и notices; наличие GPL-текста с исключением не равно автоматическому
  требованию перевести FakeDetector под GPL.
- OpenCV Windows: `cv2/LICENSE.txt` содержит MIT упаковки,
  `cv2/LICENSE-3RD-PARTY.txt` — Apache-2.0 OpenCV и LGPLv2.1 для FFmpeg.
  Этот FFmpeg входит в зависимость независимо от внешнего `ffmpeg.exe`.
  Headless не означает «без FFmpeg». Qt и ряд перечисленных там библиотек
  относятся только к другим платформам/не-headless вариантам; нельзя переносить
  весь список на Windows без проверки конкретного wheel.
- Pillow Windows: `pillow-12.3.0.dist-info/licenses/LICENSE` включает собственный
  MIT-CMU и notices для brotli, FreeType, HarfBuzz, lcms2, libavif, libjpeg-turbo,
  libpng, libwebp, OpenJPEG, TIFF, xz, zlib-ng. FreeType содержит альтернативы
  FTL/GPL; для разрешительной поставки проверяется вариант FTL с его attribution,
  а не объявляется GPL-лицензия всего Pillow. Для JPEG-компонентов сохраняются
  IJG/BSD-уведомления; полный файл, а не эта выборка, определяет обязанности.

Контрольные SHA-256 прочитанных bundled license files (это хэши текстов,
**не** hashes wheels и не сертификат их происхождения):

| Файл установленного пакета | SHA-256 |
|---|---|
| `numpy-2.5.2.dist-info/licenses/LICENSE.txt` | `a804dff0ead9fadc5293456410bcbfc32bf024be9c4513459663fb7b442d2341` |
| `opencv_python_headless-4.14.0.94.dist-info/LICENSE-3RD-PARTY.txt` | `e24e3768561906cc7ccba808f2e8bb4b4bcb2988fece11656b7b56cf14da6bc5` |
| `pillow-12.3.0.dist-info/licenses/LICENSE` | `4f7866a74802c6326f81faff59a56546b6aec2b10b91973e0e9308de95e79857` |

Нативные `.pyd` у pydantic-core, watchfiles и PyYAML не становятся полностью
проверенными по одному top-level License-Expression. Полный состав статически
включённых библиотек и необходимых notices проверяется на точных артефактах
перед их повторным распространением. Текущий проход не выполнял бинарную
декомпозицию либо полный аудит всех Rust/C/C++ исходников этих пакетов.

### Python и средства сборки

- Python 3.12 — [PSF License v2 и исторические/включённые лицензии](https://docs.python.org/3.12/license.html).
  Коммерческая и закрытая поставка допустимы при условиях лицензий; при
  распространении Python сохраняются соответствующие тексты и copyright,
  для изменений — требуемое описание. Interpreter сейчас внешний; будущий
  installer/standalone требует отдельного учёта bundled OpenSSL и других частей.
- Build backend `hatchling==1.32.3` закреплён в `pyproject.toml`;
  [upstream Hatch — MIT](https://github.com/pypa/hatch/blob/master/LICENSE.txt).
  `uv` — [Apache-2.0 OR MIT](https://github.com/astral-sh/uv#license).
  Это средства сборки/установки, не runtime libraries FakeDetector и не содержимое
  нынешнего ZIP. Сам факт их использования не задаёт лицензию build output;
  если их код/бинарники когда-либо включаются в поставку, аудит проводится отдельно.
- Dev/test tools не приписываются runtime-поставке. Генератор demo входит в kit
  как собственный код; fixtures и исходные медиа не входят автоматически.

### Внешние FFmpeg / ffprobe

**ФАКТ:** `ffmpeg -L` и `ffprobe -L` в этой среде идентифицировали
`9.0.1-full_build-www.gyan.dev`, флаги `--enable-gpl --enable-version3`
и лицензию **GPL-3.0-or-later**. Это baseline из `MVP_HANDOFF.md`, а не
минимальная допустимая версия. [Gyan](https://www.gyan.dev/ffmpeg/builds/)
также описывает свои основные сборки как GPLv3. Этот вывод не переносится
на все FFmpeg builds: [официальное объяснение FFmpeg](https://ffmpeg.org/legal.html)
различает базовую LGPL и сборки с GPL-компонентами.

**ИНЖЕНЕРНЫЙ ВЫВОД:** текущая поставка требует установленных пользователем
executables и не распространяет их. Это отдельная граница от FFmpeg внутри
OpenCV wheel, а не универсальная юридическая льгота. При будущей поставке
бинарников нужны точные build flags, source provenance, тексты лицензий,
применимый способ предоставления соответствующих исходников и проверка
способа связи с продуктом; LGPL-интеграция также требует проверки условий
замены/перелинковки и reverse engineering для отладки изменений библиотеки.
Не объявлять GPL «некоммерческой» и не считать внешний subprocess достаточным
доказательством совместимости любого сценария.

Патенты на кодеки и иные IP-вопросы остаются самостоятельным screening:
copyright-лицензия FFmpeg не гарантирует свободу от патентных требований.
Macro 0 не меняет tested build, не добавляет executable в kit и не сертифицирует
новую модель распространения.

### Вывод проверки и дальнейшие уведомления

**ФАКТ:** у проверенных прямых библиотек основного кода — разрешительные лицензии;
бинарный состав включает отдельные copyleft/exception и attribution-условия.
Ограничение noncommercial в текущих прямых runtime license files не обнаружено.
Это не заключение «вся бинарная поставка разрешительная».

**ИНЖЕНЕРНАЯ ОЦЕНКА:** ни Apache-2.0, ни MIT не исключены найденными фактами для
собственного кода FakeDetector. Окончательная совместимость зависит от состава
и способа поставки, сохранения уведомлений и выполнения условий native-компонентов.
References-таблица не заменяет тексты LICENSE/NOTICE, которые нужно передавать
получателю при применимом распространении.

### Стратегия уведомлений после выбора Apache-2.0

Корневой `LICENSE` — неизменённый официальный текст
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0.txt).
`[project].license = "Apache-2.0"` и `license-files = ["LICENSE"]`
задают современную SPDX/PEP 639 metadata для закреплённого Hatchling.
В sdist лицензия находится в корне пакета, в wheel — в
`fakedetector-<version>.dist-info/licenses/LICENSE`, а в kit — отдельным
обязательным файлом с SHA-256 в manifest. Эти механизмы передают одну лицензию
собственного кода и не включают зависимости в wheel FakeDetector.

Отдельные `NOTICE`/`THIRD_PARTY_NOTICES` сейчас не создаются: в собственных
исходниках и ресурсах нынешней поставки не установлено заимствованного материала
с отдельной атрибуцией, которую требуется перенести в такой файл. Зависимости
устанавливаются отдельными distributions со своими license files;
Python и внешние ffmpeg/ffprobe не включены. Apache-2.0 сама по себе не требует
пустого NOTICE. Это вывод о текущем составе, не освобождение от будущих obligations.
Если будет адаптирован сторонний код/ресурс или изменён способ поставки,
применимые лицензии/NOTICE проверяются и передаются вместе с материалом.

До повторного распространения зависимостей
нужно сопоставить точные wheels с lock/hash/платформой, проверить полный native
состав и собрать применимые тексты, notices и source obligations. Macro 9
повторяет эту проверку для фактической публичной поставки. Создание wheelhouse,
bundling FFmpeg/Python и публикация не разрешаются этой записью.

## Лицензия FakeDetector — Apache-2.0 выбрана владельцем

**ФАКТЫ:** источники — [Apache License 2.0, §§2–6](https://www.apache.org/licenses/LICENSE-2.0),
[Apache licensing FAQ](https://www.apache.org/foundation/license-faq.html)
и [MIT License](https://opensource.org/license/mit). Проверено 2026-09-20.
Решение владельца Pass 2 от 2026-09-20 — **Apache-2.0**; корневой `LICENSE`
и package metadata его оформляют. Сравнение ниже сохраняет основания выбора,
а не открытый вопрос; сторонние компоненты не перелицензируются.

| Критерий | Apache-2.0 | MIT |
|---|---|---|
| Коммерческое/частное использование, модификация, распространение | Разрешены с выполнением условий | Разрешены с выполнением условий |
| Патенты | Явный grant от contributors в пределах §3; прекращается для работы при указанном там патентном иске | Нет явного патентного grant/retaliation в тексте; это не доказательство отсутствия патентных прав |
| Attribution/notice | Копия лицензии, применимые уведомления, отметки изменённых файлов; атрибуция NOTICE при его наличии | Copyright и текст разрешения в копиях/существенных частях |
| Вклады участников | §5 по умолчанию задаёт условия намеренно переданных вкладов, с оговоркой об отдельных соглашениях | Нет аналогичного отдельного раздела; условия приёма вкладов следует ясно сообщить |
| Публичная разработка/GitHub | Подходит; подробнее условия вкладов и патентов | Подходит; короткий знакомый текст |
| Платный продукт/сервис, закрытые интеграции и форки | Возможны при соблюдении условий; нет общего требования открыть собственные дополнения | Возможны при сохранении уведомлений |
| Текущие и будущие MIT/BSD/Apache зависимости | Предварительно пригодна, права dependencies сохраняются | Предварительно пригодна; Apache-компоненты всё равно сохраняют собственные условия |
| Copyleft-совместимость | Apache FAQ различает GPLv3 и GPLv2-only; это не blanket-совместимость всего binary stack | Более простой permissive текст не отменяет GPL/LGPL/AGPL условий зависимостей |
| Простота для пользователя | Больше обязательств и длиннее текст | Минимальная нагрузка уведомлений |

**ИНЖЕНЕРНАЯ РЕКОМЕНДАЦИЯ:** Apache-2.0 предпочтительна для FakeDetector благодаря
явным патентным условиям и правилам вкладов при сохранении коммерческого пути.
Недостатки — больший объём текста и дисциплина notices/изменённых файлов.
MIT — разумная альтернатива при приоритете простоты, с менее явным патентным
регулированием. Обе позволяют сторонним участникам делать коммерческие закрытые
форки: ни одна не резервирует рынок платного продукта исключительно за владельцем.
Ни одна не заменяет проверку прав contributors и патентов третьих лиц;
отдельная CLA не вводится автоматически выбором Apache-2.0.

Лицензия FakeDetector не покрывает автоматически внешние executables,
модели/веса, datasets или реализации из исследовательских ссылок.

## Исследовательские материалы для будущих методов

Эти записи — `RESEARCH_REFERENCE`, не production provenance новых анализаторов
и не разрешение на добавление runtime-зависимостей.

### Noiseprint

- Научный источник: Davide Cozzolino, Luisa Verdoliva, «Noiseprint: A CNN-Based
  Camera Model Fingerprint», [авторский repository и ссылки на работу](https://github.com/grip-unina/noiseprint).
- [Официальная LICENSE.txt](https://github.com/grip-unina/noiseprint/blob/master/LICENSE.txt),
  проверенная 2026-09-20, ограничивает использование информационными/
  некоммерческими целями и запрещает неразрешённое промышленное/прибыльное
  использование. Оригинальные код и веса не интегрируются в Stage 12 core
  при рассмотренных ограничительных условиях; отдельное разрешение на
  коммерческое использование весов этим аудитом не установлено.
- Идея шумового остатка остаётся исследовательским входом. Допустима независимо
  спроектированная собственная классическая noise-residual-consistency эвристика
  с её собственным provenance, без копирования ограниченного кода. Её нельзя
  описывать как «Noiseprint без ML».
- В Stage 13+ возможно отдельное исследование независимо обученного learned
  residual/camera-pipeline подхода: новый provenance, права на обучающие данные,
  лицензия весов и patent/IP review проверяются заново.

### PhotoHolmes

[Официальный README, раздел License](https://github.com/photoholmes/photoholmes#license)
на дату проверки 2026-09-20 прямо различает базовую Apache-2.0 и лицензии
отдельных методов в `src/photoholmes/methods/<METHOD>`; пример TruFor содержит
ограничение nonprofit. Framework нельзя принимать как целиком
Apache-совместимую зависимость. Для конкретного заимствования проверяются точная
версия метода, файлы, веса и данные; сейчас библиотека не добавляется.

## Исследование JPEG-зависимостей Macro 1 — 2026-09-20

Категория: `RUNTIME_LIBRARY`. Ниже сохранены результаты исследовательского
Pass 1 от 2026-09-20; тогда зависимости проекта не менялись. По принятому G1
в M1-B от 2026-09-21 интегрирован только `pyjpegio==0.3.0`, см. запись ниже.
Решение владельца и последовательность реализации находятся в `ROADMAP.md`.
Модели, веса и datasets не использовались.

### pyjpegio 0.3.0

- Источник: [релиз PyPI](https://pypi.org/project/pyjpegio/0.3.0/),
  [исходники v0.3.0](https://github.com/dwgoon/jpegio/tree/v0.3.0).
  PyPI attestation указывает commit
  `cf402ff8ba615660e2882d31e342964312c87f1f` и workflow `deploy.yml`.
  Distribution называется `pyjpegio`, import — `jpegio`; это не старый
  PyPI distribution `jpegio==0.2.8`.
- Проверен точный `pyjpegio-0.3.0-cp312-cp312-win_amd64.whl`, опубликованный
  2026-07-04: **238 459 байт**, сумма несжатых ZIP members **805 532 байта**.
  SHA-256: `b3c7dcccf6b6eac9ed5aabe9a18a7cbc0b7c746707baf3479a779cdf094c4701`.
  Архив загружен с PyPI и исследован без установки в окружение проекта.
- Metadata: Python ≥3.9, `numpy>=1.23`, Development Status `4 - Beta`.
  Default binding — CPython C API/C++; vendored libjpeg-turbo статически
  линкуется. Сборка из исходников требует C/C++ compiler и CMake, а wheel
  не требует компилятора получателя. SIMD/NASM относится к сборке.
  Основание: [setup.py](https://github.com/dwgoon/jpegio/blob/v0.3.0/setup.py)
  и metadata проверенного wheel.
- Лицензия wrapper — [Apache-2.0](https://github.com/dwgoon/jpegio/blob/v0.3.0/LICENSE).
  Wheel действительно содержит `LICENSE`, `NOTICE`,
  `third_party/libjpeg-turbo/LICENSE.md` и `README.ijg` в `.dist-info/licenses`.
  [NOTICE](https://github.com/dwgoon/jpegio/blob/v0.3.0/NOTICE) указывает
  **libjpeg-turbo 3.2.0**, IJG/BSD-3-Clause и zlib для SIMD. Коммерческое
  использование допускается при соблюдении соответствующих условий;
  top-level Apache не заменяет bundled notices и IJG attribution.
- API предоставляет native quantized `coef_arrays`, `quant_tables`,
  `comp_info`, precision и coding facts; spatial decode по умолчанию выключен.
  Код читает полный сжатый файл и сохраняет APP/COM markers; это не streaming
  coefficient decoder. C API возвращает int32 views с удержанием native owner.
  Основания: [README](https://github.com/dwgoon/jpegio/blob/v0.3.0/README.md),
  [jstruct.cpp](https://github.com/dwgoon/jpegio/blob/v0.3.0/src/jpegio/_backend/jstruct.cpp),
  [binding](https://github.com/dwgoon/jpegio/blob/v0.3.0/src/jpegio/_capi/decompressedjpeg.cpp).
  README отдельно указывает происхождение базового C/C++ кода из лаборатории
  Jessica Fridrich; источник метода не приписывается FakeDetector.

Проведён отдельный ограниченный smoke: новый venv вне repository, CPython
3.12.10 / Windows x64, binary-only установка `pyjpegio==0.3.0` и
`numpy==2.5.2`, запуски с `-I` из внешнего cwd. Import origin находится в
исследовательском `site-packages`, checkout в `sys.path` отсутствует.
Малые JPEG fixtures созданы существующим Pillow, без внешних медиа.

| Проверка | Наблюдаемый результат |
|---|---|
| Baseline RGB 17×13, subsampling 4:2:0 | Чтение успешно; int32 planes 16×24, 8×16, 8×16; две quantization tables |
| Progressive RGB 17×13, 4:4:4 | Чтение успешно; три planes 16×24; progressive flag установлен |
| Grayscale 17×13 | Чтение успешно; один plane 16×24 и одна quantization table |
| Не-JPEG и удаление последних 50 байт JPEG | Python `RuntimeError`; второй случай также выводит bounded-observed warning в stderr |
| Удаление только двух байт EOI | Возвращаются coefficients и 27 байт stderr: успешный return не доказывает целостность JPEG |
| Существующий JPEG с кириллицей в абсолютном имени | `RuntimeError`; Python подтверждает наличие файла |
| Unicode cwd и ASCII basename в отдельном child | Чтение успешно без копирования файла; релевантно существующему controlled source с именем `source` |

Это свидетельство работы точного installed dependency wheel, а не сертификация
FakeDetector с новой зависимостью, fuzzing или доказательство отсутствия native
дефектов. В частности, fatal-error handler не отменяет soft recovery; raw native
exceptions/stderr могут содержать private details. Полная integration/resource/
reap/cleanup матрица остаётся критерием будущей реализации.

### Сравниваемые альтернативы

- **jpeglib 1.0.2**: [PyPI](https://pypi.org/project/jpeglib/1.0.2/) публикует
  `jpeglib-1.0.2-cp38-abi3-win_amd64.whl` от 2025-09-18,
  **9 852 148 байт**; tag совместим с CPython 3.12 x64.
  Metadata dependencies — `numpy`, `wheel`, `setuptools`; библиотека поставляет
  несколько версий libjpeg/libjpeg-turbo/mozjpeg, предоставляет DCT/quantization
  API. Wrapper — MPL-2.0; коммерческое использование допустимо, но при
  распространении действуют обязанности по covered source/notices, отдельно
  проверяются bundled codec licenses. [Mozilla FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/)
  объясняет file-level copyleft и совместимость larger work с Apache-кодом.
  [read_dct v1.0.2](https://github.com/martinbenes1996/jpeglib/blob/1.0.2/src/jpeglib/functional.py)
  прямо предупреждает о возможном завершении процесса libjpeg; функция также
  читает полный файл. В этом проходе этот wheel не устанавливался и его
  bundled license inventory не сертифицирован.
- **jpegio 0.2.8**: [старый distribution](https://pypi.org/project/jpegio/0.2.8/)
  от 2021-10-15 не содержит Windows CPython 3.12 wheel; не путать с проверенным
  `pyjpegio`. Source build не подтверждает требуемую Windows-поставку.
- **Собственный parser / существующий Pillow**: публичный Pillow
  [JPEG API](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg)
  предоставляет quantization tables, но не native quantized coefficient API.
  По [ITU-T T.81](https://www.w3.org/Graphics/JPEG/itu-t81.pdf) header/marker facts
  и entropy decoding — разные задачи: восстановление native coefficients
  требует обработки scans, Huffman/arithmetic coding, restarts и progressive
  refinement. DCT декодированных RGB-пикселей не воспроизводит исходные
  quantized coefficients. Малый собственный header parser не является заменой
  такого decoder. Private ABI библиотек, встроенных в Pillow/OpenCV, не является
  проверенным независимым installed-wheel интерфейсом.

### Проверка арифметики JPEG preflight M1-A — 2026-09-21

Проверены официальные исходники **libjpeg-turbo 3.2.0**:
[jdinput.c](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/3.2.0/src/jdinput.c)
вычисляет размеры component blocks через округление отношения размеров и
sampling factors вверх;
[jdcoefct.c](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/3.2.0/src/jdcoefct.c)
резервирует full-image coefficient arrays с округлением обоих измерений до
sampling-factor blocks. На этом основано разделение выдаваемых и native padded
коэффициентов в M1-A. Реализована собственная арифметическая оценка и тесты,
сторонний код не копировался. Это проверка формул, не повторный wheel smoke
и не доказательство ограничения всего native RSS; вызов `pyjpegio` в M1-A
отсутствует. Принятый выбор зависимости и ограничения описаны в
`CONTRACTS.md` §7.5, статус реализации — в `ROADMAP.md`.

### Интеграция pyjpegio 0.3.0 в M1-B — 2026-09-21

`uv add pyjpegio==0.3.0` добавил точный runtime pin и штатно обновил `uv.lock`.
Windows CPython 3.12 использует тот же wheel и SHA-256, что исследованы выше;
Apache-2.0 wrapper и bundled libjpeg-turbo 3.2.0 notices не изменились.
При распространении wheel/сборки зависимости необходимо сохранять `LICENSE`,
`NOTICE`, libjpeg-turbo `LICENSE.md` и `README.ijg`; разрешение коммерческого
использования не отменяет обязанностей при redistribution. FakeDetector не
копирует исходники wrapper/codec и не выдаёт библиотеку за forensic method.

Граница адаптации — собственный bounded marker parser, resource preflight,
изолированный child и typed raw coefficient artifacts. Реализованный контракт
находится в `CONTRACTS.md` §7.5. По установленному `_backend/jstruct.cpp`
подтверждено: `quant_tables` — компактный список в порядке возрастания slot IDs,
а selectors компонентов сохраняют исходные IDs; fixture с IDs 0/3 проходит.
Missing EOI отвергается до native decode; warning при повреждённой entropy
приводит к отказу без сохранения raw stderr.

Для Windows child проверен механизм CPython 3.12.10
[getpath.py](https://github.com/python/cpython/blob/v3.12.10/Modules/getpath.py):
реальный interpreter с явно заданным `__PYVENV_LAUNCHER__` сохраняет venv,
обходя дополнительный процесс redirector. PID проверен относительно Popen;
код CPython не копировался. NumPy native pool ограничен одним OpenBLAS thread.
Это частная граница поддерживаемого CPython 3.12, не обещание совместимости
с произвольными Python launchers.

Наблюдение Windows `GetProcessMemoryInfo(PeakWorkingSetSize)` после reap
реального decoder PID, один запуск каждого generated fixture:

| JPEG | MCU-padded coefficients | Raw int32 bytes | Peak working set, bytes |
|---|---:|---:|---:|
| RGB 17×17 baseline 4:2:0 | 1536 | 4352 | 69 025 792 |
| RGB 1664×1664 progressive 4:2:0 | 4 153 344 | 16 613 376 | 72 519 680 |
| Grayscale 2048×2048 baseline | 4 194 304 | 16 777 216 | 78 290 944 |

Peak pagefile/commit counters: 59 215 872 / 59 105 280 / 59 338 752 байт
соответственно. Это наблюдения полной среды child, включая imports; они не
являются верхней границей для любых данных. При обычном NumPy thread pool
наблюдалось около 0.8 GB commit, что обосновывает явный лимит threads.
Ограничение коэффициентов и output не является process-wide hard RAM sandbox;
Windows Job Object RAM quota не реализована. Риск native allocations/дефектов,
общего RSS с parent и нескольких одновременных задач перенесён в M1-G.
Installed-wheel проверка M1-B встроена в `scripts/verify_release_package.py`;
strict clean-tree certification остаётся отдельной проверкой M1-G.

## M2-R1 — исследование JPEG DQ/grid, 2026-09-23

Все записи ниже имеют категорию **RESEARCH_REFERENCE**, итог допуска —
**только исследование**. Проверены агентом 2026-09-23 по указанным первичным
источникам; owner acceptance метода отсутствует. Применение в предложениях —
[METHODS.md](METHODS.md#кандидаты-stage-12--macro-2), сравнение —
[исследовательский отчёт](research/2026-09-23-jpeg-dq-grid-method-selection.md).

Статьи/стандарты цитируются, а не включаются в wheel, ZIP или репозиторий.
Текст, иллюстрации, код, datasets и демонстрационные изображения не копируются
в продукт. Для всех записей: моделей/весов нет; внешние datasets в M2-R1 не
использовались, лицензии данных из экспериментов авторов не считаются допуском
проектного корпуса. Patent clearance не проводился; ссылка и собственная
реализация не доказывают отсутствие IP-ограничений. Неустановленные права
повторного распространения не трактуются как разрешённые.

<a id="jpeg-t81"></a>

### JPEG-T81 — стандарт JPEG

- Авторы: CCITT/ITU-T и ISO/IEC JTC 1; *Digital compression and coding of
  continuous-tone still images — Requirements and guidelines*, 1992;
  Recommendation T.81 / ISO/IEC 10918-1:1994.
- Источник: [T.81, PDF на W3C](https://www.w3.org/Graphics/JPEG/itu-t81.pdf).
- Использовано: Annex A/F/G/B — 8×8 DCT, квантование, components/sampling,
  последовательный и progressive режимы, DQT selectors. Header хранит текущие
  таблицы, не журнал предыдущих сохранений. Quality label не заменяет DQT.
- Implementation source: не применяется, стандарт не код. Лицензия текущего
  `pyjpegio==0.3.0` отдельно проверена в записи Macro 1 выше; допуск стандарта
  для чтения не разрешает перепубликовать PDF или чужой decoder.

<a id="jpeg-pf04"></a>

### JPEG-PF04 — гистограммная периодичность DQ

- Alin C. Popescu, Hany Farid. *Statistical Tools for Digital Forensics*.
  Information Hiding 2004, LNCS 3200, pp. 128–147, 2004.
- [Авторский PDF](https://farid.berkeley.edu/downloads/publications/ih04.pdf),
  [DOI 10.1007/978-3-540-30114-1_10](https://doi.org/10.1007/978-3-540-30114-1_10).
- Прочитан §3, особенно §§3.2–3.3: периодическое перераспределение histogram
  bins, спектральные пики и вырожденные отношения квантов. Демонстрации статьи
  не задают переносимый рабочий порог FakeDetector. В статье для вывода
  используется floor; rounding-модель предложения обозначена отдельно.
- Implementation source: код не использован. Право коммерческого копирования
  текста/кода не установлено; научное цитирование не означает такую лицензию.

<a id="jpeg-lf03"></a>

### JPEG-LF03 — первичная таблица и неоднозначность

- Jan Lukáš, Jessica Fridrich. *Estimation of Primary Quantization Matrix in
  Double Compressed JPEG Images*. Digital Forensic Research Workshop, 2003.
- [Авторский PDF, SUNY Binghamton](https://ws2.binghamton.edu/fridrich/Research/Doublecompression.pdf).
- Прочитаны §§2–4: missing values, peak/valley и double peaks, зависимость
  от q1/q2, округления и реализации DCT; первичная таблица восстанавливается
  не во всех случаях. В работе сопоставляются оценочные подходы, включая
  neural-network classifier; этот classifier не предлагается для Stage 12.
- Implementation source: отсутствует; ни код, ни обученные параметры не взяты.
  Права на их коммерческую поставку не проверены; запись — только ссылка.

<a id="jpeg-pf08"></a>

### JPEG-PF08 — обучение на гистограммных признаках

- Tomáš Pevný, Jessica Fridrich. *Estimation of Primary Quantization Matrix
  for Steganalysis of Double-Compressed JPEG Images*. SPIE 6819, 681911, 2008.
- [Авторский PDF](https://ws2.binghamton.edu/fridrich/Research/paper_3_color.pdf),
  [DOI 10.1117/12.759155](https://doi.org/10.1117/12.759155).
- Использованы abstract и описание feature/classifier pipeline: low-frequency
  DCT histograms для SVM detection/primary-step estimation. Это альтернатива
  простому измерению, требующая обученного decision boundary; она не становится
  детерминированным безобучающим порогом только из-за фиксированного inference.
- Implementation source: отсутствует. Код, модели, training corpus и их права
  не проверены и не допускаются этой записью.

<a id="jpeg-bp12"></a>

### JPEG-BP12 — aligned/non-aligned likelihood maps

- Tiziano Bianchi, Alessandro Piva. *Image Forgery Localization via
  Block-Grained Analysis of JPEG Artifacts*. IEEE Transactions on Information
  Forensics and Security 7(3), pp. 1003–1017, 2012.
- [DOI 10.1109/TIFS.2012.2187516](https://doi.org/10.1109/TIFS.2012.2187516),
  [авторская версия в Politecnico di Torino](https://iris.polito.it/retrieve/e384c42e-2465-d4b2-e053-9f05fe0a1d67/bian_TIFS2012_OA.pdf).
- Прочитаны §§III–V, Algorithms 2/3, equations 18–22: отдельные A-DJPG и
  NA-DJPG модели, likelihood maps, оценка q1/mixture и ROC-выбор operating point.
  Отношение likelihood >1 не обеспечивает заданную production FPR.
- Implementation source: отсутствует. Внешний MATLAB/code не копировался;
  license такого кода не проверена. Собственная будущая реализация требует
  отдельного точного профиля и provenance, не вывода лицензии из IEEE PDF.

<a id="jpeg-niu19"></a>

### JPEG-NIU19 — повторное сжатие с той же таблицей

- Yakun Niu, Xiaolong Li, Yao Zhao, Rongrong Ni. *An enhanced approach for
  detecting double JPEG compression with the same quantization matrix*.
  Signal Processing: Image Communication 76, pp. 89–96, 2019.
- [Страница издателя, abstract и открытый preview](https://www.sciencedirect.com/science/article/abs/pii/S0923596518309196),
  [DOI 10.1016/j.image.2019.04.016](https://doi.org/10.1016/j.image.2019.04.016).
- Использованы доступные abstract/introduction: repeated recompression и
  random perturbation как отдельная семья для same-table случая; ограничение
  при низком качестве. Полный алгоритм по paywalled частям не проверен;
  production формулы и thresholds из него не заимствуются.
- Implementation source: отсутствует; код, параметры, datasets и права
  коммерческой поставки не проверены. Отказ от этой семьи в текущем scope
  обусловлен требованием нового экспериментального codec pipeline, а не
  утверждением, что задача same-table принципиально всегда неразрешима.

<a id="jpeg-grid20"></a>

### JPEG-GRID20 — локальная решётка по blocking artifacts

- Tina Nikoukhah, Miguel Colom, Jean-Michel Morel, Rafael Grompone von Gioi.
  *Local JPEG Grid Detector via Blocking Artifacts, a Forgery Detection Tool*.
  Image Processing On Line 10, pp. 24–42, 2020.
- [Издание, DOI 10.5201/ipol.2020.283](https://www.ipol.im/pub/art/2020/283/),
  [полный текст](https://www.ipol.im/pub/art/2020/283/article_lr.pdf).
- Прочитаны Algorithm 1, §§2–5: cross-difference (с указанием происхождения
  от Chen/Hsu 2008), phase votes, binomial-tail NFA, epsilon=1, window support,
  сложность и false grids от upsampling. Формулы native-coordinate/bounded
  окон FakeDetector не приписываются авторам.
- Статья помечена CC-BY-NC-SA; не копировать её текст/рисунки в коммерческий
  продукт. Издание указывает **AGPL-3.0-or-later**, software v2.0, SWH directory
  `ec361fe603bb131ceb72d7fb39cd6856c1f6c06c` для reference code.
  [Авторский repository GOD](https://github.com/tinankh/GOD) использован только
  как указатель реализации, не как источник кода. AGPL не запрещает коммерцию,
  но интеграция/распространение требуют отдельного разбора обязательств;
  этой задачей они не разрешены. Предлагается собственная реализация по
  математическому описанию, без copying/translation reference source.

<a id="jpeg-zero21"></a>

### JPEG-ZERO21 — альтернативный grid detector

- Tina Nikoukhah, Jérémy Anger, Miguel Colom, Jean-Michel Morel,
  Rafael Grompone von Gioi. *ZERO: a Local JPEG Grid Origin Detector Based on
  the Number of DCT Zeros and its Applications in Image Forensics*.
  Image Processing On Line 11, pp. 396–433, 2021.
- [Издание, DOI 10.5201/ipol.2021.390](https://www.ipol.im/pub/art/2021/390/),
  [полный текст](https://www.ipol.im/pub/art/2021/390/article_lr.pdf).
- Использованы описание метода и §3: оценка DCT zeros на возможных grid origins,
  локальная/global проверка с NFA. Native coefficients только одной текущей
  сетки не заменяют проверку всех фаз по decoded pixels.
- Статья CC-BY-NC-SA; code v4.0 обозначен изданием AGPL-3.0-or-later, SWH
  directory `71b30c873962f1725c6291aa5f08a5691bcb1af4`. Код не загружался и
  не копировался; commercial redistribution/сетевой сценарий не допущены
  этой записью. Предлагаемый продукт не включает ZERO, его изображения или
  datasets. Не переносить лицензию существующего NumPy на чужой алгоритм/code.

<a id="jpeg-m2r1-proposal"></a>

### JPEG-M2R1-PROPOSAL — собственные измерительные профили

- Методические источники: JPEG-PF04/LF03/BP12 и JPEG-GRID20; различия и
  ограничения указаны в `METHODS.md`.
- Method source для конкретных bounded diagnostics/sampling/aggregation:
  **project-specific heuristic**.
- Implementation source: **original FakeDetector implementation** — только
  план будущей реализации; в M2-R1 реализация отсутствует, версии analyzer нет.
  Будущий собственный код подчиняется корневому Apache-2.0; это не
  перелицензирование статей или reference implementations.
- Новые библиотеки, executable, models/weights, datasets отсутствуют.
  Предполагаемые building blocks — уже существующие NumPy/Pillow/pyjpegio;
  их отдельные version/license записи в этом реестре сохраняются.
- Целевая поставка — существующий CPU-only Windows/Python профиль, без
  добавленного внешнего кода. Before-release review должен проверить реальный
  implementation diff, attribution и обязательства фактически используемых
  артефактов; сейчас production/provenance acceptance не заявляется.

<a id="m2-r3a-datasets"></a>
## M2-R3A — кандидаты реального корпуса, 2026-09-24

Инженерная проверка опубликованных условий для внутренней калибровки
коммерчески применимого FakeDetector. Это не юридическое заключение и не
принятие dataset в production. Методический план и сравнение находятся в
[отчёте R3A](research/2026-09-24-jpeg-real-corpus-operating-point-design.md).
Медиа не скачивались; прочитаны страницы и metadata. Никакие dataset files,
производные изображения или внешние реализации не включаются в Git/поставку.
Для R3B нужны per-record manifest, hashes и сохранённые условия выбранных файлов;
проверка страницы набора не заменяет admission каждой записи. Права на
изображённых людей/чужие произведения проверяются отдельно от copyright dataset.

<a id="dataset-raise"></a>
### DATASET-RAISE — не допущен для предполагаемой калибровки

- Категория: `DATASET`, технически рассмотренный кандидат; MMLab, DISI,
  University of Trento. Авторы: Dang-Nguyen, Pasquini, Conotter, Boato;
  *RAISE – A Raw Images Dataset for Digital Image Forensics*, MMSys 2015.
- Provenance: [официальный сайт](https://loki.disi.unitn.it/RAISE/),
  [guide и форматы](https://loki.disi.unitn.it/RAISE/guide.html),
  [правообладатель/контакт](https://loki.disi.unitn.it/RAISE/contact.html).
  8156 camera-native фотографий; NEF и TIFF — связанные версии, не независимые
  samples; три Nikon-модели, природные и бытовые сцены.
- Условия: [download](https://loki.disi.unitn.it/RAISE/download.html) разрешает
  non-commercial research/education с цитированием. Публичная загрузка и
  исследовательское назначение не разрешают автоматически коммерческую калибровку.
- Внутренняя калибровка FakeDetector: **требуется выяснение**, до письменного
  разрешения/уточнения owner/legal использовать нельзя. Включение в CORE не разрешено.
- Распространение исходников/производных: разрешение не установлено.
  Публикация research results предусмотрена с цитированием в разрешённом режиме;
  право коммерческого использования результатов требует отдельного выяснения.
  Размер полной поставки заявлен ~350 GB; есть меньшие поднаборы.

<a id="dataset-pixls-cc0"></a>
### DATASET-PIXLS-CC0 — рекомендуемое отобранное подмножество

- Категория: `DATASET`; PIXLS.US и индивидуальные авторы вкладов.
  Provenance: [сайт/правила приёма](https://raw.pixls.us/),
  [живой metadata-каталог](https://raw.pixls.us/json/getrepository.php?set=all).
  Поставщик просит camera-native RAW, но есть разные режимы/лицензии; история
  каждого master проверяется отдельно. Это camera-compatibility коллекция,
  не случайная выборка пользователей FakeDetector.
- Срез 2026-09-24: 2016 записей, из них 1870 с CC0 URL и 146 с другими
  условиями; 925 точных make/model пар среди CC0, 922 без учёта регистра.
  Показанные kB/MB дают ~55,740 GB при десятичном прочтении и ~58,448 GB при
  двоичном; планировать ~60 GB без производных. Числа получены из metadata, не
  подтверждают столько независимых сцен или устройств. Снимок/hash вне Git.
- Лицензия выбранных записей: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
  Внутренняя калибровка, коммерческое использование, копирование/адаптация и
  распространение разрешены в пределах переданных copyright прав. Attribution
  не является условием CC0, но URL/автор/hash сохраняются для provenance.
- Изображения/производные и собственные агрегаты допускают публикацию в этих
  пределах; CC0 не снимает privacy/trademark/чужие права. Не-CC0 записи не
  входят в рекомендацию. Итог: **пригоден для указанного внутреннего сценария
  после per-record проверки**, не blanket-разрешение на весь архив.

<a id="dataset-vision"></a>
### DATASET-VISION — рекомендуемая внешняя workflow-проверка

- Категория: `DATASET`; CSP Lab, Department of Information Engineering,
  University of Florence. Shullani, Fontani, Iuliani, Al Shaya, Piva,
  *VISION: a video and image dataset for source identification*, 2017,
  [DOI/статья](https://doi.org/10.1186/s13635-017-0067-2).
- Provenance: [официальная поставка](https://lesc.dinfo.unifi.it/VISION/),
  [dataset README](https://lesc.dinfo.unifi.it/VISION/README.txt).
  11 732 native изображения, 34 427 с социальными версиями; 35 portable devices,
  11 брендов. В scope только JPEG-изображения и их группы native/social,
  не 1914 видео. Native не доказывает число внутренних JPEG-проходов камеры.
- **Dataset — CC BY-SA 4.0**, как прямо указано в README, не CC BY 4.0 статьи.
  [Условия лицензии](https://creativecommons.org/licenses/by-sa/4.0/)
  допускают коммерческое использование и внутреннюю калибровку.
- При передаче изображений/адаптаций сохранить attribution, ссылку на условия,
  обозначение изменений, применимый ShareAlike; не вводить дополнительные
  ограничения. Apache-2.0 собственного кода не перелицензирует фотографии.
- Собственные агрегированные измерения без воспроизведения фото можно
  публиковать с цитированием; существенное переиздание базы/адаптаций требует
  отдельного рассмотрения ShareAlike/database rights. Итог: **пригоден для
  внутренней workflow-проверки при выполнении условий**, не разрешение bundling.
  Размер выбранных 600 групп ещё не измерен; план 2–10 GB с социальными версиями.

<a id="dataset-openimages-v7"></a>
### DATASET-OPENIMAGES-V7 — резервный challenge, не single-history corpus

- Категория: `DATASET`; Google LLC — dataset/аннотации, авторы исходных
  фотографий — права на изображения, CVDF — канал доставки.
  [V7 description/licensing](https://storage.googleapis.com/openimages/web/factsfigures_v7.html),
  [download/metadata](https://storage.googleapis.com/openimages/web/download_v7.html).
  Около 9 млн разнообразных изображений; JPEG-поставка не гарантирует ни
  native resolution, ни известную JPEG-историю, ни physical device ID.
- Фото заявлены CC BY 2.0; аннотации — CC BY 4.0. Издатель прямо не гарантирует
  лицензию каждого фото и требует самостоятельной проверки. `OriginalURL`,
  `OriginalLandingURL`, `License`, `Author`, `Title`, `OriginalMD5/Size`
  позволяют документировать конкретную запись, но сами не заменяют проверку.
- По [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) коммерческая
  калибровка и распространение фото/адаптаций возможны с attribution и
  применимым указанием изменений; сохранить предоставленные title/notices,
  не вводить ограничений сверх лицензии. Неясные записи **непригодны до
  уточнения прав**, даже для internal use.
- Собственные агрегаты без фото отделять от перепубликации dataset. Итог:
  **не выбран в основной acquisition** из-за unknown history и стоимости
  per-image rights review; возможен отдельный challenge после проверки.
  Подвыборка 1000 оригиналов: оценка 1–10 GB, уточнить по metadata.

<a id="research-rawpy-m2r3b"></a>
## M2-R3B — исследовательская RAW-проявка

- Инструмент: `rawpy==0.27.1`, wrapper LibRaw; владелец явно разрешил его только
  в отдельном внешнем research environment. В runtime FakeDetector, lock,
  requirements, metadata и release artifacts инструмент не включён.
- Источник: [официальный PyPI release](https://pypi.org/project/rawpy/0.27.1/),
  binary wheel `rawpy-0.27.1-cp312-cp312-win_amd64.whl`, 921 403 bytes;
  SHA-256 `e9d9c83cd0422e84b2052a02eb9d612839ac68dfae4d6d3751740e08024599b1`,
  проверен по JSON PyPI и bytes скачанного wheel. Сборка из исходников не выполнялась.
- rawpy — [MIT](https://github.com/letmaik/rawpy/blob/v0.27.1/LICENSE).
  В поставке wheel присутствует [LICENSE.LibRaw, LGPL 2.1](https://github.com/letmaik/rawpy/blob/v0.27.1/LICENSE.LibRaw).
  Загруженная библиотека сообщает LibRaw `0.22.1`; GPL2/GPL3 demosaic packs
  отключены согласно `rawpy.flags`. Компоненты wheel не перелицензируются
  лицензией собственного кода проекта. Wheel и license snapshots хранятся вне Git.
- Среда измерения: Windows 11 x64, CPython 3.12.10, NumPy 2.5.2, Pillow 12.3.0;
  binary-only установка во внешнее venv. Полные platform/build flags и hashes
  находятся во внешнем provenance bundle.
- [Параметры rawpy](https://letmaik.github.io/rawpy/api/rawpy.Params.html)
  определяют значения postprocess. Фактически использованный единый профиль,
  ограничения CFA, преобразование master и результаты воспроизведения
  документированы в [отчёте пилота](research/2026-09-24-jpeg-real-corpus-pilot.md).
  Embedded previews не являются masters; это offline research preprocessing,
  не расширение production intake и не принятие DQ/Grid.

## M2-BR1 — классические residual/resampling методы, 2026-09-24

Все записи этого раздела — **RESEARCH_REFERENCE**, без допуска production-кода.
Сравнение, фактически выполненные проверки и ограничения находятся в
[исследовательском отчёте](research/2026-09-24-image-noise-resampling-method-selection.md).
Из публикаций заимствованы концепции, не код, изображения, текст алгоритмов
или их числовые пороги. Внешние реализации не запускались и не копировались.
Публичность PDF/GitHub не означает разрешение включения в Apache-2.0 CORE.

| ID | Первичный источник | Принцип и граница рассмотрения |
|---|---|---|
| `NR-MS09` | Babak Mahdian, Stanislav Saic. *Using noise inconsistencies for blind image forensics*, 2009. [DOI](https://doi.org/10.1016/j.imavis.2009.02.001), [авторский PDF в ÚTIA](https://library.utia.cas.cz/separaty/2009/ZOI/saic-using%20noise%20inconsistencies%20for%20blind%20image%20forensics.pdf) | Сегментация по локальным уровням аддитивного белого гауссова шума. Проверен индексируемый abstract/первая страница; полный PDF при повторном доступе недоступен. Детали воспроизведения не подтверждены |
| `NR-CB13` | Miguel Colom, Antoni Buades. *Analysis and Extension of the Ponomarenko et al. Method, Estimating a Noise Curve from a Single Image*, 2013. [DOI/страница](https://doi.org/10.5201/ipol.2013.45), [полный текст](https://www.ipol.im/pub/art/2013/45/article.pdf) | Оценка по высокочастотным DCT-компонентам блоков с малой низкочастотной энергией; зависимость от яркости. Статья прочитана как источник концепции matching; опубликованные параметры не перенесены |
| `RS-PF05` | Alin C. Popescu, Hany Farid. *Exposing Digital Forgeries by Detecting Traces of Resampling*, 2005. [DOI](https://doi.org/10.1109/TSP.2004.839932), [авторский PDF](https://farid.berkeley.edu/downloads/publications/sp05.pdf) | EM-оценка локального предсказателя, периодичность p-map, сравнение спектров. Полный текст; EM-профиль не реализован |
| `RS-MS08` | Babak Mahdian, Stanislav Saic. *Blind Authentication Using Periodic Properties of Interpolation*, 2008. [DOI](https://doi.org/10.1109/TIFS.2004.924603), [авторский PDF в ÚTIA](https://library.utia.cas.cz/separaty/2008/ZOI/saic-blind%20authentication%20using%20periodic%20properties%20ofinterpolation.pdf) | Периодичность ковариации интерполированного сигнала и производных. Проверен индексируемый abstract/первая страница; полный PDF недоступен. Полная Radon-процедура не воспроизведена |
| `RS-K08` | Matthias Kirchner. *Fast and Reliable Resampling Detection by Spectral Analysis of Fixed Linear Predictor Residue*, 2008. [DOI](https://doi.org/10.1145/1411328.1411333), [авторский PDF](https://ws.binghamton.edu/kirchner/papers/2008_MMSec.pdf) | Фиксированный линейный предсказатель вместо EM, спектр остатка и cumulative periodogram. Полный текст; собственный BR1 descriptor не объявляется реализацией статьи |
| `RS-KG09` | Matthias Kirchner, Thomas Gloe. *On Resampling Detection in Re-compressed Images*, 2009. [авторский PDF](https://ws.binghamton.edu/kirchner/papers/2009_WIFS.pdf) | Преобразованные JPEG-следы могут усиливать resampling peaks; последующее сжатие подавляет сигнал и добавляет пики. Полный текст; вариант на JPEG-решётке не выбран |

Лицензии и использование: `NR-MS09` — Elsevier, на первой странице all rights
reserved; `NR-CB13` — на статье CC BY-NC-SA; `RS-K08` — ACM copyright с
ограниченным разрешением personal/classroom copies; `RS-PF05`, `RS-MS08`,
`RS-KG09` — научные IEEE-публикации, разрешительная лицензия реализации не
установлена. Эти сведения о статьях не являются лицензиями программ.
Ни архив IPOL C++, ни внешние forensic repositories не изучались как исходный
код; упоминание доступной реализации не означает её лицензионный допуск.
Никакие PDF, сторонние исходники, модели или веса в поставку не добавлены.

### NR-RS-BR1-FIRSTPARTY — собственные исследовательские профили

- Method source: project-specific heuristic, концептуальные основания — записи
  выше. `N-MAD-MATCH-1` и `R-D2-MATCH-1` — собственные exploratory profiles,
  не Noiseprint, PRNU или source-camera identification.
- Implementation source: **FIRSTPARTY_CODE**, оригинальные внешние scripts
  M2-BR1; повторно использованы private NumPy kernels Macro 1. Building blocks:
  установленный NumPy 2.5.2, OpenCV 4.14.0 (`opencv-python-headless` из lock),
  Pillow 12.3.0 из существующего окружения, Python 3.12.10 и standard library.
  Новых dependencies, SciPy, ML, весов и runtime network нет.
- Данные: 20 VISION native JPEG из уже reviewed exploration manifest M2-R3B,
  не DQ calibration/validation/holdout; лицензия и attribution —
  [DATASET-VISION](#dataset-vision--рекомендуемая-внешняя-workflow-проверка).
  Native не означает отсутствие внутрикамерной обработки. Хэши исходников и
  снимка условий сверены; crop/контролируемые преобразования явно записаны.
- Фотографии, вырезки и contact sheet остаются внешними материалами с
  CC BY-SA 4.0 и attribution CSP Lab/авторов VISION; не перелицензируются в
  Apache-2.0. Четыре процедурных контроля созданы собственным кодом.
  Manifest, scripts, результаты и hashes находятся только в заданном root
  `FakeDetector-Work/research/M2-BR1-noise-resampling/`; в Git — отчёт и ссылки.
- Итог допуска: только исследование. Production promotion, точная спецификация
  Findings и thresholds требуют отдельного gate METHODS и приёмки владельца.

## Общие библиотеки и инструменты

### Python standard library

- Назначение: базовые операции, hashing и техническая обработка без внешней
  runtime dependency для `audio_pcm_quality`.
- Версия runtime: Python 3.12.
- Документация: <https://docs.python.org/3.12/>.
- Source: <https://github.com/python/cpython>.
- License: PSF License; <https://docs.python.org/3.12/license.html>.

Фактически используются `wave`, `array`, `math` и `sys` для потокового чтения и
расчёта PCM-метрик, а также `hashlib` и `json` для content-addressed `finding_id`.

### Pillow

- Назначение: доступ к image metadata и sampled frames как implementation
  building block.
- Текущая dependency: `pillow>=12.3.0`; текущая разрешённая lock-версия —
  `12.3.0`.
- Repository: <https://github.com/python-pillow/Pillow>.
- Документация: <https://pillow.readthedocs.io/>.
- License: MIT-CMU; <https://github.com/python-pillow/Pillow/blob/12.3.0/LICENSE>.

### OpenCV

- Назначение: компонент реализации для ORB-дескрипторов и подбора модели методом
  RANSAC в `image_copy_move_correspondence`.
- Фактическая версия пакета: `opencv-python-headless==4.14.0.94`; фактическая
  версия OpenCV: `4.14.0`.
- Репозиторий исходного проекта: <https://github.com/opencv/opencv>.
- Репозиторий пакета Python: <https://github.com/opencv/opencv-python>.
- Пакет: <https://pypi.org/project/opencv-python-headless/4.14.0.94/>.
- Официальная документация: <https://docs.opencv.org/4.x/>.
- Лицензия OpenCV: Apache License 2.0;
  <https://github.com/opencv/opencv/blob/4.x/LICENSE>.
- Лицензия проекта упаковки Python `opencv-python`: MIT;
  <https://github.com/opencv/opencv-python/blob/4.x/LICENSE.txt>.
- Уведомления о сторонних компонентах wheel: поставка содержит соответствующий
  версии `LICENSE-3RD-PARTY.txt`; в частности, wheel включает FFmpeg под LGPLv2.1,
  а полный набор применимых уведомлений зависит от платформы:
  <https://github.com/opencv/opencv-python/blob/4.x/LICENSE-3RD-PARTY.txt>.

Минимальная проверка Increment 2 пройдена на Windows / Python 3.12 / uv:
`import cv2`, создание ORB, `detectAndCompute` и
`estimateAffinePartial2D(..., RANSAC)` выполнены успешно. Исправление зависимостей
не потребовалось.

### NumPy

- Назначение: фактический компонент работы с массивами и численных операций для
  `image_copy_move_correspondence`.
- Фактическая версия пакета и среды выполнения: `numpy==2.5.2`.
- Проект: <https://numpy.org/>.
- Репозиторий: <https://github.com/numpy/numpy>.
- Пакет: <https://pypi.org/project/numpy/2.5.2/>.
- Официальная документация: <https://numpy.org/doc/stable/>.
- License: основной код NumPy — BSD-3-Clause; поставка также содержит компоненты
  с лицензиями, перечисленными в versioned license file:
  <https://github.com/numpy/numpy/blob/v2.5.2/LICENSE.txt>.

Минимальная проверка Increment 2 пройдена без исправления зависимостей. Метаданные
wheel фиксируют составное лицензионное выражение для включённых компонентов;
соответствующий версии `LICENSE.txt` остаётся полным источником применимых
уведомлений.

### Audio numeric foundations M1-D — 2026-09-21

Собственные audio helpers в `_media_tools.py` и профиль preprocessing —
`FIRST_PARTY_CODE`, Apache-2.0 проекта. Новые внешние исходники не копировались.
Используются существующие NumPy 2.5.2 и внешние FFmpeg/ffprobe, указанные
выше; состав зависимостей и способ поставки не меняются. Дополнительно используется
NumPy rFFT, без SciPy/librosa/soundfile. Метод — обычные framing, periodic Hann и
DFT; forensic detector, PSD или статистическая калибровка не заявляются.

Первичные определения интерфейсов:
[NumPy rFFT](https://numpy.org/doc/stable/reference/generated/numpy.fft.rfft.html),
[FFmpeg ashowinfo](https://ffmpeg.org/ffmpeg-filters.html#ashowinfo),
[FFmpeg atrim](https://ffmpeg.org/ffmpeg-filters.html#atrim),
[FFmpeg seek/copyts](https://ffmpeg.org/ffmpeg.html).
Документация используется для семантики вызова, а не как источник копируемого
кода. Точная локальная числовая семантика закреплена только в `CONTRACTS.md` §7.5.
Тестовые данные создаются собственными deterministic PCM codes/тонами и локальным
FFmpeg; внешние recordings, datasets, models и weights не применяются.

### Dense video foundations M1-F — 2026-09-21

Dense producer, strict diagnostic parser и региональное A/V mapping — собственный
`FIRST_PARTY_CODE`, Apache-2.0 проекта. Используются прежние FFmpeg/ffprobe,
NumPy и стандартный `zlib.adler32`; внешние исходники не копировались,
зависимости и способ поставки не меняются. Fixtures создаются локально FFmpeg.
Семантика ограничений и диагностики сверяется с первичными интерфейсами:
[FFmpeg showinfo](https://ffmpeg.org/ffmpeg-filters.html#showinfo),
[FFmpeg trim](https://ffmpeg.org/ffmpeg-filters.html#trim),
[реализация EOF в trim](https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/trim.c).
Исходник используется только для проверки семантики остановки filtergraph.
Точные локальные contracts принадлежат `CONTRACTS.md` §7.5; forensic detector
или внешний метод оценки синхронизации не заимствуется и не заявляется.

## Происхождение политики оценки Stage 7

- Политика: `score_model_v1@0.1.0`, включая полноту, корреляцию, `score`,
  `critical_override` и правила рекомендаций.
- Источник метода: внутренняя проектная эвристика.
- Источник реализации: оригинальная реализация FakeDetector.
- Внешняя статистическая модель, калиброванная `probability`, веса модели и
  набор данных для валидации не применяются и не заявляются.
- Детерминированные модульные фикстуры проверяют только реализацию утверждённой
  внутренней политики и не являются статистическим набором данных для валидации.

## Analyzer references

### image_metadata_consistency

- `analyzer_id`: `image_metadata_consistency`.
- `analyzer_version`: `1.0.0`.
- Implementation status: implemented в Stage 6 Increment 1.
- Method: deterministic consistency checks доступных image metadata и
  подтверждённых технических параметров.
- Method source: project-specific heuristic.
- Implementation source: original FakeDetector implementation + Pillow; сведения
  о версии Pillow, source и license приведены в разделе «Общие библиотеки и
  инструменты».
- Фактический источник семантики формата: CIPA DC-008-Translation-2026
  «Exchangeable image file format for digital still cameras: Exif Version 3.1»,
  §4.6.5.1.6, Table 7, Figures 11–14 и §4.6.6.3.1–2.
- Официальный источник: https://www.cipa.jp/e/std/std-sec.html.
- Роль CIPA ограничена нормативной семантикой EXIF tags
  `PixelXDimension`, `PixelYDimension` и `Orientation`; стандарт не является
  источником forensic heuristic FakeDetector.
- Model/weights source: не применяется.
- Dataset/source: не применяется; используются deterministic generated fixtures.
- FakeDetector-specific adaptation: правила consistency, applicability,
  bounded metadata handling, candidate findings и их преобразование в `Finding`.
- Реализуется самим FakeDetector: вся логика consistency и threshold/policy
  interpretation.
- Фактические implementation building blocks: Pillow `Image.open()`, bounded
  boolean presence checks, безопасное числовое чтение EXIF dimension/orientation
  tags и bounded factual publication валидированного `Orientation` без raw
  metadata blobs или неограниченных строковых значений.
- Known limitations: отсутствие EXIF или иных естественно необязательных metadata
  само по себе не является finding; metadata могут быть удалены обычным export,
  пересылкой или повторным сохранением. Анализатор не заявляется научно
  валидированным forensic detector.

### audio_pcm_quality

- `analyzer_id`: `audio_pcm_quality`.
- `analyzer_version`: `1.0.0`.
- Implementation status: implemented в Stage 6 Increment 1.
- Method: peak, RMS, DC offset, silence и full-scale sample ratio как стандартные
  signal metrics, объединённые в bounded техническую эвристику.
- Method source: project-specific heuristic на основе стандартных signal metrics.
- Implementation source: original FakeDetector implementation.
- Implementation building block: Python standard library.
- Фактические implementation building blocks: `wave` и chunked `readframes()`,
  `array('h')`, `math` и явная little-endian интерпретация signed 16-bit PCM.
- Model/weights source: не применяется.
- Dataset/source: не применяется; используются deterministic generated fixtures.
- FakeDetector-specific adaptation: bounded PCM processing, applicability,
  candidate findings и их преобразование в `Finding`.
- Реализуется самим FakeDetector: расчёт метрик, interpretation и threshold
  policy.
- Versioned deterministic MVP default: `full_scale_sample_ratio` threshold =
  `0.001`.
- Known limitations: threshold не является статистически валидированным forensic
  threshold; метрики качества PCM не обнаруживают синтетическую речь и не
  доказывают искусственное происхождение аудио.

### video_sampled_frame_quality

- `analyzer_id`: `video_sampled_frame_quality`.
- `analyzer_version`: `1.0.0`.
- Implementation status: implemented в Stage 6 Increment 1.
- Method: bounded deterministic comparison подготовленных sampled frames.
- Method source: project-specific heuristic.
- Implementation source: original FakeDetector implementation.
- Implementation building block: Pillow; точное сравнение выполняется по
  декодированным mode, dimensions и pixel bytes двух соседних samples без
  сравнения compressed PNG byte stream.
- Model/weights source: не применяется.
- Dataset/source: не применяется; используются deterministic generated fixtures.
- FakeDetector-specific adaptation: sampling-scope interpretation, bounded frame
  comparison, applicability, candidate findings и их преобразование в `Finding`.
- Реализуется самим FakeDetector: вся comparison и finding policy.
- Known limitations: анализируется только ограниченная выборка подготовленных
  кадров; finding не является доказательством video forgery и не заменяет
  temporal или content detector.

### image_copy_move_correspondence

- `analyzer_id`: `image_copy_move_correspondence`.
- `analyzer_version`: `1.0.0`.
- Статус реализации: реализовано в Stage 6 Increment 2.
- Группа признаков: `content`.
- Метод: поиск пространственно разделённых соответствий локальных признаков с
  ограниченной фильтрацией и проверкой геометрической согласованности методом RANSAC.
- Источник метода: проектная эвристика, использующая ORB и RANSAC только как
  составные части метода.
- Источник реализации: собственная реализация FakeDetector поверх OpenCV и NumPy.
- Источник модели и весов: не применяется.
- Источник набора данных: не применяется; используются детерминированные
  генерируемые фикстуры.

Составные части метода:

1. **ORB.** Ethan Rublee, Vincent Rabaud, Kurt Konolige, Gary Bradski. “ORB: An
   efficient alternative to SIFT or SURF.” Proceedings of the IEEE International
   Conference on Computer Vision (ICCV), 2011. DOI:
   <https://doi.org/10.1109/ICCV.2011.6126544>.
2. **RANSAC.** Martin A. Fischler, Robert C. Bolles. “Random Sample Consensus: A
   Paradigm for Model Fitting with Applications to Image Analysis and Automated
   Cartography.” Communications of the ACM, 1981. DOI:
   <https://doi.org/10.1145/358669.358692>.

Компоненты реализации:

- OpenCV / `opencv-python-headless==4.14.0.94` — ORB-дескрипторы и геометрические
  операции с RANSAC;
- `numpy==2.5.2` — ограниченные численные операции и операции с массивами.

Собственная реализация и адаптация FakeDetector:

- ограниченная проверка PNG в RGB/RGBA и маска признаков с учётом альфа-канала;
- правила сопоставления признаков внутри изображения с исключением тривиального
  самосопоставления до проверки отношения расстояний;
- пространственное разделение;
- ограниченная фильтрация сопоставлений;
- итеративная геометрическая кластеризация;
- правила принятия кластера;
- приведение симметричных пар к каноническому виду и подавление дублирующих кластеров;
- парное IoU-подавление при перекрытии `>= 0.5` используется только как внутреннее
  правило устранения дублирующего вывода, а не как порог экспертного анализа;
- построение ограничивающих прямоугольников;
- правила порогов и пределов;
- преобразование кандидатов в `Finding`;
- правила `correlation_group`.

Версионированные детерминированные значения MVP по умолчанию:

| Параметр | Значение |
|---|---:|
| `min_dimension_px` | `128` |
| `max_pixels` | `12_000_000` |
| `max_keypoints` | `5_000` |
| `descriptor_ratio` | `0.75` |
| `min_spatial_separation_px` | `max(32, 0.05 * min_dimension)` |
| `ransac_reprojection_threshold_px` | `3` |
| `min_cluster_inliers` | `12` |
| `min_cluster_inlier_ratio` | `0.5` |
| `max_clusters` | `4` |

Эти значения не являются статистически валидированными порогами экспертного
анализа. Они являются воспроизводимыми значениями MVP по умолчанию и могут
изменяться в Stage 6 только после обоснования детерминированными положительными,
отрицательными и проверяющими ограничения фикстурами и фиксации изменения.

Известные ограничения: повторяющаяся архитектура, окна, плитка, узоры, логотипы,
симметричные объекты, интерфейсные элементы, текстуры и естественно повторяющиеся
детали могут создавать допустимые положительные наблюдения; сжатие и малые
изображения могут приводить к пропущенным соответствиям. Finding означает только
геометрически согласованное повторяющееся соответствие областей и не является
доказательством подделки переносом области, злонамеренного редактирования,
deepfake или изображения, созданного ИИ. Полный конвейер FakeDetector не заявляется
реализацией одной из перечисленных статей: ORB и RANSAC используются только как
составные части собственной ограниченной эвристики.
