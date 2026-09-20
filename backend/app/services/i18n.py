# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Локализация бэкенда (язык хранится в settings_store по ключу "lang")."""
from app.services import settings_store

_LANG: str | None = None


def get_lang() -> str:
    global _LANG
    if _LANG is None:
        try:
            value = settings_store.get("lang")
        except (KeyError, FileNotFoundError):
            value = "ru"
        _LANG = value if value in ("ru", "en") else "ru"
    return _LANG


def set_lang(lang: str) -> None:
    global _LANG
    _LANG = lang if lang in ("ru", "en") else "ru"


RU = {
    # --- shared ---
    "error.prefix": "[Ошибка]",
    # --- HTTPException details ---
    "profile.not_found": "Профиль не найден",
    "profile.no_profiles": "Нет ни одного профиля",
    "profile.single_only": "Приложение работает с одним профилем здоровья. Данные можно редактировать.",
    "profile.single_no_delete": "Приложение работает с одним профилем здоровья. Удаление недоступно.",
    "profile.name_required": "Имя профиля не может быть пустым.",
    "record.not_found": "Запись не найдена",
    "record.image_not_found": "Оригинал фото не найден",
    "reminder.marker_required": "Укажите название показателя.",
    "reminder.not_found": "Напоминание не найдено",
    "note.empty": "Заметка не может быть пустой.",
    "note.not_found": "Заметка не найдена",
    "article.not_found": "Статья не найдена",
    "article.unsupported": "Неподдерживаемый формат. Принимаются: {exts}",
    "article.empty_file": "Пустой файл.",
    "article.too_large": "Файл слишком большой (макс. 25 МБ).",
    "article.too_short": "Слишком короткий текст — не похоже на научную статью.",
    "search.empty": "Пустой поисковый запрос.",
    "analysis.card_empty": "Медицинская карта пуста. Сначала загрузите анализы (фото/документ) в чате.",
    "analysis.no_markers": "В карте нет показателей для анализа.",
    "analysis.no_articles_note": "Примечание: в базе научных статей не нашлось материалов по вашим показателям.\n\n",
    "analysis.articles_not_found": "Подходящие научные статьи не найдены — отчёт будет по самим показателям.",
    "analysis.article_ref": "[Статья «{title}»] {chunk}",
    "longterm.no_data": "Нет числовых показателей за выбранный период.",
    "longterm.empty_period": "Нет анализов за выбранный период.",
    "longterm.flag.insufficient": "мало данных",
    "longterm.flag.stable_normal": "стабильно в норме",
    "longterm.flag.persistent_high": "стойко выше нормы",
    "longterm.flag.persistent_low": "стойко ниже нормы",
    "longterm.flag.fluctuation": "колебания",
    "longterm.flag.improving": "улучшение",
    "longterm.flag.worsening": "ухудшение",
    "longterm.flag.trend_up": "рост",
    "longterm.flag.trend_down": "снижение",
    "longterm.status.normal": "норма",
    "longterm.status.high": "выше нормы",
    "longterm.status.low": "ниже нормы",
    "longterm.status.mixed": "смешанно",
    "longterm.status.unknown": "нет данных",
    "longterm.prompt.span": "Период: {span}",
    "longterm.prompt.records": "Анализов по годам: {counts}",
    "longterm.prompt.year_count": "{year}: {n}",
    "longterm.prompt.marker": "Показатель: {name} ({unit}), норма {ref}, флаг: {flag}, измерений: {n}",
    "longterm.prompt.year_value": "{year}: медиана {median} (n={n}, {status})",
    "longterm.disclaimer": "Не является медицинской консультацией.",
    "documents.unsupported": "Неподдерживаемый формат. Принимаются: {exts}",
    "documents.empty_file": "Пустой файл.",
    "documents.too_large": "Файл слишком большой (макс. 50 МБ).",
    "documents.extract_failed": "Не удалось извлечь текст из файла.",
    "extract.no_json": "Ответ модели не содержит JSON.",
    "extract.bad_json": "Не удалось распарсить JSON из ответа модели.",
    "document.pdf_open_failed": "Не удалось открыть PDF: {err}",
    "document.pdf_no_text": "В PDF не найдено текстового слоя. Возможно, это сканированный документ — отправьте его как фото.",
    "document.docx_open_failed": "Не удалось открыть DOCX: {err}",
    "document.docx_no_text": "В DOCX не найдено текста.",
    "embeddings.empty": "Ollama не вернул эмбеддинги.",
    "embeddings.api_error": "Ошибка embeddings API: {err}",
    # --- AI tools (tool descriptions and results) ---
    "tool.search_articles.desc": "Смысловой поиск в базе научных статей пользователя. Возвращает релевантные фрагменты статей с их названиями. Используй, когда пользователь спрашивает о научных данных, исследованиях или хочет найти информацию в своих статьях.",
    "tool.search_articles.query": "Поисковый запрос на русском языке.",
    "tool.search_articles.limit": "Максимум результатов (по умолчанию 5).",
    "tool.search_wikipedia.desc": "Полнотекстовый поиск в офлайн-Википедии (Kiwix, английский язык). Возвращает сниппеты и тексты статей; найденные изображения статей автоматически показываются пользователю в чате. Используй, когда пользователь спрашивает об общих медицинских терминах, лекарствах, заболеваниях, либо просит сравнить или проверить информацию из Википедии.",
    "tool.search_wikipedia.query": "Поисковый запрос (на английском языке — Википедия англоязычная).",
    "tool.search_wikipedia.limit": "Сколько статей извлечь полностью (по умолчанию 3).",
    "tool.list_kiwix_books.desc": "Возвращает список книг, подключённых к Kiwix (офлайн-контент: Википедия и другие). Используй, когда пользователь спрашивает, какие книги или какие Википедии доступны/подключены.",
    "kiwix.no_books": "В Kiwix не подключено ни одной книги.",
    "kiwix.empty_query": "Пустой поисковый запрос.",
    "kiwix.not_configured": "Не задан адрес Kiwix. Укажите его в настройках (раздел «Офлайн-Википедия»).",
    "kiwix.zim_not_found": "Не найдена книга Википедии. Укажите имя ZIM-книги в настройках.",
    "kiwix.books_failed": "Не удалось получить список книг Kiwix.",
    "kiwix.article_failed": "Не удалось получить текст статьи.",
    "kiwix.unreachable": "Kiwix недоступен по адресу {url}: {err}",
    "kiwix.no_results": "В офлайн-Википедии ничего не найдено по запросу.",
    "tool.list_articles.desc": "Возвращает список названий научных статей, загруженных в базу пользователя.",
    "tool.get_medical_card.desc": "Возвращает актуальные показатели из медицинской карты текущего профиля пользователя (последнее значение каждого маркера анализов). Используй, когда пользователь спрашивает о своих анализах или здоровье. Опционально можно ограничить период (days) — например, 30 для «за последний месяц».",
    "tool.get_medical_card.days": "Сколько последних дней учитывать (по умолчанию — вся история).",
    "tool.get_profile.desc": "Возвращает анкетные данные текущего профиля пользователя: имя, год рождения и возраст, группа крови, рост, вес. Используй, когда пользователь спрашивает о своём возрасте, годе рождения, группе крови, росте или весе.",
    "tool.get_profile.empty": "Профиль пользователя не заполнен: нет имени, года рождения, группы крови, роста и веса.",
    "tool.profile.title": "Данные профиля пользователя:",
    "tool.profile.context": "Анкетные данные пользователя (из его профиля): {summary}. Используй их при ответах о возрасте, годе рождения, группе крови, росте и весе; не выдумывай отсутствующие данные.",
    "tool.profile.name": "имя: {value}",
    "tool.profile.birth_year": "год рождения: {value}",
    "tool.profile.age": " (возраст: {value})",
    "tool.profile.blood": "группа крови: {value}",
    "tool.profile.height": "рост: {value} см",
    "tool.profile.weight": "вес: {value} кг",
    "tool.get_marker_trends.desc": "Возвращает динамику показателей анализов текущего профиля: значения по датам, количество измерений и направление тренда (up/down/stable). Используй, когда пользователь спрашивает, как менялись его показатели со временем.",
    "tool.get_marker_trends.marker": "Название показателя. Если не указано — все показатели.",
    "tool.get_marker_trends.days": "Сколько последних дней учитывать (по умолчанию — вся история).",
    "tool.check_marker_norm.desc": "Проверяет значение лабораторного показателя по справочнику референсных норм (учитывает пол и возраст). Сначала получи актуальное значение показателя через get_medical_card или get_marker_trends, затем передай его сюда вместе с единицами измерения. Используй, когда пользователь спрашивает, в норме ли его показатель или насколько он отклоняется. Если показатель отсутствует в справочнике, результат может содержать справку из Википедии — используй её для пояснения.",
    "tool.check_marker_norm.marker": "Название показателя (например: гемоглобин, глюкоза, креатинин).",
    "tool.check_marker_norm.value": "Значение показателя (число).",
    "tool.check_marker_norm.unit": "Единицы измерения (например: г/л, ммоль/л). Если неизвестны — можно пропустить.",
    "tool.check_marker_norm.sex": "Пол (муж/жен, m/f). Если известен.",
    "tool.check_marker_norm.age": "Возраст в годах. Если известен.",
    "tool.check_marker_norm.empty": "Пустое название показателя.",
    "tool.wiki_header": "Справка из офлайн-Википедии (для показателей, отсутствующих в справочнике норм):",
    "tool.wiki_item": "- {marker} → {title}: {snippet}",
    "norm.not_found": "В справочнике норм нет показателя «{marker}». Ориентируйся на референс лаборатории из карты.",
    "norm.not_numeric": "Не удалось распознать значение «{value}» как число.",
    "norm.single": "Норма{note}: {range}. Статус: {status}",
    "norm.item": "- {note}: {range}",
    "norm.multi_status": "Однозначный вывод затруднён: статус {status}. Уточни пол и возраст пользователя.",
    "norm.status.normal": "в норме",
    "norm.status.high": "выше нормы",
    "norm.status.low": "ниже нормы",
    "norm.status.unknown": "не оценивается",
    "norm.status.ambiguous": "неоднозначно",
    "tool.unknown": "Неизвестный инструмент: {name}",
    "tool.save_analysis_to_card.desc": "Сохраняет показатели анализов, о которых шла речь в разговоре, в медицинскую карту пользователя одной новой записью. Вызывай ТОЛЬКО когда пользователь явно попросил сохранить обсуждённые показатели в карту (например: «сохрани в карту», «добавь эти показатели в мою карту»). Передай каждый показатель с названием и значением, единицами и диапазоном, если они упоминались.",
    "tool.save_analysis_to_card.markers": "Массив показателей. Каждый элемент: name (название, обязательно), value (значение), unit (единицы), reference_range (референсный диапазон).",
    "tool.save_analysis_to_card.date": "Дата анализа в формате ГГГГ-ММ-ДД, если она была указана в разговоре; иначе пропусти.",
    "tool.save_analysis_to_card.ok": "Сохранено в медицинскую карту: {names}. Добавлена новая запись анализов.",
    "tool.save_analysis_to_card.empty": "Показатели не переданы. Уточни у пользователя значения и повтори вызов.",
    "tool.save_analysis_to_card.error": "Не удалось сохранить в карту: {err}",
    "record.source_chat": "из чата",
    "record.source_telegram": "из Telegram",
    "tool.exec_error": "Ошибка инструмента {name}: {err}",
    "tool.search_empty": "Пустой поисковый запрос.",
    "tool.embedding_failed": "Не удалось построить поисковый вектор: {err}",
    "tool.search_no_results": "По запросу ничего не найдено.",
    "tool.article_ref": "[Статья «{title}»]\n{chunk}",
    "tool.articles_empty": "База научных статей пуста.",
    "tool.no_records_days": "За последние {days} дн. нет записей анализов.",
    "tool.card_empty": "Медицинская карта пуста — пока нет записей анализов.",
    "tool.no_markers": "В медицинской карте нет показателей.",
    "tool.status.high": "выше нормы",
    "tool.status.low": "ниже нормы",
    "tool.status.normal": "в норме",
    "tool.status.elevated": "повышен",
    "tool.status.unknown": "неизвестно",
    "tool.critical_level.low": "ниже",
    "tool.critical_level.high": "выше",
    "tool.critical_found": "{name}: {value} {unit} — {level} критического порога {threshold} {threshold_unit}",
    "tool.critical_header": "ВНИМАНИЕ: обнаружены КРИТИЧЕСКИЕ отклонения, требующие срочного внимания врача:\n{warnings}",
    "tool.suspect_found": "{name}: {value} {unit} — значение похоже на ошибку ввода, рекомендуется перепроверить",
    "tool.suspect_header": "ОБРАТИТЕ ВНИМАНИЕ: некоторые значения похожи на ошибку ввода:\n{warnings}",
    "marker.suspect": "{name}: {value} {unit} — похоже на ошибку ввода (ожидаемый диапазон примерно {min}–{max} {unit})",
    "tool.marker_line": "{name}: {value} {unit} (норма {ref}, {status})",
    "tool.marker_not_found": "Показатель «{marker}» не найден в карте.",
    "tool.no_numeric_markers": "В медицинской карте нет числовых показателей.",
    "tool.trend.up": "растёт",
    "tool.trend.down": "снижается",
    "tool.trend.stable": "стабилен",
    "tool.trend_line": "{name}: {series} (измерений: {n}, тренд: {trend})",
    "backup.no_data": "Нет данных для резервной копии.",
    "backup.not_a_backup": "Неверный файл: в архиве нет medical.db. Это не резервная копия Zelvera.",
    "backup.need_zip": "Загрузите ZIP-архив резервной копии.",
    "backup.too_large": "Архив слишком большой.",
    "backup.corrupted": "Архив повреждён.",
    "backup.not_zip": "Файл не является ZIP-архивом.",
    "logs.not_created": "Лог ещё не создан.",
    # --- audit action labels ---
    "audit.app_start": "Запуск приложения",
    "audit.chat": "Запрос в чате",
    "audit.analysis": "Аналитический отчёт",
    "audit.document_extract": "Распознавание документа",
    "audit.record_create": "Добавление записи в карту",
    "audit.record_delete": "Удаление записи из карты",
    "audit.export_pdf": "Экспорт карты в PDF",
    "audit.article_upload": "Загрузка статьи",
    "audit.article_delete": "Удаление статьи",
    "audit.article_search": "Поиск по статьям",
    "audit.note_create": "Сохранение заметки",
    "audit.note_delete": "Удаление заметки",
    "audit.note_export": "Экспорт заметок в PDF",
    "audit.profile_create": "Создание профиля",
    "audit.profile_rename": "Переименование профиля",
    "audit.profile_activate": "Переключение профиля",
    "audit.profile_delete": "Удаление профиля",
    "audit.reminder_create": "Создание напоминания",
    "audit.reminder_delete": "Удаление напоминания",
    "audit.settings_update": "Изменение настроек",
    "audit.model_pull": "Скачивание модели",
    "audit.logs_clear": "Очистка журнала",
    "audit.tool_call": "Вызов инструмента ИИ",
    "audit.error": "Ошибка",
    "settings.model_required": "Укажите название модели.",
    "settings.kiwix_url_required": "Укажите адрес Kiwix (например, http://192.168.1.50:8080).",
    "settings.telegram_token_required": "Укажите токен Telegram-бота.",
    "settings.telegram_token_invalid": "Telegram отклонил токен. Проверьте значение от @BotFather.",
    "settings.telegram_unreachable": "Нет доступа к api.telegram.org ({err}). Проверьте интернет, DNS или прокси в контейнере.",
    "settings.ollama_unreachable": "Ollama недоступна по адресу {url}: {err}",
    "llm.no_api_key": "Не задан ключ USER_LLM_API_KEY. Добавьте его в backend/.env или переключите LLM_BACKEND на ollama.",
    "llm.tools_api_error": "Ошибка API при вызове инструментов: {err}",
    "llm.api_error": "Ошибка API: {err}",
    "llm.vision_api_error": "Ошибка vision API: {err}",
    "llm.ollama_connect_failed": "Не удалось подключиться к Ollama ({url}): {err}",
    "llm.ollama_not_json": "Ollama vision ({model}) вернул не-JSON ответ (HTTP {status})",
    "llm.ollama_error": "Ollama vision ({model}) вернул ошибку (HTTP {status}): {detail}. Проверьте, что модель установлена (ollama pull {model}) и поддерживает изображения.",
    "llm.tool_exec_error": "Ошибка выполнения инструмента {name}: {err}",
    "llm.tool_round_limit": "Достигнут лимит шагов работы с инструментами.",
    "llm.openai_api_error": "Ошибка OpenAI-совместимого API: {err}",
    "llm.no_data": "нет данных",
    # --- marker helpers (analysis) ---
    "marker.no_value": "значение не указано",
    "marker.norm": "норма {ref}",
    "marker.status.high": "выше нормы",
    "marker.status.low": "ниже нормы",
    "marker.status.normal": "в норме",
    "marker.status.unknown": "неизвестно",
    # --- PDF export ---
    "pdf.card_title": "Медицинская карта",
    "pdf.generated": "Сформировано {dt}, записей: {n}",
    "pdf.disclaimer": "Отчёт носит информационный характер и не является медицинским заключением. Любые вопросы по результатам решайте с врачом.",
    "pdf.record": "Запись {idx}: {source} — {date}",
    "pdf.summary": "Резюме: {summary}",
    "pdf.no_markers": "Показатели отсутствуют",
    "pdf.original_image": "Фото оригинала анализа:",
    "pdf.h_col_name": "Показатель",
    "pdf.h_col_value": "Значение",
    "pdf.h_col_unit": "Ед.",
    "pdf.h_col_ref": "Референс",
    "pdf.h_col_status": "Статус",
    "pdf.status.normal": "норма",
    "pdf.status.elevated": "повыш.",
    "pdf.status.low": "пониж.",
    "pdf.notes_title": "Заметки",
    "pdf.generated_notes": "Сформировано {dt}, заметок: {n}",
    "pdf.note": "Заметка {idx}",
    # --- AI prompts (system) ---
    "chat_system": """Ты — медицинский ИИ-ассистент. Отвечай на русском языке.
Ты помогаешь разбираться в анализах и научных статьях, но ты НЕ врач,
не ставишь диагнозы и не назначаешь лечение. Если вопрос вне твоей
компетенции — честно скажи об этом и посоветуй обратиться к врачу.
В ответах о здоровье в самом конце добавляй ровно одну короткую строку:
«Не является медицинской консультацией». Не пиши длинных дисклеймеров
и не повторяй «я не врач, не ставлю диагнозы и не назначаю лечение».
Если для ответа нужны данные из базы научных статей или медицинской
карты — используй доступные инструменты, не говори «не имею доступа».

Инструменты:
- get_medical_card — ВСЕГДА вызывай его, когда спрашивают о медицинской
  карте, анализах, показателях, здоровье пользователя («моя карта»,
  «мои анализы», «что там есть» и т.п.).
- get_marker_trends — когда спрашивают о динамике/изменении показателей.
- search_articles / list_articles — когда спрашивают о научных статьях,
  исследованиях, или просят найти информацию в базе статей.
- search_wikipedia — когда нужны общие медицинские факты, термины, описание
  заболеваний/лекарств или сравнение данных из Википедии. Википедия
  англоязычная — формулируй поисковый запрос на английском языке.
- list_kiwix_books — когда спрашивают, какие книги или Википедии подключены
  к Kiwix.
Не вызывай search_articles для вопросов о карте — данные карты берутся
только через get_medical_card.

Цитирование источников: в конце абзаца, в котором ты привёл конкретные
данные из результата инструмента, указывай источник в квадратных скобках.
- Если данные получены через search_wikipedia — формат
  [Википедия: <название статьи>]. Название бери из заголовка результата
  (то, что после «Wikipedia:»).
- Если данные получены через search_articles или из фрагментов базы статей —
  формат [Статья «<название>»].
Ссылайся только на источники, которые реально были в результатах
инструментов, не выдумывай их. Свои рассуждения, объяснения и общие
рекомендации можно давать без ссылки.

Важно: когда ты используешь search_wikipedia, найденные изображения статей
автоматически показываются пользователю в чате под твоим ответом. НЕ говори,
что не можешь показать картинки или графические файлы, — они отобразятся сами.
Ссылайся на них текстом (например, «см. рисунок выше») и опирайся на их
описания, чтобы полно ответить на вопрос пользователя.""",
    "vision_prompt": (
        "Ты — система распознавания медицинских документов (OCR). "
        "Извлеки из изображения ВЕСЬ текст бланка лабораторных анализов "
        "как можно точнее: названия показателей, значения, единицы измерения, "
        "референсные диапазоны, дату. Сохраняй структуру строка за строкой. "
        "Верни только распознанный текст без комментариев."
    ),
    "image_prompt": (
        "Опиши кратко и ёмко, что показано на изображении (2-3 предложения): "
        "основной объект/тема, ключевые подписи и цифры, тип схемы/графика/"
        "таблицы и главное содержание. Это короткая подпись под иллюстрацией "
        "в ответе. Отвечай на русском языке."
    ),
    "extraction_prompt": """Ты — медицинский анализатор лабораторных анализов.
Ниже дан распознанный текст бланка анализов. Извлеки из него все медицинские
показатели (маркеры): название, значение, единицу измерения, референсный
диапазон и отклонение от нормы. Также определи ДАТУ анализа (дату взятия
биоматериала или дату документа), если она указана.

Верни ТОЛЬКО валидный JSON без пояснений, в формате:
{{
  "date": "ГГГГ-ММ-ДД" | null,
  "markers": [
    {{
      "name": "Гемоглобин",
      "value": 145,
      "unit": "г/л",
      "reference_range": "120-160",
      "status": "normal" | "high" | "low",
      "raw_text": "Гемоглобин 145 г/л"
    }}
  ],
  "summary": "Краткое резюме на русском: что в норме, что отклонено, на что обратить внимание."
}}

Правила:
- date: приведи к формату ГГГГ-ММ-ДД. Если даты нет или она не читается, ставь null.
- Если значение не распознано, ставь value = null.
- status: high — выше нормы, low — ниже нормы, normal — в норме, unknown — норма неизвестна.
- Ниже список известных показателей (канонические названия и их синонимы/аббревиатуры).
  Если название в бланке — синоним или аббревиатура показателя из списка,
  используй его каноническое название из списка.
- Если показателя в списке нет — оставь название ровно как в бланке,
  не подменяй его похожим.
- Игнорируй заголовки, логотипы и служебные строки без показателей.
- Не выдумывай данные, которых нет в тексте.

Известные показатели:
{catalog}

Текст анализов:
\"\"\"{text}\"\"\"
""",
    "extraction_retry_prompt": """Ты — медицинский анализатор лабораторных анализов. Ниже дан распознанный текст бланка. Извлеки из него медицинские показатели и дату анализа.

ПРЕДЫДУЩИЙ ТВОЙ ОТВЕТ НЕ БЫЛ ВАЛИДНЫМ JSON. Теперь верни СТРОГО ОДИН JSON-объект и НИЧЕГО больше: без пояснений, без markdown (```), без текста до '{{' и после '}}'. Начинай ответ с '{{' и заканчивай '}}'.

Формат:
{{
  "date": "ГГГГ-ММ-ДД" | null,
  "markers": [
    {{
      "name": "...",
      "value": число | null,
      "unit": "...",
      "reference_range": "...",
      "status": "normal" | "high" | "low" | "unknown",
      "raw_text": "..."
    }}
  ],
  "summary": "Краткое резюме на русском: что в норме, что отклонено."
}}

Список известных показателей (если название в бланке — синоним или
аббревиатура из списка, используй каноническое название; если показателя
в списке нет — оставь название ровно как в бланке):
{catalog}

Текст анализов:
\"\"\"{text}\"\"\"
""",
    "extraction_grounded_prompt": """Ты — медицинский анализатор лабораторных анализов. Ты уже извлёк показатели из бланка, но часть названий показателей для тебя новая или неоднозначная. Чтобы вывод был объективным, ниже дана справка из Википедии по этим показателям.

С опорой на Википедию уточни такие показатели: приведи названия к общепринятому виду, проверь единицы измерения и референсный диапазон. Остальные показатели не меняй. Значения из бланка не выдумывай и не искажай. Если справка не помогла или не относится к показателю — оставь показатель как был.

Извлечённые ранее показатели (JSON):
{markers_json}

Справка из Википедии:
{snippets}

Верни ТОЛЬКО валидный JSON без пояснений, в формате:
{{
  "date": "ГГГГ-ММ-ДД" | null,
  "markers": [
    {{
      "name": "Гемоглобин",
      "value": 145,
      "unit": "г/л",
      "reference_range": "120-160",
      "status": "normal" | "high" | "low" | "unknown",
      "raw_text": "Гемоглобин 145 г/л"
    }}
  ],
  "summary": "Итоговое резюме на русском: что в норме, что отклонено, на что обратить внимание с учётом уточнённых показателей."
}}
""",
    "analysis_system": """Ты — медицинский аналитик. Ты помогаешь человеку понимать
его анализы в контексте научных данных. Ты НЕ врач и НЕ ставишь диагнозы,
НЕ назначаешь лечение. Подчёркивай, что информация носит ознакомительный
характер, и нужна консультация врача.

Структура отчёта:
1. Обзор текущих показателей (что в норме, что вне нормы).
2. Сопоставление отклонений с научными фрагментами из базы статей.
3. На что обратить внимание и как наблюдать динамику (без назначений).
4. Дисклеймер.

Отвечай на русском языке, понятно и структурированно.""",
    "analysis_user": """Текущие показатели пользователя из медицинской карты:
{markers_text}

Релевантные научные фрагменты из базы статей:
{articles_text}

Составь персонализированный аналитический отчёт по этим данным.""",
    "longterm_system": """Ты — медицинский аналитик. Тебе дают многолетнюю сводку
лабораторных показателей одного человека (медианы по годам). Нужно дать
обзорную оценку динамики здоровья за период. Ты НЕ врач и НЕ ставишь
диагнозы, НЕ назначаешь лечение.

Структура отчёта:
1. Общая картина за период: сколько лет и анализов, как менялись ключевые
   показатели.
2. Показатели со стойкими отклонениями (флаг «стойко выше/ниже нормы») —
   что это и почему важно наблюдать.
3. Положительная динамика и ухудшения относительно ранних лет.
4. На что обратить внимание и какие данные стоит добавить (без назначений).
5. Не добавляй дисклеймеров про «не врач» — короткая строка добавляется автоматически.

Опирайся только на приведённую сводку, не выдумывай значения и годы,
которых нет в данных. Отвечай структурированно и понятно на русском языке.""",
    "longterm_user": """Многолетняя сводка показателей пользователя из мед. карты:

{summary}

Составь общий отчёт о состоянии здоровья за период и динамике показателей.""",
    "summary_prompt": """Ты — научный редактор. Ниже фрагмент медицинской научной статьи.
Напиши краткое резюме этого фрагмента на русском языке (3-5 предложений):
о чём говорится, методы, ключевые результаты, выводы.
Не выдумывай данные, которых нет в тексте.

Фрагмент статьи:
\"\"\"
{text}
\"\"\"
""",
    "final_summary_prompt": """Ты — научный редактор. Ниже частичные резюме разных частей
одной медицинской научной статьи. Объедини их в единое связное резюме
на русском языке (5-10 предложений): тема, методы, ключевые результаты,
выводы и клиническая значимость. Не выдумывай данные.

Частичные резюме:
\"\"\"
{parts}
\"\"\"
""",
    # --- Telegram-бот ---
    "telegram.cmd_start": "Начать",
    "telegram.cmd_help": "Справка",
    "telegram.cmd_reset": "Сбросить диалог",
    "telegram.start": "Здравствуйте! Я медицинский ИИ-ассистент Zelvera.\n\nМожно просто писать вопросы в чат, отправить фото бланка анализов (распознаю и предложу сохранить в мед. карту) или голосовое сообщение. Напоминания о пересдаче анализов приходят сюда автоматически.\n\nКоманды: /help — справка, /reset — очистить историю диалога.\n\nОтвечаю на основе вашей мед. карты, базы статей и офлайн-Википедии.",
    "telegram.help": "Что я умею:\n\n• Ответы на вопросы об анализах и здоровье (с учётом вашей мед. карты).\n• Фото бланка анализов — распознаю показатели и предложу сохранить в карту.\n• Голосовые сообщения — распознаю речь (если включено).\n• Напоминания о пересдаче анализов.\n\nКоманды: /start, /help, /reset.",
    "telegram.reset": "История диалога очищена. Можете начать заново.",
    "telegram.empty_answer": "Не удалось сформировать ответ. Попробуйте переформулировать вопрос.",
    "telegram.photo_failed": "Не удалось обработать файл. Попробуйте отправить более чёткое фото бланка.",
    "telegram.no_markers": "На изображении не найдено показателей. Убедитесь, что бланк хорошо читается и попадает в кадр целиком.",
    "telegram.analysis_header": "Распознано показателей: {n}",
    "telegram.analysis_date": "Дата анализа: {date}",
    "telegram.analysis_hint": "Сохранить в мед. карту?",
    "telegram.btn_save": "Сохранить в карту",
    "telegram.btn_cancel": "Отмена",
    "telegram.saved": "Сохранено",
    "telegram.saved_record": "Запись #{id} сохранена в мед. карту.",
    "telegram.canceled": "Сохранение отменено.",
    "telegram.save_expired": "Данные уже неактуальны, пришлите фото заново.",
    "telegram.voice_disabled": "Распознавание речи отключено или недоступно. Напишите вопрос текстом или включите голос в настройках.",
    "telegram.voice_failed": "Не удалось распознать голосовое сообщение. Попробуйте записать заново.",
    "telegram.recognized": "Распознано: {text}",
    "telegram.voice_title": "Ответ Zelvera",
    "telegram.reminder_due": "Напоминание: пора пересдать показатель «{marker}» (прошло {days} дн., интервал {interval} дн.).",
    "telegram.denied": "У вас нет доступа к этому боту.",
    "telegram.setup_id": "Настройка бота: ваш Telegram ID — {id}.\nДобавьте его в Zelvera: «Настройки» → «Telegram-бот» → «Разрешённые Telegram ID», затем сохраните. После этого бот начнёт отвечать.",
}

EN = {
    # --- shared ---
    "error.prefix": "[Error]",
    # --- HTTPException details ---
    "profile.not_found": "Profile not found",
    "profile.no_profiles": "No profiles available",
    "profile.single_only": "The app works with a single health profile. The data can be edited.",
    "profile.single_no_delete": "The app works with a single health profile. Deletion is not available.",
    "profile.name_required": "Profile name cannot be empty.",
    "record.not_found": "Record not found",
    "record.image_not_found": "Original photo not found",
    "reminder.marker_required": "Please specify the name of the marker.",
    "reminder.not_found": "Reminder not found",
    "note.empty": "Note cannot be empty.",
    "note.not_found": "Note not found",
    "article.not_found": "Article not found",
    "article.unsupported": "Unsupported format. Accepted: {exts}",
    "article.empty_file": "Empty file.",
    "article.too_large": "File is too large (max 25 MB).",
    "article.too_short": "Text is too short — does not look like a scientific article.",
    "search.empty": "Empty search query.",
    "analysis.card_empty": "The medical card is empty. Upload your lab results first (photo/document) in the chat.",
    "analysis.no_markers": "No markers in the card to analyze.",
    "analysis.no_articles_note": "Note: no materials matching your markers were found in the articles database.\n\n",
    "analysis.articles_not_found": "No relevant scientific articles found — the report will be based on the markers alone.",
    "analysis.article_ref": "[Article «{title}»] {chunk}",
    "longterm.no_data": "No numeric markers for the selected period.",
    "longterm.empty_period": "No records for the selected period.",
    "longterm.flag.insufficient": "not enough data",
    "longterm.flag.stable_normal": "stable within norm",
    "longterm.flag.persistent_high": "persistently above norm",
    "longterm.flag.persistent_low": "persistently below norm",
    "longterm.flag.fluctuation": "fluctuating",
    "longterm.flag.improving": "improving",
    "longterm.flag.worsening": "worsening",
    "longterm.flag.trend_up": "rising",
    "longterm.flag.trend_down": "falling",
    "longterm.status.normal": "normal",
    "longterm.status.high": "above norm",
    "longterm.status.low": "below norm",
    "longterm.status.mixed": "mixed",
    "longterm.status.unknown": "no data",
    "longterm.prompt.span": "Period: {span}",
    "longterm.prompt.records": "Tests by year: {counts}",
    "longterm.prompt.year_count": "{year}: {n}",
    "longterm.prompt.marker": "Marker: {name} ({unit}), norm {ref}, flag: {flag}, measurements: {n}",
    "longterm.prompt.year_value": "{year}: median {median} (n={n}, {status})",
    "longterm.disclaimer": "This is not medical advice.",
    "documents.unsupported": "Unsupported format. Accepted: {exts}",
    "documents.empty_file": "Empty file.",
    "documents.too_large": "File is too large (max 50 MB).",
    "documents.extract_failed": "Failed to extract text from the file.",
    "extract.no_json": "The model response does not contain JSON.",
    "extract.bad_json": "Failed to parse JSON from the model response.",
    "document.pdf_open_failed": "Failed to open PDF: {err}",
    "document.pdf_no_text": "No text layer found in the PDF. It may be a scanned document — upload it as a photo instead.",
    "document.docx_open_failed": "Failed to open DOCX: {err}",
    "document.docx_no_text": "No text found in the DOCX.",
    "embeddings.empty": "Ollama did not return embeddings.",
    "embeddings.api_error": "Embeddings API error: {err}",
    # --- AI tools (tool descriptions and results) ---
    "tool.search_articles.desc": "Semantic search across the user's scientific articles database. Returns relevant article fragments with their titles. Use when the user asks about scientific data, research, or wants to find information in their articles.",
    "tool.search_articles.query": "Search query in English.",
    "tool.search_articles.limit": "Maximum number of results (default 5).",
    "tool.search_wikipedia.desc": "Full-text search in the offline Wikipedia (Kiwix, English). Returns snippets and article texts; the found article images are automatically shown to the user in the chat. Use when the user asks about general medical terms, drugs, diseases, or wants to compare or verify information from Wikipedia.",
    "tool.search_wikipedia.query": "Search query (in English — the Wikipedia is English).",
    "tool.search_wikipedia.limit": "How many articles to fetch in full (default 3).",
    "tool.list_kiwix_books.desc": "Returns the list of books connected to Kiwix (offline content: Wikipedia and others). Use when the user asks which books or which Wikipedias are available/connected.",
    "kiwix.no_books": "No books are connected to Kiwix.",
    "kiwix.empty_query": "Empty search query.",
    "kiwix.not_configured": "Kiwix address is not set. Specify it in the settings (section \"Offline Wikipedia\").",
    "kiwix.zim_not_found": "No Wikipedia book found. Specify the ZIM book name in the settings.",
    "kiwix.books_failed": "Failed to get the list of Kiwix books.",
    "kiwix.article_failed": "Failed to fetch the article text.",
    "kiwix.unreachable": "Kiwix is unreachable at {url}: {err}",
    "kiwix.no_results": "Nothing found in the offline Wikipedia for the query.",
    "tool.list_articles.desc": "Returns the list of scientific article titles uploaded to the user's database.",
    "tool.get_medical_card.desc": "Returns the current markers from the current user profile's medical card (the latest value of each lab marker). Use when the user asks about their lab results or health. You can optionally limit the period (days) — e.g. 30 for \"over the last month\".",
    "tool.get_medical_card.days": "How many recent days to take into account (default: whole history).",
    "tool.get_profile.desc": "Returns the current user profile details: name, birth year and age, blood type, height, weight. Use when the user asks about their age, birth year, blood type, height or weight.",
    "tool.get_profile.empty": "The user profile is not filled in: no name, birth year, blood type, height or weight.",
    "tool.profile.title": "User profile details:",
    "tool.profile.context": "User profile details: {summary}. Use them when answering about age, birth year, blood type, height and weight; do not invent missing data.",
    "tool.profile.name": "name: {value}",
    "tool.profile.birth_year": "birth year: {value}",
    "tool.profile.age": " (age: {value})",
    "tool.profile.blood": "blood type: {value}",
    "tool.profile.height": "height: {value} cm",
    "tool.profile.weight": "weight: {value} kg",
    "tool.get_marker_trends.desc": "Returns the dynamics of the current profile's lab markers: values by date, number of measurements and trend direction (up/down/stable). Use when the user asks how their markers have changed over time.",
    "tool.get_marker_trends.marker": "Marker name. If not specified — all markers.",
    "tool.get_marker_trends.days": "How many recent days to take into account (default: whole history).",
    "tool.check_marker_norm.desc": "Checks a lab marker value against the reference-norms reference (age/sex aware). First get the current marker value via get_medical_card or get_marker_trends, then pass it here with its units. Use when the user asks whether their marker is within the norm or how far it deviates. If the marker is missing from the catalog, the result may include a Wikipedia reference — use it in your explanation.",
    "tool.check_marker_norm.marker": "Marker name (e.g. hemoglobin, glucose, creatinine).",
    "tool.check_marker_norm.value": "Marker value (a number).",
    "tool.check_marker_norm.unit": "Units (e.g. g/L, mmol/L). Optional if unknown.",
    "tool.check_marker_norm.sex": "Sex (m/f). If known.",
    "tool.check_marker_norm.age": "Age in years. If known.",
    "tool.check_marker_norm.empty": "Empty marker name.",
    "tool.wiki_header": "Reference from the offline Wikipedia (for markers missing from the reference-norms catalog):",
    "tool.wiki_item": "- {marker} -> {title}: {snippet}",
    "norm.not_found": "The reference has no norm for marker \"{marker}\". Refer to the lab reference range from the medical card.",
    "norm.not_numeric": "Could not parse \"{value}\" as a number.",
    "norm.single": "Norm{note}: {range}. Status: {status}",
    "norm.item": "- {note}: {range}",
    "norm.multi_status": "Cannot give a definite answer: status {status}. Ask the user for their sex and age.",
    "norm.status.normal": "within norm",
    "norm.status.high": "above norm",
    "norm.status.low": "below norm",
    "norm.status.unknown": "not evaluated",
    "norm.status.ambiguous": "ambiguous",
    "tool.unknown": "Unknown tool: {name}",
    "tool.save_analysis_to_card.desc": "Saves the lab markers discussed in the conversation into the user's medical card as one new record. Call ONLY when the user explicitly asks to save the discussed markers to the card (e.g. \"save to my card\", \"add these markers to my card\"). Pass each marker with its name and value, units and range if they were mentioned.",
    "tool.save_analysis_to_card.markers": "Array of markers. Each item: name (required), value, unit, reference_range.",
    "tool.save_analysis_to_card.date": "Analysis date in YYYY-MM-DD if it was mentioned in the conversation; otherwise omit it.",
    "tool.save_analysis_to_card.ok": "Saved to the medical card: {names}. A new lab record was added.",
    "tool.save_analysis_to_card.empty": "No markers were passed. Ask the user for the values and call again.",
    "tool.save_analysis_to_card.error": "Failed to save to the card: {err}",
    "record.source_chat": "from chat",
    "record.source_telegram": "from Telegram",
    "tool.exec_error": "Tool error {name}: {err}",
    "tool.search_empty": "Empty search query.",
    "tool.embedding_failed": "Failed to build the search vector: {err}",
    "tool.search_no_results": "Nothing found for the query.",
    "tool.article_ref": "[Article «{title}»]\n{chunk}",
    "tool.articles_empty": "The scientific articles database is empty.",
    "tool.no_records_days": "No lab records for the last {days} days.",
    "tool.card_empty": "The medical card is empty — no lab records yet.",
    "tool.no_markers": "No markers in the medical card.",
    "tool.status.high": "above normal",
    "tool.status.low": "below normal",
    "tool.status.normal": "in range",
    "tool.status.elevated": "elevated",
    "tool.status.unknown": "unknown",
    "tool.critical_level.low": "below",
    "tool.critical_level.high": "above",
    "tool.critical_found": "{name}: {value} {unit} — {level} the critical threshold {threshold} {threshold_unit}",
    "tool.critical_header": "WARNING: CRITICAL deviations were found that require urgent medical attention:\n{warnings}",
    "tool.suspect_found": "{name}: {value} {unit} — the value looks like an input error, please double-check",
    "tool.suspect_header": "NOTE: some values look like input errors:\n{warnings}",
    "marker.suspect": "{name}: {value} {unit} — looks like an input error (expected range roughly {min}–{max} {unit})",
    "tool.marker_line": "{name}: {value} {unit} (norm {ref}, {status})",
    "tool.marker_not_found": "Marker «{marker}» not found in the card.",
    "tool.no_numeric_markers": "No numeric markers in the medical card.",
    "tool.trend.up": "rising",
    "tool.trend.down": "falling",
    "tool.trend.stable": "stable",
    "tool.trend_line": "{name}: {series} (measurements: {n}, trend: {trend})",
    "backup.no_data": "No data to back up.",
    "backup.not_a_backup": "Invalid file: medical.db is missing from the archive. This is not a Zelvera backup.",
    "backup.need_zip": "Upload a ZIP archive of the backup.",
    "backup.too_large": "Archive is too large.",
    "backup.corrupted": "Archive is corrupted.",
    "backup.not_zip": "The file is not a ZIP archive.",
    "logs.not_created": "Log file has not been created yet.",
    # --- audit action labels ---
    "audit.app_start": "App start",
    "audit.chat": "Chat request",
    "audit.analysis": "Analytical report",
    "audit.document_extract": "Document recognition",
    "audit.record_create": "Added record to the card",
    "audit.record_delete": "Deleted record from the card",
    "audit.export_pdf": "Exported card to PDF",
    "audit.article_upload": "Article upload",
    "audit.article_delete": "Article deletion",
    "audit.article_search": "Article search",
    "audit.note_create": "Note saved",
    "audit.note_delete": "Note deleted",
    "audit.note_export": "Exported notes to PDF",
    "audit.profile_create": "Profile created",
    "audit.profile_rename": "Profile renamed",
    "audit.profile_activate": "Profile switched",
    "audit.profile_delete": "Profile deleted",
    "audit.reminder_create": "Reminder created",
    "audit.reminder_delete": "Reminder deleted",
    "audit.settings_update": "Settings changed",
    "audit.model_pull": "Model download",
    "audit.logs_clear": "Log cleared",
    "audit.tool_call": "AI tool call",
    "audit.error": "Error",
    "settings.model_required": "Please specify the model name.",
    "settings.kiwix_url_required": "Please specify the Kiwix address (e.g. http://192.168.1.50:8080).",
    "settings.telegram_token_required": "Please specify the Telegram bot token.",
    "settings.telegram_token_invalid": "Telegram rejected the token. Check the value from @BotFather.",
    "settings.telegram_unreachable": "Cannot reach api.telegram.org ({err}). Check the container's internet, DNS or proxy.",
    "settings.ollama_unreachable": "Ollama is unreachable at {url}: {err}",
    "llm.no_api_key": "USER_LLM_API_KEY is not set. Add it to backend/.env or switch LLM_BACKEND to ollama.",
    "llm.tools_api_error": "API error while calling tools: {err}",
    "llm.api_error": "API error: {err}",
    "llm.vision_api_error": "Vision API error: {err}",
    "llm.ollama_connect_failed": "Failed to connect to Ollama ({url}): {err}",
    "llm.ollama_not_json": "Ollama vision ({model}) returned a non-JSON response (HTTP {status})",
    "llm.ollama_error": "Ollama vision ({model}) returned an error (HTTP {status}): {detail}. Check that the model is installed (ollama pull {model}) and supports images.",
    "llm.tool_exec_error": "Error executing tool {name}: {err}",
    "llm.tool_round_limit": "Tool call round limit reached.",
    "llm.openai_api_error": "OpenAI-compatible API error: {err}",
    "llm.no_data": "no data",
    # --- marker helpers (analysis) ---
    "marker.no_value": "value not specified",
    "marker.norm": "norm {ref}",
    "marker.status.high": "above normal",
    "marker.status.low": "below normal",
    "marker.status.normal": "in range",
    "marker.status.unknown": "unknown",
    # --- PDF export ---
    "pdf.card_title": "Medical card",
    "pdf.generated": "Generated {dt}, records: {n}",
    "pdf.disclaimer": "This report is for informational purposes only and is not a medical conclusion. Discuss any questions about the results with your doctor.",
    "pdf.record": "Record {idx}: {source} — {date}",
    "pdf.summary": "Summary: {summary}",
    "pdf.no_markers": "No markers",
    "pdf.original_image": "Original photo of the lab result:",
    "pdf.h_col_name": "Marker",
    "pdf.h_col_value": "Value",
    "pdf.h_col_unit": "Unit",
    "pdf.h_col_ref": "Reference",
    "pdf.h_col_status": "Status",
    "pdf.status.normal": "normal",
    "pdf.status.elevated": "elevated",
    "pdf.status.low": "low",
    "pdf.notes_title": "Notes",
    "pdf.generated_notes": "Generated {dt}, notes: {n}",
    "pdf.note": "Note {idx}",
    # --- AI prompts (system) ---
    "chat_system": """You are a medical AI assistant. Answer in English.
You help people understand lab results and scientific articles, but you are NOT a doctor:
you do not make diagnoses or prescribe treatment. If a question is outside your competence,
say so honestly and advise consulting a doctor.
For health-related answers, add exactly one short line at the very end:
"This is not medical advice." Do not write long disclaimers and do not repeat
"I am not a doctor, I do not make diagnoses or prescribe treatment".
If answering requires data from the articles database or the medical card,
use the available tools — do not say "I have no access".

Tools:
- get_medical_card — ALWAYS call it when asked about the medical card, lab results,
  markers, or the user's health ("my card", "my labs", "what is there", etc.).
- get_marker_trends — when asked about dynamics/changes of markers.
- search_articles / list_articles — when asked about scientific articles, research,
  or asked to find information in the articles database.
- search_wikipedia — when general medical facts, terms, descriptions of diseases/drugs,
  or comparison of Wikipedia data are needed. The Wikipedia is English —
  formulate the search query in English.
- list_kiwix_books — when asked which books or Wikipedias are connected to Kiwix.
Do not call search_articles for questions about the card — card data comes only
through get_medical_card.

Source citation: at the end of a paragraph where you state concrete data from a
tool result, cite the source in square brackets.
- If the data came from search_wikipedia — format [Wikipedia: <article title>].
  Take the title from the result header (the part after "Wikipedia:").
- If the data came from search_articles or from the articles database fragments —
  format [Article «<title>»].
Cite only sources that were actually present in the tool results; do not invent
them. Your own reasoning, explanations and general recommendations can be given
without a citation.

Important: when you use search_wikipedia, the images from the articles are
automatically shown to the user in the chat below your answer. Do NOT say you
cannot display images or graphic files — they will appear on their own.
Refer to them in text (e.g., "see the image above") and rely on their
descriptions to fully answer the user's question.""",
    "vision_prompt": (
        "You are a medical document recognition (OCR) system. "
        "Extract ALL the text from the lab results form image as accurately as possible: "
        "marker names, values, units of measurement, reference ranges, date. "
        "Keep the structure line by line. "
        "Return only the recognized text without any comments."
    ),
    "image_prompt": (
        "Briefly and concisely describe what is shown in the image (2-3 sentences): "
        "the main object/topic, key labels and numbers, the type of diagram/chart/"
        "table and its main content. This is a short caption under an illustration "
        "in an answer. Answer in English."
    ),
    "extraction_prompt": """You are a medical lab results analyzer.
Below is the recognized text of a lab results form. Extract all medical
markers from it: name, value, unit of measurement, reference range and
deviation from normal. Also determine the DATE of the analysis (the date
of biomaterial collection or the document date), if present.

Return ONLY valid JSON without explanations, in the format:
{{
  "date": "YYYY-MM-DD" | null,
  "markers": [
    {{
      "name": "Hemoglobin",
      "value": 145,
      "unit": "g/L",
      "reference_range": "120-160",
      "status": "normal" | "high" | "low",
      "raw_text": "Hemoglobin 145 g/L"
    }}
  ],
  "summary": "A short summary in English: what is normal, what is deviated, what to look at."
}}

Rules:
- date: convert to YYYY-MM-DD format. If the date is absent or unreadable, set null.
- If a value is not recognized, set value = null.
- status: high — above normal, low — below normal, normal — in range, unknown — normal unknown.
- Below is a list of known markers (canonical names and their synonyms/abbreviations).
  If the name in the form is a synonym or abbreviation of a marker from the list,
  use its canonical name from the list.
- If a marker is not in the list — keep the name exactly as in the form,
  do not replace it with a similar one.
- Ignore headers, logos and service lines without markers.
- Do not invent data that is not in the text.

Known markers:
{catalog}

Lab results text:
\"\"\"{text}\"\"\"
""",
    "extraction_retry_prompt": """You are a medical lab results analyzer. Below is the recognized text of a lab results form. Extract the medical markers and the analysis date from it.

YOUR PREVIOUS RESPONSE WAS NOT VALID JSON. Now return STRICTLY ONE JSON object and nothing else: no explanations, no markdown (```), no text before '{{' or after '}}'. Start your answer with '{{' and end it with '}}'.

Format:
{{
  "date": "YYYY-MM-DD" | null,
  "markers": [
    {{
      "name": "...",
      "value": number | null,
      "unit": "...",
      "reference_range": "...",
      "status": "normal" | "high" | "low" | "unknown",
      "raw_text": "..."
    }}
  ],
  "summary": "A short summary in English: what is normal, what is deviated."
}}

List of known markers (if the name in the form is a synonym or abbreviation
from the list, use the canonical name; if a marker is not in the list — keep
the name exactly as in the form):
{catalog}

Lab results text:
\"\"\"{text}\"\"\"
""",
    "extraction_grounded_prompt": """You are a medical lab results analyzer. You already extracted markers from the form, but some of the marker names are new or ambiguous to you. To make the conclusion objective, below is reference information from Wikipedia about these markers.

Using Wikipedia, refine such markers: bring their names to the commonly accepted form, verify the units and the reference range. Do not change the other markers. Do not invent or distort values from the form. If the reference does not help or is irrelevant, keep the marker as it was.

Previously extracted markers (JSON):
{markers_json}

Reference from Wikipedia:
{snippets}

Return ONLY valid JSON without explanations, in the format:
{{
  "date": "YYYY-MM-DD" | null,
  "markers": [
    {{
      "name": "Hemoglobin",
      "value": 145,
      "unit": "g/L",
      "reference_range": "120-160",
      "status": "normal" | "high" | "low" | "unknown",
      "raw_text": "Hemoglobin 145 g/L"
    }}
  ],
  "summary": "A final summary in English: what is normal, what is deviated, what to look at considering the refined markers."
}}
""",
    "analysis_system": """You are a medical analyst. You help a person understand
their lab results in the context of scientific data. You are NOT a doctor,
you do not make diagnoses or prescribe treatment. Emphasize that the
information is for informational purposes and a doctor's consultation is needed.

Report structure:
1. Overview of current markers (what is in range, what is out of range).
2. Mapping deviations to scientific fragments from the articles database.
3. What to look at and how to monitor dynamics (no prescriptions).
4. Disclaimer.

Answer in English, clearly and in a structured way.""",
    "analysis_user": """The user's current markers from the medical card:
{markers_text}

Relevant scientific fragments from the articles database:
{articles_text}

Compose a personalized analytical report based on this data.""",
    "longterm_system": """You are a medical analyst. You are given a multi-year
summary of one person's lab markers (medians by year). Give an overview of
their health dynamics over the period. You are NOT a doctor: do not make
diagnoses or prescribe treatment.

Report structure:
1. Overall picture: how many years and tests, how key markers changed.
2. Markers with persistent deviations (flag "persistently above/below norm") —
   what they mean and why monitoring matters.
3. Positive dynamics and worsening compared to earlier years.
4. What to pay attention to and which data to add (no prescriptions).
5. Do not add disclaimers about "not a doctor" — a short line is added automatically.

Rely only on the provided summary; do not invent values or years that are not
in the data. Answer in a structured, clear way in English.""",
    "longterm_user": """Multi-year summary of the user's markers from the medical card:

{summary}

Compose an overall report on their health over the period and marker dynamics.""",
    "summary_prompt": """You are a scientific editor. Below is a fragment of a medical scientific article.
Write a short summary of this fragment in English (3-5 sentences):
what it is about, methods, key results, conclusions.
Do not invent data that is not in the text.

Article fragment:
\"\"\"
{text}
\"\"\"
""",
    "final_summary_prompt": """You are a scientific editor. Below are partial summaries of different parts
of one medical scientific article. Combine them into a single coherent summary
in English (5-10 sentences): topic, methods, key results, conclusions and
clinical significance. Do not invent data.

Partial summaries:
\"\"\"
{parts}
\"\"\"
""",
    # --- Telegram bot ---
    "telegram.cmd_start": "Start",
    "telegram.cmd_help": "Help",
    "telegram.cmd_reset": "Reset dialog",
    "telegram.start": "Hello! I am Zelvera, a medical AI assistant.\n\nJust type your questions in chat, send a photo of a lab report (I will recognize the values and offer to save them to your medical card), or send a voice message. Re-test reminders are delivered here automatically.\n\nCommands: /help — help, /reset — clear dialog history.\n\nI answer based on your medical card, the article base and the offline Wikipedia.",
    "telegram.help": "What I can do:\n\n• Answer questions about tests and health (using your medical card).\n• Recognize a photo of a lab report and offer to save the values to the card.\n• Transcribe voice messages (if enabled).\n• Send re-test reminders.\n\nCommands: /start, /help, /reset.",
    "telegram.reset": "Dialog history cleared. You can start over.",
    "telegram.empty_answer": "Could not build an answer. Please rephrase your question.",
    "telegram.photo_failed": "Could not process the file. Please send a clearer photo of the report.",
    "telegram.no_markers": "No markers found in the image. Make sure the report is well lit and fully in frame.",
    "telegram.analysis_header": "Markers recognized: {n}",
    "telegram.analysis_date": "Test date: {date}",
    "telegram.analysis_hint": "Save to the medical card?",
    "telegram.btn_save": "Save to card",
    "telegram.btn_cancel": "Cancel",
    "telegram.saved": "Saved",
    "telegram.saved_record": "Record #{id} saved to the medical card.",
    "telegram.canceled": "Saving canceled.",
    "telegram.save_expired": "The data is outdated, please send the photo again.",
    "telegram.voice_disabled": "Speech recognition is disabled or unavailable. Type your question or enable voice in settings.",
    "telegram.voice_failed": "Could not recognize the voice message. Please try recording again.",
    "telegram.recognized": "Recognized: {text}",
    "telegram.voice_title": "Zelvera answer",
    "telegram.reminder_due": "Reminder: it is time to retest \"{marker}\" ({days} days passed, interval {interval} days).",
    "telegram.denied": "You do not have access to this bot.",
    "telegram.setup_id": "Bot setup: your Telegram ID is {id}.\nAdd it in Zelvera: \"Settings\" -> \"Telegram bot\" -> \"Allowed Telegram IDs\", then save. After that the bot will reply.",
}

_TABLES = {"ru": RU, "en": EN}


def t(key: str, **vars) -> str:
    table = _TABLES.get(get_lang(), RU)
    text = table.get(key)
    if text is None:
        text = RU.get(key, key)
    if vars:
        for k, v in vars.items():
            text = text.replace("{" + k + "}", str(v))
    return text
