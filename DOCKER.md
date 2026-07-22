# Развёртывание в Docker

Бот запускается одним контейнером (`bot`), который при старте сам накатывает
Alembic-миграции и затем запускает `python -m app.main` (polling, без портов
наружу — HTTP не используется). Опционально можно поднять локальный
PostgreSQL вторым контейнером (`db`), если не используется внешняя managed БД.

## Требования

- Docker 24+
- Docker Compose v2 (команда `docker compose`, не `docker-compose`)

## 1. Настроить `.env`

Бот по-прежнему настраивается через `backend/.env` (как и раньше, без Docker):

```bash
cp backend/env.example backend/.env
nano backend/.env
```

Обязательно заполнить `BOT_TOKEN` и `ADMIN_IDS`. Для базы данных — см. ниже.

## 2. Выбрать базу данных

### Вариант А: внешняя/уже существующая БД (PostgreSQL или SQLite)

Ничего дополнительно делать не нужно — просто укажите в `backend/.env` то,
что указывали бы без Docker: либо `DATABASE_URL`, либо `DB_HOST`/`DB_PORT`/
`DB_USER`/`DB_PASSWORD`/`DB_NAME` для внешнего PostgreSQL, либо оставьте
`DATABASE_URL=sqlite+aiosqlite:///./db/bot.db` для SQLite (файл БД будет
жить в volume `bot_db`, переживает пересоздание контейнера).

```bash
docker compose up -d --build
```

### Вариант Б: локальный PostgreSQL в Docker

Если внешней БД нет, можно поднять PostgreSQL как второй контейнер (профиль
`local-db`, по умолчанию выключен, чтобы не заводить лишнюю БД тем, у кого
уже есть внешняя).

1. Задать пароль для локальной БД — создать `.env` **в корне репозитория**
   (рядом с `docker-compose.yml`, это отдельный файл от `backend/.env`):
   ```bash
   echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)" > .env
   ```
2. В `backend/.env` указать, что бот должен подключаться к контейнеру `db`
   (имя сервиса из `docker-compose.yml` резолвится Docker'ом как хостнейм):
   ```env
   DATABASE_URL=
   DB_HOST=db
   DB_PORT=5432
   DB_USER=bot_user
   DB_PASSWORD=<то же значение, что в POSTGRES_PASSWORD выше>
   DB_NAME=telegram_bot
   ```
3. Запустить оба контейнера:
   ```bash
   docker compose --profile local-db up -d --build
   ```

## Основные команды

```bash
# Запуск (в фоне)
docker compose up -d --build

# Логи (real-time)
docker compose logs -f bot

# Статус
docker compose ps

# Остановить
docker compose down

# Перезапуск после изменения кода/.env
docker compose up -d --build
```

## Миграции

Применяются автоматически при каждом старте контейнера (`alembic upgrade head`
в `backend/docker/entrypoint.sh`) — отдельно запускать не нужно. Чтобы
прогнать миграции вручную (например, посмотреть SQL или откатить):

```bash
docker compose run --rm bot alembic upgrade head
docker compose run --rm bot alembic downgrade -1
```

## Обновление бота

```bash
git pull
docker compose up -d --build
```

Пересборка образа подтянет новый код и зависимости; миграции применятся
автоматически при старте.

## Резервное копирование

### SQLite (volume `bot_db`)

```bash
docker compose exec bot cp /app/db/bot.db /app/db/bot.db.$(date +%Y%m%d_%H%M%S)
# или скопировать наружу:
docker cp $(docker compose ps -q bot):/app/db/bot.db ./backup_bot_$(date +%Y%m%d_%H%M%S).db
```

### Локальный PostgreSQL (профиль `local-db`)

```bash
docker compose exec db pg_dump -U bot_user telegram_bot > backup_$(date +%Y%m%d_%H%M%S).sql
```

## Логи

Логи идут в stdout контейнера (`docker compose logs -f bot`) и дополнительно
пишутся в volume `bot_logs` (`/app/logs` внутри контейнера), если приложение
настроено писать в файл — ротацию для volume настраивать не нужно, Docker
сам ограничивает размер stdout-логов при стандартном json-file драйвере
(см. `docker info` / настройки демона, при необходимости добавить
`logging: driver: json-file, options: {max-size: "10m", max-file: "3"}` в
`docker-compose.yml`).

## Файлы

- `backend/Dockerfile` — образ бота (Python 3.11-slim).
- `backend/docker/entrypoint.sh` — миграции + запуск.
- `backend/.dockerignore` — исключает `.env`, `db/`, тесты и т.п. из образа.
- `docker-compose.yml` (корень репозитория) — сервисы `bot` и опциональный `db`.
