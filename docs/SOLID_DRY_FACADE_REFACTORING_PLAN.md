> **Статус выполнения** ведётся прямо в этом файле — у каждого пункта в
> заголовке проставляется `[ ]` / `[x]`, а после раздела "Шаги" добавляется
> блок "Результат" с датой и кратким описанием сделанного. Обновляется по
> ходу рефакторинга, начиная с 2026-07-21.

# План рефакторинга: SOLID / DRY / Facade

Документ описывает пошаговый план устранения проблем, найденных при аудите
проекта на соответствие SOLID, DRY и паттерну Facade (см. переписку/аудит от
2026-07-21). В отличие от более ранних `SOLID_ANALYSIS.md` / `REFACTORING_PLAN.md`
в корне репозитория (которые описывают уже выполненную работу), этот документ
фиксирует **текущее фактическое состояние кода** и план по каждой находке.

Все пути — относительно `backend/`, если не указано иное.

## Как читать этот план

Каждый пункт оформлен как самостоятельная задача:

- **Проблема** — что не так и почему это важно.
- **Где** — конкретные файлы и строки.
- **Решение** — целевое состояние кода.
- **Шаги** — пошаговая последовательность действий.
- **Проверка** — как убедиться, что рефакторинг не сломал поведение.
- **Приоритет / Эффект** — P0 (сначала) → P2 (можно отложить), и ожидаемый эффект.

## Предварительный шаг: safety net (сделать один раз, до P0) — [x] Выполнено

Сейчас в `backend/tests/` нет тестов на `handlers/`, `services/`, `repositories/`
(есть только `test_metrics.py`, `test_rate_limiter.py`, `test_translation_service.py`).
Рефакторинг вслепую, без тестов — риск регрессий в самом чувствительном месте
(создание брони, уведомления). Прежде чем трогать `booking.py` и
`NotificationService`, добавить минимальный набор интеграционных тестов:

1. `tests/test_booking_service.py` — happy path `create_booking`, `accept_booking`,
   `reject_booking`, `propose_new_time*`, `confirm_proposed_time`, `cancel_booking`
   на in-memory/тестовой БД (см. `conftest.py`, там уже должна быть фикстура
   сессии — если нет, добавить через `aiosqlite`/тестовый Postgres).
2. `tests/test_notification_service.py` — с `Bot`, замоканным через
   `unittest.mock.AsyncMock`, проверить, что нужные тексты и клавиатуры уходят
   нужным получателям (creator/mechanic/other mechanics).
3. Ручной regression-чеклист (т.к. e2e-тестов бота нет): полный сценарий
   "создать бронь → принять → отклонить → предложить новое время → подтвердить"
   через реального бота в тестовом чате — прогонять после каждой фазы ниже.

Без этого шага — риски по пунктам 1.2, 2.1, 2.5, 3.2 ниже становятся высокими;
двигаться дальше на свой страх и риск можно только по низкорисковым пунктам
(2.2, 2.6, 3.1 частично).

**Результат (2026-07-21).** Добавлены `tests/test_booking_service.py` (17
тестов на `BookingService`: создание/двойное бронирование, accept/reject,
propose/confirm negotiation, cancel) и `tests/test_notification_service.py`
(11 тестов на `NotificationService` с замоканным `Bot`). По пути найдены и
исправлены два независимых бага в тестовой инфраструктуре, из-за которых эти
фикстуры были фактически неработоспособны и никогда не запускались:
- `tests/conftest.py`: фикстура `db_session` создавала SQLAlchemy engine с
  `NullPool` поверх `sqlite+aiosqlite:///:memory:` — с этим пулом каждое
  новое соединение открывает **новую** пустую in-memory БД, поэтому после
  создания таблиц следующий `session.execute(...)` падал с
  `no such table: users`. Заменено на `StaticPool` +
  `connect_args={"check_same_thread": False}`, чтобы все сессии в тесте
  использовали одно и то же соединение/БД.
- Добавлен `backend/pytest.ini` (`asyncio_mode = auto`,
  `asyncio_default_fixture_loop_scope = function`) — до этого в репозитории
  не было конфигурации pytest-asyncio вообще, а async-фикстуры в
  `conftest.py` были объявлены как обычные `@pytest.fixture` (для strict
  mode pytest-asyncio они должны быть `@pytest_asyncio.fixture`). Явно
  заданный `asyncio_mode = auto` снимает эту проблему без правки самих
  фикстур.
- Обнаружен и обойдён process-wide singleton `get_notification_rate_limiter()`:
  тесты, использующие один и тот же `telegram_id` мехника (2002) в разных
  функциях, попадали под реальный 60-секундный rate limit друг друга. Добавлен
  autouse-фикстур `reset_notification_rate_limiter` с `limiter.reset()`
  до/после каждого теста.

Полный прогон: `36 passed` (`python -m pytest tests/ -q` из `backend/`).

---

## Часть 1. SOLID

### 1.1 DIP — `NotificationService` зависит от presentation-слоя — [x] Выполнено

**Проблема.** Сервисный слой (`app/services/notification_service.py`) импортирует
и вызывает функции из `app/bot/handlers/common.py` — модуля хендлеров. Зависимость
идёт "снизу вверх" (business logic → UI), что ломает слоистую архитектуру и
делает `NotificationService` непереиспользуемым вне aiogram-хендлеров (например,
из будущего REST API или админ-скрипта).

**Где.**
- `app/services/notification_service.py:72` — `from app.bot.handlers.common import schedule_main_menu_return`
- `app/services/notification_service.py:77-78` — `from app.bot.handlers.common import _build_menu_payload`
- `app/services/notification_service.py:81` — `from app.core.deferred_message_manager import get_deferred_message_manager` (само по себе ок, но используется здесь ради UI-логики, а не уведомлений)

**Решение.** Вынести построение меню и "menu payload" в отдельный модуль,
не зависящий от `services/`, и сделать `handlers/common.py` его тонкой обёрткой
(либо вовсе удалить `handlers/common.py` как отдельный слой для этой логики).

Целевая структура:
```
app/bot/ui/menu.py          # чистая функция build_menu_payload(user) -> (text, keyboard)
                             # не импортирует ничего из services/
app/bot/handlers/common.py  # роутер + safe_callback_answer/send_clean_menu,
                             # использует app.bot.ui.menu
app/services/notification_service.py
                             # использует app.bot.ui.menu вместо handlers.common
```

**Шаги.**
1. Создать `app/bot/ui/__init__.py`, `app/bot/ui/menu.py`.
2. Перенести туда `_build_menu_payload` (переименовать в публичную `build_menu_payload`)
   без изменений логики.
3. Перенести `schedule_main_menu_return` в `app/bot/ui/menu.py` — она зависит
   только от `Bot`, `User`, `DeferredMessageManager`, не от хендлеров.
4. В `app/bot/handlers/common.py` заменить локальные определения на
   `from app.bot.ui.menu import build_menu_payload, schedule_main_menu_return`
   (с алиасом `_build_menu_payload = build_menu_payload` на переходный период,
   либо сразу поправить оба места использования — их немного, см. п. 3.2).
5. В `app/services/notification_service.py` заменить импорты
   `app.bot.handlers.common` → `app.bot.ui.menu`.
6. Прогнать grep, чтобы убедиться, что `services/` больше нигде не
   импортирует `app.bot.handlers.*`:
   `grep -rn "from app.bot.handlers" backend/app/services`
   (должно быть пусто).

**Проверка.** Тесты из safety-net (`test_notification_service.py`), плюс
ручной прогон "принять бронь" / "отклонить бронь" — сообщения и меню должны
формироваться так же, как раньше.

**Приоритет:** P0 — это единственное нарушение направления зависимостей в
проекте, дальше архитектуру наращивать на нём нельзя.

**Результат (2026-07-21).** Создан пакет `app/bot/ui/` (`__init__.py` с
явным комментарием-контрактом "не импортировать app.services/app.bot.handlers
отсюда", `menu.py`) — туда перенесены `build_menu_payload` (бывшая
`_build_menu_payload`) и `schedule_main_menu_return` без изменения логики.
`app/bot/handlers/common.py` теперь реэкспортирует обе функции из
`app.bot.ui.menu` (`from app.bot.ui.menu import build_menu_payload as
_build_menu_payload, schedule_main_menu_return`), поэтому все остальные
хендлеры (`mechanic.py`, `booking.py`, `admin/*.py`), импортировавшие эти
функции из `handlers.common`, не потребовали правок. `notification_service.py`
переведён на прямой импорт `from app.bot.ui.menu import build_menu_payload,
schedule_main_menu_return` на уровне модуля (были убраны 2 локальных
`from app.bot.handlers.common import ...` внутри методов). Заодно убран
неиспользуемый импорт `Bot` из `handlers/common.py`.
Проверка `grep -rn "from app.bot.handlers" backend/app/services` — пусто.
Полный прогон — `40 passed`.

---

### 1.2 SRP — «толстый» хендлер `handlers/booking.py` — [x] Выполнено (в рамках 3.2)

**Проблема.** Файл 783 строки, отдельные функции-хендлеры одновременно:
управляют FSM-переходами, обращаются к репозиторию напрямую (мимо сервиса),
оркестрируют 3–4 сервиса, форматируют текст ответа и решают, кому и что
отправить. Это затрудняет тестирование и изменение любой из этих
ответственностей по отдельности.

**Где.** Особенно показательны:
- `time_selected` (`booking.py:193-309`) — 116 строк, ветвление
  mechanic/creator/normal-flow в одной функции.
- `skip_description` / `description_entered` (см. 2.1 ниже) — дублирующаяся
  оркестрация создания брони.

**Решение.** Это следствие отсутствия фасада для сценария бронирования —
подробное решение и шаги вынесены в **3.2 (Facade: `BookingWorkflowService`)**,
чтобы не делать работу дважды. После введения фасада хендлеры в `booking.py`
станут тонкими адаптерами Telegram-событий к вызовам фасада, а `time_selected`
разобьётся на 2-3 более простых функции (см. 3.2, шаг 4).

**Приоритет:** P1, выполняется как часть 3.2.

---

### 1.3 OCP / дублирование — `BaseRepository.get_all()` vs `count()` — [x] Выполнено

**Проблема.** Оба метода реализуют одинаковый цикл применения `**filters`,
и `count()` неэффективен: тянет из БД все строки и делает `len(list(...))`
вместо `SELECT COUNT(*)`. Любое расширение фильтрации (например, добавление
операторов `>=`, `in`, `like`) потребует правки в двух местах.

**Где.** `app/repositories/base.py:41-67` (`get_all`) и `:121-139` (`count`).

**Решение.**
```python
def _apply_filters(self, query, filters: dict[str, Any]):
    for key, value in filters.items():
        if hasattr(self.model, key):
            query = query.where(getattr(self.model, key) == value)
    return query

async def get_all(self, skip: int = 0, limit: int = 100, **filters) -> List[ModelType]:
    query = self._apply_filters(select(self.model), filters)
    query = query.offset(skip).limit(limit)
    result = await self.session.execute(query)
    return list(result.scalars().all())

async def count(self, **filters) -> int:
    from sqlalchemy import func
    query = self._apply_filters(select(func.count()).select_from(self.model), filters)
    result = await self.session.execute(query)
    return result.scalar_one()
```

**Шаги.**
1. Добавить `_apply_filters` в `BaseRepository`.
2. Переписать `get_all` и `count` через него (`count` — на `func.count()`).
3. Прогнать существующие вызовы `count()` (`grep -rn "\.count(" backend/app`)
   и убедиться, что нигде не полагаются на побочные эффекты старой реализации
   (например, на предзагрузку связанных объектов — `func.count()` их не грузит,
   но раньше это и не гарантировалось).

**Проверка.** Юнит-тест на `BaseRepository`/любой конкретный репозиторий:
`count(**filter)` возвращает то же число, что и `len(await get_all(**filter))`
на тестовых данных.

**Приоритет:** P2 — изолированный, низкорисковый, но желательный фикс
производительности и OCP.

**Результат (2026-07-21).** `_apply_filters()` добавлен в `BaseRepository`
(`app/repositories/base.py`), `get_all()` и `count()` переписаны через него;
`count()` теперь делает `SELECT count() ... WHERE ...` вместо загрузки всех
строк и `len(list(...))`. Добавлен `tests/test_base_repository.py` (4 теста
через `UserRepository`): без фильтров, с одним фильтром, с несколькими
фильтрами и с неизвестным ключом фильтра — во всех случаях `count()` и
`len(get_all())` совпадают. Полный прогон — `40 passed`.

---

### 1.4 DIP — `ServiceFactory` спроектирован, но не используется — [x] Выполнено (вариант А)

**Проблема.** `DbSessionMiddleware` (`app/bot/middlewares/db.py:34-39`) кладёт
`ServiceFactory` в `data["service_factory"]` для каждого update. Однако из ~28
мест создания сервисов в хендлерах фабрика используется только в двух
(`handlers/admin/users.py:68,116`). Остальные хендлеры создают сервисы
напрямую (`BookingService(session)`, `TimeService(session)` и т.д.), что
сводит на нет цель DI: сейчас нельзя ни подменить реализацию сервиса в
тестах через фабрику, ни централизованно поменять способ конструирования
сервиса (например, добавить кэширование/логирование на уровне создания).

**Где.** Примеры прямого создания в обход фабрики:
`booking.py:46,86,100,154,165,236,435,524,668`, `mechanic.py:40,75,131`,
`admin/services.py:47,245,272,310`, и т.д. (полный список: `grep -rn "Service(session)" backend/app/bot/handlers`).

**Решение.** Принять одно из двух решений (рекомендуется вариант А):

**Вариант А (рекомендуется): убрать `ServiceFactory`, оставить прямое создание.**
Для проекта такого размера (Telegram-бот с одним процессом, без тестовых
дублей сервисов) полноценный DI-контейнер — избыточная абстракция, которая
создаёт видимость гибкости, но не используется. Раз she не используется —
явное создание `XService(session)` в хендлере проще для чтения и не вводит
в заблуждение.
1. Удалить `app/core/service_factory.py`.
2. Убрать инъекцию `service_factory` из `DbSessionMiddleware` (`db.py:34-39`).
3. В `handlers/admin/users.py:68,116` заменить `ServiceFactory(...)` на прямой
   вызов нужных сервисов (по аналогии с остальными хендлерами).
4. `grep -rn "ServiceFactory\|service_factory" backend/app` — должно быть пусто.

**Вариант Б: реально внедрить `ServiceFactory` везде.**
Если в планах — покрытие хендлеров юнит-тестами с моками сервисов, тогда
имеет смысл наоборот усилить фабрику:
1. Добавить в сигнатуру каждого хендлера параметр `service_factory: ServiceFactory`
   (аiogram уже прокидывает его из `data`).
2. Заменить все прямые инстанцирования на `service_factory.get_*_service()`.
3. В тестах подменять `ServiceFactory` тестовым дублем.

**Решение по умолчанию для этого плана — Вариант А**, т.к. пока нет тестов,
которым нужна была бы подмена сервисов, а лишняя неиспользуемая инфраструктура
сама по себе является источником путаницы (что и показал аудит).

**Приоритет:** P1 — не блокирует остальное, но стоит решить до того, как
кто-то начнёт "доиспользовать" фабрику в новых хендлерах и закрепит
непоследовательность.

**Результат (2026-07-21).** Реализован Вариант А. Удалён
`app/core/service_factory.py`. Из `DbSessionMiddleware`
(`app/bot/middlewares/db.py`) убрана инъекция `data["service_factory"]` и
неиспользуемый импорт `Bot`. В `app/bot/handlers/admin/users.py`
(единственные 2 реальных вызова) `ServiceFactory(session, message.bot).get_auth_service()`
заменён на прямой `AuthService(session)`. `tests/conftest.py` тоже
использовал `ServiceFactory` в фикстуре `service_factory`, которую не
использовал ни один тест — фикстура и импорт удалены. Проверка
`grep -rn "ServiceFactory\|service_factory" backend/app backend/tests` —
пусто. Полный прогон — `40 passed`.

---

## Часть 2. DRY

### 2.1 Дублирование `skip_description` / `description_entered` — [x] Выполнено (в рамках 3.2)

**Проблема.** Две функции-хендлера в `booking.py` (405-497 и 499-585, ~90
строк) почти побитово идентичны — включая отладочный код с `structlog`,
который забыли убрать после дебага. Отличие только в источнике события
(`callback.message` vs `message`) и способе ответа (`edit_text` vs `answer`).
Любое изменение логики создания брони нужно вносить в двух местах, и уже
видно, что это забывали делать синхронно (отладочные логи остались в обеих
копиях).

**Где.** `app/bot/handlers/booking.py:405-497` (`skip_description`),
`:499-585` (`description_entered`).

**Решение.** Выделить общую функцию `_finalize_booking_creation`, принимающую
абстрактный "responder" (объект с методами `reply(text)` / `edit(text)`),
либо просто `Callable[[str], Awaitable]` для отправки текста плюс исходный
`Message`-объект для ответа. Проще всего — общая async-функция, принимающая
явные параметры вместо `callback`/`message`:

```python
async def _create_booking_and_notify(
    *,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    description: str,
    bot: Bot | None,
    answer: Callable[[str], Awaitable[TelegramMessage]],
    edit_or_answer: Callable[[str], Awaitable[Any]],
    show_translating: Callable[[], Awaitable[TelegramMessage]],
    _: Callable[[str], str],
) -> None:
    """Общая логика создания брони после ввода/пропуска описания."""
    data = await state.get_data()
    service_id = data.get("service_id")
    if not service_id:
        await edit_or_answer(_("errors.unknown"))
        await state.clear()
        return

    trans_msg = await show_translating()

    booking_service = BookingService(session)
    booking_datetime = ensure_local(datetime.fromisoformat(data["booking_time"]))
    booking_language = get_user_language(user)

    booking, msg = await booking_service.create_booking(
        creator_telegram_id=user.telegram_id,
        service_id=service_id,
        car_brand=data["car_brand"],
        car_model=data["car_model"],
        car_number=data["car_number"],
        client_name=data["client_name"],
        client_phone=data["client_phone"],
        description=description,
        language=booking_language,
        booking_datetime=booking_datetime,
    )
    await trans_msg.delete()

    if booking:
        language = get_user_language(user)
        details = format_booking_details(booking, language, _)
        await answer(details)
        await answer(_("booking.confirm.success"))
        if bot:
            notification_service = NotificationService(session, bot)
            await notification_service.notify_mechanics_new_booking(booking)
    else:
        await edit_or_answer(_("booking.confirm.error") + f"\n{msg}")

    await state.clear()
```

Учитывая п. 3.2 (введение `BookingWorkflowService`), эта общая функция в
итоге сведётся к одному вызову `booking_workflow.create_and_notify(...)` —
поэтому это можно сделать сразу как часть 3.2, а не отдельным шагом (см. ниже).

**Шаги (если делать до 3.2, отдельно).**
1. Добавить `_create_booking_and_notify` в `booking.py` (или в новый
   `app/bot/handlers/_booking_helpers.py`).
2. В `skip_description` оставить только код, специфичный для callback
   (получение `description = ""`, обёртки `answer`/`edit_or_answer` через
   `callback.message`), и один вызов общей функции.
3. То же для `description_entered` через `message`.
4. Удалить отладочные `import structlog` / `log.info(...)` блоки полностью
   (они не несут продовой ценности — если нужна диагностика таймзон, завести
   `logger.debug(...)` один раз внутри `BookingService.create_booking`, где
   она уже частично есть, `services/booking_service.py:84-92,131-138`).

**Проверка.** Прогнать оба сценария (skip description / enter description)
руками + safety-net тест на `BookingService.create_booking`.

**Приоритет:** P0 — самое явное и рискованное дублирование (уже привело к
рассинхронизации debug-кода).

---

### 2.2 Повторяющийся `isinstance(callback.message, TelegramMessage)` (40 раз) — [x] Выполнено

**Проблема.** Проверка типа перед каждым `edit_text`/доступом к `chat.id`
повторяется 40 раз по хендлерам (`booking.py` — 27, `mechanic.py` — 11).
Это защитный boilerplate против того, что `callback.message` может быть
`InaccessibleMessage`, но он визуально засоряет бизнес-логику.

**Решение.** Ввести хелпер в `handlers/common.py` (или `utils/telegram_utils.py`):

```python
async def edit_or_ignore(callback: CallbackQuery, text: str, **kwargs) -> bool:
    """Edit callback.message text if it's a real Message; return False if not possible."""
    if not isinstance(callback.message, TelegramMessage):
        return False
    await callback.message.edit_text(text, **kwargs)
    return True
```

**Шаги.**
1. Добавить `edit_or_ignore` (и при необходимости `get_chat_id(callback) -> int | None`)
   в `handlers/common.py`.
2. Точечно заменять вызовы `if isinstance(callback.message, TelegramMessage): await callback.message.edit_text(...)`
   на `await edit_or_ignore(callback, ...)` — начиная с `booking.py` и `mechanic.py`,
   по одному хендлеру за коммит, чтобы диффы были маленькими и review-able.
3. Не переписывать места, где после успешной проверки нужен доступ к
   `callback.message.chat.id` для нескольких операций подряд — там `isinstance`
   как охранное условие для блока читается яснее, чем 3 вызова хелпера.

**Проверка.** Точечные ручные клики по каждому переписанному хендлеру
(поведение при "старом"/недоступном сообщении — бот не должен падать).

**Приоритет:** P2 — чисто косметический рефакторинг, делать пачками, не
блокирует остальное.

**Результат (2026-07-21).** Добавлен `edit_or_ignore(callback, text, **kwargs)`
в `handlers/common.py`. Применён в `booking.py` (18 мест мехонически +
4 места, где перед вызовом строился текст/клавиатура, вручную вынесены за
пределы `if`) и в `mechanic.py` (8 + 2 места аналогично). Не тронуты 6 мест,
подпадающих под исключение из плана: там, где `callback.message` используется
для нескольких операций подряд (`accept_booking`/`reject_booking` в
`mechanic.py` читают `callback.message.text` для построения нового текста и
одновременно проверяют `callback.bot`) или где `callback.message.chat.id`
передаётся в `schedule_main_menu_return` — в этих местах `isinstance`-проверка
осталась как есть, как и предполагалось пунктом "не переписывать" в шаге 3.
Полный прогон — `53 passed`.

---

### 2.3 Повторяющийся паттерн `get_user_language(user)` (19 раз) — [x] Выполнено

**Проблема.** Комментарий `# Get language with fallback` + вызов
`get_user_language(user)` продублирован 19 раз. Само по себе это не страшно
(однострочный вызов утилиты — нормально), но факт, что закомментировано
одинаково 19 раз, говорит о copy-paste без переиспользования на уровне выше.

**Решение.** Не вводить новую абстракцию ради одной строки — вместо этого
сократить количество мест, где это вообще нужно, за счёт следующего шага:
там, где `language` используется только чтобы построить `_()`-замыкание
(`def _(key, **kwargs): return get_text(key, language, **kwargs)`), эта
пара уже приходит из `I18nMiddleware` как `data["_"]` и `data["language"]`
(`bot/middlewares/i18n.py:52-53`) — значит, во многих местах повторный вызов
`get_user_language(user)` просто дублирует то, что мидлварь уже вычислила.

**Шаги.**
1. Добавить параметр `language: str` в сигнатуры хендлеров, где он сейчас
   вычисляется вручную (он уже есть в `data`, аналогично `_`).
2. Убрать локальные `language = get_user_language(user)` там, где значение
   совпадает с middleware-вычисленным (обычный случай — язык самого
   вызывающего пользователя). Оставить ручной вызов только там, где нужен
   язык **другого** пользователя (например, в `NotificationService`, где
   форматируется сообщение для получателя, а не для инициатора).
3. Пройтись по списку из грепа `grep -rn "get_user_language(user)" backend/app/bot/handlers`
   и для каждого вхождения решить: "это язык текущего пользователя из
   middleware" (удалить дублирование) или "это язык другого участника"
   (оставить как есть).

**Проверка.** Визуальная — тексты продолжают приходить на правильном языке
для соответствующих ролей (ручной прогон на PL/RU пользователях).

**Приоритет:** P2, можно делать одновременно с 2.2 небольшими PR.

**Результат (2026-07-21).** Проверены все 19 вхождений — во всех случаях
`get_user_language(user)` вычислял язык **текущего** актора (того же
пользователя, для которого `I18nMiddleware` уже положил `language` в `data`),
поэтому все 19 убраны: в `calendar.py` (2), `mechanic.py` (4),
`admin/services.py` (3), `booking.py` (7 — включая 2 внутри
`_create_booking_and_respond`, куда `language` теперь передаётся явным
параметром от `skip_description`/`description_entered`, т.к. это не
роутер-хендлер и не получает инъекцию от aiogram напрямую). Во всех
затронутых хендлерах добавлен параметр `language: str`, автоматически
подставляемый aiogram из `data["language"]`. Импорт `get_user_language`
убран из `booking.py`, `mechanic.py`, `calendar.py`, `admin/services.py` —
теперь используется только там, где он и должен быть: в
`NotificationService`, который вычисляет язык **получателя** уведомления
(не текущего актора) и потому не может полагаться на middleware. Полный
прогон — `53 passed`.

---

### 2.4 Хендлеры создают репозитории напрямую, минуя сервисный слой — [x] Выполнено

**Проблема.** `BookingRepository` инстанцируется прямо в хендлерах в 7 местах,
хотя по архитектуре хендлер должен работать только с сервисами.
Из-за этого фильтрация/сортировка бронирований (по статусу, по механику,
по дате) реализована в хендлерах, а не в `BookingService`, и там же неизбежно
дублируется (`mechanic.py:213-217` и `booking.py` делают похожую фильтрацию
по-разному).

**Где.**
- `calendar.py:11`
- `admin/mechanics.py:18` (`UserRepository`)
- `mechanic.py:114,164,209,294`
- `user_settings.py:10` (`UserRepository`)
- `booking.py:225,603,727`
- `admin/users.py:16` (`UserRepository`)

**Решение.** Добавить в `BookingService` (и, где нужно, `AuthService`)
недостающие методы верхнего уровня, которые уже инкапсулируют то, что сейчас
собирается в хендлере вручную:

```python
# services/booking_service.py
async def get_booking_with_relations(self, booking_id: int) -> Optional[Booking]:
    return await self.booking_repo.get_with_relations(booking_id)

async def get_pending_bookings_list(self) -> List[Booking]:
    return await self.booking_repo.get_by_status(BookingStatus.PENDING)

async def get_confirmed_future_bookings_by_mechanic(self, mechanic_user_id: int) -> List[Booking]:
    bookings = await self.booking_repo.get_by_mechanic(mechanic_user_id)
    confirmed = [b for b in bookings if b.status == BookingStatus.ACCEPTED]
    return filter_future_bookings(confirmed)  # переиспользуем utils/booking_utils.py
```

**Шаги.**
1. Пройти по каждому месту из списка "Где", определить, какой метод сервиса
   нужен (часть уже есть — `get_booking_details`, `get_user_bookings`,
   `get_mechanic_bookings`; часть нужно добавить, как в примере выше).
2. Добавить недостающие методы в `BookingService`/`AuthService`.
3. Заменить `from app.repositories.booking import BookingRepository; ...` в
   хендлерах на вызов соответствующего метода сервиса, убрать локальный импорт.
4. `grep -rn "from app.repositories" backend/app/bot/handlers` — после
   рефакторинга должно остаться пусто (репозитории видны только сервисам).

**Проверка.** Тесты safety-net на новых методах `BookingService` + ручной
прогон экранов "мои брони" / "брони механика по дням" / "ожидающие брони".

**Приоритет:** P1 — умеренный риск (логика фильтрации переносится, важно не
изменить порядок сортировки/условия), но большой выигрыш для дальнейшей
поддержки.

**Результат (2026-07-21).** Все 8 мест из списка "Где" переведены на вызовы
сервисов:
- `mechanic.py` (`change_booking_time`, `user_propose_time`-аналог для
  механиков через `booking:change_time:`) и `booking.py`
  (`time_selected`/time-change-ветка, `user_propose_time`) → `BookingService.get_booking_details(booking_id)`
  (метод уже существовал в `BookingService`, но не был востребован —
  подтверждает вывод аудита).
- `mechanic.py: show_pending_bookings` → `BookingService.get_pending_bookings()`
  (тоже уже существовал).
- `mechanic.py: show_mechanic_bookings`, `show_mechanic_bookings_day` →
  `BookingService.get_mechanic_bookings(user.telegram_id)` (уже существовал).
- `booking.py: show_my_bookings` → `BookingService.get_user_bookings(user.telegram_id)`
  (уже существовал).
- `calendar.py` (`show_calendar_menu`, `show_calendar_day`,
  `_get_available_calendar_dates`) → добавлен новый метод
  `BookingService.get_bookings_by_date(target_date)`, хендлер переведён на
  `BookingService` вместо `BookingRepository`.
- `admin/mechanics.py: list_mechanics` → добавлен `AuthService.get_all_mechanics()`.
- `admin/users.py: list_users` → добавлен `AuthService.get_all_users()`.
- `user_settings.py: toggle_reminder_setting` → добавлен
  `AuthService.update_reminder_settings(telegram_id, **flags)` (заодно убран
  дублирующий ручной `session.commit()` в хендлере — теперь коммитит сервис,
  как и остальные методы `AuthService`).

Итог: `grep -rn "from app.repositories" backend/app/bot/handlers` — пусто.
Добавлены тесты `tests/test_auth_service.py` (4 теста на новые методы) и
кейс `TestGetBookingsByDate` в `tests/test_booking_service.py`. Полный
прогон — `45 passed`.

---

### 2.5 Дублирующиеся шаблоны отправки уведомлений в `NotificationService` — [x] Выполнено

**Проблема.** `_send_booking_accepted_notification`, `_send_booking_rejected_notification`,
`_send_time_confirmed_notification` реализуют один и тот же скелет: получить
язык → собрать `_()` → отформатировать детали → проверить rate limiter →
`send_message` → залогировать ошибку. Различаются только ключом перевода и
набором `format()`-аргументов.

**Где.** `app/services/notification_service.py:278-343` (accepted/rejected),
`:344-377` (time_confirmed). `_send_time_change_notification` (:379-435)
похожа, но добавляет клавиатуру — оставить отдельной.

**Решение.**
```python
async def _send_simple_notification(
    self,
    recipient: User,
    text_key: str,
    **format_kwargs: Any,
) -> None:
    lang = get_user_language(recipient)
    notification = get_text(text_key, lang).format(**format_kwargs)
    try:
        if not await self.rate_limiter.is_allowed(recipient.telegram_id):
            logger.warning(f"Rate limit exceeded for {recipient.telegram_id}, skipping {text_key}")
            return
        await self.bot.send_message(recipient.telegram_id, notification)
        await self.rate_limiter.record_message(recipient.telegram_id)
    except Exception as e:
        logger.error(f"Failed to notify {recipient.telegram_id}: {e}")
```
`_send_booking_accepted_notification` и аналоги превращаются в тонкие обёртки,
которые готовят `format_kwargs` (включая `details=format_booking_details(...)`)
и вызывают `_send_simple_notification`.

**Шаги.**
1. Добавить `_send_simple_notification` в `NotificationService`.
2. Переписать `_send_booking_accepted_notification`, `_send_booking_rejected_notification`,
   `_send_time_confirmed_notification`, `_send_new_booking_notification` через неё —
   для тех, что отправляют клавиатуру (`_send_new_booking_notification`,
   `_send_time_change_notification`), либо добавить необязательный параметр
   `reply_markup` в `_send_simple_notification`, либо оставить их отдельно —
   решить по месту, не усложняя сигнатуру ради двух случаев.
3. Убедиться, что тексты логов об ошибках не потеряли контекст (какое именно
   уведомление не отправилось) — передавать `text_key` в лог.

**Проверка.** `test_notification_service.py` из safety-net должен покрыть
все публичные `notify_*` методы и проверить, что при `rate_limiter.is_allowed=False`
сообщение не уходит, а при исключении в `bot.send_message` — не падает наружу.

**Приоритет:** P1, делать после 1.1 (т.к. тот же файл) в одном заходе.

**Результат (2026-07-21).** Добавлен `_send_simple_notification(recipient,
text_key, *, reply_markup=None, error_label="notification", **format_kwargs)`
— общий шаблон "перевести → проверить rate limit → отправить → залогировать
ошибку". Через него переписаны все пять `_send_*_notification` методов
(`_send_new_booking_notification`, `_send_booking_accepted_notification`,
`_send_booking_rejected_notification`, `_send_time_confirmed_notification`,
`_send_time_change_notification`) и `notify_mechanic_reminder` — включая те
два, что передают `reply_markup` (клавиатуру), как и предполагалось в плане
(параметр `reply_markup` в общем хелпере снял необходимость держать их
отдельно). У каждого метода сохранена своя специфика формирования
`format_kwargs`/guard-условий (например, ранний `return` в
`_send_time_change_notification`, если `booking.proposed_date` не задан).
Полный набор тестов `test_notification_service.py` (уже написанный в Фазе 0
именно для этого случая) прошёл без изменений — `45 passed`, что
подтверждает: видимое поведение (кому уходит сообщение, с какой клавиатурой,
пропуск при рейт-лимите) не изменилось.

---

### 2.6 Мёртвый дублирующий код: `TimeService.format_date` / `format_time` — [x] Выполнено

**Проблема.** Статические методы-обёртки над `DateFormatter`
(`services/time_service.py:292-321`) нигде не вызываются (проверено:
`grep -rn "TimeService.format_date\|TimeService.format_time\|time_service.format_date\|time_service.format_time" backend/app`
— 0 совпадений). Везде в проекте используется `DateFormatter` напрямую.
Это забытый дубликат интерфейса, который вводит в заблуждение (два способа
сделать одно и то же).

**Решение.** Удалить оба метода.

**Шаги.**
1. Финальная проверка перед удалением: `grep -rn "\.format_date(\|\.format_time(" backend/app | grep -i time_service` — подтвердить отсутствие использования.
2. Удалить `app/services/time_service.py:292-321`.
3. Убедиться, что `DateFormatter` по-прежнему импортируется напрямую всюду,
   где нужно форматирование (уже так и есть — правок в вызывающем коде не требуется).

**Проверка.** `pytest`/типчек (`pyright`, см. `pyrightconfig.json`) — не
должно появиться новых ошибок неразрешённых импортов.

**Приоритет:** P2 — тривиально, можно сделать первым же коммитом (низкий риск,
быстрый результат).

**Результат (2026-07-21).** Оба статических метода удалены из
`app/services/time_service.py`. Повторный grep на использование —
0 совпадений вне самого файла (как и было предсказано). `import app.services.time_service`
и полный прогон тестов (`36 passed` на тот момент) — без регрессий.

---

## Часть 3. Facade

### 3.1 `ServiceFactory` — не факад, а неиспользуемый Service Locator — [x] Выполнено

См. **1.4** — решение и шаги уже описаны там (удалить либо довнедрить).
Здесь фиксируется только вывод из аудита: `ServiceFactory` не выполняет роль
фасада (не скрывает оркестрацию нескольких сервисов за одним вызовом), это
просто фабрика объектов 1:1, и её текущее использование непоследовательно.

**Приоритет:** см. 1.4 (P1).

---

### 3.2 Ввести настоящий фасад `BookingWorkflowService` для сценария бронирования — [x] Выполнено

**Проблема.** Сценарий "создать бронь", "предложить новое время",
"подтвердить время" требует согласованной работы `BookingService` +
`TimeService` + `NotificationService` + переводов — и сейчас эта оркестрация
живёт в хендлерах (`booking.py`), из-за чего:
- она продублирована (см. 2.1),
- `time_selected` — 116-строчная функция с четырьмя ветками (см. 1.2),
- при добавлении нового канала (например, админ-панели или API) всю
  оркестрацию пришлось бы копировать заново.

**Решение.** Ввести `app/services/booking_workflow_service.py` —
Facade, который прячет за собой всю последовательность операций и умеет
сам решить, кого уведомить:

```python
class BookingWorkflowService:
    """Facade over BookingService + TimeService + NotificationService
    for multi-step booking scenarios."""

    def __init__(self, session: AsyncSession, bot: Bot | None):
        self.session = session
        self.bot = bot
        self.booking_service = BookingService(session)
        self.notification_service = NotificationService(session, bot) if bot else None

    async def create_booking_and_notify(
        self, *, creator_telegram_id: int, service_id: int, language: str,
        booking_datetime: datetime, **booking_fields,
    ) -> Tuple[Optional[Booking], str]:
        booking, msg = await self.booking_service.create_booking(
            creator_telegram_id=creator_telegram_id,
            service_id=service_id,
            language=language,
            booking_datetime=booking_datetime,
            **booking_fields,
        )
        if booking and self.notification_service:
            await self.notification_service.notify_mechanics_new_booking(booking)
        return booking, msg

    async def propose_time_and_notify(
        self, *, booking_id: int, proposer_telegram_id: int, is_mechanic: bool,
        new_datetime: datetime,
    ) -> Tuple[Optional[Booking], str]:
        if is_mechanic:
            booking, msg = await self.booking_service.propose_new_time(
                booking_id, proposer_telegram_id, new_datetime)
            if booking and self.notification_service:
                proposer = await self.booking_service.user_repo.get_by_telegram_id(proposer_telegram_id)
                await self.notification_service.notify_time_change_proposed(booking, proposer)
        else:
            booking, msg = await self.booking_service.propose_new_time_by_user(
                booking_id, proposer_telegram_id, new_datetime)
            if booking and booking.mechanic and self.notification_service:
                proposer = await self.booking_service.user_repo.get_by_telegram_id(proposer_telegram_id)
                await self.notification_service.notify_user_time_change_proposed(booking, proposer)
        return booking, msg

    async def accept_and_notify(self, *, booking_id: int, mechanic_telegram_id: int) -> Tuple[Optional[Booking], str]:
        booking, msg = await self.booking_service.accept_booking(booking_id, mechanic_telegram_id)
        if booking and self.notification_service:
            mechanic = await self.booking_service.user_repo.get_by_telegram_id(mechanic_telegram_id)
            await self.notification_service.notify_booking_accepted(booking, mechanic)
        return booking, msg

    # reject_and_notify, confirm_time_and_notify — по тому же образцу
```

Хендлеры после этого сводятся к:

```python
@router.message(BookingStates.entering_description)
async def description_entered(message, session, user, _, state):
    description = message.text or ""
    data = await state.get_data()
    if not data.get("service_id"):
        await message.answer(_("errors.unknown"))
        await state.clear()
        return

    trans_msg = await message.answer(_("booking.create.translating"))
    workflow = BookingWorkflowService(session, message.bot)
    booking, msg = await workflow.create_booking_and_notify(
        creator_telegram_id=user.telegram_id,
        service_id=data["service_id"],
        car_brand=data["car_brand"], car_model=data["car_model"],
        car_number=data["car_number"], client_name=data["client_name"],
        client_phone=data["client_phone"], description=description,
        language=get_user_language(user),
        booking_datetime=ensure_local(datetime.fromisoformat(data["booking_time"])),
    )
    await trans_msg.delete()

    if booking:
        await message.answer(format_booking_details(booking, get_user_language(user), _))
        await message.answer(_("booking.confirm.success"))
    else:
        await message.answer(_("booking.confirm.error") + f"\n{msg}")
    await state.clear()
```

`skip_description` становится копией с `description = ""` и `callback.message.edit_text`/`answer`
вместо `message.answer` — уже не 90, а ~15 строк отличия, дублирование
перестаёт быть проблемой (общая часть — в фасаде).

**Шаги.**
1. Создать `app/services/booking_workflow_service.py` с методами:
   `create_booking_and_notify`, `propose_time_and_notify`, `accept_and_notify`,
   `reject_and_notify`, `confirm_time_and_notify`.
2. Написать юнит-тесты на фасад (с моком `NotificationService` — проверить,
   что при успешном создании брони уведомление отправляется, а при ошибке — нет).
3. Переписать `booking.py`: `skip_description`, `description_entered`,
   `time_selected` (ветки confirm/propose), `confirm_proposed_time`
   — заменить прямые вызовы `BookingService`+`NotificationService` на вызовы `BookingWorkflowService`.
4. Переписать `mechanic.py`: `accept_booking`, `reject_booking` — аналогично.
5. Разбить `time_selected` на 2 функции: `_handle_time_change_proposal` (текущие
   строки 223-296) и оставшуюся часть как `time_selected` (298-309) — обе
   короче и обе используют фасад из шага 1.
6. Удалить из `booking.py`/`mechanic.py` прямые импорты `NotificationService`,
   если после рефакторинга они больше нигде не используются напрямую.

**Проверка.** Полный regression-чеклист из "Предварительного шага" — все
сценарии бронирования, включая обе роли (creator/mechanic) в
propose-time-flow.

**Приоритет:** P1 — самый трудоёмкий пункт плана, но закрывает сразу три
находки аудита (1.2, 2.1, частично 2.4). Делать после 1.1 (т.к. фасад будет
использовать `NotificationService`, а тот должен быть уже "чист" от
зависимости на `handlers.common`) и после 2.4 (методы `BookingService`,
которые понадобятся фасаду, уже должны существовать).

**Результат (2026-07-21).** Создан `app/services/booking_workflow_service.py`
с методами `create_booking_and_notify`, `propose_time_and_notify`,
`confirm_time_and_notify`, `accept_and_notify`, `reject_and_notify` — каждый
оборачивает вызов `BookingService` соответствующим вызовом
`NotificationService` (или пропускает уведомление, если `bot=None`, что
пригодится для будущих неботовых вызовов, например из cron/скриптов).
Добавлены 8 тестов в `tests/test_booking_workflow_service.py`, включая
кейс "работает без бота".

На фасад переведены:
- `booking.py: skip_description` / `description_entered` — общая часть
  вынесена в `_create_booking_and_respond()` (~60 строк), сами хендлеры
  теперь ~15 строк каждый и отличаются только тем, как отвечать в Telegram
  (`edit_text` vs `answer`). Заодно из обоих полностью убран забытый
  отладочный блок с `import structlog` — предмет находки 2.1.
- `booking.py: time_selected` — ветка "изменение времени" (была 70+ строк
  внутри одной функции) вынесена в отдельную `_handle_time_change_proposal()`,
  использующую `workflow.propose_time_and_notify(is_mechanic=...)` — предмет
  находки 1.2. `time_selected` теперь занимается только маршрутизацией
  между "это флоу смены времени" и "обычное создание брони".
- `booking.py: confirm_proposed_time` → `workflow.confirm_time_and_notify(...)`.
- `mechanic.py: accept_booking`, `reject_booking` → `workflow.accept_and_notify(...)`,
  `workflow.reject_and_notify(...)`.

Ни один хендлер больше не создаёт `NotificationService` напрямую (`grep -rn
"NotificationService(" backend/app/bot/handlers` — пусто) — вся оркестрация
"изменить состояние брони → уведомить нужных людей" теперь в одном месте.
`booking.py` уменьшился с 783 до 703 строк несмотря на добавление двух новых
именованных хелперов (то есть чистое сокращение дублирования, а не просто
перенос кода).

Ограничение проверки: в этом окружении нет живого Telegram-бота/пользователя,
поэтому ручной regression-чеклist по всем сценариям (создание брони, принятие/
отклонение, предложение и подтверждение нового времени обеими сторонами) не
прогонялся вручную через реальный бот-чат — вместо этого корректность
подтверждена (а) построчным сопоставлением нового кода со старым при
переносе логики, (б) полным набором unit/integration-тестов на сервисном
уровне (`53 passed`), который покрывает те же переходы состояний и
уведомления, что видел бы пользователь. Перед реальным деплоем рекомендуется
всё же пройти ручной чеклист на тестовом боте.

---

## Рекомендуемый порядок выполнения (фазы)

```
Фаза 0 (safety net):     тесты на BookingService, NotificationService                [x]
Фаза 1 (низкий риск):    2.6 (мёртвый код) → 1.3 (BaseRepository)                     [x]
Фаза 2 (архитектурная
        развязка):        1.1 (NotificationService ↔ handlers.common)                [x]
Фаза 3 (решение по DI):   1.4 / 3.1 (ServiceFactory: удалить или довнедрить)          [x]
Фаза 4 (сервисный слой):  2.4 (репозитории → методы сервисов)                         [x]
                          2.5 (шаблоны уведомлений в NotificationService)             [x]
Фаза 5 (facade):          3.2 (BookingWorkflowService) + 2.1 (устранение              [x]
                          дублирования skip_description/description_entered
                          как следствие 3.2) + 1.2 (разбиение time_selected)
Фаза 6 (полировка):       2.2 (isinstance-хелпер), 2.3 (language boilerplate)         [x]
```

Каждая фаза — отдельная ветка/PR с прогоном regression-чеклиста перед мержем
в `main`. Фазы 2-5 трогают один и тот же файл (`booking.py`,
`notification_service.py`), поэтому их стоит делать строго последовательно,
не параллельно, чтобы избежать конфликтов слияния.

## Итоговый статус (2026-07-21)

**Все 10 пунктов плана выполнены** (P0/P1/P2). Итоги:

- Новых/изменённых production-модулей: `app/bot/ui/menu.py` (новый),
  `app/services/booking_workflow_service.py` (новый), `app/repositories/base.py`,
  `app/services/{time_service,auth_service,notification_service,booking_service}.py`,
  `app/bot/middlewares/db.py`, `app/bot/handlers/{common,booking,mechanic,calendar}.py`,
  `app/bot/handlers/admin/{users,mechanics,services}.py`,
  `app/bot/handlers/user_settings.py`; удалён `app/core/service_factory.py`.
- Тестов добавлено: `tests/test_booking_service.py`,
  `tests/test_notification_service.py`, `tests/test_base_repository.py`,
  `tests/test_auth_service.py`, `tests/test_booking_workflow_service.py` —
  53 теста, все зелёные (`python -m pytest tests/ -q` из `backend/`).
- Побочно исправлены два независимых бага тестовой инфраструктуры
  (`NullPool` на in-memory SQLite, отсутствие конфигурации pytest-asyncio) —
  без них ни один async-тест с реальной БД в проекте не мог бы работать.
- Не пройдено вручную: полный regression-чеклист через живого
  Telegram-бота (см. "Ограничение проверки" в разделе 3.2) — рекомендуется
  сделать перед деплоем в прод, особенно для сценариев с уведомлениями
  (`notify_booking_accepted`/`rejected`, смена времени обеими сторонами).
