#!/bin/bash
# Скрипт установки Telegram Bot как systemd service
# Использование: sudo bash install_service.sh

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функции для вывода
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    error "Этот скрипт должен быть запущен с правами root (sudo)"
    exit 1
fi

# Переменные
BOT_USER="bot"
BOT_GROUP="bot"
SERVICE_NAME="telegram-bot"
SERVICE_FILE="telegram-bot.service"

# Определение пути к проекту
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$PROJECT_DIR/.." && pwd)"

# Проверка наличия systemd
if ! command -v systemctl &> /dev/null; then
    error "systemd не найден. Этот скрипт работает только с systemd."
    exit 1
fi

info "=== Установка Telegram Bot как systemd service ==="
echo ""

# Проверка существования service файла
SERVICE_SOURCE="$PROJECT_DIR/systemd/$SERVICE_FILE"
if [ ! -f "$SERVICE_SOURCE" ]; then
    error "Service файл не найден: $SERVICE_SOURCE"
    exit 1
fi

# 1. Создание пользователя и группы
info "1. Проверка пользователя и группы..."
if ! id "$BOT_USER" &>/dev/null; then
    info "Создание пользователя $BOT_USER..."
    useradd -r -s /bin/bash -d "$ROOT_DIR" -m "$BOT_USER" || {
        error "Не удалось создать пользователя $BOT_USER"
        exit 1
    }
    info "Пользователь $BOT_USER создан"
else
    info "Пользователь $BOT_USER уже существует"
fi

# 2. Настройка прав доступа к проекту
info "2. Настройка прав доступа..."
if [ -d "$ROOT_DIR" ]; then
    chown -R "$BOT_USER:$BOT_GROUP" "$ROOT_DIR"
    chmod -R 755 "$ROOT_DIR"
    info "Права доступа установлены для $ROOT_DIR"
else
    warn "Директория проекта не найдена: $ROOT_DIR"
    warn "Убедитесь, что проект находится в правильном месте"
fi

# 3. Проверка наличия .env файла
info "3. Проверка конфигурации..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    warn ".env файл не найден!"
    if [ -f "$PROJECT_DIR/env.example" ]; then
        info "Создание .env из примера..."
        cp "$PROJECT_DIR/env.example" "$PROJECT_DIR/.env"
        chown "$BOT_USER:$BOT_GROUP" "$PROJECT_DIR/.env"
        chmod 600 "$PROJECT_DIR/.env"
        warn "Пожалуйста, отредактируйте $PROJECT_DIR/.env и укажите BOT_TOKEN и ADMIN_IDS"
        warn "Команда: sudo nano $PROJECT_DIR/.env"
    else
        error "env.example не найден. Создайте .env файл вручную."
    fi
else
    info ".env файл найден"
    chown "$BOT_USER:$BOT_GROUP" "$PROJECT_DIR/.env"
    chmod 600 "$PROJECT_DIR/.env"
fi

# 4. Копирование service файла
info "4. Установка systemd service..."
cp "$SERVICE_SOURCE" "/etc/systemd/system/$SERVICE_NAME.service"
info "Service файл скопирован в /etc/systemd/system/$SERVICE_NAME.service"

# 5. Обновление путей в service файле (если нужно)
# Проверяем, нужно ли обновить WorkingDirectory
CURRENT_WD=$(grep "^WorkingDirectory=" "/etc/systemd/system/$SERVICE_NAME.service" | cut -d'=' -f2)
if [ "$CURRENT_WD" != "$PROJECT_DIR" ]; then
    info "Обновление WorkingDirectory в service файле..."
    sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|" "/etc/systemd/system/$SERVICE_NAME.service"
fi

# 6. Перезагрузка systemd
info "5. Перезагрузка systemd daemon..."
systemctl daemon-reload
info "systemd daemon перезагружен"

# 7. Включение автозапуска
info "6. Включение автозапуска..."
systemctl enable "$SERVICE_NAME"
info "Автозапуск включен"

# 8. Проверка статуса
info "7. Проверка конфигурации service..."
if systemctl is-enabled "$SERVICE_NAME" &>/dev/null; then
    info "Service успешно настроен и включен"
else
    warn "Service не включен. Проверьте конфигурацию."
fi

echo ""
info "=== Установка завершена ==="
echo ""
echo "Полезные команды:"
echo "  Запустить бота:    sudo systemctl start $SERVICE_NAME"
echo "  Остановить бота:   sudo systemctl stop $SERVICE_NAME"
echo "  Перезапустить:     sudo systemctl restart $SERVICE_NAME"
echo "  Статус:            sudo systemctl status $SERVICE_NAME"
echo "  Логи:              sudo journalctl -u $SERVICE_NAME -f"
echo "  Логи (последние):  sudo journalctl -u $SERVICE_NAME -n 50"
echo ""
warn "ВАЖНО: Перед запуском убедитесь, что:"
warn "  1. .env файл настроен (BOT_TOKEN, ADMIN_IDS)"
warn "  2. База данных инициализирована (alembic upgrade head)"
warn "  3. Python зависимости установлены"
echo ""
read -p "Запустить бота сейчас? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    info "Запуск бота..."
    systemctl start "$SERVICE_NAME"
    sleep 2
    systemctl status "$SERVICE_NAME" --no-pager
    echo ""
    info "Используйте 'sudo journalctl -u $SERVICE_NAME -f' для просмотра логов"
fi

