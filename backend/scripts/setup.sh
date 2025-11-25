#!/bin/bash

# Setup script for VPS deployment

set -e

echo "=== Telegram Bot Setup Script ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo"
    exit 1
fi

# Variables
BOT_USER="bot"
BOT_DIR="/opt/telegram-bot"

# 1. Create user for bot
echo "Creating user for bot..."
if ! id "$BOT_USER" &>/dev/null; then
    useradd -r -s /bin/bash -d "$BOT_DIR" "$BOT_USER"
    echo "User $BOT_USER created"
else
    echo "User $BOT_USER already exists"
fi

# 2. Create directory structure
echo "Creating directory structure..."
mkdir -p "$BOT_DIR"
chown -R "$BOT_USER:$BOT_USER" "$BOT_DIR"

# 3. Install system dependencies
echo "Installing system dependencies..."
apt update
apt install -y python3 python3-pip git postgresql postgresql-contrib

# 4. Setup PostgreSQL (optional)
read -p "Do you want to setup PostgreSQL? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Setting up PostgreSQL..."
    sudo -u postgres psql -c "CREATE DATABASE telegram_bot;"
    sudo -u postgres psql -c "CREATE USER bot_user WITH PASSWORD 'your_password_here';"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE telegram_bot TO bot_user;"
    echo "PostgreSQL setup complete"
fi

# 5. Clone repository
if [ ! -d "$BOT_DIR/.git" ]; then
    echo "Please manually clone your repository to $BOT_DIR"
    echo "Example: git clone <your-repo-url> $BOT_DIR"
else
    echo "Repository already cloned"
fi

# 6. Install Python dependencies
echo "Installing Python dependencies..."
sudo -u "$BOT_USER" python3 -m pip install --upgrade pip --user
sudo -u "$BOT_USER" python3 -m pip install -r "$BOT_DIR/backend/requirements.txt" --user

# 7. Setup .env file
if [ ! -f "$BOT_DIR/backend/.env" ]; then
    echo "Creating .env file..."
    cp "$BOT_DIR/backend/env.example" "$BOT_DIR/backend/.env"
    echo "Please edit $BOT_DIR/backend/.env with your configuration"
    nano "$BOT_DIR/backend/.env"
else
    echo ".env file already exists"
fi

# 8. Run database migrations
echo "Running database migrations..."
cd "$BOT_DIR/backend"
sudo -u "$BOT_USER" python3 -m alembic upgrade head

# 9. Install systemd service
echo "Installing systemd service..."
cp "$BOT_DIR/backend/systemd/telegram-bot.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable telegram-bot

# 10. Start service
read -p "Do you want to start the bot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl start telegram-bot
    echo "Bot started"
    echo "Check status with: systemctl status telegram-bot"
    echo "Check logs with: journalctl -u telegram-bot -f"
fi

echo ""
echo "=== Setup Complete ==="
echo "Bot directory: $BOT_DIR"
echo "Service name: telegram-bot"
echo ""
echo "Useful commands:"
echo "  Start bot:    systemctl start telegram-bot"
echo "  Stop bot:     systemctl stop telegram-bot"
echo "  Restart bot:  systemctl restart telegram-bot"
echo "  View status:  systemctl status telegram-bot"
echo "  View logs:    journalctl -u telegram-bot -f"

