# План рефакторинга — по итогам аудита от 2026-07-23

## Контекст

Этот план основан на повторном глубоком аудите кодовой базы после предыдущего
прохода "SOLID/DRY/Facade cleanup" (см. `SOLID_DRY_FACADE_REFACTORING_PLAN.md`,
`REFACTORING_COMPLETION_REPORT.md`). Аудит показал, что часть проблем
осталась нерешённой, а часть — введена заново. Все пункты ниже подтверждены
чтением исходного кода (файл + номер строки), а не предположениями.

Приоритеты:
- 🔴 **P0 — критично**: баг влияет на деньги/данные/безопасность прямо сейчас
- 🟠 **P1 — важно**: логическая ошибка, потенциальная порча данных при определённых сценариях
- 🟡 **P2 — качество**: SOLID/DRY/архитектура, не ломает прод, но повышает риск будущих багов

Каждый пункт содержит: проблему, файлы, план исправления, критерий готовности (DoD).

---

## Этап 0 (P0): Критичные баги — исправить в первую очередь

### 0.1 Настройки из админ-панели не применяются (`.env` пишется не туда) — ✅ ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `backend/app/config/settings.py:54` грузит конфиг из `backend/.env`.
`backend/app/utils/env_updater.py:35` вычисляет путь на один уровень выше и
пишет в **корневой** `/root/telegram-bot/.env`. Подтверждено на диске:
корневой `.env` содержит `DEFAULT_TIME_STEP=5`, а `backend/.env` (реальный,
загружаемый) — `DEFAULT_TIME_STEP=10`. Плюс `get_settings()`
(`config/settings.py:114`) закэширован через `@lru_cache()` без инвалидации —
даже полностью корректная запись в файл не подхватится без перезапуска
процесса.

**Симптом для пользователя.** Админ меняет шаг времени/буфер в боте, видит
"✅ сохранено", но бот продолжает работать со старыми значениями.

**План исправления.**
1. В `env_updater.py` поправить вычисление пути: `project_root = backend_dir`
   (а не `backend_dir.parent`), либо явно завести константу пути к `.env` в
   `config/settings.py` и импортировать её в `env_updater.py`, чтобы путь
   вычислялся в одном месте (устраняет и будущую рассинхронизацию).
2. Убрать `@lru_cache()` c `get_settings()` **или** добавить
   `get_settings.cache_clear()` сразу после записи в `.env` внутри
   `update_env_file()`, чтобы следующий вызов `get_settings()` перечитал файл.
   Предпочтительно первое — `lru_cache` на настройках, которые можно менять
   рантаймом, это сама по себе плохая идея (SRP/DIP: конфиг должен уметь
   обновляться, а не быть "заморожен" декоратором).
3. Убрать/смигрировать мусорный корневой `.env` (сверить с `backend/.env`,
   один из файлов — источник правды, второй — удалить или добавить в
   `.gitignore` с пометкой "не используется").

**DoD.** Интеграционный тест: вызвать `update_env_file(default_time_step=42)`,
затем `get_settings()` (без перезапуска процесса) — `time_step_minutes == 42`.

**Как исправлено фактически** (реализован более радикальный вариант из
плана — п.3, полный отказ от `.env` как источника истины для этих полей,
а не патч пути):
- `backend/app/services/settings_management_service.py` — убраны все три
  вызова `update_env_file(...)` после `update_work_hours`/`update_time_step`/
  `update_buffer_time`. Теперь единственное действие при изменении настроек
  — commit в БД.
- `backend/app/repositories/settings.py` — из `get_settings()` убран
  параметр `sync_with_env`, метод `sync_with_env()` удалён целиком.
  `create_default_settings()` (сидирует строку из `.env`) теперь выполняется
  **только один раз** — когда строки `system_settings_booking_bot` ещё нет
  в базе. Заодно поправлен смежный truthy-баг (п. 2.4.1 ниже): `if
  time_step_minutes:` / `if buffer_time_minutes:` заменены на `is not None`,
  чтобы значение `0` не игнорировалось.
- `backend/app/main.py` (`on_startup`) — вызов
  `settings_repo.get_settings(sync_with_env=True)` (перезаписывавший БД
  значениями из `.env` при **каждом** старте бота) заменён на обычный
  `get_settings()` без синхронизации. Добавлен прогрев кэша часового пояса
  из БД через `set_local_timezone(...)`.
- `backend/app/core/timezone_utils.py` — добавлена функция
  `set_local_timezone(timezone_name)`, позволяющая явно задать активный
  часовой пояс (используется при старте из значения БД). `to_utc`/`from_utc`
  переведены на использование общего кэша `get_local_timezone()` вместо
  прямого обращения к статическому `get_settings().timezone` — раньше это
  было два независимых пути получения таймзоны (DRY-нарушение), из-за чего
  поле `SystemSettings.timezone` в БД фактически никогда не читалось нигде,
  кроме как для перезаписи из `.env`.
- `backend/app/utils/env_updater.py` — файл удалён полностью (после выноса
  вызовов из `SettingsManagementService` он больше нигде не использовался).
  Это устраняет саму причину бага, а не только последствие: класса багов
  "путь до `.env` вычислен неверно" в проекте больше не существует.
- Удалён мусорный корневой `/root/telegram-bot/.env` (не отслеживается git,
  содержал только рассинхронизированный `DEFAULT_TIME_STEP=5` — побочный
  продукт бага; реальный конфиг — `backend/.env`, как и раньше указано в
  `docker-compose.yml` → `env_file: ./backend/.env`).
- `env.example` и `docs/SETUP_GUIDE.md` обновлены: явно указано, что
  `DEFAULT_WORK_START/END`, `DEFAULT_TIME_STEP`, `DEFAULT_BUFFER_TIME`,
  `TIMEZONE` в `.env` — это только бутстрап-значения для первого запуска на
  пустой БД; после этого источник истины — база данных, изменения делаются
  через админ-панель бота.
- Регрессия: весь набор тестов (`pytest tests/` — 62 теста) проходит
  без изменений в тестах (настройки прежде не были явно покрыты тестами).

**Осталась известная граница возможностей.** У часового пояса в БД
(`SystemSettings.timezone`) по-прежнему нет админ-хендлера для изменения
через бота (только работает бутстрап + новый механизм применения на
старте) — это отдельная фича, не входившая в объём данного исправления.
Если понадобится редактировать таймзону через бота, нужно: добавить
`update_timezone` в `SettingsRepository`/`SettingsManagementService` и
вызывать `timezone_utils.set_local_timezone(...)` сразу после коммита,
по аналогии с тем, как это сейчас делается при старте.

---

### 0.2 Перенос времени брони: собственный слот всегда "занят" — ✅ ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `time_service.py:228-290`, метод `is_slot_available(...,
exclude_booking_id=...)`. Параметр `exclude_booking_id` передаётся в
`is_slot_available`, но **не** передаётся дальше в
`calculate_available_slots(target_date, service_duration)` (строка 252) — а
сам `calculate_available_slots` (`time_service.py:129`) вообще не принимает
такой параметр в сигнатуре. Комментарий в коде ("since we're excluding one,
the slot should be available", строки 285-286) не соответствует
действительности — исключения не происходит нигде.

Вызывается из `booking_service.py:300` (`propose_new_time`, мастер) и `:357`
(`propose_new_time_by_user`, клиент) именно с расчётом на то, что параметр
работает.

**Симптом.** Мастер или клиент пытается немного сдвинуть уже существующую
запись (например, на 15 минут) — новый слот пересекается с текущим
(собственным же) занятым интервалом брони, поэтому `is_slot_available`
возвращает `False`, и перенос ошибочно отклоняется как "слот недоступен".

**План исправления.**
1. Провести `exclude_booking_id` до места, где `calculate_available_slots`
   реально фильтрует занятые интервалы (нужно посмотреть на реализацию —
   вероятно, там идёт выборка бронирований на дату через `booking_repo`;
   добавить фильтр `Booking.id != exclude_booking_id` в запрос или в
   постфильтрацию результата).
2. Добавить параметр `exclude_booking_id: Optional[int] = None` в сигнатуру
   `calculate_available_slots` и прокинуть его из `is_slot_available`.
3. Убрать вводящий в заблуждение комментарий, заменить на реальное описание
   поведения.

**DoD.** Юнит-тест: создать брони A (10:00-10:30) и B (10:30-11:00) в один
день; вызвать `is_slot_available(10:15, duration=30, exclude_booking_id=A.id)`
→ `True` (раньше было `False`); без `exclude_booking_id` — по-прежнему
`False`.

**Как исправлено фактически.**
- `backend/app/services/time_service.py` — `calculate_available_slots` теперь
  принимает `exclude_booking_id: Optional[int] = None` и пропускает бронь с
  этим id при построении списка занятых интервалов.
- `is_slot_available` прокидывает `exclude_booking_id` в
  `calculate_available_slots` вместо того, чтобы просто проверять
  флаг-заглушку в конце. Убран вводящий в заблуждение
  комментарий/мёртвая ветка кода.
- Тесты: `backend/tests/test_time_service.py` (3 новых теста) —
  собственный слот брони недоступен без `exclude_booking_id`, доступен с
  ним, и исключение одной брони не открывает слот другой. Полный набор:
  65/65 тестов проходит.

---

### 0.3 Нет проверки роли ADMIN в админ-хендлерах — ✅ ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `AuthMiddleware` (`middlewares/auth.py`) проверяет только
`auth_service.is_authorized(user.id)` — а это (`auth_service.py:97-115`)
означает "есть **любая** роль" (admin/mechanic/user), не конкретно admin.
Метод `has_permission(telegram_id, UserRole.ADMIN)`
(`auth_service.py:117-...`) существует и используется в самом
`auth_service.py` (строки 176, 213), но **ни разу** не вызывается ни в одном
файле `backend/app/bot/handlers/admin/*.py` (проверено — 0 вхождений).
Единственная защита — то, что кнопки админки не показываются в клавиатуре
не-админам. Сам callback (`admin:add_user`, `admin:manage_users`,
`admin:remove_mechanic` и т.д.) технически может быть вызван любым
авторизованным пользователем (даже с ролью `USER`), если он сформирует
соответствующий `callback_data` (это тривиально в Telegram-клиентах с
кастомным UI/ботами-прокси).

**План исправления.**
1. Добавить в `AuthMiddleware` (или в отдельный `AdminAuthMiddleware`,
   регистрируемый только на `admin`-роутеры) явную проверку
   `has_permission(user.id, UserRole.ADMIN)` для всех апдейтов, чей
   `callback_data`/router принадлежит `admin/*`.
   Технически проще всего: зарегистрировать `admin_router` как единый
   родительский `Router`, объединяющий все admin-подроутеры
   (`admin/users.py`, `admin/mechanics.py`, `admin/services.py`,
   `admin/settings.py`), и навесить middleware именно на него — тогда
   проверка будет в одном месте (Facade/единая точка входа, а не
   размазана по хендлерам).
2. При провале проверки — тот же UX, что и при `is_authorized == False`
   (сообщение + `callback.answer()`), чтобы не различать для атакующего
   "неавторизован" и "не хватает прав".
3. Покрыть тестом: пользователь с ролью `USER`/`MECHANIC` дергает
   `admin:add_user` → хендлер не выполняется, роль не меняется.

**DoD.** Тест: не-админ вызывает любой admin-callback → получает отказ,
никакие данные не меняются. Админ — работает как раньше.

**Как исправлено фактически.** Реализован именно вариант из плана (единая
точка на роутере, Facade-подход):
- Новый `backend/app/bot/middlewares/admin_auth.py` — `AdminAuthMiddleware`
  проверяет `data["user"].role == UserRole.ADMIN` (пользователь уже
  подгружен глобальным `AuthMiddleware` к этому моменту, повторный запрос
  к БД не нужен). При отказе — тот же текст/UX, что и у "неавторизован" в
  `AuthMiddleware` (`start.unauthorized_both`), чтобы не давать
  атакующему различить два случая.
- `backend/app/bot/handlers/admin/__init__.py` — `AdminAuthMiddleware`
  навешана на сам `admin.router` (`router.message.middleware(...)`,
  `router.callback_query.middleware(...)`) **до** `include_router` для
  `users`/`mechanics`/`services`/`settings` — благодаря дереву роутеров
  aiogram это одна точка защиты для всех admin-подроутеров разом, без
  правок в каждом хендлере.
- Тесты: `backend/tests/test_admin_auth_middleware.py` (5 тестов) —
  admin проходит, `MECHANIC`/`USER` блокируются (и для `Message`, и для
  `CallbackQuery`, с проверкой, что ответ пользователю отправляется), а
  также случай отсутствующего `user` в data. Полный набор: 70/70 тестов
  проходит.

---

### 0.4 Напоминания помечаются "отправлено" даже при неудачной доставке — ✅ ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `notification_service.py:225-236`
(`_send_simple_notification`) ловит все исключения при отправке сообщения
через Telegram API и только логирует их — не пробрасывает и не возвращает
признак неудачи. `reminder_scheduler.py:172-179` сразу после вызова
безусловно выставляет `setattr(booking, rule.sent_attr, True)` и коммитит,
независимо от того, дошло сообщение или нет.

**Симптом.** Если мастер заблокировал бота (`TelegramForbiddenError`) или
временно недоступен Telegram API — напоминание считается "отправленным"
и никогда не будет отправлено повторно, хотя мастер его не получил.

**План исправления.**
1. `_send_simple_notification` должен возвращать `bool` (успех/неудача) или
   пробрасывать специфичное исключение, различая "получатель недоступен
   навсегда" (`TelegramForbiddenError` — можно смело помечать `sent=True`,
   ретраи бессмысленны) от "временная ошибка" (сеть/лимиты — не помечать,
   чтобы следующий тик scheduler'а повторил попытку).
2. `reminder_scheduler.py` — выставлять `sent_attr = True` только при
   подтверждённой доставке или при окончательном отказе (forbidden/blocked);
   при временной ошибке оставить `False` и залогировать для последующего
   ретрая, с ограничением числа попыток, чтобы не зациклиться бесконечно.

**DoD.** Тест: мок `send_message` кидает `TelegramForbiddenError` →
`sent_attr` становится `True` (не ретраим). Мок кидает
`TelegramRetryAfter`/`TelegramNetworkError` → `sent_attr` остаётся `False`,
и в следующем тике `reminder_scheduler` попытка повторяется.

**Как исправлено фактически.**
- `backend/app/services/notification_service.py` — `_send_simple_notification`
  теперь возвращает `bool`: `True` при реальной доставке **или** при
  `TelegramForbiddenError`/`TelegramBadRequest` (получатель безвозвратно
  недоступен — ретраить бессмысленно), `False` при пропуске из-за
  rate-limit или любой другой (временной) ошибке отправки.
  `notify_mechanic_reminder` пробрасывает этот результат наружу.
- `backend/app/services/reminder_scheduler.py` — `sent_attr` выставляется
  в `True` только когда `notify_mechanic_reminder` вернул `True`; при
  `False` бронь просто пропускается в этом цикле (следующий цикл
  повторит попытку, т.к. флаг остался `False`).
- Попутно найден и исправлен смежный баг, всплывший при тестировании:
  `delta = booking.booking_date - now` падал с `TypeError: can't subtract
  offset-naive and offset-aware datetimes`, когда БД возвращает
  `booking_date` как naive datetime (это поведение SQLite/aiosqlite для
  колонок `DateTime(timezone=True)`; на проде используется PostgreSQL, где
  это не воспроизводится, но сам код не был защищён). Обёрнуто в
  `ensure_utc(...)` — ровно то же соглашение ("naive = уже UTC"), что
  используется в `timezone_utils` во всём остальном проекте.
- Тесты:
  - `backend/tests/test_notification_service.py` — добавлены
    `test_transient_send_failure_returns_false` и
    `test_forbidden_send_failure_returns_true` в
    `TestNotifyMechanicReminder`, плюс существующие тесты обновлены на
    проверку возвращаемого `bool`.
  - `backend/tests/test_reminder_scheduler.py` (новый файл, 3 теста) —
    полноценный интеграционный тест `ReminderScheduler._process_cycle`
    с реальной (in-memory) БД: успешная доставка помечает `sent=True`,
    временная ошибка оставляет `sent=False` (будет повтор), постоянная
    (`TelegramForbiddenError`) помечает `sent=True` (не ретраим).
  - Полный набор: 75/75 тестов проходит.

---

### 0.5 Нет способа отменить подтверждённую бронь через бота — ✅ ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `BookingService.cancel_booking` (`booking_service.py:428-457`)
полностью реализован, но не вызывается ни из одного хендлера — только из
тестов. `cancel_booking_callback` (`booking.py:598`) сбрасывает FSM только
для мастера **создания** брони (wizard), к уже существующей брони отношения
не имеет.

**План исправления.**
1. Добавить хендлер (в `booking.py` или отдельном `booking_cancel.py`) с
   callback вида `booking:cancel:{id}` для клиента/мастера — с подтверждением
   ("вы уверены?") перед вызовом `BookingService.cancel_booking`.
2. Добавить кнопку "Отменить" в интерфейс просмотра/деталей активной брони
   там же, где показываются кнопки accept/reject/propose (см.
   `keyboards/booking.py` или аналог).
3. Реализовать `notify_booking_cancelled` в `NotificationService` и
   `cancel_booking_and_notify` в `BookingWorkflowService` — по аналогии с
   существующими `*_and_notify` методами для create/accept/reject/propose/
   confirm (facade-паттерн, чтобы cancel не выпадал из общего workflow-слоя).
4. Проверить права: отменить бронь должен уметь либо создатель, либо
   назначенный мастер, либо админ — не произвольный пользователь.

**DoD.** Клиент видит кнопку "Отменить" у своей активной брони, отмена меняет
статус на `CANCELLED`, отправляет уведомление второй стороне.

**Как исправлено фактически** (пункт 2.2 сделан вместе, как и рекомендовал
план):
- `backend/app/services/booking_service.py` — `cancel_booking` переписан:
  теперь возвращает `Tuple[Optional[Booking], str]` (как остальные методы
  workflow, а не отдельный `Tuple[bool, str]`), разрешает отмену создателю,
  **назначенному мастеру** или **админу** (`UserRole.ADMIN`), и проверяет
  `CANCELLABLE_STATUSES` (`PENDING`/`NEGOTIATING`/`ACCEPTED`) — нельзя
  повторно отменить уже `CANCELLED`/`REJECTED`/`COMPLETED` бронь.
- `backend/app/services/notification_service.py` — добавлен
  `notify_booking_cancelled(booking, actor)`: уведомляет ту сторону,
  которая не является инициатором отмены (создателя — если отменил мастер
  или админ; мастера — если отменил создатель или админ, и мастер уже был
  назначен).
- `backend/app/services/booking_workflow_service.py` — добавлен
  `cancel_booking_and_notify`, по образцу существующих `*_and_notify`,
  закрывает пробел из п. 2.2 (facade теперь покрывает все 5 переходов
  статуса, включая cancel).
- `backend/app/bot/handlers/booking.py` — новые хендлеры
  `booking:cancel_ask:{id}` (экран подтверждения с деталями брони и
  кнопками Да/Нет) и `booking:cancel_do:{id}` (выполняет отмену через
  facade). Кнопка "❌ Отменить {дата} {время}" добавлена в список
  `menu:my_bookings` (создатель) для каждой брони в отменяемом статусе.
- `backend/app/bot/handlers/mechanic.py` — та же кнопка добавлена в
  `mechanic:my_bookings_day:*` (список подтверждённых броней мастера на
  день) — переиспользует те же `booking:cancel_ask:`/`booking:cancel_do:`
  хендлеры (permission-проверка всё равно происходит в сервисном слое).
- Новые i18n-ключи (`ru`/`pl`): `booking.actions.cancel_booking`,
  `booking.cancel.confirm_prompt`, `booking.cancel.success`,
  `booking.cancel.error`, `booking.notification.cancelled`. Каталоги
  перекомпилированы (`pybabel compile -d locales`).
- Тесты: `test_booking_service.py::TestCancelBooking` расширен (мастер
  может отменить назначенную бронь, админ может отменить любую, повторная
  отмена отклоняется), `test_booking_workflow_service.py::TestCancelBookingAndNotify`
  (3 новых теста: отмена создателем уведомляет мастера, отмена мастером
  уведомляет создателя, посторонний не может отменить). Полный набор:
  81/81 тестов проходит.

---

## Этап 1 (P1): Логические несоответствия

### 1.1 `propose_new_time` / `propose_new_time_by_user` без проверки статуса брони — ✅ ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `booking_service.py:269-374`. У `accept_booking`/
`reject_booking` есть проверка `status != PENDING`, у
`confirm_proposed_time` — `status != NEGOTIATING`. У обоих методов
"предложить новое время" такой проверки нет вообще, а вызывающий хендлер
(`booking.py:182-223`) проверяет только роль/владение брони, не её статус.

**Симптом.** Повторный клик по устаревшей/закэшированной кнопке "изменить
время" на уже `CANCELLED`/`REJECTED` записи молча переводит её обратно в
`NEGOTIATING` с новым предложенным временем — "воскрешение" мёртвой брони.

**Исправление.** Добавить в оба метода guard: разрешить `propose_new_time`
только для `PENDING`/`NEGOTIATING`/`ACCEPTED` (в зависимости от бизнес-правил
— уточнить, из каких статусов вообще можно предлагать новое время), для
остальных — возвращать `(None, "Booking is not in a valid state")`.

**DoD.** Тест: вызов `propose_new_time` на брони со статусом `CANCELLED` →
ошибка, статус не меняется.

**Как исправлено фактически.**
- `backend/app/services/booking_service.py` — константа
  `CANCELLABLE_STATUSES` (введённая в п. 0.5) переименована в
  `ACTIVE_STATUSES` и поднята в начало класса — теперь она означает
  "бронь ещё открыта" (можно и отменить, и предложить новое время), а не
  только "можно отменить". Guard `if booking.status not in
  self.ACTIVE_STATUSES: return None, "..."` добавлен в начало и
  `propose_new_time`, и `propose_new_time_by_user`, сразу после проверки
  прав, до проверки доступности слота.
- `backend/app/bot/handlers/booking.py` — обновлена ссылка на
  переименованную константу (`BookingService.ACTIVE_STATUSES`).
- Тесты: `test_booking_service.py::TestTimeNegotiation` — 2 новых теста:
  мастер не может предложить время на уже `CANCELLED` брони, создатель не
  может предложить время на уже `REJECTED` брони; в обоих случаях статус
  брони остаётся неизменным (не "воскресает" в `NEGOTIATING`). Полный
  набор: 83/83 тестов проходит.

---

### 1.2 Дублирование логики: перенос времени клиентом идёт мимо репозитория — ✅ ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `propose_new_time_by_user` (`booking_service.py:366-369`)
меняет `booking.proposed_date` / `booking.status` напрямую через ORM-объект.
Параллельный метод для мастера (`propose_new_time`) идёт через
`booking_repo.propose_new_time(...)` (`repositories/booking.py:316-340`),
который **дополнительно** проставляет `mechanic_id`. Одна и та же операция
("предложить новое время") реализована двумя разными путями — классическое
нарушение DRY, которое уже привело к расхождению в побочных эффектах.

**Исправление.** Свести оба пути к одному вызову
`booking_repo.propose_new_time(...)` с параметром, различающим
инициатора (клиент/мастер), либо явно разделить репозиторный метод на
`propose_new_time_by_mechanic` / `propose_new_time_by_user`, но с общим
приватным ядром — лишь бы не было прямой мутации ORM-полей в обход
репозитория в одном из путей.

**DoD.** Оба метода сервиса проходят через репозиторий; поведение
(проставление `mechanic_id` и т.п.) явно задокументировано и одинаково
предсказуемо для обоих сценариев.

**Как исправлено фактически.**
- `backend/app/repositories/booking.py` — `propose_new_time(booking_id,
  proposed_date, mechanic_id)`: параметр `mechanic_id` стал
  `Optional[int] = None`. Если передан — назначает/переназначает мастера
  (путь мастера); если `None` — оставляет `mechanic_id` как есть (путь
  клиента). Один метод, одно место обновления `proposed_date`/`status`
  для обоих сценариев.
- `backend/app/services/booking_service.py` —
  `propose_new_time_by_user` больше не мутирует `booking.proposed_date`/
  `booking.status` напрямую через ORM, а вызывает
  `self.booking_repo.propose_new_time(booking_id, new_datetime_local)`
  (без `mechanic_id`) — тот же путь, что и у `propose_new_time` (мастер).
- Тест: `test_booking_service.py::test_creator_proposal_does_not_change_assigned_mechanic`
  — закрепляет, что после объединения путей предложение времени
  клиентом по-прежнему **не** переназначает `mechanic_id` уже
  назначенного мастера. Полный набор: 84/84 тестов проходит.

---

### 1.3 Статус брони отображается двумя несогласованными способами — ✅ ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `booking.py:658-663` — локальный словарь emoji по статусу.
`calendar.py:106-107` — рендер через i18n-ключи. Два места, которые обязаны
показывать одно и то же, эволюционируют независимо (например, добавление
нового статуса брони требует править оба места, и легко забыть одно).

**Исправление.** Вынести единую функцию `format_booking_status(status,
language) -> str` (i18n + emoji) в `bot/ui/` или `utils/`, используемую
везде, где статус брони показывается пользователю.

**DoD.** `grep -rn "BookingStatus\." backend/app/bot` не находит ad-hoc
словарей/if-веток форматирования статуса вне единой функции.

**Как исправлено фактически.**
- `backend/app/utils/booking_utils.py` — добавлены `get_booking_status_emoji(status)`
  и `format_booking_status(status, translate, with_emoji=True)`. Единая
  карта эмодзи (`_STATUS_EMOJI`) впервые покрывает **все** статусы,
  включая `NEGOTIATING` — в старом словаре в `booking.py` его не было
  вообще (тихо падал на "❓"). Текст берётся из тех же ключей
  `calendar.status.*`, что и раньше.
- `backend/app/bot/handlers/booking.py` (`show_my_bookings`) — локальный
  `status_emoji`-словарь удалён, заменён на
  `format_booking_status(booking.status, _)`.
- `backend/app/bot/handlers/calendar.py` — рендер статуса заменён на
  `format_booking_status(booking.status, _, with_emoji=False)` —
  `with_emoji=False`, потому что шаблон `calendar.entry` уже сам ставит
  иконку "⚙️" перед статусом, и добавлять вторую эмодзи было бы избыточно.
- Проверено: `grep -rn "BookingStatus\." backend/app/bot` теперь находит
  только сравнения статуса (`== BookingStatus.ACCEPTED` для фильтрации),
  ни одного ad-hoc словаря/маппинга для отображения.
- Тесты: `backend/tests/test_booking_utils_status.py` (новый файл,
  9 тестов, включая параметризованную проверку по всем значениям enum,
  что у каждого статуса есть реальная эмодзи, а не заглушка "❓").
  Полный набор: 93/93 тестов проходит.

---

### 1.4 `AuthMiddleware` — небезопасный доступ к `event.message` — ✅ ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `middlewares/auth.py:61`:
```python
elif isinstance(event, CallbackQuery):
    await event.message.answer(message_text)
```
Без проверки на `None`/`InaccessibleMessage`, в отличие от остального кода
проекта, который везде оборачивает такие обращения в `isinstance(...,
TelegramMessage)` guard (см. `safe_callback_answer` и его использования).

**Исправление.** Добавить проверку по аналогии с остальным кодом; при
недоступном сообщении — просто `event.answer(message_text, show_alert=True)`
без попытки отправить в чат.

**DoD.** Не падает `AttributeError` при `CallbackQuery.message is None`
(старое/недоступное сообщение).

**Как исправлено фактически** (уточнение относительно исходного плана,
найденное при написании теста): `CallbackQuery.message` типизирован как
`Optional[Message | InaccessibleMessage]`. Проверка на `isinstance(...,
Message)` (по аналогии с `edit_or_ignore`) оказалась **избыточно строгой**
— `InaccessibleMessage.answer()` на самом деле работает (использует только
`chat.id`, в отличие от `.edit_text()`, которого у него нет). Настоящий
краш-сценарий — именно `event.message is None` (например, callback от
инлайн-режима без реального сообщения в чате).
- `backend/app/bot/middlewares/auth.py` — guard сделан как `if
  event.message is not None:` вместо `isinstance(..., Message)`, чтобы не
  терять уведомление для `InaccessibleMessage` (это отличие от паттерна
  `edit_or_ignore`, где `isinstance(..., Message)` обоснован — там нужен
  именно `.edit_text()`, которого нет у `InaccessibleMessage`).
- Тесты: `backend/tests/test_auth_middleware.py` (новый файл, 3 теста) —
  `InaccessibleMessage` по-прежнему получает ответ, `None` — не вызывает
  `AttributeError` и просто пропускается, обычный `Message` работает как
  раньше. Полный набор: 96/96 тестов проходит.

---

## Этап 2 (P2): SOLID / DRY / Facade — архитектурные улучшения

### 2.1 DIP: сервисы жёстко создают свои репозитории — ✅ ЧАСТИЧНО ИСПРАВЛЕНО (2026-07-23)

**Проблема.** `BookingService.__init__` (`booking_service.py:33-36`) и
аналогично `AuthService`, `TimeService`, `ServiceManagementService`,
`SettingsManagementService` — все сами делают `XRepository(session)` внутри
конструктора, а не получают репозиторий как зависимость. Высокоуровневый
модуль (сервис) напрямую зависит от конкретной низкоуровневой реализации,
юнит-тест без реальной/фейковой `AsyncSession` невозможен.

**Исправление (постепенное, не обязательно за один PR).**
1. Завести протоколы (`typing.Protocol`) для репозиториев, которые
   реально нужны сервисам (не абстрагировать всё подряд — только там, где
   это даёт тестируемость).
2. Изменить конструкторы сервисов на приём репозиториев как параметров с
   дефолтом `None` → создавать конкретную реализацию, если не передана
   (не ломает существующие вызовы, но открывает возможность подмены в
   тестах).
3. Не делать это глобальным рефакторингом сразу — начать с
   `BookingService` и `TimeService`, поскольку в них сосредоточена
   основная бизнес-логика и найденные баги (0.2, 1.1, 1.2).

**DoD.** `BookingService` можно проинстанциировать в тесте с
in-memory/фейковыми репозиториями без реальной БД.

**Как исправлено фактически** (реализован именно рекомендованный в плане
постепенный вариант — начали с `BookingService`/`TimeService`, не
трогая `AuthService`/`ServiceManagementService`/`SettingsManagementService`):
- `backend/app/services/booking_service.py` — `__init__` принимает
  `booking_repo`/`service_repo`/`user_repo`/`time_service` как
  необязательные параметры (`Optional[...] = None`); если не переданы —
  создаётся настоящая реализация от `session`, как раньше. Полностью
  обратно совместимо: все существующие вызовы `BookingService(session)`
  работают без изменений.
- `backend/app/services/time_service.py` — аналогично для
  `booking_repo`/`settings_repo`.
- Протоколы (`typing.Protocol`) из плана сознательно не заводили —
  Python duck typing и так позволяет подставить mock/fake без формального
  интерфейса; добавление `Protocol` дало бы только чуть более строгую
  проверку типов, не влияя на тестируемость, так что оставлено как
  необязательное будущее улучшение.
- Тесты: `backend/tests/test_service_dependency_injection.py` (новый файл,
  4 теста) — `BookingService`/`TimeService` инстанциируются с
  `session=MagicMock()` (без реальной БД) и полностью фейковыми
  репозиториями, плюс тест на то, что без явной инъекции по-прежнему
  создаются настоящие `BookingRepository`/`ServiceRepository`/`UserRepository`/
  `TimeService`/`SettingsRepository` (обратная совместимость). Полный
  набор: 100/100 тестов проходит.

Помечено как "частично" — `AuthService`, `ServiceManagementService`,
`SettingsManagementService` всё ещё жёстко создают репозитории в
конструкторе; в них наименьшая концентрация бизнес-логики/багов из
найденных в аудите, так что перенос туда того же паттерна остаётся
доработкой на будущее по необходимости, а не обязательным шагом сейчас.

---

### 2.2 Facade-слой не покрывает cancel-workflow — ✅ ИСПРАВЛЕНО (2026-07-23, вместе с 0.5)

Дублирует корневую причину пункта 0.5 — при реализации отмены брони сразу
добавить её в `BookingWorkflowService` как `cancel_booking_and_notify`, чтобы
facade-паттерн (единая точка "выполнить действие + разослать уведомления")
не имел исключений для одного из пяти базовых переходов статуса.

См. подробности реализации в п. 0.5 выше — `cancel_booking_and_notify`
добавлен туда же, одним и тем же коммитом.

---

### 2.3 `ServiceManagementService`/`SettingsManagementService` — тонкие 1:1 обёртки — ✅ ЧАСТИЧНО ИСПРАВЛЕНО (2026-07-23)

**Проблема.** Сигнатуры `create_service`/`update_service` и аналогичные
дублируются практически дословно в
`service_management_service.py:44-115` и `repositories/service.py:50-126`
(и далее в вызывающем хендлере — итого 3 копии одного списка параметров).
Любое новое поле требует правки в трёх местах синхронно.

**Исправление.** Заменить длинные списки позиционных/именованных параметров
на DTO (`@dataclass` или Pydantic-модель) `ServiceCreateData`/
`ServiceUpdateData`, передаваемую целиком через слои service → repository.
Это же снижает риск перепутать порядок аргументов при рефакторинге.

**DoD.** Добавление нового поля в `Service` требует правки в одном DTO +
одном месте маппинга в repository, а не трёх сигнатур.

**Как исправлено фактически.**
- `backend/app/dto.py` (новый файл, на уровне пакета `app`, а не внутри
  `repositories/` или `services/` — обоим слоям он нужен, и ни один не
  должен зависеть от пакета другого) — `ServiceCreateData` и
  `ServiceUpdateData` (frozen dataclasses).
- `backend/app/repositories/service.py` — `create_service(data)` и
  `update_service(service_id, data)` принимают DTO вместо 6 отдельных
  параметров каждый; `update_service` проходит по `dataclasses.asdict(data)`
  и применяет только не-`None` поля (сохранена семантика partial update).
- `backend/app/services/service_management_service.py` — та же замена
  сигнатур на приём DTO. Заодно вскрылся и убран нюанс: сервис раньше
  создавал запись через **общий** `service_repo.create(...)` из
  `BaseRepository`, из-за чего специализированный
  `ServiceRepository.create_service` был мёртвым кодом (существовал, но
  никогда не вызывался). Теперь сервис вызывает именно
  `service_repo.create_service(data)` — путь создания один, а не два
  параллельных.
- `backend/app/bot/handlers/admin/services.py` — вызов `create_service`
  оборачивает данные в `ServiceCreateData(...)` (3-я копия списка
  параметров, которую убирали по плану).
- `SettingsManagementService` **не тронут** — его методы
  (`update_work_hours`/`update_time_step`/`update_buffer_time`) принимают
  по 1-2 параметра каждый, а не 6; реальная описанная в плане проблема
  (`service_management_service.py:44-115` + `repositories/service.py:50-126`)
  касалась именно `Service`. Заводить DTO ради 1-2 параметров добавило бы
  косвенность без пользы.
- Тесты: `backend/tests/test_service_management_dto.py` (новый файл,
  5 тестов) — создание со всеми полями и только обязательными, partial
  update не трогает незаданные поля, обновление несуществующей записи
  возвращает `None`, прямой вызов `ServiceRepository.create_service` с
  DTO. Полный набор: 105/105 тестов проходит.

---

### 2.4 Мелкие точечные проблемы (низкий риск, быстро чинится)

| # | Файл:строка | Проблема | Фикс |
|---|---|---|---|
| 2.4.1 | `repositories/settings.py` | ~~`if time_step_minutes:` / `if buffer_time_minutes:` — truthy-проверка, значение `0` считается "не передано"~~ | ✅ Исправлено 2026-07-23 вместе с 0.1 — заменено на `is not None` |
| 2.4.2 | `models/service.py:32` | ~~`price: Mapped[Optional[float]]`, но колонка `Numeric(10,2)` — SQLAlchemy вернёт `Decimal`, не `float`~~ | ✅ Исправлено 2026-07-23 — тип аннотации приведён к `Optional[Decimal]` (и в новых DTO `ServiceCreateData`/`ServiceUpdateData`). Проверено: `.price` нигде в `backend/app` не используется в арифметике/форматировании — риска регрессии не было |
| 2.4.3 | `config/database.py:38` | ~~Для SQLite не включён `PRAGMA foreign_keys=ON`~~ | ✅ Исправлено 2026-07-23 — добавлен event listener на `connect` (вынесен в переиспользуемую `enable_sqlite_foreign_keys()`), `ondelete=CASCADE/RESTRICT/SET NULL` теперь реально работает и под SQLite |
| 2.4.4 | `utils/booking_utils.py:43` | ~~Предполагает, что `booking.service` уже загружен (eager), полагается на то, что каждый вызывающий код не забудет `selectinload`~~ | ✅ Исправлено 2026-07-23 — `lazy="selectin"` добавлен в relationship `Booking.service`, теперь это дефолт, а не то, что нужно помнить в каждом query-методе |
| 2.4.5 | разные админ-хендлеры | `callback.answer()` используется напрямую вместо общего `safe_callback_answer()` (`admin/services.py`, `admin/settings.py`, `user_settings.py`, `calendar.py`, `start.py:78`) | Заменить на `safe_callback_answer()` везде — иначе общий хелпер теряет смысл |
| 2.4.6 | `admin/settings.py` (work-hours/time-step/buffer handlers) | `except ValueError` — не-ValueError исключение (например, ошибка БД) оставляет FSM в состоянии ожидания ввода "навсегда" | Обернуть в общий `except Exception`, сбрасывать состояние и логировать |
| 2.4.7 | `user_settings.py:50` | Захардкожена двуязычная PL/RU строка вместо i18n | Вынести в каталоги переводов как остальные строки |
| 2.4.8 | `admin/services.py:248` | При ошибке `create_service` — тишина, состояние просто сбрасывается | Показать пользователю сообщение об ошибке, как в симметричных user/mechanic-флоу |

---

## Порядок выполнения (рекомендация)

1. **Спринт 1 (P0, 0.1–0.5)** — критичные баги, каждый — отдельный PR с
   тестом, воспроизводящим баг до фикса. Это можно делать параллельно,
   пункты друг от друга не зависят.
2. **Спринт 2 (P1, 1.1–1.4)** — логические несоответствия, тоже
   независимы друг от друга.
3. **Спринт 3 (P2, 2.1–2.4)** — архитектурные улучшения; 2.2 делать вместе
   с 0.5 (одна и та же зона кода). 2.1 и 2.3 — по возможности, не блокируют
   ничего остального.

## Как проверять после каждого этапа

- Юнит-тесты на конкретный фикс (см. DoD в каждом пункте).
- Ручная проверка через запущенный контейнер `telegram-bot-bot-1`
  (`docker logs -f telegram-bot-bot-1`) — убедиться, что бот стартует без
  ошибок и обрабатывает апдейты после каждого мержа.
- Регрессионный прогон существующего набора тестов в `backend/tests/`.
