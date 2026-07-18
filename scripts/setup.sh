#!/bin/bash
# scripts/setup.sh

set -e

echo "🚀 Setting up Odoo on VPS..."

# Create necessary directories
mkdir -p odoo/config nginx/conf.d addons certbot/www certbot/conf

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found! Create one from .env.example"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

# Replace domain in nginx config
sed -i "s/\${DOMAIN}/79.132.192.98/g" nginx/conf.d/odoo.conf

# Start services
echo "📦 Starting Docker containers..."
docker-compose down
docker-compose up -d

# Wait for Odoo to start
echo "⏳ Waiting for Odoo to be ready..."
sleep 10

# Check if Odoo is responding
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8069 | grep -q "200\|301\|302"; then
    echo "✅ Odoo is running!"
    echo "🌐 Access at: http://79.132.192.98 (or http://your-vps-ip)"
else
    echo "⚠️  Odoo might not be ready yet. Check logs with: docker-compose logs odoo"
fi

echo "📊 Container Status:"
docker-compose ps

echo ""
echo "🔧 Useful commands:"
echo "  - View logs: docker-compose logs -f"
echo "  - Restart: docker-compose restart"
echo "  - Stop: docker-compose down"
echo "  - Backup: ./scripts/backup.sh"