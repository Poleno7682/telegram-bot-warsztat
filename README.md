# Telegram Bot - Auto Service Booking System

Система записи клиентов на автосервис через Telegram Bot с поддержкой двух языков (польский/русский).

Репозиторий проекта: [github.com/Poleno7682/telegram-bot-warsztat](https://github.com/Poleno7682/telegram-bot-warsztat)

## 🏗️ Архитектура проекта

Проект следует принципам **чистой архитектуры** с четким разделением на frontend и backend:

```
Telegram-Bot-Warsztat/
├── 📱 frontend (Bot UI Layer)            # Telegram Bot интерфейс
│   └── handlers/                         # Обработчики сообщений
│   └── keyboards/                        # Клавиатуры и кнопки
│   └── states/                           # FSM состояния
│   └── middlewares/                      # Middleware слой
│
├── ⚙️ backend (Business Logic Layer)     # Бизнес-логика
│   ├── services/                         # Сервисы (SOLID)
│   ├── repositories/                     # Репозитории (Repository Pattern)
│   ├── models/                           # SQLAlchemy модели
│   └── core/                             # Ядро (i18n, config)
│
├── 🚀 Launcher Scripts
│   ├── run_bot.py                        # Python launcher
│   ├── run_bot.bat                       # Windows launcher
│   ├── run_bot.sh                        # Linux/Mac launcher
│   ├── setup_windows.bat                 # Windows setup
│   └── setup_linux.sh                    # Linux/Mac setup
│
├── 🐳 Docker
│   ├── docker-compose.yml                # bot + optional local PostgreSQL
│   ├── backend/Dockerfile
│   └── backend/docker/entrypoint.sh      # migrations + start
│
├── 🚀 Deployment (legacy, without Docker)
│   ├── deployment/
│   │   ├── systemd/                     # systemd unit files
│   │   └── logrotate/                    # logrotate configs
│
└── 📚 Documentation
    ├── README.md                         # This file
    ├── backend/README.md                 # Backend docs
    ├── docs/DOCKER.md                    # Docker deployment guide
    ├── docs/QUICKSTART.md                # Quick start guide
    └── docs/DEPLOYMENT.md                # Legacy (non-Docker) deployment guide
```

## 📋 Детальная структура

### Frontend (Telegram Bot UI – `backend/app/bot/`)

```
backend/app/bot/
├── handlers/                       # Обработчики событий (UI контроллеры)
│   ├── start.py                   # Команда /start, первичный выбор языка
│   ├── common.py                  # Главное меню, навигация, безопасные ответы на callback
│   ├── booking.py                 # Создание и изменение записей (FSM)
│   ├── mechanic.py                # Интерфейс механика, подтверждение/отклонение записей
│   ├── calendar.py                # Календарь записей для администратора/механика
│   ├── user_settings.py           # Личные настройки пользователя (язык и др.)
│   ├── health.py                  # /health для проверки живости бота
│   └── admin/                     # Админ-панели (подпакет)
│       ├── services.py            # Управление услугами
│       ├── mechanics.py           # Управление механиками
│       ├── users.py               # Управление пользователями
│       └── settings.py            # Управление системными настройками (часы работы, шаг времени и т.п.)
│
├── keyboards/                      # UI элементы (кнопки)
│   └── inline.py                  # Inline-клавиатуры (меню, выбор дат/времени, подтверждения)
│
├── states/                         # FSM состояния для диалогов
│   └── booking.py                 # Состояния процесса записи и изменения времени
│
└── middlewares/                    # Middleware слой
    ├── auth.py                    # Авторизация и инъекция User
    ├── i18n.py                    # Определение языка, загрузка переводов
    ├── db.py                      # Инжекция AsyncSession
    └── error_handler.py           # Глобальная обработка ошибок aiogram/БД
```

### Backend (Business Logic – `backend/app/`)

```
backend/app/
├── services/              # Бизнес-логика (SOLID Services)
│   ├── auth_service.py           # Авторизация и управление ролями
│   ├── booking_service.py        # Управление записями
│   ├── time_service.py           # Расчет свободного времени
│   ├── translation_service.py    # Автоматический перевод
│   └── notification_service.py   # Уведомления пользователей
│
├── repositories/          # Доступ к данным (Repository Pattern)
│   ├── base.py           # Базовый репозиторий (CRUD)
│   ├── user.py           # Работа с пользователями
│   ├── service.py        # Работа с услугами
│   ├── booking.py        # Работа с записями
│   └── settings.py       # Системные настройки
│
├── models/                # SQLAlchemy модели (Data Layer)
│   ├── user.py           # Пользователь + роли
│   ├── service.py        # Услуги автосервиса
│   ├── booking.py        # Записи + статусы
│   └── settings.py       # Системные настройки
│
├── core/                  # Ядро приложения
│   ├── i18n/             # Система многоязычности
│   │   ├── loader.py     # Загрузчик переводов и вспомогательные функции (get_text, get_text_bilingual)
│   │   └── locales/      # JSON-файлы переводов (pl.json, ru.json)
│   ├── timezone_utils.py # Утилиты работы с часовыми поясами (UTC ↔ локальное время)
│   ├── logging_config.py # Настройка структурированного логирования (structlog)
│   ├── metrics.py        # Простые in-memory метрики (счетчики/гейджи)
│   ├── rate_limiter.py   # Лимитер частоты отправки уведомлений
│   ├── deferred_message_manager.py # Отложенные сообщения и защита от дубликатов
│   └── service_factory.py# Фабрика для удобного создания сервисов в тестах и не только
│
└── config/                # Конфигурация
    ├── settings.py       # Настройки (Pydantic)
    └── database.py       # Настройка БД
```

## ✨ Ключевые особенности

### 🎯 SOLID и слоистая архитектура

#### **Single Responsibility Principle (SRP)**
- ✅ Каждый service отвечает за одну задачу
- ✅ `AuthService` - только авторизация
- ✅ `BookingService` - только бронирования
- ✅ `NotificationService` - только уведомления (исправлено!)

#### **Open/Closed Principle (OCP)**
- ✅ Легко добавить новый язык (просто JSON файл)
- ✅ Легко добавить новую роль
- ✅ Расширяемая система уведомлений

#### **Liskov Substitution Principle (LSP)**
- ✅ `BaseRepository` взаимозаменяем с конкретными репозиториями
- ✅ Все сервисы следуют единому интерфейсу

#### **Interface Segregation Principle (ISP)**
- ✅ Middleware разделены по функциям
- ✅ Репозитории имеют специфичные методы
- ✅ Нет "жирных" интерфейсов

#### **Dependency Inversion Principle (DIP)**
- ✅ Handlers зависят от сервисов (абстракций)
- ✅ Сервисы зависят от репозиториев (абстракций)
- ✅ Никто не зависит от деталей реализации

### 🌍 Многоязычность и выбор языка

- Польский и русский языки "из коробки"
- Легко добавить новые языки (достаточно добавить JSON в `backend/app/core/i18n/locales/`)
- Автоматический перевод описаний (deep-translator) при создании записи
- Поддержка "язык не выбран" (`LANGUAGE_UNSET`) и диалог выбора языка при первом входе
- Возможность смены языка через меню "Мои настройки"

### 👥 Система ролей

- **Администратор**: Управление пользователями, услугами, настройками
- **Механик**: Обработка записей, управление услугами
- **Пользователь**: Создание записей

### 📅 Умное управление временем

- Автоматический расчет свободных слотов
- Учет длительности услуги + буферное время
- Проверка пересечений
- Настраиваемый шаг времени (из настроек системы)
- Отображение только будущих слотов, учитывая текущее локальное время
- Поддержка сценария "предложить другое время" как от механика, так и от клиента

### ⏰ Часовые пояса и настройки системы

- Все расчеты делают акцент на **локальном времени сервиса** (например, Europe/Warsaw)
- Временные слоты, записи и предложения времени хранятся в локальном часовом поясе, чтобы "08:00" всегда означало 8 утра по местному времени
- Централизованная модель `SystemSettings` в БД (часы работы, шаг, буфер, таймзона, глубина календаря)
- Значения синхронизируются с `.env` при запуске, а изменения через админ-панель сохраняются обратно в `.env`

### 🧩 Уведомления и устойчивость бота

- Централизованный `NotificationService` с rate limiter-ом, чтобы не спамить пользователей
- Отдельные уведомления:
  - о создании, принятии, отклонении записи
  - о предложении нового времени
  - о подтверждении нового времени
- Глобальный middleware `ErrorHandlerMiddleware`:
  - перехватывает ошибки Telegram API (включая "query is too old")
  - обрабатывает сетевые и БД-ошибки
  - возвращает пользователю понятные сообщения вместо падения бота

### ✅ Тесты и метрики

- Юнит-тесты для ядра (метрики, rate limiter, i18n/переводы)
- Простая система метрик `MetricsCollector` для отслеживания базовых показателей

### 🔄 Workflow согласования

```
Пользователь создает запись
        ↓
Уведомление всем механикам
        ↓
Механик: Принять / Отклонить / Изменить время
        ↓
При изменении времени → Согласование с пользователем
        ↓
После согласования → Запись сохранена
```

## 🚀 Быстрый старт

### Windows

```batch
REM 1. Установка
setup_windows.bat

REM 2. Настройка
notepad backend\.env
REM Укажите BOT_TOKEN и ADMIN_IDS

REM 3. Запуск
run_bot.bat
```

### Linux/Mac

```bash
# 1. Установка
chmod +x setup_linux.sh run_bot.sh
./setup_linux.sh

# 2. Настройка
nano backend/.env
# Укажите BOT_TOKEN и ADMIN_IDS

# 3. Запуск
./run_bot.sh
```

### Python напрямую

```bash
# 1. Установка
cd backend
python3 -m pip install --upgrade pip --user
python3 -m pip install -r requirements.txt --user

# 2. Настройка
cp env.example .env
nano .env  # Укажите BOT_TOKEN и ADMIN_IDS

# 3. Миграции
mkdir -p db
python3 -m alembic upgrade head

# 4. Запуск
cd ..
python3 run_bot.py
```

## 📖 Документация

- [🐳 DOCKER.md](docs/DOCKER.md) - Развёртывание в Docker (рекомендуется)
- [📘 QUICKSTART.md](docs/QUICKSTART.md) - Подробный гайд по запуску и использованию
- [🚀 DEPLOYMENT.md](docs/DEPLOYMENT.md) - Развертывание на VPS без Docker (legacy)
- [⚙️ Backend README](backend/README.md) - Детальное описание backend

## 🛠️ Технологии

- **Bot Framework**: aiogram 3.22.0 (async)
- **Database**: SQLAlchemy 2.0 + Alembic (async)
- **Translation**: deep-translator
- **Configuration**: pydantic-settings
- **Patterns**: Repository, Service Layer, Dependency Injection

## 📦 Deployment

### Требования к серверу

**Минимальные требования:**
- RAM: 512MB
- Disk: 5GB
- CPU: 1 core
- OS: Linux (Ubuntu 20.04+, Debian 11+, Alpine 3.15+)

**Рекомендуемые требования:**
- RAM: 2GB+
- Disk: 20GB+
- CPU: 2+ cores
- OS: Ubuntu 22.04 LTS или Debian 12

### Docker (рекомендуется)

```bash
# 1. Клонировать проект
git clone https://github.com/Poleno7682/telegram-bot-warsztat.git telegram-bot
cd telegram-bot

# 2. Настроить .env
cp backend/env.example backend/.env
nano backend/.env   # BOT_TOKEN, ADMIN_IDS, данные БД

# 3. Запустить
docker compose up -d --build
```

Миграции применяются автоматически при старте контейнера. Подробнее,
включая вариант с локальным PostgreSQL в Docker: [DOCKER.md](docs/DOCKER.md).

**Управление:**
```bash
docker compose logs -f bot   # логи
docker compose ps            # статус
docker compose down          # остановить
```

### VPS без Docker (legacy)

```bash
# 1. Клонировать проект
cd /opt
sudo git clone https://github.com/Poleno7682/telegram-bot-warsztat.git telegram-bot

# 2. Установить зависимости
cd telegram-bot/backend
sudo bash scripts/setup.sh

# 3. Установить как systemd service
sudo bash scripts/install_service.sh
```

**Управление сервисом:**
```bash
# Запуск
sudo systemctl start telegram-bot

# Статус
sudo systemctl status telegram-bot

# Логи (real-time)
sudo journalctl -u telegram-bot -f
```

Подробнее: [DEPLOYMENT.md](docs/DEPLOYMENT.md)

## 🔧 Разработка

### Добавление нового языка

1. Создайте файл `backend/app/core/i18n/locales/{код}.json`
2. Скопируйте структуру из `pl.json`
3. Переведите все ключи
4. Готово! Язык доступен в боте

### Добавление новой услуги (через бота)

1. Войдите как Администратор или Механик
2. Меню → Управление услугами
3. Добавить услугу
4. Укажите название (PL + RU), длительность, цену

### Добавление нового пользователя

**Через .env:**
```env
ADMIN_IDS=123456789,987654321
MECHANIC_IDS=111111111
USER_IDS=222222222
```

**Через бота** (только для Администратора):
1. Меню администратора → Управление пользователями
2. Добавить пользователя/механика
3. Ввести Telegram ID

## 🐛 Troubleshooting

### Бот не отвечает
- Проверьте `BOT_TOKEN` в `.env`
- Проверьте что бот запущен: `ps aux | grep python` или `systemctl status telegram-bot`

### "User not authorized"
- Добавьте свой Telegram ID в `ADMIN_IDS` в `.env`
- Узнать ID: @userinfobot в Telegram

### Ошибки БД
```bash
# Пересоздать БД
cd backend
python3 -m alembic downgrade base
python3 -m alembic upgrade head
```

## 📝 License

MIT

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

## 📧 Support

Для вопросов и поддержки создавайте Issues в GitHub.

