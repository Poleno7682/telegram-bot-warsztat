# 🚀 Быстрая настройка бота

## Шаг 1: Получить Bot Token

1. Откройте Telegram
2. Найдите **@BotFather**
3. Отправьте команду: `/newbot`
4. Следуйте инструкциям:
   - Введите имя бота (например: `My Auto Service Bot`)
   - Введите username бота (должен заканчиваться на `bot`, например: `my_auto_service_bot`)
5. **Скопируйте токен** который вам даст BotFather
   - Выглядит примерно так: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

## Шаг 2: Узнать свой Telegram ID

1. Найдите в Telegram бота **@userinfobot**
2. Нажмите `/start`
3. Бот покажет ваш ID (например: `123456789`)
4. **Скопируйте этот ID**

## Шаг 3: Настроить .env файл

Откройте файл `backend/.env` (он уже создан) и замените:

```env
# Вставьте ваш токен от @BotFather
BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# Вставьте ваш Telegram ID от @userinfobot
ADMIN_IDS=123456789
```

### Пример готового .env:

```env
BOT_TOKEN=5678901234:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
ADMIN_IDS=987654321
DATABASE_URL=sqlite+aiosqlite:///./db/bot.db
```

## Шаг 4: Запустить бота

Просто запустите `run_bot.bat` снова! ✅

---

## ⚙️ Дополнительные настройки (опционально)

### Добавить механиков через .env:

```env
MECHANIC_IDS=111111111,222222222
```

### Добавить пользователей через .env:

```env
USER_IDS=333333333,444444444
```

### Изменить рабочие часы, шаг записи, буфер, часовой пояс:

Эти настройки хранятся в базе данных и меняются через бота:
**админ-панель → ⚙️ Настройки**. Изменения применяются сразу, без
перезапуска бота.

`DEFAULT_WORK_START`/`DEFAULT_WORK_END`/`DEFAULT_TIME_STEP`/
`DEFAULT_BUFFER_TIME`/`TIMEZONE` в `.env` используются только как
начальные значения при самом первом запуске на пустой базе данных
(чтобы создать первую запись настроек). После этого `.env` для них уже
не читается — редактировать `.env` на уже работающем боте бесполезно,
источник истины — база данных.

### Использовать PostgreSQL вместо SQLite:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
```

---

## ❓ Troubleshooting

### "ValidationError: BOT_TOKEN Field required"
➡️ Вы забыли указать BOT_TOKEN в `backend/.env`

### "ValidationError: ADMIN_IDS Field required"
➡️ Вы забыли указать ADMIN_IDS в `backend/.env`

### "Unauthorized"
➡️ Проверьте что BOT_TOKEN правильный

### "User not authorized"
➡️ Ваш Telegram ID должен быть в ADMIN_IDS

---

## 📝 Полный пример .env файла:

```env
# ============================================
#  Telegram Bot Configuration
# ============================================

# Токен от @BotFather (ОБЯЗАТЕЛЬНО)
BOT_TOKEN=5678901234:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw

# База данных (SQLite по умолчанию)
DATABASE_URL=sqlite+aiosqlite:///./db/bot.db

# ============================================
#  Пользователи и роли
# ============================================

# Администраторы (ОБЯЗАТЕЛЬНО)
# Получите ID от @userinfobot
ADMIN_IDS=987654321,123456789

# Механики (опционально, можно добавить через бота)
MECHANIC_IDS=111111111,222222222

# Пользователи (опционально, можно добавить через бота)
USER_IDS=333333333

# ============================================
#  Настройки сервиса
# ============================================

# Рабочие часы (формат HH:MM)
DEFAULT_WORK_START=08:00
DEFAULT_WORK_END=16:00

# Шаг времени для записи (в минутах)
DEFAULT_TIME_STEP=10

# Буферное время между записями (в минутах)
DEFAULT_BUFFER_TIME=15

# Часовой пояс
TIMEZONE=Europe/Warsaw

# Уровень логирования (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

---

## ✅ Готово!

После настройки `.env` файла:

1. Запустите `run_bot.bat`
2. Найдите вашего бота в Telegram
3. Отправьте `/start`
4. Выберите язык
5. Начните работу! 🎉

---

## 📚 Дополнительная документация:

- [QUICKSTART.md](QUICKSTART.md) - Подробное руководство
- [DEPLOYMENT.md](DEPLOYMENT.md) - Развертывание на VPS
- [README.md](README.md) - Полная документация проекта

