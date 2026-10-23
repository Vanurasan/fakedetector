"""Private RU/EN presentation copy; persisted analytical prose is never translated."""

_COPY: dict[str, tuple[str, str]] = {
    "result.unnamed_file": ("Имя файла не сохранено", "Filename was not recorded"),
    "localization.scope": (
        "Локализация относится к техническому наблюдению, а не к доказанной области подделки.",
        "Localization describes a technical observation, not a proven manipulation region.",
    ),
    "app.subtitle": (
        ("Анализ мультимедиа"),
        ("Multimedia analysis"),
    ),
    "nav.skip": (
        ("К содержимому"),
        ("Skip to content"),
    ),
    "nav.new": (
        ("Новый анализ"),
        ("New analysis"),
    ),
    "nav.upload": (
        ("К загрузке"),
        ("Back to upload"),
    ),
    "nav.language": (
        ("Язык интерфейса"),
        ("Interface language"),
    ),
    "nav.other_file": (
        ("Проверить другой файл"),
        ("Analyze another file"),
    ),
    "upload.title": (
        ("Новый анализ"),
        ("New analysis"),
    ),
    "upload.file": (
        ("Файл"),
        ("File"),
    ),
    "upload.help": (
        ("Изображение, аудио или видео. Форматы и лимиты ниже."),
        ("Image, audio or video. Formats and limits are listed below."),
    ),
    "upload.submit": (
        ("Начать анализ"),
        ("Start analysis"),
    ),
    "upload.submitting": (
        ("Отправляем файл…"),
        ("Uploading file…"),
    ),
    "upload.formats": (
        ("Поддерживаемые форматы и лимиты"),
        ("Supported formats and limits"),
    ),
    "upload.up_to": (
        ("До {limit} МиБ"),
        ("Up to {limit} MiB"),
    ),
    "status.title": (
        ("Состояние анализа"),
        ("Analysis status"),
    ),
    "status.stage": (
        ("Текущий этап"),
        ("Current stage"),
    ),
    "status.refresh": (
        ("Обновить статус"),
        ("Refresh status"),
    ),
    "status.refresh_notice": (
        ("Страница обновляется каждые 2 секунды."),
        ("This page refreshes every 2 seconds."),
    ),
    "status.pause": (
        ("Остановить обновление"),
        ("Pause refresh"),
    ),
    "status.resume": (
        ("Возобновить обновление"),
        ("Resume refresh"),
    ),
    "status.paused": (
        ("Автообновление остановлено. Анализ продолжается."),
        ("Automatic refresh is paused. Analysis continues."),
    ),
    "result.title": (
        ("Результат анализа"),
        ("Analysis result"),
    ),
    "result.file": (
        ("Сведения о файле"),
        ("File information"),
    ),
    "result.id": (
        ("Идентификатор анализа"),
        ("Analysis identifier"),
    ),
    "result.media": (
        ("Тип медиа"),
        ("Media type"),
    ),
    "result.state": (
        ("Состояние обработки"),
        ("Processing state"),
    ),
    "result.created": (
        ("Создан"),
        ("Created"),
    ),
    "result.finished": (
        ("Завершён"),
        ("Finished"),
    ),
    "result.risk": (
        ("Технический риск"),
        ("Technical risk"),
    ),
    "result.score": (
        ("Эвристические баллы"),
        ("Heuristic score"),
    ),
    "result.signal": (
        ("Сводный эвристический сигнал"),
        ("Combined heuristic signal"),
    ),
    "result.execution": (
        ("Выполнение плана"),
        ("Plan execution"),
    ),
    "result.interpretation": (
        ("Как понимать результат"),
        ("Interpretation"),
    ),
    "result.findings": (
        ("Технические признаки"),
        ("Technical findings"),
    ),
    "result.analyzers": (
        ("Проверки и измерения"),
        ("Checks and measurements"),
    ),
    "result.recommendation": (
        ("Рекомендация"),
        ("Recommendation"),
    ),
    "result.details": (
        ("Технические сведения"),
        ("Technical details"),
    ),
    "result.measurements": (
        ("Измерения"),
        ("Measurements"),
    ),
    "result.messages": (
        ("Ошибки и предупреждения"),
        ("Errors and warnings"),
    ),
    "result.limitations": (
        ("Ограничения"),
        ("Limitations"),
    ),
    "result.source": (
        ("Источник признака"),
        ("Finding source"),
    ),
    "result.applicable": (
        ("Применимость"),
        ("Applicability"),
    ),
    "result.manual": (
        ("Требуется ручная проверка"),
        ("Manual review required"),
    ),
    "result.no_risk": (
        ("Оценка риска недоступна"),
        ("Risk assessment unavailable"),
    ),
    "result.no_recommendation": (
        ("Рекомендация не сформирована"),
        ("No recommendation was produced"),
    ),
    "result.no_analyzers": (
        ("Сохранённых результатов анализаторов нет."),
        ("No analyzer results were recorded."),
    ),
    "result.no_file": (
        ("Сведения о файле не сохранены."),
        ("File information was not recorded."),
    ),
    "result.no_metrics": (
        ("Структурированные измерения не сохранены."),
        ("Structured measurements were not recorded."),
    ),
    "result.no_findings": (
        (
            "В сохранённом результате нет нормализованных признаков. Это не подтверждает "
            "подлинность."
        ),
        ("No normalized findings were recorded. This does not establish authenticity."),
    ),
    "result.analyzer_errors": (
        ("Есть ошибки отдельных проверок."),
        ("Some checks reported errors."),
    ),
    "error.title": (
        ("Не удалось выполнить запрос"),
        ("The request could not be completed"),
    ),
    "error.next_action": (
        ("Следующее действие"),
        ("Next action"),
    ),
    "error.code": (
        ("Код ошибки"),
        ("Error code"),
    ),
    "error.status_link": (
        ("Открыть статус"),
        ("Open status"),
    ),
    "error.result_link": (
        ("Открыть сохранённый результат"),
        ("Open saved result"),
    ),
    "error.post_language_en": (
        ("К загрузке на английском"),
        ("Open upload in English"),
    ),
    "error.post_language_ru": (
        ("К загрузке на русском"),
        ("Open upload in Russian"),
    ),
    "common.yes": (
        ("Да"),
        ("Yes"),
    ),
    "common.no": (
        ("Нет"),
        ("No"),
    ),
    "common.unknown": (
        ("Не указано"),
        ("Not recorded"),
    ),
    "common.label_unavailable": (
        ("Подпись недоступна"),
        ("Label unavailable"),
    ),
    "common.metadata_unavailable": (
        ("Метаданные версии недоступны"),
        ("Version metadata unavailable"),
    ),
    "notice.expert": (
        (
            "Это автоматизированная оценка технических признаков. Она не заменяет окончательную"
            " экспертную экспертизу."
        ),
        (
            "This is an automated assessment of technical indicators. It does not replace an "
            "expert examination."
        ),
    ),
    "notice.execution_scope": (
        (
            "Полнота описывает выполнение применимых анализаторов настроенного плана. "
            "Выполненный план не означает проверку всех способов манипуляции и не гарантирует "
            "достаточность криминалистических свидетельств."
        ),
        (
            "Completeness describes execution of the configured applicable analyzer plan. A "
            "completed plan does not cover every form of manipulation or guarantee sufficient "
            "forensic evidence."
        ),
    ),
    "notice.low_not_authentic": (
        (
            "Низкий технический риск или score=0 не подтверждают подлинность или безопасность "
            "файла. Отсутствующие, недостаточные или недоступные свидетельства не означают "
            "отрицательный результат проверки на манипуляцию."
        ),
        (
            "Low technical risk or score=0 does not establish authenticity or safety. Missing, "
            "insufficient or unavailable evidence is not a negative manipulation test."
        ),
    ),
    "notice.heuristic": (
        ("Эвристическая оценка, не вероятность подделки."),
        ("A heuristic assessment, not a probability of manipulation."),
    ),
    "notice.original": (
        (
            "Сохранённые пояснения и сообщения анализаторов показаны на исходном языке; часть "
            "текста может быть на английском. Подписи интерфейса переведены."
        ),
        (
            "Saved explanations and analyzer messages are shown in their original language and "
            "may be in Russian. Interface labels are translated."
        ),
    ),
    "notice.non_scoring": (
        ("Не участвует в расчёте риска"),
        ("Excluded from risk scoring"),
    ),
    "measurement.insufficient": (
        ("Измерение: недостаточно свидетельств"),
        ("Measurement: insufficient evidence"),
    ),
    "measurement.digital_silence": (
        ("Выбранный префикс цифрово беззвучен"),
        ("Selected prefix is digitally silent"),
    ),
    "measurement.too_short": (
        ("Выбранный префикс слишком короткий"),
        ("Selected prefix is too short"),
    ),
    "localization.file": (
        ("Файл целиком"),
        ("Whole file"),
    ),
    "localization.box": (
        ("Нормализованная область: x={x}, y={y}, ширина={width}, высота={height}"),
        ("Normalized region: x={x}, y={y}, width={width}, height={height}"),
    ),
    "localization.time": (
        ("Интервал: {start}–{end} с"),
        ("Interval: {start}–{end} s"),
    ),
    "localization.frames": (
        ("Кадры: {start}–{end}"),
        ("Frames: {start}–{end}"),
    ),
    "analysis_status.queued": (
        ("В очереди"),
        ("Queued"),
    ),
    "analysis_status.running": (
        ("Анализ выполняется"),
        ("Analysis running"),
    ),
    "analysis_status.completed": (
        ("Анализ завершён"),
        ("Analysis completed"),
    ),
    "analysis_status.partial": (
        ("Анализ выполнен частично"),
        ("Analysis partially completed"),
    ),
    "analysis_status.rejected": (
        ("Файл отклонён"),
        ("File rejected"),
    ),
    "analysis_status.failed": (
        ("Анализ завершился ошибкой"),
        ("Analysis failed"),
    ),
    "stage.registered": (
        ("Задача зарегистрирована"),
        ("Task registered"),
    ),
    "stage.validation": (
        ("Проверка файла"),
        ("Validating file"),
    ),
    "stage.routing": (
        ("Выбор плана обработки"),
        ("Selecting processing plan"),
    ),
    "stage.queued": (
        ("Ожидание запуска"),
        ("Waiting to start"),
    ),
    "stage.preprocessing": (
        ("Подготовка данных"),
        ("Preparing media"),
    ),
    "stage.analysis": (
        ("Выполнение проверок"),
        ("Running checks"),
    ),
    "stage.finding_formation": (
        ("Формирование признаков"),
        ("Forming findings"),
    ),
    "stage.risk_assessment": (
        ("Расчёт технического риска"),
        ("Calculating technical risk"),
    ),
    "stage.result_formation": (
        ("Формирование результата"),
        ("Preparing result"),
    ),
    "stage.cleanup": (
        ("Очистка временных данных"),
        ("Cleaning up temporary data"),
    ),
    "stage.persistence": (
        ("Сохранение результата"),
        ("Saving result"),
    ),
    "stage.finished": (
        ("Обработка завершена"),
        ("Processing finished"),
    ),
    "risk.low": (
        ("Низкий технический риск"),
        ("Low technical risk"),
    ),
    "risk.medium": (
        ("Средний технический риск"),
        ("Medium technical risk"),
    ),
    "risk.high": (
        ("Высокий технический риск"),
        ("High technical risk"),
    ),
    "severity.weak": (
        ("Слабый признак"),
        ("Weak finding"),
    ),
    "severity.significant": (
        ("Значимый признак"),
        ("Significant finding"),
    ),
    "severity.critical": (
        ("Критический признак"),
        ("Critical finding"),
    ),
    "analyzer_status.completed": (
        ("Проверка выполнена"),
        ("Check completed"),
    ),
    "analyzer_status.skipped": (
        ("Проверка пропущена"),
        ("Check skipped"),
    ),
    "analyzer_status.not_applicable": (
        ("Неприменимо к этому файлу"),
        ("Not applicable to this file"),
    ),
    "analyzer_status.error": (
        ("Ошибка проверки"),
        ("Check error"),
    ),
    "analyzer_status.timeout": (
        ("Время проверки истекло"),
        ("Check timed out"),
    ),
    "completeness.complete": (
        ("Применимый план выполнен"),
        ("Applicable plan completed"),
    ),
    "completeness.partial": (
        ("Применимый план выполнен частично"),
        ("Applicable plan partially completed"),
    ),
    "completeness.insufficient": (
        ("Недостаточное покрытие плана"),
        ("Insufficient plan coverage"),
    ),
    "completeness.not_assessed": (
        ("Выполнение плана не оценивалось"),
        ("Plan execution not assessed"),
    ),
    "cleanup.not_started": (
        ("Очистка не начата"),
        ("Cleanup not started"),
    ),
    "cleanup.completed": (
        ("Очистка завершена"),
        ("Cleanup completed"),
    ),
    "cleanup.partial": (
        ("Очистка выполнена частично"),
        ("Cleanup partially completed"),
    ),
    "cleanup.failed": (
        ("Ошибка очистки"),
        ("Cleanup failed"),
    ),
    "media.image": (
        ("Изображение"),
        ("Image"),
    ),
    "media.audio": (
        ("Аудио"),
        ("Audio"),
    ),
    "media.video": (
        ("Видео"),
        ("Video"),
    ),
    "action.no_additional_action": (
        ("Нет дополнительных действий по выполненным проверкам"),
        ("No additional action for the checks performed"),
    ),
    "action.manual_review": (
        ("Ручная проверка"),
        ("Manual review"),
    ),
    "action.verify_source": (
        ("Проверить источник"),
        ("Verify the source"),
    ),
    "action.verify_source_via_independent_channel": (
        ("Подтвердить источник по независимому каналу"),
        ("Verify the source through an independent channel"),
    ),
    "action.request_better_quality_source": (
        ("Запросить исходник лучшего качества"),
        ("Request a better-quality source"),
    ),
    "action.retry_analysis": (
        ("Повторить анализ"),
        ("Repeat the analysis"),
    ),
    "action.escalate_to_security": (
        ("Передать специалистам ИБ"),
        ("Escalate to security"),
    ),
    "action.send_to_incident_response": (
        ("Передать группе реагирования"),
        ("Send to incident response"),
    ),
    "error.authentication_required": (
        ("Требуется вход через HTTP Basic."),
        ("HTTP Basic sign-in is required."),
    ),
    "error.authentication_failed": (
        ("Данные доступа не приняты."),
        ("Sign-in details were not accepted."),
    ),
    "error.same_origin_required": (
        ("Запрос загрузки не прошёл проверку источника."),
        ("The upload request failed the origin check."),
    ),
    "error.invalid_multipart": (
        ("Не удалось безопасно прочитать форму загрузки."),
        ("The upload form could not be read safely."),
    ),
    "error.file_missing": (
        ("Файл не выбран."),
        ("No file was selected."),
    ),
    "error.file_empty": (
        ("Выбран пустой файл."),
        ("The selected file is empty."),
    ),
    "error.file_too_large": (
        ("Размер файла или запроса превышает допустимый предел."),
        ("The file or request exceeds the allowed size."),
    ),
    "error.missing_extension": (
        ("В имени файла отсутствует расширение."),
        ("The filename has no extension."),
    ),
    "error.unsupported_extension": (
        ("Расширение файла не поддерживается."),
        ("This file extension is not supported."),
    ),
    "error.unsupported_mime_type": (
        ("Тип содержимого файла не поддерживается."),
        ("This content type is not supported."),
    ),
    "error.unsupported_media_type": (
        ("Этот тип медиа не поддерживается."),
        ("This media type is not supported."),
    ),
    "error.file_signature_mismatch": (
        ("Фактический тип файла не соответствует заявленному."),
        ("The detected file type does not match the declared type."),
    ),
    "error.unsafe_or_unreadable_file": (
        ("Файл не удалось безопасно прочитать."),
        ("The file could not be read safely."),
    ),
    "error.stage5_resource_limit": (
        ("Подготовка данных превысила ресурсный предел."),
        ("Media preparation exceeded a resource limit."),
    ),
    "error.processing_timeout": (
        ("Время обработки истекло."),
        ("Processing timed out."),
    ),
    "error.analyzer_error": (
        ("Одна из проверок завершилась ошибкой."),
        ("A check reported an error."),
    ),
    "error.analyzer_timeout": (
        ("Время одной из проверок истекло."),
        ("A check timed out."),
    ),
    "error.result_not_found": (
        ("Анализ не найден."),
        ("Analysis not found."),
    ),
    "error.result_write_failed": (
        ("Результат недоступен из-за ошибки сохранения."),
        ("The result is unavailable because it could not be saved."),
    ),
    "error.cleanup_failed": (
        ("Не удалось полностью очистить временные данные."),
        ("Temporary data could not be fully cleaned up."),
    ),
    "error.invalid_configuration": (
        ("Конфигурация не прошла проверку."),
        ("Configuration validation failed."),
    ),
    "error.internal_error": (
        ("Не удалось выполнить запрос."),
        ("The request could not be completed."),
    ),
    "analyzer.image_metadata_consistency.name": (
        ("Согласованность метаданных изображения"),
        ("Image metadata consistency"),
    ),
    "analyzer.audio_pcm_quality.name": (
        ("Качество аудио PCM"),
        ("Audio PCM quality"),
    ),
    "analyzer.video_sampled_frame_quality.name": (
        ("Качество выборочных кадров видео"),
        ("Sampled video frame quality"),
    ),
    "analyzer.image_copy_move_correspondence.name": (
        ("Соответствие повторяющихся областей изображения"),
        ("Repeated image region correspondence"),
    ),
    "analyzer.image_jpeg_double_quantization.name": (
        ("Двойное квантование JPEG"),
        ("JPEG double quantization"),
    ),
    "analyzer.audio_aasist_l_measurement.name": (
        ("Измерение AASIST-L"),
        ("AASIST-L measurement"),
    ),
    "analyzer.audio_repeated_segment_correspondence.name": (
        ("Соответствие повторяющихся аудиофрагментов"),
        ("Repeated audio segment correspondence"),
    ),
    "analyzer.video_repeated_content_correspondence.name": (
        ("Соответствие повторяющегося содержимого видео"),
        ("Repeated video content correspondence"),
    ),
    "analyzer.video_visual_discontinuity.name": (
        ("Визуальные переходы видео"),
        ("Video visual transitions"),
    ),
    "analyzer.video_timing_anomaly.name": (
        ("Нарушения временных меток видео"),
        ("Video timestamp irregularities"),
    ),
    "analyzer.image_noise_residual_consistency.name": (
        ("Согласованность остаточного сигнала изображения"),
        ("Image residual consistency"),
    ),
    "analyzer.image_resampling_consistency.name": (
        ("Согласованность признаков ресэмплинга изображения"),
        ("Image resampling consistency"),
    ),
    "analyzer.audio_temporal_discontinuity.name": (
        ("Временные разрывы аудио"),
        ("Audio temporal discontinuities"),
    ),
    "analyzer.audio_spectral_consistency.name": (
        ("Спектральная согласованность аудио"),
        ("Audio spectral consistency"),
    ),
    "analyzer.audio_background_noise_consistency.name": (
        ("Спектральная согласованность низкоэнергетического аудио"),
        ("Low-energy audio spectral consistency"),
    ),
    "upload.intro": (
        (
            "Автоматизированная оценка технических признаков искусственного создания или "
            "модификации."
        ),
        ("Automated assessment of technical indicators of artificial creation or modification."),
    ),
    "result.caution": (
        ("Как понимать полноту и риск"),
        ("Understanding completeness and risk"),
    ),
    "result.scale": (
        ("Шкала политики 0–100; не вероятность. Типы медиа эмпирически не сопоставлены."),
        ("Policy scale 0–100; not probability. Media types are not empirically comparable."),
    ),
    "result.no_assessment": (
        ("Сохранённая оценка риска отсутствует."),
        ("No risk assessment was recorded."),
    ),
    "result.warnings_present": (
        ("В результате есть сообщения об ограничениях или ошибках."),
        ("The result contains messages about limitations or errors."),
    ),
    "result.no_messages": (
        ("Ошибок и предупреждений в сохранённом результате нет."),
        ("No errors or warnings were recorded in the result."),
    ),
    "result.top_messages": (
        ("Общие сообщения"),
        ("General messages"),
    ),
    "result.cleanup": (
        ("Очистка временных данных"),
        ("Temporary data cleanup"),
    ),
    "result.cleanup_partial": (
        ("Очистка временных данных выполнена частично."),
        ("Temporary data cleanup was partial."),
    ),
    "result.cleanup_failed": (
        ("Не удалось очистить временные данные."),
        ("Temporary data cleanup failed."),
    ),
    "result.finding_details": (
        ("Сведения о признаке"),
        ("Finding details"),
    ),
    "result.model": (
        ("Модель оценки"),
        ("Assessment model"),
    ),
    "result.application": (
        ("Версия приложения"),
        ("Application version"),
    ),
    "result.config": (
        ("Идентификатор конфигурации"),
        ("Configuration identifier"),
    ),
    "result.explanation": (
        ("Объяснение оценки"),
        ("Assessment explanation"),
    ),
    "result.execution_explanation": (
        ("Объяснение выполнения плана"),
        ("Plan execution explanation"),
    ),
    "result.coverage": (
        ("Покрытие выполнения плана (не уверенность обнаружения)"),
        ("Plan execution coverage (not detection confidence)"),
    ),
    "result.missing": (
        ("Недоступные возможности текущего плана"),
        ("Unavailable capabilities in the current plan"),
    ),
    "result.started": (
        ("Начат"),
        ("Started"),
    ),
    "result.original_deleted": (
        ("Исходный файл удалён"),
        ("Original file deleted"),
    ),
    "result.intermediate_deleted": (
        ("Промежуточные файлы удалены"),
        ("Intermediate files deleted"),
    ),
    "result.quarantine": (
        ("Использован карантин"),
        ("Quarantine used"),
    ),
    "result.parameters": (
        ("Технические параметры медиа"),
        ("Media technical parameters"),
    ),
    "result.size": (
        ("Размер файла"),
        ("File size"),
    ),
    "result.duration": (
        ("Длительность обработки"),
        ("Processing duration"),
    ),
    "result.width": (
        ("Ширина"),
        ("Width"),
    ),
    "result.height": (
        ("Высота"),
        ("Height"),
    ),
    "result.media_duration": (
        ("Продолжительность медиа"),
        ("Media duration"),
    ),
    "result.sample_rate": (
        ("Частота дискретизации"),
        ("Sample rate"),
    ),
    "result.channels": (
        ("Количество каналов"),
        ("Channel count"),
    ),
    "result.bitrate": (
        ("Битрейт"),
        ("Bitrate"),
    ),
    "result.score_level": (
        ("Уровень до critical override"),
        ("Level before critical override"),
    ),
    "result.override": (
        ("Применён critical override"),
        ("Critical override applied"),
    ),
    "result.critical_ids": (
        ("Основания critical override"),
        ("Critical override findings"),
    ),
    "maturity.CORE": (
        ("Базовая проверка"),
        ("Core check"),
    ),
    "maturity.EXPERIMENTAL": (
        ("Экспериментальное измерение"),
        ("Experimental measurement"),
    ),
    "maturity.EXPERIMENTAL_WEAK": (
        ("Экспериментальное измерение · слабый сигнал"),
        ("Experimental measurement · weak signal"),
    ),
    "format.bytes": (
        ("байт"),
        ("bytes"),
    ),
    "format.mib": (
        ("МиБ"),
        ("MiB"),
    ),
    "format.seconds": (
        ("с"),
        ("s"),
    ),
    "counter.planned_analyzers": (
        ("Запланировано"),
        ("Planned"),
    ),
    "counter.applicable_analyzers": (
        ("Применимо"),
        ("Applicable"),
    ),
    "counter.completed_analyzers": (
        ("Завершено"),
        ("Completed"),
    ),
    "counter.failed_analyzers": (
        ("С ошибкой"),
        ("Failed"),
    ),
    "counter.timed_out_analyzers": (
        ("С истекшим временем"),
        ("Timed out"),
    ),
    "counter.skipped_analyzers": (
        ("Пропущено"),
        ("Skipped"),
    ),
    "counter.not_applicable_analyzers": (
        ("Неприменимо"),
        ("Not applicable"),
    ),
    "activity.registered": (
        ("Задача принята; дождитесь следующего состояния."),
        ("The task was received; wait for the next state."),
    ),
    "activity.validation": (
        ("Задача принята; дождитесь следующего состояния."),
        ("The task was received; wait for the next state."),
    ),
    "activity.routing": (
        ("Задача принята; дождитесь следующего состояния."),
        ("The task was received; wait for the next state."),
    ),
    "activity.queued": (
        ("Задача принята; дождитесь следующего состояния."),
        ("The task was received; wait for the next state."),
    ),
    "activity.preprocessing": (
        ("Система готовит данные для настроенных проверок."),
        ("Preparing data for the configured checks."),
    ),
    "activity.analysis": (
        ("Выполняются применимые проверки."),
        ("Applicable checks are running."),
    ),
    "activity.finding_formation": (
        ("Формируются признаки и сводная техническая оценка."),
        ("Preparing findings and the combined technical assessment."),
    ),
    "activity.risk_assessment": (
        ("Формируются признаки и сводная техническая оценка."),
        ("Preparing findings and the combined technical assessment."),
    ),
    "activity.result_formation": (
        ("Обработка завершается; результат будет доступен после сохранения."),
        ("Processing is finishing; the result becomes available after it is saved."),
    ),
    "activity.cleanup": (
        ("Обработка завершается; результат будет доступен после сохранения."),
        ("Processing is finishing; the result becomes available after it is saved."),
    ),
    "activity.persistence": (
        ("Обработка завершается; результат будет доступен после сохранения."),
        ("Processing is finishing; the result becomes available after it is saved."),
    ),
    "activity.finished": (
        ("Обработка завершена; проверяем доступность результата."),
        ("Processing finished; checking result availability."),
    ),
    "error_action.authentication_required": (
        ("Войти средствами браузера"),
        ("Sign in using your browser"),
    ),
    "error_action.authentication_failed": (
        ("Проверить данные и повторить вход"),
        ("Check your details and sign in again"),
    ),
    "error_action.same_origin_required": (
        ("Открыть загрузку в FakeDetector"),
        ("Open upload in FakeDetector"),
    ),
    "error_action.invalid_multipart": (
        ("Выбрать файл заново"),
        ("Select the file again"),
    ),
    "error_action.file_missing": (
        ("Выбрать файл"),
        ("Select a file"),
    ),
    "error_action.file_empty": (
        ("Выбрать непустой файл"),
        ("Select a non-empty file"),
    ),
    "error_action.file_too_large": (
        ("Сверить лимиты на странице загрузки"),
        ("Check the upload limits"),
    ),
    "error_action.missing_extension": (
        ("Проверить формат исходного файла"),
        ("Check the original file format"),
    ),
    "error_action.unsupported_extension": (
        ("Выбрать поддерживаемый файл"),
        ("Select a supported file"),
    ),
    "error_action.unsupported_mime_type": (
        ("Сверить поддерживаемые форматы"),
        ("Check supported formats"),
    ),
    "error_action.unsupported_media_type": (
        ("Сверить поддерживаемые форматы"),
        ("Check supported formats"),
    ),
    "error_action.file_signature_mismatch": (
        ("Проверить исходный файл"),
        ("Check the original file"),
    ),
    "error_action.unsafe_or_unreadable_file": (
        ("Проверить исходный файл"),
        ("Check the original file"),
    ),
    "error_action.stage5_resource_limit": (
        ("Выбрать меньший файл; подробности передать оператору"),
        ("Choose a smaller file; share the details with the operator"),
    ),
    "error_action.processing_timeout": (
        ("Открыть сохранённый результат, если доступен"),
        ("Open the saved result if available"),
    ),
    "error_action.analyzer_error": (
        ("Изучить ограничения результата"),
        ("Review the result limitations"),
    ),
    "error_action.analyzer_timeout": (
        ("Изучить ограничения результата"),
        ("Review the result limitations"),
    ),
    "error_action.result_not_found": (
        ("Проверить ссылку или начать новый анализ"),
        ("Check the link or start a new analysis"),
    ),
    "error_action.result_write_failed": (
        ("Передать код оператору; новый анализ отправляет файл заново"),
        ("Share the code with the operator; a new analysis uploads the file again"),
    ),
    "error_action.cleanup_failed": (
        ("Передать код оператору"),
        ("Share the code with the operator"),
    ),
    "error_action.invalid_configuration": (
        ("Обратиться к оператору"),
        ("Contact the operator"),
    ),
    "error_action.internal_error": (
        ("Вернуться к загрузке или передать код оператору"),
        ("Return to upload or share the code with the operator"),
    ),
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    locale: {key: values[index] for key, values in _COPY.items()}
    for index, locale in enumerate(("ru", "en"))
}


def translate(locale: str, key: str, **values: object) -> str:
    """Use a stable key, with RU and then a neutral fallback; return plain text."""
    selected = TRANSLATIONS.get(locale, TRANSLATIONS["ru"])
    template = selected.get(key, TRANSLATIONS["ru"].get(key))
    if template is None:
        template = selected["common.label_unavailable"]
    return template.format(**values)


def error_copy(locale: str, code: str, *, action: bool = False) -> str:
    """Unknown diagnostic codes keep a generic safe heading and next action."""
    prefix = "error_action." if action else "error."
    key = prefix + code
    if key not in TRANSLATIONS["ru"]:
        key = prefix + "internal_error"
    return translate(locale, key)
