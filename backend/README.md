# Telegram Bot - Auto Service Booking System

Backend для системы записи клиентов на автосервис через Telegram Bot.

## Особенности

- ✅ Асинхронная архитектура (aiogram 3.x + SQLAlchemy async)
- ✅ Многоязычность (польский/русский) с легким добавлением новых языков
- ✅ SOLID принципы
- ✅ Система ролей (Администратор, Механик, Пользователь)
- ✅ Workflow согласования записей
- ✅ Автоматический расчет свободного времени
- ✅ Автоматический перевод текста (googletrans)

## Структура проекта

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Настройки приложения
│   │   └── database.py            # Database configuration
│   ├── core/
│   │   ├── __init__.py
│   │   ├── i18n/                  # Система многоязычности
│   │   │   ├── __init__.py
│   │   │   ├── loader.py          # Загрузчик переводов
│   │   │   └── locales/           # JSON файлы переводов
│   │   │       ├── pl.json
│   │   │       └── ru.json
│   │   └── dependencies/          # DI контейнер
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── service.py
│   │   ├── booking.py
│   │   └── settings.py
│   ├── repositories/              # Repository pattern (SOLID)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── service.py
│   │   └── booking.py
│   ├── services/                  # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── booking_service.py
│   │   ├── time_service.py
│   │   └── translation_service.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers/              # Bot handlers
│   │   │   ├── __init__.py
│   │   │   ├── start.py
│   │   │   ├── admin.py
│   │   │   ├── mechanic.py
│   │   │   └── user.py
│   │   ├── middlewares/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   └── i18n.py
│   │   ├── keyboards/
│   │   │   ├── __init__.py
│   │   │   └── inline.py
│   │   ├── states/
│   │   │   ├── __init__.py
│   │   │   └── booking.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── helpers.py
│   └── utils/
│       ├── __init__.py
│       └── logger.py
├── alembic/                       # Database migrations
│   ├── versions/
│   └── env.py
├── systemd/
│   └── telegram-bot.service       # Systemd service file
├── .env.example
├── .gitignore
├── requirements.txt
├── alembic.ini
└── README.md
```

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd backend
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env файл, указав BOT_TOKEN и ADMIN_IDS
```

### 5. Инициализация базы данных

```bash
alembic upgrade head
```

### 6. Запуск бота

```bash
python -m app.main
```

## Деплой на VPS (Linux)

### 1. Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python 3.11+
sudo apt install python3 python3-pip python3-venv -y

# Установка PostgreSQL (опционально)
sudo apt install postgresql postgresql-contrib -y
```

### 2. Копирование проекта

```bash
# Загрузка проекта на сервер
cd /opt
sudo git clone <repository-url> telegram-bot
cd telegram-bot/backend
```

### 3. Настройка виртуального окружения

```bash
sudo python3 -m venv venv
sudo chown -R $USER:$USER venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Настройка .env

```bash
sudo cp .env.example .env
sudo nano .env  # Редактирование конфигурации
```

### 5. Настройка Systemd Service

```bash
sudo cp systemd/telegram-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

### 6. Проверка статуса

```bash
sudo systemctl status telegram-bot
```

### 7. Просмотр логов

```bash
journalctl -u telegram-bot -f
```

## Роли пользователей

### Администратор
- Назначается через ADMIN_IDS в .env
- Может назначать механиков и пользователей
- Может управлять услугами и настройками
- Может создавать записи (но не принимает их как механик)

### Механик
- Назначается через MECHANIC_IDS в .env или через бота
- Может создавать записи
- Принимает/отклоняет/изменяет время записей
- Может управлять услугами и настройками

### Пользователь
- Назначается через USER_IDS в .env или через бота
- Может только создавать новые записи
- Участвует в согласовании времени с механиками

## Workflow записи

1. **Создание записи** - Пользователь создает запись с деталями (авто, клиент, услуга, время)
2. **Уведомление механиков** - Всем механикам отправляется уведомление
3. **Действия механика**:
   - **Принять** → Запись сохраняется, всем отправляется уведомление
   - **Отклонить** → Всем отправляется уведомление об отклонении
   - **Изменить время** → Механик предлагает новое время
4. **Согласование времени** - Пользователь и механик согласовывают время
5. **Сохранение** - После согласования запись сохраняется в БД

## Многоязычность

Все тексты хранятся в JSON файлах:
- `app/core/i18n/locales/pl.json` - Польский
- `app/core/i18n/locales/ru.json` - Русский

Для добавления нового языка:
1. Создайте файл `app/core/i18n/locales/{код_языка}.json`
2. Скопируйте структуру из существующего файла
3. Переведите все ключи

## Разработка

### Создание новой миграции

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Тестирование

```bash
pytest
```

## Лицензия

MIT

