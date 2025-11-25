# Руководство по развертыванию на VPS

## Предварительные требования

- VPS с Ubuntu 20.04+ или Debian 11+
- Root доступ или sudo права
- Python 3.11 или выше
- Git

## Быстрое развертывание

### Автоматическая установка (рекомендуется)

```bash
# 1. Скачать проект
cd /opt
sudo git clone <your-repository-url> telegram-bot

# 2. Запустить скрипт установки
cd telegram-bot/backend
sudo bash scripts/setup.sh
```

Скрипт автоматически:
- Создаст пользователя для бота
- Установит все зависимости
- Настроит виртуальное окружение
- Создаст .env файл
- Запустит миграции БД
- Настроит systemd service

### Ручная установка

#### 1. Подготовка системы

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y python3 python3-pip git
```

#### 2. Создание пользователя

```bash
sudo useradd -r -s /bin/bash -d /opt/telegram-bot bot
```

#### 3. Клонирование проекта

```bash
cd /opt
sudo git clone <your-repository-url> telegram-bot
sudo chown -R bot:bot telegram-bot
```

#### 4. Установка Python зависимостей

```bash
cd /opt/telegram-bot/backend
sudo -u bot python3 -m pip install --upgrade pip --user
sudo -u bot python3 -m pip install -r requirements.txt --user
```

#### 5. Настройка конфигурации

```bash
# Создать .env файл
sudo cp env.example .env

# Редактировать конфигурацию
sudo nano .env
```

Обязательные параметры в `.env`:
```env
BOT_TOKEN=your_telegram_bot_token_from_@BotFather
DATABASE_URL=sqlite+aiosqlite:///./db/bot.db
ADMIN_IDS=123456789,987654321
```

#### 6. Инициализация базы данных

```bash
# Создать директорию для БД
sudo -u bot mkdir -p db

# Запустить миграции
sudo -u bot python3 -m alembic upgrade head
```

#### 7. Настройка systemd service

```bash
# Копировать service файл
sudo cp systemd/telegram-bot.service /etc/systemd/system/

# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable telegram-bot

# Запустить сервис
sudo systemctl start telegram-bot
```

#### 8. Проверка работы

```bash
# Проверить статус
sudo systemctl status telegram-bot

# Посмотреть логи
sudo journalctl -u telegram-bot -f
```

## Использование PostgreSQL (опционально)

Для production рекомендуется использовать PostgreSQL вместо SQLite:

### 1. Установка PostgreSQL

```bash
sudo apt install -y postgresql postgresql-contrib
```

### 2. Создание базы данных

```bash
# Войти в PostgreSQL
sudo -u postgres psql

# Создать БД и пользователя
CREATE DATABASE telegram_bot;
CREATE USER bot_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE telegram_bot TO bot_user;
\q
```

### 3. Обновление .env

```env
DATABASE_URL=postgresql+asyncpg://bot_user:your_secure_password@localhost:5432/telegram_bot
```

### 4. Запуск миграций

```bash
cd /opt/telegram-bot/backend
sudo -u bot python3 -m alembic upgrade head
```

## Управление сервисом

### Основные команды

```bash
# Запуск
sudo systemctl start telegram-bot

# Остановка
sudo systemctl stop telegram-bot

# Перезапуск
sudo systemctl restart telegram-bot

# Статус
sudo systemctl status telegram-bot

# Логи (real-time)
sudo journalctl -u telegram-bot -f

# Логи за последние 100 строк
sudo journalctl -u telegram-bot -n 100

# Логи за сегодня
sudo journalctl -u telegram-bot --since today
```

### Обновление бота

```bash
# Остановить бота
sudo systemctl stop telegram-bot

# Обновить код
cd /opt/telegram-bot
sudo -u bot git pull

# Обновить зависимости (если изменились)
cd backend
sudo -u bot python3 -m pip install -r requirements.txt --user

# Запустить миграции (если есть)
sudo -u bot python3 -m alembic upgrade head

# Запустить бота
sudo systemctl start telegram-bot
```

## Резервное копирование

### SQLite

```bash
# Создать backup
sudo -u bot cp /opt/telegram-bot/backend/db/bot.db /backup/bot.db.$(date +%Y%m%d_%H%M%S)

# Восстановить из backup
sudo -u bot cp /backup/bot.db.20241121_120000 /opt/telegram-bot/backend/db/bot.db
```

### PostgreSQL

```bash
# Создать backup
sudo -u postgres pg_dump telegram_bot > /backup/telegram_bot_$(date +%Y%m%d_%H%M%S).sql

# Восстановить из backup
sudo -u postgres psql telegram_bot < /backup/telegram_bot_20241121_120000.sql
```

## Мониторинг

### Настройка автоматических backups

Добавить в crontab:

```bash
sudo crontab -e
```

Добавить строку:
```cron
# Backup каждый день в 3:00
0 3 * * * cp /opt/telegram-bot/backend/db/bot.db /backup/bot.db.$(date +\%Y\%m\%d)
```

### Мониторинг логов

Настроить logrotate для управления размером логов:

```bash
sudo nano /etc/logrotate.d/telegram-bot
```

Содержимое:
```
/opt/telegram-bot/backend/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
}
```

## Безопасность

### Рекомендации:

1. **Ограничить доступ к .env файлу:**
```bash
sudo chmod 600 /opt/telegram-bot/backend/.env
```

2. **Использовать firewall:**
```bash
sudo ufw allow ssh
sudo ufw enable
```

3. **Регулярно обновлять систему:**
```bash
sudo apt update && sudo apt upgrade -y
```

4. **Использовать сильные пароли для БД**

5. **Настроить fail2ban для защиты SSH**

## Troubleshooting

### Бот не запускается

1. Проверить логи:
```bash
sudo journalctl -u telegram-bot -n 50
```

2. Проверить .env файл
3. Проверить что BOT_TOKEN корректный
4. Проверить доступ к БД

### Ошибки БД

```bash
# Проверить подключение к БД
sudo -u bot python3 -c "from app.config.database import engine; import asyncio; asyncio.run(engine.connect())"

# Пересоздать БД (осторожно! удалит все данные)
sudo -u bot python3 -m alembic downgrade base
sudo -u bot python3 -m alembic upgrade head
```

### Высокое использование ресурсов

1. Проверить количество активных соединений
2. Настроить connection pooling в database.py
3. Увеличить ресурсы VPS

## Поддержка

При возникновении проблем:
1. Проверьте логи: `sudo journalctl -u telegram-bot -f`
2. Проверьте статус: `sudo systemctl status telegram-bot`
3. Убедитесь что все зависимости установлены
4. Проверьте .env конфигурацию

